from __future__ import annotations
import os
import json
from typing import Dict, List, Optional, Sequence
import base64

import requests

from .prompt_loader import load_prompt_text


def _compose_prompt(patient: Dict, results_map: Dict[str, Dict[int, float]], freqs: List[int]) -> str:
    base = load_prompt_text() or "Analizza il seguente audiogramma e scrivi una sintesi non diagnostica."
    name = (patient.get('cognome','') + ' ' + patient.get('nome','')).strip()
    sex = patient.get('sex') or ''
    dob = patient.get('birth_date') or ''
    lines = [base.strip(), "", "[DATI ASSISTITO]", f"ID: {patient.get('id','')}", f"Nome: {name}", f"Data nascita: {dob}", f"Sesso: {sex}"]
    lines += ["", "[SOGLIE dB HL]"]
    def row_for(ear):
        out: List[str] = []
        em = results_map.get(ear, {}) or {}
        for f in freqs:
            v = em.get(f)
            out.append(str(v) if v is not None else '-')
        return out
    header = "Hz," + ",".join(str(f) for f in freqs)
    rrow = "OD (R)," + ",".join(row_for('R'))
    lrow = "OS (L)," + ",".join(row_for('L'))
    lines += [header, rrow, lrow]
    lines += ["", "[RICHIESTA] Scrivi una breve sintesi in italiano, non diagnostica, chiara al paziente."]
    return "\n".join(lines)


def _b64_png(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def _openai_chat_payload(prompt: str, images_png: Optional[Sequence[bytes]], model: str) -> Dict[str, object]:
    # Build Chat Completions payload with text + image_url content
    content: List[Dict[str, object]] = [{"type": "text", "text": prompt}]
    if images_png:
        for b in images_png:
            try:
                if not isinstance(b, (bytes, bytearray)):
                    continue
                b64 = _b64_png(b)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })
            except Exception:
                continue
    return {
        "model": model,
        "messages": [
            {"role": "user", "content": content}
        ]
    }


def generate_analysis_via_prompt(
    patient: Dict,
    results_map: Dict[str, Dict[int, float]],
    freqs: List[int],
    images_png: Optional[Sequence[bytes]] = None,
) -> str:
    """Calls OpenAI Chat Completions API (ChatGPT) with text + images.

    Requires OPENAI_API_KEY (or AI_API_KEY). Optional: AI_MODEL/OPENAI_MODEL.
    Fallback returns the plain prompt text if no key or on error.
    """
    prompt = _compose_prompt(patient, results_map, freqs)
    api_key = os.getenv('OPENAI_API_KEY') or os.getenv('AI_API_KEY')
    if not api_key:
        return prompt
    endpoint = 'https://api.openai.com/v1/chat/completions'
    model = os.getenv('AI_MODEL') or os.getenv('OPENAI_MODEL') or 'gpt-4o-mini'
    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        org = os.getenv('OPENAI_ORG') or os.getenv('OPENAI_ORGANIZATION')
        if org:
            headers["OpenAI-Organization"] = org
        payload = _openai_chat_payload(prompt, images_png, model)
        resp = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=45)
        if resp.ok:
            data = resp.json()
            txt = (
                data.get('text')
                or data.get('message')
                or (data.get('choices', [{}])[0].get('message', {}).get('content'))
            )
            if isinstance(txt, str) and txt.strip():
                return txt.strip()
        else:
            try:
                return f"__AI_ERROR__ status={resp.status_code} body={resp.text[:500]}"
            except Exception:
                return "__AI_ERROR__"
    except Exception:
        pass
    return prompt
