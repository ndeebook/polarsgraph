"""
Declarative attribute system for nodes.

Each node declares its editable settings as `attrs = [Attr(...), ...]` on the
node class. The framework uses that list to:
    - apply default values at node construction (BaseNode.__init__)
    - build the settings widget's form rows and wire signals
      (BaseSettingsWidget.build_attr_form)
    - populate the widgets in set_node (BaseSettingsWidget.load_attrs)

Writes go through each attr's `_write(settings_widget, value)` which can be
overridden to retarget — see `ExposedAttr` for exposing a child node's
attribute on a parent subgraph.

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
        # Last widget built. Settings widgets access this for ad-hoc tweaks
        # (`attr.widget.setMaximum(...)`) and load_attrs uses it to find the
        # widget without needing a separate registry.
        self.widget: QtWidgets.QWidget = None

    def apply_default(self, settings):
        if settings.get(self.key) is None and self.default is not None:
            settings[self.key] = self.default

    def build(self, settings_widget):
        widget = self._make_widget(settings_widget)
        self.widget = widget
        self._connect(widget, settings_widget, self._write)
        return self.label, widget

    def _make_widget(self, settings_widget):
        raise NotImplementedError

    def _connect(self, widget, settings_widget, write):
        raise NotImplementedError

    def load(self, widget, settings_widget, node, input_tables):
        raise NotImplementedError

    def _write(self, settings_widget, value):
        """
        Persist a widget change. Default: write to `settings_widget.node[key]`
        and notify. Override to retarget (see ExposedAttr).
        """
        settings_widget.node[self.key] = value
        settings_widget.emit_changed()


class StrAttr(Attr):
    def __init__(self, key, default=None, label=None, placeholder=None):
        super().__init__(key, default=default, label=label)
        self.placeholder = placeholder

    def _make_widget(self, _):
        w = QtWidgets.QLineEdit()
        if self.placeholder:
            w.setPlaceholderText(self.placeholder)
        return w

    def _connect(self, widget, settings_widget, write):
        widget.editingFinished.connect(
            lambda: write(settings_widget, widget.text() or None))

    def load(self, widget, _settings_widget, node, _tables):
        widget.setText(node[self.key] or self.default or '')


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

    def _connect(self, widget, settings_widget, write):
        widget.textChanged.connect(
            lambda: write(settings_widget, widget.toPlainText() or None))

    def load(self, widget, _settings_widget, node, _tables):
        widget.setPlainText(node[self.key] or '')


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

    def _connect(self, widget, settings_widget, write):
        widget.valueChanged.connect(
            lambda: write(settings_widget, int(widget.value())))

    def load(self, widget, _settings_widget, node, _tables):
        value = node[self.key]
        if value is None:
            value = self.default if self.default is not None else 0
        widget.setValue(int(value))


class ColorAttr(Attr):
    """Button that opens a QColorDialog; stores the QColor on the node."""

    def __init__(self, key, default=None, label=None, button_text='Color'):
        super().__init__(key, default=default, label=label)
        self.button_text = button_text

    def _make_widget(self, _):
        return QtWidgets.QPushButton(self.button_text)

    def _connect(self, widget, settings_widget, write):
        widget.clicked.connect(lambda: self._pick(settings_widget, write))

    def _pick(self, settings_widget, write):
        # NB: reads from settings_widget.node — won't DTRT if wrapped by
        # ExposedAttr (reads subgraph instead of child).
        current = settings_widget.node[self.key]
        initial = QtGui.QColor(current) if current else QtGui.QColor()
        color = QtWidgets.QColorDialog.getColor(initial)
        if not color.isValid():
            return
        write(settings_widget, color)

    def load(self, _widget, _settings_widget, _node, _tables):
        pass  # the color is read on demand from the node when picking


class BoolAttr(Attr):
    def _make_widget(self, _):
        return QtWidgets.QCheckBox()

    def _connect(self, widget, settings_widget, write):
        widget.stateChanged.connect(
            lambda: write(settings_widget, widget.isChecked()))

    def load(self, widget, _settings_widget, node, _tables):
        widget.setChecked(bool(node[self.key]))


class ChoiceAttr(Attr):
    def __init__(self, key, options, default=None, label=None):
        super().__init__(key, default=default or options[0], label=label)
        self.options = options

    def _make_widget(self, _):
        w = QtWidgets.QComboBox()
        w.addItems(self.options)
        return w

    def _connect(self, widget, settings_widget, write):
        widget.currentTextChanged.connect(
            lambda: write(settings_widget, widget.currentText()))

    def load(self, widget, _settings_widget, node, _tables):
        widget.setCurrentText(node[self.key] or self.default)


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

    def _connect(self, widget, settings_widget, write):
        widget.currentTextChanged.connect(
            lambda: write(settings_widget, widget.currentText()))

    def load(self, widget, _settings_widget, node, input_tables):
        df = input_tables[self.input_index] if input_tables else None
        set_combo_values_from_table_columns(
            widget, df, node[self.key] or '',
            extra_values=self.extra_values, sort=self.sort)


class CompoundAttr(Attr):
    """
    Escape hatch for attrs that don't map 1:1 to a widget. Owns multiple
    settings keys and renders as one row in the auto-form.

    Subclass and override: default_values, _make_widget, _connect, load.
    Compound attrs are not exposable through ExposedAttr.
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


class ExposedAttr(Attr):
    """
    Proxy that exposes a child node's attribute on a parent subgraph's
    settings panel. Widget is a fresh instance (not the child's widget);
    reads load from the child's current settings; writes target the child
    and propagate dirty through the graph.

    Instantiated dynamically by SubgraphSettingsWidget each time a subgraph
    instance is loaded, based on `settings['exposed_attrs']`.
    """

    def __init__(self, child_name, inner: Attr, label=None):
        self.child_name = child_name
        self.inner = inner
        self.key = inner.key
        self.default = None  # the child owns the default
        self.label = (
            label if label is not None
            else f'[{child_name}] {inner.label}')
        self.keys = (inner.key,)
        self.widget = None

    def apply_default(self, _settings):
        pass  # default applies on the child, not the subgraph

    def build(self, settings_widget):
        # Fresh widget, independent of the child's own panel widget.
        widget = self.inner._make_widget(settings_widget)
        self.widget = widget
        # Reuse inner's wiring logic, but with our widget + our write target.
        self.inner._connect(widget, settings_widget, self._write)
        return self.label, widget

    def _write(self, settings_widget, value):
        from polarsgraph.graph import set_dirty_recursive
        graph = settings_widget.node.graph
        child = graph[self.child_name]
        child[self.inner.key] = value
        child.dirty = True
        # Downstream of the child needs to re-run.
        set_dirty_recursive(graph, self.child_name)
        settings_widget.emit_changed()

    def load(self, widget, settings_widget, node, _tables):
        from polarsgraph.graph import get_input_tables
        graph = node.graph
        child = graph[self.child_name]
        child_tables = get_input_tables(graph, child)
        self.inner.load(widget, settings_widget, child, child_tables)
