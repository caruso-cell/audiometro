#!/usr/bin/env python3
"""Automatizza bump versione, build e pubblicazione su FTP per Audiometro."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_version import read_version  # noqa: E402

DEFAULT_DOWNLOAD_URL = (
    "https://www.audiomedicatrentina.it/software/audiometro/"
    "Audiometro_Setup_{version}.exe"
)
DEFAULT_BUMP = 'patch'
MAX_NOTES_LENGTH = 1000


def _bump_version(base: str, bump: str) -> str:
    major, minor, patch = (int(part) for part in base.split('.', 3)[:3])
    if bump == 'major':
        return f"{major + 1}.0.0"
    if bump == 'minor':
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _run(cmd: List[str], *, cwd: Optional[Path] = None) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def _resolve_iscc(path_hint: Optional[str]) -> str:
    if path_hint:
        candidate = Path(path_hint)
        if candidate.exists():
            return str(candidate)
        exe_in_path = shutil.which(path_hint)
        if exe_in_path:
            return exe_in_path
    candidates: List[Path] = []
    for env_key in ('ProgramFiles(x86)', 'ProgramFiles'):
        base = os.environ.get(env_key)
        if base:
            candidates.append(Path(base) / 'Inno Setup 6' / 'ISCC.exe')
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return path_hint or 'iscc'


def _collect_auto_notes(version: str) -> str:
    summary_lines: List[str] = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    summary_lines.append(f"Versione {version} pubblicata il {timestamp}.")
    summary_lines.append('Novita:')
    summary_lines.append('- Aggiornamenti recenti al codice base (vedi changelog).')
    summary_lines.append('- Migliorata gestione auto-update con installazione automatica.')
    summary_lines.append('- Ripristino automatico del paziente e della cuffia dopo l\'aggiornamento.')

    try:
        result = subprocess.run(
            ['git', 'log', '-3', '--pretty=format:%h %s'],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        git_summary = result.stdout.strip()
        if git_summary:
            summary_lines.append('Ultime commit:\n' + git_summary)
    except Exception:
        pass

    notes = '\n'.join(summary_lines).strip()
    if len(notes) > MAX_NOTES_LENGTH:
        notes = notes[: MAX_NOTES_LENGTH - 3].rstrip() + '...'
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', help='Versione esplicita da impostare (es. 1.10.0).')
    parser.add_argument('--bump', choices=('major', 'minor', 'patch'), help='Incrementa semver attuale (default patch).')
    parser.add_argument('--notes', help='Note di rilascio testuali da includere nel manifest.')
    parser.add_argument('--notes-file', help='File di testo con le note di rilascio.')
    parser.add_argument('--size-bytes', type=int, help='Dimensione installer da riportare nel manifest.')
    parser.add_argument('--published-at', help='Timestamp ISO8601 da usare nel manifest.')
    parser.add_argument('--download-url', help="URL completo dell'installer; default basato sul dominio Audiomedicatrentina.")
    parser.add_argument('--pyinstaller-extra', nargs=argparse.REMAINDER, help='Argomenti extra da passare a PyInstaller.')
    parser.add_argument('--iscc-path', help='Percorso di ISCC.exe (default prova a trovarlo automaticamente).')
    parser.add_argument('--skip-build', action='store_true', help='Salta PyInstaller (usa solo se dist/Audiometro.exe è già aggiornato).')
    parser.add_argument('--skip-installer', action='store_true', help='Salta compilazione Inno Setup.')
    parser.add_argument('--skip-upload', action='store_true', help='Non esegue upload FTP finale.')
    parser.add_argument('--upload-config', help='Config JSON personalizzato per upload_release.py. Default config/ftp_upload.json.')
    parser.add_argument('--filezilla', help='Percorso alternativo FileZilla.xml da usare per upload.')
    parser.add_argument('--server-name', help='Nome profilo FileZilla da selezionare.')
    args = parser.parse_args()

    current = read_version()
    if args.version:
        target_version = args.version.strip()
        bump_used = None
    else:
        bump_used = args.bump or DEFAULT_BUMP
        target_version = _bump_version(current, bump_used)

    download_url = args.download_url or DEFAULT_DOWNLOAD_URL.format(version=target_version)
    print(f"Versione corrente: {current}")
    if bump_used:
        print(f"Incremento:      {bump_used}")
    print(f"Versione target:  {target_version}")
    print(f"Download URL:     {download_url}")

    notes_args: List[str] = []
    temp_notes_path: Optional[Path] = None
    if args.notes:
        notes_text = args.notes.strip()
        if len(notes_text) > MAX_NOTES_LENGTH:
            notes_text = notes_text[: MAX_NOTES_LENGTH - 3].rstrip() + '...'
        notes_args = ['--notes', notes_text]
    elif args.notes_file:
        notes_args = ['--notes-file', args.notes_file]
    else:
        auto_notes = _collect_auto_notes(target_version)
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as handle:
            handle.write(auto_notes)
            temp_notes_path = Path(handle.name)
        notes_args = ['--notes-file', str(temp_notes_path)]

    try:
        set_version_cmd: List[str] = [sys.executable, str(ROOT / 'tools' / 'set_version.py'), target_version, '--download-url', download_url]
        set_version_cmd.extend(notes_args)
        if args.size_bytes is not None:
            set_version_cmd += ['--size-bytes', str(args.size_bytes)]
        if args.published_at:
            set_version_cmd += ['--published-at', args.published_at]
        _run(set_version_cmd, cwd=ROOT)

        if not args.skip_build:
            pyinstaller_cmd: List[str] = [sys.executable, '-m', 'PyInstaller', 'Audiometro.spec']
            if args.pyinstaller_extra:
                pyinstaller_cmd.extend(args.pyinstaller_extra)
            _run(pyinstaller_cmd, cwd=ROOT)
        else:
            print('[info] Build PyInstaller saltata per richiesta utente.')

        installer_output = ROOT / 'installer' / 'Output'
        setup_path = installer_output / f'Audiometro_Setup_{target_version}.exe'

        if not args.skip_installer:
            iscc_exe = _resolve_iscc(args.iscc_path)
            print(f'[info] Uso Inno Setup compiler: {iscc_exe}')
            _run([iscc_exe, str(ROOT / 'installer' / 'SETUP.ISS')], cwd=ROOT)
            if not setup_path.exists():
                raise SystemExit(f'Installer atteso non trovato: {setup_path}')
            if args.size_bytes is None and setup_path.exists():
                size = setup_path.stat().st_size
                print(f'[info] Aggiorno manifest con size-bytes={size}')
                size_cmd = [sys.executable, str(ROOT / 'tools' / 'set_version.py'), target_version, '--download-url', download_url, '--size-bytes', str(size)]
                size_cmd.extend(notes_args)
                if args.published_at:
                    size_cmd += ['--published-at', args.published_at]
                _run(size_cmd, cwd=ROOT)
        else:
            print('[info] Compilazione Inno Setup saltata per richiesta utente.')
            if not setup_path.exists():
                print("[warning] L'installer preesistente non è stato verificato.")

        manifest_path = ROOT / 'installer' / 'update_manifest.json'
        if not manifest_path.exists():
            raise SystemExit('Manifest mancante. set_version.py non ha generato update_manifest.json?')

        if not args.skip_upload:
            upload_cmd: List[str] = [sys.executable, str(ROOT / 'tools' / 'upload_release.py')]
            if args.upload_config:
                upload_cmd += ['--config', args.upload_config]
            if args.filezilla:
                upload_cmd += ['--filezilla', args.filezilla]
            if args.server_name:
                upload_cmd += ['--server-name', args.server_name]
            upload_cmd.append(str(setup_path))
            upload_cmd.append(str(manifest_path))
            _run(upload_cmd, cwd=ROOT)
        else:
            print('[info] Upload FTP saltato per richiesta utente.')

        ts = datetime.now().isoformat(timespec='seconds')
        print(f'Rilascio completato alle {ts}.')
        print('- dist/Audiometro.exe')
        print(f'- {setup_path}')
        print(f'- {manifest_path}')
    finally:
        if temp_notes_path and temp_notes_path.exists():
            temp_notes_path.unlink(missing_ok=True)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())


