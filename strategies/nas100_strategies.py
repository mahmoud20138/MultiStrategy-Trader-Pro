"""
╔══════════════════════════════════════════════════════════════════╗
║              NAS100 Strategies I–M                              ║
╚══════════════════════════════════════════════════════════════════╝
I  Opening Range Breakout    (Scalp)   58-70%  1:2
J  EMA Ribbon Scalp          (Scalp)   55-60%  1:1.5
K  ICT Power of 3            (Scalp)   55-65%  1:3
L  Gap Fill                  (Day)     65-72%  1:1.5
M  20/50 EMA Pullback        (Swing)   55-62%  1:2-3
"""
from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from config import TF
from strategies.base import (
    BaseStrategy, Signal, SignalDirection, SignalStrength,
)
from indicators.trend import (
    add_ema, add_sma, add_vwap, add_ema_ribbon,
    ema_trend_direction, ema_stack_signal,
)
from indicators.momentum import add_rsi, add_stochastic, stoch_signal
from indicators.volatility import add_atr, add_bbands
from indicators.volume import add_volume_sma, volume_surge, volume_confirms_breakout
from indicators.structure import (
    find_swing_points, detect_bos, find_order_blocks,
    find_fvg, find_support_resistance,
)


# ══════════════════════════════════════════════════════════════════
# I — Opening Range Breakout (Scalp, M5/M15)
# ══════════════════════════════════════════════════════════════════
class StrategyI(BaseStrategy):
    """
    First 15/30 min range after NY open → breakout above/below with
    volume surge + VWAP confirmation → enter with SL at opposite end.
    """

    def __init__(self) -> None:
        super().__init__("I")
        self.orb_minutes = 30  # Opening range = first 30 min

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        if m5 is None or len(m5) < 60:
            return None

        m5 = add_vwap(m5.copy())
        m5 = add_atr(m5, 14)
        m5 = add_volume_sma(m5, 20)
        atr_val = m5["ATR_14"].iloc[-1]

        # Calculate opening range (13:30 – 14:00 UTC = 9:30-10:00 ET)
        now = datetime.now(timezone.utc)
        orb_start_hour, orb_start_min = 13, 30

        orb_mask = (
            (m5.index.hour == orb_start_hour) & (m5.index.minute >= orb_start_min)
        ) | (
            (m5.index.hour == 14) & (m5.index.minute < orb_start_min)
        )
        orb_bars = m5[orb_mask]

        if len(orb_bars) < 3:
            return None

        orb_high = orb_bars["High"].max()
        orb_low = orb_bars["Low"].min()
        orb_size = orb_high - orb_low

        # ORB should be meaningful but not too wide
        if orb_size < atr_val * 0.3 or orb_size > atr_val * 2:
            return None

        last = m5.iloc[-1]
        vwap_val = m5["VWAP"].iloc[-1] if "VWAP" in m5.columns else last["Close"]

        # Only take breakouts AFTER the range is established
        if now.hour < 14 or (now.hour == 14 and now.minute < orb_start_min):
            return None

        confluence: List[str] = [f"ORB range {orb_low:.1f}-{orb_high:.1f}"]

        # Volume surge confirmation
        has_vol_surge = volume_surge(m5, threshold=1.5)
        if has_vol_surge:
            confluence.append("Volume surge on breakout")

        # Breakout above
        if last["Close"] > orb_high and last["Close"] > vwap_val:
            entry = last["Close"]
            sl = orb_low - atr_val * 0.2
            tp = entry + orb_size * 2
            confluence.append("Breakout above ORB")
            confluence.append("Above VWAP")
            if volume_confirms_breakout(m5):
                confluence.append("Volume confirms breakout")
            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                notes="ORB breakout buy — NAS100",
                strength=SignalStrength.STRONG if len(confluence) >= 4 else SignalStrength.MODERATE,
                data=data,
            )

        # Breakout below
        if last["Close"] < orb_low and last["Close"] < vwap_val:
            entry = last["Close"]
            sl = orb_high + atr_val * 0.2
            tp = entry - orb_size * 2
            confluence.append("Breakout below ORB")
            confluence.append("Below VWAP")
            if volume_confirms_breakout(m5):
                confluence.append("Volume confirms breakout")
            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                notes="ORB breakout sell — NAS100",
                strength=SignalStrength.STRONG if len(confluence) >= 4 else SignalStrength.MODERATE,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# J — EMA Ribbon Scalp (M1/M5)
