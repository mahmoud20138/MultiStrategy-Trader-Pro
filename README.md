# 🛡️ MT5 Multi-Strategy Trader Pro

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/MetaTrader-5-orange.svg" alt="MT5">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Strategies-25-yellow.svg" alt="25 Strategies">
  <img src="https://img.shields.io/badge/Instruments-6-red.svg" alt="6 Instruments">
</p>

A professional-grade automated trading system that connects to **MetaTrader 5**, runs **25 independent strategies** across **6 instruments** (Gold, NAS100, US500, US30, BTC, ETH), and provides a real-time **Dash dashboard** with confluence-based signal scoring, backtesting engine, risk management, trade journaling, and multi-channel alert notifications.

---

## 🎯 Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **25 Trading Strategies** | From scalping to swing trading across 6 instruments |
| 📊 **Real-Time Dashboard** | Plotly Dash UI with live signals, charts, and analytics |
| 🧠 **Confluence Scoring** | Multi-factor signal quality assessment (0-100) |
| 📈 **Backtesting Engine** | Walk-forward optimization with professional metrics |
| 🛡️ **Risk Management** | Position sizing, daily/weekly/monthly loss caps |
| 📔 **Trade Journal** | Auto-sync from MT5 with analytics |
| 🔔 **Multi-Channel Alerts** | Desktop, Sound, Telegram, Discord |
| ⚡ **Multi-Timeframe** | M1/M5/M15/H1/H4/D1/W1 analysis |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRADING SYSTEM PRO                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐   │
│  │   MT5 Terminal  │ ───► │    Data Feed     │ ───► │   Strategy      │   │
│  │  (Live Prices)  │      │ (Multi-TF Cache) │      │    Scanner      │   │
│  └─────────────────┘      └──────────────────┘      └────────┬─────────┘   │
│                                                                             │
│                                                  ┌──────────────┐          │
│                                                  │ 25 Strategies │          │
│                                                  │  A - Y        │          │
│                                                  └───────┬───────┘          │
│                                                          │                  │
│                                                          ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         SIGNAL PROCESSING PIPELINE                  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  1. Strategy.analyze() ──► Raw Signal (direction, entry, SL, TP)  │   │
│  │  2. ConfluenceEngine.score() ──► Scored Signal (0-100, tier)       │   │
│  │  3. RiskManager.check_entry() ──► Position sizing validated       │   │
│  │  4. AlertEngine.fire() ──► Multi-channel notifications              │   │
│  │  5. JournalDB.log_signal() ──► SQLite persistence                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│                              ┌─────────┬─────────┬─────────┐               │
│                              │   📊   │   🛡️   │   🔔   │               │
│                              │Dashboard│  Risk   │ Alerts  │               │
│                              │ (Dash)  │Manager  │ Engine  │               │
│                              └─────────┴─────────┴─────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MT5 Terminal ─────────────────────────────────────────────► Prices         │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                         DATA FEED                                    │   │
│  │  • Polls MT5 every N seconds                                        │   │
│  │  • Fetches M1/M5/M15/H1/H4/D1/W1 for all symbols                   │   │
│  │  • Caches OHLCV DataFrames                                          │   │
│  │  • Fires new-bar callbacks to strategies                            │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                       INDICATORS                                    │   │
│  │  • Trend: EMA, SMA, ADX, Ichimoku                                  │   │
│  │  • Momentum: RSI, MACD, Stochastic, Williams %R, CCI              │   │
│  │  • Volatility: ATR, Bollinger Bands, Keltner Channels             │   │
│  │  • Structure: Swing Points, BOS, Order Blocks, FVGs, S/R          │   │
│  │  • Volume: Volume SMA, OBV, VWAP, Volume Surge                   │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  STRATEGIES ───► Signal (direction, entry, SL, TP, confluence)    │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                    CONFLUENCE ENGINE                               │   │
│  │  • Trend alignment (20%)    • Structure proximity (18%)          │   │
│  │  • Volume confirmation (16%) • Momentum zone (16%)               │   │
│  │  • Session quality (14%)    • Volatility context (12%)           │   │
│  │  • Multi-TF bonus (4%)      • RR multiplier [1.0-1.5]           │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                       RISK MANAGER                                 │   │
│  │  • Per-trade risk %           • Daily/Weekly/Monthly caps        │   │
│  │  • Consecutive loss pause     • Correlation blocks                │   │
│  │  • Position sizing formula: Lots = (Balance × Risk%) / (SL × PV) │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│       │                                                                   │
│       ▼                                                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐        │
│  │  Dashboard │ │   Alerts    │ │   Journal   │ │  Backtest  │        │
│  │    (UI)    │ │  (Multi-CH) │ │  (SQLite)   │ │   (Engine) │        │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📈 All 25 Strategies

