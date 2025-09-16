from __future__ import annotations
import os
from typing import List, Dict, Any

import io
import datetime as dt
import matplotlib.pyplot as plt
# Ensure a font with Latin accents is used in PDFs
plt.rcParams['font.family'] = 'DejaVu Sans'
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg

from ..plotting.audiogram_plot import render_audiogram_image


DISCLAIMER = (
    "Avvertenza: questo software non \u00E8 un dispositivo medico ai sensi del Reg. (UE) 2017/745. "
    "I risultati non hanno validit\u00E0 legale e non sostituiscono esami eseguiti con audiometro certificato."
)


def _title_block(patient: Dict[str, Any], device: str | None, hp_id: str | None) -> str:
    nome = (patient.get('cognome', '') + ' ' + patient.get('nome', '')).strip()
    pid = patient.get('id', '')
    lines = []
    lines.append(f"Assistito: {nome or '(sconosciuto)'}   ID: {pid}")
    if device:
        lines.append(f"Dispositivo audio: {device}")
    if hp_id:
        lines.append(f"ID cuffia: {hp_id}")
    return '\n'.join(lines)


def _fmt_age(birth_date: str | None) -> str:
    if not birth_date:
        return ""
    try:
        y, m, d = [int(x) for x in birth_date.split('-')]
        dob = dt.date(y, m, d)
        today = dt.date.today()
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return f"{years} anni"
    except Exception:
        return ""


def build_pdf_report(
    patient: Dict[str, Any],
    rows: List[List[Any]] | List[Dict[str, Any]],
    device: str | None,
    hp_id: str | None,
    freqs: List[int],
    logo_path: str | None,
    out_pdf_path: str,
    notes: str | None = None,
):
    os.makedirs(os.path.dirname(out_pdf_path) or '.', exist_ok=True)

    with PdfPages(out_pdf_path) as pdf:
        # Cover page with header + disclaimer
        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait
        ax.axis('off')
        y = 0.95
        if logo_path and os.path.exists(logo_path):
            try:
                logo = mpimg.imread(logo_path)
                ax.imshow(logo, extent=(0.05, 0.35, y - 0.07, y), aspect='auto', zorder=1)
            except Exception:
                pass
        ax.text(0.37, y - 0.015, 'Audiofarm Audiometer', fontsize=18, weight='bold', va='top')
        info = _title_block(patient, device, hp_id)
        ax.text(0.05, 0.83, info, fontsize=11, va='top')
        ax.text(0.05, 0.13, DISCLAIMER, fontsize=9, color='#444444', wrap=True)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # Audiogram page
        fig2, ax2 = render_audiogram_image(rows, patient, device, freqs=freqs, out_path=None, dpi=170)
        # Right panel: meta + thresholds table
        ax_meta = fig2.add_axes([0.60, 0.73, 0.35, 0.22])
        ax_meta.axis('off')
        sex = (patient.get('sex') or '').upper()
        dob = patient.get('birth_date') or ''
        age = _fmt_age(dob)
        operator = os.getenv('USERNAME', '')
        when = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
        meta_lines = [
            f"Data esame: {when}",
            f"Operatore: {operator}",
            f"Data nascita: {dob or '-'}   Et\u00E0: {age or '-'}   Sesso: {sex or '-'}",
            f"Metodo: Manuale (tonale, aria)",
        ]
        ax_meta.text(0, 1, '\n'.join(meta_lines), va='top', fontsize=9)

        # Build thresholds map
        def to_map(rows_list):
            m = {'R': {}, 'L': {}}
            for r in rows_list:
                if isinstance(r, dict):
                    ear, f, db = r.get('ear'), int(r.get('freq')), float(r.get('dbhl'))
                else:
                    ear, f, db = r[2], int(r[3]), float(r[4])
                if ear in ('R', 'L'):
                    m[ear][f] = db
            return m

        m_thr = to_map(rows)
        headers = ['Hz'] + [str(f) for f in freqs]
        rowR = ['OD (R)'] + [m_thr['R'].get(f, '-') for f in freqs]
        rowL = ['OS (L)'] + [m_thr['L'].get(f, '-') for f in freqs]
        ax_tbl = fig2.add_axes([0.60, 0.36, 0.35, 0.34])
        ax_tbl.axis('off')
        table_data = [headers, rowR, rowL]
        tbl = ax_tbl.table(cellText=table_data, loc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1.0, 1.2)

        # Notes + signature area
        ax_note = fig2.add_axes([0.05, 0.02, 0.90, 0.28])
        ax_note.axis('off')
        if notes:
            ax_note.text(0, 0.85, 'Note esame:', fontsize=10, weight='bold')
            ax_note.text(0, 0.55, notes, fontsize=9, wrap=True)
        ax_note.text(0, 0.20, 'Firma Operatore: ____________________________', fontsize=9)
        ax_note.text(0.55, 0.20, 'Firma Assistito: ____________________________', fontsize=9)
        pdf.savefig(fig2, bbox_inches='tight')
        plt.close(fig2)

    return out_pdf_path


