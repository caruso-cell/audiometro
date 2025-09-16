from __future__ import annotations
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class FigureCanvas(FigureCanvasTkAgg):
    def __init__(self, master, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(fig, master)
    def get_tk_widget(self):
        return super().get_tk_widget()
    def clear(self):
        self.figure.clf()
        self.draw()
    def draw(self):
        return super().draw()
