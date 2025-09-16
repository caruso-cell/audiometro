from __future__ import annotations
from typing import Dict, List


SEVERITY = [
    (0, 20, "normale"),
    (21, 40, "lieve"),
    (41, 55, "moderata"),
    (56, 70, "moderata-grave"),
    (71, 90, "grave"),
    (91, 999, "profonda"),
]


def _classify(db: float) -> str:
    for lo, hi, lab in SEVERITY:
        if lo <= db <= hi:
            return lab
    return SEVERITY[-1][2]


def _pta(map_: Dict[int, float], bands=(500, 1000, 2000)) -> float:
    vals = [map_.get(f) for f in bands if f in map_]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def generate_analysis_text(results_map: Dict[str, Dict[int, float]], freqs: List[int]) -> str:
    """Crea una breve analisi descrittiva dell'audiogramma (non diagnostica)."""
    L = results_map.get('L', {}) or {}
    R = results_map.get('R', {}) or {}
    pta_L = _pta(L)
    pta_R = _pta(R)
    sev_L = _classify(pta_L)
    sev_R = _classify(pta_R)

    def slope(m: Dict[int, float]) -> str:
        low = m.get(500)
        high = m.get(4000)
        if low is None or high is None:
            return ""
        delta = high - low
        if delta >= 20:
            return " andamento discendente alle alte frequenze"
        if delta <= -20:
            return " andamento ascendente verso le alte frequenze"
        return " andamento relativamente piatto"

    def asymmetry(a: Dict[int, float], b: Dict[int, float]) -> str:
        consec = 0
        for f in freqs:
            if f in a and f in b:
                if abs(a[f] - b[f]) >= 15:
                    consec += 1
                    if consec >= 3:
                        return " asimmetria significativa (>=15 dB su >=3 frequenze)"
                else:
                    consec = 0
        return ""

    text = []
    text.append(f"Sintesi non clinica: PTA OD {pta_R:.0f} dB HL ({sev_R}), PTA OS {pta_L:.0f} dB HL ({sev_L}).")
    text.append(f"OD:{slope(R)}; OS:{slope(L)}.")
    asy = asymmetry(R, L)
    if asy:
        text.append(asy.strip())
    text.append("Nota: risultato non diagnostico; per valutazione clinica rivolgersi a professionista e strumenti certificati.")
    return " ".join(text)

