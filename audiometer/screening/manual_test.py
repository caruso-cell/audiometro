import threading
import time
import random

from ..audio.tone_generator import sine_wave
from ..audio.playback import TonePlayer


class ManualTest:
    """
    Modalità manuale aggiornata:
    - Frecce sinistra/destra: cambia frequenza (lista discreta dai settings)
    - Frecce su/giù: cambia livello dB HL (invertite: SU = +, GIÙ = -)
    - SPAZIO: start/stop tono (toggle)
    - INVIO: memorizza punto corrente e ferma il tono
    - TAB: cambia orecchio (R/L) — gestito dalla UI
    """

    def __init__(self, settings, audio_mgr, calibration_store, results_store, ui_callbacks):
        self.settings = settings
        self.audio_mgr = audio_mgr
        self.calib = calibration_store
        self.results = results_store
        self.ui = ui_callbacks

        self.player = TonePlayer(settings['sample_rate'],
                                 left_index=settings['left_channel_index'],
                                 right_index=settings['right_channel_index'])

        self._stop_evt = threading.Event()
        self._loop_thread = None
        self._playing = False

        self.freqs = self.settings['frequencies_hz']
        self.freq_index = 0
        self.level_db = float(self.settings.get('start_level_dbhl', 40))  # livello iniziale
        self.ear = "R"

    # ---------------- Utils ----------------
    def set_ear(self, ear):
        self.ear = "R" if ear == "R" else "L"
        try:
            self.ui._call(self.ui.manual_on_cursor, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_cursor(self.current_freq(), self.level_db, self.ear)

    def current_freq(self):
        return int(self.freqs[self.freq_index])

    def amplitude_from_dbhl(self, dbhl, freq_hz):
        if hasattr(self.calib, 'get_total_offset'):
            corr = self.calib.get_total_offset(self.ear, freq_hz)
        else:
            corr = self.calib.get_offset(freq_hz)
        adj_db = dbhl + corr
        amp = 0.5 * (10 ** ((adj_db - 60.0)/20.0))
        if amp < 0.0005:
            amp = 0.0005
        if amp > 0.9:
            amp = 0.9
        return float(amp)

    # ---------------- Audio loop (controllato da toggle) ----------------
    def _play_once(self):
        dur_ms = self.settings.get('tone_duration_ms', 1500)
        isi = random.randint(self.settings.get('isi_ms_min', 1200), self.settings.get('isi_ms_max', 2500)) / 1000.0
        f = self.current_freq()
        amp = self.amplitude_from_dbhl(self.level_db, f)
        mono = sine_wave(f, dur_ms/1000.0, self.settings['sample_rate'], amplitude=amp)
        self.player.play_stereo_tone(mono, ear=self.ear)
        time.sleep(isi)

    def _loop(self):
        while not self._stop_evt.is_set():
            if not self._playing:
                break
            try:
                self.ui._call(self.ui.manual_on_status, self.current_freq(), self.level_db, self.ear)
            except Exception:
                self.ui.manual_on_status(self.current_freq(), self.level_db, self.ear)
            try:
                self._play_once()
            except Exception as e:
                try:
                    self.ui.on_error(str(e))
                except Exception:
                    pass
                break

    def _start_play(self):
        if self._playing:
            return
        self._playing = True
        self._stop_evt.clear()
        self._loop_thread = threading.Thread(target=self._loop, daemon=True)
        self._loop_thread.start()

    def _stop_play(self):
        self._playing = False
        self.player.stop()

    # ---------------- API usate dalla UI ----------------
    def start(self):
        # avvio modalità manuale (senza suonare)
        self._stop_evt.clear()
        self._playing = False
        try:
            self.ui._call(self.ui.manual_on_cursor, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_cursor(self.current_freq(), self.level_db, self.ear)

    def stop(self):
        self._stop_evt.set()
        self._stop_play()

    def on_space(self):
        # toggle start/stop
        if self._playing:
            self._stop_play()
        else:
            self._start_play()

    def commit_current(self):
        # memorizza e ferma tono
        self.results.add_result(self.ear, self.current_freq(), self.level_db)
        try:
            self.ui._call(self.ui.manual_on_mark, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_mark(self.current_freq(), self.level_db, self.ear)
        self._stop_play()

    def move_freq(self, delta):
        # cambiare frequenza interrompe la riproduzione
        self._stop_play()
        self.freq_index = max(0, min(len(self.freqs)-1, self.freq_index + delta))
        try:
            self.ui._call(self.ui.manual_on_cursor, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_cursor(self.current_freq(), self.level_db, self.ear)

    def move_level(self, delta_db):
        # cambiare livello interrompe la riproduzione
        self._stop_play()
        step = self.settings.get('step_db', 5)
        new_level = self.level_db + delta_db*step
        new_level = max(self.settings.get('min_level_dbhl', 0), min(self.settings.get('max_level_dbhl', 100), new_level))
        self.level_db = new_level
        try:
            self.ui._call(self.ui.manual_on_cursor, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_cursor(self.current_freq(), self.level_db, self.ear)

    # ---- Supporto per flusso calibrazione ----
    def get_results(self):
        return self.results.to_map_by_ear()

    def clear_results(self):
        self.results.clear()

    # ---- Utility: toggle ear ----
    def toggle_ear(self):
        self.ear = 'L' if self.ear == 'R' else 'R'
        try:
            self.ui._call(self.ui.manual_on_cursor, self.current_freq(), self.level_db, self.ear)
        except Exception:
            self.ui.manual_on_cursor(self.current_freq(), self.level_db, self.ear)
