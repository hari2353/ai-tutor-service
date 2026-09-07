"""Lab 21 — BI filter context. Tests mirror README steps 1-6.

Starter must FAIL every test (NotImplementedError); solution must PASS.
"""
import pytest

TOTAL = lambda rows: sum(r["amount"] for r in rows)


# ---- step 1: Model + filter propagation -----------------------------------


def test_fact_rows_no_filters_is_all_rows(model):
    rows = model.fact_rows("Sales", {})
    assert len(rows) == 5


def test_filter_propagates_through_relationship(model):
    rows = model.fact_rows("Sales", {"Product": {"P1"}})
    assert [r["amount"] for r in rows] == [100, 50, 30]


def test_filters_intersect_across_dimensions(model):
    rows = model.fact_rows("Sales", {"Product": {"P1"}, "Store": {"S1"}})
    assert [r["amount"] for r in rows] == [100, 30]


def test_filter_on_unrelated_dimension_is_ignored(model):
    # a fact-only model: Date has no relation to Sales rows here? It does.
    # Instead: filter values that match nothing survive nothing.
    rows = model.fact_rows("Sales", {"Product": {"NOPE"}})
    assert rows == []


def test_empty_value_set_filters_everything_out(model):
    rows = model.fact_rows("Sales", {"Product": set()})
    assert rows == []


# ---- step 2: evaluate ------------------------------------------------------


def test_evaluate_no_context_is_all_rows(B, model):
    assert B.evaluate(model, "Sales", TOTAL) == 310


def test_evaluate_under_context(model):
    from bi_model import evaluate  # noqa: F401  (module fixture covers it)
    pass


def test_evaluate_respects_context(B, model):
    assert B.evaluate(model, "Sales", TOTAL, {"Product": {"P2"}}) == 130


def test_measure_never_sees_other_dimensions(B, model):
    # measure_fn receives ONLY surviving rows — a filter on Product should
    # not leak Date semantics the measure didn't ask for.
    rows_seen = {}

    def spy(rows):
        rows_seen["n"] = len(rows)
        return sum(r["amount"] for r in rows)

    B.evaluate(model, "Sales", spy, {"Product": {"P1"}})
    assert rows_seen["n"] == 3


# ---- step 3: calculate (context transition) --------------------------------


def test_calculate_filter_replaces_context(B, model):
    v = B.calculate(model, "Sales", TOTAL, {"Product": {"P1"}},
                    ("filter", "Product", {"P2"}))
    assert v == 130


def test_calculate_filter_adds_dimension(B, model):
    # CALCULATE introduces a filter the visual never set
    v = B.calculate(model, "Sales", TOTAL, None,
                    ("filter", "Product", {"P2"}))
    assert v == 130


def test_calculate_all_clears_dimension(B, model):
    v = B.calculate(model, "Sales", TOTAL, {"Product": {"P2"}},
                    ("all", "Product"))
    assert v == 310


def test_calculate_removefilters_alias(B, model):
    v = B.calculate(model, "Sales", TOTAL, {"Product": {"P2"}},
                    ("removefilters", "Product"))
    assert v == 310


def test_calculate_all_all_clears_everything(B, model):
    v = B.calculate(model, "Sales", TOTAL,
                    {"Product": {"P1"}, "Store": {"S2"}},
                    ("all_all", None))
    assert v == 310


def test_calculate_modifiers_in_order_last_wins(B, model):
    v = B.calculate(model, "Sales", TOTAL, {"Product": {"P1"}},
                    ("all", "Product"), ("filter", "Product", {"P2"}))
    assert v == 130


def test_calculate_leaves_untouched_dimensions_alone(B, model):
    v = B.calculate(model, "Sales", TOTAL, {"Product": {"P2"}, "Store": {"S1"}},
                    ("all", "Product"))
    assert v == 200  # Store filter still applies: rows 0,2,3


# ---- step 4: calculated column ---------------------------------------------


def test_calculated_column_stored_on_rows(B, model):
    vals = B.calculated_column(model, "Sales", "double", lambda r: r["amount"] * 2)
    assert vals == [200, 100, 140, 60, 120]
    # stored: the fact rows now carry the column
    assert model.tables["Sales"][0]["double"] == 200
    assert model.tables["Sales"][4]["double"] == 120


def test_calculated_column_is_row_local_not_context(B, model):
    B.calculated_column(model, "Sales", "band",
                        lambda r: "hi" if r["amount"] >= 70 else "lo")
    # a stored column slices: measure over rows where band == 'hi'
    rows = model.fact_rows("Sales", {})
    hi = [r["amount"] for r in rows if r["band"] == "hi"]
    assert hi == [100, 70]
    # and that stored value is INERT to later filter context changes:
    # it was computed at refresh, it never recomputes
    assert B.evaluate(model, "Sales", TOTAL, {"Product": {"P2"}}) == 130


# ---- step 5: FIXED LOD ------------------------------------------------------


def test_fixed_lod_ignores_filter_on_grouping_dim(B, model):
    # {FIXED [Product]: SUM(amount)} with Product filtered to P1 in ctx:
    # group totals still computed for BOTH products
    res = B.fixed_lod(model, "Sales", "Product", lambda xs: sum(xs),
                      {"Product": {"P1"}})
    assert res == {"P1": 180, "P2": 130}


def test_fixed_lod_respects_context_on_other_dims(B, model):
    res = B.fixed_lod(model, "Sales", "Product", lambda xs: sum(xs),
                      {"Store": {"S1"}})
    assert res == {"P1": 130, "P2": 70}  # S1 rows: 100+30, 70


def test_fixed_lod_disagrees_with_context_percent(B, model):
    # the lesson: FIXED numerator ignores the slicer, context % doesn't
    fixed = B.fixed_lod(model, "Sales", "Product", sum, {"Product": {"P1"}})
    assert fixed["P1"] == 180  # all of P1, slicer ignored
    # context-respecting: P1 share of the UNFILTERED total is 58%, not 100%
    pct = B.percent_of_total(model, "Sales", TOTAL, {"Product": {"P1"}})
    assert pct == pytest.approx(180 / 310 * 100)


# ---- step 6: percent of total -----------------------------------------------


def test_percent_of_total_default_denominator(B, model):
    pct = B.percent_of_total(model, "Sales", TOTAL, {"Product": {"P1"}})
    assert pct == pytest.approx(180 / 310 * 100)


def test_percent_of_total_explicit_denominator(B, model):
    # numerator: P1+S1 -> 100+30=130 ; denominator: S1 -> 100+70+30=200
    pct = B.percent_of_total(model, "Sales", TOTAL,
                             {"Product": {"P1"}, "Store": {"S1"}},
                             {"Store": {"S1"}})
    assert pct == pytest.approx(130 / 200 * 100)


def test_percent_of_total_empty_ctx_is_100(B, model):
    assert B.percent_of_total(model, "Sales", TOTAL, {}) == 100.0
