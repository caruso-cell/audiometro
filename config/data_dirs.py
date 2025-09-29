from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class DataDirectories:
    root: Path
    patients: Path
    calibrations: Path
    export: Path


def _documents_root() -> Path:
    candidates = [
        os.environ.get('DOCUMENTS'),
        os.environ.get('USERPROFILE'),
    ]
    for value in candidates:
        if not value:
            continue
        candidate = Path(value)
        if candidate.name.lower() != 'documents' and 'documents' not in candidate.name.lower():
            candidate = candidate / 'Documents'
        if candidate.exists():
            return candidate
    fallback = Path.home() / 'Documents'
    return fallback if fallback.exists() else Path.home()


def ensure_data_dirs() -> DataDirectories:
    root = _documents_root() / 'SW_MIMMO' / 'Audiometro'
    patients = root / 'Pazienti'
    calibrations = root / 'Calibrazioni'
    export = root / 'Export'
    for path in (root, patients, calibrations, export):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return DataDirectories(root=root, patients=patients, calibrations=calibrations, export=export)
