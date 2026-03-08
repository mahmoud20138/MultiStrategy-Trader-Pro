"""
╔══════════════════════════════════════════════════════════════════╗
║     Structure Analysis — S/R, Order Blocks, FVGs, Trendlines   ║
╚══════════════════════════════════════════════════════════════════╝
Market structure tools used across multiple strategies:
  • Swing highs/lows  • Break of structure (BOS)
  • Order blocks      • Fair Value Gaps (FVG)
  • Round number levels • Fibonacci retracements
  • Trendline detection
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass

__all__ = [
    "find_swing_points", "detect_bos", "find_order_blocks",
    "find_fvg", "find_round_levels", "fibonacci_levels",
    "find_trendline_break", "find_support_resistance",
    "SwingPoint", "OrderBlock", "FairValueGap",
]


# ══════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════
@dataclass
class SwingPoint:
    index: int
    time: pd.Timestamp
    price: float
    type: str  # "high" or "low"


@dataclass
class OrderBlock:
    time: pd.Timestamp
    high: float
    low: float
    type: str  # "bullish" or "bearish"
    mitigated: bool = False


@dataclass
class FairValueGap:
    time: pd.Timestamp
    high: float
    low: float
    type: str  # "bullish" or "bearish"
    filled: bool = False


# ══════════════════════════════════════════════════════════════════
# SWING POINTS
# ══════════════════════════════════════════════════════════════════
def find_swing_points(
    df: pd.DataFrame, lookback: int = 5,
) -> List[SwingPoint]:
    """Detect swing highs and lows with N-bar lookback."""
    points = []
    highs = df["High"].values
    lows = df["Low"].values

    for i in range(lookback, len(df) - lookback):
        # Swing high
        if highs[i] == max(highs[i - lookback:i + lookback + 1]):
            points.append(SwingPoint(
                index=i, time=df.index[i], price=highs[i], type="high",
            ))
        # Swing low
        if lows[i] == min(lows[i - lookback:i + lookback + 1]):
            points.append(SwingPoint(
                index=i, time=df.index[i], price=lows[i], type="low",
            ))
    return points


# ══════════════════════════════════════════════════════════════════
# BREAK OF STRUCTURE (BOS)
# ══════════════════════════════════════════════════════════════════
def detect_bos(
    df: pd.DataFrame, lookback: int = 5,
) -> Optional[str]:
    """
    Detect Break of Structure — Strategy K (Power of 3), Strategy R (Silver Bullet).
    Returns 'bullish_bos', 'bearish_bos', or None.
    """
    swings = find_swing_points(df, lookback)
    if len(swings) < 4:
        return None

    # Get recent swing highs and lows
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]

    if len(highs) < 2 or len(lows) < 2:
        return None

    current_price = df["Close"].iloc[-1]

    # Bullish BOS: price breaks above the most recent swing high
    last_high = highs[-1]
    if current_price > last_high.price and last_high.index < len(df) - 2:
        return "bullish_bos"

    # Bearish BOS: price breaks below the most recent swing low
    last_low = lows[-1]
    if current_price < last_low.price and last_low.index < len(df) - 2:
        return "bearish_bos"

    return None


# ══════════════════════════════════════════════════════════════════
# ORDER BLOCKS
# ══════════════════════════════════════════════════════════════════
def find_order_blocks(
    df: pd.DataFrame, lookback: int = 50,
) -> List[OrderBlock]:
    """
    Identify order blocks (last opposing candle before a strong move).
    Used by Strategy B (VWAP+OB Sniper) and Strategy K (Power of 3).
    """
    obs: List[OrderBlock] = []
    data = df.iloc[-lookback:] if len(df) > lookback else df

    for i in range(2, len(data)):
        # Bullish OB: bearish candle followed by strong bullish move
        if (data["Close"].iloc[i-1] < data["Open"].iloc[i-1] and  # bearish candle
            data["Close"].iloc[i] > data["High"].iloc[i-1]):       # strong close above
            ob = OrderBlock(
                time=data.index[i-1],
                high=data["High"].iloc[i-1],
                low=data["Low"].iloc[i-1],
                type="bullish",
            )
            # Check if mitigated (price returned to OB)
            subsequent = data.iloc[i:]
            if len(subsequent) > 0 and subsequent["Low"].min() <= ob.high:
                ob.mitigated = True
            obs.append(ob)

        # Bearish OB: bullish candle followed by strong bearish move
        if (data["Close"].iloc[i-1] > data["Open"].iloc[i-1] and  # bullish candle
            data["Close"].iloc[i] < data["Low"].iloc[i-1]):        # strong close below
            ob = OrderBlock(
                time=data.index[i-1],
                high=data["High"].iloc[i-1],
                low=data["Low"].iloc[i-1],
                type="bearish",
            )
            subsequent = data.iloc[i:]
            if len(subsequent) > 0 and subsequent["High"].max() >= ob.low:
                ob.mitigated = True
            obs.append(ob)

    return obs


# ══════════════════════════════════════════════════════════════════
# FAIR VALUE GAPS (FVG)
# ══════════════════════════════════════════════════════════════════
def find_fvg(
    df: pd.DataFrame, lookback: int = 50,
) -> List[FairValueGap]:
    """
    Detect Fair Value Gaps (3-candle imbalance).
    Used by Strategy K (Power of 3) and Strategy R (Silver Bullet).
    """
    fvgs: List[FairValueGap] = []
    data = df.iloc[-lookback:] if len(df) > lookback else df

    for i in range(2, len(data)):
        # Bullish FVG: candle 3's low > candle 1's high
        if data["Low"].iloc[i] > data["High"].iloc[i-2]:
            fvg = FairValueGap(
                time=data.index[i-1],
                high=data["Low"].iloc[i],
                low=data["High"].iloc[i-2],
                type="bullish",
            )
            # Check if filled
            if i < len(data) - 1:
                subsequent = data.iloc[i+1:]
                if len(subsequent) > 0 and subsequent["Low"].min() <= fvg.low:
                    fvg.filled = True
            fvgs.append(fvg)

        # Bearish FVG: candle 3's high < candle 1's low
        if data["High"].iloc[i] < data["Low"].iloc[i-2]:
            fvg = FairValueGap(
                time=data.index[i-1],
                high=data["Low"].iloc[i-2],
                low=data["High"].iloc[i],
                type="bearish",
            )
            if i < len(data) - 1:
                subsequent = data.iloc[i+1:]
                if len(subsequent) > 0 and subsequent["High"].max() >= fvg.high:
                    fvg.filled = True
            fvgs.append(fvg)

    return fvgs


# ══════════════════════════════════════════════════════════════════
# ROUND NUMBER LEVELS
# ══════════════════════════════════════════════════════════════════
def find_round_levels(
    current_price: float,
    instrument: str,
    count: int = 5,
) -> List[Tuple[float, str]]:
    """
    Generate round number levels near current price.
    Strategy Q (US30 Round Number Bounce).
    Returns list of (level, significance) sorted by distance.
    """
    steps = {
        "gold":   [10, 25, 50, 100],
        "nas100": [50, 100, 250, 500],
        "us500":  [25, 50, 100, 250],
        "us30":   [50, 100, 500, 1000],
        "btc":    [1000, 2500, 5000, 10000],   # Bitcoin round levels
        "eth":    [100, 250, 500, 1000],       # Ethereum round levels
    }
    instrument_steps = steps.get(instrument, [50, 100, 500])

    levels = []
    for step in instrument_steps:
        sig = "minor" if step == instrument_steps[0] else (
            "major" if step == instrument_steps[-1] else "medium"
        )
        base = round(current_price / step) * step
        for offset in range(-count, count + 1):
            level = base + offset * step
            dist = abs(level - current_price)
            levels.append((level, sig, dist))

    # Sort by distance from price, take closest
    levels.sort(key=lambda x: x[2])
    seen = set()
    result = []
    for lv, sig, _ in levels:
        if lv not in seen:
            seen.add(lv)
            result.append((lv, sig))
            if len(result) >= count * 2:
                break
    return result


# ══════════════════════════════════════════════════════════════════
# FIBONACCI RETRACEMENTS
# ══════════════════════════════════════════════════════════════════
def fibonacci_levels(
    swing_high: float,
    swing_low: float,
    direction: str = "up",
) -> dict:
    """
    Calculate Fibonacci retracement levels.
    Strategy H (Fibonacci Cluster) and Strategy F.
    """
    diff = swing_high - swing_low
    if direction == "up":
        return {
            "0.0": swing_high,
            "0.236": swing_high - diff * 0.236,
            "0.382": swing_high - diff * 0.382,
            "0.5": swing_high - diff * 0.5,
            "0.618": swing_high - diff * 0.618,
            "0.786": swing_high - diff * 0.786,
            "1.0": swing_low,
            "1.272": swing_low - diff * 0.272,
            "1.618": swing_low - diff * 0.618,
        }
    else:
        return {
            "0.0": swing_low,
            "0.236": swing_low + diff * 0.236,
            "0.382": swing_low + diff * 0.382,
            "0.5": swing_low + diff * 0.5,
            "0.618": swing_low + diff * 0.618,
            "0.786": swing_low + diff * 0.786,
            "1.0": swing_high,
            "1.272": swing_high + diff * 0.272,
            "1.618": swing_high + diff * 0.618,
        }


def fibonacci_cluster(
    df: pd.DataFrame, lookback: int = 100, tolerance_pct: float = 0.3,
) -> List[Tuple[float, int]]:
    """
    Find zones where multiple Fibonacci levels cluster (Strategy H).
    Returns list of (price_level, cluster_count) sorted by count.
    """
    swings = find_swing_points(df, lookback=5)
    highs = [s for s in swings if s.type == "high"]
    lows = [s for s in swings if s.type == "low"]

    all_fib_levels = []
    # Generate Fibs from multiple swing pairs
    for h in highs[-4:]:
        for l in lows[-4:]:
            if h.index != l.index:
                fibs = fibonacci_levels(h.price, l.price, "up" if h.index > l.index else "down")
                all_fib_levels.extend(fibs.values())

    if not all_fib_levels:
        return []

    # Cluster nearby levels
    all_fib_levels.sort()
    clusters = []
    current_cluster = [all_fib_levels[0]]

    for i in range(1, len(all_fib_levels)):
        if abs(all_fib_levels[i] - current_cluster[-1]) / current_cluster[-1] * 100 < tolerance_pct:
            current_cluster.append(all_fib_levels[i])
        else:
            if len(current_cluster) >= 2:
                avg = sum(current_cluster) / len(current_cluster)
                clusters.append((avg, len(current_cluster)))
            current_cluster = [all_fib_levels[i]]

    if len(current_cluster) >= 2:
        avg = sum(current_cluster) / len(current_cluster)
        clusters.append((avg, len(current_cluster)))

    clusters.sort(key=lambda x: x[1], reverse=True)
    return clusters


# ══════════════════════════════════════════════════════════════════
# TRENDLINE DETECTION
# ══════════════════════════════════════════════════════════════════
def find_trendline_break(
    df: pd.DataFrame,
    min_touches: int = 3,
    lookback: int = 100,
) -> Optional[dict]:
    """
    Detect trendline breaks (Strategy F — Trendline Break+Retest).
    Finds trendlines with at least `min_touches` touches, checks if current
    price has broken through.

    Returns dict with trendline info or None.
    """
    swings = find_swing_points(df.iloc[-lookback:], lookback=3)
    lows = [s for s in swings if s.type == "low"]
    highs = [s for s in swings if s.type == "high"]

    current = df["Close"].iloc[-1]
    result = None

    # ── Upward trendline (connecting lows) — bearish break ──
    if len(lows) >= min_touches:
        for i in range(len(lows) - min_touches + 1):
            subset = lows[i:i + min_touches]
            if all(subset[j].price <= subset[j+1].price for j in range(len(subset)-1)):
                # Rising trendline
                x1, y1 = subset[0].index, subset[0].price
                x2, y2 = subset[-1].index, subset[-1].price
                if x2 - x1 == 0:
                    continue
                slope = (y2 - y1) / (x2 - x1)
                projected = y2 + slope * (len(df) - 1 - x2)
                if current < projected:
                    result = {
                        "type": "bearish_break",
                        "touches": len(subset),
                        "trendline_price": projected,
                        "break_distance": projected - current,
                        "slope": slope,
                    }

    # ── Downward trendline (connecting highs) — bullish break ──
    if len(highs) >= min_touches:
        for i in range(len(highs) - min_touches + 1):
            subset = highs[i:i + min_touches]
            if all(subset[j].price >= subset[j+1].price for j in range(len(subset)-1)):
                x1, y1 = subset[0].index, subset[0].price
                x2, y2 = subset[-1].index, subset[-1].price
                if x2 - x1 == 0:
                    continue
                slope = (y2 - y1) / (x2 - x1)
                projected = y2 + slope * (len(df) - 1 - x2)
                if current > projected:
                    result = {
                        "type": "bullish_break",
                        "touches": len(subset),
                        "trendline_price": projected,
                        "break_distance": current - projected,
                        "slope": slope,
                    }

    return result


# ══════════════════════════════════════════════════════════════════
# SUPPORT / RESISTANCE ZONES
# ══════════════════════════════════════════════════════════════════
def find_support_resistance(
    df: pd.DataFrame,
    lookback: int = 200,
    tolerance_pct: float = 0.2,
    min_touches: int = 2,
) -> List[Tuple[float, int, str]]:
    """
    Find S/R zones via swing point clustering.
    Returns [(price, touch_count, 'support'|'resistance'), ...].
    """
    swings = find_swing_points(df.iloc[-lookback:], lookback=5)
    prices = [s.price for s in swings]
    if not prices:
        return []

    prices.sort()
    clusters = []
    current_cluster = [prices[0]]

    for i in range(1, len(prices)):
        if abs(prices[i] - current_cluster[-1]) / current_cluster[-1] * 100 < tolerance_pct:
            current_cluster.append(prices[i])
        else:
            if len(current_cluster) >= min_touches:
                avg = sum(current_cluster) / len(current_cluster)
                clusters.append((avg, len(current_cluster)))
            current_cluster = [prices[i]]

    if len(current_cluster) >= min_touches:
        avg = sum(current_cluster) / len(current_cluster)
        clusters.append((avg, len(current_cluster)))

    current_price = df["Close"].iloc[-1]
    result = []
    for level, count in clusters:
        sr_type = "support" if level < current_price else "resistance"
        result.append((level, count, sr_type))

    result.sort(key=lambda x: abs(x[0] - current_price))
    return result
