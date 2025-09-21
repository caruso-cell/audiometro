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
        # Logo with preserved aspect ratio
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
        ax_title = fig.add_axes([title_x, header_top - header_h*0.9, 0.9 - title_x, header_h])
        ax_title.axis('off')
        ax_title.text(0.0, 0.5, title_text, fontsize=12, weight='bold', va='center')

    with PdfPages(out_pdf_path) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        draw_header(fig, 'Audiofarm Audiometer')

        # Two columns: left=Operatore, right=Paziente
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

        ax_left = fig.add_axes([0.06, 0.80, 0.42, 0.12]); ax_left.axis('off')
        left_lines = [
            'Operatore',
            f'Nome: {operator or "-"}',
            f'Data esame: {when}',
            'Metodo: Manuale (tonale, aria)'
        ]
        ax_left.text(0, 1, '\n'.join(left_lines), va='top', fontsize=11)

        ax_right = fig.add_axes([0.52, 0.80, 0.42, 0.12]); ax_right.axis('off')
        right_lines = [
            'Assistito',
            f'ID: {patient.get("id","")}',
            f'Nome: {(patient.get("cognome","") + " " + patient.get("nome"," ")).strip()}',
            f'Data nascita: {dob or "-"}    Et : {age or "-"}    Sesso: {sex or "-"}',
            f'Dispositivo audio: {device or "-"}    ID cuffia: {hp_id or "-"}'
        ]
        ax_right.text(0, 1, '\n'.join(right_lines), va='top', fontsize=11)

        # Audiogram (render to image to avoid overlaps)
        pfig, pax = render_audiogram_image(rows, patient, device, freqs=freqs, out_path=None, dpi=170)
        buf = io.BytesIO(); pfig.savefig(buf, format='png', dpi=170, bbox_inches='tight'); plt.close(pfig); buf.seek(0)
        ax_img = fig.add_axes([0.05, 0.42, 0.90, 0.36]); ax_img.axis('off'); ax_img.imshow(mpimg.imread(buf))

        # Notes (more space)
        ax_note = fig.add_axes([0.05, 0.20, 0.90, 0.18]); ax_note.axis('off')
        ax_note.text(0, 0.95, 'Note esame:', fontsize=11, weight='bold', va='top')
        if notes:
            ax_note.text(0, 0.88, notes, fontsize=10, wrap=True, va='top')

        # Signatures area
        ax_sig = fig.add_axes([0.05, 0.12, 0.90, 0.06]); ax_sig.axis('off')
        ax_sig.text(0.0, 0.5, 'Timbro e Firma Operatore: ____________________________', fontsize=9)
        ax_sig.text(0.55, 0.5, 'Firma Assistito: ____________________________', fontsize=9)

        # Footer disclaimer
        axf = fig.add_axes([0.05, 0.05, 0.90, 0.05]); axf.axis('off')
        axf.text(0.0, 0.5, DISCLAIMER, fontsize=8, color='#555555', va='center')

        pdf.savefig(fig, bbox_inches='tight'); plt.close(fig)

    return out_pdf_path

