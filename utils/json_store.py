"""
Centralized JSON persistence layer for Indaba.
All data I/O goes through here — atomic writes, consistent error handling.
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')


def read_json(filename):
    """Read a JSON file from the data directory. Returns None if missing or corrupt."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def write_json(filename, data):
    """Atomically write data to a JSON file in the data directory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    abs_path = os.path.abspath(path)
    tmp = abs_path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, abs_path)
