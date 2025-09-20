from __future__ import annotations
from typing import List, Dict, Optional
import os
import json
import datetime


def _parse_created_at(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        return 0.0
    return dt.timestamp()


def list_patient_exams(base_appdata: str, patient_id: str) -> List[Dict]:
    """
    Elenca audiometrie di un assistito, restituendo metadati (data, path, anteprima).
    """
    root = os.path.join(base_appdata, "Farmaudiometria", "audiometries", patient_id)
    if not os.path.isdir(root):
        return []
    out: List[Dict] = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            entry = {
                "path": path,
                "created_at": data.get("created_at"),
                "summary": data.get("notes", ""),
            }
            out.append(entry)
    out.sort(key=lambda item: (_parse_created_at(item.get("created_at")), os.path.basename(item["path"])), reverse=True)
    return out
