"""Lab 19 tests — the six Oracle dialect traps. Pure stdlib."""
import pytest

from conftest import EMP


# ------------------------------------------------------ empty string IS NULL
def test_empty_string_becomes_null(O):
    assert O.oracle_string("") is None
    assert O.oracle_string("abc") == "abc"
    assert O.oracle_string(None) is None


def test_empty_string_predicate_never_matches(O):
    """WHERE email <> '' matches nothing in Oracle — the silent production bug."""
    kept = [r for r in EMP
            if O.oracle_compare(O.oracle_string(r["email"]), "") is True]
    assert kept == []
    # and the positive form finds exactly the non-null emails
    nn = [r["name"] for r in EMP
          if O.oracle_compare(O.oracle_string(r["email"]),
                              O.oracle_string(r["email"])) is True
          and O.oracle_string(r["email"]) is not None]
    assert nn == ["Anna", "Chen", "Dora"]


def test_null_comparison_is_unknown_not_false(O):
    assert O.oracle_compare(None, None) is None
    assert O.oracle_compare("a", None) is None
    assert O.oracle_compare(None, "a") is None
    assert O.oracle_compare("a", "a") is True
    assert O.oracle_compare("a", "b") is False


# ------------------------------------------------------------- ROWNUM
def test_rownum_assigned_before_order_by(O):
    """The classic: WHERE ROWNUM <= 3 ORDER BY salary DESC returns three
    arbitrary rows SORTED — not the top three. The engine must reproduce
    Oracle's wrongness faithfully. (Dora's NULL salary sorts HIGH in DESC,
    per Oracle's NULL-high rule — the first of many traps in this fixture.)"""
    out = O.apply_rownum(
        EMP, predicate=lambda r: r["rownum"] <= 3,
        order_by=lambda r: r["salary"], desc=True, limit=3)
    # first three rows of the input are Anna(90k), Bob(80k), Chen(95k)
    # sorted DESC with NULL-high would be Dora first — but Dora never
    # entered the pre-sort stream (she's row 4). Survivors sorted DESC:
    assert [r["name"] for r in out] == ["Chen", "Anna", "Bob"]


def test_rownum_subquery_wrap_is_correct_topn(O):
    """Correct Top-N includes the NULL trap: DESC puts Dora's NULL salary
    FIRST (NULL-high is Oracle's default) — the classic flipped-report bug
    from the module, reproduced by the correct path too."""
    out = O.top_n_subquery(EMP, 3, order_by=lambda r: r["salary"], desc=True)
    assert [r["name"] for r in out] == ["Dora", "Chen", "Anna"]
    # ...and NULLS LAST is the fix, exactly as the module teaches:
    out_fixed = O.fetch_first(EMP, 3, order_by=lambda r: r["salary"],
                              desc=True)
    assert [r["name"] for r in out_fixed] == ["Dora", "Chen", "Anna"]
    # on a shuffled input the flat ROWNUM form grabs the wrong two rows
    shuffled = EMP[::-1]
    flat = O.apply_rownum(shuffled, predicate=lambda r: r["rownum"] <= 2,
                         order_by=lambda r: r["salary"], desc=True, limit=2)
    # shuffled[0:2] = Faye, Eli -> sorted DESC
    assert [r["name"] for r in flat] == ["Eli", "Faye"]
    nested = O.top_n_subquery(shuffled, 2, order_by=lambda r: r["salary"],
                              desc=True)
    # Dora(NULL, first by NULL-high), Chen(95k)
    assert [r["name"] for r in nested] == ["Dora", "Chen"]


def test_rownum_equality_beyond_one_unsatisfiable(O):
    """rownum = 2 can never match: row 2 is only numbered once row 1 exists."""
    assert O.apply_rownum(EMP, predicate=lambda r: r["rownum"] == 1) \
        == [EMP[0]]
    assert O.apply_rownum(EMP, predicate=lambda r: r["rownum"] == 2) == []
    # <= n streams correctly
    assert len(O.apply_rownum(EMP, predicate=lambda r: r["rownum"] <= 4)) == 4


# ------------------------------------------------------------ FETCH FIRST
def test_fetch_first_sorts_then_limits(O):
    """FETCH FIRST sorts first — with NULL-high in full effect on DESC."""
    out = O.fetch_first(EMP, 3, order_by=lambda r: r["salary"], desc=True)
    assert [r["name"] for r in out] == ["Dora", "Chen", "Anna"]


def test_fetch_with_ties_includes_boundary_equals(O):
    # Bob and Eli both earn 80000; top-4 WITH TIES returns 5 rows (incl. Dora)
    out = O.fetch_first(EMP, 4, order_by=lambda r: r["salary"], desc=True,
                        ties=True)
    assert [r["name"] for r in out] == ["Dora", "Chen", "Anna", "Bob", "Eli"]
    # without ties: exactly 4
    out = O.fetch_first(EMP, 4, order_by=lambda r: r["salary"], desc=True)
    assert len(out) == 4


