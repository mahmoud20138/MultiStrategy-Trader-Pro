"""
╔══════════════════════════════════════════════════════════════════╗
║        Backtesting Engine — Historical Replay & Metrics          ║
╚══════════════════════════════════════════════════════════════════╝
Enables strategy backtesting against historical MT5 data with:
- Parquet caching for fast re-runs
- Vectorized indicator pre-computation
- Bar-by-bar signal replay
- Professional metrics (Sharpe, Sortino, CAGR, etc.)
- Multiprocessing for non-blocking execution
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd

# PyArrow is required for Parquet caching
try:
    import pyarrow  # noqa: F401
except ImportError:
    raise ImportError(
        "pyarrow is required for Parquet caching. Install with: pip install pyarrow>=14.0"
    )

from config import CONFIG, TF, STRATEGY_REGISTRY
from core.mt5_connection import get_mt5

log = logging.getLogger("backtest")

# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class BacktestTrade:
    """Single trade executed during backtest."""
    trade_id: str
    strategy_id: str
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry_time: datetime
    entry_price: float
    entry_bar_idx: int
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_bar_idx: Optional[int] = None
    exit_reason: str = ""  # "SL_HIT", "TP_HIT", "END_OF_DATA"
    quantity: float = 1.0
    profit: float = 0.0
    rr_achieved: float = 0.0
    confluence_score: int = 0

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
        }


@dataclass
class BacktestResults:
    """Complete backtest output."""
    run_id: str
    strategy_id: str
    strategy_name: str
    symbol: str
    from_date: str
    to_date: str
    starting_capital: float
    final_capital: float
    status: str  # "completed", "no_trades", "error"

    # Trade log
    trades: List[BacktestTrade] = field(default_factory=list)

    # Equity curve (list of {time, equity})
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)

    # Metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    recovery_factor: float = 0.0
    roi_pct: float = 0.0
    cagr_pct: float = 0.0
    max_consecutive_losses: int = 0
    avg_rr_achieved: float = 0.0
    avg_confluence_score: float = 0.0

    # Timing
    run_timestamp: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "trades": [t.to_dict() for t in self.trades],
        }


# ══════════════════════════════════════════════════════════════════
# HISTORICAL DATA FETCHER (T009)
# ══════════════════════════════════════════════════════════════════

class HistoricalDataFetcher:
    """
    Fetches historical MT5 data with Parquet caching.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._cache_dir = Path(cache_dir or (Path(CONFIG.db_path).parent / "backtest_cache"))
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._mt5 = get_mt5()

    def fetch(
        self,
        symbol: str,
        timeframe: int,
        from_date: datetime,
        to_date: datetime,
        use_cache: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical rates from MT5, chunked at 1-year intervals.
        Caches as Parquet for fast re-runs.
        """
        tf_name = TF.name(timeframe)
        cache_file = self._cache_dir / f"{symbol}_{tf_name}_{from_date:%Y%m%d}_{to_date:%Y%m%d}.parquet"

        # Try cache first
        if use_cache and cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                log.debug("Loaded %d bars from cache: %s", len(df), cache_file.name)
                return df
            except Exception as e:
                log.warning("Failed to read cache %s: %s", cache_file.name, e)

        # Fetch from MT5 in chunks
        all_rates = []
        current_start = from_date

        while current_start < to_date:
            chunk_end = min(current_start + timedelta(days=365), to_date)

            try:
                rates = self._mt5.copy_rates_range(symbol, timeframe, current_start, chunk_end)
                if rates is not None and len(rates) > 0:
                    all_rates.append(rates)
                    log.debug("Fetched %d bars %s -> %s", len(rates), current_start.date(), chunk_end.date())
            except Exception as e:
                log.warning("Failed to fetch %s %s %s: %s", symbol, tf_name, current_start.date(), e)

            current_start = chunk_end

        if not all_rates:
            log.warning("No data fetched for %s %s %s - %s", symbol, tf_name, from_date.date(), to_date.date())
            return None

        # Combine chunks
        import numpy as np
        combined = np.concatenate(all_rates)
        df = pd.DataFrame(combined)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time").sort_index()
        df = df[~df.index.duplicated(keep="first")]  # Remove duplicates at chunk boundaries

        # Cache it
        try:
            df.to_parquet(cache_file, index=True)
            log.info("Cached %d bars to %s", len(df), cache_file.name)
        except Exception as e:
            log.warning("Failed to write cache: %s", e)

        return df


# ══════════════════════════════════════════════════════════════════
# BACKTEST METRICS (T011)
# ══════════════════════════════════════════════════════════════════

class BacktestMetrics:
    """Static methods for calculating performance metrics."""

    @staticmethod
    def calculate_all(
        trades: List[BacktestTrade],
        starting_capital: float,
        equity_curve: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate all metrics from trades and equity curve."""

        if not trades:
            return {"total_trades": 0, "status": "no_trades"}

        # Basic counts
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.profit > 0)
        losing_trades = sum(1 for t in trades if t.profit <= 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # P&L
        profits = [t.profit for t in trades if t.profit > 0]
        losses = [abs(t.profit) for t in trades if t.profit <= 0]
        gross_profit = sum(profits) if profits else 0
        gross_loss = sum(losses) if losses else 0
        net_profit = gross_profit - gross_loss

        # Profit factor
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        # Averages
        avg_win = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0

        # Expectancy
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss) if total_trades > 0 else 0

        # Drawdown from equity curve
        if equity_curve:
            equity_series = pd.Series([e["equity"] for e in equity_curve])
            running_max = equity_series.expanding().max()
            drawdown = running_max - equity_series
            drawdown_pct = (drawdown / running_max * 100).replace([np.inf, -np.inf], 0).fillna(0)
            max_drawdown_abs = float(drawdown.max())
            max_drawdown_pct = float(drawdown_pct.max())
        else:
            max_drawdown_abs = 0
            max_drawdown_pct = 0

        # Sharpe Ratio (annualized, 2% risk-free)
        if equity_curve and len(equity_curve) > 1:
            equity_series = pd.Series([e["equity"] for e in equity_curve])
            returns = equity_series.pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                rf_daily = 0.02 / 252  # 2% annual, daily
                excess_returns = returns - rf_daily
                sharpe_ratio = float((excess_returns.mean() / returns.std()) * np.sqrt(252))
            else:
                sharpe_ratio = 0

            # Sortino Ratio (downside std only)
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0 and downside_returns.std() > 0:
                sortino_ratio = float((excess_returns.mean() / downside_returns.std()) * np.sqrt(252))
            else:
                sortino_ratio = sharpe_ratio if sharpe_ratio > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0

        # Recovery Factor
        recovery_factor = net_profit / max_drawdown_abs if max_drawdown_abs > 0 else 0

        # ROI
        roi_pct = (net_profit / starting_capital * 100) if starting_capital > 0 else 0

        # CAGR (simplified: annualize total return)
        if equity_curve:
            days = len(equity_curve)
            years = days / 252
            if years > 0:
                final_equity = equity_curve[-1]["equity"]
                total_return = final_equity / starting_capital - 1
                cagr_pct = ((1 + total_return) ** (1 / years) - 1) * 100 if total_return > -1 else 0
            else:
                cagr_pct = 0
        else:
            cagr_pct = 0

        # Max consecutive losses
        consec_losses = 0
        max_consec_losses = 0
        for t in trades:
            if t.profit <= 0:
                consec_losses += 1
                max_consec_losses = max(max_consec_losses, consec_losses)
            else:
                consec_losses = 0

        # Average R:R achieved
        rr_values = [t.rr_achieved for t in trades if t.rr_achieved > 0]
        avg_rr_achieved = float(np.mean(rr_values)) if rr_values else 0

        # Average confluence score
        scores = [t.confluence_score for t in trades]
        avg_confluence_score = float(np.mean(scores)) if scores else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_profit": round(net_profit, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "max_drawdown_abs": round(max_drawdown_abs, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "recovery_factor": round(recovery_factor, 2),
            "roi_pct": round(roi_pct, 2),
            "cagr_pct": round(cagr_pct, 2),
            "max_consecutive_losses": max_consecutive_losses,
            "avg_rr_achieved": round(avg_rr_achieved, 2),
            "avg_confluence_score": round(avg_confluence_score, 1),
        }


