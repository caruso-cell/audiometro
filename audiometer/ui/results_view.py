from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any
from .utils_mpl import FigureCanvas  # thin wrapper we add below
from ..plotting.audiogram_plot import plot_audiogram_from_results

class ResultsView(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self._build()

    def _build(self):
        top = ttk.Frame(self); top.pack(fill=tk.X, pady=4)
        ttk.Label(top, text="Sessioni salvate").pack(side=tk.LEFT, padx=6)

        self.tree = ttk.Treeview(self, columns=("ts","notes"), show="headings", height=6)
        self.tree.heading("ts", text="Timestamp")
        self.tree.heading("notes", text="Note")
        self.tree.pack(fill=tk.X, padx=6, pady=(0,6))

        self.fig = FigureCanvas(self, width=5, height=4, dpi=100)
        self.fig.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def load_sessions(self, sessions: List[Dict[str, Any]]):
        # fill the tree
        for i in self.tree.get_children():
            self.tree.delete(i)
        for s in sessions:
            ts = s.get("ts")
            notes = s.get("meta",{}).get("notes","")
            self.tree.insert("", "end", values=(ts, notes))
        # plot last session if present
        if sessions:
            self.plot_session(sessions[-1])
        else:
            self.fig.clear()

    def plot_session(self, session: Dict[str, Any]):
        ax = self.fig.figure.add_subplot(111)
        ax.clear()
        plot_audiogram_from_results(ax, session.get("results", {}))
        self.fig.draw()