### 🥇 Gold (XAUUSD) — 8 Strategies

| ID | Strategy Name | Style | Timeframes | Win Rate | R:R | Trading Session |
|----|---------------|-------|------------|----------|-----|-----------------|
| **A** | London Breakout Trap | Scalp | M5, M15 | 60-68% | 1:2 | London Open |
| **B** | VWAP+OB Sniper | Scalp | M1, M5 | 55-62% | 1:2 | NY Open |
| **C** | News Spike Fade | Scalp | M1, M5 | 55-60% | 1:1.5 | NY Open, London |
| **D** | DXY Divergence | Day | M15, H1 | 62-70% | 1:2 | London-NY Overlap |
| **E** | Session Transition | Day | M15, H1 | 58-65% | 1:2 | NY Open |
| **F** | Trendline Break+Retest | Day | M15, H1 | 55-62% | 1:2.5 | London, NY |
| **G** | Weekly Institutional | Swing | H4, D1, W1 | 55-60% | 1:3+ | London, NY |
| **H** | Fibonacci Cluster | Swing | H4, D1 | 55-60% | 1:3-5 | London, NY |

### 📈 NAS100 (USTEC) — 5 Strategies

| ID | Strategy Name | Style | Timeframes | Win Rate | R:R | Trading Session |
|----|---------------|-------|------------|----------|-----|-----------------|
| **I** | ORB (Opening Range) | Scalp | M5, M15 | 58-70% | 1:2 | NY Open |
| **J** | EMA Ribbon Scalp | Scalp | M1, M5 | 55-60% | 1:1.5 | NY Open, London |
| **K** | Power of 3 (ICT) | Scalp | M5, M15 | 55-65% | 1:3 | NY Open |
| **L** | Gap Fill | Day | M15, H1 | 65-72% | 1:1.5 | NY Open |
| **M** | 20/50 EMA Pullback | Swing | H4, D1 | 55-62% | 1:2.5 | NY |

### 📊 US500 (S&P 500) — 3 Strategies

| ID | Strategy Name | Style | Timeframes | Win Rate | R:R | Trading Session |
|----|---------------|-------|------------|----------|-----|-----------------|
| **N** | VWAP Mean Reversion | Scalp | M1, M5 | 63-72% | 1:1.75 | NY Open |
| **O** | Multi-TF Trend | Day | M5, M15, H1 | 58-64% | 1:2 | London, NY |
| **P** | RSI + Structure | Swing | D1, W1 | 55-62% | 1:2.5 | NY |

### 📉 US30 (Dow Jones) — 3 Strategies

| ID | Strategy Name | Style | Timeframes | Win Rate | R:R | Trading Session |
|----|---------------|-------|------------|----------|-----|-----------------|
| **Q** | Round Number Bounce | Scalp | M5, M15 | 60-66% | 1:2 | NY Open, London |
| **R** | ICT Silver Bullet | Day | M5, M15 | 55-65% | 1:3 | Silver Bullet Windows |
| **S** | Breakout-Retest | Swing | H4, D1 | 60-70% | 1:3 | NY |

### ₿ Crypto (BTC/ETH) — 6 Strategies

