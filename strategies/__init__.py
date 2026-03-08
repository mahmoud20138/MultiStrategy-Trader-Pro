"""
Strategy package — registry & factory
"""
from __future__ import annotations
from typing import Dict, List, Type

from strategies.base import BaseStrategy, Signal, SignalDirection, SignalStrength
from strategies.gold_strategies import (
    StrategyA, StrategyB, StrategyC, StrategyD,
    StrategyE, StrategyF, StrategyG, StrategyH,
)
from strategies.nas100_strategies import (
    StrategyI, StrategyJ, StrategyK, StrategyL, StrategyM,
)
from strategies.us500_strategies import StrategyN, StrategyO, StrategyP
from strategies.us30_strategies import StrategyQ, StrategyR, StrategyS
from strategies.crypto_strategies import StrategyT, StrategyU, StrategyV, StrategyW, StrategyX, StrategyY

# Master map: letter → class
STRATEGY_MAP: Dict[str, Type[BaseStrategy]] = {
    "A": StrategyA,
    "B": StrategyB,
    "C": StrategyC,
    "D": StrategyD,
    "E": StrategyE,
    "F": StrategyF,
    "G": StrategyG,
    "H": StrategyH,
    "I": StrategyI,
    "J": StrategyJ,
    "K": StrategyK,
    "L": StrategyL,
    "M": StrategyM,
    "N": StrategyN,
    "O": StrategyO,
    "P": StrategyP,
    "Q": StrategyQ,
    "R": StrategyR,
    "S": StrategyS,
    "T": StrategyT,  # BTC Round Number Bounce
    "U": StrategyU,  # ETH Trend Following
    "V": StrategyV,  # BTC Momentum Breakout
    "W": StrategyW,  # BTC RSI Divergence
    "X": StrategyX,  # ETH Order Block Sniper
    "Y": StrategyY,  # ETH Multi-TF Confluence
}

# Alias for backtest engine
STRATEGY_CLASSES = STRATEGY_MAP


def build_active_strategies(enabled: List[str] | None = None) -> List[BaseStrategy]:
    """
    Instantiate strategies.  If *enabled* is None every strategy is built;
    otherwise only IDs in the list are created.

    Crypto strategies (T, U, V, W, X, Y) are only included when
    ENABLE_CRYPTO=true in the environment.
    """
    from config import SYMBOLS

    # Crypto strategy IDs
    CRYPTO_IDS = {"T", "U", "V", "W", "X", "Y"}

    ids = enabled if enabled else list(STRATEGY_MAP.keys())
    instances: List[BaseStrategy] = []

    for sid in ids:
        sid_upper = sid.upper()
        cls = STRATEGY_MAP.get(sid_upper)
        if cls is None:
            continue

        # Skip crypto strategies if crypto is disabled (US6)
        if sid_upper in CRYPTO_IDS and not SYMBOLS.enable_crypto:
            continue

        instances.append(cls())

    return instances


__all__ = [
    "BaseStrategy",
    "Signal",
    "SignalDirection",
    "SignalStrength",
    "STRATEGY_MAP",
    "STRATEGY_CLASSES",
    "build_active_strategies",
]
