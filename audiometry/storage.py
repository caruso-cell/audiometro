from __future__ import annotations
from typing import Dict
import json, datetime
from pathlib import Path


def save_exam(base_appdata: str, patient_id: str, exam: Dict, *, data_root: str | Path | None = None) -> str:
    """
    Salva l'esame in %APPDATA%/Farmaudiometria/audiometries/<patient_id>/YYYY/MM/
    Ritorna il path del file.
    """
    if data_root is not None:
        root = Path(data_root) / 'Pazienti' / patient_id / 'Audiometrie'
    else:
        root = Path(base_appdata) / 'Farmaudiometria' / 'audiometries' / patient_id
    now = datetime.datetime.now()
    folder = root / f"{now:%Y}" / f"{now:%m}"
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / f"{now:%Y%m%d_%H%M%S}.json"
    file_path.write_text(json.dumps(exam, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(file_path)
