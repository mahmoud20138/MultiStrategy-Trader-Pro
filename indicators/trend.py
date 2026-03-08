"""
╔══════════════════════════════════════════════════════════════════╗
║            Trend Indicators — EMA, SMA, VWAP, Supertrend       ║
╚══════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional

__all__ = [
    "add_ema",
    "add_sma",
    "add_ema_ribbon",
    "add_vwap",
    "add_supertrend",
    "ema_trend_direction",
    "ema_stack_signal",
]


def add_ema(df: pd.DataFrame, period: int, col: str = "Close") -> pd.DataFrame:
    """Add EMA column using pandas ewm."""
    df[f"EMA_{period}"] = df[col].ewm(span=period, adjust=False).mean()
    return df


def add_sma(df: pd.DataFrame, period: int, col: str = "Close") -> pd.DataFrame:
    """Add SMA column using pandas rolling mean."""
    df[f"SMA_{period}"] = df[col].rolling(window=period).mean()
    return df


def add_ema_ribbon(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    """Add EMA ribbon (default: 9, 21, 55 for Strategy J)."""
    if periods is None:
        periods = [9, 21, 55]
    for p in periods:
        df[f"EMA_{p}"] = df["Close"].ewm(span=p, adjust=False).mean()
    return df


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    VWAP — Volume-Weighted Average Price.
    Manual calculation using typical price and cumulative volumes.
    """
    # Typical price
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    cumvol = df["Volume"].cumsum()
    cumtp = (tp * df["Volume"]).cumsum()
    df["VWAP"] = cumtp / cumvol.replace(0, np.nan)
    return df


def add_vwap_bands(df: pd.DataFrame, std_mult: float = 1.0) -> pd.DataFrame:
    """Add VWAP with upper/lower bands (for Strategy N — VWAP Mean Reversion)."""
    if "VWAP" not in df.columns:
        add_vwap(df)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    dev = tp.rolling(20).std() * std_mult
    df["VWAP_Upper"] = df["VWAP"] + dev
    df["VWAP_Lower"] = df["VWAP"] - dev
    return df


def add_supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
) -> pd.DataFrame:
    """Add Supertrend indicator (for Multi-TF Trend — Strategy O)."""
    # Calculate ATR (Average True Range)
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period).mean()

    # Calculate basic bands
    hl_avg = (df["High"] + df["Low"]) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)

    # Initialize supertrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    for i in range(period, len(df)):
        if i == period:
            supertrend.iloc[i] = lower_band.iloc[i]
            direction.iloc[i] = 1
        else:
            # Update supertrend based on previous values
            if df["Close"].iloc[i] > supertrend.iloc[i - 1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif df["Close"].iloc[i] < supertrend.iloc[i - 1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i - 1]
                direction.iloc[i] = direction.iloc[i - 1]

            # Adjust for band crossovers
            if direction.iloc[i] == 1 and supertrend.iloc[i] < supertrend.iloc[i - 1]:
                supertrend.iloc[i] = supertrend.iloc[i - 1]
            elif (
                direction.iloc[i] == -1 and supertrend.iloc[i] > supertrend.iloc[i - 1]
            ):
                supertrend.iloc[i] = supertrend.iloc[i - 1]

    df["Supertrend"] = supertrend
    df["Supertrend_Dir"] = direction
    return df


def ema_trend_direction(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> str:
    """Return 'bullish', 'bearish', or 'neutral' based on EMA cross."""
    f_col, s_col = f"EMA_{fast}", f"EMA_{slow}"
    if f_col not in df.columns:
        add_ema(df, fast)
    if s_col not in df.columns:
        add_ema(df, slow)
    if df[f_col].iloc[-1] > df[s_col].iloc[-1]:
        return "bullish"
    elif df[f_col].iloc[-1] < df[s_col].iloc[-1]:
        return "bearish"
    return "neutral"


def ema_stack_signal(df: pd.DataFrame, periods: list = None) -> Optional[str]:
    """
    Check if EMAs are perfectly stacked (Strategy J — EMA Ribbon).
    Returns 'bullish_stack', 'bearish_stack', or None.
    """
    if periods is None:
        periods = [9, 21, 55]
    vals = []
    for p in periods:
        col = f"EMA_{p}"
        if col not in df.columns:
            return None
        vals.append(df[col].iloc[-1])

    if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
        return "bullish_stack"
    if all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
        return "bearish_stack"
    return None
