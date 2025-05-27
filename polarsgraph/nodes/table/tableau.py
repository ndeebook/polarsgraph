import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt


LINE_HEIGHT = 24

BGCOLOR_COLUMN_SUFFIX = '~color'


class Tableau(QtWidgets.QWidget):
    def __init__(self, table=None):
        super().__init__()

        self.get_colors()

        self.setMinimumHeight(120)
        self._vertical_scroll = 0
        self._horizontal_scroll = 0
        self.row_number_offset = 1
        self.column_sizes: dict = {}

        self.df: pl.DataFrame
        self.set_table(table)

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QtGui.QPainter):
        rect = self.rect()

        # Background
        painter.setBrush(self.BACKGROUND_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        if self.df is None:
            return

        # header sizes
        vertical_header_width = 24  # TODO: compute based on texts widths
        horizontal_header_height = 24  # TODO: compute based on texts heights

        # horizontal header
        r = QtCore.QRect(rect)
        r.setHeight(horizontal_header_height)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self.HEADER_TEXT)
        columns_widths = []
        for rowidx, title in enumerate(self.df.columns):
            x = vertical_header_width + sum(columns_widths)
            width = 40
            r = QtCore.QRect(x, 0, width, horizontal_header_height)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, title)
            columns_widths.append(40)

        # vertical header
        r = QtCore.QRect(rect)
        r.setWidth(vertical_header_width)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.HEADER_COLOR)
        painter.drawRect(r)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self.HEADER_TEXT)
        for rowidx in range(self.row_count):
            r = QtCore.QRect(
                0,
                horizontal_header_height + LINE_HEIGHT * rowidx,
                vertical_header_width,
                LINE_HEIGHT)
            painter.drawText(
                r, Qt.AlignmentFlag.AlignCenter,
                str(rowidx + self.row_number_offset))

        # Paint cells
        painter.setPen(self.TEXT_COLOR)
        columns_widths = []
        ys = []
        for colidx in range(self.column_count):
            for rowidx in range(self.row_count):
                value = self.df[rowidx, colidx]
                x = vertical_header_width + sum(columns_widths)
                y = horizontal_header_height + LINE_HEIGHT * rowidx
                ys.append(y + LINE_HEIGHT)
                width = 40
                height = LINE_HEIGHT
                # Text
                r = QtCore.QRect(x, y, width, height)
                painter.drawText(
                    r.adjusted(1, 1, -1, -1),
                    Qt.AlignmentFlag.AlignCenter,
                    str(value))
            columns_widths.append(40)

        # vertical lines
        painter.setPen(self.GRID_COLOR)
        x2 = sum(columns_widths) + vertical_header_width
        for y in ys:
            r = QtCore.QRect(x, y, width, height)
            painter.drawLine(vertical_header_width, y, x2, y)

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

    def set_column_sizes(self, sizes):
        self.column_sizes = sizes

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
    tableau.show()
    app.exec()
