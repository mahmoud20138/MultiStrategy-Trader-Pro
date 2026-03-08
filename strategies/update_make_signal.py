#!/usr/bin/env python3
"""Add data=data to all _make_signal calls."""
import re
import sys

files = [
    "strategies/gold_strategies.py",
    "strategies/nas100_strategies.py",
    "strategies/us500_strategies.py",
    "strategies/us30_strategies.py",
    "strategies/crypto_strategies.py",
]

def process_file(filepath):
    """Process a single file and add data=data to _make_signal calls."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    modified = False

    while i < len(lines):
        line = lines[i]

        # Check for _make_signal( pattern
        if '_make_signal(' in line:
            # Collect the entire call until we find matching closing paren
            call_start = i
            paren_depth = 0

            # Count depth from opening paren of _make_signal
            j = i
            while j < len(lines):
                paren_depth += lines[j].count('(') - lines[j].count(')')
                if paren_depth <= 0:
                    # Found the closing paren
                    break
                j += 1

            # Extract the call content
            call_lines = lines[i:j+1]
            call_text = ''.join(call_lines)

            # Check if it already has data=
            if 'data=data' in call_text:
                new_lines.extend(lines[i:j+1])
                i = j + 1
                continue

            # Find the closing ) and add data=data before it
            # Look for the last occurrence of strength=...
            if 'strength=' in call_text:
                # Find the closing ) after strength=
                # Insert data=data, before the closing )
                idx = call_text.rfind(')')
                if idx > 0:
                    new_call_text = call_text[:idx] + ',\n                    data=data,\n                )'
                    # Split into lines and add
                    new_lines.extend(new_call_text.split('\n'))
                    modified = True
                    i = j + 1
                    continue

        new_lines.append(line)
        i += 1

    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False

# Process each file
count = 0
for filepath in files:
    print(f"Processing {filepath}...")
    if process_file(filepath):
        count += 1
        print(f"  Updated {filepath}")
    else:
        print(f"  - No changes needed")

print(f"\nTotal files updated: {count}")
