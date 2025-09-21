from __future__ import annotations
from typing import Optional, Dict, Sequence, Any, List
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QBrush
from PySide6 import QtWidgets
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
import tempfile
import os

FREQS = [125, 250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000]
FREQ_POS = {freq: idx for idx, freq in enumerate(FREQS)}
LOSS_REGIONS = [
    (-10, 20, QColor('#e8f5e9'), 'Normale'),
    (20, 40, QColor('#fffde7'), 'Lieve'),
    (40, 70, QColor('#ffe0b2'), 'Moderata'),
    (70, 90, QColor('#ffcdd2'), 'Grave'),
    (90, 120, QColor('#ef9a9a'), 'Profonda'),
]

CROSSHAIR_COLOR = '#009688'
AXIS_TEXT_COLOR = '#333333'
AXIS_LINE_COLOR = '#b0bec5'
BACKGROUND_COLOR = QColor('#ffffff')
LEGEND_BRUSH_COLOR = QColor(255, 255, 255, 235)
LOSS_REGION_OPACITY = 0.45
GRID_ALPHA = 0.3


class AudiogramView(QWidget):
    """Widget che visualizza l'audiogramma."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plot = pg.PlotWidget()
        self.plot.setBackground(BACKGROUND_COLOR)
        layout.addWidget(self.plot)
        self._data: Dict[str, Dict[int, float]] = {"OD": {}, "OS": {}}
        self._series: Dict[str, Dict[str, pg.GraphicsObject]] = {}
        self._overlay_items: List[pg.GraphicsObject] = []
        self.legend: Optional[pg.LegendItem] = None
        self.hline: Optional[pg.InfiniteLine] = None
        self.vline: Optional[pg.InfiniteLine] = None
        self._setup_plot()

    def _setup_plot(self) -> None:
        axis_bottom = pg.AxisItem(orientation='bottom')
        axis_bottom.setTicks([[(idx, str(freq)) for idx, freq in enumerate(FREQS)]])
        axis_bottom.setPen(pg.mkPen(AXIS_LINE_COLOR))
        axis_bottom.setTextPen(pg.mkPen(AXIS_TEXT_COLOR))
        axis_left = pg.AxisItem(orientation='left')
        axis_left.setTicks([
            [(val, str(val)) for val in range(-10, 130, 10)],
            [(val, '') for val in range(-5, 125, 5) if val % 10]
        ])
        axis_left.setPen(pg.mkPen(AXIS_LINE_COLOR))
        axis_left.setTextPen(pg.mkPen(AXIS_TEXT_COLOR))
        self.plot.setAxisItems({'bottom': axis_bottom, 'left': axis_left})
        self.plot.showGrid(x=True, y=True, alpha=GRID_ALPHA)
        self.plot.setLabel('bottom', 'Frequenza (Hz)', color=AXIS_TEXT_COLOR)
        self.plot.setLabel('left', 'Soglia (dB HL)', color=AXIS_TEXT_COLOR)
        self.plot.invertY(True)
        self.plot.setLimits(xMin=-0.5, xMax=len(FREQS) - 0.5, yMin=-10, yMax=120)
        self.plot.setRange(xRange=(-0.5, len(FREQS) - 0.5), yRange=(-10, 120), padding=0.02)

        self._add_background_regions()

        self.legend = self.plot.addLegend(offset=(10, 10))
        if self.legend:
            self.legend.setBrush(QBrush(LEGEND_BRUSH_COLOR))
            self.legend.setPen(pg.mkPen(AXIS_LINE_COLOR))
        for ear, color in {'OD': '#d43f3a', 'OS': '#1f77b4'}.items():
            pen = pg.mkPen(color, width=2)
            marker_brush = pg.mkColor(color).lighter(160)
            symbol = 'o' if ear == 'OD' else 'x'
            line = pg.PlotDataItem([], [], pen=pen)
            scatter = pg.ScatterPlotItem(
                pen=pen,
                brush=pg.mkBrush(marker_brush),
                size=12,
                symbol=symbol,
            )
            label = 'OD (O)' if ear == 'OD' else 'OS (X)'
            if self.legend:
                self.legend.addItem(line, label)
            self.plot.addItem(line)
            self.plot.addItem(scatter)
            self._series[ear] = {
                'line': line,
                'scatter': scatter,
                'symbol': symbol,
                'brush': marker_brush,
            }

        crosshair_pen = pg.mkPen(color=CROSSHAIR_COLOR, width=2, style=Qt.DashLine)
        self.hline = pg.InfiniteLine(angle=0, pen=crosshair_pen)
        self.vline = pg.InfiniteLine(angle=90, pen=crosshair_pen)
        self.hline.setZValue(10)
        self.vline.setZValue(10)
        self.plot.addItem(self.hline, ignoreBounds=True)
        self.plot.addItem(self.vline, ignoreBounds=True)

    def _add_background_regions(self) -> None:
        width = len(FREQS)
        for low, high, color, _label in LOSS_REGIONS:
            rect = QtWidgets.QGraphicsRectItem(-0.5, low, width, high - low)
            rect.setBrush(QBrush(color, Qt.SolidPattern))
            rect.setPen(pg.mkPen(None))
            rect.setOpacity(LOSS_REGION_OPACITY)
            rect.setZValue(-20)
            self.plot.addItem(rect)

    def update_points(self, ear: str, data: Dict[int, float]) -> None:
        if ear not in self._series:
            raise ValueError("ear deve essere 'OD' o 'OS'.")
        clean_data = {int(freq): float(level) for freq, level in data.items() if int(freq) in FREQS}
        self._data[ear] = clean_data
        ordered_freqs = [freq for freq in FREQS if freq in clean_data]
        positions = [FREQ_POS[freq] for freq in ordered_freqs]
        levels = [clean_data[freq] for freq in ordered_freqs]
        series = self._series[ear]
        series['line'].setData(positions, levels)
        pen = series['line'].opts['pen']
        marker_brush = series.get('brush')
        spots = []
        for pos, level, freq in zip(positions, levels, ordered_freqs):
            spots.append({
                'pos': (pos, level),
                'brush': pg.mkBrush(marker_brush) if marker_brush is not None else pg.mkBrush(0, 0, 0, 0),
                'pen': pen,
                'symbol': series['symbol'],
                'size': 12,
                'data': {'tooltip': f"{ear} {freq} Hz\n{level:.1f} dB HL"},
            })
        series['scatter'].setData(spots)

    def update_crosshair(self, freq: int, level: float) -> None:
        pos = FREQ_POS.get(freq)
        if pos is None:
            return
        if self.hline is not None:
            self.hline.setPos(level)
        if self.vline is not None:
            self.vline.setPos(pos)

    def clear_overlays(self) -> None:
        for item in self._overlay_items:
            try:
                self.plot.removeItem(item)
                if self.legend:
                    self.legend.removeItem(item)
            except Exception:
                pass
        self._overlay_items.clear()

    def set_overlays(self, exams: Sequence[Dict[str, Any]]) -> None:
        self.clear_overlays()
        if not exams:
            return
        colors = ['#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#17becf', '#7f7f7f']
        for idx, exam in enumerate(exams):
            color = colors[idx % len(colors)]
            label = exam.get('label', f"Esame {idx + 1}")
            for ear in ('OD', 'OS'):
                ear_data = exam.get(ear, {}) or {}
                pos_list: List[int] = []
                level_list: List[float] = []
                for freq in FREQS:
                    value = ear_data.get(freq)
                    if value is None:
                        value = ear_data.get(str(freq))
                    if value is None:
                        continue
                    pos_list.append(FREQ_POS[freq])
                    level_list.append(float(value))
                if not pos_list:
                    continue
                pen_style = Qt.SolidLine if ear == 'OD' else Qt.DashLine
                pen = pg.mkPen(color=color, width=1.5, style=pen_style)
                line = pg.PlotDataItem(pos_list, level_list, pen=pen)
                self.plot.addItem(line)
                legend_label = f"{label} - {ear}"
                if self.legend:
                    self.legend.addItem(line, legend_label)
                self._overlay_items.append(line)

    def save_png(self, out_path: str, hide_crosshair: bool = False, width: int | None = None) -> None:
        to_restore = []
        if hide_crosshair:
            for line in (self.hline, self.vline):
                if line is not None:
                    to_restore.append((line, line.isVisible()))
                    line.setVisible(False)
        try:
            QApplication.processEvents()
            exporter = ImageExporter(self.plot.plotItem)
            if width is None:
                width = int(max(1, self.plot.width()))
            exporter.parameters()['width'] = width
            exporter.export(out_path)
        finally:
            for line, visible in to_restore:
                line.setVisible(visible)

    def export_png_bytes(self, hide_crosshair: bool = False) -> bytes:
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_path = tmp.name
            tmp.close()
            self.save_png(tmp_path, hide_crosshair=hide_crosshair)
            with open(tmp_path, 'rb') as handle:
                return handle.read()
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
