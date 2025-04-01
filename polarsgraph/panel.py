import os
import re

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget
from polarsgraph.serialize import deserialize_node


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

        self.node_type_label = QtWidgets.QLabel()

        self.settings_edit = TextSettingsWidget(fixed_font, self)
        self.settings_edit.settings_changed.connect(self.settings_changed.emit)

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
        serialized_settings_button.clicked.connect(self.show_text_settings)

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

        type_layout = QtWidgets.QHBoxLayout()
        type_layout.addStretch()
        type_layout.addWidget(self.node_type_label)
        type_layout.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(type_layout)
        layout.addLayout(self.node_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def set_node(self, node: BaseNode, input_tables: list[pl.LazyFrame]):
        self.node = node
        node_type = node.type if node else ''
        self.node_type_label.setText(f'<b>{node_type.title()}</b>')
        for widget in self.types_widgets.values():
            widget.setVisible(False)
        widget = self.types_widgets[node_type]
        widget.setVisible(True)
        widget.set_node(node, input_tables)
        self.set_settings_edit_text()

    def set_settings_edit_text(self):
        if not self.node:
            return self.settings_edit.clear()
        self.settings_edit.set_node(self.node)

    def show_text_settings(self):
        self.set_settings_edit_text()
        self.settings_edit.show()

    def show_error(self):
        if not self.node or not self.node.error:
            self.errors_browser.clear()
        else:
            self.errors_browser.setHtml(format_error(self.node.error))
        self.errors_browser.show()

    def clear(self):
        self.settings_edit.clear()


class TextSettingsWidget(QtWidgets.QWidget):
    settings_changed = QtCore.Signal(str)
    default_css = 'font-family:consolas;font-size:10pt'
    red_bg_css = default_css + ';background-color:#991111'

    def __init__(self, font, parent=None):
        super().__init__(parent=parent)

        self.node: BaseNode = None

        self.setWindowTitle('Node Settings')
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setFont(font)
        self.setWindowFlags(Qt.WindowType.Window)

        self.text_edit = QtWidgets.QPlainTextEdit(styleSheet=self.default_css)
        self.text_edit.setWindowFlags(Qt.Tool)
        self.text_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.highlighter = CustomHighlighter(self.text_edit.document())

        save_btn = QtWidgets.QPushButton('Save', clicked=self.save_settings)

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout.addWidget(save_btn)

    def clear(self):
        self.text_edit.clear()

    def set_node(self, node: BaseNode):
        self.node = node
        self.text_edit.setStyleSheet(self.default_css)
        self.text_edit.setPlainText(self.node.serialize())

    def save_settings(self):
        text_settings = self.text_edit.toPlainText()
        try:
            settings = deserialize_node(text_settings)
        except BaseException:
            self.text_edit.setStyleSheet(self.red_bg_css)
            return
        self.node.settings.update(settings)
        self.settings_changed.emit(self.node['name'])
        self.close()


class CustomHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        aqua_mint = '#4ec9b0'
        ocean_blue = '#569cd6'
        orchid_purple = '#c586c0'
        golden_beige = '#d7ba7d'

        self.white_format = QtGui.QTextCharFormat()
        self.white_format.setForeground(QtGui.QColor('#FFFFFF'))

        self.orchid_format = QtGui.QTextCharFormat(self.white_format)
        self.orchid_format.setForeground(QtGui.QColor(orchid_purple))

        self.goldenbeige_format = QtGui.QTextCharFormat(self.white_format)
        self.goldenbeige_format.setForeground(QtGui.QColor(golden_beige))

        self.oceanblue_format = QtGui.QTextCharFormat(self.white_format)
        self.oceanblue_format.setForeground(QtGui.QColor(ocean_blue))

        self.aquamint_format = QtGui.QTextCharFormat()
        self.aquamint_format.setForeground(QtGui.QColor(aqua_mint))

    def highlightBlock(self, text):
        patterns_format = [
            # (r'@\w+', self.function_format),
            (r'"[^"]*?"', self.aquamint_format),
            # (r'\{[^{}]*?}', self.curly_format),
        ]
        for pattern, format in patterns_format:
            for match in re.finditer(pattern, text):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, format)

        for i, char in enumerate(text):
            if char in '()':
                self.setFormat(i, 1, self.white_format)
            if char in '{}[]':
                self.setFormat(i, 1, self.orchid_format)
            if char == '"':
                self.setFormat(i, 1, self.goldenbeige_format)
            if char == ',':
                self.setFormat(i, 1, self.oceanblue_format)


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
