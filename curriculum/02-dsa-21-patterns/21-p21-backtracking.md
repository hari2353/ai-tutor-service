# Pattern: Backtracking

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** recursion, T02-p10-subsets, arrays
> **Module id:** `T02-p21-backtracking` · **Tags:** pattern, recursion
> **Practice:** the Problems tab in the app — this pattern has curated LeetCode problems rather than a lab

## The 30-second version

Backtracking is exhaustive search over a decision tree with early exit: at every node you **choose** a candidate, **explore** the consequences recursively, then **unchoose** it (undo the mutation) before trying the next candidate — that unchoose step is what lets a single mutable data structure (one list, one board, one partial string) stand in for the entire tree of possibilities instead of copying state at every level. The skeleton is four lines: check the base case, loop over choices, recurse after choosing, undo after returning. What separates a working solution from a brute-force timeout is **pruning** — checking a constraint before recursing (or as early as possible inside the loop) so entire invalid subtrees are never explored, rather than generating every possibility and filtering at the leaves. Recognize it whenever a problem says "generate all," "find all valid," or "count the number of ways" over combinatorial structures (subsets, permutations, board placements, partitions) where a partial choice can be checked for validity before committing further — that "check early, prune hard" property is what turns naive exponential enumeration into a tractable exponential-but-pruned search.

## Why this gets asked

It tests whether you can write recursive search with in-place mutation and correct cleanup instead of leaking state across branches or reaching for expensive copying at every level, and whether you actually prune instead of generating everything and filtering afterward — the difference between a solution that finishes and one that times out on the exact same input. Interviewers who've built constraint solvers, scheduling/allocation systems with hard constraints (room booking, shift assignment), config/dependency resolution (SAT-adjacent constraint checking), or puzzle/game engines (any board-placement or move-generation logic) have hit the real failure this models: an exhaustive search that's correct but explores orders of magnitude more states than necessary because it doesn't prune as early as the problem's constraints actually allow.

---

## Lineage: past → present → future

**What came before.** The direct ancestor is plain brute-force enumeration — generate every possible combination/permutation/arrangement, then filter for validity at the end. This is correct but wasteful: for N-Queens on an 8x8 board, brute-force placing 8 queens with no constraint checking explores `64 choose 8` (over 4 billion) placements before filtering, while pruning row/column/diagonal conflicts as each queen is placed cuts this to roughly 2,057 actual board states explored. Backtracking as a formalized technique traces to 1950s-60s combinatorial search work (the term itself is attributed to D.H. Lehmer, and it was refined through AI/constraint-satisfaction research in the 1960s-70s); the pain it killed was exactly this — brute-force enumeration's inability to abandon an invalid partial solution before fully constructing it.

**Where it stands now.** Settled as a technique; the live, real engineering questions are about pruning strategy and ordering, not the core recursion skeleton. **Constraint propagation** (checking not just "is this choice valid right now" but "does this choice make some *other* future choice impossible," e.g., forward-checking in constraint satisfaction) prunes more aggressively than naive backtracking at the cost of more bookkeeping per node — this is the live tradeoff in real constraint solvers (SAT/SMT solvers, CSP libraries) versus textbook backtracking. **Branch-and-bound** extends backtracking with a bound function to prune optimization problems (not just feasibility problems) the moment a partial solution's best-possible outcome can't beat a known solution. Interviewers rarely expect full CSP machinery, but naming that these exist as a "next step past plain backtracking" is a senior signal.

**Where it's heading.** No paradigm shift expected at interview scope. In production, actual constraint-satisfaction and combinatorial-optimization problems at scale (scheduling, resource allocation, verification) are solved with dedicated SAT/SMT/CP solvers (Z3, OR-Tools CP-SAT, MiniZinc-backed solvers) that implement highly optimized backtracking-plus-propagation-plus-learning (conflict-driven clause learning, in modern SAT solvers) rather than hand-rolled recursive backtracking — knowing to reach for OR-Tools instead of hand-rolling N-Queens-style search for a real production constraint problem is the correct senior answer, the same way LP/ILP solvers are the correct answer past hand-rolled knapsack DP at scale.

