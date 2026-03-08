"""
╔══════════════════════════════════════════════════════════════════╗
║           Dash Application — Callbacks & Server                 ║
╚══════════════════════════════════════════════════════════════════╝
All real-time callbacks for chart, scanner, alerts, journal, KPIs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html, dcc, no_update, ALL
import plotly.graph_objects as go

from config import CONFIG, TF, STRATEGY_REGISTRY
from strategy_reference import build_tv_url, STRATEGY_DESCRIPTIONS as _STRAT_DESCS
from dashboard.layout import build_layout, CLR
from dashboard.charts import build_chart

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────
# Dash application factory
# ────────────────────────────────────────────────────────────────

def create_app(
    data_feed,
    alert_engine,
    journal_db,
    journal_analytics,
    mt5_conn,
    strategy_instances,
    backtest_manager=None,
    optimizer_manager=None,
) -> dash.Dash:
    """Create and return the Dash app with all callbacks wired."""

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.CYBORG],
        assets_folder=str(Path(__file__).resolve().parent / "assets"),
        title="Trading System Pro",
        update_title=None,
        suppress_callback_exceptions=True,
    )
    app.layout = build_layout()

    # Store references for callbacks
    app._ts_data_feed = data_feed
    app._ts_alert_engine = alert_engine
    app._ts_journal_db = journal_db
    app._ts_analytics = journal_analytics
    app._ts_mt5 = mt5_conn
    app._ts_strategies = strategy_instances
    app._ts_backtest_mgr = backtest_manager
    app._ts_optimizer_mgr = optimizer_manager

    # ── Chart callback ──────────────────────────────────────
    @app.callback(
        Output("chart-container", "children"),
        [
            Input("interval-fast", "n_intervals"),
            Input("btn-refresh", "n_clicks"),
        ],
        [
            State("symbol-selector", "value"),
            State("tf-selector", "value"),
        ],
    )
    def update_chart(n_intervals, n_clicks, symbol, tf_str):
        from config import SYMBOLS
        tf = int(tf_str) if tf_str else 15
        # Map instrument key → MT5 broker symbol
        _sym_map = {
            "gold": SYMBOLS.gold, "nas100": SYMBOLS.nas100,
            "us500": SYMBOLS.us500, "us30": SYMBOLS.us30,
            "btc": SYMBOLS.btc, "eth": SYMBOLS.eth,
        }
        mt5_symbol = _sym_map.get(symbol, symbol)
        try:
            df = app._ts_data_feed.get_latest(mt5_symbol, tf, bars=200)
        except Exception:
            df = None

        signals = app._ts_alert_engine.get_buffer() if app._ts_alert_engine else []
        # Filter signals for selected symbol
        sym_signals = [s for s in signals if s.get("symbol", "") == symbol]

        fig = build_chart(
            df,
            signals=sym_signals[-10:],  # last 10 signals on chart
            title=f"{symbol} — {_tf_label(tf)}",
        )
        return [dcc.Graph(figure=fig, style={"height": "100%"}, config={"displayModeBar": False})]

    # ── KPI cards ───────────────────────────────────────────
    @app.callback(
        [
            Output("kpi-balance", "children"),
            Output("kpi-equity", "children"),
            Output("kpi-daily-pnl", "children"),
            Output("kpi-open-pos", "children"),
            Output("kpi-win-rate", "children"),
            Output("kpi-risk-status", "children"),
        ],
        Input("interval-slow", "n_intervals"),
    )
    def update_kpis(n):
        try:
            acc = app._ts_mt5.account_info()
        except Exception:
            acc = None

        if acc:
            balance = acc.get("balance", 0)
            equity = acc.get("equity", 0)
            daily_pnl = equity - balance
        else:
            balance = equity = daily_pnl = 0

        # Open positions
        try:
            positions = app._ts_mt5.get_positions()
            n_pos = len(positions) if positions is not None else 0
        except Exception:
            n_pos = 0

        # Win rate
        stats = app._ts_analytics.strategy_stats() if app._ts_analytics else {}
        win_rate = stats.get("win_rate", 0)

        # Risk status
        risk_color = CLR["green"]
        risk_text = "OK"
        if daily_pnl < 0:
            pct = abs(daily_pnl) / balance * 100 if balance else 0
            if pct > 3:
                risk_color = CLR["red"]
                risk_text = "DAILY LIMIT"
            elif pct > 2:
                risk_color = CLR["yellow"]
                risk_text = "CAUTION"

        return [
            _kpi_content("Balance", f"${balance:,.2f}"),
            _kpi_content("Equity", f"${equity:,.2f}"),
            _kpi_content("Daily P&L", f"${daily_pnl:,.2f}", CLR["green"] if daily_pnl >= 0 else CLR["red"]),
            _kpi_content("Open Positions", str(n_pos)),
            _kpi_content("Win Rate", f"{win_rate}%"),
            _kpi_content("Risk Status", risk_text, risk_color),
        ]

    # ── Scanner ─────────────────────────────────────────────
    @app.callback(
        Output("scanner-body", "children"),
        Input("interval-fast", "n_intervals"),
    )
    def update_scanner(n):
        signals = app._ts_alert_engine.get_buffer() if app._ts_alert_engine else []
        if not signals:
            return html.P("No active signals", style={"color": CLR["muted"]})

        # Sort signals by score descending (highest first)
        sorted_signals = sorted(signals[-20:], key=lambda s: s.get("score", 0), reverse=True)

        rows = []
        for sig in sorted_signals:
            dir_color = CLR["green"] if sig.get("direction") == "BUY" else CLR["red"]
            dir_icon = "▲" if sig.get("direction") == "BUY" else "▼"
            score = sig.get("score", 0)

            # Tier-based row background color
            if score >= 85:
                row_bg = "rgba(63,185,80,0.25)"  # Elite green
                tier_badge = "ELITE"
                tier_color = CLR["green"]
            elif score >= 70:
                row_bg = "rgba(180,200,80,0.20)"  # High yellow-green
                tier_badge = "HIGH"
                tier_color = "#b4c850"
            elif score >= 60:
                row_bg = "rgba(100,100,100,0.15)"  # Normal neutral
                tier_badge = ""
                tier_color = CLR["muted"]
            else:
                row_bg = "transparent"  # Below threshold (shouldn't appear)
                tier_badge = ""
                tier_color = CLR["muted"]

            rows.append(
                html.Div(
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "padding": "4px 8px",
                        "borderBottom": f"1px solid {CLR['border']}",
                        "fontSize": "12px",
                        "backgroundColor": row_bg,
                    },
                    children=[
                        html.Span(
                            f"{dir_icon} {sig.get('strategy_id', '')} ",
                            style={"color": dir_color, "fontWeight": "bold", "width": "60px"},
                        ),
                        html.Span(sig.get("symbol", ""), style={"width": "80px"}),
                        html.Span(
                            f"Entry: {sig.get('entry', 0):.2f}",
                            style={"width": "120px"},
                        ),
                        html.Span(
                            f"{score:.0f}% {tier_badge}",
                            style={"width": "100px", "color": tier_color, "fontWeight": "bold"},
                        ),
                        html.Span(
                            sig.get("timestamp", "")[-8:],
                            style={"color": CLR["muted"], "width": "70px"},
                        ),
                    ],
                )
            )
        return rows

    # ── Alerts ──────────────────────────────────────────────
    @app.callback(
        Output("alerts-body", "children"),
        Input("interval-fast", "n_intervals"),
    )
    def update_alerts(n):
        alerts = app._ts_alert_engine.get_buffer() if app._ts_alert_engine else []
        if not alerts:
            return html.P("No alerts yet", style={"color": CLR["muted"]})

        rows = []
        for a in reversed(alerts[-30:]):
            level = a.get("level", "info")
            level_colors = {
                "info": CLR["blue"],
                "signal": CLR["green"],
                "warning": CLR["yellow"],
                "critical": CLR["red"],
            }
            lc = level_colors.get(level, CLR["text"])
            rows.append(
                html.Div(
                    style={
                        "padding": "4px 8px",
                        "borderBottom": f"1px solid {CLR['border']}",
                        "fontSize": "11px",
                    },
                    children=[
                        html.Span(f"[{level.upper()}] ", style={"color": lc, "fontWeight": "bold"}),
                        html.Span(a.get("title", ""), style={"color": CLR["text"]}),
                        html.Br(),
                        html.Span(a.get("body", ""), style={"color": CLR["muted"], "fontSize": "10px"}),
                    ],
                )
            )
        return rows

    # ── Pair Monitor — All Instruments × Timeframes ─────────
    @app.callback(
        Output("pair-monitor-body", "children"),
        Input("interval-fast", "n_intervals"),
    )
    def update_pair_monitor(n):
        from datetime import datetime, timezone
        from config import STRATEGY_REGISTRY, SYMBOLS, TF as TFC

        now = datetime.now(timezone.utc)

        # Build mapping: instrument → { mt5_symbol, strategies, timeframes, is_crypto }
        instruments = [
            {"name": "GOLD",   "key": "gold",   "symbol": SYMBOLS.gold,   "crypto": False},
            {"name": "NAS100", "key": "nas100", "symbol": SYMBOLS.nas100, "crypto": False},
            {"name": "US500",  "key": "us500",  "symbol": SYMBOLS.us500,  "crypto": False},
            {"name": "US30",   "key": "us30",   "symbol": SYMBOLS.us30,   "crypto": False},
            {"name": "BTC",    "key": "btc",    "symbol": SYMBOLS.btc,    "crypto": True},
            {"name": "ETH",    "key": "eth",    "symbol": SYMBOLS.eth,    "crypto": True},
        ]

        # Collect active signals per symbol from the buffer
        signals = app._ts_alert_engine.get_buffer() if app._ts_alert_engine else []
        signal_by_symbol: dict[str, list] = {}
        for sig in signals:
            sym = sig.get("symbol", "")
            if sym not in signal_by_symbol:
                signal_by_symbol[sym] = []
            signal_by_symbol[sym].append(sig)

        # TF display order
        all_tfs = [
            (TFC.M1, "M1"), (TFC.M5, "M5"), (TFC.M15, "M15"),
            (TFC.H1, "H1"), (TFC.H4, "H4"), (TFC.D1, "D1"),
        ]

        # Header
        header_cells = [html.Span("Instrument", style={"width": "90px", "fontWeight": "bold"})]
        header_cells.append(html.Span("Symbol", style={"width": "90px"}))
        header_cells.append(html.Span("Strategies", style={"width": "170px"}))
        header_cells.append(html.Span("Session", style={"width": "70px"}))
        for _, tf_name in all_tfs:
            header_cells.append(html.Span(tf_name, style={"width": "55px", "textAlign": "center"}))
        header_cells.append(html.Span("Signals", style={"width": "70px", "textAlign": "center"}))
        header_cells.append(html.Span("Latest Signal", style={"flex": "1"}))

        header = html.Div(
            style={
                "display": "flex", "padding": "6px 10px",
                "borderBottom": f"2px solid {CLR['border']}",
                "fontSize": "11px", "color": CLR["muted"],
                "textTransform": "uppercase", "letterSpacing": "0.5px",
                "fontWeight": "bold",
            },
            children=header_cells,
        )

        rows = [header]

        for inst in instruments:
            # Find strategies for this instrument
            strats_for = [
                (sid, meta) for sid, meta in STRATEGY_REGISTRY.items()
                if meta.instrument == inst["key"] and meta.enabled
            ]
            strat_ids = [sid for sid, _ in strats_for]
            strat_tfs = set()
            for _, meta in strats_for:
                strat_tfs.update(meta.timeframes)

            # Session check (use strategy instances)
            session_active = inst["crypto"]  # crypto always active
            if not inst["crypto"] and app._ts_strategies:
                for s in app._ts_strategies:
                    if s.meta.instrument == inst["key"]:
                        if s.is_active_session():
                            session_active = True
                            break

            session_color = CLR["green"] if session_active else CLR["red"]
            session_text = "LIVE" if session_active else "CLOSED"

            # TF status dots
            tf_cells = []
            for tf_val, tf_name in all_tfs:
                if tf_val in strat_tfs:
                    # Check if data exists in cache
                    df = None
                    try:
                        df = app._ts_data_feed.get(inst["symbol"], tf_val) if app._ts_data_feed else None
                    except Exception:
                        pass
                    if df is not None and len(df) > 0:
                        tf_cells.append(html.Span("●", style={"width": "55px", "textAlign": "center", "color": CLR["green"], "fontSize": "14px"}, title=f"{tf_name}: {len(df)} bars"))
                    else:
                        tf_cells.append(html.Span("●", style={"width": "55px", "textAlign": "center", "color": CLR["red"], "fontSize": "14px"}, title=f"{tf_name}: No data"))
                else:
                    tf_cells.append(html.Span("○", style={"width": "55px", "textAlign": "center", "color": CLR["muted"], "fontSize": "14px"}, title=f"{tf_name}: Not monitored"))

            # Signals count for this symbol
            sym_signals = signal_by_symbol.get(inst["symbol"], [])
            sig_count = len(sym_signals)
            sig_count_color = CLR["green"] if sig_count > 0 else CLR["muted"]

            # Latest signal summary
            latest_text = "—"
            latest_color = CLR["muted"]
            if sym_signals:
                last = sym_signals[-1]
                d = last.get("direction", "?")
                e = last.get("entry", 0)
                latest_color = CLR["green"] if d == "BUY" else CLR["red"]
                icon = "▲" if d == "BUY" else "▼"
                sid_last = last.get("strategy_id", "?")
                ts_last = last.get("timestamp", "")[-8:]
                latest_text = f"{icon} {d} [{sid_last}] @ {e:.2f} ({ts_last})"

            # Row flash if has recent signals
            has_recent = False
            if sym_signals:
                try:
                    last_ts = sym_signals[-1].get("timestamp", "")
                    sig_time = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    if (now - sig_time).total_seconds() < 300:  # 5 min
                        has_recent = True
                except Exception:
                    pass

            row_class = ""
            if has_recent:
                d_last = sym_signals[-1].get("direction", "BUY")
                row_class = "signal-row-buy" if d_last == "BUY" else "signal-row-sell"

            cells = [
                html.Span(inst["name"], style={"width": "90px", "fontWeight": "bold", "color": CLR["blue"]}),
                html.Span(inst["symbol"], style={"width": "90px", "fontSize": "11px"}),
                html.Span(" ".join(strat_ids), style={"width": "170px", "fontSize": "10px", "color": CLR["muted"]}),
                html.Span(session_text, style={"width": "70px", "color": session_color, "fontWeight": "bold", "fontSize": "10px"}),
            ] + tf_cells + [
                html.Span(str(sig_count), style={"width": "70px", "textAlign": "center", "fontWeight": "bold", "color": sig_count_color, "fontSize": "14px"}),
                html.Span(latest_text, style={"flex": "1", "color": latest_color, "fontSize": "11px", "fontFamily": "monospace"}),
            ]

            rows.append(html.Div(
                className=row_class,
                style={
                    "display": "flex", "padding": "8px 10px",
                    "borderBottom": f"1px solid {CLR['border']}",
                    "fontSize": "12px", "alignItems": "center",
                },
                children=cells,
            ))

        # Legend
        legend = html.Div(
            style={"padding": "6px 10px", "fontSize": "10px", "color": CLR["muted"], "borderTop": f"1px solid {CLR['border']}"},
            children=[
                html.Span("● Data live", style={"color": CLR["green"], "marginRight": "12px"}),
                html.Span("● No data", style={"color": CLR["red"], "marginRight": "12px"}),
                html.Span("○ Not monitored", style={"marginRight": "12px"}),
                html.Span("│", style={"marginRight": "12px"}),
                html.Span("LIVE = session open", style={"color": CLR["green"], "marginRight": "12px"}),
                html.Span("CLOSED = outside session hours", style={"color": CLR["red"]}),
            ],
        )
        rows.append(legend)

        return rows

    # ── Signal Detail Table — All Signals, All TFs ──────────
    @app.callback(
        Output("signal-table-body", "children"),
        Input("interval-fast", "n_intervals"),
    )
    def update_signal_table(n):
        from datetime import datetime, timezone
        from config import STRATEGY_REGISTRY as SR, TF as TFC

        signals = app._ts_alert_engine.get_buffer() if app._ts_alert_engine else []
        if not signals:
            return html.Div(
                style={"textAlign": "center", "padding": "60px 20px"},
                children=[
                    html.P("📡 Scanning all pairs × all timeframes...", style={"color": CLR["muted"], "fontSize": "16px"}),
                    html.P("Signals will appear here with full analysis when detected", style={"color": CLR["muted"], "fontSize": "12px"}),
                ],
            )

        # Header row
        grid_cols = "55px 90px 90px 60px 55px 95px 85px 85px 50px 55px 1fr 75px"
        header = html.Div(
            style={
                "display": "grid", "gridTemplateColumns": grid_cols,
                "padding": "6px 10px", "fontWeight": "bold",
                "borderBottom": f"2px solid {CLR['border']}",
                "fontSize": "10px", "color": CLR["muted"],
                "textTransform": "uppercase", "letterSpacing": "0.5px",
            },
            children=[
                html.Span("ID"),
                html.Span("Strategy"),
                html.Span("Pair"),
                html.Span("Type"),
                html.Span("Score"),
                html.Span("Entry"),
                html.Span("Stop Loss"),
                html.Span("Take Profit"),
                html.Span("R:R"),
                html.Span("Status"),
                html.Span("WHY — Confluence / Reasoning"),
                html.Span("Time"),
            ],
        )

        rows = [header]
        now = datetime.now(timezone.utc)

        # Sort signals by score descending (highest quality first)
        sorted_signals = sorted(signals[-50:], key=lambda s: s.get("score", 0), reverse=True)

        # Show ALL signals, sorted by score descending
        for sig in sorted_signals:
            direction = sig.get("direction", "?")
            symbol = sig.get("symbol", "?")
            strategy_id = sig.get("strategy_id", "?")
            entry = sig.get("entry", 0)
            sl = sig.get("sl", 0)
            tp = sig.get("tp", 0)
            score = sig.get("score", 0)
            confluence = sig.get("confluence", "")
            ts_str = sig.get("timestamp", "")
            notes = sig.get("body", "")  # alert body often has context

            # Compute R:R
            risk = abs(entry - sl) if sl else 0
            reward = abs(tp - entry) if tp else 0
            rr = reward / risk if risk > 0 else 0

            # Freshness → flashing
            row_class = ""
            status_text = "ACTIVE"
            status_color = CLR["green"]
            try:
                sig_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_min = (now - sig_time).total_seconds() / 60
                if age_min < 5:
                    row_class = "signal-row-buy" if direction == "BUY" else "signal-row-sell"
                    status_text = "🔴 LIVE"
                elif age_min < 30:
                    row_class = "signal-row-buy" if direction == "BUY" else "signal-row-sell"
                    status_text = "ACTIVE"
                else:
                    row_class = "signal-row-stale"
                    status_text = "STALE"
                    status_color = CLR["muted"]
            except Exception:
                row_class = "signal-row-buy" if direction == "BUY" else "signal-row-sell"

            dir_color = CLR["green"] if direction == "BUY" else CLR["red"]
            dir_icon = "▲ BUY" if direction == "BUY" else "▼ SELL"

            # Tier-based row background
            if score >= 85:
                tier_bg = "rgba(63,185,80,0.20)"
            elif score >= 70:
                tier_bg = "rgba(180,200,80,0.15)"
            elif score >= 60:
                tier_bg = "transparent"
            else:
                tier_bg = "transparent"

            # Format confluence (the WHY)
            if isinstance(confluence, list):
                conf_str = " • ".join(confluence)
            elif isinstance(confluence, str):
                conf_str = confluence
            else:
                conf_str = str(confluence)
            # Append notes if present
            if notes and notes != conf_str:
                conf_str = f"{conf_str} | {notes}" if conf_str else notes

            # Strategy name
            strat_meta = SR.get(strategy_id)
            strat_name = strat_meta.name if strat_meta else "Unknown"
            style_badge = strat_meta.style.upper() if strat_meta else ""

            # Price decimals
            decimals = 2

            rows.append(
                html.Div(
                    className=row_class,
                    style={
                        "display": "grid", "gridTemplateColumns": grid_cols,
                        "padding": "6px 10px",
                        "borderBottom": f"1px solid {CLR['border']}",
                        "fontSize": "12px", "alignItems": "center",
                        "backgroundColor": tier_bg,
                    },
                    children=[
                        html.Span(strategy_id, style={"color": CLR["blue"], "fontWeight": "bold"}),
                        html.Span(strat_name, style={"fontSize": "10px", "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"}, title=f"{strat_name} ({style_badge})"),
                        html.Span(symbol, style={"fontWeight": "bold"}),
                        html.Span(dir_icon, style={"color": dir_color, "fontWeight": "bold", "fontSize": "11px"}),
                        html.Span(f"{score:.0f}%", style={"color": CLR["blue"]}),
                        html.Span(f"{entry:.{decimals}f}", style={"fontFamily": "monospace"}),
                        html.Span(f"{sl:.{decimals}f}", style={"color": CLR["red"], "fontFamily": "monospace"}),
                        html.Span(f"{tp:.{decimals}f}", style={"color": CLR["green"], "fontFamily": "monospace"}),
                        html.Span(f"{rr:.1f}", style={"fontWeight": "bold"}),
                        html.Span(status_text, style={"color": status_color, "fontWeight": "bold", "fontSize": "10px"}),
                        html.Span(conf_str, style={"color": CLR["text"], "fontSize": "10px", "whiteSpace": "nowrap", "overflow": "hidden", "textOverflow": "ellipsis"}, title=conf_str),
                        html.Span(ts_str[-8:] if len(ts_str) >= 8 else ts_str, style={"color": CLR["muted"], "fontFamily": "monospace", "fontSize": "10px"}),
                    ],
                )
            )

        # Summary
        all_sigs = signals[-50:]
        n_buy = sum(1 for s in all_sigs if s.get("direction") == "BUY")
        n_sell = sum(1 for s in all_sigs if s.get("direction") == "SELL")
        unique_pairs = len(set(s.get("symbol", "") for s in all_sigs))
        unique_strats = len(set(s.get("strategy_id", "") for s in all_sigs))
        summary = html.Div(
            style={
                "display": "flex", "justifyContent": "space-between",
                "padding": "8px 10px", "borderTop": f"2px solid {CLR['border']}",
                "marginTop": "4px", "fontSize": "12px",
            },
            children=[
                html.Span(f"Showing {len(all_sigs)} signals | {unique_pairs} pairs | {unique_strats} strategies", style={"fontWeight": "bold"}),
                html.Span([
                    html.Span(f"▲ {n_buy} BUY", style={"color": CLR["green"], "marginRight": "16px"}),
                    html.Span(f"▼ {n_sell} SELL", style={"color": CLR["red"]}),
                ]),
            ],
        )
        rows.append(summary)

        return rows

    # ── Journal ─────────────────────────────────────────────
    @app.callback(
        Output("journal-body", "children"),
        Input("interval-slow", "n_intervals"),
    )
    def update_journal(n):
        trades = app._ts_journal_db.get_trades(limit=30) if app._ts_journal_db else []
        if not trades:
            return html.P("No trades recorded", style={"color": CLR["muted"]})

        header = html.Div(
            style={
                "display": "flex",
                "padding": "4px 8px",
                "fontWeight": "bold",
                "borderBottom": f"2px solid {CLR['border']}",
                "fontSize": "11px",
                "color": CLR["muted"],
            },
            children=[
                html.Span("Ticket", style={"width": "80px"}),
                html.Span("Symbol", style={"width": "80px"}),
                html.Span("Dir", style={"width": "50px"}),
                html.Span("Strategy", style={"width": "70px"}),
                html.Span("Entry", style={"width": "90px"}),
                html.Span("Close", style={"width": "90px"}),
                html.Span("P&L", style={"width": "80px"}),
                html.Span("R:R", style={"width": "60px"}),
                html.Span("Result", style={"width": "60px"}),
                html.Span("Close Time", style={"width": "120px"}),
            ],
        )

        rows = [header]
        for t in trades:
            outcome = t.get("outcome", "")
            pnl = t.get("profit", 0) + t.get("commission", 0) + t.get("swap", 0)
            pnl_color = CLR["green"] if pnl >= 0 else CLR["red"]
            result_color = CLR["green"] if outcome == "WIN" else CLR["red"] if outcome == "LOSS" else CLR["muted"]

            rows.append(
                html.Div(
                    style={
                        "display": "flex",
                        "padding": "3px 8px",
                        "borderBottom": f"1px solid {CLR['border']}",
                        "fontSize": "11px",
                    },
                    children=[
                        html.Span(str(t.get("ticket", "")), style={"width": "80px"}),
                        html.Span(t.get("symbol", ""), style={"width": "80px"}),
                        html.Span(t.get("direction", ""), style={"width": "50px"}),
                        html.Span(t.get("strategy_id", ""), style={"width": "70px", "color": CLR["blue"]}),
                        html.Span(f"{t.get('entry_price', 0):.2f}", style={"width": "90px"}),
                        html.Span(f"{t.get('close_price', 0):.2f}", style={"width": "90px"}),
                        html.Span(f"${pnl:.2f}", style={"width": "80px", "color": pnl_color}),
                        html.Span(f"{t.get('rr_achieved', 0):.1f}", style={"width": "60px"}),
                        html.Span(outcome, style={"width": "60px", "color": result_color, "fontWeight": "bold"}),
                        html.Span(str(t.get("close_time", ""))[:16], style={"width": "120px", "color": CLR["muted"]}),
                    ],
                )
            )
        return rows

    # ── Stats ───────────────────────────────────────────────
    @app.callback(
        Output("stats-body", "children"),
        Input("interval-slow", "n_intervals"),
    )
    def update_stats(n):
        stats = app._ts_analytics.strategy_stats() if app._ts_analytics else {}
        if not stats or stats.get("total", 0) == 0:
            return html.P("No statistics available yet", style={"color": CLR["muted"]})

        items = [
            ("Total Trades", stats.get("total", 0)),
            ("Win Rate", f"{stats.get('win_rate', 0)}%"),
            ("Profit Factor", stats.get("profit_factor", 0)),
            ("Avg R:R", stats.get("avg_rr", 0)),
            ("Total P&L", f"${stats.get('total_pnl', 0):,.2f}"),
            ("Avg Win", f"${stats.get('avg_win', 0):,.2f}"),
            ("Avg Loss", f"${stats.get('avg_loss', 0):,.2f}"),
            ("Max Drawdown", f"${stats.get('max_drawdown', 0):,.2f}"),
            ("Max Consec Losses", stats.get("max_consec_losses", 0)),
            ("Expectancy", f"${stats.get('expectancy', 0):,.2f}"),
        ]

        rows = []
        for label, value in items:
            rows.append(
                html.Div(
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "padding": "4px 12px",
                        "borderBottom": f"1px solid {CLR['border']}",
                        "fontSize": "12px",
                    },
                    children=[
                        html.Span(label, style={"color": CLR["muted"]}),
                        html.Span(str(value), style={"fontWeight": "bold"}),
                    ],
                )
            )
        return rows

    # ── Strategy Reference toggle ──────────────────────────────
    @app.callback(
        Output("collapse-ref", "is_open"),
        Input("btn-toggle-ref", "n_clicks"),
        State("collapse-ref", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_strategy_ref(n, is_open):          # noqa: ARG001
        return not is_open
    # ── TradingView Chart Modal (per-strategy) ───────────
    @app.callback(
        [
            Output("tv-modal", "is_open"),
            Output("tv-iframe", "src"),
            Output("tv-modal-title", "children"),
            Output("tv-strategy-hint", "children"),
        ],
        Input({"type": "btn-tv-chart", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def _open_tv_chart(n_clicks_list):
        """Open a TradingView Advanced Chart for the clicked strategy."""
        if not any(n_clicks_list):
            raise dash.exceptions.PreventUpdate

        triggered = dash.ctx.triggered_id
        if not triggered:
            raise dash.exceptions.PreventUpdate

        sid = triggered["index"]
        url = build_tv_url(sid)
        meta = STRATEGY_REGISTRY.get(sid)
        desc = _STRAT_DESCS.get(sid, {})

        title = f"📊 Strategy {sid}: {meta.name}" if meta else f"Strategy {sid}"

        # Hint line: indicators + entry/exit summary
        parts = []
        if desc.get("indicators"):
            parts.append(f"Indicators: {desc['indicators']}")
        if desc.get("entry"):
            parts.append(f"Entry: {desc['entry']}")
        hint = "  |  ".join(parts) if parts else ""

        return True, url, title, hint

    # ── Backtest callbacks ───────────────────────────────────────
    @app.callback(
        [
            Output("backtest-run-id-store", "data"),
            Output("backtest-status-text", "children"),
        ],
        Input("backtest-run-btn", "n_clicks"),
        [
            State("backtest-strategy-dropdown", "value"),
            State("backtest-from-date", "date"),
            State("backtest-to-date", "date"),
        ],
        prevent_initial_call=True,
    )
    def trigger_backtest(n_clicks, strategy_id, from_date, to_date):
        """Submit a backtest job to the manager."""
        if not n_clicks or not strategy_id or not from_date or not to_date:
            return no_update, "Missing parameters"

        if not app._ts_backtest_mgr:
            return None, "Backtest manager not initialized"

        try:
            from datetime import datetime
            from config import SYMBOLS

            # Get symbol for strategy
            meta = STRATEGY_REGISTRY.get(strategy_id)
            if not meta:
                return None, f"Unknown strategy: {strategy_id}"

            sym_map = {
                "gold": SYMBOLS.gold,
                "nas100": SYMBOLS.nas100,
                "us500": SYMBOLS.us500,
                "us30": SYMBOLS.us30,
                "btc": SYMBOLS.btc,
                "eth": SYMBOLS.eth,
            }
            symbol = sym_map.get(meta.instrument)
            if not symbol:
                return None, f"Unknown instrument: {meta.instrument}"

            from_dt = datetime.fromisoformat(from_date)
            to_dt = datetime.fromisoformat(to_date)

            run_id = app._ts_backtest_mgr.submit_backtest(
                strategy_id=strategy_id,
                symbol=symbol,
                from_date=from_dt,
                to_date=to_dt,
            )

            return run_id, f"Running backtest {run_id}..."

        except Exception as e:
            return None, f"Error: {str(e)}"

    @app.callback(
        [
            Output("backtest-progress", "value"),
            Output("backtest-status-text", "children", allow_duplicate=True),
            Output("backtest-equity-chart-container", "children"),
            Output("backtest-results-panel", "children"),
            Output("backtest-trades-panel", "children"),
        ],
        Input("interval-fast", "n_intervals"),
        State("backtest-run-id-store", "data"),
        prevent_initial_call=True,
    )
    def poll_backtest(n_intervals, run_id):
        """Poll for backtest results and update UI."""
        if not run_id or not app._ts_backtest_mgr:
            return no_update, no_update, no_update, no_update, no_update

        result = app._ts_backtest_mgr.get_result(run_id)
        if not result:
            return 0, "Waiting...", no_update, no_update, no_update

        status = result.get("status", "unknown")

        if status == "pending":
            return 10, "Fetching data...", no_update, no_update, no_update
        elif status == "running":
            return 50, "Running backtest...", no_update, no_update, no_update
        elif status == "error":
            return 100, f"Error: {result.get('error', 'Unknown error')}", no_update, no_update, no_update
        elif status == "completed":
            # Build equity chart
            equity_curve = result.get("equity_curve", [])
            if equity_curve:
                import plotly.graph_objects as go
                fig = go.Figure()
                times = [e["time"][-8:] for e in equity_curve[::max(1, len(equity_curve)//100)]]  # Sample for performance
                equities = [e["equity"] for e in equity_curve[::max(1, len(equity_curve)//100)]]
                fig.add_trace(go.Scatter(
                    y=equities,
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color=CLR["green"], width=2),
                    name="Equity",
                ))
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor=CLR["bg"],
                    plot_bgcolor=CLR["bg"],
                    margin=dict(l=40, r=20, t=20, b=40),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor=CLR["border"]),
                    height=280,
                )
                equity_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
            else:
                equity_chart = html.P("No equity curve data", style={"color": CLR["muted"]})

            # Build metrics table
            metrics_data = [
                ("Total Trades", result.get("total_trades", 0)),
                ("Win Rate", f"{result.get('win_rate', 0):.1f}%"),
                ("Net Profit", f"${result.get('net_profit', 0):,.2f}"),
                ("Profit Factor", f"{result.get('profit_factor', 0):.2f}"),
                ("Max Drawdown", f"{result.get('max_drawdown_pct', 0):.1f}%"),
                ("Sharpe Ratio", f"{result.get('sharpe_ratio', 0):.2f}"),
                ("Sortino Ratio", f"{result.get('sortino_ratio', 0):.2f}"),
                ("ROI", f"{result.get('roi_pct', 0):.1f}%"),
                ("CAGR", f"{result.get('cagr_pct', 0):.1f}%"),
                ("Avg Win", f"${result.get('avg_win', 0):,.2f}"),
                ("Avg Loss", f"${result.get('avg_loss', 0):,.2f}"),
                ("Expectancy", f"${result.get('expectancy', 0):,.2f}"),
                ("Max Consec Losses", result.get("max_consecutive_losses", 0)),
                ("Avg R:R Achieved", f"{result.get('avg_rr_achieved', 0):.2f}"),
                ("Avg Score", f"{result.get('avg_confluence_score', 0):.0f}"),
                ("Duration", f"{result.get('duration_seconds', 0):.1f}s"),
            ]

            metrics_table = dbc.Table(
                [
                    html.Thead(html.Tr([
                        html.Th("Metric", style={"color": CLR["muted"], "fontSize": "11px"}),
                        html.Th("Value", style={"color": CLR["muted"], "fontSize": "11px"}),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(label, style={"fontSize": "12px"}),
                            html.Td(str(value), style={"fontSize": "12px", "fontWeight": "bold", "color": CLR["green"] if "Profit" in label and isinstance(value, str) and value.startswith("$") and not value.startswith("$-") else CLR["text"]}),
                        ]) for label, value in metrics_data
                    ]),
                ],
                bordered=False,
                size="sm",
                style={"marginBottom": "0"},
            )

            # Build trade log
            trades = result.get("trades", [])
            if trades:
                trade_rows = []
                for t in trades[-20:]:  # Show last 20 trades
                    pnl_color = CLR["green"] if t.get("profit", 0) > 0 else CLR["red"]
                    trade_rows.append(html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "60px 60px 70px 80px 80px 70px 60px",
                            "padding": "4px 0",
                            "borderBottom": f"1px solid {CLR['border']}",
                            "fontSize": "11px",
                            "fontFamily": "monospace",
                        },
                        children=[
                            html.Span(t.get("direction", "?"), style={"color": CLR["green"] if t.get("direction") == "BUY" else CLR["red"], "fontWeight": "bold"}),
                            html.Span(str(t.get("entry_time", ""))[-8:] if t.get("entry_time") else "?"),
                            html.Span(f"${t.get('entry_price', 0):.2f}"),
                            html.Span(f"SL: ${t.get('stop_loss', 0):.2f}", style={"color": CLR["red"]}),
                            html.Span(f"TP: ${t.get('take_profit', 0):.2f}", style={"color": CLR["green"]}),
                            html.Span(f"${t.get('profit', 0):.2f}", style={"color": pnl_color, "fontWeight": "bold"}),
                            html.Span(t.get("exit_reason", ""), style={"color": CLR["muted"]}),
                        ],
                    ))

                trade_log = html.Div([
                    html.Div(style={"display": "grid", "gridTemplateColumns": "60px 60px 70px 80px 80px 70px 60px", "padding": "4px 0", "borderBottom": f"2px solid {CLR['border']}", "fontSize": "10px", "color": CLR["muted"], "fontWeight": "bold"}, children=[
                        html.Span("Dir"), html.Span("Time"), html.Span("Entry"),
                        html.Span("SL"), html.Span("TP"), html.Span("P&L"), html.Span("Exit"),
                    ]),
                    *trade_rows,
                ])
            else:
                trade_log = html.P("No trades executed", style={"color": CLR["muted"]})

            return (
                100,
                f"✅ Completed: {result.get('total_trades', 0)} trades, {result.get('win_rate', 0):.1f}% win rate",
                equity_chart,
                metrics_table,
                trade_log,
            )

        return no_update, f"Status: {status}", no_update, no_update, no_update

    # ── Performance Charts callbacks (US3) ───────────────────────────
    @app.callback(
        [
            Output("perf-equity-chart", "children"),
            Output("perf-drawdown-chart", "children"),
            Output("perf-heatmap-chart", "children"),
            Output("perf-daily-pnl-chart", "children"),
            Output("perf-stats-table", "children"),
        ],
        [
            Input("btn-refresh-performance", "n_clicks"),
            Input("perf-date-range", "start_date"),
            Input("perf-date-range", "end_date"),
        ],
        prevent_initial_call=False,
    )
    def update_performance_charts(n_clicks, start_date, end_date):
        """Update all performance charts based on selected date range."""
        from datetime import datetime, timedelta
        import pandas as pd
        from dashboard.charts import (
            build_equity_chart,
            build_drawdown_chart,
            build_strategy_heatmap,
            build_daily_pnl_chart,
            calculate_drawdown,
        )

        # Get trades from journal
        trades = app._ts_journal_db.get_trades(limit=500) if app._ts_journal_db else []

        if not trades:
            empty_msg = html.P("No trades recorded yet", style={"color": CLR["muted"], "textAlign": "center", "padding": "20px"})
            return [empty_msg] * 5

        # Convert to DataFrame
        df = pd.DataFrame(trades)

        # Parse dates
        if "close_time" in df.columns:
            df["date"] = pd.to_datetime(df["close_time"], errors="coerce")
        elif "open_time" in df.columns:
            df["date"] = pd.to_datetime(df["open_time"], errors="coerce")
        else:
            df["date"] = pd.Timestamp.now()

        # Filter by date range if specified
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df["date"] >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(end_date) + timedelta(days=1)  # Include end date
            df = df[df["date"] < end_dt]

        if df.empty:
            no_data = html.P("No trades in selected date range", style={"color": CLR["muted"], "textAlign": "center", "padding": "20px"})
            return [no_data] * 5

        # Sort by date
        df = df.sort_values("date")

        # Calculate P&L per trade
        if "profit" in df.columns:
            df["net_pnl"] = df["profit"]
            if "commission" in df.columns:
                df["net_pnl"] = df["net_pnl"] + df["commission"].fillna(0)
            if "swap" in df.columns:
                df["net_pnl"] = df["net_pnl"] + df["swap"].fillna(0)
        else:
            df["net_pnl"] = 0

        # Calculate cumulative equity curve
        df["cumulative_pnl"] = df["net_pnl"].cumsum()
        starting_capital = 100000  # Default starting capital
        df["equity"] = starting_capital + df["cumulative_pnl"]

        # Set date as index for charts
        df_indexed = df.set_index("date")

        # 1. Equity Chart
        equity_df = df_indexed[["equity"]].copy()
        equity_fig = build_equity_chart(equity_df, title="Equity Curve")
        equity_chart = dcc.Graph(figure=equity_fig, config={"displayModeBar": False}, style={"height": "100%"})

        # 2. Drawdown Chart
        drawdown_df = calculate_drawdown(df_indexed["equity"])
        drawdown_fig = build_drawdown_chart(drawdown_df, title="Drawdown")
        drawdown_chart = dcc.Graph(figure=drawdown_fig, config={"displayModeBar": False}, style={"height": "100%"})

        # 3. Strategy Heatmap
        # Map symbol field for heatmap
        if "symbol" not in df.columns:
            df["symbol"] = "Unknown"
        heatmap_fig = build_strategy_heatmap(df, title="Win Rate by Strategy")
        heatmap_chart = dcc.Graph(figure=heatmap_fig, config={"displayModeBar": False}, style={"height": "100%"})

        # 4. Daily P&L
        daily_pnl = df.groupby(df["date"].dt.date)["net_pnl"].sum().reset_index()
        daily_pnl.columns = ["date", "profit"]
        daily_pnl_df = daily_pnl.set_index("date")
        daily_pnl_fig = build_daily_pnl_chart(daily_pnl_df, title="Daily P&L")
        daily_pnl_chart = dcc.Graph(figure=daily_pnl_fig, config={"displayModeBar": False}, style={"height": "100%"})

        # 5. Stats Table
        total_trades = len(df)
        wins = df[df["net_pnl"] > 0]
        losses = df[df["net_pnl"] <= 0]
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0

        total_profit = df["net_pnl"].sum()
        gross_profit = wins["net_pnl"].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses["net_pnl"].sum()) if len(losses) > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        avg_win = wins["net_pnl"].mean() if len(wins) > 0 else 0
        avg_loss = losses["net_pnl"].mean() if len(losses) > 0 else 0

        max_drawdown = drawdown_df["drawdown_pct"].max() if not drawdown_df.empty else 0

        # Calculate expectancy
        expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss) if total_trades > 0 else 0

        stats_items = [
            ("Period", f"{df['date'].min().strftime('%Y-%m-%d') if not df.empty else '-'} to {df['date'].max().strftime('%Y-%m-%d') if not df.empty else '-'}"),
            ("Total Trades", str(total_trades)),
            ("Win Rate", f"{win_rate:.1f}%"),
            ("Net P&L", f"${total_profit:,.2f}"),
            ("Profit Factor", f"{profit_factor:.2f}" if profit_factor != float('inf') else "∞"),
            ("Avg Win", f"${avg_win:,.2f}"),
            ("Avg Loss", f"${avg_loss:,.2f}"),
            ("Expectancy", f"${expectancy:,.2f}"),
            ("Max Drawdown", f"{max_drawdown:.1f}%"),
            ("Best Day", f"${daily_pnl['profit'].max():,.2f}" if not daily_pnl.empty else "$0.00"),
            ("Worst Day", f"${daily_pnl['profit'].min():,.2f}" if not daily_pnl.empty else "$0.00"),
        ]

        stats_table = dbc.Table(
            [
                html.Tbody([
                    html.Tr([
                        html.Td(label, style={"color": CLR["muted"], "fontSize": "11px", "width": "50%"}),
                        html.Td(
                            str(value),
                            style={
                                "fontSize": "11px",
                                "fontWeight": "bold",
                                "color": CLR["green"] if ("Win Rate" in label and win_rate >= 50) or ("Net P&L" in label and total_profit > 0) or ("Profit Factor" in label and profit_factor > 1) else CLR["red"] if ("Win Rate" in label and win_rate < 50) or ("Net P&L" in label and total_profit < 0) else CLR["text"]
                            }
                        ),
                    ]) for label, value in stats_items
                ]),
            ],
            bordered=False,
            size="sm",
            style={"marginBottom": "0"},
        )

        return [equity_chart, drawdown_chart, heatmap_chart, daily_pnl_chart, stats_table]

    # ── Optimizer callbacks (US5) ───────────────────────────────────
    @app.callback(
        [
            Output("optimizer-job-id-store", "data"),
            Output("optimizer-status-text", "children"),
            Output("optimizer-warning-text", "is_open"),
            Output("optimizer-warning-text", "children"),
        ],
        Input("optimizer-run-btn", "n_clicks"),
        [
            State("optimizer-strategy-dropdown", "value"),
            State("optimizer-param-grid-input", "value"),
            State("optimizer-train-from", "date"),
            State("optimizer-train-to", "date"),
            State("optimizer-test-from", "date"),
            State("optimizer-test-to", "date"),
        ],
        prevent_initial_call=True,
    )
    def trigger_optimization(n_clicks, strategy_id, param_grid_json, train_from, train_to, test_from, test_to):
        """Submit an optimization job."""
        import json
        from datetime import datetime
        from config import SYMBOLS

        if not n_clicks or not strategy_id:
            return None, "Missing parameters", False, ""

        if not app._ts_optimizer_mgr:
            return None, "Optimizer not initialized", True, "Optimization manager not available"

        # Parse param grid JSON
        try:
            param_grid = json.loads(param_grid_json) if param_grid_json else {}
        except json.JSONDecodeError as e:
            return None, "Invalid JSON", True, f"Parameter grid JSON error: {e}"

        if not param_grid:
            return None, "Empty param grid", True, "Please provide a parameter grid"

        # Get symbol for strategy
        meta = STRATEGY_REGISTRY.get(strategy_id)
        if not meta:
            return None, f"Unknown strategy: {strategy_id}", True, ""

        sym_map = {
            "gold": SYMBOLS.gold,
            "nas100": SYMBOLS.nas100,
            "us500": SYMBOLS.us500,
            "us30": SYMBOLS.us30,
            "btc": SYMBOLS.btc,
            "eth": SYMBOLS.eth,
        }
        symbol = sym_map.get(meta.instrument)
        if not symbol:
            return None, f"Unknown instrument: {meta.instrument}", True, ""

        # Validate combination count
        from itertools import product
        keys = list(param_grid.keys())
        value_lists = [param_grid[k] for k in keys]
        combinations = list(product(*value_lists))
        if len(combinations) > 500:
            return (
                None, "Too many combinations",
                True, f"Too many parameter combinations ({len(combinations)}). Maximum is 500."
            )

        try:
            train_from_dt = datetime.fromisoformat(train_from)
            train_to_dt = datetime.fromisoformat(train_to)
            test_from_dt = datetime.fromisoformat(test_from)
            test_to_dt = datetime.fromisoformat(test_to)
        except Exception as e:
            return None, "Invalid date", True, f"Date parsing error: {e}"

        try:
            job_id = app._ts_optimizer_mgr.submit(
                strategy_id=strategy_id,
                symbol=symbol,
                param_grid=param_grid,
                train_from=train_from_dt,
                train_to=train_to_dt,
                test_from=test_from_dt,
                test_to=test_to_dt,
            )
            return job_id, f"Running optimization {job_id}...", False, ""
        except Exception as e:
            return None, f"Error: {e}", True, str(e)

    @app.callback(
        [
            Output("optimizer-progress", "value"),
            Output("optimizer-status-text", "children", allow_duplicate=True),
            Output("optimizer-results-panel", "children"),
            Output("optimizer-warning-text", "is_open", allow_duplicate=True),
            Output("optimizer-warning-text", "children", allow_duplicate=True),
        ],
        Input("interval-fast", "n_intervals"),
        State("optimizer-job-id-store", "data"),
        prevent_initial_call=True,
    )
    def poll_optimization(n_intervals, job_id):
        """Poll for optimization results and update UI."""
        if not job_id or not app._ts_optimizer_mgr:
            return no_update, no_update, no_update, no_update, no_update

        status = app._ts_optimizer_mgr.get_status(job_id)
        if not status:
            return 0, "Job not found", no_update, no_update, no_update

        job_status = status.get("status", "unknown")
        progress = status.get("progress_pct", 0)

        if job_status == "pending":
            return 5, "Waiting...", no_update, no_update, no_update
        elif job_status == "running":
            return progress, f"Running... {progress:.0f}%", no_update, no_update, no_update
        elif job_status == "error":
            return 100, f"Error: {status.get('error', 'Unknown')}", no_update, True, status.get("error", "Unknown error")
        elif job_status == "completed":
            results = status.get("results", [])
            warning = status.get("warning", "")

            if results:
                # Build results table
                header = html.Div(
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "40px 140px 70px 70px 70px 70px 70px 80px",
                        "padding": "6px 8px",
                        "fontWeight": "bold",
                        "borderBottom": f"2px solid {CLR['border']}",
                        "fontSize": "10px",
                        "color": CLR["muted"],
                    },
                    children=[
                        html.Span("#"),
                        html.Span("Params"),
                        html.Span("IS PF"),
                        html.Span("IS WR"),
                        html.Span("OOS PF"),
                        html.Span("OOS WR"),
                        html.Span("OOS DD"),
                        html.Span("Score"),
                    ],
                )

                rows = [header]
                for r in results:
                    params_str = str(r.get("params", {}))[:20] + "..." if len(str(r.get("params", {}))) > 20 else str(r.get("params", {}))
                    rows.append(html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "40px 140px 70px 70px 70px 70px 70px 80px",
                            "padding": "4px 8px",
                            "borderBottom": f"1px solid {CLR['border']}",
                            "fontSize": "11px",
                            "backgroundColor": "rgba(63,185,80,0.15)" if r.get("rank") == 1 else "transparent",
                        },
                        children=[
                            html.Span(str(r.get("rank", "?")), style={"fontWeight": "bold", "color": CLR["blue"]}),
                            html.Span(params_str, style={"fontFamily": "monospace", "fontSize": "10px"}, title=str(r.get("params", {}))),
                            html.Span(f"{r.get('in_sample_pf', 0):.2f}"),
                            html.Span(f"{r.get('in_sample_wr', 0):.1f}%"),
                            html.Span(f"{r.get('oos_pf', 0):.2f}", style={"color": CLR["green"] if r.get("oos_pf", 0) > 1 else CLR["text"]}),
                            html.Span(f"{r.get('oos_wr', 0):.1f}%"),
                            html.Span(f"{r.get('oos_dd', 0):.1f}%", style={"color": CLR["red"] if r.get("oos_dd", 0) > 20 else CLR["text"]}),
                            html.Span(f"{r.get('composite_score', 0):.2f}", style={"fontWeight": "bold"}),
                        ],
                    ))

                # Summary
                best = results[0] if results else {}
                summary = html.Div(
                    style={"padding": "8px", "borderTop": f"2px solid {CLR['border']}", "marginTop": "8px"},
                    children=[
                        html.Span(f"Best params: {best.get('params', {})}", style={"color": CLR["green"], "fontSize": "11px"}),
                    ],
                )
                rows.append(summary)

                results_panel = html.Div(rows)
            else:
                results_panel = html.P("No results", style={"color": CLR["muted"]})

            warning_open = bool(warning)
            return (
                100,
                f"✅ Completed: {len(results)} combinations tested",
                results_panel,
                warning_open,
                warning,
            )

        return progress, f"Status: {job_status}", no_update, no_update, no_update

    return app


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────
def _kpi_content(label: str, value: str, color: str | None = None) -> html.Div:
    return html.Div(
        [
            html.Small(label, style={"color": CLR["muted"], "fontSize": "10px"}),
            html.Br(),
            html.Strong(value, style={"color": color or CLR["text"], "fontSize": "16px"}),
        ]
    )


def _tf_label(tf: int) -> str:
    return {1: "M1", 5: "M5", 15: "M15", 60: "H1", 240: "H4", 1440: "D1"}.get(tf, f"{tf}m")
