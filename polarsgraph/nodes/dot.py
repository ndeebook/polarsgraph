from PySide6 import QtWidgets

from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes import GRAY as DEFAULT_COLOR
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class DotNode(BaseNode):
    type = 'dot'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR

    def _build_query(self, tables):
        self.tables['table'] = tables[0]


class DotSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(DotNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
