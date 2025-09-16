import numpy as np

def sine_wave(freq_hz, duration_s, sample_rate, amplitude=0.2, phase=0.0):
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    wave = amplitude * np.sin(2 * np.pi * freq_hz * t + phase)
    return wave.astype(np.float32)
