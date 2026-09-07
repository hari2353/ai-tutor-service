"""Lab 04 tests: selectivity, index selection, pushdown, join choice,
and optimized-plan-equals-naive-plan row equality."""
import pytest


# ---------------------------------------------------------------- fixtures
def make_users(P, n=20):
    rows = [{"id": i, "name": f"u{i}", "age": 20 + i, "city": f"c{i % 5}"}
            for i in range(n)]
    stats = {"id": {"ndistinct": n, "min": 0, "max": n - 1},
             "age": {"ndistinct": n, "min": 20, "max": 20 + n - 1},
             "city": {"ndistinct": 5, "min": None, "max": None}}
    return P.Table("users", rows, stats)


def make_orders(P, n=60):
    rows = [{"oid": i, "user_id": i % 20, "total": i * 10}
            for i in range(n)]
    stats = {"oid": {"ndistinct": n, "min": 0, "max": n - 1},
             "user_id": {"ndistinct": 20, "min": 0, "max": 19},
             "total": {"ndistinct": n, "min": 0, "max": (n - 1) * 10}}
    return P.Table("orders", rows, stats)


@pytest.fixture
def cat(P):
    c = P.Catalog()
    c.add_table(make_users(P))
    c.add_table(make_orders(P))
    return c


# ------------------------------------------------------------ selectivity
def test_selectivity_equality_is_one_over_ndistinct(P, cat):
    assert P.estimate_selectivity(cat, "users", "city", "=", "c0") == pytest.approx(1 / 5)
    assert P.estimate_selectivity(cat, "users", "id", "=", 3) == pytest.approx(1 / 20)


def test_selectivity_range_interpolates_linearly(P, cat):
    # age: min 20, max 39 -> (39-30)/(39-20) = 9/19
    assert P.estimate_selectivity(cat, "users", "age", ">", 30) == pytest.approx(9 / 19)
    assert P.estimate_selectivity(cat, "users", "age", "<", 30) == pytest.approx(10 / 19)


def test_selectivity_clamped_to_unit_interval(P, cat):
    assert P.estimate_selectivity(cat, "users", "age", ">", 999) == 0.0
    assert P.estimate_selectivity(cat, "users", "age", "<", -999) == 0.0


def test_selectivity_unknown_column_defaults(P, cat):
    assert P.estimate_selectivity(cat, "users", "ghost", "=", 1) == 0.5


# ------------------------------------------------------------------- render
def test_render_plan_shape(P, cat):
    plan = P.Project(P.Filter(P.SeqScan("users"), "age", ">", 30), ["name"])
    assert P.render_plan(plan) == "SeqScan(users)->Filter(age>30)->Project(name)"


def test_render_join_and_limit(P, cat):
    j = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    lim = P.Limit(j, 5)
    s = P.render_plan(lim)
    assert s == "SeqScan(users)->SeqScan(orders)->HashJoin(id=user_id)->Limit(5)"


def test_render_index_scan(P, cat):
    s = P.render_plan(P.IndexScan("users", "city", "c0"))
    assert s == "IndexScan(users.city=c0)"


# ------------------------------------------------------- index selection
def test_index_chosen_when_selectivity_below_threshold(P, cat):
    """city: ndistinct 5 -> eq selectivity 0.2 > 0.1... give users a sparse
    index on id instead: 1/20 = 0.05 < 0.1 -> IndexScan."""
    cat.add_index("users", "id")
    plan = P.Filter(P.SeqScan("users"), "id", "=", 7)
    opt = P.Planner(cat).optimize(plan)
    assert isinstance(opt, P.IndexScan)
    assert (opt.table, opt.column, opt.key) == ("users", "id", 7)
    assert P.render_plan(opt) == "IndexScan(users.id=7)"


def test_index_not_chosen_at_or_above_threshold(P, cat):
    """ndistinct 5 -> selectivity 0.2 >= 0.1: seq scan stays, even indexed."""
    cat.add_index("users", "city")
    plan = P.Filter(P.SeqScan("users"), "city", "=", "c0")
    opt = P.Planner(cat).optimize(plan)
    assert isinstance(opt, P.Filter) and isinstance(opt.child, P.SeqScan)
    assert P.render_plan(opt) == "SeqScan(users)->Filter(city=c0)"


def test_index_needs_an_index_to_exist(P, cat):
    """Same selectivity as the chosen case, but no index registered."""
    plan = P.Filter(P.SeqScan("users"), "id", "=", 7)
    opt = P.Planner(cat).optimize(plan)
    assert isinstance(opt, P.Filter), "no index -> no IndexScan, ever"


# ------------------------------------------------------ predicate pushdown
def test_filter_pushes_below_project(P, cat):
    """Project over Filter over SeqScan -> Filter must sink to the scan."""
    plan = P.Project(P.Filter(P.SeqScan("users"), "age", ">", 30), ["name"])
    opt = P.Planner(cat).optimize(plan)
    assert P.render_plan(opt) == "SeqScan(users)->Filter(age>30)->Project(name)"


