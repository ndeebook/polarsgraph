from PySide6 import QtWidgets

from polarsgraph.nodes import LIGHT_GRAY
from polarsgraph.graph import BACKDROP_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    WIDTH = 'width'
    HEIGHT = 'height'
    COLOR = 'color'
    TEXT = 'text'
    TEXT_SIZE = 'text_size'


class BackdropNode(BaseNode):
    type = 'backdrop'
    category = BACKDROP_CATEGORY
    default_color = LIGHT_GRAY

    def __init__(self, settings=None):
        super().__init__(settings)
        settings[ATTR.COLOR] = settings.get(ATTR.COLOR) or LIGHT_GRAY
        settings[ATTR.WIDTH] = settings.get(ATTR.WIDTH) or 200
        settings[ATTR.HEIGHT] = settings.get(ATTR.HEIGHT) or 100
        settings[ATTR.TEXT_SIZE] = settings.get(ATTR.TEXT_SIZE) or 20

    def _build_query(self, tables):
        return


class BackdropSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.color_button = QtWidgets.QPushButton(
            'Color', clicked=self.set_color)
        self.text_edit = QtWidgets.QPlainTextEdit()
        self.text_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(self.text_edit, ATTR.TEXT))
        self.text_size_spinbox = QtWidgets.QSpinBox(maximum=999)
        self.text_size_spinbox.valueChanged.connect(
            lambda: self.spinbox_to_settings(
                self.text_size_spinbox, ATTR.TEXT_SIZE))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.COLOR.title(), self.color_button)
        form_layout.addRow(ATTR.TEXT.title(), self.text_edit)
        form_layout.addRow('Font size', self.text_size_spinbox)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        self.node[ATTR.COLOR] = color
        self.emit_changed()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.text_edit.setPlainText(node[ATTR.TEXT] or '')
        self.text_size_spinbox.setValue(node[ATTR.TEXT_SIZE] or 20)
        self.blockSignals(False)
