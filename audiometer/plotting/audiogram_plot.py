import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

DEFAULT_FREQS = [125, 250, 500, 1000, 2000, 3000, 4000, 6000, 8000]

# Bande qualitative (dB HL)
BANDS = [
    (0, 20, "Normale", "#c8e6c9"),
    (20, 30, "Lieve", "#fff59d"),
    (30, 40, "Leggera", "#ffe082"),
    (40, 55, "Moderata", "#ffccbc"),
    (55, 70, "Mod. grave", "#ef9a9a"),
    (70, 90, "Grave", "#e57373"),
    (90, 120, "Profonda", "#ef5350"),
]


def _prep_series(rows, freqs):
    right = {f: None for f in freqs}
    left = {f: None for f in freqs}
    for r in rows:
        if isinstance(r, dict):
            ear, f, db = r["ear"], int(r["freq"]), float(r["dbhl"])
        else:
            ear, f, db = r[2], int(r[3]), float(r[4])
        if f in right:
            if ear == "R":
                right[f] = db
            elif ear == "L":
                left[f] = db
    return right, left


def render_audiogram_image(rows, patient, device_name, freqs=DEFAULT_FREQS, out_path=None, dpi=150):
    right, left = _prep_series(rows, freqs)

    fig, ax = plt.subplots(figsize=(7.5, 7))
    # Clean title with patient info (UTF-8 safe)
    title = (
        f"Audiogramma - {patient.get('cognome','')} {patient.get('nome','')}  "
        f"(ID {patient.get('id','')})"
    )
    if device_name:
        title += f"\nDevice: {device_name}"
    ax.set_title(title, pad=14)

    for (y0, y1, label, color) in BANDS:
        ax.axhspan(y0, y1, facecolor=color, alpha=0.9, edgecolor='none')
        ax.text(freqs[0] * 0.9, (y0 + y1) / 2.0, label, va='center', ha='right', fontsize=10, fontweight='bold')

    ax.set_ylim(120, 0)  # 0 in alto
    ax.set_xlim(min(freqs) * 0.9, max(freqs) * 1.2)
    ax.set_xscale('log', base=10)
    ax.set_xticks(freqs)
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Frequenza (Hz)")
    ax.set_ylabel("Soglia (dB HL)")

    # Griglia: major 10 dB, minor 5 dB
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
    ax.grid(True, which='major', linestyle='--', alpha=0.5)
    ax.grid(True, which='minor', linestyle=':', alpha=0.35)

    def _series_plot(data_map, marker, color, label):
        xs = [f for f in freqs if data_map.get(f) is not None]
        ys = [data_map[f] for f in xs]
        if xs:
            ax.plot(xs, ys, marker=marker, label=label, linewidth=1.5, color=color)

    # Conventions: OD=red circle (o), OS=blue cross (x)
    _series_plot(right, 'o', '#ff0000', 'OD (R)')
    _series_plot(left, 'x', '#0000ff', 'OS (L)')

    ax.legend(loc='lower right')
    fig.tight_layout()

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fig.savefig(out_path, dpi=dpi)
    return fig, ax


# Convenience: plot into an existing Matplotlib Axes from a results map
def plot_audiogram_from_results(ax, results_map, freqs=DEFAULT_FREQS, title=None):
    """
    Plot an audiogram into the given Axes using a results map of the form:
      { 'R': [(hz, dbhl), ...], 'L': [(hz, dbhl), ...] }
    This mirrors the shape produced by the integration screening and UI storage.
    """
    # Build rows compatible with _prep_series
    rows = []
    for ear in ('R', 'L'):
        for item in (results_map.get(ear) or []):
            try:
                hz, db = int(item[0]), float(item[1])
                rows.append({'ear': ear, 'freq': hz, 'dbhl': db})
            except Exception:
                continue

    right, left = _prep_series(rows, freqs)

    # Initialize axes
    if title:
        ax.set_title(title, pad=14)
    ax.set_ylim(120, 0)
    ax.set_xlim(min(freqs) * 0.9, max(freqs) * 1.2)
    ax.set_xscale('log', base=10)
    ax.set_xticks(freqs)
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Frequenza (Hz)")
    ax.set_ylabel("Soglia (dB HL)")

    # Background bands and labels
    for (y0, y1, label, color) in BANDS:
        ax.axhspan(y0, y1, facecolor=color, alpha=0.9, edgecolor='none')
        ax.text(freqs[0] * 0.9, (y0 + y1) / 2.0, label, va='center', ha='right', fontsize=10, fontweight='bold')

    # Grid
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
    ax.grid(True, which='major', linestyle='--', alpha=0.5)
    ax.grid(True, which='minor', linestyle=':', alpha=0.35)

    # Plot series
    def _series_plot(data_map, marker, color, label):
        xs = [f for f in freqs if data_map.get(f) is not None]
        ys = [data_map[f] for f in xs]
        if xs:
            ax.plot(xs, ys, marker=marker, label=label, linewidth=1.5, color=color)

    _series_plot(right, 'o', '#ff0000', 'OD (R)')
    _series_plot(left, 'x', '#0000ff', 'OS (L)')
    ax.legend(loc='lower right')
    return ax

