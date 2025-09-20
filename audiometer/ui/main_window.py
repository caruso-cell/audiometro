import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from dotenv import load_dotenv
import re
import logging

from ..app_controller import AppController
from ..plotting.audiogram_plot import LiveAudiogram
from .theme import configure_style, get_logo_path, resource_path
from ..export.pdf_report import build_pdf_report_v3 as build_pdf_report
from ..version import __version__

ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")

def run_app():
    load_dotenv()
    root = tk.Tk()
    root.title(f"Audiofarm Audiometer v{__version__}")
    root.geometry("1280x900")
    try:
        # Bring window to front on start (helps if hidden/minimized)
        root.lift()
        root.attributes('-topmost', True)
        root.after(300, lambda: root.attributes('-topmost', False))
        root.update_idletasks()
    except Exception:
        pass
    configure_style(root)
    # Set window icon (runtime) from assets/app.ico or PNG
    try:
        ico = resource_path('assets', 'app.ico')
        if os.path.exists(ico):
            try:
                root.iconbitmap(ico)
            except Exception:
                pass
        else:
            png = resource_path('assets', 'app.png')
            if os.path.exists(png):
                try:
                    img = tk.PhotoImage(file=png)
                    root.iconphoto(True, img)
                except Exception:
                    pass
    except Exception:
        pass
    app = MainWindow(root)
    root.mainloop()

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.callbacks = UICallbacks(self)
        self.controller = AppController(self.callbacks)
        self._logger = logging.getLogger('audiometer.ui')
        try:
            self.debug_ui = bool(self.controller.settings.get('debug_ui_events', True))
        except Exception:
            self.debug_ui = True

        self._build_ui()

    # -------- UI layout --------
    def _build_ui(self):
        # Header con brand e logo
        hdr = ttk.Frame(self.root, style="Header.TFrame")
        hdr.pack(fill=tk.X)
        # Gestione chiusura finestra: stop audio, thread e timer
        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass
        # Logo (ridotto) + titolo + disclaimer
        self.logo_img = None
        lp = get_logo_path()
        if lp:
            try:
                _img = tk.PhotoImage(file=lp)
                # Riduci altezza a ~32px mantenendo proporzioni
                try:
                    h = _img.height()
                    factor = max(1, int(h/32))
                    if factor > 1:
                        _img = _img.subsample(factor, factor)
                except Exception:
                    pass
                self.logo_img = _img
                ttk.Label(hdr, image=self.logo_img, style="Header.TLabel").pack(side=tk.LEFT, padx=(10,6), pady=6)
            except Exception:
                pass
        head = ttk.Frame(hdr, style="Header.TFrame")
        head.pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Label(head, text="Audiofarm Audiometer", style="Header.TLabel").pack(anchor="w")
        disclaimer = (
            "Avvertenza: questo software non Ã¨ un dispositivo medico ai sensi del Reg. (UE) 2017/745. "
            "I risultati non hanno validitÃ  legale e non sostituiscono esami eseguiti con audiometro certificato. "
            "Uso consentito a fini di preâ€‘screening/benessere da personale formato sullâ€™uso del software."
        )
        lbl_note = ttk.Label(head, text=disclaimer, style="HeaderNote.TLabel", wraplength=860, justify="left")
        # Normalize and ensure UTF-8 accents in disclaimer text
        disclaimer_clean = (
            "Avvertenza: questo software non \u00E8 un dispositivo medico ai sensi del Reg. (UE) 2017/745. "
            "I risultati non hanno validit\u00E0 legale e non sostituiscono esami eseguiti con audiometro certificato. "
            "Uso consentito a fini di pre-screening/benessere da personale formato sull'uso del software."
        )
        try:
            lbl_note.configure(text=disclaimer_clean)
        except Exception:
            pass
        lbl_note.pack(anchor="w")

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True)

        # TAB Paziente
        self.tab_patient = ttk.Frame(self.nb); self.nb.add(self.tab_patient, text="Assistito")
        hdr = ttk.Frame(self.tab_patient); hdr.pack(fill=tk.X, pady=8)
        self.lbl_patient = ttk.Label(hdr, text=self.controller.get_patient_display(), font=("Segoe UI", 16))
        self.lbl_patient.pack(side=tk.LEFT, padx=10)

        ttk.Button(hdr, text="Nuovo assistito", command=self._open_new_patient_modal).pack(side=tk.RIGHT, padx=6)
        ttk.Button(hdr, text="Apri assistito", command=self._open_open_patient_modal).pack(side=tk.RIGHT, padx=6)

        ttk.Label(self.tab_patient, text=f"Versione: {__version__}  —  Usa 'Nuovo paziente' per crearne uno oppure 'Apri paziente' per selezionare dall'archivio per Nome/Cognome.").pack(pady=10)

        # TAB Cuffie/Dispositivo + Calibrazione (unificati)
        self.tab_device = ttk.Frame(self.nb)
        # Calibrazione disattivata se enable_calibration=False
        try:
            if bool(self.controller.settings.get('enable_calibration', True)):
                self.nb.add(self.tab_device, text="Cuffie/Calibrazione")
        except Exception:
            self.nb.add(self.tab_device, text="Cuffie/Calibrazione")
        ttk.Label(self.tab_device, text="Seleziona output audio (cuffie)").pack(pady=6)
        self.cmb_devices = ttk.Combobox(self.tab_device, state="readonly", width=60, values=self.controller.list_output_devices())
        self.cmb_devices.pack(pady=5)
        btnrow = ttk.Frame(self.tab_device); btnrow.pack(pady=4)
        ttk.Button(btnrow, text="Imposta dispositivo", command=self._set_device).pack(side=tk.LEFT, padx=5)
        self.lbl_active_dev = ttk.Label(self.tab_device, text="Dispositivo attivo: -")
        self.lbl_active_dev.pack(pady=5)
        self.lbl_hp_id = ttk.Label(self.tab_device, text="ID cuffia corrente: -")
        self.lbl_hp_id.pack(pady=2)
        ttk.Label(self.tab_device, text="Nota: OS=Canale Sinistro, OD=Canale Destro").pack(pady=5)

        # Editor offset dispositivo (avanzato) nascosto per semplicitÃ . Lasciamo solo pulsanti utili.
        ctl_frame = ttk.Frame(self.tab_device); ctl_frame.pack(fill=tk.X, padx=10, pady=4)
        ttk.Button(ctl_frame, text="Play 1 kHz a 40 dBHL (OD)", command=lambda:self.controller.play_tone_for_calibration(1000,40,"R")).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl_frame, text="Play 1 kHz a 40 dBHL (OS)", command=lambda:self.controller.play_tone_for_calibration(1000,40,"L")).pack(side=tk.LEFT, padx=4)

        # TAB Audiometria (unificato)
        self.tab_audio = ttk.Frame(self.nb); self.nb.add(self.tab_audio, text="Audiometria")
        topbar = ttk.Frame(self.tab_audio); topbar.pack(fill=tk.X, pady=6)
        ttk.Label(topbar, text="Orecchio:").pack(side=tk.LEFT, padx=10)
        self.var_ear = tk.StringVar(value="R")
        ttk.Combobox(topbar, state="readonly", textvariable=self.var_ear, values=["R","L"], width=4).pack(side=tk.LEFT, padx=4)
        ttk.Button(topbar, text="Avvia", style="Primary.TButton", command=self._start_audiometry).pack(side=tk.LEFT, padx=6)
        ttk.Button(topbar, text="Annulla/Stop", command=self._stop_audiometry).pack(side=tk.LEFT, padx=6)
        self.lbl_status = ttk.Label(self.tab_audio, text="Pronto.", font=("Segoe UI", 11))
        self.lbl_status.pack(pady=4)

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.live_plot = LiveAudiogram(self.controller.settings["frequencies_hz"], title="Audiogramma LIVE")
        self.live_fig, _ = self.live_plot.figure()
        self.plot_canvas = FigureCanvasTkAgg(self.live_fig, master=self.tab_audio)
        self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        # Key bindings for manual mode
        self.root.bind("<Up>", lambda e: (self._log_key(e), self._kbd_move_level(+1)))
        self.root.bind("<Down>", lambda e: (self._log_key(e), self._kbd_move_level(-1)))
        self.root.bind("<Left>", lambda e: (self._log_key(e), self._kbd_move_freq(-1)))
        self.root.bind("<Right>", lambda e: (self._log_key(e), self._kbd_move_freq(+1)))
        self.root.bind("<space>", lambda e: (self._log_key(e), self.controller.manual_space()))
        self.root.bind("<Return>", lambda e: (self._log_key(e), self.controller.manual_enter()))
        self.root.bind("<Tab>", lambda e: (self._log_key(e), self._on_tab(e)))
        ttk.Label(self.tab_audio, text="Tasti: SPAZIO start/stop · INVIO memorizza · Su/Giù = dB (SU=+) · Sinistra/Destra = frequenza · TAB cambia orecchio").pack(pady=4)
        self._live_refresh_from_rows()

        ttk.Label(self.tab_audio, text="Tasti: SPAZIO = conferma/ho sentito · Frecce Sx/Destra = frequenza · Frecce Su/Giù = dB (manuale) · TAB cambia orecchio").pack(pady=4)

        # TAB Archivio
        self.tab_arch = ttk.Frame(self.nb); self.nb.add(self.tab_arch, text="Archivio")
        self.tree_arch = ttk.Treeview(self.tab_arch, columns=("ts","path","img"), show="headings", height=12)
        self.tree_arch.heading("ts", text="Timestamp")
        self.tree_arch.heading("path", text="JSON")
        self.tree_arch.heading("img", text="PNG")
        self.tree_arch.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        btn_arch = ttk.Frame(self.tab_arch); btn_arch.pack(pady=6)
        ttk.Button(btn_arch, text="Apri screening selezionato", command=self._arch_open_selected).pack(side=tk.LEFT, padx=4)
        # NEW: doppio click per aprire
        self.tree_arch.bind("<Double-1>", lambda e: self._arch_open_selected())

        # TAB Risultati
        self.tab_res = ttk.Frame(self.nb); self.nb.add(self.tab_res, text="Risultati")
        self.tree = ttk.Treeview(self.tab_res, columns=("pid","nome","orecchio","freq","dbhl"), show="headings", height=12)
        for c, t in [("pid","ID"),("nome","Assistito"),("orecchio","Orecchio"),("freq","Hz"),("dbhl","dB HL")]:
            self.tree.heading(c, text=t)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        frm_export = ttk.Frame(self.tab_res); frm_export.pack(pady=6)
        ttk.Button(frm_export, text="Aggiorna Tabella", command=self._refresh_results).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_export, text="Salva in locale", command=self._save_local).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_export, text="Esporta PDF", command=self._export_pdf_report).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_export, text="Mostra grafico statico", command=self._show_plot_static).pack(side=tk.LEFT, padx=4)

        # Note esame (modificabili e salvate con l'esame)
        frm_notes = ttk.LabelFrame(self.tab_res, text="Note esame")
        frm_notes.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.txt_notes = tk.Text(frm_notes, height=5, wrap='word')
        self.txt_notes.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        row_btn = ttk.Frame(frm_notes); row_btn.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(row_btn, text="Salva note", command=self._save_notes).pack(side=tk.LEFT, padx=4)
        try:
            self.txt_notes.delete('1.0', tk.END)
            self.txt_notes.insert('1.0', self.controller.get_exam_notes())
        except Exception:
            pass

        # Nessuna tab Impostazioni: parametri principali prelevati da settings.json

        # Global keybindings (manuale): Su/GiÃ¹ = dB (SU=+), Sin/Destra = freq, SPAZIO = start/stop, INVIO = memorizza, TAB = cambia orecchio
        self.root.bind("<Left>", lambda e: (self._log_key(e), self._kbd_move_freq(-1)))
        self.root.bind("<Right>", lambda e: (self._log_key(e), self._kbd_move_freq(+1)))
        # Invertito: UP sposta il cursore in alto (HL diminuisce); DOWN verso il basso (HL aumenta)
        self.root.bind("<Up>", lambda e: (self._log_key(e), self._kbd_move_level(-1)))
        self.root.bind("<Down>", lambda e: (self._log_key(e), self._kbd_move_level(+1)))
        self.root.bind("<Tab>", lambda e: (self._log_key(e), self._on_tab(e)))
        self.root.bind("<space>", lambda e: (self._log_key(e), self._on_space()))
        self.root.bind("<Return>", lambda e: (self._log_key(e), self._on_enter()))
        self.root.bind("<Escape>", lambda e: (self._log_key(e), self._end_ref_entry() if getattr(self, 'ref_mode', False) else None))

        # Global hooks for debug: log any key/button
        try:
            self.root.bind_all("<Key>", self._on_any_key, add=True)
            self.root.bind_all("<Button-1>", self._on_any_button, add=True)
        except Exception:
            pass

    # -------- Logging helpers --------
    def _log_key(self, event):
        if getattr(self, 'debug_ui', False):
            try:
                self._logger.debug(
                    f"Key: keysym={getattr(event,'keysym',None)} keycode={getattr(event,'keycode',None)} char={repr(getattr(event,'char',None))}"
                )
            except Exception:
                pass

    def _on_any_key(self, event):
        self._log_key(event)

    def _on_any_button(self, event):
        if getattr(self, 'debug_ui', False):
            try:
                w = event.widget
                label = ''
                try:
                    if hasattr(w, 'cget'):
                        label = w.cget('text') or ''
                except Exception:
                    label = ''
                self._logger.debug(f"Click: widget={w.__class__.__name__} text={label}")
            except Exception:
                pass

        self._refresh_active_device_label()
        self._refresh_current_hp_label()

        # Sezione Calibrazione integrata nella tab Cuffie/Calibrazione
        try:
            if bool(self.controller.settings.get('enable_calibration', True)):
                self._build_calibration_tab(self.tab_device)
        except Exception:
            pass

    def _select_tab(self, tab):
        try:
            self.nb.select(tab)
        except Exception:
            pass

    def _on_close(self):
        # Ferma qualsiasi riproduzione e thread, annulla timer UI, poi chiude la finestra
        try:
            self.controller.cancel_test()
        except Exception:
            pass
        try:
            self.controller.stop_manual()
        except Exception:
            pass
        try:
            self.controller.stop_calibration()
        except Exception:
            pass
        try:
            if hasattr(self, '_cal_live_after') and self._cal_live_after:
                self.root.after_cancel(self._cal_live_after)
                self._cal_live_after = None
        except Exception:
            pass
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # Unified save: salva soglie + note in un colpo solo
    def _save_local(self):
        try:
            # Persisti note correnti
            try:
                if hasattr(self, 'txt_notes'):
                    text = self.txt_notes.get('1.0', tk.END).strip()
                    self.controller.set_exam_notes(text)
            except Exception:
                pass
            path, img = self.controller.save_results_local()
            messagebox.showinfo("Salvato", f"Esame salvato in:\n{path}")
        except Exception as e:
            messagebox.showerror("Salva", str(e))

    # -------- Settings tab --------
    def _build_settings_tab(self):
        frm_set = ttk.Frame(self.tab_settings); frm_set.pack(pady=10)
        ttk.Label(frm_set, text="Durata tono (s):").grid(row=0, column=0, padx=4, pady=4, sticky="e")
        self.var_dur = tk.DoubleVar(value=self.controller.settings.get("tone_duration_ms",1500)/1000.0)
        ttk.Spinbox(frm_set, from_=1.0, to=3.0, increment=0.1, textvariable=self.var_dur, width=6).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frm_set, text="Intervallo min (s):").grid(row=1, column=0, padx=4, pady=4, sticky="e")
        self.var_isi_min = tk.DoubleVar(value=self.controller.settings.get("isi_ms_min",1200)/1000.0)
        ttk.Spinbox(frm_set, from_=1.0, to=3.0, increment=0.1, textvariable=self.var_isi_min, width=6).grid(row=1, column=1, padx=4, pady=4)
        ttk.Label(frm_set, text="Intervallo max (s):").grid(row=2, column=0, padx=4, pady=4, sticky="e")
        self.var_isi_max = tk.DoubleVar(value=self.controller.settings.get("isi_ms_max",2500)/1000.0)
        ttk.Spinbox(frm_set, from_=1.0, to=3.0, increment=0.1, textvariable=self.var_isi_max, width=6).grid(row=2, column=1, padx=4, pady=4)
        ttk.Button(frm_set, text="Applica", command=self._apply_settings).grid(row=3, column=0, padx=4, pady=8)
        ttk.Button(frm_set, text="Default", command=self._default_settings).grid(row=3, column=1, padx=4, pady=8)

    def _apply_settings(self):
        try:
            dur = max(1.0, min(3.0, float(self.var_dur.get())))
            isi_min = max(1.0, min(3.0, float(self.var_isi_min.get())))
            isi_max = max(1.0, min(3.0, float(self.var_isi_max.get())))
            if isi_min > isi_max:
                raise ValueError("Intervallo minimo maggiore del massimo.")
            self.controller.settings["tone_duration_ms"] = int(dur*1000)
            self.controller.settings["isi_ms_min"] = int(isi_min*1000)
            self.controller.settings["isi_ms_max"] = int(isi_max*1000)
            # Persist immediatamente
            import json
            from ..paths import path_settings
            with open(path_settings(), "w", encoding="utf-8") as f:
                json.dump(self.controller.settings, f, indent=2)
            messagebox.showinfo("OK", "Impostazioni applicate e salvate.")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _default_settings(self):
        self.var_dur.set(1.5)
        self.var_isi_min.set(1.2)
        self.var_isi_max.set(2.5)
        self._apply_settings()

    # -------- Paziente: modali --------
    def _open_new_patient_modal(self):
        win = tk.Toplevel(self.root); win.title("Nuovo assistito")
        ttk.Label(win, text="ID (alfanumerico, 3â€“24):").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        var_id = tk.StringVar(); ttk.Entry(win, textvariable=var_id, width=18).grid(row=0, column=1, padx=8, pady=6)
        ttk.Button(win, text="Suggerisci ID", command=lambda:self._suggest_into(var_id)).grid(row=0, column=2, padx=6, pady=6)
        ttk.Label(win, text="Nome:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        var_nome = tk.StringVar(); ttk.Entry(win, textvariable=var_nome, width=22).grid(row=1, column=1, padx=8, pady=6)
        ttk.Label(win, text="Cognome:").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        var_cognome = tk.StringVar(); ttk.Entry(win, textvariable=var_cognome, width=22).grid(row=2, column=1, padx=8, pady=6)
        def create_and_close():
            pid = var_id.get().strip().upper()
            if not pid or not ALNUM_RE.match(pid) or len(pid)<3 or len(pid)>24:
                messagebox.showwarning("Attenzione", "ID non valido (alfanumerico, 3â€“24)."); return
            try:
                self.controller.create_patient(pid, var_nome.get().strip(), var_cognome.get().strip())
                self.lbl_patient.config(text=self.controller.get_patient_display())
                win.destroy()
            except Exception as e:
                messagebox.showerror("Errore", str(e))
        ttk.Button(win, text="Crea assistito", command=create_and_close).grid(row=3, column=1, padx=8, pady=10)

    def _open_open_patient_modal(self):
        win = tk.Toplevel(self.root); win.title("Apri assistito")
        ttk.Label(win, text="Cerca:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        var_q = tk.StringVar(); ent = ttk.Entry(win, textvariable=var_q, width=28); ent.grid(row=0, column=1, padx=6, pady=6, sticky="w")
        cols = ("name","id","last"); tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for c, t in [("name","Cognome Nome"),("id","ID"),("last","Ultimo esame")]:
            tree.heading(c, text=t)
        tree.grid(row=1, column=0, columnspan=3, padx=6, pady=6)
        data = self.controller.list_saved_patients()
        def refresh():
            q = var_q.get().strip().lower()
            for i in tree.get_children():
                tree.delete(i)
            for p in data:
                label = (p.get("name") or "").lower()
                if q and q not in label and q not in (p.get("id","").lower()):
                    continue
                tree.insert("", tk.END, values=(p.get("name") or "", p.get("id"), p.get("last_ts") or ""))
        refresh()
        def on_sel():
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            pid = item["values"][1]
            idx = self.controller.load_patient_archive(pid)
            self.lbl_patient.config(text=self.controller.get_patient_display())
            for i in self.tree_arch.get_children():
                self.tree_arch.delete(i)
            for ex in idx.get("exams", []):
                self.tree_arch.insert("", tk.END, values=(ex.get("ts"), ex.get("path"), ex.get("image")))
            win.destroy()
        ttk.Button(win, text="Apri selezionato", command=on_sel).grid(row=2, column=1, pady=8)
        ent.bind("<KeyRelease>", lambda e: refresh())

    def _suggest_into(self, var):
        suggestion = self.controller.suggest_patient_id()
        if suggestion:
            var.set(suggestion)

    # -------- Cuffie/calibrazione --------
    def _set_device(self):
        name = self.cmb_devices.get()
        if not name:
            messagebox.showwarning("Attenzione", "Seleziona un dispositivo.")
            return
        try:
            self.controller.set_output_device(name)
            # Auto-assegna ID cuffia dal dispositivo
            uid = None
            try:
                uid = self.controller.assign_hp_from_device()
            except Exception:
                uid = None
            if uid and hasattr(self, 'var_hp2'):
                try:
                    self.var_hp2.set(uid)
                except Exception:
                    pass
            self._refresh_active_device_label()
            self._refresh_current_hp_label()
            self._refresh_calibration_tree()
            messagebox.showinfo("OK", f"Impostato: {name}")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _refresh_active_device_label(self):
        dev = self.controller.get_active_device()
        self.lbl_active_dev.config(text=f"Dispositivo attivo: {dev or '-'}")

    def _refresh_calibration_tree(self):
        if hasattr(self, 'tree_cal'):
            for i in self.tree_cal.get_children():
                self.tree_cal.delete(i)
            for f, off in self.controller.get_calibration_map().items():
                self.tree_cal.insert("", tk.END, values=(f, off))

    def _refresh_current_hp_label(self):
        try:
            hp = self.controller.get_headphone_id()
        except Exception:
            hp = None
        if hasattr(self, 'lbl_hp_id'):
            self.lbl_hp_id.config(text=f"ID cuffia corrente: {hp or '-'}")

    def _edit_offset(self):
        if not hasattr(self, 'tree_cal'):
            messagebox.showinfo("Avanzate", "Editor offset dispositivo non attivo.")
            return
        sel = self.tree_cal.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona una frequenza.")
            return
        item = self.tree_cal.item(sel[0])
        freq = int(item["values"][0])
        off = float(item["values"][1])
        win = tk.Toplevel(self.root); win.title(f"Offset {freq} Hz")
        v = tk.DoubleVar(value=off)
        ttk.Entry(win, textvariable=v).pack(padx=10, pady=10)
        def ok():
            try:
                self.controller.set_calibration_value(freq, float(v.get()))
                self._refresh_calibration_tree()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Errore", str(e))
        ttk.Button(win, text="OK", command=ok).pack(pady=6)

    def _reset_profile(self):
        dev = self.controller.get_active_device()
        if not dev:
            messagebox.showwarning("Attenzione", "Nessun dispositivo attivo.")
            return
        if messagebox.askyesno("Conferma", f"Azzero il profilo per '{dev}'?"):
            self.controller.calibration.reset_profile(dev)
            self._refresh_calibration_tree()
            messagebox.showinfo("OK", f"Profilo '{dev}' azzerato.")

    def _suggest_hp_id(self):
        # Suggerisci un ID cuffia basato sul nome dispositivo attivo
        name = self.controller.get_active_device() or self.cmb_devices.get() or "cuffia"
        import re
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        if not slug:
            slug = "cuffia"
        self.var_hp_id.set(slug[:32])

    def _suggest_hp_into(self, var):
        name = self.controller.get_active_device() or self.cmb_devices.get() or "cuffia"
        import re
        slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        if not slug:
            slug = "cuffia"
        var.set(slug[:32])

    def _start_calibration_norm(self):
        hp_id = (self.var_hp_id.get() or "").strip()
        if not hp_id:
            self._suggest_hp_id()
            hp_id = self.var_hp_id.get()
        try:
            self.controller.start_calibration(hp_id)
            self._select_tab(self.tab_audio)
            messagebox.showinfo("Calibrazione", "ModalitÃ  calibrazione avviata. Esegui l'audiometria manuale su soggetto normoudente, poi premi 'Salva calibrazione da risultati'.")
        except Exception as e:
            messagebox.showerror("Calibrazione", str(e))

    def _finish_calibration_norm(self):
        try:
            bias = self.controller.finish_calibration_save()
            messagebox.showinfo("Calibrazione", f"Calibrazione salvata per cuffia '{self.var_hp_id.get()}'.")
        except Exception as e:
            messagebox.showerror("Calibrazione", str(e))

    # Wizard calibrazione rimosso

    def _open_calibration_panel(self):
        messagebox.showinfo("Info", "Usa la tabella qui sotto per modificare gli offset per frequenza.\nPuoi anche riprodurre 1 kHz a 40 dBHL per OD/OS.")

    # -------- Audiometria --------
    def _start_audiometry(self):
        ear = self.var_ear.get()
        self.controller.manual_set_ear(ear)
        self.controller.start_manual()
        self._select_tab(self.tab_audio)

    def _stop_audiometry(self):
        self.controller.stop_manual()

    def _kbd_move_freq(self, delta):
        self.controller.manual_move_freq(delta)

    def _kbd_move_level(self, delta):
        self.controller.manual_move_level(delta)

    # Gestione SPAZIO/INVIO a seconda della modalitÃ  (normale vs inserimento ref)
    def _on_space(self):
        if getattr(self, 'ref_mode', False):
            return  # in inserimento ref non generiamo audio
        self.controller.manual_space()

    def _on_enter(self):
        if getattr(self, 'ref_mode', False):
            self._ref_commit_point()
        else:
            self.controller.manual_enter()

    def _toggle_ear(self):
        cur = self.var_ear.get()
        self.var_ear.set("L" if cur == "R" else "R")
        self.controller.manual_set_ear(self.var_ear.get())

    def _on_tab(self, event):
        # Cambia orecchio e impedisce cambio focus
        self._toggle_ear()
        return "break"

    # -------- Archivio: apri screening -> Risultati --------
    def _arch_open_selected(self):
        sel = self.tree_arch.selection()
        if not sel:
            messagebox.showwarning("Archivio", "Seleziona una riga (screening).")
            return
        item = self.tree_arch.item(sel[0])
        json_path = item["values"][1]  # path column
        ok, msg = self.controller.preview_rows_from_exam_path(json_path)
        if not ok:
            messagebox.showerror("Archivio", msg)
            return
        self._refresh_results()
        parent = self.tab_res.master  # notebook
        try:
            parent.select(self.tab_res)
        except Exception:
            pass

    # -------- Risultati & grafico --------
    def _refresh_results(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in self.controller.get_results_rows():
            self.tree.insert("", tk.END, values=row)
        self._live_refresh_from_rows()

    def _save_local(self):
        try:
            path, img_path = self.controller.save_results_local()
            messagebox.showinfo("Salvato", f"Esame salvato in:\n{path}\n\nImmagine:\n{img_path}")
        except Exception as e:
            messagebox.showerror("Errore salvataggio", str(e))

    def _show_plot_static(self):
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from ..plotting.audiogram_plot import render_audiogram_image
            rows = self.controller.get_results_rows()
            fig, ax = render_audiogram_image(
                rows,
                {"id": self.controller.patient["id"], "nome": self.controller.patient.get("nome",""), "cognome": self.controller.patient.get("cognome","")},
                self.controller.get_active_device(),
                self.controller.settings["frequencies_hz"],
                out_path=None
            )
            win = tk.Toplevel(self.root); win.title("Grafico statico")
            canvas = FigureCanvasTkAgg(fig, master=win)
            canvas.get_tk_widget().pack(fill="both", expand=True)
            canvas.draw()
        except Exception as e:
            messagebox.showerror("Grafico", str(e))

    def _live_refresh_from_rows(self):
        rows = self.controller.get_results_rows()
        self.live_plot.update_rows(rows)
        self.plot_canvas.draw()

    # -------- Helper --------
    def _calib_help_text(self):
        return (
            "Ogni cuffia ha un profilo di calibrazione dedicato.\n"
            "Quando cambi dispositivo: se esiste un profilo viene proposto il caricamento;\n"
            "altrimenti viene creato un profilo nuovo con offset a 0 dB.\n\n"
            "Per calibrare (senza wizard):\n"
            "1) Imposta l'ID cuffia.\n"
            "2) Avvia l'audiometria di calibrazione (APP) su soggetto normoudente (OD/OS).\n"
            "3) Premi 'Finito (usa questi risultati)' per salvare gli offset.\n\n"
            "Opzionale: puoi caricare un audiogramma di riferimento certificato e allineare."
        )

    # -------- Tab Calibrazione --------
    def _build_calibration_tab(self, parent):
        # Legacy references use self.tab_calib; bind it to parent for backward compatibility
        self.tab_calib = parent
        frm_hp = ttk.LabelFrame(self.tab_calib, text="Cuffia")
        frm_hp.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(frm_hp, text="ID cuffie:").pack(side=tk.LEFT, padx=6)
        self.var_hp2 = tk.StringVar(value="")
        # Back-compat: some methods reference var_hp_id
        self.var_hp_id = self.var_hp2
        ent = ttk.Entry(frm_hp, textvariable=self.var_hp2, width=24); ent.pack(side=tk.LEFT)
        ttk.Button(frm_hp, text="Imposta ID cuffia", command=lambda: (
            self.controller.set_headphone_id(self.var_hp2.get().strip() or "default"),
            self._refresh_current_hp_label()
        )).pack(side=tk.LEFT, padx=6)

        # Esecuzione audiometria di calibrazione (pagina separata rispetto ad Audiometria paziente)
        frm_run = ttk.LabelFrame(self.tab_calib, text="Esecuzione audiometria di calibrazione (APP)")
        frm_run.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(frm_run, text="Orecchio:").pack(side=tk.LEFT, padx=6)
        self.cal_var_ear = tk.StringVar(value="R")
        ttk.Combobox(frm_run, state="readonly", textvariable=self.cal_var_ear, values=["R","L"], width=4).pack(side=tk.LEFT)
        ttk.Button(frm_run, text="Avvia", command=self._cal_run_start).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_run, text="Stop", command=self._cal_run_stop).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_run, text="Finito (usa questi risultati)", command=self._cal_run_finish).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_run, text="Salva calibrazione (normoudente)", command=self._cal_save_norm).pack(side=tk.LEFT, padx=6)
        # Wizard calibrazione rimosso

        # Grafico dedicato alla calibrazione
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.cal_live_plot = LiveAudiogram(self.controller.settings["frequencies_hz"], title="Audiogramma calibrazione")
        self.cal_live_fig, _ = self.cal_live_plot.figure()
        self.cal_plot_canvas = FigureCanvasTkAgg(self.cal_live_fig, master=self.tab_calib)
        self.cal_plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        frm_app = ttk.LabelFrame(self.tab_calib, text="Audiometria di calibrazione (APP)")
        frm_app.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(frm_app, text="Usa risultati correnti", command=self._calib_use_current_results).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_app, text="Carica da archivio...", command=self._calib_load_app_from_archive).pack(side=tk.LEFT, padx=4)
        # L'audiometria di calibrazione si avvia da questa pagina (pulsanti sopra)

        frm_ref = ttk.LabelFrame(self.tab_calib, text="Audiogramma di riferimento (certificato)")
        frm_ref.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(frm_ref, text="Inizia inserimento manuale su grafico", command=self._start_ref_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_ref, text="Termina inserimento", command=self._end_ref_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(frm_ref, text="Importa CSV...", command=self._import_ref_csv).pack(side=tk.LEFT, padx=4)

        # Tabella rapida per inserire il riferimento certificato (OD/OS per frequenza)
        frm_tbl = ttk.LabelFrame(self.tab_calib, text="Inserimento rapido riferimento (tabella)")
        frm_tbl.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(frm_tbl, text=(
            "AVVISO: i valori qui inseriti devono provenire da un'audiometria eseguita con audiometro certificato.\n"
            "Servono per migliorare la calibrazione della cuffia quando il soggetto non è normoudente."
        ), foreground="#884400").grid(row=0, column=0, columnspan=3, sticky='w', padx=4, pady=(2,6))
        freqs = self.controller.settings.get("frequencies_hz", [])
        # Intestazioni
        ttk.Label(frm_tbl, text="Hz").grid(row=1, column=0, padx=4, pady=2)
        ttk.Label(frm_tbl, text="OD (R)").grid(row=1, column=1, padx=4, pady=2)
        ttk.Label(frm_tbl, text="OS (L)").grid(row=1, column=2, padx=4, pady=2)
        self.ref_entries = {'R': {}, 'L': {}}
        for i, f in enumerate(freqs, start=2):
            ttk.Label(frm_tbl, text=str(f)).grid(row=i, column=0, padx=4, pady=2, sticky='e')
            vr = tk.StringVar(value="")
            vl = tk.StringVar(value="")
            self.ref_entries['R'][f] = vr
            self.ref_entries['L'][f] = vl
            ttk.Spinbox(frm_tbl, from_=-10, to=120, textvariable=vr, width=6).grid(row=i, column=1, padx=2, pady=2)
            ttk.Spinbox(frm_tbl, from_=-10, to=120, textvariable=vl, width=6).grid(row=i, column=2, padx=2, pady=2)
        def _apply_ref_table():
            ref = {'R': {}, 'L': {}}
            try:
                for ear in ('R','L'):
                    for f, var in self.ref_entries[ear].items():
                        val = var.get().strip()
                        if val != "":
                            ref[ear][int(f)] = float(val)
                self.calib_ref_map = ref
                self._refresh_calibration_preview()
            except Exception as e:
                messagebox.showerror("Riferimento", str(e))
        ttk.Button(frm_tbl, text="Applica tabella", command=_apply_ref_table).grid(row=len(freqs)+2, column=0, columnspan=3, pady=6)

        # Bias cuffia: vista e correzione manuale per OD/OS
        frm_bias = ttk.LabelFrame(self.tab_calib, text="Bias cuffia (modificabili)" )
        frm_bias.pack(fill=tk.BOTH, padx=8, pady=6)
        cols = ("freq","db")
        sub_left = ttk.Frame(frm_bias); sub_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        sub_right = ttk.Frame(frm_bias); sub_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        ttk.Label(sub_right, text="OD (R)").pack(anchor='w')
        self.tree_bias_R = ttk.Treeview(sub_right, columns=cols, show="headings", height=8)
        self.tree_bias_R.heading("freq", text="Hz"); self.tree_bias_R.heading("db", text="dB")
        self.tree_bias_R.pack(fill=tk.BOTH, expand=True)
        ttk.Label(sub_left, text="OS (L)").pack(anchor='w')
        self.tree_bias_L = ttk.Treeview(sub_left, columns=cols, show="headings", height=8)
        self.tree_bias_L.heading("freq", text="Hz"); self.tree_bias_L.heading("db", text="dB")
        self.tree_bias_L.pack(fill=tk.BOTH, expand=True)
        btns = ttk.Frame(frm_bias); btns.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(btns, text="Modifica OD", command=lambda: self._edit_bias('R')).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Modifica OS", command=lambda: self._edit_bias('L')).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Salva bias cuffia", command=lambda: self.controller.calibration.save_headphone()).pack(side=tk.LEFT, padx=8)
        self._refresh_bias_tables()

        frm_apply = ttk.LabelFrame(self.tab_calib, text="Allineamento e salvataggio")
        frm_apply.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(frm_apply, text="ID soggetto:").pack(side=tk.LEFT, padx=4)
        self.var_subj = tk.StringVar(value="anon")
        ttk.Entry(frm_apply, textvariable=self.var_subj, width=12).pack(side=tk.LEFT)
        self.var_is_normo = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_apply, text="Normoudente", variable=self.var_is_normo).pack(side=tk.LEFT, padx=8)
        self.var_agg = tk.StringVar(value="median")
        self.var_smooth = tk.BooleanVar(value=True)
        self.var_outlier = tk.DoubleVar(value=25.0)
        ttk.Label(frm_apply, text="Aggregatore:").pack(side=tk.LEFT, padx=4)
        ttk.Combobox(frm_apply, state="readonly", textvariable=self.var_agg, values=["median","mean"], width=8).pack(side=tk.LEFT)
        ttk.Checkbutton(frm_apply, text="Smoothing 3-punti", variable=self.var_smooth).pack(side=tk.LEFT, padx=8)
        ttk.Label(frm_apply, text="Outlier Â±dB:").pack(side=tk.LEFT, padx=4)
        ttk.Entry(frm_apply, width=6, textvariable=self.var_outlier).pack(side=tk.LEFT)
        ttk.Button(frm_apply, text="Applica come bias", command=self._apply_bias_now).pack(side=tk.LEFT, padx=8)
        ttk.Button(frm_apply, text="Mostra dati calibrazione", command=self._show_calibration_data).pack(side=tk.LEFT, padx=8)

        frm_hist = ttk.LabelFrame(self.tab_calib, text="Storico sessioni calibrazione")
        frm_hist.pack(fill=tk.BOTH, padx=8, pady=6, expand=True)
        cols = ("name","subject","normo","ref")
        self.tree_sess = ttk.Treeview(frm_hist, columns=cols, show="headings", height=6)
        self.tree_sess.heading("name", text="File")
        self.tree_sess.heading("subject", text="Soggetto")
        self.tree_sess.heading("normo", text="Normo")
        self.tree_sess.heading("ref", text="Ref")
        self.tree_sess.column("name", width=200)
        self.tree_sess.column("subject", width=120)
        self.tree_sess.column("normo", width=60)
        self.tree_sess.column("ref", width=60)
        self.tree_sess.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        btn_hist = ttk.Frame(frm_hist); btn_hist.pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(btn_hist, text="Ricarica elenco", command=self._reload_sessions).pack(fill=tk.X, pady=2)
        ttk.Button(btn_hist, text="Ricalcola bias", command=self._recompute_bias).pack(fill=tk.X, pady=2)

        frm_io = ttk.LabelFrame(self.tab_calib, text="Esporta/Importa calibrazione")
        frm_io.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(frm_io, text="Esporta...", command=self._export_calibration).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_io, text="Importa...", command=self._import_calibration).pack(side=tk.LEFT, padx=6)

        # Stato locale calibrazione
        self.calib_app_map = None  # HL_app
        self.calib_ref_map = {'L': {}, 'R': {}}  # HL_ref
        self.ref_mode = False
        self.plot_context = 'main'  # 'main' | 'cal'

    # ---- Esecuzione audiometria calibrazione (APP) ----
    def _cal_run_start(self):
        ear = self.cal_var_ear.get()
        self.controller.cal_manual_set_ear(ear)
        self.controller.start_calibration(self.var_hp2.get().strip() or 'default')
        # Reindirizza le callback sul grafico di calibrazione
        self._orig_live_plot = getattr(self, 'live_plot', None)
        self._orig_plot_canvas = getattr(self, 'plot_canvas', None)
        self.live_plot = self.cal_live_plot
        self.plot_canvas = self.cal_plot_canvas
        self.plot_context = 'cal'
        self._select_tab(self.tab_device)
        # Avvia refresh live del grafico calibrazione
        try:
            self._cal_live_after = self.root.after(400, self._cal_live_tick)
        except Exception:
            pass

    def _cal_run_stop(self):
        self.controller.stop_calibration()
        # Ripristina plotting predefinito
        if hasattr(self, '_orig_live_plot') and self._orig_live_plot is not None:
            self.live_plot = self._orig_live_plot
        if hasattr(self, '_orig_plot_canvas') and self._orig_plot_canvas is not None:
            self.plot_canvas = self._orig_plot_canvas
        self.plot_context = 'main'
        # Ferma refresh live
        try:
            if hasattr(self, '_cal_live_after') and self._cal_live_after:
                self.root.after_cancel(self._cal_live_after)
                self._cal_live_after = None
        except Exception:
            pass

    def _cal_run_finish(self):
        self.controller.stop_calibration()
        # Sposta risultati correnti dell'audiometria in mappa APP per la calibrazione
        self.calib_app_map = self.controller.results_map_calibration()
        # Aggiorna grafico di calibrazione
        self._refresh_calibration_preview()
        # Ripristina plotting predefinito e lascia i risultati su preview
        if hasattr(self, '_orig_live_plot') and self._orig_live_plot is not None:
            self.live_plot = self._orig_live_plot
        if hasattr(self, '_orig_plot_canvas') and self._orig_plot_canvas is not None:
            self.plot_canvas = self._orig_plot_canvas
        self.plot_context = 'main'
        # Ferma refresh live
        try:
            if hasattr(self, '_cal_live_after') and self._cal_live_after:
                self.root.after_cancel(self._cal_live_after)
                self._cal_live_after = None
        except Exception:
            pass

    def _cal_live_tick(self):
        try:
            if self.plot_context != 'cal' or not self.controller.is_calibration_mode():
                return
            m = self.controller.results_map_calibration() or {}
            rows = []
            for ear in ('R','L'):
                for f, db in (m.get(ear) or {}).items():
                    rows.append([self.controller.patient.get('id',''), '', ear, int(f), float(db)])
            self.cal_live_plot.update_rows(rows)
            self.cal_plot_canvas.draw()
        except Exception:
            pass
        finally:
            try:
                self._cal_live_after = self.root.after(500, self._cal_live_tick)
            except Exception:
                pass

    def _cal_save_norm(self):
        """Salva direttamente la calibrazione della cuffia assumendo soggetto normoudente.
        Converte le soglie APP in bias (= -soglia) e persiste su file cuffia.
        """
        try:
            # Assicura che l'ID cuffia sia impostato
            hp = (self.var_hp2.get() or '').strip() or 'default'
            self.controller.set_headphone_id(hp)
            # Se non abbiamo ancora copiato i risultati APP, prendili ora
            if not self.calib_app_map:
                self.calib_app_map = self.controller.results_map_calibration()
            bias = self.controller.finish_calibration_save()
            # Aggiorna vista bias e storico
            self._refresh_bias_tables()
            try:
                self._reload_sessions()
            except Exception:
                pass
            messagebox.showinfo("Calibrazione", f"Calibrazione (normo) salvata per cuffia '{hp}'.")
        except Exception as e:
            messagebox.showerror("Calibrazione", str(e))

    def _reload_sessions(self):
        hp = (self.var_hp2.get() or '').strip() or 'default'
        for i in (self.tree_sess.get_children() if hasattr(self, 'tree_sess') else []):
            self.tree_sess.delete(i)
        try:
            sessions = self.controller.list_calibration_sessions(hp)
            for s in sessions:
                self.tree_sess.insert("", tk.END, values=(s.get('name'), s.get('subject_id'), 'si' if s.get('is_normoacusic') else 'no', 'si' if s.get('has_ref') else 'no'))
        except Exception as e:
            messagebox.showerror("Sessioni", str(e))

    def _recompute_bias(self):
        hp = (self.var_hp2.get() or '').strip() or 'default'
        try:
            self.controller.recompute_headphone_bias(hp, aggregator=self.var_agg.get(), smoothing=bool(self.var_smooth.get()), outlier_abs=float(self.var_outlier.get()))
            self._refresh_bias_tables()
            messagebox.showinfo("Ricalcolo", f"Bias ricalcolati per '{hp}'.")
        except Exception as e:
            messagebox.showerror("Ricalcolo", str(e))

    def _calib_use_current_results(self):
        self.calib_app_map = self.controller.results_map_calibration()
        self._refresh_calibration_preview()

    def _calib_load_app_from_archive(self):
        path = filedialog.askopenfilename(filetypes=[["JSON","*.json"]], title="Seleziona esame (JSON)")
        if not path:
            return
        try:
            self.calib_app_map = self.controller.load_app_results_from_archive(path)
            self._refresh_calibration_preview()
        except Exception as e:
            messagebox.showerror("Archivio", str(e))

    def _refresh_calibration_preview(self):
        # Disegna ref e (ri)disegna risultati correnti nel grafico di calibrazione
        rows = []
        if self.calib_app_map:
            for ear in ('R','L'):
                for f, db in self.calib_app_map.get(ear, {}).items():
                    rows.append([self.controller.patient.get('id',''), '', ear, int(f), float(db)])
        self.cal_live_plot.update_rows(rows)
        self.cal_live_plot.update_reference_map(self.calib_ref_map)
        self.cal_plot_canvas.draw()
        # Aggiorna tabelle bias
        self._refresh_bias_tables()

    def _start_ref_entry(self):
        self.ref_mode = True
        self.calib_ref_map = self.calib_ref_map or {'L': {}, 'R': {}}
        self.lbl_status.config(text="Inserimento ref: cursori per muovere, INVIO per memorizzare, TAB cambia orecchio, ESC per terminare")
        self._select_tab(self.tab_device)

    def _end_ref_entry(self):
        self.ref_mode = False
        self.lbl_status.config(text="ModalitÃ  ref terminata")

    def _ref_commit_point(self):
        cur = self.controller.get_manual_cursor()
        if not cur:
            return
        freq, level, ear = cur
        ear = 'R' if ear == 'R' else 'L'
        self.calib_ref_map.setdefault(ear, {})[int(freq)] = float(level)
        self._refresh_calibration_preview()

    def _import_ref_csv(self):
        path = filedialog.askopenfilename(filetypes=[["CSV","*.csv"],["All","*.*"]], title="Importa audiogramma certificato (CSV)")
        if not path:
            return
        try:
            import csv
            ref = {'L': {}, 'R': {}}
            with open(path, 'r', encoding='utf-8-sig') as f:
                rd = csv.DictReader(f)
                for r in rd:
                    ear = (r.get('ear') or r.get('orecchio') or '').strip().upper()
                    freq = r.get('freq_hz') or r.get('freq') or r.get('hz')
                    db = r.get('hl_db') or r.get('dbhl') or r.get('db')
                    if ear in ('L','R') and freq and db:
                        ref[ear][int(float(freq))] = float(db)
            self.calib_ref_map = ref
            self._refresh_calibration_preview()
        except Exception as e:
            messagebox.showerror("Import", str(e))

    def _refresh_bias_tables(self):
        try:
            m = self.controller.get_headphone_bias_map()
        except Exception:
            m = {'L': {}, 'R': {}}
        # fill trees
        for t in (getattr(self, 'tree_bias_L', None), getattr(self, 'tree_bias_R', None)):
            if t:
                for i in t.get_children():
                    t.delete(i)
        try:
            for f in sorted((m.get('L') or {}).keys()):
                self.tree_bias_L.insert('', tk.END, values=(int(f), float(m['L'][f])))
        except Exception:
            pass
        try:
            for f in sorted((m.get('R') or {}).keys()):
                self.tree_bias_R.insert('', tk.END, values=(int(f), float(m['R'][f])))
        except Exception:
            pass

    def _edit_bias(self, ear: str):
        ear = 'R' if ear == 'R' else 'L'
        tree = self.tree_bias_R if ear == 'R' else self.tree_bias_L
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Bias', 'Seleziona una riga da modificare.')
            return
        item = tree.item(sel[0])
        freq = int(item['values'][0]); cur = float(item['values'][1])
        win = tk.Toplevel(self.root); win.title(f"Bias {ear} @ {freq} Hz")
        v = tk.DoubleVar(value=cur)
        ttk.Entry(win, textvariable=v, width=8).pack(padx=10, pady=10)
        def ok():
            try:
                self.controller.set_headphone_bias(ear, freq, float(v.get()))
                self._refresh_bias_tables()
                win.destroy()
            except Exception as e:
                messagebox.showerror('Bias', str(e))
        ttk.Button(win, text='OK', command=ok).pack(pady=6)

    def _show_calibration_data(self):
        try:
            app_map = self.calib_app_map or {}
        except Exception:
            app_map = {}
        try:
            ref_map = self.calib_ref_map or {'L':{},'R':{}}
        except Exception:
            ref_map = {'L':{},'R':{}}
        try:
            bias = self.controller.get_headphone_bias_map() or {'L':{},'R':{}}
        except Exception:
            bias = {'L':{},'R':{}}
        def fmt_map(title, mp):
            lines = [title]
            for ear in ('R','L'):
                vals = ", ".join(f"{f}: {mp.get(ear,{}).get(f)}" for f in sorted((mp.get(ear) or {}).keys()))
                lines.append(f"  {ear}: {vals or '-'}")
            return "\n".join(lines)
        text = "\n\n".join([
            fmt_map("[APP] Soglie (dB HL)", app_map),
            fmt_map("[REF] Certificato (dB HL)", ref_map),
            fmt_map("[BIAS] Cuffia (dB)", bias),
        ])
        win = tk.Toplevel(self.root); win.title("Dati calibrazione")
        txt = tk.Text(win, width=80, height=24)
        txt.pack(fill=tk.BOTH, expand=True)
        try:
            txt.insert('1.0', text)
        except Exception:
            pass

    def _apply_bias_now(self):
        hp = (self.var_hp2.get() or '').strip() or 'default'
        if not self.calib_app_map:
            messagebox.showwarning("Calibrazione", "Seleziona o esegui prima l'audiometria APP.")
            return
        # Se presente ref, puÃ² essere ipoacusico; se assente, assumiamo normoudente
        is_normo = bool(self.var_is_normo.get())
        if not is_normo:
            # Per ipoacusici richiediamo ref presente
            has_ref = any((self.calib_ref_map.get('L') or {}).values()) or any((self.calib_ref_map.get('R') or {}).values())
            if not has_ref:
                messagebox.showwarning("Calibrazione", "Per soggetto ipoacusico Ã¨ obbligatorio inserire l'audiogramma di riferimento certificato.")
                return
        try:
            subj = {'id': (self.var_subj.get().strip() or 'anon'), 'is_normoacusic': bool(is_normo)}
            bias = self.controller.apply_calibration_bias(hp, subj, self.calib_app_map, (None if is_normo else self.calib_ref_map), aggregator=self.var_agg.get(), smoothing=bool(self.var_smooth.get()), outlier_abs=float(self.var_outlier.get()))
            # Aggiorna tabelle bias
            self._refresh_bias_tables()
            messagebox.showinfo("Calibrazione", f"Bias aggiornati per '{hp}'.")
        except Exception as e:
            messagebox.showerror("Calibrazione", str(e))

    def _export_calibration(self):
        hp = (self.var_hp2.get() or '').strip() or 'default'
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[["JSON","*.json"]], title="Esporta calibrazione cuffia")
        if not path:
            return
        try:
            self.controller.export_headphone_calibration(hp, path)
            messagebox.showinfo("Export", "Esportazione completata.")
        except Exception as e:
            messagebox.showerror("Export", str(e))

    def _import_calibration(self):
        path = filedialog.askopenfilename(filetypes=[["JSON","*.json"]], title="Importa calibrazione cuffia")
        if not path:
            return
        try:
            hp = self.controller.import_headphone_calibration(path)
            self.var_hp2.set(hp)
            messagebox.showinfo("Import", f"Calibrazione importata per '{hp}'.")
        except Exception as e:
            messagebox.showerror("Import", str(e))

    # --- Note/analisi ---

    def _save_notes(self):
        try:
            text = self.txt_notes.get('1.0', tk.END).strip()
            self.controller.set_exam_notes(text)
            messagebox.showinfo("Note", "Note salvate nell'esame corrente.")
        except Exception as e:
            messagebox.showerror("Note", str(e))

    # Callback dal controller quando si carica un esame dall'archivio
    def on_notes_loaded(self, text):
        try:
            self.txt_notes.delete('1.0', tk.END)
            self.txt_notes.insert('1.0', text or "")
        except Exception:
            pass

    # -------- Export PDF report --------
    def _export_pdf_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[["PDF","*.pdf"]], title="Esporta report PDF")
        if not path:
            return
        try:
            rows = self.controller.get_results_rows()
            logo = get_logo_path()
            hp_id = self.controller.get_headphone_id()
            build_pdf_report(
                patient={
                    'id': self.controller.patient.get('id',''),
                    'nome': self.controller.patient.get('nome',''),
                    'cognome': self.controller.patient.get('cognome','')
                },
                rows=rows,
                device=self.controller.get_active_device(),
                hp_id=hp_id,
                freqs=self.controller.settings.get('frequencies_hz', []),
                logo_path=logo,
                out_pdf_path=path,
                notes=self.controller.get_exam_notes()
            )
            messagebox.showinfo("PDF", "Report PDF esportato con successo.")
        except Exception as e:
            messagebox.showerror("PDF", str(e))

