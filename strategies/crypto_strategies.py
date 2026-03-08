"""
╔══════════════════════════════════════════════════════════════════╗
║               Crypto Strategies (BTC/ETH) - 24/7 Trading        ║
╚══════════════════════════════════════════════════════════════════╝
T  BTC Round Number Bounce  (Scalp, M5)   - $1000 levels
U  ETH Trend Following      (Day, H4)     - Moving average crossover
"""
from __future__ import annotations
from typing import Dict, List, Optional

import pandas as pd

from config import TF
from strategies.base import (
    BaseStrategy, Signal, SignalDirection, SignalStrength,
)
from indicators.trend import add_ema
from indicators.momentum import add_rsi
from indicators.volatility import add_atr
from indicators.structure import find_round_levels


# ══════════════════════════════════════════════════════════════════
# T — BTC Round Number Bounce (Scalp, M5)
# ══════════════════════════════════════════════════════════════════
class StrategyT(BaseStrategy):
    """
    BTC reacts at $1000, $5000, $10000 round numbers.
    Wait for bounce confirmation with RSI support.
    """

    def __init__(self) -> None:
        super().__init__("T")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        m5 = data.get(TF.M5)
        if m5 is None or len(m5) < 40:
            return None

        m5 = add_atr(m5.copy(), 14)
        m5 = add_rsi(m5, 14)
        m5 = add_ema(m5, 21)

        atr_val = m5["ATR_14"].iloc[-1]
        rsi_val = m5["RSI_14"].iloc[-1]
        last = m5.iloc[-1]
        prev = m5.iloc[-2]
        price = last["Close"]
        ema_val = last.get("EMA_21", price)

        # Find nearest round levels for BTC
        levels = find_round_levels(price, "btc", count=3)
        if not levels:
            return None

        nearest = min(levels, key=lambda l: abs(l[0] - price))[0]
        dist = abs(price - nearest)

        # Must be near the level (within 0.3% or 300 USD for BTC)
        threshold = max(atr_val * 0.5, 300)
        if dist > threshold:
            return None

        confluence: List[str] = [f"Near ${nearest:.0f} round level"]

        # Bullish bounce: was below, now closing above with RSI support
        if prev["Low"] <= nearest and last["Close"] > nearest and last["Close"] > last["Open"]:
            if rsi_val > 40:  # Not oversold, showing strength
                confluence.append(f"Bounce from ${nearest:.0f} support")
                if price > ema_val:
                    confluence.append("Above EMA 21")
                entry = last["Close"]
                sl = nearest - atr_val * 1.2
                tp = entry + atr_val * 3
                return self._make_signal(
                    SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                    notes=f"BTC round number bounce buy at ${nearest:.0f}",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                    data=data,
                )

        # Bearish bounce: was above, now closing below
        if prev["High"] >= nearest and last["Close"] < nearest and last["Close"] < last["Open"]:
            if rsi_val < 60:  # Not overbought
                confluence.append(f"Rejection at ${nearest:.0f} resistance")
                if price < ema_val:
                    confluence.append("Below EMA 21")
                entry = last["Close"]
                sl = nearest + atr_val * 1.2
                tp = entry - atr_val * 3
                return self._make_signal(
                    SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                    notes=f"BTC round number rejection sell at ${nearest:.0f}",
                    strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                    data=data,
                )

        return None


