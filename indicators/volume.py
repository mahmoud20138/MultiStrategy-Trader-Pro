"""
╔══════════════════════════════════════════════════════════════════╗
║              Volume Indicators & Analysis                       ║
╚══════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import pandas as pd
import numpy as np

__all__ = [
    "add_volume_sma", "volume_surge", "add_obv", "volume_confirms_breakout",
]


def add_volume_sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Add volume SMA for comparison."""
    df[f"Vol_SMA_{period}"] = df["Volume"].rolling(window=period).mean()
    return df


def volume_surge(
    df: pd.DataFrame, period: int = 20, threshold: float = 1.5,
) -> bool:
    """
    Check if current volume is surging above average.
    Used by Strategy I (ORB), Strategy S (Breakout-Retest).
    """
    col = f"Vol_SMA_{period}"
    if col not in df.columns:
        add_volume_sma(df, period)
    avg = df[col].iloc[-1]
    if np.isnan(avg) or avg == 0:
        return False
    return df["Volume"].iloc[-1] > avg * threshold


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """Add On-Balance Volume."""
    obv = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i-1]:
            obv.append(obv[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i-1]:
            obv.append(obv[-1] - df["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    df["OBV"] = obv
    return df


def volume_confirms_breakout(
    df: pd.DataFrame, lookback: int = 5, threshold: float = 1.5,
) -> bool:
    """
    Verify breakout has volume confirmation.
    Breakout bar volume > threshold × average of prior `lookback` bars.
    """
    if len(df) < lookback + 1:
        return False
    avg_vol = df["Volume"].iloc[-(lookback + 1):-1].mean()
    current_vol = df["Volume"].iloc[-1]
    if avg_vol == 0:
        return False
    return current_vol > avg_vol * threshold
