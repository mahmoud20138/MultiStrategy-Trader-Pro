# Trading System Pro

**19 strategies · 4 instruments · Real-time MT5 scanner · Dash dashboard**

A professional-grade automated strategy scanner that connects to MetaTrader 5,
evaluates 19 trading strategies across Gold (XAUUSD), NAS100, US500, and US30,
fires multi-channel alerts, maintains a trading journal, and displays everything
on a real-time web dashboard.

---

## Architecture

```
main.py                     ← Entry point (orchestrator)
├── core/
│   ├── mt5_connection.py   ← Thread-safe MT5 singleton
│   ├── data_feed.py        ← Multi-TF cache & polling engine
│   └── risk_manager.py     ← Position sizing & loss limits
├── indicators/
│   ├── trend.py            ← EMA, SMA, VWAP, Supertrend
│   ├── momentum.py         ← RSI, MACD, Stochastic, divergence
│   ├── volatility.py       ← Bollinger, ATR, Keltner, Asian range
│   ├── volume.py           ← Volume SMA, surge, OBV
│   └── structure.py        ← BOS, order blocks, FVG, S/R, Fib
├── strategies/
│   ├── base.py             ← BaseStrategy ABC + Signal model
│   ├── gold_strategies.py  ← A-H (8 strategies)
│   ├── nas100_strategies.py← I-M (5 strategies)
│   ├── us500_strategies.py ← N-P (3 strategies)
│   └── us30_strategies.py  ← Q-S (3 strategies)
├── alerts/
│   └── alert_engine.py     ← Desktop/Sound/Telegram + dedup
├── journal/
│   └── journal.py          ← SQLite journal + MT5 sync + analytics
└── dashboard/
    ├── layout.py           ← Dash UI components
    ├── charts.py           ← Plotly candlestick + overlays
    └── app.py              ← Dash callbacks (6 real-time panels)
```

## Strategies

| ID | Name | Instrument | Style | R:R |
|----|------|-----------|-------|-----|
| A | London Breakout Trap | Gold | Scalp | 1:2 |
| B | VWAP+OB Sniper | Gold | Scalp | 1:2 |
| C | News Spike Fade | Gold | Scalp | 1:1.5 |
| D | DXY Divergence | Gold | Day | 1:2 |
| E | Session Transition | Gold | Day | 1:2 |
| F | Trendline Break+Retest | Gold | Day | 1:2.5 |
| G | Weekly Institutional | Gold | Swing | 1:3 |
| H | Fibonacci Cluster | Gold | Swing | 1:4 |
| I | Opening Range Breakout | NAS100 | Scalp | 1:2 |
| J | EMA Ribbon Scalp | NAS100 | Scalp | 1:1.5 |
| K | ICT Power of 3 | NAS100 | Scalp | 1:3 |
| L | Gap Fill | NAS100 | Day | 1:1.5 |
| M | 20/50 EMA Pullback | NAS100 | Swing | 1:2.5 |
| N | VWAP Mean Reversion | US500 | Scalp | 1:1.75 |
| O | Multi-TF Trend | US500 | Day | 1:2 |
| P | RSI + Structure | US500 | Swing | 1:2.5 |
| Q | Round Number Bounce | US30 | Scalp | 1:2 |
| R | ICT Silver Bullet | US30 | Day | 1:3 |
| S | Breakout-Retest | US30 | Swing | 1:3 |

## Prerequisites

- **Windows** (required for MT5)
- **Python 3.10+**
- **MetaTrader 5** terminal installed, running, and **logged in** to your broker
- Symbols available: XAUUSD, USTEC/NAS100, US500, US30

## Quick Start

### Option 1: Run Script (Recommended)
```batch
run.bat
```
This creates a virtual environment, installs dependencies, and launches the system.

### Option 2: Manual Setup
```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env with your symbol names

# Launch
python main.py
```

## Configuration

Edit `.env` (copied from `.env.example`):

```ini
# MT5 terminal path (optional — auto-detects if only one installed)
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# Symbol names (must match your broker's naming)
SYMBOL_GOLD=XAUUSD
SYMBOL_NAS100=USTEC
SYMBOL_US500=US500
SYMBOL_US30=US30

# Risk management
MAX_RISK_PER_TRADE=1.0
MAX_DAILY_LOSS=3.0
MAX_WEEKLY_LOSS=6.0

# Alerts
ENABLE_DESKTOP_ALERTS=true
ENABLE_SOUND_ALERTS=true
ENABLE_TELEGRAM=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Dashboard
DASH_HOST=127.0.0.1
DASH_PORT=8050
```

## Usage

```bash
# Full system (scanner + dashboard)
python main.py

# Headless mode (scanner + alerts only, no web UI)
python main.py --no-dashboard

# Specific strategies only
python main.py --strategies A,B,D,I,Q

# Filter by instrument
python main.py --strategies gold     # Strategies A-H
python main.py --strategies nas100   # Strategies I-M
python main.py --strategies us30     # Strategies Q-S

# Filter by style
python main.py --strategies scalp    # All scalp strategies
python main.py --strategies swing    # All swing strategies

# Custom host/port
python main.py --host 0.0.0.0 --port 9090
```

## Dashboard

Open `http://127.0.0.1:8050` after launch. The dashboard shows:

- **Live Chart** — Candlestick with EMA/VWAP/Bollinger overlays, RSI subplot, signal markers
- **KPI Cards** — Balance, Equity, Daily P&L, Open Positions, Win Rate, Risk Status
- **Signal Scanner** — Real-time signal feed from all active strategies
- **Alert Feed** — All alerts with severity levels
- **Trade Journal** — Auto-synced closed trades from MT5
- **Performance Stats** — Win rate, profit factor, expectancy, drawdown

## Threading Model

| Thread | Purpose | Interval |
|--------|---------|----------|
| Main | Dash web server | — |
| DataFeed | MT5 candle polling | 2s |
| Scanner | Strategy evaluation | 2s |
| TradeSyncer | MT5 history → journal | 30s |

All MT5 calls are serialized through a thread-safe singleton with `threading.Lock`.

## Alert Channels

| Channel | Config Key | Notes |
|---------|-----------|-------|
| Desktop | `ENABLE_DESKTOP_ALERTS` | Windows toast via plyer |
| Sound | `ENABLE_SOUND_ALERTS` | Beep frequency by severity |
| Telegram | `ENABLE_TELEGRAM` | Requires bot token + chat ID |

Alerts are deduplicated via MD5 fingerprint with 5-minute cooldown.

## Risk Management

- Per-trade risk capped at configured % of balance
- Daily/weekly/monthly loss limits enforced
- Auto-pause after 3 consecutive losses (60 min)
- Correlation blocks prevent simultaneous trades on NAS100+US500 or US500+US30
- Position sizing: `Lots = (Balance × Risk%) / (SL_pips × Pip_value)`

## Data Storage

All data is stored in `data/trading.db` (SQLite):

- `trades` — Closed trade records (auto-synced from MT5)
- `signals_log` — Every signal generated
- `alerts` — Alert history

Logs are written to `data/logs/trading_YYYYMMDD.log` (rotating, 5MB × 5 backups).

---

**Note:** This system generates signals and alerts only — it does **not** auto-execute trades. You retain full manual control over trade entry and management.
