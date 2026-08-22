# MVCC vs Locking, Isolation Levels, Every Anomaly, Write Skew

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 3h · **Prereqs:** none
> **Module id:** `T17-mvcc-isolation` · **Tags:** sprint, internals, critical
> **Lab:** `labs/py/03-mvcc-toy/`

## The 30-second version

MVCC lets readers never block writers and writers never block readers by keeping multiple versions of each row and giving every transaction a consistent snapshot to read from, instead of the locking alternative (2PL) where reads take shared locks and writes take exclusive locks that actually block each other. Postgres implements this with two hidden columns per row, `xmin` and `xmax`, and a visibility rule: a row version is visible to your snapshot if it was created by a transaction that committed before your snapshot and not yet deleted by one. The catch is that snapshot isolation — what most people mean when they loosely say "MVCC" — prevents dirty reads, dirty writes, and read skew, but it does NOT prevent write skew, because two transactions can each read a consistent-but-stale snapshot, make a decision based on it, and write to different rows in a way that jointly violates an invariant neither transaction's individual write violated on its own. True serializable isolation costs more (Postgres does it via SSI, predicate locks that detect dangerous read-write dependency cycles) and is required whenever your invariant spans rows that two concurrent transactions might each read-then-write independently.

## Why this gets asked

Because "read committed is the Postgres default" is trivia anyone can look up, but knowing *why* a business invariant silently broke in production despite every individual transaction looking correct is the actual signal. The interviewer has watched an on-call rotation end up with zero doctors on call, or an account go negative despite a `CHECK (balance >= 0)` on every single transaction, and wants to know if you can name write skew specifically, explain why snapshot isolation lets it through, and say what actually fixes it (not "just use serializable" without knowing the cost).

---

## Lineage: past → present → future

**What came before.** Early relational databases used **two-phase locking (2PL)** as the only mechanism for serializability: a transaction acquires a shared lock before reading a row and an exclusive lock before writing one, holds every lock until commit (the "shrinking phase" only begins at commit, hence "two-phase"), and any conflicting lock request blocks the requester until the holder releases. This gives correct serializable behavior but at a direct throughput cost — readers block writers and writers block readers on every contended row, and long-running read transactions can starve writers for their whole duration. The pain that killed pure locking as the default: OLTP workloads with mixed read/write traffic on hot rows saw throughput collapse under contention, and the correctness guarantee (true serializability) was frequently more than the application actually needed, paid for on every single transaction whether or not a conflict was possible.

**Where it stands now.** MVCC (pioneered in production by InterBase in the 1980s and later Oracle, then formalized broadly) is now the default concurrency model in Postgres, Oracle, MySQL/InnoDB, and SQL Server (as an optional mode). The current consensus: **snapshot isolation** (what Postgres calls REPEATABLE READ and Oracle calls SERIALIZABLE, confusingly) is the right default for the vast majority of OLTP workloads because it eliminates dirty reads, dirty writes, and read skew at low cost with no reader-writer blocking, but it is *not* true serializability, and write skew is the specific, well-documented gap. The live disagreement is over how much this actually matters in practice: many teams run at snapshot isolation for years without hitting a write-skew bug because the application rarely has two concurrent transactions checking-then-violating the same cross-row invariant; other teams (banking, scheduling, inventory-with-hard-floors) hit it routinely and either add explicit locking (`SELECT ... FOR UPDATE`) at the specific contended read, or pay for full serializable (SSI in Postgres) globally. What's actually deployed at scale: most systems run READ COMMITTED or snapshot-isolation REPEATABLE READ as the default and reach for `FOR UPDATE`/`FOR SHARE` or application-level compare-and-swap on the specific few invariants that matter, rather than paying SSI's overhead everywhere.

**Where it's heading.** Postgres's SSI (Cahill, Röhm, Fekete's 2008 algorithm, shipped in Postgres 9.1, 2011) remains the reference implementation of optimistic serializable isolation without full locking, and distributed databases (CockroachDB, YugabyteDB) have adopted the same serializable-by-default philosophy at the cluster level, betting that the retry cost from serialization failures is more predictable and easier to reason about than silent anomalies. Confidence: this is a live, real design split — CockroachDB defaults to SERIALIZABLE precisely because the anomaly-hunting cost of a weaker default in a distributed system is judged worse than periodic transaction retries. More speculative: increasing tooling to detect write-skew-shaped bugs statically (analyzing which invariants span which tables and flagging read-then-write patterns that don't take a lock or run under serializable) is an active research area but not yet a standard part of most ORMs or migration tooling.

---

## Mental model

