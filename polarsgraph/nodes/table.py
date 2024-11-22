import traceback

import yaml
import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'


class TableNode(BaseNode):
    type = 'table'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables):
        self.tables['table'] = tables[0]
        # Update display
        if not self.display_widget:
            return
        self.display_widget.set_table(tables[0])

    def clear(self):
        self.display_widget.set_table(pl.LazyFrame())

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = TableDisplay()
        return self._display_widget


class TableSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        ...

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.blockSignals(False)


class TableDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.node: TableNode = None
        self._resizing = False

        # Widgets
        self.table_view = QtWidgets.QTableView()
        self.table_view.setStyleSheet(TABLE_HANDLE_CSS)
        mode = QtWidgets.QHeaderView.ScrollPerPixel
        self.table_view.setVerticalScrollMode(mode)
        self.table_view.setHorizontalScrollMode(mode)
        self.table_view.horizontalHeader().sectionResized.connect(
            self.record_column_width)

        self.table_model = PolarsLazyFrameModel()
        self.table_view.setModel(self.table_model)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table_view)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            return self.table_model.set_dataframe(pl.DataFrame())
        self.table_model.set_dataframe(table.collect(stream=True))

    def show_dataframe(self, node):
        raise NotImplementedError
        self.node = node
        # Color dataframes first to avoid display error
        bg_color_df = node.bg_color_dfs.get(table_name)
        if bg_color_df is not None:
            bg_color_df = bg_color_df.collect(stream=True)
        self.table_model.set_dataframe(bg_color_df, which='bg_color')

        text_color_df = node.text_color_dfs.get(table_name)
        if text_color_df is not None:
            text_color_df = text_color_df.collect(stream=True)
        self.table_model.set_dataframe(text_color_df, which='text_color')

        # Content dataframe:
        try:
            dataframe = node.dataframes[table_name].collect(stream=True)
            self.table_name_label.setText(
                f'{node.full_name}: {table_name}')
            self.table_details_label.setText(
                f'{dataframe.height} x {dataframe.width}')
            self.table_model.set_dataframe(dataframe)
            # Resize
            try:
                columns_sizes = yaml.safe_load(
                    self.node.settings.get('columns_sizes'))
            except BaseException:
                columns_sizes = dict()
            if columns_sizes:
                self._resizing = True
                for index, width in columns_sizes.items():
                    self.table_view.setColumnWidth(index, width)
                self._resizing = False
            elif dataframe.height * dataframe.width < 1000:
                self.table_view.resizeColumnsToContents()
            else:
                # When there is a lot of content it's slow, only check headers:
                fit_columns_to_headers(self.table_view)
        except BaseException:
            dataframe = pl.DataFrame()
            self.table_name_label.setText('Error')
            self.table_details_label.setText('')
            self.stack.set_error(node, traceback.format_exc())
            self.table_model.set_dataframe(dataframe)

    def export_dataframe(self):
        if self.table_model.dataframe is None:
            return QtWidgets.QMessageBox.warning(
                self, 'Empty', 'No Table to export',
                QtWidgets.QMessageBox.Ok)
        prompt_save_df(self.table_model.dataframe, name=self.node['name'])

    def get_pixmap(self):
        top_label_size = 40

        size = get_table_size(self.table_view)
        size.setHeight(size.height() + top_label_size)
        pixmap = QtGui.QPixmap(size)
        pixmap.fill(Qt.black)
        self.table_view.render(
            pixmap, targetOffset=QtCore.QPoint(0, top_label_size))
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
        string = '\t'.join(self.table_model.dataframe.columns)
        for row in self.table_model.dataframe.to_dicts():
            string += '\n' + '\t'.join(str(v) for v in row.values())
        QtWidgets.QApplication.clipboard().setText(string)

    def record_column_width(self, column, oldWidth, newWidth):
        if self._resizing:
            return
        try:
            sizes = yaml.safe_load(self.node['columns_sizes'])
        except BaseException:
            sizes = dict()
        sizes[column] = newWidth
        if self.node:
            self.node.settings.update(dict(columns_sizes=sizes))


class PolarsLazyFrameModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataframe = pl.DataFrame()
        self.bg_colors_df: pl.DataFrame = None
        self.text_colors_df: pl.DataFrame = None

    def set_dataframe(self, dataframe: pl.DataFrame, which='main'):
        self.layoutAboutToBeChanged.emit()
        if which == 'main':
            self.dataframe = dataframe
        elif which == 'bg_color':
            self.bg_colors_df = dataframe
        elif which == 'text_color':
            self.text_colors_df = dataframe
        else:
            raise ValueError(f'Bad "which" argument value "{which}"')
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Vertical:
                return str(section + 1)
            if orientation == Qt.Horizontal:
                return self.dataframe.columns[section]
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

    def rowCount(self, *_):
        return self.dataframe.height

    def columnCount(self, *_):
        return self.dataframe.width

    def data(self, index, role):
        if not index.isValid():
            return

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        row, col = index.row(), index.column()

        if role == Qt.DisplayRole:
            value = self.dataframe[row, col]
            if value is None:
                return ''
            return str(value)

        if self.bg_colors_df is not None and role == Qt.BackgroundColorRole:
            color = self.bg_colors_df[row, col]
            if color:
                return QtGui.QColor(color)
        elif self.text_colors_df is not None and role == Qt.TextColorRole:
            color = self.text_colors_df[row, col]
            if color:
                return QtGui.QColor(color)


def export_df_to_file(df: pl.DataFrame, path: str):
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
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
        else:
            raise ValueError(f'Extension not covered ({path})')
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def prompt_save_df(df, parent=None):
    filepath, result = QtWidgets.QFileDialog.getSaveFileName(
        parent, 'Export', filter='(*.xlsx *.parquet)')
    if not result:
        return
    export_df_to_file(df, filepath)


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


def fit_columns_to_headers(table: QtWidgets.QTableView):
    header = table.horizontalHeader()
    for column in range(header.count()):
        header_width = header.sectionSizeHint(column)
        table.setColumnWidth(column, header_width)
