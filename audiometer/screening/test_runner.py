import threading
import time
import random
from collections import Counter

from ..audio.tone_generator import sine_wave
from ..audio.playback import TonePlayer

class TestRunner:
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
        self._space_evt = threading.Event()
        self._worker = None

    def amplitude_from_dbhl(self, dbhl, freq_hz, ear):
        try:
            if hasattr(self.calib, 'get_total_offset'):
                corr = self.calib.get_total_offset(ear, freq_hz)
            else:
                corr = self.calib.get_offset(freq_hz)
        except Exception:
            corr = 0.0
        adj_db = dbhl + corr
        amp = 0.5 * (10 ** ((adj_db - 60.0)/20.0))
        if amp < 0.0005: amp = 0.0005
        if amp > 0.9: amp = 0.9
        return float(amp)

    def play_single_tone(self, freq_hz, level_dbhl, ear, duration_ms=None):
        duration_ms = duration_ms or self.settings.get('tone_duration_ms', 1500)
        mono = sine_wave(freq_hz, duration_ms/1000.0, self.settings['sample_rate'], amplitude=self.amplitude_from_dbhl(level_dbhl, freq_hz, ear))
        self.player.play_stereo_tone(mono, ear=ear)

    def start_test(self, ear):
        if self._worker and self._worker.is_alive():
            return
        self._stop_evt.clear()
        self._space_evt.clear()
        self._worker = threading.Thread(target=self._run_test, args=(ear,), daemon=True)
        self._worker.start()

    def cancel_test(self):
        self._stop_evt.set()
        self.player.stop()

    def on_space_pressed(self):
        self._space_evt.set()

    def _ascend_until_heard(self, ear, freq, start_level, max_level, step, tone_ms):
        level = start_level
        while level <= max_level and not self._stop_evt.is_set():
            self._space_evt.clear()
            try:
                self.ui._call(self.ui.on_level_changed, ear, freq, level)
            except Exception:
                self.ui.on_level_changed(ear, freq, level)
            try:
                self.play_single_tone(freq, level, ear, duration_ms=tone_ms)
            except Exception as e:
                self.ui.on_error(str(e)); return (False, None)

            heard = self._space_evt.is_set()
            isi = random.randint(self.settings.get('isi_ms_min', 1200), self.settings.get('isi_ms_max', 2500)) / 1000.0
            time.sleep(isi)
            if heard:
                return (True, level)
            level += step
        return (False, None)

    def _verify_until_two_matches_any(self, ear, freq, first_level, min_level, max_level, step, tone_ms):
        counts = Counter()
        counts[first_level] += 1
        cycles = 0
        last_confirmed = first_level

        while not self._stop_evt.is_set():
            cycles += 1
            if cycles > int(self.settings.get('verification_max_cycles', 8)):
                maxc = max(counts.values())
                candidates = [lvl for lvl, c in counts.items() if c == maxc]
                return min(candidates)

            restart = max(min_level, last_confirmed - 2*step)
            try:
                self.ui._call(self.ui.on_frequency_started, ear, freq)
            except Exception:
                self.ui.on_frequency_started(ear, freq)
            heard, level = self._ascend_until_heard(ear, freq, restart, max_level, step, tone_ms)
            if not heard:
                maxc = max(counts.values())
                candidates = [lvl for lvl, c in counts.items() if c == maxc]
                return min(candidates)

            counts[level] += 1
            last_confirmed = level
            if counts[level] >= 2:
                return level

        maxc = max(counts.values())
        candidates = [lvl for lvl, c in counts.items() if c == maxc]
        return min(candidates)

    def _run_test(self, ear):
        freqs = self.settings['frequencies_hz']
        minlv = self.settings['min_level_dbhl']
        maxlv = self.settings.get('max_level_dbhl', 100)
        step  = self.settings['step_db']
        tone_ms = self.settings.get('tone_duration_ms', 1500)

        try:
            self.ui._call(self.ui.on_test_started, ear)
        except Exception:
            self.ui.on_test_started(ear)

        for f in freqs:
            if self._stop_evt.is_set():
                break
            try:
                self.ui._call(self.ui.on_frequency_started, ear, f)
            except Exception:
                self.ui.on_frequency_started(ear, f)

            heard, L1 = self._ascend_until_heard(ear, f, minlv, maxlv, step, tone_ms)
            if not heard:
                self.results.add_result(ear, f, maxlv)
                try:
                    self.ui._call(self.ui.on_threshold_captured, ear, f, maxlv)
                except Exception:
                    self.ui.on_threshold_captured(ear, f, maxlv)
                continue

            thr = self._verify_until_two_matches_any(ear, f, L1, minlv, maxlv, step, tone_ms)
            self.results.add_result(ear, f, thr)
            try:
                self.ui._call(self.ui.on_threshold_captured, ear, f, thr)
            except Exception:
                self.ui.on_threshold_captured(ear, f, thr)

        try:
            self.ui._call(self.ui.on_test_finished, ear)
        except Exception:
            self.ui.on_test_finished(ear)
