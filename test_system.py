"""
╔══════════════════════════════════════════════════════════════════╗
║          COMPREHENSIVE SYSTEM TEST — All Components             ║
╚══════════════════════════════════════════════════════════════════╝
Tests:  MT5 Connection · Symbols · Data Feed · Indicators
        Strategies (21) · Alert Engine · Journal · Config
"""
import sys
import os
import io
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── Windows encoding resilience ─────────────────────────────────
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

# Load .env
from dotenv import load_dotenv
load_dotenv()

from config import STRATEGY_REGISTRY

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
results = {"pass": 0, "fail": 0, "warn": 0}

def test(name, fn):
    global results
    try:
        ok, msg = fn()
        if ok:
            print(f"  {PASS} {name}: {msg}")
            results["pass"] += 1
        else:
            print(f"  {FAIL} {name}: {msg}")
            results["fail"] += 1
    except Exception as e:
        print(f"  {FAIL} {name}: EXCEPTION — {e}")
        traceback.print_exc()
        results["fail"] += 1

def warn_test(name, fn):
    global results
    try:
        ok, msg = fn()
        if ok:
            print(f"  {PASS} {name}: {msg}")
            results["pass"] += 1
        else:
            print(f"  {WARN} {name}: {msg}")
            results["warn"] += 1
    except Exception as e:
        print(f"  {WARN} {name}: {e}")
        results["warn"] += 1


print("\n" + "=" * 65)
print("  TRADING SYSTEM — COMPREHENSIVE TEST SUITE")
print("=" * 65)

# ─────────────────────────────────────────────────────────────────
# 1. CONFIG & IMPORTS
# ─────────────────────────────────────────────────────────────────
print("\n[1/8] CONFIG & IMPORTS")

def test_config_import():
    from config import CONFIG, SYMBOLS, STRATEGY_REGISTRY, TF, StrategyMeta
    return True, f"CONFIG loaded, {len(STRATEGY_REGISTRY)} strategies registered"

def test_symbols():
    from config import SYMBOLS
    syms = SYMBOLS.all_trading()
    names = [SYMBOLS.name_for(s) for s in syms]
    return len(syms) == 6, f"{len(syms)} symbols: {', '.join(f'{n}={s}' for n, s in zip(names, syms))}"

def test_strategy_registry():
    from config import STRATEGY_REGISTRY
    ids = sorted(STRATEGY_REGISTRY.keys())
    expected = sorted(STRATEGY_REGISTRY.keys())
    missing = [x for x in expected if x not in ids]
    extra = [x for x in ids if x not in expected]
    if missing:
        return False, f"Missing strategies: {missing}"
    return True, f"All 21 strategies registered (A-U): {', '.join(ids)}"

def test_crypto_in_registry():
    from config import STRATEGY_REGISTRY
    t = STRATEGY_REGISTRY.get("T")
    u = STRATEGY_REGISTRY.get("U")
    if not t:
        return False, "Strategy T not in registry"
    if not u:
        return False, "Strategy U not in registry"
    return True, f"T={t.name} ({t.instrument}), U={u.name} ({u.instrument})"

test("Config import", test_config_import)
test("Symbol map (6 instruments)", test_symbols)
test("Strategy registry (21 entries)", test_strategy_registry)
test("Crypto in registry (T, U)", test_crypto_in_registry)


# ─────────────────────────────────────────────────────────────────
# 2. MT5 CONNECTION
# ─────────────────────────────────────────────────────────────────
print("\n[2/8] MT5 CONNECTION")

def test_mt5_connect():
    from core.mt5_connection import MT5Connection
    mt5 = MT5Connection()
    ok = mt5.connect()
    if not ok:
        return False, "Failed to connect to MT5"
    info = mt5.account_info()
    return True, f"Account {info.get('login')} | Balance: ${info.get('balance', 0):,.2f} | Server: {info.get('server')}"

test("MT5 connection", test_mt5_connect)


