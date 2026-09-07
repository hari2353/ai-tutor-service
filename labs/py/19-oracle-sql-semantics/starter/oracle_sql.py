"""Lab 19 — Oracle SQL semantics. Fill in every TODO. Tests define done.

Rules:
  * '' IS NULL in Oracle: every string that enters the engine goes through
    oracle_string() first. Predicates on NULL never match — not even <> ''.
  * ROWNUM is assigned BEFORE ORDER BY executes. This single fact is the lab.
"""
from __future__ import annotations

from typing import Any, Callable


def oracle_string(value: str | None) -> str | None:
    """Oracle VARCHAR2 coercion: the empty string is NULL. Everything else
    passes through unchanged. Applied at the column boundary."""
    # TODO(step 1)
    raise NotImplementedError


def oracle_compare(a: Any, b: Any) -> bool | None:
    """NULL-aware comparison. If either side is None the result is None
    (unknown) — never True, never False. Otherwise equality/inequality
    returns normally. (Only == and != semantics are needed for this lab.)"""
    # TODO(step 2)
    raise NotImplementedError


def apply_rownum(rows: list[dict], predicate: Callable[[dict], bool],
                 order_by: Callable[[dict], Any] | None = None,
                 desc: bool = False,
                 limit: int | None = None) -> list[dict]:
    """ROWNUM assignment as Oracle actually does it.

    If order_by is None: rows are numbered 1..n as they enter the result
    set (list order), the predicate is evaluated against that number, and
    `limit` (a ROWNUM <= n cap) applies as rows stream in.

    If order_by is given, the WRONG behaviour (which you must implement,
    because Oracle does it) is: number the rows in the ORIGINAL list order,
    apply the limit to the pre-sort stream, and only then sort the survivors
    (desc=True sorts descending; NULLs follow Oracle's NULL-high rule).
    The correct Top-N needs the caller to nest — provide
    `top_n_subquery(rows, n, order_by)` for that.

    predicate receives the row dict plus {'rownum': i}.
    """
    # TODO(step 3)
    raise NotImplementedError


def top_n_subquery(rows: list[dict], n: int,
                   order_by: Callable[[dict], Any],
                   desc: bool = False) -> list[dict]:
    """The pre-12c correct Top-N: sort in the 'subquery', apply ROWNUM
    outside, after the sort. Returns the first n rows in sorted order."""
    # TODO(step 3b)
    raise NotImplementedError


def fetch_first(rows: list[dict], n: int,
                order_by: Callable[[dict], Any] | None = None,
                desc: bool = False, ties: bool = False,
                offset: int = 0) -> list[dict]:
    """12c FETCH FIRST: sort first (by definition), then skip `offset`
    rows, then take n. With ties=True include rows equal to the last kept
    row under order_by (FETCH FIRST n ROWS WITH TIES) — requires order_by.
    Raise ValueError if ties=True and order_by is None."""
    # TODO(step 4)
    raise NotImplementedError


def order_oracle(rows: list[dict], key: Callable[[dict], Any],
                 desc: bool = False, nulls: str | None = None) -> list[dict]:
    """Oracle default: NULLs sort HIGHER than any value — ASC puts them
    last, DESC puts them first. nulls='first' or 'last' overrides.
    Returns a NEW list; does not mutate the input."""
    # TODO(step 5)
    raise NotImplementedError


def nvl(expr: Any, substitute: Any) -> Any:
    """Return expr unless it is None (or '' — which IS None here), in which
    case return substitute. Both arguments are received eagerly — that is
    the documented NVL behaviour this lab tests."""
    # TODO(step 6)
    raise NotImplementedError


def nvl2(expr: Any, if_not_null: Any, if_null: Any) -> Any:
    """expr non-null -> if_not_null; expr null -> if_null."""
    # TODO(step 6b)
    raise NotImplementedError


def decode(expr: Any, *args: Any) -> Any:
    """Oracle DECODE: pairs (match, result), optional trailing default.
    NULL matches NULL (unlike = everywhere else). No match and no default
    -> None."""
    # TODO(step 6c)
    raise NotImplementedError


def top_n_analytic(rows: list[dict], n: int, key: Callable[[dict], Any],
                   desc: bool = True, func: str = "rank") -> list[dict]:
    """Analytic Top-N: compute the window function over the WHOLE set,
    then keep rows with value <= n.
      rank       1,1,3  (skips after ties)
      dense_rank 1,1,2  (no skip)
      row_number 1,2,3  (unique, order-dependent)
    Raise ValueError on an unknown func. Deterministic tie order: stable
    sort by key, then original index for row_number."""
    # TODO(step 7)
    raise NotImplementedError
