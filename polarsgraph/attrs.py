"""
Declarative attribute system for nodes.

Each node declares its editable settings as `attrs = [Attr(...), ...]` on the
node class. The framework uses that list to:
    - apply default values at node construction (BaseNode.__init__)
    - build the settings widget's form rows and wire signals
      (BaseSettingsWidget.build_attr_form)
    - populate the widgets in set_node (BaseSettingsWidget.load_attrs)

The escape hatch is `CompoundAttr`: a subclass that owns more than one
settings key and provides its own widget + load/write logic. Use it when a
single key→widget mapping doesn't fit (e.g. a sort spec that pairs columns
and orders).
"""
from PySide6 import QtGui, QtWidgets

from polarsgraph.qtutils import set_combo_values_from_table_columns


class Attr:
    """Single-key, single-widget attribute spec."""

    def __init__(self, key, default=None, label=None):
        self.key = key
        self.default = default
        self.label = label if label is not None else key.title()
        self.keys = (key,)
        self.widget: QtWidgets.QWidget = None

    def apply_default(self, settings):
        if settings.get(self.key) is None and self.default is not None:
            settings[self.key] = self.default

    def build(self, settings_widget):
        self.widget = self._make_widget(settings_widget)
        self._connect(settings_widget)
        return self.label, self.widget

    def _make_widget(self, settings_widget):
        raise NotImplementedError

    def _connect(self, settings_widget):
        raise NotImplementedError

    def load(self, settings_widget, node, input_tables):
        raise NotImplementedError


class StrAttr(Attr):
    def __init__(self, key, default=None, label=None, placeholder=None):
        super().__init__(key, default=default, label=label)
        self.placeholder = placeholder

    def _make_widget(self, _):
        w = QtWidgets.QLineEdit()
        if self.placeholder:
            w.setPlaceholderText(self.placeholder)
        return w

    def _connect(self, sw):
        self.widget.editingFinished.connect(
            lambda: sw.line_edit_to_settings(self.widget, self.key))

    def load(self, _sw, node, _tables):
        self.widget.setText(node[self.key] or self.default or '')


class TextAttr(Attr):
    """Multi-line text — QPlainTextEdit."""

    def __init__(self, key, default=None, label=None, placeholder=None):
        super().__init__(key, default=default, label=label)
        self.placeholder = placeholder

    def _make_widget(self, _):
        w = QtWidgets.QPlainTextEdit()
        if self.placeholder:
            w.setPlaceholderText(self.placeholder)
        return w

    def _connect(self, sw):
        self.widget.textChanged.connect(
            lambda: sw.line_edit_to_settings(self.widget, self.key))

    def load(self, _sw, node, _tables):
        self.widget.setPlainText(node[self.key] or '')


class IntAttr(Attr):
    def __init__(
            self, key, default=None, label=None,
            minimum=None, maximum=None):
        super().__init__(key, default=default, label=label)
        self.minimum = minimum
        self.maximum = maximum

    def _make_widget(self, _):
        w = QtWidgets.QSpinBox()
        if self.minimum is not None:
            w.setMinimum(self.minimum)
        if self.maximum is not None:
            w.setMaximum(self.maximum)
        return w

    def _connect(self, sw):
        self.widget.valueChanged.connect(
            lambda: sw.spinbox_to_settings(self.widget, self.key))

    def load(self, _sw, node, _tables):
        value = node[self.key]
        if value is None:
            value = self.default if self.default is not None else 0
        self.widget.setValue(int(value))


class ColorAttr(Attr):
    """Button that opens a QColorDialog; stores the QColor on the node."""

    def __init__(self, key, default=None, label=None, button_text='Color'):
        super().__init__(key, default=default, label=label)
        self.button_text = button_text

    def _make_widget(self, _):
        w = QtWidgets.QPushButton(self.button_text)
        return w

    def _connect(self, sw):
        self.widget.clicked.connect(lambda: self._pick(sw))

    def _pick(self, sw):
        current = sw.node[self.key]
        initial = QtGui.QColor(current) if current else QtGui.QColor()
        color = QtWidgets.QColorDialog.getColor(initial)
        if not color.isValid():
            return
        sw.node[self.key] = color
        sw.emit_changed()

    def load(self, _sw, _node, _tables):
        pass  # the color is read on demand from the node when picking


class BoolAttr(Attr):
    def _make_widget(self, _):
        return QtWidgets.QCheckBox()

    def _connect(self, sw):
        self.widget.stateChanged.connect(
            lambda: sw.checkbox_to_settings(self.widget, self.key))

    def load(self, _sw, node, _tables):
        self.widget.setChecked(bool(node[self.key]))


class ChoiceAttr(Attr):
    def __init__(self, key, options, default=None, label=None):
        super().__init__(key, default=default or options[0], label=label)
        self.options = options

    def _make_widget(self, _):
        w = QtWidgets.QComboBox()
        w.addItems(self.options)
        return w

    def _connect(self, sw):
        self.widget.currentTextChanged.connect(
            lambda: sw.combobox_to_settings(self.widget, self.key))

    def load(self, _sw, node, _tables):
        self.widget.setCurrentText(node[self.key] or self.default)


class ColumnChoiceAttr(Attr):
    """Combobox whose options are the columns of input_tables[input_index]."""

    def __init__(
            self, key, default=None, label=None,
            extra_values=None, sort=True, input_index=0):
        super().__init__(key, default=default, label=label)
        self.extra_values = extra_values
        self.sort = sort
        self.input_index = input_index

    def _make_widget(self, _):
        return QtWidgets.QComboBox()

    def _connect(self, sw):
        self.widget.currentTextChanged.connect(
            lambda: sw.combobox_to_settings(self.widget, self.key))

    def load(self, _sw, node, input_tables):
        df = input_tables[self.input_index] if input_tables else None
        set_combo_values_from_table_columns(
            self.widget, df, node[self.key] or '',
            extra_values=self.extra_values, sort=self.sort)


class CompoundAttr(Attr):
    """
    Escape hatch for attrs that don't map 1:1 to a widget. Owns multiple
    settings keys and renders as one row in the auto-form.

    Subclass and override: default_values, _make_widget, _connect, load.
    If you need control over form placement, skip the auto-form and build
    the widget manually in your settings widget's __init__.
    """

    def __init__(self, keys, label):
        self.keys = tuple(keys)
        self.key = self.keys[0]
        self.label = label
        self.widget = None

    def apply_default(self, settings):
        for k, v in self.default_values().items():
            if settings.get(k) is None and v is not None:
                settings[k] = v

    def default_values(self) -> dict:
        return {}
