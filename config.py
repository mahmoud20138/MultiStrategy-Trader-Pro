"""
╔══════════════════════════════════════════════════════════════════╗
║              TRADING SYSTEM — Configuration Module              ║
║          19 Strategies · 4 Instruments · Full Automation        ║
╚══════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    _example = Path(__file__).parent / ".env.example"
    if _example.exists():
        load_dotenv(_example)

# ── Helpers ──────────────────────────────────────────────────────
def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.getenv(key, str(default)))

def _env_int(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))

def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


# ══════════════════════════════════════════════════════════════════
# SYMBOL MAP
# ══════════════════════════════════════════════════════════════════
@dataclass
class SymbolMap:
    gold: str      = _env("SYMBOL_GOLD", "XAUUSD")
    nas100: str    = _env("SYMBOL_NAS100", "USTEC")
    us500: str     = _env("SYMBOL_US500", "US500")
    us30: str      = _env("SYMBOL_US30", "US30")
    dxy: str       = _env("SYMBOL_DXY", "USDX")
    btc: str       = _env("SYMBOL_BTC", "BTCUSD")
    eth: str       = _env("SYMBOL_ETH", "ETHUSD")
    enable_crypto: bool = _env_bool("ENABLE_CRYPTO", False)

    def all_trading(self) -> List[str]:
        symbols = [self.gold, self.nas100, self.us500, self.us30]
        if self.enable_crypto:
            symbols.extend([self.btc, self.eth])
        return symbols

    def name_for(self, symbol: str) -> str:
        _map = {
            self.gold: "GOLD", self.nas100: "NAS100",
            self.us500: "US500", self.us30: "US30", self.dxy: "DXY",
            self.btc: "BTC", self.eth: "ETH",
        }
        return _map.get(symbol, symbol)


# ══════════════════════════════════════════════════════════════════
# RISK CONFIG
# ══════════════════════════════════════════════════════════════════
@dataclass
class RiskConfig:
    max_risk_pct: float           = _env_float("MAX_RISK_PER_TRADE", 1.0)
    max_daily_loss_pct: float     = _env_float("MAX_DAILY_LOSS", 3.0)
    max_weekly_loss_pct: float    = _env_float("MAX_WEEKLY_LOSS", 6.0)
    max_monthly_dd_pct: float     = _env_float("MAX_MONTHLY_DRAWDOWN", 10.0)
    max_concurrent: int           = _env_int("MAX_CONCURRENT_TRADES", 3)
    consecutive_loss_pause: int   = 3          # pause after N consecutive losses
    pause_minutes: int            = 60         # how long to pause
    reduce_risk_after_loss_day: float = 0.5    # factor to reduce next day


# ══════════════════════════════════════════════════════════════════
# ALERT CONFIG
# ══════════════════════════════════════════════════════════════════
@dataclass
class AlertConfig:
    desktop: bool         = _env_bool("ENABLE_DESKTOP_ALERTS", True)
    sound: bool           = _env_bool("ENABLE_SOUND_ALERTS", True)
    telegram: bool        = _env_bool("ENABLE_TELEGRAM", False)
    telegram_token: str   = _env("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = _env("TELEGRAM_CHAT_ID", "")

    # Confluence scoring threshold — signals below this score are suppressed
    confluence_min_score: int = _env_int("CONFLUENCE_MIN_SCORE", 60)

    # Discord webhook notifications
    discord: bool              = _env_bool("ENABLE_DISCORD", False)
    discord_webhook_url: str   = _env("DISCORD_WEBHOOK_URL", "")
    discord_rate_limit: int    = _env_int("DISCORD_RATE_LIMIT_PER_30SEC", 30)


# ══════════════════════════════════════════════════════════════════
# TIMEFRAME CONSTANTS
# ══════════════════════════════════════════════════════════════════
class TF:
    """MT5 timeframe constants (mirrors MetaTrader5 module)."""
    M1  = 1
    M5  = 5
    M15 = 15
    M30 = 30
    H1  = 16385
    H4  = 16388
    D1  = 16408
    W1  = 32769
    MN1 = 49153

    _NAMES = {
        1: "M1", 5: "M5", 15: "M15", 30: "M30",
        16385: "H1", 16388: "H4", 16408: "D1",
        32769: "W1", 49153: "MN1",
    }

    @classmethod
    def name(cls, tf: int) -> str:
        return cls._NAMES.get(tf, f"TF({tf})")


# ══════════════════════════════════════════════════════════════════
# SESSION WINDOWS (UTC)
# ══════════════════════════════════════════════════════════════════
@dataclass
class SessionWindow:
    name: str
    start_hour: int
    start_minute: int = 0
    end_hour: int = 0
    end_minute: int = 0

SESSIONS = {
    "asian":          SessionWindow("Asian",          0, 0,  8, 0),
    "asian_range":    SessionWindow("Asian Range",    0, 0,  6, 0),
    "london_open":    SessionWindow("London Open",    7, 0,  9, 0),
    "london":         SessionWindow("London",         7, 0, 16, 0),
    "ny_open":        SessionWindow("NY Open",       12, 0, 14, 0),
    "ny":             SessionWindow("New York",      12, 0, 21, 0),
    "silver_bullet_1":SessionWindow("Silver Bullet AM", 15, 0, 16, 0),  # 10-11 AM ET
    "silver_bullet_2":SessionWindow("Silver Bullet PM", 19, 0, 20, 0),  # 2-3 PM ET
    "london_ny_overlap": SessionWindow("Overlap",    12, 0, 16, 0),
}


# ══════════════════════════════════════════════════════════════════
# STRATEGY METADATA
# ══════════════════════════════════════════════════════════════════
@dataclass
class StrategyMeta:
    id: str
    name: str
    instrument: str        # "gold", "nas100", "us500", "us30"
    style: str             # "scalp", "day", "swing"
    win_rate: tuple        # (low, high) as decimals
    risk_reward: tuple     # (1, target)
    timeframes: List[int]
    sessions: List[str]
    enabled: bool = True

STRATEGY_REGISTRY: Dict[str, StrategyMeta] = {
    "A": StrategyMeta("A", "London Breakout Trap",   "gold",   "scalp", (0.60, 0.68), (1, 2), [TF.M5, TF.M15], ["london_open"]),
    "B": StrategyMeta("B", "VWAP+OB Sniper",        "gold",   "scalp", (0.55, 0.62), (1, 2), [TF.M1, TF.M5],  ["ny_open"]),
    "C": StrategyMeta("C", "News Spike Fade",        "gold",   "scalp", (0.55, 0.60), (1, 1.5), [TF.M1, TF.M5], ["ny_open", "london"]),
    "D": StrategyMeta("D", "DXY Divergence",         "gold",   "day",   (0.62, 0.70), (1, 2), [TF.M15, TF.H1], ["london_ny_overlap"]),
    "E": StrategyMeta("E", "Session Transition",     "gold",   "day",   (0.58, 0.65), (1, 2), [TF.M15, TF.H1], ["ny_open"]),
    "F": StrategyMeta("F", "Trendline Break+Retest", "gold",   "day",   (0.55, 0.62), (1, 2.5), [TF.M15, TF.H1], ["london", "ny"]),
    "G": StrategyMeta("G", "Weekly Institutional",   "gold",   "swing", (0.55, 0.60), (1, 3), [TF.H4, TF.D1, TF.W1], ["london", "ny"]),
    "H": StrategyMeta("H", "Fibonacci Cluster",      "gold",   "swing", (0.55, 0.60), (1, 4), [TF.H4, TF.D1], ["london", "ny"]),
    "I": StrategyMeta("I", "ORB (Opening Range)",    "nas100", "scalp", (0.58, 0.70), (1, 2), [TF.M5, TF.M15], ["ny_open"]),
    "J": StrategyMeta("J", "EMA Ribbon Scalp",       "nas100", "scalp", (0.55, 0.60), (1, 1.5), [TF.M1, TF.M5], ["ny_open", "london"]),
    "K": StrategyMeta("K", "Power of 3 (ICT)",       "nas100", "scalp", (0.55, 0.65), (1, 3), [TF.M5, TF.M15], ["ny_open"]),
    "L": StrategyMeta("L", "Gap Fill",               "nas100", "day",   (0.65, 0.72), (1, 1.5), [TF.M15, TF.H1], ["ny_open"]),
    "M": StrategyMeta("M", "20/50 EMA Pullback",     "nas100", "swing", (0.55, 0.62), (1, 2.5), [TF.H4, TF.D1], ["ny"]),
    "N": StrategyMeta("N", "VWAP Mean Reversion",    "us500",  "scalp", (0.63, 0.72), (1, 1.75), [TF.M1, TF.M5], ["ny_open"]),
    "O": StrategyMeta("O", "Multi-TF Trend",         "us500",  "day",   (0.58, 0.64), (1, 2), [TF.M5, TF.M15, TF.H1], ["london", "ny"]),
    "P": StrategyMeta("P", "RSI + Structure",        "us500",  "swing", (0.55, 0.62), (1, 2.5), [TF.D1, TF.W1], ["ny"]),
    "Q": StrategyMeta("Q", "Round Number Bounce",    "us30",   "scalp", (0.60, 0.66), (1, 2), [TF.M5, TF.M15], ["ny_open", "london"]),
    "R": StrategyMeta("R", "ICT Silver Bullet",      "us30",   "day",   (0.55, 0.65), (1, 3), [TF.M5, TF.M15], ["silver_bullet_1", "silver_bullet_2"]),
    "S": StrategyMeta("S", "Breakout-Retest",        "us30",   "swing", (0.60, 0.70), (1, 3), [TF.H4, TF.D1], ["ny"]),
    "T": StrategyMeta("T", "BTC Round Number Bounce","btc",    "scalp", (0.60, 0.70), (1, 3), [TF.M5], []),  # 24/7 trading
    "U": StrategyMeta("U", "ETH Trend Following",    "eth",    "day",   (0.58, 0.65), (1, 2.5), [TF.H4], []),  # 24/7 trading
    # Crypto strategies (US6)
    "V": StrategyMeta("V", "BTC Momentum Breakout",  "btc",    "scalp", (0.58, 0.68), (1, 3), [TF.M15], []),
    "W": StrategyMeta("W", "BTC RSI Divergence",     "btc",    "day",   (0.60, 0.68), (1, 2.5), [TF.H1], []),
    "X": StrategyMeta("X", "ETH Order Block Sniper", "eth",    "scalp", (0.58, 0.66), (1, 2), [TF.M5], []),
    "Y": StrategyMeta("Y", "ETH Multi-TF Confluence","eth",    "swing", (0.55, 0.63), (1, 3), [TF.H4, TF.D1], []),
}


# ══════════════════════════════════════════════════════════════════
# CORRELATION MATRIX — blocks simultaneous same-direction trades
# ══════════════════════════════════════════════════════════════════
CORRELATION_BLOCKS = [
    ({"nas100", "us500"}, 0.92),
    ({"us500", "us30"},   0.95),
]


# ══════════════════════════════════════════════════════════════════
# MASTER CONFIG
# ══════════════════════════════════════════════════════════════════
@dataclass
class AppConfig:
    symbols: SymbolMap    = field(default_factory=SymbolMap)
    risk: RiskConfig      = field(default_factory=RiskConfig)
    alerts: AlertConfig   = field(default_factory=AlertConfig)

    mt5_path: str         = _env("MT5_PATH", "")
    db_path: str          = _env("DB_PATH", "data/journal.db")
    log_path: str         = _env("LOG_PATH", "data/logs")
    poll_interval: int    = _env_int("POLL_INTERVAL_SECONDS", 2)

    dash_host: str        = _env("DASH_HOST", "127.0.0.1")
    dash_port: int        = _env_int("DASH_PORT", 8050)
    dash_debug: bool      = _env_bool("DASH_DEBUG", False)


# Singleton
CONFIG = AppConfig()
SYMBOLS = CONFIG.symbols