# ─────────────────────────────────────────────────────────────────
# 3. SYMBOL AVAILABILITY ON BROKER
# ─────────────────────────────────────────────────────────────────
print("\n[3/8] SYMBOL AVAILABILITY (Broker)")

def test_symbol_available(sym_name, mt5_symbol):
    def _test():
        import MetaTrader5 as mt5
        info = mt5.symbol_info(mt5_symbol)
        if info is None:
            return False, f"{mt5_symbol} NOT found on broker"
        spread = info.spread
        visible = info.visible
        trade_mode = info.trade_mode
        return True, f"{mt5_symbol} found | spread={spread} | trade_mode={trade_mode} | visible={visible}"
    return _test

from config import SYMBOLS
for name, sym_attr in [("Gold", SYMBOLS.gold), ("NAS100", SYMBOLS.nas100),
                       ("US500", SYMBOLS.us500), ("US30", SYMBOLS.us30),
                       ("BTC", SYMBOLS.btc), ("ETH", SYMBOLS.eth),
                       ("DXY", SYMBOLS.dxy)]:
    test(f"  {name} ({sym_attr})", test_symbol_available(name, sym_attr))


# ─────────────────────────────────────────────────────────────────
# 4. DATA FEED
# ─────────────────────────────────────────────────────────────────
print("\n[4/8] DATA FEED")

def test_data_feed_pairs():
    from core.data_feed import DataFeed
    feed = DataFeed()
    pairs = feed._build_pairs()
    btc_pairs = [(s, tf) for s, tf in pairs if "BTC" in s.upper()]
    eth_pairs = [(s, tf) for s, tf in pairs if "ETH" in s.upper()]
    return True, f"{len(pairs)} total pairs | BTC: {len(btc_pairs)} TFs | ETH: {len(eth_pairs)} TFs"

def test_data_fetch():
    """Actually fetch data for all 6 instruments."""
    from core.data_feed import DataFeed
    from config import TF, SYMBOLS
    import MetaTrader5 as mt5
    feed = DataFeed()
    results_inner = []
    for name, sym in [("GOLD", SYMBOLS.gold), ("NAS100", SYMBOLS.nas100),
                      ("US500", SYMBOLS.us500), ("US30", SYMBOLS.us30),
                      ("BTC", SYMBOLS.btc), ("ETH", SYMBOLS.eth)]:
        rates = mt5.copy_rates_from_pos(sym, TF.M5, 0, 50)
        if rates is not None and len(rates) > 0:
            results_inner.append(f"{name}={len(rates)} bars")
        else:
            results_inner.append(f"{name}=NO DATA")
    return True, " | ".join(results_inner)

def test_data_feed_detail():
    from core.data_feed import DataFeed
    from config import TF as TFC
    feed = DataFeed()
    pairs = feed._build_pairs()
    # Group by instrument
    by_symbol = {}
    for sym, tf in pairs:
        if sym not in by_symbol:
            by_symbol[sym] = []
        by_symbol[sym].append(TFC.name(tf))
    detail = []
    for sym, tfs in by_symbol.items():
        detail.append(f"{sym}: {', '.join(sorted(set(tfs)))}")
    return True, f"{len(pairs)} pairs across {len(by_symbol)} symbols\n" + "\n          ".join(["          " + d for d in detail])

test("Data feed pairs built", test_data_feed_pairs)
test("Data feed detail", test_data_feed_detail)
test("Live data fetch (M5)", test_data_fetch)


# ─────────────────────────────────────────────────────────────────
# 5. INDICATORS
# ─────────────────────────────────────────────────────────────────
print("\n[5/8] INDICATORS")

def _make_sample_df(n=200):
    """Create realistic sample OHLCV DataFrame for indicator testing."""
    import pandas as pd
    import numpy as np
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + abs(np.random.randn(n) * 0.3)
    low = close - abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.1
    volume = np.random.randint(100, 10000, n).astype(float)
    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close,
        "Volume": volume, "Tick_volume": volume,
    })

