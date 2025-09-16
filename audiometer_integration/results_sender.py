import datetime
try: import requests
except Exception: requests=None
def build_payload(patient, meta, results):
    ts = meta.get('timestamp') or datetime.datetime.now().isoformat()
    s = {'patientId':patient.get('patient_id',''),'timestamp':ts,'operator':meta.get('operator',''),'device':meta.get('device',''),'calibrationRef':meta.get('calibrationRef',''),'note':meta.get('note','')}
    soglie=[]; 
    for ear in ('R','L'):
        for hz,db in results.get(ear,[]): soglie.append({'ear':ear,'hz':int(hz),'dbhl':float(db),'masked':False,'method':meta.get('method','HW')})
    return {'screening':s,'soglie':soglie}
def post_results(url, auth_header, payload, dry_run=False):
    if dry_run or not url: return {'ok':True,'dry_run':True,'payload':payload}
    if requests is None: return {'ok':False,'error':"requests non disponibile"}
    try:
        h={'Content-Type':'application/json'}; 
        if auth_header: h.update(auth_header)
        r=requests.post(url, json=payload, headers=h, timeout=12); r.raise_for_status()
        return r.json() if 'application/json' in r.headers.get('Content-Type','') else {'ok':True,'text':r.text}
    except Exception as e: return {'ok':False,'error':str(e)}
def send_chat_message(webhook_url, text):
    if not webhook_url or requests is None: return None
    try: requests.post(webhook_url, json={'text':text}, timeout=8); return {'ok':True}
    except Exception as e: return {'ok':False,'error':str(e)}
