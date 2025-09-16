from __future__ import annotations
import os, json
from typing import Dict, Any

from ..paths import get_app_data_dir

HP_DIR = os.path.join(get_app_data_dir(True), "headphones")
os.makedirs(HP_DIR, exist_ok=True)

STD_FREQS = [250, 500, 1000, 2000, 4000, 8000]

class CalibrationStore:
    """Gestione offset di calibrazione per dispositivo, persistiti in un JSON.

    Struttura file (come calibrations.json nel repo):
    {
      "active_device": "Nome Dispositivo",
      "profiles": { "Nome Dispositivo": { "250": 0.0, ... } }
    }
    """

    def __init__(self, json_path: str, frequencies_hz: list[int]):
        self.json_path = json_path
        self.frequencies = [int(f) for f in frequencies_hz]
        self._data: Dict[str, Any] = self._load()
        self.active_device: str | None = self._data.get("active_device")

    def _load(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("profiles", {})
                return data
        except Exception:
            pass
        return {"active_device": None, "profiles": {}}

    def _ensure_profile(self, device_name: str) -> Dict[str, float]:
        profiles = self._data.setdefault("profiles", {})
        prof = profiles.get(device_name)
        if prof is None:
            prof = {str(f): 0.0 for f in self.frequencies}
            profiles[device_name] = prof
        else:
            for f in self.frequencies:
                prof.setdefault(str(f), 0.0)
        return prof

    # ---- API usata dal resto dell'app ----
    def has_profile_for(self, device_name: str) -> bool:
        return device_name in self._data.get("profiles", {})

    def set_active_device(self, device_name: str, create_if_missing: bool = False) -> None:
        if create_if_missing:
            self._ensure_profile(device_name)
        self.active_device = device_name
        self._data["active_device"] = device_name

    def load_profile(self, device_name: str) -> None:
        if not self.has_profile_for(device_name):
            raise ValueError(f"Profilo non trovato per dispositivo: {device_name}")
        self.set_active_device(device_name, create_if_missing=False)

    def reset_profile(self, device_name: str) -> None:
        self._data.setdefault("profiles", {})[device_name] = {str(f): 0.0 for f in self.frequencies}

    def get_map(self) -> Dict[int, float]:
        if not self.active_device:
            return {int(f): 0.0 for f in self.frequencies}
        prof = self._ensure_profile(self.active_device)
        return {int(k): float(v) for k, v in prof.items()}

    def get_offset(self, freq_hz: int) -> float:
        return float(self.get_map().get(int(freq_hz), 0.0))

    def set_offset(self, freq_hz: int, offset_db: float) -> None:
        if not self.active_device:
            return
        prof = self._ensure_profile(self.active_device)
        prof[str(int(freq_hz))] = float(offset_db)

    def save(self) -> str:
        if self.active_device:
            self._ensure_profile(self.active_device)
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        return self.json_path

class HeadphoneCalibration:
    """Gestisce bias per cuffie per-frequenza e per-orecchio.
    Bias (dB) è sommato al livello richiesto: livello_out = livello_HL + bias[f, ear].
    La calibrazione 'normoudente' imposta bias = -soglia_misurata, per portare la soglia a 0 dB HL.
    """
    def __init__(self):
        self.hp_id: str | None = None
        self.bias: Dict[str, Dict[int, float]] = { 'L': {}, 'R': {} }

    def set_headphone(self, hp_id: str) -> Dict[str, Dict[int, float]]:
        self.hp_id = hp_id or "default"
        self.bias = self._load_bias(self.hp_id)
        return self.bias

    def get_bias_db(self, ear: str, freq: int) -> float:
        return float(self.bias.get(ear, {}).get(int(freq), 0.0))

    def set_bias_map(self, bias_map: Dict[str, Dict[int, float]]) -> None:
        # sanitize keys
        out = {'L': {}, 'R': {}}
        for ear in ('L','R'):
            for f, v in (bias_map.get(ear, {}) or {}).items():
                try:
                    out[ear][int(f)] = float(v)
                except Exception:
                    continue
        self.bias = out

    def save(self) -> str:
        assert self.hp_id, "Headphone ID non impostato"
        path = self._file_for(self.hp_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.bias, f, ensure_ascii=False, indent=2)
        return path

    # ---- Calibrazione normoudente ----
    def compute_bias_from_thresholds(self, measured: Dict[str, Dict[int, float]]) -> Dict[str, Dict[int, float]]:
        """measured: {'L': {freq: soglia_dbHL}, 'R': {...}} -> bias = -soglia."""
        bias = {'L': {}, 'R': {}}
        for ear in ('L','R'):
            m = measured.get(ear, {}) or {}
            for f, th in m.items():
                try:
                    bias[ear][int(f)] = -float(th)
                except Exception:
                    pass
        return bias

    # ---- I/O helpers ----
    @staticmethod
    def _file_for(hp_id: str) -> str:
        return os.path.join(HP_DIR, f"{hp_id}.json")

    @staticmethod
    def _load_bias(hp_id: str) -> Dict[str, Dict[int, float]]:
        path = HeadphoneCalibration._file_for(hp_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # normalize
                norm = {'L': {}, 'R': {}}
                for ear in ('L','R'):
                    for k, v in (data.get(ear, {}) or {}).items():
                        try:
                            norm[ear][int(k)] = float(v)
                        except Exception:
                            continue
                return norm
            except Exception:
                pass
        return {'L': {}, 'R': {}}


class CombinedCalibration:
    """Wrapper che combina offset dispositivo (per-frequenza) e bias cuffia (per-orecchio).

    Usata da ManualTest/TestRunner per calcolare l'offset totale: device_offset[f] + bias[ear][f].
    Espone anche i metodi della store dispositivo per compatibilità UI.
    """
    def __init__(self, device_store: CalibrationStore, hp_store: HeadphoneCalibration):
        self._dev = device_store
        self._hp = hp_store

    # --- Offset combinato ---
    def get_total_offset(self, ear: str, freq_hz: int) -> float:
        return float(self._dev.get_offset(freq_hz)) + float(self._hp.get_bias_db(ear, freq_hz))

    @property
    def active_device(self) -> str | None:
        return getattr(self._dev, 'active_device', None)

    # --- Pass-through per UI dispositivo ---
    def has_profile_for(self, device_name: str) -> bool:
        return self._dev.has_profile_for(device_name)

    def set_active_device(self, device_name: str, create_if_missing: bool = False) -> None:
        self._dev.set_active_device(device_name, create_if_missing=create_if_missing)

    def load_profile(self, device_name: str) -> None:
        self._dev.load_profile(device_name)

    def reset_profile(self, device_name: str) -> None:
        self._dev.reset_profile(device_name)

    def get_map(self) -> Dict[int, float]:
        return self._dev.get_map()

    def get_offset(self, freq_hz: int) -> float:
        return self._dev.get_offset(freq_hz)

    def set_offset(self, freq_hz: int, offset_db: float) -> None:
        self._dev.set_offset(freq_hz, offset_db)

    def save(self) -> str:
        return self._dev.save()

    # --- API cuffie ---
    def set_headphone(self, hp_id: str):
        return self._hp.set_headphone(hp_id)

    def compute_bias_from_thresholds(self, measured: Dict[str, Dict[int, float]]) -> Dict[str, Dict[int, float]]:
        return self._hp.compute_bias_from_thresholds(measured)

    def set_bias_map(self, bias_map: Dict[str, Dict[int, float]]):
        self._hp.set_bias_map(bias_map)

    def save_headphone(self) -> str:
        return self._hp.save()