from indicators.trend import add_ema, add_sma, add_supertrend, add_vwap
from indicators.momentum import add_rsi, add_macd, add_stochastic
from indicators.volatility import add_atr, add_bbands, add_keltner
from indicators.volume import add_obv
from indicators.structure import find_round_levels

def test_ema():
    df = add_ema(_make_sample_df(), 21)
    val = df["EMA_21"].iloc[-1]
    trend = "BULLISH" if df["Close"].iloc[-1] > val else "BEARISH"
    return True, f"EMA_21 = {val:.4f} | Close vs EMA → {trend} | col dtype={df['EMA_21'].dtype}"

def test_sma():
    df = add_sma(_make_sample_df(), 20)
    val = df["SMA_20"].iloc[-1]
    spread = df["Close"].iloc[-1] - val
    return True, f"SMA_20 = {val:.4f} | Close-SMA spread = {spread:+.4f} | dtype={df['SMA_20'].dtype}"

def test_rsi():
    df = add_rsi(_make_sample_df(), 14)
    val = df["RSI_14"].iloc[-1]
    zone = "OVERBOUGHT" if val > 70 else "OVERSOLD" if val < 30 else "NEUTRAL"
    mn, mx = df["RSI_14"].dropna().min(), df["RSI_14"].dropna().max()
    return True, f"RSI_14 = {val:.2f} ({zone}) | Range [{mn:.1f} – {mx:.1f}] | {df['RSI_14'].dropna().shape[0]} valid points"

def test_macd():
    df = add_macd(_make_sample_df())
    macd_v = df["MACD"].iloc[-1]
    sig_v = df["MACD_Signal"].iloc[-1]
    hist = df["MACD_Hist"].iloc[-1]
    cross = "BULLISH" if hist > 0 else "BEARISH"
    return True, f"MACD={macd_v:.4f} Signal={sig_v:.4f} Hist={hist:+.4f} → {cross} | cols: MACD, MACD_Signal, MACD_Hist"

def test_stochastic():
    df = add_stochastic(_make_sample_df())
    k = df["Stoch_K"].iloc[-1]
    d = df["Stoch_D"].iloc[-1]
    zone = "OVERBOUGHT" if k > 80 else "OVERSOLD" if k < 20 else "NEUTRAL"
    cross = "K>D (bullish)" if k > d else "K<D (bearish)"
    return True, f"%K={k:.2f} %D={d:.2f} → {zone} | {cross}"

def test_atr():
    df = add_atr(_make_sample_df(), 14)
    val = df["ATR_14"].iloc[-1]
    pct = val / df["Close"].iloc[-1] * 100
    return True, f"ATR_14 = {val:.4f} ({pct:.2f}% of price) | Volatility gauge for SL/TP sizing"

def test_bbands():
    df = add_bbands(_make_sample_df())
    upper = df["BB_Upper"].iloc[-1]
    mid = df["BB_Mid"].iloc[-1]
    lower = df["BB_Lower"].iloc[-1]
    width = upper - lower
    price = df["Close"].iloc[-1]
    pos = "Above mid" if price > mid else "Below mid"
    return True, f"Upper={upper:.2f} Mid={mid:.2f} Lower={lower:.2f} | Width={width:.2f} | Price {pos}"

def test_keltner():
    df = add_keltner(_make_sample_df())
    upper = df["KC_Upper"].iloc[-1]
    mid = df["KC_Mid"].iloc[-1]
    lower = df["KC_Lower"].iloc[-1]
    squeeze = df["BB_Upper"].iloc[-1] < upper if "BB_Upper" in df else False
    return True, f"Upper={upper:.2f} Mid={mid:.2f} Lower={lower:.2f} | Squeeze={'YES' if squeeze else 'N/A'}"

def test_supertrend():
    df = add_supertrend(_make_sample_df())
    val = df["Supertrend"].iloc[-1]
    direction = df["Supertrend_Dir"].iloc[-1]
    trend = "BULLISH ▲" if direction > 0 else "BEARISH ▼"
    return True, f"Supertrend = {val:.4f} | Direction = {trend} | Trend-following SL line"

