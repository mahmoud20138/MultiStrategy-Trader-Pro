"""
╔══════════════════════════════════════════════════════════════════╗
║        Risk Manager — Position Sizing & Loss Limits             ║
╚══════════════════════════════════════════════════════════════════╝
Enforces:
  • Per-trade risk %   • Daily / Weekly / Monthly loss caps
  • Consecutive-loss pause   • Correlation blocks
  • Position sizing formula: Lots = (Balance × Risk%) / (SL_points × Point_value)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from config import CONFIG, SYMBOLS, CORRELATION_BLOCKS
from core.mt5_connection import get_mt5

log = logging.getLogger("risk")


@dataclass
class RiskState:
    """Tracks running loss/win counters during the session."""
    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    monthly_loss: float = 0.0
    consecutive_losses: int = 0
    last_loss_time: Optional[datetime] = None
    paused_until: Optional[datetime] = None
    loss_day_yesterday: bool = False
    trades_today: int = 0

    def reset_daily(self) -> None:
        self.loss_day_yesterday = self.daily_loss < 0
        self.daily_loss = 0.0
        self.trades_today = 0
        self.consecutive_losses = 0

    def reset_weekly(self) -> None:
        self.weekly_loss = 0.0

    def reset_monthly(self) -> None:
        self.monthly_loss = 0.0


class RiskManager:
    """Central risk gatekeeper — call check_entry() before every trade."""

    def __init__(self) -> None:
        self.state = RiskState()
        self.cfg = CONFIG.risk

    # ── Position Sizing ──────────────────────────────────────────
    def calculate_lot_size(
        self,
        symbol: str,
        sl_points: float,
        style: str = "day",
    ) -> float:
        """
        Lots = (Balance × Risk%) / (SL_distance_in_price × Contract_size / Point)
        Adjusts risk % based on style and consecutive-loss state.
        """
        mt5 = get_mt5()
        acct = mt5.account_info()
        if acct is None:
            log.error("Cannot size position — no account info")
            return 0.0

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            log.error("Cannot size position — symbol %s not found", symbol)
            return 0.0

        balance = acct["balance"]

        # Adaptive risk %
        risk_pct = self.cfg.max_risk_pct / 100.0
        if style == "scalp":
            risk_pct = min(risk_pct, 0.01)        # cap at 1%
        elif style == "swing":
            risk_pct = min(risk_pct * 1.5, 0.02)  # up to 2%

        # Reduce after losing day
        if self.state.loss_day_yesterday:
            risk_pct *= self.cfg.reduce_risk_after_loss_day
            log.info("Risk reduced to %.2f%% after losing day", risk_pct * 100)

        risk_amount = balance * risk_pct
        point_value = sym_info["trade_contract_size"] * sym_info["point"]
        if point_value == 0 or sl_points == 0:
            return 0.0

        lots = risk_amount / (sl_points * point_value)

        # Snap to volume step
        step = sym_info["volume_step"]
        lots = max(sym_info["volume_min"], round(lots / step) * step)
        lots = min(lots, sym_info["volume_max"])

        return round(lots, 2)

    # ── Entry Gate ───────────────────────────────────────────────
    def check_entry(
        self,
        symbol: str,
        direction: str,
        style: str,
    ) -> Tuple[bool, str]:
        """
        Returns (allowed, reason).
        Checks daily/weekly/monthly caps, pause, correlation, concurrency.
        """
        now = datetime.now(timezone.utc)
        acct = get_mt5().account_info()
        if acct is None:
            return False, "No account info"

        balance = acct["balance"]

        # ── Pause check ──
        if self.state.paused_until and now < self.state.paused_until:
            remaining = (self.state.paused_until - now).seconds // 60
            return False, f"Paused ({remaining}m remaining after {self.cfg.consecutive_loss_pause} consecutive losses)"

        # ── Daily loss cap ──
        daily_cap = balance * self.cfg.max_daily_loss_pct / 100
        if abs(self.state.daily_loss) >= daily_cap:
            return False, f"Daily loss cap hit ({self.state.daily_loss:.2f} >= {daily_cap:.2f})"

        # ── Weekly loss cap ──
        weekly_cap = balance * self.cfg.max_weekly_loss_pct / 100
        if abs(self.state.weekly_loss) >= weekly_cap:
            return False, f"Weekly loss cap hit"

        # ── Monthly drawdown cap ──
        monthly_cap = balance * self.cfg.max_monthly_dd_pct / 100
        if abs(self.state.monthly_loss) >= monthly_cap:
            return False, f"Monthly drawdown cap hit"

        # ── Concurrent positions ──
        open_positions = get_mt5().get_positions()
        if len(open_positions) >= self.cfg.max_concurrent:
            return False, f"Max concurrent trades ({self.cfg.max_concurrent}) reached"

        # ── Correlation block ──
        instrument_name = SYMBOLS.name_for(symbol).lower()
        for pos in open_positions:
            pos_instrument = SYMBOLS.name_for(pos["symbol"]).lower()
            for block_set, corr in CORRELATION_BLOCKS:
                if {instrument_name, pos_instrument} == block_set:
                    if pos["type"].upper() == direction.upper():
                        return False, (
                            f"Correlation block: {instrument_name} & {pos_instrument} "
                            f"(ρ={corr}) — same direction forbidden"
                        )

        return True, "OK"

    # ── Record Trade Result ──────────────────────────────────────
    def record_result(self, pnl: float) -> None:
        """Call after a trade closes to update running counters."""
        self.state.daily_loss += pnl
        self.state.weekly_loss += pnl
        self.state.monthly_loss += pnl
        self.state.trades_today += 1

        if pnl < 0:
            self.state.consecutive_losses += 1
            self.state.last_loss_time = datetime.now(timezone.utc)
            if self.state.consecutive_losses >= self.cfg.consecutive_loss_pause:
                self.state.paused_until = (
                    datetime.now(timezone.utc) + timedelta(minutes=self.cfg.pause_minutes)
                )
                log.warning(
                    "PAUSED for %d minutes after %d consecutive losses",
                    self.cfg.pause_minutes, self.state.consecutive_losses,
                )
        else:
            self.state.consecutive_losses = 0

    # ── Pre-trade Checklist Score ────────────────────────────────
    def pre_trade_checklist(
        self,
        trend_aligned: bool,
        key_level: bool,
        rr_ok: bool,
        session_ok: bool,
        no_news: bool,
        volume_ok: bool,
        signal_clear: bool,
        risk_sized: bool,
        plan_written: bool,
        emotions_ok: bool,
    ) -> Tuple[int, int, bool]:
        """
        10-point checklist from the strategy guide.
        Returns (score, total, passed).
        Must score 8/10 to pass.
        """
        checks = [
            trend_aligned, key_level, rr_ok, session_ok, no_news,
            volume_ok, signal_clear, risk_sized, plan_written, emotions_ok,
        ]
        score = sum(checks)
        return score, 10, score >= 8


# ── Singleton ────────────────────────────────────────────────────
_risk_mgr: Optional[RiskManager] = None

def get_risk_manager() -> RiskManager:
    global _risk_mgr
    if _risk_mgr is None:
        _risk_mgr = RiskManager()
    return _risk_mgr
