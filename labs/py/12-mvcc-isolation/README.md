# Lab 12: MVCC & Isolation Levels From Scratch

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 2h · **XP:** 50
**Module:** `T17-mvcc-isolation`

**You will build:** a version-chained KV store where every write appends `{value, begin_ts, end_ts}` and every read resolves the newest version visible to a snapshot — plus all four isolation levels on top of one visibility function, and an SSI-lite rw-antidependency check that catches write skew without taking a single lock.

**You will be able to answer:** *"Walk me through xmin/xmax visibility — and why exactly does snapshot isolation prevent lost updates but not write skew?"*

## Setup

```bash
cd labs/py/12-mvcc-isolation
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

No threads, no sleeps, no wall clock. A deterministic driver executes explicit two-transaction interleavings (`("t1","w","k",v)`, `("t2","r","k")`, `("t1","commit")`), so every anomaly is reproducible bit-for-bit.

1. **`Version` chains** — each `write` appends `Version(value, begin_ts, end_ts=None)` to the key's chain; `begin_ts` is stamped at *write-start* (that's what makes uncommitted data visible to RU). `commit` stamps ONE `commit_ts` on all the tx's versions and closes the superseded predecessor's window with `end_ts = commit_ts`.
2. **Visibility** `_visible(v, tx, snap)` — own versions: always (read-your-writes). Creator aborted: invisible to *everyone* (even RU). `READ_UNCOMMITTED`: `begin_ts <= snap < end_ts`. RC/RR/SER: committed AND `commit_ts <= snap < end_ts`. Half-open windows, newest-version-first scan.
3. **Snapshot policy IS the ladder** — RU and RC take a fresh snapshot at the start of every statement; RR/SER pin one snapshot at `begin()` and never refresh.
4. **First-committer-wins** — at RR/SER `commit`, lose with `SerializationFailure('ww-conflict')` if anyone else committed a write to a key you wrote after your snapshot was taken. Uncommitted writers don't block you — they lose later against your commit timestamp. RC/RU: no checks (that's why lost updates happen there).
5. **SSI-lite** — SERIALIZABLE transactions record SIREADs (keys + range predicates read). Writes record rw-antidependency edges `(reader, writer)`; if two concurrent transactions have edges in BOTH directions, the detector aborts with `'ssi-cycle'`. Bookkeeping only — nobody ever blocks, `store.locks` stays empty by construction.
6. **Range reads** — `keys_between(tx, lo, hi)` for the phantom scenarios; range predicates feed SIREADs too.
7. **Driver + assertions** — `simulate(steps, levels, seed)` returns a result with `.reads(name,key)`, `.ranges(name)`, `.committed`, `.aborted`, `.final_state()`. Every anomaly test asserts BOTH the level where the anomaly appears AND the level(s) where it is prevented.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **GC/vacuum** — aborted versions currently stay in the chains forever; implement a vacuum pass and prove visibility results are identical before/after. *(Interview: "what are dead tuples costing you?")*
2. **Full 2-cycle SSI++** — replace the pairwise dangerous-structure check with a real rw-antidependency graph and three-transaction pivot detection (Cahill et al.). Construct the in+out pivot case that the pairwise check misses.
3. **Statement-level rollback points / savepoints** — partial rollbacks inside one transaction.
4. **XID wraparound** — make `tick()` wrap at 32 bits with a freeze horizon and explain precisely which visibility comparisons become ambiguous.

## Anomaly map (what the tests reproduce)

| Anomaly | Appears at | Prevented at | Test |
|---|---|---|---|
| Dirty read | READ_UNCOMMITTED | RC · RR · SER | `test_dirty_read_visible_at_ru_blocked_at_rc_rr_ser` |
| Non-repeatable read | RC (and RU) | RR · SER | `test_non_repeatable_read_occurs_at_rc_prevented_at_rr_and_ser` |
| Phantom read | RC (and RU) | RR · SER | `test_phantom_occurs_at_rc_prevented_by_snapshot_at_rr_and_ser` |
| Lost update | RU · RC | RR/SI (ww-conflict) · SER | `test_lost_update_at_ru_rc_prevented_by_first_committer_wins_at_si` |
| Write skew | RU · RC · **RR/SI** | SER only | `test_write_skew_allowed_under_plain_snapshot_isolation` / `..._aborted_under_serializable_ssi_lite` |
