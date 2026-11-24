"""
Create new column with an Formula.
See `EXAMPLES_TEXT` for examples.
"""
import os
import re

import polars as pl

from PySide6 import QtWidgets, QtGui, QtCore

from polarsgraph.attrs import StrAttr, TextAttr
from polarsgraph.nodes import ORANGE as DEFAULT_COLOR, OPERATOR_MAGIC_METHODS
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


COLUMN = 'column'
FORMULA = 'formula'


ARGLESS_COLUMNS_METHODS = (
    'abs', 'count', 'ceil',

    'is_infinite', 'is_finite', 'is_nan', 'is_null', 'is_duplicated',
    'is_unique',

    'degrees', 'radians',
    'sin', 'cos', 'tan', 'sinh', 'cosh', 'tanh',
    'arcsin', 'arccos', 'arctan', 'arcsinh', 'arccosh', 'arctanh'
)
STR_ARGLESS_COLUMNS_METHODS = (
    'to_uppercase',
    'to_lowercase',
    'to_titlecase',
    'to_integer',
    'to_decimal',
    'len_chars',
)
STR_ARGLESS_ALIASES = dict(
    strip='strip_chars',
    strip_left='strip_chars_start',
    strip_right='strip_chars_end',
    reverse='reverse',
)
# @function({column}, argument) -> argument can be a "string" or a {column}
STR_ONE_ARG_METHODS = dict(
    startswith=lambda s, arg: s.starts_with(arg),
    endswith=lambda s, arg: s.ends_with(arg),
    contains=lambda s, arg: s.contains(arg, literal=True),
    icontains=lambda s, arg: s.to_lowercase().str.contains(
        arg.str.to_lowercase(), literal=True),
    matches=lambda s, arg: s.contains(arg),  # regex
    count_text=lambda s, arg: s.count_matches(arg, literal=True),
    find=lambda s, arg: s.find(arg, literal=True),
    extract=lambda s, arg: s.extract(arg, 1),  # regex, first group
    remove_prefix=lambda s, arg: s.strip_prefix(arg),
    remove_suffix=lambda s, arg: s.strip_suffix(arg),
    remove=lambda s, arg: s.replace_all(arg, '', literal=True),
)
DT_ARGLESS_COLUMNS_METHODS = [
    method for method in dir(pl.col('_').dt)
    if not method.startswith('_') and method != 'to_string']
EXAMPLES_TEXT = """
{column_name1} + ({column_name2} + 1 / 2)
{column_name1} + "_" + {column_name2}

@round({column_name}, 2)
@slice({column_name}, 2, -2)

@replace_string({column_name}, "old value", "new value")
@replace_int({column_name}, 1, 2)
@replace_float({column_name}, 0.999, 1.0)
@replace_bool({column_name}, true, none)
@replace_nans({column_name}, 1.0)
@replace_nulls({column_name}, 1.0)

@startswith({column_name}, "prefix")
@endswith({column_name}, "suffix")
@contains({column_name}, "text")
@icontains({column_name}, "text")  // case insensitive
@matches({column_name}, "^regex$")
@count_text({column_name}, "text")
@find({column_name}, "text")  // index or null
@extract({column_name}, "regex_(group)")
@remove({column_name}, "text")
@remove_prefix({column_name}, "prefix")
@remove_suffix({column_name}, "suffix")
@replace_text({column_name}, "old", "new")
@replace_regex({column_name}, "(\\d+)", "#$1")
@strip({column_name}) / @strip_left / @strip_right / @reverse
@zfill({column_name}, 4)
@pad_left({column_name}, 10, " ") / @pad_right

@remove_nans({column_name})
@remove_infs({column_name})

@to_boolean({column_name})
@to_string({column_name})

@weekday({date_column})
@day({date_column})
@ordinal_day({date_column})
@month({date_column})
@year({date_column})

@""" + '\n@'.join(STR_ARGLESS_COLUMNS_METHODS + ARGLESS_COLUMNS_METHODS)

BOOL_DICT = dict(true=True, false=False)


re_bool = r'null|none|true|false'
re_column = r'\{[^\}]*\}'
re_number = r'-?\d+\.\d+|-?\d+'
re_function = r'@\w+'
re_string = r'"[^"]*"'
re_operator = r'[+\-*/(),\|\^\&]|==|!=|<=|>=|>|<'
re_tokens = re_bool, re_column, re_number, re_function, re_string, re_operator
token_pattern = re.compile(r'\s*' + '|'.join(re_tokens) + r'\s*')


