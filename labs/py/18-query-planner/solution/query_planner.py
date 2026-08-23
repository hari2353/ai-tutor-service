"""Lab 18 — cost-based join planner toy (reference solution).

The planner sees STATISTICS ONLY: row counts, row widths, selectivity factors.
Every number it emits is an estimate computed without touching data — that is
the whole lesson of cost-based optimization.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- constants
PAGE_SIZE = 8192              # bytes per heap page
IDX_DEFAULT_HEIGHT = 3        # B-tree descent levels, toy-index terms
HASH_FIXED_COST = 25.0        # one-off hash-table setup
HASH_ROW_COST = 0.02          # per build-side row inserted
SORT_PAGE_FACTOR = 2.5        # external merge-sort passes over each page
MERGE_ROW_COST = 0.01         # lockstep merge walk, per input tuple
DEFAULT_JOIN_SEL = 0.01       # fallback when a join-graph edge is missing
MAX_SEARCH_RELATIONS = 6      # spec cap: exhaustive left-deep search <= 6 rels
DEFAULT_BEAM_WIDTH = 10       # greedy-pruned DP-lite: keep top-K partial plans/level

ALGORITHMS = ("nested_loop", "hash_join", "merge_join")
# Deterministic tie-break: lower rank wins equal-cost comparisons.
ALGORITHM_RANK = {"nested_loop": 0, "hash_join": 1, "merge_join": 2}


# --------------------------------------------------------------------------- statistics
@dataclass(frozen=True)
class Predicate:
    """A filter predicate. Carries its own selectivity factor — the planner
    never inspects data, it only multiplies factors (independence assumption)."""
    column: str
    selectivity: float


@dataclass
class Relation:
    name: str
    rows: int
    row_width: int                                   # bytes per row
    predicates: tuple[Predicate, ...] = ()
    sorted_key: str | None = None                    # non-None => arrives pre-sorted on this key

    @property
    def selectivity(self) -> float:
        """Product of all predicate selectivities (independence assumption)."""
        s = 1.0
        for p in self.predicates:
            s *= p.selectivity
        return s

    @property
    def est_rows(self) -> float:
        """Estimated rows AFTER local filters are applied."""
        return self.rows * self.selectivity


# --------------------------------------------------------------------------- page math
def pages(rows: float, row_width: int) -> int:
    """Heap pages holding `rows` rows of `row_width` bytes each. 0 rows => 0 pages."""
    if rows <= 0:
        return 0
    return math.ceil(rows * row_width / PAGE_SIZE)


# --------------------------------------------------------------------------- scan costing
def seq_scan_cost(rel: Relation) -> float:
    """Full sequential scan: read every page once."""
    return float(pages(rel.est_rows, rel.row_width))


def index_scan_cost(rel: Relation, selectivity: float,
                    idx_height: int = IDX_DEFAULT_HEIGHT,
                    idx_keys: int | None = None) -> float:
    """Index scan: descend the tree (`idx_height`), then pay per matched row a
    clustering penalty of rows/idx_keys (the average rows per key value; a
    unique index has idx_keys == rows, i.e. penalty 1.0 per matched row)."""
    keys = rel.rows if idx_keys is None else idx_keys
    fanout = (rel.rows / keys) if keys > 0 else 0.0
    matched = rel.est_rows * selectivity
    return idx_height + matched * fanout


# --------------------------------------------------------------------------- join costing
def nested_loop_cost(outer_rows: float, inner_rows: float,
                     outer_width: int, inner_width: int) -> float:
    """Read outer once, then re-read the inner's pages once per outer row."""
    return float(pages(outer_rows, outer_width)) + outer_rows * pages(inner_rows, inner_width)


def hash_join_cost(build_rows: float, build_width: int,
                   probe_rows: float, probe_width: int) -> float:
    """Each input read once (build side becomes the hash table), plus a small
    per-build-row overhead for inserting into / probing the table."""
    return (pages(build_rows, build_width) + pages(probe_rows, probe_width)
            + HASH_FIXED_COST + HASH_ROW_COST * build_rows)


def sort_cost(rows: float, row_width: int) -> float:
    """External merge sort: O(n log n) modeled as SORT_PAGE_FACTOR * pages * log2(pages)."""
    p = max(pages(rows, row_width), 1)
    return SORT_PAGE_FACTOR * p * math.log2(max(p, 2))


