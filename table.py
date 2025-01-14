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
    QMessageBox, QSplitter, QListWidget, QAbstractItemView, QListWidgetItem, QFormLayout, QDateEdit, QTimeEdit,
    QLineEdit, QDateTimeEdit, QSlider,
)
from PyQt5.QtCore import Qt, QDate, QTime, QDateTime
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
        self.setWindowTitle("Timeline Table with Event Detail Panel")
        self.resize(2048, 1200)

        # Menu Bar
        self.create_menu()

        # Main Layout: Central Splitter
        self.central_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.central_splitter)

        # CENTER: Timeline Table and Slider
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.central_splitter.addWidget(self.main_widget)

        # EAST: Event List and Details
        self.event_splitter = QSplitter(Qt.Vertical)  # Event List (top) and Details Panel (bottom)
        self.central_splitter.addWidget(self.event_splitter)

        # EAST-TOP: Event List
        self.event_list_widget = QListWidget()
        self.event_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.event_list_widget.itemClicked.connect(self.on_event_selected)
        self.event_splitter.addWidget(self.event_list_widget)

        # EAST-BOTTOM: Detail Panel
        self.event_detail_panel = QWidget()
        self.event_detail_layout = QFormLayout(self.event_detail_panel)
        self.event_detail_layout.setLabelAlignment(Qt.AlignLeft)
        self.event_splitter.addWidget(self.event_detail_panel)

        # Set Splitter Sizes
        self.central_splitter.setSizes([1200, 0])  # Hide EAST panel by setting its width to 0
        self.event_splitter.setSizes([400, 200])  # EAST-TOP:EAST-BOTTOM proportions

    def populate_event_list(self):
        """Populate the event list panel with events and select the first event."""
        self.event_list_widget.clear()  # Clear existing items

        first_item = None  # Track the first item for auto-selection

        for row, (entity, entity_events) in enumerate(self.events.items()):
            if entity == "min_datetime":
                continue

            for event_name, details in entity_events.items():
                if "DateTime" not in details:
                    continue  # Skip non-datetime events

                # Format event details
                event_time = datetime.fromisoformat(details["DateTime"])
                display_text = f"{event_time.strftime('%d-%b %I:%M %p')} - {event_name} ({entity})"

                # Add to the event list
                list_item = QListWidgetItem(display_text)
                list_item.setData(Qt.UserRole, {"entity": entity, "row": row, "details": details})
                self.event_list_widget.addItem(list_item)

                # Save the first item for auto-selection
                if first_item is None:
                    first_item = list_item

        # Auto-select the first item and display its details
        if first_item:
            self.event_list_widget.setCurrentItem(first_item)
            self.on_event_selected(first_item)

    def on_event_selected(self, item):
        """Populate the detail panel when an event is selected."""
        event_data = item.data(Qt.UserRole)
        details = event_data["details"]

        # Clear the detail panel
        for i in reversed(range(self.event_detail_layout.count())):
            widget = self.event_detail_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Populate Date and Time fields
        if "DateTime" in details:
            dt = datetime.fromisoformat(details["DateTime"])
            date_edit = QDateEdit(QDate(dt.year, dt.month, dt.day))
            time_edit = QTimeEdit(QTime(dt.hour, dt.minute))
            self.event_detail_layout.addRow("Date:", date_edit)
            self.event_detail_layout.addRow("Time:", time_edit)

        # Populate additional fields
        for key, value in details.items():
            if key == "DateTime":
                continue  # Skip DateTime (already added)
            field = QLineEdit(str(value))
            self.event_detail_layout.addRow(f"{key}:", field)

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

            # Populate event list in the EAST panel
            self.populate_event_list()

            # Resize columns to fit initially
            self.timeline_table.resize_columns_to_fit()

            # Ensure the EAST panel is visible
            self.central_splitter.setSizes([1200, 600])  # Adjust proportions to show EAST panel

            # Ensure the main window updates correctly
            self.update()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def setup_slider_panel(self, main_layout):
        """Set up the dual-carat range slider with DateTime edits."""
        # Create the range slider panel
        self.range_slider_panel = QWidget()
        self.range_slider_panel.setFixedHeight(100)
        panel_layout = QVBoxLayout(self.range_slider_panel)

        # Add an expanding spacer
        panel_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Create DateTime Edit widgets
        self.start_datetime_edit = QDateTimeEdit(QDateTime(self.time_intervals[0]))
        self.start_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_datetime_edit.dateTimeChanged.connect(self.on_start_datetime_changed)

        self.end_datetime_edit = QDateTimeEdit(QDateTime(self.time_intervals[-1]))
        self.end_datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_datetime_edit.dateTimeChanged.connect(self.on_end_datetime_changed)

        # Create dual sliders
        self.start_slider = QSlider(Qt.Horizontal)
        self.start_slider.setMinimum(0)
        self.start_slider.setMaximum(len(self.time_intervals) - 1)
        self.start_slider.setValue(0)
        self.start_slider.valueChanged.connect(self.on_slider_change)

        self.end_slider = QSlider(Qt.Horizontal)
        self.end_slider.setMinimum(0)
        self.end_slider.setMaximum(len(self.time_intervals) - 1)
        self.end_slider.setValue(len(self.time_intervals) - 1)
        self.end_slider.valueChanged.connect(self.on_slider_change)

        # Add sliders and DateTime Edits to the layout
        slider_layout = QVBoxLayout()
        slider_layout.addWidget(self.start_slider)
        slider_layout.addWidget(self.end_slider)

        datetime_layout = QHBoxLayout()
        datetime_layout.addWidget(self.start_datetime_edit)
        datetime_layout.addStretch()
        datetime_layout.addWidget(self.end_datetime_edit)

        # Add layouts to the panel
        panel_layout.addLayout(slider_layout)
        panel_layout.addLayout(datetime_layout)

        # Add the range slider panel to the main layout
        main_layout.addWidget(self.range_slider_panel)

    def on_slider_change(self):
        """Handle slider changes and update DateTime edits."""
        start_index = self.start_slider.value()
        end_index = self.end_slider.value()

        # Ensure sliders don't cross over
        if start_index > end_index:
            self.start_slider.setValue(end_index)
            return
        if end_index < start_index:
            self.end_slider.setValue(start_index)
            return

        # Update DateTime edits
        self.start_datetime_edit.setDateTime(self.time_intervals[start_index])
        self.end_datetime_edit.setDateTime(self.time_intervals[end_index])

        # Update table visibility
        if self.timeline_table:
            self.timeline_table.set_visible_columns(start_index, end_index)
            self.timeline_table.resize_columns_to_fit()

    def on_start_datetime_changed(self):
        """Update the start slider when the DateTime edit changes."""
        start_dt = self.start_datetime_edit.dateTime().toPyDateTime()
        start_index = next((i for i, t in enumerate(self.time_intervals) if t >= start_dt), 0)
        self.start_slider.setValue(start_index)

    def on_end_datetime_changed(self):
        """Update the end slider when the DateTime edit changes."""
        end_dt = self.end_datetime_edit.dateTime().toPyDateTime()
        end_index = next((i for i, t in enumerate(self.time_intervals) if t >= end_dt), len(self.time_intervals) - 1)
        self.end_slider.setValue(end_index)

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


    def create_menu(self):
        """Create the menu bar with File > Open, Exit, and Panel toggle options."""
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

        # View Menu
        view_menu = menubar.addMenu("View")

        # Toggle Event Panel Action
        toggle_panel_action = QAction("Show/Hide Event Panel", self)
        toggle_panel_action.setCheckable(True)
        toggle_panel_action.setChecked(True)
        toggle_panel_action.triggered.connect(self.toggle_event_panel)
        view_menu.addAction(toggle_panel_action)

    def toggle_event_panel(self):
        """Show or hide the event list panel."""
        if self.event_list_widget.isVisible():
            self.event_list_widget.hide()
        else:
            self.event_list_widget.show()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
