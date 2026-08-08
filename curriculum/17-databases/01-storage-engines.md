# B+Tree vs LSM-Tree: Compaction, Write/Read/Space Amplification

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T17-storage-engines` · **Tags:** internals, critical
> **Lab:** `labs/py/01-storage-engine-toy/`

## The 30-second version

B+Trees and LSM-Trees are both ways to make a slow disk look like a fast sorted map, and they make opposite bets. A B+Tree keeps data sorted on disk at all times and updates in place: every write does a small number of random I/Os (find the leaf, maybe split a page), so reads are cheap and predictable but writes cost more per byte because you're doing random writes into an existing structure. An LSM-Tree never updates in place: writes go to an in-memory memtable and get flushed sequentially as immutable SSTables, which makes writes extremely cheap (pure sequential I/O) but means reads may have to check several files and a background compaction process has to continuously rewrite data to keep read cost and space bounded. The concrete numbers: B-Trees (InnoDB) write-amplify roughly 3-4x and read-amplify close to 1x; LSM-Trees (RocksDB) write-amplify 10-30x+ under leveled compaction but sustain far higher write throughput because that amplification is sequential I/O done in the background, not blocking the write path. Pick B+Tree for read-heavy or mixed OLTP with moderate write rates (Postgres, MySQL/InnoDB); pick LSM for write-heavy, high-ingest workloads where you can tolerate read and space amplification (Cassandra, RocksDB-backed stores, time series, logging).

## Why this gets asked

Because "LSM is faster for writes" is a slogan, and the interviewer wants to know if you understand *why*, in terms of amplification, and whether you can reason about the actual tradeoff triangle (you cannot simultaneously minimize write, read, and space amplification — pick two). They've watched a team pick Cassandra for a read-heavy workload and get burned by read amplification across SSTables, or pick Postgres for a write-firehose ingestion pipeline and get burned by WAL and checkpoint I/O saturating disk. The follow-up they're really listening for is compaction: can you explain what it costs, when it falls behind, and what happens to p99 latency when it does.

---

## Lineage: past → present → future

**What came before.** Early databases used simple heap files with secondary indexes built as unbalanced binary trees or ISAM (Indexed Sequential Access Method, IBM, 1960s) — static, sorted index files rebuilt in bulk. ISAM's index was cheap to read but expensive to maintain: any insert that didn't fit in pre-allocated overflow space required a full rebuild, and overflow chains degraded lookups over time as inserts accumulated. The B-Tree (Bayer & McCreight, 1972) fixed this by allowing the index itself to grow incrementally through localized node splits, keeping it balanced without a full rebuild, and it became the default index structure for nearly every relational database for the next 40 years because random-access disks (spinning platters) made in-place updates with occasional splits a reasonable cost model. The pain that eventually mattered: as write volumes grew (especially with SSDs where random writes still cost more than sequential ones, and with distributed systems doing far higher ingest than a single spinning disk could serve), B-Tree random-write I/O became the bottleneck for write-heavy workloads, and rebalancing/splitting under heavy concurrent write load caused lock contention and unpredictable latency spikes.

**Where it stands now.** The LSM-Tree (O'Neil et al., 1996, "The Log-Structured Merge-Tree") turns random writes into sequential ones by never modifying data in place: writes accumulate in memory and get flushed as sorted, immutable files, deferring the cost of reorganization to an asynchronous background compaction process. Google's Bigtable (2006) and LevelDB (2011) popularized it in production; Facebook's RocksDB (2013, forked from LevelDB) is now the LSM engine embedded inside Cassandra (optionally), CockroachDB, TiKV, MyRocks, and countless other systems. The current consensus: B+Trees remain the right default for general-purpose OLTP with mixed read/write and moderate write volume (Postgres, MySQL/InnoDB, SQL Server all use B-Tree-family structures for primary storage), while LSM dominates for write-heavy, high-ingest, or embedded/mobile workloads (Cassandra, ScyllaDB, RocksDB-backed key-value stores, SQLite's newer LSM alternatives). The live disagreement is over **read amplification and compaction overhead in practice**: LSM proponents point to bloom filters and leveled compaction bringing read amplification down close to B-Tree levels for point lookups; skeptics point out that compaction is a real, ongoing CPU/IO tax that competes with foreground traffic and that tail latency under heavy write load is harder to bound in LSM systems than in B-Trees, where the cost model is simpler and more local.

**Where it's heading.** Hybrid designs are the active area: B-epsilon trees and "Bε-trees" (used in TokuDB/TokuMX, now largely superseded) tried to buffer writes inside internal B-Tree nodes to get some sequential-write benefit without going fully LSM; that lineage mostly lost to RocksDB's ecosystem dominance, but the idea persists in newer designs. **Key-value separation** (WiscKey, 2016, and RocksDB's BlobDB) — storing large values separately from the sorted key index to cut compaction I/O — is real and shipping, since compaction cost scales with total bytes moved, and if values are large, you're needlessly re-sorting bytes that don't need re-sorting. **FPGA/SmartSSD-offloaded compaction** and **disaggregated storage LSMs** (compaction running on separate compute from the write path, as in some cloud-native databases) are appearing in research and some managed cloud offerings, but are not yet a default anyone should assume without checking the specific vendor. Treat compaction offload as a real, still-maturing direction, not settled practice.

---

## Mental model

```
B+TREE (in-place, always sorted on disk)          LSM-TREE (append-only, sorted in stages)

        [ root ]                                   MEMTABLE (in-memory, sorted: skiplist/RB-tree)
       /   |    \                                       │  flush when full (e.g. 64MB)
   [leaf][leaf][leaf]  <- data lives here, sorted        ▼
   each write: find leaf (log_B N random reads),   L0:  [SSTable][SSTable][SSTable]  <- unsorted
              write in place, maybe SPLIT a              between files, sorted within
              full page into two                        │ compaction merges + sorts
                                                          ▼
   read: O(log_B N) — one path root->leaf,         L1:  [SSTable---][SSTable---]      <- sorted,
         page cache usually keeps upper                  non-overlapping key ranges
         levels hot, so ~1-2 real disk reads             │ compaction
                                                          ▼
                                                   L2:  [SSTable-------------]  (10x bigger than L1)
                                                          │ ...
                                                          ▼
                                                   Ln: bigger, older, colder data

                                                   read: check memtable, then L0 (may be several
                                                   files, all must be checked — no key-range
                                                   guarantee), then one file per lower level
                                                   (bloom filter skips most non-matches)
