import json
import os

from .params import get_patient_params
from .screening.results import ResultsStore
from .screening.test_runner import TestRunner
from .screening.exporter import export_results_to_webapp
from .screening.manual_test import ManualTest
from .audio.device_manager import AudioDeviceManager
from .audio.calibration import CalibrationStore
from .audio.calibration import HeadphoneCalibration, CombinedCalibration
from .plotting.audiogram_plot import render_audiogram_image
from .storage import save_exam, patient_dir, list_patients, load_patient_index, create_patient, load_patient_profile, suggest_next_patient_id, update_patient_profile
from .paths import path_settings, path_calibrations, ensure_default_file
from .version import __version__
from .audio.calibration import HP_DIR
from .analysis import generate_analysis_text

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

class AppController:
    def __init__(self, ui_callbacks):
        self.ui = ui_callbacks
        # Ensure defaults in appdata on first run
        ensure_default_file(path_settings(), "settings.json")
        ensure_default_file(path_calibrations(), "calibrations.json")

        self.settings = self._load_settings()
        # attach version into settings (read-only usage)
        self.settings.setdefault("__version__", __version__)
        # enable UI debug events by default (can be disabled by setting to False)
        if 'debug_ui_events' not in self.settings:
            self.settings['debug_ui_events'] = True
            try:
                self._save_settings()
            except Exception:
                pass

        self.patient = get_patient_params()
        if "id" in self.patient:
            self.patient["id"] = str(self.patient["id"]).upper()
        # Ensure patient profile exists/updated with provided fields (eta/birth_date)
        try:
            update_patient_profile(
                self.patient.get('id','PZ0000'),
                nome=self.patient.get('nome',''),
                cognome=self.patient.get('cognome',''),
                eta=self.patient.get('eta'),
                birth_date=self.patient.get('birth_date'),
            )
        except Exception:
            pass
        self.audio_mgr = AudioDeviceManager()

        # Stores: dispositivo (per-frequenza) + cuffia (per-orecchio)
        self._dev_cal = CalibrationStore(path_calibrations(), self.settings["frequencies_hz"])
        self._hp_cal = HeadphoneCalibration()
        # Wrapper combinato per l'app (usa entrambi dove serve)
        self.calibration = CombinedCalibration(self._dev_cal, self._hp_cal)

        # Ripristina ultimo HP_ID se presente
        hp_last = self.settings.get("last_hp_id")
        if hp_last:
            try:
                self.set_headphone_id(hp_last)
            except Exception:
                pass

        self._results = ResultsStore()
        self._preview_rows = None  # for archive preview

        if self.settings.get("default_output_device"):
            try:
                self.audio_mgr.set_output_device_by_name(self.settings["default_output_device"])
                self._after_device_selected(self.settings["default_output_device"])
                try:
                    self._assign_headphone_id_from_device()
                except Exception:
                    pass
            except Exception:
                pass

        self.testrunner = TestRunner(self.settings, self.audio_mgr, self.calibration, self._results, self.ui)
        self.manual = ManualTest(self.settings, self.audio_mgr, self.calibration, self._results, self.ui)
        # Separate results + manual runner for CALIBRATION (isolated from patient exams)
        self._calib_results_store = ResultsStore()
        self.manual_cal = ManualTest(self.settings, self.audio_mgr, self.calibration, self._calib_results_store, self.ui)

    def _load_settings(self):
        path = path_settings()
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_settings(self):
        path = path_settings()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

    # Dispositivi
    def list_output_devices(self):
        return self.audio_mgr.list_output_devices()

    def set_output_device(self, device_name):
        self.audio_mgr.set_output_device_by_name(device_name)
        self._after_device_selected(device_name)
        # Persist choice
        self.settings["default_output_device"] = device_name
        self._save_settings()

    def _after_device_selected(self, device_name):
        if self.calibration.has_profile_for(device_name):
            if self.ui.ask_yes_no(f"Trovata calibrazione salvata per '{device_name}'. Vuoi caricarla?"):
                self.calibration.load_profile(device_name)
                self.ui.show_info(f"Profilo '{device_name}' caricato.")
            else:
                self.calibration.set_active_device(device_name, create_if_missing=True)
                self.calibration.reset_profile(device_name)
                self.ui.show_info(f"Profilo per '{device_name}' azzerato. Procedi con la calibrazione.")
        else:
            self.calibration.set_active_device(device_name, create_if_missing=True)
            self.ui.show_info(f"Nessun profilo per '{device_name}'. Ne è stato creato uno nuovo (offset 0).")

    def get_active_device(self):
        return self.calibration.active_device

    def _assign_headphone_id_from_device(self):
        try:
            uid = self.audio_mgr.get_current_output_uid()
        except Exception:
            uid = None
        if uid:
            self.set_headphone_id(uid)
        return uid

    # Public helper: assign headphone ID from current device UID
    def assign_hp_from_device(self):
        return self._assign_headphone_id_from_device()

    def get_headphone_id(self):
        return getattr(self, '_headphone_id', None)

    def get_calibration_map(self):
        return self.calibration.get_map()

    def set_calibration_value(self, freq_hz, offset_db):
        self.calibration.set_offset(freq_hz, offset_db)

    def save_calibration(self):
        self.calibration.save()

    def play_tone_for_calibration(self, freq_hz, level_dbhl, ear):
        self.testrunner.play_single_tone(freq_hz, level_dbhl, ear, duration_ms=800)

    # Test automatico
    
    def start_test(self, *args, **kwargs):
        """Modalità unica: manuale."""
        return self.start_manual()

    def cancel_test(self):
        self.testrunner.cancel_test()

    # Test manuale
    def start_manual(self):
        self._preview_rows = None  # clear preview
        self.manual.start()

    def stop_manual(self):
        self.manual.stop()

    def manual_space(self):
        if self.is_calibration_mode():
            try:
                self.manual_cal.on_space()
            except Exception:
                pass
        else:
            self.manual.on_space()

    def manual_move_freq(self, delta):
        if self.is_calibration_mode():
            try:
                self.manual_cal.move_freq(delta)
            except Exception:
                pass
        else:
            self.manual.move_freq(delta)

    def manual_move_level(self, delta):
        if self.is_calibration_mode():
            try:
                self.manual_cal.move_level(delta)
            except Exception:
                pass
        else:
            self.manual.move_level(delta)

    def manual_set_ear(self, ear):
        if self.is_calibration_mode():
            self.manual_cal.set_ear(ear)
        else:
            self.manual.set_ear(ear)

    # Risultati
    @property
    def results(self):
        return self._results

    def get_results_rows(self):
        if self._preview_rows is not None:
            return self._preview_rows
        return self._results.to_rows(patient=self.patient)

    def get_preview_rows(self):
        return self._preview_rows

    def save_results_local(self):
        from datetime import datetime as dt
        payload = self._results.to_payload(self.patient)
        ts = dt.now().strftime("%Y%m%d_%H%M%S")
        pdir = patient_dir(self.patient["id"])
        img_dir = os.path.join(pdir, "screenings")
        img_path = os.path.join(img_dir, f"{ts}.png")
        rows = self._results.rows
        render_audiogram_image(rows, self.patient, self.get_active_device(), self.settings["frequencies_hz"], out_path=img_path)
        path = save_exam(self.patient, payload, ts=ts, image_path=img_path)
        return path, img_path

    def export_results(self, webapp_url, auth_token):
        payload = self._results.to_payload(self.patient)
        return export_results_to_webapp(webapp_url, auth_token, payload)

    def get_patient_display(self):
        nome = self.patient.get("nome","")
        cognome = self.patient.get("cognome","")
        base = f"{cognome} {nome}".strip()
        extra = []
        eta = (self.patient.get('eta') or '').strip() if isinstance(self.patient.get('eta'), str) else self.patient.get('eta')
        if eta:
            try:
                extra.append(f"età: {int(eta)}")
            except Exception:
                extra.append(f"età: {eta}")
        suffix = f" (ID: {self.patient['id']})"
        if extra:
            suffix += " - " + ", ".join(extra)
        return f"{base}{suffix}" if base else f"{suffix}"

    # Wizard (removed)

    # Archivio pazienti
    def list_saved_patients(self):
        return list_patients()

    def load_patient_archive(self, patient_id):
        prof = load_patient_profile(patient_id)
        # Keep optional fields if present (birth_date, sex)
        self.patient = {
            "id": prof["id"],
            "nome": prof.get("nome",""),
            "cognome": prof.get("cognome",""),
            "birth_date": prof.get("birth_date"),
            "sex": prof.get("sex"),
        }
        idx = load_patient_index(self.patient["id"])
        self.ui.on_patient_loaded(idx)
        return idx

    # Archivio: anteprima screening
    def preview_rows_from_exam_path(self, json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return False, f"Errore lettura file: {e}"

        soglie = data.get("soglie") or data.get("thresholds") or []
        pat = data.get("patient") or self.patient
        display_name = ((pat.get("cognome","") + " " + pat.get("nome","")).strip())
        pid = pat.get("id") or self.patient.get("id")
        rows = []
        for s in soglie:
            ear = s.get("ear") or s.get("orecchio") or s.get("side") or "?"
            freq = s.get("freq") or s.get("frequency") or s.get("hz")
            dbhl = s.get("dbhl") or s.get("level") or s.get("db")
            if freq is None or dbhl is None or ear not in ("R","L"):
                continue
            rows.append((pid, display_name, ear, int(freq), float(dbhl)))

        # Carica eventuali note/analisi
        notes = data.get('analysis') or ((data.get('screening') or {}).get('note') if isinstance(data.get('screening'), dict) else None)
        if isinstance(notes, str):
            self._results.set_notes(notes)
            if hasattr(self.ui, 'on_notes_loaded'):
                try:
                    self.ui.on_notes_loaded(notes)
                except Exception:
                    pass
        self._preview_rows = rows
        self.ui.on_preview_loaded(rows)
        return True, f"Caricati {len(rows)} punti"

    # Nuovo paziente
    def suggest_patient_id(self):
        return suggest_next_patient_id()

    def create_patient(self, patient_id, nome, cognome):
        prof = create_patient(patient_id, nome, cognome)
        self.patient = {"id": prof["id"], "nome": prof.get("nome",""), "cognome": prof.get("cognome","")}
        self.ui.on_patient_created(self.patient)
        return self.patient


    def set_headphone_id(self, hp_id: str):
        """Imposta cuffia corrente e carica bias salvati."""
        self._headphone_id = hp_id or "default"
        return self.calibration.set_headphone(self._headphone_id)


    def get_results(self):
        """Ritorna risultati correnti come {'L':{freq:db}, 'R':{...}}."""
        return self.manual.get_results()


    def start_calibration(self, hp_id: str | None = None):
        """Start calibration run using a dedicated results store (no linkage to patient exam)."""
        if hp_id:
            self.set_headphone_id(hp_id)
        self._calib_mode = True
        try:
            self._calib_results_store.clear()
        except Exception:
            pass
        self.manual_cal.start()
        return True


    def finish_calibration_save(self):
        """Fine calibrazione: calcola bias = -soglia e salva su file della cuffia."""
        # take thresholds measured in calibration run (isolated)
        measured = self._calib_results_store.to_map_by_ear()
        bias = self.calibration.compute_bias_from_thresholds(measured)
        self.calibration.set_bias_map(bias)
        # Persist headphone bias
        path = self.calibration.save_headphone()
        # Save a calibration session snapshot (normo by definition here)
        try:
            hp = self.get_headphone_id() or 'default'
            subj = {
                'id': (self.patient.get('id') or 'anon'),
                'is_normoacusic': True,
            }
            self.save_calibration_session(hp, subj, measured, None, options={'mode': 'normo_direct'})
        except Exception:
            pass
        self._calib_mode = False
        return bias

    def is_calibration_mode(self) -> bool:
        return bool(getattr(self, '_calib_mode', False))


    def manual_enter(self):
        """Invio: memorizza soglia corrente (e garantisce stop)."""
        if self.is_calibration_mode():
            try:
                self.manual_cal.commit_current()
                self.manual_cal._stop_play()
            except Exception:
                pass
        else:
            self.manual.commit_current()
            self.manual._stop_play()
        return True



    def manual_move(self, axis: str, delta: int):
        """Muove cursore: axis='freq'|'level'. Ferma tono.
        Semantica frecce **invertita**: UP -> delta=-1 (più forte), DOWN -> delta=+1 (più debole)."""
        self.manual._stop_play()
        if axis == 'freq':
            self.manual.move_freq(delta)
        elif axis == 'level':
            # inversione definita qui a livello controller
            self.manual.move_level(delta)
        return True



    def manual_toggle_ear(self):
        if self.is_calibration_mode():
            self.manual_cal.toggle_ear()
        else:
            self.manual.toggle_ear()
        return True

    # -------- Calibration (manual) helpers --------
    def cal_manual_set_ear(self, ear: str):
        self.manual_cal.set_ear(ear)

    def stop_calibration(self):
        self.manual_cal.stop()

    def results_map_calibration(self):
        return self._calib_results_store.to_map_by_ear()

    # -------- Calibrazione: bias cuffie --------
    def get_headphone_bias_map(self):
        try:
            # Access underlying headphone store via CombinedCalibration
            return {
                'L': dict(self.calibration._hp.bias.get('L', {})),
                'R': dict(self.calibration._hp.bias.get('R', {})),
            }
        except Exception:
            return {'L': {}, 'R': {}}

    def set_headphone_bias(self, ear: str, freq_hz: int, value_db: float):
        ear = 'R' if ear == 'R' else 'L'
        m = self.get_headphone_bias_map()
        m.setdefault(ear, {})[int(freq_hz)] = float(value_db)
        self.calibration.set_bias_map(m)
        try:
            self.calibration.save_headphone()
        except Exception:
            pass
        return m

    def apply_calibration_bias(self, hp_id: str, subject: dict, app_map: dict, ref_map: dict | None = None,
                               aggregator: str = 'median', smoothing: bool = True, outlier_abs: float = 25.0):
        """Calcola e salva bias cuffia a partire da:
        - app_map: soglie misurate con l'app ({'L':{freq:db}, 'R':{...}})
        - ref_map: soglie da audiometro certificato (stesso soggetto). Se None => assume normoudente.
        Regola: normoudente -> bias = -HL_app; con ref -> bias = HL_ref - HL_app.
        Applica smoothing (3-punti) e limita outlier.
        """
        try:
            self.set_headphone_id(hp_id)
        except Exception:
            pass

        def agg(vals):
            if not vals:
                return None
            if aggregator == 'mean':
                return sum(vals) / len(vals)
            # default median
            s = sorted(vals)
            n = len(s)
            return (s[n//2] if n % 2 == 1 else (s[n//2 - 1] + s[n//2]) / 2.0)

        out = {'L': {}, 'R': {}}
        for ear in ('L','R'):
            a = app_map.get(ear, {}) or {}
            r = (ref_map.get(ear, {}) if ref_map else None) or {}
            # Frequenze union
            freqs = sorted({int(f) for f in list(a.keys()) + list(r.keys())})
            for f in freqs:
                app_val = a.get(f)
                ref_val = r.get(f) if r else None
                deltas = []
                if app_val is not None:
                    if ref_map is None:
                        deltas.append(-float(app_val))
                    elif ref_val is not None:
                        deltas.append(float(ref_val) - float(app_val))
                d = agg(deltas)
                if d is None:
                    continue
                # clamp outliers
                try:
                    if abs(d) > float(outlier_abs):
                        d = float(outlier_abs) if d > 0 else -float(outlier_abs)
                except Exception:
                    pass
                out[ear][int(f)] = float(d)

            # smoothing 3-punti
            if smoothing and out[ear]:
                fsorted = sorted(out[ear].keys())
                sm = {}
                for i, f in enumerate(fsorted):
                    vals = [out[ear][f]]
                    if i > 0:
                        vals.append(out[ear][fsorted[i-1]])
                    if i+1 < len(fsorted):
                        vals.append(out[ear][fsorted[i+1]])
                    sm[f] = sum(vals) / len(vals)
                out[ear] = sm

        # Applica e salva
        self.calibration.set_bias_map(out)
        try:
            self.calibration.save_headphone()
        except Exception:
            pass
        return out

    # Placeholders for UI hooks (no session persistence implemented)
    def list_calibration_sessions(self, hp_id: str):
        return []

    def recompute_headphone_bias(self, hp_id: str, aggregator: str = 'median', smoothing: bool = True, outlier_abs: float = 25.0):
        # No stored sessions: keep current bias; re-save to ensure file exists
        try:
            self.set_headphone_id(hp_id)
            self.calibration.save_headphone()
        except Exception:
            pass
        return self.get_headphone_bias_map()

    # -------- Export/Import headphone calibration --------
    def export_headphone_calibration(self, hp_id: str, out_path: str) -> str:
        try:
            self.set_headphone_id(hp_id)
        except Exception:
            pass
        data = {
            'hp_id': hp_id,
            'bias': self.get_headphone_bias_map(),
            'frequencies_hz': self.settings.get('frequencies_hz', []),
            'app_version': __version__,
        }
        import json, os
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out_path

    def import_headphone_calibration(self, in_path: str) -> str:
        import json, os
        if not os.path.exists(in_path):
            raise FileNotFoundError(in_path)
        with open(in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        hp = data.get('hp_id') or 'default'
        bias = data.get('bias') or {'L': {}, 'R': {}}
        self.set_headphone_id(hp)
        self.calibration.set_bias_map(bias)
        self.calibration.save_headphone()
        return hp

    # -------- Esame: note/analisi --------
    def set_exam_notes(self, text: str):
        self._results.set_notes(text or "")

    def get_exam_notes(self) -> str:
        return self._results.get_notes()

    def generate_exam_analysis(self) -> str:
        m = self._results.to_map_by_ear()
        text = generate_analysis_text(m, self.settings.get('frequencies_hz', []))
        self._results.set_notes(text)
        return text

    # -------- Calibrazione clinica con riferimento --------
    def get_manual_cursor(self):
        """Ritorna (freq, level, ear) del cursore manuale corrente."""
        try:
            return self.manual.current_freq(), self.manual.level_db, self.manual.ear
        except Exception:
            return None

    def set_headphone_id(self, hp_id: str):
        self.settings["last_hp_id"] = hp_id
        self._save_settings()
        return self.calibration.set_headphone(hp_id)

    def results_map_current(self):
        """Mappa ear->freq->db dai risultati correnti."""
        return self._results.to_map_by_ear()

    def results_map_from_rows(self, rows):
        m = {'L': {}, 'R': {}}
        for r in rows:
            if isinstance(r, dict):
                ear, f, db = r.get('ear'), int(r.get('freq')), float(r.get('dbhl'))
            else:
                ear, f, db = r[2], int(r[3]), float(r[4])
            if ear in ('L','R'):
                m[ear][f] = db
        return m

    def load_app_results_from_archive(self, json_path):
        """Carica un esame JSON dall'archivio e restituisce mappa ear->freq->db."""
        try:
            import json
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Errore lettura esame: {e}")
        soglie = data.get('soglie') or []
        rows = []
        for s in soglie:
            ear = s.get('ear') or s.get('orecchio') or s.get('side')
            freq = s.get('hz') or s.get('freq')
            dbhl = s.get('dbhl') or s.get('level')
            if ear in ('L','R') and freq is not None and dbhl is not None:
                rows.append((None, None, ear, int(freq), float(dbhl)))
        return self.results_map_from_rows(rows)

    def _sessions_dir(self, hp_id: str):
        import os
        return os.path.join(HP_DIR, hp_id, 'calibration_sessions')

    def save_calibration_session(self, hp_id: str, subject: dict, hl_app: dict, hl_ref: dict | None, options: dict | None = None):
        import os, json, datetime
        d = self._sessions_dir(hp_id)
        os.makedirs(d, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        payload = {
            'subject': subject or {},
            'hl_app': hl_app or {},
            'hl_ref': hl_ref or {},
            'options': options or {},
        }
        path = os.path.join(d, f'{ts}_{subject.get("id","anon")}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def _iter_sessions(self, hp_id: str):
        import os, json
        d = self._sessions_dir(hp_id)
        if not os.path.isdir(d):
            return []
        out = []
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if not os.path.isfile(p) or not name.lower().endswith('.json'):
                continue
            try:
                data = json.load(open(p, 'r', encoding='utf-8'))
                data['__path'] = p
                data['__name'] = name
                out.append(data)
            except Exception:
                continue
        return out

    @staticmethod
    def _median(values):
        s = sorted(values)
        n = len(s)
        if n == 0: return None
        m = n//2
        if n % 2: return s[m]
        return 0.5*(s[m-1]+s[m])

    def _aggregate_bias(self, hp_id: str, freqs: list[int], outlier_abs=25.0, smoothing=True, aggregator='median'):
        sessions = self._iter_sessions(hp_id)
        acc = {'L': {f: [] for f in freqs}, 'R': {f: [] for f in freqs}}
        for sess in sessions:
            hl_app = sess.get('hl_app') or {}
            hl_ref = sess.get('hl_ref') or {}
            subj = sess.get('subject') or {}
            is_normo = bool(subj.get('is_normoacusic'))
            for ear in ('L','R'):
                app_map = {int(k): float(v) for k, v in (hl_app.get(ear, {}) or {}).items()}
                if hl_ref:
                    ref_map = {int(k): float(v) for k, v in (hl_ref.get(ear, {}) or {}).items()}
                else:
                    ref_map = {}
                for f in freqs:
                    if f in app_map:
                        if ref_map:
                            if f in ref_map:
                                delta = ref_map[f] - app_map[f]
                            else:
                                continue
                        else:
                            if not is_normo:
                                continue
                            delta = -app_map[f]
                        if abs(delta) <= outlier_abs:
                            acc[ear][f].append(delta)
        bias = {'L': {}, 'R': {}}
        for ear in ('L','R'):
            for f in freqs:
                vals = acc[ear][f]
                if not vals:
                    continue
                if aggregator == 'mean':
                    v = sum(vals)/len(vals)
                else:
                    v = self._median(vals)
                bias[ear][f] = float(v)
        if smoothing:
            def smooth_one(d: dict):
                out = {}
                arr = []
                for f in freqs:
                    arr.append((f, d.get(f)))
                # 3-point moving average over available points
                for i, (f, v) in enumerate(arr):
                    if v is None:
                        continue
                    neigh = [v]
                    if i-1 >= 0 and arr[i-1][1] is not None: neigh.append(arr[i-1][1])
                    if i+1 < len(arr) and arr[i+1][1] is not None: neigh.append(arr[i+1][1])
                    out[f] = sum(neigh)/len(neigh)
                return out
            bias = {'L': smooth_one(bias.get('L', {})), 'R': smooth_one(bias.get('R', {}))}
        return bias

    def apply_calibration_bias(self, hp_id: str, subject: dict, hl_app: dict, hl_ref: dict | None, aggregator='median', smoothing=True, outlier_abs=25.0):
        if not hp_id:
            raise ValueError("HP_ID mancante")
        # Save session
        self.save_calibration_session(hp_id, subject, hl_app, hl_ref, options={'aggregator': aggregator, 'smoothing': smoothing, 'outlier_abs': outlier_abs})
        # Recompute aggregated bias
        freqs = [int(f) for f in self.settings['frequencies_hz']]
        bias = self._aggregate_bias(hp_id, freqs, outlier_abs=outlier_abs, smoothing=smoothing, aggregator=aggregator)
        self.calibration.set_headphone(hp_id)
        self.calibration.set_bias_map(bias)
        self.calibration.save_headphone()
        return bias

    def recompute_headphone_bias(self, hp_id: str, aggregator='median', smoothing=True, outlier_abs=25.0):
        freqs = [int(f) for f in self.settings['frequencies_hz']]
        bias = self._aggregate_bias(hp_id, freqs, outlier_abs=outlier_abs, smoothing=smoothing, aggregator=aggregator)
        self.calibration.set_headphone(hp_id)
        self.calibration.set_bias_map(bias)
        self.calibration.save_headphone()
        return bias

    def list_calibration_sessions(self, hp_id: str):
        out = []
        for s in self._iter_sessions(hp_id):
            subj = s.get('subject') or {}
            hl_ref = s.get('hl_ref') or {}
            out.append({
                'name': s.get('__name'),
                'path': s.get('__path'),
                'subject_id': subj.get('id') or '',
                'is_normoacusic': bool(subj.get('is_normoacusic')),
                'has_ref': bool((hl_ref.get('L') or {}) or (hl_ref.get('R') or {})),
            })
        return out

    def export_headphone_calibration(self, hp_id: str, dst_path: str):
        import os, json
        self.calibration.set_headphone(hp_id)
        data = {
            'hp_id': hp_id,
            'bias_db': self.calibration._hp.bias,  # ear->freq->dB
            'meta': {'exported_at': __import__('datetime').datetime.now().isoformat()}
        }
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return dst_path

    def import_headphone_calibration(self, src_path: str):
        import json
        with open(src_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        hp_id = data.get('hp_id') or 'imported'
        bias = data.get('bias_db') or {}
        self.calibration.set_headphone(hp_id)
        self.calibration.set_bias_map(bias)
        self.calibration.save_headphone()
        return hp_id
