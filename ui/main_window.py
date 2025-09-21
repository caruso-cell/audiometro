from __future__ import annotations
from typing import Optional, Dict, Any, List
import os
import json
import re
import shutil
import tempfile
import sys
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QLabel,
    QStackedLayout,
    QPushButton,
    QDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

from ui.menus import MenuBuilder
from ui.audiogram_view import AudiogramView, FREQS
from ui.sidebar_controls import SidebarControls
from ui.dialogs import NewPatientDialog, OpenPatientDialog
from ui.status_panel import HistoryPanel
from ui.log_panel import LogPanel
from audio.engine import AudioEngine
from audio.devices import list_output_devices
from calibration_loader.profiles import (
    load_profile,
    local_profile_path_for_device,
    CalibrationProfileError,
)
from patient.repo import PatientRepo
from audiometry.session import AudiometrySession
from audiometry.storage import save_exam
from results.browser import list_patient_exams
from export.png import export_graph_png
from export.pdf import build_pdf_report_v3, _REPORTLAB_AVAILABLE
from app_settings import load_settings, save_settings


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    return os.path.join(base_path, relative_path)


class MainWindow(QMainWindow):
    """Finestra principale dell'app di audiometria."""

    def __init__(self, parent: Optional[QWidget] = None, cli_patient: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Audiometria")
        self.setWindowIcon(QIcon(resource_path('data/icona.png')))
        self.resize(1200, 720)

        self._appdata = os.getenv("APPDATA") or os.path.expanduser("~")
        self._settings = load_settings(self._appdata)
        self._cli_patient = cli_patient

        self.patient_repo = PatientRepo(self._appdata)
        self.audio_engine = AudioEngine()
        self.session = AudiometrySession()

        self.current_patient: Optional[Dict[str, Any]] = None
        self.current_device: Optional[Dict[str, Any]] = None
        self.current_profile: Optional[Dict[str, Any]] = None
        self.current_profile_path: Optional[str] = None
        self.last_exam_path: Optional[str] = None

        self._freqs = FREQS
        self._current_freq_index = self._freqs.index(1000) if 1000 in self._freqs else 0
        self._current_level = 30.0
        self._current_ear = "OD"
        self._current_step = 5
        self._masking_enabled = False
        self._tone_timeout = QTimer(self)
        self._tone_timeout.setSingleShot(True)
        self._tone_timeout.timeout.connect(self.stop_audio)

        self._last_export_dir = os.getcwd()
        self._preview_cached_points: dict[str, dict[int, float]] | None = None
        self._preview_active = False
        self._history_selected_exam: dict[str, Any] | None = None

        self._builder = MenuBuilder(self)
        self._builder.build()

        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)
        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout, 1)

        # Sidebar controls + placeholder
        self.sidebar = SidebarControls(self)
        self.sidebar_placeholder_label = QLabel()
        self.sidebar_placeholder_label.setAlignment(Qt.AlignCenter)
        self.sidebar_placeholder_label.setWordWrap(True)
        self.sidebar_placeholder_label.setStyleSheet("color: #666; font-size: 14px;")
        self.sidebar_placeholder_button = QPushButton("Manuale (nuovo esame)")
        self.sidebar_placeholder_button.clicked.connect(self.start_manual_exam)
        placeholder_layout = QVBoxLayout()
        placeholder_layout.addStretch(1)
        placeholder_layout.addWidget(self.sidebar_placeholder_label)
        placeholder_layout.addSpacing(12)
        placeholder_layout.addWidget(self.sidebar_placeholder_button, 0, Qt.AlignCenter)
        placeholder_layout.addStretch(2)
        self.sidebar_placeholder = QWidget(self)
        self.sidebar_placeholder.setLayout(placeholder_layout)

        self.sidebar_stack = QStackedLayout()
        self.sidebar_stack.addWidget(self.sidebar_placeholder)
        self.sidebar_stack.addWidget(self.sidebar)
        sidebar_container = QWidget(self)
        sidebar_container.setLayout(self.sidebar_stack)
        main_layout.addWidget(sidebar_container, 0)

        # Graph + placeholder
        self.graph = AudiogramView(self)
        self.graph_placeholder_label = QLabel("Premi \"Manuale (nuovo esame)\" per iniziare una misurazione.")
        self.graph_placeholder_label.setAlignment(Qt.AlignCenter)
        self.graph_placeholder_label.setStyleSheet("color: #666; font-size: 15px;")
        self.graph_stack = QStackedLayout()
        self.graph_stack.addWidget(self.graph_placeholder_label)
        self.graph_stack.addWidget(self.graph)
        graph_container = QWidget(self)
        graph_container.setLayout(self.graph_stack)
        main_layout.addWidget(graph_container, 1)

        # History panel
        self.history_panel = HistoryPanel(self)
        main_layout.addWidget(self.history_panel, 0)

        # Log panel
        self.log_panel = LogPanel(self)
        root_layout.addWidget(self.log_panel)

        self.setCentralWidget(central)

        # Signal wiring
        self.sidebar.btn_new.clicked.connect(self.start_manual_exam)
        self.sidebar.btn_done.clicked.connect(self._on_exam_completed)
        self.sidebar.stopRequested.connect(self.stop_audio)
        self.sidebar.playRequested.connect(self._on_play_requested)
        self.sidebar.storeRequested.connect(self._store_current_point)
        self.sidebar.frequencyChanged.connect(self._on_frequency_changed)
        self.sidebar.levelChanged.connect(self._on_level_changed)
        self.sidebar.earChanged.connect(self._on_ear_changed)
        self.sidebar.stepChanged.connect(self._on_step_changed)
        self.sidebar.maskingToggled.connect(self._on_masking_toggled)
        self.sidebar.notesChanged.connect(self._on_notes_changed)

        self.history_panel.selectionChanged.connect(self._on_history_selection_changed)
        self.history_panel.exportPngRequested.connect(self.export_graph_png)\n        self.history_panel.exportPdfRequested.connect(self.create_pdf_report)

        # Status bar
        self._status_patient_label = QLabel("Assistito: -")
        self._status_device_label = QLabel("Cuffia: -")
        bar = self.statusBar()
        bar.addPermanentWidget(self._status_patient_label)
        bar.addPermanentWidget(self._status_device_label)

        self._show_controls(False)
        self._show_graph(False)
        self._set_exam_controls_enabled(False)
        self._apply_state_to_controls()
        self._refresh_graph()
        self._update_placeholder_message()

        QTimer.singleShot(0, self._initial_setup)

    # ----- Initial workflow -----

    def _initial_setup(self) -> None:
        if self._cli_patient:
            self._activate_patient(self._cli_patient, persist=True)
            self.set_status("Assistito caricato da riga di comando.")
        else:
            self._prompt_patient_choice()
        self._prompt_device_choice()
        self._update_placeholder_message()

    def _prompt_patient_choice(self) -> None:
        if self.current_patient:
            return
        patients = self.patient_repo.list_all()
        if not patients:
            self.create_new_patient()
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Assistito")
        msg.setText("Vuoi aprire un assistito esistente o crearne uno nuovo?")
        open_btn = msg.addButton("Apri assistito", QMessageBox.ActionRole)
        new_btn = msg.addButton("Nuovo assistito", QMessageBox.ActionRole)
        cancel_btn = msg.addButton(QMessageBox.Cancel)
        msg.setDefaultButton(open_btn)
        msg.exec()
        if msg.clickedButton() == open_btn:
            self.open_patient_from_repo()
        elif msg.clickedButton() == new_btn:
            self.create_new_patient()
        else:
            self.set_status("Nessun assistito attivo. Puoi crearne uno dal menu ASSISTITO.")

    def _prompt_device_choice(self) -> None:
        devices = list_output_devices()
        if not devices:
            self.set_status("Nessun dispositivo di uscita disponibile.")
            return
        stored_id = self._settings.get('preferred_device_id')
        stored_device = next((d for d in devices if d.get('wasapi_id') == stored_id), None)
        if stored_device:
            reply = QMessageBox.question(
                self,
                "Cuffia",
                f"Usare la cuffia salvata {stored_device['name']}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._set_current_device(stored_device)
                return
        default_device = next((d for d in devices if d.get('is_default')), None)
        if default_device:
            reply = QMessageBox.question(
                self,
                "Cuffia",
                f"Rilevata cuffia predefinita {default_device['name']}. Vuoi usarla?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._set_current_device(default_device)
                return
        self.select_output_device()

    # ----- Helpers -----

    def set_status(self, message: str, *, log: bool = True, timeout: int = 6000) -> None:
        if log:
            self.log_panel.append(message)
        self.statusBar().showMessage(message, timeout)

    def _set_status_quick(self, message: str) -> None:
        self.set_status(message, log=False, timeout=2000)

    def _show_graph(self, visible: bool) -> None:
        if visible:
            self.graph_stack.setCurrentWidget(self.graph)
        else:
            self.graph_stack.setCurrentWidget(self.graph_placeholder_label)

    def _show_controls(self, visible: bool) -> None:
        if visible:
            self.sidebar_stack.setCurrentWidget(self.sidebar)
        else:
            self.sidebar_stack.setCurrentWidget(self.sidebar_placeholder)

    def _set_exam_controls_enabled(self, enabled: bool) -> None:
        widgets = [
            self.sidebar.btn_play,
            self.sidebar.btn_stop,
            self.sidebar.btn_memorize,
            self.sidebar.btn_done,
            self.sidebar.cmb_freq,
            self.sidebar.spin_level,
            self.sidebar.cmb_step,
            self.sidebar.chk_masking,
            self.sidebar.txt_notes,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
        self.sidebar.btn_new.setEnabled(enabled)

    def _has_recorded_points(self) -> bool:
        return bool(self.session.points_od or self.session.points_os)

    def _build_results_table(self, od_map: dict[int, float] | None = None, os_map: dict[int, float] | None = None, freqs: list[int] | None = None) -> str:
        col_w = 6
        freq_list = freqs or self._freqs
        freq_cells = [f"{freq:>{col_w}}" for freq in freq_list]

        def _fmt(mapping: dict[int, float] | None, freq: int) -> str:
            if not mapping or freq not in mapping:
                return f"{'-':>{col_w}}"
            return f"{int(round(mapping[freq])):>{col_w}}"

        od_source = od_map or self.session.points_od
        os_source = os_map or self.session.points_os
        od_cells = [_fmt(od_source, freq) for freq in freq_list]
        os_cells = [_fmt(os_source, freq) for freq in freq_list]

        label_w = 14
        line_freq = f"{'Freq (Hz)':>{label_w}}: " + ' '.join(freq_cells)
        line_od = f"{'OD (dB HL) dx':>{label_w}}: " + ' '.join(od_cells)
        line_os = f"{'OS (dB HL) sx':>{label_w}}: " + ' '.join(os_cells)
        return "\n".join([line_freq, line_od, line_os])

    def _export_base_filename(self) -> str:
        patient = self.current_patient or {}
        pieces = [str(patient.get('cognome', '')).strip(), str(patient.get('nome', '')).strip(), str(patient.get('id', '')).strip()]
        base = '_'.join([p for p in pieces if p])
        base = re.sub(r'[^A-Za-z0-9_-]+', '_', base).strip('_')
        if not base:
            base = 'audiometria'
        return base

    def _suggest_export_path(self, extension: str) -> str:
        directory = self._last_export_dir or os.getcwd()
        base = self._export_base_filename()
        return os.path.join(directory, f"{base}{extension}")

    def _write_exam_snapshot(self, base_path_without_ext: str) -> None:
        if not self.current_patient:
            return
        try:
            os.makedirs(os.path.dirname(base_path_without_ext) or '.', exist_ok=True)
            exam = self.session.to_dict(self.current_patient, self.current_device, self.current_profile)
        except Exception:
            exam = {}
        try:
            rows = self.controller.get_results_rows()
        except Exception:
            rows = []
        try:
            history = list_patient_exams(self._appdata, str(self.current_patient.get('id', '')))
        except Exception:
            history = []
        history_exam = self._history_selected_exam
        snapshot = {
            'generated_at': datetime.now().isoformat(),
            'patient': self.current_patient,
            'device': self.current_device,
            'headphone_id': self.controller.get_headphone_id(),
            'notes': (history_exam.get('data', {}).get('notes', '') if history_exam else self.session.notes),
            'current_exam': exam,
            'results_rows': rows,
            'saved_exams': history,
        }
        if history_exam:
            snapshot['selected_exam'] = history_exam.get('data')
            snapshot['selected_exam_path'] = history_exam.get('meta', {}).get('path')
        json_path = f"{base_path_without_ext}.json"
        try:
            with open(json_path, 'w', encoding='utf-8') as handle:
                json.dump(snapshot, handle, ensure_ascii=False, indent=2)
        except Exception as exc:
            if hasattr(self, '_logger'):
                self._logger.warning('Impossibile salvare snapshot esame: %s', exc)

    def _apply_state_to_controls(self) -> None:
        freq = self._freqs[self._current_freq_index]
        self.sidebar.set_frequency(freq)
        self.sidebar.set_level(self._current_level)
        self.sidebar.set_ear(self._current_ear)
        self.sidebar.set_step(self._current_step)
        self.sidebar.set_masking(self._masking_enabled)
        self.sidebar.set_notes(self.session.notes)
        self.graph.update_crosshair(freq, self._current_level)

    def _refresh_graph(self) -> None:
        self.graph.update_points("OD", self.session.points_od)
        self.graph.update_points("OS", self.session.points_os)
        self.graph.update_crosshair(self._freqs[self._current_freq_index], self._current_level)

    def _update_placeholder_message(self) -> None:
        if self.current_patient:
            txt = (
                f"Assistito attivo: {self.current_patient['cognome']} {self.current_patient['nome']}"
                f" (ID {self.current_patient['id']}).\n"
                "Premi \"Manuale (nuovo esame)\" per iniziare una misurazione."
            )
            self.sidebar_placeholder_button.setEnabled(True)
        else:
            txt = "Crea o apri un assistito dal menu ASSISTITO prima di iniziare un esame."
            self.sidebar_placeholder_button.setEnabled(False)
        self.sidebar_placeholder_label.setText(txt)

    def _stop_before_change(self) -> None:
        if self.audio_engine.running:
            self.audio_engine.stop(immediate=True)

    def _current_frequency(self) -> int:
        return self._freqs[self._current_freq_index]

    def _save_settings(self) -> None:
        save_settings(self._appdata, self._settings)

    def _update_status_bar(self) -> None:
        if self.current_patient:
            patient_text = (
                f"Assistito: {self.current_patient['cognome']} {self.current_patient['nome']}"
                f" (ID {self.current_patient['id']})"
            )
        else:
            patient_text = "Assistito: -"
        if self.current_device:
            device_text = f"Cuffia: {self.current_device.get('name', '-') }"
        else:
            device_text = "Cuffia: -"
        self._status_patient_label.setText(patient_text)
        self._status_device_label.setText(device_text)

    def _refresh_exam_history(self) -> None:
        if not self.current_patient:
            self.history_panel.set_exams([])
            return
        exams = list_patient_exams(self._appdata, str(self.current_patient['id']))
        self.history_panel.set_exams(exams)

    # ----- Menu actions -----

    def select_output_device(self) -> None:
        devices = list_output_devices()
        if not devices:
            QMessageBox.warning(self, "Nessun dispositivo", "Nessun dispositivo WASAPI disponibile.")
            return
        labels = [f"{d.get('name', 'Sconosciuto')} ({d.get('wasapi_id', '?')})" for d in devices]
        choice, ok = QInputDialog.getItem(self, "Seleziona dispositivo output", "Dispositivo:", labels, 0, False)
        if not ok:
            return
        idx = labels.index(choice)
        device = devices[idx]
        self._set_current_device(device)

    def _set_current_device(self, device: Dict[str, Any]) -> None:
        new_device_id = device.get("wasapi_id")
        current_id = self.current_device.get("wasapi_id") if self.current_device else None
        if current_id != new_device_id:
            reply = QMessageBox.question(
                self,
                "Conferma cuffia",
                f"Vuoi inviare i toni sulla cuffia '{device.get('name', 'Sconosciuto')}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                self.set_status("Cuffia invariata.")
                return
        if self.current_device and current_id != new_device_id:
            self.audio_engine.stop()
            self.session = AudiometrySession()
            self.session.notes = ''
            self._current_level = 30.0
            self._current_freq_index = self._freqs.index(1000) if 1000 in self._freqs else 0
            self._masking_enabled = False
            self._apply_state_to_controls()
            self._refresh_graph()
            self.sidebar.set_notes(self.session.notes)
            self._show_graph(False)
            self._show_controls(False)
            self._set_exam_controls_enabled(False)
            self.graph.set_overlays([])
            self._update_status_bar()
            self._refresh_exam_history()
            self._update_placeholder_message()
        self.current_device = device
        self.audio_engine.sample_rate = int(device.get("sample_rate", self.audio_engine.sample_rate))
        device_index = device.get('index')
        try:
            resolved_index = int(device_index) if device_index is not None else None
        except (TypeError, ValueError):
            resolved_index = None
        self.audio_engine.set_output_device(resolved_index)
        self._settings['preferred_device_id'] = device.get('wasapi_id')
        self._save_settings()
        self._update_status_bar()
        self.set_status(f"Cuffia attiva: {device.get('name', 'Sconosciuto')}")
        if not self._ensure_calibration_for_current_device():
            self.set_status("Carica un profilo di calibrazione per la cuffia selezionata.")
            self.open_calibration_file()
        self._update_placeholder_message()

    def _ensure_calibration_for_current_device(self) -> bool:
        if not self.current_device:
            return False
        wasapi_id = self.current_device.get('wasapi_id', '')
        calib_map = self._settings.setdefault('calibrations', {})
        stored_path = calib_map.get(wasapi_id)
        if stored_path and os.path.exists(stored_path):
            self._load_and_store_profile(stored_path, skip_copy=True)
            self.set_status("Profilo di calibrazione caricato automaticamente.")
            return True
        profile_path = local_profile_path_for_device(self._appdata, wasapi_id)
        if profile_path:
            self._load_and_store_profile(profile_path, skip_copy=True)
            self.set_status("Profilo di calibrazione trovato nella cartella locale.")
            return True
        return False

    def open_calibration_file(self) -> None:
        if not self.current_device:
            QMessageBox.warning(self, "Seleziona dispositivo", "Seleziona prima un dispositivo cuffie.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Apri calibrazione",
            "",
            "Profili calibrazione (*.json *.yaml *.yml)",
        )
        if not path:
            return
        self._load_and_store_profile(path)

    def save_current_audiometry(self) -> None:
        if not self.current_patient:
            QMessageBox.warning(self, "Assistito mancante", "Crea o apri un assistito prima di salvare.")
            return
        if not self.current_device or not self.current_profile:
            QMessageBox.warning(self, "Profilo mancante", "Seleziona cuffie e profilo di calibrazione valido.")
            return
        exam = self.session.to_dict(self.current_patient, self.current_device, self.current_profile)
        path = save_exam(self._appdata, str(self.current_patient['id']), exam)
        self.last_exam_path = path
        self._refresh_exam_history()
        self.set_status(f"Audiometria salvata: {os.path.basename(path)}")

    def create_new_patient(self) -> None:
        dialog = NewPatientDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_result()
        if not data:
            return
        self._activate_patient(data, persist=True)
        self.set_status(
            f"Assistito attivo: {data['nome']} {data['cognome']} (ID {data['id']})"
        )

    def open_patient_from_repo(self) -> None:
        patients = self.patient_repo.list_all()
        dialog = OpenPatientDialog(patients, self)
        if dialog.exec() != QDialog.Accepted:
            return
        selected = dialog.get_selected()
        if not selected:
            return
        self._activate_patient(selected, persist=False)
        self.set_status(
            f"Assistito attivo: {selected['nome']} {selected['cognome']} (ID {selected['id']})"
        )

    def start_manual_exam(self) -> None:
        if not self.current_patient:
            self._prompt_patient_choice()
            if not self.current_patient:
                self.set_status("Seleziona un assistito per iniziare un esame.")
                return
        if not self.current_profile:
            QMessageBox.warning(self, "Profilo mancante", "Carica un profilo di calibrazione valido.")
            return
        self.history_panel.list_widget.clearSelection()
        self._clear_history_preview()
        self.audio_engine.stop()
        self.session = AudiometrySession()
        self.session.notes = ''
        self._current_level = 30.0
        self._current_freq_index = self._freqs.index(1000) if 1000 in self._freqs else 0
        self._masking_enabled = False
        self._apply_state_to_controls()
        self._refresh_graph()
        self.graph.set_overlays([])
        self.sidebar.set_notes(self.session.notes)
        self._show_controls(True)
        self._show_graph(True)
        self._set_exam_controls_enabled(True)
        self.set_status("Esame manuale avviato. Registra i punti con i controlli dedicati.")

    def _on_history_selection_changed(self, exams: List[Dict[str, Any]]) -> None:
        if not exams:
            self._history_selected_exam = None
            self.history_panel.set_details('')
            self.graph.set_overlays([])
            if self._preview_active:
                self._preview_active = False
                self._preview_cached_points = None
                self._refresh_graph()
            return

        exam_meta = exams[0]
        path = exam_meta.get('path')
        if not path:
            self.history_panel.set_details('')
            return
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception as exc:
            QMessageBox.warning(self, "Risultati", f"Impossibile leggere l'esame:
{exc}")
            return

        try:
            freqs = [int(f) for f in data.get('frequencies_hz', self._freqs)]
        except Exception:
            freqs = self._freqs
        od_map = {int(k): float(v) for k, v in (data.get('OD') or {}).items() if str(k).isdigit()}
        os_map = {int(k): float(v) for k, v in (data.get('OS') or {}).items() if str(k).isdigit()}

        self.history_panel.set_details(data.get('notes', ''))
        self._history_selected_exam = {
            'meta': exam_meta,
            'data': data,
            'od': od_map,
            'os': os_map,
            'freqs': freqs,
        }
        self._show_history_exam_on_graph(od_map, os_map)

    def _show_history_exam_on_graph(self, od_map: Dict[int, float], os_map: Dict[int, float]) -> None:
        if not self._preview_active:
            self._preview_active = True
            self._preview_cached_points = {
                'OD': dict(self.session.points_od),
                'OS': dict(self.session.points_os),
            }
        self.graph.set_overlays([])
        self.graph.update_points('OD', od_map)
        self.graph.update_points('OS', os_map)

    def _clear_history_preview(self) -> None:
        if self._preview_active:
            self._preview_active = False
            self._preview_cached_points = None
            self._refresh_graph()

    def show_results_browser(self) -> None:
        if not self.current_patient:
            QMessageBox.information(self, 'Assistito mancante', 'Nessun assistito selezionato.')
            return
        self._refresh_exam_history()
        if self.history_panel.list_widget.count() == 0:
            QMessageBox.information(self, 'Risultati', 'Nessuna audiometria salvata per questo assistito.')
            return
        self.history_panel.list_widget.setFocus()
        if not self.history_panel.list_widget.selectedItems():
            self.history_panel.list_widget.setCurrentRow(0)

    def export_graph_png(self) -> None:
        if not self.current_patient:
            QMessageBox.warning(self, "Assistito mancante", "Nessun assistito selezionato.")
            return
        suggested = self._suggest_export_path('.png')
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta grafico PNG",
            suggested,
            "Immagine PNG (*.png)",
        )
        if not out_path:
            return
        self._last_export_dir = os.path.dirname(out_path) or self._last_export_dir
        export_graph_png(self.graph, out_path)
        if self.current_patient:
            base_no_ext, _ = os.path.splitext(out_path)
            self._write_exam_snapshot(base_no_ext)
        self.set_status(f"PNG salvato in: {out_path}")

    def create_pdf_report(self) -> None:
        history_exam = self._history_selected_exam
        if not _REPORTLAB_AVAILABLE:
            QMessageBox.warning(self, 'ReportLab mancante', 'Installa reportlab per generare il PDF.')
            return
        if history_exam is None:
            if not self.current_patient or not self.current_device or not self.current_profile:
                QMessageBox.warning(self, 'Dati mancanti', 'Serve assistito, dispositivo e profilo attivi.')
                return
            exam_dict = self.session.to_dict(self.current_patient, self.current_device, self.current_profile)
            patient_info = self.current_patient
            device_info = self.current_device
            notes = self.session.notes
            od_map = None
            os_map = None
            freqs = exam_dict.get('frequencies_hz', self._freqs)
        else:
            exam_dict = history_exam.get('data', {})
            patient_info = exam_dict.get('patient') or self.current_patient or {}
            device_info = exam_dict.get('device') or self.current_device or {}
            notes = exam_dict.get('notes', '')
            od_map = history_exam.get('od')
            os_map = history_exam.get('os')
            freqs = history_exam.get('freqs', self._freqs)
        suggested = self._suggest_export_path(".pdf")
        out_pdf, _ = QFileDialog.getSaveFileName(self, 'Crea relazione PDF', suggested, 'PDF (*.pdf)')
        if not out_pdf:
            return
        self._last_export_dir = os.path.dirname(out_pdf) or self._last_export_dir
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            export_graph_png(self.graph, tmp_path)
            table_text = self._build_results_table(od_map, os_map, freqs)
            build_pdf_report_v3(
                out_pdf,
                patient_info,
                device_info,
                exam_dict,
                notes,
                '',
                tmp_path,
                table_text,
                '',
            )
            base_no_ext, _ = os.path.splitext(out_pdf)
            self._write_exam_snapshot(base_no_ext)
            self.set_status(f'Relazione PDF creata in: {out_pdf}')
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def _activate_patient(self, patient: Dict[str, Any], persist: bool = True) -> None:
        self.current_patient = patient
        if persist:
            self.patient_repo.save(patient)
        self.audio_engine.stop()
        self.session = AudiometrySession()
        self.session.notes = ''
        self._current_level = 30.0
        self._current_freq_index = self._freqs.index(1000) if 1000 in self._freqs else 0
        self._masking_enabled = False
        self._apply_state_to_controls()
        self._refresh_graph()
        self.sidebar.set_notes(self.session.notes)
        self._show_controls(False)
        self._show_graph(False)
        self._set_exam_controls_enabled(False)
        self.graph.set_overlays([])
        self._update_status_bar()
        self._refresh_exam_history()
        self._update_placeholder_message()

    def _load_and_store_profile(self, path: str, skip_copy: bool = False) -> None:
        if not self.current_device:
            return
        try:
            profile = load_profile(path)
        except CalibrationProfileError as exc:
            QMessageBox.warning(self, "Profilo non valido", str(exc))
            return
        wasapi_id = self.current_device.get('wasapi_id', 'unknown')
        dest_folder = os.path.join(self._appdata, "Farmaudiometria", "calibrations", wasapi_id)
        os.makedirs(dest_folder, exist_ok=True)
        filename = os.path.basename(path)
        dest_path = os.path.join(dest_folder, filename)
        if not skip_copy:
            try:
                if os.path.abspath(path) != os.path.abspath(dest_path):
                    shutil.copy2(path, dest_path)
            except OSError as exc:
                QMessageBox.warning(self, "Errore copia", f"Impossibile copiare il profilo:\n{exc}")
                return
        self.current_profile = profile
        self.current_profile_path = dest_path
        if hasattr(self.audio_engine, "set_profile"):
            self.audio_engine.set_profile(profile)
        else:
            self.audio_engine.profile = profile  # type: ignore[attr-defined]
        calib_map = self._settings.setdefault('calibrations', {})
        calib_map[wasapi_id] = dest_path
        self._save_settings()
        self._update_status_bar()
        self.set_status("Profilo di calibrazione caricato con successo.")

    # ----- Sidebar actions / audio helpers -----

    def _on_play_requested(self) -> None:
        try:
            self._play_current_tone()
        except Exception as exc:
            QMessageBox.warning(self, "Errore riproduzione", str(exc))

    def _store_current_point(self) -> None:
        self._stop_before_change()
        if not self.current_profile:
            QMessageBox.warning(self, "Profilo mancante", "Carica un profilo di calibrazione prima di memorizzare.")
            return
        freq = self._current_frequency()
        level = self._current_level
        self.session.add_point(self._current_ear, freq, level)
        self._refresh_graph()
        self.set_status(f"Punto memorizzato: {self._current_ear} {freq} Hz @ {level:.1f} dB HL")

    def _on_exam_completed(self) -> None:
        self.audio_engine.stop()
        self.set_status("Esame completato. Salva o esporta i risultati.")

    def stop_audio(self) -> None:
        self._tone_timeout.stop()
        self.audio_engine.stop(immediate=True)
        self.set_status("Riproduzione arrestata.")

    def _on_frequency_changed(self, freq: int) -> None:
        self._stop_before_change()
        if freq in self._freqs:
            self._current_freq_index = self._freqs.index(freq)
        self.graph.update_crosshair(freq, self._current_level)
        self._set_status_quick(f"Frequenza selezionata: {freq} Hz")

    def _on_level_changed(self, level: float) -> None:
        self._stop_before_change()
        self._current_level = max(-10.0, min(level, 120.0))
        self.graph.update_crosshair(self._current_frequency(), self._current_level)
        self._set_status_quick(f"Livello aggiornato: {self._current_level:.1f} dB HL")

    def _on_ear_changed(self, ear: str) -> None:
        if ear not in ("OD", "OS"):
            return
        self._stop_before_change()
        self._current_ear = ear
        self._set_status_quick(f"Orecchio selezionato: {ear}")

    def _on_step_changed(self, step: int) -> None:
        self._current_step = step
        self._set_status_quick(f"Passo impostato a {step} dB")

    def _on_masking_toggled(self, enabled: bool) -> None:
        self._masking_enabled = enabled
        if enabled:
            self.set_status("Mascheramento attivo (non implementato in riproduzione).")
        else:
            self.set_status("Mascheramento disattivato.")

    def _on_notes_changed(self, notes: str) -> None:
        self.session.notes = notes

    def _play_current_tone(self) -> None:
        if not self.current_profile:
            raise RuntimeError("Profilo di calibrazione non caricato.")
        freq = self._current_frequency()
        level = self._current_level
        self.audio_engine.play_tone(freq, level, self._current_ear)
        self._tone_timeout.start(3000)
        self.set_status(f"Riproduzione: {self._current_ear} {freq} Hz @ {level:.1f} dB HL")

    # ----- Keyboard handling -----

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_Right):
            self._stop_before_change()
            delta = -1 if key == Qt.Key_Left else 1
            new_index = max(0, min(len(self._freqs) - 1, self._current_freq_index + delta))
            self._current_freq_index = new_index
            freq = self._current_frequency()
            self.sidebar.set_frequency(freq)
            self.graph.update_crosshair(freq, self._current_level)
            self.set_status(f"Frequenza selezionata: {freq} Hz", log=False, timeout=2000)
            event.accept()
            return
        if key in (Qt.Key_Up, Qt.Key_Down):
            self._stop_before_change()
            delta = -self._current_step if key == Qt.Key_Up else self._current_step
            self._current_level = max(-10.0, min(120.0, self._current_level + delta))
            self.sidebar.set_level(self._current_level)
            self.graph.update_crosshair(self._current_frequency(), self._current_level)
            direction = 'su' if key == Qt.Key_Up else 'giu'
            self.set_status(f"Livello {direction}: {self._current_level:.1f} dB HL", log=False, timeout=2000)
            event.accept()
            return
        if key == Qt.Key_Space:
            if self.audio_engine.running:
                self.stop_audio()
            else:
                self._on_play_requested()
            event.accept()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._store_current_point()
            event.accept()
            return
        if key == Qt.Key_Tab:
            self._stop_before_change()
            self._current_ear = "OS" if self._current_ear == "OD" else "OD"
            self.sidebar.set_ear(self._current_ear)
            self.set_status(f"Orecchio selezionato: {self._current_ear}", log=False, timeout=2000)
            event.accept()
            return
        if key == Qt.Key_Escape:
            self.stop_audio()
            event.accept()
            return
        if key == Qt.Key_M:
            self._masking_enabled = not self._masking_enabled
            self.sidebar.set_masking(self._masking_enabled)
            self._on_masking_toggled(self._masking_enabled)
            event.accept()
            return
        super().keyPressEvent(event)


