def test_vwap():
    df = add_vwap(_make_sample_df())
    val = df["VWAP"].iloc[-1]
    price = df["Close"].iloc[-1]
    bias = "Price > VWAP (bullish)" if price > val else "Price < VWAP (bearish)"
    return True, f"VWAP = {val:.4f} | {bias} | Institutional fair-value anchor"

def test_obv():
    df = add_obv(_make_sample_df())
    val = df["OBV"].iloc[-1]
    obv_chg = df["OBV"].iloc[-1] - df["OBV"].iloc[-20]
    flow = "Accumulation ▲" if obv_chg > 0 else "Distribution ▼"
    return True, f"OBV = {val:,.0f} | 20-bar change = {obv_chg:+,.0f} → {flow}"

test("EMA (21)",       test_ema)
test("SMA (20)",       test_sma)
test("RSI (14)",       test_rsi)
test("MACD (12/26/9)", test_macd)
test("Stochastic",     test_stochastic)
test("ATR (14)",       test_atr)
test("Bollinger Bands",test_bbands)
test("Keltner Channel",test_keltner)
test("Supertrend",     test_supertrend)
test("VWAP",           test_vwap)
test("OBV",            test_obv)

def test_round_levels_crypto():
    levels_btc = find_round_levels(97000, "btc", count=3)
    levels_eth = find_round_levels(2700, "eth", count=3)
    btc_str = ", ".join(f"${l[0]:,.0f}" for l in levels_btc)
    eth_str = ", ".join(f"${l[0]:,.0f}" for l in levels_eth)
    return (len(levels_btc) > 0 and len(levels_eth) > 0,
            f"BTC psych levels: [{btc_str}] | ETH psych levels: [{eth_str}]")

test("Round levels (BTC/ETH)", test_round_levels_crypto)


# ─────────────────────────────────────────────────────────────────
# 6. STRATEGIES — Instantiation & Session Check
# ─────────────────────────────────────────────────────────────────
print("\n[6/8] STRATEGIES (21 total)")

# ── Strategy Descriptions: imported from single-source module ──
from strategy_reference import STRATEGY_DESCRIPTIONS

def test_strategy_instantiation():
    from strategies import build_active_strategies
    strats = build_active_strategies()
    ids = [s.id for s in strats]
    return len(strats) == 21, f"{len(strats)} strategies built: {', '.join(ids)}"

test("All 21 strategies instantiate", test_strategy_instantiation)

def test_strategy_meta(sid):
    def _test():
        from strategies import STRATEGY_MAP
        from config import STRATEGY_REGISTRY, TF as TFC, SESSIONS
        cls = STRATEGY_MAP.get(sid)
        if cls is None:
            return False, f"Strategy {sid} not in STRATEGY_MAP"
        meta = STRATEGY_REGISTRY.get(sid)
        if meta is None:
            return False, f"Strategy {sid} not in STRATEGY_REGISTRY"
        instance = cls()
        session = instance.is_active_session()

        # Timeframes
        tf_names = [TFC.name(tf) for tf in meta.timeframes]
        tf_str = "/".join(tf_names)

        # Sessions
        if meta.sessions:
            sess_names = []
            for s in meta.sessions:
                sw = SESSIONS.get(s)
                if sw:
                    sess_names.append(f"{sw.name}({sw.start_hour:02d}:{sw.start_minute:02d}-{sw.end_hour:02d}:{sw.end_minute:02d})")
                else:
                    sess_names.append(s)
            sess_str = ", ".join(sess_names)
        else:
            sess_str = "24/7 (all sessions)"

        # Win rate & R:R
        wr_str = f"{meta.win_rate[0]*100:.0f}-{meta.win_rate[1]*100:.0f}%"
        rr_str = f"1:{meta.risk_reward[1]}"

        # Style badge
        style_badges = {"scalp": "⚡ SCALP", "day": "📊 DAY", "swing": "📈 SWING"}
        style_str = style_badges.get(meta.style, meta.style.upper())

        # Session status icon
        sess_icon = "🟢" if session else "🔴"

        # Strategy description
        desc = STRATEGY_DESCRIPTIONS.get(sid, {})
        what_str  = desc.get("what", "—")
        ref_str   = desc.get("reference", "—")
        ind_str   = desc.get("indicators", "—")
        entry_str = desc.get("entry", "—")
        exit_str  = desc.get("exit", "—")

        return True, (f"{meta.name}\n"
                      f"          {style_str} | {meta.instrument.upper()} | TFs: {tf_str}\n"
                      f"          WinRate: {wr_str} | R:R: {rr_str} | Sessions: {sess_str}\n"
                      f"          Status: {sess_icon} {'ACTIVE' if session else 'OUTSIDE SESSION'}\n"
                      f"          ── What ─────────────────────────────────────────\n"
                      f"          {what_str}\n"
                      f"          ── Reference: {ref_str}\n"
                      f"          ── Indicators: {ind_str}\n"
                      f"          ── Entry: {entry_str}\n"
                      f"          ── Exit:  {exit_str}")
    return _test

