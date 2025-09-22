from __future__ import annotations
from typing import Iterable, List, Dict, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QScrollArea
from PySide6.QtCore import Signal

ENVIRONMENT_OPTIONS: List[Dict[str, Any]] = [
    {"code": 1, "label": "Casa in silenzio"},
    {"code": 2, "label": "Casa con televisione o radio accese"},
    {"code": 3, "label": "Conversazioni familiari in salotto o cucina"},
    {"code": 4, "label": "Ristorante / bar / caffetteria"},
    {"code": 5, "label": "Riunioni di lavoro o di condominio"},
    {"code": 6, "label": "Cene con amici o familiari numerosi"},
    {"code": 7, "label": "Feste o ricevimenti"},
    {"code": 8, "label": "Automobile"},
    {"code": 9, "label": "Autobus / treno"},
    {"code": 10, "label": "Aereo"},
    {"code": 11, "label": "Chiesa / luogo di culto"},
    {"code": 12, "label": "Cinema / teatro"},
    {"code": 13, "label": "Concerti / ascolto di musica"},
    {"code": 14, "label": "Eventi sportivi (palazzetti, stadi)"},
    {"code": 15, "label": "Passeggiate all'aperto (parco, montagna, mare)"},
    {"code": 16, "label": "Traffico cittadino (strada, incroci, piazze affollate)"},
    {"code": 17, "label": "Mercati o centri commerciali"},
    {"code": 18, "label": "Ufficio (colleghi, telefoni, PC)"},
    {"code": 19, "label": "Scuola / aula universitaria"},
    {"code": 20, "label": "Fabbrica / officina (macchinari, rumori continui)"},
]


class EnvironmentChecklist(QWidget):
    """Elenco di ambienti selezionabili con checkbox numerate."""

    selectionChanged = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Ambienti di ascolto")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(4, 4, 4, 4)
        host_layout.setSpacing(2)

        self._check_pairs: List[tuple[Dict[str, Any], QCheckBox]] = []
        self._block = False

        for entry in ENVIRONMENT_OPTIONS:
            text = f"{entry['code']}. {entry['label']}"
            checkbox = QCheckBox(text)
            checkbox.stateChanged.connect(self._on_state_changed)
            self._check_pairs.append((entry, checkbox))
            host_layout.addWidget(checkbox)
        host_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        scroll.setFixedHeight(260)
        layout.addWidget(scroll)

    def selected(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for entry, checkbox in self._check_pairs:
            if checkbox.isChecked():
                items.append({"code": entry["code"], "description": entry["label"]})
        return items

    def set_selected(self, values: Iterable[Any] | None) -> None:
        codes = set()
        if values:
            for value in values:
                code = None
                if isinstance(value, dict):
                    code = value.get("code")
                else:
                    try:
                        code = int(value)
                    except (TypeError, ValueError):
                        code = None
                if code is not None:
                    try:
                        codes.add(int(code))
                    except (TypeError, ValueError):
                        continue
        self._block = True
        for entry, checkbox in self._check_pairs:
            checkbox.setChecked(entry["code"] in codes)
        self._block = False
        self._emit_selection()

    def set_enabled(self, enabled: bool) -> None:
        for _, checkbox in self._check_pairs:
            checkbox.setEnabled(enabled)

    def clear(self) -> None:
        self.set_selected([])

    def _on_state_changed(self) -> None:
        if not self._block:
            self._emit_selection()

    def _emit_selection(self) -> None:
        self.selectionChanged.emit(self.selected())
