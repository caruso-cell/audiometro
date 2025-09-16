from __future__ import annotations
import os
from typing import Optional

from ..ui.theme import resource_path


PROMPT_REL_PATH = ("assets", "promptanalisi audiogramma.txt")


def prompt_file_path() -> str:
    return resource_path(*PROMPT_REL_PATH)


def load_prompt_text() -> Optional[str]:
    path = prompt_file_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        return None
    return None