# ══════════════════════════════════════════════════════════════════
class StrategyJ(BaseStrategy):
    """
    EMA 9/21/55 ribbon on M1 → wait for all aligned (bullish stack
    or bearish stack) → enter on stochastic pullback crossover.
    """

    def __init__(self) -> None:
        super().__init__("J")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m1 = data.get(TF.M1)
        m5 = data.get(TF.M5)
        if m1 is None or len(m1) < 80:
            return None

        m1 = add_ema_ribbon(m1.copy())
        m1 = add_stochastic(m1, 14, 3, 3)
        m1 = add_atr(m1, 14)
        atr_val = m1["ATR_14"].iloc[-1]

        stack = ema_stack_signal(m1)
        if stack is None:
            return None  # No clean stack

        stoch_sig = stoch_signal(m1)
        last = m1.iloc[-1]
        confluence: List[str] = [f"EMA ribbon {stack}"]

        if stack == "bullish" and stoch_sig == "bullish":
            confluence.append("Stochastic bullish cross from pullback")
            entry = last["Close"]
            sl = entry - atr_val * 1.5
            tp = entry + atr_val * 2.5
            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.M1, confluence,
                notes="EMA ribbon scalp buy — NAS100",
                strength=SignalStrength.MODERATE,
                data=data,
            )

        if stack == "bearish" and stoch_sig == "bearish":
            confluence.append("Stochastic bearish cross from pullback")
            entry = last["Close"]
            sl = entry + atr_val * 1.5
            tp = entry - atr_val * 2.5
            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.M1, confluence,
                notes="EMA ribbon scalp sell — NAS100",
                strength=SignalStrength.MODERATE,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# K — ICT Power of 3 (Scalp, M5/M15)
# ══════════════════════════════════════════════════════════════════
class StrategyK(BaseStrategy):
    """
    Accumulation → Manipulation → Distribution.
    1) Accumulation: tight range.
    2) Manipulation: false break (liquidity grab).
    3) Distribution: BOS + FVG entry in true direction.
    """

    def __init__(self) -> None:
        super().__init__("K")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        m15 = data.get(TF.M15)
        if m5 is None or m15 is None or len(m5) < 60:
            return None

        m5 = add_atr(m5.copy(), 14)
        atr_val = m5["ATR_14"].iloc[-1]

        # Phase 1: Accumulation — tight range in first bars
        accum_bars = m5.iloc[-30:-20]
        if len(accum_bars) < 8:
            return None

        accum_range = accum_bars["High"].max() - accum_bars["Low"].min()
        if accum_range > atr_val * 1.2:
            return None  # Too wide — not accumulation

        accum_high = accum_bars["High"].max()
        accum_low = accum_bars["Low"].min()

        # Phase 2: Manipulation — look for sweep beyond range
        manip_bars = m5.iloc[-20:-10]
        swept_high = manip_bars["High"].max() > accum_high + atr_val * 0.1
        swept_low = manip_bars["Low"].min() < accum_low - atr_val * 0.1
        if not (swept_high or swept_low):
            return None

        # Phase 3: Distribution — BOS + FVG in true direction
        recent = m5.iloc[-10:]
        bos = detect_bos(m5.iloc[-20:])
        fvgs = find_fvg(m5.iloc[-15:])

        last = m5.iloc[-1]
        confluence: List[str] = ["ICT Power of 3 pattern"]

        if swept_low and not swept_high:
            # Manipulation swept lows → true direction = UP
            confluence.append("Manipulation: low sweep (liquidity grab)")
            if bos and bos[-1].get("direction") == "bullish":
                confluence.append("Bullish BOS confirmed")
            if fvgs:
                for fvg in fvgs:
                    if fvg.direction == "bullish" and fvg.low <= last["Close"] <= fvg.high:
                        confluence.append(f"Bullish FVG at {fvg.low:.1f}-{fvg.high:.1f}")
                        break

            if len(confluence) >= 3:
                entry = last["Close"]
                sl = accum_low - atr_val * 0.3
                tp = entry + (entry - sl) * 3
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                    notes="ICT P3 buy — manipulation swept lows, distribution up",
                    strength=SignalStrength.VERY_STRONG,
                    data=data,
                )

        if swept_high and not swept_low:
            confluence.append("Manipulation: high sweep (liquidity grab)")
            if bos and bos[-1].get("direction") == "bearish":
                confluence.append("Bearish BOS confirmed")
            if fvgs:
                for fvg in fvgs:
                    if fvg.direction == "bearish" and fvg.low <= last["Close"] <= fvg.high:
                        confluence.append(f"Bearish FVG at {fvg.low:.1f}-{fvg.high:.1f}")
                        break

            if len(confluence) >= 3:
                entry = last["Close"]
                sl = accum_high + atr_val * 0.3
                tp = entry - (sl - entry) * 3
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                    notes="ICT P3 sell — manipulation swept highs, distribution down",
                    strength=SignalStrength.VERY_STRONG,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# L — Gap Fill (Day Trade, M15/H1)
