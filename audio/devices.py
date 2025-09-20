from __future__ import annotations
from typing import List, Dict

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - opzionale
    sd = None


def list_output_devices() -> List[Dict[str, object]]:
    """Elenca i dispositivi audio di uscita disponibili."""
    devices: List[Dict[str, object]] = []
    if sd is None:
        return devices

    try:
        default_output = sd.default.device[1]
    except Exception:
        default_output = None

    try:
        hostapis = sd.query_hostapis()
    except Exception:
        hostapis = []

    for idx, info in enumerate(sd.query_devices()):
        if info.get("max_output_channels", 0) <= 0:
            continue
        hostapi_idx = info.get("hostapi")
        host_name = hostapis[hostapi_idx]["name"] if hostapis and hostapi_idx is not None else ""
        wasapi_id = info.get("name", f"device-{idx}")
        if host_name and "wasapi" in host_name.lower():
            wasapi_id = info.get("name", wasapi_id)
        devices.append(
            {
                "name": info.get("name", f"Dispositivo {idx}"),
                "wasapi_id": wasapi_id,
                "sample_rate": info.get("default_samplerate", 48000),
                "index": idx,
                "is_default": default_output == idx,
            }
        )
    return devices
