import os
import re

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


DEFAULT_COLORS = 'background-color:#1e1e1e; color: #cccccc'
EXPRESSIONS_COLORS = {
    r'.*polars\.exceptions.*': 'orange',
    r'.*could not determine dtype.*': 'orange',
}


class SettingsWidget(QtWidgets.QWidget):
    settings_changed = QtCore.Signal(str)
    rename_asked = QtCore.Signal(str, str)

    def __init__(self, types):
        super().__init__()

        self.types = types
        self.types_widgets: dict[str, BaseSettingsWidget] = dict()
        self.node = None

        # Fixed size font
        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)

        # Widgets
        self.setMinimumWidth(333)

        self.settings_edit = QtWidgets.QPlainTextEdit()
        self.settings_edit.setMinimumWidth(300)
        self.settings_edit.setMinimumHeight(200)
        self.settings_edit.setFont(fixed_font)
        self.settings_edit.setParent(self)
        self.settings_edit.setWindowFlags(Qt.WindowType.Window)
        self.settings_edit.setWindowTitle('Node Settings')

        self.errors_browser = QtWidgets.QTextBrowser()
        self.errors_browser.setParent(self)
        self.errors_browser.setWindowFlags(Qt.WindowType.Window)
        self.errors_browser.setMinimumWidth(700)
        self.errors_browser.setMinimumHeight(300)
        self.errors_browser.setFont(fixed_font)
        self.errors_browser.setWindowTitle('Node Error')

        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.HelpAbout)
        serialized_settings_button = QtWidgets.QPushButton(
            '  show settings', icon=icon)
        serialized_settings_button.clicked.connect(self.settings_edit.show)

        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentProperties)
        errors_button = QtWidgets.QPushButton(
            '  show error', icon=icon)
        errors_button.clicked.connect(self.show_error)

        # Layout
        self.node_layout = QtWidgets.QVBoxLayout()
        for typename, config in self.types.items():
            widget: BaseSettingsWidget = config['widget']()
            self.types_widgets[typename] = widget
            widget.setVisible(False)
            widget.settings_changed.connect(self.settings_changed.emit)
            widget.settings_changed.connect(self.set_settings_edit_text)
            widget.rename_asked.connect(self.rename_asked.emit)
            self.node_layout.addWidget(widget)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(serialized_settings_button)
        buttons_layout.addWidget(errors_button)
        buttons_layout.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.node_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

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

    def show_error(self):
        if not self.node or not self.node.error:
            self.errors_browser.clear()
        else:
            self.errors_browser.setHtml(format_error(self.node.error))
        self.errors_browser.show()

    def clear(self):
        self.settings_edit.clear()


def format_error(text):
    for expression, color in EXPRESSIONS_COLORS.items():
        for string in re.findall(expression, text):
            text = text.replace(
                string, f'<font color="{color}">{string}</font>')
    text = (
        text
        .replace('\n', '<br>')
        .replace('  ', '&nbsp;&nbsp;')
    )
    text = f'<body style="{DEFAULT_COLORS}">{text}</body>'
    return text
