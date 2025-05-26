import os

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.nodes.base import DISPLAY_INDEX_ATTR, BaseNode, BaseDisplay


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'
BLACK = QtGui.QColor('black')
WHITE = QtGui.QColor('white')

BGCOLOR_COLUMN_SUFFIX = '~color'


class ATTR:
    NAME = 'name'
    COLUMNS_WIDTHS = 'columns_widths'
    DISPLAY_INDEX = DISPLAY_INDEX_ATTR


class TableDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self._resizing = False
        self.node: BaseNode = node
        self.columns = None

        # Widgets
        self.table_view = QtWidgets.QTableView()
        self.table_view.setStyleSheet(TABLE_HANDLE_CSS)
        mode = QtWidgets.QHeaderView.ScrollPerPixel
        self.table_view.setVerticalScrollMode(mode)
        self.table_view.setHorizontalScrollMode(mode)
        self.table_view.horizontalHeader().sectionResized.connect(
            self.record_column_width)

        self.table_model = PolarsLazyFrameModel(
            dark_theme=self.palette().color(QtGui.QPalette.Base).valueF() < .3)
        self.table_view.setModel(self.table_model)

        self.table_details_label = QtWidgets.QLabel()
        resize_button = QtWidgets.QPushButton(
            '⇔ columns', clicked=self.table_view.resizeColumnsToContents)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditCopy)
        clipboard_image_button = QtWidgets.QPushButton(
            'image', icon=icon, clicked=self.image_to_clipboard)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentSave)
        save_image_button = QtWidgets.QPushButton(
            'image', icon=icon, clicked=self.save_image)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditCopy)
        clipboard_csv_button = QtWidgets.QPushButton(
            'csv', icon=icon, clicked=self.csv_to_clipboard)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditCopy)
        clipboard_ascii_button = QtWidgets.QPushButton(
            'text', icon=icon, clicked=self.ascii_to_clipboard)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentSave)
        save_button = QtWidgets.QPushButton(
            'table', icon=icon, clicked=self.export_dataframe)

        # Layout
        self.bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.table_details_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(resize_button)
        bottom_layout.addWidget(clipboard_image_button)
        bottom_layout.addWidget(clipboard_csv_button)
        bottom_layout.addWidget(clipboard_ascii_button)
        bottom_layout.addWidget(save_image_button)
        bottom_layout.addWidget(save_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.table_view)
        layout.addWidget(self.bottom_widget)

    def set_table(self, table: pl.DataFrame):
        if table is None:
            self.table_details_label.setText('')
            return self.table_model.set_dataframe(pl.DataFrame())
        columns_count = self.table_model.set_dataframe(table)

        # Label
        self.table_details_label.setText(
            f'{table.height} x {columns_count}')

        # Recover saved columns sizes (by column name):
        self.columns = table.schema.names()
        saved_sizes = self.node[ATTR.COLUMNS_WIDTHS] or {}
        for i, column_name in enumerate(self.columns):
            if column_name in saved_sizes:
                self.table_view.setColumnWidth(i, saved_sizes[column_name])

    def set_board_mode(self, board_enabled: bool):
        self.bottom_widget.setVisible(not board_enabled)

    def export_dataframe(self):
        if self.table_model.dataframe is None:
            return QtWidgets.QMessageBox.warning(
                self, 'Empty', 'No Table to export',
                QtWidgets.QMessageBox.Ok)
        prompt_save_df(self.table_model.dataframe, self)

    def get_pixmap(self):
        size = get_table_size(self.table_view)
        size.setHeight(size.height())
        pixmap = QtGui.QPixmap(size)
        self.table_view.render(pixmap)
        return pixmap

    def save_image(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save spreadsheet', '', '*.png')
        if not filepath:
            return
        self.get_pixmap().save(filepath)

    def image_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setPixmap(self.get_pixmap())

    def csv_to_clipboard(self):
        df = get_table_without_color_columns(self.table_model.dataframe)
        string = '\t'.join(df.columns)
        for row in df.to_dicts():
            string += '\n' + '\t'.join(str(v) for v in row.values())
        QtWidgets.QApplication.clipboard().setText(string)

    def ascii_to_clipboard(self):
        df = get_table_without_color_columns(self.table_model.dataframe)
        settings = {
            'POLARS_FMT_MAX_ROWS': '300',
            'POLARS_FMT_MAX_COLS': '50',
            'POLARS_FMT_TABLE_WIDTH': '160'}
        for k, v in settings.items():
            os.environ[k] = v
        text = str(df).replace('null', '    ')
        text = text.split('\n')
        del text[4]  # --- separators
        del text[3]  # column types
        del text[0]  # shape: (2, 4)
        text = '\n'.join(text)
        for k in settings:
            os.environ.pop(k)
        QtWidgets.QApplication.clipboard().setText(text)

    def record_column_width(self, column, oldWidth, newWidth):
        if not self.node[ATTR.COLUMNS_WIDTHS]:
            self.node[ATTR.COLUMNS_WIDTHS] = {}
        column_name = self.columns[column]
        self.node[ATTR.COLUMNS_WIDTHS][column_name] = newWidth


class PolarsLazyFrameModel(QtCore.QAbstractTableModel):
    def __init__(self, dark_theme=False, parent=None):
        super().__init__(parent)

        self.dark_theme = dark_theme
        self.default_text_color = Qt.white if dark_theme else Qt.black

        self.dataframe = pl.DataFrame()
        self.column_count = 0
        self.row_count = 0
        self.bgcolor_column_indexes = dict()

    def set_dataframe(self, dataframe: pl.DataFrame):
        self.layoutAboutToBeChanged.emit()

        self.dataframe = dataframe

        # Columns and Rows counts
        self.column_count = len([
            c for c in self.dataframe.columns
            if not c.endswith(BGCOLOR_COLUMN_SUFFIX)])
        self.row_count = self.dataframe.height

        # Cache existing color columns
        columns = dataframe.columns
        self.bgcolor_column_indexes = {
            columns.index(c): index_or_none(columns, get_bgcolor_name(c))
            for c in columns}

        self.layoutChanged.emit()

        return self.column_count

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Vertical:
                return str(section + 1)
            if orientation == Qt.Horizontal:
                return self.dataframe.columns[section]
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

    def rowCount(self, *_):
        return self.row_count

    def columnCount(self, *_):
        return self.column_count

    def _get_bg_color(self, row, col):
        color_col = self.bgcolor_column_indexes.get(col)
        if color_col is None:
            return
        color = self.dataframe[row, color_col]
        if color:
            return QtGui.QColor(color)

    def data(self, index, role):
        if not index.isValid():
            return

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        row, col = index.row(), index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            value = self.dataframe[row, col]
            if value is None:
                return ''
            return str(value)

        if role == Qt.ItemDataRole.BackgroundRole:
            return self._get_bg_color(row, col)

        elif role == Qt.ItemDataRole.ForegroundRole:
            bg_color = self._get_bg_color(row, col)
            if not bg_color:
                return self.default_text_color
            if bg_color.valueF() < .5:
                return WHITE
            else:
                return BLACK


def prompt_save_df(df, parent=None):
    filepath, result = QtWidgets.QFileDialog.getSaveFileName(
        parent, 'Export', filter='(*.xlsx *.parquet, *.pickle)')
    if not result:
        return
    export_df_to_file(df, filepath)


def export_df_to_file(df: pl.DataFrame, path: str):
    df = get_table_without_color_columns(df)
    logger.debug(path)
    QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        if path.endswith('xlsx'):
            for col, dtype in zip(df.columns, df.dtypes):
                if dtype == pl.String:
                    df = df.with_columns(pl.col(col).str.replace('false', ''))
            df.write_excel(path)
        elif path.endswith('parquet'):
            df.write_parquet(path)
        elif path.endswith('pickle'):
            import pickle
            with open(path, 'wb') as f:
                pickle.dump(df, f)
        else:
            raise ValueError(f'Extension not covered ({path})')
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def get_table_without_color_columns(df):
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
    color_columns = [
        c for c in df.columns if c.endswith(BGCOLOR_COLUMN_SUFFIX)]
    return df.drop(color_columns)


def get_table_size(table: QtWidgets.QTableView):
    """
    table.size() includes blank space.
    Use position of last cell + its size + header
    """
    # height
    last_row = table.model().rowCount() - 1
    height = (
        table.rowViewportPosition(last_row) +
        table.rowHeight(last_row) +
        table.horizontalHeader().height())

    # width
    last_col = table.model().columnCount() - 1
    width = (
        table.columnViewportPosition(last_col) +
        table.columnWidth(last_col) +
        table.verticalHeader().width())

    width = min(table.width(), width)
    height = min(table.height(), height)

    return QtCore.QSize(width, height)


def index_or_none(list_: list, value):
    try:
        return list_.index(value)
    except ValueError:
        return


def get_bgcolor_name(column):
    return f'{column}{BGCOLOR_COLUMN_SUFFIX}'
