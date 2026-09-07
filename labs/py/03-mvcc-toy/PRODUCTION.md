# Production notes — MVCC & isolation

## What you'd actually use

| Your piece | Real thing | What it adds over yours |
|---|---|---|
| Version chain `(txn_id, value, committed, begin_ts, end_ts)` | Postgres heap tuples with `xmin`/`xmax` (32-bit XIDs) | chain links are implicit via xmin/xmax, no list to walk; CLOG commits in batches; freeze vacuum beats XID wraparound |
| Visibility `begin_ts <= snapshot && end_ts > snapshot` | Postgres snapshot = (xmin horizon, in-progress XID list, xmax) — `HeapTupleSatisfiesMVCC` | handles the exact "committed but *after* my snapshot" case your `committed` flag approximates |
| Snapshot per statement (RC) / per txn (RR) | exactly Postgres: RC re-snapshots per statement, RR/SER take one at `BEGIN` | — your model matches |
| First-committer-wins | Postgres RR "could not serialize access due to concurrent update" | the real check is per-tuple against the snapshot, message = SQLSTATE 40001, retry expected |
| SERIALIZABLE = RR + read-set conflict check | Postgres SSI (Cahill/Spears, 9.1): SIREAD predicate locks + rw-antidependency dangerous-structure detection | never blocks readers; aborts only on true 2-rw-edge cycles through a pivot txn — fewer false aborts than your coarse read-set check |
| `abort()` | rollback — Postgres keeps the dead tuples for other snapshots, vacuum reclaims later | no undo log needed (versions ARE the undo); Oracle/InnoDB instead reconstruct old versions from undo logs |

The systems to name in interviews: **Postgres** (MVCC via xmin/xmax in the heap; RR = snapshot isolation; SERIALIZABLE = SSI), **MySQL/InnoDB** (MVCC via undo logs + next-key gap locking at RR — its RR prevents most phantoms, beyond the ANSI minimum), **Oracle** (undo segments; its "SERIALIZABLE" is actually snapshot isolation — write skew survives the name; the classic gotcha), **SQL Server** (opt-in SNAPSHOT isolation), **CockroachDB/YugabyteDB** (serializable-by-default, retry-oriented philosophy).

## What the real ones add over yours

- **Reads never block, but writes still conflict — per version, cheaply.** Your conflict scan is O(chain length); Postgres checks xmax on the one current tuple and consults the in-progress list. This is why Postgres RR conflict detection is O(1) in practice.
- **Real SSI has no false positives on non-conflicting workloads.** Your SERIALIZABLE check ("did anyone commit a write to *any* key I read since my snapshot?") aborts conservatively; SSI's rw-edges fire only when a genuine dangerous structure forms. Interviewers accept the approximation if you *name* it as one.
- **Vacuum.** Every update leaves a dead version; MVCC without garbage collection bloats tables and indexes (the #1 Postgres operational failure mode — see the failure table).
- **XID wraparound.** 32-bit XIDs wrap at ~4B txns; freeze vacuum rewrites old tuples' xmin to FrozenXID. Under-vacuumed clusters hit forced read-only mode — the dramatic production story.
- **Predicate/range conflicts.** Your read-set is exact keys; real engines must also catch inserts into a scanned *range* (phantoms). SIREAD locks cover ranges and pages, growing to coarser locks when memory-bound.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Invariant violated, no error logged anywhere | write skew at RC/RR (the doctors case) | `SELECT ... FOR UPDATE` on the rows backing the invariant, or SERIALIZABLE + retry |
| Balance negative despite per-txn checks | lost update at RC (read-modify-write race) | FOR UPDATE, atomic `UPDATE ... WHERE balance >= x`, or RR's first-committer-wins + retry |
| Random 40001 serialization failures under load | expected: first-committer-wins / SSI aborts | retry idempotently on SQLSTATE 40001 — this is the isolation level working, not a bug |
| Table bloat, scans slow over months | dead versions not vacuumed (autovacuum behind) | tune autovacuum per table; monitor `pg_stat_user_tables.n_dead_tup` |
| Long-running report pins xmin horizon | old snapshot blocks vacuum reclaiming *everything* after it | cancel/timeout long txns (`idle_in_transaction_session_timeout`, `old_snapshot_threshold`) |
| Write-only SERIALIZABLE txns abort far too often | coarse conflict detection (your approximation!) or genuine hot-key cycles | shorten the txn, move invariant checks into a single atomic statement, or lock the specific rows |

## The 3 questions an interviewer asks after you describe this

1. *"Why does snapshot isolation stop lost updates but not write skew?"* — lost update is a same-row write-write: first-committer-wins catches it at commit. Write skew writes *different rows*: no write-write conflict exists, so SI's only conflict detector never fires — the invariant dies in the gap between the two disjoint writes.
2. *"Why not just run SERIALIZABLE everywhere?"* — real overhead: SIREAD bookkeeping on every read plus a higher abort/retry rate under contention; teams instead pay for targeted locking on the few invariants that matter. Blanket SERIALIZABLE is the classic overcorrection.
3. *"Your engine keeps old versions forever. What happens?"* — unbounded growth; reads get slower scanning past dead versions; and in Postgres specifically, the oldest live snapshot pins the vacuum horizon so *everything* after it is un-reclaimable. MVCC always needs a vacuum story.