# ══════════════════════════════════════════════════════════════════
class StrategyL(BaseStrategy):
    """
    Gap analysis: <1% gap → fade (gap fill), >1.5% gap → trend
    continuation.  Enter after first 15-min confirmation.
    """

    def __init__(self) -> None:
        super().__init__("L")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m15 = data.get(TF.M15)
        d1 = data.get(TF.D1)
        if m15 is None or d1 is None or len(m15) < 20 or len(d1) < 5:
            return None

        m15 = add_vwap(m15.copy())
        m15 = add_atr(m15, 14)
        atr_val = m15["ATR_14"].iloc[-1]

        gap = calculate_gap(d1)
        if gap is None:
            return None

        gap_pct = gap["gap_pct"]
        gap_dir = gap["direction"]  # "up" or "down"

        if abs(gap_pct) < 0.1:
            return None  # No meaningful gap

        last = m15.iloc[-1]
        vwap_val = m15["VWAP"].iloc[-1] if "VWAP" in m15.columns else last["Close"]
        confluence: List[str] = [f"Gap {gap_dir} {abs(gap_pct):.2f}%"]

        # Small gap (<1%) → FADE the gap
        if abs(gap_pct) < 1.0:
            confluence.append("Small gap — fade setup")
            prev_close = gap["prev_close"]

            if gap_dir == "up":
                # Gap up, fade down toward prev close
                entry = last["Close"]
                sl = entry + atr_val * 1.5
                tp = prev_close
                confluence.append("Fade gap down to prev close")
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M15, confluence,
                    notes="Gap fill sell — NAS100",
                    strength=SignalStrength.MODERATE,
                    data=data,
                )
            else:
                entry = last["Close"]
                sl = entry - atr_val * 1.5
                tp = prev_close
                confluence.append("Fade gap up to prev close")
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M15, confluence,
                    notes="Gap fill buy — NAS100",
                    strength=SignalStrength.MODERATE,
                    data=data,
                )

        # Large gap (>1.5%) → CONTINUATION
        if abs(gap_pct) > 1.5:
            confluence.append("Large gap — continuation setup")

            if gap_dir == "up" and last["Close"] > vwap_val:
                entry = last["Close"]
                sl = vwap_val - atr_val * 0.5
                tp = entry + atr_val * 3
                confluence.append("Above VWAP — momentum continues up")
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M15, confluence,
                    notes="Gap continuation buy — NAS100",
                    strength=SignalStrength.STRONG,
                    data=data,
                )
            elif gap_dir == "down" and last["Close"] < vwap_val:
                entry = last["Close"]
                sl = vwap_val + atr_val * 0.5
                tp = entry - atr_val * 3
                confluence.append("Below VWAP — momentum continues down")
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M15, confluence,
                    notes="Gap continuation sell — NAS100",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        return None


