import os
import json
from datetime import datetime as dt
from .paths import get_app_data_dir

# Directory root per i dati pazienti
def _patients_root():
    root = os.path.join(get_app_data_dir(True), "patients")
    os.makedirs(root, exist_ok=True)
    return root

def patient_dir(patient_id):
    pdir = os.path.join(_patients_root(), str(patient_id).upper())
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(os.path.join(pdir, "screenings"), exist_ok=True)
    return pdir

def _patient_profile_path(patient_id):
    return os.path.join(patient_dir(patient_id), "profile.json")

def _patient_index_path(patient_id):
    return os.path.join(patient_dir(patient_id), "index.json")

def create_patient(patient_id, nome, cognome, eta=None, birth_date=None):
    prof = {"id": str(patient_id).upper(), "nome": nome or "", "cognome": cognome or ""}
    if eta is not None and eta != "":
        prof["eta"] = eta
    if birth_date:
        prof["birth_date"] = birth_date
    with open(_patient_profile_path(patient_id), "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False)
    # ensure index file
    idx_path = _patient_index_path(patient_id)
    if not os.path.exists(idx_path):
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump({"id": prof["id"], "exams": []}, f, indent=2, ensure_ascii=False)
    return prof

def load_patient_profile(patient_id):
    with open(_patient_profile_path(patient_id), "r", encoding="utf-8") as f:
        return json.load(f)

def load_patient_index(patient_id):
    idx_path = _patient_index_path(patient_id)
    if not os.path.exists(idx_path):
        return {"id": str(patient_id).upper(), "exams": []}
    with open(idx_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_exam(patient, payload, ts=None, image_path=None):
    pid = patient["id"]
    if not ts:
        ts = dt.now().strftime("%Y%m%d_%H%M%S")
    pdir = patient_dir(pid)
    # Save JSON
    json_path = os.path.join(pdir, "screenings", f"{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    # Update index
    idx = load_patient_index(pid)
    entry = {"ts": ts, "path": json_path.replace("\\", "/")}
    if image_path:
        entry["image"] = image_path.replace("\\", "/")
    idx.setdefault("exams", []).append(entry)
    with open(_patient_index_path(pid), "w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
    return json_path

def update_patient_profile(patient_id, **fields):
    """Merge provided fields into patient profile and save.
    Creates the profile if missing.
    """
    try:
        prof = load_patient_profile(patient_id)
    except Exception:
        prof = {"id": str(patient_id).upper()}
    changed = False
    for k, v in fields.items():
        if v is None:
            continue
        if prof.get(k) != v:
            prof[k] = v
            changed = True
    if changed or not os.path.exists(_patient_profile_path(patient_id)):
        with open(_patient_profile_path(patient_id), "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2, ensure_ascii=False)
    return prof

def list_patients():
    root = _patients_root()
    out = []
    for pid in sorted(os.listdir(root)):
        pdir = os.path.join(root, pid)
        if not os.path.isdir(pdir):
            continue
        prof_path = os.path.join(pdir, "profile.json")
        idx_path = os.path.join(pdir, "index.json")
        name = ""
        last = ""
        if os.path.exists(prof_path):
            try:
                prof = json.load(open(prof_path, "r", encoding="utf-8"))
                name = f"{prof.get('cognome','')} {prof.get('nome','')}".strip()
            except Exception:
                pass
        if os.path.exists(idx_path):
            try:
                idx = json.load(open(idx_path, "r", encoding="utf-8"))
                if idx.get("exams"):
                    last = idx["exams"][-1].get("ts","")
            except Exception:
                pass
        out.append({"id": pid, "name": name, "last_ts": last})
    return out

def suggest_next_patient_id():
    root = _patients_root()
    base = "PZ"
    i = 1
    exists = set(n.upper() for n in os.listdir(root))
    while True:
        cand = f"{base}{i:04d}"
        if cand not in exists:
            return cand
        i += 1
