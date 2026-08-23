"""Lab 18 tests. No data, no randomness — the planner only ever sees statistics,
so every fixture asserts EXACT numbers (or tight approx where log2 is involved)."""
import itertools
import math

import pytest


def _rel(R, name, rows, width, preds=(), sorted_key=None):
    return R.Relation(name, rows, width, tuple(preds), sorted_key)


# ------------------------------------------------------------------ statistics
def test_predicate_selectivities_multiply_into_effective_rows(R):
    """The independence assumption in one line: selectivities simply multiply."""
    t = _rel(R, "t", 1000, 8, preds=[R.Predicate("city", 0.1), R.Predicate("state", 0.5)])
    assert t.selectivity == pytest.approx(0.05)
    assert t.est_rows == 50.0


# ------------------------------------------------------------------ page math
def test_pages_exact_page_math(R):
    assert R.pages(1024, 8) == 1            # exactly one page: 1024*8 == PAGE_SIZE
    assert R.pages(1025, 8) == 2            # one row spills into a second page
    assert R.pages(8192, 1) == 1
    assert R.pages(8193, 1) == 2
    assert R.pages(0, 999) == 0             # empty table reads nothing


def test_seq_scan_cost_is_page_count(R):
    users = _rel(R, "users", 4000, 20)      # 80_000 bytes -> ceil(9.77) -> 10 pages
    assert R.seq_scan_cost(users) == 10.0


def test_index_scan_cost_formula_exact(R):
    """cost = idx_height + matched_rows * (rows/idx_keys); unique index => penalty 1."""
    users = _rel(R, "users", 4000, 20)
    # sel=0.001 over a unique-ish index: matched = 4000*0.001 = 4 rows, fanout 4000/4000 = 1
    assert R.index_scan_cost(users, 0.001) == pytest.approx(3 + 4.0)
    assert R.index_scan_cost(users, 0.001, idx_height=4) == pytest.approx(4 + 4.0)
    # low-cardinality key: 100 distinct keys => fanout 40 => each match costs 40x
    assert R.index_scan_cost(users, 0.001, idx_keys=100) == pytest.approx(3 + 4 * 40)


def test_index_scan_cost_grows_with_selectivity(R):
    users = _rel(R, "users", 4000, 20)
    cheap = R.index_scan_cost(users, 0.0001)
    mid = R.index_scan_cost(users, 0.01)
    full = R.index_scan_cost(users, 0.5)
    assert cheap < mid < full
    # at some selectivity the random-access penalty beats a straight seq scan
    seq = R.seq_scan_cost(users)
    assert cheap < seq < full


# ------------------------------------------------------------------ join algorithm costs
def test_nested_loop_cost_formula(R):
    # pages(50, 80) = 1, pages(500, 80) = 5 -> 1 + 50*5
    assert R.nested_loop_cost(50, 500, 80, 80) == 1 + 50 * 5
    # the outer's own pages are paid once; inner's pages once PER OUTER ROW
    assert R.nested_loop_cost(10_000, 500, 8, 800) == 10 + 10_000 * 49


def test_hash_join_reads_each_side_once(R):
    # build 100x80 -> 1 page; probe 5000x8 -> 5 pages; + 25 fixed + 0.02*100
    expected = 1 + 5 + R.HASH_FIXED_COST + R.HASH_ROW_COST * 100
    assert R.hash_join_cost(100, 80, 5000, 8) == pytest.approx(expected)


def test_sort_cost_is_n_log_n(R):
    p = R.pages(10_000, 40)
    assert p == 49
    assert R.sort_cost(10_000, 40) == pytest.approx(R.SORT_PAGE_FACTOR * p * math.log2(p))
    # superlinear-but-near-linear growth: 10x rows cost ~15x (n log n factor)
    small = R.sort_cost(100_000, 8)      # 98 pages
    big = R.sort_cost(1_000_000, 8)      # 977 pages
    assert 13 * small < big < 17 * small


# ------------------------------------------------------------------ two-way plan choice
def _crossover_pair(R, outer_rows):
    outer = _rel(R, "s", outer_rows, 80)
    inner = _rel(R, "big", 500, 80)          # pages(inner) == 5
    return outer, inner


def test_nl_vs_hash_crossover_point_is_numeric(R):
    """With pages(inner)=5 and hash overhead ~31+0.02o vs NL 1+5o, the models
    cross between o=6 (NL 31.00 < HJ 31.12) and o=7 (NL 36 > HJ 31.14).
    Small outer favors nested loop; past the crossover hash takes over."""
    for o in range(1, 7):
        outer, inner = _crossover_pair(R, o)
        nl = R.nested_loop_cost(o, 500, 80, 80)
        hj = R.hash_join_cost(o, 80, 500, 80)
        assert nl < hj, f"outer={o}: model says NL must still win"
        assert R.plan_join(outer, inner, 1.0).algorithm == "nested_loop"
    for o in range(7, 13):
        outer, inner = _crossover_pair(R, o)
        nl = R.nested_loop_cost(o, 500, 80, 80)
        hj = R.hash_join_cost(o, 80, 500, 80)
        assert hj < nl, f"outer={o}: model says HJ must have taken over"
        assert R.plan_join(outer, inner, 1.0).algorithm == "hash_join"


