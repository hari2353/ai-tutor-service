# Pattern: Monotonic Stack

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** arrays, stacks
> **Module id:** `T02-p20-monotonic-stack` · **Tags:** pattern, stack

## The 30-second version

A monotonic stack keeps its elements in strictly increasing or strictly decreasing order at all times by popping anything that would violate that order before pushing the new element — and the elements it pops *are themselves the answer* for "next greater/smaller element" style problems, not a side effect to discard. The invariant is: maintain a decreasing stack to find each element's **next greater element** (pop everything smaller than the current value; whatever gets popped just found its next-greater, which is the current value), and maintain an increasing stack to find each element's **next smaller element**, symmetrically. Every element is pushed once and popped at most once across the whole array, so despite the nested-looking "while stack and condition: pop" loop, total work is **O(n)**, not O(n²) — that amortized argument is the thing candidates who've only memorized the template usually can't explain. Recognize it whenever a problem asks about the next/previous greater or smaller element, spans until a value changes, or a bar/building's visible width or trapped area — anything reducible to "for each element, how far can I see in one direction before something taller/shorter blocks me."

## Why this gets asked

It tests whether you can derive the O(n) amortized argument for what looks like a nested loop, and whether you recognize the same four-line skeleton underneath surface-different problems (next greater element, daily temperatures, histogram area, trapping rain water) instead of treating each as a new algorithm. Interviewers who've built log-analysis systems (span-based alerting: "how long has this metric stayed below threshold"), stock/price-analysis tooling (span/streak calculations), or layout engines (visible-width/skyline calculations) have hit the real version of this: a naive O(n²) nested-loop scan for "next value that breaks this streak" that's fine on small test data and falls over on real time-series volumes, where the monotonic-stack O(n) rewrite is the actual production fix.

---

## Lineage: past → present → future

**What came before.** The obvious brute-force answer to "find the next greater element for every position" is a nested loop — for each index, scan forward until you find something bigger, O(n²) worst case (a strictly decreasing array forces every element to scan to the end). The monotonic stack technique is a direct descendant of the same **amortized analysis** ideas that came out of data-structure work in the 1970s-80s (the same era and style of reasoning as union-find's amortized bounds, `T02-p19-union-find`) — the insight that a sequence of push/pop operations can be bounded in *total* even though individual operations look expensive, because each element only ever gets pushed once and popped once across the whole run. The specific "next greater element" framing and its histogram/rain-water applications became interview staples once they were catalogued as a distinct pattern (well documented on LeetCode's discussion boards and interview-prep material from the mid-2010s onward), but the underlying amortized-stack idea itself is older, straight out of classical algorithms analysis.

**Where it stands now.** Fully settled and small: know the invariant (increasing vs decreasing stack, and which one answers which question), know that indices (not just values) are usually what you push so you can compute distances/spans afterward, and know the amortized O(n) argument cold. There's no live methodological disagreement — the only real interview-relevant nuance is that "next greater" and "previous greater" are mirror-image traversals (left-to-right vs right-to-left, or equivalently, forward with a stack of unresolved indices vs a single backward pass), and mixing them up under pressure is the most common live mistake.

**Where it's heading.** Nothing new for interviews — closed, small toolkit. Where it generalizes in practice: streaming/windowed variants (sliding window maximum, LC 239, uses a monotonic **deque**, not a plain stack, since elements must expire from *both* ends — the invariant is the same "maintain monotonic order by popping violators" idea, but the container needs two-ended eviction for the window's aging-out elements as well). Recognizing that the monotonic-deque sliding-window-maximum pattern is the same core idea with an extra eviction rule, not a separate technique, is a good signal of actually understanding the invariant rather than pattern-matching on "stack" as a keyword.

---

## Mental model

Walk left to right maintaining a stack that's always strictly decreasing (bottom to top). The moment the current value is bigger than the stack's top, that top element has just found its answer — pop it, record the current value as its "next greater," and keep comparing against the new top.

