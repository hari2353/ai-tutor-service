# Interval & String DP + Grid Simulation: Burst Balloons, Matrix Chain, Decode Ways, Spiral — the Google Most-Asked Long Tail

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.5h · **Prereqs:** T02-p15-knapsack-01, T02-p04-merge-intervals
> **Module id:** `T02-adv-dp-matrix` · **Tags:** advanced, blind75, google

## The 30-second version

The 21-pattern track teaches families; a working interview sheet (e.g. the widely-shared 200+ Google SDE list) puts *named* problems inside those families, and three sub-families keep slipping through a patterns-only study: **interval DP** (`dp[i][j]` over ranges where you enumerate the last thing decided inside the range — LC 312 Burst Balloons, Matrix Chain Multiplication, Count Palindromic Substrings), the **two-string DP table** (LCS / Edit Distance — `dp[i][j]` over prefixes of both strings, match takes the diagonal, everything else pays; both the 50-patterns handbook and the Google SDE sheet name it, and diff/git/eval tooling is built on it), the **string-count DP** family (`dp[i]` counts walks through the string one or two characters deep, with zero/lead constraints — Decode Ways, Distinct Subsequences, Word Break), and the **in-place grid simulation** family (Spiral Matrix, Rotate Image, Set Matrix Zeroes, Game of Life — where the whole question is the O(1)-space trick, not the traversal). What interviewers grade is that you can *state the state* — "what does `dp[i][j]` mean, and which `k` am I enumerating" — before touching code, because all these families are unlearnable from pattern names alone: the transition formula is the answer.

## Why this gets asked

These are the most-asked per-category questions on Google-style sheets precisely because they are cheap to adapt (change a constraint, ask for count-vs-list, ask for space-optimization) and each one separates memorization from state-defining skill. LC 312 Burst Balloons is the canonical example of an answer that cannot be brute-forced into understanding: the naive "min/max over first burst" framing is wrong because left and right *neighbors change* after a burst — "last balloon to burst" reframing fixes the dependency — and that reframe is exactly the skill an interviewer can watch happen or not happen. Same for the string family: Decode Ways dies on `"0"`-handling, Word Break II dies without memo, Game of Life dies without the in-place bit trick. Small, adaptable, diagnostic — the whole interview cocktail.

---

## Lineage: past → present → future

**What came before.** Interval DP descends from dynamic programming's 1950s formalization (Bellman) and the classic matrix-chain parenthesization problem in CLRS — before LeetCode existed, this was THE interval DP exercise in every algorithms course. Conway's Game of Life predates all of them (1970, cellular automata). LeetCode's era flattened both into named interview problems with blind-75-canonical status; the "count ways to decode" formulation is the same paths-through-a-lattice counting as climbing stairs with an alphabet twist.

**Where it stands now.** The state definitions have not changed in a decade; what moves is the follow-up pressure: O(n²)/O(n³) time is assumed, and the scored conversation is space (1D rolling for the string family, O(1) bit-packing for Game of Life, boundary-in-place for spiral), then enumerating-all-answers variants (Word Break II), then "adapt it to X" mutations (balloons with rewards dependent on neighbors, chain multiplication with GPU-aware costs).

**Where it's heading.** Low-risk prediction: the string DP family absorbs "how would this change for streaming" style follow-ups more often as LLM-era interviewers like tokenization-adjacent framing (Decode Ways literally *is* a tokenizer with an ambiguous vocabulary — a nice interview line to make explicitly). Interval DP stays interval DP: it is the problem shape where an interviewer can watch you pick a two-dimensional state, and no pattern-list study substitutes for having derived it once.

---

## Mental model

Three states to keep distinct.

```
INTERVAL DP        dp[i][j] = best over range [i..j]
                   enumerate k: the LAST (or first) thing resolved inside
                   transition: dp[i][j] = max/opt over k of dp[i][k] + cost(k) + dp[k+1][j]
                   order: by range LENGTH (small → large)

STRING COUNT DP    dp[i] = number of ways (or min/max cost) for prefix s[:i]
                   transition: dp[i] = f(dp[i-1], dp[i-2], ... constraint)
                   order: single left-to-right pass

GRID SIMULATION    traversal / in-place trick chosen by contract:
                   spiral = boundary contraction; rotate = transpose+reverse;
                   set-zeroes = first row/col as flag storage; life = bit-packing
```

Interval DP is the one people under-train, because it looks like nothing else in the pattern list: the `k` inside the range represents "the last decision," which is *backwards* from how you'd naturally think (first decision).

---

## Recognition heuristics

