from __future__ import annotations
from typing import Optional, Dict, Any
import math
import threading

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None


class AudioEngine:
    def __init__(self) -> None:
        self.sample_rate = 48000
        self.profile: Optional[Dict[str, Any]] = None
        self.max_db_hl = 100.0
        self.output_device_index: Optional[int] = None
        self._stream: Optional[sd.OutputStream] = None if sd else None
        self._lock = threading.Lock()
        self.running = False
        self._phase = 0.0
        self._current_gain = 0.0
        self._target_gain = 0.0
        self._current_freq = 0.0
        self._current_ear = "OD"
        self._playing = False
        self._samples_since_start = 0
        self._auto_stop_seconds = 3.0
        self._channel_map: Dict[str, int] = {"OS": 0, "OD": 1}
        self._channel_count = 2

    def set_profile(self, profile: Dict[str, Any]) -> None:
        self.profile = profile
        self.max_db_hl = float(profile.get("max_db_hl", self.max_db_hl))
        self._apply_profile_settings(profile)

    def _apply_profile_settings(self, profile: Dict[str, Any]) -> None:
        device_info = profile.get("device") or {}
        sample_rate = device_info.get("sample_rate") or profile.get("sample_rate")
        if sample_rate is not None:
            try:
                self.sample_rate = int(sample_rate)
            except (TypeError, ValueError):
                pass
        channel_map = self._extract_channel_map(profile)
        if channel_map:
            self.set_channel_map(channel_map)

    def _extract_channel_map(self, profile: Dict[str, Any]) -> Dict[str, int]:
        def _from_container(container: Dict[str, Any]) -> Dict[str, int]:
            keys = ("channel_map", "channels_map", "channel_indices", "channel_roles")
            for key in keys:
                raw = container.get(key)
                if isinstance(raw, dict):
                    norm = self._normalise_channel_dict(raw)
                    if norm:
                        return norm
            left = container.get("left_channel_index")
            right = container.get("right_channel_index")
            mapping: Dict[str, int] = {}
            if left is not None:
                try:
                    mapping["OS"] = int(left)
                except (TypeError, ValueError):
                    pass
            if right is not None:
                try:
                    mapping["OD"] = int(right)
                except (TypeError, ValueError):
                    pass
            return mapping

        for container in (profile, profile.get("device") or {}, profile.get("headphones") or {}):
            if isinstance(container, dict):
                mapping = _from_container(container)
                if mapping:
                    return mapping
        return {}

    @staticmethod
    def _normalise_ear_label(label: Any) -> Optional[str]:
        text = str(label).strip().upper()
        aliases = {
            "R": "OD",
            "RIGHT": "OD",
            "DX": "OD",
            "OD": "OD",
            "EAR_R": "OD",
            "L": "OS",
            "LEFT": "OS",
            "SX": "OS",
            "OS": "OS",
            "EAR_L": "OS",
        }
        return aliases.get(text)

    def _normalise_channel_dict(self, data: Dict[Any, Any]) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for key, value in data.items():
            ear = self._normalise_ear_label(key)
            if ear is None:
                continue
            try:
                idx = int(value)
            except (TypeError, ValueError):
                continue
            if idx < 0:
                continue
            mapping[ear] = idx
        return mapping

    def set_channel_map(self, mapping: Dict[Any, Any]) -> None:
        normalised = self._normalise_channel_dict(mapping)
        if not normalised:
            return
        changed = False
        for ear, idx in normalised.items():
            if self._channel_map.get(ear) != idx:
                self._channel_map[ear] = idx
                changed = True
        if not changed:
            return
        new_count = max(self._channel_map.values()) + 1
        if new_count != self._channel_count:
            self._channel_count = max(1, new_count)
        self.shutdown_stream()

    def set_output_device(self, device_index: Optional[int]) -> None:
        idx = None
        if device_index is not None:
            try:
                idx = int(device_index)
            except (TypeError, ValueError):
                idx = None
        if idx != self.output_device_index:
            self.shutdown_stream()
            self.output_device_index = idx

    def play_tone(self, freq_hz: float, level_db_hl: float, ear: str) -> None:
        if sd is None:
            raise RuntimeError("sounddevice non disponibile: installa la dipendenza per riprodurre audio.")
        if self.profile is None:
            raise RuntimeError("Profilo di calibrazione non caricato.")
        ear_key = str(ear).strip().upper()
        amplitude = self._level_to_amplitude(ear_key, freq_hz, level_db_hl)
        if amplitude <= 0.0:
            raise ValueError("Calibrazione assente per la frequenza selezionata.")
        self._ensure_stream()
        with self._lock:
            self._current_freq = float(freq_hz)
            self._current_ear = ear_key
            self._target_gain = amplitude
            self._playing = True
            self.running = True
            self._samples_since_start = 0

    def stop(self, immediate: bool = False) -> None:
        with self._lock:
            self._playing = False
            if immediate:
                self._target_gain = 0.0
                self._current_gain = 0.0
                self.running = False
            else:
                self._target_gain = 0.0

    def shutdown_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            finally:
                self._stream = None
                with self._lock:
                    self._current_gain = 0.0
                    self._target_gain = 0.0
                    self._playing = False
                    self.running = False

    def _ensure_stream(self) -> None:
        if sd is None:
            return
        if self._stream is not None:
            return
        kwargs = {
            'samplerate': int(self.sample_rate),
            'channels': int(self._channel_count),
            'dtype': 'float32',
            'callback': self._callback,
            'blocksize': 256,
            'latency': 'low',
        }
        if self.output_device_index is not None:
            kwargs['device'] = self.output_device_index
        self._stream = sd.OutputStream(**kwargs)
        self._stream.start()

    def _callback(self, outdata, frames, _time, status) -> None:  # pragma: no cover
        if status:
            pass
        with self._lock:
            freq = self._current_freq
            ear = self._current_ear
            target_gain = self._target_gain
            current_gain = self._current_gain
            playing = self._playing
            samples_since_start = self._samples_since_start
        if freq <= 0 or (not playing and current_gain <= 1e-6 and target_gain <= 1e-6):
            outdata[:] = 0.0
            with self._lock:
                self._current_gain = 0.0
                self.running = False
            return
        phase = self._phase
        t = (np.arange(frames, dtype=np.float32) + phase) / float(self.sample_rate)
        wave = np.sin(2 * math.pi * freq * t)
        if abs(target_gain - current_gain) > 1e-6:
            step = (target_gain - current_gain) / max(frames, 1)
            gains = current_gain + step * np.arange(frames, dtype=np.float32)
            current_gain = float(gains[-1])
        else:
            gains = np.full(frames, current_gain, dtype=np.float32)
        buffer = np.zeros((frames, int(self._channel_count)), dtype=np.float32)
        channel = self._channel_map.get(ear)
        if channel is None:
            channel = self._channel_map.get("OD", 1 if self._channel_count > 1 else 0)
        channel = max(0, min(channel, self._channel_count - 1))
        buffer[:, channel] = wave * gains
        outdata[:] = buffer
        phase = (phase + frames) % self.sample_rate
        with self._lock:
            self._phase = phase
            self._current_gain = current_gain
            if playing:
                samples_since_start += frames
                self._samples_since_start = samples_since_start
                if self._auto_stop_seconds > 0:
                    max_samples = int(self.sample_rate * self._auto_stop_seconds)
                    if samples_since_start >= max_samples:
                        self._playing = False
                        self._target_gain = 0.0

    def _level_to_amplitude(self, ear: str, freq: float, level_db_hl: float) -> float:
        if not self.profile:
            return 0.0
        channels = self.profile.get("channels", {})
        channel_data = channels.get(ear, {})
        ref_dbfs = channel_data.get(int(freq))
        if ref_dbfs is None:
            ref_dbfs = channel_data.get(-1)
        if ref_dbfs is None:
            ref_dbfs = -40.0
        ref_dbfs = float(ref_dbfs)
        if ref_dbfs >= -5.0:
            ref_dbfs = -35.0
        level = float(max(-10.0, min(level_db_hl, self.max_db_hl)))
        target_dbfs = ref_dbfs + level
        target_dbfs = min(target_dbfs, -2.0)
        amplitude = 10 ** (target_dbfs / 20.0)
        return float(max(0.0, min(1.0, amplitude)))
