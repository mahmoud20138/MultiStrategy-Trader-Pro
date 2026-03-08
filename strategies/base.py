"""
╔══════════════════════════════════════════════════════════════════╗
║            Strategy Engine — Base Class & Signal Model          ║
╚══════════════════════════════════════════════════════════════════╝
All 19 strategies inherit from BaseStrategy and implement analyze().
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum

import pandas as pd

from config import TF, STRATEGY_REGISTRY, StrategyMeta, SESSIONS, SessionWindow
from indicators.confluence import ConfluenceEngine


# ══════════════════════════════════════════════════════════════════
# SIGNAL MODEL
# ══════════════════════════════════════════════════════════════════
class SignalDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalStrength(Enum):
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass
class Signal:
    """Unified output from every strategy."""
    strategy_id: str
    strategy_name: str
    instrument: str
    direction: SignalDirection
    strength: SignalStrength

    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float

    timeframe: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Extra context
    confluence_factors: List[str] = field(default_factory=list)
    notes: str = ""
    score: int = 0  # 0–100 confidence score (computed by ConfluenceEngine)
    score_breakdown: Dict[str, Any] = field(default_factory=dict)  # per-factor scores 0–1
    quality_tier: str = ""  # "elite" (≥85) / "high" (≥70) / "normal" (≥60) / "low" (<60)

    @property
    def sl_distance(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def tp_distance(self) -> float:
        return abs(self.take_profit - self.entry_price)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "instrument": self.instrument,
            "direction": self.direction.value,
            "strength": self.strength.name,
            "entry": self.entry_price,
            "sl": self.stop_loss,
            "tp": self.take_profit,
            "rr": round(self.risk_reward, 2),
            "confluence": self.confluence_factors,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "quality_tier": self.quality_tier,
            "notes": self.notes,
            "time": self.timestamp.isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# BASE STRATEGY
# ══════════════════════════════════════════════════════════════════
class BaseStrategy(ABC):
    """All 19 strategies implement this interface."""

    def __init__(self, strategy_id: str) -> None:
        self.meta: StrategyMeta = STRATEGY_REGISTRY[strategy_id]
        self.id = strategy_id
        self.name = self.meta.name

    @abstractmethod
    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        """
        Analyze multi-TF data and return a Signal if conditions are met.
        `data` is a dict of {timeframe: DataFrame}.
        Returns None if no valid setup found.
        """
        ...

    def is_active_session(self) -> bool:
        """Check if current UTC time falls within this strategy's sessions.
        Empty sessions list means 24/7 (e.g. crypto)."""
        if not self.meta.sessions:
            return True  # 24/7 trading (crypto)
        now = datetime.now(timezone.utc)
        for session_key in self.meta.sessions:
            sw: SessionWindow = SESSIONS.get(session_key)
            if sw is None:
                continue
            start = now.replace(hour=sw.start_hour, minute=sw.start_minute, second=0)
            end = now.replace(hour=sw.end_hour, minute=sw.end_minute, second=0)
            if start <= now <= end:
                return True
        return False

    def _make_signal(
        self,
        direction: SignalDirection,
        entry: float,
        sl: float,
        tp: float,
        timeframe: int,
        confluence: List[str],
        notes: str = "",
        strength: SignalStrength = SignalStrength.MODERATE,
        **kwargs,
    ) -> Signal:
        sl_dist = abs(entry - sl)
        tp_dist = abs(tp - entry)
        rr = tp_dist / sl_dist if sl_dist > 0 else 0

        # Compute multi-factor confluence score (falls back to RR-only when data=None)
        data_passed = kwargs.get('data', None)
        score, breakdown = ConfluenceEngine().calculate(
            direction.value, entry, sl, tp, rr, confluence, data_passed, self.meta
        )

        return Signal(
            strategy_id=self.id,
            strategy_name=self.name,
            instrument=self.meta.instrument,
            direction=direction,
            strength=strength,
            entry_price=round(entry, 5),
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            risk_reward=round(rr, 2),
            timeframe=timeframe,
            confluence_factors=confluence,
            notes=notes,
            score=score,
            score_breakdown=breakdown,
            quality_tier=breakdown.get("quality_tier", ""),
        )
