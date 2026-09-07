"""Lab 20 — reference solution: dynamic-array Excel semantics."""
from __future__ import annotations

import re
from typing import Any, Callable

_REF_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")


class Sheet:
    def __init__(self) -> None:
        self.cells: dict[str, Any] = {}
        self.spill_anchors: dict[str, tuple] = {}

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


def _col_to_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _index_to_col(x: int) -> str:
    x = x + 1
    out = ""
    while x > 0:
        x, rem = divmod(x - 1, 26)
        out = chr(65 + rem) + out
    return out


def ref_to_xy(ref: str) -> tuple[int, int]:
    m = _REF_RE.match(ref)
    if not m:
        raise ValueError(f"bad ref {ref!r}")
    return _col_to_index(m.group(1)), int(m.group(2)) - 1


def xy_to_ref(x: int, y: int) -> str:
    if x < 0 or y < 0:
        raise ValueError(f"negative coords {x},{y}")
    return f"{_index_to_col(x)}{y + 1}"


def _cells_in_range(sheet: Sheet, top_left: str,
                    bottom_right: str) -> list[str]:
    x0, y0 = ref_to_xy(top_left)
    x1, y1 = ref_to_xy(bottom_right)
    return [xy_to_ref(x, y) for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)]


def spill(sheet: Sheet, anchor: str, values: list[list[Any]]) -> tuple[str, str]:
    if not values or not any(values):
        return (anchor, anchor)

    height = len(values)
    width = max(len(row) for row in values)
    ax, ay = ref_to_xy(anchor)
    bottom_right = xy_to_ref(ax + width - 1, ay + height - 1)
    claimed = _cells_in_range(sheet, anchor, bottom_right)

    # previous claim by this anchor (relinkable: a re-spill may replace it)
    prev = sheet.spill_anchors.get(anchor)
    prev_cells: set[str] = set()
    if prev:
        prev_cells = set(_cells_in_range(sheet, prev[0], prev[1]))

    for ref in claimed:
        existing = sheet.cells.get(ref)
        if existing is not None and ref not in prev_cells:
            sheet.cells[anchor] = "#SPILL!"
            return ("#SPILL!", "#SPILL!")

    # clear the previous claim's cells (they may be outside the new range)
    for ref in prev_cells:
        if ref not in claimed:
            sheet.cells.pop(ref, None)

    for i, row in enumerate(values):
        for j, v in enumerate(row):
            sheet.set(xy_to_ref(ax + j, ay + i), v)
    sheet.spill_anchors[anchor] = (anchor, bottom_right)
    return (anchor, bottom_right)


def spill_ref(sheet: Sheet, anchor: str) -> list[list[Any]]:
    owned = sheet.spill_anchors.get(anchor)
    if owned is None:
        return [[sheet.get(anchor)]]
    x0, y0 = ref_to_xy(owned[0])
    x1, y1 = ref_to_xy(owned[1])
    return [[sheet.get(xy_to_ref(x, y)) for x in range(x0, x1 + 1)]
            for y in range(y0, y1 + 1)]


def let(bindings: list[tuple[str, Any]],
        body_fn: Callable[[dict[str, Any]], Any]) -> Any:
    env: dict[str, Any] = {}
    for name, value in bindings:
        if callable(value):
            env[name] = value(env) if value.__code__.co_argcount else value()
        else:
            env[name] = value
    return body_fn(env)


def lambda_fn(params: list[str],
              body_fn: Callable[..., Any]) -> Callable[..., Any]:
    def call(*args: Any) -> Any:
        if len(args) != len(params):
            raise TypeError(
                f"lambda takes {len(params)} args, got {len(args)}")
        return body_fn(*args)
    return call


def ifs(pairs: list[tuple, Any], default: Any = None) -> Any:
    for cond, result in pairs:
        if callable(cond):
            cond = cond()
        if cond:
            return result() if callable(result) else result
    return default


def _col_x(colref: str) -> int:
    """Accept 'A' (bare column letter) or 'A1' (cell ref) — both name a
    column; return the zero-based x."""
    if _REF_RE.match(colref):
        return ref_to_xy(colref)[0]
    if re.fullmatch(r"[A-Z]+", colref):
        return _col_to_index(colref)
    raise ValueError(f"bad column ref {colref!r}")


def xlookup(sheet: Sheet, lookup_value: Any, lookup_col: str,
            return_cols: list[str],
            if_not_found: Any = "#N/A") -> list[Any]:
    x = _col_x(lookup_col)
    ret_xs = [_col_x(rc) for rc in return_cols]
    max_row = 0
    for ref in sheet.cells:
        _, cy = ref_to_xy(ref)
        max_row = max(max_row, cy)
    for row in range(0, max_row + 1):
        if sheet.get(xy_to_ref(x, row)) == lookup_value:
            return [sheet.get(xy_to_ref(rx, row)) for rx in ret_xs]
    return [if_not_found] * len(return_cols)
