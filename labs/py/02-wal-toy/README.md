# Lab 02: WAL + ARIES Recovery

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2h · **XP:** 50
**Module:** `T17-wal-recovery`

**You will build:** a write-ahead log with LSN-numbered records (`BEGIN`/`UPDATE`/`COMMIT`/`ABORT` with before/after images) appended to a real file under `tmp_path`, a `BufferManager` holding dirty pages, WAL-rule enforcement (log record durable *before* the page it describes), crash simulation (discard dirty buffers without flushing), then ARIES-style recovery: **analysis** (find active transactions), **redo** (reapply after-images, skipping LSN ≤ pageLSN), **undo** (reverse before-images of losers, writing CLRs so undo itself is crash-safe).

**You will be able to answer:** *"Walk me through what happens between 'the client got COMMIT ack' and 'the data page is on disk' — and what does recovery do after a crash?"*

## Setup

```bash
cd labs/py/02-wal-toy
python -m venv . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`WAL(path)`** — append-only log file, one JSON line per record. `append(txn_id, type, page=None, before=None, after=None)` assigns a monotonically increasing LSN (1, 2, 3...), writes the record durably (write + flush + fsync), returns the LSN. `read_all()` parses the file back into dicts. Each record: `{lsn, txn, type, page, before, after}`.
2. **`BufferManager`** — pages live in a dict: `page -> {value, page_lsn, dirty}`. `write(page, value, lsn)` records a dirty page whose `page_lsn` is the LSN of the newest change reflected in it. `flush_page(page)` simulates a durable page write (records the flush point). `flushed_lsn` tracks the highest LSN whose log record has been fsynced; the WAL rule helper `check_wal_rule(page)` asserts that the log record describing that page's newest change was flushed (LSN ≤ `flushed_lsn`) **before** the page flush happened — a violation helper `wal_violation(page)` must return True exactly when `page_lsn > flushed_lsn` at flush time.
3. **`Transaction` / engine API** — `begin()`, `update(page, after)` (captures `before` automatically), `commit()` appends COMMIT and returns, `abort()` appends ABORT. Updates apply to the buffer pool, not directly to "disk". `pages()` exposes the buffer contents for assertions (values + page_lsns).
4. **Crash** — `crash()` throws away every dirty buffer without flushing any page to disk (real crashes lose volatile memory, not the fsynced log). The WAL file survives.
5. **`recover(wal, disk_pages)` → recovered pages** — the ARIES three-pass:
   - **Analysis**: one forward scan — transactions with a BEGIN but no COMMIT/ABORT are *losers* (active at crash).
   - **Redo**: "repeat history" — replay the after-image of **every** UPDATE in LSN order (committed *and* uncommitted — you can't know yet), skipping records where `lsn <= page_lsn` of that page (idempotency), starting from the disk pages.
   - **Undo**: roll back each loser in **reverse LSN order**, restoring before-images, appending a **CLR** (compensation log record: `type="CLR", undo_of=<lsn>`) so a crash during undo resumes instead of restarting.
6. **Idempotency** — running `recover` twice on the same inputs yields the identical page state (pageLSN guards make redo a no-op the second time; the second recovery's analysis finds no losers because the CLRs plus ABORT records make the losers complete).

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Checkpoints** — a `CHECKPOINT` record that snapshots active txns + dirty page table so analysis starts there instead of the log head. What does it bound? (Recovery time, not disk space.)
2. **Fuzzy checkpoint** — checkpoint without stopping the world. Why is it safe? (Redo's LSN-guarded idempotency tolerates an inconsistent snapshot.)
3. **Group commit** — batch N transactions' appends into one fsync. What's the throughput/latency tradeoff at N=1 vs N=50?
4. **Torn pages** — flip a bit in a disk page mid-"write", then recover with `full_page_writes` on/off. What does the on-version give you?
