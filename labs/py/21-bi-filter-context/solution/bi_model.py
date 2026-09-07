"""Lab 21 — reference solution. The starter is the same file with every
body replaced by NotImplementedError."""
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

    def _edges_for(self, fact: str):
        return [r for r in self.relations if r[2] == fact]

    def fact_rows(self, fact: str, dim_filters: FilterCtx) -> list[dict]:
        rows = self.tables[fact]
        for dim, key, _f, fkey in self._edges_for(fact):
            if dim in dim_filters:
                allowed = set(dim_filters[dim])
                rows = [r for r in rows if r[fkey] in allowed]
        return list(rows)


def evaluate(model: Model, fact: str, measure_fn: Callable[[list[dict]], Any],
             filter_ctx: FilterCtx | None = None) -> Any:
    ctx = filter_ctx or {}
    rows = model.fact_rows(fact, ctx)
    return measure_fn(rows)


Modifier = tuple  # ("filter", dim, set) | ("all", dim) | ("removefilters", dim) | ("all_all", None)


def calculate(model: Model, fact: str, measure_fn: Callable[[list[dict]], Any],
              filter_ctx: FilterCtx | None,
              *modifiers: Modifier) -> Any:
    ctx: FilterCtx = {d: set(v) for d, v in (filter_ctx or {}).items()}
    for mod in modifiers:
        kind = mod[0]
        if kind == "filter":
            _, dim, values = mod
            ctx[dim] = set(values)
        elif kind in ("all", "removefilters"):
            ctx.pop(mod[1], None)
        elif kind == "all_all":
            ctx.clear()
        else:
            raise ValueError(f"unknown modifier: {mod!r}")
    return evaluate(model, fact, measure_fn, ctx)


def calculated_column(model: Model, fact: str, name: str,
                      row_fn: Callable[[dict], Any]) -> list[Any]:
    out = []
    for row in model.tables[fact]:
        row[name] = row_fn(row)
        out.append(row[name])
    return out


def fixed_lod(model: Model, fact: str, group_dim: str,
              agg_fn: Callable[[list], Any],
              filter_ctx: FilterCtx | None) -> dict:
    ctx: FilterCtx = {d: set(v) for d, v in (filter_ctx or {}).items()}
    ctx.pop(group_dim, None)  # FIXED ignores the grouping dimension
    rows = model.fact_rows(fact, ctx)
    edge = next(e for e in model._edges_for(fact) if e[0] == group_dim)
    fkey = edge[3]
    groups: dict[Any, list] = {}
    for r in rows:
        groups.setdefault(r[fkey], []).append(r["amount"])
    return {g: agg_fn(vs) for g, vs in groups.items()}


def percent_of_total(model: Model, fact: str,
                     measure_fn: Callable[[list[dict]], Any],
                     filter_ctx: FilterCtx | None,
                     denom_ctx: FilterCtx | None = None) -> float:
    num = evaluate(model, fact, measure_fn, filter_ctx)
    den = evaluate(model, fact, measure_fn, denom_ctx)
    return num / den * 100