---

## Mental model

A decision tree where you walk down, try a choice, and if it doesn't pan out (or you've explored everything below it), you walk back up and undo it before trying the sibling choice.

```
choose/explore/unchoose over {1, 2, 3}, building all subsets:

                        []
          choose 1 /    |    \ choose 2         \ choose 3
              [1]      [2]                       [3]
           /      \      \
      choose 2   choose 3  choose 3
        [1,2]      [1,3]     [2,3]
          \
        choose 3
         [1,2,3]

at [1,2]: choose 3 -> explore [1,2,3] -> record it -> UNCHOOSE (pop 3) -> back to [1,2]
at [1,2]: no more choices -> UNCHOOSE (pop 2) -> back to [1]
at [1]:   choose 3 -> explore [1,3] -> record -> UNCHOOSE -> back to [1]
at [1]:   no more choices -> UNCHOOSE (pop 1) -> back to []
... continue with choose 2, choose 3 from the root
```

The single mutable list `[1, 2, ...]` (or board, or partial string) is reused at every level — pushed to on choose, popped on unchoose — so the entire tree is walked with O(depth) extra memory for the "current path," not O(tree size).

---

## Recognition heuristics

- **"Generate all subsets/permutations/combinations"** — the direct combinatorial-enumeration tell (overlaps with `T02-p10-subsets`, but backtracking is the general mechanism subsets/permutations are built from).
- **"Find all valid ways to place N non-attacking queens/pieces on a board"** — board-placement problems where each placement invalidates certain future placements (N-Queens).
- **"Partition a string/array into valid pieces"** subject to a constraint checkable on each piece independently (Palindrome Partitioning: each substring must itself be a palindrome).
- **"Fill in a grid/board so every row/column/region satisfies a constraint"** (Sudoku Solver) — the constraint can be checked incrementally as each cell is filled, which is exactly what makes pruning effective.
- **"Return all combinations that sum to a target"** where numbers can or cannot repeat (Combination Sum family) — partial sums can be checked against the target *before* recursing further, pruning branches that have already exceeded it.
- **A qualifier like "the number of valid boards/paths can be large but the search space, if pruned, is manageable"** — signals the interviewer wants pruning, not naive enumeration.

If the problem asks only for a **count** or an **optimal value** rather than the actual list of valid configurations, and has overlapping subproblems (the same partial state reachable multiple ways), it may be a DP problem in disguise (`T02-p15-knapsack-01`, `T02-p16-knapsack-unbounded`) rather than pure backtracking — backtracking enumerates; DP counts/optimizes without re-deriving each path.

---

## How it actually works — the choose/explore/unchoose skeleton and pruning

**The skeleton, made explicit.**

```
def backtrack(state, choices_remaining):
    if is_complete(state):
        record(state)              # base case: a full valid (or complete) state found
        return
    for choice in candidates(state, choices_remaining):
        if not is_valid(state, choice):     # PRUNE: skip invalid choices before recursing
            continue
        choose(state, choice)               # mutate state in place
        backtrack(state, choices_remaining - {choice})
        unchoose(state, choice)             # undo the mutation — this is what makes reuse safe
```

Three moving parts, and losing any one of them breaks correctness or efficiency:
- **Choose** mutates the shared state (append to a list, place a queen, fill a cell) so the recursive call sees the world as it would be with this choice made.
- **Explore** is the recursive call itself — it's where "try everything from here" happens.
- **Unchoose** undoes exactly the mutation `choose` made, restoring the state to what it was before this iteration, so the *next* sibling choice in the loop starts from a clean slate. Forgetting this is the single most common backtracking bug: without unchoosing, state mutated by one branch leaks into sibling branches that never actually should have seen it.

