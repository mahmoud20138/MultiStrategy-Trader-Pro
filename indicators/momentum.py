"""
╔══════════════════════════════════════════════════════════════════╗
║       Momentum Indicators — RSI, MACD, Stochastic, Divergence  ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple

__all__ = [
    "add_rsi",
    "add_macd",
    "add_stochastic",
    "detect_rsi_divergence",
    "rsi_zone",
    "stoch_signal",
]


def add_rsi(df: pd.DataFrame, period: int = 14, col: str = "Close") -> pd.DataFrame:
    """Add RSI column using Wilder's smoothing."""
    delta = df[col].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df[f"RSI_{period}"] = rsi
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Add MACD, MACD Signal, and MACD Histogram."""
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    df["MACD"] = macd_line
    df["MACD_Signal"] = signal_line
    df["MACD_Hist"] = histogram
    return df


def add_stochastic(
    df: pd.DataFrame,
    k: int = 14,
    d: int = 3,
    smooth_k: int = 3,
) -> pd.DataFrame:
    """Add Stochastic %K and %D."""
    low_min = df["Low"].rolling(window=k).min()
    high_max = df["High"].rolling(window=k).max()

    stoch_k = 100 * (df["Close"] - low_min) / (high_max - low_min)
    stoch_k = stoch_k.rolling(window=smooth_k).mean()  # Smooth %K
    stoch_d = stoch_k.rolling(window=d).mean()  # %D is SMA of %K

    df["Stoch_K"] = stoch_k
    df["Stoch_D"] = stoch_d
    return df


def detect_rsi_divergence(
    df: pd.DataFrame,
    rsi_col: str = "RSI_14",
    lookback: int = 30,
    price_col: str = "Close",
) -> Optional[str]:
    """
    Detect bullish/bearish RSI divergence in the last `lookback` bars.
    Bullish: price makes lower low, RSI makes higher low
    Bearish: price makes higher high, RSI makes lower high

    Returns 'bullish_div', 'bearish_div', or None.
    Used by Strategy D (DXY Divergence) and Strategy P (RSI+Structure).
    """
    if rsi_col not in df.columns or len(df) < lookback:
        return None

    price = df[price_col].iloc[-lookback:]
    rsi = df[rsi_col].iloc[-lookback:]

    # Find swing points (simplified: compare to neighbors)
    def find_lows(series: pd.Series, n: int = 5) -> List[Tuple[int, float]]:
        lows = []
        for i in range(n, len(series) - n):
            if series.iloc[i] == series.iloc[i - n : i + n + 1].min():
                lows.append((i, series.iloc[i]))
        return lows

    def find_highs(series: pd.Series, n: int = 5) -> List[Tuple[int, float]]:
        highs = []
        for i in range(n, len(series) - n):
            if series.iloc[i] == series.iloc[i - n : i + n + 1].max():
                highs.append((i, series.iloc[i]))
        return highs

    # ── Bullish divergence ──
    price_lows = find_lows(price)
    rsi_lows = find_lows(rsi)
    if len(price_lows) >= 2 and len(rsi_lows) >= 2:
        p1, p2 = price_lows[-2], price_lows[-1]
        r1, r2 = rsi_lows[-2], rsi_lows[-1]
        if p2[1] < p1[1] and r2[1] > r1[1]:
            return "bullish_div"

    # ── Bearish divergence ──
    price_highs = find_highs(price)
    rsi_highs = find_highs(rsi)
    if len(price_highs) >= 2 and len(rsi_highs) >= 2:
        p1, p2 = price_highs[-2], price_highs[-1]
        r1, r2 = rsi_highs[-2], rsi_highs[-1]
        if p2[1] > p1[1] and r2[1] < r1[1]:
            return "bearish_div"

    return None


def rsi_zone(df: pd.DataFrame, period: int = 14) -> str:
    """
    Classify current RSI zone.
    Used by Strategy P: RSI 40-50 = bullish pullback zone.
    """
    col = f"RSI_{period}"
    if col not in df.columns:
        add_rsi(df, period)
    val = df[col].iloc[-1]
    if np.isnan(val):
        return "unknown"
    if val >= 70:
        return "overbought"
    if val >= 50:
        return "bullish"
    if val >= 40:
        return "pullback_zone"  # Strategy P sweet spot
    if val >= 30:
        return "bearish"
    return "oversold"


def stoch_signal(df: pd.DataFrame) -> Optional[str]:
    """
    Stochastic cross signal. Used by Strategy J (EMA Ribbon).
    Returns 'bullish_cross', 'bearish_cross', or None.
    """
    if "Stoch_K" not in df.columns or "Stoch_D" not in df.columns:
        return None
    if len(df) < 2:
        return None

    k_now, d_now = df["Stoch_K"].iloc[-1], df["Stoch_D"].iloc[-1]
    k_prev, d_prev = df["Stoch_K"].iloc[-2], df["Stoch_D"].iloc[-2]

    if np.isnan(k_now) or np.isnan(d_now):
        return None

    if k_prev <= d_prev and k_now > d_now and k_now < 20:
        return "bullish_cross"
    if k_prev >= d_prev and k_now < d_now and k_now > 80:
        return "bearish_cross"
    return None
