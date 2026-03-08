"""
╔══════════════════════════════════════════════════════════════════╗
║               Gold Strategies A–H  (XAUUSD)                    ║
╚══════════════════════════════════════════════════════════════════╝
A  London Breakout Trap     (Scalp)   60-68%  1:2
B  VWAP + Order Block Sniper(Scalp)   55-62%  1:2
C  News Spike Fade          (Scalp)   55-60%  1:1.5
D  DXY Divergence           (Day)     62-70%  1:2
E  Session Transition       (Day)     58-65%  1:2
F  Trendline Break + Retest (Day)     55-62%  1:2.5
G  Weekly Institutional     (Swing)   55-60%  1:3+
H  Fibonacci Cluster        (Swing)   55-60%  1:3-5
"""
from __future__ import annotations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import TF, CONFIG
from strategies.base import (
    BaseStrategy, Signal, SignalDirection, SignalStrength,
)
from indicators.trend import add_ema, add_vwap, add_vwap_bands, ema_trend_direction
from indicators.momentum import add_rsi, add_macd, detect_rsi_divergence, rsi_zone
from indicators.volatility import (
    add_bbands, add_atr, calculate_asian_range, calculate_gap,
)
from indicators.volume import add_volume_sma, volume_surge
from indicators.structure import (
    find_swing_points, detect_bos, find_order_blocks,
    find_fvg, find_round_levels, fibonacci_levels, fibonacci_cluster,
    find_trendline_break, find_support_resistance, SwingPoint,
)