def build_pdf_report_v2(
    patient: Dict[str, Any],
    rows: List[List[Any]] | List[Dict[str, Any]],
    device: str | None,
    hp_id: str | None,
    freqs: List[int],
    logo_path: str | None,
    out_pdf_path: str,
    notes: str | None = None,
):
    """Two-page clean layout: page 1 audiogram; page 2 meta+tabella+note. Small header with logo on each page."""
    os.makedirs(os.path.dirname(out_pdf_path) or '.', exist_ok=True)

    def draw_header(fig, title_text: str):
        """Draw small header with logo preserving aspect ratio."""
        header_top = 0.97
        header_h = 0.06
        left = 0.05
        title_x = left
        if logo_path and os.path.exists(logo_path):
            try:
                img = mpimg.imread(logo_path)
                ih, iw = img.shape[0], img.shape[1]
                target_h = header_h * 0.8
                target_w = max(0.01, target_h * (iw / ih))
                ax_logo = fig.add_axes([left, header_top - target_h, target_w, target_h])
                ax_logo.axis('off')
                ax_logo.imshow(img)
                title_x = left + target_w + 0.02
            except Exception:
                title_x = left
        ax_title = fig.add_axes([title_x, header_top - header_h * 0.9, 0.9 - title_x, header_h])
        ax_title.axis('off')
        ax_title.text(0.0, 0.5, title_text, fontsize=12, weight='bold', va='center')

    with PdfPages(out_pdf_path) as pdf:
        # Page 1: audiogram + notes (no overlap)
        fig = plt.figure(figsize=(8.27, 11.69)); draw_header(fig, 'Audiofarm Audiometer')
        pfig, _ = render_audiogram_image(rows, patient, device, freqs=freqs, out_path=None, dpi=170)
        buf = io.BytesIO(); pfig.savefig(buf, format='png', dpi=170, bbox_inches='tight'); plt.close(pfig); buf.seek(0)
        ax_img = fig.add_axes([0.05, 0.42, 0.90, 0.46]); ax_img.axis('off'); ax_img.imshow(mpimg.imread(buf))
        # Notes section
        ax_note = fig.add_axes([0.05, 0.18, 0.90, 0.20]); ax_note.axis('off')
        ax_note.text(0, 0.95, 'Note esame:', fontsize=11, weight='bold', va='top')
        if notes: ax_note.text(0, 0.88, notes, fontsize=10, wrap=True, va='top')
        # Footer disclaimer (wrap + unicode accents)
        axf = fig.add_axes([0.05, 0.06, 0.90, 0.06]); axf.axis('off')
        try:
            import textwrap as _tw
            _disc = _tw.fill(DISCLAIMER, width=130)
        except Exception:
            _disc = DISCLAIMER
        axf.text(0.0, 0.5, _disc, fontsize=8, color='#555555', va='center')
        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

        # Page 2: meta + thresholds table (no notes)
        fig2 = plt.figure(figsize=(8.27, 11.69)); draw_header(fig2, 'Audiofarm Audiometer')
        sex = (patient.get('sex') or '').upper(); dob = patient.get('birth_date') or ''; age = _fmt_age(dob)
        operator = os.getenv('USERNAME', ''); when = dt.datetime.now().strftime('%d/%m/%Y %H:%M')
        info = _title_block(patient, device, hp_id)
        meta_lines = [info, f'Data esame: {when}    Operatore: {operator}', f'Data nascita: {dob or "-"}    Et\u00E0: {age or "-"}    Sesso: {sex or "-"}', 'Metodo: Manuale (tonale, aria)']
        ax_meta = fig2.add_axes([0.05, 0.82, 0.90, 0.12]); ax_meta.axis('off'); ax_meta.text(0,1,'\n'.join(meta_lines), va='top', fontsize=10)

        # Tabella soglie
        def to_map(rows_list):
            m = {'R': {}, 'L': {}}
            for r in rows_list:
                if isinstance(r, dict): ear, f, db = r.get('ear'), int(r.get('freq')), float(r.get('dbhl'))
                else: ear, f, db = r[2], int(r[3]), float(r[4])
                if ear in ('R','L'): m[ear][f] = db
            return m
        mthr = to_map(rows)
        headers = ['Hz'] + [str(f) for f in freqs]
        rowR = ['OD (R)'] + [mthr['R'].get(f, '-') for f in freqs]
        rowL = ['OS (L)'] + [mthr['L'].get(f, '-') for f in freqs]
        ax_tbl = fig2.add_axes([0.05, 0.58, 0.90, 0.18]); ax_tbl.axis('off')
        tbl = ax_tbl.table(cellText=[headers, rowR, rowL], loc='center'); tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1.1,1.3)

        # Firme
        ax_sig = fig2.add_axes([0.05, 0.05, 0.90, 0.06]); ax_sig.axis('off')
        ax_sig.text(0.0, 0.5, 'Firma Operatore: ____________________________', fontsize=9)
        ax_sig.text(0.55, 0.5, 'Firma Assistito: ____________________________', fontsize=9)
        pdf.savefig(fig2, bbox_inches='tight'); plt.close(fig2)

    return out_pdf_path