# ══════════════════════════════════════════════════════════════════
# U — ETH Trend Following (Day Trade, H4)
# ══════════════════════════════════════════════════════════════════
class StrategyU(BaseStrategy):
    """
    ETH trend with EMA 21/50 crossover confirmation.
    Enter on pullback after crossover.
    """

    def __init__(self) -> None:
        super().__init__("U")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        h4 = data.get(TF.H4)
        if h4 is None or len(h4) < 60:
            return None

        h4 = add_ema(h4.copy(), 21)
        h4 = add_ema(h4, 50)
        h4 = add_rsi(h4, 14)
        h4 = add_atr(h4, 14)

        ema21 = h4["EMA_21"].iloc[-1]
        ema50 = h4["EMA_50"].iloc[-1]
        prev_ema21 = h4["EMA_21"].iloc[-2]
        prev_ema50 = h4["EMA_50"].iloc[-2]
        
        rsi_val = h4["RSI_14"].iloc[-1]
        atr_val = h4["ATR_14"].iloc[-1]
        last = h4.iloc[-1]
        price = last["Close"]

        confluence: List[str] = []

        # Bullish crossover (EMA 21 crossed above EMA 50 recently)
        if ema21 > ema50 and prev_ema21 <= prev_ema50:
            confluence.append("EMA 21 crossed above EMA 50 (bullish)")
            
            # Wait for pullback to EMA 21
            if abs(price - ema21) < atr_val * 0.5:
                confluence.append("Pullback to EMA 21")
                if rsi_val > 45 and rsi_val < 70:
                    confluence.append(f"RSI healthy ({rsi_val:.1f})")
                    if last["Close"] > last["Open"]:
                        confluence.append("Bullish candle")
                        entry = last["Close"]
                        sl = ema50 - atr_val * 0.5
                        tp = entry + abs(entry - sl) * 2.5
                        return self._make_signal(
                            SignalDirection.BUY, entry, sl, tp, TF.H4, confluence,
                            notes="ETH trend following buy (EMA crossover pullback)",
                            strength=SignalStrength.STRONG if len(confluence) >= 4 else SignalStrength.MODERATE,
                            data=data,
                        )

        # Bearish crossover (EMA 21 crossed below EMA 50 recently)
        if ema21 < ema50 and prev_ema21 >= prev_ema50:
            confluence.append("EMA 21 crossed below EMA 50 (bearish)")
            
            # Wait for pullback to EMA 21
            if abs(price - ema21) < atr_val * 0.5:
                confluence.append("Pullback to EMA 21")
                if rsi_val < 55 and rsi_val > 30:
                    confluence.append(f"RSI healthy ({rsi_val:.1f})")
                    if last["Close"] < last["Open"]:
                        confluence.append("Bearish candle")
                        entry = last["Close"]
                        sl = ema50 + atr_val * 0.5
                        tp = entry - abs(sl - entry) * 2.5
                        return self._make_signal(
                            SignalDirection.SELL, entry, sl, tp, TF.H4, confluence,
                            notes="ETH trend following sell (EMA crossover pullback)",
                            strength=SignalStrength.STRONG if len(confluence) >= 4 else SignalStrength.MODERATE,
                            data=data,
                        )

        return None


# ══════════════════════════════════════════════════════════════════
# V — BTC Momentum Breakout (Scalp, M15)
# ══════════════════════════════════════════════════════════════════
class StrategyV(BaseStrategy):
    """
    BTC breakout above previous M15 session high with volume surge.
    Confirm with RSI > 55.
    """

    def __init__(self) -> None:
        super().__init__("V")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        m15 = data.get(TF.M15)
        if m15 is None or len(m15) < 20:
            return None

        m15 = add_atr(m15.copy(), 14)
        m15 = add_rsi(m15, 14)

        atr_val = m15["ATR_14"].iloc[-1]
        rsi_val = m15["RSI_14"].iloc[-1]
        last = m15.iloc[-1]

        # Session high (last 12 bars = 3 hours)
        lookback = 12
        session_high = m15["High"].iloc[-lookback:-1].max()
        session_low = m15["Low"].iloc[-lookback:-1].min()

        price = last["Close"]
        volume = last.get("Volume", 0)
        avg_volume = m15["Volume"].iloc[-lookback:-1].mean() if "Volume" in m15.columns else 0

        confluence: List[str] = []

        # Volume surge check
        volume_surge = volume > avg_volume * 1.5 if avg_volume > 0 else False

        # Bullish breakout
        if price > session_high and rsi_val > 55:
            confluence.append("Session high breakout")
            if volume_surge:
                confluence.append("Volume surge confirmed")
            if rsi_val > 60:
                confluence.append("RSI bullish zone")

            entry = last["Close"]
            sl = entry - atr_val * 1.5
            tp = entry + atr_val * 3

            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.M15, confluence,
                notes="BTC momentum breakout buy",
                strength=SignalStrength.STRONG if volume_surge else SignalStrength.MODERATE,
                data=data,
            )

        # Bearish breakout
        if price < session_low and rsi_val < 45:
            confluence.append("Session low breakdown")
            if volume_surge:
                confluence.append("Volume surge confirmed")
            if rsi_val < 40:
                confluence.append("RSI bearish zone")

            entry = last["Close"]
            sl = entry + atr_val * 1.5
            tp = entry - atr_val * 3

            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.M15, confluence,
                notes="BTC momentum breakdown sell",
                strength=SignalStrength.STRONG if volume_surge else SignalStrength.MODERATE,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# W — BTC RSI Divergence (Day, H1)
