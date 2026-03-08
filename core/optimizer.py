"""
╔══════════════════════════════════════════════════════════════════╗
║           Walk-Forward Strategy Optimizer                        ║
╚══════════════════════════════════════════════════════════════════╝
Grid search with in-sample training and out-of-sample validation.
"""
from __future__ import annotations

import itertools
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import STRATEGY_REGISTRY
from core.backtest_engine import BacktestEngine, BacktestMetrics

log = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of a single parameter combination optimization."""
    params: Dict[str, Any]
    in_sample_metrics: Dict[str, Any]
    out_of_sample_metrics: Dict[str, Any]
    composite_score: float = 0.0
    rank: int = 0


@dataclass
class OptimizationJob:
    """Represents an active optimization job."""
    job_id: str
    strategy_id: str
    symbol: str
    param_grid: Dict[str, List[Any]]
    train_from: datetime
    train_to: datetime
    test_from: datetime
    test_to: datetime
    status: str = "pending"  # pending, running, completed, error
    progress_pct: float = 0.0
    results: List[OptimizationResult] = field(default_factory=list)
    best_params: Dict[str, Any] = field(default_factory=dict)
    warning: str = ""
    error: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WalkForwardOptimizer:
    """
    Walk-forward optimization: train on in-sample data, validate on out-of-sample.

    Usage:
        optimizer = WalkForwardOptimizer()
        results = optimizer.optimize(
            strategy_id="A",
            symbol="XAUUSD",
            param_grid={"ema_period": [20, 50], "rsi_threshold": [30, 40]},
            train_from=datetime(2023, 1, 1),
            train_to=datetime(2023, 12, 31),
            test_from=datetime(2024, 1, 1),
            test_to=datetime(2024, 3, 31),
        )
    """

    MAX_COMBINATIONS = 500

    def __init__(self) -> None:
        self._train_pct = float(os.getenv("OPTIMIZER_TRAIN_PCT", "0.75"))

    def optimize(
        self,
        strategy_id: str,
        symbol: str,
        param_grid: Dict[str, List[Any]],
        train_from: datetime,
        train_to: datetime,
        test_from: datetime,
        test_to: datetime,
        progress_queue: Optional[Any] = None,
    ) -> List[OptimizationResult]:
        """
        Run walk-forward optimization.

        Args:
            strategy_id: Strategy to optimize
            symbol: MT5 symbol
            param_grid: Dict of param_name -> list of values
            train_from/train_to: In-sample period
            test_from/test_to: Out-of-sample period
            progress_queue: Optional queue to report progress

        Returns:
            List of OptimizationResult sorted by composite_score descending
        """
        # Generate all parameter combinations
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*value_lists))

        if len(combinations) > self.MAX_COMBINATIONS:
            raise ValueError(
                f"Too many parameter combinations ({len(combinations)}). "
                f"Maximum allowed: {self.MAX_COMBINATIONS}"
            )

        total = len(combinations)
        log.info(
            "Starting optimization for %s: %d combinations, "
            "train=%s to %s, test=%s to %s",
            strategy_id, total,
            train_from.date(), train_to.date(),
            test_from.date(), test_to.date(),
        )

        # Get strategy meta and class
        meta = STRATEGY_REGISTRY.get(strategy_id)
        if not meta:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        from strategies import STRATEGY_CLASSES
        strategy_cls = STRATEGY_CLASSES.get(strategy_id)
        if not strategy_cls:
            raise ValueError(f"Strategy class not found for: {strategy_id}")

        # Phase 1: In-sample training
        in_sample_results = []
        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))

            try:
                # Instantiate strategy with override params
                strategy = self._create_strategy_with_params(
                    strategy_cls, meta, params
                )

                # Run backtest on training period
                engine = BacktestEngine()
                results = engine.backtest(
                    strategy=strategy,
                    symbol=symbol,
                    timeframes=meta.timeframes,
                    from_date=train_from,
                    to_date=train_to,
                    starting_capital=100000,
                )

                in_sample_results.append({
                    "params": params,
                    "metrics": results.to_dict() if hasattr(results, "to_dict") else results,
                })

            except Exception as exc:
                log.warning("In-sample backtest failed for params %s: %s", params, exc)
                in_sample_results.append({
                    "params": params,
                    "metrics": {"sharpe_ratio": -999, "error": str(exc)},
                })

            # Report progress
            pct = (i + 1) / total * 50  # First 50% is in-sample
            if progress_queue:
                try:
                    progress_queue.put({"pct": pct})
                except Exception:
                    pass

        # Select top-10 by Sharpe ratio
        sorted_in_sample = sorted(
            in_sample_results,
            key=lambda x: x["metrics"].get("sharpe_ratio", -999),
            reverse=True,
        )[:10]

        # Phase 2: Out-of-sample validation
        oos_results = []
        for i, isr in enumerate(sorted_in_sample):
            params = isr["params"]

            try:
                strategy = self._create_strategy_with_params(
                    strategy_cls, meta, params
                )

                engine = BacktestEngine()
                results = engine.backtest(
                    strategy=strategy,
                    symbol=symbol,
                    timeframes=meta.timeframes,
                    from_date=test_from,
                    to_date=test_to,
                    starting_capital=100000,
                )

                metrics = results.to_dict() if hasattr(results, "to_dict") else results

                # Calculate composite score
                pf = metrics.get("profit_factor", 0)
                wr = metrics.get("win_rate", 0) / 100.0
                dd = max(metrics.get("max_drawdown_pct", 0) / 100.0, 0.01)
                composite = (pf * wr) / dd

                oos_results.append(OptimizationResult(
                    params=params,
                    in_sample_metrics=isr["metrics"],
                    out_of_sample_metrics=metrics,
                    composite_score=composite,
                ))

            except Exception as exc:
                log.warning("OOS backtest failed for params %s: %s", params, exc)
                oos_results.append(OptimizationResult(
                    params=params,
                    in_sample_metrics=isr["metrics"],
                    out_of_sample_metrics={"error": str(exc), "net_profit": -1},
                    composite_score=-999,
                ))

            # Report progress
            pct = 50 + (i + 1) / 10 * 50  # Remaining 50% is OOS
            if progress_queue:
                try:
                    progress_queue.put({"pct": pct})
                except Exception:
                    pass

        # Sort by composite score
        oos_results.sort(key=lambda x: x.composite_score, reverse=True)

        # Assign ranks
        for i, result in enumerate(oos_results):
            result.rank = i + 1

        return oos_results

    def _create_strategy_with_params(self, strategy_cls, meta, params: Dict[str, Any]):
        """
        Create a strategy instance with override parameters.

        Strategies may accept params via constructor or have settable attributes.
        """
        # Try passing params to constructor
        try:
            return strategy_cls(meta, **params)
        except TypeError:
            pass

        # Try creating then setting attributes
        try:
            instance = strategy_cls(meta)
            for key, value in params.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            return instance
        except Exception as exc:
            log.warning("Could not create strategy with params: %s", exc)
            return strategy_cls(meta)


class OptimizationJobManager:
    """
    Manages optimization jobs with background execution.

    Usage:
        mgr = OptimizationJobManager()
        job_id = mgr.submit("A", "XAUUSD", {"ema_period": [20, 50]}, ...)
        status = mgr.get_status(job_id)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, OptimizationJob] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        strategy_id: str,
        symbol: str,
        param_grid: Dict[str, List[Any]],
        train_from: datetime,
        train_to: datetime,
        test_from: datetime,
        test_to: datetime,
    ) -> str:
        """
        Submit an optimization job for background execution.

        Returns:
            job_id for tracking
        """
        # Validate param combinations
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = list(itertools.product(*value_lists))

        if len(combinations) > WalkForwardOptimizer.MAX_COMBINATIONS:
            raise ValueError(
                f"Too many parameter combinations ({len(combinations)}). "
                f"Maximum: {WalkForwardOptimizer.MAX_COMBINATIONS}"
            )

        job_id = str(uuid.uuid4())[:8]
        job = OptimizationJob(
            job_id=job_id,
            strategy_id=strategy_id,
            symbol=symbol,
            param_grid=param_grid,
            train_from=train_from,
            train_to=train_to,
            test_from=test_from,
            test_to=test_to,
            status="pending",
            started_at=datetime.now(),
        )

        with self._lock:
            self._jobs[job_id] = job

        # Start background thread
        thread = threading.Thread(
            target=self._run_optimization,
            args=(job_id,),
            daemon=True,
        )
        thread.start()

        log.info("Submitted optimization job %s for strategy %s", job_id, strategy_id)
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get current status of an optimization job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"error": f"Job not found: {job_id}"}

            return {
                "job_id": job.job_id,
                "strategy_id": job.strategy_id,
                "status": job.status,
                "progress_pct": job.progress_pct,
                "results": [
                    {
                        "rank": r.rank,
                        "params": r.params,
                        "in_sample_pf": r.in_sample_metrics.get("profit_factor", 0),
                        "in_sample_wr": r.in_sample_metrics.get("win_rate", 0),
                        "oos_pf": r.out_of_sample_metrics.get("profit_factor", 0),
                        "oos_wr": r.out_of_sample_metrics.get("win_rate", 0),
                        "oos_dd": r.out_of_sample_metrics.get("max_drawdown_pct", 0),
                        "oos_net": r.out_of_sample_metrics.get("net_profit", 0),
                        "composite_score": r.composite_score,
                    }
                    for r in job.results
                ],
                "best_params": job.best_params,
                "warning": job.warning,
                "error": job.error,
            }

    def _run_optimization(self, job_id: str) -> None:
        """Background worker to run optimization."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

        try:
            job.status = "running"

            optimizer = WalkForwardOptimizer()
            results = optimizer.optimize(
                strategy_id=job.strategy_id,
                symbol=job.symbol,
                param_grid=job.param_grid,
                train_from=job.train_from,
                train_to=job.train_to,
                test_from=job.test_from,
                test_to=job.test_to,
            )

            job.results = results
            job.progress_pct = 100.0

            # Set best params
            if results and results[0].composite_score > 0:
                job.best_params = results[0].params
            else:
                job.warning = "No profitable configuration found in out-of-sample period"

            job.status = "completed"
            job.completed_at = datetime.now()
            log.info("Optimization job %s completed: %d results", job_id, len(results))

        except Exception as exc:
            log.error("Optimization job %s failed: %s", job_id, exc)
            job.status = "error"
            job.error = str(exc)
