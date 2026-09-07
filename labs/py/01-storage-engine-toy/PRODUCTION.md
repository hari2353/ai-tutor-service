# Production notes — LSM storage engines

## What you'd actually use

| Your piece | Real thing | What it adds over yours |
|---|---|---|
| MemTable (dict + sort) | RocksDB skiplist memtable (`write_buffer_size` default 64 MB) | lock-free concurrent writers, arena allocation, immutable-memtable switch so writers never stall during flush |
| SSTable (JSON lines) | RocksDB SST files: block-based, prefix-compressed, sparse index block, per-file bloom filter (`FilterPolicy`, ~10 bits/key ≈ 1% FP) | binary format ~10-20x smaller, index blocks cached separately from data, whole-file skip via bloom |
| Manifest (a JSON list) | RocksDB `MANIFEST-*` (itself a log) + `CURRENT` pointer, atomic via rename | versioned edits (add/delete file), recovery replays the manifest log to reconstruct live state |
| Reads newest-first | memtable → L0 (many files, overlapping ranges) → one file per level below, bloom-filtered | read amplification bounded by levels, not file count; ~1-2 real I/Os warm |
| Tombstone (None) | real tombstone records with sequence numbers + `gc_grace_seconds` (Cassandra) | tombstones must *outlive* replicas' missed deletes — dropping them too early resurrects deleted data |
| `compact()` full merge | background leveled (RocksDB default) / size-tiered / time-window (Cassandra TWCS) | incremental, throttled (`rate_limiter`), non-blocking; only expired whole files drop for TTL workloads |
| fsync discipline | WAL before memtable insert (`WriteOptions.sync`) | your toy skips durability entirely — crash = memtable loss; the next lab (`02-wal-toy`) builds exactly that piece |

The systems to name in interviews: **RocksDB** (embedded LSM; Cassandra option, CockroachDB, TiKV, MyRocks), **LevelDB** (the 2011 origin, simpler, single-threaded compaction), **Cassandra/ScyllaDB** (LSM per node + replication + repair on top), **HBase/Bigtable** lineage (memtable → SSTable is literally the Bigtable paper's terminology), **SQLite's LSM extension**.

## What the real ones add over yours

- **Sequence numbers.** Every write carries a global monotonic seq; versions are compared by seq, not file order — same effect as your newest-SSTable-first ordering, but explicit and checked per record.
- **Levels with non-overlapping ranges.** Your `compact()` is a full (major) compaction every time — O(total data) per call. Real systems do minor compactions that touch only a few files; that is the entire write-amplification story (10-30x leveled vs ~10-15x size-tiered).
- **Background + throttled compaction.** Foreground `compact()` blocks the caller; real compaction runs on separate threads with I/O rate limits so p99 write latency doesn't see it — and has backpressure stop-writes triggers (`level0_stop_writes_trigger`) when it falls behind.
- **Crash-safe flush and manifest.** Flush writes a temp file, fsyncs, renames, then commits via a manifest *edit record* — any crash in the middle leaves either the old or the new state, never a half-written SSTable. Yours could be caught mid-file by a crash.
- **Bloom filters + block cache.** Point reads in your engine open every file; production skips most files in memory (bloom) and caches hot blocks.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| p99 write latency spikes periodically | memtable flush or big compaction competing with foreground I/O | bigger `write_buffer_size`, compaction rate limiting, more compaction threads |
| Reads slow down steadily over weeks | compaction fallen behind ingest; L0 file count climbing (each L0 file must be checked per read) | alert on L0 count / pending-compaction-bytes; throttle writes or scale compaction — the classic LSM production incident |
| Disk usage ≫ logical data size | stale versions + tombstones not yet compacted away; size-tiered lingering | force major compaction as stopgap; switch strategy (leveled / TWCS for TTL data) |
| Tombstone "resurrection" bug | compaction dropped a tombstone while a replica still had an older value | Cassandra `gc_grace_seconds` — hold tombstones longer than replication-lag repair windows |
| Writes stall entirely ("Stopping writes") | `level0_stop_writes_trigger` hit — a deliberate safety valve | fix the compaction-vs-ingest imbalance; raising the trigger converts a stall into unbounded read amplification |

## The 3 questions an interviewer asks after you describe this

1. *"Why is a write to your engine cheaper than a B+Tree write?"* — one sequential file append (plus the memtable insert) vs finding a leaf + possibly splitting pages. The reorganization cost is deferred to background bulk merges — that's the entire tradeoff, not a free lunch.
2. *"What's the cost of that cheap write?"* — read amplification (check memtable + every L0 file + one file per level), space amplification (stale versions linger until compaction), and the compaction CPU/IO tax competing with foreground traffic. RUM conjecture: you can't minimize all three.
3. *"When does compaction drop a tombstone?"* — only when the compaction's inputs include *everything* older than it (a full compaction, or the bottom level). Drop it while an older version survives somewhere and a later read resurrects the deleted key — the subtlest correctness bug in every LSM codebase.

## What breaks at scale (amplification numbers)

| Metric | B+Tree (InnoDB/Postgres) | LSM (RocksDB) |
|---|---|---|
| Write amplification | ~3-4x (buffer pool batches page writes) | ~10-15x size-tiered, 20-30x+ leveled |
| Read amplification | ~1-2x warm (cached upper levels) | ~1-2x with tuned blooms, 5-10x+ without |
| Space amplification | 1.1-1.5x (fill factor, fragmentation) | 1.1-1.3x tuned; spikes to ~2x mid-compaction |
