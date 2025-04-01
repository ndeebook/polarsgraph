from functools import partial

import polars as pl
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, get_format_exp)
from polarsgraph.nodes.format.colors import (
    DisplayRuleWidget, generate_color_columns)


class ATTR:
    NAME = 'name'
    COLUMN_FORMATS = 'formats'
    ALL_COLUMNS_AS_STRING = 'convert_all_columns_to_string'
    DEFAULT_TEXT_COLOR = 'text_default_color'
    DEFAULT_BACKGROUND_COLOR = 'default_background_color'
    DISPLAY_RULES = 'display_rules'


class FormatNode(BaseNode):
    type = 'format'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        # 1. Generate color columns
        df = generate_color_columns(
            df=df,
            default_color=self[ATTR.DEFAULT_BACKGROUND_COLOR],
            rules=self[ATTR.DISPLAY_RULES])

        # 2. Apply formats to columns
        all_to_string = self[ATTR.ALL_COLUMNS_AS_STRING] in (None, True)
        column_rules = self[ATTR.DISPLAY_RULES] or {}
        for col_name in df.collect_schema():
            rule = column_rules.get(col_name, {})
            col = pl.col(col_name)
            fmt = rule.get('format')
            exp = get_format_exp(col, fmt)
            if all_to_string and fmt != 'string':
                exp = exp.cast(pl.String)
            df = df.with_columns(exp)

        self.tables['table'] = df


class FormatSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        # Widgets
        self.all_as_string_cb = QtWidgets.QCheckBox(
            'Convert all columns to string')
        self.all_as_string_cb.checkStateChanged.connect(
            lambda: self.checkbox_to_settings(
                self.all_as_string_cb, ATTR.ALL_COLUMNS_AS_STRING))
        self.color_label = QtWidgets.QLabel(
            'Default Colors:', alignment=Qt.AlignmentFlag.AlignCenter)
        self.bg_color_button = QtWidgets.QPushButton('BG Color')
        self.bg_color_button.clicked.connect(
            lambda: self.choose_default_color(ATTR.DEFAULT_BACKGROUND_COLOR))
        self.text_color_button = QtWidgets.QPushButton('FG Color')
        self.text_color_button.clicked.connect(
            lambda: self.choose_default_color(ATTR.DEFAULT_TEXT_COLOR))
        self.reset_button = QtWidgets.QPushButton('Reset', fixedWidth=48)
        self.reset_button.clicked.connect(self.reset_default_colors)

        self.colors_table = QtWidgets.QTableWidget(minimumHeight=400)
        self.colors_table.setColumnCount(5)
        self.colors_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self.colors_table.setHorizontalHeaderLabels(
            ['Column', '', '', '', ''])

        refresh_button = QtWidgets.QPushButton('Refresh columns list')
        refresh_button.clicked.connect(self.populate_format_table)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)

        color_layout = QtWidgets.QHBoxLayout()
        color_layout.addWidget(self.color_label)
        color_layout.addWidget(self.bg_color_button)
        color_layout.addWidget(self.text_color_button)
        color_layout.addWidget(self.reset_button)

        display_group = QtWidgets.QGroupBox('Display')
        display_layout = QtWidgets.QVBoxLayout(display_group)
        display_layout.addLayout(color_layout)
        display_layout.addWidget(self.colors_table)
        display_layout.addWidget(refresh_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addSpacing(32)
        layout.addWidget(self.all_as_string_cb)
        layout.addWidget(display_group)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node

        self.name_edit.setText(node[ATTR.NAME])
        self.all_as_string_cb.setChecked(
            True if node[ATTR.ALL_COLUMNS_AS_STRING] in (None, True)
            else False)

        self.input_table: pl.LazyFrame = input_tables[0]

        self.set_label_color_from_settings()
        self.populate_format_table()

        self.blockSignals(False)

    def get_default_color(self, which='bg'):
        if which == 'bg':
            return self.node[ATTR.DEFAULT_TEXT_COLOR] or '#FFFFFF'
        else:
            return self.node[ATTR.DEFAULT_BACKGROUND_COLOR] or '#000000'

    def choose_default_color(self, attribute):
        bg_color = self.get_default_color('bg')
        text_color = self.get_default_color('text')
        start_color = (
            text_color if attribute == ATTR.DEFAULT_TEXT_COLOR else bg_color)
        color = QtWidgets.QColorDialog.getColor(
            initial=QtGui.QColor(start_color))
        if not color.isValid():
            return
        self.node[attribute] = color.name()
        self.set_label_color_from_settings()
        self.emit_changed()

    def reset_default_colors(self):
        try:
            del self.node.settings[ATTR.DEFAULT_BACKGROUND_COLOR]
        except KeyError:
            pass
        try:
            del self.node.settings[ATTR.DEFAULT_TEXT_COLOR]
        except KeyError:
            pass
        self.set_label_color_from_settings()
        self.emit_changed()

    def set_label_color_from_settings(self):
        self.color_label.setStyleSheet(
            f'background-color: {self.get_default_color("bg")};'
            f'color: {self.get_default_color("text")}')

    def populate_format_table(self):
        if self.input_table is None:
            columns = []
        else:
            columns = self.input_table.collect_schema().names()
        self.colors_table.blockSignals(True)
        self.colors_table.setRowCount(len(columns))

        for i, column in enumerate(columns):
            # Add column name
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(Qt.ItemIsEnabled)
            self.colors_table.setItem(i, 0, column_item)

            # Add buttons: config, clear, copy, paste
            icon = QtGui.QIcon.fromTheme(
                QtGui.QIcon.ThemeIcon.DocumentProperties)
            configure_btn = QtWidgets.QPushButton(
                '', fixedWidth=32, icon=icon)
            configure_btn.clicked.connect(
                partial(self.configure_column_colors, self.node, column))
            self.colors_table.setCellWidget(i, 1, configure_btn)

            icon = QtGui.QIcon.fromTheme(
                QtGui.QIcon.ThemeIcon.EditDelete)
            clear_btn = QtWidgets.QPushButton('', fixedWidth=32, icon=icon)
            clear_btn.clicked.connect(
                partial(self.clear_column_colors, self.node, column))
            self.colors_table.setCellWidget(i, 2, clear_btn)

            icon = QtGui.QIcon.fromTheme(
                QtGui.QIcon.ThemeIcon.EditCopy)
            copy_btn = QtWidgets.QPushButton('', fixedWidth=32, icon=icon)
            copy_btn.clicked.connect(
                partial(self.copy, self.node, column))
            self.colors_table.setCellWidget(i, 3, copy_btn)

            icon = QtGui.QIcon.fromTheme(
                QtGui.QIcon.ThemeIcon.EditPaste)
            paste_btn = QtWidgets.QPushButton('', fixedWidth=32, icon=icon)
            paste_btn.clicked.connect(
                partial(self.paste, self.node, column))
            self.colors_table.setCellWidget(i, 4, paste_btn)

    def configure_column_colors(self, node, column_name):
        if not node[ATTR.DISPLAY_RULES]:
            node[ATTR.DISPLAY_RULES] = {}
        column_rules = node[ATTR.DISPLAY_RULES].get(column_name) or {}
        dialog = DisplayRuleWidget(column_rules, parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        if not node[ATTR.DISPLAY_RULES].get(column_name):
            node[ATTR.DISPLAY_RULES][column_name] = {}
        node[ATTR.DISPLAY_RULES][column_name].update(
            dialog.get_settings())
        self.emit_changed()

    def clear_column_colors(self, node, column_name):
        try:
            del node[ATTR.DISPLAY_RULES][column_name]
            self.emit_changed()
        except KeyError:
            pass

    def copy(self, node, column_name):
        try:
            self.clipboard = node.settings[
                ATTR.DISPLAY_RULES][column_name]
        except BaseException:
            self.clipboard = {}

    def paste(self, node, column_name):
        settings = node[ATTR.DISPLAY_RULES]
        if column_name not in settings:
            settings[column_name] = {}
        settings[column_name].update(self.clipboard)
        self.emit_changed()

    def _handle_format_change(self, column):
        formats = {}
        for row in range(self.column_format_table.rowCount()):
            column_item = self.column_format_table.item(row, 0)
            if not column_item:
                continue
            col_name = column_item.text()
            format_combo = self.column_format_table.cellWidget(row, 1)
            if format_combo:
                formats[col_name] = format_combo.currentText()

        self.node[ATTR.COLUMN_FORMATS] = formats
        self.emit_changed()
