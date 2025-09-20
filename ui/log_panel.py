from __future__ import annotations
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit
from PySide6.QtCore import Qt


class LogPanel(QWidget):
    """Area di log con dimensione compatta (circa due righe visibili)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(2)
        label = QLabel("Log")
        layout.addWidget(label)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._view.setMaximumBlockCount(500)
        line_height = self._view.fontMetrics().lineSpacing()
        self._view.setFixedHeight(int(line_height * 3.2))
        layout.addWidget(self._view)

    def append(self, message: str) -> None:
        timestamp = datetime.now().strftime('%H:%M:%S')
        self._view.appendPlainText(f"[{timestamp}] {message}")
        self._view.verticalScrollBar().setValue(self._view.verticalScrollBar().maximum())

    def clear(self) -> None:
        self._view.clear()
