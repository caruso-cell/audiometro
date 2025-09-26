#!/usr/bin/env python3
"""Upload release artifacts to an FTP or FTPS server."""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path
from typing import Dict, Iterable, List, Optional

CONFIG_DEFAULT = Path('config/ftp_upload.json')


def _load_config(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f'Config {path} non leggibile: {exc}')
    if not isinstance(data, dict):
        raise SystemExit(f'Config {path} deve essere un oggetto JSON.')
    return data


def _resolve_password(config: Dict[str, object], explicit: Optional[str], env_name: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    if env_name:
        value = os.getenv(env_name)
        if value:
            return value
    cfg_env = config.get('password_env')
    if isinstance(cfg_env, str):
        value = os.getenv(cfg_env)
        if value:
            return value
    password = config.get('password')
    if isinstance(password, str) and password:
        return password
    return None


def _ensure_remote_path(ftp: FTP, remote_dir: str) -> None:
    if not remote_dir or remote_dir == '.':
        return
    parts: Iterable[str] = [segment for segment in remote_dir.replace('\\', '/').split('/') if segment]
    for part in parts:
        try:
            ftp.mkd(part)
        except error_perm as exc:
            if not str(exc).startswith('550'):
                raise
        ftp.cwd(part)


def _upload_file(ftp: FTP, local_path: Path) -> None:
    with local_path.open('rb') as handle:
        ftp.storbinary(f'STOR {local_path.name}', handle, blocksize=64 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(CONFIG_DEFAULT), help='File JSON con i parametri di upload (default config/ftp_upload.json).')
    parser.add_argument('--host', help='Hostname o IP del server FTP.')
    parser.add_argument('--port', type=int, help='Porta TCP (default 21 oppure 990 per FTPS).')
    parser.add_argument('--user', help='Username FTP.')
    parser.add_argument('--password', help='Password FTP (sconsigliato: meglio config/env).')
    parser.add_argument('--password-env', help='Nome variabile ambiente contenente la password.')
    parser.add_argument('--remote-dir', default='.', help='Cartella remota dove caricare i file.')
    parser.add_argument('--use-tls', action='store_true', help='Abilita FTPS (FTP esplicito su TLS).')
    parser.add_argument('paths', nargs='*', help='File locali da caricare.')
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else CONFIG_DEFAULT
    config = _load_config(config_path)

    host = args.host or config.get('host')
    if not host:
        parser.error('Specificare --host oppure impostare "host" nel file di config.')

    use_tls = bool(args.use_tls or config.get('use_tls'))

    port = args.port or config.get('port')
    if port is None:
        port = 990 if use_tls else 21
    else:
        port = int(port)

    user = args.user or config.get('user')
    if not user:
        parser.error('Specificare --user oppure impostare "user" nel file di config.')

    password = _resolve_password(config, args.password, args.password_env)
    if not password:
        prompt_flag = config.get('prompt_password', True)
        if prompt_flag:
            password = getpass.getpass('FTP password: ')
        else:
            parser.error('Password non disponibile. Fornire password via CLI, env o config.')

    remote_dir = args.remote_dir
    if remote_dir == '.' and isinstance(config.get('remote_dir'), str):
        remote_dir = str(config['remote_dir'])

    paths: List[str] = list(args.paths)
    if not paths:
        cfg_paths = config.get('paths')
        if isinstance(cfg_paths, list):
            paths = [str(p) for p in cfg_paths]
    if not paths:
        parser.error('Indicare almeno un file da caricare (CLI o campo "paths" nel config).')

    local_paths = [Path(p).resolve() for p in paths]
    missing = [str(p) for p in local_paths if not p.is_file()]
    if missing:
        raise SystemExit(f'File inesistenti: {", ".join(missing)}')

    ftp_cls = FTP_TLS if use_tls else FTP

    print(f'Connessione a {host}:{port} (TLS={"si" if use_tls else "no"})...')
    with ftp_cls() as ftp:
        ftp.connect(host, port)
        if use_tls:
            assert isinstance(ftp, FTP_TLS)
            ftp.auth()
            ftp.prot_p()
        ftp.login(user, password)
        print('Login eseguito.')

        original_cwd = ftp.pwd()
        try:
            _ensure_remote_path(ftp, remote_dir)
            for path in local_paths:
                print(f'Upload di {path.name}...')
                _upload_file(ftp, path)
                print('  ok')
        finally:
            ftp.cwd(original_cwd)
        ftp.quit()
    print('Completato.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

