"""Test stub for the external ``sounddevice`` dependency.

The real project depends on the PortAudio binary which is unavailable in the
execution environment.  This lightweight stub provides the minimal surface
required by the imported modules so that the test-suite can run without
attempting to access the real audio backend.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Defaults:
    samplerate: int | None = None
    channels: int | None = None
    dtype: str | None = None


default = _Defaults()


def play(data, samplerate, blocking=False):  # noqa: D401
    """Pretend to play *data* at *samplerate*; no-op for tests."""


def stop():  # noqa: D401
    """Pretend to stop playback; no-op for tests."""


def sleep(duration_ms):  # noqa: D401
    """Pretend to sleep for *duration_ms* milliseconds; no-op for tests."""

