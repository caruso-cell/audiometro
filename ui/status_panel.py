ï»¿ÃƒÂ¯Ã‚Â»Ã‚Â¿from __future__ import annotations
from typing import List, Dict, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal


class HistoryPanel(QWidget):
    """Pannello laterale che mostra le audiometrie salvate."""

    examActivated = Signal()
    selectionChanged = Signal(list)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.label = QLabel("Audiometrie salvate")
        layout.addWidget(self.label)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list_widget, 1)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.examActivated.emit())
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

    def set_exams(self, exams: List[Dict[str, Any]]) -> None:
        self.list_widget.clear()
        for exam in exams:
            created = exam.get('created_at', 'sconosciuta')
            summary = exam.get('summary', '')
            text = f"{created} - {summary}".strip()
            item = QListWidgetItem(text or created)
            item.setData(Qt.UserRole, exam)
            self.list_widget.addItem(item)
        self.selectionChanged.emit([])

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
        self.selectionChanged.emit(self.selected_exams())