**Why pruning is the entire efficiency story.** Every problem in this pattern has an exponential-sized *raw* search space (all subsets, all permutations, all board fillings), and backtracking's value proposition is never changing that asymptotic worst case in the theoretical sense — N-Queens is still exponential, Sudoku is still exponential in general grid size — but pruning changes the *actual* explored fraction of that space enormously in practice. Concretely, for N-Queens, checking row/column/diagonal conflicts *before* placing the next queen (rather than placing all N queens and checking validity only at the end) means an invalid partial placement is abandoned after just a few queens instead of after placing all N and discovering it's invalid combinatorially later — this is the difference between exploring `~4 x 10^9` raw placements and `~2,057` actual states for 8-Queens. The earlier a check happens in the loop/recursion, the more of the invalid subtree underneath it gets skipped entirely.

**Where the choices come from matters too.** Structuring the "candidates" generation itself to only ever produce locally-consistent choices (e.g., only trying columns not already occupied in N-Queens, rather than trying all columns and checking afterward) is an even stronger form of pruning than a post-hoc validity check — it avoids generating the invalid candidate at all, rather than generating and then rejecting it.

---

## Template code (Python, Java, Go)

```python
# Python — Subsets (LC 78): the base choose/explore/unchoose skeleton
def subsets(nums: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    path: list[int] = []

    def backtrack(start: int):
        result.append(path[:])                      # every partial state is itself valid here
        for i in range(start, len(nums)):
            path.append(nums[i])                     # choose
            backtrack(i + 1)                          # explore
            path.pop()                                # unchoose

    backtrack(0)
    return result

# Permutations (LC 46) — uses a "used" tracker instead of a start index
def permute(nums: list[int]) -> list[list[int]]:
    result: list[list[int]] = []
    path: list[int] = []
    used = [False] * len(nums)

    def backtrack():
        if len(path) == len(nums):
            result.append(path[:])
            return
        for i in range(len(nums)):
            if used[i]:
                continue
            used[i] = True                            # choose
            path.append(nums[i])
            backtrack()                                # explore
            path.pop()                                  # unchoose
            used[i] = False

    backtrack()
    return result

# N-Queens (LC 51) — pruning via column/diagonal conflict sets, checked BEFORE recursing
def solve_n_queens(n: int) -> list[list[str]]:
    result: list[list[str]] = []
    cols: set[int] = set()
    diag1: set[int] = set()    # row - col constant along one diagonal
    diag2: set[int] = set()    # row + col constant along the other diagonal
    placement: list[int] = []   # placement[row] = col

    def backtrack(row: int):
        if row == n:
            board = []
            for c in placement:
                board.append("." * c + "Q" + "." * (n - c - 1))
            result.append(board)
            return
        for col in range(n):
            if col in cols or (row - col) in diag1 or (row + col) in diag2:
                continue                                # PRUNE before recursing
            cols.add(col); diag1.add(row - col); diag2.add(row + col)  # choose
            placement.append(col)
            backtrack(row + 1)                           # explore
            placement.pop()                              # unchoose
            cols.remove(col); diag1.remove(row - col); diag2.remove(row + col)

    backtrack(0)
    return result

# Combination Sum (LC 39) — numbers reusable, prune when running sum exceeds target
def combination_sum(candidates: list[int], target: int) -> list[list[int]]:
    result: list[list[int]] = []
    path: list[int] = []

    def backtrack(start: int, remaining: int):
        if remaining == 0:
            result.append(path[:])
            return
        for i in range(start, len(candidates)):
            if candidates[i] > remaining:               # PRUNE: sorted candidates assumed
                break
            path.append(candidates[i])                  # choose
            backtrack(i, remaining - candidates[i])       # explore (i, not i+1: reuse allowed)
            path.pop()                                    # unchoose

    candidates.sort()
    backtrack(0, target)
    return result
```

