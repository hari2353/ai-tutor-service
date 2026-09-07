# Production notes — range trees

## Where these actually run

| Structure | Real system |
|---|---|
| Segment trees / Fenwick | Database range aggregates: PostgreSQL index-only scans over sorted runs, time-series engines (InfluxDB, Prometheus downsampling windows) |
| BIT over ranks | Competitive programming's workhorse: CSES / Codeforces range-update problems; CF ratings run on these |
| Inversion counting | Near-duplicate detection (documents "close" when inversion count is low), measuring sortedness of streams, Kendall-tau rank correlation — Spotify / recommendation systems computing rank agreement |
| Lazy propagation | Multi-tenant accounting: apply a rate to every user in an ID range (ledger balances, billing tiers) without touching each row |

## What the real ones add over yours

- **Persistence / versioning** — persistent segment trees give sum-at-time-t (git-for-your-data). Production time-series engines snapshot buckets rather than mutate; your tree can't time-travel.
- **Concurrency** — yours is single-threaded. Atlassian or database implementations shard by node subtree so readers go lock-free; writes take an epoch or a compare-and-swap on the node.
- **B-tree crossover** — production range aggregates actually live in B+ trees with page-level cached sums (every database index is a segment tree over pages, with lazy tag = "page dirty, recompute later"). Your 4n array-of-doubles is a teaching shape; real ones sit on disk pages.
- **Compression** — lossy bucketing (t-digest, DDSketch) trades exactness for fixed memory. For streaming quantiles over 10⁹ elements you don't build an exact tree, you build a sketch.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Range sum slower than a plain list | Updates rare, ranges mostly full | Don't build a tree for a read-mostly workload — a prefix-sum array is O(1) per query |
| Lazy tree returns stale sums | Tags applied on the way down but not pushed to leaves before sibling visits | Push before descending; the discipline is the entire correctness argument |
| BIT gives wrong answers | Mixed 0-based API and 1-based internals | Pick one convention at the module boundary; off-by-one here is the most common bug in BIT code |
| Inversions wrong on duplicates | Using `>=` instead of `>` when counting previous-strictly-greater | Equal elements never invert; count strictly greater |
| Counting inversions O(n²) | Nested loops "good enough" | BIT over ranks, O(n log n) — the reason LeetCode 493 exists |

## The 3 questions an interviewer asks after you describe this

1. *"Prefix sums are O(1) — why does anyone build a tree?"* — updates. A prefix array pays O(n) per point update; the tree pays O(log n). If your workload is read-only, you don't need the tree — saying that earns more points than building it.
2. *"Why does a BIT need n integers and a segment tree 4n?"* — the BIT stores partial prefix sums overlapping only its own index path (one value per index, exploiting the `i & -i` parent structure); the segment tree stores one node per interval of a full binary decomposition. You trade generality (BIT can't do arbitrary lazy range updates) for half the memory and a tighter constant.
3. *"Count inversions in 10 million elements?"* — coordinate-compress, BIT of counts, O(n log n), ~10⁸ ops; or merge sort with a counting side-effect if values are already dense integers. Be ready for the follow-up: "what does inversion count tell you about two rankings?" — Kendall tau similarity.
