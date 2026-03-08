#!/usr/bin/env python3
"""Update _make_signal calls to add data=data parameter."""
import re

files = [
    "strategies/gold_strategies.py",
    "strategies/nas100_strategies.py",
    "strategies/us500_strategies.py",
    "strategies/us30_strategies.py",
    "strategies/crypto_strategies.py",
]

for filepath in files:
    print(f"Processing {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Pattern: find _make_signal(...) calls
    # Match from _make_signal( all the way to closing )
    pattern = re.compile(r'(_make_signal\([^)]+\bstrength\s*=\s*SignalStrength\.[^,)]+[^)]*)(\))')

    def replacer(match):
        call_content = match.group(1)
        closing_paren = match.group(2)
        # If already has data=, skip
        if 'data=data' in call_content or 'data = data' in call_content:
            return match.group(0)
        # Add data=data before closing paren
        # If last char is comma, just add data=data,
        # If no comma, add , data=data
        if call_content.rstrip().endswith(','):
            return call_content + '\n                    data=data' + closing_paren
        else:
            return call_content + ',\n                    data=data' + closing_paren

    content = pattern.sub(replacer, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  Updated {filepath}")
    else:
        print(f"  - No changes needed")

print("\nDone!")
