"""
╔══════════════════════════════════════════════════════════════════╗
║              US500 Strategies N–P (S&P 500)                     ║
╚══════════════════════════════════════════════════════════════════╝
N  VWAP Mean Reversion       (Scalp)   63-72%  1:1.5-2
O  Multi-TF Trend Following  (Day)     58-64%  1:2
P  RSI + Structure           (Swing)   55-62%  1:2-3
"""

from __future__ import annotations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import TF
from strategies.base import (
    BaseStrategy,
    Signal,
    SignalDirection,
    SignalStrength,
)
from indicators.trend import (
    add_ema,
    add_sma,
    add_vwap,
    add_vwap_bands,
    add_supertrend,
    ema_trend_direction,
)
from indicators.momentum import add_rsi, detect_rsi_divergence, rsi_zone
from indicators.volatility import add_atr, add_bbands, is_range_day
from indicators.volume import add_volume_sma, volume_surge
from indicators.structure import find_swing_points, detect_bos, find_support_resistance


# ══════════════════════════════════════════════════════════════════
# N — VWAP Mean Reversion (Scalp, M1/M5)
# ══════════════════════════════════════════════════════════════════
class StrategyN(BaseStrategy):
    """
    Range day filter → VWAP upper/lower band touch → RSI(7) extreme
    → enter fade toward VWAP middle.  Best on mean-reverting days.
    """

    def __init__(self) -> None:
        super().__init__("N")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        h1 = data.get(TF.H1)
        if m5 is None or len(m5) < 60:
            return None

        m5 = add_vwap(m5.copy())
        m5 = add_vwap_bands(m5)
        m5 = add_rsi(m5, 7)
        m5 = add_atr(m5, 14)
        atr_val = m5["ATR_14"].iloc[-1]

        # Range-day filter: if trending strongly, skip mean reversion
        if h1 is not None and len(h1) > 20:
            if not is_range_day(h1):
                return None  # Trending day — don't mean-revert

        last = m5.iloc[-1]
        rsi_val = last.get("RSI_7")
        vwap_mid = last.get("VWAP")
        vwap_upper = last.get("VWAP_upper")
        vwap_lower = last.get("VWAP_lower")

        if any(v is None for v in [rsi_val, vwap_mid, vwap_upper, vwap_lower]):
            return None

        confluence: List[str] = ["Range day confirmed"]

        # Overbought at upper band → SELL toward VWAP
        if last["Close"] >= vwap_upper and rsi_val > 75:
            confluence.append("Price at VWAP upper band")
            confluence.append(f"RSI(7) overbought: {rsi_val:.1f}")
            entry = last["Close"]
            sl = entry + atr_val * 1.0
            tp = vwap_mid
            return self._make_signal(
                SignalDirection.SELL,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes="VWAP mean reversion sell — US500",
                strength=SignalStrength.STRONG,
                data=data,
            )

        # Oversold at lower band → BUY toward VWAP
        if last["Close"] <= vwap_lower and rsi_val < 25:
            confluence.append("Price at VWAP lower band")
            confluence.append(f"RSI(7) oversold: {rsi_val:.1f}")
            entry = last["Close"]
            sl = entry - atr_val * 1.0
            tp = vwap_mid
            return self._make_signal(
                SignalDirection.BUY,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes="VWAP mean reversion buy — US500",
                strength=SignalStrength.STRONG,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# O — Multi-TF Trend Following (Day Trade, M5/M15/H1)
# ══════════════════════════════════════════════════════════════════
class StrategyO(BaseStrategy):
    """
    H1: 200 EMA direction sets bias.
    M15: structure (BOS) confirms.
    M5: Supertrend flip for precise entry.
    """

    def __init__(self) -> None:
        super().__init__("O")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        m15 = data.get(TF.M15)
        h1 = data.get(TF.H1)
        if m5 is None or m15 is None or h1 is None:
            return None
        if len(m5) < 60 or len(m15) < 30 or len(h1) < 220:
            return None

        # H1: 200 EMA trend direction
        h1 = add_ema(h1.copy(), 200)
        h1 = add_atr(h1, 14)
        atr_val = h1["ATR_14"].iloc[-1]

        h1_trend = ema_trend_direction(h1, 200)
        if h1_trend == "flat":
            return None  # No clear bias

        # M15: BOS confirmation
        m15_bos = detect_bos(m15)
        m15_dir = None
        if m15_bos and isinstance(m15_bos, str):
            m15_dir = "bullish" if "bullish" in m15_bos else "bearish"

        # M5: Supertrend entry
        m5 = add_supertrend(m5.copy())
        last_m5 = m5.iloc[-1]
        prev_m5 = m5.iloc[-2]

        st_col = [c for c in m5.columns if "SUPERTd" in c]
        if not st_col:
            return None
        st_dir = last_m5[st_col[0]]
        st_prev = prev_m5[st_col[0]]

        confluence: List[str] = [f"H1 200EMA trend: {h1_trend}"]

        # All three TFs aligned BULLISH
        if h1_trend == "up" and m15_dir == "bullish" and st_dir == 1 and st_prev != 1:
            confluence.append("M15 bullish BOS")
            confluence.append("M5 Supertrend flipped bullish")
            entry = last_m5["Close"]
            sl = entry - atr_val * 1.5
            tp = entry + atr_val * 3
            return self._make_signal(
                SignalDirection.BUY,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes="Multi-TF trend buy — US500 (H1→M15→M5 aligned)",
                strength=SignalStrength.VERY_STRONG,
                data=data,
            )

        # All three TFs aligned BEARISH
        if (
            h1_trend == "down"
            and m15_dir == "bearish"
            and st_dir == -1
            and st_prev != -1
        ):
            confluence.append("M15 bearish BOS")
            confluence.append("M5 Supertrend flipped bearish")
            entry = last_m5["Close"]
            sl = entry + atr_val * 1.5
            tp = entry - atr_val * 3
            return self._make_signal(
                SignalDirection.SELL,
                entry,
                sl,
                tp,
                TF.M5,
                confluence,
                notes="Multi-TF trend sell — US500 (H1→M15→M5 aligned)",
                strength=SignalStrength.VERY_STRONG,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# P — RSI + Structure (Swing, D1/H4)
# ══════════════════════════════════════════════════════════════════
class StrategyP(BaseStrategy):
    """
    Weekly: 200 SMA direction.
    Daily: RSI dropping into 40-50 "pullback zone" in uptrend.
    Entry at Daily 50 SMA with confirmation candle.
    """

    def __init__(self) -> None:
        super().__init__("P")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        d1 = data.get(TF.D1)
        h4 = data.get(TF.H4)
        if d1 is None or h4 is None or len(d1) < 210:
            return None

        d1 = add_sma(d1.copy(), 200)
        d1 = add_sma(d1, 50)
        d1 = add_rsi(d1, 14)
        d1 = add_atr(d1, 14)

        atr_val = d1["ATR_14"].iloc[-1]
        last_d1 = d1.iloc[-1]

        sma200 = last_d1.get("SMA_200")
        sma50 = last_d1.get("SMA_50")
        rsi_val = last_d1.get("RSI_14")
        if any(v is None for v in [sma200, sma50, rsi_val]):
            return None

        price = last_d1["Close"]
        zone = rsi_zone(rsi_val)
        confluence: List[str] = []

        # ──── BULLISH setup: Uptrend + RSI pullback zone ────
        if price > sma200 and sma50 > sma200:
            confluence.append("Above Weekly 200 SMA (uptrend)")

            # RSI in sweet spot (40-50 = pullback in uptrend)
            if zone == "pullback_zone" or (40 <= rsi_val <= 55):
                confluence.append(f"RSI in pullback zone ({rsi_val:.1f})")

                # Price near Daily 50 SMA
                dist_to_50 = abs(price - sma50)
                if dist_to_50 < atr_val * 0.8:
                    confluence.append("Price at Daily 50 SMA support")

                    # 4H confirmation
                    h4 = add_ema(h4.copy(), 21)
                    last_h4 = h4.iloc[-1]
                    h4_bullish = last_h4["Close"] > last_h4["Open"]

                    if h4_bullish:
                        confluence.append("4H bullish confirmation")
                        entry = last_h4["Close"]
                        recent_low = h4.iloc[-8:]["Low"].min()
                        sl = recent_low - atr_val * 0.5
                        tp = entry + (entry - sl) * 2.5
                        return self._make_signal(
                            SignalDirection.BUY,
                            entry,
                            sl,
                            tp,
                            TF.H4,
                            confluence,
                            notes="RSI+Structure swing buy — US500 uptrend pullback",
                            strength=SignalStrength.VERY_STRONG
                            if len(confluence) >= 4
                            else SignalStrength.STRONG,
                            data=data,
                        )

        # ──── BEARISH setup: Downtrend + RSI pullback zone ────
        if price < sma200 and sma50 < sma200:
            confluence.append("Below Weekly 200 SMA (downtrend)")

            if zone == "pullback_zone" or (50 <= rsi_val <= 60):
                confluence.append(f"RSI in pullback zone ({rsi_val:.1f})")

                dist_to_50 = abs(price - sma50)
                if dist_to_50 < atr_val * 0.8:
                    confluence.append("Price at Daily 50 SMA resistance")

                    h4 = add_ema(h4.copy(), 21)
                    last_h4 = h4.iloc[-1]
                    h4_bearish = last_h4["Close"] < last_h4["Open"]

                    if h4_bearish:
                        confluence.append("4H bearish confirmation")
                        entry = last_h4["Close"]
                        recent_high = h4.iloc[-8:]["High"].max()
                        sl = recent_high + atr_val * 0.5
                        tp = entry - (sl - entry) * 2.5
                        return self._make_signal(
                            SignalDirection.SELL,
                            entry,
                            sl,
                            tp,
                            TF.H4,
                            confluence,
                            notes="RSI+Structure swing sell — US500 downtrend pullback",
                            strength=SignalStrength.VERY_STRONG
                            if len(confluence) >= 4
                            else SignalStrength.STRONG,
                            data=data,
                        )

        return None
