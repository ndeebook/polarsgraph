import os

from PySide6 import QtGui, QtWidgets
import polars as pl

from polarsgraph.graph import LOAD_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    PATH = 'path'


class LoadNode(BaseNode):
    type = 'load'
    category = LOAD_CATEGORY
    inputs = None
    outputs = 'table',
    default_color = QtGui.QColor(5, 5, 5)

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, _):
        path = self.settings['path']
        if not path:
            raise ValueError('Please specify a file path to open')
        path = os.path.expandvars(path)
        extension = path.split('.')[-1]
        open_func = dict(xlsx=pl.read_excel)[extension]
        self.tables[self.outputs[0]] = open_func(path).lazy()


class LoadSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.path_edit = QtWidgets.QLineEdit()
        self.browse_button = QtWidgets.QPushButton('Browse')

        # Signals
        self.browse_button.clicked.connect(self._browse)
        self.path_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.path_edit, ATTR.PATH))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.PATH.title(), self.path_edit)
        form_layout.addRow(' ', self.browse_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.path_edit.setText(node[ATTR.PATH])
        self.blockSignals(False)

    def _browse(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open spreadsheet', '', '*.xlsx')
        if not filepath:
            return
        self.path_edit.setText(filepath)
        self.line_edit_to_settings(self.path_edit, ATTR.PATH)
