"""Lab 04 — reference solution: a toy query planner."""
from __future__ import annotations

from dataclasses import dataclass


class Table:
    def __init__(self, name: str, rows: list[dict],
                 column_stats: dict[str, dict] | None = None) -> None:
        self.name = name
        self.rows = rows
        self.column_stats = column_stats or {}


class Catalog:
    def __init__(self) -> None:
        self.tables: dict[str, Table] = {}
        self.indexes: dict[tuple[str, str], bool] = {}

    def add_table(self, table: Table) -> None:
        self.tables[table.name] = table

    def add_index(self, table: str, column: str) -> None:
        self.indexes[(table, column)] = True

    def has_index(self, table: str, column: str) -> bool:
        return (table, column) in self.indexes


@dataclass
class SeqScan:
    table: str
    columns: list[str] | None = None


@dataclass
class IndexScan:
    table: str
    column: str
    key: object


@dataclass
class Filter:
    child: object
    column: str
    op: str
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
    if isinstance(node, SeqScan):
        return f"SeqScan({node.table})"
    if isinstance(node, IndexScan):
        return f"IndexScan({node.table}.{node.column}={node.key})"
    if isinstance(node, Filter):
        return f"Filter({node.column}{node.op}{node.value})"
    if isinstance(node, Project):
        return f"Project({','.join(node.columns)})"
    if isinstance(node, HashJoin):
        return f"HashJoin({node.left_key}={node.right_key})"
    if isinstance(node, NestedLoopJoin):
        return f"NestedLoopJoin({node.left_key}={node.right_key})"
    if isinstance(node, Limit):
        return f"Limit({node.n})"
    raise TypeError(f"unknown node {node!r}")


def render_plan(node) -> str:
    """Bottom-up one-line rendering: children first, then this node."""
    parts = []

    def walk(n):
        for attr in ("child", "left", "right"):
            c = getattr(n, attr, None)
            if c is not None and hasattr(c, "__dataclass_fields__"):
                walk(c)
        parts.append(render(n))

    walk(node)
    return "->".join(parts)


def _children(node):
    return [c for c in (getattr(node, "child", None),
                        getattr(node, "left", None),
                        getattr(node, "right", None))
            if c is not None and hasattr(c, "__dataclass_fields__")]


def estimate_selectivity(catalog: Catalog, table: str, column: str,
                         op: str, value) -> float:
    stats = catalog.tables.get(table).column_stats.get(column) \
        if table in catalog.tables else None
    if not stats:
        return 0.5
    if op == "=":
        nd = max(1, stats.get("ndistinct", 1))
        return min(1.0, 1.0 / nd)
    lo, hi = stats.get("min"), stats.get("max")
    if lo is None or hi is None or hi == lo:
        return 0.5
    if op == ">":
        frac = (hi - value) / (hi - lo)
    elif op == "<":
        frac = (value - lo) / (hi - lo)
    else:
        return 0.5
    return min(1.0, max(0.0, frac))


def estimate_rows(catalog: Catalog, node) -> int:
    if isinstance(node, SeqScan):
        return len(catalog.tables[node.table].rows)
    if isinstance(node, IndexScan):
        t = catalog.tables[node.table]
        sel = estimate_selectivity(catalog, node.table, node.column, "=", node.key)
        return int(len(t.rows) * sel)
    if isinstance(node, Filter):
        base = estimate_rows(catalog, node.child)
        scan = _scan_under(node)
        sel = 0.5
        if scan is not None:
            table = scan.table
            sel = estimate_selectivity(catalog, table, node.column,
                                       node.op, node.value)
        return int(base * sel)
    if isinstance(node, Project):
        return estimate_rows(catalog, node.child)
    if isinstance(node, (HashJoin, NestedLoopJoin)):
        l = estimate_rows(catalog, node.left)
        r = estimate_rows(catalog, node.right)
        ltab = _scan_under(node.left)
        nd = 1
        if ltab is not None and ltab.table in catalog.tables:
            st = catalog.tables[ltab.table].column_stats.get(node.left_key)
            if st:
                nd = max(1, st.get("ndistinct", 1))
        return int(l * r / nd)
    if isinstance(node, Limit):
        return min(node.n, estimate_rows(catalog, node.child))
    raise TypeError(f"unknown node {node!r}")


def _scan_under(node):
    while node is not None and not isinstance(node, (SeqScan, IndexScan)):
        kids = _children(node)
        if not kids:
            return None
        node = kids[0]
    return node


SELECTIVITY_THRESHOLD = 0.1