```java
// Java — Subsets (LC 78)
public List<List<Integer>> subsets(int[] nums) {
    List<List<Integer>> result = new ArrayList<>();
    backtrack(nums, 0, new ArrayList<>(), result);
    return result;
}

private void backtrack(int[] nums, int start, List<Integer> path, List<List<Integer>> result) {
    result.add(new ArrayList<>(path));
    for (int i = start; i < nums.length; i++) {
        path.add(nums[i]);                 // choose
        backtrack(nums, i + 1, path, result); // explore
        path.remove(path.size() - 1);       // unchoose
    }
}

// N-Queens (LC 51) — pruning via conflict sets
public List<List<String>> solveNQueens(int n) {
    List<List<String>> result = new ArrayList<>();
    Set<Integer> cols = new HashSet<>(), diag1 = new HashSet<>(), diag2 = new HashSet<>();
    int[] placement = new int[n];
    backtrackQueens(0, n, cols, diag1, diag2, placement, result);
    return result;
}

private void backtrackQueens(int row, int n, Set<Integer> cols, Set<Integer> diag1,
                              Set<Integer> diag2, int[] placement, List<List<String>> result) {
    if (row == n) {
        List<String> board = new ArrayList<>();
        for (int c : placement) {
            StringBuilder sb = new StringBuilder();
            for (int j = 0; j < n; j++) sb.append(j == c ? 'Q' : '.');
            board.add(sb.toString());
        }
        result.add(board);
        return;
    }
    for (int col = 0; col < n; col++) {
        int d1 = row - col, d2 = row + col;
        if (cols.contains(col) || diag1.contains(d1) || diag2.contains(d2)) continue; // prune
        cols.add(col); diag1.add(d1); diag2.add(d2); placement[row] = col;            // choose
        backtrackQueens(row + 1, n, cols, diag1, diag2, placement, result);            // explore
        cols.remove(col); diag1.remove(d1); diag2.remove(d2);                          // unchoose
    }
}
```

```go
// Go — Subsets (LC 78)
func subsets(nums []int) [][]int {
    var result [][]int
    var path []int

    var backtrack func(start int)
    backtrack = func(start int) {
        snapshot := make([]int, len(path))
        copy(snapshot, path)
        result = append(result, snapshot)
        for i := start; i < len(nums); i++ {
            path = append(path, nums[i]) // choose
            backtrack(i + 1)             // explore
            path = path[:len(path)-1]    // unchoose
        }
    }
    backtrack(0)
    return result
}

// N-Queens (LC 51) — pruning via conflict sets
func solveNQueens(n int) [][]string {
    var result [][]string
    cols := make(map[int]bool)
    diag1 := make(map[int]bool)
    diag2 := make(map[int]bool)
    placement := make([]int, 0, n)

    var backtrack func(row int)
    backtrack = func(row int) {
        if row == n {
            board := make([]string, n)
            for r, c := range placement {
                row := make([]byte, n)
                for j := range row {
                    row[j] = '.'
                }
                row[c] = 'Q'
                board[r] = string(row)
            }
            result = append(result, board)
            return
        }
        for col := 0; col < n; col++ {
            d1, d2 := row-col, row+col
            if cols[col] || diag1[d1] || diag2[d2] {
                continue // prune
            }
            cols[col], diag1[d1], diag2[d2] = true, true, true // choose
            placement = append(placement, col)
            backtrack(row + 1) // explore
            placement = placement[:len(placement)-1]
            cols[col], diag1[d1], diag2[d2] = false, false, false // unchoose
        }
    }
    backtrack(0)
    return result
}
```

## Complexity, derived

Backtracking's complexity is inherently problem-specific and exponential in the worst case, since it's exhaustively searching a combinatorial space: **Subsets** is O(2^n) states (every subset), each recorded in O(n) to copy, giving O(n·2^n) total. **Permutations** is O(n!) states, each O(n) to build, giving O(n·n!) total. **N-Queens** without any pruning would explore up to `C(n², n)` raw placements; with column/diagonal pruning applied *before* recursing (as in the template), the actual explored state count drops dramatically in practice (roughly 2,057 states for 8-Queens instead of billions), though the *worst-case theoretical bound* remains exponential — pruning changes the practical constant/base of the exponential, not its fundamental exponential nature. **Combination Sum**-style problems are bounded by the number of valid combinations found times the depth to build each, with the `if candidates[i] > remaining: break` prune (on sorted input) cutting off entire remaining-candidate ranges in O(1) per level rather than exploring them. The unifying honest statement: backtracking does not turn an NP-hard-shaped enumeration problem into a polynomial one; it turns a naive "generate everything then filter" into "generate only what survives constraints so far," which is a real, large, but non-asymptotic improvement.