# ------------------ LIVE PLOT FOR UI ------------------
class LiveAudiogram:
    """Matplotlib figure for dynamic audiogram display (embedded in Tk)."""

    def __init__(self, freqs=DEFAULT_FREQS, title="Audiometria live"):
        self.freqs = list(freqs)
        self.fig, self.ax = plt.subplots(figsize=(7.5, 7))
        self._init_axes(title)
        # Stateful artists
        self.right_line, = self.ax.plot([], [], 'o-', color='#ff0000', label='OD (R)', linewidth=1.5)
        self.left_line, = self.ax.plot([], [], 'x-', color='#0000ff', label='OS (L)', linewidth=1.5)
        # Reference (certified audiogram) series
        self.right_ref_line, = self.ax.plot([], [], '^--', color='#cc4444', label='R (ref)', linewidth=1.0)
        self.left_ref_line, = self.ax.plot([], [], 'v--', color='#4444cc', label='L (ref)', linewidth=1.0)
        # Probe marker (current tone)
        self.probe = self.ax.scatter([], [], marker='s', s=70, c='#444444', edgecolors='#111111', linewidths=0.8,
                                     alpha=0.9, label='In riproduzione', zorder=5)
        # Probe label
        self.probe_text = self.ax.text(
            0, 0, "", va='bottom', ha='left', fontsize=10, weight='bold',
            bbox=dict(facecolor='white', alpha=0.75, edgecolor='none'), visible=False, zorder=6
        )
        # Cursor marker for manual mode
        self.cursor = self.ax.scatter([], [], marker='D', s=80, facecolors='none', edgecolors='#333333',
                                      linewidths=1.5, label='Cursore', zorder=4)
        # Current frequency vertical line
        self.vline = self.ax.axvline(x=self.freqs[0], linestyle='--', color='#555555', alpha=0.6, zorder=1)
        self.ax.legend(loc='lower right')
        self.fig.tight_layout()

    def _init_axes(self, title):
        self.ax.set_title(title, pad=14)
        # Background bands
        for (y0, y1, label, color) in BANDS:
            self.ax.axhspan(y0, y1, facecolor=color, alpha=0.9, edgecolor='none')
            self.ax.text(self.freqs[0] * 0.9, (y0 + y1) / 2.0, label, va='center', ha='right', fontsize=10,
                         fontweight='bold')
        self.ax.set_ylim(120, 0)
        self.ax.set_xlim(min(self.freqs) * 0.9, max(self.freqs) * 1.2)
        self.ax.set_xscale('log', base=10)
        self.ax.set_xticks(self.freqs)
        self.ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        self.ax.set_xlabel("Frequenza (Hz)")
        self.ax.set_ylabel("Soglia (dB HL)")
        self.ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
        self.ax.yaxis.set_minor_locator(mticker.MultipleLocator(5))
        self.ax.grid(True, which='major', linestyle='--', alpha=0.5)
        self.ax.grid(True, which='minor', linestyle=':', alpha=0.35)

    def update_rows(self, rows):
        right_map, left_map = _prep_series(rows, self.freqs)
        rx = [f for f in self.freqs if right_map.get(f) is not None]
        ry = [right_map[f] for f in rx]
        lx = [f for f in self.freqs if left_map.get(f) is not None]
        ly = [left_map[f] for f in lx]
        self.right_line.set_data(rx, ry)
        self.left_line.set_data(lx, ly)

    def update_reference_map(self, ref_map):
        ref_r = ref_map.get('R', {}) if ref_map else {}
        ref_l = ref_map.get('L', {}) if ref_map else {}
        rx = [f for f in self.freqs if ref_r.get(f) is not None]
        ry = [ref_r[f] for f in rx]
        lx = [f for f in self.freqs if ref_l.get(f) is not None]
        ly = [ref_l[f] for f in lx]
        self.right_ref_line.set_data(rx, ry)
        self.left_ref_line.set_data(lx, ly)

    def set_probe(self, ear, freq, level):
        self.probe.set_offsets([[freq, level]])
        self.probe.set_sizes([90])
        # Label near the probe: "xx dB"
        self.probe_text.set_text(f"{int(round(level))} dB")
        self.probe_text.set_position((freq, level))
        self.probe_text.set_visible(True)

    def clear_probe(self):
        # Matplotlib expects an Nx2 array for set_offsets; use (0,2) empty
        self.probe.set_offsets(np.empty((0, 2)))
        self.probe_text.set_visible(False)

    def set_cursor(self, ear, freq, level):
        self.cursor.set_offsets([[freq, level]])

    def clear_reference(self):
        self.right_ref_line.set_data([], [])
        self.left_ref_line.set_data([], [])

    def set_current_freq(self, freq):
        self.vline.set_xdata([freq])

    def figure(self):
        return self.fig, self.ax
