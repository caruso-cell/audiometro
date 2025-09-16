from __future__ import annotations
import json, os
from typing import List, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

def _load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(RESULTS_FILE):
        return []
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_all(items: List[Dict[str, Any]]) -> None:
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def add_result(item: Dict[str, Any]) -> None:
    data = _load_all()
    data.append(item)
    _save_all(data)

def list_results() -> List[Dict[str, Any]]:
    return _load_all()

