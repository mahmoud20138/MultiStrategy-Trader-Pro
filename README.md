# MT5 Multi-Strategy Trader

**25 Strategies -- 6 Instruments -- Real-Time Dashboard -- MetaTrader 5**

A professional-grade automated strategy scanner that connects to MetaTrader 5, runs 25 independent trading strategies across Gold, NAS100, US500, US30, BTC, and ETH. Features a real-time Plotly Dash dashboard, confluence-based signal scoring, backtesting engine, risk management, trade journaling, and alert system.

---

## Architecture

```
+------------------+     +------------------+     +------------------+
|   MT5 Terminal   | --> |    Data Feed     | --> |   25 Strategies  |
|  (Live Prices)   |     | (Multi-TF OHLCV) |     |  (A through Y)   |
+------------------+     +------------------+     +--------+---------+
                                                           |
                                                    Signals + Scores
                                                           |
                    +--------------------------------------+
                    |              |              |         |
              +-----+----+  +-----+----+  +------+---+  +-+--------+
              | Dashboard |  |   Risk   |  |  Alert   |  | Journal  |
              | (Dash UI) |  | Manager  |  |  Engine  |  | (SQLite) |
              +-----------+  +----------+  +----------+  +----------+
```

### Data Flow

```
MT5 OHLCV (M1/M5/M15/H1/H4/D1/W1)
        |
        v
  Indicators (Momentum, Trend, Volatility, Structure, Volume)
        |
        v
  Strategy.analyze() --> Raw Signal (direction, entry, SL, TP)
        |
        v
  ConfluenceEngine.score() --> Scored Signal (0-100, quality tier)
        |
        v
  RiskManager.validate() --> Position sizing, daily limits
        |
        v
  Dashboard display + Alert notifications + Journal logging
```

---

## All 25 Strategies

### Gold (XAUUSD) -- 8 Strategies

| ID | Name | Style | Timeframes | Session |
|----|------|-------|-----------|---------|
| A | London Breakout Trap | Scalp | M5, M15 | London Open |
| B | VWAP+OB Sniper | Scalp | M1, M5 | NY Open |
| C | News Spike Fade | Scalp | M1, M5 | NY Open, London |
| D | DXY Divergence | Day | M15, H1 | London-NY Overlap |
| E | Session Transition | Day | M15, H1 | NY Open |
| F | Trendline Break+Retest | Day | M15, H1 | London, NY |
| G | Weekly Institutional | Swing | H4, D1, W1 | London, NY |
| H | Fibonacci Cluster | Swing | H4, D1 | London, NY |

### NAS100 (USTEC) -- 5 Strategies

| ID | Name | Style | Timeframes | Session |
|----|------|-------|-----------|---------|
| I | ORB (Opening Range) | Scalp | M5, M15 | NY Open |
| J | EMA Ribbon Scalp | Scalp | M1, M5 | NY Open, London |
| K | Power of 3 (ICT) | Scalp | M5, M15 | NY Open |
| L | Gap Fill | Day | M15, H1 | NY Open |
| M | 20/50 EMA Pullback | Swing | H4, D1 | NY |

### US500 (S&P 500) -- 3 Strategies

| ID | Name | Style | Timeframes | Session |
|----|------|-------|-----------|---------|
| N | VWAP Mean Reversion | Scalp | M1, M5 | NY Open |
| O | Multi-TF Trend | Day | M5, M15, H1 | London, NY |
| P | RSI + Structure | Swing | D1, W1 | NY |

### US30 (Dow Jones) -- 3 Strategies

| ID | Name | Style | Timeframes | Session |
|----|------|-------|-----------|---------|
| Q | Round Number Bounce | Scalp | M5, M15 | NY Open, London |
| R | ICT Silver Bullet | Day | M5, M15 | Silver Bullet windows |
| S | Breakout-Retest | Swing | H4, D1 | NY |

### Crypto (BTC/ETH) -- 6 Strategies

| ID | Name | Style | Timeframes | Notes |
|----|------|-------|-----------|-------|
| T | BTC Round Number Bounce | Scalp | M5 | 24/7 trading |
| U | ETH Trend Following | Day | H4 | 24/7 trading |
| V | BTC Momentum Breakout | Scalp | M15 | 24/7 trading |
| W | BTC RSI Divergence | Day | H1 | 24/7 trading |
| X | ETH Order Block Sniper | Scalp | M5 | 24/7 trading |
| Y | ETH Multi-TF Confluence | Swing | H4, D1 | 24/7 trading |

---

## Confluence Scoring

Every signal passes through a `ConfluenceEngine` that scores it 0-100 based on multiple factors:

- Trend alignment (multi-TF EMA/SMA agreement)
- Momentum confirmation (RSI, MACD, Stochastic)
- Volatility context (ATR, Bollinger Band position)
- Structure levels (support/resistance, swing points)
- Volume confirmation

Quality tiers based on score:
- **Elite** (85+): Highest confidence, full position size
- **High** (70-84): Strong setup, standard size
- **Normal** (60-69): Acceptable, reduced size
- **Low** (<60): Filtered out

---

## Indicators