| ID | Strategy Name | Style | Timeframes | Win Rate | R:R | Notes |
|----|---------------|-------|------------|----------|-----|-------|
| **T** | BTC Round Number Bounce | Scalp | M5 | 60-70% | 1:3 | 24/7 Trading |
| **U** | ETH Trend Following | Day | H4 | 58-65% | 1:2.5 | 24/7 Trading |
| **V** | BTC Momentum Breakout | Scalp | M15 | 58-68% | 1:3 | 24/7 Trading |
| **W** | BTC RSI Divergence | Day | H1 | 60-68% | 1:2.5 | 24/7 Trading |
| **X** | ETH Order Block Sniper | Scalp | M5 | 58-66% | 1:2 | 24/7 Trading |
| **Y** | ETH Multi-TF Confluence | Swing | H4, D1 | 55-63% | 1:3 | 24/7 Trading |

---

## 🧠 Confluence Scoring System

Every signal passes through the `ConfluenceEngine` that calculates a **quality score from 0-100**:

### Factor Weights

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONFLUENCE SCORING WEIGHTS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┬────────┬─────────────────────────────────────────┐    │
│  │ Factor          │ Weight │ Description                             │    │
│  ├─────────────────┼────────┼─────────────────────────────────────────┤    │
│  │ 🔮 Trend        │  20%   │ Multi-TF EMA alignment (M5/M15/H1)      │    │
│  │ 📊 Structure    │  18%   │ Proximity to OB/FVG/S/R/Round Levels    │    │
│  │ 📈 Volume       │  16%   │ Volume surge + OBV confirmation        │    │
│  │ 💪 Momentum     │  16%   │ RSI zone + MACD histogram direction    │    │
│  │ ⏰ Session      │  14%   │ Session quality (optimal/suboptimal)    │    │
│  │ 🌊 Volatility   │  12%   │ ATR regime (not range-day, not spike)   │    │
│  │ 🔄 Multi-TF    │   4%   │ Bonus for 3-TF alignment               │    │
│  └─────────────────┴────────┴─────────────────────────────────────────┘    │
│                                                                             │
│  RR Multiplier: 1.0 + min(RR / 5.0, 0.5) = [1.0 - 1.5]                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Quality Tiers

| Tier | Score Range | Description | Action |
|------|-------------|-------------|--------|
| 🏆 **Elite** | 85-100 | Highest confidence | Full position size |
| ⭐ **High** | 70-84 | Strong setup | Standard size |
| ✅ **Normal** | 60-69 | Acceptable | Reduced size |
| ❌ **Low** | <60 | Below threshold | **Filtered out** |

### Veto Gates (Score → 0)
- ❌ Cross-TF trend conflict (H1 direction opposes M15)
- ❌ Volume divergence (declining volume into entry bar)

### Partial Penalty (×0.5)
- ⚠️ RSI divergence detected

---

## 📊 Indicators Module

| Module | File | Indicators |
|--------|------|------------|
| **Trend** | `indicators/trend.py` | EMA (10/21/50/200), SMA, ADX, Ichimoku Cloud, VWAP |
| **Momentum** | `indicators/momentum.py` | RSI, MACD, Stochastic, Williams %R, CCI |
| **Volatility** | `indicators/volatility.py` | ATR, Bollinger Bands, Keltner Channels, Asian Range, Gap |
| **Structure** | `indicators/structure.py` | Swing Points, BOS/CHoCH, Order Blocks, FVGs, S/R, Round Levels, Trendlines |
| **Volume** | `indicators/volume.py` | Volume SMA, OBV, VWAP, Volume Surge, Volume ROC |
| **Confluence** | `indicators/confluence.py` | Multi-factor scoring engine |

---

## 🖥️ Dashboard

The real-time **Plotly Dash** dashboard provides:

### Main Sections

| Section | Description |
|---------|-------------|
| 📡 **Signal Table** | Live signals with direction, score, quality tier, entry/SL/TP |
| 📈 **TradingView Charts** | Interactive charts per instrument with entry/exit markers |
| 📊 **Strategy Performance** | Win rates, P&L, signal history per strategy |
| 🛡️ **Risk Monitor** | Daily P&L, open exposure, consecutive losses |
| 📔 **Journal View** | Complete trade history with analytics |
| ⚙️ **Backtest Panel** | Run historical tests and view results |
| 🔔 **Alert History** | Recent alerts and notifications |

