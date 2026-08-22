# Sliding Window

> **Track:** T02 DSA: 21 Patterns · **Time:** 2h · **Prereqs:** T02-p01-two-pointers · **Updated:** 2026-07-26
> **Module id:** `T02-p02-sliding-window` · **Tags:** pattern, arrays, strings

## The 30-second version

Sliding Window turns "find the best contiguous subarray/substring satisfying a condition" from an O(n^2) or O(n^3) brute force into O(n) by maintaining a window `[left, right]` that only ever expands or contracts, never resets to scratch. The right pointer always advances to grow the window and admit a new element into your running state (a sum, a character-frequency map, a distinct-count); the left pointer advances only to shrink the window back into validity once it's been violated. The reason this is O(n) and not O(n^2) is that `left` and `right` each traverse the array at most once, total, across the entire run — the window never re-scans work it already did. Recognize it from: "contiguous subarray/substring," plus a size constraint (fixed k) or a validity constraint (sum, distinct count, character frequency) to optimize.

## Why this gets asked

The interviewer is checking whether you can identify when recomputation is wasted work. The brute-force instinct for "longest substring with property X" is to check every substring, or to recompute the property from scratch for every window position — both are wasteful because 99% of a window's state carries over when you slide it by one. This is precisely the failure mode they've lived through in production: a service recomputing an aggregate over a rolling time window from scratch on every event instead of incrementally updating counts as events enter and expire (rate limiters, moving averages, streaming percentiles all have this exact shape). At senior level, the follow-up is whether you can tell the difference between a *fixed-size* window (trivial: pop when the window exceeds size k) and a *variable-size* window (harder: the shrink condition is itself a function of what's currently in the window), and whether your shrink loop is a `while`, not an `if` — a single `if` fails the moment more than one shrink is needed to restore validity.

---

## Lineage: past → present → future

**What came before.** The naive approach to "best contiguous subarray of length k" or "longest valid substring" is to enumerate all `O(n)` or `O(n^2)` starting points and, for each, scan forward to evaluate the window from scratch — O(n^2) at best, O(n^3) if the per-window evaluation itself isn't O(1). This mirrors the general history of "incremental computation replacing recomputation" that shows up across computing: the same idea underlies streaming aggregates, rolling hashes (Rabin-Karp, 1987, which is itself a fixed-size sliding window over a rolling hash), and TCP's sliding window protocol for flow control (RFC 793, 1981) — a genuinely older and unrelated-but-same-named idea from networking that interview prep material sometimes conflates with the array/string pattern. The interview-pattern framing was popularized the same way two pointers was: Design Gurus' *Grokking the Coding Interview* names it as pattern #1, and it appears throughout NeetCode's problem taxonomy as one of the highest-frequency array/string categories.

**Where it stands now.** Universally expected; the open question at interview time is never "should I use sliding window" (that's usually obvious from the prompt) but "is my shrink condition and shrink loop correct," because that's where nearly all sliding-window bugs live. There is a real, live distinction in practice between window problems solvable with a simple counter (max sum of size-k subarray) and ones that need a full frequency map with a "how many distinct/violating characters right now" auxiliary counter (minimum window substring, longest substring with at most k distinct characters) — candidates who've only practiced the simple kind consistently fail the harder kind by trying to recompute validity from the map on every step instead of maintaining a running violation counter.

**Where it's heading.** As with other classic patterns, expect debugging-style prompts to grow: "here is a sliding window solution to minimum window substring with the shrink condition inverted, find the bug" is cheap to write and precisely targets understanding versus memorization. It also transfers directly to a skill increasingly relevant on the job: LLM context-window and token-budget management is, mechanically, a sliding-window problem (what stays in the window, what gets evicted, in what order) — interviewers with agentic-systems backgrounds have started drawing this parallel explicitly in interviews as of 2025-2026, treating classic sliding window fluency as a proxy for "can reason about context compaction." Treat that connection as an emerging framing, not yet a standardized interview ask.

---

## Mental model

Variable-size window, growing and shrinking based on a validity condition:

```
s = "e c e b a"
     0 1 2 3 4

right=0: window="e"          valid (no repeat)      best=1
right=1: window="ec"         valid                  best=2
right=2: window="ece"        INVALID (repeat 'e')   shrink:
           left=0 -> drop 'e', window="ce"           still has 'e' at idx2? check last_seen
           left=1 -> window="ce" now valid           best stays 2
right=3: window="ceb"        valid                   best=3
right=4: window="ceba"       valid                   best=4  <- answer

     L---------R              window always contiguous, L only moves forward, never resets
     ^ never revisits ground already covered -> total pointer movement is O(n), not O(n^2)
```

Fixed-size window (fold in new element, drop the one falling off the back):

```
nums = [2, 1, 5, 1, 3, 2],  k = 3
window sum, sliding right by one each step, dropping nums[right-k] as nums[right] enters:

[2,1,5] sum=8   best=8
   [1,5,1] sum=8-2+1=7
      [5,1,3] sum=7-1+3=9   best=9
         [1,3,2] sum=9-5+2=6
```

---

## Recognition heuristics

- **"Contiguous subarray/substring"** is the load-bearing phrase. If the problem allows non-contiguous selection, this is not sliding window — it's usually DP or subsets/backtracking.
- **A fixed window size k is given** ("subarray of size k", "every window of k elements") — the simple fixed-window variant: one running aggregate, pop the element leaving the back as you add the one entering the front.
- **A validity constraint on window contents** ("no more than k distinct characters," "sum at least/at most X," "contains all characters of T," "no repeating characters") — variable-size window: grow with `right`, shrink with a `while` loop whenever the constraint is violated.
- **"Longest / shortest / smallest / maximum / minimum" + contiguous** — sliding window is almost always faster than the DP or brute-force alternative when the objective is monotonic in window size (adding elements can only help or only hurt the constraint, not both unpredictably).
- **Anagram / permutation checks between a pattern and a text** — fixed-size window equal to the pattern's length, comparing frequency maps incrementally rather than recomputing per position.
- **You're about to write nested loops where the inner loop restarts from the outer loop's position** — that's the brute-force tell; ask whether the inner loop's work from the previous outer iteration can be reused instead of redone.

**Anti-signal:** if elements can be picked non-contiguously, or the "window" needs to jump non-locally (not just shrink from the left / grow from the right), sliding window doesn't apply — look at hashing/prefix sums or DP instead.

---

## Template code (Python, Java, Go)

Variable-size window — longest substring without repeating characters, the canonical shrink-on-violation skeleton:

**Python**
```python
def length_of_longest_substring(s: str) -> int:
    last_seen: dict[str, int] = {}
    left = 0
    best = 0
    for right, ch in enumerate(s):
        if ch in last_seen and last_seen[ch] >= left:
            left = last_seen[ch] + 1     # jump left past the earlier occurrence
        last_seen[ch] = right
        best = max(best, right - left + 1)
    return best
```

**Java**
```java
public int lengthOfLongestSubstring(String s) {
    Map<Character, Integer> lastSeen = new HashMap<>();
    int left = 0, best = 0;
    for (int right = 0; right < s.length(); right++) {
        char c = s.charAt(right);
        if (lastSeen.containsKey(c) && lastSeen.get(c) >= left) {
            left = lastSeen.get(c) + 1;
        }
        lastSeen.put(c, right);
        best = Math.max(best, right - left + 1);
    }
    return best;
}
```

**Go**
```go
func lengthOfLongestSubstring(s string) int {
	lastSeen := make(map[byte]int)
	left, best := 0, 0
	for right := 0; right < len(s); right++ {
		c := s[right]
		if idx, ok := lastSeen[c]; ok && idx >= left {
			left = idx + 1
		}
		lastSeen[c] = right
		if right-left+1 > best {
			best = right - left + 1
		}
	}
	return best
}
```

---

## Complexity, derived

`right` advances exactly once per iteration of the for-loop: `n` total advances. `left` only ever moves forward (never resets backward), and its total movement across the entire run is bounded by `n` as well, since it can't exceed `right`. So total pointer work across the whole run is `O(n) + O(n)` = **O(n) time**, not the naive `O(n^2)` of re-scanning from every start index. Space is **O(min(n, alphabet size))** for the frequency/last-seen map — O(1) if the alphabet is fixed (e.g., 26 lowercase letters, so a fixed-size array replaces the hash map and drops the constant factor).

---

## The 5 variants interviewers actually ask

1. **Fixed-size window — max sum subarray of size k.** Modification: no shrink condition at all; maintain a running sum, subtract `nums[right - k]` and add `nums[right]` each step once the window first reaches size k.
2. **Minimum Window Substring.** Modification: grow until the window contains all required characters (tracked via a "how many required chars are currently satisfied" counter, not a full remap check), then shrink greedily while it's still valid, recording the shortest valid window at each shrink step — the shrink is the part that produces the answer, not the growth.
3. **Longest Substring with At Most K Distinct Characters.** Modification: shrink (in a `while`, not `if`) whenever `len(frequency_map) > k`, decrementing counts and removing zero-count entries from the map.
4. **Longest Repeating Character Replacement.** Modification: track the count of the *most frequent* character currently in the window; the window is valid if `window_size - max_freq <= k` (at most k characters need replacing); shrink by one when invalid — note the window never needs to shrink below its historical max, so `best` can be tracked as `window_size` at the end without ever decreasing it, a subtle but load-bearing optimization.
5. **Permutation in String / Find All Anagrams.** Modification: fixed-size window equal to `len(pattern)`; maintain a frequency map diff or a "matches" counter that increments/decrements as characters enter and leave, so validity is checked in O(1) per step rather than comparing full frequency maps.

---

## Common bugs

- **Using `if` instead of `while` to shrink the window.** A single `if` only removes one offending element; if adding the new right-most element created two or more violations at once (e.g., a duplicate that also pushes distinct-count over the limit), one `if` leaves the window still invalid. Always shrink in a `while` loop that re-checks the condition.
- **Recomputing window validity from scratch on every step** (e.g., rebuilding and comparing full frequency maps) instead of maintaining a running counter that's updated incrementally as elements enter/exit — this silently degrades an O(n) solution to O(n * alphabet size) or worse, which can still pass small test cases and fail on real input sizes.
- **Off-by-one on the window length formula.** The correct window length for indices `[left, right]` inclusive is `right - left + 1`; forgetting the `+1` undercounts every window by one.
- **Updating `best` before shrinking a still-invalid window**, recording a window length that doesn't actually satisfy the constraint.
- **Forgetting to remove a key from the frequency map once its count hits zero**, which corrupts a later "number of distinct keys" check (`len(freq_map)`) even though the count is zero, because the key is still present.
- **In minimum-window-substring style problems, shrinking too eagerly or too late** — the correct order is: grow until valid, then shrink *while still valid*, recording the best at each successful shrink, then stop shrinking exactly at the point it becomes invalid again.

---

## Interview questions

### Q1 — Longest Substring Without Repeating Characters (LC3)
**Testing:** the base variable-size window shrink pattern.
**Answer:** Track `last_seen` index per character; when the incoming character was last seen at or after `left`, jump `left` to `last_seen[ch] + 1`. O(n) time, O(min(n, alphabet)) space.
**Follow-up trap:** *"Why jump left directly instead of incrementing it one at a time in a while loop?"* — both are O(n) amortized, but the direct jump is O(1) per character instead of a potentially longer while loop; interviewers accept either, but you should be able to explain that the while-loop version is still correct and why (it just does more, harmless, work).

### Q2 — Minimum Window Substring (LC76)
**Testing:** whether you can combine grow-until-valid with shrink-while-valid, and use a running "satisfied count" instead of comparing maps.
**Answer:** Maintain required-character counts and a `formed` counter incremented when a character's count in the window first meets its requirement; grow `right` until `formed == len(required distinct chars)`, then shrink `left` while still valid, updating the best window each time before it breaks validity.
**Follow-up trap:** *"What if the target string T has duplicate characters?"* — your required-count map must count occurrences per character (not just presence), and `formed` must only increment when the window's count for that character reaches its *required* count, not merely becomes nonzero; getting this wrong is the most common failure on this problem.

### Q3 — Longest Substring with At Most K Distinct Characters (LC340)
**Testing:** the `while`-shrink-on-map-size pattern.
**Answer:** Frequency map; shrink `while len(freq) > k`, decrementing and deleting zero-count entries; track `best = max(best, right - left + 1)` after every successful placement.
**Follow-up trap:** *"K = 0, what should happen?"* — the window can never be valid with any character in it, so the answer is 0; candidates whose shrink loop assumes `k >= 1` implicitly can infinite-loop or return a wrong nonzero value here.

### Q4 — Longest Repeating Character Replacement (LC424)
**Testing:** whether you can maintain an auxiliary "running max frequency in window" rather than recomputing it, and understand why the window doesn't need to shrink below its best-known size.
**Answer:** Track `max_freq` of any single character in the current window (it's fine if this value goes slightly stale since it only ever needs to be a valid lower bound, not exact); window is valid if `(right - left + 1) - max_freq <= k`; otherwise shrink by exactly one from the left.
**Follow-up trap:** *"Why is it safe to never let `max_freq` decrease, even after shrinking?"* — because the answer can only grow by finding a window at least as large as the best seen so far combined with a higher `max_freq`; an underestimate of `max_freq` after a shrink only makes the algorithm stricter (shrink again if needed next step), never lets it overcount. It's a genuine but bounded approximation, not a bug.

### Q5 — Permutation in String (LC567)
**Testing:** fixed-size window with O(1) validity check via a match counter instead of full array comparison.
**Answer:** Fixed window of size `len(s1)`; maintain frequency diffs between window and pattern with a `matches` counter tracking how many of the 26 letters currently have equal counts; slide one character at a time, updating counts and `matches` incrementally.
**Follow-up trap:** *"Isn't comparing two 26-length arrays each step still O(1)?"* — technically yes since 26 is constant, but the intended answer demonstrates the *general* technique (incremental match counting) that scales to non-fixed alphabets, which is what the interviewer is actually testing.

### Q6 — Find All Anagrams in a String (LC438)
**Testing:** the same fixed-window technique as Q5, but requiring you to collect all valid start indices, not just a boolean.
**Answer:** Identical sliding mechanism to Permutation in String; append `left` to the result list every time the window matches, then continue sliding rather than stopping at the first match.
**Follow-up trap:** *"What if `s1` is longer than `s2`?"* — return an empty result immediately; failing to guard this causes an out-of-bounds or infinite loop in languages without automatic bounds checking.

### Q7 — Max Consecutive Ones III (LC1004)
**Testing:** recognizing "flip at most k zeros" as a validity-constrained variable window, not a DP problem.
**Answer:** Track `zero_count` in the window; shrink while `zero_count > k`, decrementing it when a zero leaves the window; `best` is the max window size seen.
**Follow-up trap:** *"Do you ever need to explicitly reset zero_count to zero and restart the window?"* — no; because the window never shrinks below its best-known valid size (same reasoning as LC424), a monotonic single pass suffices, and resetting would be O(n^2) wasted work.

### Q8 — Fruit Into Baskets (LC904)
**Testing:** whether you can translate an oddly-worded problem ("two baskets, one fruit type each") into "at most 2 distinct values in the window" — a rephrasing test as much as an algorithm test.
**Answer:** Exactly the "at most K distinct" template with K=2; frequency map, shrink `while len(freq) > 2`.
**Follow-up trap:** *"Generalize to K basket types."* — the same template with `K` as a parameter; if a candidate's Fruit Into Baskets solution hardcoded logic for exactly two distinct values (e.g., two named variables instead of a map), they cannot generalize without a rewrite, which is the point of the follow-up.

### Q9 — Sliding Window Maximum (LC239)
**Testing:** whether you know when sliding window needs a monotonic deque instead of a simple running aggregate, because max/min isn't incrementally updatable by simple add/remove.
**Answer:** Maintain a deque of indices with strictly decreasing values; pop from the back while the new element is greater-or-equal (they can never be the answer while the new element is in the window); pop from the front when the front index falls outside the window; the front of the deque is always the current window's max.
**Follow-up trap:** *"Why can't you just track a running max the way you tracked a running sum?"* — a running sum updates in O(1) on removal (subtract the leaving value), but max does not: if the max leaves the window you'd need to rescan to find the new max, which reintroduces O(n) per step. The monotonic deque avoids this by discarding values from the back that can never become the max while a larger, newer value is still in the window.

### Q10 — Subarrays with K Different Integers (LC992)
**Testing:** the "exactly K" decomposition trick — a genuine staff-level twist on the at-most-K template.
**Answer:** `exactly(K) = atMost(K) - atMost(K - 1)`, where `atMost` is the standard "at most K distinct" sliding window counting the number of valid subarrays ending at each `right` (which is `right - left + 1` once the window is valid) rather than just the longest one.
**Follow-up trap:** *"Why can't you write `exactly(K)` directly with one sliding window?"* — "exactly K" is not monotonic in window size the way "at most K" is (growing a window can move you from exactly-K to more-than-K, but shrinking doesn't cleanly restore "exactly"), so there's no single valid/invalid boundary to slide against; decomposing into two monotonic "at most" problems restores that property.

### Q11 — Minimum Size Subarray Sum (LC209)
**Testing:** the "shortest valid window" variant, which shrinks even more eagerly than "longest."
**Answer:** Grow `right` accumulating sum; once `sum >= target`, shrink `left` in a `while` loop recording the minimum window length at every successful shrink, stopping the instant `sum < target` again.
**Follow-up trap:** *"All inputs are positive here — what breaks if negative numbers are allowed?"* — sliding window requires that growing the window monotonically helps and shrinking monotonically hurts (or vice versa) with respect to the sum constraint; negative numbers break that monotonicity (a bigger window doesn't guarantee a bigger sum), so the correct tool becomes prefix sums with binary search or another technique entirely, not sliding window.

---

## Red flags that fail you

- Shrinking the window with `if` where multiple violations can occur — must be `while`.
- Recomputing the entire frequency map or scanning the whole window to check validity at every step, instead of maintaining an incremental counter.
- Forgetting the `+1` in `right - left + 1` for window length.
- Applying sliding window to a problem that allows non-contiguous selection.
- Claiming Sliding Window Maximum can use a running max variable, with no deque or equivalent.
- Trying to solve "exactly K distinct" with one direct window instead of the at-most(K) - at-most(K-1) decomposition, and getting stuck justifying why it doesn't converge.

---

## Cheat card

```
PRECONDITION   contiguous subarray/substring + (fixed size k) or (validity constraint)
GROW           right always advances, folding new element into running state (sum/freq/count)
SHRINK         left advances in a WHILE loop (not if) until validity is restored
WINDOW LENGTH  right - left + 1  (never forget the +1)
FIXED WINDOW   no shrink logic; once size==k, subtract element leaving, add element entering
AT-MOST-K      shrink while len(freq_map) > K; delete zero-count keys from map
MIN WINDOW     grow until valid, THEN shrink while still valid, record best during shrink
MAX/MIN VALUE  running sum/count updates O(1); running MAX/MIN needs a monotonic deque
EXACTLY K      exactly(K) = atMost(K) - atMost(K-1)   <- decomposition, not a direct window
COMPLEXITY     O(n) total: left and right each traverse the array at most once, combined
WRONG TOOL     non-contiguous selection allowed, or non-monotonic constraint (e.g. negatives
               in a sum-threshold problem) -> prefix sums / DP / binary search instead
```

## Sources
- [NeetCode 150 — Coding Interview Questions](https://neetcode.io/practice/practice/neetcode150) — accessed 2026-07-26
- [Ultimate Coding Patterns Cheat Sheet for Tech Interviews — DesignGurus](https://www.designgurus.io/blog/coding-patterns-for-tech-interviews) — accessed 2026-07-26
- [Minimum Window Substring — LeetCode](https://leetcode.com/problems/minimum-window-substring/) — accessed 2026-07-26
- [Sliding Window Maximum — LeetCode](https://leetcode.com/problems/sliding-window-maximum/) — accessed 2026-07-26
- [Subarrays with K Different Integers — LeetCode](https://leetcode.com/problems/subarrays-with-k-different-integers/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