```
array:        [2, 1, 2, 4, 3]
building a DECREASING stack (store indices), looking for NEXT GREATER element

i=0 (val=2): stack empty -> push 0.                     stack(vals): [2]
i=1 (val=1): 1 < top(2), no violation -> push 1.         stack(vals): [2,1]
i=2 (val=2): 2 > top(1) -> pop 1, ans[1]=2 (next greater of 1 is 2)
             2 == top(2)? not strictly greater by this array's values... 2 not > 2 -> push 2
                                                          stack(vals): [2,2]
i=3 (val=4): 4 > top(2) -> pop, ans[2]=4
             4 > top(2) -> pop, ans[0]=4
             stack empty -> push 3.                      stack(vals): [4]
i=4 (val=3): 3 < top(4), no violation -> push 4.         stack(vals): [4,3]

end of array: anything still on the stack has no next greater -> ans = -1 for those (indices 3,4)

final ans (next greater element per position): [4, 2, 4, -1, -1]
```

Every element is pushed exactly once; it's popped at most once, whenever something bigger finally shows up. That's the whole amortized argument in one picture: total pushes = n, total pops ≤ n, so total work across the entire pass is O(n) even though any single step's `while` loop could in principle pop many elements at once.

---

## Recognition heuristics

- **"Next greater element"** / **"next smaller element"** / **"previous greater/smaller"** stated directly — the canonical framing (LC 496, 503, 739).
- **"How many days until the temperature rises"** / **"how long until the price drops"** — span-until-change problems, structurally identical to next-greater-element with the answer expressed as a distance rather than a value (Daily Temperatures).
- **Largest rectangle in a histogram / maximal rectangle in a binary matrix** — for each bar, you need the nearest shorter bar on both the left and right to know how far it can extend; that's simultaneously a "previous smaller" and "next smaller" query per position.
- **Trapping rain water** — the water trapped at each position depends on the tallest wall to its left and right; while this has an O(1)-space two-pointer solution, the monotonic-stack formulation (processing "layer by layer" using bars popped off a decreasing stack) is the variant that generalizes to less regular shapes.
- **"Remove k digits / remove duplicate letters to make the smallest possible result while keeping some constraint"** — greedy removal decisions where a monotonic stack decides, character by character, whether the previous choice should be popped in favor of the current one.
- **"Stock span"** — for each day, how many consecutive prior days had a price less than or equal to today's — an online (streaming) variant of next-smaller/previous-greater bookkeeping using a stack that persists across calls.

If the problem needs a *global* maximum/minimum over a fixed window rather than a per-element next/previous relationship, and the window slides, that's the monotonic-**deque** sliding-window-maximum variant (LC 239) — same invariant, different container because both ends need eviction.

---

## How it actually works — the invariant made explicit, and why it generalizes

**The invariant, precisely.** A monotonic stack processes elements left to right (or right to left) and maintains one property at all times: *before pushing a new element, pop everything on the stack that violates the desired order relative to the new element.* For "next greater element," the desired order is strictly decreasing bottom-to-top; anything smaller than or equal to the incoming value no longer belongs, because the incoming value is now a better (closer, and satisfying) "next greater" candidate for everything it just popped.

**Why what gets popped is the answer, not a discard.** At the moment index `j`'s value causes a pop of index `i` (where `i < j` and `stack` had `i` on top), it's guaranteed that every index between `i` and `j` was already popped by something *smaller* than `arr[j]` or doesn't exist — meaning `arr[j]` is the *first* element to the right of `i` that's greater than `arr[i]`. That's exactly the definition of "next greater element." The stack's job is to hold, at every moment, exactly the indices whose next-greater-element hasn't been found yet, in an order that guarantees whichever one is on top will be resolved first.

**Generalizing the direction.** Four combinations exist, and all four reuse the identical pop-loop skeleton with only the comparison flipped and/or the traversal direction reversed:
- Decreasing stack, left-to-right → next greater element.
- Increasing stack, left-to-right → next smaller element.
- Decreasing stack, right-to-left → previous greater element.
- Increasing stack, right-to-left → previous smaller element.

Histogram/rain-water problems typically need **two** of these simultaneously (e.g., previous smaller AND next smaller, to know how far a bar extends both directions), which is why those problems feel harder — they're not a new technique, they're two applications of the same invariant combined.

