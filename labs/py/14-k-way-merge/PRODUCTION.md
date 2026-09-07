# Production notes — k-way merge

## Where k-way merge ships

- **External sorting** — every database `ORDER BY` that spills to disk: sort runs of RAM-sized chunks, then k-way merge the runs. Postgres, Spark `sortMerge`, DuckDB spill files — all the same shape. The merge phase is a heap (or tournament tree) of run cursors.
- **MapReduce / Spark shuffle** — the reduce side receives k sorted map-output partitions per key-range and merges them; this is the actual "shuffle sort" step.
- **LSM-tree compaction** — RocksDB/Cassandra merge sorted runs (memtable + SSTables). Size-tiered compaction is literally `merge_k_sorted_lists` on disk; Leveled compaction merges k=2 mostly. The merge step is where write amplification is paid.
- **Log merge / time-series** — merging k sorted log segments by timestamp (the `k-way` in every log-structured system).
- **Search engines** — posting-list intersection/union is a k-way merge over sorted doc-id lists.

## Complexity table

| Strategy | Comparisons | Notes |
|---|---|---|
| Pairwise append (`res = merge(res, next)`) | O(Nk) | the trap — fine for k=2, awful for k=200 |
| Divide & conquer (merge pairs of lists) | O(N log k) | good cache behaviour, but needs the data twice |
| Binary heap of k cursors | O(N log k) | **O(k) memory** — the streaming/external answer |
| Tournament tree (loser's tree) | O(N log k), ~½ the comparisons | what production sorters use |
| 2-way merge per level, k = #runs | O(N log k) disk passes | I/O-bound: minimise passes, not comparisons |

For external sort the real cost is I/O passes: with 1GB RAM and 100GB input you get 100 runs; one merge pass at k=100 is feasible — k > RAM/runs forces multiple passes (fan-in limited by memory + file descriptors).

## The 3 questions an interviewer asks

1. *"Why a min-heap of cursors and not just concatenating and sorting?"* — O(N log k) vs O(N log N), and merge is streaming: memory stays O(k) even when N is infinite.
2. *"Where does merge stability come from?"* — tie-break by source-list index inside the heap key; the loser's tree encodes it by construction.
3. *"LSM reads get slower as runs accumulate — why?"* — point lookup must check every run; compaction (k-way merge) trades write amplification for read freshness. Same primitive, different cost centre.