- **"minimize cost to multiply / burst / merge / cut sticks, score depends on neighbors"** → interval DP. The tell is *neighbor-dependent payoff* — the classic reason first-decision framing fails.
- **"number of ways to decode / partition / build strings from vocabulary"** → 1D count DP with 2-step memory; handle `0` as an *unsettable* digit, never as a standalone code.
- **"how many subsequences of S equal T"** → distinct-subsequences shape: `dp[i][j]` over both strings, take-or-skip the source character.
- **"min edits to turn S into T / longest shared subsequence"** → the LCS/Edit-Distance two-string table: `dp[i][j] = dp[i-1][j-1]` on match, else `1 + min(insert, delete, replace)`; reconstruct with traceback — which is exactly how `git diff` renders both files.
- **"in-place, O(1) extra space, transform the grid"** → simulation trick, not an algorithm: boundary contraction (spiral), transpose+reverse (rotate), flag-reuse (set zeroes), neighbor-count bit-packing (life).
- **"output where out[i] = product of all except nums[i], division forbidden"** → prefix/suffix product decomposition (Google-deck warmup): two running passes, O(n) time, O(1) extra beyond the output — the running-accumulator family the sliding-window module trusts, extended to products; the no-division constraint is the whole interview.
- **"search a sorted grid / rotated matrix"** → binary search variants from `T02-p11`, just carried into 2D indexing — check the matrix first, then reuse.

---

## How it actually works — the two states worth writing once

**LC 312 Burst Balloons.** Balloons `1..n`, bursting balloon `i` yields `nums[left] * nums[i] * nums[right]` where neighbors are the *current* survivors. The dependency trap: after any burst, left/right neighbors change, so "decide the next burst" can't be memoized. The fix is deciding the *last* burst in a (padded) range, which fences off the interior transitions:

```python
def max_coins(nums):
    a = [1] + nums + [1]                       # pad: boundaries never burst
    n = len(a)
    dp = [[0] * n for _ in range(n)]           # dp[i][j]: best in (i, j) exclusive
    for length in range(2, n):                 # length-2 open range (i, j), j = i + length
        for i in range(n - length):
            j = i + length
            for k in range(i + 1, j):          # k = LAST balloon popped in this range
                dp[i][j] = max(dp[i][j], dp[i][k] + a[i]*a[k]*a[j] + dp[k][j])
    return dp[0][n - 1]
```

**Game of Life, O(1) space.** Each cell is an int with spare bits: encode next state in bit 1, current in bit 0; two passes (count neighbors from current bits, then shift), and "infinite board" follow-ups get the honest answer — for an unbounded grid you must spill to a sparse live-set (`set` of live coords), not a matrix.

**String family, one template with three skins.** `dp[0] = 1; dp[i] = Σ dp[j] if s[j..i] satisfies the constraint` — Decode Ways (`j = i-1`, single char ≠ '0'; plus `j = i-2` if two-digit in 10..26), Word Break (`j` is any earlier prefix whose suffix is in the word set), Distinct Subsequences is the 2D cousin (`take` + `skip` additivity).

**Spiral Matrix** = four boundaries (`top, bottom, left, right`), walk each edge then contract the matching boundary; the bug class is elements between when top > bottom — handle single-row/single-column remainders *inside* the loop, not after.

## Complexity — derived, not asserted

| Problem | Time | Space | The bound comes from |
|---|---|---|---|
| Burst Balloons / Matrix Chain | O(n³) | O(n²) | length × i × k enumeration |
| Palindromic Substrings | O(n²) | O(1) | expand-around-center beats table version |
| Decode Ways / Word Break | O(n) | O(n) | single pass; rolling 2 vars possible |
| Spiral / Rotate / Set Zeroes / Life | O(m·n) | O(1) | every cell touched once, flags in-place |

The scored sentence: for interval DP, "O(n³) time for O(n²) states — the extra factor is the last-position enumeration." Saying it unprompted is most of the signal.

## The 5 variants interviewers actually ask

1. **Matrix Chain Multiplication 1:1 with Burst Balloons** — same `dp[i][j]` + last-split `k`; state it loudly, interviewers shouldn't be able to tell which variant you came from.
2. **Palindromic Substrings (count) vs Longest Palindromic Substring (span)** — expand-around-center does count in O(n²)/O(1); the table version silently costs O(n²) memory you didn't need.
3. **Word Break → Word Break II** — switch from count to enumerate-all-cuts; that's DP-guided backtracking (memo the failing prefixes).
4. **Rotate Image 90°** (transpose then reverse rows) at 45° and -90° variants, plus "do it for a non-square matrix" as the trap answer: you copy-row tricks break there.
5. **Game of Life board-to-board update with simultaneous rule evaluation** — the bit-pack trick, then the honest infinite-grid answer.

