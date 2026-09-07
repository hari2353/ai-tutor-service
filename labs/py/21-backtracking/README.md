# Lab 21: Backtracking

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p21-backtracking`

**You will build:** the backtracking family — subsets/permutations/combinations (with the dedup variants), N-Queens (count and board), word search on a grid, generate-parentheses, and a full 9×9 Sudoku solver with a fixed solvable puzzle in the fixtures.

**You will be able to answer:** *"Backtracking is exponential — so why does it power Sudoku solvers, crossword compilers, and SAT preprocessors? And when is it simply the wrong tool?"*

## Setup

```bash
cd labs/py/21-backtracking
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`subsets(nums)`** — all subsets (power set), any order, exactly 2ⁿ subsets, no duplicates even when `nums` has duplicate values (dedup variant included: input may contain repeats; result must have each distinct subset once). Empty input → `[[]]`.
2. **`subsets_with_dup(nums)`** — power set of a multiset: each distinct subset once (input `[1,2,2]` yields 6, not 8).
3. **`permutations(nums)`** — all orders of distinct elements, n! results, no duplicates.
4. **`permutations_with_dup(nums)`** — all distinct orders of a multiset (`[1,1,2]` → 3 orders).
5. **`combinations(n, k)`** — all k-sized subsets of 1..n in lexicographic order; `combinations(4, 2)` has exactly 6 results.
6. **`solve_n_queens(n)`** — return **one** solution board (list of strings, `Q`/`.`), or `None` if impossible (n=2, n=3); `count_n_queens(n)` — number of solutions (n=1→1, n=4→2, n=5→10, n=8→92).
7. **`word_search(board, word)`** — True if `word` is a contiguous 4-directional path on the board (cells reusable across different searches but once within a word).
8. **`generate_parentheses(n)`** — all valid combos of n pairs, sorted output (deterministic), Catalan(n) results.
9. **`solve_sudoku(board)`** — 9×9 grid of digits 0-9 or the string puzzle rows (fixtures give one fixed solvable puzzle); solve **in place**, return the board; `is_valid_sudoku(board)` checks row/col/box constraints. The fixture puzzle has a unique solution — the test asserts the exact completed grid.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Pruning wins** — add the "occupied columns/diagonals bitmask" optimization to N-Queens and count how much faster n=12 becomes; state the complexity honestly.
2. **Sudoku with constraint propagation** — before recursing, propagate singles (naked singles via row/col/box candidate sets); note the node-count drop.
3. **Word search with trie pruning** — search many words at once (lab 18 crossover).
4. **When NOT to backtrack** — estimate the branching factor × depth for a 100-city TSP and articulate why you want DP/mip/2-opt instead; write one sentence per failure mode in your own words.
