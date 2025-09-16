import os
import sys
import json
import tkinter as tk
from tkinter import ttk


BRAND_DEFAULT = {
    "primary": "#0F766E",       # teal
    "primary_dark": "#0B5E57",
    "accent": "#22C55E",        # green accent
    "bg": "#F7F8FA",
    "fg": "#1F2937",
    "muted": "#6B7280",
    "success": "#16A34A",
    "warn": "#D97706",
    "error": "#DC2626",
    "tab_bg": "#FFFFFF",
    "tab_active": "#E6FFFA",
}


def _base_path():
    return getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


def resource_path(*parts: str) -> str:
    base = _base_path()
    return os.path.join(base, *parts)


def load_brand_colors() -> dict:
    path = resource_path("assets", "brand", "brand_colors.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            out = dict(BRAND_DEFAULT)
            out.update({k: str(v) for k, v in (data or {}).items()})
            return out
    except Exception:
        pass
    return dict(BRAND_DEFAULT)


def get_logo_path() -> str | None:
    # Preferred: assets/brand/logo.png
    for fname in ("logo.png", "logo_small.png", "logo.jpg"):
        p = resource_path("assets", "brand", fname)
        if os.path.exists(p):
            return p
    return None


def configure_style(root: tk.Tk, colors: dict | None = None):
    colors = colors or load_brand_colors()
    style = ttk.Style(master=root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=colors["bg"])  # window background
    style.configure("TFrame", background=colors["bg"])  # default frames
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])

    # Header bar
    style.configure("Header.TFrame", background=colors["primary"])
    style.configure("Header.TLabel", background=colors["primary"], foreground="#ffffff", font=("Segoe UI", 13, "bold"))
    style.configure("HeaderNote.TLabel", background=colors["primary"], foreground="#E5E7EB", font=("Segoe UI", 9))

    # Notebook
    style.configure("TNotebook", background=colors["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=colors["tab_bg"], foreground=colors["fg"], padding=(12, 6))
    style.map("TNotebook.Tab",
              background=[("selected", colors["tab_active"])],
              foreground=[("selected", colors["fg"])])

    # Buttons
    style.configure("TButton", padding=(10, 6))
    style.configure("Primary.TButton", background=colors["primary"], foreground="#ffffff")
    style.map("Primary.TButton",
              background=[("active", colors["primary_dark"])])
    style.configure("Accent.TButton", background=colors["accent"], foreground="#0B3D2E")
    style.map("Accent.TButton",
              background=[("active", colors["success"])])
