import os

from PySide6 import QtWidgets
import polars as pl

from polarsgraph.attrs import StrAttr
from polarsgraph.nodes import BLACK as DEFAULT_COLOR
from polarsgraph.graph import LOAD_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


PATH = 'path'
CSV_SEPARATOR = 'csv_separator'
PREFIX = 'columns_prefix'


OPEN_FUNCTIONS = {
    'xlsx': pl.read_excel,
    'ods': pl.read_ods,
    'csv': pl.read_csv,
    'parquet': pl.read_parquet,
    'json': pl.read_json,
}
MASK = ' '.join([f'*.{ext}' for ext in OPEN_FUNCTIONS])


class LoadNode(BaseNode):
    type = 'load'
    category = LOAD_CATEGORY
    inputs = None
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        StrAttr(PATH, label='Path'),
        StrAttr(CSV_SEPARATOR, default=',', label='CSV Separator'),
        StrAttr(PREFIX, label='Columns prefix'),
    ]

    def _build_query(self, _):
        path = self[PATH]
        if not path:
            raise ValueError('Please specify a file path to open')
        path = os.path.expanduser(os.path.expandvars(path))

        extension = path.split('.')[-1]
        open_func = OPEN_FUNCTIONS[extension]
        kwargs = dict()
        if extension == 'csv':
            kwargs['separator'] = self[CSV_SEPARATOR]

        table: pl.DataFrame = open_func(path, **kwargs)

        prefix = self[PREFIX]
        if prefix:
            table = table.rename({c: f'{prefix}{c}' for c in table.columns})

        self.tables[self.output_plugs[0]] = table.lazy()


class LoadSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        path_attr, separator_attr, prefix_attr = LoadNode.attrs

        form = QtWidgets.QFormLayout()
        form.addRow('Name', self.name_edit)
        for attr in (path_attr, separator_attr, prefix_attr):
            label, widget = self.register_attr(attr)
            form.addRow(label, widget)

        self.browse_button = QtWidgets.QPushButton('Browse')
        self.browse_button.clicked.connect(self._browse)
        self.reload_button = QtWidgets.QPushButton('Reload file')
        self.reload_button.clicked.connect(self.emit_changed)

        # Insert the browse button right after the Path row.
        form.insertRow(2, ' ', self.browse_button)
        form.addRow(' ', self.reload_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)

    def _browse(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open spreadsheet', '', MASK)
        if not filepath:
            return
        path_attr = LoadNode.attrs[0]
        path_attr.widget.setText(filepath)
        self.line_edit_to_settings(path_attr.widget, PATH)
