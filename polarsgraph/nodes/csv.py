import io

from PySide6 import QtWidgets
import polars as pl

from polarsgraph.nodes import BLACK as DEFAULT_COLOR
from polarsgraph.graph import LOAD_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    DATA = 'data'
    CSV_SEPARATOR = 'csv_separator'
    PREFIX = 'columns_prefix'


class CsvNode(BaseNode):
    type = 'csv'
    category = LOAD_CATEGORY
    inputs = None
    output_plugs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.CSV_SEPARATOR] = settings.get(ATTR.CSV_SEPARATOR) or ','
        super().__init__(settings)

    def _build_query(self, _):
        data = self[ATTR.DATA]
        if not data:
            raise ValueError('Please enter some CSV data')

        table: pl.DataFrame = pl.read_csv(
            io.StringIO(data),
            separator=self[ATTR.CSV_SEPARATOR] or ',',
        )

        prefix = self[ATTR.PREFIX]
        if prefix:
            table = table.rename({c: f'{prefix}{c}' for c in table.columns})

        self.tables[self.output_plugs[0]] = table.lazy()


class CsvSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.data_edit = QtWidgets.QPlainTextEdit()
        self.data_edit.setPlaceholderText('Paste CSV data here...')
        self.data_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(self.data_edit, ATTR.DATA))

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
        form_layout.addRow('CSV Separator', self.csv_separator_edit)
        form_layout.addRow('Columns prefix', self.prefix_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QtWidgets.QLabel('CSV Data'))
        layout.addWidget(self.data_edit)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.csv_separator_edit.setText(node[ATTR.CSV_SEPARATOR] or ',')
        self.prefix_edit.setText(node[ATTR.PREFIX] or '')
        self.data_edit.setPlainText(node[ATTR.DATA] or '')
        self.blockSignals(False)
