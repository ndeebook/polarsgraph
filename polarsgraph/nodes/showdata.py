from PySide6 import QtGui
from polarsgraph.nodes.base import BaseNode


class ShowdataNode(BaseNode):
    type = 'show_data'
    inputs = None
    outputs = 'user', 'status', 'task', 'worktime'
    default_color = QtGui.QColor(5, 5, 5)

    def __init__(self, name, settings=None):
        super().__init__(name, settings)
