import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt


ROW_HEIGHT = 24
DEFAULT_COL_WIDTH = 80
MINIMUM_COL_WIDTH = 24

BGCOLOR_COLUMN_SUFFIX = '~color'


class Tableau(QtWidgets.QWidget):
    columns_resized = QtCore.Signal()

    def __init__(self, table=None, parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.MinimumExpanding,
            QtWidgets.QSizePolicy.Policy.MinimumExpanding)

        self.setMouseTracking(True)
        self.font_ = self.font()
        self.metrics = QtGui.QFontMetrics(self.font_)

        self.get_colors()

        self._vertical_scroll = 0
        self._horizontal_scroll = 0
        self.row_number_offset = 0

        self.column_sizes: dict = {}

        self.df: pl.DataFrame
        self.set_table(table)

        self.TEXT_COLOR: QtGui.QColor
        self.BACKGROUND_COLOR: QtGui.QColor
        self.GRID_COLOR: QtGui.QColor
        self.HEADER_TEXT: QtGui.QColor
        self.HEADER_COLOR: QtGui.QColor

        self.columns_separators: list[QtCore.QRect] = []
        self.selected_column: int | None = None
        self._column_resized = False

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def compute_headers_sizes(self):
        rect = self.rect()

        # Horizontal header size
        max_height = max([
            self.metrics.boundingRect(rect, Qt.AlignCenter, c).height()
            for c in self.df.columns])
        self.horizontal_header_height = max(24, max_height + 4)

        # vertical header size
        last_label = str(self.row_count + self.row_number_offset - 1)
        text_rect = self.metrics.boundingRect(
            rect, Qt.AlignmentFlag.AlignCenter, last_label)
        self.vertical_header_width = max(24, text_rect.width() + 4)

    def get_table_size(self):
        self.compute_headers_sizes()
        h = self.horizontal_header_height + self.row_count * ROW_HEIGHT
        columns_widths = [
            self.column_sizes.get(c, DEFAULT_COL_WIDTH)
            for c in self.df.columns]
        w = self.vertical_header_width + sum(columns_widths)
        return w, h

    def set_vertical_scroll(self, value):
        self._vertical_scroll = value
        self.update()

    def set_horizontal_scroll(self, value):
        self._horizontal_scroll = value
        self.update()

    def _paint(self, painter: QtGui.QPainter):
        # Collect main sizes
        self.compute_headers_sizes()
        column_sizes = [
            self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            for colname in self.df.columns]

        rect = self.rect()

        # Background
        painter.setBrush(self.BACKGROUND_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        if self.df is None:
            return

        # Paint cells
        painter.setPen(self.TEXT_COLOR)
        columns_widths = []
        rows_y = dict()
        columns_x = dict()
        rows_offset = int(self._vertical_scroll / ROW_HEIGHT)
        pixels_offset = self._vertical_scroll % ROW_HEIGHT
        widget_width = rect.width()
        for col_index, colname in enumerate(self.df.columns):
            col_width = column_sizes[col_index]
            x = (
                self.vertical_header_width
                + sum(columns_widths)
                - self._horizontal_scroll)
            is_column_invisible = x > widget_width and (x + col_width) < 0
            if is_column_invisible:
                continue
            columns_x[col_index] = x
            for row_index in range(self.row_count):
                if row_index < rows_offset:
                    continue  # row not visible
                value = self.df[row_index, col_index]
                visual_row_index = row_index - rows_offset
                y = (
                    self.horizontal_header_height
                    + ROW_HEIGHT * visual_row_index
                    - pixels_offset)
                rows_y[row_index] = y
                # Text
                r = QtCore.QRect(x, y, col_width, ROW_HEIGHT)
                painter.drawText(
                    r.adjusted(1, 1, -1, -1),
                    Qt.AlignmentFlag.AlignCenter,
                    str(value))
            columns_widths.append(col_width)

        # horizontal lines
        painter.setPen(self.GRID_COLOR)
        x2 = sum(columns_widths) + self.vertical_header_width
        for y in rows_y.values():
            y += ROW_HEIGHT
            painter.drawLine(self.vertical_header_width, y, x2, y)

        # horizontal header
        r = QtCore.QRect(rect)
        r.setHeight(self.horizontal_header_height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        columns_widths = []
        self.columns_separators.clear()
        separator_vertical_margin = 4
        separator_selection_margin = 4
        pixels_offset = self._horizontal_scroll % ROW_HEIGHT
        for col_index, colname in enumerate(self.df.columns):
            if col_index not in columns_x:
                continue
            x = columns_x[col_index]
            col_width = self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            r = QtCore.QRect(x, 0, col_width, self.horizontal_header_height)
            painter.setPen(self.HEADER_TEXT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, colname)
            columns_widths.append(col_width)
            painter.setPen(self.BACKGROUND_COLOR)
            painter.drawLine(
                x + col_width,
                separator_vertical_margin,
                x + col_width,
                self.horizontal_header_height - separator_vertical_margin)
            self.columns_separators.append(QtCore.QRectF(
                x + col_width - separator_selection_margin,
                0,
                separator_selection_margin * 2,
                self.horizontal_header_height))

        # vertical header
        r = QtCore.QRect(rect)
        r.setWidth(self.vertical_header_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self.HEADER_TEXT)
        for row_index in range(self.row_count):
            if row_index not in rows_y:
                continue
            value = row_index - self.row_number_offset + 1
            if value < 1:
                continue
            r = QtCore.QRect(
                0,
                rows_y[row_index],
                self.vertical_header_width,
                ROW_HEIGHT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(value))

    def get_separator_column_under_cursor(self, pos) -> str:
        for i, rect in enumerate(self.columns_separators):
            if rect.contains(pos):
                return self.df.columns[i]

    def set_cursor(self, pos):
        if self.get_separator_column_under_cursor(pos):
            QtWidgets.QApplication.setOverrideCursor(
                Qt.CursorShape.SizeHorCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        # Drag:
        if self.selected_column:
            pos = event.position()
            delta = self.drag_start.x() - pos.x()
            current_width = self.column_sizes.get(
                self.selected_column, DEFAULT_COL_WIDTH)
            new_width = max(current_width - delta, MINIMUM_COL_WIDTH)
            self.column_sizes[self.selected_column] = new_width
            if new_width != MINIMUM_COL_WIDTH:
                self.drag_start = pos
            self._column_resized = True
            self.update()
            return
        # Mouse Hover:
        self.set_cursor(event.position())

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        pos = event.position()
        self.selected_column = self.get_separator_column_under_cursor(pos)
        self.drag_start = pos
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.selected_column = None
        if self._column_resized:
            self.columns_resized.emit()
            self._column_resized = False
        return super().mouseReleaseEvent(event)

    def set_table(self, table: pl.DataFrame):
        self.df = table
        if table is None:
            self.column_count = 0
            self.row_count = 0
            return

        self.column_count = len([
            c for c in self.df.columns
            if not c.endswith(BGCOLOR_COLUMN_SUFFIX)])
        self.row_count = self.df.height

    def set_column_sizes(self, column_sizes):
        self.column_sizes = column_sizes
        self.update()

    def get_colors(self):
        table = QtWidgets.QTableView()
        palette = table.palette()
        self.TEXT_COLOR = palette.color(QtGui.QPalette.Text)
        self.BACKGROUND_COLOR = palette.color(QtGui.QPalette.Base)
        self.GRID_COLOR = palette.color(QtGui.QPalette.Mid)

        header_palette = table.horizontalHeader().palette()
        self.HEADER_TEXT = header_palette.color(QtGui.QPalette.ButtonText)
        self.HEADER_COLOR = header_palette.color(QtGui.QPalette.Button)


class TableauWithScroll(QtWidgets.QWidget):
    columns_resized = QtCore.Signal()

    def __init__(self, table=None):
        super().__init__()

        self.tableau = Tableau(parent=self)
        self.tableau.columns_resized.connect(self.adjust_scrollbars)
        self.set_column_sizes = self.tableau.set_column_sizes

        self.vertical_scroll = QtWidgets.QScrollBar(
            Qt.Orientation.Vertical)
        self.vertical_scroll.valueChanged.connect(
            self.tableau.set_vertical_scroll)

        self.horizontal_scroll = QtWidgets.QScrollBar(
            Qt.Orientation.Horizontal)
        self.horizontal_scroll.valueChanged.connect(
            self.tableau.set_horizontal_scroll)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tableau, 0, 0)
        layout.addWidget(self.vertical_scroll, 0, 1)
        layout.addWidget(self.horizontal_scroll, 1, 0)

        self.set_table(table)

    def set_table(self, table):
        self.tableau.set_table(table)
        self.adjust_scrollbars()

    def adjust_scrollbars(self):
        content_width, content_height = self.tableau.get_table_size()
        widget_width, widget_height = self.size().toTuple()

        self.horizontal_scroll.setVisible(content_width > widget_width)
        self.horizontal_scroll.setMaximum(
            content_width - widget_width + self.vertical_scroll.width())
        self.horizontal_scroll.setMinimum(0)

        self.vertical_scroll.setVisible(content_height > widget_height)
        self.vertical_scroll.setMaximum(
            content_height - widget_height + self.horizontal_scroll.height())
        self.vertical_scroll.setMinimum(0)

    def resizeEvent(self, event):
        r = super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)
        return r

    def showEvent(self, event):
        r = super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)
        return r


if __name__ == '__main__':
    import os
    app = QtWidgets.QApplication([])
    df = pl.read_ods(os.path.expandvars('$SAMPLES/sample.ods'))
    tableau = TableauWithScroll(df)
    tableau.set_column_sizes(dict(z=30))
    tableau.show()
    app.exec()