# ══════════════════════════════════════════════════════════════════
# A — London Breakout Trap (Scalp, M5/M15)
# ══════════════════════════════════════════════════════════════════
class StrategyA(BaseStrategy):
    """
    Asian session range calculation → wait for London open sweep beyond
    range → reversal candle (engulfing) → enter on pullback inside range.
    SL = beyond the sweep wick.  TP = opposite end of Asian range.
    """

    def __init__(self) -> None:
        super().__init__("A")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        if m5 is None or len(m5) < 100:
            return None

        m5 = add_atr(m5.copy(), 14)
        m5 = add_ema(m5, 21)

        # Asian range
        ar = calculate_asian_range(m5)
        if ar is None:
            return None
        a_high, a_low, a_size = ar["High"], ar["Low"], ar["size"]

        # Need minimum range (not too narrow / not too wide)
        atr_val = m5["ATR_14"].iloc[-1]
        if a_size < atr_val * 0.3 or a_size > atr_val * 2.5:
            return None

        last = m5.iloc[-1]
        prev = m5.iloc[-2]
        confluence: List[str] = []

        # === Bullish trap: price swept below Asian low then reversed ===
        if prev["Low"] < a_low and last["Close"] > a_low:
            # Engulfing / strong reversal
            if last["Close"] > last["Open"] and (last["Close"] - last["Open"]) > (prev["Open"] - prev["Close"]) * 0.8:
                entry = last["Close"]
                sl = prev["Low"] - atr_val * 0.2
                tp = a_high
                confluence.append("Asian low sweep")
                confluence.append("Bullish reversal candle")
                if entry > m5[f"EMA_21"].iloc[-1]:
                    confluence.append("Above EMA 21")
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                    notes="London trap buy — swept Asian low",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                    data=data,
                )

        # === Bearish trap: price swept above Asian high then reversed ===
        if prev["High"] > a_high and last["Close"] < a_high:
            if last["Close"] < last["Open"] and (last["Open"] - last["Close"]) > (prev["Close"] - prev["Open"]) * 0.8:
                entry = last["Close"]
                sl = prev["High"] + atr_val * 0.2
                tp = a_low
                confluence.append("Asian high sweep")
                confluence.append("Bearish reversal candle")
                if entry < m5[f"EMA_21"].iloc[-1]:
                    confluence.append("Below EMA 21")
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                    notes="London trap sell — swept Asian high",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# B — VWAP + Order Block Sniper (Scalp, M1/M5)
# ══════════════════════════════════════════════════════════════════
class StrategyB(BaseStrategy):
    """
    Entry at confluence of VWAP and a fresh order block during NY session.
    Price must tap order block zone while near VWAP.
    """

    def __init__(self) -> None:
        super().__init__("B")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m5 = data.get(TF.M5)
        if m5 is None or len(m5) < 100:
            return None

        m5 = add_vwap(m5.copy())
        m5 = add_atr(m5, 14)
        atr_val = m5["ATR_14"].iloc[-1]

        # Find fresh order blocks
        obs = find_order_blocks(m5, lookback=30)
        if not obs:
            return None

        last = m5.iloc[-1]
        vwap_val = m5["VWAP"].iloc[-1] if "VWAP" in m5.columns else None
        if vwap_val is None:
            return None

        # Price near VWAP (within 0.5 ATR)
        near_vwap = abs(last["Close"] - vwap_val) < atr_val * 0.5

        for ob in obs[-3:]:  # Check 3 most recent OBs
            in_ob_zone = ob.low <= last["Close"] <= ob.high
            if not (in_ob_zone and near_vwap):
                continue

            confluence: List[str] = ["Order Block zone", "VWAP confluence"]

            if ob.direction == "bullish":
                entry = last["Close"]
                sl = ob.low - atr_val * 0.3
                tp = entry + (entry - sl) * 2
                confluence.append(f"Bullish OB at {ob.low:.2f}-{ob.high:.2f}")
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                    notes="VWAP + OB sniper buy",
                    strength=SignalStrength.STRONG,
                    data=data,
                )
            else:
                entry = last["Close"]
                sl = ob.high + atr_val * 0.3
                tp = entry - (sl - entry) * 2
                confluence.append(f"Bearish OB at {ob.low:.2f}-{ob.high:.2f}")
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                    notes="VWAP + OB sniper sell",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# C — News Spike Fade (Scalp, M1/M5)
# ══════════════════════════════════════════════════════════════════
class StrategyC(BaseStrategy):
    """
    After a >$15 news spike, wait for momentum to stall (small bodies,
    wicks), then enter the fade.  Quick TP = 50% retrace of spike.
    """

    def __init__(self) -> None:
        super().__init__("C")
        self.spike_threshold = 15.0  # USD for Gold

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m1 = data.get(TF.M1)
        if m1 is None or len(m1) < 30:
            return None

        m1 = add_atr(m1.copy(), 14)
        atr_val = m1["ATR_14"].iloc[-1]

        # Detect spike: look for a single candle > $15 move in recent 10 bars
        recent = m1.iloc[-10:]
        spike_idx = None
        spike_dir = None
        for i in range(len(recent)):
            bar = recent.iloc[i]
            move = abs(bar["Close"] - bar["Open"])
            if move >= self.spike_threshold:
                spike_idx = i
                spike_dir = "up" if bar["Close"] > bar["Open"] else "down"

        if spike_idx is None:
            return None

        # Need at least 3 bars after spike for stall confirmation
        bars_after = len(recent) - spike_idx - 1
        if bars_after < 3:
            return None

        stall_bars = recent.iloc[spike_idx + 1:]
        avg_body = stall_bars.apply(lambda r: abs(r["Close"] - r["Open"]), axis=1).mean()
        spike_bar = recent.iloc[spike_idx]
        spike_body = abs(spike_bar["Close"] - spike_bar["Open"])

        # Stall = subsequent bars average body < 30% of spike body
        if avg_body > spike_body * 0.3:
            return None

        last = m1.iloc[-1]
        confluence = ["News spike detected", "Momentum stall confirmed"]

        if spike_dir == "up":
            # Fade the spike down
            entry = last["Close"]
            sl = spike_bar["High"] + atr_val * 0.3
            retrace_50 = spike_bar["Open"] + (spike_bar["Close"] - spike_bar["Open"]) * 0.5
            tp = retrace_50
            confluence.append(f"Spike up ${spike_body:.1f}")
            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.M1, confluence,
                notes="News spike fade sell",
                strength=SignalStrength.MODERATE,
                data=data,
            )
        else:
            entry = last["Close"]
            sl = spike_bar["Low"] - atr_val * 0.3
            retrace_50 = spike_bar["Open"] - (spike_bar["Open"] - spike_bar["Close"]) * 0.5
            tp = retrace_50
            confluence.append(f"Spike down ${spike_body:.1f}")
            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.M1, confluence,
                notes="News spike fade buy",
                strength=SignalStrength.MODERATE,
                data=data,
            )


