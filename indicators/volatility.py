"""
╔══════════════════════════════════════════════════════════════════╗
║    Volatility Indicators — BBands, ATR, Asian Range, Keltner   ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional, Tuple

__all__ = [
    "add_bbands",
    "add_atr",
    "add_keltner",
    "calculate_asian_range",
    "is_range_day",
    "calculate_gap",
]


def add_bbands(
    df: pd.DataFrame,
    period: int = 20,
    std: float = 2.0,
) -> pd.DataFrame:
    """Add Bollinger Bands (upper, mid, lower)."""
    sma = df["Close"].rolling(window=period).mean()
    rolling_std = df["Close"].rolling(window=period).std()

    df["BB_Mid"] = sma
    df["BB_Upper"] = sma + (rolling_std * std)
    df["BB_Lower"] = sma - (rolling_std * std)
    df["BB_Width"] = df["BB_Upper"] - df["BB_Lower"]
    df["BB_Pct"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Average True Range using Wilder's smoothing."""
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df[f"ATR_{period}"] = true_range.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add Average True Range using Wilder's smoothing."""
    # Normalize column names to lowercase
    df.columns = [c.lower() if isinstance(c, str) else c for c in df.columns]
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df[f"ATR_{period}"] = true_range.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()
    return df


def add_keltner(
    df: pd.DataFrame,
    period: int = 20,
    multiplier: float = 1.5,
) -> pd.DataFrame:
    """Add Keltner Channel (EMA ± ATR*mult)."""
    ema = df["Close"].ewm(span=period, adjust=False).mean()

    if f"ATR_{period}" not in df.columns:
        add_atr(df, period)
    atr = df[f"ATR_{period}"]

    df["KC_Mid"] = ema
    df["KC_Upper"] = ema + atr * multiplier
    df["KC_Lower"] = ema - atr * multiplier
    return df


def calculate_asian_range(
    df: pd.DataFrame,
    start_hour: int = 0,
    end_hour: int = 6,
) -> Optional[Tuple[float, float, float]]:
    """
    Calculate the Asian session range (Strategy A — London Breakout Trap).
    Returns (high, low, range_size) for the most recent Asian session.
    Expects UTC-indexed DataFrame on M5/M15.
    """
    if df.index.tz is None:
        return None

    today = df.index[-1].date()
    mask = (df.index.hour >= start_hour) & (df.index.hour < end_hour)
    # Try today first, fall back to yesterday
    asian = df[mask & (df.index.date == today)]
    if len(asian) < 3:
        from datetime import timedelta

        yesterday = today - timedelta(days=1)
        asian = df[mask & (df.index.date == yesterday)]
    if len(asian) < 3:
        return None

    high = asian["High"].max()
    low = asian["Low"].min()
    return high, low, high - low


def is_range_day(
    df: pd.DataFrame,
    atr_period: int = 14,
    threshold: float = 0.7,
) -> bool:
    """
    Determine if today is a range day (Strategy N — VWAP Mean Reversion).
    Range day = today's range < threshold × ATR.
    """
    atr_col = f"ATR_{atr_period}"
    if atr_col not in df.columns:
        add_atr(df, atr_period)
    atr_val = df[atr_col].iloc[-1]
    if np.isnan(atr_val) or atr_val == 0:
        return False

    # Current day range
    today = df.index[-1].date()
    today_data = df[df.index.date == today]
    if len(today_data) < 2:
        return False
    day_range = today_data["High"].max() - today_data["Low"].min()
    return day_range < atr_val * threshold


def calculate_gap(
    df_daily: pd.DataFrame,
) -> Optional[Tuple[float, str]]:
    """
    Calculate overnight gap % for Strategy L (NAS100 Gap Fill).
    Returns (gap_percent, 'gap_up' | 'gap_down') or None.
    gap < 1% → fade, gap > 1.5% → continuation
    """
    if len(df_daily) < 2:
        return None
    prev_close = df_daily["Close"].iloc[-2]
    today_open = df_daily["Open"].iloc[-1]
    if prev_close == 0:
        return None
    gap_pct = (today_open - prev_close) / prev_close * 100
    direction = "gap_up" if gap_pct > 0 else "gap_down"
    return abs(gap_pct), direction
