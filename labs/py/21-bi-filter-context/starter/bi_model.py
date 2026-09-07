"""Lab 21 — BI filter-context semantics. Fill in every TODO.

Tables are name -> list-of-row-dicts. A star schema's facts reference
dimensions by key. Filter context is {dim_name: set(values)}.
"""
from __future__ import annotations

from typing import Any, Callable


FilterCtx = dict[str, set]


class Model:
    """Star schema: dimensions (one) -> facts (many)."""

    def __init__(self, relations: list[tuple[str, str, str, str]]) -> None:
        # (dim_name, dim_key, fact_name, fact_key)
        self.relations = relations
        self.tables: dict[str, list[dict]] = {}

    def add_table(self, name: str, rows: list[dict]) -> None:
        self.tables[name] = rows

    def fact_rows(self, fact: str, dim_filters: FilterCtx) -> list[dict]:
        """Fact rows surviving filter PROPAGATION: a filter on dim D only
        reaches the fact through D's relationship. Filters on dimensions
        with no relationship to this fact are ignored (the star's edges
        ARE the routing). Empty/no filters -> all rows."""
        # TODO(step 1)
        raise NotImplementedError


def evaluate(model: Model, fact: str, measure_fn: Callable[[list[dict]], Any],
             filter_ctx: FilterCtx | None = None) -> Any:
    """Measure evaluation under filter context: resolve the context to
    surviving rows, run measure_fn on exactly those. No context = all rows."""
    # TODO(step 2)
    raise NotImplementedError


Modifier = tuple  # ("filter", dim, set) | ("all", dim) | ("removefilters", dim) | ("all_all", None)


def calculate(model: Model, fact: str, measure_fn: Callable[[list[dict]], Any],
              filter_ctx: FilterCtx | None,
              *modifiers: Modifier) -> Any:
    """CALCULATE: context transition. Start from filter_ctx, apply each
    modifier in order ('filter' replaces/adds that dimension's filter,
    'all'/'removefilters' clears it, 'all_all' clears everything), then
    evaluate the measure under the RESULTING context."""
    # TODO(step 3)
    raise NotImplementedError


def calculated_column(model: Model, fact: str, name: str,
                      row_fn: Callable[[dict], Any]) -> list[Any]:
    """The anti-measure: compute per fact row AT REFRESH, store on the row
    under `name`, return the column values in fact order. Row-level
    values, stored, sliceable — never context-aware again."""
    # TODO(step 4)
    raise NotImplementedError


def fixed_lod(model: Model, fact: str, group_dim: str,
              agg_fn: Callable[[list], Any],
              filter_ctx: FilterCtx | None) -> dict:
    """{FIXED [group_dim]: agg(values)}: group ALL fact rows by their
    group_dim value (through the relationship), aggregate per group —
    ignoring filter_ctx ON group_dim while still respecting context on
    OTHER dimensions. Returns {group_value: agg_result}."""
    # TODO(step 5)
    raise NotImplementedError


def percent_of_total(model: Model, fact: str,
                     measure_fn: Callable[[list[dict]], Any],
                     filter_ctx: FilterCtx | None,
                     denom_ctx: FilterCtx | None = None) -> float:
    """Numerator under filter_ctx, denominator under denom_ctx (or the
    empty context), as a percentage. The table-calc flavor: BOTH sides
    respect context."""
    # TODO(step 6)
    raise NotImplementedError