# Helper import at module level (used by StrategyL)
from indicators.volatility import calculate_gap


# ══════════════════════════════════════════════════════════════════
# M — 20/50 EMA Pullback (Swing, H4/D1)
# ══════════════════════════════════════════════════════════════════
class StrategyM(BaseStrategy):
    """
    Daily EMA 20/50 trend → pullback to one of those EMAs → 4H
    trigger candle → enter with SL below pullback low.
    """

    def __init__(self) -> None:
        super().__init__("M")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        d1 = data.get(TF.D1)
        h4 = data.get(TF.H4)
        if d1 is None or h4 is None or len(d1) < 60 or len(h4) < 30:
            return None

        d1 = add_ema(d1.copy(), 20)
        d1 = add_ema(d1, 50)
        d1 = add_atr(d1, 14)
        h4 = add_ema(h4.copy(), 21)

        atr_val = d1["ATR_14"].iloc[-1]
        last_d1 = d1.iloc[-1]
        last_h4 = h4.iloc[-1]

        ema20 = last_d1.get("EMA_20")
        ema50 = last_d1.get("EMA_50")
        if ema20 is None or ema50 is None:
            return None

        price = last_d1["Close"]
        confluence: List[str] = []

        # Bullish: EMA20 > EMA50, price pulled back to EMA20 or EMA50
        if ema20 > ema50:
            confluence.append("Daily uptrend (EMA20 > EMA50)")
            near_ema20 = abs(price - ema20) < atr_val * 0.5
            near_ema50 = abs(price - ema50) < atr_val * 0.5
            pullback_level = None

            if near_ema50:
                confluence.append("Deep pullback to EMA 50")
                pullback_level = ema50
            elif near_ema20:
                confluence.append("Pullback to EMA 20")
                pullback_level = ema20
            else:
                return None

            # 4H trigger: bullish candle
            h4_body = last_h4["Close"] - last_h4["Open"]
            if h4_body > 0 and h4_body > (last_h4["High"] - last_h4["Low"]) * 0.5:
                confluence.append("4H bullish trigger candle")
                entry = last_h4["Close"]
                # SL below pullback low
                recent_low = h4.iloc[-5:]["Low"].min()
                sl = recent_low - atr_val * 0.3
                tp = entry + (entry - sl) * 2.5
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.H4, confluence,
                    notes="EMA pullback swing buy — NAS100",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        # Bearish: EMA20 < EMA50, price pulled back up to EMA20 or EMA50
        if ema20 < ema50:
            confluence.append("Daily downtrend (EMA20 < EMA50)")
            near_ema20 = abs(price - ema20) < atr_val * 0.5
            near_ema50 = abs(price - ema50) < atr_val * 0.5

            if near_ema50:
                confluence.append("Deep pullback to EMA 50")
            elif near_ema20:
                confluence.append("Pullback to EMA 20")
            else:
                return None

            h4_body = last_h4["Close"] - last_h4["Open"]
            if h4_body < 0 and abs(h4_body) > (last_h4["High"] - last_h4["Low"]) * 0.5:
                confluence.append("4H bearish trigger candle")
                entry = last_h4["Close"]
                recent_high = h4.iloc[-5:]["High"].max()
                sl = recent_high + atr_val * 0.3
                tp = entry - (sl - entry) * 2.5
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.H4, confluence,
                    notes="EMA pullback swing sell — NAS100",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        return None
