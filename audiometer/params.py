"""
Parameter reader for launching via custom protocol or CLI.
Accepted keys (querystring or CLI): nome, cognome, eta, rowid.
Examples:
  screening://start?nome=Mario&cognome=Rossi&eta=45&rowid=PZ123
  --nome Mario --cognome Rossi --eta 45 --rowid PZ123
Fallback returns demo values if nothing is provided.
"""

from __future__ import annotations
import sys
from urllib.parse import urlparse, parse_qs, unquote_plus
from datetime import date


def _parse_argv(argv: list[str]) -> dict:
    if not argv:
        return {}
    first = argv[0]
    # screening:// URL or compact "key=value&..."
    if first.startswith('screening://'):
        parsed = urlparse(first)
        q = parse_qs(parsed.query)
        g = lambda k: unquote_plus(q.get(k, [''])[0])
        return {
            'nome': g('nome') or '',
            'cognome': g('cognome') or '',
            'eta': g('eta') or '',
            'rowid': g('rowid') or '',
        }
    if ('=' in first) and ('&' in first) and ('nome=' in first or 'rowid=' in first):
        fake = 'screening://start?' + first
        return _parse_argv([fake])
    # CLI style: --nome --cognome --eta --rowid
    out = {}
    it = iter(argv)
    for tok in it:
        if tok.startswith('--'):
            key = tok[2:].lower()
            try:
                val = next(it)
            except StopIteration:
                val = ''
            out[key] = val
    return out


def _derive_birth_date_from_age(age_str: str | int) -> str | None:
    try:
        age = int(age_str)
        today = date.today()
        year = max(1900, today.year - age)
        # Use mid-year to avoid edge-cases
        return f"{year}-06-30"
    except Exception:
        return None


def get_patient_params() -> dict:
    args = _parse_argv(sys.argv[1:])
    nome = (args.get('nome') or '').strip()
    cognome = (args.get('cognome') or '').strip()
    rowid = (args.get('rowid') or '').strip() or (args.get('id') or '').strip()
    eta = (args.get('eta') or '').strip()

    # Default demo values if nothing provided
    if not (nome or cognome or rowid or eta):
        return {"nome": "peppino", "cognome": "campione", "id": "12"}

    patient = {
        'nome': nome,
        'cognome': cognome,
        'id': rowid or 'PZ0000',
    }
    if eta:
        patient['eta'] = eta
        bd = _derive_birth_date_from_age(eta)
        if bd:
            patient.setdefault('birth_date', bd)
    return patient
