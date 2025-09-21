from __future__ import annotations
from typing import Any


def export_graph_png(audiogram_view: Any, out_path: str) -> None:
    """
    Salva il grafico corrente come PNG su file.
    """
    audiogram_view.save_png(out_path, hide_crosshair=True)
