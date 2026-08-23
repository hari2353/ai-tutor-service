"""Lab 18 — cost-based join planner toy. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. Costs are floats derived ONLY from statistics — no data, no
    sampling, no randomness. Same stats in, same plan out.
  * The planner never sees actual rows; est_rows is the independence assumption:
    filter selectivities and join selectivities simply multiply.
  * Ties break deterministically: lower ALGORITHM_RANK wins, then name order.
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
ALGORITHM_RANK = {"nested_loop": 0, "hash_join": 1, "merge_join": 2}   # tie-break order


# --------------------------------------------------------------------------- statistics
@dataclass(frozen=True)
class Predicate:
    """A filter predicate carrying its own selectivity factor."""
    column: str
    selectivity: float


@dataclass
class Relation:
    """Base-table statistics: the only thing a cost-based planner ever sees."""
    name: str
    rows: int
    row_width: int                                   # bytes per row
    predicates: tuple[Predicate, ...] = ()
    sorted_key: str | None = None                    # non-None => arrives pre-sorted on this key

    @property
    def selectivity(self) -> float:
        """Product of all predicate selectivities (independence assumption)."""
        # TODO(step 1a): multiply every predicate's selectivity together (start at 1.0)
        raise NotImplementedError

    @property
    def est_rows(self) -> float:
        """Estimated rows AFTER local filters are applied."""
        # TODO(step 1b): rows * selectivity
        raise NotImplementedError


# --------------------------------------------------------------------------- page math
def pages(rows: float, row_width: int) -> int:
    """Heap pages holding `rows` rows of `row_width` bytes each.

    pages = ceil(rows * row_width / PAGE_SIZE), and 0 rows => 0 pages.
    Every other cost in this lab bottoms out here."""
    # TODO(step 2a)
    raise NotImplementedError


# --------------------------------------------------------------------------- scan costing
def seq_scan_cost(rel: Relation) -> float:
    """Full sequential scan: read every page once."""
    # TODO(step 2b): pages(rel.est_rows, rel.row_width)
    raise NotImplementedError


def index_scan_cost(rel: Relation, selectivity: float,
                    idx_height: int = IDX_DEFAULT_HEIGHT,
                    idx_keys: int | None = None) -> float:
    """Index scan: descend the tree (`idx_height` levels), then pay per matched
    row a clustering penalty of rows/idx_keys — the average rows per key value.
    idx_keys defaults to rel.rows (unique index => penalty exactly 1.0).

        cost = idx_height + matched_rows * (rows / idx_keys)

    where matched_rows = rel.est_rows * selectivity (the predicate driving THIS
    index is passed in; any table-level predicates are already inside est_rows)."""
    # TODO(step 2c)
    raise NotImplementedError


# --------------------------------------------------------------------------- join costing
def nested_loop_cost(outer_rows: float, inner_rows: float,
                     outer_width: int, inner_width: int) -> float:
    """Read outer's pages once, then re-read inner's pages once PER OUTER ROW:

        cost = pages(outer) + outer_rows * pages(inner)

    Brutal without an index on the inner side — that is why small outers win."""
    # TODO(step 3a)
    raise NotImplementedError


def hash_join_cost(build_rows: float, build_width: int,
                   probe_rows: float, probe_width: int) -> float:
    """Each input read exactly once (build side becomes the hash table):

        cost = pages(build) + pages(probe) + HASH_FIXED_COST + HASH_ROW_COST*build_rows"""
    # TODO(step 3b)
    raise NotImplementedError


def sort_cost(rows: float, row_width: int) -> float:
    """External merge sort, O(n log n) modeled as:

        cost = SORT_PAGE_FACTOR * max(pages,1) * log2(max(pages,2))"""
    # TODO(step 3c)
    raise NotImplementedError


def merge_join_cost(a_rows: float, b_rows: float, a_width: int, b_width: int,
                    a_sorted: bool, b_sorted: bool) -> float:
    """Near-linear lockstep walk over two sorted streams:

        base = MERGE_ROW_COST * (a_rows + b_rows)
        plus sort_cost for EACH unsorted input — merge join requires sort keys."""
    # TODO(step 3d)
    raise NotImplementedError


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


def _fmt(x: float) -> str:
    return f"{x:g}"


def _join_candidates(name_a: str, rows_a: float, width_a: int, a_sorted: bool,
                     name_b: str, rows_b: float, width_b: int, b_sorted: bool,
                     join_sel: float) -> list[Candidate]:
    """Enumerate ALL physical strategies for one join. The cardinality estimate
    is IDENTICAL for every strategy: rows_a * rows_b * join_sel.

      * nested_loop — try both orientations, keep the cheaper (tie: a is outer).
      * hash_join   — build on the SMALLER estimated side (tie: a builds);
                      steps must name the build side via 'Hash Build on <name>'.
      * merge_join  — near-linear if both inputs sorted, else prepend one
                      'Sort <name> by join key ...' step per unsorted input;
                      it is the only candidate with preserves_sorted=True.
    Steps order scans first, then Sort lines (merge only), then the join line."""
    # TODO(step 4a): build and return [Candidate(nested_loop...), Candidate(hash_join...),
    #                 Candidate(merge_join...)] using nested_loop_cost / hash_join_cost /
    #                 merge_join_cost. est_rows identical on all three.
    raise NotImplementedError


def _pick(candidates: Sequence[Candidate]) -> Candidate:
    """Lowest cost wins; equal costs break by ALGORITHM_RANK (deterministic)."""
    # TODO(step 4b): min by (cost, ALGORITHM_RANK[algo])
    raise NotImplementedError


def scan_plan(rel: Relation, method: str = "seq",
              selectivity: float = 1.0,
              idx_height: int = IDX_DEFAULT_HEIGHT,
              idx_keys: int | None = None) -> Plan:
    """Single-relation access-path plan ('seq' or 'index'). Algorithm names:
    'seq_scan' / 'index_scan'; steps carry one human-readable operation line."""
    # TODO(step 5)
    raise NotImplementedError


# --------------------------------------------------------------------------- two-way join
def plan_join(rel_a: Relation, rel_b: Relation,
              join_sel: float = DEFAULT_JOIN_SEL,
              algorithms_available: Iterable[str] = ALGORITHMS) -> Plan:
    """Cost every available physical strategy for `rel_a JOIN rel_b` and return
    the cheapest-looking one.

      * est_rows is EXACTLY rel_a.est_rows * rel_b.est_rows * join_sel.
      * algorithms_available restricts the menu (e.g. ('merge_join',)).
      * empty menu or unknown algorithm names => ValueError."""
    # TODO(step 6): validate availability, filter _join_candidates output,
    #               pick the winner, wrap it in a Plan with order=(rel_a.name, rel_b.name)
    raise NotImplementedError


# --------------------------------------------------------------------------- multi-join search
def _norm_key(key) -> frozenset[str]:
    return frozenset(key)


def _edge_sel(join_sels: Mapping[frozenset[str], float],
              left_names: frozenset[str], right_name: str) -> float:
    """Selectivity for joining an ACCUMULATED result with one more relation:

      1. exact composite key ({all left names} | {right_name}) wins if present;
      2. else multiply every edge connecting right_name to each left member
         (independence again);
      3. no edges at all => DEFAULT_JOIN_SEL."""
    # TODO(step 7a)
    raise NotImplementedError


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
    """Join the accumulated result with ONE more base relation (this is what
    makes the search space left-deep-only: never composite x composite).
    Widths add up; sortedness survives only through merge joins."""
    # TODO(step 7b): use _edge_sel + _join_candidates + _pick; accumulate cost/steps/width
    raise NotImplementedError


def candidate_orders(names: Sequence[str]):
    """The LEFT-DEEP search space: every permutation of relation names (sorted
    input => deterministic yield order). Bushy trees are unreachable because
    each step adds exactly one base relation."""
    # TODO(step 7c): itertools.permutations(sorted(names))
    raise NotImplementedError


def _start_state(rel: Relation, name: str) -> _Acc:
    return _Acc(seq_scan_cost(rel), rel.est_rows, rel.row_width,
                [f"Seq Scan on {name} (est rows={_fmt(rel.est_rows)})"],
                "seq_scan", rel.sorted_key is not None)


def best_order(rels: Sequence[Relation],
               join_sels: Mapping[Mapping[str, str] | frozenset[str], float],
               beam_width: int | None = DEFAULT_BEAM_WIDTH) -> Plan:
    """Cheapest left-deep join order for up to MAX_SEARCH_RELATIONS relations.

    Selinger-style DP over prefixes, greedy-pruned: after each depth keep only
    the beam_width cheapest partial plans (None => exhaustive). Final choice
    sorts by _Acc.key() then the order tuple itself — fully deterministic.
    Raises ValueError for empty/duplicated input or too many relations."""
    # TODO(step 7d): level-by-level expansion over candidate_orders-style prefixes
    raise NotImplementedError


def brute_force_best_order(rels: Sequence[Relation],
                           join_sels: Mapping[Mapping[str, str] | frozenset[str], float]) -> Plan:
    """Reference enumerator: simulate EVERY left-deep order end-to-end with no
    pruning. Small instances must agree with best_order exactly."""
    # TODO(step 7e)
    raise NotImplementedError


# --------------------------------------------------------------------------- EXPLAIN renderer
def explain(plan: Plan) -> str:
    """EXPLAIN-like aligned text table. Header row ALGORITHM | EST_ROWS | COST |
    OPERATION, then one row per plan step (values repeated per row). Every line
    padded to the same width; must not crash when plan.steps is empty (fall
    back to a single synthesized row)."""
    # TODO(step 8)
    raise NotImplementedError
