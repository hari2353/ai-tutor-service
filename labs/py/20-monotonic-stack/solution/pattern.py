"""Lab 20 — monotonic stack. Reference solution."""
from __future__ import annotations

from typing import List, Sequence, Tuple, Union

Matrix = Sequence[Union[str, Sequence[int]]]


def _cells(row) -> List[int]:
    """'0110' or [0,1,1,0] → list of ints."""
    if isinstance(row, str):
        return [int(ch) for ch in row]
    return [int(v) for v in row]


def next_greater_element(nums: List[int]) -> List[int]:
    res = [-1] * len(nums)
    stack: List[int] = []                         # indices, values descending
    for i, v in enumerate(nums):
        while stack and nums[stack[-1]] < v:
            res[stack.pop()] = v
        stack.append(i)
    return res


def previous_greater_element(nums: List[int]) -> List[int]:
    res = [-1] * len(nums)
    stack: List[int] = []                         # values, strictly descending
    for i, v in enumerate(nums):
        while stack and nums[stack[-1]] <= v:
            stack.pop()
        if stack:
            res[i] = nums[stack[-1]]
        stack.append(i)
    return res


def daily_temperatures(temps: List[int]) -> List[int]:
    res = [0] * len(temps)
    stack: List[int] = []                          # indices with warmer pending
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            j = stack.pop()
            res[j] = i - j
        stack.append(i)
    return res


def largest_rectangle_in_histogram(heights: List[int]) -> int:
    best = 0
    stack: List[Tuple[int, int]] = []             # (start_index, height)
    for i, h in enumerate(list(heights) + [0]):    # sentinel flush
        start = i
        while stack and stack[-1][1] > h:
            j, hj = stack.pop()
            best = max(best, hj * (i - j))
            start = j
        if h > 0:
            stack.append((start, h))
    return best


def maximal_square(matrix: Matrix) -> int:
    if not matrix:
        return 0
    rows = [_cells(r) for r in matrix]
    if not rows[0]:
        return 0
    n_cols = len(rows[0])
    dp = [0] * (n_cols + 1)
    best = 0
    for row in rows:
        new = [0] * (n_cols + 1)
        for j, cell in enumerate(row):
            if cell:
                new[j + 1] = min(dp[j], dp[j + 1], new[j]) + 1
                best = max(best, new[j + 1])
        dp = new
    return best * best


def maximal_rectangle(matrix: Matrix) -> int:
    if not matrix:
        return 0
    rows = [_cells(r) for r in matrix]
    if not rows[0]:
        return 0
    n_cols = len(rows[0])
    heights = [0] * n_cols
    best = 0
    for row in rows:
        for j in range(n_cols):
            heights[j] = heights[j] + 1 if row[j] else 0
        best = max(best, largest_rectangle_in_histogram(heights))
    return best


def stock_span(prices: List[int]) -> List[int]:
    res: List[int] = []
    stack: List[Tuple[int, int]] = []              # (price, span)
    for p in prices:
        span = 1
        while stack and stack[-1][0] <= p:
            span += stack.pop()[1]
        stack.append((p, span))
        res.append(span)
    return res
