# Production notes — MVCC & isolation

## What you'd actually use

| Database | Mechanism | RR means | SERIALIZABLE means |
|---|---|---|---|
| PostgreSQL | heap tuples + `xmin`/`xmax`, vacuum | snapshot isolation | SSI (SIREAD locks, rw-cycle detection) |
| MySQL/InnoDB | undo logs (versions rebuilt from undo) + next-key locks at RR | MVCC + gap locks — suppresses most phantoms beyond the ANSI minimum | 2PL-ish, locking-based |
| Oracle | undo segments | — | snapshot isolation **under a different name** (write skew survives!) |
| SQL Server | row version store (opt-in `SNAPSHOT` / `RCSI`) | snapshot isolation | lock-based |

**The name trap:** Oracle's `SERIALIZABLE` is not serializable. Postgres's `REPEATABLE READ` is stronger than the ANSI minimum (full SI: phantoms and lost updates prevented). Verify the implementation behind the label, never the label.

## What the real ones add over yours

- **Vacuum/undo management** — your aborted versions pile up forever; Postgres's autovacuum reclaims dead tuples and must outrun write churn or the table bloats until it hits XID-wraparound protection and goes read-only.
- **Per-statement snapshot caching, horizon tracking** — real engines compute a global visibility horizon (oldest running snapshot) so they know which versions can never be seen again by anyone.
- **SSI with pivot detection** — yours aborts on a pairwise two-transaction cycle; real SSI tracks in+out rw-antidependencies through a *pivot* transaction across arbitrary graph sizes, with `max_prepared_transactions`-style tuning knobs.
- **Predicate-lock coarsening** — SIREAD locks on full ranges get page-granularity approximations; yours tracks exact key sets.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Invariant broke despite every tx looking correct, zero errors logged | Write skew under SI — disjoint writes jointly violated what neither violated alone | `SELECT ... FOR UPDATE` on the invariant-backing rows, or true SERIALIZABLE |
| Random `could not serialize access due to concurrent update` errors | FCW/SSI doing their job — this is correct behavior | Idempotent retry on the serialization error code only |
| Table bloat, queries slow down over months | Vacuum falling behind dead-tuple accumulation | Tune autovacuum per-table; monitor `pg_stat_user_tables` |
| Postgres suddenly refuses writes | XID wraparound protection | Freeze horizon must advance; this is a hard limit |
| Report returns different counts each run inside one transaction | RC fresh-snapshot-per-statement | Run the report at REPEATABLE READ/SERIALIZABLE |
| Balance went negative with a CHECK constraint present | Lost update or skew — CHECK is single-row, the anomaly was cross-row | Atomic conditional UPDATE or explicit locking |

## Cost & latency

MVCC's win is removing reader-writer blocking, not removing cost: every row carries version overhead, chains grow under hot-row contention until vacuum catches up, and SERIALIZABLE trades a higher retry rate for safety. Read Committed remains the right default for CRUD workloads without cross-row invariants — pay for SSI only where an invariant actually spans rows two transactions can touch concurrently.

## The 3 questions an interviewer asks after you describe this

1. *"Why doesn't SI catch write skew if it catches lost updates?"* — lost update needs both writers to touch the SAME row (FCW sees it); write skew's writes are disjoint, so the conflict lives in the read-sets, which SI never re-validates. That's why you need SIREADs/rw-cycles, i.e., SSI.
2. *"Where exactly does your snapshot come from in Read Committed?"* — fresh per statement, which is precisely why two SELECTs in one RC transaction can disagree (read skew). RR/SER pin one at BEGIN.
3. *"Your store has no locks — how do concurrent writers to one row resolve?"* — they don't block; first COMMITTER wins, the loser gets a serialization failure at its own commit and retries. Deterministic here because the driver orders steps explicitly; in a real DB the blocking window is between write and commit.
