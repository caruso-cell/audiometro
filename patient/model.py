from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Patient:
    id: str
    nome: str
    cognome: str
    eta: int
