#!/usr/bin/env python3
"""Set or bump the application semantic version across build assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_version import read_version, write_version

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
INNO_VERSION_INCLUDE = Path('installer') / 'version.isi'
UPDATE_MANIFEST = Path('installer') / 'update_manifest.json'
DEFAULT_PLACEHOLDER_URL = 'https://example.com/audiometro/Audiometro_Setup_{version}.exe'


def _bump_version(base: str, bump: str) -> str:
    core = base.split('-', 1)[0].split('+', 1)[0]
    major, minor, patch = (int(part) for part in core.split('.'))
    if bump == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump == 'minor':
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def _write_inno_include(version: str) -> None:
    INNO_VERSION_INCLUDE.write_text(f'#define AppVersion "{version}"\n', encoding='utf-8')


def _load_previous_manifest() -> dict[str, object] | None:
    if not UPDATE_MANIFEST.exists():
        return None
    try:
        return json.loads(UPDATE_MANIFEST.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_download_url(version: str, explicit: str | None, previous: dict[str, object] | None) -> str:
    if explicit:
        return explicit
    if previous:
        url = previous.get('installer_url')
        if isinstance(url, str) and url:
            parts = urlsplit(url)
            name = f'Audiometro_Setup_{version}.exe'
            if parts.scheme and parts.netloc:
                base_path = parts.path.rsplit('/', 1)[0]
                prefix = f"{parts.scheme}://{parts.netloc}"
                if base_path:
                    prefix += base_path if base_path.endswith('/') else base_path + '/'
                else:
                    prefix += '/'
                return prefix + name
            if url.endswith('/'):
                return url + name
            return f"{url}/{name}"
    return DEFAULT_PLACEHOLDER_URL.format(version=version)


def _read_release_notes(args: argparse.Namespace) -> str:
    if args.notes and args.notes_file:
        raise SystemExit('Use either --notes or --notes-file, not both.')
    if args.notes_file:
        path = Path(args.notes_file)
        return path.read_text(encoding='utf-8').strip()
    if args.notes:
        return args.notes.strip()
    return ''


def _write_manifest(version: str, download_url: str, notes: str, size_bytes: int | None, published_at: str | None) -> None:
    filename = f'Audiometro_Setup_{version}.exe'
    payload = {
        'version': version,
        'installer_basename': filename,
        'installer_url': download_url,
        'release_notes': notes,
        'size_bytes': size_bytes,
        'published_at': published_at or datetime.now(timezone.utc).isoformat(),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'installer_relative_path': f'Output/{filename}',
        'build_relative_path': 'dist/Audiometro.exe',
    }
    UPDATE_MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', nargs='?', help='Explicit semantic version to set.')
    parser.add_argument('--bump', choices=('major', 'minor', 'patch'), help='Increment version based on the current one.')
    parser.add_argument('--dry-run', action='store_true', help='Show the planned changes without writing files.')
    parser.add_argument('--download-url', help='Absolute URL for the installer binary in the manifest.')
    parser.add_argument('--notes', help='Inline release notes for the manifest.')
    parser.add_argument('--notes-file', help='Path to a text file containing release notes.')
    parser.add_argument('--size-bytes', type=int, help='Size of the installer in bytes to publish.')
    parser.add_argument('--published-at', help='Override the publish timestamp (ISO 8601).')
    args = parser.parse_args()

    current = read_version()
    if not args.version and not args.bump:
        parser.error('Provide a target version or choose --bump mode.')
    if args.version and args.bump:
        parser.error('Choose either an explicit version or --bump, not both.')

    target = args.version.strip() if args.version else _bump_version(current, args.bump or 'patch')
    if not SEMVER_RE.fullmatch(target):
        parser.error(f'Invalid semantic version: {target!r}')

    notes = _read_release_notes(args)
    previous_manifest = _load_previous_manifest()
    download_url = _resolve_download_url(target, args.download_url, previous_manifest)

    print(f'Current version: {current}')
    print(f'Target version:  {target}')
    print(f'Download URL:    {download_url}')
    if notes:
        print('Release notes provided.')
    if args.dry_run:
        print('Dry run enabled; no files have been modified.')
        return 0

    write_version(target)
    _write_inno_include(target)
    _write_manifest(target, download_url, notes, args.size_bytes, args.published_at)
    print(f'Updated {INNO_VERSION_INCLUDE} and {UPDATE_MANIFEST}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
