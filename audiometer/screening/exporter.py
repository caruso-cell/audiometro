import json
import requests

def export_results_to_webapp(webapp_url, auth_token, payload):
    if not webapp_url:
        return False, "WEBAPP_URL non configurata (.env)."
    try:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["X-Auth"] = auth_token
        r = requests.post(webapp_url, headers=headers, data=json.dumps(payload), timeout=10)
        if r.ok:
            return True, r.text
        else:
            return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)