class DeriveNode(BaseNode):
    type = 'derive'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        StrAttr(COLUMN, default='Derived column', label='Column name'),
        TextAttr(FORMULA, label='Formula'),
    ]

    def _build_query(self, tables):
        table: pl.LazyFrame = tables[0]
        formula = remove_comments(self[FORMULA])
        column_name = self[COLUMN] or 'Derived column'
        expression = formula_to_polars_expression(formula)
        table = table.with_columns(expression.alias(column_name))
        self.tables['table'] = table


class ColumnCompleter(QtWidgets.QListWidget):
    def __init__(self, editor: QtWidgets.QPlainTextEdit):
        super().__init__()
        self.editor = editor
        self.column_names = []

        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool |
            QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            'QListWidget {'
            '  background: #2d2d2d; color: #c586c0;'
            '  border: 1px solid #555; font-family: consolas;'
            '}')

        self.itemClicked.connect(self._complete)
        editor.textChanged.connect(self._update)
        editor.installEventFilter(self)

    def set_columns(self, names):
        self.column_names = list(names)

    def _partial(self):
        cursor = self.editor.textCursor()
        text = cursor.block().text()[:cursor.positionInBlock()]
        i = text.rfind('{')
        if i == -1 or '}' in text[i + 1:]:
            return None
        return text[i + 1:]

    def _update(self):
        partial = self._partial()
        if partial is None or not self.column_names:
            self.hide()
            return
        matches = [
            n for n in self.column_names if partial.lower() in n.lower()]
        if not matches:
            self.hide()
            return
        self.clear()
        self.addItems(matches)
        self.setCurrentRow(0)
        pos = self.editor.mapToGlobal(self.editor.cursorRect().bottomLeft())
        self.move(pos)
        self.resize(250, min(200, self.count() * 22 + 4))
        self.show()

    def _complete(self, item=None):
        partial = self._partial()
        if partial is None:
            return
        text = (item or self.currentItem()).text()
        cursor = self.editor.textCursor()
        for _ in range(len(partial)):
            cursor.deletePreviousChar()
        cursor.insertText(text + '}')
        self.editor.setTextCursor(cursor)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self.editor:
            if event.type() == QtCore.QEvent.Type.FocusOut:
                self.hide()
                return False
        if obj is self.editor and self.isVisible():
            if event.type() == QtCore.QEvent.Type.KeyPress:
                key = event.key()
                if key == QtCore.Qt.Key.Key_Down:
                    self.setCurrentRow(
                        min(self.currentRow() + 1, self.count() - 1))
                    return True
                if key == QtCore.Qt.Key.Key_Up:
                    self.setCurrentRow(max(self.currentRow() - 1, 0))
                    return True
                if key in (
                        QtCore.Qt.Key.Key_Return,
                        QtCore.Qt.Key.Key_Enter,
                        QtCore.Qt.Key.Key_Tab):
                    self._complete()
                    return True
                if key == QtCore.Qt.Key.Key_Escape:
                    self.hide()
                    return True
        return super().eventFilter(obj, event)


