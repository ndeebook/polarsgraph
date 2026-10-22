import polars as pl

from polarsgraph.attrs import TextAttr
from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode
from polarsgraph.nodes.derive import (
    FORMULA, DeriveSettingsWidget,
    formula_to_polars_expression, remove_comments)


EXAMPLES_TEXT = """
{column_name} == 0
{column_name} != "test"
{column_name} <= 3
{column_name} >= 4
{column_name} < 3
{column_name} > 4
...

"&" means "and"
"|" means "or"

Example:

    ({column_name} == "a")
    | ({column_name} == "b")
    & ({column_name} != "c")
    & ({column_name} != "d")

Also:

    (
        (({col} == "a") | ({col} == "b"))
        &
        (({col} != "c") & ({col} != "d"))
    )

"""


class FilterExpNode(BaseNode):
    type = 'filterexp'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [TextAttr(FORMULA, label='Formula')]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        formula = remove_comments(self[FORMULA] or '')
        if not formula.strip():
            self.tables['table'] = df
            return
        expression = formula_to_polars_expression(formula)
        self.tables['table'] = df.filter(expression)


class FilterExpSettingsWidget(DeriveSettingsWidget):
    def __init__(self):
        super().__init__(
            attrs=FilterExpNode.attrs,
            help_text=EXAMPLES_TEXT)
