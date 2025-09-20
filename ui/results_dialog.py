from __future__ import annotations
from typing import Dict, Any, List, Optional
import json

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QHBoxLayout,
)
from PySide6.QtCore import Qt

from ui.audiogram_view import AudiogramView
from results.browser import list_patient_exams


class ResultsDialog(QDialog):
    """Dialog che mostra lo storico delle audiometrie per un assistito."""

    def __init__(
        self,
        base_appdata: str,
        patient: Dict[str, Any],
        parent=None,
        exams: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Risultati audiometrie")
        self.resize(900, 600)
        self._base_appdata = base_appdata
        self._patient = patient
        self._exams = exams if exams is not None else list_patient_exams(base_appdata, str(patient.get('id', '')))

        layout = QVBoxLayout(self)
        header = QLabel(
            f"Assistito: {patient.get('cognome', '')} {patient.get('nome', '')} (ID {patient.get('id', '-')})"
        )
        layout.addWidget(header)

        body = QHBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addLayout(body)
        body.addWidget(self.list_widget, 1)

        self.graph = AudiogramView(self)
        body.addWidget(self.graph, 2)

        self.lbl_details = QLabel("Seleziona uno o piu esami per visualizzare l'overlay.")
        self.lbl_details.setWordWrap(True)
        layout.addWidget(self.lbl_details)

        for exam in self._exams:
            created = exam.get('created_at', 'sconosciuta')
            summary = exam.get('summary', '')
            text = f"{created} - {summary}".strip()
            item = QListWidgetItem(text or created)
            item.setData(Qt.UserRole, exam)
            self.list_widget.addItem(item)

        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self) -> None:
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            self.graph.clear_overlays()
            self.lbl_details.setText("Seleziona uno o piu esami per visualizzare l'overlay.")
            return
        overlays: List[Dict[str, Any]] = []
        details_lines: List[str] = []
        for item in selected_items:
            meta = item.data(Qt.UserRole)
            if not isinstance(meta, dict):
                continue
            path = meta.get('path')
            try:
                with open(path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            label = data.get('created_at', 'Esame')
            overlays.append({
                'label': label,
                'OD': data.get('OD', {}),
                'OS': data.get('OS', {}),
            })
            note = data.get('notes', '')
            if note:
                details_lines.append(f"{label} - Note: {note}")
        self.graph.set_overlays(overlays)
        self.lbl_details.setText('\n'.join(details_lines) or "Nessuna nota disponibile.")
