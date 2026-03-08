"""
Core package — MT5 connection, data feed, risk management, backtesting, optimization.
"""
from core.backtest_engine import BacktestEngine, BacktestManager
from core.optimizer import WalkForwardOptimizer, OptimizationJobManager

__all__ = [
    "BacktestEngine",
    "BacktestManager",
    "WalkForwardOptimizer",
    "OptimizationJobManager",
]
