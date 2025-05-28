import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt


ROW_HEIGHT = 24
DEFAULT_COL_WIDTH = 80
MINIMUM_COL_WIDTH = 24
AUTO_SIZE_MARGIN = 16

BGCOLOR_COLUMN_SUFFIX = '~color'
BLACK = QtGui.QColor('black')
WHITE = QtGui.QColor('white')


class Tableau(QtWidgets.QWidget):
    columns_resized = QtCore.Signal()

    def __init__(self, table=None, parent=None):
        super().__init__(parent)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding)

        self.setMouseTracking(True)
        self.font_ = self.font()
        self.metrics = QtGui.QFontMetrics(self.font_)

        self._vertical_scroll = 0
        self._horizontal_scroll = 0
        self.row_number_offset = 0
        self.frozen_columns = 0
        self.frozen_rows = 0

        self.column_sizes: dict = {}
        self._column_sizes: list = []

        self.df: pl.DataFrame
        self.set_table(table)

        self.TEXT_COLOR: QtGui.QColor
        self.BACKGROUND_COLOR: QtGui.QColor
        self.GRID_COLOR: QtGui.QColor
        self.HEADER_TEXT: QtGui.QColor
        self.HEADER_COLOR: QtGui.QColor
        self.get_palette_colors()

        self.columns_separators: dict[int, QtCore.QRect] = {}
        self.selected_column_separator: str | None = None
        self._column_resized = False

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def compute_headers_sizes(self):
        if not self.columns:
            return
        rect = self.rect()

        # Horizontal header size
        max_height = max([
            self.metrics.boundingRect(rect, Qt.AlignCenter, c).height()
            for c in self.columns])
        self.horizontal_header_height = max(24, max_height + 4)

        # vertical header size
        last_label = str(self.row_count + self.row_number_offset - 1)
        text_rect = self.metrics.boundingRect(
            rect, Qt.AlignmentFlag.AlignCenter, last_label)
        self.vertical_header_width = max(24, text_rect.width() + 4)

    def get_table_size(self):
        if not self.columns:
            return 0, 0
        self.compute_headers_sizes()
        h = self.horizontal_header_height + self.row_count * ROW_HEIGHT
        columns_widths = [
            self.column_sizes.get(c, DEFAULT_COL_WIDTH)
            for c in self.columns]
        w = self.vertical_header_width + sum(columns_widths)
        return w, h

    def set_vertical_scroll(self, value):
        self._vertical_scroll = value
        self.update()

    def set_horizontal_scroll(self, value):
        self._horizontal_scroll = value
        self.update()

    def _get_column_x(self, column_index, viewport_width):
        x = self.vertical_header_width + sum(self._column_sizes[:column_index])

        # if not frozen, offset by scroll:
        if column_index >= self.frozen_columns:
            x -= self._horizontal_scroll

        # check if column is visible:
        if x + self._column_sizes[column_index] < 0:
            return
        if x > viewport_width:
            return
        return x

    def _get_row_y(self, row_index, viewport_height):
        y = self.horizontal_header_height + row_index * ROW_HEIGHT

        # if not frozen, offset by scroll:
        if row_index >= self.frozen_rows:
            y -= self._vertical_scroll

        # check if row is visible:
        if y + ROW_HEIGHT < 0:
            return
        if y > viewport_height:
            return

        return y

    def _get_cell_colors(self, row, col):
        color_col = self.bgcolor_column_indexes.get(col)
        if color_col:
            color = self.df[row, color_col]
            if color:
                bg_color = QtGui.QColor(color)
                text_color = WHITE if bg_color.valueF() < .5 else BLACK
                return bg_color, text_color
        return self.BACKGROUND_COLOR, self.TEXT_COLOR

    def _paint(self, painter: QtGui.QPainter):
        # Collect main sizes
        self.compute_headers_sizes()
        self._column_sizes = [
            self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            for colname in self.columns]

        rect = self.rect()
        widget_width, widget_height = rect.size().toTuple()

        # Background
        painter.setBrush(self.BACKGROUND_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        if self.df is None or not self.columns:
            return

        # Paint cells
        columns_widths = []
        rows_y = dict()  # cache values for headers
        columns_x = dict()  # cache values for headers
        for col_index, colname in reversed(list(enumerate(self.columns))):
            col_width = self._column_sizes[col_index]
            x = self._get_column_x(col_index, widget_width)
            if x is None:
                continue
            columns_x[col_index] = x
            for row_index in reversed(range(self.row_count)):
                # Rect
                y = self._get_row_y(row_index, widget_height)
                if y is None:
                    continue
                rows_y[row_index] = y
                value = self.df[row_index, col_index]
                r = QtCore.QRect(x, y, col_width, ROW_HEIGHT)
                # Background
                bg_color, text_color = self._get_cell_colors(
                    row_index, col_index)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.BACKGROUND_COLOR)
                painter.drawRect(r)  # needed to hide frozen cells last pixels
                painter.setBrush(bg_color)
                painter.drawRect(r.adjusted(0, 0, -1, 0))
                # Text
                painter.setPen(text_color)
                painter.drawText(
                    r.adjusted(1, 1, -1, -1),
                    Qt.AlignmentFlag.AlignCenter,
                    str(value))
                # Line under cell
                painter.setPen(self.GRID_COLOR)
                painter.drawLine(
                    x, y + ROW_HEIGHT, x + col_width, y + ROW_HEIGHT)
            columns_widths.append(col_width)

        # horizontal header
        r = QtCore.QRect(rect)
        r.setHeight(self.horizontal_header_height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        self.columns_separators.clear()
        separator_vertical_margin = 4
        separator_selection_margin = 4
        for col_index, colname in reversed(list(enumerate(self.columns))):
            # Rect
            if col_index not in columns_x:
                continue
            x = columns_x[col_index]
            col_width = self.column_sizes.get(colname, DEFAULT_COL_WIDTH)
            r = QtCore.QRect(x, 0, col_width, self.horizontal_header_height)
            # Background
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(r)
            # Text
            painter.setPen(self.HEADER_TEXT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, colname)
            # Separator
            painter.setPen(self.BACKGROUND_COLOR)
            painter.drawLine(
                x + col_width,
                separator_vertical_margin,
                x + col_width,
                self.horizontal_header_height - separator_vertical_margin)
            selection_rect = QtCore.QRectF(
                x + col_width - separator_selection_margin,
                0,
                separator_selection_margin * 2,
                self.horizontal_header_height)
            self.columns_separators[col_index] = selection_rect
            # Frozen columns separator
            if col_index == self.frozen_columns - 1:
                painter.setPen(self.GRID_COLOR)
                y = max(rows_y.values()) + ROW_HEIGHT
                x += self._column_sizes[col_index]
                painter.drawLine(x, self.horizontal_header_height, x, y)

        # vertical header
        r = QtCore.QRect(rect)
        r.setWidth(self.vertical_header_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        for row_index in reversed(range(self.row_count)):
            # Rect
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
            # Background
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(r)
            # Text
            painter.setPen(self.HEADER_TEXT)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, str(value))

        # header corner
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        corner_height = (
            self.horizontal_header_height
            + ROW_HEIGHT * self.row_number_offset)
        painter.drawRect(0, 0, self.vertical_header_width, corner_height)

    def get_separator_column_under_cursor(self, pos) -> str:
        for i, rect in self.columns_separators.items():
            if rect.contains(pos):
                return self.columns[i]

    def set_cursor(self, pos):
        if self.get_separator_column_under_cursor(pos):
            QtWidgets.QApplication.setOverrideCursor(
                Qt.CursorShape.SizeHorCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def leaveEvent(self, event):
        QtWidgets.QApplication.restoreOverrideCursor()
        return super().leaveEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        # Drag:
        if self.selected_column_separator:
            pos = event.position()
            delta = self.drag_start.x() - pos.x()
            current_width = self.column_sizes.get(
                self.selected_column_separator, DEFAULT_COL_WIDTH)
            new_width = max(current_width - delta, MINIMUM_COL_WIDTH)
            self.column_sizes[self.selected_column_separator] = new_width
            if new_width != MINIMUM_COL_WIDTH:
                self.drag_start = pos
            self._column_resized = True
            self.update()
            return
        # Mouse Hover:
        self.set_cursor(event.position())

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        pos = event.position()
        self.selected_column_separator = (
            self.get_separator_column_under_cursor(pos))
        self.drag_start = pos
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.selected_column_separator = None
        if self._column_resized:
            self.columns_resized.emit()
            self._column_resized = False
        return super().mouseReleaseEvent(event)

    def set_table(self, table: pl.DataFrame):
        table = table if table is not None else pl.DataFrame()
        self.df = table
        if table is None:
            self.column_count = 0
            self.row_count = 0
            return

        self.columns = [
            c for c in self.df.columns
            if not c.endswith(BGCOLOR_COLUMN_SUFFIX)]
        self.column_count = len(self.columns)
        self.row_count = self.df.height

        columns = table.columns
        self.bgcolor_column_indexes = {
            columns.index(c): index_or_none(columns, get_bgcolor_name(c))
            for c in columns}

    def resize_columns_to_contents(self):
        sizes = dict()
        for col_index, col_name in enumerate(self.columns):
            max_cell_width = max([
                self.metrics.boundingRect(str(self.df[row, col_index])).width()
                for row in range(self.row_count)])
            sizes[col_name] = max([
                self.metrics.boundingRect(col_name).width(),
                max_cell_width]) + AUTO_SIZE_MARGIN
        self.set_column_sizes(sizes)

    def set_column_sizes(self, column_sizes):
        self.column_sizes = column_sizes
        self.update()

    def get_palette_colors(self):
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

        scroll_width = self.vertical_scroll.width()
        self.horizontal_scroll.setVisible(
            content_width > widget_width - scroll_width)
        self.horizontal_scroll.setMaximum(
            content_width - widget_width + scroll_width)
        self.horizontal_scroll.setMinimum(0)

        scroll_height = self.horizontal_scroll.height()
        self.vertical_scroll.setVisible(
            content_height > widget_height - scroll_height)
        self.vertical_scroll.setMaximum(
            content_height - widget_height + scroll_height)
        self.vertical_scroll.setMinimum(0)

    def set_frozen_columns(self, count):
        self.tableau.frozen_columns = count or 0
        self.update()

    def set_frozen_rows(self, count):
        self.tableau.frozen_rows = count or 0
        self.update()

    def set_rows_number_offset(self, offset):
        self.tableau.row_number_offset = offset or 0
        self.update()

    def resize_columns_to_contents(self):
        self.tableau.resize_columns_to_contents()
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)

    def set_column_sizes(self, sizes):
        self.tableau.set_column_sizes(sizes)
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)

    def wheelEvent(self, event: QtGui.QWheelEvent):
        offset = ROW_HEIGHT / 2
        if event.angleDelta().y() > 0:
            offset *= -1
        value = max(0, min(
            self.vertical_scroll.value() + offset,
            self.vertical_scroll.maximum()))
        self.vertical_scroll.setValue(value)
        self.tableau.set_vertical_scroll(value)
        return super().wheelEvent(event)

    def resizeEvent(self, event):
        r = super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)
        return r

    def showEvent(self, event):
        r = super().showEvent(event)
        QtCore.QTimer.singleShot(0, self.adjust_scrollbars)
        return r


def index_or_none(list_: list, value):
    try:
        return list_.index(value)
    except ValueError:
        return


def get_bgcolor_name(column):
    return f'{column}{BGCOLOR_COLUMN_SUFFIX}'


if __name__ == '__main__':
    import os
    app = QtWidgets.QApplication([])
    df = pl.read_ods(os.path.expandvars('$SAMPLES/sample.ods'))
    tableau = TableauWithScroll(df)
    tableau.set_column_sizes(dict(z=30))
    tableau.set_frozen_columns(2)
    tableau.set_frozen_rows(2)
    tableau.show()
    app.exec()
