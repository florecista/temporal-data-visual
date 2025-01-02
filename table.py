import sys
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QToolTip,
    QSpacerItem,
    QSizePolicy,
    QMenuBar,
    QAction,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor
import pyqtgraph as pg


class EventDelegate(QStyledItemDelegate):
    """Custom delegate to render events as dots in table cells and show tooltips."""
    def paint(self, painter, option, index):
        painter.save()
        item_data = index.data(Qt.UserRole)
        if item_data and "dots" in item_data:
            # Extract the dots data
            dots = item_data["dots"]
            dot_color = "#2E8B57"
            painter.setBrush(QColor(dot_color))
            radius = min(option.rect.width(), option.rect.height()) // 6
            cell_width = option.rect.width()

            # Draw each dot
            for dot in dots:
                x_pos = option.rect.left() + dot["time_fraction"] * cell_width
                y_center = option.rect.top() + (option.rect.height() // 2)
                painter.drawEllipse(int(x_pos) - radius, int(y_center) - radius, radius * 2, radius * 2)
        else:
            super().paint(painter, option, index)
        painter.restore()

    def helpEvent(self, event, view, option, index):
        """Handle tooltip display for individual dots."""
        if event.type() == event.ToolTip:
            item_data = index.data(Qt.UserRole)
            if item_data and "dots" in item_data:
                # Extract the dots and cell geometry
                dots = item_data["dots"]
                cell_width = option.rect.width()
                radius = min(option.rect.width(), option.rect.height()) // 6

                # Determine which dot is hovered
                local_x = event.pos().x() - option.rect.left()
                for dot in dots:
                    dot_x_pos = dot["time_fraction"] * cell_width
                    if abs(local_x - dot_x_pos) <= radius:
                        # Show the tooltip for the matched dot
                        tooltip_text = f"<b>{dot['title']}</b><br>{dot['time']}"
                        QToolTip.showText(event.globalPos(), tooltip_text)
                        return True
        return super().helpEvent(event, view, option, index)


class TimelineTable(QTableWidget):
    """Table-based timeline visualization."""
    def __init__(self, events, time_intervals, show_borders=True):
        super().__init__()
        self.events = events
        self.time_intervals = time_intervals

        # Prepare data for two header rows
        self.date_intervals = self.generate_date_intervals(time_intervals)

        # Adjust table dimensions (+1 column for entity names)
        self.setRowCount(len(events) + 2)  # +2 for the two header rows
        self.setColumnCount(len(time_intervals) + 1)  # +1 for entity names

        # Hide default headers
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)

        # Populate table
        self.populate_date_header()
        self.populate_time_header()
        self.populate_table()

        # Apply delegate
        self.setItemDelegate(EventDelegate())

        # Border toggle
        self.toggle_borders(show_borders)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_columns_to_fit()

    def populate_date_header(self):
        """Populate the first header row with dates."""
        for date, start_col, span in self.date_intervals:
            date_item = QTableWidgetItem(date)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(0, start_col + 1, date_item)
            self.setSpan(0, start_col + 1, 1, span)

    def populate_time_header(self):
        """Populate the second header row with times."""
        self.setItem(1, 0, QTableWidgetItem("Entities"))  # Entity column header
        for col, time in enumerate(self.time_intervals):
            time_label = time.strftime("%I:%M %p").lstrip("0")  # Format time
            self.setItem(1, col + 1, QTableWidgetItem(time_label))

    def populate_table(self):
        """Populate the table with entity names and event data."""
        current_row = 2  # Start after the header rows

        for entity, entity_events in self.events.items():
            if entity == "min_datetime":
                continue

            # Add entity name in the first column
            self.setItem(current_row, 0, QTableWidgetItem(entity))

            # Populate events in the remaining columns
            for event_name, details in entity_events.items():
                if "DateTime" not in details:
                    continue  # Skip non-date events

                try:
                    event_time = datetime.fromisoformat(details["DateTime"])
                except ValueError:
                    print(f"Invalid DateTime for event: {event_name} in {entity}. Details: {details}")
                    continue

                # Assign to all matching time intervals
                for col, interval_start in enumerate(self.time_intervals):
                    interval_end = interval_start + timedelta(hours=6)
                    if interval_start <= event_time < interval_end:
                        time_fraction = (event_time - interval_start).total_seconds() / (6 * 3600)

                        # Update or create the cell item
                        existing_item = self.item(current_row, col + 1)
                        if not existing_item:
                            existing_item = QTableWidgetItem()
                            existing_item.setData(Qt.UserRole, {"dots": []})
                            self.setItem(current_row, col + 1, existing_item)

                        # Append the current event
                        cell_data = existing_item.data(Qt.UserRole)
                        cell_data["dots"].append({
                            "title": event_name,
                            "time": event_time.strftime("%d-%b %I:%M %p"),
                            "time_fraction": time_fraction
                        })
                        existing_item.setData(Qt.UserRole, cell_data)

            current_row += 1

    def generate_date_intervals(self, time_intervals):
        """Group columns by date and calculate their spans."""
        date_intervals = []
        current_date = None
        start_col = 0
        span = 0

        for col, time_label in enumerate(self.time_intervals):
            # Extract the date as a string in the desired format (e.g., "01-Jan")
            date_label = time_label.strftime("%d-%b")
            if date_label != current_date:
                # Save the previous date's interval
                if current_date is not None:
                    date_intervals.append((current_date, start_col, span))
                # Start a new date interval
                current_date = date_label
                start_col = col
                span = 0
            span += 1

        # Append the final date interval
        if current_date is not None:
            date_intervals.append((current_date, start_col, span))

        return date_intervals

    def toggle_borders(self, show_borders):
        """Toggle borders."""
        self.setStyleSheet("" if show_borders else "QTableWidget::item { border: none; }")

    def set_visible_columns(self, start_index, end_index):
        """Set which columns are visible based on slider range."""
        for col in range(1, self.columnCount()):  # Skip entity column
            self.setColumnHidden(col, not (start_index <= col - 1 <= end_index))

    def resize_columns_to_fit(self):
        """Resize columns to fit the table width, considering the Entity Name column."""
        print("Resizing columns to fit the table width.")
        total_width = self.viewport().width()
        print(f"Table viewport width: {total_width}")
        entity_column_width = 150  # Fixed width for the Entity Name column
        visible_columns = [col for col in range(1, self.columnCount()) if not self.isColumnHidden(col)]

        if not visible_columns:
            print("No visible columns to resize.")
            return

        data_columns_width = total_width - entity_column_width
        column_width = max(data_columns_width // len(visible_columns), 1)

        print(
            f"Entity column width: {entity_column_width}, Data columns width: {data_columns_width}, Individual column width: {column_width}")

        self.setColumnWidth(0, entity_column_width)
        for col in visible_columns:
            self.setColumnWidth(col, column_width)
        print("Finished resizing columns.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Table with Dual Range Slider")
        self.resize(2048, 1200)  # Adjust size as needed

        # Menu Bar
        self.create_menu()

        # Initialize attributes
        self.slider_widget = None
        self.range_slider = None
        self.timeline_table = None
        self.events = {}
        self.time_intervals = []

        # Main Layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

    def create_menu(self):
        """Create the menu bar with File > Open and Exit options."""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        # Open Action
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        # Exit Action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+X")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_file(self):
        """Open a JSON file and load its data."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Event Data", "", "JSON Files (*.json)")
        if not file_path:
            return  # No file selected

        try:
            self.events = self.load_event_data(file_path)
            self.time_intervals = self.generate_time_intervals(self.events)

            # Clear the current layout and reload the table
            for i in reversed(range(self.main_layout.count())):
                widget = self.main_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()

            # Add timeline table and slider panel
            self.timeline_table = TimelineTable(self.events, self.time_intervals, show_borders=False)
            self.main_layout.addWidget(self.timeline_table)
            self.setup_slider_panel(self.main_layout)

            # Resize columns to fit initially
            self.timeline_table.resize_columns_to_fit()

            # Ensure the main window updates correctly
            self.update()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def setup_slider_panel(self, main_layout):
        """Set up the slider panel with proper spacing and layout."""
        # Create the range slider panel
        self.range_slider_panel = QWidget()
        self.range_slider_panel.setFixedHeight(120)  # Fixed height for the panel containing the slider + labels
        panel_layout = QVBoxLayout(self.range_slider_panel)

        # Add an expanding spacer at the top to push everything down
        panel_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Slider Widget
        self.slider_widget = pg.PlotWidget()
        self.range_slider = pg.LinearRegionItem([0, len(self.time_intervals) - 1])
        self.range_slider.setZValue(10)
        self.range_slider.sigRegionChanged.connect(self.on_range_slider_change)
        self.slider_widget.addItem(self.range_slider)
        self.slider_widget.setFixedHeight(60)  # Fixed height for the slider
        self.slider_widget.getPlotItem().hideAxis("left")
        self.slider_widget.getPlotItem().hideAxis("bottom")
        panel_layout.addWidget(self.slider_widget)

        # Label Layout
        self.label_layout = QHBoxLayout()
        self.add_slider_labels(self.label_layout)
        panel_layout.addLayout(self.label_layout)

        # Add the range slider panel to the main layout, anchoring to the bottom
        main_layout.addWidget(self.range_slider_panel)

    def add_slider_labels(self, layout):
        """Add date labels dynamically with proper vertical spacing."""
        min_time = self.time_intervals[0]
        max_time = self.time_intervals[-1]

        # Clear existing labels
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Add labels for each day in the range
        current_time = min_time
        while current_time <= max_time:
            label = QLabel(current_time.strftime("%d-%b"))
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, alignment=Qt.AlignCenter)
            current_time += timedelta(days=1)

    def load_event_data(self, file_path):
        """Load event data from a JSON file with validation."""
        with open(file_path, "r") as file:
            raw_events = json.load(file)

        events = {}
        all_times = []

        for entity, entity_events in raw_events.items():
            events[entity] = {}
            for event, details in entity_events.items():
                if isinstance(details, dict) and "DateTime" in details:
                    # If details is a dictionary with "DateTime", process normally
                    dt = details.get("DateTime")
                    if isinstance(dt, str):
                        try:
                            parsed_dt = datetime.fromisoformat(dt)
                            all_times.append(parsed_dt)
                            events[entity][event] = details
                        except ValueError:
                            print(f"Invalid DateTime format for event: {event} in {entity}. Details: {dt}")
                elif isinstance(details, str):
                    # If details is a simple ISO 8601 string, treat it as a valid date
                    try:
                        parsed_dt = datetime.fromisoformat(details)
                        all_times.append(parsed_dt)
                        events[entity][event] = {"DateTime": details}  # Wrap it in a dictionary for consistency
                    except ValueError:
                        print(f"Invalid DateTime string for event: {event} in {entity}. Details: {details}")
                else:
                    print(f"Skipping invalid event: {event} for {entity}. Details: {details}")

        if all_times:
            events["min_datetime"] = min(all_times)
        else:
            events["min_datetime"] = datetime.now()  # Fallback if no valid dates

        return events

    def generate_time_intervals(self, events):
        """Generate time intervals dynamically based on the dataset's datetime range."""
        all_times = []

        for entity, entity_events in events.items():
            if entity == "min_datetime":
                continue
            for e in entity_events.values():
                if isinstance(e, dict) and "DateTime" in e:
                    dt = e["DateTime"]
                    if isinstance(dt, str):
                        try:
                            all_times.append(datetime.fromisoformat(dt))
                        except ValueError:
                            print(f"Invalid DateTime: {dt}")

        if not all_times:
            raise ValueError("No valid DateTime values found in the dataset.")

        # Determine the range
        min_time = min(all_times).replace(hour=0, minute=0, second=0, microsecond=0)
        max_time = (max(all_times) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Generate intervals in 6-hour steps
        intervals = []
        current_time = min_time
        while current_time < max_time:
            intervals.append(current_time)
            current_time += timedelta(hours=6)
        return intervals

    def on_range_slider_change(self):
        """Handle changes to the range slider."""
        start_index, end_index = map(int, self.range_slider.getRegion())
        if self.timeline_table:
            self.timeline_table.set_visible_columns(start_index, end_index)
            self.timeline_table.resize_columns_to_fit()

    def showEvent(self, event):
        """Ensure the table resizes to fit the window width after the window is shown."""
        super().showEvent(event)
        if self.timeline_table:
            self.timeline_table.resize_columns_to_fit()

    def update_table_view(self):
        """Resize columns immediately upon application launch."""
        if self.timeline_table:
            self.timeline_table.resize_columns_to_fit()

    def create_timeline_table(self):
        """Create the timeline table and setup the slider panel."""
        # Clear the current layout
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add the timeline table
        self.timeline_table = TimelineTable(self.events, self.time_intervals, show_borders=False)
        self.main_layout.addWidget(self.timeline_table)

        # Resize columns to fit initially
        self.timeline_table.resize_columns_to_fit()

        # Add the slider panel
        self.setup_slider_panel(self.main_layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
