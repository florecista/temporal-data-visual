import sys
import json
from datetime import datetime, timedelta
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
        self.getPlotItem().hideAxis("bottom")  # Hides X-axis numbers
        self.getPlotItem().hideAxis("left")    # Hides Y-axis numbers
        self.y_labels = y_labels or []
        self.events = events
        self.update_chart()


    def update_chart(self):
        """Redraw the chart."""
        self.clear()

        colors = {"truth": QColor("#2E8B57"), "match": QColor("#6495ED"), "discrepancy": QColor("#FF6347")}

        # Compute the minimum datetime for X-axis alignment
        min_datetime = min(
            datetime.fromisoformat(event["DateTime"])
            for person_events in self.events.values()
            for event in person_events.values()
            if isinstance(event, dict) and "DateTime" in event
        )

        for i, label in enumerate(self.y_labels):
            person_events = self.events.get(label, {})
            for event, details in person_events.items():
                if isinstance(details, str):  # Simple datetime events like 'Left Home'
                    event_time = datetime.fromisoformat(details)
                elif isinstance(details, dict):  # Events with details like Flight Departure
                    event_time = datetime.fromisoformat(details["DateTime"])
                else:
                    continue

                # Convert datetime to hours since min_datetime
                hours_since_start = (event_time - min_datetime).total_seconds() / 3600

                # Determine color
                color = colors["truth"] if event == "Flight Departure" else colors["match"]

                # Tooltip text
                tooltip = f"{event}\n{event_time}\n"
                if isinstance(details, dict):
                    tooltip += f"Port: {details.get('Port Origin', details.get('Port Destination', 'N/A'))}"

                # Add hoverable scatter plot point
                scatter = HoverableScatterPlot(
                    [hours_since_start],  # X-coordinate
                    [i + 0.5],  # Y-coordinate
                    size=10,
                    brush=color,
                    pen=None,
                    symbol="o",
                )
                scatter.set_hover_text({(hours_since_start, i + 0.5): tooltip})
                self.addItem(scatter)

    def set_x_range(self, x_min, x_max):
        """Adjust the visible X-axis range."""
        self.setXRange(x_min, x_max)


class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Load Event Data from JSON File
        self.events = self.load_event_data("events.json")

        # Compute the minimum and maximum datetimes in the dataset
        self.min_datetime, self.max_datetime = self.get_datetime_range()

        # Calculate the total hours range for the slider
        self.total_hours = int((self.max_datetime - self.min_datetime).total_seconds() // 3600)

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
        self.chart.getPlotItem().hideAxis("bottom")  # Hide the bottom X-axis labels
        self.layout.addWidget(self.chart, 1, 1)

        # Time Slider (Dual Carat using LinearRegionItem)
        self.slider = pg.PlotWidget(background="w")
        self.slider.setFixedHeight(100)
        self.region = pg.LinearRegionItem([0, 24], movable=True, brush=(50, 50, 200, 50))
        self.slider.addItem(self.region)
        self.slider.setXRange(0, self.total_hours)  # Set slider range based on total hours
        self.slider.getPlotItem().hideAxis("left")  # Hide the left Y-axis
        self.slider.getPlotItem().hideAxis("bottom")  # Hide the slider's numerical bottom axis
        self.layout.addWidget(self.slider, 2, 1)

        # Slider Labels (Under the Slider)
        self.slider_labels_widget = QWidget()
        self.slider_labels_layout = QHBoxLayout(self.slider_labels_widget)
        self.slider_labels_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.slider_labels_widget, 3, 1)

        # Connect Signal
        self.region.sigRegionChanged.connect(self.on_slider_change)

        # Initial X-Axis Labels Update
        self.update_x_axis_labels(0, 24)
        self.update_slider_labels(0, 24)

        # Trigger Initial Alignment
        self.on_slider_change()

    def load_event_data(self, file_path):
        """Load event data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            raise

    def get_datetime_range(self):
        """Calculate the minimum and maximum datetimes in the dataset."""
        all_datetimes = [
            datetime.fromisoformat(event["DateTime"])
            for person_events in self.events.values()
            for event in person_events.values()
            if isinstance(event, dict) and "DateTime" in event
        ]
        return min(all_datetimes), max(all_datetimes)

    def update_x_axis_labels(self, x_min, x_max):
        """Update the X-axis labels based on the slider range."""
        # Clear existing labels
        for i in reversed(range(self.x_axis_layout.count())):
            widget = self.x_axis_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add new labels based on the visible range
        step = 6  # Label interval (6 hours)
        for hour in range(int(x_min), int(x_max) + 1, step):
            label_datetime = self.min_datetime + timedelta(hours=hour)
            label = label_datetime.strftime("%b %d, %H:%M")
            self.x_axis_layout.addWidget(QLabel(label, alignment=Qt.AlignCenter))

    def update_slider_labels(self, x_min, x_max):
        """Update the slider labels based on the slider range."""
        # Clear existing labels
        for i in reversed(range(self.slider_labels_layout.count())):
            widget = self.slider_labels_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add new labels based on the visible range
        step = 6  # Label interval (6 hours)
        for hour in range(int(x_min), int(x_max) + 1, step):
            label_datetime = self.min_datetime + timedelta(hours=hour)
            label = label_datetime.strftime("%b %d, %H:%M")
            self.slider_labels_layout.addWidget(QLabel(label, alignment=Qt.AlignCenter))

    def on_slider_change(self):
        """Adjust the chart and X-axis labels based on the slider's region."""
        x_min, x_max = self.region.getRegion()

        # Update chart range
        self.chart.set_x_range(x_min, x_max)

        # Update X-axis labels
        self.update_x_axis_labels(x_min, x_max)

        # Update slider labels
        self.update_slider_labels(x_min, x_max)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Temporal Data Visualisation")
        try:
            self.setCentralWidget(TimelineWidget())
        except Exception as e:
            print(f"Error during initialization: {e}")
        self.resize(1024, 600)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
