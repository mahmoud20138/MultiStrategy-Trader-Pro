"""
╔══════════════════════════════════════════════════════════════════╗
║       Strategy Reference — Single Source of Truth               ║
╚══════════════════════════════════════════════════════════════════╝
Contains the detailed description for every strategy (A-U).
Imported by both the Dash dashboard and the test suite so
wording never drifts between the two.
"""
from __future__ import annotations

from config import STRATEGY_REGISTRY

# ── Strategy Descriptions ────────────────────────────────────────
# Key = strategy ID (must match STRATEGY_REGISTRY).
# Fields: what, reference, indicators, entry, exit.
# ─────────────────────────────────────────────────────────────────

STRATEGY_DESCRIPTIONS = {
    "A": {
        "what":       "Calculates the Asian session range (22:00-06:00 UTC), then waits for London open to sweep "
                      "beyond that range — a liquidity grab. Enters on the reversal candle pullback inside the range.",
        "reference":  "Liquidity Sweep / ICT Asian Range",
        "indicators": "ATR(14), EMA(21), Asian Range high/low, Engulfing candle patterns",
        "entry":      "London sweeps above/below Asian range → reversal engulfing candle → enter on pullback inside range",
        "exit":       "SL beyond the sweep wick (farthest point of trap) | TP at opposite end of Asian range",
    },
    "B": {
        "what":       "Identifies fresh Order Blocks on M15 that align with VWAP during the NY session. "
                      "Entry only when price taps the OB while VWAP confirms direction — dual confluence for precision.",
        "reference":  "ICT Order Blocks + VWAP Confluence",
        "indicators": "VWAP, ATR(14), Order Block detection (ICT), OB freshness check",
        "entry":      "Price taps fresh Order Block + is on correct side of VWAP → enter at OB level",
        "exit":       "SL beyond Order Block body | TP at 1:3 R:R or next structure level",
    },
    "C": {
        "what":       "After high-impact news causes a spike >$15 in Gold, monitors for momentum stall "
                      "(small candle bodies, long wicks). Fades the spike expecting a partial retracement.",
        "reference":  "News Spike Fade / Mean Reversion",
        "indicators": "ATR(14), Spike size detection (>$15), Candle body-to-range ratio (stall confirmation)",
        "entry":      "Spike >$15 detected → 3+ stall candles (body < 30% of range) → enter fade opposite to spike",
        "exit":       "SL beyond spike extreme | TP at 50% retracement of the spike",
    },
    "D": {
        "what":       "Exploits the inverse correlation between Gold and US Dollar Index (DXY). When DXY falls but "
                      "Gold is flat/rising → bullish divergence. Confirmed with RSI divergence on M15.",
        "reference":  "Intermarket Correlation / DXY-Gold Inverse",
        "indicators": "DXY price feed, RSI(14) divergence detection, EMA(50), ATR(14), S/R levels for TP",
        "entry":      "DXY falling + Gold flat/rising (or vice versa) + RSI divergence confirms → enter",
        "exit":       "SL = 2×ATR | TP at next H1 Support/Resistance level or 4×ATR",
    },
    "E": {
        "what":       "Identifies the dominant London session direction, then waits for the NY open pullback to VWAP. "
                      "Enters continuation trade in London's direction from the VWAP pullback.",
        "reference":  "Session Transition / London-NY Continuation",
        "indicators": "VWAP, ATR(14), EMA(21), London session direction (07:00-12:00 UTC bar analysis)",
        "entry":      "London moves > 1 ATR in one direction → NY open pulls back to VWAP → enter continuation",
        "exit":       "SL below/above VWAP ± 0.5 ATR | TP at 75% of London session move",
    },
    "F": {
        "what":       "Draws H1 trendlines with 3+ touches. When price breaks through, waits for a retest of the "
                      "broken trendline (now acting as support/resistance) and enters on the confirmation candle.",
        "reference":  "Classical Trendline Analysis / Break & Retest",
        "indicators": "ATR(14), Trendline detection (3+ touch points), Break distance measurement",
        "entry":      "H1 trendline break → price retests broken trendline (within 0.3 ATR) → enter on confirmation",
        "exit":       "SL beyond trendline ± 0.5 ATR | TP at 3.5× ATR from entry",
    },
    "G": {
        "what":       "Swing strategy targeting Gold's $50/$100 round-number institutional levels. Waits for D1 RSI "
                      "extreme (overbought >70 or oversold <30) near a round level, then enters on a H4 reversal candle.",
        "reference":  "Institutional Round Numbers + RSI Extremes",
        "indicators": "Round levels ($50 steps), RSI(14) on D1, ATR(14), EMA(21) on H4, Reversal candle pattern",
        "entry":      "Price within 1 ATR of $50/$100 round level + D1 RSI extreme + H4 reversal candle (body > 60%) → enter",
        "exit":       "SL beyond H4 reversal wick ± 0.5 ATR | TP at 5× ATR (wide swing target)",
    },
    "H": {
        "what":       "Identifies Fibonacci cluster zones where multiple Fibonacci retracements from different swing "
                      "points converge within a $3-5 zone — a high-probability reversal area. Enters when price is in the cluster.",
        "reference":  "Fibonacci Cluster / Multi-Swing Confluence",
        "indicators": "Fibonacci retracements (multiple swings), Fibonacci cluster detection, RSI(14) on D1, EMA(21) on H4, ATR(14)",
        "entry":      "Price enters Fib cluster zone (2+ Fib levels within ±0.5 ATR) + RSI supportive + H4 trend ok → enter",
        "exit":       "SL beyond cluster zone ± 0.8 ATR | TP at 3.5× risk (cluster edge to target)",
    },
    "I": {
        "what":       "Calculates the first 30-minute range after NY open (13:30-14:00 UTC). Waits for a breakout above/below "
                      "that range with volume surge (>1.5× avg) and VWAP alignment to confirm direction.",
        "reference":  "Opening Range Breakout (ORB)",
        "indicators": "VWAP, ATR(14), Volume SMA(20), Opening Range calculation (13:30-14:00 UTC)",
        "entry":      "Price breaks above/below 30-min opening range + volume > 1.5× SMA(20) + correct side of VWAP → enter",
        "exit":       "SL at opposite end of opening range | TP at 1:3 R:R",
    },
    "J": {
        "what":       "Uses an EMA ribbon (9/21/55) on M1 — when all three EMAs are stacked in order (trending), "
                      "waits for a Stochastic pullback crossover to enter in the trend direction. Ultra-fast scalp.",
        "reference":  "EMA Ribbon + Stochastic Pullback",
        "indicators": "EMA(9), EMA(21), EMA(55) — ribbon alignment, Stochastic(14,3,3) crossover, ATR(14)",
        "entry":      "All 3 EMAs stacked (9>21>55 bull or reverse) + Stochastic crosses in pullback zone → enter",
        "exit":       "SL = 1.2× ATR below/above entry | TP = 2× ATR",
    },
    "K": {
        "what":       "Implements ICT Power of 3: (1) Accumulation — price in tight range (<1.5 ATR), "
                      "(2) Manipulation — false breakout/liquidity grab beyond range, "
                      "(3) Distribution — Break of Structure (BOS) in true direction + Fair Value Gap (FVG) for entry.",
        "reference":  "ICT Power of 3 (Accumulation → Manipulation → Distribution)",
        "indicators": "ATR(14), Range detection, BOS (Break of Structure), FVG (Fair Value Gap)",
        "entry":      "Tight range → false break (manipulation) → BOS in real direction → enter at FVG in true direction",
        "exit":       "SL beyond manipulation wick ± 0.5 ATR | TP at 3× ATR (distribution target)",
    },
    "L": {
        "what":       "Analyzes overnight gaps in NAS100. Small gaps (<1%) → fade toward gap fill (mean reversion). "
                      "Large gaps (>1.5%) → trade continuation in gap direction with momentum.",
        "reference":  "Gap Trading / Gap Fill vs Continuation",
        "indicators": "VWAP, ATR(14), Gap size calculation (today open vs yesterday close on D1)",
        "entry":      "Gap <1%: enter fade toward previous close | Gap >1.5%: enter continuation in gap direction (VWAP confirms)",
        "exit":       "Fade: SL = 0.5× gap, TP = previous close | Continuation: SL below/above gap, TP = gap_size × 0.6",
    },
    "M": {
        "what":       "Multi-timeframe trend following: D1 EMA(20) above EMA(50) confirms trend → price pulls back to EMA zone "
                      "→ drop to H4 for trigger candle (bullish/bearish close within 1 ATR of 4H EMA 21) → enter.",
        "reference":  "Trend Pullback / Multi-TF EMA Alignment",
        "indicators": "EMA(20) + EMA(50) on D1 (trend), EMA(21) on H4 (trigger), ATR(14)",
        "entry":      "D1 EMA 20 > EMA 50 (uptrend) → D1 pullback to EMA zone → H4 trigger candle near EMA 21 → enter",
        "exit":       "SL = 2× ATR below/above H4 trigger | TP = 4× ATR",
    },
    "N": {
        "what":       "Mean reversion on range-bound days. Filters for low-volatility ('range day') conditions, then waits for "
                      "price to touch VWAP upper/lower band with RSI(7) at extreme (>80 or <20) → fades back toward VWAP mid.",
        "reference":  "VWAP Band Mean Reversion",
        "indicators": "VWAP with upper/lower bands (±1 std dev), RSI(7) for extremes, ATR(14), Range-day filter",
        "entry":      "Range day + price at VWAP band extreme + RSI(7) overbought/oversold → fade toward VWAP middle",
        "exit":       "SL beyond VWAP band ± 0.5 ATR | TP at VWAP center line",
    },
    "O": {
        "what":       "Three-timeframe alignment: H1 EMA(200) sets directional bias → M15 Break of Structure (BOS) confirms the move "
                      "→ M5 Supertrend flip provides the precise entry trigger. All three must agree.",
        "reference":  "Multi-Timeframe Trend + Smart Money BOS + Supertrend",
        "indicators": "EMA(200) on H1, BOS detection on M15, Supertrend on M5, ATR(14)",
        "entry":      "H1 price above EMA 200 (bull) → M15 BOS bullish confirms → M5 Supertrend flips bullish → enter",
        "exit":       "SL = Supertrend level ± 0.5 ATR | TP = 3× ATR",
    },
    "P": {
        "what":       "Weekly SMA(200) determines macro trend → Daily RSI pulls back into the 40-50 'buy zone' (uptrend) "
                      "or 50-60 'sell zone' (downtrend) → price near Daily SMA(50) → H4 confirmation candle triggers entry.",
        "reference":  "RSI Pullback Zone + Weekly Structure",
        "indicators": "SMA(200) on Weekly (trend), SMA(50) on Daily (entry zone), RSI(14) on Daily, EMA(21) on H4, ATR(14)",
        "entry":      "Weekly uptrend (>SMA 200) → D1 RSI in 40-50 zone + near SMA 50 → H4 bullish candle → enter",
        "exit":       "SL = D1 SMA 50 - 1.5× ATR | TP = 4.5× ATR (wide swing target)",
    },
    "Q": {
        "what":       "US30 reacts strongly at psychological round numbers (every 50, 100, 500, 1000 points). "
                      "Two modes: (a) Bounce — price touches level + reversal candle → scalp bounce. "
                      "(b) Break+Retest — price breaks through level → retests it → enter in break direction.",
        "reference":  "Price Psychology / Round Number Trading",
        "indicators": "Round levels (50/100/500/1000-pt steps), EMA(21), ATR(14)",
        "entry":      "Mode A: Touch round level + reversal candle → enter bounce | Mode B: Break level → retest → enter continuation",
        "exit":       "SL beyond round level ± 1.5 ATR | TP = 3× ATR",
    },
    "R": {
        "what":       "ICT Silver Bullet: trades only in two specific 1-hour windows — 10:00-11:00 AM ET (15:00-16:00 UTC) "
                      "and 2:00-3:00 PM ET (19:00-20:00 UTC). Within the window: identifies BOS, enters at the Fair Value Gap.",
        "reference":  "ICT Silver Bullet (Time-Based Liquidity Windows)",
        "indicators": "BOS (Break of Structure), FVG (Fair Value Gap), ATR(14), Time-window filter",
        "entry":      "Inside Silver Bullet window → BOS occurs → enter at FVG in BOS direction → ride the displacement",
        "exit":       "SL beyond FVG zone ± 0.5 ATR | TP = 3× ATR",
    },
    "S": {
        "what":       "Identifies key S/R levels on D1, then waits for a volume-confirmed breakout (>2× average volume). "
                      "After the breakout, drops to H4 to wait for a retest of the broken level before entering.",
        "reference":  "Breakout-Retest / Volume Confirmation",
        "indicators": "S/R levels (D1), Volume SMA(20) on D1 (>2× surge), EMA(21) on H4, ATR(14)",
        "entry":      "D1 S/R breakout with volume >2× avg → H4 retest of broken level (within 1 ATR) → enter",
        "exit":       "SL beyond broken level ± 1.5 ATR | TP = 4× ATR",
    },
    "T": {
        "what":       "BTC gravitates toward $1,000/$5,000/$10,000 round numbers. Waits for price to approach a round level, "
                      "then confirms bounce with RSI support (>40 for longs, <60 for shorts) and candle reversal pattern.",
        "reference":  "Crypto Round Number Psychology",
        "indicators": "Round levels ($1K/$5K/$10K steps), RSI(14), EMA(21), ATR(14)",
        "entry":      "Price near BTC round level (within 0.5 ATR or $300) + bounce candle + RSI not extreme → enter",
        "exit":       "SL beyond round level ± 1.2 ATR | TP = 3× ATR",
    },
    "U": {
        "what":       "ETH trend following using EMA 21/50 crossover on H4. Waits for the golden/death cross, then enters on "
                      "the first pullback to EMA 21 — confirmed by healthy RSI (45-70 for longs) and a directional candle.",
        "reference":  "Moving Average Crossover + Pullback",
        "indicators": "EMA(21), EMA(50) on H4 (crossover signal), RSI(14) (health filter), ATR(14)",
        "entry":      "EMA 21 crosses above EMA 50 → price pulls back to EMA 21 → RSI 45-70 + bullish candle → enter",
        "exit":       "SL below EMA 50 ± 0.5 ATR | TP = 2.5× risk distance",
    },
}


