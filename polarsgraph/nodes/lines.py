import polars as pl
from PySide6 import QtWidgets, QtGui, QtCharts, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, BaseNode, BaseSettingsWidget, BaseDisplay)


COLOR = dict(
    text=Qt.GlobalColor.white,
    axis_text=QtGui.QColor('#888888'),
    grid=QtGui.QColor('#888888'),
    bg=QtGui.QColor('#2F2F2F'),
)


class ATTR:
    NAME = 'name'
    TITLE = 'title'
    DISPLAY_INDEX = DISPLAY_INDEX_ATTR
    INVERT_AXES = 'invert_axes'


class LinesNode(BaseNode):
    type = 'lines'
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
        pass

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = LinesDisplay(self)
        return self._display_widget


class LinesSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.index_combo = QtWidgets.QComboBox()
        self.index_combo.addItems(['auto'] + [str(i) for i in range(1, 10)])
        self.index_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.index_combo, ATTR.DISPLAY_INDEX))

        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.title_edit, ATTR.TITLE))
        self.invert_axes_cb = QtWidgets.QCheckBox(
            'Invert Axes')
        self.invert_axes_cb.checkStateChanged.connect(
            lambda: self.checkbox_to_settings(
                self.invert_axes_cb, ATTR.INVERT_AXES))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Display index', self.index_combo)
        form_layout.addRow(ATTR.TITLE.title(), self.title_edit)
        form_layout.addRow('', self.invert_axes_cb)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.title_edit.setText(node[ATTR.TITLE] or '')
        self.blockSignals(False)


class LinesDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self.node: LinesNode = node
        self._resizing = False

        # Widgets
        self.chart_view = QtCharts.QChartView()
        self.chart_view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.error_label = QtWidgets.QLabel('Error')

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)
        layout.addWidget(self.error_label)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            return
        table = table.collect()
        title = self.node[ATTR.TITLE] or self.node[ATTR.NAME]
        invert_axes = bool(self.node[ATTR.INVERT_AXES])
        self.node.error = make_chart(
            self.chart_view, table, title, invert_axes)
        if self.node.error:
            self.chart_view.setVisible(False)
            self.error_label.setVisible(True)
        else:
            self.chart_view.setVisible(True)
            self.error_label.setVisible(False)

    def get_pixmap(self):
        pixmap = QtGui.QPixmap(self.chart_view.size())
        self.chart_view.render(pixmap)
        return pixmap

    def save_image(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save spreadsheet', '', '*.png')
        if not filepath:
            return
        self.get_pixmap().save(filepath)

    def image_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setPixmap(self.get_pixmap())


def make_chart(
        chart_view: QtCharts.QChartView,
        dataframe: pl.DataFrame,
        title: str,
        invert_axes: bool = False):
    # Create the chart
    chart = QtCharts.QChart()
    chart.legend().hide()
    chart.setTitle(title)
    chart.setBackgroundBrush(QtGui.QBrush(COLOR['bg']))
    text_brush = QtGui.QBrush(COLOR['text'])
    chart.setTitleBrush(text_brush)
    chart.setMargins(QtCore.QMargins(0, 0, 0, 0))

    # Create the Lines Series
    series = QtCharts.QLineSeries()

    # Sum data for each column to calculate their share in the lines
    for values in dataframe.iter_rows():
        for x, y in zip(values[::2], values[1::2]):
            if invert_axes:
                x, y = y, x
            try:
                series.append(x, y)
            except TypeError as e:
                return str(e)

    # Configure the axes
    chart.addSeries(series)

    # chart.createDefaultAxes()
    axis_x = QtCharts.QValueAxis()
    axis_y = QtCharts.QValueAxis()
    # axis_x.setTitleText("X-Axis")
    # axis_y.setTitleText("Y-Axis")
    axis_x.setLabelsBrush(QtGui.QBrush(COLOR['axis_text']))
    axis_y.setLabelsBrush(QtGui.QBrush(COLOR['axis_text']))
    grid_pen = QtGui.QPen(COLOR['grid'])
    grid_pen.setWidth(.5)
    axis_x.setGridLinePen(grid_pen)
    axis_y.setGridLinePen(grid_pen)
    chart.addAxis(axis_x, QtCore.Qt.AlignBottom)
    chart.addAxis(axis_y, QtCore.Qt.AlignLeft)
    series.attachAxis(axis_x)
    series.attachAxis(axis_y)

    chart_view.setChart(chart)
