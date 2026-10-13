import datetime
import math
import traceback

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, BaseNode, BaseSettingsWidget, BaseDisplay)


COLOR = dict(
    text=Qt.GlobalColor.white,
    axis_text=QtGui.QColor('#888888'),
    grid=QtGui.QColor('#444444'),
    bg=QtGui.QColor('#2F2F2F'),
)

LINE_COLORS = [
    '#4F77A8',
    '#F28E2C',
    '#E15659',
    '#59A14F',
    '#ECC947',
    '#76B7B1',
    '#B17AA1',
    '#FE9DA6',
    '#9B755E',
]


class ATTR:
    NAME = 'name'
    TITLE = 'title'
    DISPLAY_INDEX = DISPLAY_INDEX_ATTR
    INVERT_AXES = 'invert_axes'
    Y_MAX = 'y_max'
    LINEAR_DATES = 'linear_dates'


class LinesNode(BaseNode):
    type = 'lines'
    category = DISPLAY_CATEGORY
    input_plugs = 'table',
    output_plugs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)
        self._display_widget = None

    def _build_query(self, tables):
        self.tables['table'] = tables[0]
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

        self.index_combo = QtWidgets.QComboBox()
        self.index_combo.addItems(['auto'] + [str(i) for i in range(1, 10)])
        self.index_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.index_combo, ATTR.DISPLAY_INDEX))

        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.title_edit, ATTR.TITLE))

        self.invert_axes_cb = QtWidgets.QCheckBox('Invert Axes')
        self.invert_axes_cb.checkStateChanged.connect(
            lambda: self.checkbox_to_settings(
                self.invert_axes_cb, ATTR.INVERT_AXES))

        self.linear_dates_cb = QtWidgets.QCheckBox('Linear date axis')
        self.linear_dates_cb.checkStateChanged.connect(
            lambda: self.checkbox_to_settings(
                self.linear_dates_cb, ATTR.LINEAR_DATES))

        self.y_max_edit = QtWidgets.QLineEdit()
        self.y_max_edit.setPlaceholderText('auto')
        self.y_max_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.y_max_edit, ATTR.Y_MAX))

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Display index', self.index_combo)
        form_layout.addRow(ATTR.TITLE.title(), self.title_edit)
        form_layout.addRow('', self.invert_axes_cb)
        form_layout.addRow('', self.linear_dates_cb)
        form_layout.addRow('Y max', self.y_max_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.title_edit.setText(node[ATTR.TITLE] or '')
        self.invert_axes_cb.setChecked(bool(node[ATTR.INVERT_AXES]))
        self.linear_dates_cb.setChecked(bool(node[ATTR.LINEAR_DATES]))
        self.y_max_edit.setText(
            str(node[ATTR.Y_MAX]) if node[ATTR.Y_MAX] is not None else '')
        self.blockSignals(False)


class LinesDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.node: LinesNode = node

        self.chart_view = CustomLinesChart()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            return
        table = table.collect()
        self.chart_view.set_data(table, self.node)
        self.node.error = self.chart_view.error

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


class CustomLinesChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataframe = pl.DataFrame()
        self.chart_dataframe = pl.DataFrame()
        self.node = None
        self.error = None
        self.series_list = []
        self.x_min = 0.0
        self.x_max = 1.0
        self.y_min = 0.0
        self.y_max = 1.0
        self.orig_x_min = None
        self.screen_x_date_mode = None
        self.screen_y_date_mode = None
        self.date_axis_values = None  # sorted unique dates when categorical
        self.x_tick_values = []
        self.y_tick_values = []

    def set_data(self, table: pl.DataFrame, node):
        self.error = None
        self.node = node
        self.dataframe = table
        try:
            self.chart_dataframe = self.convert_dates()
            self._parse()
        except Exception as e:
            self.error = str(e)
            traceback.print_exc()
        self.update()

    def convert_dates(self):
        self.date_axis_values = None
        linear = bool(self.node[ATTR.LINEAR_DATES]) if self.node else False

        date_cols = [
            c for c, dt in self.dataframe.schema.items()
            if isinstance(dt, (pl.Date, pl.Datetime))]
        if not date_cols:
            return self.dataframe

        if linear:
            exprs = []
            for col_name in date_cols:
                dtype = self.dataframe.schema[col_name]
                if isinstance(dtype, pl.Date):
                    # Days elapsed from min
                    exprs.append(
                        (pl.col(col_name) - pl.col(col_name).min())
                        .dt.total_days().alias(col_name))
                else:
                    # Seconds elapsed from min
                    exprs.append(
                        (pl.col(col_name) - pl.col(col_name).min())
                        .dt.total_seconds().cast(pl.Float64).alias(col_name))
            return self.dataframe.with_columns(exprs)

        # Categorical: shared ordinal axis over all distinct date values
        all_dates = set()
        for c in date_cols:
            all_dates.update(self.dataframe[c].drop_nulls().to_list())
        self.date_axis_values = sorted(all_dates)
        index_by_date = {d: float(i) for i, d in enumerate(self.date_axis_values)}

        exprs = [
            pl.col(c).map_elements(
                lambda d: index_by_date.get(d),
                return_dtype=pl.Float64,
            ).alias(c)
            for c in date_cols
        ]
        return self.dataframe.with_columns(exprs)

    def _parse(self):
        self.series_list = []
        self.x_min, self.x_max = 0.0, 1.0
        self.y_min, self.y_max = 0.0, 1.0
        self.orig_x_min = None
        self.screen_x_date_mode = None
        self.screen_y_date_mode = None

        df = self.chart_dataframe
        if df.is_empty() or df.width < 2:
            return
        if df.width % 2 != 0:
            raise ValueError(
                'Dataframe must have an even number of columns (pairs of X,Y)')

        invert_axes = bool(self.node[ATTR.INVERT_AXES])

        # Figure out which screen axis gets date labels, if any
        orig_x_dtype = self.dataframe.dtypes[0]
        self.orig_x_min = self.dataframe[self.dataframe.columns[0]].min()
        if isinstance(orig_x_dtype, pl.Date):
            date_mode = 'date'
        elif isinstance(orig_x_dtype, pl.Datetime):
            date_mode = 'datetime'
        else:
            date_mode = None
        if date_mode:
            if invert_axes:
                self.screen_y_date_mode = date_mode
            else:
                self.screen_x_date_mode = date_mode

        # Extract each (x,y) pair as polars columns, drop nulls, cast to Float64
        screen_x_cols, screen_y_cols = [], []
        for col_index in range(0, df.width, 2):
            x_col, y_col = df.columns[col_index], df.columns[col_index + 1]
            if invert_axes:
                x_col, y_col = y_col, x_col
            pair = (
                df.lazy()
                .select(
                    pl.col(x_col).cast(pl.Float64).alias('x'),
                    pl.col(y_col).cast(pl.Float64).alias('y'))
                .drop_nulls()
                .collect())
            if pair.is_empty():
                continue
            self.series_list.append((pair['x'].to_list(), pair['y'].to_list()))
            screen_x_cols.append(x_col)
            screen_y_cols.append(y_col)

        if not self.series_list:
            return

        # Global min/max via a single polars aggregation
        agg = df.select(
            *(pl.col(c).min().alias(f'min_{i}')
              for i, c in enumerate(screen_x_cols)),
            *(pl.col(c).max().alias(f'max_{i}')
              for i, c in enumerate(screen_x_cols)),
            *(pl.col(c).min().alias(f'ymin_{i}')
              for i, c in enumerate(screen_y_cols)),
            *(pl.col(c).max().alias(f'ymax_{i}')
              for i, c in enumerate(screen_y_cols)),
        ).row(0, named=True)

        self.x_min = min(
            agg[f'min_{i}'] for i in range(len(screen_x_cols)))
        self.x_max = max(
            agg[f'max_{i}'] for i in range(len(screen_x_cols)))
        y_min_data = min(
            agg[f'ymin_{i}'] for i in range(len(screen_y_cols)))
        y_max_data = max(
            agg[f'ymax_{i}'] for i in range(len(screen_y_cols)))

        # Resolve y range (0-anchored for non-date, override wins)
        y_max_raw = self.node[ATTR.Y_MAX]
        try:
            y_max_override = (
                float(y_max_raw) if y_max_raw not in (None, '') else None)
        except (ValueError, TypeError):
            y_max_override = None

        self.y_min = (
            y_min_data if self.screen_y_date_mode else min(0.0, y_min_data))
        if y_max_override is not None:
            self.y_max = y_max_override
        elif self.screen_y_date_mode:
            self.y_max = y_max_data
        else:
            self.y_max = _nice_max(y_max_data)
        if self.y_max <= self.y_min:
            self.y_max = self.y_min + 1

        # Tick values: in categorical date mode, land ticks on actual indices
        self.x_tick_values = self._compute_ticks(
            self.x_min, self.x_max, self.screen_x_date_mode)
        self.y_tick_values = self._compute_ticks(
            self.y_min, self.y_max, self.screen_y_date_mode)

    def _compute_ticks(self, axis_min, axis_max, date_mode):
        if date_mode and self.date_axis_values is not None:
            n = len(self.date_axis_values)
            if n == 0:
                return []
            if n <= 10:
                return [float(i) for i in range(n)]
            return sorted({round(i * (n - 1) / 5) for i in range(6)})
        return [axis_min + i / 5 * (axis_max - axis_min) for i in range(6)]

    def _fmt_axis_label(self, val, date_mode):
        if date_mode in ('date', 'datetime') and self.date_axis_values is not None:
            idx = int(round(val))
            if not 0 <= idx < len(self.date_axis_values):
                return ''
            d = self.date_axis_values[idx]
            if date_mode == 'date' or (d.hour == 0 and d.minute == 0):
                return d.strftime('%d/%m/%y')
            return d.strftime('%d/%m %H:%M')
        if date_mode == 'date':
            d = self.orig_x_min + datetime.timedelta(days=int(val))
            return d.strftime('%d/%m/%y')
        if date_mode == 'datetime':
            dt = self.orig_x_min + datetime.timedelta(seconds=float(val))
            if dt.hour == 0 and dt.minute == 0:
                return dt.strftime('%d/%m/%y')
            return dt.strftime('%d/%m %H:%M')
        return _fmt_value(val)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Background
        rect = self.rect()
        painter.fillRect(rect, COLOR['bg'])

        if not self.node:
            return

        # Title
        title = self.node[ATTR.TITLE] or self.node[ATTR.NAME]
        painter.setPen(COLOR['text'])
        title_rect = QtCore.QRect(0, 0, rect.width(), 28)
        painter.drawText(title_rect, Qt.AlignCenter, title)

        if self.error:
            painter.setPen(QtGui.QColor('#E15659'))
            painter.drawText(
                rect.adjusted(0, 28, 0, 0), Qt.AlignCenter, self.error)
            return

        if not self.series_list:
            return

        # Chart Rect
        m_left = 48
        m_top = 28
        m_right = 48
        m_bottom = 30

        chart_rect = QtCore.QRectF(
            m_left, m_top,
            rect.width() - m_left - m_right,
            rect.height() - m_top - m_bottom)

        if chart_rect.width() < 10 or chart_rect.height() < 10:
            return

        x_range = (self.x_max - self.x_min) or 1
        y_range = (self.y_max - self.y_min) or 1

        def to_sx(x):
            return chart_rect.left() + (x - self.x_min) / x_range * chart_rect.width()

        def to_sy(y):
            return chart_rect.bottom() - (y - self.y_min) / y_range * chart_rect.height()

        # Axis Labels
        small_font = QtGui.QFont()
        small_font.setPointSize(8)
        painter.setFont(small_font)

        # Y grid lines and labels
        for y_val in self.y_tick_values:
            sy = to_sy(y_val)
            painter.setPen(QtGui.QPen(COLOR['grid'], 0.5))
            painter.drawLine(
                QtCore.QPointF(chart_rect.left(), sy),
                QtCore.QPointF(chart_rect.right(), sy))
            painter.setPen(COLOR['axis_text'])
            painter.drawText(
                QtCore.QRectF(0, sy - 10, m_left - 4, 20),
                Qt.AlignRight | Qt.AlignVCenter,
                self._fmt_axis_label(y_val, self.screen_y_date_mode))

        # X grid lines and labels
        for x_val in self.x_tick_values:
            sx = to_sx(x_val)
            painter.setPen(QtGui.QPen(COLOR['grid'], 0.5))
            painter.drawLine(
                QtCore.QPointF(sx, chart_rect.top()),
                QtCore.QPointF(sx, chart_rect.bottom()))
            painter.setPen(COLOR['axis_text'])
            painter.drawText(
                QtCore.QRectF(sx - 40, chart_rect.bottom() + 4, 80, m_bottom - 4),
                Qt.AlignCenter | Qt.AlignTop,
                self._fmt_axis_label(x_val, self.screen_x_date_mode))

        # Lines
        for idx, (xs, ys) in enumerate(self.series_list):
            color = QtGui.QColor(LINE_COLORS[idx % len(LINE_COLORS)])
            points = [
                QtCore.QPointF(to_sx(x), to_sy(y))
                for x, y in zip(xs, ys)]
            if len(points) > 1:
                painter.setPen(QtGui.QPen(color, 2))
                painter.drawPolyline(QtGui.QPolygonF(points))
            elif len(points) == 1:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(points[0], 3, 3)


def _fmt_value(val):
    if val == 0:
        return '0'
    if abs(val) >= 10000:
        return f'{val:,.0f}'
    if val == int(val):
        return str(int(val))
    return f'{val:.3g}'


def _fmt_datetime(timestamp):
    dt = datetime.datetime.fromtimestamp(timestamp)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt.strftime('%d/%m/%y')
    return dt.strftime('%d/%m %H:%M')


def _nice_max(value):
    if value <= 0:
        return 1 if value == 0 else value * 1.1
    if value > 1:
        size = len(str(math.ceil(value)))
        step = 10 ** (size - 2)
    else:
        step = 1.0
        while value * step < 1:
            step *= 10
        step = 1.0 / step
    result = int(value / step) * step
    while result <= value * 1.001:
        result += step
    return result
