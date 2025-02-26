import polars as pl
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

from polarsgraph.nodes.base import convert_values, get_converter


FORMATS = [
    '',
    '%',
    'seconds to hours, minutes, seconds',
    'date: YYYY/MM/DD',
    'date: DD/MM/YYYY',
    'date: DD/MM/YY'
]


class COLORTYPE:
    NONE = 'No color'
    STEPS = 'Steps'
    MAP = 'Map/Gradient'


class DisplayRuleWidget(QtWidgets.QDialog):
    TYPES = COLORTYPE.NONE, COLORTYPE.STEPS, COLORTYPE.MAP

    def __init__(self, rules: dict = None, parent=None):
        super().__init__(parent=parent)

        self.setWindowTitle('Display rule')

        # Widgets
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(FORMATS)
        self.format_combo.setCurrentText(rules.get('format', ''))
        self.ruletype_combo = QtWidgets.QComboBox()
        self.ruletype_combo.addItems(self.TYPES)
        self.ruletype_combo.currentIndexChanged.connect(self.set_subwidget)
        self.step_widget = ColorStepsWidget(rules)
        self.map_widget = ColorMapWidget(rules)
        self.ok_button = QtWidgets.QPushButton('Ok')
        self.ok_button.released.connect(self.accept)

        # Layout
        format_layout = QtWidgets.QHBoxLayout()
        format_layout.addWidget(
            QtWidgets.QLabel('Value Format:', fixedWidth=100))
        format_layout.addWidget(self.format_combo)

        rule_layout = QtWidgets.QHBoxLayout()
        rule_layout.addWidget(
            QtWidgets.QLabel('Color Rule type:', fixedWidth=100))
        rule_layout.addWidget(self.ruletype_combo)

        colors_group = QtWidgets.QGroupBox('Colors')
        colors_layout = QtWidgets.QVBoxLayout(colors_group)
        colors_layout.addLayout(rule_layout)
        colors_layout.addWidget(self.step_widget)
        colors_layout.addWidget(self.map_widget)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(format_layout)
        layout.addSpacing(20)
        layout.addWidget(colors_group)
        layout.addWidget(self.ok_button)

        # Init
        try:
            i = self.TYPES.index(rules.get('type'))
        except ValueError:
            i = 0
        self.ruletype_combo.setCurrentIndex(i)
        self.set_subwidget()

    def set_subwidget(self):
        # Display step or map
        if self.ruletype_combo.currentText() == COLORTYPE.STEPS:
            self.step_widget.setVisible(True)
            self.step_widget.setEnabled(True)
            self.map_widget.setVisible(False)
        else:
            self.step_widget.setVisible(False)
            self.map_widget.setVisible(True)
            self.map_widget.setEnabled(True)
        # Disable
        if self.ruletype_combo.currentText() == COLORTYPE.NONE:
            self.step_widget.setEnabled(False)
            self.map_widget.setEnabled(False)

    def get_settings(self):
        # Get color rule
        if self.ruletype_combo.currentText() == COLORTYPE.NONE:
            settings = dict(type=COLORTYPE.NONE)
        elif self.ruletype_combo.currentText() == COLORTYPE.MAP:
            settings = self.map_widget.get_settings()
        else:
            settings = self.step_widget.get_settings()

        # Add format to settings
        format = self.format_combo.currentText()
        if format:
            settings['format'] = format
        elif 'format' in settings:
            del settings['format']

        return settings


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
        return dict(type=COLORTYPE.STEPS, values=values, colors=colors)


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
        colors = self.get_settings().get(COLORTYPE.MAP)
        if not colors:
            return self.color_result.setStyleSheet('')
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
            type=COLORTYPE.MAP,
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
    fg_df = None
    bg_df = df.clone()
    for column, data_type in schema.items():
        column_rules = rules.get(column)
        if not column_rules or column_rules.get('type') == COLORTYPE.NONE:
            if default_color:
                bg_df = bg_df.with_columns(
                    pl.lit(default_color).alias(column))
            else:
                bg_df = bg_df.with_columns(
                    pl.lit('').alias(column))
        elif column_rules.get('type') == COLORTYPE.MAP:
            bg_df = get_column_gradient_colors(
                bg_df, column, column_rules, data_type)
        elif column_rules.get('type') == COLORTYPE.STEPS:
            bg_df = get_column_step_colors(
                bg_df, column, column_rules, data_type)
    return bg_df, fg_df


def get_column_gradient_colors(
        df: pl.LazyFrame, column, column_rules, data_type):
    if not column_rules:
        return df
    colors_values = column_rules.get('map')
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
        expression = expression.otherwise(pl.lit(last_color))

    # Apply to df
    return df.with_columns(expression.name.keep())


def get_column_step_colors(
        df: pl.LazyFrame, column, column_rules, data_type):
    if not column_rules:
        return df
    colors = column_rules['colors']
    if not colors:
        return df
    if len(colors) == 1:
        color = column_rules['colors'][0]
        return df.with_columns(pl.lit(color).alias(column))
    values = convert_values(column_rules['values'], data_type)
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


def get_closest_value_index(value, values):
    min_delta = max(values) - min(values)
    for i, value2 in enumerate(values):
        delta = abs(value - value2)
        if delta == 0:
            return i
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
    for new_value in new_values:
        for i in range(len(colors_values)):
            value1, color1 = colors_values[i]
            value2, color2 = colors_values[i + 1]
            if new_value == value1:
                new_colors_values.append((new_value, color1))
                break
            if new_value < value1:
                continue
            if new_value > value2:
                continue
            ratio = (new_value - value1) / (value2 - value1)
            color = interpolate_between_two_colors(color1, color2, ratio)
            new_colors_values.append((new_value, color))
            break
    return new_colors_values


if __name__ == '__main__':
    colors_values = [(0, '#000000'), (4.0, '#404040')]
    expected = [
        (0, '#000000'), (1.0, '#101010'), (2.0, '#202020'), (4.0, '#404040')]
    assert extend_color_values_steps(colors_values, 4) == expected