## Common bugs and how these get shipped wrong under pressure

- Interval DP enumerating `k` as the *first* decision ("dp[i][k] + dp[k+1][j]" without the range-exclusive padding) — produces a plausible-looking wrong answer with no test that catches it under time pressure.
- Decode Ways ignoring `"0"` adjacency entirely (`"06"` is 0 ways, not 1), and the `"10"`/`"20"` boundary in the two-digit range.
- Game of Life counting neighbors from the *updated* grid — the classic simultaneous-evolution violation; only playable if updates were encoded in bits, not overwritten.
- Spiral skipping the final single column when dimensions are odd — test `[[1,2,3],[4,5,6]]` specifically before claiming done.
- Word Break attempting greedy longest-prefix first — fails on `"applepenapple"`-style overlaps; DP over all `j` is the point.

## Interview questions

1. **Burst Balloons with rewards, LC 312.** Derive the last-burst reframe out loud; then face the follow-up *"why does first-burst memoization fail?"* — neighbors mutate.
2. **Matrix Chain Multiplication, parenthesization.** Same state; walk one 4-matrix example by hand.
3. **Decode Ways with `"0"` cases.** Contract: `"0" → 0, "10" → 1, "101" → 1, "100" → 0` — get the corner cases right live.
4. **Distinct Subsequences ("rabbbit"/"rabbit").** Take/skip additivity; then the follow-up: reduce to O(min(m,n)) space, walking the larger string with a 1D rolling row.
5. **In-place grid transforms.** Spiral / rotate / set-zeroes / life, each with the O(1) trick; the interviewer probes which boundary your loop *actually* trusts.
6. **Word Break II with memoization.** Enumerate paths, prune with the count DP's reachability as a precheck.

## Red flags that fail you

- Writing interval DP without being able to say what `dp[i][j]` *means* after two prompts.
- Claiming Game of Life needs an O(m·n) copy without being shown why bits exist.
- Quietly making spiral/rotate in-place asserts false (mutating boundaries, 45° confusion).
- Solving Decode Ways greedily — there's no greedy here, and trying shows you haven't internalized counting DP.

## Cheat card

- Interval DP: pad the range, sort by length, enumerate the **last** element inside; O(n³)/O(n²).
- String count DP: `dp[i]` over prefix ends, 1- and 2-char lookbacks, `0` never decodes alone; O(n).
- String count DP: `dp[i]` over prefix ends, 1- and 2-char lookbacks, `0` never decodes alone; O(n).
- LCS / Edit Distance: two-string table, diagonal on match; O(m·n)/O(m·n) table — 1D rolling row is the standard space follow-up.
- Distinct Subsequences = 2D take/skip; rolling row for space.
- Grid sims: spiral = 4 boundaries contracted; rotate = transpose + reverse; set-zeroes = flag the first row/col; life = neighbor bits then shift.
- State the state. Then code. Given a sheet like "200+ Google SDE Qs", this module is everything the 21-pattern list under-covers.

## Sources

- [codebuilderhq — 200+ Google SDE Interview Questions (slide OCR, DM-gated PDF)](https://www.instagram.com/p/DQZHx3zkWOH/) — categories: Array/String, Matrix/Grid, Tree/BST, Linked List, Recursion, Stack/Queue/Heap, Graph, DP, CS Fundamentals + Behavioral (accessed 2026-10-31)
- [codedsoul_05 — 50 Coding Patterns handwritten handbook (slide OCR)](https://www.instagram.com/p/DbnephXDbZb/) — pages 1-18 map 1:1 onto the T02 pattern modules; naming aligned (accessed 2026-10-31)
- [datasciencebrain — Top 55 Python Questions With Solutions (slide OCR)](https://www.instagram.com/p/DQLWlT_Eyu7/) — Python answer shapes for the same T02 families (accessed 2026-10-31)
- [LeetCode 312 — Burst Balloons](https://leetcode.com/problems/burst-balloons/) and [LeetCode 494/115 — Target Sum / Distinct Subsequences](https://leetcode.com/problems/distinct-subsequences/) — problem definitions (accessed 2026-10-31)
- [CLRS — Matrix-Chain Multiplication, Ch. 14 (canonical interval DP)](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/) (accessed 2026-10-31)

## Changelog

- 2026-10-31: Created — OCR of the Google SDE / 50-pattern / 55-Python deck material confirmed these named families absent while every true pattern already had a module.
