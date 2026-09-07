"""Lab 21 — backtracking. Reference solution."""
from __future__ import annotations

from typing import List, Optional


def subsets(nums: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    cur: List[int] = []

    def bt(i: int) -> None:
        if i == len(nums):
            out.append(list(cur))
            return
        cur.append(nums[i])                 # choose
        bt(i + 1)                           # explore
        cur.pop()                           # unchoose
        bt(i + 1)

    bt(0)
    return out


def subsets_with_dup(nums: List[int]) -> List[List[int]]:
    ns = sorted(nums)
    out: List[List[int]] = []
    cur: List[int] = []

    def bt(i: int) -> None:
        if i == len(ns):
            out.append(list(cur))
            return
        cur.append(ns[i])
        bt(i + 1)
        cur.pop()
        # skip the whole run of duplicates at this level
        j = i + 1
        while j < len(ns) and ns[j] == ns[i]:
            j += 1
        bt(j)

    bt(0)
    return out


def permutations(nums: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    used = [False] * len(nums)

    def bt(cur: List[int]) -> None:
        if len(cur) == len(nums):
            out.append(list(cur))
            return
        for i in range(len(nums)):
            if used[i]:
                continue
            used[i] = True
            cur.append(nums[i])
            bt(cur)
            cur.pop()
            used[i] = False

    bt([])
    return out


def permutations_with_dup(nums: List[int]) -> List[List[int]]:
    ns = sorted(nums)
    out: List[List[int]] = []

    def bt(cur: List[int], used: List[bool]) -> None:
        if len(cur) == len(ns):
            out.append(list(cur))
            return
        for i in range(len(ns)):
            if used[i]:
                continue
            if i > 0 and ns[i] == ns[i - 1] and not used[i - 1]:
                continue                    # same-level duplicate skip
            used[i] = True
            cur.append(ns[i])
            bt(cur, used)
            cur.pop()
            used[i] = False

    bt([], [False] * len(ns))
    return out


def combinations(n: int, k: int) -> List[List[int]]:
    out: List[List[int]] = []

    def bt(start: int, cur: List[int]) -> None:
        if len(cur) == k:
            out.append(list(cur))
            return
        for v in range(start, n + 1):
            cur.append(v)
            bt(v + 1, cur)
            cur.pop()

    bt(1, [])
    return out


def solve_n_queens(n: int) -> Optional[List[str]]:
    if n == 0:
        return []
    board = [-1] * n                        # row -> col

    def ok(row: int, col: int) -> bool:
        for r in range(row):
            c = board[r]
            if c == col or abs(c - col) == row - r:
                return False
        return True

    def bt(row: int) -> bool:
        if row == n:
            return True
        for col in range(n):
            if ok(row, col):
                board[row] = col
                if bt(row + 1):
                    return True
                board[row] = -1
        return False

    if not bt(0):
        return None
    out = []
    for r in range(n):
        out.append("".join("Q" if board[r] == c else "." for c in range(n)))
    return out


def count_n_queens(n: int) -> int:
    if n == 0:
        return 1
    cols = [False] * n
    diag1 = [False] * (2 * n)               # r - c + n
    diag2 = [False] * (2 * n)               # r + c
    total = 0

    def bt(row: int) -> None:
        nonlocal total
        if row == n:
            total += 1
            return
        for c in range(n):
            if cols[c] or diag1[row - c + n] or diag2[row + c]:
                continue
            cols[c] = diag1[row - c + n] = diag2[row + c] = True
            bt(row + 1)
            cols[c] = diag1[row - c + n] = diag2[row + c] = False

    bt(0)
    return total


def word_search(board: List[List[str]], word: str) -> bool:
    if not word:
        return True
    if not board or not board[0]:
        return False
    rows, cols = len(board), len(board[0])

    def bt(r: int, c: int, i: int) -> bool:
        if i == len(word):
            return True
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return False
        if board[r][c] != word[i]:
            return False
        ch = board[r][c]
        board[r][c] = "#"
        found = (bt(r + 1, c, i + 1) or bt(r - 1, c, i + 1)
                 or bt(r, c + 1, i + 1) or bt(r, c - 1, i + 1))
        board[r][c] = ch
        return found

    for r in range(rows):
        for c in range(cols):
            if bt(r, c, 0):
                return True
    return False


def generate_parentheses(n: int) -> List[str]:
    out: List[str] = []

    def bt(cur: str, opens: int, closes: int) -> None:
        if len(cur) == 2 * n:
            out.append(cur)
            return
        if opens < n:
            bt(cur + "(", opens + 1, closes)
        if closes < opens:
            bt(cur + ")", opens, closes + 1)

    bt("", 0, 0)
    return sorted(out)


def is_valid_sudoku(board: List[List[int]]) -> bool:
    for i in range(9):
        row = [v for v in board[i] if v]
        col = [board[r][i] for r in range(9) if board[r][i]]
        if len(row) != len(set(row)) or len(col) != len(set(col)):
            return False
    for br in range(0, 9, 3):
        for bc in range(0, 9, 3):
            box = [board[br + r][bc + c]
                   for r in range(3) for c in range(3)
                   if board[br + r][bc + c]]
            if len(box) != len(set(box)):
                return False
    return True


def solve_sudoku(board: List[List[int]]) -> List[List[int]]:
    rows = [set(range(1, 10)) for _ in range(9)]
    cols = [set(range(1, 10)) for _ in range(9)]
    boxes = [set(range(1, 10)) for _ in range(9)]
    empties = []
    for r in range(9):
        for c in range(9):
            v = board[r][c]
            if v:
                rows[r].discard(v)
                cols[c].discard(v)
                boxes[(r // 3) * 3 + c // 3].discard(v)
            else:
                empties.append((r, c))

    def bt(i: int) -> bool:
        if i == len(empties):
            return True
        r, c = empties[i]
        b = (r // 3) * 3 + c // 3
        for v in sorted(rows[r] & cols[c] & boxes[b]):
            board[r][c] = v
            rows[r].discard(v)
            cols[c].discard(v)
            boxes[b].discard(v)
            if bt(i + 1):
                return True
            board[r][c] = 0
            rows[r].add(v)
            cols[c].add(v)
            boxes[b].add(v)
        return False

    bt(0)
    return board