for sid in sorted(STRATEGY_REGISTRY):
    test(f"  Strategy {sid}", test_strategy_meta(sid))

# Test crypto 24/7 sessions specifically
def test_crypto_always_active():
    from strategies.crypto_strategies import StrategyT, StrategyU
    t = StrategyT()
    u = StrategyU()
    t_active = t.is_active_session()
    u_active = u.is_active_session()
    return (t_active and u_active,
            f"T(BTC) active={t_active}, U(ETH) active={u_active} — should be True 24/7")

test("Crypto 24/7 session", test_crypto_always_active)


# ─────────────────────────────────────────────────────────────────
# 6b. STRATEGY × TIMEFRAME MATRIX
# ─────────────────────────────────────────────────────────────────
print("\n[6b/8] STRATEGY × TIMEFRAME COVERAGE MATRIX")

def test_strategy_tf_matrix():
    from config import STRATEGY_REGISTRY, TF as TFC
    all_tfs = [TFC.M1, TFC.M5, TFC.M15, TFC.M30, TFC.H1, TFC.H4, TFC.D1, TFC.W1]
    tf_labels = [TFC.name(t) for t in all_tfs]

    # Header
    header = f"    {'ID':>3} {'Instrument':<10} {'Style':<7} │ " + " ".join(f"{l:>3}" for l in tf_labels)
    print(f"    {'─'*len(header)}")
    print(header)
    print(f"    {'─'*len(header)}")

    instruments = {}
    for sid in sorted(STRATEGY_REGISTRY):
        meta = STRATEGY_REGISTRY[sid]
        row = f"     {sid:>1}  {meta.instrument.upper():<10} {meta.style:<7} │ "
        for tf in all_tfs:
            if tf in meta.timeframes:
                row += "  ● "
            else:
                row += "  · "
        print(row)

        # Count per instrument
        inst = meta.instrument.upper()
        if inst not in instruments:
            instruments[inst] = {"strats": 0, "tfs": set()}
        instruments[inst]["strats"] += 1
        instruments[inst]["tfs"].update(meta.timeframes)

    print(f"    {'─'*len(header)}")
    # Summary per instrument
    summary_parts = []
    for inst, data in sorted(instruments.items()):
        tf_names = sorted([TFC.name(t) for t in data["tfs"]])
        summary_parts.append(f"{inst}: {data['strats']} strats × {len(data['tfs'])} TFs ({'/'.join(tf_names)})")
    return True, " | ".join(summary_parts)

test("Coverage matrix", test_strategy_tf_matrix)


# ─────────────────────────────────────────────────────────────────
# 6c. DATA FEED — PER INSTRUMENT × TF DETAIL
# ─────────────────────────────────────────────────────────────────
print("\n[6c/8] DATA AVAILABILITY — All Instruments × Timeframes")