def test_filter_never_pushes_below_limit(P, cat):
    """Filter over Limit would change semantics if the filter sank below
    the limit — the limit must keep seeing pre-filter rows... in OUR rule
    set the filter may not pass *through* the limit node."""
    plan = P.Filter(P.Limit(P.SeqScan("users"), 5), "age", ">", 25)
    opt = P.Planner(cat).optimize(plan)
    # the Filter must stay ABOVE the Limit
    assert P.render_plan(opt).startswith("SeqScan(users)->Limit(5)->Filter(")


# ---------------------------------------------------------- limit pushdown
def test_limit_pushes_below_project(P, cat):
    plan = P.Limit(P.Project(P.SeqScan("users"), ["name"]), 5)
    opt = P.Planner(cat).optimize(plan)
    assert P.render_plan(opt) == "SeqScan(users)->Limit(5)->Project(name)"


def test_limit_not_pushed_below_filter(P, cat):
    """Limit over Filter: limit may NOT sink past the filter — the filter
    decides which rows exist at all."""
    plan = P.Limit(P.Filter(P.SeqScan("users"), "age", ">", 30), 5)
    opt = P.Planner(cat).optimize(plan)
    assert P.render_plan(opt) == "SeqScan(users)->Filter(age>30)->Limit(5)"


# ----------------------------------------------------------- join choice
def test_hashjoin_when_build_fits_budget(P, cat):
    join = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    opt = P.Planner(cat, memory_budget_rows=1000).optimize(join)
    assert isinstance(opt, P.HashJoin)
    assert "HashJoin" in P.render_plan(opt)


def test_nlj_when_build_exceeds_budget(P, cat):
    join = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    opt = P.Planner(cat, memory_budget_rows=2).optimize(join)
    assert isinstance(opt, P.NestedLoopJoin)
    assert "NestedLoopJoin" in P.render_plan(opt)


def test_budget_flip_on_same_plan(P, cat):
    join = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    p_big = P.Planner(cat, memory_budget_rows=10_000).optimize(join)
    p_small = P.Planner(cat, memory_budget_rows=1).optimize(join)
    assert isinstance(p_big, P.HashJoin)
    assert isinstance(p_small, P.NestedLoopJoin)


# ------------------------------------------------- optimized == naive rows
def _key(row):
    return tuple(sorted(row.items(), key=lambda kv: kv[0]))


def _sorted_rows(rows):
    return sorted(rows, key=_key)


def test_optimized_plan_returns_same_rows_as_naive(P, cat):
    naive = P.Filter(P.SeqScan("users"), "age", ">", 30)
    cat.add_index("users", "age")
    opt = P.Planner(cat).optimize(naive)
    # whatever shape the optimizer chose, the rows must be identical
    assert _sorted_rows(P.execute(cat, opt)) == _sorted_rows(P.execute(cat, naive))


def test_optimized_join_returns_same_rows(P, cat):
    naive = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    opt = P.Planner(cat, memory_budget_rows=1000).optimize(naive)
    assert isinstance(opt, P.HashJoin)
    nlj = P.Planner(cat, memory_budget_rows=1).optimize(naive)
    assert isinstance(nlj, P.NestedLoopJoin)
    assert _sorted_rows(P.execute(cat, opt)) == _sorted_rows(P.execute(cat, naive))
    assert _sorted_rows(P.execute(cat, nlj)) == _sorted_rows(P.execute(cat, naive))


def test_full_pipeline_plan_shape_and_rows(P, cat):
    """Project(Limit(Filter(Join(Scan, Scan)))) — every rule at once."""
    cat.add_index("users", "id")
    naive = P.Limit(
        P.Project(
            P.Filter(
                P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"),
                           "id", "user_id"),
                "total", ">", 100),
            ["name", "total"]),
        3)
    planner = P.Planner(cat, memory_budget_rows=10_000)
    opt = planner.optimize(naive)
    got = _sorted_rows(P.execute(cat, opt))
    want = _sorted_rows(P.execute(cat, naive))
    assert got == want, "optimizer changed the ANSWER, not just the shape"
    # and the naive plan actually returns the right rows to begin with
    assert len(want) == 3


# ------------------------------------------------------------- estimates
def test_estimate_rows_scan_and_filter(P, cat):
    assert P.estimate_rows(cat, P.SeqScan("users")) == 20
    f = P.Filter(P.SeqScan("users"), "age", ">", 30)
    assert P.estimate_rows(cat, f) == int(20 * (9 / 19))


def test_estimate_rows_index_scan(P, cat):
    est = P.estimate_rows(cat, P.IndexScan("users", "id", 7))
    assert est == int(20 * (1 / 20))      # ndistinct 20 -> 1 row


def test_estimate_rows_limit_caps_child(P, cat):
    assert P.estimate_rows(cat, P.Limit(P.SeqScan("users"), 5)) == 5
    assert P.estimate_rows(cat, P.Limit(P.SeqScan("users"), 999)) == 20


def test_estimate_rows_join_uses_ndistinct(P, cat):
    j = P.HashJoin(P.SeqScan("users"), P.SeqScan("orders"), "id", "user_id")
    # 20 * 60 / max(ndistinct(id)=20, 1) = 60
    assert P.estimate_rows(cat, j) == 60
