from __future__ import annotations
from typing import Dict

_REPORTLAB_AVAILABLE = True

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader, simpleSplit
except Exception:  # pragma: no cover - opzionale
    _REPORTLAB_AVAILABLE = False


def _ensure_reportlab() -> None:
    if not _REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab non disponibile: installa il pacchetto 'reportlab'.")


def _draw_box(c: "canvas.Canvas", title: str, text: str, x: float, y: float, width: float, height: float) -> None:
    c.rect(x, y - height, width, height, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 6, y - 16, title)
    c.setFont("Helvetica", 9)
    lines = simpleSplit(text or "", "Helvetica", 9, width - 12)
    text_y = y - 28
    for line in lines:
        if text_y < y - height + 12:
            break
        c.drawString(x + 6, text_y, line)
        text_y -= 12


def build_pdf_report_v3(
    out_pdf_path: str,
    patient: Dict,
    device: Dict,
    exam: Dict,
    notes: str,
    esito_ai: str,
    png_graph_path: str,
    table_text: str,
    ai_prompt: str,
) -> None:
    """Genera un report PDF con grafico e note."""
    _ensure_reportlab()

    c = canvas.Canvas(out_pdf_path, pagesize=A4)
    width, height = A4
    margin = 20 * mm

    y = height - margin
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "Audiometria tonale manuale")
    y -= 18
    c.setFont("Helvetica", 10)
    patient_line = f"Assistito: {patient.get('cognome', '')} {patient.get('nome', '')} (ID {patient.get('id', '-')})"
    c.drawString(margin, y, patient_line.strip())
    y -= 12
    c.drawString(margin, y, f"Eta: {patient.get('eta', 'n/d')}")
    y -= 12
    device_line = f"Dispositivo: {device.get('name', 'n/d')} ({device.get('wasapi_id', 'n/d')})"
    c.drawString(margin, y, device_line)
    y -= 12
    c.drawString(margin, y, f"Data esame: {exam.get('created_at', 'n/d')}")
    y -= 18

    graph_height = 100 * mm
    graph_width = width - 2 * margin
    c.drawImage(ImageReader(png_graph_path), margin, y - graph_height, graph_width, graph_height, preserveAspectRatio=True)
    y -= graph_height + 16

    table_height = 40 * mm
    _draw_box(c, "Risultati (dB HL)", table_text, margin, y, graph_width, table_height)
    y -= table_height + 12

    box_width = width - 2 * margin
    _draw_box(c, "Note", notes, margin, y, box_width, 40 * mm)
    y -= 40 * mm + 12
    c.showPage()
    c.save()