| Module | Indicators |
|--------|-----------|
| `trend.py` | EMA (10/21/50/200), SMA, ADX, Ichimoku Cloud |
| `momentum.py` | RSI, MACD, Stochastic, Williams %R, CCI |
| `volatility.py` | ATR, Bollinger Bands, Keltner Channels, Standard Deviation |
| `structure.py` | Swing highs/lows, support/resistance, BOS/CHoCH, Order Blocks, FVGs |
| `volume.py` | Volume SMA, OBV, Volume Rate of Change, VWAP |
| `confluence.py` | Multi-factor scoring engine combining all indicators |

---

## Dashboard

Real-time Plotly Dash dashboard with:

- **Signal Table**: All active signals with direction, score, quality tier, entry/SL/TP
- **TradingView-style Charts**: Embedded interactive charts per instrument
- **Strategy Performance**: Win rates, P&L, signal history per strategy
- **Risk Monitor**: Daily P&L, open exposure, consecutive losses
- **Journal View**: Complete trade history with analytics

---

## Backtesting Engine

Built-in backtester for validating strategies on historical data:

- Walk-forward optimization with configurable in-sample/out-of-sample splits
- Per-strategy and multi-strategy backtesting
- Metrics: win rate, profit factor, Sharpe ratio, max drawdown, R-multiples
- Optimization job manager for parameter sweeps

---

## Risk Management

- **Max risk per trade**: 1.0% (configurable)
- **Max daily loss**: 3.0%
- **Max weekly loss**: 6.0%
- **Max monthly drawdown**: 10.0%
- **Max concurrent trades**: 3
- **Consecutive loss pause**: After 3 losses, pause 60 minutes
- **Next-day risk reduction**: 0.5x after a losing day

---

## Installation

### Prerequisites

- Python 3.10+
- MetaTrader 5 terminal running on Windows
- MT5 broker account

### Setup

```bash
cd trading_system
pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env` and fill in:
   ```
   MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
   MT5_LOGIN=12345678
   MT5_PASSWORD=your_password
   MT5_SERVER=YourBroker-Server
   SYMBOL_GOLD=XAUUSD
   SYMBOL_NAS100=USTEC
   SYMBOL_US500=US500
   SYMBOL_US30=US30
   ENABLE_CRYPTO=false
   MAX_RISK_PER_TRADE=1.0
   MAX_DAILY_LOSS=3.0
   ```

2. Adjust symbol names to match your broker's naming convention.

---

## Usage

```bash
# Launch full system with dashboard
python main.py

# Headless scanner only (no dashboard UI)
python main.py --no-dashboard

# Enable only specific strategies
python main.py --strategies A,B,D,I

# Enable crypto strategies
ENABLE_CRYPTO=true python main.py
```

### CLI Flags

| Flag | Description |
|------|------------|
| `--no-dashboard` | Run scanner without the Dash UI |
| `--strategies A,B,D` | Enable only specified strategy IDs |
| `--scan-interval 300` | Scan interval in seconds (default: 300) |

---

## Results & Output

### Signal Example

```
[SIGNAL] Strategy A: London Breakout Trap
  Instrument: XAUUSD | Direction: BUY | Strength: STRONG
  Entry: 2345.50 | SL: 2340.00 | TP: 2356.50 | RR: 2.0
  Score: 82/100 | Tier: HIGH
  Confluence: [trend_aligned, rsi_oversold, at_support, volume_spike]
```

### Dashboard Output

The dashboard runs at `http://localhost:8050` and shows:
- Live signal table updated every scan interval
- Per-strategy win rate and P&L tracking
- Interactive charts with entry/exit markers

### Journal Database

All signals and trades logged to SQLite (`data/trading.db`) with full metadata for later analysis.

---

## Project Structure

```
trading_system/
  main.py                          # Entry point
  config.py                        # All configuration (symbols, risk, strategies)
  requirements.txt
  .env.example                     # Environment template
  core/
    mt5_connection.py              # MT5 terminal wrapper
    data_feed.py                   # Multi-TF OHLCV data fetcher
    risk_manager.py                # Position sizing, daily limits
    backtest_engine.py             # Walk-forward backtester
    optimizer.py                   # Parameter optimization
  strategies/
    __init__.py                    # Strategy registry (A-Y)
    base.py                        # BaseStrategy + Signal model
    gold_strategies.py             # Strategies A-H (Gold)
    nas100_strategies.py           # Strategies I-M (NAS100)
    us500_strategies.py            # Strategies N-P (US500)
    us30_strategies.py             # Strategies Q-S (US30)
    crypto_strategies.py           # Strategies T-Y (BTC/ETH)
  indicators/
    trend.py                       # EMA, SMA, ADX, Ichimoku
    momentum.py                    # RSI, MACD, Stochastic
    volatility.py                  # ATR, Bollinger, Keltner
    structure.py                   # Swing points, BOS, OBs, FVGs
    volume.py                      # OBV, VWAP, Volume SMA
    confluence.py                  # Multi-factor scoring engine
  dashboard/
    app.py                         # Dash application
    layout.py                      # UI layout
    charts.py                      # Plotly chart builders
  alerts/
    alert_engine.py                # Multi-level alert system
  journal/
    journal.py                     # SQLite journal + analytics + trade syncer
  data/
    logs/                          # Rotating log files
```