```

The one-sentence version: a B+Tree pays its reorganization cost **up front, per write, in place**; an LSM-Tree defers it to **background compaction, in bulk, out of the write path** — and that deferral is exactly what makes ingest fast and reads/space eventually more expensive.

---

## How it actually works

### B+Tree: node structure, fanout, height, splits

A B+Tree node (page) is a fixed-size block, typically matching the storage page size: **8 KB in Postgres, 16 KB in InnoDB by default**. Internal nodes store `(key, child-pointer)` pairs; only leaf nodes store the actual row data (or, for a clustered index, the full row) and leaves are linked together for efficient range scans.

**Fanout** is how many children a node has, bounded by how many `(key, pointer)` pairs fit in one page:

```
fanout ≈ page_size / (key_size + pointer_size)
```

For a 16 KB InnoDB page with a 16-byte key and 8-byte pointer, fanout ≈ 16384 / 24 ≈ **~680**. This is the single most important number in the whole structure, because tree **height** is `log_fanout(N)`:

```
N = 100,000,000 rows, fanout = 680
height = log_680(100,000,000) ≈ 3
```

Three or four levels covers essentially any table you will ever build, which is why "B-Tree lookups are O(log N)" is true but misleading in practice — it's really **O(3-4) disk reads**, and the top 1-2 levels are almost always cache-resident, so a warm B-Tree lookup is often **1 real disk read**, not log N of them.

**Splits.** An insert that doesn't fit in its target leaf splits the leaf into two half-full leaves and inserts a new separator key into the parent — which can itself overflow and split, cascading up to the root in the worst case (rare; most splits are one level). Splitting is the source of B-Tree write amplification: writing one 200-byte row can dirty an entire 16 KB page (and its neighbor, on a split), and that whole page gets flushed to disk — **write amplification here is `page_size / row_size`**, easily 20-80x at the page level, though buffer-pool batching means not every logical write triggers an immediate physical page write.

**Page layout** typically reserves a **fill factor** (Postgres default 100% for non-updated tables, commonly tuned to 70-90% for frequently-updated ones) — free space left in each page specifically so that updates (especially UPDATE-heavy HOT updates in Postgres) can happen without an immediate split. Leave no headroom and every insert into a full table triggers cascading splits; leave too much and you waste space and add a level to the tree sooner.

### LSM-Tree: memtable, SSTable, and the write path

1. **Write** goes to a WAL (for durability) and then into the **memtable** — an in-memory sorted structure (skip list in RocksDB, chunked into a red-black tree in some designs). This is a pure sequential WAL append plus an in-memory insert: no random disk I/O on the write path at all.
2. When the memtable hits a size threshold (RocksDB default **`write_buffer_size` 64 MB**), it becomes immutable and is flushed to disk as a new **SSTable** (Sorted String Table) — an immutable, sorted, indexed file, typically with a bloom filter and a sparse index block written alongside it.
3. Newly flushed SSTables land in **Level 0 (L0)**. Critically, L0 files can have **overlapping key ranges** with each other, because each one was flushed independently from a different memtable snapshot in time — this is why L0 is the most expensive level to read from.
4. **Compaction** merges SSTables together, dropping overwritten/deleted keys (tombstones) and re-sorting, producing new, larger SSTables in the next level down, whose key ranges no longer overlap within that level (in leveled compaction).

### Compaction strategies: size-tiered vs leveled

| | Size-tiered (STCS) | Leveled (LCS) |
|---|---|---|
| Structure | Files of similar size grouped; N similar-sized files merge into one bigger file when threshold reached | Fixed levels, each ~10x bigger than the last; each level (L1+) has non-overlapping key ranges |
| Write amplification | Lower (~O(log N) merges per key, fewer total rewrites) — roughly **10-15x** | Higher — every file at Ln can be rewritten by every compaction touching Ln+1, roughly **20-30x+** |
| Read amplification | Higher — many files can hold the same key range (no non-overlap guarantee within a tier) | Lower — one file per level (per key), so a point read checks memtable + L0 (several files) + one file per lower level |
| Space amplification | Higher — can temporarily need up to 2x the dataset size mid-compaction, and duplicate/overwritten data lingers longer across tiers | Lower — bounded overhead per level, tighter space usage overall |
| Used by | Cassandra (default was STCS historically, now often LCS or TWCS for time-series), old LevelDB configs | RocksDB (default), Cassandra's LCS option, most modern LSM stores |

The rule of thumb: **STCS trades read/space amplification for lower write amplification; LCS trades higher write amplification for lower read/space amplification.** Cassandra also has **Time-Window Compaction Strategy (TWCS)** for time-series data with TTLs — it groups SSTables by time window and never compacts across windows, so expired data drops out by simply deleting whole files, avoiding a rewrite entirely. If your workload is time-bucketed with TTL expiry, TWCS is usually the right answer and neither STCS nor LCS is.

### Write, read, and space amplification — defined precisely

- **Write amplification (WA)** = (total bytes physically written to storage) / (bytes the application logically wrote). A B-Tree writing a 200-byte row into a dirtied 16 KB page that eventually gets flushed has WA driven by page-to-row-size ratio and buffering; concretely **B-Tree WA ≈ 3-4x** for typical OLTP with buffer pool batching, and **LSM WA ≈ 10-30x** under leveled compaction because each byte gets rewritten roughly once per level it passes through.
- **Read amplification (RA)** = (number of disk reads to answer one logical read) / (1). B-Tree point reads are close to **RA ≈ 1-2** once warm (root/internal pages cached). LSM point reads must potentially check the memtable, every L0 file (several), and one file per remaining level — **RA can be 5-10+ without bloom filters**, brought down to **~1-2 effective I/Os** with well-tuned bloom filters (RocksDB default **10 bits per key ≈ ~1% false-positive rate**) that let you skip files that provably don't contain the key.
- **Space amplification (SA)** = (physical bytes on disk) / (logical bytes of live data). B-Trees have SA driven by page fill factor and fragmentation, typically **1.1-1.5x**. LSM has SA driven by how much stale/overwritten data hasn't been compacted away yet — can spike to **2x+** mid-compaction and settles to **1.1-1.3x** for well-tuned leveled compaction, but can be much worse under size-tiered strategies or when compaction falls behind ingest.

You cannot minimize all three simultaneously — this is a proven tradeoff space (see the RUM conjecture: Read, Update, Memory — pick two to optimize). B-Trees optimize read and memory (space) at the cost of update (write) cost; LSM optimizes update at the cost of read and space.

### Which workloads suit which

| Workload | Engine | Why |
|---|---|---|
| OLTP, mixed read/write, point lookups dominant, moderate write rate | B+Tree (Postgres, InnoDB) | Read amplification stays low; write cost is acceptable at OLTP scale; ACID transaction semantics are mature |
| High-ingest logging, metrics, event streams, append-heavy | LSM (Cassandra, RocksDB) | Sequential-write throughput is 5-10x higher; reads are less latency-sensitive or served from a cache/index in front |
| Embedded / mobile with limited I/O bandwidth | LSM (RocksDB, LevelDB) or SQLite (B-Tree) depending on read/write ratio | LSM if writes dominate flash-wear and battery cost; SQLite's B-Tree if reads dominate and simplicity matters |
| Time-series with TTL expiry | LSM + TWCS specifically | Whole-file drops on expiry avoid rewriting live data at all |
| Analytics / OLAP scans | Neither directly — columnar (see `15-oltp-vs-olap.md`) | Both B-Tree and LSM are row-oriented point-access structures; large sequential scans want columnar layout instead |

---

## Build it from scratch

A minimal from-scratch LSM (the more illustrative build, since a correct from-scratch B-Tree with splits is a bigger undertaking better suited to the lab):

```python
# untested sketch — illustrates the mechanics, not production-grade
import bisect, os, json

