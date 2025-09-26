from __future__ import annotations
from typing import Any, Dict
import json
import os

_SETTINGS_FILENAME = 'settings.json'


def _settings_path(base_appdata: str) -> str:
    folder = os.path.join(base_appdata, 'Farmaudiometria')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, _SETTINGS_FILENAME)


def _default_settings() -> Dict[str, Any]:
    return {
        'preferred_device_id': None,
        'calibrations': {},
        'updates': {
            'manifest_url': None,
            'last_check': None,
            'pending': None,
        },
    }


def load_settings(base_appdata: str) -> Dict[str, Any]:
    path = _settings_path(base_appdata)
    if not os.path.exists(path):
        return _default_settings()
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_settings()
    data.setdefault('preferred_device_id', None)
    data.setdefault('calibrations', {})
    updates = data.setdefault('updates', {})
    updates.setdefault('manifest_url', None)
    updates.setdefault('last_check', None)
    updates.setdefault('pending', None)
    return data


def save_settings(base_appdata: str, settings: Dict[str, Any]) -> None:
    path = _settings_path(base_appdata)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
