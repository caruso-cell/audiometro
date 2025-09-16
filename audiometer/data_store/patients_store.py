from __future__ import annotations
import json, os
from typing import List, Optional
from ..models.patient import Patient

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
PATIENTS_FILE = os.path.join(DATA_DIR, "patients.json")

def _load_all() -> List[Patient]:
    if not os.path.exists(PATIENTS_FILE):
        return []
    with open(PATIENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Patient.from_dict(p) for p in data]

def _save_all(patients: List[Patient]) -> None:
    with open(PATIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in patients], f, ensure_ascii=False, indent=2)

def list_patients() -> List[Patient]:
    return _load_all()

def add_or_update_patient(p: Patient) -> None:
    items = _load_all()
    by_id = {x.patient_id: x for x in items}
    by_id[p.patient_id] = p
    _save_all(list(by_id.values()))

def get_patient(pid: str) -> Optional[Patient]:
    for p in _load_all():
        if p.patient_id == pid:
            return p
    return None

