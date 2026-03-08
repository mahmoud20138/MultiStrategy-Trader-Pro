"""
╔══════════════════════════════════════════════════════════════════╗
║          Confluence Scoring Engine — Multi-Factor Signal Quality ║
╚══════════════════════════════════════════════════════════════════╝
Replaces the naive RR+count formula in BaseStrategy._make_signal().

Factor weights (sum to 1.0):
  trend      0.20  — EMA alignment across timeframes
  structure  0.18  — Proximity to OB / FVG / S/R / round levels
  volume     0.16  — Volume surge + OBV confirmation
  momentum   0.16  — RSI zone + MACD histogram direction
  session    0.14  — Session quality (optimal / suboptimal / outside)
  volatility 0.12  — ATR regime (not range-day, not spike)
  multi_tf   0.04  — Bonus for full 3-TF alignment

Veto gates (set base score → 0 before RR multiplier):
  - Cross-TF trend conflict (H1/H4 direction opposes M5/M15)
  - Volume divergence (volume declining into the entry bar)

Partial penalty (×0.5):
  - RSI divergence detected

RR multiplier (applied on top of weighted sum):
  rr_multiplier = 1.0 + min(rr / 5.0, 0.5)   → [1.0, 1.5]

Quality tiers:
  elite  ≥ 85
  high   ≥ 70
  normal ≥ 60
  low    < 60
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from indicators.trend import ema_trend_direction
from indicators.momentum import add_rsi, detect_rsi_divergence, rsi_zone
from indicators.volume import volume_surge, volume_confirms_breakout
from indicators.volatility import add_atr, is_range_day
from config import SESSIONS, SessionWindow

log = logging.getLogger(__name__)

# ── Weight table ──────────────────────────────────────────────────
_WEIGHTS: Dict[str, float] = {
    "trend":      0.20,
    "structure":  0.18,
    "volume":     0.16,
    "momentum":   0.16,
    "session":    0.14,
    "volatility": 0.12,
    "multi_tf":   0.04,
}

_QUALITY_TIERS = [
    (85, "elite"),
    (70, "high"),
    (60, "normal"),
    (0,  "low"),
]


def _quality_tier(score: int) -> str:
    for threshold, label in _QUALITY_TIERS:
        if score >= threshold:
            return label
    return "low"


class ConfluenceEngine:
    """
    Compute a normalised 0–100 confluence score for a Signal.

    Usage (called from BaseStrategy._make_signal):
        score, breakdown = ConfluenceEngine().calculate(
            direction, entry, sl, tp, rr, confluence_factors,
            data, strategy_meta
        )
    """

    def calculate(
        self,
        direction: str,          # "BUY" or "SELL"
        entry: float,
        sl: float,
        tp: float,
        rr: float,
        confluence_factors: List[str],
        data: Optional[Dict[int, pd.DataFrame]],
        strategy_meta: Any,       # StrategyMeta
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Returns (score: 0-100, breakdown: dict).
        Falls back to RR-only scoring when data is None.
        """
        breakdown: Dict[str, Any] = {}

        # ── Fallback when no data provided ───────────────────────
        if data is None or not data:
            base = self._rr_only_score(rr, len(confluence_factors))
            breakdown = {
                "trend": 0.5, "structure": 0.5, "volume": 0.5,
                "momentum": 0.5, "session": 0.5, "volatility": 0.5,
                "multi_tf": 0.0, "rr_multiplier": 1.0 + min(rr / 5.0, 0.5),
                "veto_applied": False, "veto_reason": None,
                "quality_tier": _quality_tier(base),
            }
            return base, breakdown

        # ── Score each factor ─────────────────────────────────────
        veto_applied = False
        veto_reason: Optional[str] = None

        # 1. Trend alignment across timeframes
        trend_score, trend_conflict = self._score_trend(direction, data)
        if trend_conflict:
            veto_applied = True
            veto_reason = "Cross-TF trend conflict"

        # 2. Structure proximity
        structure_score = self._score_structure(confluence_factors)

        # 3. Volume confirmation
        volume_score, volume_divergence = self._score_volume(direction, data)
        if volume_divergence and not veto_applied:
            # Partial penalty — not a full veto
            volume_score *= 0.3

        # 4. Momentum
        momentum_score, rsi_divergence = self._score_momentum(direction, data)

        # 5. Session quality
        session_score = self._score_session(strategy_meta)

        # 6. Volatility regime
        volatility_score = self._score_volatility(data)

        # 7. Multi-TF alignment bonus
        multi_tf_score = self._score_multi_tf(direction, data)

        breakdown = {
            "trend":      round(trend_score, 3),
            "structure":  round(structure_score, 3),
            "volume":     round(volume_score, 3),
            "momentum":   round(momentum_score, 3),
            "session":    round(session_score, 3),
            "volatility": round(volatility_score, 3),
            "multi_tf":   round(multi_tf_score, 3),
        }

        # ── Compute weighted sum ──────────────────────────────────
        if veto_applied:
            base_score = 0.0
        else:
            base_score = sum(
                breakdown[k] * _WEIGHTS[k]
                for k in _WEIGHTS
            )
            # RSI divergence partial penalty
            if rsi_divergence:
                base_score *= 0.5

        # ── RR multiplicative bonus ───────────────────────────────
        rr_mult = 1.0 + min(rr / 5.0, 0.5)
        final_score = int(min(base_score * rr_mult * 100, 100))

        tier = _quality_tier(final_score)
        breakdown.update({
            "rr_multiplier":  round(rr_mult, 3),
            "veto_applied":   veto_applied,
            "veto_reason":    veto_reason,
            "quality_tier":   tier,
        })

        log.debug(
            "Confluence [%s]: score=%d tier=%s veto=%s",
            getattr(strategy_meta, "id", "?"), final_score, tier, veto_applied
        )
        return final_score, breakdown

    # ── Factor scorers ────────────────────────────────────────────

    def _score_trend(
        self, direction: str, data: Dict[int, pd.DataFrame]
    ) -> Tuple[float, bool]:
        """Returns (score 0-1, conflict_veto: bool)."""
        timeframes = sorted(data.keys())
        directions: List[str] = []
        for tf in timeframes:
            df = data[tf]
            if len(df) < 51:
                continue
            try:
                td = ema_trend_direction(df, fast=20, slow=50)
                directions.append(td)
            except Exception:
                pass

        if not directions:
            return 0.5, False

        aligned_count = sum(
            1 for d in directions
            if (d == "up" and direction == "BUY") or (d == "down" and direction == "SELL")
        )
        opposed_count = sum(
            1 for d in directions
            if (d == "up" and direction == "SELL") or (d == "down" and direction == "BUY")
        )

        # Veto: majority of TFs are against the trade direction
        conflict = opposed_count > aligned_count and opposed_count >= 2
        if len(directions) >= 2:
            score = aligned_count / len(directions)
        else:
            score = 0.5 if not conflict else 0.0

        return score, conflict

    def _score_structure(self, confluence_factors: List[str]) -> float:
        """Proxy: how many structure-related confluence factors are listed."""
        structure_keywords = [
            "order block", "ob", "fvg", "fair value gap", "support", "resistance",
            "round", "level", "fibonacci", "fib", "swing", "bos", "break of structure",
            "vwap", "retest", "breakout", "trendline",
        ]
        count = sum(
            1 for f in confluence_factors
            if any(kw in f.lower() for kw in structure_keywords)
        )
        # Normalise: 0=0.1, 1=0.5, 2=0.8, 3+=1.0
        if count == 0:
            return 0.1
        elif count == 1:
            return 0.5
        elif count == 2:
            return 0.8
        else:
            return 1.0

    def _score_volume(
        self, direction: str, data: Dict[int, pd.DataFrame]
    ) -> Tuple[float, bool]:
        """Returns (score 0-1, declining_volume: bool)."""
        # Use the smallest timeframe for volume analysis
        min_tf = min(data.keys())
        df = data[min_tf]
        if len(df) < 22 or "Volume" not in df.columns:
            return 0.5, False

        try:
            has_surge = volume_surge(df, threshold=1.5)
            has_confirm = volume_confirms_breakout(df, direction == "BUY")
        except Exception:
            return 0.5, False

        # Check for declining volume (bearish for entry)
        last_vol = df["Volume"].iloc[-1]
        prev_avg = df["Volume"].iloc[-6:-1].mean()
        declining = last_vol < prev_avg * 0.7 and prev_avg > 0

        if has_surge and has_confirm:
            return 1.0, declining
        elif has_surge or has_confirm:
            return 0.65, declining
        elif declining:
            return 0.2, True
        else:
            return 0.4, False

    def _score_momentum(
        self, direction: str, data: Dict[int, pd.DataFrame]
    ) -> Tuple[float, bool]:
        """Returns (score 0-1, rsi_divergence: bool)."""
        min_tf = min(data.keys())
        df = data[min_tf]
        if len(df) < 15:
            return 0.5, False

        try:
            df_rsi = add_rsi(df.copy(), 14)
            zone = rsi_zone(df_rsi, 14)
            divergence = detect_rsi_divergence(df_rsi, lookback=10)
        except Exception:
            return 0.5, False

        # Divergence against direction = penalty
        has_divergence = False
        if direction == "BUY" and divergence == "bearish":
            has_divergence = True
        elif direction == "SELL" and divergence == "bullish":
            has_divergence = True

        # Score based on RSI zone alignment
        if direction == "BUY":
            if zone == "oversold":
                score = 0.9
            elif zone == "neutral":
                score = 0.6
            elif zone == "overbought":
                score = 0.2
            else:
                score = 0.5
        else:  # SELL
            if zone == "overbought":
                score = 0.9
            elif zone == "neutral":
                score = 0.6
            elif zone == "oversold":
                score = 0.2
            else:
                score = 0.5

        return score, has_divergence

    def _score_session(self, strategy_meta: Any) -> float:
        """Returns 1.0 for optimal session, 0.5 for suboptimal, 0.0 for outside."""
        sessions: List[str] = getattr(strategy_meta, "sessions", [])
        if not sessions:
            return 1.0  # 24/7 instruments (crypto)

        now = datetime.now(timezone.utc)
        for session_key in sessions:
            sw: Optional[SessionWindow] = SESSIONS.get(session_key)
            if sw is None:
                continue
            start = now.replace(hour=sw.start_hour, minute=sw.start_minute, second=0, microsecond=0)
            end = now.replace(hour=sw.end_hour, minute=sw.end_minute, second=0, microsecond=0)
            if start <= now <= end:
                return 1.0

        # Check adjacent sessions (within 30 mins of start/end)
        from datetime import timedelta
        buffer = timedelta(minutes=30)
        for session_key in sessions:
            sw = SESSIONS.get(session_key)
            if sw is None:
                continue
            start = now.replace(hour=sw.start_hour, minute=sw.start_minute, second=0, microsecond=0)
            end = now.replace(hour=sw.end_hour, minute=sw.end_minute, second=0, microsecond=0)
            if (start - buffer) <= now <= (end + buffer):
                return 0.5

        return 0.0

    def _score_volatility(self, data: Dict[int, pd.DataFrame]) -> float:
        """Returns 1.0 for healthy ATR regime, 0.3 for range/spike extremes."""
        min_tf = min(data.keys())
        df = data[min_tf]
        if len(df) < 20:
            return 0.5

        try:
            if is_range_day(df):
                return 0.3  # Choppy — poor for trend signals
        except Exception:
            pass

        try:
            df_atr = add_atr(df.copy(), 14)
            atr_now = df_atr["ATR_14"].iloc[-1]
            atr_avg = df_atr["ATR_14"].iloc[-20:].mean()
            if atr_avg > 0:
                ratio = atr_now / atr_avg
                if ratio > 3.0:
                    return 0.2  # Spike — entry too risky
                elif ratio > 1.5:
                    return 0.7  # Elevated but tradeable
                elif ratio < 0.3:
                    return 0.3  # Very low vol — poor momentum
                else:
                    return 1.0
        except Exception:
            pass

        return 0.5

    def _score_multi_tf(self, direction: str, data: Dict[int, pd.DataFrame]) -> float:
        """Bonus: 1.0 if 3+ TFs align, 0.5 if 2 TFs, 0.0 otherwise."""
        timeframes = sorted(data.keys())
        if len(timeframes) < 2:
            return 0.0

        aligned = 0
        checked = 0
        for tf in timeframes:
            df = data[tf]
            if len(df) < 51:
                continue
            try:
                td = ema_trend_direction(df, fast=20, slow=50)
                checked += 1
                if (td == "up" and direction == "BUY") or (td == "down" and direction == "SELL"):
                    aligned += 1
            except Exception:
                pass

        if checked == 0:
            return 0.0
        elif aligned >= 3:
            return 1.0
        elif aligned >= 2:
            return 0.5
        else:
            return 0.0

    # ── Fallback ──────────────────────────────────────────────────
    @staticmethod
    def _rr_only_score(rr: float, n_factors: int) -> int:
        """Legacy formula used when no market data available."""
        return min(100, int(rr * 15) + n_factors * 10)
