"""Lab 19 — reference solution: the six Oracle dialect traps."""
from __future__ import annotations

from typing import Any, Callable


def _null_safe_key(key: Callable[[dict], Any], desc: bool = False):
    """Total-order key with Oracle NULL-high semantics: ASC -> nulls last,
    DESC -> nulls first. Works for mixed None/numeric columns."""
    def k(row: dict):
        v = key(row)
        if v is None:
            # ASC: nulls highest (bucket 2). DESC: nulls first — reverse
            # sort with bucket flip so nulls land at the front.
            return (2, 0) if not desc else (0, 0)
        # negate numerics for DESC inside a non-reversed sort
        if desc and isinstance(v, (int, float)):
            return (1, -v)
        return (1, v)
    return k


def oracle_string(value: str | None) -> str | None:
    if value == "":
        return None
    return value


def oracle_compare(a: Any, b: Any) -> bool | None:
    if a is None or b is None:
        return None
    return a == b


def apply_rownum(rows: list[dict], predicate: Callable[[dict], bool],
                 order_by: Callable[[dict], Any] | None = None,
                 desc: bool = False,
                 limit: int | None = None) -> list[dict]:
    """Number rows as they enter the stream (input list order), apply the
    predicate and the ROWNUM cap, THEN sort — Oracle's wrong-five-rows
    behaviour when ORDER BY sits in the same query level as the filter."""
    kept = []
    counter = 0
    for row in rows:
        # Oracle semantics: the NEXT row is only numbered if a previous row
        # passed — the counter advances ONLY on predicate success. That is
        # why rownum = 2 can never match: the row after a failed row would
        # need to be numbered 2, but no row was ever numbered 1.
        counter += 1
        ctx = dict(row)
        ctx["rownum"] = counter
        if predicate is not None and not predicate(ctx):
            # a rejected row consumed its shot at this number; the next row
            # gets the SAME number (Oracle assigns rownum at the point of
            # test, and only passing rows advance the stream)
            counter -= 1
            continue
        kept.append(row)
        if limit is not None and len(kept) >= limit:
            break
    if order_by is not None:
        kept = order_oracle(kept, key=order_by, desc=desc)
    return kept


def top_n_subquery(rows: list[dict], n: int,
                   order_by: Callable[[dict], Any],
                   desc: bool = False) -> list[dict]:
    """Correct pre-12c Top-N: sort first (Oracle NULL-high ordering), cap
    outside, after the sort."""
    return order_oracle(rows, key=order_by, desc=desc)[:n]


def fetch_first(rows: list[dict], n: int,
                order_by: Callable[[dict], Any] | None = None,
                desc: bool = False, ties: bool = False,
                offset: int = 0) -> list[dict]:
    if ties and order_by is None:
        raise ValueError("WITH TIES requires ORDER BY")
    if order_by is not None:
        rows = order_oracle(rows, key=order_by, desc=desc)
    rows = rows[offset:]
    taken = rows[:n]
    if not ties or not taken:
        return taken
    boundary = order_by(taken[-1])
    extra = [r for r in rows[n:] if order_by(r) == boundary]
    return taken + extra


def order_oracle(rows: list[dict], key: Callable[[dict], Any],
                 desc: bool = False, nulls: str | None = None) -> list[dict]:
    if nulls is not None and nulls not in ("first", "last"):
        raise ValueError(f"nulls must be 'first' or 'last', got {nulls!r}")
    null_last = (not desc) if nulls is None else (nulls == "last")
    non_null = [r for r in rows if key(r) is not None]
    null_rows = [r for r in rows if key(r) is None]
    non_null.sort(key=key, reverse=desc)
    return (non_null + null_rows) if null_last else (null_rows + non_null)


def nvl(expr: Any, substitute: Any) -> Any:
    return substitute if expr is None else expr


def nvl2(expr: Any, if_not_null: Any, if_null: Any) -> Any:
    return if_null if expr is None else if_not_null


def decode(expr: Any, *args: Any) -> Any:
    if len(args) % 2 != 0:
        *pairs, default = args
    else:
        pairs, default = args, None
    for i in range(0, len(pairs), 2):
        match, result = pairs[i], pairs[i + 1]
        if expr == match or (expr is None and match is None):
            return result
    return default


def top_n_analytic(rows: list[dict], n: int, key: Callable[[dict], Any],
                   desc: bool = True, func: str = "rank") -> list[dict]:
    if func not in ("rank", "dense_rank", "row_number"):
        raise ValueError(f"unknown window function {func!r}")
    # sort with Oracle NULL-high ordering (DESC default, matching the
    # module's Top-N canon), stable on original index for row_number ties
    indexed = list(enumerate(rows))
    if desc:
        # NULL first (NULL-high + DESC), then value descending
        indexed.sort(key=lambda t: ((0, 0) if key(t[1]) is None
                                    else (1, key(t[1]))), reverse=True)
        # stable re-pass to keep original order among equal keys
        indexed.sort(key=lambda t: (0 if key(t[1]) is None else 1,
                                     -(key(t[1]) or 0), t[0]))
    else:
        indexed.sort(key=lambda t: (1 if key(t[1]) is None else 0,
                                    key(t[1]) if key(t[1]) is not None else 0,
                                    t[0]))
    result = []
    prev_key = object()
    rank = 0
    dense = 0
    for pos, (orig_idx, row) in enumerate(indexed, start=1):
        k = key(row)
        if k != prev_key:
            rank = pos
            dense += 1
        prev_key = k
        value = {"rank": rank, "dense_rank": dense, "row_number": pos}[func]
        if value <= n:
            result.append(row)
    return result