def validate_descriptions() -> list[str]:
    """Return list of strategy IDs in STRATEGY_REGISTRY but missing from STRATEGY_DESCRIPTIONS."""
    return [sid for sid in sorted(STRATEGY_REGISTRY) if sid not in STRATEGY_DESCRIPTIONS]


# ══════════════════════════════════════════════════════════════════
# TradingView Chart Integration
# ══════════════════════════════════════════════════════════════════

# Instrument → TradingView symbol
TV_SYMBOLS = {
    "gold":  "OANDA:XAUUSD",
    "nas100": "OANDA:NAS100USD",
    "us500": "OANDA:SPX500USD",
    "us30":  "OANDA:US30USD",
    "btc":   "BITSTAMP:BTCUSD",
    "eth":   "BITSTAMP:ETHUSD",
}

# MT5 TF constant → TradingView interval
TV_INTERVALS = {
    1: "1", 5: "5", 15: "15", 30: "30",
    16385: "60", 16388: "240", 16408: "D",
    32769: "W", 49153: "M",
}

# Per-strategy TradingView studies with exact parameters + annotations
# Each strategy has:
#   "studies" — list of (study_id, {inputs}) to load on the chart
#   "annotations" — text labels to overlay, explaining the setup
TV_CHART_CONFIG = {
    "A": {
        "studies": [
            ("MAExp@tv-basicstudies", {"length": 21}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy A: London Breakout Trap ──",
            "① Draw Asian Range (22:00–06:00 UTC high/low) as horizontal lines",
            "② Wait for London open sweep above/below the range (liquidity grab)",
            "③ Enter on reversal engulfing candle pulling BACK inside the range",
            "EMA(21) = trend filter  |  ATR(14) = SL sizing",
            "SL: beyond sweep wick  |  TP: opposite end of Asian range",
        ],
        "levels": [
            {"name": "Asian High", "color": "#3fb950", "style": "dashed", "desc": "22:00-06:00 UTC range upper boundary"},
            {"name": "Asian Low", "color": "#f85149", "style": "dashed", "desc": "22:00-06:00 UTC range lower boundary"},
            {"name": "EMA 21", "color": "#d29922", "style": "solid", "desc": "Trend direction filter"},
        ],
        "ranges": [
            {"name": "Asian Range", "color": "rgba(88,166,255,0.15)", "desc": "22:00-06:00 UTC consolidation box"},
            {"name": "Sweep Zone", "color": "rgba(248,81,73,0.15)", "desc": "Liquidity grab area beyond the range"},
        ],
        "flow": ["Draw Asian Range", "Wait London Sweep", "Spot Reversal", "Enter Inside Range"],
        "key_rules": [
            "Only trade at London open (07:00-08:30 UTC)",
            "Sweep must be a clean wick beyond the range",
            "Entry requires engulfing candle pulling back inside",
            "SL beyond sweep wick | TP opposite end of range",
        ],
    },
    "B": {
        "studies": [
            ("VWAP@tv-basicstudies",  {}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy B: VWAP + Order Block Sniper ──",
            "① Mark fresh Order Blocks on M15 (last unmitigated OB)",
            "② Check if price is on correct side of VWAP",
            "③ Enter when price taps fresh OB + VWAP confirms direction",
            "VWAP = directional bias  |  ATR(14) = SL sizing",
            "SL: beyond OB body  |  TP: 1:3 R:R or next structure",
        ],
        "levels": [
            {"name": "VWAP", "color": "#d29922", "style": "solid", "desc": "Volume-Weighted Average Price - directional filter"},
            {"name": "OB Top", "color": "#3fb950", "style": "dashed", "desc": "Order Block upper boundary"},
            {"name": "OB Bottom", "color": "#f85149", "style": "dashed", "desc": "Order Block lower boundary"},
        ],
        "ranges": [
            {"name": "Order Block", "color": "rgba(63,185,80,0.15)", "desc": "Fresh unmitigated M15 demand/supply zone"},
            {"name": "VWAP Zone", "color": "rgba(210,153,34,0.15)", "desc": "VWAP +/- tolerance area"},
        ],
        "flow": ["Mark Fresh OB on M15", "Check VWAP Side", "Price Taps OB", "Enter at OB Level"],
        "key_rules": [
            "Order Block must be unmitigated (first touch only)",
            "VWAP must confirm direction (price on correct side)",
            "NY session only for best liquidity",
            "SL beyond OB body | TP 1:3 R:R or next structure",
        ],
    },
    "C": {
        "studies": [
            ("ATR@tv-basicstudies", {"length": 14}),
        ],
        "annotations": [
            "── Strategy C: News Spike Fade ──",
            "① Detect spike > $15 after high-impact news",
            "② Wait for 3+ stall candles (body < 30% of range = momentum dying)",
            "③ Enter fade opposite to spike direction",
            "ATR(14) = spike & stall measurement",
            "SL: beyond spike extreme  |  TP: 50% retracement of spike",
        ],
        "levels": [
            {"name": "Pre-News Price", "color": "#8b949e", "style": "dotted", "desc": "Price level before news release"},
            {"name": "Spike Extreme", "color": "#f85149", "style": "dashed", "desc": "Highest/lowest point of news spike"},
            {"name": "50% Retrace", "color": "#3fb950", "style": "solid", "desc": "Target - 50% of spike distance"},
        ],
        "ranges": [
            {"name": "Spike Range", "color": "rgba(248,81,73,0.15)", "desc": "Full spike distance from pre-news to extreme"},
            {"name": "Stall Zone", "color": "rgba(210,153,34,0.15)", "desc": "3+ candles with body < 30% range - momentum dying"},
        ],
        "flow": ["Detect Spike > $15", "Count 3+ Stall Candles", "Confirm Momentum Loss", "Enter Fade"],
        "key_rules": [
            "Spike must be > $15 from pre-news price",
            "Need at least 3 stall candles (body < 30% of range)",
            "Fade = trade opposite to the spike direction",
            "SL beyond spike extreme | TP 50% retracement of spike",
        ],
    },
    "D": {
        "studies": [
            ("RSI@tv-basicstudies",   {"length": 14}),
            ("MAExp@tv-basicstudies",  {"length": 50}),
            ("ATR@tv-basicstudies",    {"length": 14}),
        ],
        "annotations": [
            "── Strategy D: DXY Divergence ──",
            "① Open DXY chart side-by-side (OANDA:DXY or TVC:DXY)",
            "② Look for inverse divergence: DXY falling + Gold flat/rising = BUY",
            "③ Confirm with RSI(14) divergence on M15",
            "EMA(50) = trend context  |  RSI(14) = divergence detection",
            "SL: 2× ATR  |  TP: next H1 S/R level or 4× ATR",
        ],
        "levels": [
            {"name": "EMA 50", "color": "#d29922", "style": "solid", "desc": "50-period EMA trend context"},
            {"name": "RSI 70", "color": "#f85149", "style": "dashed", "desc": "Overbought extreme - look for sell"},
            {"name": "RSI 30", "color": "#3fb950", "style": "dashed", "desc": "Oversold extreme - look for buy"},
        ],
        "ranges": [
            {"name": "Divergence Zone", "color": "rgba(88,166,255,0.15)", "desc": "Area where DXY and Gold move inversely"},
        ],
        "flow": ["Open DXY Side-by-Side", "Spot Inverse Move", "Confirm RSI Divergence", "Enter Trade"],
        "key_rules": [
            "DXY falling + Gold flat/rising = BUY Gold",
            "DXY rising + Gold flat/falling = SELL Gold",
            "RSI(14) divergence on M15 required for confirmation",
            "SL = 2x ATR | TP = next H1 S/R or 4x ATR",
        ],
    },
    "E": {
        "studies": [
            ("VWAP@tv-basicstudies",  {}),
            ("MAExp@tv-basicstudies",  {"length": 21}),
            ("ATR@tv-basicstudies",    {"length": 14}),
        ],
        "annotations": [
            "── Strategy E: Session Transition ──",
            "① Draw London session direction (07:00–12:00 UTC high → low or low → high)",
            "② Measure London move — must be > 1 ATR",
            "③ Wait for NY open pullback to VWAP → enter continuation in London's direction",
            "VWAP = pullback level  |  EMA(21) = trend  |  ATR(14) = filter",
            "SL: VWAP ± 0.5 ATR  |  TP: 75% of London session move",
        ],
        "levels": [
            {"name": "London High", "color": "#3fb950", "style": "dashed", "desc": "Highest point of London session 07:00-12:00 UTC"},
            {"name": "London Low", "color": "#f85149", "style": "dashed", "desc": "Lowest point of London session"},
            {"name": "VWAP", "color": "#d29922", "style": "solid", "desc": "NY pullback target level"},
            {"name": "EMA 21", "color": "#58a6ff", "style": "solid", "desc": "Trend filter on M15/H1"},
        ],
        "ranges": [
            {"name": "London Move", "color": "rgba(63,185,80,0.15)", "desc": "07:00-12:00 UTC session total range"},
            {"name": "NY Pullback", "color": "rgba(88,166,255,0.15)", "desc": "Area near VWAP where NY open pulls back"},
        ],
        "flow": ["Measure London Move", "Verify > 1 ATR", "Wait NY Pullback to VWAP", "Enter Continuation"],
        "key_rules": [
            "London move must exceed 1 ATR to qualify",
            "NY open must pull back to VWAP level",
            "Enter in London's direction (continuation)",
            "SL = VWAP +/- 0.5 ATR | TP = 75% of London move",
        ],
    },
    "F": {
        "studies": [
            ("ATR@tv-basicstudies", {"length": 14}),
        ],
        "annotations": [
            "── Strategy F: Trendline Break + Retest ──",
            "① Draw H1 trendlines with 3+ touch points",
            "② Wait for clean break through the trendline",
            "③ Wait for price to RETEST the broken trendline (within 0.3 ATR)",
            "④ Enter on confirmation candle at the retest",
            "ATR(14) = break distance & SL sizing",
            "SL: beyond trendline ± 0.5 ATR  |  TP: 3.5× ATR",
        ],
        "levels": [
            {"name": "Trendline", "color": "#d29922", "style": "solid", "desc": "H1 trendline with 3+ touch points"},
            {"name": "Retest Level", "color": "#58a6ff", "style": "dashed", "desc": "Broken trendline as new S/R"},
            {"name": "SL Level", "color": "#f85149", "style": "dashed", "desc": "Stop loss beyond trendline +/- 0.5 ATR"},
            {"name": "TP Level", "color": "#3fb950", "style": "dashed", "desc": "Take profit at 3.5x ATR from entry"},
        ],
        "ranges": [
            {"name": "Retest Zone", "color": "rgba(88,166,255,0.15)", "desc": "Area within 0.3 ATR of broken trendline"},
        ],
        "flow": ["Draw H1 Trendline (3+ touches)", "Wait Clean Break", "Wait Retest (0.3 ATR)", "Enter on Confirmation"],
        "key_rules": [
            "Trendline must have 3+ touches to be valid",
            "Break must be clean close (not just wick)",
            "Retest must be within 0.3 ATR of broken trendline",
            "SL beyond trendline +/- 0.5 ATR | TP 3.5x ATR",
        ],
    },
    "G": {
        "studies": [
            ("RSI@tv-basicstudies",   {"length": 14}),
            ("MAExp@tv-basicstudies",  {"length": 21}),
            ("ATR@tv-basicstudies",    {"length": 14}),
        ],
        "annotations": [
            "── Strategy G: Weekly Institutional Levels ──",
            "① Draw horizontal lines at $50 / $100 round-number levels",
            "② Wait for D1 RSI extreme: >70 (overbought) or <30 (oversold)",
            "③ Drop to H4 — enter on reversal candle (body > 60% of range) near round level",
            "RSI(14) on D1 = extreme filter  |  EMA(21) on H4 = trend",
            "SL: beyond H4 wick ± 0.5 ATR  |  TP: 5× ATR",
        ],
        "levels": [
            {"name": "Round Number", "color": "#d29922", "style": "solid", "desc": "$50 or $100 institutional level"},
            {"name": "RSI 70", "color": "#f85149", "style": "dashed", "desc": "D1 RSI overbought extreme"},
            {"name": "RSI 30", "color": "#3fb950", "style": "dashed", "desc": "D1 RSI oversold extreme"},
            {"name": "EMA 21", "color": "#58a6ff", "style": "solid", "desc": "H4 trend context filter"},
        ],
        "ranges": [
            {"name": "Round Level Zone", "color": "rgba(210,153,34,0.15)", "desc": "+/- 1 ATR zone around $50/$100 level"},
        ],
        "flow": ["Mark $50/$100 Levels", "Wait D1 RSI Extreme (>70/<30)", "Drop to H4", "Enter on Reversal Candle"],
        "key_rules": [
            "Draw levels at every $50 and $100 round number",
            "D1 RSI must be > 70 (sell setup) or < 30 (buy setup)",
            "H4 reversal candle body > 60% of candle range",
            "SL beyond H4 wick +/- 0.5 ATR | TP 5x ATR",
        ],
    },
    "H": {
        "studies": [
            ("RSI@tv-basicstudies",   {"length": 14}),
            ("MAExp@tv-basicstudies",  {"length": 21}),
            ("ATR@tv-basicstudies",    {"length": 14}),
        ],
        "annotations": [
            "── Strategy H: Fibonacci Cluster ──",
            "① Use Fibonacci retracement tool from multiple swing highs/lows",
            "② Identify cluster zone where 2+ Fib levels converge within ±0.5 ATR ($3–5 zone)",
            "③ Draw a rectangle/box marking the cluster zone",
            "④ Enter when price reaches cluster + RSI supportive + H4 trend OK",
            "RSI(14) = confirmation  |  EMA(21) = trend",
            "SL: beyond cluster ± 0.8 ATR  |  TP: 3.5× risk",
        ],
        "levels": [
            {"name": "Fib 38.2%", "color": "#3fb950", "style": "dashed", "desc": "First Fibonacci retracement level"},
            {"name": "Fib 50.0%", "color": "#d29922", "style": "dashed", "desc": "Mid-point Fibonacci level"},
            {"name": "Fib 61.8%", "color": "#f85149", "style": "dashed", "desc": "Golden ratio retracement level"},
        ],
        "ranges": [
            {"name": "Cluster Zone", "color": "rgba(88,166,255,0.15)", "desc": "2+ Fib levels converge within +/- 0.5 ATR ($3-5)"},
        ],
        "flow": ["Draw Multiple Fib Retracements", "Find Cluster (2+ levels)", "RSI + Trend Confirm", "Enter at Cluster"],
        "key_rules": [
            "Use Fibonacci from multiple different swing points",
            "Cluster = 2+ Fib levels within +/- 0.5 ATR ($3-5 zone)",
            "Draw rectangle/box marking the cluster zone",
            "SL beyond cluster +/- 0.8 ATR | TP 3.5x risk",
        ],
    },
    "I": {
        "studies": [
            ("VWAP@tv-basicstudies",    {}),
            ("ATR@tv-basicstudies",      {"length": 14}),
            ("Volume@tv-basicstudies",   {}),
        ],
        "annotations": [
            "── Strategy I: Opening Range Breakout (ORB) ──",
            "① Draw horizontal lines at 13:30–14:00 UTC range high & low (first 30 min of NY)",
            "② Wait for breakout above/below with volume > 1.5× SMA(20)",
            "③ Confirm price on correct side of VWAP → enter",
            "VWAP = direction  |  Volume = surge confirmation",
            "SL: opposite end of opening range  |  TP: 1:3 R:R",
        ],
        "levels": [
            {"name": "ORB High", "color": "#3fb950", "style": "dashed", "desc": "30-min range high (13:30-14:00 UTC)"},
            {"name": "ORB Low", "color": "#f85149", "style": "dashed", "desc": "30-min range low (13:30-14:00 UTC)"},
            {"name": "VWAP", "color": "#d29922", "style": "solid", "desc": "Direction filter for breakout"},
        ],
        "ranges": [
            {"name": "Opening Range", "color": "rgba(88,166,255,0.15)", "desc": "13:30-14:00 UTC first 30-min NY range"},
            {"name": "Volume Surge", "color": "rgba(63,185,80,0.15)", "desc": "Volume bars > 1.5x SMA(20) on breakout"},
        ],
        "flow": ["Mark 30-min Range (13:30-14:00)", "Wait Breakout", "Confirm Volume > 1.5x", "Enter + VWAP Filter"],
        "key_rules": [
            "Draw horizontal lines at 13:30-14:00 range high and low",
            "Breakout volume must exceed 1.5x SMA(20)",
            "VWAP must confirm breakout direction",
            "SL opposite end of opening range | TP 1:3 R:R",
        ],
    },
    "J": {
        "studies": [
            ("MAExp@tv-basicstudies",       {"length": 9}),
            ("MAExp@tv-basicstudies",       {"length": 21}),
            ("MAExp@tv-basicstudies",       {"length": 55}),
            ("Stochastic@tv-basicstudies",  {"length": 14}),
            ("ATR@tv-basicstudies",          {"length": 14}),
        ],
        "annotations": [
            "── Strategy J: EMA Ribbon Scalp ──",
            "① Add EMA 9 (blue), EMA 21 (yellow), EMA 55 (red) — the ribbon",
            "② BULL: all 3 stacked 9 > 21 > 55  |  BEAR: 9 < 21 < 55",
            "③ Wait for Stochastic(14,3,3) pullback crossover in trending zone",
            "④ Enter in trend direction on Stochastic cross",
            "EMA ribbon = trend direction  |  Stochastic = timing",
            "SL: 1.2× ATR  |  TP: 2× ATR",
        ],
        "levels": [
            {"name": "EMA 9", "color": "#58a6ff", "style": "solid", "desc": "Fast EMA - ribbon top in uptrend"},
            {"name": "EMA 21", "color": "#d29922", "style": "solid", "desc": "Mid EMA - ribbon middle"},
            {"name": "EMA 55", "color": "#f85149", "style": "solid", "desc": "Slow EMA - ribbon bottom in uptrend"},
        ],
        "ranges": [
            {"name": "EMA Ribbon", "color": "rgba(210,153,34,0.15)", "desc": "Zone between EMA 9 and EMA 55 - trend band"},
        ],
        "flow": ["Check EMA Stack (9>21>55)", "Wait Stochastic Pullback", "Stochastic Cross Signal", "Enter in Trend"],
        "key_rules": [
            "BULL: EMA 9 > 21 > 55 | BEAR: EMA 9 < 21 < 55",
            "Stochastic(14,3,3) must cross in pullback zone",
            "Enter ONLY in direction of EMA stack",
            "SL = 1.2x ATR | TP = 2x ATR",
        ],
    },
    "K": {
        "studies": [
            ("ATR@tv-basicstudies", {"length": 14}),
        ],
        "annotations": [
            "── Strategy K: ICT Power of 3 ──",
            "① ACCUMULATION: Draw box around tight range (< 1.5 ATR)",
            "② MANIPULATION: Mark the false breakout / liquidity grab beyond the range",
            "③ DISTRIBUTION: Mark Break of Structure (BOS) in the TRUE direction",
            "④ Enter at Fair Value Gap (FVG) — the 3-candle imbalance gap in BOS direction",
            "Draw: range box → manipulation wick → BOS line → FVG zone",
            "SL: beyond manipulation wick ± 0.5 ATR  |  TP: 3× ATR",
        ],
        "levels": [
            {"name": "Range High", "color": "#8b949e", "style": "dashed", "desc": "Accumulation range upper boundary"},
            {"name": "Range Low", "color": "#8b949e", "style": "dashed", "desc": "Accumulation range lower boundary"},
            {"name": "BOS Level", "color": "#3fb950", "style": "solid", "desc": "Break of Structure in the true direction"},
        ],
        "ranges": [
            {"name": "Accumulation", "color": "rgba(139,148,158,0.15)", "desc": "Tight range < 1.5 ATR - price compressing"},
            {"name": "Manipulation", "color": "rgba(248,81,73,0.15)", "desc": "False breakout / liquidity grab beyond range"},
            {"name": "FVG", "color": "rgba(63,185,80,0.15)", "desc": "Fair Value Gap - 3-candle imbalance for entry"},
        ],
        "flow": ["Mark Accumulation Range", "Detect Manipulation Sweep", "Confirm BOS", "Enter at FVG"],
        "key_rules": [
            "Accumulation range must be < 1.5 ATR (tight)",
            "Manipulation = false breakout grabbing liquidity",
            "BOS in true direction confirms the real move",
            "Enter at FVG (3-candle imbalance) in BOS direction",
            "SL beyond manipulation wick +/- 0.5 ATR | TP 3x ATR",
        ],
    },
    "L": {
        "studies": [
            ("VWAP@tv-basicstudies", {}),
            ("ATR@tv-basicstudies",  {"length": 14}),
        ],
        "annotations": [
            "── Strategy L: Gap Fill ──",
            "① Draw horizontal line at yesterday's close (D1)",
            "② Measure gap size: today's open vs yesterday's close",
            "③ Gap < 1%: FADE toward gap fill (mean reversion to yesterday close)",
            "④ Gap > 1.5%: CONTINUATION in gap direction (VWAP must confirm)",
            "VWAP = direction filter for continuation gaps",
            "Fade: SL = 0.5× gap, TP = prev close  |  Cont: SL = below gap, TP = gap × 0.6",
        ],
        "levels": [
            {"name": "Yesterday Close", "color": "#d29922", "style": "solid", "desc": "Previous day closing price - gap reference"},
            {"name": "Today Open", "color": "#58a6ff", "style": "dashed", "desc": "Current day opening price"},
            {"name": "Gap Fill Target", "color": "#3fb950", "style": "dashed", "desc": "For fade trades: yesterday close level"},
        ],
        "ranges": [
            {"name": "Gap Zone", "color": "rgba(88,166,255,0.15)", "desc": "Distance between yesterday close and today open"},
        ],
        "flow": ["Measure Gap Size", "Gap<1%: Fade / Gap>1.5%: Continue", "VWAP Filter", "Enter Trade"],
        "key_rules": [
            "Small gap (< 1%): FADE toward yesterday close",
            "Large gap (> 1.5%): CONTINUATION in gap direction",
            "VWAP must confirm direction for continuation trades",
            "Fade SL=0.5x gap TP=prev close | Cont SL=below gap TP=0.6x gap",
        ],
    },
    "M": {
        "studies": [
            ("MAExp@tv-basicstudies", {"length": 20}),
            ("MAExp@tv-basicstudies", {"length": 50}),
            ("MAExp@tv-basicstudies", {"length": 21}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy M: 20/50 EMA Pullback ──",
            "① D1 chart: EMA 20 (blue) above EMA 50 (red) = UPTREND",
            "② Wait for D1 pullback into the EMA 20–50 zone",
            "③ Drop to H4: look for trigger candle near EMA 21 (within 1 ATR)",
            "④ Enter on bullish/bearish close at H4 EMA 21",
            "D1 EMAs = trend  |  H4 EMA(21) = trigger level",
            "SL: 2× ATR below trigger  |  TP: 4× ATR",
        ],
        "levels": [
            {"name": "D1 EMA 20", "color": "#58a6ff", "style": "solid", "desc": "Daily fast EMA - trend on D1"},
            {"name": "D1 EMA 50", "color": "#f85149", "style": "solid", "desc": "Daily slow EMA - trend confirmation"},
            {"name": "H4 EMA 21", "color": "#d29922", "style": "solid", "desc": "H4 trigger level for entry"},
        ],
        "ranges": [
            {"name": "EMA Pullback Zone", "color": "rgba(88,166,255,0.15)", "desc": "D1 zone between EMA 20 and EMA 50"},
        ],
        "flow": ["D1: EMA 20 > 50 (Uptrend)", "D1 Pullback to EMA Zone", "H4: Trigger near EMA 21", "Enter on Candle"],
        "key_rules": [
            "D1 EMA 20 above EMA 50 for longs (below for shorts)",
            "Wait for D1 pullback into the 20-50 EMA zone",
            "H4 entry candle must be within 1 ATR of EMA 21",
            "SL = 2x ATR below trigger | TP = 4x ATR",
        ],
    },
    "N": {
        "studies": [
            ("VWAP@tv-basicstudies",  {}),
            ("RSI@tv-basicstudies",   {"length": 7}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy N: VWAP Mean Reversion ──",
            "① Check for RANGE DAY (low ATR, no strong trend)",
            "② Draw VWAP upper/lower bands (±1 std dev) — or use VWAP with bands indicator",
            "③ When price touches VWAP band extreme + RSI(7) > 80 or < 20 → FADE",
            "④ Enter toward VWAP center line",
            "VWAP bands = range levels  |  RSI(7) = extreme timing",
            "SL: beyond VWAP band ± 0.5 ATR  |  TP: VWAP center",
        ],
        "levels": [
            {"name": "VWAP Center", "color": "#d29922", "style": "solid", "desc": "VWAP center line - mean reversion target"},
            {"name": "VWAP Upper Band", "color": "#3fb950", "style": "dashed", "desc": "VWAP + 1 std dev - sell extreme"},
            {"name": "VWAP Lower Band", "color": "#f85149", "style": "dashed", "desc": "VWAP - 1 std dev - buy extreme"},
        ],
        "ranges": [
            {"name": "VWAP Band", "color": "rgba(210,153,34,0.15)", "desc": "VWAP +/- 1 std dev mean reversion area"},
        ],
        "flow": ["Confirm Range Day", "Price at VWAP Extreme", "RSI(7) > 80 or < 20", "Fade to VWAP Center"],
        "key_rules": [
            "Only trade on RANGE DAYS (low ATR, no strong trend)",
            "Price must touch VWAP band extreme (+/- 1 std dev)",
            "RSI(7) must be > 80 (sell) or < 20 (buy)",
            "SL beyond VWAP band +/- 0.5 ATR | TP = VWAP center",
        ],
    },
    "O": {
        "studies": [
            ("MAExp@tv-basicstudies",       {"length": 200}),
            ("Supertrend@tv-basicstudies",   {}),
            ("ATR@tv-basicstudies",          {"length": 14}),
        ],
        "annotations": [
            "── Strategy O: Multi-TF Trend (H1 → M15 → M5) ──",
            "① H1: Price above EMA(200) = BULL bias (draw EMA 200 line)",
            "② M15: Mark Break of Structure (BOS) — bullish BOS confirms",
            "③ M5: Supertrend flips bullish → ENTER",
            "All 3 TFs must agree in same direction",
            "EMA(200) on H1 = bias  |  BOS on M15 = confirmation  |  Supertrend on M5 = trigger",
            "SL: Supertrend level ± 0.5 ATR  |  TP: 3× ATR",
        ],
        "levels": [
            {"name": "H1 EMA 200", "color": "#d29922", "style": "solid", "desc": "H1 macro bias filter"},
            {"name": "M15 BOS", "color": "#3fb950", "style": "dashed", "desc": "M15 Break of Structure level"},
            {"name": "M5 Supertrend", "color": "#58a6ff", "style": "solid", "desc": "M5 Supertrend - precise entry trigger"},
        ],
        "ranges": [
            {"name": "Bull Zone", "color": "rgba(63,185,80,0.15)", "desc": "Above H1 EMA 200 = bullish bias"},
            {"name": "Bear Zone", "color": "rgba(248,81,73,0.15)", "desc": "Below H1 EMA 200 = bearish bias"},
        ],
        "flow": ["H1: Price vs EMA 200", "M15: BOS Confirms Direction", "M5: Supertrend Flips", "Enter on Flip"],
        "key_rules": [
            "All 3 timeframes MUST agree in same direction",
            "H1 EMA 200 = bias (above=bull, below=bear)",
            "M15 BOS = structural confirmation",
            "M5 Supertrend flip = entry trigger",
            "SL = Supertrend level +/- 0.5 ATR | TP = 3x ATR",
        ],
    },
    "P": {
        "studies": [
            ("MASimple@tv-basicstudies", {"length": 200}),
            ("MASimple@tv-basicstudies", {"length": 50}),
            ("RSI@tv-basicstudies",      {"length": 14}),
            ("MAExp@tv-basicstudies",    {"length": 21}),
            ("ATR@tv-basicstudies",      {"length": 14}),
        ],
        "annotations": [
            "── Strategy P: RSI + Structure (Weekly → Daily → H4) ──",
            "① Weekly: Draw SMA(200) — price above = macro UPTREND",
            "② Daily: SMA(50) as entry zone + RSI(14) pullback to 40–50 zone (buy zone)",
            "③ H4: Bullish confirmation candle near EMA(21) → ENTER",
            "SMA(200) W = macro  |  SMA(50) D = zone  |  RSI = timing  |  EMA(21) H4 = trigger",
            "SL: D1 SMA 50 − 1.5× ATR  |  TP: 4.5× ATR",
        ],
        "levels": [
            {"name": "W SMA 200", "color": "#d29922", "style": "solid", "desc": "Weekly macro trend line"},
            {"name": "D SMA 50", "color": "#58a6ff", "style": "solid", "desc": "Daily entry zone level"},
            {"name": "H4 EMA 21", "color": "#3fb950", "style": "solid", "desc": "H4 trigger level for entry"},
            {"name": "RSI 40-50", "color": "#f85149", "style": "dashed", "desc": "D1 RSI pullback buy zone"},
        ],
        "ranges": [
            {"name": "RSI Buy Zone", "color": "rgba(63,185,80,0.15)", "desc": "D1 RSI 40-50 for longs (50-60 for shorts)"},
            {"name": "SMA Entry Zone", "color": "rgba(88,166,255,0.15)", "desc": "Area near Daily SMA 50"},
        ],
        "flow": ["W: Above SMA 200?", "D: RSI 40-50 + Near SMA 50", "H4: Candle at EMA 21", "Enter on Confirmation"],
        "key_rules": [
            "Weekly: price above SMA 200 = macro uptrend",
            "Daily: RSI must pull back to 40-50 (buy) or 50-60 (sell)",
            "Daily: price near SMA 50 = optimal entry zone",
            "H4: bullish confirmation candle near EMA 21",
            "SL = D1 SMA 50 - 1.5x ATR | TP = 4.5x ATR",
        ],
    },
    "Q": {
        "studies": [
            ("MAExp@tv-basicstudies", {"length": 21}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy Q: Round Number Bounce ──",
            "① Draw horizontal lines at every 50, 100, 500, 1000 points on US30",
            "② MODE A (Bounce): Price touches round level + reversal candle → enter bounce",
            "③ MODE B (Break+Retest): Price breaks level → retests → enter continuation",
            "EMA(21) = trend context for mode selection",
            "SL: beyond round level ± 1.5 ATR  |  TP: 3× ATR",
        ],
        "levels": [
            {"name": "Round 100", "color": "#d29922", "style": "solid", "desc": "100-pt round numbers (39100, 39200...)"},
            {"name": "Round 500", "color": "#58a6ff", "style": "solid", "desc": "500-pt levels (stronger reaction)"},
            {"name": "Round 1000", "color": "#3fb950", "style": "solid", "desc": "1000-pt levels (strongest reaction)"},
            {"name": "EMA 21", "color": "#8b949e", "style": "solid", "desc": "Trend context for mode A/B selection"},
        ],
        "ranges": [
            {"name": "Bounce Zone", "color": "rgba(210,153,34,0.15)", "desc": "+/- 1.5 ATR reaction area around round number"},
        ],
        "flow": ["Mark Round Levels (50/100/500/1K)", "Mode A: Bounce / Mode B: Break", "EMA 21 Trend Filter", "Enter"],
        "key_rules": [
            "Draw lines at every 50, 100, 500, 1000 point levels",
            "Mode A (Bounce): reversal candle at level -> scalp bounce",
            "Mode B (Break+Retest): break -> retest -> continuation",
            "EMA 21 determines which mode (with/against trend)",
            "SL beyond round level +/- 1.5 ATR | TP = 3x ATR",
        ],
    },
    "R": {
        "studies": [
            ("ATR@tv-basicstudies", {"length": 14}),
        ],
        "annotations": [
            "── Strategy R: ICT Silver Bullet ──",
            "① Draw vertical lines at Silver Bullet windows:",
            "   Window 1: 10:00–11:00 AM ET (15:00–16:00 UTC)",
            "   Window 2: 2:00–3:00 PM ET (19:00–20:00 UTC)",
            "② Inside window: Mark Break of Structure (BOS)",
            "③ Enter at Fair Value Gap (FVG) in BOS direction",
            "Only trade inside these 1-hour windows!",
            "SL: beyond FVG ± 0.5 ATR  |  TP: 3× ATR",
        ],
        "levels": [
            {"name": "BOS Level", "color": "#3fb950", "style": "solid", "desc": "Break of Structure inside time window"},
            {"name": "FVG Top", "color": "#58a6ff", "style": "dashed", "desc": "Fair Value Gap upper boundary"},
            {"name": "FVG Bottom", "color": "#58a6ff", "style": "dashed", "desc": "Fair Value Gap lower boundary"},
        ],
        "ranges": [
            {"name": "Window 1", "color": "rgba(88,166,255,0.15)", "desc": "10:00-11:00 AM ET (15:00-16:00 UTC)"},
            {"name": "Window 2", "color": "rgba(210,153,34,0.15)", "desc": "2:00-3:00 PM ET (19:00-20:00 UTC)"},
            {"name": "FVG Zone", "color": "rgba(63,185,80,0.15)", "desc": "3-candle imbalance gap for entry"},
        ],
        "flow": ["Inside Time Window?", "Spot BOS", "Find FVG in BOS Direction", "Enter at FVG"],
        "key_rules": [
            "ONLY trade inside Silver Bullet windows!",
            "Window 1: 10:00-11:00 AM ET (15:00-16:00 UTC)",
            "Window 2: 2:00-3:00 PM ET (19:00-20:00 UTC)",
            "BOS must occur inside window, enter at FVG",
            "SL beyond FVG +/- 0.5 ATR | TP = 3x ATR",
        ],
    },
    "S": {
        "studies": [
            ("MAExp@tv-basicstudies",  {"length": 21}),
            ("ATR@tv-basicstudies",    {"length": 14}),
            ("Volume@tv-basicstudies", {}),
        ],
        "annotations": [
            "── Strategy S: Breakout-Retest ──",
            "① Draw key S/R levels on D1 (horizontal lines)",
            "② Wait for breakout with volume > 2× average (big green/red volume bar)",
            "③ Drop to H4: wait for retest of the broken level (within 1 ATR)",
            "④ Enter on retest confirmation candle",
            "Volume = breakout quality  |  EMA(21) H4 = trend",
            "SL: beyond broken level ± 1.5 ATR  |  TP: 4× ATR",
        ],
        "levels": [
            {"name": "D1 S/R", "color": "#d29922", "style": "solid", "desc": "Key Support/Resistance on Daily chart"},
            {"name": "Broken Level", "color": "#58a6ff", "style": "dashed", "desc": "S/R after breakout - now acts as opposite"},
            {"name": "EMA 21", "color": "#3fb950", "style": "solid", "desc": "H4 trend context filter"},
        ],
        "ranges": [
            {"name": "Retest Zone", "color": "rgba(88,166,255,0.15)", "desc": "Within 1 ATR of broken level"},
            {"name": "Volume Surge", "color": "rgba(63,185,80,0.15)", "desc": "Volume > 2x average on breakout"},
        ],
        "flow": ["Mark D1 S/R Levels", "Breakout + Volume > 2x", "H4 Retest of Level", "Enter on Confirmation"],
        "key_rules": [
            "Draw key S/R levels on Daily chart first",
            "Breakout volume must be > 2x average",
            "Drop to H4: wait for retest within 1 ATR",
            "Confirmation candle at retest triggers entry",
            "SL beyond broken level +/- 1.5 ATR | TP = 4x ATR",
        ],
    },
    "T": {
        "studies": [
            ("RSI@tv-basicstudies",   {"length": 14}),
            ("MAExp@tv-basicstudies",  {"length": 21}),
            ("ATR@tv-basicstudies",    {"length": 14}),
        ],
        "annotations": [
            "── Strategy T: BTC Round Number Bounce ──",
            "① Draw horizontal lines at $1K / $5K / $10K round levels on BTC",
            "② Wait for price within 0.5 ATR (or ~$300) of round level",
            "③ Confirm: bounce candle + RSI not at extreme (> 40 for longs, < 60 for shorts)",
            "④ Enter bounce trade",
            "RSI(14) = filter extremes  |  EMA(21) = trend context",
            "SL: beyond round level ± 1.2 ATR  |  TP: 3× ATR",
        ],
        "levels": [
            {"name": "$1K Level", "color": "#8b949e", "style": "dashed", "desc": "$1,000 multiples - minor round number"},
            {"name": "$5K Level", "color": "#d29922", "style": "solid", "desc": "$5,000 multiples - medium round number"},
            {"name": "$10K Level", "color": "#3fb950", "style": "solid", "desc": "$10,000 multiples - major round number"},
            {"name": "EMA 21", "color": "#58a6ff", "style": "solid", "desc": "Trend context filter"},
        ],
        "ranges": [
            {"name": "Round Zone", "color": "rgba(210,153,34,0.15)", "desc": "+/- 0.5 ATR (~$300) around round number"},
        ],
        "flow": ["Mark BTC Round Levels ($1K/$5K/$10K)", "Price Within 0.5 ATR", "RSI Not Extreme", "Enter Bounce"],
        "key_rules": [
            "Draw lines at $1K, $5K, $10K multiples",
            "Price must be within 0.5 ATR (~$300) of round level",
            "RSI > 40 for longs, < 60 for shorts",
            "Bounce candle + RSI confirmation -> enter",
            "SL beyond round level +/- 1.2 ATR | TP = 3x ATR",
        ],
    },
    "U": {
        "studies": [
            ("MAExp@tv-basicstudies", {"length": 21}),
            ("MAExp@tv-basicstudies", {"length": 50}),
            ("RSI@tv-basicstudies",   {"length": 14}),
            ("ATR@tv-basicstudies",   {"length": 14}),
        ],
        "annotations": [
            "── Strategy U: ETH Trend Following ──",
            "① H4 chart: Add EMA 21 (blue) + EMA 50 (red)",
            "② Golden cross: EMA 21 crosses ABOVE EMA 50 → look for LONG",
            "③ Wait for pullback to EMA 21 + RSI(14) in 45–70 zone + bullish candle → ENTER",
            "EMA crossover = signal  |  RSI = health filter  |  Pullback = entry timing",
            "SL: below EMA 50 ± 0.5 ATR  |  TP: 2.5× risk distance",
        ],
        "levels": [
            {"name": "EMA 21", "color": "#58a6ff", "style": "solid", "desc": "Fast EMA - pullback entry level"},
            {"name": "EMA 50", "color": "#f85149", "style": "solid", "desc": "Slow EMA - trend and SL reference"},
            {"name": "RSI 45-70", "color": "#d29922", "style": "dashed", "desc": "Healthy RSI zone for longs"},
        ],
        "ranges": [
            {"name": "Crossover Zone", "color": "rgba(88,166,255,0.15)", "desc": "Area between EMA 21 and EMA 50"},
            {"name": "RSI Health", "color": "rgba(63,185,80,0.15)", "desc": "RSI 45-70 for longs (healthy territory)"},
        ],
        "flow": ["H4: Golden Cross (EMA21>50)", "Wait Pullback to EMA 21", "RSI in 45-70", "Bullish Candle -> Enter"],
        "key_rules": [
            "Golden cross: EMA 21 must cross above EMA 50",
            "Do NOT chase the cross - wait for pullback",
            "RSI(14) must be in 45-70 zone (healthy momentum)",
            "Enter on bullish candle at EMA 21 pullback",
            "SL below EMA 50 +/- 0.5 ATR | TP = 2.5x risk",
        ],
    },
}


def build_tv_url(strategy_id: str) -> str:
    """Build a local TV chart page URL for *strategy_id*.

    Points to /assets/tv_chart.html which constructs the TradingView
    Advanced Chart widget with the correct symbol, interval, indicators
    (with exact parameters), and strategy annotation overlay.
    """
    import json
    from urllib.parse import quote

    meta = STRATEGY_REGISTRY.get(strategy_id)
    if not meta:
        return ""

    tv_symbol = TV_SYMBOLS.get(meta.instrument, "OANDA:XAUUSD")
    primary_tf = meta.timeframes[0] if meta.timeframes else 15
    tv_interval = TV_INTERVALS.get(primary_tf, "15")

    cfg = TV_CHART_CONFIG.get(strategy_id, {})
    studies = cfg.get("studies", [])
    annotations = cfg.get("annotations", [])

    # Encode config as JSON in the URL hash (avoids server round-trip)
    payload = json.dumps({
        "symbol": tv_symbol,
        "interval": tv_interval,
        "studies": [[s[0], s[1]] for s in studies],
        "annotations": annotations,
        "levels": cfg.get("levels", []),
        "ranges": cfg.get("ranges", []),
        "flow": cfg.get("flow", []),
        "key_rules": cfg.get("key_rules", []),
        "title": f"Strategy {strategy_id}: {meta.name}",
    }, separators=(",", ":"))

    return f"/assets/tv_chart.html#" + quote(payload, safe="")
