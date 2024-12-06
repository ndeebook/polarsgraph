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
re_operator = r'[+\-*/(),]'
re_tokens = re_column, re_number, re_function, re_string, re_operator


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
        formula = self[ATTR.FORMULA]
        column_name = self[ATTR.COLUMN] or 'Derived column'
        expression = formula_to_polars_expression(formula)
        table = table.with_columns(expression.alias(column_name))
        self.tables['table'] = table


class DeriveSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.column_edit = QtWidgets.QLineEdit()
        self.column_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.column_edit, ATTR.COLUMN))

        self.formula_edit = QtWidgets.QPlainTextEdit()
        self.formula_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(
                self.formula_edit, ATTR.FORMULA))

        # Fixed size font
        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)

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


def formula_to_polars_expression(formula: str):
    tokens = tokenize(formula)
    tokens_with_depth = mark_depth(tokens)
    while len(tokens_with_depth) > 1:
        tokens_with_depth = convert_highest_depth(tokens_with_depth)
    return tokens_with_depth[0][1]


def tokenize(formula) -> list[str]:
    """split all parts of the formula in a list"""
    token_pattern = re.compile(r'\s*' + '|'.join(re_tokens) + r'\s*')
    tokens = token_pattern.findall(formula)
    return [t.strip() for t in tokens if t.strip()]  # strip + exclude empty


def mark_depth(tokens) -> list[tuple]:
    """convert all tokens to (depth, token) tuples"""
    depth = 0
    new = []
    for token in tokens:
        if token == '(':
            depth += 1
        elif token == ')':
            depth -= 1
        else:
            if token.startswith('@'):
                new_token = depth + 1, token
                depth += 1
            elif token == ',':
                new_token = depth - 1, token
            else:
                new_token = depth, token
            new.append(new_token)
    return new


def convert_highest_depth(tokens_with_depth):
    """
    Example:
        replace:
            [(0, '{column_name1}'),
             (0, '+'),
             (1, '@round'),
             (2, '{column_name1}'),
             (2, '*'),
             (2, '{column name2}'),
             (1, '2')]
        by:
            [(0, '{column_name1}'),
             (0, '+'),
             (1, '@round'),
             (1, `polars expression`),
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
