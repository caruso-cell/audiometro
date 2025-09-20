import numpy as np
import sounddevice as sd


class TonePlayer:
    def __init__(self, sample_rate, left_index=0, right_index=1):
        self.sample_rate = sample_rate
        self.channel_map = {"L": int(left_index), "R": int(right_index)}

    def set_channel_map(self, left_index: int | None = None, right_index: int | None = None) -> None:
        if left_index is not None:
            try:
                self.channel_map["L"] = int(left_index)
            except (TypeError, ValueError):
                pass
        if right_index is not None:
            try:
                self.channel_map["R"] = int(right_index)
            except (TypeError, ValueError):
                pass

    def _channel_count(self) -> int:
        idxs = [idx for idx in self.channel_map.values() if isinstance(idx, int)]
        if not idxs:
            return 2
        return max(max(idxs) + 1, 1)

    def play_stereo_tone(self, mono, ear="R"):
        # ear: "R"=OD (right channel), "L"=OS (left channel)
        channel_key = "R" if ear == "R" else "L"
        channel_index = self.channel_map.get(channel_key)
        if not isinstance(channel_index, int) or channel_index < 0:
            channel_index = 0 if channel_key == "L" else 1
        channel_count = max(channel_index + 1, self._channel_count())
        buffer = np.zeros((len(mono), channel_count), dtype=np.float32)
        buffer[:, channel_index] = mono.astype(np.float32, copy=False)
        try:
            try:
                sd.default.samplerate = self.sample_rate
                sd.default.channels = channel_count
                sd.default.dtype = 'float32'
            except Exception:
                pass
            sd.stop()
            sd.play(buffer, self.sample_rate, blocking=False)
            try:
                duration_ms = int(1000 * (len(mono) / float(self.sample_rate)))
                sd.sleep(max(0, duration_ms + 10))
            except Exception:
                pass
        except Exception as e:
            raise RuntimeError(f"Riproduzione audio fallita: {e}")

    def stop(self):
        try:
            sd.stop()
        except Exception:
            pass
