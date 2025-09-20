from __future__ import annotations
from typing import Dict
import os, json, datetime

def save_exam(base_appdata: str, patient_id: str, exam: Dict) -> str:
    """
    Salva l'esame in %APPDATA%/Farmaudiometria/audiometries/<patient_id>/YYYY/MM/
    Ritorna il path del file.
    """
    root = os.path.join(base_appdata, "Farmaudiometria", "audiometries", patient_id)
    now = datetime.datetime.now()
    folder = os.path.join(root, f"{now:%Y}", f"{now:%m}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{now:%Y%m%d_%H%M%S}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(exam, f, ensure_ascii=False, indent=2)
    return path
