import sys
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGridLayout, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QToolTip, QMenu, QAction
)
from PyQt5.QtCore import Qt

import pyqtgraph as pg
from PyQt5.QtGui import QColor, QBrush, QPainterPath
from PyQt5.QtCore import QRectF



class HoverableScatterPlot(pg.ScatterPlotItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hovered_points = {}

    def set_hover_text(self, point_data):
        """Set hover text for specific points."""
        for point, text in point_data.items():
            self.hovered_points[tuple(point)] = text

    def hoverEvent(self, ev):
        """Handle hover events."""
        if ev.isExit():
            QToolTip.hideText()  # Hide tooltip when not hovering over a point
            return

        hovered_points = self.pointsAt(ev.pos())
        if hovered_points.size > 0:  # Explicitly check if the array is not empty
            point = hovered_points[0].pos()
            tooltip_text = self.hovered_points.get((point.x(), point.y()), "")
            if tooltip_text:
                QToolTip.showText(ev.screenPos().toPoint(), tooltip_text)


class ColumnShading(pg.GraphicsObject):
    def __init__(self, x_start, width, height, color):
        super().__init__()
        self.x_start = x_start
        self.width = width
        self.height = height
        self.color = color
        self.path = QPainterPath()
        self._build_path()

    def _build_path(self):
        """Build the rectangular path for shading."""
        rect = QRectF(self.x_start, 0, self.width, self.height)
        self.path.addRect(rect)

    def paint(self, painter, option, widget):
        """Draw the shaded column."""
        brush = QBrush(QColor(self.color))
        painter.fillPath(self.path, brush)

    def boundingRect(self):
        """Return the bounding rectangle of the shaded column."""
        return QRectF(self.x_start, 0, self.width, self.height)


class HorizontalScrollViewBox(pg.ViewBox):
    def __init__(self, drag_speed=0.2):
        super().__init__()
        self.drag_speed = drag_speed  # Adjust the speed of dragging
        self.scroll_limits = None  # Placeholder for scrolling limits

    def set_scroll_limits(self, x_min, x_max):
        """Set horizontal scrolling limits."""
        self.scroll_limits = (x_min, x_max)
        print(f"Scroll limits set: x_min={x_min}, x_max={x_max}")

    def mouseDragEvent(self, ev):
        """Restrict dragging to the X-axis with controlled speed and limits."""
        if ev.button() == Qt.LeftButton:
            # Calculate horizontal delta with scaling factor
            delta_x = (ev.pos().x() - ev.lastPos().x()) * self.drag_speed
            current_x_min, current_x_max = self.state["viewRange"][0]
            new_x_range = (current_x_min + delta_x, current_x_max + delta_x)

            # Debugging prints to track values
            print(f"Dragging: delta_x={delta_x}, new_x_range={new_x_range}")

            # Check and apply limits
            if self.scroll_limits:
                x_min, x_max = self.scroll_limits
                if new_x_range[0] < x_min:
                    delta_x -= (new_x_range[0] - x_min)
                if new_x_range[1] > x_max:
                    delta_x -= (new_x_range[1] - x_max)

            # Debugging prints after applying limits
            print(f"Adjusted delta_x={delta_x}")

            self.translateBy(x=delta_x, y=0)  # Allow only horizontal movement
            ev.accept()  # Mark the event as handled
        else:
            super().mouseDragEvent(ev)  # Default behavior for other buttons

    def suggestPadding(self, axis):
        """Disable padding by always returning 0."""
        return 0


class CustomChart(pg.PlotWidget):
    def __init__(self, events, y_labels=None, parent=None):
        # Use the custom HorizontalScrollViewBox
        self.view_box = HorizontalScrollViewBox(drag_speed=0.2)
        plot_item = pg.PlotItem(viewBox=self.view_box)
        plot_item.hideAxis("left")  # Hide Y-axis labels
        plot_item.hideAxis("bottom")  # Hide X-axis labels

        super().__init__(parent=parent, plotItem=plot_item)

        self.setBackground("w")  # Default to white background
        self.events = events
        self.y_labels = y_labels or []
        self.row_height = 1  # Placeholder, updated later during rendering
        self.time_step = 6  # 6 hours per column
        self.alternate_colors = ["#FFFFFF", "#DDEEFF"]  # White and light blue

        # Compute and set scrolling limits
        self.set_scrolling_limits()
        self.update_chart()

    def set_scrolling_limits(self):
        """Compute and apply scrolling limits based on event times."""
        all_times = []

        # Collect all event times
        for person_events in self.events.values():
            if isinstance(person_events, dict):  # Ensure person_events is a dictionary
                for details in person_events.values():
                    if isinstance(details, dict) and "DateTime" in details:
                        all_times.append(datetime.fromisoformat(details["DateTime"]))
                    elif isinstance(details, str):  # Handle simple datetime strings
                        all_times.append(datetime.fromisoformat(details))

        if not all_times:
            return  # No data to set limits

        # Calculate the limits (previous midnight to next midnight)
        min_time = min(all_times)
        max_time = max(all_times)

        # Align X-axis range with pyqtgraph's expected range in hours
        x_min_hours = 0  # Start from midnight of the earliest day
        next_midnight = (max_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        x_max_hours = (next_midnight - min_time).total_seconds() / 3600  # Extend to the next midnight

        print(f"Calculated limits: x_min_hours={x_min_hours}, x_max_hours={x_max_hours}")
        self.view_box.set_scroll_limits(x_min_hours, x_max_hours)

    def draw_shaded_columns(self):
        """Draw alternating shaded columns in the background."""
        # Use the full scroll range for shading
        x_min, x_max = self.view_box.scroll_limits if self.view_box.scroll_limits else (0, 24)

        # Adjust to the nearest multiple of the time step
        start_column = int(x_min // self.time_step)  # Start at the nearest 6-hour interval
        end_column = int(x_max // self.time_step) + 1  # End at the next 6-hour interval

        for column in range(start_column, end_column):
            # Calculate column boundaries
            x_start = column * self.time_step
            width = self.time_step

            # Choose alternating color
            color = self.alternate_colors[column % 2]

            # Add shading to the chart
            shading = ColumnShading(x_start, width, len(self.y_labels), color)
            self.getPlotItem().addItem(shading)

    def update_chart(self):
        """Redraw the chart with alternating column shading."""
        self.clear()  # Clear existing plots

        # Draw alternating column shading
        self.draw_shaded_columns()

        # Draw the data points
        self.draw_data_points()

    def draw_data_points(self):
        """Draw data points on the chart."""
        colors = {"truth": "#2E8B57", "match": "#6495ED", "discrepancy": "#FF6347"}

        num_labels = len(self.y_labels)
        self.row_height = self.height() / num_labels if num_labels > 0 else 1

        for i, label in enumerate(self.y_labels):
            person_events = self.events.get(label, {})
            if not isinstance(person_events, dict):  # Validate person_events is a dictionary
                continue

            for event, details in person_events.items():
                if isinstance(details, dict) and "DateTime" in details:
                    event_time = datetime.fromisoformat(details["DateTime"])
                elif isinstance(details, str):  # Handle simple datetime strings
                    event_time = datetime.fromisoformat(details)
                else:
                    continue  # Skip invalid entries

                # Convert datetime to hours since the first event
                hours_since_start = (event_time - self.events["min_datetime"]).total_seconds() / 3600

                # Determine color
                color = colors["truth"] if event == "Flight Departure" else colors["match"]

                # Tooltip for hover
                tooltip = f"{event}\n{event_time.strftime('%b %d, %H:%M')}"
                if isinstance(details, dict):
                    tooltip += f"\nPort: {details.get('Port Origin', details.get('Port Destination', 'N/A'))}"

                # Calculate Y-coordinate to align with the row
                y_pos = i + 0.5  # Centered in row

                # Add hoverable scatter plot point
                scatter = HoverableScatterPlot(
                    [hours_since_start],  # X-coordinate
                    [y_pos],  # Centered Y-coordinate
                    size=10,
                    brush=pg.mkBrush(color),
                    pen=None,
                    symbol="o",
                )
                scatter.set_hover_text({(hours_since_start, y_pos): tooltip})
                self.addItem(scatter)

    def set_x_range(self, x_min, x_max):
        """Adjust the visible X-axis range and redraw shaded columns."""
        self.setXRange(x_min, x_max)
        self.update_chart()

class TimelineWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Load Event Data
        self.events = self.load_event_data("events.json")

        # Compute min and max datetimes
        self.min_datetime, self.max_datetime = self.get_datetime_range()

        # Add min_datetime to events for reference
        self.events["min_datetime"] = self.min_datetime

        # Calculate the total hours range for the slider
        self.total_hours = int((self.max_datetime - self.min_datetime).total_seconds() // 3600)

        # Y-Axis Labels
        self.y_labels = [key for key in self.events.keys() if key != "min_datetime"]

        # Main Layout
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

        # Chart
        self.chart = CustomChart(events=self.events, y_labels=self.y_labels)
        self.layout.addWidget(self.chart, 1, 1)

        # Time Slider (Datetime Range Slider)
        self.slider = pg.PlotWidget(background="w")
        self.slider.setFixedHeight(100)
        self.region = pg.LinearRegionItem([0, 24], movable=True, brush=(50, 50, 200, 50))
        self.slider.addItem(self.region)
        self.slider.setXRange(0, self.total_hours)  # Set slider range based on total hours
        self.slider.getPlotItem().hideAxis("left")  # Hide the left Y-axis
        self.slider.getPlotItem().hideAxis("bottom")  # Hide the slider's numerical bottom axis
        self.layout.addWidget(self.slider, 2, 1)

        # Slider Labels (Below the Slider)
        self.slider_labels_widget = QWidget()
        self.slider_labels_layout = QHBoxLayout(self.slider_labels_widget)
        self.slider_labels_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.slider_labels_widget, 3, 1)

        # Connect slider signal
        self.region.sigRegionChanged.connect(self.on_slider_change)

        # Initial Updates
        self.update_x_axis_labels()
        self.update_slider_labels(0, self.total_hours)
        self.on_slider_change()

    def on_slider_change(self):
        """Update the chart and slider labels based on the slider's region."""
        x_min, x_max = self.region.getRegion()
        self.chart.set_x_range(x_min, x_max)
        self.update_slider_labels(x_min, x_max)

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
            label = QLabel(label_datetime.strftime("%b %d, %I:%M %p"), alignment=Qt.AlignCenter)
            self.slider_labels_layout.addWidget(label)

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
        all_datetimes = []

        for person_events in self.events.values():
            for details in person_events.values():
                if isinstance(details, dict) and "DateTime" in details:
                    all_datetimes.append(datetime.fromisoformat(details["DateTime"]))
                elif isinstance(details, str):  # Handle simple datetime strings
                    all_datetimes.append(datetime.fromisoformat(details))

        if not all_datetimes:
            raise ValueError("No datetime information found in the dataset.")

        return min(all_datetimes), max(all_datetimes)

    def update_x_axis_labels(self, x_range=None):
        """Update the X-axis labels above the chart based on the visible range."""
        # Fetch the X-axis range directly from the ViewBox if no range is provided
        if x_range is None or not isinstance(x_range, (tuple, list)):
            x_range = self.chart.view_box.state["viewRange"][0]

        x_min, x_max = x_range

        # Clear existing labels
        for i in reversed(range(self.x_axis_layout.count())):
            widget = self.x_axis_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Align min_datetime to the nearest midnight
        aligned_min_datetime = self.min_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

        # Convert x_min and x_max to datetime
        start_datetime = aligned_min_datetime + timedelta(hours=int(x_min))
        end_datetime = aligned_min_datetime + timedelta(hours=int(x_max))

        # Align start_datetime to the nearest 6-hour interval
        if start_datetime.hour % 6 != 0:
            start_datetime += timedelta(hours=6 - start_datetime.hour % 6)

        # Generate labels for 6-hour intervals within the visible range
        current_datetime = start_datetime
        while current_datetime <= end_datetime:
            # Only add labels for 12:00 AM and 12:00 PM
            if current_datetime.hour in {0, 12}:
                label_text = current_datetime.strftime("%d-%b %I:%M %p")
                label = QLabel(label_text, alignment=Qt.AlignCenter)
                self.x_axis_layout.addWidget(label)

            # Increment to the next 6-hour interval
            current_datetime += timedelta(hours=6)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Temporal Data Visualisation")
        self.resize(1024, 600)

        # Set up central widget
        self.central_widget = TimelineWidget()
        self.setCentralWidget(self.central_widget)

        # Create the menu
        self.create_menu()

    def create_menu(self):
        """Create the menu with themes."""
        # Main menu bar
        menu_bar = self.menuBar()

        # Options menu
        options_menu = menu_bar.addMenu("Options")

        # Themes submenu
        themes_menu = QMenu("Themes", self)
        options_menu.addMenu(themes_menu)

        # Theme actions
        self.theme_actions = {}
        for theme in ["Classic", "Dark"]:
            action = QAction(theme, self, checkable=True)
            action.triggered.connect(lambda checked, t=theme: self.change_theme(t))
            self.theme_actions[theme] = action
            themes_menu.addAction(action)

        # Set Classic theme as default
        self.theme_actions["Classic"].setChecked(True)

    def change_theme(self, theme):
        """Change the theme based on the selected menu item."""
        # Uncheck all actions
        for action in self.theme_actions.values():
            action.setChecked(False)

        # Check the selected action
        self.theme_actions[theme].setChecked(True)

        # Apply the selected theme
        self.apply_theme(theme)

    def apply_theme(self, theme):
        """Apply the selected theme."""
        if theme == "Classic":
            self.setStyleSheet("")  # Default style
            self.central_widget.chart.setBackground("w")
        elif theme == "Dark":
            self.setStyleSheet("background-color: #121212; color: #FFFFFF;")
            self.central_widget.chart.setBackground("#121212")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
