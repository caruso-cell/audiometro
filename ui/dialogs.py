from __future__ import annotations
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDialogButtonBox,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
)
from PySide6.QtCore import Qt

import uuid
from datetime import datetime


class NewPatientDialog(QDialog):
    """Dialog per creare un nuovo assistito. Restituisce dict con nome/cognome/eta/id."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuovo assistito")
        self._result: Optional[Dict[str, object]] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._ed_nome = QLineEdit()
        self._ed_cognome = QLineEdit()
        self._ed_id = QLineEdit()
        self._ed_id.setReadOnly(True)
        self._ed_id.setText(self._generate_patient_id())
        self._ed_id.setCursorPosition(0)
        self._ed_id.setToolTip('Generato automaticamente')
        self._sp_eta = QSpinBox()
        self._sp_eta.setRange(0, 120)
        self._sp_eta.setValue(40)
        form.addRow("Nome", self._ed_nome)
        form.addRow("Cognome", self._ed_cognome)
        form.addRow("Eta", self._sp_eta)
        form.addRow("ID assistito", self._ed_id)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _generate_patient_id(self) -> str:
        stamp = datetime.now().strftime('%Y%m%d')
        suffix = uuid.uuid4().hex[:6].upper()
        return f'PAT-{stamp}-{suffix}'

    def _on_accept(self) -> None:
        nome = self._ed_nome.text().strip()
        cognome = self._ed_cognome.text().strip()
        patient_id = self._ed_id.text().strip()
        eta = int(self._sp_eta.value())
        if not nome or not cognome:
            QMessageBox.warning(self, "Campi mancanti", "Compila nome e cognome.")
            return
        if not patient_id:
            patient_id = self._generate_patient_id()
            self._ed_id.setText(patient_id)
        self._result = {
            "nome": nome,
            "cognome": cognome,
            "id": patient_id,
            "eta": eta,
            "ambienti": [],
        }
        self.accept()

    def get_result(self) -> Optional[Dict[str, object]]:
        return self._result


class OpenPatientDialog(QDialog):
    """Dialog per selezionare un assistito locale esistente."""

    def __init__(self, patients: List[Dict[str, object]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apri assistito")
        self._selected: Optional[Dict[str, object]] = None

        layout = QVBoxLayout(self)
        if not patients:
            layout.addWidget(QLabel("Nessun assistito salvato."))
        self._list = QListWidget()
        for patient in patients:
            label = f"{patient.get('cognome', '')} {patient.get('nome', '')} ({patient.get('id', '')})"
            item = QListWidgetItem(label.strip())
            item.setData(Qt.UserRole, patient)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(lambda _: self._on_accept())
        layout.addWidget(self._list)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._list.currentItemChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, current: QListWidgetItem, _: QListWidgetItem) -> None:
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(current is not None)

    def _on_accept(self) -> None:
        item = self._list.currentItem()
        if item is None:
            QMessageBox.information(self, "Seleziona assistito", "Scegli un assistito dall'elenco.")
            return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            QMessageBox.warning(self, "Errore", "Elemento non valido.")
            return
        self._selected = data
        self.accept()

    def get_selected(self) -> Optional[Dict[str, object]]:
        return self._selected
