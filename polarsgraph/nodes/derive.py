"""
Create new column with an Formula.
See `EXAMPLES_TEXT` for examples.
"""
import os
import re

import polars as pl

from PySide6 import QtWidgets, QtGui

from polarsgraph.nodes import ORANGE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


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
EXAMPLES_TEXT = """
{column_name1} + ({column_name2} + 1 / 2)
{column_name1} + "_" + {column_name2}

@round({column_name}, 2)
@slice({column_name}, 2, -2)

@replace_string({column_name}, "old value", "new value")
@replace_int({column_name}, 1, 2)
@replace_float({column_name}, 0.999, 1.0)

@remove_nans({column_name})
@remove_infs({column_name})

@to_boolean({column_name})
@to_string({column_name})
...
""" + ', '.join(STR_ARGLESS_COLUMNS_METHODS + ARGLESS_COLUMNS_METHODS)

BOOL_DICT = dict(true=True, false=False)

OPERATOR_MAGIC_METHODS = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '//': '__floordiv__',
    '%': '__mod__',
    '**': '__pow__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '~': '__invert__',
    '==': '__eq__',
    '!=': '__ne__',
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
    'in': '__contains__',
    '+=': '__iadd__',
    '-=': '__isub__',
    '*=': '__imul__',
    '/=': '__itruediv__',
    '//=': '__ifloordiv__',
    '%=': '__imod__',
    '**=': '__ipow__',
    '&=': '__iand__',
    '|=': '__ior__',
    '^=': '__ixor__',
}


re_column = r'\{[^\}]*\}'
re_number = r'-?\d+\.\d+|-?\d+'
re_function = r'@\w+'
re_string = r'"[^"]*"'
re_operator = r'[+\-*/(),]|==|!=|<=|>=|>|<'
re_tokens = re_column, re_number, re_function, re_string, re_operator
token_pattern = re.compile(r'\s*' + '|'.join(re_tokens) + r'\s*')


class ATTR:
    NAME = 'name'
    COLUMN = 'column'
    FORMULA = 'formula'


class DeriveNode(BaseNode):
    type = 'derive'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        table: pl.LazyFrame = tables[0]
        formula = remove_comments(self[ATTR.FORMULA])
        column_name = self[ATTR.COLUMN] or 'Derived column'
        expression = formula_to_polars_expression(formula)
        table = table.with_columns(expression.alias(column_name))
        self.tables['table'] = table


class DeriveSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Fixed size font
        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)
        editor_font = QtGui.QFont(fixed_font)
        editor_font.setPointSizeF(editor_font.pointSizeF() * 1.2)

        # Widgets
        self.column_edit = QtWidgets.QLineEdit()
        self.column_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.column_edit, ATTR.COLUMN))

        self.formula_edit = QtWidgets.QPlainTextEdit()
        self.formula_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(
                self.formula_edit, ATTR.FORMULA))
        self.formula_edit.setStyleSheet(
            'QPlainTextEdit{background-color:#333333;color:#9cdcfe}')
        self.formula_edit.setFont(editor_font)
        self.highlighter = CustomHighlighter(self.formula_edit.document())

        help_label = QtWidgets.QLabel(EXAMPLES_TEXT, font=fixed_font)
        help_label.setWordWrap(True)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Column name', self.column_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QtWidgets.QLabel('Formula'))
        layout.addWidget(self.formula_edit)
        layout.addWidget(QtWidgets.QLabel('Examples:'))
        layout.addWidget(help_label)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.column_edit.setText(node[ATTR.COLUMN] or 'Derived column')
        self.formula_edit.setPlainText(node[ATTR.FORMULA] or '')
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
    if function_name in STR_ARGLESS_COLUMNS_METHODS:
        column = token_to_value(tokens[0])
        return getattr(column.str, function_name)()
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