class UICallbacks:
    def __init__(self, win: 'MainWindow'):
        self.win = win
        try:
            self._after = self.win.root.after
        except Exception:
            self._after = None

    def _call(self, fn, *args, **kwargs):
        """Schedule a UI update on Tk main thread (safe from worker threads)."""
        try:
            if self._after:
                if getattr(self.win, 'debug_ui', False):
                    try:
                        name = getattr(fn, '__name__', '<callable>')
                        self.win._logger.debug(f"UI dispatch scheduled: {name} args={args} kwargs={kwargs}")
                    except Exception:
                        pass
                self._after(0, lambda: fn(*args, **kwargs))
                return
        except Exception:
            pass
        try:
            fn(*args, **kwargs)
        except Exception:
            pass

    def ask_yes_no(self, question):
        return messagebox.askyesno("Conferma", question)

    def show_info(self, msg):
        messagebox.showinfo("Info", msg)

    # --- Plot-aware callbacks ---
    def on_test_started(self, ear):
        self.win.lbl_status.config(text=f"Test {ear}: in corso... (UP-only, verifica non consecutiva)")
        self.win.live_plot.clear_probe()
        self.win.plot_canvas.draw()

    def on_frequency_started(self, ear, freq):
        self.win.lbl_status.config(text=f"Test {ear} â€” Frequenza {freq} Hz")
        self.win.live_plot.set_current_freq(freq)
        self.win.live_plot.clear_probe()
        self.win.plot_canvas.draw()

    def on_level_changed(self, ear, freq, level_dbhl):
        self.win.lbl_status.config(text=f"Ascolta: {ear} {freq} Hz â€” {level_dbhl} dB HL (premi SPAZIO se lo SENTE)")
        self.win.live_plot.set_current_freq(freq)
        self.win.live_plot.set_probe(ear, freq, level_dbhl)
        self.win.plot_canvas.draw()

    def on_threshold_captured(self, ear, freq, level_dbhl):
        self.win.lbl_status.config(text=f"Soglia {ear} {freq} Hz: {level_dbhl} dB HL (2 conferme raggiunte)")
        self.win._refresh_results()

    def on_test_finished(self, ear):
        self.win.lbl_status.config(text=f"Test {ear}: completato.")
        self.win.live_plot.clear_probe()
        self.win.plot_canvas.draw()

    # Wizard callbacks rimossi

    # Manual callbacks
    def manual_on_cursor(self, freq, level, ear):
        self.win.lbl_status.config(text=f"Manuale: {ear} {freq} Hz â€” {level} dB HL (loop attivo)")
        self.win.live_plot.set_current_freq(freq)
        self.win.live_plot.set_cursor(ear, freq, level)
        self.win.plot_canvas.draw()

    def manual_on_status(self, freq, level, ear):
        self.win.lbl_status.config(text=f"Manuale loop â€” {ear} {freq} Hz â€” {level} dB HL (SPAZIO: memorizza)")

    def manual_on_mark(self, freq, level, ear):
        self.win.lbl_status.config(text=f"Memorizzato {ear} {freq} Hz = {level} dB HL")
        self.win._refresh_results()

    def on_error(self, msg):
        messagebox.showerror("Errore", msg)

    # Archivio/paziente
    def on_patient_loaded(self, idx):
        for i in self.win.tree_arch.get_children():
            self.win.tree_arch.delete(i)
        for ex in idx.get("exams", []):
            self.win.tree_arch.insert("", tk.END, values=(ex.get("ts"), ex.get("path"), ex.get("image")))

    def on_patient_created(self, patient):
        self.win.lbl_patient.config(text=self.win.controller.get_patient_display())
        messagebox.showinfo("Assistito", f"Creato assistito {patient['id']} - {patient.get('cognome','')} {patient.get('nome','')}")

    def on_preview_loaded(self, rows):
        self.win._refresh_results()