# ══════════════════════════════════════════════════════════════════
# D — DXY Divergence (Day Trade, M15/H1)
# ══════════════════════════════════════════════════════════════════
class StrategyD(BaseStrategy):
    """
    DXY falling + Gold flat/rising → Gold likely to rally (inverse corr).
    Confirm with RSI divergence on M15, TP at next structure level.
    """

    def __init__(self) -> None:
        super().__init__("D")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        gold_m15 = data.get(TF.M15)
        gold_h1 = data.get(TF.H1)
        if gold_m15 is None or gold_h1 is None or len(gold_m15) < 60:
            return None

        # We need DXY data passed in as a separate key
        dxy_m15 = data.get(("DXY", TF.M15))
        if dxy_m15 is None or len(dxy_m15) < 30:
            # Fallback: skip DXY check if unavailable
            return None

        gold_m15 = add_rsi(gold_m15.copy(), 14)
        gold_m15 = add_atr(gold_m15, 14)
        gold_m15 = add_ema(gold_m15, 50)
        atr_val = gold_m15["ATR_14"].iloc[-1]

        # DXY direction: last 15 bars
        dxy_recent = dxy_m15.iloc[-15:]
        dxy_change = dxy_recent["Close"].iloc[-1] - dxy_recent["Close"].iloc[0]

        # Gold direction
        gold_recent = gold_m15.iloc[-15:]
        gold_change = gold_recent["Close"].iloc[-1] - gold_recent["Close"].iloc[0]

        confluence: List[str] = []
        last = gold_m15.iloc[-1]

        # Bullish Gold signal: DXY falling, Gold flat or rising
        if dxy_change < -0.1 and gold_change >= -atr_val * 0.3:
            confluence.append("DXY falling")
            # RSI divergence
            div = detect_rsi_divergence(gold_m15, lookback=20)
            if div == "bullish":
                confluence.append("Bullish RSI divergence")
            if gold_change > 0:
                confluence.append("Gold already rising")

            if len(confluence) >= 2:
                entry = last["Close"]
                sl = entry - atr_val * 2
                tp = entry + atr_val * 4
                # Check structure levels for better TP
                sr = find_support_resistance(gold_h1)
                for price, _count, _sr_type in sorted(sr, key=lambda x: x[0]):
                    if price > entry + atr_val * 2:
                        tp = price
                        confluence.append(f"TP at S/R {price:.2f}")
                        break

                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M15, confluence,
                    notes="DXY divergence buy — DXY weak, Gold primed",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                data=data,
                )

        # Bearish Gold signal: DXY rising, Gold flat or falling
        if dxy_change > 0.1 and gold_change <= atr_val * 0.3:
            confluence.append("DXY rising")
            div = detect_rsi_divergence(gold_m15, lookback=20)
            if div == "bearish":
                confluence.append("Bearish RSI divergence")
            if gold_change < 0:
                confluence.append("Gold already falling")

            if len(confluence) >= 2:
                entry = last["Close"]
                sl = entry + atr_val * 2
                tp = entry - atr_val * 4
                sr = find_support_resistance(gold_h1)
                for price, _count, _sr_type in sorted(sr, key=lambda x: x[0], reverse=True):
                    if price < entry - atr_val * 2:
                        tp = price
                        confluence.append(f"TP at S/R {price:.2f}")
                        break

                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M15, confluence,
                    notes="DXY divergence sell — DXY strong, Gold weak",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# E — Session Transition (Day Trade, M15/H1)
# ══════════════════════════════════════════════════════════════════
class StrategyE(BaseStrategy):
    """
    Identify London session direction → wait for NY open pullback
    to VWAP → enter with London trend continuation.
    """

    def __init__(self) -> None:
        super().__init__("E")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        m15 = data.get(TF.M15)
        h1 = data.get(TF.H1)
        if m15 is None or h1 is None or len(m15) < 60:
            return None

        m15 = add_vwap(m15.copy())
        m15 = add_atr(m15, 14)
        m15 = add_ema(m15, 21)
        atr_val = m15["ATR_14"].iloc[-1]

        if "VWAP" not in m15.columns:
            return None

        # Identify London direction (07:00 – 12:00 UTC bars)
        london_mask = m15.index.hour.isin(range(7, 13))
        london_bars = m15[london_mask]
        if len(london_bars) < 5:
            return None

        london_open = london_bars.iloc[0]["Open"]
        london_close = london_bars.iloc[-1]["Close"]
        london_dir = "bull" if london_close > london_open else "bear"
        london_move = abs(london_close - london_open)

        # Require meaningful London move (> 1 ATR)
        if london_move < atr_val:
            return None

        last = m15.iloc[-1]
        vwap_val = m15["VWAP"].iloc[-1]
        confluence: List[str] = [f"London {london_dir}ish ({london_move:.1f} pts)"]

        # Pullback to VWAP at NY
        near_vwap = abs(last["Close"] - vwap_val) < atr_val * 0.4
        if not near_vwap:
            return None

        confluence.append("Pullback to VWAP at NY open")

        if london_dir == "bull" and last["Close"] > vwap_val:
            entry = last["Close"]
            sl = vwap_val - atr_val * 0.5
            tp = entry + london_move * 0.75
            confluence.append("Continuation buy")
            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.M15, confluence,
                notes="Session transition — London bull → NY continuation",
                strength=SignalStrength.STRONG,
                data=data,
            )

        if london_dir == "bear" and last["Close"] < vwap_val:
            entry = last["Close"]
            sl = vwap_val + atr_val * 0.5
            tp = entry - london_move * 0.75
            confluence.append("Continuation sell")
            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.M15, confluence,
                notes="Session transition — London bear → NY continuation",
                strength=SignalStrength.STRONG,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# F — Trendline Break + Retest (Day Trade, M15/H1)
