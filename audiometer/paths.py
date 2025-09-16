import os
import sys
import platform

APP_NAME = "AudiofarmAudiometer"

def _windows_appdata():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    return os.path.join(base, APP_NAME)

def _mac_appdata():
    base = os.path.expanduser("~/Library/Application Support")
    return os.path.join(base, APP_NAME)

def _linux_appdata():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)

def get_app_data_dir(create=True):
    system = platform.system().lower()
    if "windows" in system:
        path = _windows_appdata()
    elif "darwin" in system or "mac" in system:
        path = _mac_appdata()
    else:
        path = _linux_appdata()
    if create:
        os.makedirs(path, exist_ok=True)
    return path

def path_settings():
    return os.path.join(get_app_data_dir(True), "settings.json")

def path_calibrations():
    return os.path.join(get_app_data_dir(True), "calibrations.json")

def ensure_default_file(target_path, default_package_rel):
    """
    If target_path does not exist, copy the default file shipped inside the package
    at 'default_package_rel' (relative to this file's parent directory).
    """
    if os.path.exists(target_path):
        return
    pkg_root = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(pkg_root, default_package_rel)
    try:
        import shutil
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copyfile(default_path, target_path)
    except Exception:
        # If copy fails, create an empty placeholder for JSON files
        if target_path.endswith(".json"):
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("{}")

def get_executable_dir() -> str:
    """Return directory of the executable (PyInstaller) or the repo root when running from sources."""
    try:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        # running from sources: use project root (two levels up from this file)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        return os.getcwd()

def get_log_file_path() -> str:
    try:
        base = get_executable_dir()
        return os.path.join(base, 'audiometer.log')
    except Exception:
        return os.path.join(get_app_data_dir(True), 'audiometer.log')