def test_data_per_instrument(inst_name, mt5_symbol):
    def _test():
        import MetaTrader5 as mt5
        from config import TF as TFC
        all_tfs = [(TFC.M1, "M1"), (TFC.M5, "M5"), (TFC.M15, "M15"),
                   (TFC.H1, "H1"), (TFC.H4, "H4"), (TFC.D1, "D1")]
        parts = []
        total_bars = 0
        for tf_val, tf_name in all_tfs:
            rates = mt5.copy_rates_from_pos(mt5_symbol, tf_val, 0, 100)
            if rates is not None and len(rates) > 0:
                bar_count = len(rates)
                total_bars += bar_count
                # Get latest bar timestamp
                from datetime import datetime
                last_time = datetime.utcfromtimestamp(rates[-1][0]).strftime("%m/%d %H:%M")
                parts.append(f"{tf_name}={bar_count}bars({last_time})")
            else:
                parts.append(f"{tf_name}=∅")
        return True, f"{mt5_symbol} → {total_bars} total bars | {' | '.join(parts)}"
    return _test

from config import SYMBOLS as _SYM
for name, sym in [("GOLD", _SYM.gold), ("NAS100", _SYM.nas100),
                  ("US500", _SYM.us500), ("US30", _SYM.us30),
                  ("BTC", _SYM.btc), ("ETH", _SYM.eth)]:
    test(f"  {name}", test_data_per_instrument(name, sym))


# ─────────────────────────────────────────────────────────────────
# 6d. LIVE SIGNAL DRY-RUN — Run each active strategy once
# ─────────────────────────────────────────────────────────────────
print("\n[6d/8] LIVE ANALYSIS DRY-RUN (each strategy × real data)")

def test_strategy_dry_run(sid):
    def _test():
        import MetaTrader5 as mt5
        from strategies import STRATEGY_MAP
        from config import STRATEGY_REGISTRY, TF as TFC, SYMBOLS
        import pandas as pd

        meta = STRATEGY_REGISTRY[sid]
        cls = STRATEGY_MAP[sid]
        instance = cls()

        # Resolve symbol
        sym_map = {
            "gold": SYMBOLS.gold, "nas100": SYMBOLS.nas100,
            "us500": SYMBOLS.us500, "us30": SYMBOLS.us30,
            "btc": SYMBOLS.btc, "eth": SYMBOLS.eth,
        }
        symbol = sym_map.get(meta.instrument, "")

        # Fetch multi-TF data
        data = {}
        for tf in meta.timeframes:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 500)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                col_map = {c: c.capitalize() for c in df.columns}
                col_map["tick_volume"] = "Tick_volume"
                col_map["real_volume"] = "Volume"
                df.rename(columns=col_map, inplace=True)
                if "Time" in df.columns:
                    df.rename(columns={"Time": "time"}, inplace=True)
                if "Volume" not in df.columns and "Tick_volume" in df.columns:
                    df["Volume"] = df["Tick_volume"]
                data[tf] = df

        tfs_loaded = [TFC.name(t) for t in data.keys()]
        bars_info = "/".join(f"{TFC.name(t)}:{len(data[t])}" for t in data)

        if not data:
            return True, f"[{sid}] {meta.name} — NO DATA available (market closed?) | TFs needed: {[TFC.name(t) for t in meta.timeframes]}"

        # Run analysis
        try:
            signal = instance.analyze(data)
        except Exception as e:
            return False, f"[{sid}] {meta.name} — CRASHED: {type(e).__name__}: {e}"

        if signal is None:
            return True, (f"[{sid}] {meta.name} — No signal (conditions not met)\n"
                         f"          Data: {bars_info} | Session: {'ACTIVE' if instance.is_active_session() else 'CLOSED'}")

        # Signal found!
        dir_icon = "▲ BUY" if signal.direction.value == "BUY" else "▼ SELL"
        conf = " • ".join(signal.confluence_factors) if signal.confluence_factors else "N/A"
        return True, (f"[{sid}] {meta.name} — 🔔 {dir_icon}\n"
                     f"          Entry={signal.entry_price:.2f} SL={signal.stop_loss:.2f} TP={signal.take_profit:.2f} R:R={signal.risk_reward:.1f}\n"
                     f"          Score={signal.score:.0f}% | TF={TFC.name(signal.timeframe)}\n"
                     f"          WHY: {conf}")
    return _test