```
LOCKING (2PL)                              MVCC (snapshot isolation)

  T1: SELECT ... (shared lock)              T1 starts, gets snapshot @ t0
  T2: UPDATE ...  ──▶ BLOCKS on T1's         T2 starts, gets snapshot @ t1
       shared lock until T1 commits          T2 UPDATEs row -> new version
                                              (xmin=T2) committed
  readers block writers,                     T1 still reads the OLD version
  writers block readers                      (xmin <= t0 snapshot) -- NO BLOCK
  and each other on the                      T1 and T2 never waited on each
  same row                                   other at all


ROW VERSION CHAIN (Postgres heap tuple, simplified):

  ┌─────────────────────────┐   ┌─────────────────────────┐
  │ xmin=101  xmax=205      │──▶│ xmin=205  xmax=0 (live)  │
  │ (created by T101,       │   │ (created by T205,        │
  │  superseded by T205)    │   │  not yet superseded)      │
  │ balance = 500           │   │ balance = 300             │
  └─────────────────────────┘   └─────────────────────────┘
        old version                   current version

  VISIBILITY RULE for a transaction with snapshot S:
  a tuple version is visible to S if:
    xmin committed AND xmin's commit is before S was taken
    AND (xmax = 0 OR xmax's transaction has NOT committed before S)
  -> S sees exactly the version that was live at the moment S was taken,
     regardless of what commits after.
```

---

## How it actually works

### MVCC mechanics: version chains, visibility, xmin/xmax

Every Postgres heap tuple carries two hidden system columns: **`xmin`** (the transaction ID that inserted this version) and **`xmax`** (the transaction ID that deleted or superseded it, `0` if still live). An `UPDATE` in Postgres never modifies a row in place — it writes a brand-new tuple with a new `xmin` and sets the old tuple's `xmax` to the updating transaction's ID, chaining old version → new version. A `DELETE` just sets `xmax` on the existing tuple; nothing is physically removed until vacuum reclaims it.

