import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QToolTip
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import pyqtgraph as pg


class HoverableScatterPlot(pg.ScatterPlotItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hovered_points = {}

    def set_hover_text(self, point_data):
        """Set hover text for points."""
        for point, text in point_data.items():
            self.hovered_points[tuple(point)] = text

    def hoverEvent(self, ev):
        """Handle hover events."""
        if ev.isExit():
            QToolTip.hideText()  # Hide tooltip when exiting hover
            return

        hovered_points = self.pointsAt(ev.pos())
        if hovered_points:
            point = hovered_points[0].pos()
            tooltip_text = self.hovered_points.get((point.x(), point.y()), "")
            if tooltip_text:
                QToolTip.showText(ev.screenPos().toPoint(), tooltip_text)


class CustomChart(pg.PlotWidget):
    def __init__(self, events, y_labels=None, parent=None):
        super().__init__(parent)
        self.setBackground("w")
        self.setXRange(0, 24)
        self.setYRange(0, len(y_labels or []))
        self.getPlotItem().hideAxis("bottom")
        self.getPlotItem().hideAxis("left")
        self.y_labels = y_labels or []
        self.events = events
        self.update_chart()

    def update_chart(self):
        """Redraw the chart."""
        self.clear()

        colors = {"truth": QColor("#2E8B57"), "match": QColor("#6495ED"), "discrepancy": QColor("#FF6347")}

        for i, label in enumerate(self.y_labels):
            person_events = self.events.get(label, {})
            for event, time in person_events.items():
                if event == "truth":
                    color = colors["truth"]  # Truth event (Object A)
                elif time == self.events["Object A"]["Event2"]:
                    color = colors["match"]  # Matches truth
                else:
                    color = colors["discrepancy"]  # Discrepancy

                # Add hoverable scatter plot point
                scatter = HoverableScatterPlot(
                    [time],  # X-coordinate
                    [i + 0.5],  # Y-coordinate
                    size=10,
                    brush=color,
                    pen=None,
                    symbol="o",
                )
                scatter.set_hover_text({(time, i + 0.5): f"{event} at {time}:00"})
                self.addItem(scatter)

    def set_x_range(self, x_min, x_max):
        """Adjust the visible X-axis range."""
        self.setXRange(x_min, x_max)


class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Event Data
        self.events = {
            "Person A": {"Event1": 6, "Event2": 12, "Event3": 17},
            "Person B": {"Event2": 12.25, "Event4": 18.25},
            "Person C": {"Event2": 12, "Event5": 6, "Event6": 18},
            "Object A": {"Event2": 12},
        }

        # Y-Axis Labels
        self.y_labels = list(self.events.keys())

        # Grid Layout
        self.layout = QGridLayout(self)
        self.layout.setSpacing(5)

        # X-Axis Labels (Above the Chart)
        self.x_axis_widget = QWidget()
        self.x_axis_layout = QHBoxLayout(self.x_axis_widget)
        self.x_axis_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.x_axis_widget, 0, 1)

        # Y-Axis Labels
        self.y_axis_widget = QWidget()
        self.y_axis_layout = QVBoxLayout(self.y_axis_widget)
        self.y_axis_layout.setContentsMargins(0, 0, 0, 0)
        for label in self.y_labels:
            self.y_axis_layout.addWidget(QLabel(label, alignment=Qt.AlignCenter))
        self.layout.addWidget(self.y_axis_widget, 1, 0)

        # Chart Area
        self.chart = CustomChart(events=self.events, y_labels=self.y_labels)
        self.layout.addWidget(self.chart, 1, 1)

        # Time Slider (Dual Carat using LinearRegionItem)
        self.slider = pg.PlotWidget(background="w")
        self.slider.setFixedHeight(100)
        self.region = pg.LinearRegionItem([6, 18], movable=True, brush=(50, 50, 200, 50))
        self.slider.addItem(self.region)
        self.slider.setXRange(0, 24)
        self.slider.getPlotItem().hideAxis("left")
        self.slider.getPlotItem().getAxis("bottom").setLabel("Time (Hours)")
        self.layout.addWidget(self.slider, 2, 1)

        # Connect Signal
        self.region.sigRegionChanged.connect(self.on_slider_change)

        # Initial X-Axis Labels Update
        self.update_x_axis_labels(6, 18)

    def update_x_axis_labels(self, x_min, x_max):
        """Update the X-axis labels based on the slider range."""
        # Clear existing labels
        for i in reversed(range(self.x_axis_layout.count())):
            widget = self.x_axis_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add new labels based on the visible range
        step = 2  # Label interval (hours)
        for hour in range(int(x_min), int(x_max) + 1, step):
            self.x_axis_layout.addWidget(QLabel(f"{hour}:00", alignment=Qt.AlignCenter))

    def on_slider_change(self):
        """Adjust the chart and X-axis labels based on the slider's region."""
        x_min, x_max = self.region.getRegion()
        self.chart.set_x_range(x_min, x_max)
        self.update_x_axis_labels(x_min, x_max)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom Timeline with Hover Tooltips")
        self.setCentralWidget(TimelineWidget())
        self.resize(1024, 600)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