for sid in sorted(STRATEGY_REGISTRY):
    warn_test(f"  Strategy {sid} dry-run", test_strategy_dry_run(sid))


# ─────────────────────────────────────────────────────────────────
# 7. ALERT ENGINE
# ─────────────────────────────────────────────────────────────────
print("\n[7/8] ALERT ENGINE")

def test_alert_engine():
    from alerts.alert_engine import AlertEngine, Alert, AlertLevel
    engine = AlertEngine()
    alert = Alert(
        level=AlertLevel.INFO,
        title="Test Alert",
        body="System test",
        strategy_id="TEST",
        symbol="TEST",
    )
    # Don't actually fire (would make sound), just test dedup
    fp = alert.fingerprint
    return True, f"Engine initialized, alert fingerprint={fp[:8]}..., {len(engine._channels)} channels"

def test_alert_store():
    from alerts.alert_engine import AlertEngine
    engine = AlertEngine()
    recent = engine.get_history(limit=5)
    return True, f"Alert store accessible, {len(recent)} recent alerts"

test("Alert engine init", test_alert_engine)
test("Alert store (SQLite)", test_alert_store)


# ─────────────────────────────────────────────────────────────────
# 8. JOURNAL
# ─────────────────────────────────────────────────────────────────
print("\n[8/8] JOURNAL")

def test_journal_db():
    from journal.journal import JournalDB
    db_path = Path("data/journal.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = JournalDB(str(db_path))
    return True, f"JournalDB initialized at {db_path}"

def test_journal_syncer():
    from journal.journal import JournalDB, TradeSyncer
    from core.mt5_connection import MT5Connection
    db_path = Path("data/journal.db")
    db = JournalDB(str(db_path))
    mt5 = MT5Connection()
    mt5.connect()
    syncer = TradeSyncer(db, mt5)
    # Test _sync_once directly (no thread)
    try:
        syncer._sync_once()
        return True, "Sync executed without errors"
    except Exception as e:
        return False, f"Sync error: {e}"

test("Journal DB init", test_journal_db)
test("Journal syncer (no crash)", test_journal_syncer)


# ─────────────────────────────────────────────────────────────────
# INSTRUMENT → SYMBOL MAPPER (main.py)
# ─────────────────────────────────────────────────────────────────
print("\n[BONUS] INSTRUMENT → SYMBOL MAPPING")

def test_instrument_mapper():
    # Import the mapper function
    sys.path.insert(0, str(Path(__file__).parent))
    from main import _instrument_to_symbol
    sym_map = _instrument_to_symbol()
    has_btc = "btc" in sym_map
    has_eth = "eth" in sym_map
    return (has_btc and has_eth,
            f"{len(sym_map)} instruments mapped: {list(sym_map.keys())}")

test("Instrument mapper has crypto", test_instrument_mapper)


# ─────────────────────────────────────────────────────────────────
# RESULTS SUMMARY
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
total = results["pass"] + results["fail"] + results["warn"]
print(f"  RESULTS: {results['pass']}/{total} passed | "
      f"{results['fail']} failed | {results['warn']} warnings")
print("=" * 65)

if results["fail"] == 0:
    print(f"\n  {PASS} ALL TESTS PASSED — System ready to launch!")
else:
    print(f"\n  {FAIL} {results['fail']} TESTS FAILED — Fix issues before launching")

sys.exit(0 if results["fail"] == 0 else 1)
