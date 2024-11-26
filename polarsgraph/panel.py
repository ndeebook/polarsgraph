import os

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class SettingsWidget(QtWidgets.QWidget):
    settings_changed = QtCore.Signal(str)
    rename_asked = QtCore.Signal(str, str)

    def __init__(self, types):
        super().__init__()

        self.types = types
        self.types_widgets: dict[str, BaseSettingsWidget] = dict()
        self.node = None

        # Widgets
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.FormatJustifyLeft)
        serialized_settings_button = QtWidgets.QPushButton(icon=icon)

        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.SyncError)
        self.error_button = QtWidgets.QPushButton(icon=icon)

        self.settings_edit = QtWidgets.QPlainTextEdit()
        self.settings_edit.setMinimumWidth(300)
        self.settings_edit.setMaximumHeight(200)
        self.settings_edit.setMinimumHeight(200)
        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)
        self.settings_edit.setFont(fixed_font)

        # settings_edit as Window
        self.settings_edit.setParent(self)
        self.settings_edit.setWindowFlags(Qt.WindowType.Tool)
        self.settings_edit.setWindowTitle('Node Settings')
        serialized_settings_button.clicked.connect(self.settings_edit.show)

        # Layout
        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.addSpacing(4)
        toolbar_layout.addWidget(serialized_settings_button)
        toolbar_layout.addWidget(self.error_button)
        toolbar_layout.addStretch()

        self.node_layout = QtWidgets.QVBoxLayout()
        for typename, config in self.types.items():
            widget: BaseSettingsWidget = config['widget']()
            self.types_widgets[typename] = widget
            widget.setVisible(False)
            widget.settings_changed.connect(self.settings_changed.emit)
            widget.settings_changed.connect(self.set_settings_edit_text)
            widget.rename_asked.connect(self.rename_asked.emit)
            self.node_layout.addWidget(widget)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar_layout)
        layout.addLayout(self.node_layout)
        layout.addStretch()
        # layout.addWidget(self.settings_edit)

    def set_node(self, node: BaseNode, input_tables: list[pl.LazyFrame]):
        self.node = node
        node_type = node.type if node else None
        for typename, widget in self.types_widgets.items():
            if node_type == typename:
                widget.setVisible(True)
                widget.set_node(node, input_tables)
            else:
                widget.setVisible(False)
        self.set_settings_edit_text()

    def set_settings_edit_text(self):
        if not self.node:
            return self.settings_edit.clear()
        self.settings_edit.setPlainText(self.node.serialize())

    def clear(self):
        self.settings_edit.clear()
