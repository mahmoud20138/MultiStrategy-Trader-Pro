"""
╔══════════════════════════════════════════════════════════════════╗
║              US30 Strategies Q–S (Dow Jones)                    ║
╚══════════════════════════════════════════════════════════════════╝
Q  Round Number Scalp        (Scalp)   60-66%  1:2
R  ICT Silver Bullet         (Day)     55-65%  1:3+
S  Breakout-Retest           (Swing)   60-70%  1:3
"""

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import TF
from strategies.base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    SignalStrength,
)
from indicators.trend import add_ema, add_sma, ema_trend_direction
from indicators.momentum import add_rsi
from indicators.volatility import add_atr, add_bbands
from indicators.volume import add_volume_sma, volume_surge, volume_confirms_breakout
from indicators.structure import (
    find_round_levels,
    detect_bos,
    find_fvg,
    find_support_resistance,
    find_swing_points,
)


# ══════════════════════════════════════════════════════════════════
# Q — Round Number Scalp (M5/M15)
# ══════════════════════════════════════════════════════════════════
class StrategyQ(BaseStrategy):
    """
    US30 reacts strongly at 50/100/500/1000-point round numbers.
    Two modes:
      (a) Reaction: bounce off round level.
      (b) Break+Retest: clean break, retest from other side, continue.
    """

    def __init__(self) -> None:
        super().__init__("Q")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        m15 = data.get(TF.M15)
        if m5 is None or len(m5) < 40:
            return None

        m5 = add_atr(m5.copy(), 14)
        m5 = add_ema(m5, 21)
        atr_val = m5["ATR_14"].iloc[-1]

        last = m5.iloc[-1]
        prev = m5.iloc[-2]
        price = last["Close"]

        # Find nearest round levels
        levels = find_round_levels(price, "us30", count=3)
        if not levels:
            return None

        nearest = min(levels, key=lambda l: abs(l[0] - price))[0]
        dist = abs(price - nearest)

        # Must be near the level (within 0.5 ATR)
        if dist > atr_val * 0.5:
            return None

        ema_val = last.get("EMA_21", price)
        confluence: List[str] = [f"Round level {nearest:.0f}"]

        # ── Mode A: REACTION (bounce off level) ──
        # Price approaches from below, bounces
        if (
            prev["Low"] <= nearest
            and last["Close"] > nearest
            and last["Close"] > last["Open"]
        ):
            confluence.append("Bounce off round level (support)")
            if price > ema_val:
                confluence.append("Above EMA 21")
            entry = last["Close"]
            sl = nearest - atr_val * 0.8
            tp = entry + atr_val * 2
            return self._make_signal(
                SignalDirection.BUY,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes=f"Round number reaction buy at {nearest:.0f} — US30",
                strength=SignalStrength.STRONG
                if len(confluence) >= 3
                else SignalStrength.MODERATE,
                data=data,
            )

        # Price approaches from above, bounces
        if (
            prev["High"] >= nearest
            and last["Close"] < nearest
            and last["Close"] < last["Open"]
        ):
            confluence.append("Bounce off round level (resistance)")
            if price < ema_val:
                confluence.append("Below EMA 21")
            entry = last["Close"]
            sl = nearest + atr_val * 0.8
            tp = entry - atr_val * 2
            return self._make_signal(
                SignalDirection.SELL,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes=f"Round number reaction sell at {nearest:.0f} — US30",
                strength=SignalStrength.STRONG
                if len(confluence) >= 3
                else SignalStrength.MODERATE,
                data=data,
            )

        # ── Mode B: BREAK + RETEST ──
        # Check if recently broke through and now retesting
        lookback = m5.iloc[-10:-2]
        was_below = (lookback["Close"] < nearest).any()
        was_above = (lookback["Close"] > nearest).any()

        # Broke upward, now retesting from above
        if was_below and price > nearest:
            if abs(last["Low"] - nearest) < atr_val * 0.3:
                confluence.append(f"Break+Retest of {nearest:.0f} from above")
                if last["Close"] > last["Open"]:
                    confluence.append("Bullish retest candle")
                    entry = last["Close"]
                    sl = nearest - atr_val * 0.5
                    tp = entry + atr_val * 2.5
                    return self._make_signal(
                        SignalDirection.BUY,
                        entry,
                        sl,
                        tp,
                        TF.M5,
                        confluence,
                        notes=f"Round number break+retest buy at {nearest:.0f} — US30",
                        strength=SignalStrength.STRONG,
                        data=data,
                    )

        # Broke downward, now retesting from below
        if was_above and price < nearest:
            if abs(last["High"] - nearest) < atr_val * 0.3:
                confluence.append(f"Break+Retest of {nearest:.0f} from below")
                if last["Close"] < last["Open"]:
                    confluence.append("Bearish retest candle")
                    entry = last["Close"]
                    sl = nearest + atr_val * 0.5
                    tp = entry - atr_val * 2.5
                    return self._make_signal(
                        SignalDirection.SELL,
                        entry,
                        sl,
                        tp,
                        TF.M5,
                        confluence,
                        notes=f"Round number break+retest sell at {nearest:.0f} — US30",
                        strength=SignalStrength.STRONG,
                        data=data,
                    )

        return None


