"""
╔══════════════════════════════════════════════════════════════════╗
║              MT5 Connection — Thread-safe Singleton             ║
╚══════════════════════════════════════════════════════════════════╝
Wraps all MetaTrader5 calls behind a lock so the polling thread,
strategy scanner, and journal sync never collide.
"""
from __future__ import annotations

import threading
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

from config import CONFIG, SYMBOLS, TF

log = logging.getLogger("mt5")

# ══════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════
class MT5Connection:
    """
    Thread-safe singleton wrapping all MT5 operations.
    Automatically connects to the running terminal — no account
    credentials needed if the user is already logged in.
    """
    _instance: Optional["MT5Connection"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MT5Connection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._mt5_lock = threading.Lock()
        self._connected = False
        self._initialized = True

    # ── Connection ────────────────────────────────────────────────
    def connect(self) -> bool:
        with self._mt5_lock:
            if self._connected:
                return True
            kwargs: dict = {}
            if CONFIG.mt5_path:
                kwargs["path"] = CONFIG.mt5_path
            if not mt5.initialize(**kwargs):
                log.error("MT5 initialize failed: %s", mt5.last_error())
                return False
            info = mt5.account_info()
            if info is None:
                log.error("No account info — is terminal logged in?")
                mt5.shutdown()
                return False
            log.info(
                "Connected: %s | Balance: %.2f %s | Server: %s",
                info.login, info.balance, info.currency, info.server,
            )
            self._connected = True
            # Pre-select all required symbols
            for sym in SYMBOLS.all_trading() + [SYMBOLS.dxy]:
                if not mt5.symbol_select(sym, True):
                    log.warning("Symbol %s not available on this broker", sym)
            return True

    def disconnect(self) -> None:
        with self._mt5_lock:
            if self._connected:
                mt5.shutdown()
                self._connected = False
                log.info("MT5 disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Account ──────────────────────────────────────────────────
    def account_info(self) -> Optional[Dict[str, Any]]:
        with self._mt5_lock:
            info = mt5.account_info()
            if info is None:
                return None
            return {
                "login": info.login,
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "free_margin": info.margin_free,
                "profit": info.profit,
                "currency": info.currency,
                "leverage": info.leverage,
                "server": info.server,
            }

    # ── Symbol Info ──────────────────────────────────────────────
    def symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._mt5_lock:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
            return {
                "symbol": info.name,
                "bid": info.bid,
                "ask": info.ask,
                "spread": info.spread,
                "point": info.point,
                "digits": info.digits,
                "trade_contract_size": info.trade_contract_size,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
                "filling_mode": info.filling_mode,
            }

    # ── OHLCV Data ───────────────────────────────────────────────
    def get_rates(
        self,
        symbol: str,
        timeframe: int,
        count: int = 500,
        from_date: Optional[datetime] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars as a DataFrame with datetime index."""
        with self._mt5_lock:
            if from_date:
                rates = mt5.copy_rates_from(symbol, timeframe, from_date, count)
            else:
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                log.warning("No rates for %s %s", symbol, TF.name(timeframe))
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df.set_index("time", inplace=True)
            df.rename(
                columns={
                    "open": "Open", "high": "High",
                    "low": "Low",   "close": "Close",
                    "tick_volume": "Volume",
                },
                inplace=True,
            )
            # Drop real_volume & spread if present
            for col in ("real_volume", "spread"):
                if col in df.columns:
                    df.drop(columns=[col], inplace=True)
            return df

    # ── Live Tick ────────────────────────────────────────────────
    def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._mt5_lock:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            return {
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "volume": tick.volume,
                "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
            }

    # ── Open Positions ───────────────────────────────────────────
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._mt5_lock:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
            if positions is None:
                return []
            result = []
            for p in positions:
                result.append({
                    "ticket": p.ticket,
                    "symbol": p.symbol,
                    "type": "BUY" if p.type == 0 else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                    "swap": p.swap,
                    "magic": p.magic,
                    "comment": p.comment,
                    "time": datetime.fromtimestamp(p.time, tz=timezone.utc),
                })
            return result

    # ── Trade History ────────────────────────────────────────────
    def get_history_deals(
        self,
        from_date: datetime,
        to_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        with self._mt5_lock:
            if to_date is None:
                to_date = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(from_date, to_date)
            if deals is None:
                return []
            result = []
            for d in deals:
                result.append({
                    "ticket": d.ticket,
                    "order": d.order,
                    "position_id": d.position_id,
                    "symbol": d.symbol,
                    "type": d.type,
                    "volume": d.volume,
                    "price": d.price,
                    "profit": d.profit,
                    "swap": d.swap,
                    "commission": d.commission,
                    "magic": d.magic,
                    "comment": d.comment,
                    "time": datetime.fromtimestamp(d.time, tz=timezone.utc),
                })
            return result

    # ── Order Execution ──────────────────────────────────────────
    def send_order(
        self,
        symbol: str,
        order_type: str,   # "BUY" or "SELL"
        volume: float,
        price: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
        magic: int = 123456,
    ) -> Dict[str, Any]:
        """
        Send a market order. Returns dict with 'success' and details.
        Auto-detects the correct filling mode for the broker.
        """
        with self._mt5_lock:
            sym_info = mt5.symbol_info(symbol)
            if sym_info is None:
                return {"success": False, "error": f"Symbol {symbol} not found"}

            # Detect filling mode
            filling = sym_info.filling_mode
            if filling & 1:     # FOK
                fill_type = mt5.ORDER_FILLING_FOK
            elif filling & 2:   # IOC
                fill_type = mt5.ORDER_FILLING_IOC
            else:
                fill_type = mt5.ORDER_FILLING_RETURN

            action_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {"success": False, "error": "Cannot get tick"}

            entry_price = tick.ask if order_type == "BUY" else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": action_type,
                "price": entry_price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": magic,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_type,
            }

            result = mt5.order_send(request)
            if result is None:
                return {"success": False, "error": str(mt5.last_error())}
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "success": False,
                    "retcode": result.retcode,
                    "error": result.comment,
                }
            return {
                "success": True,
                "ticket": result.order,
                "price": result.price,
                "volume": result.volume,
            }

    # ── Modify Position (SL/TP) ──────────────────────────────────
    def modify_position(
        self, ticket: int, sl: float = 0.0, tp: float = 0.0
    ) -> Dict[str, Any]:
        with self._mt5_lock:
            pos = mt5.positions_get(ticket=ticket)
            if pos is None or len(pos) == 0:
                return {"success": False, "error": "Position not found"}
            p = pos[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": p.symbol,
                "sl": sl if sl else p.sl,
                "tp": tp if tp else p.tp,
            }
            result = mt5.order_send(request)
            if result is None:
                return {"success": False, "error": str(mt5.last_error())}
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"success": False, "error": result.comment}
            return {"success": True}

    # ── Close Position ───────────────────────────────────────────
    def close_position(self, ticket: int) -> Dict[str, Any]:
        with self._mt5_lock:
            pos = mt5.positions_get(ticket=ticket)
            if pos is None or len(pos) == 0:
                return {"success": False, "error": "Position not found"}
            p = pos[0]
            close_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(p.symbol)
            if tick is None:
                return {"success": False, "error": "Cannot get tick"}
            close_price = tick.bid if p.type == 0 else tick.ask

            sym_info = mt5.symbol_info(p.symbol)
            filling = sym_info.filling_mode
            if filling & 1:
                fill_type = mt5.ORDER_FILLING_FOK
            elif filling & 2:
                fill_type = mt5.ORDER_FILLING_IOC
            else:
                fill_type = mt5.ORDER_FILLING_RETURN

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": close_type,
                "price": close_price,
                "position": ticket,
                "deviation": 20,
                "magic": p.magic,
                "comment": "close",
                "type_filling": fill_type,
            }
            result = mt5.order_send(request)
            if result is None:
                return {"success": False, "error": str(mt5.last_error())}
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"success": False, "error": result.comment}
            return {"success": True, "price": result.price}


# ── Module-level accessor ────────────────────────────────────────
def get_mt5() -> MT5Connection:
    return MT5Connection()
