from __future__ import annotations
from typing import Any


def export_graph_png(audiogram_view: Any, out_path: str) -> None:
    """
    Salva il grafico corrente come PNG su file.
    """
    png_bytes = audiogram_view.export_png_bytes()
    with open(out_path, "wb") as handle:
        handle.write(png_bytes)
