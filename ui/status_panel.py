from __future__ import annotations
from typing import List, Dict, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, Signal


class HistoryPanel(QWidget):
    """Pannello laterale che mostra le audiometrie salvate e relative azioni."""

    examActivated = Signal()
    selectionChanged = Signal(list)
    exportPngRequested = Signal()
    exportPdfRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.label = QLabel("Audiometrie salvate")
        layout.addWidget(self.label)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.list_widget, 1)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.examActivated.emit())
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        self.notes_label = QLabel("Note selezionate")
        layout.addWidget(self.notes_label)

        self.notes_view = QTextEdit()
        self.notes_view.setReadOnly(True)
        self.notes_view.setMinimumHeight(120)
        layout.addWidget(self.notes_view)

        btn_layout = QHBoxLayout()
        self.btn_export_png = QPushButton("Esporta PNG")
        self.btn_export_pdf = QPushButton("Esporta PDF")
        btn_layout.addWidget(self.btn_export_png)
        btn_layout.addWidget(self.btn_export_pdf)
        layout.addLayout(btn_layout)

        self.btn_export_png.clicked.connect(self.exportPngRequested.emit)
        self.btn_export_pdf.clicked.connect(self.exportPdfRequested.emit)
        self.set_export_enabled(False)

    def set_exams(self, exams: List[Dict[str, Any]]) -> None:
        self.list_widget.clear()
        for exam in exams:
            created = exam.get('created_at', 'sconosciuta')
            summary = exam.get('summary', '')
            text = f"{created} - {summary}".strip()
            item = QListWidgetItem(text or created)
            item.setData(Qt.UserRole, exam)
            self.list_widget.addItem(item)
        self.set_details('')
        self.set_export_enabled(False)
        self.selectionChanged.emit([])

    def set_details(self, text_value: str) -> None:
        self.notes_view.setPlainText(text_value or '')

    def set_export_enabled(self, enabled: bool) -> None:
        self.btn_export_png.setEnabled(enabled)
        self.btn_export_pdf.setEnabled(enabled)

    def exams(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for row in range(self.list_widget.count()):
            data = self.list_widget.item(row).data(Qt.UserRole)
            if isinstance(data, dict):
                result.append(data)
        return result

    def selected_exams(self) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        for item in self.list_widget.selectedItems():
            data = item.data(Qt.UserRole)
            if isinstance(data, dict):
                selected.append(data)
        return selected

    def _on_selection_changed(self) -> None:
        selected = self.selected_exams()
        self.selectionChanged.emit(selected)
        self.set_export_enabled(bool(selected))
        if not selected:
            self.set_details('')
