"""
╔══════════════════════════════════════════════════════════════════╗
║              Trading Journal — Auto-Sync + Analytics            ║
╚══════════════════════════════════════════════════════════════════╝
• Auto-imports closed trades from MT5 (history_deals)
• Logs every signal + outcome with strategy_id
• Computes performance analytics per strategy / day / week
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import CONFIG

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# Data models
# ────────────────────────────────────────────────────────────────
@dataclass
class TradeRecord:
    ticket: int
    symbol: str
    direction: str  # "BUY" / "SELL"
    strategy_id: str
    open_time: datetime
    close_time: Optional[datetime] = None
    entry_price: float = 0.0
    close_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    lot: float = 0.0
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    pips: float = 0.0
    rr_achieved: float = 0.0
    outcome: str = ""  # "WIN" / "LOSS" / "BE"
    confluence: List[str] = field(default_factory=list)
    notes: str = ""
    screenshot: str = ""

    @property
    def net_pnl(self) -> float:
        return self.profit + self.commission + self.swap


# ────────────────────────────────────────────────────────────────
# Journal DB
# ────────────────────────────────────────────────────────────────
class JournalDB:
    """SQLite-based trade journal."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS trades (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket       INTEGER UNIQUE,
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
        outcome      TEXT,
        confluence   TEXT,
        notes        TEXT,
        screenshot   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_trades_ticket ON trades(ticket);
    CREATE INDEX IF NOT EXISTS idx_trades_strat  ON trades(strategy_id);
    CREATE INDEX IF NOT EXISTS idx_trades_close  ON trades(close_time);

    CREATE TABLE IF NOT EXISTS signals_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT    NOT NULL,
        strategy_id  TEXT,
        symbol       TEXT,
        direction    TEXT,
        entry        REAL,
        sl           REAL,
        tp           REAL,
        score        REAL,
        confluence   TEXT,
        acted_on     INTEGER DEFAULT 0,
        ticket       INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_siglog_ts ON signals_log(timestamp);
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.executescript(self._DDL)
            con.close()

    # ── write ───────────────────────────────────────────────
    def upsert_trade(self, t: TradeRecord) -> None:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.execute(
                """INSERT INTO trades
                   (ticket,symbol,direction,strategy_id,open_time,close_time,
                    entry_price,close_price,sl,tp,lot,profit,commission,swap,
                    pips,rr_achieved,outcome,confluence,notes,screenshot)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(ticket) DO UPDATE SET
                    close_time=excluded.close_time,
                    close_price=excluded.close_price,
                    profit=excluded.profit,
                    commission=excluded.commission,
                    swap=excluded.swap,
                    pips=excluded.pips,
                    rr_achieved=excluded.rr_achieved,
                    outcome=excluded.outcome,
                    notes=excluded.notes""",
                (
                    t.ticket, t.symbol, t.direction, t.strategy_id,
                    t.open_time.isoformat(), t.close_time.isoformat() if t.close_time else None,
                    t.entry_price, t.close_price, t.sl, t.tp, t.lot,
                    t.profit, t.commission, t.swap, t.pips, t.rr_achieved,
                    t.outcome, json.dumps(t.confluence), t.notes, t.screenshot,
                ),
            )
            con.commit()
            con.close()

    def log_signal(self, signal_data: Dict[str, Any]) -> None:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.execute(
                """INSERT INTO signals_log
                   (timestamp,strategy_id,symbol,direction,entry,sl,tp,score,confluence)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    signal_data.get("strategy_id", ""),
                    signal_data.get("symbol", ""),
                    signal_data.get("direction", ""),
                    signal_data.get("entry", 0),
                    signal_data.get("sl", 0),
                    signal_data.get("tp", 0),
                    signal_data.get("score", 0),
                    json.dumps(signal_data.get("confluence", [])),
                ),
            )
            con.commit()
            con.close()

    # ── read ────────────────────────────────────────────────
    def get_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]

    def get_trades_by_strategy(self, strategy_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM trades WHERE strategy_id=? ORDER BY id DESC LIMIT ?",
                (strategy_id, limit),
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]

    def get_trades_range(self, start: str, end: str) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM trades WHERE close_time >= ? AND close_time <= ? ORDER BY close_time",
                (start, end),
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]

    def get_signals_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM signals_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────────
# Analytics
# ────────────────────────────────────────────────────────────────
class JournalAnalytics:
    """Compute performance metrics from journal data."""

    def __init__(self, db: JournalDB) -> None:
        self._db = db

    def strategy_stats(self, strategy_id: str | None = None) -> Dict[str, Any]:
        if strategy_id:
            trades = self._db.get_trades_by_strategy(strategy_id, limit=500)
        else:
            trades = self._db.get_trades(limit=1000)

        if not trades:
            return {"total": 0}

        wins = [t for t in trades if t.get("outcome") == "WIN"]
        losses = [t for t in trades if t.get("outcome") == "LOSS"]
        total = len(trades)
        win_count = len(wins)
        loss_count = len(losses)

        total_profit = sum(t.get("profit", 0) + t.get("commission", 0) + t.get("swap", 0) for t in trades)
        win_total = sum(t.get("profit", 0) for t in wins) if wins else 0
        loss_total = sum(abs(t.get("profit", 0)) for t in losses) if losses else 0

        avg_win = win_total / win_count if win_count else 0
        avg_loss = loss_total / loss_count if loss_count else 0

        # Max drawdown (sequential)
        equity_curve = []
        running = 0
        for t in sorted(trades, key=lambda x: x.get("close_time", "")):
            running += t.get("profit", 0) + t.get("commission", 0) + t.get("swap", 0)
            equity_curve.append(running)

        max_dd = 0
        peak = 0
        for eq in equity_curve:
            peak = max(peak, eq)
            dd = peak - eq
            max_dd = max(max_dd, dd)

        # Consecutive losses
        max_consec_loss = 0
        curr_consec = 0
        for t in sorted(trades, key=lambda x: x.get("close_time", "")):
            if t.get("outcome") == "LOSS":
                curr_consec += 1
                max_consec_loss = max(max_consec_loss, curr_consec)
            else:
                curr_consec = 0

        # Average R:R
        rrs = [t.get("rr_achieved", 0) for t in trades if t.get("rr_achieved")]
        avg_rr = sum(rrs) / len(rrs) if rrs else 0

        return {
            "total": total,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_count / total * 100, 1) if total else 0,
            "total_pnl": round(total_profit, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(win_total / loss_total, 2) if loss_total else float("inf"),
            "avg_rr": round(avg_rr, 2),
            "max_drawdown": round(max_dd, 2),
            "max_consec_losses": max_consec_loss,
            "expectancy": round(
                (win_count / total * avg_win) - (loss_count / total * avg_loss), 2
            ) if total else 0,
        }

    def daily_pnl(self, days: int = 30) -> List[Dict[str, Any]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        trades = self._db.get_trades_range(start.isoformat(), end.isoformat())

        daily: Dict[str, float] = {}
        for t in trades:
            ct = t.get("close_time", "")
            if ct:
                day = ct[:10]
                pnl = t.get("profit", 0) + t.get("commission", 0) + t.get("swap", 0)
                daily[day] = daily.get(day, 0) + pnl

        return [{"date": k, "pnl": round(v, 2)} for k, v in sorted(daily.items())]


# ────────────────────────────────────────────────────────────────
# MT5 Trade Sync
# ────────────────────────────────────────────────────────────────
class TradeSyncer:
    """
    Background thread syncs closed trades from MT5 into journal.
    Runs every 30 seconds, looks back 24 hours.
    """

    def __init__(self, journal_db: JournalDB, mt5_conn) -> None:
        self._db = journal_db
        self._mt5 = mt5_conn
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._signal_map: Dict[int, Dict[str, Any]] = {}  # ticket → signal info

    def register_signal(self, ticket: int, signal_data: Dict[str, Any]) -> None:
        """Link a signal to an opened trade ticket."""
        self._signal_map[ticket] = signal_data

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="TradeSyncer")
        self._thread.start()
        log.info("Trade syncer started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while self._running:
            try:
                self._sync_once()
            except Exception as exc:
                log.error("Sync error: %s", exc)
            time.sleep(30)

    def _sync_once(self) -> None:
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(hours=24)

        deals = self._mt5.get_history_deals(from_date, now)
        if not deals:
            return

        # Group by position_id
        from collections import defaultdict
        groups: Dict[int, list] = defaultdict(list)
        for d in deals:
            pid = d.get("position_id", 0)
            if pid != 0:
                groups[pid].append(d)

        for ticket, grp in groups.items():
            # Need at least open + close
            if len(grp) < 2:
                continue

            open_deal = grp[0]
            close_deal = grp[-1]

            direction = "BUY" if open_deal.get("type", 0) == 0 else "SELL"
            profit = close_deal.get("profit", 0)
            commission = sum(d.get("commission", 0) for d in grp)
            swap = sum(d.get("swap", 0) for d in grp)

            # Determine outcome
            net = profit + commission + swap
            if net > 0:
                outcome = "WIN"
            elif net < 0:
                outcome = "LOSS"
            else:
                outcome = "BE"

            # Check signal map for strategy_id
            sig = self._signal_map.get(ticket, {})

            entry_price = open_deal.get("price", 0)
            close_price = close_deal.get("price", 0)
            sl_val = sig.get("sl", 0)

            # Calculate R:R achieved
            risk = abs(entry_price - sl_val) if sl_val else 0
            reward = abs(close_price - entry_price)
            rr = round(reward / risk, 2) if risk > 0 else 0

            open_time = open_deal.get("time", 0)
            close_time = close_deal.get("time", 0)
            # Handle both datetime objects and timestamps
            if isinstance(open_time, datetime):
                ot = open_time
            else:
                ot = datetime.fromtimestamp(open_time, tz=timezone.utc)
            if isinstance(close_time, datetime):
                ct = close_time
            else:
                ct = datetime.fromtimestamp(close_time, tz=timezone.utc)

            record = TradeRecord(
                ticket=int(ticket),
                symbol=open_deal.get("symbol", ""),
                direction=direction,
                strategy_id=sig.get("strategy_id", "manual"),
                open_time=ot,
                close_time=ct,
                entry_price=entry_price,
                close_price=close_price,
                sl=sl_val,
                tp=sig.get("tp", 0),
                lot=open_deal.get("volume", 0),
                profit=profit,
                commission=commission,
                swap=swap,
                rr_achieved=rr if outcome == "WIN" else -rr,
                outcome=outcome,
                confluence=sig.get("confluence", []),
                notes=sig.get("notes", ""),
            )
            self._db.upsert_trade(record)

        log.debug("Synced %d positions from MT5", len(groups))
