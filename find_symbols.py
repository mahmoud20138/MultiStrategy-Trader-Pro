"""
Helper script to find available symbol names on your MT5 broker.
Run this to discover the correct symbol names for your broker.
"""
import MetaTrader5 as mt5

# Initialize connection
if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    exit()

print("✅ Connected to MT5\n")
print("=" * 70)
print("AVAILABLE SYMBOLS ON YOUR BROKER")
print("=" * 70)

# Get all symbols
symbols = mt5.symbols_get()
if symbols is None:
    print("Failed to get symbols")
    mt5.shutdown()
    exit()

# Common keywords to search for
keywords = {
    "Gold": ["GOLD", "XAU", "XAUUSD"],
    "NASDAQ 100": ["NAS", "US100", "NDX", "USTEC", "NAS100"],
    "S&P 500": ["US500", "SPX", "SP500", "S&P"],
    "Dow Jones": ["US30", "DJI", "DOW", "DJ30"],
    "Dollar Index": ["DXY", "DX", "DOLLAR", "USDX", "USDOLLAR"],
}

print("\nSearching for trading instruments...\n")

found_symbols = {key: [] for key in keywords.keys()}

for symbol in symbols:
    name = symbol.name.upper()
    for instrument, patterns in keywords.items():
        for pattern in patterns:
            if pattern in name:
                found_symbols[instrument].append(symbol.name)
                break

# Display results
for instrument, syms in found_symbols.items():
    print(f"{instrument}:")
    if syms:
        for sym in set(syms):  # Remove duplicates
            # Get symbol info
            info = mt5.symbol_info(sym)
            if info:
                print(f"  • {sym:<15} - {info.description}")
    else:
        print(f"  ❌ Not found")
    print()

print("=" * 70)
print("\nTo use these symbols, update your .env file:")
print("  SYMBOL_GOLD=<symbol_name>")
print("  SYMBOL_NAS100=<symbol_name>")
print("  SYMBOL_US500=<symbol_name>")
print("  SYMBOL_US30=<symbol_name>")
print("  SYMBOL_DXY=<symbol_name>")
print()

mt5.shutdown()
