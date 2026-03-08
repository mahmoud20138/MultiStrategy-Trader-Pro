"""
╔══════════════════════════════════════════════════════════════════╗
║                   Chart Builder (Plotly)                        ║
╚══════════════════════════════════════════════════════════════════╝
Candlestick + EMA / VWAP / Bollinger overlays + signal markers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from indicators.trend import add_ema, add_vwap
from indicators.volatility import add_bbands
from indicators.momentum import add_rsi
from dashboard.layout import CLR


def build_chart(
    df: pd.DataFrame,
    signals: List[Dict[str, Any]] | None = None,
    show_ema: bool = True,
    show_bb: bool = True,
    show_vwap: bool = True,
    show_volume: bool = True,
    show_rsi: bool = True,
    title: str = "",
) -> go.Figure:
    """Build a professional candlestick chart with overlays."""

    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No data",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=20, color=CLR["muted"]),
                )
            ],
        )
        return fig

    df = df.copy()

    # Use column names as-is from MT5 (capitalized: Open, High, Low, Close, Volume)
    rows = 1
    row_heights = [0.7]
    if show_volume:
        rows += 1
        row_heights.append(0.15)
    if show_rsi:
        rows += 1
        row_heights.append(0.15)

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=row_heights,
    )

    # ── Candlestick ─────────────────────────────────────────
    fig.add_trace(
        go.Candlestick(
            x=df.index
            if not isinstance(df.index, pd.RangeIndex)
            else df.get("time", df.index),
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            increasing_line_color=CLR["green"],
            decreasing_line_color=CLR["red"],
            name="Price",
        ),
        row=1,
        col=1,
    )

    # ── EMA overlays ────────────────────────────────────────
    if show_ema:
        for period, color in [
            (21, CLR["blue"]),
            (50, CLR["yellow"]),
            (200, CLR["muted"]),
        ]:
            col_name = f"EMA_{period}"
            df = add_ema(df, period)
            if col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col_name],
                        mode="lines",
                        line=dict(width=1, color=color),
                        name=col_name,
                    ),
                    row=1,
                    col=1,
                )

    # ── VWAP ────────────────────────────────────────────────
    if show_vwap and "Volume" in df.columns:
        df = add_vwap(df)
        if "VWAP" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["VWAP"],
                    mode="lines",
                    line=dict(width=1.5, color="#e0aaff", dash="dash"),
                    name="VWAP",
                ),
                row=1,
                col=1,
            )

    # ── Bollinger Bands ─────────────────────────────────────
    if show_bb:
        df = add_bbands(df)
        for col, dash in [("BBU_20_2.0", "dot"), ("BBL_20_2.0", "dot")]:
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df[col],
                        mode="lines",
                        line=dict(width=0.8, color=CLR["muted"], dash=dash),
                        name=col[:3],
                    ),
                    row=1,
                    col=1,
                )

    # ── Volume bars ─────────────────────────────────────────
    current_row = 2
    if show_volume and "Volume" in df.columns:
        colours = [
            CLR["green"] if c >= o else CLR["red"]
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                marker_color=colours,
                opacity=0.5,
                name="Volume",
            ),
            row=current_row,
            col=1,
        )
        current_row += 1

    # ── RSI ─────────────────────────────────────────────────
    if show_rsi:
        from indicators.momentum import add_rsi as _add_rsi

        df = _add_rsi(df, 14)
        rsi_col = "RSI_14"
        if rsi_col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[rsi_col],
                    mode="lines",
                    line=dict(width=1, color=CLR["blue"]),
                    name="RSI 14",
                ),
                row=current_row,
                col=1,
            )
            # 70 / 30 lines
            for lv, clr in [(70, CLR["red"]), (30, CLR["green"])]:
                fig.add_hline(
                    y=lv,
                    line_dash="dot",
                    line_color=clr,
                    opacity=0.5,
                    row=current_row,
                    col=1,
                )

    # ── Signal markers ──────────────────────────────────────
    if signals:
        for sig in signals:
            direction = sig.get("direction", "")
            entry = sig.get("entry", 0)
            ts = sig.get("timestamp", "")
            marker_color = CLR["green"] if direction == "BUY" else CLR["red"]
            marker_symbol = "triangle-up" if direction == "BUY" else "triangle-down"

            fig.add_trace(
                go.Scatter(
                    x=[ts] if ts else [df.index[-1]],
                    y=[entry],
                    mode="markers+text",
                    marker=dict(symbol=marker_symbol, size=14, color=marker_color),
                    text=[f"{sig.get('strategy_id', '')} {direction}"],
                    textposition="top center",
                    textfont=dict(size=9, color=marker_color),
                    name=f"Signal {sig.get('strategy_id', '')}",
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

            # SL / TP lines
            sl = sig.get("sl", 0)
            tp = sig.get("tp", 0)
            if sl:
                fig.add_hline(
                    y=sl,
                    line_dash="dash",
                    line_color=CLR["red"],
                    opacity=0.4,
                    row=1,
                    col=1,
                    annotation_text=f"SL {sl:.2f}",
                    annotation_font_color=CLR["red"],
                )
            if tp:
                fig.add_hline(
                    y=tp,
                    line_dash="dash",
                    line_color=CLR["green"],
                    opacity=0.4,
                    row=1,
                    col=1,
                    annotation_text=f"TP {tp:.2f}",
                    annotation_font_color=CLR["green"],
                )

    # ── Layout ──────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=14, color=CLR["text"])),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=9)),
        margin=dict(l=50, r=20, t=40, b=20),
        height=500,
    )
    fig.update_xaxes(gridcolor=CLR["border"])
    fig.update_yaxes(gridcolor=CLR["border"])

    return fig


# ══════════════════════════════════════════════════════════════════
# PERFORMANCE DASHBOARD CHARTS (T017)
# ══════════════════════════════════════════════════════════════════


def calculate_drawdown(equity_series: pd.Series) -> pd.DataFrame:
    """
    Calculate drawdown metrics from equity curve.
    Returns DataFrame with equity, drawdown, drawdown_pct, running_max columns.
    """
    if equity_series is None or len(equity_series) == 0:
        return pd.DataFrame(
            columns=["equity", "drawdown", "drawdown_pct", "running_max"]
        )

    df = pd.DataFrame(index=equity_series.index)
    df["equity"] = equity_series
    df["running_max"] = equity_series.expanding().max()
    df["drawdown"] = df["running_max"] - df["equity"]
    df["drawdown_pct"] = (
        (df["drawdown"] / df["running_max"] * 100)
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
    )

    return df


def build_equity_chart(df: pd.DataFrame, title: str = "Equity Curve") -> go.Figure:
    """
    Build equity curve chart with fill to zero.
    Expects DataFrame with 'equity' or 'cumulative_pnl' column, and time index.
    """
    fig = go.Figure()

    if df is None or df.empty:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No equity data",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    # Get equity column
    if "equity" in df.columns:
        y_values = df["equity"]
    elif "cumulative_pnl" in df.columns:
        y_values = df["cumulative_pnl"]
    elif "net_pnl" in df.columns:
        y_values = df["net_pnl"].cumsum()
    else:
        y_values = df.iloc[:, 0] if len(df.columns) > 0 else pd.Series([0])

    x_values = (
        df.index
        if not isinstance(df.index, pd.RangeIndex)
        else df.get("time", df.index)
    )

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(63, 185, 80, 0.15)",
            line=dict(color=CLR["green"], width=2),
            name="Equity",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=12, color=CLR["text"])),
        margin=dict(l=40, r=20, t=30, b=30),
        height=300,
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CLR["border"]),
        yaxis=dict(showgrid=True, gridcolor=CLR["border"], tickprefix="$"),
    )

    return fig


def build_drawdown_chart(df: pd.DataFrame, title: str = "Drawdown") -> go.Figure:
    """
    Build drawdown chart as stacked area.
    Shows running max (invisible) + equity (fill to nexty).
    """
    fig = go.Figure()

    if df is None or df.empty or "drawdown_pct" not in df.columns:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No drawdown data",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    x_values = (
        df.index
        if not isinstance(df.index, pd.RangeIndex)
        else df.get("time", df.index)
    )

    # Drawdown as negative area (inverted)
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=-df["drawdown_pct"],  # Negative for visual effect (draws down)
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(248, 81, 73, 0.3)",
            line=dict(color=CLR["red"], width=1.5),
            name="Drawdown %",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=12, color=CLR["text"])),
        margin=dict(l=40, r=20, t=30, b=30),
        height=250,
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CLR["border"]),
        yaxis=dict(showgrid=True, gridcolor=CLR["border"], ticksuffix="%"),
    )

    return fig


def build_strategy_heatmap(
    df: pd.DataFrame, title: str = "Strategy Win Rate Heatmap"
) -> go.Figure:
    """
    Build heatmap of win rates by strategy and symbol.
    Expects DataFrame with 'strategy_id', 'symbol', and outcome/profit columns.
    """
    fig = go.Figure()

    if df is None or df.empty:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No trade data for heatmap",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    # Calculate win rate per strategy x symbol
    if "outcome" in df.columns:
        df["is_win"] = df["outcome"] == "WIN"
    elif "profit" in df.columns:
        df["is_win"] = df["profit"] > 0
    else:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="Missing outcome column",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    pivot = df.groupby(["strategy_id", "symbol"])["is_win"].mean().reset_index()
    pivot["win_rate"] = (pivot["is_win"] * 100).round(1)

    if pivot.empty:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="Insufficient data",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    # Pivot to matrix
    matrix = pivot.pivot(index="strategy_id", columns="symbol", values="win_rate")

    fig.add_trace(
        go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            colorscale="RdYlGn",
            zmid=50,
            zmin=0,
            zmax=100,
            text=[
                [f"{v:.0f}%" if pd.notna(v) else "-" for v in row]
                for row in matrix.values
            ],
            texttemplate="%{text}",
            textfont=dict(size=10),
            colorbar=dict(title="Win %", tickfont=dict(size=9)),
            hovertemplate="Strategy: %{y}<br>Symbol: %{x}<br>Win Rate: %{z:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=12, color=CLR["text"])),
        margin=dict(l=60, r=20, t=30, b=40),
        height=350,
        xaxis=dict(title="Symbol", tickfont=dict(size=9)),
        yaxis=dict(title="Strategy", tickfont=dict(size=9)),
    )

    return fig


def build_daily_pnl_chart(df: pd.DataFrame, title: str = "Daily P&L") -> go.Figure:
    """
    Build daily P&L bar chart with per-bar color coding.
    Expects DataFrame with date index and 'profit' or 'net_pnl' column.
    """
    fig = go.Figure()

    if df is None or df.empty:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No daily P&L data",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    # Get P&L column
    if "profit" in df.columns:
        pnl = df["profit"]
    elif "net_pnl" in df.columns:
        pnl = df["net_pnl"]
    else:
        pnl = df.iloc[:, 0] if len(df.columns) > 0 else pd.Series([0])

    x_values = (
        df.index
        if not isinstance(df.index, pd.RangeIndex)
        else df.get("date", df.index)
    )

    # Color bars based on profit/loss
    colors = [CLR["green"] if v >= 0 else CLR["red"] for v in pnl]

    fig.add_trace(
        go.Bar(
            x=x_values,
            y=pnl,
            marker_color=colors,
            opacity=0.8,
            name="Daily P&L",
            hovertemplate="Date: %{x}<br>P&L: $%{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=12, color=CLR["text"])),
        margin=dict(l=50, r=20, t=30, b=30),
        height=280,
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CLR["border"]),
        yaxis=dict(showgrid=True, gridcolor=CLR["border"], tickprefix="$"),
        bargap=0.1,
    )

    return fig


def build_backtest_equity_chart(
    equity_curve: List[Dict[str, Any]], title: str = "Backtest Equity"
) -> go.Figure:
    """
    Build equity chart from backtest equity_curve list.
    """
    fig = go.Figure()

    if not equity_curve:
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=CLR["bg"],
            plot_bgcolor=CLR["bg"],
            annotations=[
                dict(
                    text="No equity curve",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=CLR["muted"]),
                )
            ],
        )
        return fig

    times = [e.get("time", i) for i, e in enumerate(equity_curve)]
    equities = [e.get("equity", 0) for e in equity_curve]

    fig.add_trace(
        go.Scatter(
            x=times,
            y=equities,
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(63, 185, 80, 0.15)",
            line=dict(color=CLR["green"], width=2),
            name="Equity",
        )
    )

    # Add starting capital line
    starting_capital = equities[0] if equities else 100000
    fig.add_hline(
        y=starting_capital,
        line_dash="dot",
        line_color=CLR["muted"],
        opacity=0.5,
        annotation_text=f"Start: ${starting_capital:,.0f}",
        annotation_font_color=CLR["muted"],
        annotation_font_size=9,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CLR["bg"],
        plot_bgcolor=CLR["bg"],
        title=dict(text=title, font=dict(size=12, color=CLR["text"])),
        margin=dict(l=50, r=20, t=30, b=30),
        height=280,
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor=CLR["border"]),
        yaxis=dict(showgrid=True, gridcolor=CLR["border"], tickprefix="$"),
    )

    return fig