# ══════════════════════════════════════════════════════════════════
class StrategyF(BaseStrategy):
    """
    H1 trendline with 3+ touches → price breaks → wait for retest
    of the trendline → enter on confirmation candle.
    """

    def __init__(self) -> None:
        super().__init__("F")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        if not self.is_active_session():
            return None

        h1 = data.get(TF.H1)
        m15 = data.get(TF.M15)
        if h1 is None or len(h1) < 60:
            return None
        if m15 is None or len(m15) < 30:
            return None

        h1 = add_atr(h1.copy(), 14)
        atr_val = h1["ATR_14"].iloc[-1]

        tl_break = find_trendline_break(h1, min_touches=3)
        if tl_break is None:
            return None

        direction = tl_break["type"]
        tl_level_at_last_bar = tl_break["trendline_price"]
        break_distance = tl_break["break_distance"]
        last = h1.iloc[-1]

        # Check if price is retesting the broken trendline
        retest_threshold = atr_val * 0.3
        confluence: List[str] = [
            "H1 trendline break (3+ touches)",
            f"Break distance: {break_distance:.2f}",
        ]

        if direction == "bullish_break":
            # Price broke upward, retesting from above
            if abs(last["Low"] - tl_level_at_last_bar) < retest_threshold and last["Close"] > tl_level_at_last_bar:
                entry = last["Close"]
                sl = tl_level_at_last_bar - atr_val * 0.5
                tp = entry + atr_val * 3.5
                confluence.append("Retest from above — bullish")
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.H1, confluence,
                    notes="Trendline break+retest buy",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        elif direction == "bearish_break":
            if abs(last["High"] - tl_level_at_last_bar) < retest_threshold and last["Close"] < tl_level_at_last_bar:
                entry = last["Close"]
                sl = tl_level_at_last_bar + atr_val * 0.5
                tp = entry - atr_val * 3.5
                confluence.append("Retest from below — bearish")
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.H1, confluence,
                    notes="Trendline break+retest sell",
                    strength=SignalStrength.STRONG,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# G — Weekly Institutional (Swing, H4/D1)