class Memtable:
    def __init__(self):
        self.data = {}          # dict stands in for a sorted skiplist

    def put(self, key, value):
        self.data[key] = value  # tombstone value = None means delete

    def get(self, key):
        return self.data.get(key, "MISS")

    def size_bytes(self):
        return sum(len(k) + len(str(v)) for k, v in self.data.items())


class SSTable:
    """Immutable, sorted, on-disk file with a sparse index and a bloom filter stand-in."""
    def __init__(self, path, sorted_items):
        self.path = path
        with open(path, "w") as f:
            json.dump(sorted_items, f)          # real impl: block-based binary format
        self.keys = [k for k, _ in sorted_items]  # in-memory sparse index for the demo

    def get(self, key):
        i = bisect.bisect_left(self.keys, key)
        if i < len(self.keys) and self.keys[i] == key:
            with open(self.path) as f:
                return dict(json.load(f))[key]
        return "MISS"


class LSMTree:
    def __init__(self, dir_, memtable_limit=4096):
        self.dir = dir_
        os.makedirs(dir_, exist_ok=True)
        self.memtable = Memtable()
        self.memtable_limit = memtable_limit
        self.sstables = []          # newest first; real impl organizes by level

    def put(self, key, value):
        self.memtable.put(key, value)
        if self.memtable.size_bytes() >= self.memtable_limit:
            self._flush()

    def _flush(self):
        sorted_items = sorted(self.memtable.data.items())
        path = os.path.join(self.dir, f"sst_{len(self.sstables)}.json")
        self.sstables.append(SSTable(path, sorted_items))
        self.memtable = Memtable()

    def get(self, key):
        v = self.memtable.get(key)
        if v != "MISS":
            return v
        for sst in reversed(self.sstables):     # newest first: most recent write wins
            v = sst.get(key)
            if v != "MISS":
                return v
        return "MISS"

    def compact(self):
        """Naive full compaction: merge everything, drop tombstones and superseded keys."""
        merged = {}
        for sst in self.sstables:               # oldest first so newer overwrites older
            with open(sst.path) as f:
                merged.update(dict(json.load(f)))
        merged = {k: v for k, v in merged.items() if v is not None}  # drop tombstones
        for sst in self.sstables:
            os.remove(sst.path)
        self.sstables = []
        for k, v in sorted(merged.items()):
            self.memtable.put(k, v)
        self._flush()
