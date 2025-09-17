from __future__ import annotations

import json
from pathlib import Path

import pytest

from audiometry_app.calibration_loader.profiles import (
    CalibrationManager,
    DeviceCalibrationFiles,
)


def test_copy_profile_persists_metadata_and_loads_immediately(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    source = tmp_path / "original_profile.cal"
    source.write_text("profile-data", encoding="utf-8")

    manager = CalibrationManager(storage)

    copied = manager.copy_profile_for_device("USB-Device #1", source, {"note": "test"})

    files = DeviceCalibrationFiles.for_device(storage, "USB-Device #1", copied.metadata["stored_filename"])
    assert files.profile_path.is_file()
    assert files.profile_path.read_text(encoding="utf-8") == "profile-data"

    metadata = json.loads(files.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_filename"] == "original_profile.cal"
    assert metadata["note"] == "test"

    loaded = manager.load_for_device("USB-Device #1")
    assert loaded is not None, "load_for_device should immediately return the copied profile"
    assert loaded.path == files.profile_path
    assert loaded.metadata["source_filename"] == "original_profile.cal"
    assert loaded.metadata["stored_filename"] == copied.metadata["stored_filename"]

