from __future__ import annotations
from typing import Dict
from datetime import datetime

from calibration_loader.profiles import profile_hash

FREQS = [125, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000]


class AudiometrySession:
    """Tiene lo stato dell'esame corrente (punti OD/OS)."""

    def __init__(self) -> None:
        self.points_od: Dict[int, float] = {}
        self.points_os: Dict[int, float] = {}
        self.notes: str = ""

    def add_point(self, ear: str, freq: int, db_hl: float) -> None:
        if freq not in FREQS:
            raise ValueError(f"Frequenza {freq} Hz non supportata.")
        if ear == "OD":
            self.points_od[freq] = float(db_hl)
        elif ear == "OS":
            self.points_os[freq] = float(db_hl)
        else:
            raise ValueError("Ear deve essere 'OD' o 'OS'.")

    def to_dict(self, patient: Dict, device: Dict, profile: Dict) -> Dict:
        timestamp = datetime.utcnow().isoformat(timespec="seconds")
        return {
            "schema": "audiometry.v1",
            "created_at": timestamp,
            "patient": patient,
            "device": device,
            "calibration_profile": {"hash": profile_hash(profile)},
            "frequencies_hz": FREQS,
            "OD": {str(k): v for k, v in sorted(self.points_od.items())},
            "OS": {str(k): v for k, v in sorted(self.points_os.items())},
            "notes": self.notes,
        }
