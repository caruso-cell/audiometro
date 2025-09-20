from __future__ import annotations
import argparse
import sys
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def _parse_args(argv: list[str]) -> tuple[Optional[Dict[str, Any]], list[str]]:
    parser = argparse.ArgumentParser(description="Audiometria tonale manuale")
    parser.add_argument("--nome", help="Nome assistito")
    parser.add_argument("--cognome", help="Cognome assistito")
    parser.add_argument("--eta", type=int, help="Eta assistito")
    parser.add_argument("--id", dest="pid", help="ID assistito")
    known, unknown = parser.parse_known_args(argv)
    fields = [known.nome, known.cognome, known.eta, known.pid]
    if any(field is not None for field in fields):
        if None in fields:
            missing = []
            if known.nome is None:
                missing.append("--nome")
            if known.cognome is None:
                missing.append("--cognome")
            if known.eta is None:
                missing.append("--eta")
            if known.pid is None:
                missing.append("--id")
            parser.error(f"Parametri assistito incompleti: specifica anche {', '.join(missing)}")
        patient = {
            "nome": known.nome,
            "cognome": known.cognome,
            "eta": known.eta,
            "id": known.pid,
        }
    else:
        patient = None
    return patient, unknown


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