# ══════════════════════════════════════════════════════════════════
# BACKTEST ENGINE (T010)
# ══════════════════════════════════════════════════════════════════

class BacktestEngine:
    """
    Runs backtests: vectorized indicator prep + bar-by-bar replay.
    """

    def __init__(self):
        self._fetcher = HistoricalDataFetcher()

    def backtest(
        self,
        strategy: "BaseStrategy",
        symbol: str,
        timeframes: List[int],
        from_date: datetime,
        to_date: datetime,
        starting_capital: float = 100000,
        prepared_data: Optional[Dict[int, pd.DataFrame]] = None,
    ) -> BacktestResults:
        """
        Execute backtest for a strategy over historical data.
        """
        import time
        start_time = time.time()

        run_id = str(uuid.uuid4())[:8]
        strategy_meta = STRATEGY_REGISTRY.get(strategy.id)

        results = BacktestResults(
            run_id=run_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            symbol=symbol,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            starting_capital=starting_capital,
            final_capital=starting_capital,
            status="completed",
            run_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Fetch or use provided data
        if prepared_data is None:
            data = {}
            for tf in timeframes:
                df = self._fetcher.fetch(symbol, tf, from_date, to_date)
                if df is None:
                    log.warning("No data for %s %s, skipping", symbol, TF.name(tf))
                    continue
                data[tf] = df
        else:
            data = prepared_data

        if not data:
            results.status = "error"
            results.duration_seconds = time.time() - start_time
            return results

        # Phase 1: Prepare indicators (vectorized)
        prepared_data = self._prepare_indicators(data)

        # Get the primary timeframe (smallest)
        primary_tf = min(prepared_data.keys())
        primary_df = prepared_data[primary_tf]

        if len(primary_df) < 50:
            results.status = "error"
            results.duration_seconds = time.time() - start_time
            return results

        # Phase 2: Bar-by-bar replay
        capital = starting_capital
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict[str, Any]] = []
        open_trade: Optional[BacktestTrade] = None

        lookback = 200  # Bars needed for indicators

        for bar_idx in range(lookback, len(primary_df)):
            current_time = primary_df.index[bar_idx]
            current_close = primary_df["close"].iloc[bar_idx]

            # Get bar slice for strategy analysis
            bar_slice = self._get_bar_slice(prepared_data, bar_idx, lookback)

            # Check open trade exits first
            if open_trade is not None:
                exit_reason = None
                exit_price = None

                if open_trade.direction == "BUY":
                    if current_close <= open_trade.stop_loss:
                        exit_reason = "SL_HIT"
                        exit_price = open_trade.stop_loss
                    elif current_close >= open_trade.take_profit:
                        exit_reason = "TP_HIT"
                        exit_price = open_trade.take_profit
                else:  # SELL
                    if current_close >= open_trade.stop_loss:
                        exit_reason = "SL_HIT"
                        exit_price = open_trade.stop_loss
                    elif current_close <= open_trade.take_profit:
                        exit_reason = "TP_HIT"
                        exit_price = open_trade.take_profit

                if exit_reason:
                    open_trade.exit_time = current_time
                    open_trade.exit_price = exit_price
                    open_trade.exit_bar_idx = bar_idx
                    open_trade.exit_reason = exit_reason

                    # Calculate P&L
                    if open_trade.direction == "BUY":
                        open_trade.profit = (exit_price - open_trade.entry_price) * open_trade.quantity
                    else:
                        open_trade.profit = (open_trade.entry_price - exit_price) * open_trade.quantity

                    capital += open_trade.profit
                    open_trade.rr_achieved = abs(open_trade.profit) / abs(open_trade.entry_price - open_trade.stop_loss) if abs(open_trade.entry_price - open_trade.stop_loss) > 0 else 0
                    trades.append(open_trade)
                    open_trade = None

            # Record equity
            equity_curve.append({
                "time": current_time.isoformat(),
                "equity": capital,
            })

            # Skip if trade already open
            if open_trade is not None:
                continue

            # Analyze for new signal
            try:
                signal = strategy.analyze(bar_slice)
                if signal is None:
                    continue

                # Open new trade
                trade_id = f"{run_id}_{len(trades)+1}"
                open_trade = BacktestTrade(
                    trade_id=trade_id,
                    strategy_id=strategy.id,
                    symbol=symbol,
                    direction=signal.direction.value,
                    entry_time=current_time,
                    entry_price=signal.entry_price,
                    entry_bar_idx=bar_idx,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    confluence_score=signal.score,
                )

            except Exception as e:
                log.debug("Strategy %s analyze error at %s: %s", strategy.id, current_time, e)
                continue

        # Close any remaining open trade at end of data
        if open_trade is not None:
            final_close = primary_df["close"].iloc[-1]
            open_trade.exit_time = primary_df.index[-1]
            open_trade.exit_price = final_close
            open_trade.exit_bar_idx = len(primary_df) - 1
            open_trade.exit_reason = "END_OF_DATA"

            if open_trade.direction == "BUY":
                open_trade.profit = (final_close - open_trade.entry_price) * open_trade.quantity
            else:
                open_trade.profit = (open_trade.entry_price - final_close) * open_trade.quantity

            capital += open_trade.profit
            trades.append(open_trade)

        # Calculate metrics
        results.trades = trades
        results.equity_curve = equity_curve
        results.final_capital = capital

        metrics = BacktestMetrics.calculate_all(trades, starting_capital, equity_curve)
        for key, value in metrics.items():
            if hasattr(results, key):
                setattr(results, key, value)

        results.duration_seconds = round(time.time() - start_time, 2)

        log.info(
            "Backtest %s: %d trades, %.1f%% win rate, $%.2f net, %.2fx PF",
            run_id, results.total_trades, results.win_rate, results.net_profit, results.profit_factor
        )

        return results

    def _prepare_indicators(self, data: Dict[int, pd.DataFrame]) -> Dict[int, pd.DataFrame]:
        """Pre-compute all indicators for each timeframe."""
        from indicators.trend import add_ema, add_sma
        from indicators.momentum import add_rsi, add_macd, add_stochastic
        from indicators.volatility import add_atr, add_bbands
        from indicators.volume import add_obv
        from indicators.structure import add_supertrend, add_vwap

        prepared = {}
        for tf, df in data.items():
            df = df.copy()

            # Trend
            try:
                df = add_ema(df, 9)
                df = add_ema(df, 21)
                df = add_ema(df, 50)
                df = add_ema(df, 200)
                df = add_sma(df, 20)
            except Exception:
                pass

            # Momentum
            try:
                df = add_rsi(df, 14)
                df = add_macd(df)
                df = add_stochastic(df)
            except Exception:
                pass

            # Volatility
            try:
                df = add_atr(df, 14)
                df = add_bbands(df, 20)
            except Exception:
                pass

            # Volume
            try:
                df = add_obv(df)
            except Exception:
                pass

            # Structure
            try:
                df = add_supertrend(df, 10, 3)
                df = add_vwap(df)
            except Exception:
                pass

            prepared[tf] = df

        return prepared

    def _get_bar_slice(
        self,
        data: Dict[int, pd.DataFrame],
        bar_idx: int,
        lookback: int,
    ) -> Dict[int, pd.DataFrame]:
        """Get a slice of data ending at bar_idx with lookback bars."""
        primary_tf = min(data.keys())
        primary_df = data[primary_tf]

        start_idx = max(0, bar_idx - lookback)
        end_idx = bar_idx + 1

        # Get primary TF slice
        primary_slice = primary_df.iloc[start_idx:end_idx].copy()

        # For other TFs, get all data up to current time
        result = {primary_tf: primary_slice}
        current_time = primary_df.index[bar_idx]

        for tf, df in data.items():
            if tf == primary_tf:
                continue
            # Get data up to current time
            tf_slice = df[df.index <= current_time].tail(lookback).copy()
            if len(tf_slice) > 0:
                result[tf] = tf_slice

        return result


