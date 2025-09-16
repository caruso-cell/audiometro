from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class Patient:
    patient_id: str
    first_name: str
    last_name: str
    birth_date: Optional[str] = None  # ISO YYYY-MM-DD
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Patient":
        return Patient(
            patient_id=d.get("patient_id",""),
            first_name=d.get("first_name",""),
            last_name=d.get("last_name",""),
            birth_date=d.get("birth_date"),
            notes=d.get("notes"),
        )
