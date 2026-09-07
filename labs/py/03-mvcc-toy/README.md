# Lab 03: A Toy MVCC Engine — Isolation Levels & the Anomalies

**Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 3h · **XP:** 50
**Module:** `T17-mvcc-isolation`

**You will build:** a toy MVCC engine with version chains `[(txn_id, value, committed, begin_ts, end_ts)]`, a `TxnManager` assigning ids and committing atomically with commit timestamps, visibility rules (a version is visible if its `begin_ts <=` snapshot and it wasn't ended before the snapshot), and a session API exposing `READ_UNCOMMITTED`, `READ_COMMITTED` (fresh snapshot per statement), `REPEATABLE_READ` (snapshot at txn start), and `SERIALIZABLE` (RR + first-committer-wins write conflict → abort).

**You will be able to answer:** *"Your on-call roster ended with zero doctors despite every transaction looking correct — walk me through exactly why, and what actually fixes it."*

## Setup

```bash
cd labs/py/03-mvcc-toy
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`MVCCStore`** — keys map to version chains: `list[Version(txn_id, value, committed, begin_ts, end_ts)]`. A write appends a version with `begin_ts` set at *commit* time (until then `committed=False`); an update by another txn sets the previous live version's `end_ts`. `TxnManager` assigns monotonic txn ids and a global commit timestamp counter; `commit(txn)` stamps all the txn's pending versions with one `begin_ts` atomically and marks them committed.
2. **Visibility** — `read(key, snapshot)` walks the chain and returns the newest version whose `begin_ts <= snapshot` **and** (`committed` at snapshot-time — i.e. the version's txn had committed with `begin_ts <= snapshot`) **and** (`end_ts` is unset or `end_ts > snapshot`). Uncommitted versions (`committed=False`) are visible **only** to their own writer and to `READ_UNCOMMITTED`.
3. **`Session(store, level)`** — the API the tests drive: `begin()`, `read(key)`, `write(key, value)`, `commit()`, `abort()`. Isolation behaviour comes from *when the snapshot is taken* and *what writes are allowed*:
   - `READ_UNCOMMITTED` — reads may see uncommitted versions (dirty reads allowed).
   - `READ_COMMITTED` — fresh snapshot **per statement**; reads see only committed data. Non-repeatable reads happen (that's the point).
   - `REPEATABLE_READ` — one snapshot at `begin()`, reused for every statement (no non-repeatable reads). Writes use **first-committer-wins**: at commit, if another txn committed a version of a key you wrote *after your snapshot*, raise `SerializationFailure` (lost update prevented).
   - `SERIALIZABLE` — REPEATABLE_READ **plus** first-committer-wins is not enough (write skew!), so additionally: track reads; at commit, if another txn **committed a write to any key you read** after your snapshot, abort with `SerializationFailure`. This is the SSI-flavoured check that catches the doctors cycle.
4. **Snapshots** — a snapshot is a commit timestamp, taken as: RU/RC → at each `read()`; RR/SER → at `begin()`.
5. **`doctors_scenario(...)` helper** (in the *tests*, not the engine) — two sessions each read `count(on_call)`, both see 2, both write their own row off-call, both commit. At RR: both commit, final on-call count 0 (write skew wins). At SERIALIZABLE: one of the two commits, the other raises `SerializationFailure` — invariant survives with 1 on call.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **True SSI rw-antidependency graph** — your SERIALIZABLE check is read-set vs concurrent commits (a coarse approximation that can abort false positives). Real SSI tracks *which* version each read saw and flags only true dangerous structures (two adjacent rw-antidependencies through a pivot). When would your version abort unnecessarily?
2. **Lost update at READ_COMMITTED** — prove RC allows two read-modify-writes to clobber each other, then fix with an explicit row lock (`SELECT ... FOR UPDATE` equivalent: a `lock(key)` API). That's the production fix.
3. **Phantom reads** — a `scan(predicate)` API; show a predicate's row set changes mid-txn at RC (phantom) but not at RR. Why does the ANSI name "REPEATABLE READ" not promise this?
4. **Deadlock in a locking engine** — build the 2PL alternative (shared locks on read, exclusive on write, held to commit) and show T1/T2 deadlocking on (a,b) vs (b,a). This is why Postgres chose MVCC+SSI over 2PL.
