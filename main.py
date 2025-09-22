from __future__ import annotations
import argparse
import sys
from urllib.parse import urlparse, parse_qs, unquote
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def _parse_args(argv: list[str]) -> tuple[Optional[Dict[str, Any]], list[str]]:
    parser = argparse.ArgumentParser(description="Audiometria tonale manuale")
    parser.add_argument("--nome", help="Nome assistito")
    parser.add_argument("--cognome", help="Cognome assistito")
    parser.add_argument("--eta", type=int, help="Eta assistito")
    parser.add_argument("--id", dest="pid", help="ID assistito")

    expected_keys = ("nome", "cognome", "eta", "id")
    url_fields: dict[str, str] = {}

    cleaned: list[str] = []
    passthrough: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        parsed = None
        if '://' in token:
            try:
                parsed = urlparse(token)
            except ValueError:
                parsed = None
        if parsed and parsed.scheme and parsed.scheme.lower() == 'audiometria':
            query = parse_qs(parsed.query)
            for key in expected_keys:
                values = query.get(key)
                if values:
                    url_fields.setdefault(key, values[0])
            path = parsed.path.strip('/')
            if path:
                for segment in path.split('/'):
                    if '=' in segment:
                        key, value = segment.split('=', 1)
                        if key in expected_keys and value:
                            url_fields.setdefault(key, unquote(value))
            fragment = parsed.fragment.strip()
            if fragment:
                for part in fragment.split('&'):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        if key in expected_keys and value:
                            url_fields.setdefault(key, unquote(value))
            i += 1
            continue
        if token.startswith("--"):
            cleaned.append(token)
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                cleaned.append(argv[i + 1])
                i += 1
        else:
            passthrough.append(token)
        i += 1

    known, unknown = parser.parse_known_args(cleaned)
    passthrough.extend(unknown)

    patient_data: dict[str, Any] = {}
    cli_values = {
        "nome": known.nome,
        "cognome": known.cognome,
        "eta": known.eta,
        "id": known.pid,
    }
    for key in expected_keys:
        value = cli_values.get(key)
        if value is None:
            value = url_fields.get(key)
            if value is not None:
                if key == "eta":
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        parser.error("Valore di --eta non valido nell'URL.")
        if value is not None:
            patient_data[key] = value

    if patient_data:
        missing = [key for key in expected_keys if key not in patient_data]
        if missing:
            parser.error(f"Parametri assistito incompleti: specifica anche {', '.join('--' + m for m in missing)}")
        patient = {
            "nome": patient_data["nome"],
            "cognome": patient_data["cognome"],
            "eta": int(patient_data["eta"]),
            "id": patient_data["id"],
        }
    else:
        patient = None
    return patient, passthrough


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv if argv is None else argv
    patient, passthrough = _parse_args(args[1:])
    qt_args = [args[0], *passthrough]
    app = QApplication(qt_args)
    win = MainWindow(cli_patient=patient)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
