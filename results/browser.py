from __future__ import annotations
from typing import List, Dict, Optional
import json
import datetime
from pathlib import Path



def _parse_created_at(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        return 0.0
    return dt.timestamp()


def list_patient_exams(base_appdata: str, patient_id: str, *, data_root: str | Path | None = None) -> List[Dict]:
    """
    Elenca audiometrie di un assistito, restituendo metadati (data, path, anteprima).
    """
    if data_root is not None:
        root = Path(data_root) / 'Pazienti' / patient_id / 'Audiometrie'
    else:
        root = Path(base_appdata) / 'Farmaudiometria' / 'audiometries' / patient_id
    if not root.is_dir():
        return []
    out: List[Dict] = []
    for file_path in root.rglob('*.json'):
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        entry = {
            "path": str(file_path),
            "created_at": data.get("created_at"),
            "summary": data.get("notes", ""),
        }
        out.append(entry)
    out.sort(key=lambda item: (_parse_created_at(item.get("created_at")), Path(item["path"]).name), reverse=True)
    return out
