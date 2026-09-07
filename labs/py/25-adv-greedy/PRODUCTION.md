# Production notes — greedy algorithms & exchange arguments

## Where greedy actually runs in production

| System | The greedy | The exchange argument you'd cite |
|---|---|---|
| Calendars / room booking (Google Calendar, Workday) | Interval scheduling: sort meetings by finish, one room max count | Earliest-finishing pick frees the most timeline — one-for-one swap keeps feasibility and count |
| Job-shop / queue dispatch (Kubernetes scheduler default, YARN CapacityScheduler) | Shortest-Job-First / earliest-deadline-first | EDF: swap any inverted pair (later deadline run first) without increasing max lateness |
| Ad auctions & pacing (budget smoothing) | Highest-bid-first under budget | Matroid-ish structure (independent sets of allocations) — greedy-by-weight is provably optimal on matroids |
| Huffman coding — the greedy you ship daily | `zlib`, `gzip`, JPEG, MP3, Kafka's compression codecs | The two least-frequent symbols can always be siblings at the deepest level of some optimal tree |
| Bin packing / VM placement heuristics (first-fit-decreasing) | Cloud consolidators, shipping loaders | No optimality — a *bounded approximation*: FFD uses ≤ 11/9·OPT + 6/9 bins, provably |

## Greedy with caveats — the ones that bite in production

**Coin change as greedy-with-caveats.** Cash register systems (vending machines, retail POS float calculation) use greedy largest-first because real currency systems are *canonical* — provably greedy-safe. The classic failure: {1, 3, 4} at 6 → greedy gives 4+1+1 (3 coins), optimal is 3+3 (2 coins). Any system whose denomination set is chosen by product managers rather than proven canonical (loyalty points, store credit, coupon decomposition) needs DP. This exact bug class has shipped in real e-commerce promotions engines.

**Task scheduling in SRE context.** The LC 621 cooldown pattern is real: cron-job sprawl across a fleet (all backups at 00:00), rate-limited API clients (LeetCode 359 style token bucket + spacing), and retry storms (a retry queue that must space identical retries). The simulation you wrote is how `sidekiq`/`celery` throttled queues actually behave; the closed-form `max(len, (max_freq-1)*(n+1) + count)` is how you size the fleet in a capacity model without simulating.

**Interval scheduling in calendars.** Meeting-room *count* (LC 945-adjacent, "minimum meeting rooms") is NOT interval scheduling — it's maximum-overlap counting via a sweep or min-heap, because nothing is rejected, everything is assigned a room. The selection-maximization greedy (this lab) and overlap-counting (heap) get conflated constantly in system design interviews. Booking.com-style overbooking checks and calendar density heatmaps are the overlap problem; "how many 1:1s can I actually keep this week" is the selection problem.

## When greedy is wrong — the failure taxonomy

1. **0/1 knapsack (indivisibility).** Greedy-by-ratio fails because the exchange step cannot be performed "in units": atomic items can't be partially swapped. The fixture in this lab: capacity 50, items (10,60),(20,100),(30,120) → greedy 160, optimal 220. Needs DP.

2. **Non-canonical coin systems.** Local choice (largest coin) can't be exchanged for a multi-coin combination of equal-or-better value in arbitrary systems. Canonicality is a property of the denomination set, checkable per-set but not assumable. Needs DP.

3. **Global constraints interacting with local choices (dependencies).** Job scheduling with precedence constraints, interval scheduling with room capacities > 1: a locally-optimal accept can foreclose combinations that a slightly worse local accept would have unlocked. Needs DP, flow, or ILP.

4. **Wrong sort key for the actual objective.** Objective determines key: maximize count → finish time; minimize rooms → start-time sweep/heap; minimize max lateness → earliest deadline; minimize total completion time → shortest processing time; minimize weighted completion time → processing-time/weight ratio. Using the right algorithm with the wrong key is still a wrong greedy, and it still passes the examples that don't probe the difference.

5. **The pattern-match to a greedy problem that's actually something else.** "Maximum non-overlapping intervals" (selection, this lab) vs "minimum rooms" (overlap counting) vs "maximum parallel sessions" (overlap counting again) — three near-identical problem statements, three different algorithms.

## What the real libraries add over yours

- **Interval scheduling:** production calendar engines add recurrance expansion, timezone normalization, and tentative-vs-confirmed states; the finish-time core survives underneath all of it.
- **Task scheduling:** real schedulers add priority preemption, fairness (WFQ, DRF in Mesos), and bin-packing hints — the cooldown/spacing core stays greedy.
- **Huffman:** real implementations (zlib) cap code lengths (16 bits) via length-limiting adjustments after the greedy pass — a bounded, proven modification.
- **Knapsack at production scale:** capacity 10⁹ makes the pseudo-polynomial DP infeasible; real systems switch to FPTAS (provably within ε of optimal in poly time) or ILP solvers (CPLEX, Gurobi) — naming this escalation is the staff-level move.

## The 3 questions an interviewer asks after you describe this

1. *"You claim greedy is correct — prove it."* — The exchange argument: assume OPT disagrees at the first choice, swap, show feasibility and no-worse value, induct. If you cannot finish those four moves in three sentences, you do not have a greedy problem; you have a DP problem.
2. *"Why does the same ratio greedy work for fractional knapsack but not 0/1?"* — Divisibility is what lets the exchange step swap material in units. Atomic items make unit swaps infeasible, and the whole-for-whole swap can breach capacity — the exchange dies at step 2.
3. *"When would you ship a greedy you know is suboptimal?"* — When it has a bounded approximation ratio you can put in a design doc (FFD bin packing: ≤ 11/9·OPT), and the exact algorithm's complexity class is infeasible at your scale. "It passed the examples" is never the answer; the bound is.