**The amortized O(n) argument, precisely.** Every index is pushed onto the stack exactly once (when its own iteration is reached) and popped at most once (whenever a qualifying element to its right/left is found) across the *entire* run of the algorithm. Even though a single iteration's `while` loop can pop many elements at once (in the worst case, one iteration pops everything currently on the stack), the *total* number of pop operations summed across all iterations cannot exceed the total number of pushes, which is `n`. So total work is `O(n) pushes + O(n) pops = O(n)`, not O(n²), despite the loop nested visually inside another loop.

---

## Template code (Python, Java, Go)

```python
# Python — Next Greater Element (LC 496/503 style), decreasing stack of indices
def next_greater_elements(nums: list[int]) -> list[int]:
    n = len(nums)
    ans = [-1] * n
    stack: list[int] = []          # holds INDICES, decreasing by value
    for i in range(n):
        while stack and nums[stack[-1]] < nums[i]:
            j = stack.pop()
            ans[j] = nums[i]
        stack.append(i)
    return ans

# Daily Temperatures (LC 739) — span until a warmer day, decreasing stack
def daily_temperatures(temps: list[int]) -> list[int]:
    n = len(temps)
    ans = [0] * n
    stack: list[int] = []
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            j = stack.pop()
            ans[j] = i - j          # distance, not value, is the answer here
        stack.append(i)
    return ans

# Largest Rectangle in Histogram (LC 84) — increasing stack, one pass
def largest_rectangle_area(heights: list[int]) -> int:
    stack: list[int] = []            # indices, increasing by height
    max_area = 0
    for i, h in enumerate(heights + [0]):   # sentinel 0 flushes the stack at the end
        while stack and heights[stack[-1]] > h:
            height = heights[stack.pop()]
            width = i if not stack else i - stack[-1] - 1
            max_area = max(max_area, height * width)
        stack.append(i)
    return max_area

# Trapping Rain Water (LC 42) — monotonic-stack formulation, layer by layer
def trap(heights: list[int]) -> int:
    stack: list[int] = []            # indices, decreasing by height
    water = 0
    for i, h in enumerate(heights):
        while stack and heights[stack[-1]] < h:
            top = stack.pop()
            if not stack:
                break
            left = stack[-1]
            width = i - left - 1
            bounded_height = min(heights[left], h) - heights[top]
            water += width * bounded_height
        stack.append(i)
    return water
```

```java
// Java — Next Greater Element
public int[] nextGreaterElements(int[] nums) {
    int n = nums.length;
    int[] ans = new int[n];
    Arrays.fill(ans, -1);
    Deque<Integer> stack = new ArrayDeque<>();   // indices, decreasing by value
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && nums[stack.peek()] < nums[i]) {
            ans[stack.pop()] = nums[i];
        }
        stack.push(i);
    }
    return ans;
}

// Daily Temperatures (LC 739)
public int[] dailyTemperatures(int[] temps) {
    int n = temps.length;
    int[] ans = new int[n];
    Deque<Integer> stack = new ArrayDeque<>();
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && temps[stack.peek()] < temps[i]) {
            int j = stack.pop();
            ans[j] = i - j;
        }
        stack.push(i);
    }
    return ans;
}

// Largest Rectangle in Histogram (LC 84)
public int largestRectangleArea(int[] heights) {
    Deque<Integer> stack = new ArrayDeque<>();
    int maxArea = 0;
    int n = heights.length;
    for (int i = 0; i <= n; i++) {
        int h = (i == n) ? 0 : heights[i];
        while (!stack.isEmpty() && heights[stack.peek()] > h) {
            int height = heights[stack.pop()];
            int width = stack.isEmpty() ? i : i - stack.peek() - 1;
            maxArea = Math.max(maxArea, height * width);
        }
        stack.push(i);
    }
    return maxArea;
}
```