def merge_join_cost(a_rows: float, b_rows: float, a_width: int, b_width: int,
                    a_sorted: bool, b_sorted: bool) -> float:
    """Near-linear lockstep walk — but BOTH inputs must be sorted on the join
    key first, and each unsorted input pays an O(n log n) Sort."""
    cost = MERGE_ROW_COST * (a_rows + b_rows)
    if not a_sorted:
        cost += sort_cost(a_rows, a_width)
    if not b_sorted:
        cost += sort_cost(b_rows, b_width)
    return cost


# --------------------------------------------------------------------------- plan object
@dataclass
class Plan:
    algorithm: str                       # winning join algorithm (or "seq_scan"/"index_scan")
    est_rows: float                      # estimated output rows
    cost: float                          # estimated total cost
    steps: list[str] = field(default_factory=list)   # EXPLAIN-style operation lines
    order: tuple[str, ...] = ()          # relation names in left-deep execution order


@dataclass
class Candidate:
    algo: str
    cost: float
    est_rows: float
    steps: list[str]
    preserves_sorted: bool               # only merge join keeps its output sorted


def scan_plan(rel: Relation, method: str = "seq",
              selectivity: float = 1.0,
              idx_height: int = IDX_DEFAULT_HEIGHT,
              idx_keys: int | None = None) -> Plan:
    """Single-relation access-path plan (useful standalone, and keeps the
    renderer happy on queries with no join at all)."""
    if method == "index":
        cost = index_scan_cost(rel, selectivity, idx_height, idx_keys)
        rows = rel.est_rows * selectivity
        return Plan("index_scan", rows, cost,
                    [f"Index Scan on {rel.name} (height={idx_height})"], (rel.name,))
    return Plan("seq_scan", rel.est_rows, seq_scan_cost(rel),
                [f"Seq Scan on {rel.name} (est rows={_fmt(rel.est_rows)})"], (rel.name,))


def _fmt(x: float) -> str:
    return f"{x:g}"


def _join_candidates(name_a: str, rows_a: float, width_a: int, a_sorted: bool,
                     name_b: str, rows_b: float, width_b: int, b_sorted: bool,
                     join_sel: float) -> list[Candidate]:
    """Enumerate the physical strategies for one join. Cardinality estimate is
    the SAME for every strategy: rows_a * rows_b * join_sel."""
    est = rows_a * rows_b * join_sel
    pa, pb = pages(rows_a, width_a), pages(rows_b, width_b)
    out: list[Candidate] = []

    # nested loop: try both orientations, keep the cheaper (tie: a is outer)
    c_ab = pa + rows_a * pb
    c_ba = pb + rows_b * pa
    if c_ab <= c_ba:
        out.append(Candidate("nested_loop", c_ab, est,
                             [f"Seq Scan on {name_a} (est rows={_fmt(rows_a)})",
                              f"Seq Scan on {name_b} (est rows={_fmt(rows_b)})",
                              f"Nested Loop Join: {name_a} JOIN {name_b}"], False))
    else:
        out.append(Candidate("nested_loop", c_ba, est,
                             [f"Seq Scan on {name_b} (est rows={_fmt(rows_b)})",
                              f"Seq Scan on {name_a} (est rows={_fmt(rows_a)})",
                              f"Nested Loop Join: {name_b} JOIN {name_a}"], False))

    # hash join: build on the smaller estimated side (tie: a builds)
    if rows_a <= rows_b:
        bn, br, bw, pn, pr, pw = name_a, rows_a, width_a, name_b, rows_b, width_b
    else:
        bn, br, bw, pn, pr, pw = name_b, rows_b, width_b, name_a, rows_a, width_a
    hj = (pages(br, bw) + pages(pr, pw)
          + HASH_FIXED_COST + HASH_ROW_COST * br)
    out.append(Candidate("hash_join", hj, est,
                         [f"Seq Scan on {pn} (probe, est rows={_fmt(pr)})",
                          f"Hash Build on {bn} (est rows={_fmt(br)})",
                          f"Hash Join: {name_a} JOIN {name_b}"], False))

    # merge join: near-linear IF both sides arrive sorted, else pay the sorts
    mj = MERGE_ROW_COST * (rows_a + rows_b)
    m_steps = []
    if not a_sorted:
        mj += sort_cost(rows_a, width_a)
        m_steps.append(f"Sort {name_a} by join key (est rows={_fmt(rows_a)})")
    if not b_sorted:
        mj += sort_cost(rows_b, width_b)
        m_steps.append(f"Sort {name_b} by join key (est rows={_fmt(rows_b)})")
    m_steps.append(f"Merge Join: {name_a} JOIN {name_b}")
    out.append(Candidate("merge_join", mj, est, m_steps, True))

    return out