def test_merge_join_wins_when_both_inputs_sorted(R):
    a = _rel(R, "a", 10_000, 40, sorted_key="k")   # 49 pages
    b = _rel(R, "b", 20_000, 40, sorted_key="k")   # 98 pages
    plan = R.plan_join(a, b, 0.001)
    assert plan.algorithm == "merge_join"
    # near-linear: no Sort nodes, just MERGE_ROW_COST per input row
    assert plan.cost == pytest.approx(R.MERGE_ROW_COST * 30_000)
    assert all("Sort" not in s for s in plan.steps)
    # and it really is cheaper than what hash would charge here
    hj = R.hash_join_cost(a.est_rows, 40, b.est_rows, 40)
    assert plan.cost < hj


def test_unsorted_inputs_force_sort_nodes_and_lose_to_hash(R):
    a = _rel(R, "a", 10_000, 40)
    b = _rel(R, "b", 20_000, 40)
    forced = R.plan_join(a, b, 0.001, algorithms_available=["merge_join"])
    assert forced.algorithm == "merge_join"
    sorts = [s for s in forced.steps if "Sort" in s]
    assert len(sorts) == 2, "both inputs arrive unsorted — two Sort nodes required"
    expected = (R.MERGE_ROW_COST * 30_000
                + R.sort_cost(10_000, 40) + R.sort_cost(20_000, 40))
    assert forced.cost == pytest.approx(expected)
    # paying n log n to enable O(n+m) is worse than hash's plain build+probe here
    free_choice = R.plan_join(a, b, 0.001)
    assert free_choice.algorithm == "hash_join"
    assert free_choice.cost < forced.cost


def test_selectivity_changes_the_winner(R):
    """Same tables, one filter: the planner flips hash join -> nested loop.
    This IS the stale-statistics failure mode from the module."""
    fact = _rel(R, "fact", 100_000, 80)     # 977 pages
    dim = _rel(R, "dim", 2000, 80)          # 20 pages
    assert R.plan_join(fact, dim, 0.01).algorithm == "hash_join"

    filtered_fact = _rel(R, "fact", 100_000, 80, preds=[R.Predicate("fk", 0.00002)])
    assert filtered_fact.est_rows == 2.0
    plan = R.plan_join(filtered_fact, dim, 0.01)
    assert plan.algorithm == "nested_loop"
    # numeric proof: 1 + 2*20 beats hash's 1+20+25+0.02*2
    assert R.nested_loop_cost(2.0, 2000, 80, 80) < R.hash_join_cost(2.0, 80, 2000, 80)
    assert plan.est_rows == pytest.approx(2.0 * 2000 * 0.01)


def test_plan_join_est_rows_formula_exact(R):
    u, o = _rel(R, "u", 1000, 8), _rel(R, "o", 500, 8)
    plan = R.plan_join(u, o, 0.125)
    assert plan.est_rows == 62_500.0                       # 1000*500*0.125, dyadic-exact
    filtered_u = _rel(R, "u", 1000, 8, preds=[R.Predicate("flag", 0.5)])
    assert R.plan_join(filtered_u, o, 0.125).est_rows == 31_250.0
    # cardinality does not depend on which physical strategy wins
    assert R.plan_join(u, o, 0.125, algorithms_available=["merge_join"]).est_rows == 62_500.0


def test_plan_join_honors_algorithms_available(R):
    a = _rel(R, "a", 10_000, 40)
    b = _rel(R, "b", 20_000, 40)
    plan = R.plan_join(a, b, 0.001, algorithms_available=("nested_loop", "hash_join"))
    assert plan.algorithm in ("nested_loop", "hash_join")
    merge_only = R.plan_join(a, b, 0.001, algorithms_available=["merge_join"])
    assert merge_only.algorithm == "merge_join"          # even though it is not cheapest
    with pytest.raises(ValueError):
        R.plan_join(a, b, 0.001, algorithms_available=[])
    with pytest.raises(ValueError):
        R.plan_join(a, b, 0.001, algorithms_available=["cartesian_blessing"])


def test_hash_build_side_is_the_smaller_input(R):
    big = _rel(R, "big", 50_000, 40)
    tiny = _rel(R, "tiny", 300, 40)
    plan = R.plan_join(big, tiny, 0.5)
    assert plan.algorithm == "hash_join"
    build_line = next(s for s in plan.steps if "Hash Build on" in s)
    assert "tiny" in build_line                          # smaller side becomes the hash table


