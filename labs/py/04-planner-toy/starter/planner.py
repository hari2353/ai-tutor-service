"""Lab 04 — a toy query planner. Fill in every TODO. Tests define done.

Two worlds live in this file:

    PLANNING uses only the fake statistics (ndistinct/min/max) — it never
    touches a real row. EXECUTION touches only rows. That separation is
    the whole point: the planner bets on estimates; EXPLAIN ANALYZE audits
    the bet against reality.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --------------------------------------------------------------------- tables
class Table:
    def __init__(self, name: str, rows: list[dict],
                 column_stats: dict[str, dict] | None = None) -> None:
        self.name = name
        self.rows = rows
        self.column_stats = column_stats or {}


class Catalog:
    def __init__(self) -> None:
        self.tables: dict[str, Table] = {}
        self.indexes: dict[tuple[str, str], bool] = {}   # (table, column) -> True

    def add_table(self, table: Table) -> None:
        self.tables[table.name] = table

    def add_index(self, table: str, column: str) -> None:
        # TODO(step 1)
        raise NotImplementedError

    def has_index(self, table: str, column: str) -> bool:
        # TODO(step 1b)
        raise NotImplementedError


# ---------------------------------------------------------------- plan nodes
@dataclass
class SeqScan:
    table: str
    columns: list[str] | None = None      # None = all


@dataclass
class IndexScan:
    table: str
    column: str
    key: object                           # the fused equality predicate


@dataclass
class Filter:
    child: object
    column: str
    op: str                               # "=", ">", "<"
    value: object


@dataclass
class Project:
    child: object
    columns: list[str]


@dataclass
class HashJoin:
    left: object
    right: object
    left_key: str = ""
    right_key: str = ""


@dataclass
class NestedLoopJoin:
    left: object
    right: object
    left_key: str = ""
    right_key: str = ""


@dataclass
class Limit:
    child: object
    n: int


def render(node) -> str:
    """One-line plan string, e.g. 'SeqScan(users)->Filter(age>30)->Project(name)'.

    IndexScan renders as 'IndexScan(users.age=...)'.
    Joins render as 'HashJoin(lkey=rkey)' / 'NestedLoopJoin(lkey=rkey)'.
    Children render first (bottom-up), joined with '->'.
    """
    # TODO(step 2)
    raise NotImplementedError


# ---------------------------------------------------------------- estimation
def estimate_selectivity(catalog: Catalog, table: str, column: str,
                         op: str, value) -> float:
    """The fake pg_stats. '=' -> 1/ndistinct. '>' -> (max-value)/(max-min).
    '<' -> (value-min)/(max-min). Clamp to [0,1]; no stats -> 0.5."""
    # TODO(step 3)
    raise NotImplementedError


def estimate_rows(catalog: Catalog, node) -> int:
    """Bottom-up row estimate. SeqScan -> len(rows). IndexScan ->
    selectivity * rows. Filter -> child * selectivity. Project -> child.
    Join -> outer*inner/max(ndistinct(key),1). Limit -> min(n, child).
    Round to int, min 0."""
    # TODO(step 4)
    raise NotImplementedError


# ------------------------------------------------------------------ optimizer
SELECTIVITY_THRESHOLD = 0.1


class Planner:
    def __init__(self, catalog: Catalog, memory_budget_rows: int = 10_000) -> None:
        self.catalog = catalog
        self.memory_budget_rows = memory_budget_rows

    def optimize(self, node):
        """Apply the rules bottom-up until nothing changes. Rules:
        1. index selection: Filter over SeqScan, indexed column,
           selectivity < SELECTIVITY_THRESHOLD -> IndexScan (fused).
        2. predicate pushdown: Filter sinks toward the scans, through
           Project, but NEVER below a Limit.
        3. join choice: build side = min(est(left), est(right));
           fits memory_budget_rows -> HashJoin else NestedLoopJoin.
        4. limit pushdown: Limit sinks below Project (row-wise, safe),
           never below Filter.
        The optimizer may not change the query's answer."""
        # TODO(step 5)
        raise NotImplementedError

    # TODO(step 5 helpers): _pushdown_filter(node), _pushdown_limit(node),
    # _choose_join(node), _use_index(node) — recurse bottom-up.


# ------------------------------------------------------------------ executor
def execute(catalog: Catalog, node) -> list[dict]:
    """Run any plan tree against real rows; inner-join semantics for both
    join nodes; returns rows (each a dict of the available columns)."""
    # TODO(step 6): SeqScan materializes, IndexScan = equality-filtered scan,
    # Filter evaluates op, Project selects columns, HashJoin/NestedLoopJoin
    # both inner-join on keys, Limit truncates.
    raise NotImplementedError
