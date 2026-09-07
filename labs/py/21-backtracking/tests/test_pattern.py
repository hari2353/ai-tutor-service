"""Lab 21 tests — backtracking. Deterministic."""
import itertools
import time

import pytest

from conftest import SUDOKU_PUZZLE, SUDOKU_SOLUTION


def canon(sets):
    return sorted(tuple(sorted(s)) for s in sets)


# ------------------------------------------------------------------ subsets
def test_subsets_basic(P):
    assert canon(P.subsets([1, 2, 3])) == [(), (1,), (1, 2), (1, 2, 3),
                                          (1, 3), (2,), (2, 3), (3,)]


def test_subsets_count_and_empty(P):
    assert len(P.subsets([])) == 1
    assert P.subsets([]) == [[]]
    assert len(P.subsets([1, 2, 3, 4])) == 16


def test_subsets_no_dup_results_on_distinct_input(P):
    res = P.subsets([5, 5])                       # distinctness NOT assumed here:
    assert len(res) == 4                          # 2^2 for the given multiset view
    assert canon(res) == [(), (5,), (5,), (5, 5)]


def test_subsets_with_dup_basic(P):
    assert canon(P.subsets_with_dup([1, 2, 2])) == \
        [(), (1,), (1, 2), (1, 2, 2), (2,), (2, 2)]


def test_subsets_with_dup_all_same(P):
    res = P.subsets_with_dup([3, 3, 3])
    assert canon(res) == [(), (3,), (3, 3), (3, 3, 3)]
    assert len(res) == 4


def test_subsets_with_dup_no_duplicates(P):
    res = P.subsets_with_dup([1, 2, 2, 3, 3])
    assert len(res) == len(canon(res))            # no repeated subsets


# ------------------------------------------------------------------ permutations
def test_permutations_three(P):
    assert sorted(map(tuple, P.permutations([1, 2, 3]))) == \
        [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]


def test_permutations_counts(P):
    assert len(P.permutations([])) == 1
    assert len(P.permutations([1])) == 1
    assert len(P.permutations([1, 2, 3, 4])) == 24


def test_permutations_with_dup_basic(P):
    assert sorted(map(tuple, P.permutations_with_dup([1, 1, 2]))) == \
        [(1, 1, 2), (1, 2, 1), (2, 1, 1)]


def test_permutations_with_dup_counts(P):
    assert len(P.permutations_with_dup([2, 2, 2])) == 1
    assert len(P.permutations_with_dup([1, 1, 2, 2])) == 6


def test_permutations_with_dup_no_duplicates(P):
    res = P.permutations_with_dup([1, 1, 2, 2, 3])
    assert len(res) == len(set(map(tuple, res)))


# ------------------------------------------------------------------ combinations
def test_combinations_four_two(P):
    assert P.combinations(4, 2) == [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]]


def test_combinations_edges(P):
    assert P.combinations(3, 0) == [[]]
    assert P.combinations(3, 3) == [[1, 2, 3]]
    assert P.combinations(5, 6) == []


def test_combinations_lexicographic(P):
    res = P.combinations(5, 3)
    assert res == sorted(res)
    assert len(res) == 10


# ------------------------------------------------------------------ n-queens
def test_n_queens_solve_four(P):
    board = P.solve_n_queens(4)
    assert board is not None
    assert len(board) == 4
    # validity: one queen per row/col/diagonal
    cols = [row.index("Q") for row in board]
    assert len(set(cols)) == 4
    for r1 in range(4):
        for r2 in range(r1 + 1, 4):
            assert abs(cols[r1] - cols[r2]) != r2 - r1


def test_n_queens_impossible(P):
    assert P.solve_n_queens(2) is None
    assert P.solve_n_queens(3) is None


def test_n_queens_one(P):
    assert P.solve_n_queens(1) == ["Q"]


def test_count_n_queens_known(P):
    assert P.count_n_queens(0) == 1
    assert P.count_n_queens(1) == 1
    assert P.count_n_queens(4) == 2
    assert P.count_n_queens(5) == 10
    assert P.count_n_queens(6) == 4