# ══════════════════════════════════════════════════════════════════
# R — ICT Silver Bullet (Day Trade, M5/M15)
# ══════════════════════════════════════════════════════════════════
class StrategyR(BaseStrategy):
    """
    Two windows: 10:00-11:00 AM ET (14:00-15:00 UTC) and
    2:00-3:00 PM ET (18:00-19:00 UTC).
    Wait for BOS within window → enter at FVG → ride displacement.
    """

    def __init__(self) -> None:
        super().__init__("R")
        # Silver Bullet time windows (UTC)
        self.windows = [
            (14, 0, 15, 0),  # 10-11 AM ET
            (18, 0, 19, 0),  # 2-3 PM ET
        ]

    def _in_silver_bullet_window(self) -> bool:
        now = datetime.now(timezone.utc)
        for sh, sm, eh, em in self.windows:
            start = now.replace(hour=sh, minute=sm, second=0)
            end = now.replace(hour=eh, minute=em, second=0)
            if start <= now <= end:
                return True
        return False

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self._in_silver_bullet_window():
            return None

        m5 = data.get(TF.M5)
        m15 = data.get(TF.M15)
        if m5 is None or len(m5) < 40:
            return None

        m5 = add_atr(m5.copy(), 14)
        atr_val = m5["ATR_14"].iloc[-1]

        # BOS detection in recent bars (within window)
        bos_list = detect_bos(m5.iloc[-12:])
        if not bos_list:
            return None

        latest_bos = bos_list[-1]
        bos_dir = latest_bos.get("direction")

        # FVG for entry
        fvgs = find_fvg(m5.iloc[-12:])
        if not fvgs:
            return None

        last = m5.iloc[-1]
        confluence: List[str] = ["ICT Silver Bullet window"]

        if bos_dir == "bullish":
            confluence.append("Bullish BOS in window")
            for fvg in reversed(fvgs):
                if fvg.direction == "bullish" and fvg.low <= last["Close"] <= fvg.high:
                    confluence.append(
                        f"Entry at bullish FVG {fvg.low:.1f}-{fvg.high:.1f}"
                    )
                    entry = last["Close"]
                    sl = fvg.low - atr_val * 0.3
                    tp = entry + (entry - sl) * 3
                    return self._make_signal(
                        SignalDirection.BUY,
                        entry,
                        sl,
                        tp,
                        TF.M5,
                        confluence,
                        notes="Silver Bullet buy — US30",
                        strength=SignalStrength.VERY_STRONG,
                        data=data,
                    )

        if bos_dir == "bearish":
            confluence.append("Bearish BOS in window")
            for fvg in reversed(fvgs):
                if fvg.direction == "bearish" and fvg.low <= last["Close"] <= fvg.high:
                    confluence.append(
                        f"Entry at bearish FVG {fvg.low:.1f}-{fvg.high:.1f}"
                    )
                    entry = last["Close"]
                    sl = fvg.high + atr_val * 0.3
                    tp = entry - (sl - entry) * 3
                    return self._make_signal(
                        SignalDirection.SELL,
                        entry,
                        sl,
                        tp,
                        TF.M5,
                        confluence,
                        notes="Silver Bullet sell — US30",
                        strength=SignalStrength.VERY_STRONG,
                        data=data,
                    )

        return None