---

## The 5 variants interviewers actually ask

1. **Subsets / Permutations / Combinations (LC 78, 46, 77) — the base skeleton with different choice-tracking mechanisms.** Subsets uses a start-index to avoid revisiting earlier elements; permutations use a `used[]` tracker since every element can appear in any position; combinations fix the output size and use a start-index like subsets.
2. **N-Queens (LC 51) / N-Queens II (LC 52) — board-placement with incremental constraint checking.** The interview differentiator is whether you check conflicts *before* recursing (via column/diagonal tracking sets) versus generating a full placement and validating afterward — the latter is correct but loses the entire point of the pattern's efficiency story.
3. **Combination Sum family (LC 39, 40, 216) — sum-target problems with different reuse/duplicate rules.** LC 39 allows unlimited reuse of each candidate (recurse with the same start index `i`, not `i+1`); LC 40 has each candidate usable once with possible duplicates in the input (recurse with `i+1`, and explicitly skip duplicate values at the same recursion depth to avoid duplicate output combinations); LC 216 fixes both the count of numbers used and the target sum simultaneously.
4. **Palindrome Partitioning (LC 131) — partition a string into pieces, each satisfying a checkable constraint.** Prune by only recursing into a substring if it's already a palindrome, checked before the recursive call, not after building a full partition and validating each piece afterward.
5. **Sudoku Solver (LC 37) / Word Search (LC 79) — grid-based backtracking with in-place board mutation.** Sudoku places a digit, recurses, and removes it on backtrack, pruning via row/column/box constraint checks before placing; Word Search marks a cell visited (or temporarily mutates the board) before recursing into neighbors and restores it afterward — the same choose/explore/unchoose discipline applied to a 2D grid instead of a list.

---

## Common bugs

- **Forgetting to unchoose (pop/remove/reset) after the recursive call returns.** This is the single most common backtracking bug — state from one branch silently leaks into sibling branches, producing wrong results that are often hard to spot because they look "almost right."
- **Appending a reference to the mutable path instead of a copy at the recording step.** `result.append(path)` instead of `result.append(path[:])` (Python) or `result.add(new ArrayList<>(path))` (Java) means every recorded "answer" is actually the *same* list object, which later mutations then silently corrupt after the fact — a bug that often doesn't show up until you print the final result and every entry looks identical.
- **Validating a completed candidate instead of pruning mid-construction.** Building a full N-Queens placement or a full Sudoku board before checking validity turns a search that should terminate branches early into one that pays the full exponential cost before ever discovering most branches are invalid.
- **Off-by-one in the reuse index for Combination Sum variants.** Using `i+1` when reuse is allowed (should be `i`) silently disables reuse; using `i` when reuse is not allowed (should be `i+1`) silently permits it — both produce plausible-looking but wrong output sets.
- **Not skipping duplicate values at the same recursion depth** in problems with duplicate input elements (Combination Sum II, Subsets II, Permutations II) — this produces duplicate output combinations/subsets/permutations that need deduplication after the fact instead of being correctly avoided during the search itself.
- **Recursion depth blowup on deep search trees** (e.g., very long strings for palindrome partitioning) — while rarely the primary concern for typical interview input sizes, it's worth naming as a real constraint for production-scale inputs, where an iterative stack-based backtracking implementation avoids language recursion limits.

---

## Interview questions

### Q1 — Generate all subsets of a set of distinct integers (LC 78).
**Testing:** the base choose/explore/unchoose skeleton.
**Answer:** Record every partial path as a valid subset; loop from a `start` index forward, choose (append), explore (recurse with `start+1`... actually `i+1`), unchoose (pop) after the recursive call returns.
**Follow-up trap:** *"What's the time complexity, and why?"* — O(n·2^n): there are 2^n subsets total, and copying each into the result costs O(n), so the dominant cost is the copy, not the recursion itself.

