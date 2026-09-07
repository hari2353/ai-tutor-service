"""Lab 20 tests — spill refusal, LET's compute-once, LAMBDA composition,
IFS laziness, XLOOKUP's exact-default. Pure stdlib."""
import pytest


# ------------------------------------------------------------- ref plumbing
def test_ref_roundtrip(E):
    assert E.ref_to_xy("A1") == (0, 0)
    assert E.ref_to_xy("B3") == (1, 2)
    assert E.ref_to_xy("AA10") == (26, 9)
    assert E.xy_to_ref(1, 2) == "B3"
    assert E.xy_to_ref(26, 9) == "AA10"
    with pytest.raises(ValueError):
        E.ref_to_xy("3B")
    with pytest.raises(ValueError):
        E.ref_to_xy("A0")
    with pytest.raises(ValueError):
        E.xy_to_ref(-1, 0)


# ------------------------------------------------------------------ spill
def test_spill_claims_and_returns_range(E, sheet):
    rng = E.spill(sheet, "B2", [[10, 20], [30, 40]])
    assert rng == ("B2", "C3")
    assert sheet.get("B2") == 10 and sheet.get("C3") == 40


def test_spill_refuses_to_overwrite(E, sheet):
    """The safety property: a spill never destroys data — it writes #SPILL!
    at the anchor and claims nothing."""
    sheet.set("C2", "occupied")                       # inside the claim
    rng = E.spill(sheet, "B2", [[10, 20], [30, 40]])
    assert rng == ("#SPILL!", "#SPILL!")
    assert sheet.get("B2") == "#SPILL!"
    assert sheet.get("C2") == "occupied"               # untouched
    assert "B2" not in sheet.spill_anchors            # nothing claimed


def test_spill_replaces_its_own_previous_claim(E, sheet):
    """Relinkable handles: re-spilling the same anchor replaces its own
    range, shrinks included, without #SPILL! against itself."""
    E.spill(sheet, "B2", [[10, 20], [30, 40], [50, 60]])
    assert sheet.get("B4") == 50
    E.spill(sheet, "B2", [[1, 2]])                    # shrink to 1x2
    assert sheet.spill_anchors["B2"] == ("B2", "C2")
    assert sheet.get("B3") is None                    # old claim cleared
    assert E.spill_ref(sheet, "B2") == [[1, 2]]


def test_spill_hash_operator(E, sheet):
    E.spill(sheet, "A1", [[1, 2, 3], [4, 5, 6]])
    whole = E.spill_ref(sheet, "A1")                  # =A1#
    assert whole == [[1, 2, 3], [4, 5, 6]]
    # a non-anchor is a one-cell 'spill'
    sheet.set("E9", "solo")
    assert E.spill_ref(sheet, "E9") == [["solo"]]


# -------------------------------------------------------------------- LET
def test_let_binds_and_scopes(E):
    out = E.let(
        [("total", lambda env: 10 + 5), ("avg", lambda env: 15 / 3)],
        lambda env: env["total"] / env["avg"])
    assert out == 3.0


def test_let_computes_each_binding_once(E):
    """The performance primitive: a value referenced three times in the
    body is computed exactly once."""
    calls = []

    def expensive():
        calls.append(1)
        return 42

    out = E.let([("x", expensive)],
                lambda env: env["x"] + env["x"] + env["x"])
    assert out == 126
    assert len(calls) == 1


def test_let_bindings_may_reference_earlier_names(E):
    out = E.let(
        [("a", 5), ("b", lambda env: env["a"] * 2),
         ("c", lambda env: env["a"] + env["b"])],
        lambda env: env["c"])
    assert out == 15


# ------------------------------------------------------------------ LAMBDA
def test_lambda_saves_and_calls(E):
    calc_total = E.lambda_fn(["price", "tax"],
                             lambda price, tax: price * (1 + tax))
    assert calc_total(150, 0.08) == 162.0
    with pytest.raises(TypeError):
        calc_total(150)                                # arity enforced


def test_lambdas_compose(E):
    """A saved lambda called inside another lambda's body — recursion's
    building block and the Name-Manager idiom."""
    add = E.lambda_fn(["a", "b"], lambda a, b: a + b)
    double_then_add = E.lambda_fn(["x"], lambda x: add(x, x))
    assert double_then_add(21) == 42


# --------------------------------------------------------------------- IFS
def test_ifs_first_truthy_wins_and_lazy(E):
    evaluated = []

    def later():
        evaluated.append(1)
        return False

    def later_result():
        evaluated.append(2)
        return "second"

    out = E.ifs([(True, "first"), (later, later_result)])
    assert out == "first"
    assert evaluated == []          # neither thunk ever evaluated


def test_ifs_catchall_is_caller_supplied(E):
    out = E.ifs([(90 > 100, "Senior"), (80 > 100, "Mid"), (True, "Junior")])
    assert out == "Junior"
    assert E.ifs([(False, "a")]) is None               # no catch-all


# ----------------------------------------------------------------- XLOOKUP
def _build_roster(E, sheet):
    data = [["Name", "Dept", "Sales", "Region"],
            ["Sarah", "Eng", 150000, "East"],
            ["Raj", "Eng", 95000, "West"],
            ["Mei", "Mktg", 98000, "East"],
            ["Diego", "Mktg", 72000, "West"],
            ["Amara", "Sales", 88000, "East"]]
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            sheet.set(E.xy_to_ref(j, i), v)
    return sheet


def test_xlookup_exact_match_default(E, sheet):
    _build_roster(E, sheet)
    assert E.xlookup(sheet, "Mei", "A", ["B", "C", "D"]) == \
        ["Mktg", 98000, "East"]


def test_xlookup_multi_column_spill_return(E, sheet):
    """XLOOKUP('Sarah', names, B2:D6) spills Dept, Sales AND Region — the
    one-formula multi-column return the module's slide 6 shows."""
    _build_roster(E, sheet)
    out = E.xlookup(sheet, "Sarah", "A", ["B", "C", "D"])
    assert out == ["Eng", 150000, "East"]


def test_xlookup_not_found(E, sheet):
    _build_roster(E, sheet)
    assert E.xlookup(sheet, "Nobody", "A", ["B"]) == ["#N/A"]
    assert E.xlookup(sheet, "Nobody", "A", ["B", "C"],
                     if_not_found="missing") == ["missing", "missing"]


def test_xlookup_is_exact_not_approximate(E, sheet):
    """The VLOOKUP fix: 'Sar' must NOT match 'Sarah' (approximate match's
    silent-wrong-value failure mode) — exact by default, always."""
    _build_roster(E, sheet)
    assert E.xlookup(sheet, "Sar", "A", ["B"]) == ["#N/A"]
    assert E.xlookup(sheet, "sarah", "A", ["B"]) == ["#N/A"]  # case-exact
