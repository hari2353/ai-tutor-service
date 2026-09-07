# Production notes — top-k selection

## Where top-k ships

- **Databases** — `ORDER BY revenue DESC LIMIT 100` is your dashboard query. Postgres offers both paths: a bounded heap (`top-N heapsort`) when N is small vs a full sort for the general case; the planner flips based on the ratio of N to rows.
- **Schedulers & OS** — the run queue is a priority queue; the Linux CFS uses a rb-tree, but `nice`-weighted pickers and timers are heap-shaped. Top-k by priority is the primitive.
- **Streaming analytics** — Kafka Streams / Flink `TopK` operators cannot buffer the stream; they keep a bounded heap (or Count-Min Sketch + heap) of size k. Your `TopKTracker` *is* that operator.
- **Search / recsys** — top-k retrieval over inverted indexes: every posting-list intersection ends in a bounded heap of the k best doc scores.
- **Leaderboards** — game leaderboards use the same bounded-heap ingest with periodic Redis ZSET flushing.

## Complexity table

| Approach | Time | Extra space | Streaming? | Notes |
|---|---|---|---|---|
| Full sort | O(n log n) | O(n) or O(log n) | no | simplest, fine to ~10⁷ in Python |
| Bounded min-heap | O(n log k) | **O(k)** | **yes** | the dashboard answer |
| quickselect | O(n) avg, O(n²) worst | O(1) in-place | no | median-of-median pivots → worst-case O(n) |
| Hash count + heap (top-k-frequent) | O(n log k) | O(distinct) | mostly | distinct values bound the map |
| Count-Min + heap | O(n log k) | O(sketch + k) | yes | approximate — heavy-hitter detection |

## The 3 questions an interviewer asks

1. *"k=10, n=10M, one pass, 10MB RAM — which algorithm and why?"* — bounded min-heap: O(k) memory, O(n log k) time, survives unlimited stream length. Quickselect needs all data resident.
2. *"When is quickselect's worst case a real risk?"* — adversarial or pre-sorted data with first/last-element pivots. Median-of-three fixes the common cases; median-of-medians fixes all of them but is 2-3x slower constant-factor.
3. *"Top-k-frequent: what's the actual memory bound?"* — O(distinct) for the counts — the heap is bounded but the map is not; if distinct is huge you need a sketch and you accept approximation.
