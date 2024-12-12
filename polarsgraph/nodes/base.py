import polars as pl
from PySide6 import QtCore, QtWidgets


from polarsgraph.graph import BaseNode


TRUE_WORDS = '1', 'true', 'yes'


class BaseSettingsWidget(QtWidgets.QWidget):
    settings_changed = QtCore.Signal(str)
    rename_asked = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()

        self.node: BaseNode = None
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(self.rename)
        self.needs_built_query = True

    def set_node(self, node, input_tables):
        raise NotImplementedError

    def rename(self):
        self.rename_asked.emit(self.node['name'], self.name_edit.text())
        self.emit_changed(make_dirty=False)

    def emit_changed(self, make_dirty=True):
        if make_dirty:
            self.node.dirty = True
        self.settings_changed.emit(self.node['name'])

    def line_edit_to_settings(
            self,
            line_edit: QtWidgets.QLineEdit,
            attribute_name,
            data_type=str):
        try:
            text = line_edit.text()
        except AttributeError:
            text = line_edit.toPlainText()  # cover QPlainTextEdit as well
        if not text:
            self.node[attribute_name] = None
        else:
            try:
                self.node[attribute_name] = data_type(text)
            except ValueError:
                self.node[attribute_name] = None
        self.emit_changed()

    def spinbox_to_settings(
            self,
            spinbox: QtWidgets.QSpinBox,
            attribute_name,
            data_type=int):
        self.node[attribute_name] = data_type(spinbox.value())
        self.emit_changed()

    def combobox_to_settings(
            self,
            combobox: QtWidgets.QComboBox,
            attribute_name,
            data_type=str,
            mapper=None):
        text = combobox.currentText()
        if mapper:
            text = mapper[text]
        self.node[attribute_name] = data_type(text)
        self.emit_changed()


class BaseDisplay(QtWidgets.QWidget):
    shown = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def set_board_mode(self, board_enabled: bool):
        pass

    def showEvent(self, event):
        self.shown.emit()
        return super().showEvent(event)


def set_combo_values(
        combo: QtWidgets.QComboBox,
        values: list[str],
        current_text: str):
    combo.clear()
    if current_text not in values:
        values = [current_text, *values]
    combo.addItems(values)
    combo.setCurrentText(current_text)


def set_combo_values_from_table_columns(
        combo: QtWidgets.QComboBox,
        df: pl.LazyFrame,
        current_text: str,
        extra_values=None):
    values = df.collect_schema().names()
    if extra_values:
        extra_values = list(set(extra_values) - set(values))
        if extra_values:
            combo.addItems(extra_values)
    set_combo_values(combo, values, current_text)


def get_converter(data_type: pl.DataType):
    if data_type.is_float():
        return lambda v: float(v.replace(',', '.'))
    elif data_type.is_integer():
        return int
    elif data_type == pl.Boolean:
        return lambda v: True if v.lower() in TRUE_WORDS else False


def convert_value(value, data_type):
    converter = get_converter(data_type)
    if converter is None:
        return value
    return converter(value)


def convert_values(values, data_type):
    converter = get_converter(data_type)
    if converter is None:
        return values
    return [converter(v) for v in values]