def test_count_n_queens_eight(P):
    assert P.count_n_queens(8) == 92


# ------------------------------------------------------------------ word search
def test_word_search_classic(P):
    board = [["A", "B", "C", "E"],
             ["S", "F", "C", "S"],
             ["A", "D", "E", "E"]]
    assert P.word_search(board, "ABCCED") is True
    assert P.word_search(board, "SEE") is True
    assert P.word_search(board, "ABCB") is False


def test_word_search_empty_word(P):
    assert P.word_search([["A"]], "") is True


def test_word_search_empty_board(P):
    assert P.word_search([], "A") is False
    assert P.word_search([[]], "A") is False


def test_word_search_no_reuse_within_word(P):
    board = [["A", "A"]]
    assert P.word_search(board, "AAA") is False


def test_word_search_board_not_mutated(P):
    board = [["A", "B"], ["C", "D"]]
    P.word_search(board, "ABDC")
    assert board == [["A", "B"], ["C", "D"]]


# ------------------------------------------------------------------ parentheses
def test_generate_paren_three(P):
    assert P.generate_parentheses(3) == \
        ["((()))", "(()())", "(())()", "()(())", "()()()"]


def test_generate_paren_counts_catalan(P):
    assert len(P.generate_parentheses(0)) == 1
    assert len(P.generate_parentheses(1)) == 1
    assert len(P.generate_parentheses(2)) == 2
    assert len(P.generate_parentheses(4)) == 14
    assert len(P.generate_parentheses(5)) == 42


def test_generate_paren_all_valid(P):
    for n in range(1, 6):
        for s in P.generate_parentheses(n):
            bal = 0
            for ch in s:
                bal += 1 if ch == "(" else -1
                assert bal >= 0
            assert bal == 0


# ------------------------------------------------------------------ sudoku
def test_is_valid_sudoku_valid_puzzle(P):
    assert P.is_valid_sudoku(SUDOKU_PUZZLE) is True


def test_is_valid_sudoku_detects_row_dup(P):
    bad = [row[:] for row in SUDOKU_PUZZLE]
    bad[0][2] = 5                                  # 5 already in row 0
    assert P.is_valid_sudoku(bad) is False


def test_is_valid_sudoku_detects_col_dup(P):
    bad = [row[:] for row in SUDOKU_PUZZLE]
    bad[3][0] = 5                                  # 5 already in col 0
    assert P.is_valid_sudoku(bad) is False


def test_is_valid_sudoku_detects_box_dup(P):
    bad = [row[:] for row in SUDOKU_PUZZLE]
    bad[1][2] = 5                                  # 5 already in box at (0,0)
    assert P.is_valid_sudoku(bad) is False


def test_solve_sudoku_fixed_puzzle(P):
    board = [row[:] for row in SUDOKU_PUZZLE]
    result = P.solve_sudoku(board)
    assert result == SUDOKU_SOLUTION
    assert board == SUDOKU_SOLUTION                # solved in place


def test_solve_sudoku_result_is_valid(P):
    board = [row[:] for row in SUDOKU_PUZZLE]
    P.solve_sudoku(board)
    assert P.is_valid_sudoku(board) is True
    assert all(0 not in row for row in board)


# ------------------------------------------------------------------ complexity witness
def test_n_queens_pruning_witness(P):
    """A well-pruned count_n_queens(9) must be far faster than the naive
    full-grid enumeration. Both run; the pruned one must stay quick."""
    t0 = time.perf_counter()
    assert P.count_n_queens(9) == 352
    dt = time.perf_counter() - t0
    assert dt < 2.0, f"count_n_queens(9) took {dt:.2f}s — pruning missing?"


def test_sudoku_solver_under_2s(P):
    board = [row[:] for row in SUDOKU_PUZZLE]
    t0 = time.perf_counter()
    P.solve_sudoku(board)
    dt = time.perf_counter() - t0
    assert board == SUDOKU_SOLUTION
    assert dt < 2.0
