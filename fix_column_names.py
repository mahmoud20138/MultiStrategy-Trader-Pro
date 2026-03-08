"""
Fix DataFrame column name case: lowercase -> Title Case
MT5 returns: Open, High, Low, Close, Volume
"""
import os
import re

# Column mapping
COLUMN_MAP = {
    '["close"]': '["Close"]',
    '["open"]': '["Open"]',
    '["high"]': '["High"]',
    '["low"]': '["Low"]',
    '["volume"]': '["Volume"]',
}

def fix_file(filepath):
    """Replace all column name references in a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Replace all lowercase column references
    for old, new in COLUMN_MAP.items():
        content = content.replace(old, new)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all strategy files"""
    strategies_dir = r"c:\Users\Mamoud\Desktop\vsc\vsc\TS\trading_system\strategies"
    
    files = [
        "gold_strategies.py",
        "nas100_strategies.py",
        "us30_strategies.py",
        "us500_strategies.py"
    ]
    
    for filename in files:
        filepath = os.path.join(strategies_dir, filename)
        if os.path.exists(filepath):
            if fix_file(filepath):
                print(f"✓ Fixed {filename}")
            else:
                print(f"- No changes needed in {filename}")
        else:
            print(f"✗ File not found: {filename}")

if __name__ == "__main__":
    main()
    print("\nDone! All column names updated.")