```go
// Go — Next Greater Element
func nextGreaterElements(nums []int) []int {
    n := len(nums)
    ans := make([]int, n)
    for i := range ans {
        ans[i] = -1
    }
    stack := []int{} // indices, decreasing by value
    for i := 0; i < n; i++ {
        for len(stack) > 0 && nums[stack[len(stack)-1]] < nums[i] {
            j := stack[len(stack)-1]
            stack = stack[:len(stack)-1]
            ans[j] = nums[i]
        }
        stack = append(stack, i)
    }
    return ans
}

// Daily Temperatures (LC 739)
func dailyTemperatures(temps []int) []int {
    n := len(temps)
    ans := make([]int, n)
    stack := []int{}
    for i := 0; i < n; i++ {
        for len(stack) > 0 && temps[stack[len(stack)-1]] < temps[i] {
            j := stack[len(stack)-1]
            stack = stack[:len(stack)-1]
            ans[j] = i - j
        }
        stack = append(stack, i)
    }
    return ans
}

// Largest Rectangle in Histogram (LC 84)
func largestRectangleArea(heights []int) int {
    stack := []int{}
    maxArea := 0
    n := len(heights)
    for i := 0; i <= n; i++ {
        h := 0
        if i < n {
            h = heights[i]
        }
        for len(stack) > 0 && heights[stack[len(stack)-1]] > h {
            height := heights[stack[len(stack)-1]]
            stack = stack[:len(stack)-1]
            width := i
            if len(stack) > 0 {
                width = i - stack[len(stack)-1] - 1
            }
            if height*width > maxArea {
                maxArea = height * width
            }
        }
        stack = append(stack, i)
    }
    return maxArea
}
```

## Complexity, derived