### Q2 — Generate all permutations of a set of distinct integers (LC 46).
**Testing:** adapting the skeleton when choices aren't naturally ordered by a start index.
**Answer:** Track a `used[]` boolean array instead of a start index, since any unused element can go in any remaining position; choose by marking used and appending, explore recursively, unchoose by unmarking and popping.
**Follow-up trap:** *"What changes if the input has duplicate values and you want distinct permutations only?"* — sort first, then at each recursion depth skip a candidate if it equals the previous candidate at the same depth AND the previous one hasn't been used yet (a specific duplicate-skipping condition, not just "skip if equal to previous"), to avoid generating the same permutation multiple times.

### Q3 — N-Queens (LC 51): place N queens on an N x N board so none attack each other; return all valid placements.
**Testing:** whether pruning happens before or after recursing, the central efficiency question of this whole pattern.
**Answer:** Track occupied columns and both diagonals (`row-col` and `row+col`, each constant along one diagonal direction) in sets; at each row, only recurse into columns not already conflicting, checked *before* the recursive call — this is what collapses 8-Queens from billions of raw placements to roughly 2,057 explored states.
**Follow-up trap:** *"What if you instead placed all N queens first and validated the whole board afterward?"* — still correct, but loses essentially all of the pattern's efficiency benefit, since you'd pay the cost of generating every full placement (`C(n²,n)`-scale) before discovering most of them are invalid, rather than abandoning invalid partial placements after just a few rows.

### Q4 — Combination Sum (LC 39): find all combinations of candidates (each reusable unlimited times) that sum to a target.
**Testing:** the reuse-index detail and the prune-on-sorted-input trick.
**Answer:** Sort candidates first; recurse with the *same* start index (not `start+1`) to allow reuse of the current candidate; prune by breaking out of the loop once `candidates[i] > remaining`, since all later candidates (sorted) are even larger and can't possibly fit.
**Follow-up trap:** *"How does this change if each candidate can only be used once, and the input may contain duplicates (Combination Sum II)?"* — recurse with `start+1` (no reuse) and explicitly skip a candidate if it equals the previous candidate *at the same recursion depth* (not globally), to avoid generating duplicate combinations while still allowing the same value to appear at different depths when it's a genuinely different occurrence.

### Q5 — Palindrome Partitioning (LC 131): partition a string into substrings that are all palindromes; return all such partitions.
**Testing:** pruning based on a per-candidate validity check rather than validating the whole partition afterward.
**Answer:** At each recursion step, try every possible next substring starting at the current position, but only recurse into it if it's already verified to be a palindrome — checked before recursing, not after a full partition is built.
**Follow-up trap:** *"How would you avoid recomputing palindrome-checks repeatedly for overlapping substrings?"* — precompute a 2D `isPalindrome[i][j]` table via DP in O(n²) upfront (a substring `[i,j]` is a palindrome iff `s[i]==s[j]` and `[i+1,j-1]` is a palindrome or empty), turning each check inside the backtracking loop into O(1) instead of O(n) per check.

### Q6 — Sudoku Solver (LC 37): fill a partially-completed 9x9 Sudoku board so every row, column, and 3x3 box contains 1-9 exactly once.
**Testing:** grid-based choose/explore/unchoose with multi-constraint pruning.
**Answer:** For each empty cell, try digits 1-9; only proceed with a digit if it doesn't already appear in the same row, column, or 3x3 box (checked before placing); place it, recurse to the next empty cell, and if that fails, remove the digit (unchoose) and try the next candidate digit.
**Follow-up trap:** *"How would you speed this up beyond basic row/column/box pruning?"* — pick the empty cell with the *fewest* remaining valid candidates at each step (minimum-remaining-values heuristic, a constraint-propagation idea) rather than always scanning cells in a fixed left-to-right, top-to-bottom order — this prunes the search tree far more aggressively by tackling the most constrained cells first.

