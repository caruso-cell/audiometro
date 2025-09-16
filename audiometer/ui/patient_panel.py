from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable
try:
    from ..models.patient import Patient  # type: ignore
except Exception:  # pragma: no cover
    Patient = None  # fallback for environments without models
try:
    # Prefer JSON-based simple store if available in subpackage
    from ..data_store import patients_store as PDB  # type: ignore
except Exception:  # pragma: no cover
    PDB = None  # gracefully degrade when optional store is unavailable

class PatientPanel(ttk.Frame):
    def __init__(self, master, on_select: Callable[[Patient], None]):
        super().__init__(master)
        self.on_select = on_select
        self._build()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill=tk.X, padx=6, pady=4)
        ttk.Label(top, text="Patient ID").pack(side=tk.LEFT)
        self.ent_id = ttk.Entry(top, width=14); self.ent_id.pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Cognome").pack(side=tk.LEFT, padx=(8,0))
        self.ent_ln = ttk.Entry(top, width=10); self.ent_ln.pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Nome").pack(side=tk.LEFT, padx=(8,0))
        self.ent_fn = ttk.Entry(top, width=10); self.ent_fn.pack(side=tk.LEFT, padx=4)
        btn_row = ttk.Frame(self); btn_row.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(btn_row, text="Salva/aggiorna", command=self._add_update).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Ricarica elenco", command=self._reload).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Seleziona", command=self._select_current_row).pack(side=tk.RIGHT)

        self.tree = ttk.Treeview(self, columns=("id","ln","fn"), show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("ln", text="Cognome")
        self.tree.heading("fn", text="Nome")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._reload()

    def _add_update(self):
        if PDB is None or Patient is None:
            messagebox.showerror("Archivio pazienti", "Archivio locale non disponibile in questa build.")
            return
        pid = self.ent_id.get().strip()
        ln = self.ent_ln.get().strip()
        fn = self.ent_fn.get().strip()
        if not pid or not ln or not fn:
            messagebox.showwarning("Campi mancanti", "ID, Cognome, Nome sono obbligatori.")
            return
        PDB.add_or_update_patient(Patient(patient_id=pid, first_name=fn, last_name=ln))
        self._reload()
        messagebox.showinfo("OK", f"Paziente {ln} {fn} ({pid}) salvato.")

    def _reload(self):
        if PDB is None:
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in PDB.list_patients():
            self.tree.insert("", "end", values=(p.patient_id, p.last_name, p.first_name))

    def _select_current_row(self):
        if PDB is None:
            messagebox.showerror("Archivio pazienti", "Archivio locale non disponibile in questa build.")
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Selezione", "Seleziona un paziente dall'elenco.")
            return
        vals = self.tree.item(sel[0], "values")
        p = PDB.get_patient(vals[0])
        if p: self.on_select(p)