# ══════════════════════════════════════════════════════════════════
# S — Breakout-Retest (Swing, D1/H4)
# ══════════════════════════════════════════════════════════════════
class StrategyS(BaseStrategy):
    """
    Daily chart patterns (H&S, triangles, rectangles) → volume
    breakout → wait for 4H retest of breakout level → enter.
    """

    def __init__(self) -> None:
        super().__init__("S")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        d1 = data.get(TF.D1)
        h4 = data.get(TF.H4)
        if d1 is None or h4 is None or len(d1) < 60 or len(h4) < 30:
            return None

        d1 = add_atr(d1.copy(), 14)
        d1 = add_volume_sma(d1, 20)
        h4 = add_ema(h4.copy(), 21)

        atr_val = d1["ATR_14"].iloc[-1]

        # Find key S/R levels (proxy for pattern breakout levels)
        sr_levels = find_support_resistance(d1)
        if not sr_levels:
            return None

        last_d1 = d1.iloc[-1]
        last_h4 = h4.iloc[-1]
        price = last_h4["Close"]

        # Volume breakout: recent daily bar with volume > 1.5x avg
        vol_breakout = volume_surge(d1, threshold=1.5)

        confluence: List[str] = []

        for level_price, touch_count, sr_type in sr_levels:
            dist = abs(price - level_price)
            if dist > atr_val * 1.5:
                continue

            # Check for breakout in last 5 daily bars
            recent_d1 = d1.iloc[-5:]
            broke_above = False
            broke_below = False

            for i in range(1, len(recent_d1)):
                prev_bar = recent_d1.iloc[i - 1]
                curr_bar = recent_d1.iloc[i]
                if prev_bar["Close"] < level_price and curr_bar["Close"] > level_price:
                    broke_above = True
                if prev_bar["Close"] > level_price and curr_bar["Close"] < level_price:
                    broke_below = True

            # ── Bullish breakout + retest from above ──
            if broke_above and price > level_price:
                # 4H retest: price pulled back near the level
                if abs(last_h4["Low"] - level_price) < atr_val * 0.4:
                    confluence = [
                        f"Breakout above {level_price:.1f}",
                        "4H retest of breakout level",
                    ]
                    if vol_breakout:
                        confluence.append("Volume confirms breakout")
                    if last_h4["Close"] > last_h4["Open"]:
                        confluence.append("Bullish retest candle")

                    if len(confluence) >= 3:
                        entry = last_h4["Close"]
                        sl = level_price - atr_val * 0.5
                        tp = entry + (entry - sl) * 3
                        return self._make_signal(
                            SignalDirection.BUY,
                            entry,
                            sl,
                            tp,
                            TF.H4,
                            confluence,
                            notes=f"Breakout-retest buy at {level_price:.1f} — US30",
                            strength=SignalStrength.VERY_STRONG
                            if vol_breakout
                            else SignalStrength.STRONG,
                            data=data,
                        )

            # ── Bearish breakdown + retest from below ──
            if broke_below and price < level_price:
                if abs(last_h4["High"] - level_price) < atr_val * 0.4:
                    confluence = [
                        f"Breakdown below {level_price:.1f}",
                        "4H retest of breakdown level",
                    ]
                    if vol_breakout:
                        confluence.append("Volume confirms breakdown")
                    if last_h4["Close"] < last_h4["Open"]:
                        confluence.append("Bearish retest candle")

                    if len(confluence) >= 3:
                        entry = last_h4["Close"]
                        sl = level_price + atr_val * 0.5
                        tp = entry - (sl - entry) * 3
                        return self._make_signal(
                            SignalDirection.SELL,
                            entry,
                            sl,
                            tp,
                            TF.H4,
                            confluence,
                            notes=f"Breakout-retest sell at {level_price:.1f} — US30",
                            strength=SignalStrength.VERY_STRONG
                            if vol_breakout
                            else SignalStrength.STRONG,
                            data=data,
                        )

        return None
