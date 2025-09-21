import os, json, sys, datetime
try:
    # Support package import
    from .param_reader import parse_cli_or_url
    from .screening import AudiometerScreening
    from .results_sender import build_payload, post_results, send_chat_message
except Exception:  # fallback when executed as a script
    from param_reader import parse_cli_or_url
    from screening import AudiometerScreening
    from results_sender import build_payload, post_results, send_chat_message


def load_config(p):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def run():
    args = parse_cli_or_url(sys.argv[1:])
    cfg = load_config(os.path.join(os.path.dirname(__file__), 'config.json')) or load_config(
        os.path.join(os.path.dirname(__file__), 'config_example.json')
    )
    am = AudiometerScreening(
        sample_rate=int(cfg.get('sample_rate', 48000)),
        device_index=cfg.get('audio_device_index', None),
        frequencies_hz=cfg.get('frequencies_hz', [500, 1000, 2000, 4000]),
        initial_dbhl=float(cfg.get('initial_dbhl', 40)),
        step_db=float(cfg.get('step_db', 5)),
        min_dbhl=float(cfg.get('min_dbhl', -10)),
        tone_duration_s=float(cfg.get('tone_duration_s', 0.8)),
        gap_s=float(cfg.get('gap_s', 0.2)),
        calibration_0dBHL_amplitude=cfg.get('calibration_0dBHL_amplitude', {}),
    )
    print('Istruzioni: premi SPAZIO quando NON senti più il tono; ESC per annullare.')
    res = am.run_both_ears()
    meta = {
        'timestamp': datetime.datetime.now().isoformat(),
        'operator': args.get('operator', ''),
        'device': 'PC + Headphones',
        'calibrationRef': 'placeholder-0dBHL',
        'note': args.get('note', ''),
        'method': 'HW',
    }
    payload = build_payload(args, meta, res)
    resp = post_results(
        cfg.get('endpoint_url', ''), cfg.get('endpoint_auth_header', {}), payload, dry_run=bool(cfg.get('dry_run', True))
    )
    print(resp)
    chat_url = cfg.get('google_chat_webhook_url', '')
    if chat_url:
        send_chat_message(chat_url, f"OK. Screening completato per {args.get('full_name','')} (ID {args.get('patient_id','')}).")


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('[Annullato]')