### Dashboard Preview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRADING SYSTEM PRO DASHBOARD                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SIGNAL SCANNER                                    🔄 Refresh: 2s  │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │  Time    │ Strategy │ Symbol │ Dir  │ Entry  │ SL   │ TP   │ Score │    │
│  │  ─────────────────────────────────────────────────────────────────  │    │
│  │  14:32   │ A        │ XAUUSD │ BUY  │ 2345.5 │ 2340 │ 2356 │  82   │    │
│  │  14:28   │ N        │ US500  │ SELL │ 5020   │ 5028 │ 5010 │  78   │    │
│  │  14:15   │ Q        │ US30   │ BUY  │ 38500  │ 38460│ 38600│  71   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────┐  ┌────────────────────────────┐   │
│  │         CHART (TradingView)         │  │      RISK MONITOR         │   │
│  │                                     │  ├────────────────────────────┤   │
│  │    [Interactive OHLCV Chart]       │  │  Balance: $10,000         │   │
│  │                                     │  │  Daily P&L: +$250 (2.5%)  │   │
│  │    Entry/Exit markers on chart      │  │  Weekly P&L: +$800 (8%)   │   │
│  │                                     │  │  Open Positions: 2/3      │   │
│  └─────────────────────────────────────┘  │  Consecutive Losses: 0    │   │
│                                           └────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Risk Management

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_RISK_PER_TRADE` | 1.0% | Maximum risk per trade |
| `MAX_DAILY_LOSS` | 3.0% | Maximum daily loss cap |
| `MAX_WEEKLY_LOSS` | 6.0% | Maximum weekly loss cap |
| `MAX_MONTHLY_DRAWDOWN` | 10.0% | Maximum monthly drawdown |
| `MAX_CONCURRENT_TRADES` | 3 | Maximum open positions |
| `CONSECUTIVE_LOSS_PAUSE` | 3 | Pause after N consecutive losses |
| `PAUSE_MINUTES` | 60 | Duration of pause (minutes) |

### Position Sizing Formula

```
Lots = (Account Balance × Risk%) / (SL Distance × Point Value)
```

Where:
- **Point Value** = Contract Size × Point
- Result is snapped to broker's volume step and bounded by min/max

### Correlation Blocks

| Instruments | Correlation | Rule |
|-------------|-------------|------|
| NAS100 ↔ US500 | 0.92 | Same direction forbidden |
| US500 ↔ US30 | 0.95 | Same direction forbidden |

---

## 📊 Backtesting Engine

### Features

- **Walk-forward optimization** with configurable in-sample/out-of-sample splits
- **Parquet caching** for fast re-runs
- **Vectorized indicators** for performance
- **Bar-by-bar signal replay**
- **Professional metrics**: Win Rate, Profit Factor, Sharpe Ratio, Sortino, CAGR, Max Drawdown

### Metrics Calculated

| Metric | Description |
|--------|-------------|
| **Win Rate** | Percentage of profitable trades |
| **Profit Factor** | Gross profit / Gross loss |
| **Sharpe Ratio** | Risk-adjusted return |
| **Sortino Ratio** | Downside risk-adjusted return |
| **CAGR** | Compound Annual Growth Rate |
| **Max Drawdown** | Largest peak-to-trough decline |
| **R-Multiples** | Average RR achieved |

---

## 📔 Trading Journal

### Features

- **Auto-sync** from MT5 history_deals
- **Signal logging** with strategy_id and confluence
- **Trade analytics** per strategy/day/week/month
- **Screenshot attachment** support
- **Notes and tags** for each trade

### Database Schema

```sql
-- Trades table
CREATE TABLE trades (
    ticket       INTEGER PRIMARY KEY,
    symbol       TEXT,
    direction    TEXT,
    strategy_id  TEXT,
    open_time    TEXT,
    close_time   TEXT,
    entry_price  REAL,
    close_price  REAL,
    sl           REAL,
    tp           REAL,
    lot          REAL,
    profit       REAL,
    commission   REAL,
    swap         REAL,
    pips         REAL,
    rr_achieved  REAL,
    outcome      TEXT,  -- WIN/LOSS/BE
    confluence   TEXT,
    notes        TEXT,
    screenshot   TEXT
);

