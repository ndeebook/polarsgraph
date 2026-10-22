import polars as pl
from PySide6 import QtGui, QtCore, QtWidgets


def set_shortcut(keysequence, parent, method, context=None):
    shortcut = QtGui.QShortcut(QtGui.QKeySequence(keysequence), parent)
    shortcut.setContext(context or QtCore.Qt.WidgetWithChildrenShortcut)
    shortcut.activated.connect(method)
    return shortcut


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
        extra_values=None,
        sort=True):
    try:
        values = df.collect_schema().names()
    except AttributeError:
        values = []
    for extra_value in extra_values or []:
        if extra_value not in values:
            values.insert(0, extra_value)
    if sort:
        values.sort()
    set_combo_values(combo, values, current_text)
