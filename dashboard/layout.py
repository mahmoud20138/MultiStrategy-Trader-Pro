"""
╔══════════════════════════════════════════════════════════════════╗
║            Plotly / Dash Layout Components                      ║
╚══════════════════════════════════════════════════════════════════╝
Reusable layout pieces consumed by app.py.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from config import CONFIG, STRATEGY_REGISTRY, SESSIONS
from strategy_reference import STRATEGY_DESCRIPTIONS as _STRATEGY_DESCRIPTIONS
from strategy_reference import TV_CHART_CONFIG


# ────────────────────────────────────────────────────────────────
# Colour palette (dark-pro theme)
# ────────────────────────────────────────────────────────────────
CLR = {
    "bg": "#0d1117",
    "card": "#161b22",
    "border": "#30363d",
    "text": "#c9d1d9",
    "green": "#3fb950",
    "red": "#f85149",
    "blue": "#58a6ff",
    "yellow": "#d29922",
    "muted": "#8b949e",
}


def card(title: str, body_id: str, height: str = "100%") -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(title, style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
            dbc.CardBody(id=body_id, style={"backgroundColor": CLR["bg"], "height": height, "overflowY": "auto"}),
        ],
        style={"border": f"1px solid {CLR['border']}", "marginBottom": "8px"},
    )


# ────────────────────────────────────────────────────────────────
# Symbol selector
# ────────────────────────────────────────────────────────────────
_symbols = list({v.instrument for v in STRATEGY_REGISTRY.values()})
symbol_dropdown = dcc.Dropdown(
    id="symbol-selector",
    options=[{"label": s, "value": s} for s in sorted(_symbols)],
    value=_symbols[0] if _symbols else "gold",
    clearable=False,
    style={"width": "200px", "backgroundColor": CLR["card"], "color": "#000"},
)

# Timeframe selector
tf_dropdown = dcc.Dropdown(
    id="tf-selector",
    options=[
        {"label": "M1", "value": "1"},
        {"label": "M5", "value": "5"},
        {"label": "M15", "value": "15"},
        {"label": "H1", "value": "16385"},
        {"label": "H4", "value": "16388"},
        {"label": "D1", "value": "16408"},
    ],
    value="15",
    clearable=False,
    style={"width": "120px", "backgroundColor": CLR["card"], "color": "#000"},
)


# ────────────────────────────────────────────────────────────────
# Main layout
# ────────────────────────────────────────────────────────────────
def build_layout() -> html.Div:
    return html.Div(
        style={"backgroundColor": CLR["bg"], "color": CLR["text"], "minHeight": "100vh", "padding": "12px"},
        children=[
            # ── Top bar ─────────────────────────────────────
            dbc.Navbar(
                dbc.Container(
                    [
                        dbc.NavbarBrand("⚡ Trading System Pro", className="ms-2", style={"fontWeight": "700"}),
                        dbc.Nav(
                            [
                                html.Div(symbol_dropdown, className="me-2"),
                                html.Div(tf_dropdown, className="me-2"),
                                dbc.Button("⟳ Refresh", id="btn-refresh", color="primary", size="sm"),
                            ],
                            className="ms-auto d-flex align-items-center",
                        ),
                    ],
                    fluid=True,
                ),
                color=CLR["card"],
                dark=True,
                style={"borderBottom": f"1px solid {CLR['border']}"},
            ),

            # ── Tabs container ───────────────────────────────
            dcc.Tabs(
                id="main-tabs",
                value="tab-live",
                style={"marginTop": "8px"},
                colors={
                    "border": CLR["border"],
                    "primary": CLR["blue"],
                    "background": CLR["card"],
                },
                children=[
                    # === LIVE TAB ===
                    dcc.Tab(
                        label="🔴 LIVE",
                        value="tab-live",
                        style={"backgroundColor": CLR["card"], "color": CLR["text"]},
                        selected_style={"backgroundColor": CLR["bg"], "color": CLR["blue"], "borderTop": f"2px solid {CLR['blue']}"},
                        children=_build_live_tab_content(),
                    ),
                    # === BACKTEST TAB ===
                    dcc.Tab(
                        label="🧪 BACKTEST",
                        value="tab-backtest",
                        style={"backgroundColor": CLR["card"], "color": CLR["text"]},
                        selected_style={"backgroundColor": CLR["bg"], "color": CLR["blue"], "borderTop": f"2px solid {CLR['blue']}"},
                        children=_build_backtest_tab_content(),
                    ),
                    # === PERFORMANCE TAB ===
                    dcc.Tab(
                        label="📊 PERFORMANCE",
                        value="tab-performance",
                        style={"backgroundColor": CLR["card"], "color": CLR["text"]},
                        selected_style={"backgroundColor": CLR["bg"], "color": CLR["blue"], "borderTop": f"2px solid {CLR['blue']}"},
                        children=_build_performance_tab_content(),
                    ),
                    # === OPTIMIZER TAB ===
                    dcc.Tab(
                        label="🔧 OPTIMIZER",
                        value="tab-optimizer",
                        style={"backgroundColor": CLR["card"], "color": CLR["text"]},
                        selected_style={"backgroundColor": CLR["bg"], "color": CLR["blue"], "borderTop": f"2px solid {CLR['blue']}"},
                        children=_build_optimizer_tab_content(),
                    ),
                ],
            ),

            # ── TradingView Chart Modal ─────────────────────
            dbc.Modal(
                [
                    dbc.ModalHeader(
                        dbc.ModalTitle(id="tv-modal-title", children="📊 TradingView Chart"),
                        close_button=True,
                        style={"backgroundColor": CLR["card"], "color": CLR["text"],
                               "borderBottom": f"1px solid {CLR['border']}"},
                    ),
                    dbc.ModalBody(
                        [
                            html.Div(id="tv-strategy-hint",
                                     style={"fontSize": "11px", "color": CLR["muted"],
                                            "marginBottom": "4px", "fontFamily": "monospace"}),
                            html.Iframe(
                                id="tv-iframe",
                                src="",
                                style={"width": "100%", "height": "85vh", "border": "none",
                                       "borderRadius": "6px"},
                            ),
                        ],
                        style={"backgroundColor": CLR["bg"], "padding": "4px"},
                    ),
                ],
                id="tv-modal",
                is_open=False,
                size="xl",
                centered=True,
                style={"maxWidth": "98vw"},
                className="tv-chart-modal",
            ),

            # ── Intervals ───────────────────────────────────
            dcc.Interval(id="interval-fast", interval=2_000, n_intervals=0),     # chart / scanner
            dcc.Interval(id="interval-slow", interval=10_000, n_intervals=0),    # journal / stats
            dcc.Store(id="signal-store", data=[]),
        ],
    )


def _build_live_tab_content() -> list:
    """Content for the LIVE tab (original dashboard)."""
    return [
        # ── Account info bar ────────────────────────────
        dbc.Row(
            id="account-bar",
            className="g-2 mt-2",
            children=[
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-balance"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-equity"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-daily-pnl"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-open-pos"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-win-rate"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
                dbc.Col(dbc.Card(dbc.CardBody(id="kpi-risk-status"), style={"backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}"}), width=2),
            ],
        ),

        # ── Main grid ───────────────────────────────────
        dbc.Row(
            className="g-2 mt-2",
            children=[
                # Left: chart
                dbc.Col(
                    [
                        card("📈 Chart", "chart-container", height="500px"),
                    ],
                    width=8,
                ),
                # Right: scanner + alerts
                dbc.Col(
                    [
                        card("🔎 Strategy Scanner", "scanner-body", height="240px"),
                        card("🔔 Live Alerts", "alerts-body", height="240px"),
                    ],
                    width=4,
                ),
            ],
        ),

        # ── Pair Monitor (all pairs × TFs) ───────────
        dbc.Row(
            className="g-2 mt-2",
            children=[
                dbc.Col(card("📡 Pair Monitor — All Instruments × Timeframes", "pair-monitor-body", height="300px"), width=12),
            ],
        ),

        # ── Signal Detail Table ─────────────────────────
        dbc.Row(
            className="g-2 mt-2",
            children=[
                dbc.Col(card("🚀 Live Signals — Type, Entries, SL/TP & Reasoning", "signal-table-body", height="400px"), width=12),
            ],
        ),

        # ── Strategy Reference ─────────────────────────
        dbc.Row(
            className="g-2 mt-2",
            children=[
                dbc.Col(
                    dbc.Card([
                        dbc.CardHeader(
                            html.Div([
                                html.Span("📖 Strategy Reference — What / Why / When / Indicators / Entry & Exit", style={"fontWeight": "600"}),
                                dbc.Button("▼ Show / Hide", id="btn-toggle-ref", color="link", size="sm",
                                           style={"color": CLR["blue"], "marginLeft": "auto", "fontSize": "11px"}),
                            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"}),
                            style={"backgroundColor": CLR["card"], "color": CLR["text"]},
                        ),
                        dbc.Collapse(
                            dbc.CardBody(
                                _build_strategy_reference(),
                                style={"backgroundColor": CLR["bg"], "overflowY": "auto", "maxHeight": "600px", "padding": "8px"},
                            ),
                            id="collapse-ref",
                            is_open=False,
                        ),
                    ], style={"border": f"1px solid {CLR['border']}", "marginBottom": "8px"}),
                    width=12,
                ),
            ],
        ),

        # ── Bottom: journal / stats ─────────────────────
        dbc.Row(
            className="g-2 mt-2",
            children=[
                dbc.Col(card("📒 Trade Journal", "journal-body", height="280px"), width=7),
                dbc.Col(card("📊 Performance Stats", "stats-body", height="280px"), width=5),
            ],
        ),
    ]


def _build_backtest_tab_content() -> list:
    """Content for the BACKTEST tab."""
    strategy_options = [
        {"label": f"{sid} — {STRATEGY_REGISTRY[sid].name}", "value": sid}
        for sid in sorted(STRATEGY_REGISTRY.keys())
    ]

    return [
        dbc.Row(
            className="g-2 mt-2",
            children=[
                # ── Left: Controls ─────────────────────────────
                dbc.Col(
                    [
                        dbc.Card([
                            dbc.CardHeader("⚙️ Backtest Configuration", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                [
                                    # Strategy selector
                                    html.Label("Strategy", style={"color": CLR["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                                    dcc.Dropdown(
                                        id="backtest-strategy-dropdown",
                                        options=strategy_options,
                                        value="A",
                                        clearable=False,
                                        style={"marginBottom": "12px"},
                                    ),

                                    # Date range
                                    dbc.Row([
                                        dbc.Col([
                                            html.Label("From Date", style={"color": CLR["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                                            dcc.DatePickerSingle(
                                                id="backtest-from-date",
                                                date="2024-01-01",
                                                display_format="YYYY-MM-DD",
                                                style={"width": "100%"},
                                            ),
                                        ], width=6),
                                        dbc.Col([
                                            html.Label("To Date", style={"color": CLR["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                                            dcc.DatePickerSingle(
                                                id="backtest-to-date",
                                                date="2024-12-31",
                                                display_format="YYYY-MM-DD",
                                                style={"width": "100%"},
                                            ),
                                        ], width=6),
                                    ], className="mb-3"),

                                    # Run button
                                    dbc.Button(
                                        "▶ Run Backtest",
                                        id="backtest-run-btn",
                                        color="success",
                                        className="mt-2",
                                        style={"width": "100%", "fontWeight": "bold"},
                                    ),

                                    # Progress bar
                                    html.Div([
                                        html.Span("Status: ", style={"color": CLR["muted"], "fontSize": "12px"}),
                                        html.Span(id="backtest-status-text", children="Ready", style={"color": CLR["text"], "fontSize": "12px"}),
                                    ], className="mt-3"),
                                    dbc.Progress(id="backtest-progress", value=0, max=100, style={"height": "8px", "marginTop": "8px"}),

                                    # Store for run ID
                                    dcc.Store(id="backtest-run-id-store"),
                                ],
                                style={"backgroundColor": CLR["bg"]},
                            ),
                        ], style={"border": f"1px solid {CLR['border']}"}),
                    ],
                    width=3,
                ),

                # ── Right: Results ─────────────────────────────
                dbc.Col(
                    [
                        # Equity curve
                        card("📈 Equity Curve", "backtest-equity-chart-container", height="300px"),

                        # Metrics table
                        dbc.Card([
                            dbc.CardHeader("📊 Performance Metrics", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                id="backtest-results-panel",
                                style={"backgroundColor": CLR["bg"], "maxHeight": "350px", "overflowY": "auto"},
                                children=[html.P("Run a backtest to see results", style={"color": CLR["muted"]})],
                            ),
                        ], style={"border": f"1px solid {CLR['border']}", "marginTop": "8px"}),

                        # Trade log
                        dbc.Card([
                            dbc.CardHeader("📋 Trade Log", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                id="backtest-trades-panel",
                                style={"backgroundColor": CLR["bg"], "maxHeight": "300px", "overflowY": "auto"},
                                children=[html.P("Trade log will appear here", style={"color": CLR["muted"]})],
                            ),
                        ], style={"border": f"1px solid {CLR['border']}", "marginTop": "8px"}),
                    ],
                    width=9,
                ),
            ],
        ),
    ]


def _build_performance_tab_content() -> list:
    """Content for the PERFORMANCE tab (US3)."""
    return [
        dbc.Row(
            className="g-2 mt-2",
            children=[
                # ── Left column: Charts ─────────────────────────────
                dbc.Col(
                    [
                        # Date range picker
                        dbc.Card([
                            dbc.CardHeader("📅 Date Range", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                [
                                    dcc.DatePickerRange(
                                        id="perf-date-range",
                                        start_date_placeholder_text="Start Date",
                                        end_date_placeholder_text="End Date",
                                        display_format="YYYY-MM-DD",
                                        style={"width": "100%"},
                                    ),
                                    dbc.Button(
                                        "🔄 Refresh",
                                        id="btn-refresh-performance",
                                        color="primary",
                                        size="sm",
                                        className="mt-2",
                                    ),
                                ],
                                style={"backgroundColor": CLR["bg"]},
                            ),
                        ], style={"border": f"1px solid {CLR['border']}", "marginBottom": "8px"}),

                        # Equity curve
                        card("📈 Equity Curve", "perf-equity-chart", height="280px"),

                        # Drawdown chart
                        card("📉 Drawdown", "perf-drawdown-chart", height="220px"),
                    ],
                    width=8,
                ),

                # ── Right column: Stats & Heatmap ─────────────────────
                dbc.Col(
                    [
                        # Strategy Win Rate Heatmap
                        card("🎯 Strategy Win Rate", "perf-heatmap-chart", height="300px"),

                        # Daily P&L
                        card("💰 Daily P&L", "perf-daily-pnl-chart", height="220px"),

                        # Performance stats table
                        dbc.Card([
                            dbc.CardHeader("📊 Performance Summary", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                id="perf-stats-table",
                                style={"backgroundColor": CLR["bg"], "maxHeight": "200px", "overflowY": "auto"},
                                children=[html.P("Select a date range to see performance stats", style={"color": CLR["muted"]})],
                            ),
                        ], style={"border": f"1px solid {CLR['border']}"}),
                    ],
                    width=4,
                ),
            ],
        ),
    ]


# ────────────────────────────────────────────────────────────────
# Strategy Reference — imported from single-source module
# ────────────────────────────────────────────────────────────────


def _build_optimizer_tab_content() -> list:
    """Content for the OPTIMIZER tab (US5)."""
    strategy_options = [
        {"label": f"{sid} — {STRATEGY_REGISTRY[sid].name}", "value": sid}
        for sid in sorted(STRATEGY_REGISTRY.keys())
    ]

    return [
        dbc.Row(
            className="g-2 mt-2",
            children=[
                # ── Left column: Controls ─────────────────────────────
                dbc.Col(
                    [
                        dbc.Card([
                            dbc.CardHeader("🔧 Optimization Configuration", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                [
                                    # Strategy selector
                                    html.Label("Strategy", style={"color": CLR["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                                    dcc.Dropdown(
                                        id="optimizer-strategy-dropdown",
                                        options=strategy_options,
                                        value="A",
                                        clearable=False,
                                        style={"marginBottom": "12px"},
                                    ),

                                    # Parameter grid input
                                    html.Label("Parameter Grid (JSON)", style={"color": CLR["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                                    dcc.Textarea(
                                        id="optimizer-param-grid-input",
                                        placeholder='{"ema_period": [20, 50], "rsi_threshold": [30, 40]}',
                                        style={
                                            "width": "100%", "height": "80px",
                                            "backgroundColor": CLR["bg"], "color": CLR["text"],
                                            "border": f"1px solid {CLR['border']}",
                                            "fontFamily": "monospace", "fontSize": "11px",
                                        },
                                    ),

                                    # Training date range
                                    html.Label("Training Period (In-Sample)", style={"color": CLR["muted"], "fontSize": "12px", "marginTop": "12px", "marginBottom": "4px"}),
                                    dbc.Row([
                                        dbc.Col([
                                            dcc.DatePickerSingle(
                                                id="optimizer-train-from",
                                                date="2023-01-01",
                                                display_format="YYYY-MM-DD",
                                            ),
                                        ], width=6),
                                        dbc.Col([
                                            dcc.DatePickerSingle(
                                                id="optimizer-train-to",
                                                date="2023-12-31",
                                                display_format="YYYY-MM-DD",
                                            ),
                                        ], width=6),
                                    ]),

                                    # Test date range
                                    html.Label("Test Period (Out-of-Sample)", style={"color": CLR["muted"], "fontSize": "12px", "marginTop": "12px", "marginBottom": "4px"}),
                                    dbc.Row([
                                        dbc.Col([
                                            dcc.DatePickerSingle(
                                                id="optimizer-test-from",
                                                date="2024-01-01",
                                                display_format="YYYY-MM-DD",
                                            ),
                                        ], width=6),
                                        dbc.Col([
                                            dcc.DatePickerSingle(
                                                id="optimizer-test-to",
                                                date="2024-03-31",
                                                display_format="YYYY-MM-DD",
                                            ),
                                        ], width=6),
                                    ]),

                                    # Run button
                                    dbc.Button(
                                        "▶ Run Optimization",
                                        id="optimizer-run-btn",
                                        color="warning",
                                        className="mt-3",
                                        style={"width": "100%", "fontWeight": "bold"},
                                    ),

                                    # Progress bar
                                    html.Div([
                                        html.Span("Status: ", style={"color": CLR["muted"], "fontSize": "12px"}),
                                        html.Span(id="optimizer-status-text", children="Ready", style={"color": CLR["text"], "fontSize": "12px"}),
                                    ], className="mt-3"),
                                    dbc.Progress(id="optimizer-progress", value=0, max=100, style={"height": "8px", "marginTop": "8px"}),

                                    # Store for job ID
                                    dcc.Store(id="optimizer-job-id-store"),

                                    # Warning alert
                                    dbc.Alert(
                                        id="optimizer-warning-text",
                                        is_open=False,
                                        color="warning",
                                        style={"marginTop": "12px", "fontSize": "12px"},
                                    ),
                                ],
                                style={"backgroundColor": CLR["bg"]},
                            ),
                        ], style={"border": f"1px solid {CLR['border']}"}),
                    ],
                    width=4,
                ),

                # ── Right column: Results ─────────────────────────────
                dbc.Col(
                    [
                        # Results table
                        dbc.Card([
                            dbc.CardHeader("📊 Optimization Results", style={"backgroundColor": CLR["card"], "color": CLR["text"], "fontWeight": "600"}),
                            dbc.CardBody(
                                id="optimizer-results-panel",
                                style={"backgroundColor": CLR["bg"], "maxHeight": "600px", "overflowY": "auto"},
                                children=[html.P("Run an optimization to see results", style={"color": CLR["muted"]})],
                            ),
                        ], style={"border": f"1px solid {CLR['border']}"}),
                    ],
                    width=8,
                ),
            ],
        ),
    ]


def _build_strategy_reference() -> list:
    """Build a static list of strategy reference cards (rendered once at layout time)."""
    from config import TF as TFC

    # Group strategies by instrument
    instrument_groups = {}
    for sid in sorted(STRATEGY_REGISTRY):
        meta = STRATEGY_REGISTRY[sid]
        inst = meta.instrument.upper()
        instrument_groups.setdefault(inst, []).append((sid, meta))

    style_badges = {"scalp": ("⚡", "#f0883e"), "day": ("📊", "#58a6ff"), "swing": ("📈", "#3fb950")}
    children = []

    for inst, strats in instrument_groups.items():
        # Instrument header
        children.append(
            html.Div(
                html.H6(f"{'🥇' if inst=='GOLD' else '📈' if inst=='NAS100' else '🏛️' if inst in ('US500','US30') else '₿' if inst=='BTC' else 'Ξ'} {inst}",
                        style={"color": CLR["blue"], "marginBottom": "4px", "marginTop": "12px", "borderBottom": f"1px solid {CLR['border']}", "paddingBottom": "4px"}),
            )
        )

        for sid, meta in strats:
            desc = _STRATEGY_DESCRIPTIONS.get(sid, {})
            badge_icon, badge_color = style_badges.get(meta.style, ("", CLR["text"]))

            # Timeframes
            tf_names = [TFC.name(tf) for tf in meta.timeframes]

            # Sessions
            if meta.sessions:
                sess_parts = []
                for s in meta.sessions:
                    sw = SESSIONS.get(s)
                    sess_parts.append(f"{sw.name} ({sw.start_hour:02d}:{sw.start_minute:02d}-{sw.end_hour:02d}:{sw.end_minute:02d})" if sw else s)
                sess_str = ", ".join(sess_parts)
            else:
                sess_str = "24/7 (all sessions)"

            wr_str = f"{meta.win_rate[0]*100:.0f}-{meta.win_rate[1]*100:.0f}%"
            rr_str = f"1:{meta.risk_reward[1]}"

            card_content = html.Div(
                style={
                    "backgroundColor": CLR["card"], "border": f"1px solid {CLR['border']}",
                    "borderRadius": "6px", "padding": "10px 14px", "marginBottom": "6px",
                },
                children=[
                    # Title row
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "6px",
                               "flexWrap": "wrap"},
                        children=[
                            html.Span(sid, style={"color": CLR["blue"], "fontWeight": "bold", "fontSize": "16px", "width": "24px"}),
                            html.Span(meta.name, style={"fontWeight": "bold", "fontSize": "14px"}),
                            html.Span(f"{badge_icon} {meta.style.upper()}",
                                      style={"color": badge_color, "fontSize": "11px", "fontWeight": "600",
                                             "border": f"1px solid {badge_color}", "borderRadius": "4px",
                                             "padding": "1px 6px"}),
                            html.Span(f"TF: {'/'.join(tf_names)}", style={"color": CLR["muted"], "fontSize": "11px"}),
                            html.Span(f"WR: {wr_str}", style={"color": CLR["green"], "fontSize": "11px"}),
                            html.Span(f"R:R {rr_str}", style={"color": CLR["yellow"], "fontSize": "11px"}),
                        ],
                    ),
                    # What
                    html.Div(
                        style={"fontSize": "12px", "lineHeight": "1.5", "marginBottom": "6px"},
                        children=[
                            html.Span("WHAT: ", style={"color": CLR["blue"], "fontWeight": "bold"}),
                            html.Span(desc.get("what", "—")),
                        ],
                    ),
                    # Reference
                    html.Div(
                        style={"fontSize": "12px", "marginBottom": "4px"},
                        children=[
                            html.Span("WHY (Reference): ", style={"color": CLR["yellow"], "fontWeight": "bold"}),
                            html.Span(desc.get("reference", "—")),
                        ],
                    ),
                    # When
                    html.Div(
                        style={"fontSize": "12px", "marginBottom": "4px"},
                        children=[
                            html.Span("WHEN: ", style={"color": "#f0883e", "fontWeight": "bold"}),
                            html.Span(sess_str),
                        ],
                    ),
                    # Indicators
                    html.Div(
                        style={"fontSize": "11px", "marginBottom": "4px"},
                        children=[
                            html.Span("Indicators: ", style={"color": CLR["muted"], "fontWeight": "bold"}),
                            html.Span(desc.get("indicators", "—"), style={"fontFamily": "monospace"}),
                        ],
                    ),
                    # Entry & Exit on same row
                    html.Div(
                        style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "8px", "fontSize": "11px"},
                        children=[
                            html.Div([
                                html.Span("▶ Entry: ", style={"color": CLR["green"], "fontWeight": "bold"}),
                                html.Span(desc.get("entry", "—")),
                            ]),
                            html.Div([
                                html.Span("◼ Exit: ", style={"color": CLR["red"], "fontWeight": "bold"}),
                                html.Span(desc.get("exit", "—")),
                            ]),
                        ],
                    ),
                    # ── TradingView Chart button — full-width bar at bottom ──
                    html.Div(
                        style={"marginTop": "8px", "borderTop": f"1px solid {CLR['border']}",
                               "paddingTop": "6px", "textAlign": "center"},
                        children=[
                            dbc.Button(
                                [html.Span("📊 ", style={"marginRight": "4px"}),
                                 f"Open TradingView Chart  —  {meta.instrument.upper()} {'/'.join(tf_names)}"],
                                id={"type": "btn-tv-chart", "index": sid},
                                color="info", size="sm", outline=True,
                                style={"fontSize": "12px", "padding": "4px 20px",
                                       "width": "100%", "fontWeight": "600",
                                       "letterSpacing": "0.5px"},
                            ),
                        ],
                    ),
                ],
            )
            children.append(card_content)

    return children
