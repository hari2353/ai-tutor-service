"""Lab 20 — modern Excel's dynamic-array semantics. Fill in every TODO.

A worksheet is {ref: value}. Sheet (given) handles ref parsing. You build
the 2019-2021 engine tier: spills, LET, LAMBDA, IFS, XLOOKUP.
"""
from __future__ import annotations

import re
from typing import Any, Callable

_REF_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")


class Sheet:
    """Minimal worksheet: dict-backed, A1-refs, no formatting."""

    def __init__(self) -> None:
        self.cells: dict[str, Any] = {}
        self.spill_anchors: dict[str, tuple] = {}   # anchor -> owned range

    @staticmethod
    def valid_ref(ref: str) -> bool:
        return bool(_REF_RE.match(ref))

    def get(self, ref: str) -> Any:
        if not self.valid_ref(ref):
            raise ValueError(f"bad ref {ref!r}")
        return self.cells.get(ref)

    def set(self, ref: str, value: Any) -> None:
        if not self.valid_ref(ref):
            raise ValueError(f"bad ref {ref!r}")
        self.cells[ref] = value


def ref_to_xy(ref: str) -> tuple[int, int]:
    """'B3' -> (1, 2), zero-based (col, row). ValueError on malformed refs."""
    # TODO(step 1)
    raise NotImplementedError


def xy_to_ref(x: int, y: int) -> str:
    """(1, 2) -> 'B3'. Inverse of ref_to_xy. x, y >= 0."""
    # TODO(step 1b)
    raise NotImplementedError


def _cells_in_range(sheet: Sheet, top_left: str,
                    bottom_right: str) -> list[str]:
    """All refs in the inclusive rectangle, row-major order."""
    x0, y0 = ref_to_xy(top_left)
    x1, y1 = ref_to_xy(bottom_right)
    return [xy_to_ref(x, y) for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)]


def spill(sheet: Sheet, anchor: str, values: list[list[Any]]) -> tuple[str, str]:
    """Dynamic-array spill: claim the rectangle starting at `anchor` sized
    to `values` (rows x cols). Rules:
      * any non-empty cell inside the claimed range that is NOT owned by
        this same anchor's previous spill -> write '#SPILL!' at anchor only,
        claim nothing, return ('#SPILL!', '#SPILL!').
      * otherwise clear this anchor's previous claim, write values, record
        the new claim, return (top_left, bottom_right) of the claim.
      * values == [[]] or [] claims nothing and returns (anchor, anchor)
        with nothing written (an empty spill is legal but owns nothing)."""
    # TODO(step 2)
    raise NotImplementedError


def spill_ref(sheet: Sheet, anchor: str) -> list[list[Any]]:
    """The '#' operator: the current values of the range this anchor's spill
    owns, as row-lists. If the anchor owns no range, return [[value]] of the
    anchor cell itself (a one-cell 'spill')."""
    # TODO(step 3)
    raise NotImplementedError


def let(bindings: list[tuple[str, Any]],
        body_fn: Callable[[dict[str, Any]], Any]) -> Any:
    """LET(name1, val1, name2, val2, ..., body): evaluate each binding ONCE
    in order (later bindings may use earlier names via the partial dict),
    then run body_fn with the full name->value dict. Bind-once-compute-once
    is the tested property — a side-effect-counting callable used three
    times in the body must run exactly once."""
    # TODO(step 4)
    raise NotImplementedError


def lambda_fn(params: list[str],
              body_fn: Callable[..., Any]) -> Callable[..., Any]:
    """LAMBDA(a, b, body): return a callable binding params positionally.
    Raises TypeError on wrong argument count. Lambdas compose — a saved
    lambda may be invoked inside another's body."""
    # TODO(step 5)
    raise NotImplementedError


def ifs(pairs: list[tuple[bool, Any]], default: Any = None) -> Any:
    """IFS(cond1, res1, cond2, res2, ...): first truthy condition's result.
    No truthy pair -> default (the caller passes a (True, x) catch-all for
    the Excel idiom; the engine adds nothing). Pairs evaluated lazily top
    down — a pair AFTER the winner is never evaluated (tests count calls)."""
    # TODO(step 6)
    raise NotImplementedError


def xlookup(sheet: Sheet, lookup_value: Any, lookup_col: str,
            return_cols: list[str],
            if_not_found: Any = "#N/A") -> list[Any]:
    """XLOOKUP(value, lookup_column, return_columns): scan rows top-down
    (row 1 to the sheet's max row); first row where lookup_col equals
    lookup_value -> [value of each return_col at that row]. Exact match is
    the DEFAULT. No match -> [if_not_found] per return column? No: Excel
    returns the if_not_found scalar — return [if_not_found]*len(return_cols).
    """
    # TODO(step 7)
    raise NotImplementedError
