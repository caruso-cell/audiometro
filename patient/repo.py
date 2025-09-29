from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json


class PatientRepo:
    """Gestisce persistenza degli assistiti."""

    def __init__(self, base_appdata: str, *, data_root: Path | str | None = None) -> None:
        if data_root is not None:
            root = Path(data_root)
            self.base = root / 'Pazienti'
        else:
            root = Path(base_appdata) / 'Farmaudiometria'
            self.base = root / 'patients'
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, patient: Dict[str, Any]) -> None:
        path = self.base / f"{patient['id']}.json"
        with path.open('w', encoding='utf-8') as handle:
            json.dump(patient, handle, ensure_ascii=False, indent=2)

    def list_all(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for file_path in sorted(self.base.glob('*.json')):
            try:
                data = json.loads(file_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                items.append(data)
        return items
