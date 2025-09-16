# Repository Guidelines

## Project Structure & Module Organization
- `audiometer/`: core package
  - `audio/` (devices, tones, calibration), `ui/` (Tk UI), `screening/` (manual test, exporter), `plotting/`, `models/`, `storage/`.
- `audiometer_integration/`: headless integration entrypoints (`main.py`, `screening.py`).
- `main.py`: desktop app entry; `launch_screening.py`: runs integration flow.
- `pyi_spec/` and `pyi_build/`, `dist/`, `build/`: PyInstaller spec, work dirs, and build outputs.
- `data/`: local assets/scratch; patient data is stored under OS app data (see `audiometer/paths.py`).
- `.env.example`: copy to `.env` to enable web export.

## Build, Test, and Development Commands
- Create env (Windows): `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`
- Run app: `.venv\Scripts\python main.py`
- Run integration: `.venv\Scripts\python audiometer_integration\main.py` (or `python launch_screening.py`)
- Build binary (PyInstaller): `pyinstaller --noconfirm --clean --workpath pyi_build --distpath dist pyi_spec/AudiofarmAudiometer.spec`
- Env config: copy `.env.example` to `.env` and set `WEBAPP_URL`, `AUTH_TOKEN`.
- One‑shot builder (Windows): `powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1` (creates venv, installs deps, builds to `dist/`).
- Icon: place `app.ico` (or `icona.ico` / `icona.png`) in `data/`; builder will copy/convert to `assets/app.ico` automatically.
 - MSI installer (WiX): `powershell -ExecutionPolicy Bypass -File scripts\build_msi.ps1` (requires WiX Toolset on PATH: `heat`, `candle`, `light`).

### New split projects
- Main app (GUI): this repo root. Headphone calibration UI/features are disabled by default (`enable_calibration=false` in settings).
- Standalone headphone calibrator: `headphone_calibrator/` (separate venv recommended). Use its `README.md` and `requirements.txt`.

## Coding Style & Naming Conventions
- Python 3.11+; PEP 8; 4‑space indentation; UTF‑8.
- Names: modules/files `snake_case.py`, functions `snake_case`, classes `CapWords`.
- Keep UI strings Italian; keep identifiers/comments English where possible.
- Prefer type hints and module‑level constants; avoid side effects at import time.

## Testing Guidelines
- No formal test suite yet. Add `pytest` tests under `tests/` as `test_*.py` when contributing.
- Smoke test: run `python main.py`, exercise manual screening, verify export and saved artifacts under `%LOCALAPPDATA%/AudiofarmAudiometer/patients/<ID>/screenings/` (JSON + PNG).
- Provide steps-to-reproduce for any bug fix.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise subject (≤72 chars). Optional scope tags like `[ui]`, `[audio]`, `[integration]`.
- PRs: include summary, linked issues, test notes (commands + expected behavior), and screenshots of UI changes.
- Do not commit `.env`, patient data, or secrets. Large binaries belong in `dist/` only via builds.

## Security & Configuration Tips
- Secrets live in `.env` only; never in code or Git history.
- Calibration/settings defaults are copied to OS app data on first run (see `audiometer/paths.py`).
- Windows custom protocol: edit `scripts\register_protocol_windows.reg` to point to the correct executable path before importing.

## Agent Startup Hints

When a new Codex session starts in this repo, please load the following context to resume quickly:

- Open `.codex_session/SESSION.md` and `.codex_session/session_context.json` for session summary and commands.
- Open these code files in the editor for continuation:
  - `audiometer/ui/main_window.py`
  - `audiometer/screening/test_runner.py`
  - `audiometer/screening/manual_test.py`
  - `audiometer/app_controller.py`
- Tail the runtime log if the exe was run previously: `dist/AudiofarmAudiometer/audiometer.log`.

Helper command:

- `powershell -ExecutionPolicy Bypass -File scripts/resume_session.ps1`
  - Opens the files above and prints handy run/build commands from the session context.
