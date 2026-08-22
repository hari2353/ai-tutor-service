# Boss: Coding Round (45 min, 2 problems)

> **Track:** T15 Interview Simulator · **Time:** 1h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T15-round-coding` · **Tags:** boss

**Runs under `tutor-mock` as round type `coding`.**

## The round in 30 seconds

Two problems, 45 minutes, no IDE, no running the code. This screens for whether DSA pattern recognition survives under a clock and an audience, not whether the patterns were once memorized. A pass looks like: complexity stated before a line of code is written, a working solution to problem 1 inside 20 minutes with named test cases run by hand afterward, and problem 2 at least structurally correct with the right pattern named even if the last edge case is unresolved. A fail looks like silent typing, a complexity guess that is wrong and undefended, or a candidate who cannot recover when the traced-through example breaks with 8 minutes left. At principal bar, the interviewer is also watching whether the candidate pushes back on an underspecified prompt instead of solving the wrong problem quickly.

## Format

- **Total: 45 minutes, 2 problems.** Budget roughly 20 min / 20 min with a 5-minute buffer, not 22.5/22.5 — problem 1 should be the one that closes early and buys time for problem 2.
- **No IDE.** Shared doc, whiteboard-equivalent, or plain text editor with no autocomplete, no run button, no linter. Syntax slips are not penalized; logic slips are.
- **Minute-by-minute shape per problem:**
  - 0:00–2:00 — restate the problem back, ask 1-2 clarifying questions (input size, duplicates allowed, sorted or not, mutate in place or not).
  - 2:00–4:00 — state the target complexity out loud before writing anything ("this should be O(n log k) with a heap of size k").
  - 4:00–14:00 — write the solution, narrating decisions, not narrating syntax.
  - 14:00–17:00 — trace through 2-3 named test cases by hand: the happy path, an empty/single-element edge case, and one adversarial case (all duplicates, already sorted, negative numbers — whichever the pattern is sensitive to).
  - 17:00–20:00 — state final complexity, and take the follow-up trap.
- **What the interviewer does:** asks the question, answers clarifying questions honestly, lets silence sit while the candidate thinks, interrupts scope creep, pushes on complexity claims ("why is that O(n) and not O(n log n)?"), and drops a follow-up trap after a working solution.
- **What the interviewer does not do:** hint at the pattern, correct a wrong complexity claim unprompted, confirm correctness before the candidate has traced a test case, or let a candidate run code to check it.
- **Think-aloud is not optional.** Two minutes of silent typing followed by "okay I think that works" is scored as a communication failure even if the code is correct — the interviewer cannot follow reasoning that was never externalized, and in a real design or debugging session that silence is unrecoverable.

## What is actually being tested

Not whether the candidate has seen this exact problem. The signals, in order of what actually moves the score:

1. **Pattern recognition speed.** How many seconds from hearing the prompt to naming the right pattern (two pointers vs. sliding window vs. binary search on the answer). A principal-level candidate names it in under 30 seconds for anything in the T02 catalogue; a senior candidate gets there by working an example.
2. **Complexity-first discipline.** Stating Big-O before writing code, and defending it precisely — "O(n) because each element is pushed and popped from the deque at most once" beats "O(n) because it feels linear."
3. **Recovery under failure.** What happens when the traced test case breaks. This is the single highest-signal moment in the round and it is manufactured deliberately — see Time-management failures below.
4. **Test-case selection.** Whether the candidate names adversarial cases unprompted (empty input, single element, all-same-value, already-sorted, integer overflow boundary) instead of only the happy path.
5. **Whether the candidate pushes back on an underspecified prompt.** "Can the array be empty? Are there duplicates? Should I optimize for time or space if I can't have both?" — asking this before coding is a seniority signal; discovering it while coding is a foot-gun.

## Question bank

Organized warmup → mid → staff/principal. Each entry: the question as asked, what a strong answer contains, what a weak answer looks like, the follow-up trap.

### Warmup

**Q1 — Longest Substring Without Repeating Characters.** ("Given a string, find the length of the longest substring with no repeated characters.")
- **Strong:** Sliding window with a hash map of last-seen index, O(n) single pass, window left pointer jumps directly to `last_seen[char] + 1` instead of incrementing one step at a time.
- **Weak:** Nested loop generating all substrings (O(n³) or O(n²)), or a sliding window that shrinks one character at a time instead of jumping — technically correct but wrong complexity, and the candidate doesn't notice.
- **Follow-up trap:** *"Now do it for at most k distinct characters instead of zero repeats."* Tests whether the candidate understands the window-shrink condition is a parameter, not a fixed rule, versus having memorized one specific window template.

**Q2 — Container With Most Water.** (Two Pointers.)
- **Strong:** Two pointers from both ends, move the shorter wall inward, argues why moving the taller wall can never improve the answer (the area is bounded by the shorter side regardless of what the other side does).
- **Weak:** O(n²) brute force with no attempt at the two-pointer insight, or two pointers with the wrong movement rule (moves the taller wall) that happens to pass the traced example by luck.
- **Follow-up trap:** *"Prove that you never miss the optimal answer by discarding the shorter wall."* A candidate who cannot articulate the exchange argument got the pattern from memory, not from understanding.

**Q3 — Merge Intervals.**
- **Strong:** Sort by start time first (states why sorting is necessary — unsorted intervals cannot be merged in one pass), then single pass merging overlapping ranges, O(n log n) dominated by the sort.
- **Weak:** Attempts to merge without sorting, or sorts but forgets the merge condition should be `>=` not `>` when the interval boundaries touch (`[1,3]` and `[3,5]` merge into `[1,5]`).
- **Follow-up trap:** *"Now insert one new interval into an already-sorted, already-merged list."* Requires recognizing this is a variant, not a new problem — the merge condition is identical, only the input shape (already sorted) changes the complexity to O(n).

### Mid

**Q4 — Meeting Rooms II (minimum meeting rooms required).** (Two Heaps / sweep line.)
- **Strong:** Either a min-heap of end times (push each meeting's end time, pop when the current meeting's start >= heap top) or a sweep-line with separate sorted start/end arrays and two pointers. States why this is fundamentally a "max concurrent intervals" problem, not a merge problem.
- **Weak:** Treats it like Merge Intervals and tries to merge overlapping meetings, which answers a different question (does anything overlap) rather than the asked question (how many rooms, at peak).
- **Follow-up trap:** *"What if meetings can be canceled and rescheduled — do you recompute from scratch?"* Tests whether the candidate reaches for an incremental data structure (a running heap you insert/delete from) versus insisting on a full re-sort every time.

**Q5 — Course Schedule (can you finish all courses given prerequisites).** (Topological Sort.)
- **Strong:** Recognizes this is cycle detection in a directed graph, builds adjacency list + in-degree array, Kahn's BFS algorithm, course order is completable iff all nodes are dequeued. States complexity O(V+E).
- **Weak:** Tries DFS without the three-color (white/gray/black) cycle check and either misses cycles or false-positives on shared ancestors in a DAG.
- **Follow-up trap:** *"Now return one valid course order, not just yes/no."* Trivial extension for Kahn's (the dequeue order is the answer) but exposes candidates who only memorized the boolean-answer version.

**Q6 — Word Ladder (shortest transformation sequence).** (BFS.)
- **Strong:** BFS from the start word, generating neighbors by single-character substitution against a word set, tracks level for shortest path, states why BFS and not DFS (BFS gives shortest path in an unweighted graph, DFS does not).
- **Weak:** DFS with path-length tracking and a "keep the minimum," which technically can work but is asymptotically worse and the candidate can't explain why BFS is the right default for shortest-path-in-unweighted-graph.
- **Follow-up trap:** *"The word list has 100,000 words. How do you avoid generating and checking 26 × word-length candidates per word against a huge set?"* Wants a hash-set lookup (O(1) membership) instead of linear scan, and possibly bidirectional BFS from both start and end.

**Q7 — Number of Islands.** (DFS/BFS on a grid.)
- **Strong:** Flood-fill from each unvisited land cell, marks visited in place or with a visited set, counts flood-fill invocations. O(rows × cols).
- **Weak:** Off-by-one boundary checks that crash or silently skip cells, or recursion depth concerns unaddressed on a large grid (stack overflow risk — should mention iterative BFS/DFS with an explicit stack as the production-safe version).
- **Follow-up trap:** *"The grid is 10,000 × 10,000 and you're getting a stack overflow with recursive DFS. Fix it without changing the algorithm."* Tests whether the candidate can convert recursion to an explicit stack under pressure — a very common failure moment.

**Q8 — Top K Frequent Elements.** (Top-K / heap or bucket sort.)
- **Strong:** Either a min-heap of size k (O(n log k)) or bucket sort by frequency (O(n), since frequency is bounded by array length). States the tradeoff: heap is simpler and generalizes better (streaming), bucket sort is asymptotically better here because frequency has a bounded range.
- **Weak:** Sorts the entire frequency map by count (O(n log n)) and calls it optimal without noticing a bucket sort or heap gets a better bound.
- **Follow-up trap:** *"Now the data arrives as an infinite stream and you need the current top-k at any point in time."* Bucket sort no longer works cleanly (unbounded, not recomputable cheaply); wants a size-k min-heap maintained incrementally.

**Q9 — LRU Cache (design).** (Hash map + doubly linked list.)
- **Strong:** Hash map for O(1) key lookup plus a doubly linked list for O(1) move-to-front and eviction, explains why a singly linked list or an array-based approach fails to hit O(1) for both get and put.
- **Weak:** Uses an `OrderedDict`-equivalent without being able to explain what it does under the hood (this is a design question testing mechanism, not library knowledge), or a plain dict with a separate "recency" list re-sorted on every access (O(n) per op).
- **Follow-up trap:** *"Make it thread-safe for concurrent get/put from multiple threads without serializing every access behind one lock."* Wants a discussion of striped locks, read-write locks on the map with a separate lock for the linked-list pointer updates, or an LFU-style sharded cache — the interviewer is checking whether "just add a lock" is the whole answer or the candidate has more.

### Staff / Principal

**Q10 — Alien Dictionary (derive character ordering from a sorted word list).** (Topological Sort, harder graph construction.)
- **Strong:** Builds a directed graph by comparing adjacent words letter-by-letter until the first differing character (that pair defines an edge), correctly handles the invalid case where a shorter word appears after a longer word with the shorter as a prefix (e.g., `["abc", "ab"]` is invalid — no valid ordering), then topologically sorts.
- **Weak:** Misses the prefix-invalidity case entirely, or compares full words character-by-character instead of stopping at the first difference (which can introduce phantom edges).
- **Follow-up trap:** *"What if there are multiple valid orderings — how do you return a deterministic one, and how would you test that your function is correct without knowing the 'true' alphabet?"* Tests whether the candidate reasons about topological sort's inherent non-uniqueness and can design a test oracle (verify the returned order is consistent with every input word pair) rather than comparing against one hardcoded expected string.

**Q11 — Network Delay Time (time for a signal to reach all nodes).** (Dijkstra.)
- **Strong:** Dijkstra's algorithm with a min-heap, states why Dijkstra (non-negative weights) and not Bellman-Ford, answer is the max of the shortest-path distances to all nodes (or -1/unreachable if any node is unreached), O((V+E) log V).
- **Weak:** Runs BFS treating all edges as weight 1, ignoring the actual edge weights, or picks Bellman-Ford by default without justifying it (correct but O(VE), strictly worse here and the candidate should know why).
- **Follow-up trap:** *"Now some edge weights can be negative because of a signal-boosting relay. Does your algorithm still work?"* Correct answer: no, Dijkstra's greedy relaxation is invalid with negative weights, and you need Bellman-Ford (accept the worse complexity) or Johnson's algorithm if you need repeated all-pairs queries. A candidate who says "just use a bigger heap" fails this.

**Q12 — Redundant Connection (find the edge that creates a cycle in a tree + 1 extra edge).** (Union-Find.)
- **Strong:** Union-Find with path compression and union by rank/size, processes edges in order, the first edge whose two endpoints are already in the same component is the answer. States near-O(1) amortized (inverse Ackermann) per operation and why that beats a DFS-cycle-check-per-edge approach (O(n) per check, O(n²) total).
- **Weak:** Re-runs a full cycle detection (DFS/BFS) after adding each edge, which is correct but O(n²), and doesn't reach for Union-Find without prompting.
- **Follow-up trap:** *"What if the graph isn't guaranteed to be a tree plus one edge — there could be multiple redundant edges. Find all of them, or the minimum set to remove to make it a tree."* This is a materially harder graph problem (related to feedback edge set) and the honest strong answer is to name it as NP-hard in general for directed graphs, tractable for undirected via counting extra edges past a spanning tree.

**Q13 — Word Search II (find all dictionary words present in a letter grid).** (Trie + backtracking/DFS.)
- **Strong:** Builds a Trie from the dictionary first, then DFS from every grid cell following Trie edges, prunes branches where no Trie path continues, marks visited cells during the DFS and unmarks on backtrack, removes found words from the Trie to avoid duplicate reporting. States why Trie-guided search beats checking each dictionary word independently against the grid (O(words × grid) vs. one shared traversal).
- **Weak:** Runs a separate DFS per dictionary word against the whole grid — correct but the complexity blows up with a large dictionary, and the candidate doesn't reach for the shared-prefix insight (a Trie) without a nudge.
- **Follow-up trap:** *"The dictionary has 100,000 words and grids can be 500×500 — what's now the bottleneck, and how do you cut it?"* Wants trie-node pruning (stop recursing once no trie children match) and possibly removing found leaf words from the trie in place so the search space shrinks as words are found.

**Q14 — Minimum Window Substring.** (Sliding Window, hardest variant.)
- **Strong:** Two-pointer sliding window with a frequency-count map of the target characters and a "characters satisfied" counter, expand right until the window is valid, then contract left while it stays valid, tracking the minimum valid window seen. O(s + t).
- **Weak:** Regenerates the frequency check from scratch on every window move instead of maintaining a running "satisfied count," which degrades to O(s × t) and the candidate can't identify why it's slow when pushed.
- **Follow-up trap:** *"Now find the minimum window that contains all characters of t in order (not just as a multiset) — a subsequence match, not a permutation match."* This is a different, harder DP problem (closer to minimum window subsequence), and recognizing that the sliding-window trick no longer applies because order matters is the actual test.

## The "8 minutes left and it doesn't work" recovery

This is deliberately engineered into the round by the interviewer's silence, not announced in advance. When a traced test case breaks with roughly 8 minutes remaining:

1. **State the bug's symptom out loud before touching the code.** "The output is `[3,1]` but I expected `[1,3]` — that's an ordering issue, not a wrong-value issue, which tells me the comparator or the iteration direction is backwards." Diagnosing before editing is what separates a debugging narrative from panicked flailing.
2. **Do not restart from scratch.** Rewriting a mostly-correct solution with 8 minutes left is close to guaranteed to fail to finish. Isolate the smallest change that fixes the traced case.
3. **Say what you would verify next if you had more time**, even if you don't have time to do it. "I'd want to check the empty-input case and confirm the fix doesn't break it" is a real signal even unexecuted.
4. **If time runs out with a known, named bug remaining**, say so plainly: "I know the boundary condition on the last window is off by one, and I believe the fix is changing `<` to `<=` on line 12, but I haven't verified it." A candidate who names the bug and the fix without time to apply it scores meaningfully higher than one who goes silent or claims it's done when it isn't.
5. **Never claim correctness you haven't traced.** The single fastest way to a NO HIRE is asserting "this works" on a solution that was never run through the test cases named earlier.

## Rubric

| Dimension | 1-2 | 3 | 4-5 |
|---|---|---|---|
| Correctness / depth | Solution wrong on the happy path, or right pattern named but never implemented; complexity claim absent or false and undefended when challenged | Happy path correct, misses 1-2 named edge cases (empty input, duplicates) without prompting; complexity correct but justification is hand-wavy | Both problems correct including edge cases raised unprompted; states and defends exact complexity ("O(n) amortized because each pointer moves at most n times total") |
| Structure / method | Starts typing within 60 seconds of hearing the prompt, no clarifying questions asked, complexity stated only after finishing (or not at all) | Asks 1 clarifying question, states complexity before coding but doesn't revisit it after the solution changes shape | Restates the problem, asks 2+ clarifying questions that change the approach, states target complexity before writing code, re-confirms complexity after the final version |
| Communication | Long silent stretches (60+ seconds) with no narration; cannot explain a line of their own code when asked; talks about syntax instead of logic | Narrates most of the coding but reverts to silence during the hardest 5 minutes; explains logic when asked but not proactively | Continuous think-aloud through the hardest section; proactively narrates the "why" behind each design choice, not just the "what"; explains tradeoffs unprompted |
| Seniority signals | Never names a rejected alternative approach; treats the first idea as the only idea; visibly panics or goes quiet when the traced test case fails | Names one alternative approach when asked but not unprompted; recovers from a failing test case but only after an interviewer nudge | Names and rejects at least one alternative unprompted with a reason ("brute force is O(n²), rejecting because n can be 10⁵"); diagnoses a failing test case's symptom before touching code; asks about real-world constraints (input size, mutability) before assuming them |

## Score bands

20-point total across the four dimensions above.

- **17-20 — STRONG HIRE.** Both problems fully correct with edge cases handled unprompted, complexity stated and defended precisely, continuous narration, and at least one unprompted alternative-approach discussion. At a principal bar this is table stakes for the coding round to not be the reason for a NO HIRE elsewhere in the loop — this round rarely wins an offer by itself but it can lose one.
- **13-16 — HIRE.** Both problems correct, complexity right but justification thinner than STRONG HIRE, communication solid but not proactive, recovers from the manufactured failure with at most one nudge.
- **9-12 — LEAN HIRE.** One problem fully correct, the other structurally right (correct pattern, incomplete implementation) or correct with a complexity mistake caught only under challenge. Some unprompted narration, some silent stretches. At principal bar this is a genuine risk signal: senior-plus candidates are not expected to fumble two well-known patterns in 45 minutes, and the panel will ask whether this was nerves or a real gap.
- **5-8 — NO HIRE.** One problem correct, the other wrong or abandoned; complexity claims wrong and undefended; long silent stretches; no unprompted edge-case handling.
- **0-4 — STRONG NO HIRE.** Neither problem reaches a correct solution; candidate cannot state or defend a complexity claim at all; cannot explain their own code when asked; treats a failing test case as the interviewer's problem rather than a bug to diagnose.

## Red flags that end the round

- Claiming a solution is correct without tracing a single test case against it.
- A complexity claim that's wrong, and doubling down when challenged instead of re-deriving it.
- More than 90 seconds of pure silence with no narration during the core implementation.
- Asking the interviewer to just confirm whether the approach is right before writing any code — offloading the thinking rather than proposing an approach and defending it.
- Treating a follow-up trap as an attack rather than a real extension — visible defensiveness instead of engaging with the new constraint.
- Restarting a mostly-working solution from scratch with under 10 minutes left.

## Time-management failures

The specific ways candidates burn the clock in this round:

- **Over-clarifying problem 1.** Spending 8+ minutes on clarifying questions for a problem whose ambiguity doesn't actually change the approach — burns time that problem 2 needed.
- **Silent debugging spirals.** Getting a wrong answer on the first trace and going quiet for 3-4 minutes trying fixes without narrating hypotheses, instead of stating the symptom and reasoning aloud.
- **Premature optimization on problem 1.** Spending the first 10 minutes trying to find the asymptotically optimal solution to a warmup problem instead of getting a correct O(n log n) solution down first and optimizing only if time remains.
- **No time reserved for tracing.** Writing code until the buzzer with zero minutes left to run through named test cases — a solution that was never traced is not a verified solution, regardless of whether it happens to be correct.
- **Ignoring the halfway checkpoint.** If problem 1 isn't at least structurally complete by minute 22, the candidate needs to consciously decide to simplify or move on; candidates who don't self-checkpoint often lose problem 2 entirely.

## Cheat card

```
BEFORE CODING: restate problem, ask 2 clarifying Qs, state target Big-O out loud
NAME THE PATTERN in <30s: two ptr / sliding window / BFS-shortest-path / heap-top-k
                          / union-find-connectivity / trie-prefix / topo-sort-DAG
