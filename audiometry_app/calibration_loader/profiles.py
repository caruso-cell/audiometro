"""Utilities for managing calibration profiles stored on disk.

This module tracks calibration profiles associated with audio devices.
Each profile is stored in a device specific directory alongside a
metadata file that keeps provenance information about the source profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Optional

DEFAULT_PROFILE_FILENAME = "profile.calibration"
METADATA_FILENAME = "metadata.json"


def _sanitize_device_id(device_id: str) -> str:
    """Return a filesystem friendly representation for *device_id*.

    Path separators and characters outside ``[-_.A-Za-z0-9]`` are replaced
    with an underscore so that the value can be safely used as a directory
    name on most filesystems. Collapsing repeated underscores keeps
    the resulting directory readable.
    """

    safe = re.sub(r"[^-_.A-Za-z0-9]+", "_", device_id.strip())
    safe = safe.strip("._") or "device"
    return re.sub(r"__+", "_", safe)


@dataclass(frozen=True)
class DeviceCalibrationFiles:
    """Represents the calibration files for a single device."""

    root_dir: Path
    device_id: str
    stored_filename: Optional[str] = None

    @property
    def device_dir(self) -> Path:
        return self.root_dir / _sanitize_device_id(self.device_id)

    @property
    def metadata_path(self) -> Path:
        return self.device_dir / METADATA_FILENAME

    @property
    def profile_path(self) -> Path:
        filename = self.stored_filename or DEFAULT_PROFILE_FILENAME
        return self.device_dir / filename

    @classmethod
    def for_device(
        cls, root_dir: os.PathLike[str] | str, device_id: str, stored_filename: str | None = None
    ) -> "DeviceCalibrationFiles":
        return cls(Path(root_dir), device_id, stored_filename)

    def ensure_directory(self) -> None:
        self.device_dir.mkdir(parents=True, exist_ok=True)

    def read_metadata(self) -> Dict[str, Any]:
        if not self.metadata_path.is_file():
            return {}
        with self.metadata_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def write_metadata(self, metadata: Dict[str, Any]) -> None:
        self.ensure_directory()
        with self.metadata_path.open("w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, sort_keys=True)


@dataclass
class CalibrationProfile:
    """Loaded calibration profile for a device."""

    device_id: str
    path: Path
    metadata: Dict[str, Any]


class CalibrationManager:
    """Manage calibration profile storage and retrieval."""

    def __init__(self, storage_dir: os.PathLike[str] | str):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def copy_profile_for_device(
        self,
        device_id: str,
        profile_path: os.PathLike[str] | str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> CalibrationProfile:
        """Copy *profile_path* into the managed storage for *device_id*.

        The profile is copied (preserving timestamps) into the location
        returned by :meth:`DeviceCalibrationFiles.for_device().profile_path`.
        Metadata for the device is updated with provenance information so the
        original filename is available even though the stored file name may be
        normalised.  The resulting :class:`CalibrationProfile` is returned so
        callers can use it immediately without reloading from disk.
        """

        source = Path(profile_path)
        if not source.is_file():
            raise FileNotFoundError(source)

        stored_filename = f"profile{source.suffix}" if source.suffix else DEFAULT_PROFILE_FILENAME
        files = DeviceCalibrationFiles.for_device(self._storage_dir, device_id, stored_filename)
        files.ensure_directory()

        shutil.copy2(source, files.profile_path)

        metadata = files.read_metadata()
        metadata.update(extra_metadata or {})
        metadata.update(
            {
                "device_id": device_id,
                "stored_filename": stored_filename,
                "source_filename": source.name,
                "copied_from": str(source.resolve()),
                "copied_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        files.write_metadata(metadata)
        return CalibrationProfile(device_id, files.profile_path, metadata)

    def load_for_device(self, device_id: str) -> Optional[CalibrationProfile]:
        files = DeviceCalibrationFiles.for_device(self._storage_dir, device_id)
        metadata = files.read_metadata()
        if not metadata:
            return None
        stored_filename = metadata.get("stored_filename")
        files = DeviceCalibrationFiles.for_device(self._storage_dir, device_id, stored_filename)
        profile_path = files.profile_path
        if not profile_path.is_file():
            return None
        return CalibrationProfile(device_id, profile_path, metadata)