### Q7 — Word Search (LC 79): determine if a word can be constructed from adjacent cells in a grid, each cell used at most once.
**Testing:** in-place mutation and restoration on a 2D grid instead of a 1D list.
**Answer:** DFS from every starting cell matching the word's first character; temporarily mark the current cell visited (e.g., overwrite it with a sentinel character) before recursing into neighbors, and restore the original character (unchoose) after the recursive calls return, regardless of whether that branch succeeded.
**Follow-up trap:** *"Why is restoring the cell necessary even on a successful match deep in the recursion?"* — because sibling starting positions or other unexplored paths from earlier in the search may need to reuse that same cell; failing to restore it (or restoring only on the failure path) corrupts the board for any search branch that runs afterward.

### Q8 — Restore IP Addresses (LC 93): given a digit string, return all ways to insert dots to form a valid IP address.
**Testing:** recognizing backtracking with a fixed structural constraint (exactly 4 segments) layered on top of a per-segment validity check.
**Answer:** Recurse choosing a length-1-to-3 substring for the next segment; prune immediately if the segment has a leading zero (unless it's exactly "0"), exceeds 255, or if fewer/more than 4 segments could possibly still be formed from the remaining digits given their count.
**Follow-up trap:** *"How do you prune based on remaining digit count, not just per-segment validity?"* — before recursing, check whether the remaining digits could possibly still be split into the remaining required segments (each segment being 1-3 digits), and abandon the branch immediately if not — this is pruning based on a *global* feasibility check, not just the current segment's own validity.

### Q9 — Would you implement a real production scheduling/allocation system using hand-rolled backtracking like the templates above?
**Testing:** production judgment about when this pattern is the wrong scale of tool.
**Answer:** Only for small, bespoke constraint problems; for anything resembling real scheduling, resource allocation, or general constraint satisfaction at scale, reach for a dedicated CP/SAT solver (OR-Tools CP-SAT, Z3, MiniZinc) that implements far more sophisticated pruning (constraint propagation, conflict-driven learning) than a hand-rolled recursive backtracking loop would realistically achieve.
**Follow-up trap:** *"What do you lose by using a general solver instead of hand-rolled backtracking?"* — some control over problem-specific pruning heuristics and potentially more overhead for genuinely tiny problem instances, but you gain vastly better worst-case performance on real-sized instances, plus a well-tested, general-purpose engine instead of custom recursive code that needs to be debugged and maintained.

### Q10 — Letter Combinations of a Phone Number (LC 17): given digits 2-9, return all letter combinations the number could represent (like old T9 texting).
**Testing:** a simpler backtracking case with no real pruning needed, to test if candidates over-engineer or correctly recognize when pruning isn't the bottleneck.
**Answer:** For each digit, loop over its mapped letters, choose one, recurse to the next digit, unchoose. There's no invalid-state pruning here since every combination is valid by construction (every letter/digit pairing is always acceptable) — the complexity is simply the product of each digit's letter-count, with no savings available from early termination.
**Follow-up trap:** *"So is backtracking even the 'right' tool here, or overkill?"* — it's the natural and correct tool since you're still enumerating a combinatorial space with the choose/explore/unchoose shape; the honest point is that not every backtracking problem has a pruning opportunity, and recognizing that this one doesn't (rather than searching for a nonexistent optimization) is itself the correct read.

### Q11 — Combinations (LC 77): return all combinations of k numbers chosen from 1 to n.
**Testing:** pruning based on remaining-count feasibility, a distinct pruning idea from constraint-violation pruning.
**Answer:** Recurse with a start index like Subsets, but prune whenever the remaining numbers available (`n - start + 1`) are fewer than the remaining slots needed to reach size k — abandon that branch immediately rather than exploring it to find it comes up short.
**Follow-up trap:** *"How much does this specific prune actually save versus not having it?"* — it avoids exploring branches that are mathematically guaranteed to fail before reaching the base case, which matters increasingly as `k` approaches `n` or as `n` grows large relative to `k`; without it, the algorithm is still correct but explores dead-end paths it could have skipped for free with a single arithmetic check.

### Q12 — Partition to K Equal Sum Subsets (LC 698): can an array be partitioned into k subsets of equal sum?
**Testing:** combining backtracking with a stronger pruning strategy than the naive per-element choice.
**Answer:** Compute the target per-subset sum (`total/k`, fail fast if not divisible); backtrack by trying to fill one subset at a time up to the target, then moving to the next subset, rather than assigning each element to one of k buckets independently — bucket-by-bucket search prunes far more aggressively since a subset is abandoned the moment its running sum would exceed the target.
**Follow-up trap:** *"Why is bucket-by-bucket search meaningfully better than trying every element-to-bucket assignment?"* — element-to-bucket assignment explores `k^n` raw possibilities before any pruning; filling one bucket to its target sum before starting the next collapses huge swaths of equivalent orderings (which elements go into "bucket 1" versus "bucket 2" often doesn't matter until you fix the actual sums), giving a dramatically smaller effective search space in practice even though both are technically backtracking.

---

## Red flags that fail you

- Forgetting to unchoose after a recursive call, letting state leak across sibling branches.
- Appending a reference to the mutable path/board into the result instead of a copy, corrupting recorded answers later.
- Validating a fully-built candidate instead of pruning mid-construction, losing the entire efficiency point of the pattern.
- Getting the reuse-index wrong in Combination Sum variants (confusing `i` vs `i+1`).
- Not knowing how to deduplicate combinations/subsets/permutations when the input has duplicate values.
- Claiming backtracking with pruning changes the worst-case asymptotic complexity, rather than describing it as reducing the practically explored fraction of an inherently exponential space.

---

## Cheat card

```
SKELETON       if complete: record; for choice in candidates: if invalid: skip (PRUNE)
               choose (mutate) -> explore (recurse) -> unchoose (undo mutation)
UNCHOOSE       #1 most common bug if forgotten — state leaks across sibling branches
RECORD COPY    append path[:] / new ArrayList<>(path), never the live mutable reference
PRUNE EARLY    check constraint BEFORE recursing, not after building a full candidate
SUBSETS        LC78: start-index loop, O(n*2^n) total (2^n subsets, O(n) copy each)
PERMUTATIONS   LC46: used[] tracker instead of start-index, O(n*n!) total
N-QUEENS       LC51: track cols/diag1(row-col)/diag2(row+col) sets, prune BEFORE placing
               ~2057 states explored for 8-Queens vs billions unpruned
COMBO SUM      LC39: reuse -> recurse with SAME index i; sorted + break when candidate>remaining
COMBO SUM II   LC40: no reuse -> recurse i+1; skip duplicate VALUE at SAME depth to dedupe output
PALINDROME PART LC131: prune substring only if already palindrome; precompute isPalin[i][j] O(n^2)
SUDOKU         LC37: prune via row/col/box check before placing digit; MRV heuristic speeds it up
WORD SEARCH    LC79: mark cell visited before recursing into neighbors, restore after, always
AT SCALE       real constraint/scheduling problems -> OR-Tools CP-SAT / Z3, not hand-rolled backtrack
```

## Sources

- [Subsets — LeetCode](https://leetcode.com/problems/subsets/) — accessed 2026-07-26
- [Permutations — LeetCode](https://leetcode.com/problems/permutations/) — accessed 2026-07-26
- [N-Queens — LeetCode](https://leetcode.com/problems/n-queens/) — accessed 2026-07-26
- [Combination Sum — LeetCode](https://leetcode.com/problems/combination-sum/) — accessed 2026-07-26
- [Combination Sum II — LeetCode](https://leetcode.com/problems/combination-sum-ii/) — accessed 2026-07-26
- [Palindrome Partitioning — LeetCode](https://leetcode.com/problems/palindrome-partitioning/) — accessed 2026-07-26
- [Sudoku Solver — LeetCode](https://leetcode.com/problems/sudoku-solver/) — accessed 2026-07-26
- [Word Search — LeetCode](https://leetcode.com/problems/word-search/) — accessed 2026-07-26
- [Restore IP Addresses — LeetCode](https://leetcode.com/problems/restore-ip-addresses/) — accessed 2026-07-26
- [Partition to K Equal Sum Subsets — LeetCode](https://leetcode.com/problems/partition-to-k-equal-sum-subsets/) — accessed 2026-07-26
- [Backtracking — Wikipedia](https://en.wikipedia.org/wiki/Backtracking) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