```

This demo makes the core tradeoff visible: `put` never touches existing files (sequential-only write path); `get` in the worst case scans every SSTable (unbounded read amplification without bloom filters or leveling); `compact` is the expensive, all-at-once operation real systems break into incremental, leveled background work. Full version with a real bloom filter, leveled compaction, and a companion from-scratch B-Tree with node splits: **`labs/py/01-storage-engine-toy/`**.

---

## How it's done in production

**Postgres / InnoDB (B+Tree family).** Both use a clustered or heap-plus-secondary-index B-Tree for storage, a buffer pool/shared buffers cache to keep hot pages in memory, and a WAL for durability (see `02-wal-recovery.md`). InnoDB additionally uses a **change buffer** to defer secondary-index updates for non-unique indexes when the target page isn't in the buffer pool, batching what would otherwise be scattered random writes. Both rely on **fill factor** and periodic maintenance (Postgres `VACUUM`, see `06-postgres.md`) to keep page utilization from degrading under update-heavy workloads.

**RocksDB / Cassandra (LSM family).** RocksDB exposes compaction strategy, level sizing, and bloom-filter bits-per-key as tunables; Cassandra layers replication, tombstone handling (`gc_grace_seconds`), and repair on top of an LSM per node. Cassandra's default per-node engine is its own LSM implementation (not literally RocksDB, though ScyllaDB and ports like MyRocks embed RocksDB directly).

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Write latency p99 spikes periodically, then recovers | Memtable flush or a large compaction competing with foreground I/O | Increase memtable size / flush threshold, cap compaction I/O with rate limiting (RocksDB `rate_limiter`), add more compaction threads |
| Reads get progressively slower over days/weeks | Compaction has fallen behind ingest; L0 file count keeps growing (read amplification climbs) | Alert on L0 file count / pending compaction bytes; throttle write rate or scale compaction parallelism; this is the single most common LSM production incident |
| Disk usage far exceeds logical data size | Size-tiered compaction lingering, or tombstones/expired TTL data not yet compacted away | Switch to leveled or TWCS as appropriate; tune `gc_grace_seconds`/tombstone thresholds; force a major compaction as a stopgap |
| B-Tree table bloats, sequential scans get slower over time | Page splits leave partially-full pages; deletes/updates leave dead tuples (Postgres) | `VACUUM`/`OPTIMIZE TABLE`, tune fill factor, autovacuum tuning (see `06-postgres.md`) |
| Insert latency degrades under heavy concurrent write load on a B-Tree | Lock contention on hot leaf pages / index page splits cascading | Use a lower-cardinality/monotonic-friendly key strategy, batch writes, consider an LSM-backed engine for that table if the write rate is fundamentally too high for in-place updates |
| RocksDB write stalls entirely ("Stopping writes") | L0 file count or pending compaction bytes crossed a hard stop threshold (`level0_stop_writes_trigger`) | This is by design — a safety valve, not a bug. Fix the upstream compaction-vs-ingest imbalance; don't just raise the threshold, which converts a stall into unbounded read amplification |

---

## Tradeoffs & when NOT to use it

- **Do not use an LSM engine for latency-sensitive point-read-heavy workloads without verifying read amplification under your real data distribution.** A cold, poorly bloom-filtered LSM can be 5-10x slower per read than a warm B-Tree.
- **Do not use a B-Tree engine for a write-firehose ingestion pipeline (metrics, logs, event streams) at high sustained write rates.** Random-write I/O and page-split contention will become the bottleneck well before an LSM would.
- **Do not pick size-tiered compaction for a workload with tight read-latency SLOs.** STCS's read amplification (many overlapping files) is the wrong tradeoff when reads matter; use leveled compaction or a hybrid.
- **Do not ignore compaction debt as an operational metric.** "Pending compaction bytes" and "L0 file count" are leading indicators of a coming latency cliff; they're invisible until you instrument them, and by the time reads visibly slow down, the backlog is already large.
- **For time-series with TTL expiry, neither plain STCS nor LCS is optimal** — use time-window compaction so whole expired files are dropped rather than rewritten.
- **For OLAP-style large sequential scans, neither engine is the right storage layout at all** — both are row-oriented, point-access-optimized structures; you want columnar storage (see `15-oltp-vs-olap.md`).

---

## Interview questions

### Q1 — What's the fundamental difference between a B+Tree and an LSM-Tree?
**Testing:** baseline vocabulary.
**Answer:** A B+Tree keeps data sorted on disk at all times and updates in place, paying reorganization cost (page splits) per write. An LSM-Tree never updates in place — writes go to an in-memory memtable, flush as immutable sorted SSTables, and a background compaction process merges them, deferring reorganization cost to an async process off the write path.
**Follow-up trap:** *"So LSM is just faster?"* — no, it trades lower write cost for higher read and space amplification; it's a different point on the RUM tradeoff curve, not a strict improvement.

### Q2 — Derive B-Tree height for 100M rows with a realistic fanout.
**Testing:** whether "O(log N)" is actually understood as a number.
**Answer:** Fanout ≈ page_size / (key_size + pointer_size); for a 16 KB page, 16-byte key, 8-byte pointer, fanout ≈ 680. Height = log_680(100,000,000) ≈ 3. With the top levels cached, a warm lookup is often 1 real disk read.
**Follow-up trap:** *"What happens to height if you double the key size?"* — fanout roughly halves (680 → ~400 for a doubled key), and height barely changes (still ~3-4) because log is insensitive to the base at this scale — the bigger practical cost is more pages needed overall, not a taller tree.

### Q3 — Define write, read, and space amplification precisely, with numbers.
**Testing:** whether these are understood as ratios with real values, not adjectives.
**Answer:** WA = physical bytes written / logical bytes written (B-Tree ~3-4x, LSM leveled ~10-30x). RA = disk reads per logical read (B-Tree ~1-2x warm, LSM ~1-2x with tuned bloom filters, 5-10x+ without). SA = physical bytes on disk / logical live bytes (B-Tree ~1.1-1.5x, LSM ~1.1-1.3x well-tuned, spikes to 2x+ mid-compaction).
**Follow-up trap:** *"Can you minimize all three at once?"* — no, this is the RUM conjecture: Read, Update, Memory (space) — optimizing any two makes the third worse, and it's provable, not just an engineering habit.

### Q4 — Size-tiered vs leveled compaction: what's the actual tradeoff?
**Answer:** Size-tiered merges similar-sized files together when a threshold count is reached — lower write amplification (~10-15x) but files can have overlapping key ranges, so point reads may check many files (higher read amplification) and space can temporarily balloon to ~2x during merges. Leveled compaction maintains non-overlapping key ranges per level — lower read amplification (one file per level) and tighter space usage, at the cost of higher write amplification (~20-30x+) since data gets rewritten roughly once per level it passes through.
**Follow-up trap:** *"Which does Cassandra use by default?"* — historically size-tiered, but leveled and time-window strategies are common choices depending on workload; the honest answer is "it's configurable per table and the choice should follow the read/write/TTL profile," not a fixed default you can assume without checking the table's schema.

### Q5 — What is write amplification actually caused by, mechanically, in each structure?
**Answer:** B-Tree: a single row update dirties an entire page (8-16 KB), and that whole page gets flushed even though only a fraction of it logically changed; a split doubles this by dirtying two pages instead of one. LSM: compaction rewrites every key it touches into a new file at the next level, so a key that survives K compaction passes (one per level it moves through) gets physically rewritten K times before it's "settled."
**Follow-up trap:** *"Does buffer pool batching change the B-Tree number?"* — yes, meaningfully: if many logical writes hit the same hot page before it's flushed, the effective amplification per logical write drops, which is why real-world B-Tree WA (~3-4x) is much lower than the naive page/row-size ratio (~20-80x) would suggest.

### Q6 — Your LSM-backed store's read latency has been climbing steadily for two weeks. Diagnose.
**Answer:** Almost certainly compaction has fallen behind write throughput: L0 file count is growing (each L0 file must be checked on most reads since they can overlap in key range), or pending-compaction-bytes is climbing. Check compaction metrics first, not query plans. Fix by throttling ingest, increasing compaction parallelism/threads, or, if this is chronic, re-evaluating whether the write rate has outgrown the current compaction strategy/hardware.
**Follow-up trap:** *"Isn't this just an indexing problem?"* — no, and reaching for "add an index" here is a red flag; the read path is already using the LSM's own sorted structure and bloom filters, this is an operational compaction-debt problem, and the fix is on the write/background-process side, not the query side.

### Q7 — Why does a B-Tree's write amplification stay roughly constant while an LSM's grows with the number of levels?
**Answer:** A B-Tree write touches O(height) pages regardless of total data size beyond the point where height stops growing meaningfully (log_680 grows extremely slowly), so amplification per write is roughly constant. An LSM key gets rewritten once per compaction pass, and the number of levels (hence passes) grows with total data volume (each level ~10x the last), so total write amplification for a key that survives to the bottom level scales with the number of levels, which does grow — slowly, but it does, as the dataset grows by orders of magnitude.
**Follow-up trap:** *"So LSM write amplification is unbounded?"* — bounded per level transition (leveled compaction has a well-understood formula, roughly the level size ratio times the number of levels), but yes, it grows with total data size in a way B-Tree page-level amplification largely doesn't; this is exactly why key-value separation (WiscKey) exists — to decouple large-value bytes from the part that needs repeated re-sorting.

### Q8 — When would you choose Cassandra/RocksDB over Postgres for a new service, and when would that be a mistake?
**Answer:** Choose LSM-backed storage when sustained write throughput is the primary constraint (high-cardinality event ingestion, time series, write-heavy logging) and reads are either less latency-sensitive, mostly recent-data-only (helped by bloom filters and hot-tier caching), or served through a separate index/cache. It's a mistake when the workload actually needs multi-row ACID transactions, complex joins, or is read-dominated with unpredictable access patterns — Postgres's B-Tree plus mature query planner and transaction semantics will outperform and be far easier to operate for that shape of workload.
**Follow-up trap:** *"Can't you just add secondary indexes to Cassandra?"* — Cassandra's secondary indexes are notoriously weak for high-cardinality columns and don't behave like a relational index; the real answer for query flexibility on an LSM store is usually denormalization into query-specific tables (or a separate search/index layer), not a secondary index reflex.

### Q9 — Explain what a bloom filter buys an LSM-Tree, with the actual numbers.
**Answer:** A bloom filter is a probabilistic set-membership structure attached to each SSTable: it can say "definitely not present" (skip this file, no disk I/O) or "maybe present" (must check the file). RocksDB's default of ~10 bits per key gives roughly a 1% false-positive rate, which means for a key that doesn't exist in a given file, you skip the disk read ~99% of the time — turning what would be an O(number of files) read amplification problem into close to O(1) for keys that mostly don't exist in most files, and O(levels) for keys that do exist somewhere.
**Follow-up trap:** *"What happens to the false-positive rate under heavy memory pressure?"* — if bloom filters get evicted from memory (they're usually block-cached), you're back to a real disk read to check file membership; this is a common cause of latency regressions after a memory-limit change or a bigger-than-expected dataset that pushes filters out of cache.

### Q10 — What is space amplification and why does an LSM sometimes need 2x the dataset's logical size mid-operation?
**Answer:** SA = physical bytes on disk / logical live bytes. During compaction, the input SSTables and the newly-written merged output SSTable coexist on disk until the merge completes and the inputs are deleted — for a full/major compaction this can temporarily require close to double the steady-state disk footprint. This is a real operational planning number: provisioning disk at exactly the steady-state size risks running out of space mid-compaction.
**Follow-up trap:** *"Does a B-Tree have an equivalent spike?"* — less dramatic, but yes: online index rebuilds and some `VACUUM FULL`-style operations in Postgres build a new copy of the table/index before dropping the old one, requiring roughly double the table's size in free disk space during the operation.

### Q11 — Design the compaction strategy for a metrics/time-series ingestion system with 30-day TTL retention.
**Testing:** whether the candidate can apply the general compaction taxonomy to a specific workload rather than reciting it.
**Answer:** Time-Window Compaction Strategy: bucket SSTables by write time window (e.g., daily), compact only within a window, never merge across windows. When a window's TTL fully expires, drop the entire file(s) for that window rather than rewriting live data to remove a few expired keys — this converts expiry from "rewrite everything to remove a fraction" into "delete a file," which is both cheaper and avoids paying compaction I/O for data that's about to be deleted anyway.
**Follow-up trap:** *"What if some rows in a time bucket have a different TTL than others?"* — that breaks TWCS's core assumption (uniform expiry per window); you'd need per-row TTL handling via tombstones and a strategy tolerant of intra-window compaction (STCS or LCS within the window), accepting the extra rewrite cost for the subset of non-uniform-TTL data, or splitting that data into a separate table with its own TTL policy.

### Q12 — A candidate says "just use whichever the framework defaults to." How do you push back on that as an interviewer, and what should the real answer include?
**Testing:** staff-level judgment about tradeoffs, not memorized facts.
**Answer:** The real answer names the workload's read/write ratio, latency SLO, data growth rate, and whether TTL/time-bucketing applies, and derives the choice (and compaction strategy) from those, the same way you'd size a bulkhead from Little's Law rather than guessing. "It depends" is only a good answer when you say what it depends on and where your specific workload lands on those axes.
**Follow-up trap:** *"Give me the one number you'd ask for first."* — sustained write throughput relative to available disk sequential-write bandwidth and CPU headroom for compaction; if the number needed exceeds what the box can do plus compaction overhead with margin, no amount of engine choice fixes an underprovisioned box, and that's the conversation before compaction strategy even comes up.

---

## Red flags that fail you

- Saying "LSM is faster" without qualifying "faster for writes, at the cost of read/space amplification."
- Describing B-Tree lookup as "O(log N) disk reads" without noting that cached upper levels make it effectively O(1-2) real I/Os in practice.
- Not knowing what compaction is, or describing it as optional.
- Claiming you can minimize write, read, and space amplification simultaneously (violates the RUM tradeoff).
- Reaching for "add an index" as the fix for LSM read-latency regressions instead of checking compaction debt.
- Not knowing what a bloom filter does or claiming it eliminates false positives.
- Recommending Cassandra/RocksDB for a workload that fundamentally needs multi-row ACID transactions and complex joins.

---

## Cheat card

```
B+TREE     in-place updates, always sorted on disk. fanout ≈ page/(key+ptr) ~500-700
           height = log_fanout(N) ~3-4 levels for 100M+ rows; warm lookup ~1-2 real I/Os
           write: find leaf + maybe SPLIT (cascades rarely past 1-2 levels)
           WA ~3-4x · RA ~1-2x · SA ~1.1-1.5x
           pages: Postgres 8KB, InnoDB 16KB default

