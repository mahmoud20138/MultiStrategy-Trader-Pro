"""
╔══════════════════════════════════════════════════════════════════╗
║           Data Feed — Multi-TF Cache & Polling Engine           ║
╚══════════════════════════════════════════════════════════════════╝
Runs in a background thread, polling MT5 for candle updates
across all instruments and timeframes needed by the 19 strategies.
Broadcasts new-bar events so strategies react instantly.
"""

from __future__ import annotations

import threading
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Tuple

import pandas as pd

from config import CONFIG, SYMBOLS, TF, STRATEGY_REGISTRY
from core.mt5_connection import get_mt5

log = logging.getLogger("feed")

# ══════════════════════════════════════════════════════════════════
# CACHE KEY = (symbol, timeframe)
# ══════════════════════════════════════════════════════════════════
CacheKey = Tuple[str, int]


class DataFeed:
    """
    Central data cache. Polls MT5 at configured interval,
    stores DataFrames, and fires callbacks on new bars.
    """

    def __init__(self) -> None:
        self._cache: Dict[CacheKey, pd.DataFrame] = {}
        self._bar_counts: Dict[CacheKey, int] = {}
        self._callbacks: List[Callable[[str, int, pd.DataFrame], None]] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Public API ───────────────────────────────────────────────
    def get(
        self, symbol: str, timeframe: int, count: int = 500
    ) -> Optional[pd.DataFrame]:
        """Return cached DataFrame (or fetch fresh if not cached)."""
        key: CacheKey = (symbol, timeframe)
        with self._lock:
            if key in self._cache:
                return self._cache[key].copy()
        # Not cached — fetch now
        df = get_mt5().get_rates(symbol, timeframe, count)
        if df is not None:
            with self._lock:
                self._cache[key] = df
                self._bar_counts[key] = len(df)
        return df

    def get_latest(
        self, symbol: str, timeframe: int, bars: int = 200
    ) -> Optional[pd.DataFrame]:
        """Alias for dashboard — returns cached data trimmed to *bars*."""
        df = self.get(symbol, timeframe)
        if df is not None and len(df) > bars:
            return df.tail(bars).reset_index(drop=True)
        return df

    def on_new_bar(self, callback: Callable[[str, int, pd.DataFrame], None]) -> None:
        """Register callback(symbol, timeframe, df) fired on each new bar."""
        self._callbacks.append(callback)

    def get_multi_tf(
        self, symbol: str, timeframes: List[int]
    ) -> Dict[int, pd.DataFrame]:
        """Fetch multiple timeframes for one symbol."""
        result = {}
        for tf in timeframes:
            df = self.get(symbol, tf)
            if df is not None:
                result[tf] = df
        return result

    # ── Polling Loop ─────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="DataFeed"
        )
        self._thread.start()
        log.info("DataFeed polling started (interval=%ds)", CONFIG.poll_interval)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("DataFeed stopped")

    def _poll_loop(self) -> None:
        """Build the set of (symbol, tf) pairs from all enabled strategies, then poll."""
        pairs = self._build_pairs()
        log.info("Polling %d symbol-timeframe pairs", len(pairs))
        while self._running:
            for symbol, tf in pairs:
                try:
                    df = get_mt5().get_rates(symbol, tf, 500)
                    if df is None:
                        continue
                    key: CacheKey = (symbol, tf)
                    with self._lock:
                        old_count = self._bar_counts.get(key, 0)
                        self._cache[key] = df
                        self._bar_counts[key] = len(df)
                    # Fire callbacks on new bar
                    if len(df) > old_count and old_count > 0:
                        for cb in self._callbacks:
                            try:
                                cb(symbol, tf, df)
                            except Exception as e:
                                log.error("Callback error: %s", e)
                except Exception as e:
                    log.error("Poll error %s/%s: %s", symbol, TF.name(tf), e)
            time.sleep(CONFIG.poll_interval)

    def _build_pairs(self) -> List[CacheKey]:
        """Collect all unique (symbol, tf) from active strategies."""
        sym_map = {
            "gold": SYMBOLS.gold,
            "nas100": SYMBOLS.nas100,
            "us500": SYMBOLS.us500,
            "us30": SYMBOLS.us30,
            "btc": SYMBOLS.btc,
            "eth": SYMBOLS.eth,
        }

        # Build list of valid symbols to poll
        valid_symbols = {}

        # Always add standard instruments (gold, nas100, us500, us30)
        for inst in ["gold", "nas100", "us500", "us30"]:
            sym = sym_map.get(inst)
            if sym:
                valid_symbols[inst] = sym

        # Add crypto instruments only if enabled (US6)
        if SYMBOLS.enable_crypto:
            for inst in ["btc", "eth"]:
                sym = sym_map.get(inst)
                if sym:
                    # Check if symbol exists at broker
                    try:
                        mt5 = get_mt5()
                        if mt5 and hasattr(mt5, "_mt5"):
                            info = mt5._mt5.symbol_info(sym)
                            if info is None:
                                log.warning(
                                    "Crypto symbol %s not found at broker — skipping",
                                    sym,
                                )
                                continue
                    except Exception:
                        pass  # If check fails, include anyway and let polling handle it
                    valid_symbols[inst] = sym

        pairs = set()
        for meta in STRATEGY_REGISTRY.values():
            if not meta.enabled:
                continue
            # Skip crypto strategies if crypto disabled
            if meta.instrument in ("btc", "eth") and not SYMBOLS.enable_crypto:
                continue
            symbol = valid_symbols.get(meta.instrument)
            if symbol:
                for tf in meta.timeframes:
                    pairs.add((symbol, tf))

        # Always add DXY for strategy D
        pairs.add((SYMBOLS.dxy, TF.M15))
        pairs.add((SYMBOLS.dxy, TF.H1))

        # Add higher TFs for context (H1, H4, D1 for all valid instruments)
        for sym in valid_symbols.values():
            for tf in [TF.H1, TF.H4, TF.D1]:
                pairs.add((sym, tf))

        return list(pairs)


# ── Module-level singleton ───────────────────────────────────────
_feed: Optional[DataFeed] = None


def get_feed() -> DataFeed:
    global _feed
    if _feed is None:
        _feed = DataFeed()
    return _feed