# ══════════════════════════════════════════════════════════════════
class StrategyG(BaseStrategy):
    """
    $50/$100 round-number zones + RSI extreme on D1 + 4H reversal
    pattern → swing entry with wide SL and 1:3+ target.
    """

    def __init__(self) -> None:
        super().__init__("G")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        d1 = data.get(TF.D1)
        h4 = data.get(TF.H4)
        if d1 is None or h4 is None or len(d1) < 30 or len(h4) < 30:
            return None

        d1 = add_rsi(d1.copy(), 14)
        d1 = add_atr(d1, 14)
        h4 = add_ema(h4.copy(), 21)

        atr_val = d1["ATR_14"].iloc[-1]
        rsi_val = d1["RSI_14"].iloc[-1]
        last_d1 = d1.iloc[-1]
        last_h4 = h4.iloc[-1]

        # Round-number levels for Gold: $50 steps
        round_levels = find_round_levels(last_d1["Close"], "gold", count=5)

        # Find nearest round level (extract price from tuple)
        nearest_rl = min(round_levels, key=lambda l: abs(l[0] - last_d1["Close"]))[0]
        dist_to_rl = abs(last_d1["Close"] - nearest_rl)

        # Must be near a round level (within 1 ATR)
        if dist_to_rl > atr_val:
            return None

        confluence: List[str] = [f"Near ${nearest_rl:.0f} round level"]

        # RSI extreme
        if rsi_val < 30:
            confluence.append(f"RSI oversold ({rsi_val:.1f})")
            # 4H bullish reversal: last bar bullish with body > 60% of range
            h4_body = abs(last_h4["Close"] - last_h4["Open"])
            h4_range = last_h4["High"] - last_h4["Low"]
            if h4_range > 0 and h4_body / h4_range > 0.6 and last_h4["Close"] > last_h4["Open"]:
                confluence.append("4H bullish reversal candle")
                entry = last_h4["Close"]
                sl = last_h4["Low"] - atr_val * 0.5
                tp = entry + atr_val * 5
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.H4, confluence,
                    notes="Weekly institutional buy at round level",
                    strength=SignalStrength.VERY_STRONG if len(confluence) >= 3 else SignalStrength.STRONG,
                    data=data,
                )

        elif rsi_val > 70:
            confluence.append(f"RSI overbought ({rsi_val:.1f})")
            h4_body = abs(last_h4["Close"] - last_h4["Open"])
            h4_range = last_h4["High"] - last_h4["Low"]
            if h4_range > 0 and h4_body / h4_range > 0.6 and last_h4["Close"] < last_h4["Open"]:
                confluence.append("4H bearish reversal candle")
                entry = last_h4["Close"]
                sl = last_h4["High"] + atr_val * 0.5
                tp = entry - atr_val * 5
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.H4, confluence,
                    notes="Weekly institutional sell at round level",
                    strength=SignalStrength.VERY_STRONG if len(confluence) >= 3 else SignalStrength.STRONG,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# H — Fibonacci Cluster (Swing, H4/D1)
# ══════════════════════════════════════════════════════════════════
class StrategyH(BaseStrategy):
    """
    Multiple Fibonacci retracements from different swings clustering
    within a $3-5 zone → high-probability reversal zone.
    """

    def __init__(self) -> None:
        super().__init__("H")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        d1 = data.get(TF.D1)
        h4 = data.get(TF.H4)
        if d1 is None or h4 is None or len(d1) < 60 or len(h4) < 40:
            return None

        d1 = add_rsi(d1.copy(), 14)
        d1 = add_atr(d1, 14)
        h4 = add_ema(h4.copy(), 21)

        atr_val = d1["ATR_14"].iloc[-1]
        last = h4.iloc[-1]

        # Find fib clusters (multiple retracements aligning within $5)
        clusters = fibonacci_cluster(d1, tolerance_pct=5.0)
        if not clusters:
            return None

        # Take the most significant cluster (first in list, sorted by count)
        cluster_price, cluster_count = clusters[0]
        # Define cluster zone as +/- 0.5 * ATR around cluster price
        cluster_tolerance = atr_val * 0.5
        cluster_low = cluster_price - cluster_tolerance
        cluster_high = cluster_price + cluster_tolerance
        
        confluence: List[str] = [
            f"Fib cluster ({cluster_count} levels) at {cluster_price:.2f}",
        ]

        # Is price in the cluster zone?
        if not (cluster_low <= last["Close"] <= cluster_high):
            return None

        confluence.append("Price in Fib cluster zone")

        rsi_val = d1["RSI_14"].iloc[-1]
        trend = ema_trend_direction(h4, 21)

        # Bullish: RSI not overbought, trend up or neutral
        if rsi_val < 55 and trend in ("up", "flat"):
            entry = last["Close"]
            sl = cluster_low - atr_val * 0.8
            tp = entry + (entry - sl) * 3.5
            confluence.append(f"RSI supportive ({rsi_val:.1f})")
            if trend == "up":
                confluence.append("4H trend up")
            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.H4, confluence,
                notes="Fibonacci cluster support buy",
                strength=SignalStrength.VERY_STRONG if cluster_count >= 4 else SignalStrength.STRONG,
                data=data,
            )

        # Bearish: RSI not oversold, trend down or neutral
        if rsi_val > 45 and trend in ("down", "flat"):
            entry = last["Close"]
            sl = cluster_high + atr_val * 0.8
            tp = entry - (sl - entry) * 3.5
            confluence.append(f"RSI supportive ({rsi_val:.1f})")
            if trend == "down":
                confluence.append("4H trend down")
            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.H4, confluence,
                notes="Fibonacci cluster resistance sell",
                strength=SignalStrength.VERY_STRONG if cluster_count >= 4 else SignalStrength.STRONG,
                data=data,
            )

        return None