COMPLEXITY DISCIPLINE: justify with the mechanism ("each element pushed/popped once")
                        not with vibes ("feels linear")
TRACE 3 CASES AFTER CODING: happy path, empty/single element, adversarial (dupes/sorted)
BUG AT T-8min: state the SYMPTOM before touching code, isolate smallest fix,
               don't rewrite from scratch, name the bug even if you can't fix it in time
NEVER claim "this works" without having traced it
FOLLOW-UP TRAP = a new constraint, not a gotcha: re-derive, don't defend the old answer
UNPROMPTED SIGNALS: name a rejected alternative + why; ask about input size/mutability
BFS = shortest path unweighted. Dijkstra = shortest path non-negative weights.
Bellman-Ford = negative weights ok. Union-Find = connectivity/cycle in O(~1) amortized.
Silence >60s with no narration is scored as a communication failure, not neutral
```

## Sources

- [FAANG Coding Interview Questions & Preparation Guide 2026 — codinginterview.com](https://www.codinginterview.com/blog/faang-coding-interview-questions/) — accessed 2026-08-01
- [FAANG-Coding-Interview-Questions curated list — GitHub](https://github.com/ombharatiya/FAANG-Coding-Interview-Questions) — accessed 2026-08-01
- [LeetCode Interview Questions: Top Patterns by Company (2026) — InterviewPilot](https://interviewpilot.dev/blog/leetcode-interview-questions) — accessed 2026-08-01
- `curriculum/02-dsa-21-patterns/` — pattern catalogue this round draws problems from (internal source of mechanism-level answers).

## Changelog
- 2026-08-01 — created
