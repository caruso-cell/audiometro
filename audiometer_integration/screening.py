import time, math, numpy as np
try: import sounddevice as sd
except Exception: sd=None
try: import msvcrt
except Exception: msvcrt=None
class AudiometerScreening:
    def __init__(self, sample_rate=48000, device_index=None, frequencies_hz=None, initial_dbhl=40.0, step_db=5.0, min_dbhl=-10.0, tone_duration_s=0.8, gap_s=0.2, calibration_0dBHL_amplitude=None):
        self.sample_rate=sample_rate; self.device_index=device_index
        self.frequencies_hz=frequencies_hz or [500,1000,2000,4000]
        self.initial_dbhl=initial_dbhl; self.step_db=step_db; self.min_dbhl=min_dbhl
        self.tone_duration_s=tone_duration_s; self.gap_s=gap_s
        self.calibration=calibration_0dBHL_amplitude or {}
    def dbhl_to_amplitude(self,f,db): base=float(self.calibration.get(str(int(f)),0.05)); return float(min(0.95,max(0.0, base*(10**(db/20.0)))))
    def _make_tone(self,freq,amp,dur,ear):
        n=int(dur*self.sample_rate); t=np.arange(n)/self.sample_rate
        wave=np.sin(2*math.pi*float(freq)*t).astype(np.float32)*amp
        a=int(0.01*self.sample_rate); r=int(0.02*self.sample_rate)
        if a>0: wave[:a]*=np.linspace(0,1,a,dtype=np.float32)
        if r>0: wave[-r:]*=np.linspace(1,0,r,dtype=np.float32)
        if ear.upper()=='R': return np.column_stack((np.zeros_like(wave),wave))
        return np.column_stack((wave,np.zeros_like(wave)))
    def _play(self, stereo):
        if sd is None: raise RuntimeError("sounddevice non disponibile")
        sd.play(stereo, self.sample_rate, device=self.device_index, blocking=True)
    def _kbhit_space(self):
        if msvcrt and msvcrt.kbhit():
            ch=msvcrt.getch()
            if ch==b' ': return True
            if ch==b'\x1b': raise KeyboardInterrupt
        return False
    def run_ear(self, ear):
        res=[]; 
        for f in self.frequencies_hz:
            cur=float(self.initial_dbhl); prev=None; thr=None
            while cur>=self.min_dbhl-1e-6:
                self._play(self._make_tone(f, self.dbhl_to_amplitude(f,cur), self.tone_duration_s, ear))
                time.sleep(self.gap_s)
                if self._kbhit_space():
                    thr = prev if prev is not None else cur; break
                prev=cur; cur-=self.step_db
            if thr is None: thr = max(self.min_dbhl, prev if prev is not None else self.initial_dbhl)
            res.append((int(f), float(thr)))
        return res
    def run_both_ears(self): return {'R': self.run_ear('R'), 'L': self.run_ear('L')}
