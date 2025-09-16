import numpy as np
import sounddevice as sd

class TonePlayer:
    def __init__(self, sample_rate, left_index=0, right_index=1):
        self.sample_rate = sample_rate
        self.left_index = left_index
        self.right_index = right_index

    def play_stereo_tone(self, mono, ear="R"):
        # ear: "R"=OD (right channel), "L"=OS (left channel)
        left = np.zeros_like(mono)
        right = np.zeros_like(mono)
        if ear == "R":
            right = mono
        else:
            left = mono
        stereo = np.column_stack((left, right)).astype(np.float32, copy=False)
        try:
            # Ensure sane defaults to avoid backend mismatches
            try:
                sd.default.samplerate = self.sample_rate
                sd.default.channels = 2
                sd.default.dtype = 'float32'
            except Exception:
                pass
            # Non-blocking play + sleep for buffer duration; safer than blocking
            sd.stop()
            sd.play(stereo, self.sample_rate, blocking=False)
            try:
                duration_ms = int(1000 * (len(mono) / float(self.sample_rate)))
                sd.sleep(max(0, duration_ms + 10))
            except Exception:
                pass
        except Exception as e:
            # Avoid crashing the whole app; bubble as RuntimeError
            raise RuntimeError(f"Riproduzione audio fallita: {e}")

    def stop(self):
        try:
            sd.stop()
        except Exception:
            pass