-- Signals log table
CREATE TABLE signals_log (
    timestamp    TEXT,
    strategy_id  TEXT,
    symbol       TEXT,
    direction    TEXT,
    entry        REAL,
    sl           REAL,
    tp           REAL,
    score        REAL,
    quality_tier TEXT,
    confluence   TEXT
);
```

---

## 🔔 Alert System

### Channels

| Channel | Description | Requirements |
|---------|-------------|--------------|
| 🖥️ **Desktop** | Windows toast notifications | `plyer` library |
| 🔊 **Sound** | Windows beep sound | `winsound` (built-in) |
| 📱 **Telegram** | Bot messages | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| 💬 **Discord** | Webhook notifications | `DISCORD_WEBHOOK_URL` |

### Alert Levels

| Level | Color | Use Case |
|-------|-------|----------|
| `INFO` | 🔵 | System start/stop |
| `SIGNAL` | 🟢 | New trading signal |
| `WARNING` | 🟡 | Signal blocked by risk |
| `CRITICAL` | 🔴 | Risk limit hit |

### Features
- **Deduplication** via fingerprint hashing
- **Cooldown** between same alerts
- **SQLite history** for audit trail
- **Severity-based** filtering

---

## 🚀 Installation

### Prerequisites

| Requirement | Version |
|-------------|---------|
| 🐍 Python | 3.10+ |
| 🖥️ OS | Windows (MT5 terminal required) |
| 📊 MT5 | Terminal running with active account |

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/mahmoud20138/MultiStrategy-Trader-Pro.git
cd MultiStrategy-Trader-Pro

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Requirements

```
MetaTrader5>=5.0.45
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
dash>=2.14.0
dash-bootstrap-components>=1.5.0
pydantic>=2.5.0
python-dotenv>=1.0.0
plyer>=2.1.0
APScheduler>=3.10.0
requests>=2.31.0
pyarrow>=14.0.0
```

### Configuration

Create a `.env` file in the project root:

```env
# MT5 Connection
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=YourBroker-Server

# Symbols
SYMBOL_GOLD=XAUUSD
SYMBOL_NAS100=USTEC
SYMBOL_US500=US500
SYMBOL_US30=US30
SYMBOL_DXY=USDX
SYMBOL_BTC=BTCUSD
SYMBOL_ETH=ETHUSD

# Crypto (enable/disable)
ENABLE_CRYPTO=false

# Risk Management
MAX_RISK_PER_TRADE=1.0
MAX_DAILY_LOSS=3.0
MAX_WEEKLY_LOSS=6.0
MAX_MONTHLY_DRAWDOWN=10.0
MAX_CONCURRENT_TRADES=3

# Alerts
ENABLE_DESKTOP_ALERTS=true
ENABLE_SOUND_ALERTS=true
ENABLE_TELEGRAM=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ENABLE_DISCORD=false
DISCORD_WEBHOOK_URL=

# Confluence Scoring
CONFLUENCE_MIN_SCORE=60

# Dashboard
DASH_HOST=127.0.0.1
DASH_PORT=8050
DASH_DEBUG=false

# System
POLL_INTERVAL_SECONDS=2
DB_PATH=data/journal.db
LOG_PATH=data/logs
```

---

## 📖 Usage

### Basic Commands

```bash
# Launch full system with dashboard
python main.py

# Headless scanner only (no dashboard UI)
python main.py --no-dashboard

# Enable specific strategies
python main.py --strategies A,B,D,I

# Enable all gold strategies (A-H)
python main.py --strategies gold

# Enable crypto strategies (requires ENABLE_CRYPTO=true in .env)
python main.py --strategies T,U,V,W,X,Y

