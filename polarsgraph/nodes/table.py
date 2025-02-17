from functools import partial

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, BaseDisplay, convert_values, get_converter)


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'
    COLUMNS_WIDTHS = 'columns_widths'
    DEFAULT_TEXT_COLOR = 'text_default_color'
    TEXT_COLOR_RULES = 'text_color_rules'
    DEFAULT_BACKGROUND_COLOR = 'default_background_color'
    BACKGROUND_COLOR_RULES = 'background_color_rules'


class TableNode(BaseNode):
    type = 'table'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables):
        self.tables['table'] = tables[0]
        # Update display
        if not self.display_widget:
            return
        self.display_widget.set_table(tables[0])

    def clear(self):
        self.display_widget.set_table(pl.LazyFrame())

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = TableDisplay(self)
        return self._display_widget


class TableSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.clipboard = {}

        # Widgets
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

        self.colors_table = QtWidgets.QTableWidget()
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

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addSpacing(20)
        layout.addWidget(QtWidgets.QLabel('Table colors:'))
        layout.addLayout(color_layout)
        layout.addWidget(self.colors_table)
        layout.addWidget(refresh_button)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
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
        del self.node.settings[ATTR.DEFAULT_BACKGROUND_COLOR]
        del self.node.settings[ATTR.DEFAULT_TEXT_COLOR]
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
        if not node[ATTR.BACKGROUND_COLOR_RULES]:
            node[ATTR.BACKGROUND_COLOR_RULES] = {}
        column_rules = node[ATTR.BACKGROUND_COLOR_RULES].get(column_name) or {}
        dialog = ColorRuleWidget(column_rules, parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        node[ATTR.BACKGROUND_COLOR_RULES][column_name].update(
            dialog.get_settings())
        self.emit_changed()

    def clear_column_colors(self, node, column_name):
        try:
            del node[ATTR.BACKGROUND_COLOR_RULES][column_name]
            self.emit_changed()
        except KeyError:
            pass

    def copy(self, node, column_name):
        try:
            self.clipboard = node.settings[
                ATTR.BACKGROUND_COLOR_RULES][column_name]
        except BaseException:
            self.clipboard = {}

    def paste(self, node, column_name):
        settings = node[ATTR.BACKGROUND_COLOR_RULES]
        if column_name not in settings:
            settings[column_name] = {}
        settings[column_name].update(self.clipboard)


class TableDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self._resizing = False
        self.node: BaseNode = node
        self.columns = None

        # Widgets
        self.table_view = QtWidgets.QTableView()
        self.table_view.setStyleSheet(TABLE_HANDLE_CSS)
        mode = QtWidgets.QHeaderView.ScrollPerPixel
        self.table_view.setVerticalScrollMode(mode)
        self.table_view.setHorizontalScrollMode(mode)
        self.table_view.horizontalHeader().sectionResized.connect(
            self.record_column_width)

        self.table_model = PolarsLazyFrameModel()
        self.table_view.setModel(self.table_model)

        self.table_details_label = QtWidgets.QLabel()
        resize_button = QtWidgets.QPushButton(
            '⇔ columns', clicked=self.table_view.resizeColumnsToContents)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditCopy)
        clipboard_image_button = QtWidgets.QPushButton(
            'image', icon=icon, clicked=self.image_to_clipboard)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentSave)
        save_image_button = QtWidgets.QPushButton(
            'image', icon=icon, clicked=self.save_image)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.EditCopy)
        clipboard_text_button = QtWidgets.QPushButton(
            'csv', icon=icon, clicked=self.csv_to_clipboard)
        icon = QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentSave)
        save_button = QtWidgets.QPushButton(
            'table', icon=icon, clicked=self.export_dataframe)

        # Layout
        self.bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout(self.bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.table_details_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(resize_button)
        bottom_layout.addWidget(clipboard_image_button)
        bottom_layout.addWidget(clipboard_text_button)
        bottom_layout.addWidget(save_image_button)
        bottom_layout.addWidget(save_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.table_view)
        layout.addWidget(self.bottom_widget)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            self.table_details_label.setText('')
            return self.table_model.set_dataframe(pl.DataFrame())

        # Table data
        table = table.collect(stream=True)
        self.table_model.set_dataframe(table)

        # Table color
        self.generate_colors(table)

        # Label
        self.table_details_label.setText(f'{table.height} x {table.width}')

        # Recover saved columns sizes (by column name):
        self.columns = table.schema.names()
        saved_sizes = self.node[ATTR.COLUMNS_WIDTHS] or {}
        for i, column_name in enumerate(self.columns):
            if column_name in saved_sizes:
                self.table_view.setColumnWidth(i, saved_sizes[column_name])

    def set_board_mode(self, board_enabled: bool):
        self.bottom_widget.setVisible(not board_enabled)

    def export_dataframe(self):
        if self.table_model.dataframe is None:
            return QtWidgets.QMessageBox.warning(
                self, 'Empty', 'No Table to export',
                QtWidgets.QMessageBox.Ok)
        prompt_save_df(self.table_model.dataframe, self)

    def get_pixmap(self):
        size = get_table_size(self.table_view)
        size.setHeight(size.height())
        pixmap = QtGui.QPixmap(size)
        self.table_view.render(pixmap)
        return pixmap

    def save_image(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save spreadsheet', '', '*.png')
        if not filepath:
            return
        self.get_pixmap().save(filepath)

    def image_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setPixmap(self.get_pixmap())

    def csv_to_clipboard(self):
        string = '\t'.join(self.table_model.dataframe.columns)
        for row in self.table_model.dataframe.to_dicts():
            string += '\n' + '\t'.join(str(v) for v in row.values())
        QtWidgets.QApplication.clipboard().setText(string)

    def record_column_width(self, column, oldWidth, newWidth):
        if not self.node[ATTR.COLUMNS_WIDTHS]:
            self.node[ATTR.COLUMNS_WIDTHS] = {}
        column_name = self.columns[column]
        self.node[ATTR.COLUMNS_WIDTHS][column_name] = newWidth

    def generate_colors(self, df: pl.DataFrame):
        # Text (Foreground) color
        color_df = generate_color_tables(
            df=df,
            default_color=self.node[ATTR.DEFAULT_TEXT_COLOR],
            rules=self.node[ATTR.TEXT_COLOR_RULES])
        self.table_model.set_dataframe(color_df, which='text_color')
        # Background color
        color_df = generate_color_tables(
            df=df,
            default_color=self.node[ATTR.DEFAULT_BACKGROUND_COLOR],
            rules=self.node[ATTR.BACKGROUND_COLOR_RULES])
        self.table_model.set_dataframe(color_df, which='bg_color')


class PolarsLazyFrameModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataframe = pl.DataFrame()
        self.bg_colors_df: pl.DataFrame = None
        self.text_colors_df: pl.DataFrame = None

    def set_dataframe(self, dataframe: pl.DataFrame, which='main'):
        self.layoutAboutToBeChanged.emit()
        if which == 'main':
            self.dataframe = dataframe
        elif which == 'bg_color':
            self.bg_colors_df = dataframe
        elif which == 'text_color':
            self.text_colors_df = dataframe
        else:
            raise ValueError(f'Bad "which" argument value "{which}"')
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Vertical:
                return str(section + 1)
            if orientation == Qt.Horizontal:
                return self.dataframe.columns[section]
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

    def rowCount(self, *_):
        return self.dataframe.height

    def columnCount(self, *_):
        return self.dataframe.width

    def data(self, index, role):
        if not index.isValid():
            return

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        row, col = index.row(), index.column()

        if role == Qt.DisplayRole:
            value = self.dataframe[row, col]
            if value is None:
                return ''
            return str(value)

        if self.bg_colors_df is not None and role == Qt.BackgroundRole:
            color = self.bg_colors_df[row, col]
            if color:
                return QtGui.QColor(color)
        elif self.text_colors_df is not None and role == Qt.ForegroundRole:
            color = self.text_colors_df[row, col]
            if color:
                return QtGui.QColor(color)


class ColorRuleWidget(QtWidgets.QDialog):
    def __init__(self, rules: dict = None, parent=None):
        super().__init__(parent=parent)

        self.setWindowTitle('Color rule')

        self.step_widget = ColorStepsWidget(rules)
        self.map_widget = ColorMapWidget(rules)
        self.ok_button = QtWidgets.QPushButton('Ok')
        self.ok_button.released.connect(self.accept)

        self.tab = QtWidgets.QTabWidget()
        self.tab.addTab(self.step_widget, 'Steps')
        self.tab.addTab(self.map_widget, 'Map/Gradient')
        if rules.get('type') == 'map':
            self.tab.setCurrentIndex(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.tab)
        layout.addWidget(self.ok_button)

    def get_settings(self):
        if self.tab.currentIndex():
            return self.map_widget.get_settings()
        else:
            return self.step_widget.get_settings()


class ColorStepsWidget(QtWidgets.QWidget):

    def __init__(self, rules=None, parent=None):
        super().__init__(parent=parent)

        colors = rules.get('colors')
        values = rules.get('values')

        # Widgets
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(1)
        self.table.horizontalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.edit_color)

        self.color_result = QtWidgets.QPushButton()

        self.add_color_btn = QtWidgets.QPushButton('Add Color')
        self.add_color_btn.clicked.connect(self.add_color)
        self.remove_color_btn = QtWidgets.QPushButton('Remove selected')
        self.remove_color_btn.clicked.connect(self.remove_row)

        # Layout
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.add_color_btn)
        button_layout.addWidget(self.remove_color_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.color_result)
        layout.addLayout(button_layout)

        # Init
        if not colors:
            return
        assert len(values) == len(colors) - 1
        i = 0
        for i in range(len(values)):
            self._add_color(QtGui.QColor(colors[i]))
            self._add_value(values[i])
        try:
            self._add_color(QtGui.QColor(colors[i + 1]))
        except IndexError:
            pass
        self.set_color_info()

    def _add_value(self, value=None):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        value_item = QtWidgets.QTableWidgetItem()
        if value:
            value_item.setText(value)
        self.table.setItem(row_index, 0, value_item)

    def _add_color(self, color: QtGui.QColor):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        color_item = QtWidgets.QTableWidgetItem()
        color_item.setFlags(color_item.flags() ^ Qt.ItemIsEditable)
        color_item.setBackground(color)
        color_item.setText(color.name().upper())
        self.table.setItem(row_index, 0, color_item)

    def set_color_info(self):
        self.color_result.setStyleSheet(
            colors_to_css_gradient_step(self.get_settings()['colors']))

    def add_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        if self.table.rowCount():
            self._add_value()
        self._add_color(color)
        self.set_color_info()

    def remove_row(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return QtWidgets.QMessageBox.warning(
                self, 'No Selection', 'Please select a color to remove.')
        self.table.removeRow(selected_row)
        if selected_row % 2:
            self.table.removeRow(selected_row)
        else:
            self.table.removeRow(selected_row - 1)

    def edit_color(self, row_index, _):
        if row_index % 2:
            return
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.table.item(row_index, 0).setBackground(color)
            self.table.item(row_index, 0).setText(color.name())
        self.set_color_info()

    def get_settings(self):
        values = []
        colors = []
        for row_index in range(self.table.rowCount()):
            if row_index % 2:
                values.append(self.table.item(row_index, 0).text())
            else:
                colors.append(self.table.item(row_index, 0).text())
        return dict(type='step', values=values, colors=colors)


class ColorMapWidget(QtWidgets.QWidget):
    def __init__(self, rules: dict = None, parent=None):
        super().__init__(parent=parent)

        # Widgets
        self.gradient_cb = QtWidgets.QCheckBox('Gradient')
        self.gradient_cb.setChecked(rules.get('gradient', True))

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(2)
        self.table.horizontalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.edit_color)

        self.color_result = QtWidgets.QPushButton()

        self.add_color_btn = QtWidgets.QPushButton('Add Color')
        self.add_color_btn.clicked.connect(self.add_row)
        self.remove_color_btn = QtWidgets.QPushButton('Remove selected')
        self.remove_color_btn.clicked.connect(self.remove_row)

        # Layout
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.add_color_btn)
        button_layout.addWidget(self.remove_color_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.gradient_cb)
        layout.addWidget(self.table)
        layout.addWidget(self.color_result)
        layout.addLayout(button_layout)

        # Init
        for value, color in rules.get('map', []):
            self._add_row(value, QtGui.QColor(color))
        self.set_color_info()

    def _add_row(self, value, color: QtGui.QColor):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        # Value
        value_item = QtWidgets.QTableWidgetItem()
        value_item.setText(str(value))
        self.table.setItem(row_index, 0, value_item)
        # Color
        color_item = QtWidgets.QTableWidgetItem()
        color_item.setFlags(color_item.flags() ^ Qt.ItemIsEditable)
        color_item.setBackground(color)
        color_item.setText(color.name().upper())
        self.table.setItem(row_index, 1, color_item)

    def set_color_info(self):
        colors = self.get_settings().get('map')
        colors = [_[1] for _ in colors]
        self.color_result.setStyleSheet(colors_to_css_gradient(colors))

    def add_row(self):
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        self._add_row(0, color)
        self.set_color_info()

    def remove_row(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return QtWidgets.QMessageBox.warning(
                self, 'No Selection', 'Please select a color to remove.')
        self.table.removeRow(selected_row)
        if selected_row % 2:
            self.table.removeRow(selected_row)
        else:
            self.table.removeRow(selected_row - 1)

    def edit_color(self, row_index, column_index):
        if column_index != 1:
            return
        if row_index % 2:
            return
        color = QtWidgets.QColorDialog.getColor()
        # et puis c'est parti.
        if color.isValid():
            self.table.item(row_index, 0).setBackground(color)
            self.table.item(row_index, 0).setText(color.name())
        self.set_color_info()

    def get_settings(self):
        map = []
        for row_index in range(self.table.rowCount()):
            value = self.table.item(row_index, 0)
            value = value.text() if value else ''
            color = self.table.item(row_index, 1).text()
            map.append((value, color))
        return dict(
            type='map',
            gradient=self.gradient_cb.isChecked(),
            map=map)


def colors_to_css_gradient_step(colors: list[str]):
    stops = ''
    for i, color in enumerate(colors):
        p1 = (i) / len(colors)
        p2 = (i + 1) / len(colors) - 0.01
        stops += f', stop: {p1} {color}'
        stops += f', stop: {p2} {color}'
    return f'background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0{stops});'


def colors_to_css_gradient(colors: list[str]):
    stops = ''
    for i, color in enumerate(colors):
        try:
            ratio = i / (len(colors) - 1)
        except ZeroDivisionError:
            ratio = 1
        stops += f', stop: {ratio} {color}'
    return f'background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0{stops});'


def generate_color_tables(
        df: pl.DataFrame,
        rules: dict,
        default_color):
    rules = rules or {}
    schema = df.collect_schema()
    for column, data_type in schema.items():
        column_rules = rules.get(column)
        if not column_rules:
            df = df.with_columns(
                pl.lit(default_color).alias(column))
        elif column_rules.get('type') == 'map':
            df = get_column_gradient_colors(
                df, column, column_rules, data_type)
        else:
            df = get_column_step_colors(
                df, column, column_rules, data_type)
    return df


def get_column_gradient_colors(
        df: pl.LazyFrame, column, column_rules, data_type):
    if not column_rules:
        return df
    colors_values = column_rules['map']
    if not colors_values:
        return df

    # Convert values
    converter = get_converter(data_type)
    colors_values = [(converter(v), c) for v, c in colors_values]

    # Choose between == and >=
    col_exp = pl.col(column)
    if column_rules.get('gradient'):
        col_method = getattr(col_exp, '__le__')
        colors_values = extend_color_values_steps(colors_values)
    else:
        col_method = getattr(col_exp, '__eq__')

    # Start expression
    value, color = colors_values[0]
    expression = pl.when(col_method(value)).then(pl.lit(color))

    # Loop through rest of values
    if len(colors_values) > 1:
        for value, color in colors_values[1:]:
            expression = expression.when(col_method(value)).then(pl.lit(color))

    # If gradient, end with last color
    if column_rules.get('gradient'):
        last_color = colors_values[-1][1]
        expression = expression.otherwise(pl.lit(last_color)).name.keep()

    # Apply to df
    return df.with_columns(expression)


def extend_color_values_steps(colors_values, target_count=64):
    """
    Add values/colors couple to make an almost-gradient
    """
    current_count = len(colors_values)
    if current_count >= target_count:
        return colors_values
    # Create new list of values
    values = [_[0] for _ in colors_values]
    min_val, max_val = min(values), max(values)
    step = (max_val - min_val) / target_count
    new_values = [min_val + step * i for i in range(target_count)]
    # Make sure original values are part of the list
    for value in values:
        new_values[get_closest_value_index(value, new_values)] = value
    # Create new value/color pairs
    new_colors_values = []
    for value in new_values:
        for i, (source_value, color) in enumerate(colors_values):
            if value == source_value:
                new_colors_values.append((value, color))
            elif value > source_value:
                value1, color1 = colors_values[i]
                value2, color2 = colors_values[i + 1]
                ratio = (value - value1) / (value2 - value1)
                color = interpolate_between_two_colors(color1, color2, ratio)
                new_colors_values.append((value, color))
    return new_colors_values


def get_closest_value_index(value, values):
    min_delta = max(values)
    for i, value2 in enumerate(values):
        delta = abs(value - value2)
        if delta < min_delta:
            min_delta = delta
            found_index = i
    return found_index


def webcolor_to_ints(c):
    c = c[1:]  # remove "#"
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def interpolate_between_two_colors(color1, color2, ratio=0.5):
    color1 = webcolor_to_ints(color1)
    color2 = webcolor_to_ints(color2)
    r, g, b = [int(a + (b - a) * ratio) for a, b in zip(color1, color2)]
    return f'#{r:02X}{g:02X}{b:02X}'


def get_column_step_colors(
        df: pl.LazyFrame, column, column_rules, data_type):
    if len(column_rules['colors']) == 1:
        color = column_rules['colors'][0]
        return df.with_columns(pl.lit(color).alias(column))
    values = convert_values(column_rules['values'], data_type)
    colors = column_rules['colors']
    assert len(values) == len(colors) - 1
    col_exp = pl.col(column)

    # Chain conditions
    """
    color_df = df.with_columns(
        pl.when(pl.col("foo") > 2)
        .then(1)
        .when(pl.col("bar") > 2)
        .then(4)
        .otherwise(-1)
        .alias("val")
    )
    """
    assert values == sorted(values)
    values = values[::-1]  # dont reverse in-place
    colors = colors[::-1]
    expression = pl.when(
        col_exp > values[0]).then(pl.lit(colors[0]))
    for i, value in enumerate(values):
        expression = expression.when(col_exp > value).then(
            pl.lit(colors[i]))
    expression = expression.otherwise(pl.lit(colors[-1])).name.keep()

    # Apply to df
    return df.with_columns(expression)


def export_df_to_file(df: pl.DataFrame, path: str):
    if isinstance(df, pl.LazyFrame):
        df = df.collect()
    logger.debug(path)
    QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        if path.endswith('xlsx'):
            for col, dtype in zip(df.columns, df.dtypes):
                if dtype == pl.String:
                    df = df.with_columns(pl.col(col).str.replace('false', ''))
            df.write_excel(path)
        elif path.endswith('parquet'):
            df.write_parquet(path)
        elif path.endswith('pickle'):
            import pickle
            with open(path, 'wb') as f:
                pickle.dump(df, f)
        else:
            raise ValueError(f'Extension not covered ({path})')
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


def prompt_save_df(df, parent=None):
    filepath, result = QtWidgets.QFileDialog.getSaveFileName(
        parent, 'Export', filter='(*.xlsx *.parquet, *.pickle)')
    if not result:
        return
    export_df_to_file(df, filepath)


def get_table_size(table: QtWidgets.QTableView):
    """
    table.size() includes blank space.
    Use position of last cell + its size + header
    """
    # height
    last_row = table.model().rowCount() - 1
    height = (
        table.rowViewportPosition(last_row) +
        table.rowHeight(last_row) +
        table.horizontalHeader().height())

    # width
    last_col = table.model().columnCount() - 1
    width = (
        table.columnViewportPosition(last_col) +
        table.columnWidth(last_col) +
        table.verticalHeader().width())

    width = min(table.width(), width)
    height = min(table.height(), height)

    return QtCore.QSize(width, height)


def fit_columns_to_headers(table: QtWidgets.QTableView):
    header = table.horizontalHeader()
    for column in range(header.count()):
        header_width = header.sectionSizeHint(column)
        table.setColumnWidth(column, header_width)
