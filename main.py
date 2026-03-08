"""
╔══════════════════════════════════════════════════════════════════╗
║          TRADING SYSTEM PRO — Main Entry Point                  ║
║   19 Strategies · 4 Instruments · Real-Time Dashboard           ║
║   Alerts · Journal · Risk Management · MT5 Integration          ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python main.py                  # Launch full system
    python main.py --no-dashboard   # Headless scanner only
    python main.py --strategies A,B,D,I  # Enable specific strategies
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional

# ── Ensure project root is on the path ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import CONFIG, SYMBOLS, STRATEGY_REGISTRY, TF
from core.mt5_connection import MT5Connection, get_mt5
from core.data_feed import DataFeed, get_feed
from core.risk_manager import RiskManager
from core.backtest_engine import BacktestManager
from core.optimizer import OptimizationJobManager
from strategies import build_active_strategies, BaseStrategy, Signal
from alerts.alert_engine import AlertEngine, Alert, AlertLevel
from journal.journal import JournalDB, JournalAnalytics, TradeSyncer


# ══════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════
def _setup_logging() -> None:
    """Configure dual logging: console + rotating file."""
    log_dir = Path(CONFIG.log_path)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use ASCII format for Windows console compatibility
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-16s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO) - use stderr to avoid flush issues on Windows
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    # File handler (DEBUG, rotating 5 MB × 5 backups)
    log_file = log_dir / f"trading_{datetime.now():%Y%m%d}.log"
    file_h = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_h)

    # Quiet noisy libs
    for name in ("urllib3", "werkzeug", "dash", "requests"):
        logging.getLogger(name).setLevel(logging.WARNING)


log = logging.getLogger("main")


# ══════════════════════════════════════════════════════════════════
# INSTRUMENT MAPPER
# ══════════════════════════════════════════════════════════════════
def _instrument_to_symbol() -> Dict[str, str]:
    """Map strategy instrument names -> MT5 symbol strings."""
    return {
        "gold": SYMBOLS.gold,
        "nas100": SYMBOLS.nas100,
        "us500": SYMBOLS.us500,
        "us30": SYMBOLS.us30,
        "btc": SYMBOLS.btc,
        "eth": SYMBOLS.eth,
    }


# ══════════════════════════════════════════════════════════════════
# STRATEGY SCANNER (background thread)
# ══════════════════════════════════════════════════════════════════
class StrategyScanner:
    """
    Continuously evaluates all active strategies against live data,
    fires alerts on valid signals, logs to journal.
    """

    def __init__(
        self,
        strategies: List[BaseStrategy],
        data_feed: DataFeed,
        alert_engine: AlertEngine,
        journal_db: JournalDB,
        risk_manager: RiskManager,
    ) -> None:
        self._strategies = strategies
        self._feed = data_feed
        self._alerts = alert_engine
        self._journal = journal_db
        self._risk = risk_manager
        self._sym_map = _instrument_to_symbol()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._scan_count = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="Scanner")
        self._thread.start()
        log.info(
            "Strategy scanner started — %d strategies active, scanning every %ds",
            len(self._strategies),
            CONFIG.poll_interval,
        )

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Strategy scanner stopped after %d scan cycles", self._scan_count)

    def _loop(self) -> None:
        # Wait for DataFeed to populate initial cache
        time.sleep(CONFIG.poll_interval + 1)

        while self._running:
            try:
                self._scan_once()
                self._scan_count += 1
            except Exception as exc:
                log.error("Scanner cycle error: %s", exc, exc_info=True)
            time.sleep(CONFIG.poll_interval)

    def _scan_once(self) -> None:
        """Run through every active strategy, collect signals."""
        for strat in self._strategies:
            try:
                # Skip if outside active session
                if not strat.is_active_session():
                    continue

                # Resolve MT5 symbol
                symbol = self._sym_map.get(strat.meta.instrument)
                if not symbol:
                    continue

                # Fetch multi-TF data for this strategy
                data = self._feed.get_multi_tf(symbol, strat.meta.timeframes)
                if not data:
                    continue

                # Analyze
                signal: Optional[Signal] = strat.analyze(data)
                if signal is None:
                    continue

                # Confluence score threshold filter
                min_score = CONFIG.alerts.confluence_min_score
                if signal.score < min_score:
                    log.debug(
                        "Signal %s-%s suppressed: score=%d < threshold=%d",
                        strat.id,
                        signal.direction.value,
                        signal.score,
                        min_score,
                    )
                    continue

                # Risk check
                ok, reason = self._risk.check_entry(
                    symbol=symbol,
                    direction=signal.direction.value,
                    style=strat.meta.style,
                )
                if not ok:
                    log.info(
                        "Signal %s-%s blocked by risk manager: %s",
                        strat.id,
                        signal.direction.value,
                        reason,
                    )
                    self._alerts.fire(
                        Alert(
                            level=AlertLevel.WARNING,
                            title=f"Signal Blocked — {strat.id}",
                            body=f"Risk check failed: {reason}",
                            strategy_id=strat.id,
                            symbol=symbol,
                        )
                    )
                    continue

                # Fire alert (dedup inside — returns False if suppressed)
                fired = self._alerts.fire_from_signal(signal, symbol=symbol)
                if not fired:
                    continue

                # Log to journal
                self._journal.log_signal(signal.to_dict() | {"symbol": symbol})

                log.info(
                    "[SIGNAL] %s %s %s | Entry=%.2f SL=%.2f TP=%.2f RR=%.1f Score=%d",
                    strat.id,
                    symbol,
                    signal.direction.value,
                    signal.entry_price,
                    signal.stop_loss,
                    signal.take_profit,
                    signal.risk_reward,
                    signal.score,
                )

            except Exception as exc:
                log.error(
                    "Strategy %s evaluation error: %s", strat.id, exc, exc_info=True
                )


# ══════════════════════════════════════════════════════════════════
# APPLICATION ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════
class TradingSystem:
    """
    Orchestrates all subsystems:
      1. MT5 connection
      2. Data feed (polling)
      3. Strategy scanner
      4. Alert engine
      5. Journal + trade syncer
      6. Risk manager
      7. Dash dashboard
    """

    def __init__(
        self, strategy_ids: Optional[List[str]] = None, headless: bool = False
    ):
        self._headless = headless
        self._strategy_ids = strategy_ids
        self._shutdown_event = threading.Event()

        # Components (initialized in start())
        self._mt5: Optional[MT5Connection] = None
        self._feed: Optional[DataFeed] = None
        self._risk: Optional[RiskManager] = None
        self._strategies: List[BaseStrategy] = []
        self._alert_engine: Optional[AlertEngine] = None
        self._journal_db: Optional[JournalDB] = None
        self._analytics: Optional[JournalAnalytics] = None
        self._syncer: Optional[TradeSyncer] = None
        self._scanner: Optional[StrategyScanner] = None
        self._backtest_mgr: Optional[BacktestManager] = None
        self._optimizer_mgr: Optional[OptimizationJobManager] = None

    def start(self) -> None:
        """Boot the entire system."""
        _print_banner()
        _setup_logging()

        log.info("=" * 60)
        log.info("  TRADING SYSTEM PRO — Initializing")
        log.info("=" * 60)

        # ── Step 1: Data directories ────────────────────────
        data_dir = PROJECT_ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 2: MT5 Connection ──────────────────────────
        log.info("[1/7] Connecting to MetaTrader 5...")
        self._mt5 = get_mt5()
        if not self._mt5.connect():
            log.critical("[ERROR] Cannot connect to MT5.")
            log.critical("")
            log.critical("Please ensure:")
            log.critical("  1. MetaTrader 5 is installed on your system")
            log.critical("  2. MT5 terminal is running and you are logged in")
            log.critical("  3. MT5_PATH in .env points to your terminal64.exe")
            log.critical("")
            log.critical("Common MT5 installation paths:")
            log.critical("  • C:\\Program Files\\MetaTrader 5\\terminal64.exe")
            log.critical("  • C:\\Program Files (x86)\\MetaTrader 5\\terminal64.exe")
            log.critical("  • Check your broker's MT5 installation folder")
            log.critical("")
            log.critical("Edit .env file and set: MT5_PATH=<your_path_here>")
            log.critical("")
            sys.exit(1)
        acc = self._mt5.account_info()
        if acc:
            log.info(
                "  [OK] Connected - Account: %s | Balance: $%s | Server: %s",
                acc.get("login", "?"),
                f"{acc.get('balance', 0):,.2f}",
                acc.get("server", "?"),
            )

        # ── Step 3: Data Feed ───────────────────────────────
        log.info("[2/7] Starting data feed...")
        self._feed = get_feed()
        self._feed.start()
        log.info(
            "  [OK] Data feed polling %d pairs every %ds",
            len(self._feed._build_pairs()),
            CONFIG.poll_interval,
        )

        # ── Step 4: Risk Manager ────────────────────────────
        log.info("[3/7] Initializing risk manager...")
        self._risk = RiskManager()
        log.info(
            "  [OK] Risk limits: %.1f%% per trade, %.1f%% daily, %.1f%% weekly",
            CONFIG.risk.max_risk_pct,
            CONFIG.risk.max_daily_loss_pct,
            CONFIG.risk.max_weekly_loss_pct,
        )

        # ── Step 5: Strategies ──────────────────────────────
        log.info("[4/7] Loading strategies...")
        self._strategies = build_active_strategies(self._strategy_ids)
        strat_summary = ", ".join(s.id for s in self._strategies)
        log.info(
            "  [OK] %d strategies active: [%s]", len(self._strategies), strat_summary
        )

        # ── Step 6: Alert Engine ────────────────────────────
        log.info("[5/7] Initializing alert engine...")
        self._alert_engine = AlertEngine()
        channels = ["Desktop", "Sound"]
        if CONFIG.alerts.telegram and CONFIG.alerts.telegram_token:
            channels.append("Telegram")
        log.info("  [OK] Alert channels: %s", ", ".join(channels))

        # ── Step 7: Journal & Syncer ────────────────────────
        log.info("[6/7] Setting up journal...")
        db_path = PROJECT_ROOT / CONFIG.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._journal_db = JournalDB(str(db_path))
        self._analytics = JournalAnalytics(self._journal_db)
        self._syncer = TradeSyncer(self._journal_db, self._mt5)
        self._syncer.start()
        log.info("  [OK] Journal DB at %s — Syncer running", db_path)

        # ── Step 8: Strategy Scanner ────────────────────────
        log.info("[7/7] Launching strategy scanner...")
        self._scanner = StrategyScanner(
            strategies=self._strategies,
            data_feed=self._feed,
            alert_engine=self._alert_engine,
            journal_db=self._journal_db,
            risk_manager=self._risk,
        )
        self._scanner.start()

        # ── Step 9: Backtest Manager ─────────────────────────
        log.info("[8/9] Starting backtest manager...")
        self._backtest_mgr = BacktestManager(num_workers=2)
        self._backtest_mgr.start()
        log.info("  [OK] Backtest workers ready (2 processes)")

        # ── Step 10: Optimization Manager (US5) ───────────────
        log.info("[9/9] Starting optimization manager...")
        self._optimizer_mgr = OptimizationJobManager()
        log.info("  [OK] Optimization job manager ready")

        # Startup alert
        self._alert_engine.fire(
            Alert(
                level=AlertLevel.INFO,
                title="System Online",
                body=f"{len(self._strategies)} strategies scanning | {_now_str()}",
            )
        )

        log.info("=" * 60)
        log.info("  [OK] ALL SYSTEMS GO — Scanner running")
        log.info("=" * 60)

        # ── Dashboard or block ──────────────────────────────
        if not self._headless:
            self._launch_dashboard()
        else:
            log.info("Headless mode — press Ctrl+C to stop")
            self._block_until_shutdown()

    def _launch_dashboard(self) -> None:
        """Create and run the Dash web dashboard."""
        log.info(
            "Starting dashboard at http://%s:%d", CONFIG.dash_host, CONFIG.dash_port
        )

        from dashboard.app import create_app

        app = create_app(
            data_feed=self._feed,
            alert_engine=self._alert_engine,
            journal_db=self._journal_db,
            journal_analytics=self._analytics,
            mt5_conn=self._mt5,
            strategy_instances=self._strategies,
            backtest_manager=self._backtest_mgr,
            optimizer_manager=self._optimizer_mgr,
        )

        try:
            app.run(
                host=CONFIG.dash_host,
                port=CONFIG.dash_port,
                debug=CONFIG.dash_debug,
                use_reloader=False,  # We manage our own threads
            )
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _block_until_shutdown(self) -> None:
        """Block main thread in headless mode."""
        try:
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Graceful shutdown of all subsystems."""
        log.info("Shutting down...")
        self._shutdown_event.set()

        if self._scanner:
            self._scanner.stop()
        if self._backtest_mgr:
            self._backtest_mgr.stop()
        if self._syncer:
            self._syncer.stop()
        if self._feed:
            self._feed.stop()

        # Final alert (best-effort, may fail if MT5 disconnected)
        try:
            if self._alert_engine:
                self._alert_engine.fire(
                    Alert(
                        level=AlertLevel.INFO,
                        title="System Offline",
                        body=f"Shutdown at {_now_str()}",
                    )
                )
        except Exception:
            pass

        log.info("All systems stopped. Goodbye.")


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _print_banner() -> None:
    try:
        banner = r"""
    +==============================================================+
    |                                                              |
    |      TRADING SYSTEM PRO                                      |
    |                                                              |
    |                  SYSTEM PRO  -  19 Strategies                |
    |        Gold - NAS100 - US500 - US30 - Real-Time MT5          |
    |                                                              |
    +==============================================================+
    """
        print(banner)
    except UnicodeEncodeError:
        # Fallback for Windows console without Unicode support
        print("=" * 60)
        print("  TRADING SYSTEM PRO - 19 Strategies")
        print("  Gold - NAS100 - US500 - US30 - Real-Time MT5")
        print("=" * 60)


