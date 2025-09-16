import datetime as dt
import os

class ResultsStore:
    def __init__(self):
        # rows: list of dicts {ear, freq, dbhl}
        self.rows = []
        self.notes = ""

    def add_result(self, ear, freq_hz, dbhl):
        self.rows.append({"ear": ear, "freq": int(freq_hz), "dbhl": float(dbhl)})

    def clear(self):
        self.rows = []

    def to_rows(self, patient):
        # Returns table rows for UI
        out = []
        for r in self.rows:
            out.append([patient["id"], f"{patient['cognome']} {patient['nome']}", r["ear"], r["freq"], r["dbhl"]])
        return out

    def to_payload(self, patient):
        # Payload for Apps Script
        return {
            "screening": {
                "patientId": patient["id"],
                "timestamp": dt.datetime.now().isoformat(),
                "operator": os.getenv("USERNAME", "Operatore"),
                "device": "Headphones",
                "calibrationRef": "ManualRelative",
                "note": self.notes or ""
            },
            "soglie": [
                {"ear": r["ear"], "hz": r["freq"], "dbhl": r["dbhl"], "masked": False, "method": "StepDownSpace"}
                for r in self.rows
            ],
            "analysis": self.notes or ""
        }

    def to_map_by_ear(self):
        """Aggrega risultati in {'L': {freq: db}, 'R': {...}} (ultima misura per freq vince)."""
        out = {'L': {}, 'R': {}}
        for r in self.rows:
            ear = 'R' if r.get('ear') == 'R' else 'L'
            out[ear][int(r.get('freq'))] = float(r.get('dbhl'))
        return out

    # Notes API
    def set_notes(self, text: str):
        self.notes = text or ""

    def get_notes(self) -> str:
        return self.notes or ""
