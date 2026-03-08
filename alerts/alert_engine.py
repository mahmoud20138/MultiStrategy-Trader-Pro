"""
╔══════════════════════════════════════════════════════════════════╗
║              Alert Engine — Multi-Channel Notifications         ║
╚══════════════════════════════════════════════════════════════════╝
Channels:  Desktop (plyer) · Sound (winsound) · Telegram (optional)
Features:  Deduplication · Cooldown · SQLite history · Severity
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
import winsound
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import CONFIG

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# Alert types / severity
# ────────────────────────────────────────────────────────────────
class AlertLevel(Enum):
    INFO = "info"
    SIGNAL = "signal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    level: AlertLevel
    title: str
    body: str
    strategy_id: str = ""
    symbol: str = ""
    direction: str = ""
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    score: float = 0.0
    confluence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Unique hash for dedup within cooldown window."""
        raw = f"{self.strategy_id}|{self.symbol}|{self.direction}|{self.entry:.2f}"
        return hashlib.md5(raw.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "title": self.title,
            "body": self.body,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "score": self.score,
            "confluence": self.confluence,
            "timestamp": self.timestamp.isoformat(),
        }


# ────────────────────────────────────────────────────────────────
# Notifiers (Desktop, Sound, Telegram)
# ────────────────────────────────────────────────────────────────
class DesktopNotifier:
    """Cross-platform toast via plyer (falls back to winsound)."""

    def send(self, alert: Alert) -> None:
        try:
            from plyer import notification  # type: ignore

            notification.notify(
                title=alert.title,
                message=alert.body[:256],
                app_name="Trading System",
                timeout=8,
            )
        except Exception as exc:
            log.warning("Desktop notification failed: %s", exc)


class SoundNotifier:
    """Windows beep — different frequency by alert level."""

    _SOUNDS = {
        AlertLevel.INFO: (600, 200),
        AlertLevel.SIGNAL: (1000, 400),
        AlertLevel.WARNING: (800, 600),
        AlertLevel.CRITICAL: (1200, 800),
    }

    def send(self, alert: Alert) -> None:
        try:
            freq, dur = self._SOUNDS.get(alert.level, (800, 300))
            winsound.Beep(freq, dur)
        except Exception as exc:
            log.warning("Sound notification failed: %s", exc)


class DiscordRateLimiter:
    """Token bucket rate limiter for Discord webhook (30 messages per 30 seconds)."""

    def __init__(self, max_per_30sec: int = 30) -> None:
        self._max = max_per_30sec
        self._timestamps: List[float] = []
        self._retry_after: float = 0.0
        self._lock = threading.Lock()

    def can_send(self) -> bool:
        """Check if we can send now (purge old timestamps, check limit)."""
        now = time.time()
        with self._lock:
            # Respect 429 retry-after
            if now < self._retry_after:
                return False

            # Purge timestamps older than 30 seconds
            cutoff = now - 30.0
            self._timestamps = [ts for ts in self._timestamps if ts > cutoff]

            # Check if under limit
            if len(self._timestamps) < self._max:
                self._timestamps.append(now)
                return True
            return False

    def wait_if_needed(self, max_retries: int = 30) -> bool:
        """Block until we can send, up to max_retries seconds. Returns True if can send."""
        for _ in range(max_retries):
            if self.can_send():
                return True
            time.sleep(1.0)
        return False

    def handle_429(self, retry_after_sec: float) -> None:
        """Set retry-after timestamp when we get a 429 response."""
        with self._lock:
            self._retry_after = time.time() + retry_after_sec


