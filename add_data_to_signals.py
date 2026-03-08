#!/usr/bin/env python3
"""Add data=data parameter to all _make_signal() calls in strategy files."""
import re

files = [
    "strategies/gold_strategies.py",
    "strategies/nas100_strategies.py",
    "strategies/us500_strategies.py",
    "strategies/us30_strategies.py",
    "strategies/crypto_strategies.py",
]

# Pattern to find _make_signal( ... strength=... ) calls
# This looks for the closing ) after strength=
pattern = re.compile(
    r'(_make_signal\(\s*\n(?:\s+.*?\n)*?\s+strength\s*=\s*SignalStrength\.[^\n)]+(?:[^\n)]|\n\s+)*?)(\))',
    re.MULTILINE
)

for filepath in files:
    print(f"Processing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    matches = list(pattern.finditer(content))
    print(f"  Found {len(matches)} _make_signal calls")

    # Process in reverse order to maintain positions
    for match in reversed(matches):
        call_content = match.group(1)
        closing_paren = match.group(2)
        # Add data=data before closing paren if not already present
        if 'data=data' not in call_content and 'data = data' not in call_content:
            new_call = call_content.rstrip() + ',\n                    data=data'
            content = content[:match.start()] + new_call + closing_paren + content[match.end():]

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Updated {filepath}")
    else:
        print(f"  - No changes needed")

print("\nDone!")
