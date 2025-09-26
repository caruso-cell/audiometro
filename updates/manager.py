from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlsplit
from urllib.request import urlopen

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from config.updates import (
    CHECK_INTERVAL_DAYS,
    DEFAULT_MANIFEST_URL,
    DOWNLOAD_TIMEOUT_SECONDS,
)
from project_version import __version__, compare_versions


@dataclass
class UpdateManifest:
    version: str
    installer_url: str
    installer_basename: Optional[str] = None
    release_notes: str = ''
    size_bytes: Optional[int] = None
    published_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdateManifest":
        version = data.get('version')
        installer_url = data.get('installer_url')
        if not version or not installer_url:
            raise ValueError('Manifest missing required fields: version/installer_url')
        return cls(
            version=version,
            installer_url=installer_url,
            installer_basename=data.get('installer_basename') or data.get('installer_filename'),
            release_notes=data.get('release_notes', ''),
            size_bytes=data.get('size_bytes'),
            published_at=data.get('published_at'),
        )

    def filename(self) -> str:
        if self.installer_basename:
            return self.installer_basename
        path = urlsplit(self.installer_url).path
        name = os.path.basename(path)
        return name or f"Audiometro_Setup_{self.version}.exe"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['installer_filename'] = self.filename()
        return payload


class _ManifestFetchThread(QThread):
    finished = Signal(object, object)

    def __init__(self, url: str, timeout: int) -> None:
        super().__init__()
        self._url = url
        self._timeout = timeout

    def run(self) -> None:  # type: ignore[override]
        try:
            with urlopen(self._url, timeout=self._timeout) as response:
                data = response.read().decode('utf-8')
            manifest = json.loads(data)
        except Exception as exc:  # pragma: no cover - network failure path
            self.finished.emit(None, str(exc))
            return
        self.finished.emit(manifest, None)


class _DownloadThread(QThread):
    progress = Signal(int, int)
    finished = Signal(object, object)

    def __init__(self, url: str, destination: Path, timeout: int) -> None:
        super().__init__()
        self._url = url
        self._destination = destination
        self._timeout = timeout

    def run(self) -> None:  # type: ignore[override]
        tmp_path = self._destination.with_suffix(self._destination.suffix + '.part')
        received = 0
        total = -1
        try:
            with urlopen(self._url, timeout=self._timeout) as response:
                length = response.headers.get('Content-Length')
                if length:
                    try:
                        total = int(length)
                    except ValueError:
                        total = -1
                with open(tmp_path, 'wb') as handle:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        received += len(chunk)
                        self.progress.emit(received, total)
            os.replace(tmp_path, self._destination)
        except Exception as exc:  # pragma: no cover - network failure path
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            self.finished.emit(None, str(exc))
            return
        self.finished.emit(str(self._destination), None)