LSM-TREE   never in-place. memtable (sorted, in-mem, e.g. skiplist) -> flush -> SSTable
           L0: overlapping key ranges (expensive to read) -> compaction -> Ln: non-overlapping
           WA leveled ~20-30x+, size-tiered ~10-15x · RA ~1-2x w/ tuned bloom, 5-10x+ w/o
           SA ~1.1-1.3x tuned, spikes ~2x mid-compaction
           bloom filter: ~10 bits/key -> ~1% false positive -> skips most non-matching files

COMPACTION   size-tiered: lower WA, higher RA/SA. leveled: higher WA, lower RA/SA (RocksDB default)
             TWCS: bucket by time window, drop whole expired files — right for TTL'd time series

RUM CONJECTURE   Read, Update, Memory(space) — optimize any two, third gets worse. No free lunch.

WORKLOAD FIT   OLTP/read-heavy/mixed -> B-Tree (Postgres, InnoDB)
               write-firehose/ingest/logs/TS -> LSM (Cassandra, RocksDB)
               OLAP scans -> neither; columnar (see 15-oltp-vs-olap.md)

PRODUCTION SIGNAL   L0 file count / pending-compaction-bytes climbing = leading indicator
                     of coming read-latency cliff. Instrument it before it's visible in p99.

REAL SYSTEMS   Postgres/InnoDB = B+Tree family + WAL + buffer pool (+change buffer, InnoDB)
               RocksDB/Cassandra = LSM family; MyRocks = InnoDB API over RocksDB storage
```

## Sources

- [Closing the B+-tree vs. LSM-tree Write Amplification Gap (USENIX FAST 2022)](https://www.usenix.org/system/files/fast22-qiao.pdf) — accessed 2026-07-26
- [TiKV Deep Dive: B-Tree vs LSM-Tree](https://tikv.org/deep-dive/key-value-engine/b-tree-vs-lsm/) — accessed 2026-07-26
- [The Great Storage Engine Debate: B-Trees vs LSM-Trees — Medium](https://medium.com/@sylvain.tiset/the-great-storage-engine-debate-b-trees-vs-lsm-trees-35d6975f2ede) — accessed 2026-07-26
- [Scavenger+: Space-Time Trade-offs in Key-Value Separated LSM-trees (arXiv 2508.13935)](https://arxiv.org/pdf/2508.13935) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