class DiscordNotifier:
    """Discord webhook integration with rich embeds."""

    _COLORS = {
        AlertLevel.SIGNAL: 65280,      # Green
        AlertLevel.CRITICAL: 16711680,  # Red
        AlertLevel.WARNING: 16753920,   # Orange
        AlertLevel.INFO: 39423,         # Blue
    }

    def __init__(self, webhook_url: str, rate_limit_per_30sec: int = 30) -> None:
        self.webhook_url = webhook_url
        self._limiter = DiscordRateLimiter(rate_limit_per_30sec)

    def send(self, alert: Alert) -> None:
        if not self.webhook_url:
            return

        # For SIGNAL/CRITICAL, wait if rate-limited; for INFO/WARNING, drop if limited
        if alert.level in (AlertLevel.SIGNAL, AlertLevel.CRITICAL):
            if not self._limiter.wait_if_needed():
                log.warning("Discord rate limit exceeded, dropping alert: %s", alert.title)
                return
        else:
            if not self._limiter.can_send():
                log.debug("Discord rate limit, dropping low-priority alert: %s", alert.title)
                return

        payload = self._build_payload(alert)
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 429:
                # Rate limited by Discord
                retry_after = resp.json().get("retry_after", 5.0)
                self._limiter.handle_429(retry_after)
                log.warning("Discord 429 rate limit, retry after %.1fs", retry_after)
            elif resp.status_code == 404:
                log.error("Discord webhook not found (404) — check DISCORD_WEBHOOK_URL")
            elif resp.status_code == 401:
                log.error("Discord webhook unauthorized (401) — check DISCORD_WEBHOOK_URL")
            elif resp.status_code == 400:
                log.error("Discord bad request (400): %s", resp.text[:200])
            elif resp.status_code >= 500:
                log.warning("Discord server error (%d)", resp.status_code)
            elif resp.status_code != 204:
                log.debug("Discord send OK: %d", resp.status_code)
        except requests.Timeout:
            log.warning("Discord webhook timeout")
        except Exception as exc:
            log.warning("Discord send error: %s", exc)

    def _build_payload(self, alert: Alert) -> Dict[str, Any]:
        """Build Discord embed payload."""
        color = self._COLORS.get(alert.level, 39423)

        embed = {
            "title": alert.title,
            "description": alert.body[:2048] if alert.body else "",
            "color": color,
            "timestamp": alert.timestamp.isoformat(),
            "fields": [],
        }

        # Add fields (inline for compact display)
        if alert.strategy_id:
            embed["fields"].append({"name": "Strategy", "value": alert.strategy_id, "inline": True})
        if alert.symbol:
            embed["fields"].append({"name": "Symbol", "value": alert.symbol, "inline": True})
        if alert.direction:
            embed["fields"].append({"name": "Direction", "value": alert.direction, "inline": True})
        if alert.entry:
            embed["fields"].append({"name": "Entry", "value": f"{alert.entry:.2f}", "inline": True})
        if alert.sl:
            embed["fields"].append({"name": "Stop Loss", "value": f"{alert.sl:.2f}", "inline": True})
        if alert.tp:
            embed["fields"].append({"name": "Take Profit", "value": f"{alert.tp:.2f}", "inline": True})
        if alert.score:
            embed["fields"].append({"name": "Score", "value": f"{alert.score:.0f}%", "inline": True})

        # Confluence as non-inline field
        if alert.confluence:
            conf_str = " · ".join(alert.confluence[:10])  # Limit to 10 factors
            embed["fields"].append({"name": "Confluence", "value": conf_str, "inline": False})

        return {"embeds": [embed]}


