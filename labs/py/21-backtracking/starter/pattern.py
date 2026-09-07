"""Lab 21 — backtracking. Fill in every TODO. Tests define done.

Rules:
  * Classic choose/explore/unchoose. No global mutable result lists that leak
    between calls (except explicit in-place semantics in solve_sudoku).
  * Determinism: sorted order where the spec says so, and identical inputs
    produce identical outputs.
  * No itertools for the core generators — that's what you're implementing.
  * The sudokus: fixture-style constants live in the tests; your functions
    take boards, not hardcoded puzzles.
"""
from __future__ import annotations

from typing import List, Optional


def subsets(nums: List[int]) -> List[List[int]]:
    """Power set of DISTINCT elements. 2^n results. Empty input -> [[]]."""
    raise NotImplementedError


def subsets_with_dup(nums: List[int]) -> List[List[int]]:
    """Power set of a MULTISET: each distinct subset once. Sort first,
    skip duplicates at the same tree level."""
    raise NotImplementedError


def permutations(nums: List[int]) -> List[List[int]]:
    """All n! orders of distinct elements."""
    raise NotImplementedError


def permutations_with_dup(nums: List[int]) -> List[List[int]]:
    """Distinct orders of a multiset ([1,1,2] -> 3 results)."""
    raise NotImplementedError


def combinations(n: int, k: int) -> List[List[int]]:
    """All k-subsets of 1..n, lexicographic order. k==0 or k==n -> one result."""
    raise NotImplementedError


def solve_n_queens(n: int) -> Optional[List[str]]:
    """One n-queens board (rows of '.'/'Q'), or None if n has no solution."""
    raise NotImplementedError


def count_n_queens(n: int) -> int:
    """Number of n-queens solutions. n=0 -> 1 (the empty board)."""
    raise NotImplementedError


def word_search(board: List[List[str]], word: str) -> bool:
    """True if word traces a contiguous 4-directional path (cell once per word)."""
    raise NotImplementedError


def generate_parentheses(n: int) -> List[str]:
    """All valid combos of n pairs, output sorted (deterministic). Catalan(n) of them."""
    raise NotImplementedError


def is_valid_sudoku(board: List[List[int]]) -> bool:
    """True if every row/col/3x3 box has no repeated non-zero digit."""
    raise NotImplementedError


def solve_sudoku(board: List[List[int]]) -> List[List[int]]:
    """Solve in place (0 = empty) and return the board. Assume solvable.

    Deterministic: fill candidates 1..9 in order at the first empty cell.
    """
    raise NotImplementedError