# ------------------------------------------------------------------ multi-join search
def test_candidate_orders_are_left_deep_permutations_only(R):
    orders = list(R.candidate_orders(["c", "a", "b"]))
    assert len(orders) == 6                              # 3! left-deep orders...
    assert set(orders) == set(itertools.permutations(("a", "b", "c")))
    # ...and never composite x composite: each step extends by ONE base relation
    for o in orders:
        assert len(set(o)) == len(o)


def test_best_order_matches_brute_force_on_three_relations(R):
    rels = [_rel(R, "a", 1000, 32), _rel(R, "b", 6000, 64), _rel(R, "c", 900, 48)]
    sels = {frozenset({"a", "b"}): 0.01,
            frozenset({"b", "c"}): 0.005,
            frozenset({"a", "c"}): 0.2}
    fast = R.best_order(rels, sels)
    brute = R.brute_force_best_order(rels, sels)
    assert fast.order == brute.order
    assert fast.cost == pytest.approx(brute.cost)
    assert fast.est_rows == pytest.approx(brute.est_rows)
    assert fast.steps == brute.steps
    # the returned object IS a full Plan with every column filled
    assert isinstance(fast, R.Plan) and fast.order and fast.steps


def test_best_order_ties_break_deterministically(R):
    """Three identical relations and identical edge selectivities: all six
    left-deep orders cost exactly the same (dyadic floats, bit-equal totals).
    The winner must be stable across calls and lexicographically first."""
    rels = [_rel(R, name, 4096, 64) for name in ("a", "b", "c")]
    sels = {frozenset(pair): 0.125 for pair in (("a", "b"), ("a", "c"), ("b", "c"))}
    first = R.best_order(rels, sels)
    again = R.best_order(rels, sels)
    assert first == again                                # same algorithm, cost, steps, order
    assert first.order == ("a", "b", "c")


def test_best_order_prefers_small_intermediates(R):
    """Join selectivities steer the order: start with the pair whose join
    nearly annihilates the intermediate (a x c has sel 1e-6)."""
    rels = [_rel(R, "a", 100, 8), _rel(R, "b", 100_000, 8), _rel(R, "c", 100_000, 8)]
    sels = {frozenset({"a", "b"}): 1.0,
            frozenset({"a", "c"}): 1e-6,
            frozenset({"b", "c"}): 1.0}
    plan = R.best_order(rels, sels)
    assert plan.order == ("a", "c", "b")
    brute = R.brute_force_best_order(rels, sels)
    assert plan.order == brute.order                     # genuinely the global optimum
    assert plan.est_rows == pytest.approx(100 * 100_000 * 1e-6 * 100_000)


def test_edge_selectivity_composite_rule(R):
    """Composite joins multiply the edges into the new relation; a fully
    unknown neighborhood falls back to DEFAULT_JOIN_SEL."""
    sels = {frozenset({"a", "b"}): 0.5, frozenset({"b", "c"}): 0.2,
            frozenset({"a", "c"}): 0.4}
    # joining {a,b} with c multiplies the edges INTO c: (a,c)=0.4 and (b,c)=0.2
    assert R._edge_sel(sels, frozenset({"a", "b"}), "c") == pytest.approx(0.4 * 0.2)
    assert R._edge_sel(sels, frozenset({"a"}), "b") == pytest.approx(0.5)
    assert R._edge_sel(sels, frozenset({"a"}), "z") == R.DEFAULT_JOIN_SEL


def test_best_order_single_relation_and_hard_cap(R):
    users = _rel(R, "users", 4000, 20)
    plan = R.best_order([users], {})
    assert plan.order == ("users",)
    assert plan.cost == R.seq_scan_cost(users)
    assert plan.steps                                    # renderer fodder exists
    many = [_rel(R, f"r{i}", 10, 8) for i in range(7)]
    with pytest.raises(ValueError):
        R.best_order(many, {})


# ------------------------------------------------------------------ EXPLAIN renderer
def test_explain_renders_all_columns_aligned(R):
    a = _rel(R, "a", 10_000, 40)
    b = _rel(R, "b", 20_000, 40)
    plan = R.plan_join(a, b, 0.001)
    out = R.explain(plan)
    lines = out.splitlines()
    assert lines[0].strip() == "QUERY PLAN"
    header = lines[1]
    for col in ("ALGORITHM", "EST_ROWS", "COST", "OPERATION"):
        assert col in header
    # aligned means padded: every line occupies exactly the same width
    assert len({len(line) for line in lines}) == 1
    # one row per step, carrying the plan's numbers
    assert len(lines) == len(plan.steps) + 2
    assert plan.algorithm in out
    assert f"{plan.cost:.2f}" in out


def test_explain_handles_single_relation_plan(R):
    users = _rel(R, "users", 4000, 20)
    for plan in (R.scan_plan(users),
                 R.scan_plan(users, method="index", selectivity=0.001),
                 R.best_order([users], {})):
        out = R.explain(plan)
        lines = out.splitlines()
        assert len({len(line) for line in lines}) == 1
        assert "users" in out
        assert f"{plan.cost:.2f}" in out