# ══════════════════════════════════════════════════════════════════
class StrategyW(BaseStrategy):
    """
    BTC RSI divergence detection.
    Bullish: price lower low, RSI higher low.
    Bearish: price higher high, RSI lower high.
    """

    def __init__(self) -> None:
        super().__init__("W")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        from indicators.momentum import detect_rsi_divergence

        h1 = data.get(TF.H1)
        if h1 is None or len(h1) < 30:
            return None

        h1 = add_atr(h1.copy(), 14)
        h1 = add_ema(h1, 50)

        atr_val = h1["ATR_14"].iloc[-1]
        ema50 = h1["EMA_50"].iloc[-1]
        last = h1.iloc[-1]
        price = last["Close"]

        # Detect divergence over last 10 bars
        divergence = detect_rsi_divergence(h1, lookback=10)
        if not divergence:
            return None

        div_type = divergence.get("type")
        swing_price = divergence.get("swing_price", price)

        confluence: List[str] = []

        if div_type == "bullish":
            confluence.append("RSI bullish divergence")
            if price > ema50:
                confluence.append("Above EMA 50")
            # Check MACD histogram for momentum shift
            if "MACD_12_26_9" in h1.columns:
                macd_hist = h1["MACD_12_26_9"].iloc[-1]
                prev_hist = h1["MACDh_12_26_9"].iloc[-2] if "MACDh_12_26_9" in h1.columns else 0
                if macd_hist > prev_hist:
                    confluence.append("Momentum shift")

            entry = last["Close"]
            sl = swing_price - atr_val * 1.2
            tp = entry + abs(entry - sl) * 2.5

            return self._make_signal(
                SignalDirection.BUY, entry, sl, tp, TF.H1, confluence,
                notes="BTC RSI bullish divergence",
                strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                data=data,
            )

        elif div_type == "bearish":
            confluence.append("RSI bearish divergence")
            if price < ema50:
                confluence.append("Below EMA 50")
            if "MACD_12_26_9" in h1.columns:
                macd_hist = h1["MACD_12_26_9"].iloc[-1]
                prev_hist = h1["MACDh_12_26_9"].iloc[-2] if "MACDh_12_26_9" in h1.columns else 0
                if macd_hist < prev_hist:
                    confluence.append("Momentum shift")

            entry = last["Close"]
            sl = swing_price + atr_val * 1.2
            tp = entry - abs(sl - entry) * 2.5

            return self._make_signal(
                SignalDirection.SELL, entry, sl, tp, TF.H1, confluence,
                notes="BTC RSI bearish divergence",
                strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                data=data,
            )

        return None


# ══════════════════════════════════════════════════════════════════
# X — ETH Order Block Sniper (Scalp, M5)
# ══════════════════════════════════════════════════════════════════
class StrategyX(BaseStrategy):
    """
    ETH order block sniper.
    Find H4 order blocks, wait for M5 return and confirmation.
    """

    def __init__(self) -> None:
        super().__init__("X")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        from indicators.structure import find_order_blocks

        m5 = data.get(TF.M5)
        h4 = data.get(TF.H4)

        if m5 is None or h4 is None or len(m5) < 30 or len(h4) < 20:
            return None

        m5 = add_atr(m5.copy(), 14)
        m5 = add_rsi(m5, 14)

        atr_val = m5["ATR_14"].iloc[-1]
        rsi_val = m5["RSI_14"].iloc[-1]
        last = m5.iloc[-1]
        price = last["Close"]

        # Find H4 order blocks
        obs = find_order_blocks(h4, lookback=10)
        if not obs:
            return None

        confluence: List[str] = []

        for ob in obs:
            ob_high = ob.get("high", 0)
            ob_low = ob.get("low", 0)
            ob_type = ob.get("type", "")  # "bullish" or "bearish"

            # Check if price is within OB zone (ATR*0.5 tolerance)
            tolerance = atr_val * 0.5
            in_zone = (ob_low - tolerance) <= price <= (ob_high + tolerance)

            if not in_zone:
                continue

            # Bullish OB
            if ob_type == "bullish" and price >= ob_low:
                confluence.append("H4 Order Block zone (bullish)")

                # M5 confirmation: bullish engulfing
                prev = m5.iloc[-2]
                if last["Close"] > prev["High"] and last["Open"] < prev["Low"]:
                    confluence.append("M5 bullish engulfing")

                # RSI check
                if 40 <= rsi_val <= 60:
                    confluence.append("RSI aligned")

                if len(confluence) >= 2:
                    entry = last["Close"]
                    sl = ob_low - atr_val * 1.0
                    tp = entry + atr_val * 2

                    return self._make_signal(
                        SignalDirection.BUY, entry, sl, tp, TF.M5, confluence,
                        notes="ETH order block buy",
                        strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                        data=data,
                    )

            # Bearish OB
            elif ob_type == "bearish" and price <= ob_high:
                confluence.append("H4 Order Block zone (bearish)")

                # M5 confirmation: bearish engulfing
                prev = m5.iloc[-2]
                if last["Close"] < prev["Low"] and last["Open"] > prev["High"]:
                    confluence.append("M5 bearish engulfing")

                # RSI check
                if 40 <= rsi_val <= 60:
                    confluence.append("RSI aligned")

                if len(confluence) >= 2:
                    entry = last["Close"]
                    sl = ob_high + atr_val * 1.0
                    tp = entry - atr_val * 2

                    return self._make_signal(
                        SignalDirection.SELL, entry, sl, tp, TF.M5, confluence,
                        notes="ETH order block sell",
                        strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                        data=data,
                    )

        return None


