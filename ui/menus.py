from __future__ import annotations
from typing import Callable
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow


class MenuBuilder:
    """
    Costruisce la barra menu:
    - FILE: Apri calibrazione, Salva audiometria, Chiudi
    - CUFFIE: Seleziona dispositivo output (e trigger caricamento calibrazione)
    - ASSISTITO: Nuovo / Apri da locale
    - AUDIOMETRIA: Manuale (nuovo esame), Risultati
    - EXPORT: PNG, PDF con Esito AI
    """

    def __init__(self, win: QMainWindow) -> None:
        self.win = win

    def _connect(self, action: QAction, handler_name: str) -> None:
        handler = getattr(self.win, handler_name, None)
        if callable(handler):
            action.triggered.connect(handler)
        else:
            action.triggered.connect(lambda: None)

    def build(self) -> None:
        mb = self.win.menuBar()
        m_file = mb.addMenu("FILE")
        m_hp = mb.addMenu("CUFFIE")
        m_pt = mb.addMenu("ASSISTITO")
        m_aud = mb.addMenu("AUDIOMETRIA")
        m_exp = mb.addMenu("EXPORT")

        # FILE
        act_open_cal = QAction("Apri calibrazione...", self.win)
        act_open_cal.setShortcut("Ctrl+O")
        act_save_exam = QAction("Salva audiometria corrente", self.win)
        act_save_exam.setShortcut("Ctrl+S")
        act_close = QAction("Chiudi", self.win)
        act_close.setShortcut("Alt+F4")
        m_file.addActions([act_open_cal, act_save_exam])
        m_file.addSeparator()
        m_file.addAction(act_close)

        self._connect(act_open_cal, "open_calibration_file")
        self._connect(act_save_exam, "save_current_audiometry")
        act_close.triggered.connect(self.win.close)

        # CUFFIE
        act_sel_dev = QAction("Seleziona dispositivo output...", self.win)
        m_hp.addAction(act_sel_dev)
        self._connect(act_sel_dev, "select_output_device")

        # ASSISTITO
        act_new = QAction("Nuovo assistito...", self.win)
        act_open = QAction("Apri assistito locale...", self.win)
        m_pt.addActions([act_new, act_open])
        self._connect(act_new, "create_new_patient")
        self._connect(act_open, "open_patient_from_repo")

        # AUDIOMETRIA
        act_manual = QAction("Manuale (nuovo esame)", self.win)
        act_results = QAction("Risultati", self.win)
        m_aud.addActions([act_manual, act_results])
        self._connect(act_manual, "start_manual_exam")
        self._connect(act_results, "show_results_browser")

        # EXPORT
        act_png = QAction("Esporta PNG grafico...", self.win)
        act_pdf = QAction("Crea relazione PDF A4...", self.win)
        m_exp.addActions([act_png, act_pdf])
        self._connect(act_png, "export_graph_png")
        self._connect(act_pdf, "create_pdf_report")


