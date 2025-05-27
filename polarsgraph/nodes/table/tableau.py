import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt


LINE_HEIGHT = 24
DEFAULT_COL_WIDTH = 80
MINIMUM_COL_WIDTH = 24

BGCOLOR_COLUMN_SUFFIX = '~color'


class Tableau(QtWidgets.QWidget):
    columns_resized = QtCore.Signal()

    def __init__(self, table=None):
        super().__init__()

        self.setMouseTracking(True)
        self.font_ = self.font()
        self.metrics = QtGui.QFontMetrics(self.font_)

        self.get_colors()

        self.setMinimumHeight(120)
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

    def _paint(self, painter: QtGui.QPainter):
        self.compute_headers_sizes()
        rect = self.rect()

        # Background
        painter.setBrush(self.BACKGROUND_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        if self.df is None:
            return

        # horizontal header
        r = QtCore.QRect(rect)
        r.setHeight(self.horizontal_header_height)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        columns_widths = []
        self.columns_separators.clear()
        separator_vertical_margin = 4
        separator_selection_margin = 4
        for colname in self.df.columns:
            x = self.vertical_header_width + sum(columns_widths)
            width = self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            r = QtCore.QRect(x, 0, width, self.horizontal_header_height)
            painter.setPen(self.HEADER_TEXT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, colname)
            columns_widths.append(width)
            painter.setPen(self.BACKGROUND_COLOR)
            painter.drawLine(
                x + width,
                separator_vertical_margin,
                x + width,
                self.horizontal_header_height - separator_vertical_margin)
            self.columns_separators.append(QtCore.QRectF(
                x + width - separator_selection_margin,
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
        for rowidx in range(self.row_count):
            value = rowidx - self.row_number_offset + 1
            if value < 1:
                continue
            r = QtCore.QRect(
                0,
                self.horizontal_header_height + LINE_HEIGHT * rowidx,
                self.vertical_header_width,
                LINE_HEIGHT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(value))

        # Paint cells
        painter.setPen(self.TEXT_COLOR)
        columns_widths = []
        ys = []
        for colidx, colname in enumerate(self.df.columns):
            width = self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            for rowidx in range(self.row_count):
                value = self.df[rowidx, colidx]
                x = self.vertical_header_width + sum(columns_widths)
                y = self.horizontal_header_height + LINE_HEIGHT * rowidx
                ys.append(y + LINE_HEIGHT)
                height = LINE_HEIGHT
                # Text
                r = QtCore.QRect(x, y, width, height)
                painter.drawText(
                    r.adjusted(1, 1, -1, -1),
                    Qt.AlignmentFlag.AlignCenter,
                    str(value))
            columns_widths.append(width)

        # vertical lines
        painter.setPen(self.GRID_COLOR)
        x2 = sum(columns_widths) + self.vertical_header_width
        for y in ys:
            r = QtCore.QRect(x, y, width, height)
            painter.drawLine(self.vertical_header_width, y, x2, y)

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


if __name__ == '__main__':
    import os
    app = QtWidgets.QApplication([])
    tableau = Tableau(pl.read_ods(os.path.expandvars('$SAMPLES/sample.ods')))
    tableau.set_column_sizes(dict(z=30))
    tableau.show()
    app.exec()