# Custom dashboard host/port
python main.py --host 0.0.0.0 --port 9000
```

### CLI Options

| Flag | Description | Example |
|------|-------------|---------|
| `--no-dashboard` | Run scanner without the Dash UI | `python main.py --no-dashboard` |
| `--strategies A,B,D` | Enable specific strategy IDs | `python main.py --strategies A,B,D` |
| `--host` | Dashboard host | `python main.py --host 0.0.0.0` |
| `--port` | Dashboard port | `python main.py --port 9000` |

### Strategy Filters

```bash
# By instrument
python main.py --strategies gold      # A-H (Gold)
python main.py --strategies nas100    # I-M (NAS100)
python main.py --strategies us500     # N-P (US500)
python main.py --strategies us30       # Q-S (US30)

# By style
python main.py --strategies scalp     # All scalp strategies
python main.py --strategies day       # All day strategies
python main.py --strategies swing     # All swing strategies
```

---

## 🎯 Signal Example Output

```
2024-01-15 14:32:15 | INFO     | main            | [SIGNAL] A London Breakout Trap
2024-01-15 14:32:15 | INFO     | main            |   Instrument: XAUUSD | Direction: BUY | Strength: STRONG
2024-01-15 14:32:15 | INFO     | main            |   Entry: 2345.50 | SL: 2340.00 | TP: 2356.50 | RR: 2.0
2024-01-15 14:32:15 | INFO     | main            |   Score: 82/100 | Tier: HIGH
2024-01-15 14:32:15 | INFO     | main            |   Confluence: [Asian low sweep, Bullish reversal candle, Above EMA 21]
```

---

## 📁 Project Structure

```
MultiStrategy-Trader-Pro/
├── main.py                          # 🎯 Entry point (TradingSystem orchestrator)
├── config.py                       # ⚙️ Configuration (symbols, risk, strategies, sessions)
├── requirements.txt                # 📦 Python dependencies
├── LICENSE                         # 📜 MIT License
├── CONTRIBUTING.md                 # 🤝 Contribution guidelines
│
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md           # 🐛 Bug report template
│   │   ├── feature_request.md      # ✨ Feature request template
│   │   └── instrument_request.md  # 🔧 Instrument request template
│   └── PULL_REQUEST_TEMPLATE.md   # 📝 PR template
│
├── core/                           # 🧠 Core trading system components
│   ├── mt5_connection.py          # 🔌 MT5 terminal wrapper (thread-safe singleton)
│   ├── data_feed.py               # 📡 Multi-TF data fetcher & polling engine
│   ├── risk_manager.py            # 🛡️ Position sizing, loss limits, correlation blocks
│   ├── backtest_engine.py         # 📊 Walk-forward backtester with metrics
│   └── optimizer.py               # 🔧 Parameter optimization job manager
│
├── strategies/                     # 🎯 Trading strategies (A-Y)
│   ├── __init__.py                # Strategy registry & factory
│   ├── base.py                    # BaseStrategy class & Signal model
│   ├── gold_strategies.py         # Strategies A-H (Gold/XAUUSD)
│   ├── nas100_strategies.py       # Strategies I-M (NAS100/USTEC)
│   ├── us500_strategies.py       # Strategies N-P (US500)
│   ├── us30_strategies.py        # Strategies Q-S (US30)
│   └── crypto_strategies.py       # Strategies T-Y (BTC/ETH)
│
├── indicators/                    # 📈 Technical indicators
│   ├── trend.py                   # EMA, SMA, ADX, Ichimoku, VWAP
│   ├── momentum.py                # RSI, MACD, Stochastic, Williams %R, CCI
│   ├── volatility.py              # ATR, Bollinger Bands, Keltner, Asian Range
│   ├── structure.py              # Swing Points, BOS, Order Blocks, FVGs, S/R
│   ├── volume.py                  # Volume SMA, OBV, VWAP, Volume Surge
│   └── confluence.py              # Multi-factor scoring engine (0-100)
│
├── dashboard/                     # 🖥️ Dash web interface
│   ├── app.py                     # Dash application factory & callbacks
│   ├── layout.py                  # UI layout (navbar, cards, tables)
│   ├── charts.py                  # Plotly chart builders
│   └── assets/
│       ├── tv_chart.html          # TradingView chart embed
│       └── signals.css            # Custom styling
│
├── alerts/                        # 🔔 Notification system
│   └── alert_engine.py            # Desktop, Sound, Telegram, Discord alerts
│
├── journal/                       # 📔 Trade journaling
│   └── journal.py                # SQLite journal, analytics, trade syncer
│
├── data/                          # 📂 Data storage
│   └── logs/                      # 📜 Rotating log files
│
└── utils/                         # 🛠️ Utilities (if any)
```

---

## 🔧 Strategy Implementation Details

### Session Windows (UTC)

| Session | Hours (UTC) | Description |
|---------|-------------|-------------|
| Asian | 00:00 - 08:00 | Tokyo session |
| Asian Range | 00:00 - 06:00 | Low volatility range |
| London Open | 07:00 - 09:00 | High volatility open |
| London | 07:00 - 16:00 | European session |
| NY Open | 12:00 - 14:00 | US market open |
| NY | 12:00 - 21:00 | US session |
| Silver Bullet AM | 15:00 - 16:00 | 10-11 AM ET |
| Silver Bullet PM | 19:00 - 20:00 | 2-3 PM ET |
| London-NY Overlap | 12:00 - 16:00 | Highest liquidity |

### Timeframe Constants

| Constant | Value | MT5 Name |
|----------|-------|----------|
| `TF.M1` | 1 | M1 (1 minute) |
| `TF.M5` | 5 | M5 (5 minutes) |
| `TF.M15` | 15 | M15 (15 minutes) |
| `TF.M30` | 30 | M30 (30 minutes) |
| `TF.H1` | 16385 | H1 (1 hour) |
| `TF.H4` | 16388 | H4 (4 hours) |
| `TF.D1` | 16408 | D1 (1 day) |
| `TF.W1` | 32769 | W1 (1 week) |
| `TF.MN1` | 49153 | MN1 (1 month) |

---

## 📊 Performance Metrics

### System Startup

```
+==============================================================+
|                                                              |
|      TRADING SYSTEM PRO                                      |
|                                                              |
|                  SYSTEM PRO  -  25 Strategies                |
|        Gold - NAS100 - US500 - US30 - Crypto - Real-Time MT5 |
|                                                              |
+==============================================================+

