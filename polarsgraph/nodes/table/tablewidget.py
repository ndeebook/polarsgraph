import os

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.nodes.base import DISPLAY_INDEX_ATTR, BaseNode, BaseDisplay
from polarsgraph.nodes.table.tableau import TableauWithScroll


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'
BLACK = QtGui.QColor('black')
WHITE = QtGui.QColor('white')

BGCOLOR_COLUMN_SUFFIX = '~color'


class ATTR:
    NAME = 'name'
    COLUMNS_WIDTHS = 'columns_widths'
    DISPLAY_INDEX = DISPLAY_INDEX_ATTR
    FROZEN_COLUMNS = 'frozen_columns'
    FROZEN_ROWS = 'frozen_rows'
    ROWS_NUMBER_OFFSET = 'rows_number_offset'


class TableDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self._resizing = False
        self.node: BaseNode = node
        self.columns = None

        # Widgets
        self.tableau = TableauWithScroll()

        self.table_details_label = QtWidgets.QLabel()
        resize_button = QtWidgets.QPushButton(
            '⇔ columns', clicked=self.tableau.resize_columns_to_contents)
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
        layout.addWidget(self.tableau)
        layout.addWidget(self.bottom_widget)

    def set_table(self, table: pl.DataFrame):
        if table is None:
            self.table_details_label.setText('')
            return self.tableau.set_table(pl.DataFrame())
        columns_count = len(table.columns)

        # Label
        self.table_details_label.setText(
            f'{table.height} x {columns_count}')

        # New widget
        self.tableau.set_table(table)
        self.tableau.set_column_sizes(self.node[ATTR.COLUMNS_WIDTHS] or {})
        self.tableau.set_frozen_columns(self.node[ATTR.FROZEN_COLUMNS])
        self.tableau.set_frozen_rows(self.node[ATTR.FROZEN_ROWS])
        self.tableau.set_rows_number_offset(self.node[ATTR.ROWS_NUMBER_OFFSET])

    def set_board_mode(self, board_enabled: bool):
        self.bottom_widget.setVisible(not board_enabled)

    def export_dataframe(self):
        if self.tableau.tableau.df is None:
            return QtWidgets.QMessageBox.warning(
                self, 'Empty', 'No Table to export',
                QtWidgets.QMessageBox.Ok)
        prompt_save_df(self.tableau.tableau.df, self)

    def get_pixmap(self):
        size = self.tableau.tableau.size()
        pixmap = QtGui.QPixmap(size)
        self.tableau.tableau.render(pixmap)
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
        df = get_table_without_color_columns(self.tableau.tableau.df)
        string = '\t'.join(df.columns)
        for row in df.to_dicts():
            string += '\n' + '\t'.join(str(v) for v in row.values())
        QtWidgets.QApplication.clipboard().setText(string)

    def ascii_to_clipboard(self):
        df = get_table_without_color_columns(self.tableau.tableau.df)
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


def index_or_none(list_: list, value):
    try:
        return list_.index(value)
    except ValueError:
        return


def get_bgcolor_name(column):
    return f'{column}{BGCOLOR_COLUMN_SUFFIX}'