def _pick(candidates: Sequence[Candidate]) -> Candidate:
    """Lowest cost wins; equal costs break by ALGORITHM_RANK (deterministic)."""
    return min(candidates, key=lambda c: (c.cost, ALGORITHM_RANK[c.algo]))


# --------------------------------------------------------------------------- two-way join
def plan_join(rel_a: Relation, rel_b: Relation,
              join_sel: float = DEFAULT_JOIN_SEL,
              algorithms_available: Iterable[str] = ALGORITHMS) -> Plan:
    """Cost every available physical strategy for `rel_a JOIN rel_b` and return
    the cheapest-looking one. est_rows is EXACTLY rel_a.est_rows *
    rel_b.est_rows * join_sel — the independence assumption in one line."""
    avail = tuple(algorithms_available)
    if not avail:
        raise ValueError("no join algorithms available")
    unknown = sorted({a for a in avail if a not in ALGORITHM_RANK})
    if unknown:
        raise ValueError(f"unknown algorithm(s) {unknown}; known: {sorted(ALGORITHM_RANK)}")

    ra, rb = rel_a.est_rows, rel_b.est_rows
    cands = [c for c in _join_candidates(rel_a.name, ra, rel_a.row_width,
                                         rel_a.sorted_key is not None,
                                         rel_b.name, rb, rel_b.row_width,
                                         rel_b.sorted_key is not None, join_sel)
             if c.algo in avail]
    best = _pick(cands)
    return Plan(best.algo, ra * rb * join_sel, best.cost, best.steps,
                (rel_a.name, rel_b.name))


# --------------------------------------------------------------------------- multi-join search
def _norm_key(key) -> frozenset[str]:
    return frozenset(key)


def _edge_sel(join_sels: Mapping[frozenset[str], float],
              left_names: frozenset[str], right_name: str) -> float:
    """Selectivity for joining an accumulated result with one more relation.

    An exact composite key ({all left names} | {right}) wins; otherwise the
    edges connecting `right_name` to each left member multiply together
    (independence again); no edges at all falls back to DEFAULT_JOIN_SEL."""
    exact = left_names | {right_name}
    if exact in join_sels:
        return join_sels[exact]
    prod, found = 1.0, False
    for m in sorted(left_names):
        edge = frozenset((m, right_name))
        if edge in join_sels:
            prod *= join_sels[edge]
            found = True
    return prod if found else DEFAULT_JOIN_SEL


@dataclass
class _Acc:
    cost: float
    est_rows: float
    width: int
    steps: list[str]
    last_algo: str
    sorted_flag: bool

    def key(self) -> tuple:
        return (self.cost, ALGORITHM_RANK.get(self.last_algo, len(ALGORITHM_RANK)))


def _extend(acc: _Acc, relmap: Mapping[str, Relation], next_name: str,
            join_sels: Mapping[frozenset[str], float], prefix: tuple[str, ...]) -> _Acc:
    nxt = relmap[next_name]
    sel = _edge_sel(join_sels, frozenset(prefix), next_name)
    cands = _join_candidates("+".join(prefix), acc.est_rows, acc.width, acc.sorted_flag,
                             next_name, nxt.est_rows, nxt.row_width,
                             nxt.sorted_key is not None, sel)
    best = _pick(cands)
    return _Acc(acc.cost + best.cost, best.est_rows, acc.width + nxt.row_width,
                acc.steps + best.steps, best.algo, best.preserves_sorted)


def candidate_orders(names: Sequence[str]):
    """The LEFT-DEEP search space: every permutation of relation names. Bushy
    trees are unreachable by construction — each step extends the accumulated
    result with exactly ONE base relation, never composite x composite."""
    return itertools.permutations(sorted(names))