class UpdateManager(QObject):
    update_available = Signal(object)
    update_check_failed = Signal(str)
    update_checked = Signal(object)
    download_started = Signal(object)
    download_progress = Signal(int, int)
    download_failed = Signal(str)
    download_completed = Signal(str, object)

    def __init__(
        self,
        base_appdata: str,
        settings: dict[str, Any],
        save_callback: Callable[[], None],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._save_callback = save_callback
        self._updates_settings = self._settings.setdefault('updates', {})
        self._manifest_url = self._updates_settings.get('manifest_url') or DEFAULT_MANIFEST_URL
        if not self._updates_settings.get('manifest_url'):
            self._updates_settings['manifest_url'] = self._manifest_url
            self._save_callback()

        root_dir = Path(base_appdata) / 'Farmaudiometria' / 'updates'
        root_dir.mkdir(parents=True, exist_ok=True)
        self._download_dir = root_dir

        self._manifest_thread: Optional[_ManifestFetchThread] = None
        self._download_thread: Optional[_DownloadThread] = None
        self._current_manifest: Optional[UpdateManifest] = None

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------
    def schedule_weekly_check(self) -> None:
        QTimer.singleShot(2500, self._maybe_check)

    def force_check(self) -> None:
        self._start_manifest_fetch()

    def _maybe_check(self) -> None:
        if self._manifest_thread and self._manifest_thread.isRunning():
            return
        last_check_iso = self._updates_settings.get('last_check')
        due = True
        if last_check_iso:
            try:
                last_check = datetime.fromisoformat(last_check_iso)
            except ValueError:
                last_check = None
            if last_check is not None:
                now = datetime.now(timezone.utc)
                if now - last_check < timedelta(days=CHECK_INTERVAL_DAYS):
                    due = False
        if due:
            self._start_manifest_fetch()

    # ------------------------------------------------------------------
    # Manifest fetching
    # ------------------------------------------------------------------
    def _start_manifest_fetch(self) -> None:
        if self._manifest_thread and self._manifest_thread.isRunning():
            return
        self._manifest_thread = _ManifestFetchThread(self._manifest_url, DOWNLOAD_TIMEOUT_SECONDS)
        self._manifest_thread.finished.connect(self._on_manifest_finished)
        self._manifest_thread.start()

    def _on_manifest_finished(self, payload: object, error: object) -> None:
        if self._manifest_thread:
            self._manifest_thread.deleteLater()
            self._manifest_thread = None
        now = datetime.now(timezone.utc).isoformat()
        self._updates_settings['last_check'] = now
        self._save_callback()

        if error:
            self.update_check_failed.emit(str(error))
            self.update_checked.emit(None)
            return
        if not isinstance(payload, dict):
            self.update_check_failed.emit('Manifest response non valido')
            self.update_checked.emit(None)
            return
        try:
            manifest = UpdateManifest.from_dict(payload)
        except ValueError as exc:
            self.update_check_failed.emit(str(exc))
            self.update_checked.emit(None)
            return

        self._updates_settings['last_manifest'] = manifest.to_dict()
        self._save_callback()

        self.update_checked.emit(manifest)

        if compare_versions(manifest.version, __version__) > 0:
            self._current_manifest = manifest
            self.update_available.emit(manifest)

    # ------------------------------------------------------------------
    # Download handling
    # ------------------------------------------------------------------
    def download_update(self, manifest: UpdateManifest) -> None:
        if self._download_thread and self._download_thread.isRunning():
            return
        filename = manifest.filename()
        target_path = self._download_dir / filename
        self._download_thread = _DownloadThread(
            manifest.installer_url,
            target_path,
            DOWNLOAD_TIMEOUT_SECONDS,
        )
        self._download_thread.progress.connect(self.download_progress)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()
        self.download_started.emit(manifest)

    def _on_download_finished(self, result: object, error: object) -> None:
        if self._download_thread:
            self._download_thread.deleteLater()
            self._download_thread = None
        if error:
            self.download_failed.emit(str(error))
            return
        if not isinstance(result, str):
            self.download_failed.emit('Percorso download non valido')
            return
        manifest = self._current_manifest
        if not manifest:
            self.download_failed.emit('Manifest aggiornamento non disponibile')
            return
        pending = {
            'version': manifest.version,
            'path': result,
            'downloaded_at': datetime.now(timezone.utc).isoformat(),
            'manifest': manifest.to_dict(),
        }
        self._updates_settings['pending'] = pending
        self._save_callback()
        self.download_completed.emit(result, manifest)

    # ------------------------------------------------------------------
    # Launching installer & persistence helpers
    # ------------------------------------------------------------------
    def clear_pending(self) -> None:
        if 'pending' in self._updates_settings:
            self._updates_settings.pop('pending', None)
            self._save_callback()

    def pending_update(self) -> Optional[dict[str, Any]]:
        pending = self._updates_settings.get('pending')
        if not isinstance(pending, dict):
            return None
        path = pending.get('path')
        if not path or not Path(path).exists():
            return None
        return pending

    def launch_installer(self, path: str) -> bool:
        if not Path(path).exists():
            return False
        try:  # pragma: no cover - platform specific
            os.startfile(path)  # type: ignore[attr-defined]
        except AttributeError:
            import subprocess

            subprocess.Popen([path])
        except OSError:
            return False
        return True


__all__ = ['UpdateManager', 'UpdateManifest']