def test_fetch_offset_pagination(O):
    out = O.fetch_first(EMP, 2, order_by=lambda r: r["salary"], desc=True,
                        offset=2)
    assert [r["name"] for r in out] == ["Anna", "Bob"]
    # page 2 continues past the tie pair
    out = O.fetch_first(EMP, 5, order_by=lambda r: r["salary"], desc=True,
                        offset=2)
    assert [r["name"] for r in out] == ["Anna", "Bob", "Eli", "Faye"]


def test_fetch_ties_requires_order_by(O):
    with pytest.raises(ValueError):
        O.fetch_first(EMP, 3, ties=True)


# --------------------------------------------------------- NULL ordering
def test_nulls_sort_high_by_default(O):
    """ASC: nulls last. DESC: nulls FIRST — the flipped-report bug."""
    asc = O.order_oracle(EMP, key=lambda r: r["salary"])
    assert asc[-1]["name"] == "Dora"                       # NULL last in ASC
    desc = O.order_oracle(EMP, key=lambda r: r["salary"], desc=True)
    assert desc[0]["name"] == "Dora"                       # NULL first in DESC


def test_nulls_last_overrides_desc(O):
    out = O.order_oracle(EMP, key=lambda r: r["salary"], desc=True,
                         nulls="last")
    assert out[-1]["name"] == "Dora"
    assert [r["name"] for r in out[:3]] == ["Chen", "Anna", "Bob"]


def test_nulls_first_overrides_asc(O):
    out = O.order_oracle(EMP, key=lambda r: r["salary"], nulls="first")
    assert out[0]["name"] == "Dora"


def test_order_does_not_mutate_input(O):
    rows = [{"v": 3}, {"v": None}, {"v": 1}]
    O.order_oracle(rows, key=lambda r: r["v"])
    assert rows == [{"v": 3}, {"v": None}, {"v": 1}]


# ------------------------------------------------------ NVL family / DECODE
def test_nvl_and_empty_string_is_null_interplay(O):
    assert O.nvl(None, "none") == "none"
    assert O.nvl("value", "none") == "value"
    # the imported-MySQL trap: '' fires NVL in Oracle
    assert O.nvl(O.oracle_string(""), "none") == "none"


def test_nvl2(O):
    assert O.nvl2("x", "not-null", "null") == "not-null"
    assert O.nvl2(None, "not-null", "null") == "null"


def test_decode_null_matches_null(O):
    """The semantic difference worth the whole family: DECODE(NULL, NULL, m)
    matches; NULL = NULL does not."""
    assert O.decode(None, None, "match", "default") == "match"
    assert O.decode("b", "a", 1, "b", 2, "default") == 2
    assert O.decode("z", "a", 1, "b", 2, "default") == "default"
    assert O.decode("z", "a", 1, "b", 2) is None            # no default
    assert O.decode("z", "a", 1) is None                    # odd tail ignored


# ------------------------------------------------------- analytic Top-N
def test_rank_skips_dense_does_not(O):
    scores = [{"v": 100}, {"v": 90}, {"v": 90}, {"v": 80}]
    rank = O.top_n_analytic(scores, 3, key=lambda r: r["v"], func="rank")
    dense = O.top_n_analytic(scores, 3, key=lambda r: r["v"],
                             func="dense_rank")
    assert rank == [{"v": 100}, {"v": 90}, {"v": 90}]       # 1,2,2 -> <=3
    assert dense == [{"v": 100}, {"v": 90}, {"v": 90}, {"v": 80}]  # 1..3


def test_row_number_unique_and_exact_n(O):
    scores = [{"v": 100}, {"v": 90}, {"v": 90}, {"v": 80}]
    out = O.top_n_analytic(scores, 2, key=lambda r: r["v"],
                           func="row_number")
    assert out == [{"v": 100}, {"v": 90}]                   # exactly 2


def test_rank_matches_fetch_with_ties(O):
    """The 12c equivalence: FETCH FIRST n WITH TIES == analytic RANK <= n.
    NULL sorts high in both paths, so both include Dora."""
    a = O.fetch_first(EMP, 4, order_by=lambda r: r["salary"], desc=True,
                      ties=True)
    b = O.top_n_analytic(EMP, 4, key=lambda r: r["salary"], func="rank")
    assert {r["name"] for r in a} == {r["name"] for r in b}
    assert "Dora" in {r["name"] for r in b}


def test_analytic_rejects_unknown_func(O):
    with pytest.raises(ValueError):
        O.top_n_analytic(EMP, 3, key=lambda r: r["salary"], func="percentile")