def _start_state(rel: Relation, name: str) -> _Acc:
    return _Acc(seq_scan_cost(rel), rel.est_rows, rel.row_width,
                [f"Seq Scan on {name} (est rows={_fmt(rel.est_rows)})"],
                "seq_scan", rel.sorted_key is not None)


def best_order(rels: Sequence[Relation],
               join_sels: Mapping[Mapping[str, str] | frozenset[str], float],
               beam_width: int | None = DEFAULT_BEAM_WIDTH) -> Plan:
    """Cheapest left-deep join order for 2..6 relations.

    Selinger-style DP over prefixes with greedy pruning: at each depth only the
    `beam_width` cheapest partial plans survive (None = exhaustive). Equal
    totals break by ALGORITHM_RANK of the root join, then by name order —
    so the answer is fully deterministic."""
    relmap = {r.name: r for r in rels}
    names = sorted(relmap)
    if not names:
        raise ValueError("best_order needs at least one relation")
    if len(names) != len(rels):
        raise ValueError("duplicate relation names")
    if len(names) > MAX_SEARCH_RELATIONS:
        raise ValueError(f"left-deep exhaustive search capped at {MAX_SEARCH_RELATIONS} relations")
    sels = {_norm_key(k): float(v) for k, v in join_sels.items()}

    states: dict[tuple[str, ...], _Acc] = {
        (n,): _start_state(relmap[n], n) for n in names
    }
    for _ in range(len(names) - 1):
        nxt: dict[tuple[str, ...], _Acc] = {}
        for prefix, acc in sorted(states.items()):          # sorted => deterministic
            for cand in names:
                if cand in prefix:
                    continue
                new_order = prefix + (cand,)
                cand_acc = _extend(acc, relmap, cand, sels, prefix)
                cur = nxt.get(new_order)
                if cur is None or cand_acc.key() < cur.key():
                    nxt[new_order] = cand_acc
        if beam_width is not None and len(nxt) > beam_width:
            keep = sorted(nxt.items(), key=lambda kv: (kv[1].key(), kv[0]))[:beam_width]
            nxt = dict(keep)
        states = nxt

    final_order, final = min(states.items(), key=lambda kv: (kv[1].key(), kv[0]))
    return Plan(final.last_algo, final.est_rows, final.cost, final.steps, final_order)


def brute_force_best_order(rels: Sequence[Relation],
                           join_sels: Mapping[Mapping[str, str] | frozenset[str], float]) -> Plan:
    """Reference enumerator: EVERY left-deep order simulated end-to-end, no
    pruning. Small instances must agree with best_order exactly."""
    relmap = {r.name: r for r in rels}
    names = sorted(relmap)
    sels = {_norm_key(k): float(v) for k, v in join_sels.items()}
    best: tuple[tuple, _Acc] | None = None
    for order in candidate_orders(names):
        acc = _start_state(relmap[order[0]], order[0])
        for i in range(1, len(order)):
            acc = _extend(acc, relmap, order[i], sels, order[:i])
        key = (acc.key(), order)
        if best is None or key < best[0]:
            best = (key, acc)
    assert best is not None
    key, acc = best
    return Plan(acc.last_algo, acc.est_rows, acc.cost, acc.steps, key[1])


# --------------------------------------------------------------------------- EXPLAIN renderer
def explain(plan: Plan) -> str:
    """EXPLAIN-style aligned text table: one row per plan step, columns
    ALGORITHM | EST_ROWS | COST | OPERATION. Safe on scan-only plans."""
    ops = plan.steps or [f"{plan.algorithm} on {'+'.join(plan.order) if plan.order else '-'}"]
    header = ("ALGORITHM", "EST_ROWS", "COST", "OPERATION")
    body = [(plan.algorithm, f"{plan.est_rows:.1f}", f"{plan.cost:.2f}", op) for op in ops]
    widths = [max(len(header[i]), *(len(row[i]) for row in body)) for i in range(4)]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(cells[i].ljust(widths[i]) for i in range(len(cells)))

    total = sum(widths) + 2 * (len(widths) - 1)
    lines = ["QUERY PLAN".ljust(total), line(header)]
    lines.extend(line(row) for row in body)
    return "\n".join(lines)
