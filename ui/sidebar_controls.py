from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QLabel,
    QTextEdit,
    QHBoxLayout,
    QScrollArea,
)
from PySide6.QtCore import Signal

FREQ_OPTIONS = [125, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000]
STEP_OPTIONS = [1, 2, 5]

ENVIRONMENT_OPTIONS = [
    {'code': 1, 'label': 'Casa in silenzio'},
    {'code': 2, 'label': 'Casa con televisione o radio accese'},
    {'code': 3, 'label': 'Conversazioni familiari in salotto o cucina'},
    {'code': 4, 'label': 'Ristorante / bar / caffetteria'},
    {'code': 5, 'label': 'Riunioni di lavoro o di condominio'},
    {'code': 6, 'label': 'Cene con amici o familiari numerosi'},
    {'code': 7, 'label': 'Feste o ricevimenti'},
    {'code': 8, 'label': 'Automobile'},
    {'code': 9, 'label': 'Autobus / treno'},
    {'code': 10, 'label': 'Aereo'},
    {'code': 11, 'label': 'Chiesa / luogo di culto'},
    {'code': 12, 'label': 'Cinema / teatro'},
    {'code': 13, 'label': 'Concerti / ascolto di musica'},
    {'code': 14, 'label': 'Eventi sportivi (palazzetti, stadi)'},
    {'code': 15, 'label': 'Passeggiate all\'aperto (parco, montagna, mare)'},
    {'code': 16, 'label': 'Traffico cittadino (strada, incroci, piazze affollate)'},
    {'code': 17, 'label': 'Mercati o centri commerciali'},
    {'code': 18, 'label': 'Ufficio (colleghi, telefoni, PC)'},
    {'code': 19, 'label': 'Scuola / aula universitaria'},
    {'code': 20, 'label': 'Fabbrica / officina (macchinari, rumori continui)'},
]


