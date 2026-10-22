from datetime import date as Date, datetime as DT

import polars as pl
from PySide6 import QtCore, QtWidgets, QtGui


from polarsgraph.graph import BaseNode
# Re-export for backwards compat — these moved to polarsgraph.qtutils.
from polarsgraph.qtutils import (  # noqa: F401
    set_combo_values, set_combo_values_from_table_columns)


TRUE_WORDS = '1', 'true', 'yes'
DISPLAY_INDEX_ATTR = 'display_index'


class FORMAT:
    DEFAULT = ''
    PERCENT = '%'
    YYYYMMDD = 'date: YYYY/MM/DD'
    DDMMYYYY = 'date: DD/MM/YYYY'
    DDMMYY = 'date: DD/MM/YY'
    S_TO_HMS = 'seconds to hours, minutes, seconds'
    SECONDS = 'seconds'


FORMATS = [v for k, v in FORMAT.__dict__.items() if not k.startswith('_')]


class BaseSettingsWidget(QtWidgets.QWidget):
    settings_changed = QtCore.Signal(str)
    rename_asked = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()

        self.node: BaseNode = None
        self.name_edit = QtWidgets.QLineEdit()
        regex = QtCore.QRegularExpression(r"[A-Za-zÀ-ÖØ-öø-ÿ _-]*")
        validator = QtGui.QRegularExpressionValidator(regex)
        self.name_edit.setValidator(validator)
        self.name_edit.editingFinished.connect(self.rename)
        self.needs_built_query = True
        self._attrs: list = []

    def set_node(self, node, input_tables):
        raise NotImplementedError

    def build_attr_form(self, attrs, form_layout=None):
        """
        Add a Name row + one row per declarative attr, wire signals.
        Returns the form layout so the caller can place it.
        """
        if form_layout is None:
            form_layout = QtWidgets.QFormLayout()
        form_layout.addRow('Name', self.name_edit)
        for attr in attrs:
            label, widget = self.register_attr(attr)
            form_layout.addRow(label, widget)
        return form_layout

    def register_attr(self, attr):
        """
        Build an attr's widget, register it for load_attrs, return
        (label, widget) so the caller can place the widget manually.
        """
        label, widget = attr.build(self)
        self._attrs.append(attr)
        return label, widget

    def load_attrs(self, node, input_tables):
        """Populate name_edit + every registered attr widget from `node`."""
        self.name_edit.setText(node['name'])
        for attr in self._attrs:
            attr.load(self, node, input_tables)

    def rename(self):
        self.rename_asked.emit(self.node['name'], self.name_edit.text())
        self.emit_changed(make_dirty=False)

    def emit_changed(self, make_dirty=True):
        if make_dirty:
            self.node.dirty = True
        self.settings_changed.emit(self.node['name'])

    def line_edit_to_settings(
            self,
            line_edit: QtWidgets.QLineEdit | QtWidgets.QPlainTextEdit,
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

    def checkbox_to_settings(
            self,
            checkbox: QtWidgets.QCheckBox,
            attribute_name):
        self.node[attribute_name] = checkbox.isChecked()
        self.emit_changed()


class BaseDisplay(QtWidgets.QWidget):
    shown = QtCore.Signal()
    action_requested = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def set_board_mode(self, board_enabled: bool):
        pass

    def showEvent(self, event):
        self.shown.emit()
        return super().showEvent(event)


def to_boolean(value):
    if value in (True, False):
        return value
    if not value:
        return False
    if isinstance(value, str):
        return value.lower() in TRUE_WORDS
    return False


def get_converter(data_type: pl.DataType):
    if data_type.is_float():
        return lambda v: float(v.replace(',', '.'))
    elif data_type.is_integer():
        return int
    elif data_type == pl.Boolean:
        return to_boolean
    elif data_type == pl.Date:
        return Date.fromisoformat
    elif data_type == pl.Datetime:
        return DT.fromisoformat
    elif data_type == pl.String:
        return str
    raise ValueError(f'No converter available for data type {data_type}')


def convert_value(value, data_type):
    if value in (None, 'null'):
        return
    converter = get_converter(data_type)
    if converter is None:
        return value
    return converter(value)


def convert_values(values, data_type):
    converter = get_converter(data_type)
    if converter is None:
        return values
    return [converter(v) for v in values]


def get_format_exp(col: pl.Expr, fmt: str):
    # %
    if not fmt:
        return col
    if fmt == FORMAT.PERCENT:
        return (col * 100).round(2).cast(pl.String) + '%'
    # Dates
    if fmt == FORMAT.YYYYMMDD:
        return col.dt.strftime("%Y/%m/%d")
    if fmt == FORMAT.DDMMYYYY:
        return col.dt.strftime("%d/%m/%Y")
    if fmt == FORMAT.DDMMYY:
        return col.dt.strftime("%d/%m/%y")
    # Time
    if fmt == FORMAT.S_TO_HMS:
        return col.map_elements(format_duration, return_dtype=pl.String)
    if fmt == FORMAT.SECONDS:
        return col.cast(pl.String) + 's'
    if fmt == 'string':
        return col.cast(pl.String)
    raise ValueError(f'Unknown format "{fmt}"')


def format_duration(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return '%ih %02dm %02ds' % (hours, minutes, seconds)
    elif minutes:
        return '%im %02ds' % (minutes, seconds)
    else:
        return '%i seconds' % seconds
