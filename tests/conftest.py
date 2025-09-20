from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Dict, List


def _install_stub() -> None:
    sd = ModuleType("sounddevice")

    @dataclass
    class _Defaults:
        device: tuple | None = (None, 0)
        samplerate: int | None = None
        channels: int | None = None
        dtype: str | None = None

    def play(data, samplerate, blocking: bool = False, **kwargs: Dict[str, Any]):
        return None

    def stop():
        return None

    def sleep(duration_ms):
        return None

    def query_devices() -> List[Dict[str, Any]]:
        return []

    def query_hostapis() -> List[Dict[str, Any]]:
        return []

    class OutputStream:
        def __init__(self, **kwargs: Any) -> None:
            self._callback = kwargs.get('callback')

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    sd.default = _Defaults()
    sd.play = play
    sd.stop = stop
    sd.sleep = sleep
    sd.query_devices = query_devices
    sd.query_hostapis = query_hostapis
    sd.OutputStream = OutputStream

    sys.modules['sounddevice'] = sd


try:
    if os.environ.get('AUDIO_FORCE_STUB'):
        raise ImportError
    import sounddevice  # noqa: F401
except Exception:
    _install_stub()
