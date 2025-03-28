from PySide6 import QtWidgets

from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes import GRAY as DEFAULT_COLOR
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'


class DotNode(BaseNode):
    type = 'dot'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        self.tables['table'] = tables[0]


class DotSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.blockSignals(False)