# ══════════════════════════════════════════════════════════════════
# BACKTEST RESULTS DB (T012)
# ══════════════════════════════════════════════════════════════════

class BacktestResultsDB:
    """
    SQLite storage for backtest results (separate from live trading.db).
    Thread-safe with locking.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = Path(db_path or (Path(CONFIG.db_path).parent / "backtest_results.db"))
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Create tables if not exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    run_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    strategy_name TEXT,
                    symbol TEXT NOT NULL,
                    from_date TEXT,
                    to_date TEXT,
                    starting_capital REAL,
                    final_capital REAL,
                    status TEXT,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    net_profit REAL DEFAULT 0,
                    profit_factor REAL DEFAULT 0,
                    max_drawdown_pct REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    roi_pct REAL DEFAULT 0,
                    run_timestamp TEXT,
                    duration_seconds REAL,
                    trades_json TEXT,
                    equity_curve_json TEXT,
                    metrics_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_runs(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_backtest_timestamp ON backtest_runs(run_timestamp);

                CREATE TABLE IF NOT EXISTS optimization_jobs (
                    job_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    completed_at TEXT,
                    best_params_json TEXT,
                    best_score REAL,
                    all_results_json TEXT
                );
            """)
            conn.commit()

    def save_run(self, results: BacktestResults) -> str:
        """Save backtest results to DB."""
        with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO backtest_runs (
                        run_id, strategy_id, strategy_name, symbol, from_date, to_date,
                        starting_capital, final_capital, status, total_trades, winning_trades,
                        losing_trades, win_rate, net_profit, profit_factor, max_drawdown_pct,
                        sharpe_ratio, roi_pct, run_timestamp, duration_seconds,
                        trades_json, equity_curve_json, metrics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    results.run_id,
                    results.strategy_id,
                    results.strategy_name,
                    results.symbol,
                    results.from_date,
                    results.to_date,
                    results.starting_capital,
                    results.final_capital,
                    results.status,
                    results.total_trades,
                    results.winning_trades,
                    results.losing_trades,
                    results.win_rate,
                    results.net_profit,
                    results.profit_factor,
                    results.max_drawdown_pct,
                    results.sharpe_ratio,
                    results.roi_pct,
                    results.run_timestamp,
                    results.duration_seconds,
                    json.dumps([t.to_dict() for t in results.trades]),
                    json.dumps(results.equity_curve),
                    json.dumps(results.to_dict()),
                ))
                conn.commit()

        return results.run_id

    def get_run(self, run_id: str) -> Optional[dict]:
        """Get a single backtest run by ID."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)
            ).fetchone()

            if row:
                return dict(row)
            return None

    def list_runs(self, strategy_id: Optional[str] = None, limit: int = 50) -> List[dict]:
        """List backtest runs, optionally filtered by strategy."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row

            if strategy_id:
                rows = conn.execute(
                    """SELECT run_id, strategy_id, strategy_name, symbol, from_date, to_date,
                              status, total_trades, win_rate, net_profit, profit_factor,
                              run_timestamp
                       FROM backtest_runs
                       WHERE strategy_id = ?
                       ORDER BY run_timestamp DESC LIMIT ?""",
                    (strategy_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT run_id, strategy_id, strategy_name, symbol, from_date, to_date,
                              status, total_trades, win_rate, net_profit, profit_factor,
                              run_timestamp
                       FROM backtest_runs
                       ORDER BY run_timestamp DESC LIMIT ?""",
                    (limit,),
                ).fetchall()

            return [dict(row) for row in rows]


# ══════════════════════════════════════════════════════════════════
# BACKTEST MANAGER (T013)
# ══════════════════════════════════════════════════════════════════

class BacktestManager:
    """
    Manages backtest worker processes for non-blocking execution.
    MT5 cannot initialize in child processes, so data is fetched in main process.
    """

    def __init__(self, num_workers: int = 2):
        self._num_workers = num_workers
        self._job_queue: mp.Queue = mp.Queue()
        self._result_queue: mp.Queue = mp.Queue()
        self._workers: List[mp.Process] = []
        self._results: Dict[str, dict] = {}
        self._results_lock = threading.Lock()
        self._running = False
        self._collector_thread: Optional[threading.Thread] = None
        self._fetcher = HistoricalDataFetcher()
        self._db = BacktestResultsDB()

    def start(self) -> None:
        """Start worker processes and result collector."""
        if self._running:
            return

        self._running = True

        # Spawn workers
        for i in range(self._num_workers):
            p = mp.Process(
                target=self._worker_loop,
                args=(self._job_queue, self._result_queue),
                daemon=True,
                name=f"BacktestWorker-{i}",
            )
            p.start()
            self._workers.append(p)

        # Start result collector thread
        self._collector_thread = threading.Thread(
            target=self._collect_results,
            daemon=True,
            name="BacktestResultCollector",
        )
        self._collector_thread.start()

        log.info("BacktestManager started with %d workers", self._num_workers)

    def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False

        # Send poison pills
        for _ in self._workers:
            try:
                self._job_queue.put(None)
            except Exception:
                pass

        # Wait for workers
        for p in self._workers:
            p.join(timeout=5)

        self._workers.clear()

        if self._collector_thread:
            self._collector_thread.join(timeout=2)

        log.info("BacktestManager stopped")

    def submit_backtest(
        self,
        strategy_id: str,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        starting_capital: float = 100000,
    ) -> str:
        """
        Submit a backtest job. Returns run_id immediately.
        Data is fetched in main process (MT5 limitation).
        """
        run_id = str(uuid.uuid4())[:8]
        meta = STRATEGY_REGISTRY.get(strategy_id)

        if not meta:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        # Fetch historical data in main process
        prepared_data = {}
        for tf in meta.timeframes:
            df = self._fetcher.fetch(symbol, tf, from_date, to_date)
            if df is not None:
                prepared_data[tf] = df

        if not prepared_data:
            raise ValueError(f"No data available for {symbol} {from_date} - {to_date}")

        # Submit job with serialized data
        job = {
            "run_id": run_id,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "starting_capital": starting_capital,
            "prepared_data": {tf: df.to_json(orient='records', date_format='iso') for tf, df in prepared_data.items()},
            "timeframes": meta.timeframes,
        }

        self._job_queue.put(job)

        # Track as pending
        with self._results_lock:
            self._results[run_id] = {"status": "pending", "progress": 0}

        log.info("Submitted backtest %s for %s on %s", run_id, strategy_id, symbol)
        return run_id

    def get_result(self, run_id: str) -> Optional[dict]:
        """Get current status/result of a backtest."""
        with self._results_lock:
            return self._results.get(run_id)

    def list_runs(self, strategy_id: Optional[str] = None) -> List[dict]:
        """List historical runs from DB."""
        return self._db.list_runs(strategy_id)

    def _collect_results(self) -> None:
        """Background thread that collects results from workers."""
        while self._running:
            try:
                result = self._result_queue.get(timeout=1)
                if result is None:
                    continue

                run_id = result.get("run_id")
                if run_id:
                    # Save to DB
                    if result.get("status") == "completed":
                        try:
                            # Reconstruct BacktestResults for DB save
                            results_obj = self._dict_to_results(result)
                            self._db.save_run(results_obj)
                        except Exception as e:
                            log.warning("Failed to save run %s to DB: %s", run_id, e)

                    with self._results_lock:
                        self._results[run_id] = result

            except Exception:
                pass

    def _dict_to_results(self, d: dict) -> BacktestResults:
        """Convert dict to BacktestResults object."""
        trades = []
        for t in d.get("trades", []):
            trades.append(BacktestTrade(
                trade_id=t.get("trade_id", ""),
                strategy_id=t.get("strategy_id", ""),
                symbol=t.get("symbol", ""),
                direction=t.get("direction", ""),
                entry_time=datetime.fromisoformat(t["entry_time"]) if t.get("entry_time") else None,
                entry_price=t.get("entry_price", 0),
                entry_bar_idx=t.get("entry_bar_idx", 0),
                stop_loss=t.get("stop_loss", 0),
                take_profit=t.get("take_profit", 0),
                exit_time=datetime.fromisoformat(t["exit_time"]) if t.get("exit_time") else None,
                exit_price=t.get("exit_price"),
                exit_bar_idx=t.get("exit_bar_idx"),
                exit_reason=t.get("exit_reason", ""),
                profit=t.get("profit", 0),
                rr_achieved=t.get("rr_achieved", 0),
                confluence_score=t.get("confluence_score", 0),
            ))

        return BacktestResults(
            run_id=d.get("run_id", ""),
            strategy_id=d.get("strategy_id", ""),
            strategy_name=d.get("strategy_name", ""),
            symbol=d.get("symbol", ""),
            from_date=d.get("from_date", ""),
            to_date=d.get("to_date", ""),
            starting_capital=d.get("starting_capital", 100000),
            final_capital=d.get("final_capital", 100000),
            status=d.get("status", ""),
            trades=trades,
            equity_curve=d.get("equity_curve", []),
            total_trades=d.get("total_trades", 0),
            winning_trades=d.get("winning_trades", 0),
            losing_trades=d.get("losing_trades", 0),
            win_rate=d.get("win_rate", 0),
            gross_profit=d.get("gross_profit", 0),
            gross_loss=d.get("gross_loss", 0),
            net_profit=d.get("net_profit", 0),
            profit_factor=d.get("profit_factor", 0),
            avg_win=d.get("avg_win", 0),
            avg_loss=d.get("avg_loss", 0),
            expectancy=d.get("expectancy", 0),
            max_drawdown_pct=d.get("max_drawdown_pct", 0),
            max_drawdown_abs=d.get("max_drawdown_abs", 0),
            sharpe_ratio=d.get("sharpe_ratio", 0),
            sortino_ratio=d.get("sortino_ratio", 0),
            recovery_factor=d.get("recovery_factor", 0),
            roi_pct=d.get("roi_pct", 0),
            cagr_pct=d.get("cagr_pct", 0),
            max_consecutive_losses=d.get("max_consecutive_losses", 0),
            avg_rr_achieved=d.get("avg_rr_achieved", 0),
            avg_confluence_score=d.get("avg_confluence_score", 0),
            run_timestamp=d.get("run_timestamp", ""),
            duration_seconds=d.get("duration_seconds", 0),
        )

    @staticmethod
    def _worker_loop(job_queue: mp.Queue, result_queue: mp.Queue) -> None:
        """Worker process loop. Executes backtests from queue."""
        while True:
            try:
                job = job_queue.get(timeout=5)
                if job is None:  # Poison pill
                    break

                run_id = job["run_id"]
                strategy_id = job["strategy_id"]

                # Import strategy class
                from strategies import STRATEGY_CLASSES

                strategy_cls = STRATEGY_CLASSES.get(strategy_id)
                if not strategy_cls:
                    result_queue.put({
                        "run_id": run_id,
                        "status": "error",
                        "error": f"Unknown strategy: {strategy_id}",
                    })
                    continue

                # Deserialize data
                prepared_data = {}
                for tf_str, df_json in job["prepared_data"].items():
                    tf = int(tf_str)
                    df = pd.read_json(df_json, orient='records')
                    if 'time' in df.columns:
                        df['time'] = pd.to_datetime(df['time'])
                        df = df.set_index('time')
                    prepared_data[tf] = df

                # Run backtest
                strategy = strategy_cls()
                engine = BacktestEngine()

                from_date = datetime.fromisoformat(job["from_date"])
                to_date = datetime.fromisoformat(job["to_date"])

                results = engine.backtest(
                    strategy=strategy,
                    symbol=job["symbol"],
                    timeframes=job["timeframes"],
                    from_date=from_date,
                    to_date=to_date,
                    starting_capital=job["starting_capital"],
                    prepared_data=prepared_data,
                )

                result_queue.put(results.to_dict())

            except Exception as e:
                import traceback
                result_queue.put({
                    "run_id": job.get("run_id", "unknown") if 'job' in dir() else "unknown",
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