class TelegramNotifier:
    """Optional Telegram bot integration."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, alert: Alert) -> None:
        if not self.bot_token or not self.chat_id:
            return
        text = self._format(alert)
        try:
            resp = requests.post(
                self.url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            if resp.status_code != 200:
                log.warning("Telegram send failed: %s", resp.text)
        except Exception as exc:
            log.warning("Telegram error: %s", exc)

    @staticmethod
    def _format(alert: Alert) -> str:
        icon = {"info": "[i]", "signal": "[ALERT]", "warning": "[!]", "critical": "[!!]"}.get(
            alert.level.value, "[*]"
        )
        lines = [
            f"{icon} <b>{alert.title}</b>",
            f"<i>{alert.body}</i>",
        ]
        if alert.entry:
            lines.append(
                f"Entry: {alert.entry:.2f}  SL: {alert.sl:.2f}  TP: {alert.tp:.2f}"
            )
        if alert.confluence:
            lines.append("Confluence: " + " · ".join(alert.confluence))
        return "\n".join(lines)


# ────────────────────────────────────────────────────────────────
# Alert history (SQLite)
# ────────────────────────────────────────────────────────────────
class AlertStore:
    """Persist alerts to SQLite for dashboard history panel."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS alerts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp   TEXT    NOT NULL,
        level       TEXT    NOT NULL,
        title       TEXT    NOT NULL,
        body        TEXT,
        strategy_id TEXT,
        symbol      TEXT,
        direction   TEXT,
        entry       REAL,
        sl          REAL,
        tp          REAL,
        score       REAL,
        confluence  TEXT,
        fingerprint TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);
    CREATE INDEX IF NOT EXISTS idx_alerts_strat ON alerts(strategy_id);
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

    def save(self, alert: Alert) -> None:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.execute(
                """INSERT INTO alerts
                   (timestamp,level,title,body,strategy_id,symbol,direction,
                    entry,sl,tp,score,confluence,fingerprint)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    alert.timestamp.isoformat(),
                    alert.level.value,
                    alert.title,
                    alert.body,
                    alert.strategy_id,
                    alert.symbol,
                    alert.direction,
                    alert.entry,
                    alert.sl,
                    alert.tp,
                    alert.score,
                    json.dumps(alert.confluence),
                    alert.fingerprint,
                ),
            )
            con.commit()
            con.close()

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]

    def get_by_strategy(self, strategy_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            con = sqlite3.connect(self._path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT * FROM alerts WHERE strategy_id=? ORDER BY id DESC LIMIT ?",
                (strategy_id, limit),
            ).fetchall()
            con.close()
            return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────────────
# Alert Engine
# ────────────────────────────────────────────────────────────────
class AlertEngine:
    """
    Central hub: dedup -> store -> dispatch to channels.

    Usage:
        engine = AlertEngine()
        engine.fire(alert)
    """

    COOLDOWN_SEC = 300  # same fingerprint suppressed for 5 min

    def __init__(self) -> None:
        self._recent: Dict[str, float] = {}  # fingerprint -> epoch
        self._lock = threading.Lock()

        # Persistent store
        db = getattr(CONFIG, "DB_PATH", "data/trading.db")
        Path(db).parent.mkdir(parents=True, exist_ok=True)
        self.store = AlertStore(db)

        # Channels
        self._channels: list = []
        self._channels.append(DesktopNotifier())
        self._channels.append(SoundNotifier())

        tg_token = getattr(CONFIG, "TELEGRAM_BOT_TOKEN", "")
        tg_chat = getattr(CONFIG, "TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            self._channels.append(TelegramNotifier(tg_token, tg_chat))
            log.info("Telegram notifications enabled.")

        # Discord webhook (US4)
        if CONFIG.alerts.discord and CONFIG.alerts.discord_webhook_url:
            self._channels.append(DiscordNotifier(
                CONFIG.alerts.discord_webhook_url,
                CONFIG.alerts.discord_rate_limit,
            ))
            log.info("Discord notifications enabled.")

        # In-memory buffer for dashboard (last 200 alerts)
        self._buffer: List[Alert] = []
        self._buffer_lock = threading.Lock()

    # ── Public ──────────────────────────────────────────────
    def fire(self, alert: Alert) -> bool:
        """Returns True if the alert passed dedup and was dispatched."""
        if self._is_duplicate(alert):
            log.debug("Alert suppressed (dedup): %s", alert.fingerprint)
            return False

        # Persist
        self.store.save(alert)

        # Buffer for dashboard
        with self._buffer_lock:
            self._buffer.append(alert)
            if len(self._buffer) > 200:
                self._buffer = self._buffer[-200:]

        # Dispatch to channels (non-blocking)
        for ch in self._channels:
            try:
                ch.send(alert)
            except Exception as exc:
                log.error("Channel %s failed: %s", type(ch).__name__, exc)

        log.info("[ALERT] ALERT [%s] %s — %s", alert.level.value, alert.title, alert.body)
        return True

    def fire_from_signal(self, signal, symbol: str = "") -> bool:
        """Convenience: build Alert from a strategies.base.Signal."""
        sym = symbol or signal.instrument
        alert = Alert(
            level=AlertLevel.SIGNAL,
            title=f"Signal {signal.strategy_id} — {signal.direction.value}",
            body=signal.notes or f"{sym} {signal.direction.value}",
            strategy_id=signal.strategy_id,
            symbol=sym,
            direction=signal.direction.value,
            entry=signal.entry_price,
            sl=signal.stop_loss,
            tp=signal.take_profit,
            score=signal.score,
            confluence=list(signal.confluence_factors),
        )
        return self.fire(alert)

    def get_buffer(self) -> List[Dict[str, Any]]:
        """Return recent alerts for dashboard."""
        with self._buffer_lock:
            return [a.to_dict() for a in self._buffer]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.store.get_recent(limit)

    # ── Private ─────────────────────────────────────────────
    def _is_duplicate(self, alert: Alert) -> bool:
        fp = alert.fingerprint
        now = time.time()
        with self._lock:
            # Purge old entries
            self._recent = {
                k: v for k, v in self._recent.items()
                if now - v < self.COOLDOWN_SEC
            }
            if fp in self._recent:
                return True
            self._recent[fp] = now
            return False