[1/9] Connecting to MetaTrader 5...
  [OK] Connected - Account: 123456 | Balance: $10,000.00 | Server: MyBroker

[2/9] Starting data feed...
  [OK] Data feed polling 24 pairs every 2s

[3/9] Initializing risk manager...
  [OK] Risk limits: 1.0% per trade, 3.0% daily, 6.0% weekly

[4/9] Loading strategies...
  [OK] 19 strategies active: [A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S]

[5/9] Initializing alert engine...
  [OK] Alert channels: Desktop, Sound

[6/9] Setting up journal...
  [OK] Journal DB at data/journal.db — Syncer running

[7/9] Launching strategy scanner...
  [OK] Scanner started — 19 strategies active, scanning every 2s

[8/9] Starting backtest manager...
  [OK] Backtest workers ready (2 processes)

[9/9] Starting optimization manager...
  [OK] Optimization job manager ready

==============================================================
  [OK] ALL SYSTEMS GO — Scanner running
==============================================================
```

---

## 🤝 Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines.

### Ways to Contribute

- 🐛 **Report bugs** via GitHub Issues
- ✨ **Suggest features** or improvements
- 📝 **Improve documentation**
- 🔧 **Submit pull requests** for new strategies or fixes

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

**⚠️ WARNING: Trading financial instruments carries significant risk.**

- This system is for **educational and research purposes only**
- Past performance does not guarantee future results
- Always use proper risk management
- Test thoroughly on demo accounts before live trading
- The authors assume no liability for trading losses

---

## 🙏 Acknowledgments

- MetaTrader 5 Python API
- Plotly Dash for the dashboard
- The trading community for strategy ideas

---

<p align="center">
  Made with ❤️ for algorithmic traders
</p>