A transaction's **snapshot** is a small data structure captured at a defined moment: the current global `xid` counter value, plus the list of transaction IDs that were still in-progress (uncommitted) at that instant. The **visibility rule** for whether a given tuple version is visible to a snapshot: `xmin`'s transaction must have committed, and that commit must have happened before the snapshot was taken (i.e., `xmin` is not in the snapshot's in-progress list and is numerically less than or equal to what the snapshot considers "done"); AND either `xmax = 0` (never deleted) or `xmax`'s transaction has not committed as of the snapshot. This rule is applied per-row during a scan, which is why MVCC reads never need a lock: a reader simply skips versions that aren't visible to its snapshot and never contends with a writer creating a newer version.

**When the snapshot is taken determines the isolation level.** For READ COMMITTED, Postgres takes a fresh snapshot at the start of *every statement* within the transaction, so each statement sees the latest committed data as of that statement, not as of transaction start — this is why two `SELECT`s in the same READ COMMITTED transaction can see different data (read skew is possible). For REPEATABLE READ and SERIALIZABLE, one snapshot is taken at the start of the transaction and reused for every statement in it.

XIDs are 32-bit integers, so they wrap around roughly every 4 billion transactions; Postgres runs a periodic "freeze" vacuum that rewrites old tuples' `xmin` to a special `FrozenXID` sentinel to avoid ambiguity once the counter wraps — this is why a table that never gets vacuumed for a very long time under sustained write load is a real operational risk (`xidwraparound` protection will eventually force Postgres into read-only mode to prevent corruption).

### 2PL as the alternative

Two-phase locking is the direct, non-MVCC path to serializability: every read acquires a shared lock, every write acquires an exclusive lock, all locks are held until commit, and lock acquisition blocks on conflict rather than proceeding against an old snapshot. It guarantees serializability without any of the anomalies below, but readers and writers block each other on every contended row, and to prevent phantoms (see below) the locks must actually be **predicate locks** — locking the *range/condition* a query scanned, not just the rows it happened to return, otherwise a new row inserted into that range slips through unnoticed. MySQL/InnoDB and SQL Server both implement their SERIALIZABLE level via variants of 2PL with range/gap locking; Postgres instead implements SERIALIZABLE via SSI (below), which achieves the same guarantee optimistically, without blocking readers.

### Every isolation level and every anomaly, with a two-transaction repro

The anomalies, from most to least severe:

| Anomaly | Definition | Two-transaction repro |
|---|---|---|
| **Dirty read** | T1 reads a row T2 has written but not yet committed | T2: `UPDATE accounts SET balance=balance-100 WHERE id=1;` (uncommitted). T1: `SELECT balance FROM accounts WHERE id=1;` sees the debited balance. T2 then `ROLLBACK`. T1 acted on a value that never existed. |
| **Dirty write** | T1 overwrites a row T2 has written but not yet committed | T2: `UPDATE orders SET status='shipped' WHERE id=1;` (uncommitted). T1: `UPDATE orders SET status='cancelled' WHERE id=1;` also succeeds under no isolation. Whichever commits last wins, silently discarding the other's intended state transition with no conflict ever surfaced. |
| **Read skew / non-repeatable read** | T1 reads the same row twice and gets two different committed values because T2 committed a change in between | T1: `SELECT balance FROM accounts WHERE id=1;` → 500. T2: `UPDATE accounts SET balance=400 WHERE id=1; COMMIT;`. T1: `SELECT balance FROM accounts WHERE id=1;` again → 400, same transaction, different answer. |
| **Phantom read** | T1 runs a predicate-based query twice and a new row T2 inserted/deleted now matches (or stops matching) the predicate | T1: `SELECT count(*) FROM orders WHERE status='pending';` → 5. T2: `INSERT INTO orders (status) VALUES ('pending'); COMMIT;`. T1: re-runs the same count → 6. The set of rows matching the predicate changed mid-transaction. |
| **Lost update** | T1 and T2 both read the same row, both compute a new value based on that read, and one write clobbers the other with no conflict detected | T1: `SELECT balance FROM accounts WHERE id=1;` → 500, computes 500+100=600. T2 (concurrently): `SELECT balance ...` → 500, computes 500+50=550. T1: `UPDATE ... SET balance=600;` commits. T2: `UPDATE ... SET balance=550;` commits. Final balance 550 — T1's +100 is gone, even though both deposits should have applied. |
| **Write skew** | T1 and T2 each read an overlapping set of rows, each independently confirms an invariant holds, and each writes to a *different* row such that the invariant is now violated even though neither individual write conflicted | The doctors-on-call example below. |

**Write skew, worked in full (the classic on-call example):** invariant — at least one doctor must be on call at all times. Alice and Bob are both currently on call.

```sql
-- T1 (Alice going off call)                    -- T2 (Bob going off call)
BEGIN; -- snapshot taken, both see 2 on-call
SELECT count(*) FROM doctors                    BEGIN;
  WHERE on_call = true;    -- returns 2          SELECT count(*) FROM doctors
-- Alice's app logic: "2 on call, safe             WHERE on_call = true; -- returns 2
--  for me to go off call"                       -- Bob's app logic: "2 on call, safe
                                                  --  for me to go off call"
UPDATE doctors SET on_call=false
  WHERE name='Alice';
COMMIT;                                          UPDATE doctors SET on_call=false
                                                    WHERE name='Bob';
                                                  COMMIT;

-- Final state: on_call count = 0. Invariant violated.
-- Neither transaction's WRITE conflicted with the other (different rows,
-- Alice's row vs Bob's row) so snapshot isolation detects nothing wrong.
```

This is the anomaly that survives snapshot isolation specifically because the *read* that grounds each transaction's decision (the count of on-call doctors) is never re-validated against what the *other* transaction is about to write — SI only guards against two transactions writing the *same* row, not against one transaction's write invalidating the premise another transaction's decision was based on.

### Snapshot isolation vs true serializable, and why write skew survives SI

**Snapshot isolation (SI)** gives every transaction a single consistent snapshot of the database as of its start, and detects conflicts only via **first-committer-wins** on rows that are actually written by both transactions (Postgres calls this a serialization failure — `ERROR: could not serialize access due to concurrent update` — and the losing transaction must retry). This is sufficient to prevent dirty reads, dirty writes, and read skew, because those anomalies all involve a transaction observing another's write; a fixed snapshot simply never sees anything committed after it started. It is NOT sufficient to prevent write skew, because write skew involves no row being written by both transactions — the invariant violation lives in the *relationship between* two disjoint writes, and SI's conflict detection mechanism has no way to see that relationship; it only checks "did anyone else write the exact row I'm writing."

**True serializability** additionally guarantees that the outcome of any concurrent execution is equivalent to *some* serial (one-at-a-time) execution of the same transactions — which by definition rules out write skew, because in any serial ordering, the second doctor to run their check would see the first doctor already off call and abort the "safe to go off call" decision. Achieving this either costs real locking overhead (2PL with predicate locks) or requires tracking a more abstract kind of conflict than "same row" — which is exactly what SSI does.

### SSI in Postgres

**Serializable Snapshot Isolation** (Cahill/Röhm/Fekete, shipped Postgres 9.1) starts from ordinary snapshot isolation (so reads still never block) and adds runtime detection of a specific structure that provably indicates a serialization anomaly: a **dangerous structure**, defined as a cycle of two adjacent **rw-antidependencies** among three (or more) concurrent transactions. An rw-antidependency exists between T1 and T2 when T1 reads a version of a row that T2 later overwrites — T1's read "conflicts" with T2's write not because they touched the same version, but because T1's read would have seen something different had T2's write happened first. Postgres tracks this by having transactions running at SERIALIZABLE take special **SIREAD locks** on rows/predicates they read; these locks never block anything (they're bookkeeping, not real locks) but a subsequent write to that data is flagged as forming an rw-antidependency edge. If Postgres detects that these edges form a cycle back to where they started (T1 → T2 → T1, a "pivot" transaction in the middle with both an incoming and outgoing rw-antidependency to transactions that ran concurrently with it), it aborts one of the transactions with a serialization failure, and the application must retry. The write-skew example above is exactly this shape: Alice's transaction reads Bob's row (before Bob's write) and Bob's transaction reads Alice's row (before Alice's write) — a cycle — so under `SERIALIZABLE` in Postgres, one of the two would be aborted and forced to retry rather than silently letting both succeed. Because SIREAD locks don't block, SSI's overhead versus SI is modest (bookkeeping and a somewhat higher retry rate under contention) and substantially cheaper than 2PL for read-heavy workloads, since Postgres never blocks a reader to achieve it.

### Isolation level → anomalies permitted → real database defaults

| Isolation level | Dirty read | Dirty write | Read skew | Phantom read | Lost update | Write skew | Real default in |
|---|---|---|---|---|---|---|---|
| **Read Uncommitted** | Possible | Prevented* | Possible | Possible | Possible | Possible | MySQL/InnoDB (available, rarely used) — Postgres maps this to Read Committed behavior; Oracle doesn't offer it |
| **Read Committed** | Prevented | Prevented | Possible | Possible | Possible | Possible | **Postgres, Oracle, SQL Server default** |
| **Repeatable Read** (lock-based, ANSI definition) | Prevented | Prevented | Prevented | Possible | Prevented (via locks) | Possible | **MySQL/InnoDB default** (InnoDB's REPEATABLE READ also uses gap locks, which actually prevent most phantoms in practice, going beyond the ANSI minimum) |
| **Snapshot Isolation** (what Postgres calls REPEATABLE READ) | Prevented | Prevented | Prevented | Prevented (via snapshot) | Prevented (first-committer-wins) | **Possible** | Postgres `REPEATABLE READ` |
| **Serializable** | Prevented | Prevented | Prevented | Prevented | Prevented | Prevented | Postgres `SERIALIZABLE` (via SSI), MySQL/Oracle/SQL Server `SERIALIZABLE` (via locking/2PL variants) |

*Dirty writes (uncommitted-write-over-uncommitted-write) are prevented by ordinary row-level write locks even at Read Uncommitted in every mainstream database; "Read Uncommitted" only affects what a transaction can *read*, not whether concurrent writes to the same row are serialized.

Note the ANSI SQL standard's own definitions (from the 1992 standard, critiqued in the well-known Berenson et al. 1995 paper "A Critique of ANSI SQL Isolation Levels") are ambiguous enough about phantom prevention that Postgres's actual `REPEATABLE READ` (true snapshot isolation) and the ANSI-minimum `REPEATABLE READ` are not the same guarantee — this mismatch between the standard's name and what a given database actually implements under that name is itself a frequent interview trap.

---

## Build it from scratch

A minimal toy MVCC store demonstrating version chains, xmin/xmax-style visibility, and first-committer-wins conflict detection — the shape of what an interviewer may ask you to reason through.

```python
# untested sketch
from dataclasses import dataclass, field

@dataclass
class Version:
    xmin: int
    xmax: int | None   # None = still live
    value: object

class MVCCStore:
    def __init__(self):
        self.versions: dict[str, list[Version]] = {}   # key -> version chain
        self.committed: set[int] = set()
        self.next_xid = 1

    def begin(self) -> int:
        xid = self.next_xid
        self.next_xid += 1
        return xid

    def snapshot(self, xid: int) -> set[int]:
        """XIDs considered 'done' (committed) as of this snapshot."""
        return set(self.committed)   # simplified: real Postgres also tracks in-progress list

    def read(self, key: str, xid: int, snap: set[int]):
        for v in reversed(self.versions.get(key, [])):
            xmin_visible = v.xmin in snap
            xmax_visible = v.xmax is None or v.xmax not in snap
            if xmin_visible and xmax_visible:
                return v.value
        return None

    def write(self, key: str, xid: int, new_value, snap: set[int]):
        chain = self.versions.setdefault(key, [])
        # first-committer-wins check: has anyone committed a write to this key
        # since MY snapshot was taken?
        for v in chain:
            if v.xmin not in snap and v.xmin in self.committed:
                raise SerializationFailure(f"key {key} written concurrently, retry xid={xid}")
        if chain:
            chain[-1].xmax = xid   # supersede the current live version
        chain.append(Version(xmin=xid, xmax=None, value=new_value))

    def commit(self, xid: int):
        self.committed.add(xid)

class SerializationFailure(Exception): ...
```

This deliberately omits SSI's rw-antidependency cycle tracking (that requires graph bookkeeping across all concurrently-serializable transactions, not just per-key state) — it demonstrates ordinary snapshot isolation's write-write conflict detection only, which is enough to show *why* write skew (a conflict between disjoint keys) sails through undetected. Full version with an SSI-style rw-antidependency tracker that catches the doctors-on-call cycle: **`labs/py/03-mvcc-toy/`**.

---

## How it's done in production

**Postgres** — MVCC via xmin/xmax heap tuples as described above; `REPEATABLE READ` = snapshot isolation; `SERIALIZABLE` = SSI. Vacuum reclaims dead tuple versions and prevents XID wraparound; under-vacuumed high-write tables are a common source of bloat and eventual forced read-only mode. **MySQL/InnoDB** — MVCC via undo logs (old versions reconstructed from undo, not kept as separate heap tuples) plus next-key locking (record + gap locks) at `REPEATABLE READ`, which is why InnoDB's `REPEATABLE READ` actually prevents most phantoms in practice despite the ANSI standard only requiring it at `SERIALIZABLE` — a frequently-misunderstood implementation detail. **Oracle** — MVCC via undo segments (very similar to InnoDB's approach); Oracle's `SERIALIZABLE` is actually snapshot isolation under a different name (it does not implement SSI or 2PL-based true serializability), so Oracle `SERIALIZABLE` transactions can still suffer write skew — a real, well-known gotcha. **SQL Server** — offers both a lock-based path (default `READ COMMITTED` with row/page/table locks) and an MVCC-style `SNAPSHOT`/`READ COMMITTED SNAPSHOT` isolation level as an opt-in.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Account balance goes negative despite a `CHECK (balance >= 0)` constraint and every individual UPDATE looking correct | Lost update or write skew between two concurrent balance-modifying transactions under Read Committed/Snapshot Isolation | `SELECT ... FOR UPDATE` on the row before computing the new value, or run the transaction at `SERIALIZABLE` and handle retries |
| On-call/roster invariant violated with no errors logged anywhere | Classic write skew — two transactions each read a shared predicate, decide independently, write to different rows | `SELECT ... FOR UPDATE` on the rows the invariant depends on (materializes a real conflict), or `SERIALIZABLE` isolation |
| Application randomly gets `ERROR: could not serialize access due to concurrent update` under load | Expected, correct behavior of snapshot isolation's first-committer-wins conflict detection, or SSI's rw-antidependency abort | Retry the transaction (idempotently) on this specific error code; this is not a bug, it's the isolation level doing its job |
| A report query returns different row counts each time it re-runs the same predicate inside one transaction | Phantom reads under Read Committed (fresh snapshot per statement) | Run the report inside a single `REPEATABLE READ`/`SERIALIZABLE` transaction to get one consistent snapshot for the whole transaction |
| Postgres table performance degrades over months, disk usage balloons | Insufficient vacuuming leaving dead tuple versions (old xmax'd rows) unreclaimed | Tune autovacuum aggressiveness for high-churn tables; monitor `pg_stat_user_tables` dead tuple counts |
| Postgres suddenly refuses all writes with a wraparound warning/forced shutdown risk | XID counter approaching the 32-bit wraparound limit due to autovacuum freeze falling behind | Ensure autovacuum freeze runs; this is a hard operational limit, not a tuning nice-to-have |
| Oracle `SERIALIZABLE` transaction still exhibits write skew | Oracle's `SERIALIZABLE` is snapshot isolation, not true serializability (no SSI, no 2PL predicate locks at that level) | Explicit row locking (`SELECT ... FOR UPDATE`) on the specific invariant-relevant rows; don't assume the isolation level name matches the ANSI guarantee |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `SERIALIZABLE`/SSI everywhere by default.** It carries real overhead (SIREAD lock bookkeeping, a genuinely higher transaction retry rate under contention) that most of your transactions don't need; blanket-applying it is a common overcorrection once someone learns about write skew.
- **Don't assume `SELECT ... FOR UPDATE` is free.** It converts a non-blocking MVCC read into a real row lock that other writers will now block on — appropriate for the specific few rows backing a hard invariant, wrong to apply broadly as a reflex "just to be safe."
- **Don't trust the isolation level's name across databases.** Oracle's `SERIALIZABLE` is snapshot isolation and still permits write skew; MySQL's `REPEATABLE READ` (via gap locks) prevents more phantoms than the ANSI minimum requires. Verify what your specific database actually implements, don't infer from the SQL standard's name alone.
- **Don't add SSI/serializable retries without idempotent transaction logic.** A transaction that gets aborted with a serialization failure must be safely retryable — if it has non-transactional side effects (an external API call inside the transaction boundary), a retry-on-conflict strategy will re-trigger that side effect.
- **For a workload with no cross-row invariants that two concurrent transactions could jointly violate** (most CRUD apps touching independent rows), Read Committed is the right, cheap default — don't pay for stronger guarantees the application logic never actually needs.
- **Distributed databases (CockroachDB, YugabyteDB) defaulting to SERIALIZABLE globally is a deliberate, debatable tradeoff**, not a universal best practice — it trades a higher baseline retry rate for eliminating an entire class of anomaly-hunting; whether that's right for you depends on whether your team can tolerate transaction retries as a normal, expected code path versus wanting to reason about weaker guarantees explicitly per-transaction.

---

## Interview questions

### Q1 — What is MVCC and why doesn't it block readers against writers?
**Testing:** baseline mechanics.
**Answer:** MVCC keeps multiple versions of each row; a transaction reads the version that was live as of its own snapshot rather than taking a lock on the current version. Since a reader never needs to wait for a writer to finish (it just reads an older, already-committed version instead of the newest one), and a writer never needs to wait for a reader (readers don't hold locks), reads and writes proceed concurrently with no blocking between them.
**Follow-up trap:** *"So MVCC never blocks anything?"* — writers still conflict with other writers on the same row (write-write conflicts are detected and one loser is aborted/retried), and explicit row locks (`SELECT ... FOR UPDATE`) still block. MVCC specifically removes reader-writer blocking, not all blocking.

### Q2 — Explain Postgres's xmin/xmax visibility rule precisely.
**Answer:** Every tuple carries `xmin` (creating transaction) and `xmax` (deleting/superseding transaction, or unset if live). A version is visible to a snapshot if `xmin`'s transaction committed before the snapshot was taken, and either `xmax` is unset or `xmax`'s transaction has not committed as of the snapshot. This is checked per-tuple during a scan.
**Follow-up trap:** *"When is the snapshot taken for Read Committed vs Repeatable Read?"* — Read Committed takes a fresh snapshot at the start of every statement (so two SELECTs in one transaction can see different committed data — read skew is possible); Repeatable Read/Serializable take one snapshot at transaction start and reuse it for the whole transaction.

### Q3 — Name every anomaly the ANSI/extended taxonomy covers and give a one-line definition of each.
**Testing:** completeness, not just "the big three."
**Answer:** Dirty read (reading another transaction's uncommitted write), dirty write (overwriting another transaction's uncommitted write), read skew/non-repeatable read (same row read twice in one transaction returns different committed values), phantom read (a predicate-based query's result set changes because rows were inserted/deleted mid-transaction), lost update (two transactions read-modify-write the same row and one write silently clobbers the other), write skew (two transactions each read overlapping data, each independently decides an invariant is safe, and their disjoint writes jointly violate it).
**Follow-up trap:** *"Which of these does plain snapshot isolation NOT prevent?"* — write skew, specifically. It prevents all the others because they all involve one transaction observing or overwriting another's write to the *same* data; write skew's writes are to different rows entirely.

### Q4 — Walk through the doctors-on-call write skew example in full.
**Answer:** [give the full two-transaction repro from above: both read count=2 on-call from their own snapshot, both independently conclude it's safe to go off-call, both update their own row, both commit, final count is 0 — invariant violated with no write-write conflict ever detected because Alice's and Bob's updates touched different rows].
**Follow-up trap:** *"How would `SELECT ... FOR UPDATE` fix this specifically?"* — if the `SELECT count(*) FROM doctors WHERE on_call=true` locked the rows it read (`FOR UPDATE`/`FOR SHARE` on the relevant rows, or a `SERIALIZABLE` transaction using SSI), the second transaction's read would either block until the first commits (2PL-style) or be detected as an rw-antidependency and aborted (SSI-style) — either way, forcing the second transaction to see the post-update state and correctly refuse to also go off-call.

### Q5 — Why does snapshot isolation prevent read skew but not write skew, given both involve reading data that changes underneath you?
**Testing:** the precise mechanical distinction, the real signal question of this module.
**Answer:** Read skew is prevented because the whole point of a fixed snapshot is that repeated reads within the transaction see a single consistent point in time — SI's snapshot mechanism directly addresses this. Write skew isn't about what a transaction reads changing underneath it (each transaction's snapshot IS internally consistent) — it's about the *invariant relating two transactions' independent decisions* being violated by their disjoint writes, which is a property SI's conflict detection (same-row write-write conflicts) simply doesn't check for, because no row is written by both transactions.
**Follow-up trap:** *"If I add a UNIQUE or CHECK constraint spanning both rows, does that fix it?"* — a single-row CHECK constraint can't reference another row at all, and a cross-row invariant generally can't be expressed as a simple constraint; you either need application-level locking on the read that grounds the decision, or a `SERIALIZABLE` transaction using true dependency-cycle detection (SSI), or restructure the schema so the invariant becomes a single-row constraint (e.g., a single "on-call count" row updated atomically).

### Q6 — Explain how Postgres's SSI actually detects write skew without blocking readers.
**Answer:** Transactions running at SERIALIZABLE take SIREAD locks on data they read — bookkeeping locks that never block anything. When a later write touches data another transaction's SIREAD lock covers, Postgres records an rw-antidependency edge from the reader to the writer. If these edges form a specific dangerous structure — a cycle through a "pivot" transaction with both an incoming and outgoing rw-antidependency to transactions that ran concurrently with it — Postgres aborts one of the transactions with a serialization failure, forcing a retry.
**Follow-up trap:** *"Why doesn't SSI just take real locks and block, like 2PL?"* — because SIREAD locks being non-blocking is exactly what lets readers never wait, which is the whole performance advantage of MVCC in the first place; SSI trades "detect the conflict optimistically and abort one side" for "never block a reader," which wins on read-heavy workloads at the cost of an occasional forced retry under real contention.

### Q7 — What's the difference between Postgres's `REPEATABLE READ` and the ANSI-standard definition of `REPEATABLE READ`?
**Answer:** The ANSI standard's `REPEATABLE READ` only requires that a re-read of the *same row* returns the same value (preventing read skew on that row) but doesn't strictly require preventing phantoms (new rows matching a predicate). Postgres's actual `REPEATABLE READ` implements full snapshot isolation, which does prevent phantoms as a side effect of the fixed transaction-wide snapshot — it's actually stronger than the ANSI minimum for that name, though still weaker than true serializability (write skew still possible).
**Follow-up trap:** *"Is MySQL's `REPEATABLE READ` the same guarantee as Postgres's?"* — no; MySQL/InnoDB's `REPEATABLE READ` uses gap/next-key locking in addition to MVCC snapshots, which in practice prevents most phantom-insert scenarios that a pure-snapshot implementation wouldn't automatically catch — the two databases use the same isolation level *name* to mean implementations with different practical guarantees, which is exactly why you verify behavior per-database rather than trusting the label.

### Q8 — Oracle's isolation levels only go up to `SERIALIZABLE` (no separate snapshot-isolation name) — is Oracle `SERIALIZABLE` actually serializable?
**Testing:** whether the candidate has hit this specific, well-known gotcha.
**Answer:** No — Oracle's `SERIALIZABLE` is implemented as snapshot isolation, not true serializability; it does not implement SSI or a 2PL-based predicate-locking scheme. This means Oracle `SERIALIZABLE` transactions remain vulnerable to write skew despite the name, which surprises people who assume "serializable" means what the term formally means in the literature.
**Follow-up trap:** *"How would you actually get write-skew protection on Oracle?"* — explicit row locking (`SELECT ... FOR UPDATE`) on the specific rows backing the invariant, since the isolation level alone won't provide it; you have to compensate at the application/query level rather than relying on the isolation level name.

### Q9 — Give the real default isolation level for Postgres, MySQL/InnoDB, Oracle, and SQL Server.
**Answer:** Postgres, Oracle, and SQL Server all default to Read Committed. MySQL/InnoDB defaults to Repeatable Read (and, unusually among these four, its Repeatable Read uses gap locking that suppresses most phantom scenarios beyond the ANSI minimum).
**Follow-up trap:** *"Why would MySQL choose a stronger default than Postgres/Oracle/SQL Server?"* — historically tied to how InnoDB's replication (statement-based replication in particular) needed more deterministic read behavior to replay correctly across replicas; Repeatable Read's stronger consistency reduced a class of replication correctness bugs that Read Committed's per-statement snapshot would have made harder to reason about.

### Q10 — What is lost update, and how is it different from write skew?
**Answer:** Lost update: two transactions read the SAME row, each computes a new value from that read, and one write overwrites the other, silently discarding one of the updates (e.g., two concurrent "+100" and "+50" deposit operations resulting in a final balance that reflects only one of them). Write skew: two transactions read OVERLAPPING but not necessarily identical data, each makes an independent decision, and they write to DIFFERENT rows in a way that jointly violates an invariant — no single write is actually lost or overwritten, the invariant itself is the casualty.
**Follow-up trap:** *"Does plain snapshot isolation prevent lost update?"* — yes, in Postgres specifically, because of first-committer-wins: the second transaction's write to the same row triggers a serialization failure it must retry rather than silently overwriting, which is a genuine table-stakes protection SI does provide (this differs by database — some MVCC implementations under weaker configuration can still lose updates, so verify the specific database's write-conflict behavior, not just "MVCC" generically).

### Q11 — When would you choose explicit row locking (`SELECT ... FOR UPDATE`) over just running the transaction at `SERIALIZABLE`?
**Answer:** When you know exactly which rows back the invariant and want to pay the locking cost only there, rather than accepting a higher retry rate and SIREAD bookkeeping overhead across your entire transaction (which under `SERIALIZABLE` applies to every read the transaction does, not just the ones that matter for this specific invariant). `FOR UPDATE` is a targeted, cheap fix for a known, narrow write-skew risk; `SERIALIZABLE` is the right call when the invariant is complex, spans multiple queries, or you don't want to hand-identify every contended read.
**Follow-up trap:** *"What if you miss one of the rows that actually needs the lock?"* — that's exactly the risk of the targeted approach — a `FOR UPDATE` fix requires correctly identifying every read that grounds the invariant, and missing one silently reintroduces the anomaly with no warning; `SERIALIZABLE`/SSI's advantage is it doesn't require you to enumerate the dangerous reads by hand, at the cost of broader overhead.

### Q12 — Design the correct fix for a flight-booking system where two transactions might both book the last seat.
**Testing:** applying the whole toolkit to a slightly different concrete invariant (capacity, not a boolean).
**Answer:** This is a capacity-invariant version of write skew if implemented naively (both transactions read `seats_available > 0`, both see true, both decide to book, both decrement, ending at -1). Correct fix: either lock the seat-count row with `SELECT seats_available FROM flights WHERE id=? FOR UPDATE` before deciding, or use an atomic conditional update (`UPDATE flights SET seats_available = seats_available - 1 WHERE id=? AND seats_available > 0` and check the affected-row count) which folds the check-then-write into one atomic operation with no separate read to go stale, or run at `SERIALIZABLE` and handle the resulting abort/retry.
**Follow-up trap:** *"Which of those three is most efficient at high contention, and why?"* — the atomic conditional `UPDATE ... WHERE ... > 0` generally wins: it never takes an explicit lock held across a round-trip (the read and the conditional write happen in one statement, minimizing the window and avoiding held-lock time), avoids SSI's broader per-transaction overhead, and fails cleanly (zero rows affected) without needing a serialization-failure retry loop — `FOR UPDATE` and `SERIALIZABLE` are both more general tools but cost more here for a case this specific pattern handles directly.

---

## Red flags that fail you

- Saying "MVCC prevents all concurrency anomalies" without naming write skew as the exception.
- Not knowing that Oracle's `SERIALIZABLE` is actually snapshot isolation, or asserting all databases' `SERIALIZABLE` behave identically.
- Confusing lost update with write skew, or being unable to give a two-transaction repro for either on request.
- Describing 2PL and MVCC as the same thing, or not knowing that predicate locks (not just row locks) are required to prevent phantoms under pure locking.
- Reaching for `SERIALIZABLE` as a reflex answer with no acknowledgment of its retry/overhead cost.
- Not knowing the real default isolation level of at least Postgres and MySQL.
- Claiming a `CHECK` constraint can prevent a cross-row invariant violation like write skew.

---

## Cheat card

```
XMIN/XMAX      xmin = creating txn, xmax = deleting/superseding txn (0/null = live)
               VISIBLE if: xmin committed before snapshot AND
                           (xmax unset OR xmax's txn not committed before snapshot)
               Read Committed: new snapshot PER STATEMENT
               Repeatable Read/Serializable: ONE snapshot for whole transaction

2PL            shared lock on read, exclusive on write, held til commit;
               needs PREDICATE locks (not just row locks) to stop phantoms;
               readers block writers and vice versa -- the cost MVCC avoids

ANOMALIES      dirty read      - see uncommitted write
               dirty write     - overwrite uncommitted write
               read skew       - same row, 2 reads in 1 txn, different answers
               phantom         - predicate result set changes mid-txn
               lost update     - same row r-m-w, one write clobbers the other
               write skew      - DIFFERENT rows, disjoint writes jointly break
                                 an invariant neither write alone violated

LEVEL -> ANOMALY TABLE
  Read Uncommitted: all possible except dirty write
  Read Committed:   dirty read/write prevented; read skew/phantom/lost update/
                    write skew still possible
  Repeatable Read (ANSI min / MySQL): + read skew prevented; phantom/write
                    skew possible (MySQL's gap locks suppress most phantoms
                    beyond the ANSI minimum, in practice)
  Snapshot Isolation (Postgres REPEATABLE READ): + phantom + lost update
                    prevented (first-committer-wins); WRITE SKEW STILL POSSIBLE
  Serializable:     everything prevented (Postgres: SSI: Postgres: SSI, not
                    locking; MySQL/Oracle/SQLServer: locking-based)

DEFAULTS       Postgres/Oracle/SQL Server -> READ COMMITTED
               MySQL/InnoDB               -> REPEATABLE READ
               GOTCHA: Oracle "SERIALIZABLE" = snapshot isolation, NOT true
               serializable -- write skew still possible on Oracle SERIALIZABLE

SSI            SIREAD locks = bookkeeping only, never block · rw-antidependency
               = txn A reads what txn B later overwrites · dangerous structure =
               cycle of 2 rw-antidependencies through a pivot txn -> abort+retry

FIX WRITE SKEW SELECT ... FOR UPDATE on the invariant-backing rows (targeted,
               cheap) OR atomic conditional UPDATE ... WHERE cond (best for
               simple capacity checks) OR run at SERIALIZABLE (general, costs
               retry rate + SIREAD overhead across the whole txn)
```

## Sources

- [Serializable Snapshot Isolation in PostgreSQL (Ports & Grittner, VLDB 2012, arXiv:1208.4179)](https://arxiv.org/pdf/1208.4179) — accessed 2026-07-26
- [PostgreSQL Documentation: 13.2. Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html) — accessed 2026-07-26
- [A Critique of ANSI SQL Isolation Levels (Berenson et al., arXiv:cs/0701157)](https://arxiv.org/pdf/cs/0701157) — accessed 2026-07-26
- [Introduction to Snapshots and Tuple Visibility in PostgreSQL — Jan Nidzwetzki](https://jnidzwetzki.github.io/2024/04/03/postgres-and-snapshots.html) — accessed 2026-07-26
- [Jepsen: PostgreSQL 12.3](https://jepsen.io/analyses/postgresql-12.3) — accessed 2026-07-26
- [Document data modeling to avoid write skew anomalies (doctors-on-call example) — YugabyteDB / DEV Community](https://dev.to/yugabyte/document-data-modeling-to-avoid-write-skew-anomaly-doctors-on-call-shift-example-465d) — accessed 2026-07-26
- [A beginner's guide to the Write Skew anomaly, 2PL vs MVCC — Vlad Mihalcea](https://vladmihalcea.com/write-skew-2pl-mvcc/) — accessed 2026-07-26
- [5.9. Serializable Snapshot Isolation — Hironobu Suzuki, The Internals of PostgreSQL](https://www.interdb.jp/pg/pgsql05/09.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
