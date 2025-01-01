import sys
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QStyledItemDelegate,
)
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import QToolTip


class EventDelegate(QStyledItemDelegate):
    """Custom delegate to render events as dots in table cells and show hover details."""

    def paint(self, painter, option, index):
        painter.save()

        # Retrieve custom data from the item
        item_data = index.data(Qt.UserRole)
        if isinstance(item_data, dict) and "time_fraction" in item_data:
            time_fraction = item_data["time_fraction"]  # Value between 0 and 1
            dot_color = item_data.get("color", "#2E8B57")  # Default green

            # Set brush color
            painter.setBrush(QColor(dot_color))

            # Calculate dot size and position
            radius = min(option.rect.width(), option.rect.height()) // 6  # Adjust size for smaller dot
            x_pos = int(option.rect.left() + time_fraction * option.rect.width())  # Convert to int
            y_center = int(option.rect.center().y())  # Convert to int

            # Draw the dot
            painter.drawEllipse(x_pos - radius, y_center - radius, radius * 2, radius * 2)
        else:
            super().paint(painter, option, index)

        painter.restore()

    def helpEvent(self, event, view, option, index):
        """Show a tooltip with event details."""
        if not event or not index.isValid():
            return False

        # Retrieve custom data from the item
        item_data = index.data(Qt.UserRole)
        if isinstance(item_data, dict) and "title" in item_data and "time" in item_data:
            # Display the title and time in a tooltip
            title = item_data["title"]
            time = item_data["time"]
            QToolTip.showText(event.globalPos(), f"{title}\n{time}", view)
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

        # Hide the default horizontal header to avoid an empty hoverable row
        self.horizontalHeader().setVisible(False)

        # Remove default row numbering (Y-axis numbering)
        self.verticalHeader().setVisible(False)

        # Populate header rows
        self.populate_date_header()  # Row 0
        self.populate_time_header()  # Row 1

        # Populate table rows with data
        self.populate_table()  # Rows 2+

        # Apply custom delegate for event rendering
        self.setItemDelegate(EventDelegate())

        # Configure border visibility
        self.toggle_borders(show_borders)

    def populate_date_header(self):
        """Populate the first header row with dates, spanning their respective columns."""
        for date, start_col, span in self.date_intervals:
            date_item = QTableWidgetItem(date)
            date_item.setTextAlignment(Qt.AlignCenter)  # Center-align the date
            self.setItem(0, start_col + 1, date_item)  # Offset by 1 for the entity column
            self.setSpan(0, start_col + 1, 1, span)  # Span across the date's columns

    def populate_time_header(self):
        """Populate the second header row with times."""
        for col, time_label in enumerate(self.time_intervals):
            self.setItem(1, col + 1, QTableWidgetItem(time_label))  # Offset by 1 to account for the entity column

    def generate_date_intervals(self, time_intervals):
        """Group columns by date, associating intervals with their correct dates."""
        date_intervals = []
        current_date = None
        start_col = 0
        span = 0

        # Base date to calculate dates from
        base_date = self.events["min_datetime"]

        # Keep track of the current date explicitly
        current_full_date = base_date

        for col, time_label in enumerate(time_intervals):
            # Parse the time and align it with the current full date
            interval_start = datetime.strptime(time_label, "%I:%M %p").replace(
                year=current_full_date.year, month=current_full_date.month, day=current_full_date.day
            )

            # Adjust date if time wraps to the next day
            if col > 0 and interval_start <= datetime.strptime(time_intervals[col - 1], "%I:%M %p").replace(
                    year=current_full_date.year, month=current_full_date.month, day=current_full_date.day
            ):
                # Increment current full date to the next day
                current_full_date += timedelta(days=1)
                interval_start = interval_start.replace(
                    year=current_full_date.year, month=current_full_date.month, day=current_full_date.day
                )

            # Extract the date label
            date_label = interval_start.strftime("%d-%b")

            if date_label != current_date:
                # Add the previous date interval
                if current_date is not None:
                    date_intervals.append((current_date, start_col, span))
                # Start a new date interval
                current_date = date_label
                start_col = col
                span = 0
            span += 1

        # Add the final date interval
        if current_date is not None:
            date_intervals.append((current_date, start_col, span))

        return date_intervals

    def populate_table(self):
        """Populate the table with entity names and event data."""
        base_date = self.events["min_datetime"]  # Get the earliest date in the dataset
        current_row = 2  # Start populating after the two header rows

        for entity, entity_events in self.events.items():
            if entity == "min_datetime":  # Skip min_datetime
                continue

            # Populate entity names in the first column
            self.setItem(current_row, 0, QTableWidgetItem(entity))

            # Populate event data in the remaining columns
            for col, time_label in enumerate(self.time_intervals):
                # Calculate the start and end of the interval
                interval_start = datetime.strptime(time_label, "%I:%M %p").replace(
                    year=base_date.year, month=base_date.month, day=base_date.day
                )
                interval_end = interval_start + timedelta(hours=6)

                # Match events to this interval
                for event_name, details in entity_events.items():
                    if isinstance(details, dict) and "DateTime" in details:
                        event_time = datetime.fromisoformat(details["DateTime"])
                    elif isinstance(details, str):
                        event_time = datetime.fromisoformat(details)
                    else:
                        continue

                    if interval_start <= event_time < interval_end:
                        # Calculate time_fraction
                        time_fraction = (event_time - interval_start).total_seconds() / (6 * 3600)
                        # Create a table widget item
                        item = QTableWidgetItem("Dot")
                        # Store custom data in the item's data model
                        item.setData(Qt.UserRole, {
                            "time_fraction": time_fraction,
                            "color": "#2E8B57",
                            "title": event_name,
                            "time": event_time.strftime("%d-%b %I:%M %p"),
                        })
                        self.setItem(current_row, col + 1, item)
                        break

            current_row += 1  # Move to the next row

    def toggle_borders(self, show_borders):
        """Show or hide table borders."""
        if not show_borders:
            self.setStyleSheet(
                "QTableWidget::item { border: none; }"
                "QTableWidget::item:selected { border: 1px solid #2E8B57; }"
            )
        else:
            self.setStyleSheet("")  # Default border


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Timeline Table Example")
        self.resize(1024, 600)

        # Load events from JSON file
        self.events = self.load_event_data("events.json")

        # Generate time intervals
        self.time_intervals = self.generate_time_intervals(self.events)

        # Initialize timeline table
        table = TimelineTable(self.events, self.time_intervals, show_borders=False)
        self.setCentralWidget(table)

    def load_event_data(self, file_path):
        """Load event data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                raw_events = json.load(file)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            sys.exit(1)

        # Extract datetime information
        events = {}
        all_times = []
        for entity, entity_events in raw_events.items():
            events[entity] = {}
            for event, details in entity_events.items():
                if isinstance(details, dict) and "DateTime" in details:
                    dt = datetime.fromisoformat(details["DateTime"])
                elif isinstance(details, str):  # Handle simple datetime strings
                    dt = datetime.fromisoformat(details)
                else:
                    continue
                all_times.append(dt)
                events[entity][event] = details

        # Add min_datetime to events for interval alignment
        if all_times:
            events["min_datetime"] = min(all_times)

        return events

    def generate_time_intervals(self, events):
        """Generate time intervals dynamically based on the dataset's datetime range."""
        all_times = []

        # Collect all event times, skipping "min_datetime"
        for entity, entity_events in events.items():
            if entity == "min_datetime":  # Skip min_datetime
                continue
            for details in entity_events.values():
                if isinstance(details, dict) and "DateTime" in details:
                    all_times.append(datetime.fromisoformat(details["DateTime"]))
                elif isinstance(details, str):
                    all_times.append(datetime.fromisoformat(details))

        # Determine the range
        if not all_times:
            raise ValueError("No datetime information found in the dataset.")

        min_time = min(all_times).replace(hour=0, minute=0, second=0, microsecond=0)
        max_time = (max(all_times) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # Generate intervals in 6-hour steps
        intervals = []
        current_time = min_time
        while current_time < max_time:  # Use '<' to stop before max_time
            intervals.append(current_time.strftime("%I:%M %p").lstrip("0"))
            current_time += timedelta(hours=6)

        return intervals


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