class SidebarControls(QWidget):
    """Controlli laterali per l'audiometria manuale."""

    frequencyChanged = Signal(int)
    levelChanged = Signal(float)
    earChanged = Signal(str)
    stepChanged = Signal(int)
    playRequested = Signal()
    stopRequested = Signal()
    storeRequested = Signal()
    maskingToggled = Signal(bool)
    notesChanged = Signal(str)
    environmentsChanged = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Controlli esame"))

        self.cmb_ear = QComboBox()
        self.cmb_ear.addItem("OD (orecchio destro)", "OD")
        self.cmb_ear.addItem("OS (orecchio sinistro)", "OS")
        self.cmb_ear.currentIndexChanged.connect(self._emit_ear)
        layout.addWidget(self.cmb_ear)

        self.cmb_freq = QComboBox()
        for freq in FREQ_OPTIONS:
            self.cmb_freq.addItem(f"{freq} Hz", freq)
        self.cmb_freq.currentIndexChanged.connect(self._emit_frequency)
        layout.addWidget(self.cmb_freq)

        self.spin_level = QDoubleSpinBox()
        self.spin_level.setPrefix("Livello: ")
        self.spin_level.setSuffix(" dB HL")
        self.spin_level.setDecimals(1)
        self.spin_level.setRange(-10.0, 120.0)
        self.spin_level.setSingleStep(5.0)
        self.spin_level.valueChanged.connect(self._emit_level)
        layout.addWidget(self.spin_level)

        row_step = QHBoxLayout()
        row_step.addWidget(QLabel("Passo dB"))
        self.cmb_step = QComboBox()
        for step in STEP_OPTIONS:
            self.cmb_step.addItem(f"{step} dB", step)
        self.cmb_step.currentIndexChanged.connect(self._emit_step)
        row_step.addWidget(self.cmb_step)
        layout.addLayout(row_step)

        self.chk_masking = QCheckBox("Mascheramento attivo")
        self.chk_masking.stateChanged.connect(self._emit_masking)
        layout.addWidget(self.chk_masking)

        row_buttons = QHBoxLayout()
        self.btn_play = QPushButton("PLAY")
        self.btn_play.clicked.connect(self.playRequested.emit)
        row_buttons.addWidget(self.btn_play)
        self.btn_memorize = QPushButton("Memorizza punto")
        self.btn_memorize.clicked.connect(self.storeRequested.emit)
        row_buttons.addWidget(self.btn_memorize)
        layout.addLayout(row_buttons)

        self.btn_new = QPushButton("Inizia nuovo esame")
        layout.addWidget(self.btn_new)

        row_bottom = QHBoxLayout()
        self.btn_done = QPushButton("FATTO")
        row_bottom.addWidget(self.btn_done)
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        row_bottom.addWidget(self.btn_stop)
        layout.addLayout(row_bottom)

        layout.addWidget(QLabel("Note assistito"))
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Annotazioni sull'esame")
        self.txt_notes.textChanged.connect(self._emit_notes)
        layout.addWidget(self.txt_notes)

        layout.addWidget(QLabel('Ambienti di ascolto'))
        self._block_environment_signal = False
        self._environment_checks = []
        env_host = QWidget()
        env_layout = QVBoxLayout(env_host)
        env_layout.setContentsMargins(0, 0, 0, 0)
        env_layout.setSpacing(4)
        for entry in ENVIRONMENT_OPTIONS:
            checkbox = QCheckBox(f"{entry['code']}. {entry['label']}")
            checkbox.stateChanged.connect(self._emit_environments)
            self._environment_checks.append((entry, checkbox))
            env_layout.addWidget(checkbox)
        env_layout.addStretch()
        env_scroll = QScrollArea()
        env_scroll.setWidgetResizable(True)
        env_scroll.setWidget(env_host)
        env_scroll.setFixedHeight(240)
        layout.addWidget(env_scroll)

        layout.addStretch()

    # --- Emitters ---

    def _emit_frequency(self) -> None:
        freq = self.frequency()
        self.frequencyChanged.emit(freq)

    def _emit_level(self, value: float) -> None:
        self.levelChanged.emit(float(value))

    def _emit_ear(self) -> None:
        self.earChanged.emit(self.ear())

    def _emit_step(self) -> None:
        self.stepChanged.emit(self.step())

    def _emit_masking(self) -> None:
        self.maskingToggled.emit(self.chk_masking.isChecked())

    def _emit_notes(self) -> None:
        self.notesChanged.emit(self.notes())

    def _emit_environments(self) -> None:
        if self._block_environment_signal:
            return
        selected = []
        for entry, checkbox in self._environment_checks:
            if checkbox.isChecked():
                selected.append({'code': entry['code'], 'description': entry['label']})
        self.environmentsChanged.emit(selected)

    # --- Accessors ---

    def frequency(self) -> int:
        return int(self.cmb_freq.currentData())

    def set_frequency(self, freq: int) -> None:
        idx = self.cmb_freq.findData(freq)
        if idx >= 0:
            self.cmb_freq.blockSignals(True)
            self.cmb_freq.setCurrentIndex(idx)
            self.cmb_freq.blockSignals(False)

    def level(self) -> float:
        return float(self.spin_level.value())

    def set_level(self, level: float) -> None:
        self.spin_level.blockSignals(True)
        self.spin_level.setValue(level)
        self.spin_level.blockSignals(False)

    def ear(self) -> str:
        return str(self.cmb_ear.currentData())

    def set_ear(self, ear: str) -> None:
        idx = self.cmb_ear.findData(ear)
        if idx >= 0:
            self.cmb_ear.blockSignals(True)
            self.cmb_ear.setCurrentIndex(idx)
            self.cmb_ear.blockSignals(False)

    def step(self) -> int:
        return int(self.cmb_step.currentData())

    def set_step(self, step: int) -> None:
        idx = self.cmb_step.findData(step)
        if idx >= 0:
            self.cmb_step.blockSignals(True)
            self.cmb_step.setCurrentIndex(idx)
            self.cmb_step.blockSignals(False)

    def set_masking(self, enabled: bool) -> None:
        self.chk_masking.blockSignals(True)
        self.chk_masking.setChecked(enabled)
        self.chk_masking.blockSignals(False)

    def notes(self) -> str:
        return self.txt_notes.toPlainText().strip()

    def set_notes(self, text: str) -> None:
        self.txt_notes.blockSignals(True)
        self.txt_notes.setPlainText(text)
        self.txt_notes.blockSignals(False)

    def environments(self) -> list:
        selected = []
        for entry, checkbox in self._environment_checks:
            if checkbox.isChecked():
                selected.append({'code': entry['code'], 'description': entry['label']})
        return selected

    def set_environments(self, selections) -> None:
        codes = set()
        if selections is None:
            selections = []
        for item in selections:
            code = None
            if isinstance(item, dict):
                code = item.get('code')
            else:
                try:
                    code = int(item)
                except (TypeError, ValueError):
                    code = None
            if code is not None:
                try:
                    codes.add(int(code))
                except (TypeError, ValueError):
                    continue
        self._block_environment_signal = True
        for entry, checkbox in self._environment_checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(entry['code'] in codes)
            checkbox.blockSignals(False)
        self._emit_environments()
        self._block_environment_signal = False
