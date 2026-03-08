#!/usr/bin/env python3
"""Add data=data to remaining strategy files."""
import re

files = [
    "strategies/nas100_strategies.py",
    "strategies/us500_strategies.py",
    "strategies/us30_strategies.py",
    "strategies/crypto_strategies.py",
]

patterns = [
    ('strength=SignalStrength.MODERATE,\n                )',
     'strength=SignalStrength.MODERATE,\n                    data=data,\n                )'),
    ('strength=SignalStrength.STRONG,\n                )',
     'strength=SignalStrength.STRONG,\n                    data=data,\n                )'),
    ('strength=SignalStrength.VERY_STRONG,\n                )',
     'strength=SignalStrength.VERY_STRONG,\n                    data=data,\n                )'),
]

for filepath in files:
    print(f"Processing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    for old, new in patterns:
        content = content.replace(old, new)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Updated {filepath}")
    else:
        print(f"  - No changes needed")

print("\nDone!")