def build_pdf_report_v3(
    patient: Dict[str, Any],
    rows: List[List[Any]] | List[Dict[str, Any]],
    device: str | None,
    hp_id: str | None,
    freqs: List[int],
    logo_path: str | None,
    out_pdf_path: str,
    notes: str | None = None,
):
    """Single-page A4 layout: header with small logo, two columns (operatore/paziente),
    audiogram, notes, signature lines, and disclaimer at bottom.
    """
    os.makedirs(os.path.dirname(out_pdf_path) or '.', exist_ok=True)

    def draw_header(fig, title_text: str):
        header_top = 0.97
        header_h = 0.06
        left = 0.05
        title_x = left
        if logo_path and os.path.exists(logo_path):
            try:
                img = mpimg.imread(logo_path)
                ih, iw = img.shape[0], img.shape[1]
                target_h = header_h * 0.8
                target_w = max(0.01, target_h * (iw / ih))
                ax_logo = fig.add_axes([left, header_top - target_h, target_w, target_h])
                ax_logo.axis('off')
                ax_logo.imshow(img)
                title_x = left + target_w + 0.02
            except Exception:
                title_x = left
        ax_title = fig.add_axes([title_x, header_top - header_h * 0.9, 0.9 - title_x, header_h])
        ax_title.axis('off')
        ax_title.text(0.0, 0.5, title_text, fontsize=12, weight='bold', va='center')

    def _wrap_line(s: str, max_chars: int = 60) -> str:
        try:
            import textwrap
            return "\n".join(textwrap.wrap(s, width=max_chars)) if s else s
        except Exception:
            return s

    with PdfPages(out_pdf_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        draw_header(fig, 'Audiofarm Audiometer')

        sex = (patient.get('sex') or '').upper()
        dob = patient.get('birth_date') or ''
        try:
            y, m, d = [int(x) for x in dob.split('-')]
            today = dt.date.today()
            years = today.year - y - ((today.month, today.day) < (m, d))
            age = f"{years} anni"
        except Exception:
            age = ''
        operator = os.getenv('USERNAME', '')
        when = dt.datetime.now().strftime('%d/%m/%Y %H:%M')

        # Operatore (left) with device info.
        ax_left = fig.add_axes([0.06, 0.75, 0.42, 0.16]); ax_left.axis('off')
        left_lines = [
            'Operatore',
            f'Nome: {operator or "-"}',
            f'Data esame: {when}',
            'Metodo: Manuale (tonale, aria)'
        ]
        if device:
            left_lines.append(f'Dispositivo audio: {device}')
        if hp_id:
            left_lines.append(f'ID cuffia: {hp_id}')
        ax_left.text(0, 1, '\n'.join(_wrap_line(l) for l in left_lines), va='top', fontsize=11)

        # Paziente (right)
        ax_right = fig.add_axes([0.52, 0.75, 0.42, 0.16]); ax_right.axis('off')
        right_lines = [
            'Assistito',
            f'ID: {patient.get("id","")}',
            f'Nome: {(patient.get("cognome","") + " " + patient.get("nome"," ")).strip()}',
            f'Data nascita: {dob or "-"}    Et\u00E0: {age or "-"}',
            f'Sesso: {sex or "-"}',
        ]
        ax_right.text(0, 1, '\n'.join(_wrap_line(l) for l in right_lines), va='top', fontsize=11)

        # Audiogram
        pfig, _ = render_audiogram_image(rows, patient, device, freqs=freqs, out_path=None, dpi=170)
        buf = io.BytesIO(); pfig.savefig(buf, format='png', dpi=170); plt.close(pfig); buf.seek(0)
        ax_img = fig.add_axes([0.05, 0.42, 0.90, 0.36]); ax_img.axis('off'); ax_img.imshow(mpimg.imread(buf))

        # Notes
        ax_note = fig.add_axes([0.05, 0.20, 0.90, 0.18]); ax_note.axis('off')
        ax_note.text(0, 0.95, 'Note esame:', fontsize=11, weight='bold', va='top')
        if notes:
            try:
                import textwrap as _tw
                _wrapped_notes = _tw.fill(notes, width=110)
            except Exception:
                _wrapped_notes = notes
            ax_note.text(0, 0.88, _wrapped_notes, fontsize=10, va='top')

        # Signatures
        ax_sig = fig.add_axes([0.05, 0.12, 0.90, 0.06]); ax_sig.axis('off')
        ax_sig.text(0.0, 0.5, 'Timbro e Firma Operatore: ____________________________', fontsize=9)
        ax_sig.text(0.55, 0.5, 'Firma Assistito: ____________________________', fontsize=9)

        # Footer disclaimer
        axf = fig.add_axes([0.05, 0.05, 0.90, 0.05]); axf.axis('off')
        try:
            import textwrap as _tw2
            _disc = _tw2.fill(DISCLAIMER, width=130)
        except Exception:
            _disc = DISCLAIMER
        axf.text(0.0, 0.5, _disc, fontsize=8, color='#555555', va='center')

        # Keep strict A4 size; do not use bbox_inches='tight'
        pdf.savefig(fig); plt.close(fig)

    return out_pdf_path

