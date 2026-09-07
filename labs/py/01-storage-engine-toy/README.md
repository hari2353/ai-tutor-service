# Lab 01: A Toy LSM-Tree Storage Engine

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2.5h · **XP:** 50
**Module:** `T17-storage-engines`

**You will build:** a working LSM-tree key-value store — `MemTable` (sorted write path), flush-to-`SSTable` when a size threshold is hit (files written under a `tmp_path` directory injected via the constructor), a `Manifest` tracking SSTables, newest-first reads, tombstone deletes, and size-tiered compaction that merges SSTables while keeping only the newest version of each key and dropping shadowed tombstones.

**You will be able to answer:** *"Walk me through the full write and read path of an LSM-tree — and why does compaction exist at all?"*

## Setup

```bash
cd labs/py/01-storage-engine-toy
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Tombstone`** — the delete marker. A sentinel value: `put(key, None)` deletes. `is_tombstone(v)` tells a tombstone from a real value. A tombstone *shadows* older versions during reads; it is *dropped* only when it can no longer shadow anything (full compaction).
2. **`MemTable`** — the sorted, in-memory write path. `put(key, value)` (value `None` = delete), `get(key)` returns the value or `None` when the key is absent (careful: a live `None`-valued key and an absent key must be distinguishable — use `MISSING` as your absence sentinel), `size()` returns the entry count, `items()` returns keys in sorted order. The real-world stand-in is a skip list; a plain dict plus a sort is enough here.
3. **`SSTable`** — an immutable sorted file. Written with `SSTable.create(path, items)` as JSON lines, read back with `SSTable(path)` + `.get(key)` (binary search over the in-memory key index, read the file for the payload) and `.items()`. A key that was deleted in that SSTable reads back as the `Tombstone`.
4. **`Manifest`** — the list of live SSTable paths, newest first, persisted as `manifest.json`. `add(path)`, `all()` (newest first), `replace(old_paths, new_path)` — the compaction swap. A fresh engine re-opens the manifest and reads its SSTables back off disk.
5. **`LSMTree(dir, memtable_limit)`** — `put`/`get`/`delete`. Writes go to the memtable; when `memtable.size() >= memtable_limit`, flush to a new SSTable file and clear. **Reads check the memtable first, then SSTables newest-first** — first hit wins, whether it is a value (return it) or a tombstone (key is deleted — stop looking). Absent everywhere → `KeyError`.
6. **`compact()`** — merge every SSTable into one: take keys oldest→newest so newer versions overwrite, keep the newest version of each key, drop tombstones that nothing older can survive beneath (a full compaction has nothing below, so all tombstones go), write one new SSTable, `replace` the inputs in the manifest, delete the input files. Data must survive across compaction, and reads must be unchanged after it.
7. **Durability check** — `file_count()` returns the number of live SSTable files on disk; used by the tests to prove flush creates a file and compaction shrinks the count.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Bloom filter** — per-SSTable membership sketch so `get` can skip files without touching the file. What false-positive rate is acceptable, and what does it cost in memory? (RocksDB: ~10 bits/key ≈ 1% FP.)
2. **Leveled compaction** — L0 overlapping ranges, L1+ non-overlapping, 10x size ratio per level. Where does write amplification come from? (Rewriting every level a key passes through.)
3. **Range scans** — `scan(prefix)` with a k-way heap merge over memtable + all SSTables. Why is a merged iterator harder than N point lookups?
4. **Recovery** — reopen the engine from the same directory: replay the manifest, and the memtable is *lost* (you didn't have a WAL — see `02-wal-toy`). This is the exact segue to the next lab.
