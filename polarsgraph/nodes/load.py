import os

from PySide6 import QtWidgets
import polars as pl

from polarsgraph.nodes import BLACK as DEFAULT_COLOR
from polarsgraph.graph import LOAD_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    PATH = 'path'
    CSV_SEPARATOR = 'csv_separator'
    PREFIX = 'columns_prefix'


OPEN_FUNCTIONS = {
    'xlsx': pl.read_excel,
    'csv': pl.read_csv,
}


class LoadNode(BaseNode):
    type = 'load'
    category = LOAD_CATEGORY
    inputs = None
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.CSV_SEPARATOR] = settings.get(ATTR.CSV_SEPARATOR) or ','
        super().__init__(settings)

    def _build_query(self, _):
        path = self[ATTR.PATH]
        if not path:
            raise ValueError('Please specify a file path to open')
        path = os.path.expanduser(os.path.expandvars(path))

        extension = path.split('.')[-1]
        open_func = OPEN_FUNCTIONS[extension]
        kwargs = dict()
        if extension == 'csv':
            kwargs['separator'] = self[ATTR.CSV_SEPARATOR]

        table: pl.LazyFrame = open_func(path, **kwargs).lazy()

        prefix = self[ATTR.PREFIX]
        if prefix:
            table = table.rename({c: f'{prefix}{c}' for c in table.columns})

        self.tables[self.outputs[0]] = table


class LoadSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.path_edit, ATTR.PATH))

        self.browse_button = QtWidgets.QPushButton('Browse')
        self.browse_button.clicked.connect(self._browse)

        self.csv_separator_edit = QtWidgets.QLineEdit()
        self.csv_separator_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.csv_separator_edit, ATTR.CSV_SEPARATOR))

        self.prefix_edit = QtWidgets.QLineEdit()
        self.prefix_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.prefix_edit, ATTR.PREFIX))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.PATH.title(), self.path_edit)
        form_layout.addRow(' ', self.browse_button)
        form_layout.addRow('CSV Separator', self.csv_separator_edit)
        form_layout.addRow('Columns prefix', self.prefix_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.path_edit.setText(node[ATTR.PATH])
        self.csv_separator_edit.setText(node[ATTR.CSV_SEPARATOR] or ',')
        self.prefix_edit.setText(node[ATTR.PREFIX] or '')
        self.blockSignals(False)

    def _browse(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open spreadsheet', '', '*.xlsx *.csv')
        if not filepath:
            return
        self.path_edit.setText(filepath)
        self.line_edit_to_settings(self.path_edit, ATTR.PATH)
