from PySide6 import QtGui, QtWidgets

from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class DeriveNode(BaseNode):
    type = 'derive'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = QtGui.QColor(111, 111, 222)

    def __init__(self, settings=None):
        super().__init__(settings)


class DeriveSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

    def set_node(self, node, input_tables):
        pass
