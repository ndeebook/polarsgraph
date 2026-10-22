import polars as pl
from PySide6 import QtWidgets, QtGui, QtCharts, QtCore
from PySide6.QtCore import Qt

from polarsgraph.attrs import ChoiceAttr, IntAttr, StrAttr
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, BaseNode, BaseSettingsWidget, BaseDisplay)


COLOR = dict(
    text=Qt.GlobalColor.white,
    bg=QtGui.QColor('#2F2F2F'),
    pie_text=QtGui.QColor('#777777'),
)


TITLE = 'title'
START_ANGLE = 'start_angle'
END_ANGLE = 'end_angle'

DISPLAY_INDEX_OPTIONS = ['auto'] + [str(i) for i in range(1, 10)]


class PieNode(BaseNode):
    type = 'pie'
    category = DISPLAY_CATEGORY
    input_plugs = 'table',
    output_plugs = 'widget',
    default_color = DEFAULT_COLOR
    attrs = [
        ChoiceAttr(DISPLAY_INDEX_ATTR, DISPLAY_INDEX_OPTIONS,
                   label='Display index'),
        StrAttr(TITLE, label='Title'),
        IntAttr(START_ANGLE, default=0, label='Start angle',
                minimum=-999, maximum=999),
        IntAttr(END_ANGLE, default=360, label='End angle',
                minimum=-999, maximum=999),
    ]

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
            self._display_widget = PieDisplay(self)
        return self._display_widget


class PieSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(PieNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)


class PieDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self.node: PieNode = node
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
        title = self.node[TITLE] or self.node['name']
        start_angle = self.node[START_ANGLE] or 0
        end_angle = self.node[END_ANGLE] or 360
        self.node.error = make_chart(
            self.chart_view, table, title, start_angle, end_angle)
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
        start_angle: float = 0,
        end_angle: float = 360):
    # Create the chart
    chart = QtCharts.QChart()
    chart.setTitle(title)
    chart.setBackgroundBrush(QtGui.QBrush(COLOR['bg']))
    chart.setTitleBrush(QtGui.QBrush(COLOR['text']))
    chart.legend().hide()
    chart.setMargins(QtCore.QMargins(0, 0, 0, 0))

    # Create the Pie Series
    series = QtCharts.QPieSeries(startAngle=start_angle, endAngle=end_angle)
    label_brush = QtGui.QBrush(COLOR['pie_text'])

    # Sum data for each column to calculate their share in the pie
    value_column = dataframe.select(dataframe.columns[1])
    total = value_column.sum()[0, 0]

    for values in dataframe.iter_rows():
        label, value, *_ = values
        ratio = value / total
        label = f'{label} ({round(ratio * 100, 1)}%)'
        try:
            slice_ = series.append(label, ratio)
        except TypeError as e:
            return str(e)
        slice_.setLabelVisible(True)
        slice_.setLabelBrush(label_brush)

    chart.addSeries(series)
    chart_view.setChart(chart)