class Planner:
    def __init__(self, catalog: Catalog, memory_budget_rows: int = 10_000) -> None:
        self.catalog = catalog
        self.memory_budget_rows = memory_budget_rows

    # ------------------------------------------------------------- rule 1
    def _use_index(self, node):
        """Filter directly above SeqScan with indexed column and
        selectivity < threshold, op '='  ->  IndexScan with fused key."""
        if (isinstance(node, Filter) and node.op == "="
                and isinstance(node.child, SeqScan)):
            scan = node.child
            if self.catalog.has_index(scan.table, node.column):
                sel = estimate_selectivity(self.catalog, scan.table,
                                           node.column, node.op, node.value)
                if sel < SELECTIVITY_THRESHOLD:
                    return IndexScan(scan.table, node.column, node.value)
        return node

    # ------------------------------------------------------------- rule 2
    def _pushdown_filter(self, node):
        """Push a Filter toward the scans, through Project. Never below a
        Limit (it would change which rows the limit sees)."""
        if isinstance(node, Project):
            inner = self._pushdown_filter(node.child)
            if isinstance(inner, Filter):
                # Project(col,...) over Filter(col op v) -> Filter over Project
                if node.columns is None or inner.column in node.columns:
                    return Filter(Project(inner.child, node.columns),
                                  inner.column, inner.op, inner.value)
            return Project(inner, node.columns)
        if isinstance(node, (HashJoin, NestedLoopJoin)):
            return type(node)(self._pushdown_filter(node.left),
                              self._pushdown_filter(node.right),
                              node.left_key, node.right_key)
        if isinstance(node, Limit):
            return Limit(self._pushdown_filter(node.child), node.n)
        if isinstance(node, Filter):
            return self._use_index(Filter(self._pushdown_filter(node.child),
                                          node.column, node.op, node.value))
        return node

    # ------------------------------------------------------------- rule 4
    def _pushdown_limit(self, node):
        """Limit sinks below Project (safe: row-wise). Never below Filter."""
        if isinstance(node, Limit):
            inner = self._pushdown_limit(node.child)
            if isinstance(inner, Project):
                # Limit(Project(X)) -> Project(Limit(X))
                return Project(Limit(inner.child, node.n), inner.columns)
            return Limit(inner, node.n)
        if isinstance(node, Project):
            return Project(self._pushdown_limit(node.child), node.columns)
        if isinstance(node, (HashJoin, NestedLoopJoin)):
            return type(node)(self._pushdown_limit(node.left),
                              self._pushdown_limit(node.right),
                              node.left_key, node.right_key)
        return node

    # ------------------------------------------------------------- rule 3
    def _choose_join(self, node):
        if isinstance(node, (HashJoin, NestedLoopJoin)):
            l = self._choose_join(node.left)
            r = self._choose_join(node.right)
            build = min(estimate_rows(self.catalog, l),
                        estimate_rows(self.catalog, r))
            cls = HashJoin if build <= self.memory_budget_rows else NestedLoopJoin
            return cls(l, r, node.left_key, node.right_key)
        if isinstance(node, (Project, Filter)):
            child = self._choose_join(node.child)
            return type(node)(child, node.column, node.op, node.value) \
                if isinstance(node, Filter) else Project(child, node.columns)
        if isinstance(node, Limit):
            return Limit(self._choose_join(node.child), node.n)
        return node

    def optimize(self, node):
        node = self._pushdown_filter(node)
        node = self._pushdown_limit(node)
        node = self._choose_join(node)
        return node


# ------------------------------------------------------------------ executor
def _pred(row: dict, column: str, op: str, value) -> bool:
    v = row.get(column)
    if op == "=":
        return v == value
    if op == ">":
        return v is not None and v > value
    if op == "<":
        return v is not None and v < value
    raise ValueError(f"unknown op {op!r}")


def execute(catalog: Catalog, node) -> list[dict]:
    if isinstance(node, SeqScan):
        t = catalog.tables[node.table]
        return [dict(r) for r in t.rows]
    if isinstance(node, IndexScan):
        t = catalog.tables[node.table]
        return [dict(r) for r in t.rows if r.get(node.column) == node.key]
    if isinstance(node, Filter):
        return [r for r in execute(catalog, node.child)
                if _pred(r, node.column, node.op, node.value)]
    if isinstance(node, Project):
        return [{c: r[c] for c in node.columns if c in r}
                for r in execute(catalog, node.child)]
    if isinstance(node, HashJoin):
        rows_l = execute(catalog, node.left)
        rows_r = execute(catalog, node.right)
        idx: dict = {}
        for rr in rows_r:
            idx.setdefault(rr.get(node.right_key), []).append(rr)
        out = []
        for lr in rows_l:
            for rr in idx.get(lr.get(node.left_key), []):
                merged = {**lr, **rr}
                out.append(merged)
        return out
    if isinstance(node, NestedLoopJoin):
        rows_l = execute(catalog, node.left)
        rows_r = execute(catalog, node.right)
        return [{**lr, **rr} for lr in rows_l for rr in rows_r
                if lr.get(node.left_key) == rr.get(node.right_key)]
    if isinstance(node, Limit):
        return execute(catalog, node.child)[:node.n]
    raise TypeError(f"unknown node {node!r}")