Every element is pushed onto the stack exactly once (its own iteration) and popped at most once (whenever a qualifying element resolves it), across the *entire* traversal — so total pushes are `n` and total pops are at most `n`, giving **O(n) total time** for the whole array despite the visually nested `while` loop inside the `for` loop. **Space is O(n)** worst case for the stack itself (a strictly monotonic input array, e.g. already sorted the "wrong" way for the query, never triggers a pop until the very end, leaving all `n` indices on the stack simultaneously). This directly beats the brute-force nested-loop alternative, which is O(n²) worst case (a strictly decreasing array for next-greater-element forces every single element to scan all the way to the array's end without ever finding a match).

---

## The 5 variants interviewers actually ask

1. **Next Greater Element I & II (LC 496, 503) — including the circular-array variant.** Direct template application; the circular version (LC 503) handles wraparound by conceptually iterating the array twice (`i % n`) without actually doubling the array in memory, while the stack logic is unchanged.
2. **Daily Temperatures (LC 739) — return distances, not values.** Identical decreasing-stack template, but the payload written into the answer array is the index gap `i - j`, not `nums[i]` itself — a small but real detail that trips people who copy the next-greater-element template verbatim.
3. **Largest Rectangle in Histogram (LC 84) / Maximal Rectangle (LC 85) — combine previous-smaller and next-smaller in one pass using an increasing stack and a trailing sentinel.** LC 85 layers this per-row on a binary matrix, treating each row as a histogram built from consecutive 1s stacked vertically from prior rows.
4. **Trapping Rain Water (LC 42) — monotonic-stack "layer by layer" formulation versus the O(1)-space two-pointer alternative.** The stack formulation processes water level by level as bars get popped, and generalizes more naturally to variants like 2D trapping rain water, where the simple two-pointer trick no longer applies.
5. **Remove Duplicate Letters (LC 316) / Remove K Digits (LC 402) — greedy stack-based construction of the smallest valid result under a keep/remove constraint.** Not next-greater-element in disguise, but the same invariant-maintenance skeleton: pop the previous choice off the stack if the current character is smaller and the popped one can still be used again later (or, for Remove K Digits, if removals remain).

---

## Common bugs

- **Pushing values instead of indices.** Once you need distances (Daily Temperatures) or widths (Largest Rectangle), you need the index, not just the value, to compute a gap; pushing raw values forces an awkward second lookup or breaks the solution outright.
- **Getting the comparison direction backward.** Using `<=` where `<` was needed (or vice versa) changes whether equal elements count as "greater/smaller," which silently changes the answer for arrays with duplicate values — always re-derive from the problem's exact wording ("strictly greater" vs "greater or equal") rather than defaulting to a memorized comparator.
- **Forgetting the sentinel in histogram-style problems.** Largest Rectangle in Histogram needs a trailing `0` (or equivalent) appended so the final pass flushes every remaining bar off the stack; without it, bars still on the stack at the end of the real array never get their width computed.
- **Confusing "next" and "previous" traversal direction.** Next-greater needs a left-to-right pass; previous-greater needs right-to-left (or an equivalent single-pass trick); mixing these up under pressure produces an answer that looks plausible but is systematically off by direction.
- **Assuming O(n) without being able to justify it.** Treating the nested `while` loop as automatically suspicious of being O(n²) and not being able to produce the "each element pushed once, popped once" argument on request — this is the single most common thing interviewers probe for explicitly.
- **Reaching for a monotonic stack when a monotonic deque was actually needed.** Sliding-window-maximum-style problems need eviction from *both* ends (elements aging out of the window, not just being dominated by a bigger element); a plain stack can't evict from the bottom, so this needs `collections.deque` (Python) / `ArrayDeque` (Java) used as a double-ended structure, not a single-ended stack.

---

## Interview questions

### Q1 — Next Greater Element (LC 496): for each element, find the first element to its right that's strictly greater, or -1 if none exists.
**Testing:** the base invariant and direction.
**Answer:** Maintain a decreasing stack of indices while scanning left to right; whenever the current value exceeds the stack's top, pop it and record the current value as its next-greater element.
**Follow-up trap:** *"Why is this O(n) despite the while loop inside the for loop?"* — each index is pushed once and popped at most once across the entire run; total pushes and pops are both bounded by n, so total work is O(n), not O(n²).

### Q2 — Daily Temperatures (LC 739): for each day, how many days until a warmer temperature?
**Testing:** whether the template can be adapted to return a distance instead of a value.
**Answer:** Same decreasing-stack template as next-greater-element, but store `i - j` (the index gap) into the answer array instead of the popped element's replacement value.
**Follow-up trap:** *"What if no warmer day ever comes for some index?"* — leave the default (typically 0, per the problem's convention) since those indices are simply never popped and remain on the stack until the array ends.

### Q3 — Next Greater Element II (LC 503): same as Q1, but the array is circular.
**Testing:** adapting the pattern to wraparound without changing its core mechanics.
**Answer:** Iterate `2n` steps using `i % n` to simulate wraparound, without physically duplicating the array; push/pop logic is otherwise identical, only ever recording an answer during the "real" first pass indices, since the second lap exists purely to let elements find a wraparound next-greater.
**Follow-up trap:** *"Does this change the complexity?"* — no, it's still O(n); iterating `2n` times instead of `n` is still a constant factor, not a different asymptotic class.

### Q4 — Largest Rectangle in Histogram (LC 84): find the largest rectangular area in a histogram of bar heights.
**Testing:** combining "previous smaller" and "next smaller" in a single increasing-stack pass.
**Answer:** Maintain an increasing stack of indices; when the current bar is shorter than the stack's top, pop it — the popped bar's height times the width between its new stack-top neighbor and the current index (exclusive) is a candidate area. Append a sentinel `0` at the end to flush remaining bars.
**Follow-up trap:** *"Why does popping give you both left and right boundaries at once?"* — when a bar is popped, the new stack top is the nearest bar to its left that's still shorter (bounding it on the left), and the current index is the nearest bar to its right that's shorter (bounding it on the right) — both boundaries fall out of the single invariant-maintaining pop, no separate left/right passes needed.

### Q5 — Trapping Rain Water (LC 42): compute total water trapped between bars given their heights.
**Testing:** knowing multiple valid approaches and their tradeoffs, not just one memorized solution.
**Answer:** The monotonic-stack formulation processes water "layer by layer": maintain a decreasing stack, and when a taller bar arrives, compute the water trapped above the just-popped bar using the new stack top (left wall) and the current bar (right wall) as bounds. An O(1)-space two-pointer alternative also exists and is often simpler for the 1D case.
**Follow-up trap:** *"Given the two-pointer solution is simpler and O(1) space, why would you ever use the stack version?"* — the stack formulation generalizes more naturally to less regular variants (e.g., water trapped in more complex 2D terrain, or when you need per-layer/per-step bookkeeping, not just a final total), where the two-pointer trick's invariant doesn't cleanly extend.

### Q6 — Remove K Digits (LC 402): remove exactly k digits from a number string to make the smallest possible resulting number.
**Testing:** recognizing a greedy-construction problem as a monotonic-stack application, not next-greater-element.
**Answer:** Maintain an increasing stack of digits; for each new digit, pop the stack while the top digit is larger than the current one and removals remain (`k > 0`), then push the current digit. After processing, remove any remaining excess from the end if `k` removals haven't been exhausted, then strip leading zeros.
**Follow-up trap:** *"Why does popping a larger digit in favor of a smaller one always help, even though you're 'giving up' a removal?"* — a smaller digit in a more significant position always produces a smaller overall number than keeping a larger digit there, regardless of what follows, so greedily preferring the smaller digit whenever a removal is still available is provably optimal (an exchange argument).

### Q7 — Sliding Window Maximum (LC 239): find the maximum in every window of size k as it slides across an array.
**Testing:** recognizing when the pattern needs a deque instead of a stack.
**Answer:** Maintain a decreasing monotonic **deque** of indices; before adding a new index, pop smaller elements off the back (same invariant as a monotonic stack); additionally, pop the front if it's fallen outside the current window's left boundary. The front of the deque is always the current window's maximum.
**Follow-up trap:** *"Why can't a plain stack handle this?"* — a stack only supports removing from one end; here, elements must also be evicted from the *front* once they age out of the window, which requires a double-ended structure (deque), not a single-ended stack.

### Q8 — Sum of Subarray Minimums (LC 907): sum the minimum of every contiguous subarray.
**Testing:** using "previous smaller" and "next smaller" together to count contribution rather than enumerate subarrays.
**Answer:** For each element, find the distance to the previous strictly-smaller element (or start) and the next strictly-smaller-or-equal element (or end); that element is the minimum for exactly `(left distance) * (right distance)` subarrays, so its contribution to the total sum is `value * left * right`. Sum contributions across all elements using one or two monotonic-stack passes.
**Follow-up trap:** *"Why must exactly one side use a strict inequality and the other non-strict (or some equivalent tie-breaking rule)?"* — without a consistent tie-breaking rule, subarrays with duplicate minimum values get double-counted (counted as the "minimum" by more than one equal element simultaneously); using strict on one side and non-strict on the other assigns each duplicate value's subarrays to exactly one canonical index.

### Q9 — Online Stock Span (LC 901): for each day's price (given one at a time, streaming), return the number of consecutive prior days with price ≤ today's.
**Testing:** applying the pattern in a streaming/online context, where the stack persists across calls rather than being built in one batch pass.
**Answer:** Maintain a stack of (price, span) pairs across calls; on each new price, pop and accumulate spans of all prior entries with price ≤ today's, then push (today's price, accumulated span + 1). Each call is amortized O(1) since the total pushes/pops across all calls combined is still bounded by the number of calls.
**Follow-up trap:** *"Is each individual call O(1), or only amortized O(1) over the whole sequence?"* — only amortized; a single call can pop many elements at once (worst case O(n) for that one call if the stock has been monotonically decreasing), but the total work across the entire sequence of calls is still O(n) by the same push-once-pop-once argument.

### Q10 — Maximal Rectangle (LC 85): find the largest rectangle of 1s in a binary matrix.
**Testing:** composing the histogram technique across multiple rows.
**Answer:** For each row, build a "histogram" where each column's height is the count of consecutive 1s ending at that row (0 if the current cell is 0, else previous height + 1); run Largest Rectangle in Histogram on that derived histogram for every row, tracking the maximum across all rows.
**Follow-up trap:** *"What's the overall complexity?"* — O(rows · cols), since building each row's histogram is O(cols) and running the histogram algorithm on it is also O(cols), for a total of O(rows · cols) across all rows — not O(rows · cols²) or worse, because each per-row histogram pass is itself linear, not quadratic.

### Q11 — Remove Duplicate Letters (LC 316): given a string, remove duplicate letters so each letter appears exactly once, keeping the result the smallest possible in lexicographic order while preserving relative order constraints.
**Testing:** the most constraint-heavy greedy-stack variant, combining multiple bookkeeping structures.
**Answer:** Maintain an increasing stack of characters plus a count of remaining occurrences of each character and a seen-set for what's currently on the stack; for each character, if it's already on the stack skip it, otherwise pop the stack while the top is larger than the current character AND the top character still has occurrences remaining later in the string, then push the current character.
**Follow-up trap:** *"Why is the 'still has occurrences remaining later' check necessary, unlike Remove K Digits?"* — unlike Remove K Digits (which just needs any k digits removed), this problem requires every distinct letter to appear exactly once in the final result, so you can only pop a letter off the stack if you're guaranteed a later chance to place it back in; without that check you could permanently lose a letter that had no more occurrences left.

---

## Red flags that fail you

- Not being able to explain why the nested-looking loop is O(n), not O(n²), on request.
- Pushing values instead of indices when the problem needs distances or widths.
- Mixing up next-greater and previous-greater direction, or increasing vs decreasing stack, under pressure.
- Forgetting the sentinel flush in histogram-style problems, leaving remaining stack entries unresolved.
- Reaching for a plain stack on a sliding-window-maximum-style problem that actually needs a deque for both-ends eviction.
- Treating trapping rain water and largest rectangle in histogram as unrelated problems instead of recognizing the shared previous/next-smaller machinery.

---

## Cheat card

```
INVARIANT      pop anything that violates monotonic order BEFORE pushing; popped elements = the answer
DECREASING     stack decreasing bottom->top  =>  answers NEXT GREATER element (pop when cur > top)
INCREASING     stack increasing bottom->top  =>  answers NEXT SMALLER element (pop when cur < top)
DIRECTION      left->right = "next X";  right->left (or reversed logic) = "previous X"
PUSH WHAT      indices, not values — needed for distances/widths (Daily Temps, Histogram)
AMORTIZED      each index pushed once, popped at most once, total across whole array => O(n), not O(n^2)
NEXT GREATER   LC 496 / 503 (circular: iterate 2n via i%n, no array duplication)
DAILY TEMPS    LC 739: same as next-greater, store i-j (distance) not value
HISTOGRAM      LC 84: increasing stack + trailing 0 sentinel; pop gives BOTH left+right bounds at once
MAX RECTANGLE  LC 85: per-row derived histogram (consecutive 1s), run LC84 per row -> O(rows*cols)
RAIN WATER     LC 42: decreasing stack, layer-by-layer; O(1)-space two-pointer alt exists for 1D case
REMOVE K DIGIT LC 402: increasing stack, pop larger digit while removals remain -> greedy smallest result
SLIDING MAX    LC 239: needs a DEQUE not a stack (evict from front on window expiry too)
STOCK SPAN     LC 901: online/streaming variant; stack persists across calls, amortized O(1)/call
```

## Sources

- [Next Greater Element I — LeetCode](https://leetcode.com/problems/next-greater-element-i/) — accessed 2026-07-26
- [Next Greater Element II — LeetCode](https://leetcode.com/problems/next-greater-element-ii/) — accessed 2026-07-26
- [Daily Temperatures — LeetCode](https://leetcode.com/problems/daily-temperatures/) — accessed 2026-07-26
- [Largest Rectangle in Histogram — LeetCode](https://leetcode.com/problems/largest-rectangle-in-histogram/) — accessed 2026-07-26
- [Maximal Rectangle — LeetCode](https://leetcode.com/problems/maximal-rectangle/) — accessed 2026-07-26
- [Trapping Rain Water — LeetCode](https://leetcode.com/problems/trapping-rain-water/) — accessed 2026-07-26
- [Sliding Window Maximum — LeetCode](https://leetcode.com/problems/sliding-window-maximum/) — accessed 2026-07-26
- [Sum of Subarray Minimums — LeetCode](https://leetcode.com/problems/sum-of-subarray-minimums/) — accessed 2026-07-26
- [Online Stock Span — LeetCode](https://leetcode.com/problems/online-stock-span/) — accessed 2026-07-26
- [Remove Duplicate Letters — LeetCode](https://leetcode.com/problems/remove-duplicate-letters/) — accessed 2026-07-26
- [Remove K Digits — LeetCode](https://leetcode.com/problems/remove-k-digits/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