class HelpDialog(QtWidgets.QDialog):
    """Non-modal, scrollable examples window (text can be copied)"""
    def __init__(self, text, font, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Formula help')
        self.resize(600, 600)
        text_edit = QtWidgets.QPlainTextEdit(text.strip('\n'))
        text_edit.setReadOnly(True)
        text_edit.setFont(font)
        text_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        close_button = QtWidgets.QPushButton('Close')
        close_button.clicked.connect(self.close)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(text_edit)
        layout.addWidget(
            close_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)


class DeriveSettingsWidget(BaseSettingsWidget):
    def __init__(self, attrs=None, help_text=EXAMPLES_TEXT):
        super().__init__()
        if attrs is None:
            attrs = DeriveNode.attrs

        # Fixed size font
        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)
        editor_font = QtGui.QFont(fixed_font)
        editor_font.setPointSizeF(editor_font.pointSizeF() * 1.2)

        # Form: Name + any non-formula declarative attrs.
        form = QtWidgets.QFormLayout()
        form.addRow('Name', self.name_edit)
        formula_attr = None
        for attr in attrs:
            if attr.key == FORMULA:
                formula_attr = attr
                continue
            label, widget = self.register_attr(attr)
            form.addRow(label, widget)
        self.form_layout = form

        # Formula editor: declarative TextAttr with styling applied here.
        _, self.formula_edit = self.register_attr(formula_attr)
        self.formula_edit.setStyleSheet(
            'QPlainTextEdit{background-color:#333333;color:#9cdcfe}')
        self.formula_edit.setFont(editor_font)
        self.highlighter = CustomHighlighter(self.formula_edit.document())
        self.completer = ColumnCompleter(self.formula_edit)

        self.help_text = help_text
        self.help_font = fixed_font
        self.help_dialog = None
        help_button = QtWidgets.QPushButton('Examples')
        help_button.clicked.connect(self.show_help)

        formula_header = QtWidgets.QHBoxLayout()
        formula_header.addWidget(QtWidgets.QLabel('Formula'))
        formula_header.addStretch()
        formula_header.addWidget(help_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(formula_header)
        layout.addWidget(self.formula_edit)

    def show_help(self):
        if self.help_dialog is None:
            self.help_dialog = HelpDialog(
                self.help_text, self.help_font, parent=self)
        # Show without blocking:
        self.help_dialog.show()
        self.help_dialog.raise_()
        self.help_dialog.activateWindow()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        if input_tables and input_tables[0] is not None:
            self.completer.set_columns(
                input_tables[0].collect_schema().names())
        else:
            self.completer.set_columns([])
        self.blockSignals(False)


class CustomHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        aqua_mint = '#4ec9b0'
        ocean_blue = '#569cd6'
        orchid_purple = '#c586c0'
        golden_beige = '#d7ba7d'
        green = '#5e993e'
        # sky_blue = '#4fc1ff'
        # pale_cyan = '#9cdcfe'
        # sage_green = '#b5cea8'
        # soft_gray = '#c8c8c8'
        # desert_sand = '#ce9178'
        # rosewood = '#d16969'
        # pale_butter = '#dcdcaa'

        self.parenthesis_format = QtGui.QTextCharFormat()
        self.parenthesis_format.setForeground(QtGui.QColor('#FFFFFF'))

        self.curly_format = QtGui.QTextCharFormat(self.parenthesis_format)
        self.curly_format.setForeground(QtGui.QColor(orchid_purple))

        self.quote_format = QtGui.QTextCharFormat(self.parenthesis_format)
        self.quote_format.setForeground(QtGui.QColor(golden_beige))

        self.operator_format = QtGui.QTextCharFormat(self.parenthesis_format)
        self.operator_format.setForeground(QtGui.QColor(ocean_blue))

        self.comment_format = QtGui.QTextCharFormat(self.parenthesis_format)
        self.comment_format.setForeground(QtGui.QColor(green))

        self.function_format = QtGui.QTextCharFormat()
        self.function_format.setForeground(QtGui.QColor(aqua_mint))
        self.function_format.setFontItalic(True)

    def highlightBlock(self, text):
        for i, char in enumerate(text):
            if char in '()':
                self.setFormat(i, 1, self.parenthesis_format)
            if char == ',':
                self.setFormat(i, 1, self.parenthesis_format)
            if char in OPERATOR_MAGIC_METHODS:
                self.setFormat(i, 1, self.operator_format)

        patterns_format = [
            (r'//.*', self.comment_format),
            (r'@\w+', self.function_format),
            (r'"[^"]*?"', self.quote_format),
            (r'\{[^{}]*?}', self.curly_format),
        ]
        for pattern, format in patterns_format:
            for match in re.finditer(pattern, text):
                start, end = match.start(), match.end()
                self.setFormat(start, end - start, format)


def formula_to_polars_expression(formula: str):
    tokens = tokenize(formula)
    if len(tokens) == 1:
        return token_to_value(tokens[0])
    tokens_with_depth = mark_depth(tokens)
    while len(tokens_with_depth) > 1:
        tokens_with_depth = convert_highest_depth(tokens_with_depth)
    return tokens_with_depth[0][1]


def tokenize(formula) -> list[str]:
    """split all parts of the formula in a list"""
    tokens = token_pattern.findall(formula)
    return [t.strip() for t in tokens if t.strip()]  # strip + exclude empty


def mark_depth(tokens: list[str]) -> list[tuple]:
    """
    Convert all tokens to (depth, token) tuples and remove parentheses.
    The idea is to identify groups/levels of token to be parsed together.

    Example with `@to_string(@round({x}/{y}*100, 1)) + "%"`:
        1 `@to_string`
            2 `@round`
                3 `{x}/{y}*100`
            2 `,` => make sure first arg of `@round` is handled first
                3 `1`
        0 + `"%"` => different group than `@to_string` to be handled afterwards
    """
    depth = 0
    tokens_with_depth = []
    opened = []
    for token in tokens:
        if token == '(':
            opened.append('(')
            depth += 1
            continue
        if token == ')':
            depth -= 1
            if opened.pop() == 'func':
                # Escape functions depths
                depth -= 2
            continue
        if token == ',':
            tokens_with_depth.append((depth - 1, ','))
            continue
        if token.startswith('@'):
            # functions in their own depth to parse them on their own
            opened.append('func')
            depth += 1
        tokens_with_depth.append((depth, token))
    return tokens_with_depth


def convert_highest_depth(tokens_with_depth: list[tuple]) -> list[tuple]:
    """
    Example:
        replace:
            [(0, '{column_name1}'),
             (0, '+'),
             (1, '@round'),
        =>   (2, '{column_name1}'),
        =>   (2, '*'),
        =>   (2, '{column name2}'),
             (1, '2')]
        by:
            [(0, '{column_name1}'),
             (0, '+'),
             (1, '@round'),
        =>   (1, `polars expression "column_name1 * column_name2"`),
             (1, '2')]
    """
    highest_depth = max(t[0] for t in tokens_with_depth)
    new_depth = highest_depth - 1
    groups = []
    group = []
    for token in tokens_with_depth:
        if token[0] == highest_depth:
            group.append(token[1])
        else:
            if group:
                groups.append((new_depth, get_polars_expression(group)))
            groups.append(token)
            group = []
    if group:
        groups.append((new_depth, get_polars_expression(group)))
    return groups


def get_polars_expression(tokens: list[str]):
    """handle lowest level with functions, columns and operators"""
    first = tokens[0]
    if isinstance(first, str) and first.startswith('@'):  # function
        return func_formula_to_polars(first[1:], tokens[1:])
    else:
        return get_polars_arithmetic_expression(tokens)


def func_formula_to_polars(function_name, tokens):
    if function_name == 'round':
        column = token_to_value(tokens[0])
        decimals_arg = int(tokens[2])  # token[1] is ","
        return column.round(decimals_arg)
    if function_name == 'slice':
        column = token_to_value(tokens[0])
        start, end = int(tokens[2]), int(tokens[4])
        length = column.str.len_chars()
        if start < 0:
            start = length + start + 1
        if end < 0:
            size = pl.max_horizontal(length + end + 1, 1)
        else:
            size = end - start + 1
        # Return expression
        if end == 0:
            return column.str.slice(start)
        else:
            return column.str.slice(start, size)
    if function_name in STR_ONE_ARG_METHODS:
        column = token_to_value(tokens[0])
        argument = token_to_value(tokens[2])
        return STR_ONE_ARG_METHODS[function_name](column.str, argument)
    if function_name == 'replace_text':
        column = token_to_value(tokens[0])
        old, new = token_to_value(tokens[2]), token_to_value(tokens[4])
        return column.str.replace_all(old, new, literal=True)
    if function_name == 'replace_regex':
        column = token_to_value(tokens[0])
        old, new = token_to_value(tokens[2]), token_to_value(tokens[4])
        return column.str.replace_all(old, new)
    if function_name in ('zfill', 'pad_left', 'pad_right'):
        column = token_to_value(tokens[0])
        width = int(tokens[2])
        if function_name == 'zfill':
            return column.str.zfill(width)
        fill = tokens[4][1:-1] if len(tokens) > 4 else ' '
        if function_name == 'pad_left':
            return column.str.pad_start(width, fill)
        return column.str.pad_end(width, fill)
    if function_name in STR_ARGLESS_ALIASES:
        column = token_to_value(tokens[0])
        return getattr(column.str, STR_ARGLESS_ALIASES[function_name])()
    if function_name in STR_ARGLESS_COLUMNS_METHODS:
        column = token_to_value(tokens[0])
        return getattr(column.str, function_name)()
    if function_name in DT_ARGLESS_COLUMNS_METHODS:
        column = token_to_value(tokens[0])
        return getattr(column.dt, function_name)()
    if function_name in ('to_boolean', 'to_string'):
        column = token_to_value(tokens[0])
        datatype = dict(to_boolean=pl.Boolean, to_string=pl.String)
        return column.cast(datatype[function_name])
    if function_name == 'len_chars':
        column = token_to_value(tokens[0])
        return column.str.len_chars()
    if function_name in ARGLESS_COLUMNS_METHODS:
        column = token_to_value(tokens[0])
        return getattr(column, function_name)()
    if function_name == 'replace_nans':
        column: pl.Expr = token_to_value(tokens[0])
        value = float(tokens[2])
        return column.fill_nan(value)
    if function_name == 'replace_nulls':
        column: pl.Expr = token_to_value(tokens[0])
        value_or_column = token_to_value(tokens[2])
        return column.fill_null(value_or_column)
    if function_name.startswith('replace_'):
        column: pl.Expr = token_to_value(tokens[0])
        value = tokens[2]
        new_value = tokens[4]
        if function_name == 'replace_string':
            value, new_value = [v.replace('"', '') for v in (value, new_value)]
            return column.replace(value, new_value)
        elif function_name == 'replace_float':
            return column.replace(float(value), float(new_value))
        elif function_name == 'replace_int':
            return column.replace(int(value), int(new_value))
        elif function_name == 'replace_bool':
            value, new_value = [parse_bool(v) for v in (value, new_value)]
            return column.replace(value, new_value)
    if function_name == 'remove_nans':
        column: pl.Expr = token_to_value(tokens[0])
        return column.fill_nan(None)
    if function_name == 'remove_infs':
        column: pl.Expr = token_to_value(tokens[0])
        return (
            column
            .replace(pl.lit(float("inf")), None)
            .replace(pl.lit(float("-inf")), None)
        )
    raise ValueError(f'Unknown function name "{function_name}"')


def get_polars_arithmetic_expression(tokens):
    expression = tokens.pop(0)
    i = 0
    while tokens:
        i += 1
        if i == 1:
            # Dont convert to expression if it's on its own
            # because it could be a func arg and not a pl.lit
            expression = token_to_value(expression)
        operator_name = tokens.pop(0)
        if not tokens:
            raise ValueError(
                f'Incomplete formula: missing operand after "{operator_name}"')
        magic_method_name = OPERATOR_MAGIC_METHODS[operator_name]
        operator_method = getattr(expression, magic_method_name)
        content = token_to_value(tokens.pop(0))
        expression = operator_method(content)
    return expression


def token_to_value(token):
    if not isinstance(token, str):  # Expression
        return token
    if token.startswith('{'):  # Column
        return pl.col(token[1:-1])
    elif token.lower() in ('true', 'false'):  # Boolean
        return pl.lit(BOOL_DICT[token.lower()])
    elif token[0] == '"':  # String
        return pl.lit(token[1:-1])
    elif '.' in token:  # Float
        return pl.lit(float(token))
    else:  # Integer
        return pl.lit(int(token))


def parse_bool(text):
    text = text.lower()
    if text in ('none', 'null'):
        return None
    if text in ('true', '1'):
        return True
    return False


if __name__ == '__main__':
    formula = '@to_string(@round({x}/{y}*100, 1)) + "%"'

    # tokenize()
    tokens = tokenize(formula)
    expected_tokens = [
        '@to_string', '(',
        '@round', '(',
        '{x}', '/', '{y}', '*', '100', ',', '1',
        ')',
        ')',
        '+', '"%"']
    assert tokens == expected_tokens

    # mark_depth()
    tokens_with_depth = mark_depth(tokens)
    expected_depths = [
        (1, '@to_string'),
        (3, '@round'),
        (4, '{x}'), (4, '/'), (4, '{y}'), (4, '*'), (4, '100'),
        (3, ','),
        (4, '1'),
        (0, '+'), (0, '"%"')]
    assert tokens_with_depth == expected_depths

    # formula_to_polars_expression()
    expression = formula_to_polars_expression(formula)
    df = pl.DataFrame([{'x': 2, 'y': 4}])
    assert df.with_columns(expression.alias('test'))[0, 2] == '50.0%'

    # Test with extra parentheses
    formula = '@to_string(@round(({x}/{y}*100), 1)) + "%"'
    expression = formula_to_polars_expression(formula)
    assert df.with_columns(expression.alias('test'))[0, 2] == '50.0%'

    # Test without function
    formula = '{tasks.duration}/25/2'
    tokens = tokenize(formula)
    tokens_with_depth = mark_depth(tokens)
    assert tokens_with_depth == [
        (0, '{tasks.duration}'), (0, '/'), (0, '25'), (0, '/'), (0, '2')]
    expression = formula_to_polars_expression(formula)
    expected = '[([(col("tasks.duration")) / (dyn int: 25)]) / (dyn int: 2)]'
    assert str(expression) == expected


def remove_comments(formula):
    return ''.join(
        [line for line in formula.split('\n') if not line.startswith('//')])