def _print_strategy_table(strategies: List[BaseStrategy]) -> None:
    """Pretty-print active strategies at startup."""
    log.info("┌─────┬────────────────────────┬──────────┬────────┬───────────────────┐")
    log.info("│  ID │ Strategy               │ Symbol   │ Style  │ Sessions          │")
    log.info("├─────┼────────────────────────┼──────────┼────────┼───────────────────┤")
    sym_map = _instrument_to_symbol()
    for s in strategies:
        sym = sym_map.get(s.meta.instrument, "?")[:8]
        sessions = ",".join(s.meta.sessions)[:17]
        log.info(
            "│  %s  │ %-22s │ %-8s │ %-6s │ %-17s │",
            s.id,
            s.name[:22],
            sym,
            s.meta.style,
            sessions,
        )
    log.info("└─────┴────────────────────────┴──────────┴────────┴───────────────────┘")


# ══════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Trading System Pro — 19-Strategy MT5 Scanner + Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           Full system with dashboard
  python main.py --no-dashboard            Headless scanner
  python main.py --strategies A,B,D,I,Q    Select specific strategies
  python main.py --strategies gold         All gold strategies (A-H)
  python main.py --strategies scalp        All scalp strategies
        """,
    )
    p.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Run in headless mode (scanner + alerts only, no web UI)",
    )
    p.add_argument(
        "--strategies",
        type=str,
        default=None,
        help=(
            "Comma-separated strategy IDs (e.g. A,B,D) "
            "or filter: 'gold', 'nas100', 'us500', 'us30', 'scalp', 'day', 'swing'"
        ),
    )
    p.add_argument(
        "--host",
        type=str,
        default=None,
        help="Dashboard host (overrides .env DASH_HOST)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=None,
        help="Dashboard port (overrides .env DASH_PORT)",
    )
    return p.parse_args()


def _resolve_strategies(raw: str) -> Optional[List[str]]:
    """Parse --strategies flag: individual IDs, instrument name, or style."""
    if not raw:
        return None  # All strategies

    raw = raw.strip().upper()

    # Instrument filter
    instrument_map = {
        "GOLD": ["A", "B", "C", "D", "E", "F", "G", "H"],
        "NAS100": ["I", "J", "K", "L", "M"],
        "US500": ["N", "O", "P"],
        "US30": ["Q", "R", "S"],
        "BTC": ["T"],
        "ETH": ["U"],
    }
    if raw in instrument_map:
        return instrument_map[raw]

    # Style filter
    style_map = {
        "SCALP": [],
        "DAY": [],
        "SWING": [],
    }
    for sid, meta in STRATEGY_REGISTRY.items():
        if meta.style.upper() in style_map:
            style_map[meta.style.upper()].append(sid)
    if raw in style_map and style_map[raw]:
        return style_map[raw]

    # Individual IDs
    ids = [s.strip() for s in raw.split(",") if s.strip()]
    valid = [s for s in ids if s in STRATEGY_REGISTRY]
    if not valid:
        log.warning("No valid strategy IDs found in '%s'. Using all strategies.", raw)
        return None
    return valid


def main() -> None:
    args = parse_args()

    # Override config from CLI
    if args.host:
        CONFIG.dash_host = args.host
    if args.port:
        CONFIG.dash_port = args.port

    strategy_ids = _resolve_strategies(args.strategies) if args.strategies else None

    system = TradingSystem(
        strategy_ids=strategy_ids,
        headless=args.no_dashboard,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    def _signal_handler(signum, frame):
        log.info("Signal %s received — initiating shutdown...", signum)
        system._shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    system.start()


if __name__ == "__main__":
    main()
