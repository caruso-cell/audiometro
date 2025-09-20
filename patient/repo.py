from __future__ import annotations
from typing import Optional, Dict, Any, List
import os, json

class PatientRepo:
    """
    Gestisce persistenza degli assistiti in %APPDATA%/Farmaudiometria/patients/
    """
    def __init__(self, base_appdata: str) -> None:
        self.base = os.path.join(base_appdata, "Farmaudiometria", "patients")
        os.makedirs(self.base, exist_ok=True)

    def save(self, patient: Dict[str, Any]) -> None:
        path = os.path.join(self.base, f"{patient['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(patient, f, ensure_ascii=False, indent=2)

    def list_all(self) -> List[Dict[str, Any]]:
        items = []
        for fn in os.listdir(self.base):
            if fn.endswith(".json"):
                with open(os.path.join(self.base, fn), "r", encoding="utf-8") as f:
                    items.append(json.load(f))
        return items