# ══════════════════════════════════════════════════════════════════
# Y — ETH Multi-TF Confluence (Swing, H4)
# ══════════════════════════════════════════════════════════════════
class StrategyY(BaseStrategy):
    """
    ETH multi-timeframe confluence.
    EMA stack alignment across H4 and D1.
    Entry on H4 pullback to EMA 21.
    """

    def __init__(self) -> None:
        super().__init__("Y")

    def analyze(self, data: Dict[int, pd.DataFrame]) -> Optional[Signal]:
        h4 = data.get(TF.H4)
        d1 = data.get(TF.D1)

        if h4 is None or d1 is None or len(h4) < 60 or len(d1) < 30:
            return None

        h4 = add_atr(h4.copy(), 14)
        h4 = add_ema(h4, 21)
        h4 = add_ema(h4, 50)
        h4 = add_ema(h4, 200)

        d1 = add_ema(d1.copy(), 21)
        d1 = add_ema(d1, 50)
        d1 = add_ema(d1, 200)
        d1 = add_rsi(d1, 14)

        atr_val = h4["ATR_14"].iloc[-1]
        last = h4.iloc[-1]
        price = last["Close"]

        # H4 EMA values
        h4_ema21 = h4["EMA_21"].iloc[-1]
        h4_ema50 = h4["EMA_50"].iloc[-1]
        h4_ema200 = h4["EMA_200"].iloc[-1] if "EMA_200" in h4.columns else h4_ema50

        # D1 EMA values
        d1_ema21 = d1["EMA_21"].iloc[-1]
        d1_ema50 = d1["EMA_50"].iloc[-1]
        d1_rsi = d1["RSI_14"].iloc[-1]

        confluence: List[str] = []

        # Check EMA stack alignment (bullish: 21 > 50 > 200)
        h4_bullish_stack = h4_ema21 > h4_ema50 > h4_ema200
        d1_bullish_stack = d1_ema21 > d1_ema50

        # Check EMA stack alignment (bearish: 21 < 50 < 200)
        h4_bearish_stack = h4_ema21 < h4_ema50 < h4_ema200
        d1_bearish_stack = d1_ema21 < d1_ema50

        # Bullish setup
        if h4_bullish_stack and d1_bullish_stack:
            confluence.append("H4/D1 EMA stack bullish")

            # Check pullback to H4 EMA 21
            dist_to_ema21 = abs(price - h4_ema21)
            if dist_to_ema21 < atr_val * 0.3:
                confluence.append("Pullback to H4 EMA 21")

                # D1 RSI check
                if 40 <= d1_rsi <= 60:
                    confluence.append("D1 RSI neutral")

                if len(confluence) >= 2:
                    entry = last["Close"]
                    sl = h4_ema50 - atr_val * 0.5
                    tp = entry + abs(entry - sl) * 3

                    return self._make_signal(
                        SignalDirection.BUY, entry, sl, tp, TF.H4, confluence,
                        notes="ETH multi-TF confluence buy",
                        strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                        data=data,
                    )

        # Bearish setup
        elif h4_bearish_stack and d1_bearish_stack:
            confluence.append("H4/D1 EMA stack bearish")

            # Check pullback to H4 EMA 21
            dist_to_ema21 = abs(price - h4_ema21)
            if dist_to_ema21 < atr_val * 0.3:
                confluence.append("Pullback to H4 EMA 21")

                # D1 RSI check
                if 40 <= d1_rsi <= 60:
                    confluence.append("D1 RSI neutral")

                if len(confluence) >= 2:
                    entry = last["Close"]
                    sl = h4_ema50 + atr_val * 0.5
                    tp = entry - abs(sl - entry) * 3

                    return self._make_signal(
                        SignalDirection.SELL, entry, sl, tp, TF.H4, confluence,
                        notes="ETH multi-TF confluence sell",
                        strength=SignalStrength.STRONG if len(confluence) >= 3 else SignalStrength.MODERATE,
                        data=data,
                    )

        return None
