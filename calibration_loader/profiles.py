from __future__ import annotations
from typing import Dict, Any, Optional, Callable
import json
import os
import hashlib
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml opzionale
    yaml = None


class CalibrationProfileError(ValueError):
    """Eccezione sollevata quando il profilo di calibrazione non passa la validazione."""


def _load_raw_profile(path: Path) -> Dict[str, Any]:
    ext = path.suffix.lower()
    with path.open('r', encoding='utf-8') as handle:
        if ext in {'.yaml', '.yml'}:
            if yaml is None:
                raise CalibrationProfileError('Supporto YAML non disponibile: installa PyYAML.')
            data = yaml.safe_load(handle)
        else:
            data = json.load(handle)
    if not isinstance(data, dict):
        raise CalibrationProfileError('Profilo non valido: atteso oggetto JSON/YAML di tipo dizionario.')
    return data


def _validate_basic_fields(data: Dict[str, Any]) -> None:
    for field in ('wasapi_id', 'device_name'):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CalibrationProfileError(f"Profilo non valido: campo '{field}' mancante o vuoto.")
    sr = data.get('sample_rate')
    if sr is not None and not isinstance(sr, (int, float)):
        raise CalibrationProfileError("Profilo non valido: 'sample_rate' deve essere numerico.")
    max_db = data.get('max_db_hl')
    if max_db is not None and not isinstance(max_db, (int, float)):
        raise CalibrationProfileError("Profilo non valido: 'max_db_hl' deve essere numerico.")


def _normalise_channel_map(raw_map: Any, value_transform: Optional[Callable[[float], float]] = None) -> Dict[int, float]:
    if raw_map is None:
        return {}
    if not isinstance(raw_map, dict):
        raise CalibrationProfileError('Profilo non valido: attesa mappa frequenza->valore.')
    converted: Dict[int, float] = {}
    for freq_key, value in raw_map.items():
        if not isinstance(value, (int, float)):
            raise CalibrationProfileError('Profilo non valido: i valori di calibrazione devono essere numerici.')
        try:
            freq = int(float(freq_key))
        except (TypeError, ValueError) as exc:
            raise CalibrationProfileError(f"Frequenza non valida nel profilo: {freq_key!r}.") from exc
        if freq <= 0:
            raise CalibrationProfileError('Le frequenze devono essere positive.')
        level = float(value)
        if value_transform is not None:
            level = value_transform(level)
        converted[freq] = level
    return converted


def _extract_channels_legacy(data: Dict[str, Any]) -> Dict[str, Dict[int, float]]:
    raw_channels = data.get('channels')
    if raw_channels is None:
        mapping = data.get('mapping')
        if isinstance(mapping, dict):
            raw_channels = {'OD': mapping, 'OS': mapping}
    if not isinstance(raw_channels, dict) or not raw_channels:
        raise CalibrationProfileError("Profilo non valido: sezione 'channels' mancante o vuota.")

    aliases = {
        'RIGHT': 'OD',
        'R': 'OD',
        'DX': 'OD',
        'OD': 'OD',
        'LEFT': 'OS',
        'L': 'OS',
        'SX': 'OS',
        'OS': 'OS',
    }
    normalised: Dict[str, Dict[int, float]] = {}
    for key, value in raw_channels.items():
        alias = aliases.get(str(key).upper(), str(key).upper())
        normalised[alias] = _normalise_channel_map(value)
    for ear in ('OD', 'OS'):
        normalised.setdefault(ear, {})
    return normalised


def _build_from_audiocalib(data: Dict[str, Any]) -> Dict[str, Any]:
    device = data.get('device')
    if not isinstance(device, dict):
        raise CalibrationProfileError("Profilo 'audiocalib' non valido: sezione 'device' mancante.")
    wasapi_id = str(device.get('wasapi_id', '')).strip()
    if not wasapi_id:
        raise CalibrationProfileError("Profilo 'audiocalib' non valido: 'device.wasapi_id' mancante.")

    mapping = data.get('mapping_dbfs')
    if not isinstance(mapping, dict) or not mapping:
        raise CalibrationProfileError("Profilo 'audiocalib' non valido: 'mapping_dbfs' mancante o vuoto.")

    ear_aliases = {
        'R': 'OD',
        'RIGHT': 'OD',
        'DX': 'OD',
        '1': 'OD',
        'OD': 'OD',
        'L': 'OS',
        'LEFT': 'OS',
        'SX': 'OS',
        '0': 'OS',
        'OS': 'OS',
    }
    channels: Dict[str, Dict[int, float]] = {'OD': {}, 'OS': {}}
    for key, ear_map in mapping.items():
        alias = ear_aliases.get(str(key).upper())
        if not alias:
            continue
        channels[alias] = _normalise_channel_map(ear_map, value_transform=lambda v: -abs(float(v)))

    profile = {
        'schema': data.get('schema', 'audiocalib.v1'),
        'device': {
            'name': device.get('name'),
            'wasapi_id': wasapi_id,
            'sample_rate': device.get('sample_rate'),
            'channels': device.get('channels'),
            'portaudio_index': device.get('portaudio_index'),
            'host_api': device.get('host_api'),
        },
        'headphones': data.get('headphones'),
        'channels': channels,
        'max_db_hl': float(data.get('max_db_hl', 100.0)),
        'notes': data.get('notes', ''),
        'created_at': data.get('created_at'),
    }
    return profile


def load_profile(path: str) -> Dict[str, Any]:
    """Carica e valida un profilo calibrazione .json/.yaml."""
    profile_path = Path(path)
    data = _load_raw_profile(profile_path)

    if 'mapping_dbfs' in data or data.get('schema', '').startswith('audiocalib'):
        profile = _build_from_audiocalib(data)
    else:
        _validate_basic_fields(data)
        channels = _extract_channels_legacy(data)
        data['channels'] = channels
        data.setdefault('schema', 'calibration.v1')
        if 'max_db_hl' not in data:
            data['max_db_hl'] = 100.0
        profile = data
    profile['source_path'] = str(profile_path)
    return profile


def profile_hash(profile: Dict[str, Any]) -> str:
    """Hash stabile del profilo per tracciamento."""
    raw = json.dumps(profile, sort_keys=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def local_profile_path_for_device(appdata: str, wasapi_id: str) -> Optional[str]:
    """
    Cerca un profilo locale per l'ID specificato.
    Ritorna path o None se assente.
    """
    folder = os.path.join(appdata, 'Farmaudiometria', 'calibrations', wasapi_id)
    if not os.path.isdir(folder):
        return None
    valid_ext = {'.json', '.yaml', '.yml'}
    for fn in sorted(os.listdir(folder)):
        if Path(fn).suffix.lower() in valid_ext:
            return os.path.join(folder, fn)
    return None
