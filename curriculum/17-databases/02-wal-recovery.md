# WAL, ARIES Recovery, Checkpoints, Durability

> **Track:** T17 Databases: SQL, NoSQL, Vector · **Time:** 1.5h · **Prereqs:** `T17-storage-engines` · **Updated:** 2026-07-26
> **Module id:** `T17-wal-recovery` · **Tags:** internals

## The 30-second version

Write-ahead logging means every change is durably recorded in a sequential log *before* the corresponding data page is allowed to hit disk, which turns an expensive random-write durability problem into a cheap sequential-append one and gives you a recovery story: replay the log after a crash and you can reconstruct any state the database claimed to have committed. ARIES (Mohan et al., 1992) formalizes crash recovery into three passes over that log — **analysis** (figure out which transactions and pages were in flight at crash time), **redo** (replay history forward from the last checkpoint so the database looks exactly as it did the instant before the crash, including the effects of transactions that hadn't committed yet), and **undo** (roll back the transactions that were never committed, using compensation log records so undo itself is crash-safe). Checkpoints exist purely to bound recovery time by giving analysis a more recent starting point than "the beginning of the log," and log truncation depends on checkpoints plus confirmation that no backup or replica still needs the old records. The number every senior engineer should know cold: a naive `fsync` per write costs roughly the rotational/flash write-commit latency (~0.1-1ms on NVMe, historically 5-10ms on spinning disk), which is why databases batch commits together (**group commit**) rather than fsyncing once per transaction, and why an `fsync` that silently no-ops because of a misconfigured disk cache, virtualized storage layer, or a documented kernel bug is one of the most catastrophic and hardest-to-detect classes of data-loss bug in production databases.

## Why this gets asked

Because "durability" sounds like a checkbox until you've watched a crash wipe out data that the application was told was committed, and the interviewer wants to know if you understand *why* that happens — usually an `fsync` that didn't actually flush to stable storage because of a write-back cache, a virtualization layer that lied about durability, or a checkpoint interval so long that recovery took an hour of downtime nobody planned for. This is one of the few topics where the gap between "textbook knows WAL exists" and "has actually debugged an `fsync` lie or sized a checkpoint interval under an SLA" is enormous, and interviewers use it specifically to find that gap.

---

## Lineage: past → present → future

**What came before.** Early database systems used two competing approaches to crash safety, both with serious downsides. **Shadow paging** (used in early System R prototypes) never modified a page in place — writes went to a fresh copy of the page, and a single atomic pointer swap of the root committed the whole transaction — which gave crash safety for free but destroyed locality (pages scatter across the disk over time) and made concurrent transactions and fine-grained locking awkward, since the whole tree effectively needed copy-on-write semantics. The alternative, **force-at-commit** (writing every dirty page to disk synchronously before acknowledging commit, with no logging needed for redo), was simple but made every commit pay for however many random-access page writes that transaction had dirtied — brutally slow, and it still needed *some* logging for undo of uncommitted transactions. The pain that killed both as general answers: neither scaled to high-throughput OLTP with many small, frequent transactions touching scattered pages, and neither gave you a clean "replay this file to recover" recovery story that didn't depend on the storage layout itself surviving intact.

**Where it stands now.** ARIES (IBM, Mohan et al., 1992) is the reference algorithm essentially every mainstream relational database's crash recovery is either a direct implementation of or a close descendant of — Postgres, MySQL/InnoDB, SQL Server, and Oracle all use WAL-based recovery following ARIES's core ideas (log sequence numbers, the "repeating history" redo philosophy, and physiological/compensation logging for undo), even where implementation details diverge. The current consensus is durable: WAL-based recovery with checkpointing is simply the accepted architecture; there is no serious competing design in mainstream production RDBMS today. The live disagreement is narrower and operational: **how aggressively to fsync**. `synchronous_commit = on` in Postgres guarantees a transaction's WAL is fsynced before the client gets an acknowledgment (safe, slower); `synchronous_commit = off` lets the transaction return before the fsync completes, risking losing the last fraction-of-a-second of commits on a crash but meaningfully increasing throughput — and different teams make genuinely different calls here depending on whether "lose the last 200ms of commits on an OS crash" is an acceptable risk (it usually is for many workloads; it usually is not for financial ledgers). **Group commit** (batching multiple transactions' fsyncs into one physical fsync call) is universal in production and is not itself controversial — the only debate is how long to wait to accumulate a batch versus how much added latency that costs any single transaction.

**Where it's heading.** Persistent memory (Intel Optane, now discontinued as a product line but influential on the ideas) drove real research into WAL designs that write directly to byte-addressable persistent memory instead of block-device fsync, since that changes the durability cost model entirely (no rotational/flash write-commit latency, just a memory-fence-level operation) — with Optane's discontinuation this specific hardware path stalled, but the WAL-on-PMEM research direction (and CXL-attached persistent memory as its likely successor) is a real, if currently dormant, area to watch. More concretely deployed today: **NVMe write-cache and FUA (Force Unit Access) semantics**, and cloud block-storage durability guarantees (EBS, Persistent Disk) that let databases reason about fsync cost and durability without owning physical disks, are the practical reality most engineers now operate in — the interesting frontier is less "new recovery algorithms" and more "trusting the storage layer's durability claims correctly," since cloud/virtualized storage has repeatedly had documented incidents where an acknowledged write was not actually durable. Treat "new recovery algorithms displacing ARIES" as unlikely near-term; treat "durability guarantees moving further into storage-layer abstractions you must verify rather than assume" as the real, ongoing trend.

---

## Mental model

```
                     COMMIT REQUEST
                          │
                          ▼
              ┌───────────────────────┐
              │  1. Append log record  │──▶  LOG (sequential, append-only)
              │     to WAL buffer      │     LSN 100, 101, 102...
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  2. fsync WAL to disk  │◀── THE DURABILITY POINT.
              │  (or wait for group    │    Nothing before this line is
              │   commit to fsync)     │    guaranteed to survive a crash.
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  3. Ack commit to      │
              │     client             │
              └───────────┬───────────┘
                          │
                    (data page write to
                     disk can happen much
                     LATER — buffer pool
                     flushes lazily)
                          ▼
              ┌───────────────────────┐
              │  4. Data page flushed  │  Can be minutes/hours after
              │     eventually         │  commit. The log is what makes
              │     (checkpoint/       │  this safe to defer.
              │      eviction)         │
              └───────────────────────┘

THE RULE: log record for a change must be durable (step 2) BEFORE the
data page containing that change is allowed to reach disk (step 4).
That's the entire WAL protocol in one sentence.
```

**Why this ordering matters.** If the data page reached disk *before* its log record, and the system crashed in between, you'd have a page on disk reflecting a change with no log record to explain or undo it — recovery has nothing to reason from. Log-first means recovery always has a complete, ordered history to replay or roll back, no matter which data pages made it to disk and which didn't before the crash.

---

## How it actually works

### The WAL protocol, precisely

Two rules, both non-negotiable in any correct WAL implementation:

1. **Log the change before writing the affected data page to disk.** (The "write-ahead" part.)
2. **Log commit records before acknowledging a transaction as committed.** (The durability part — the client cannot be told "done" until the WAL record proving it is durable.)

Every log record carries a **Log Sequence Number (LSN)** — a monotonically increasing identifier. Every data page carries a **pageLSN**: the LSN of the last log record whose change is reflected in that page. This pairing is what lets recovery figure out, per page, exactly which log records still need replaying (any LSN greater than the page's current pageLSN) versus which are already reflected (any LSN ≤ pageLSN) — critical because recovery must be **idempotent**: re-applying an already-applied change must be a no-op, not a double-apply.

### ARIES: analysis, redo, undo

**Analysis.** Scan forward from the last checkpoint to the end of the log (or to a crash point). Reconstruct two tables: the **Transaction Table** (which transactions were active, and where in the log their most recent record is) and the **Dirty Page Table** (which pages had uncommitted changes in the buffer pool, and the LSN of the earliest log record that dirtied each — the `recLSN`). This tells recovery exactly where redo needs to start: the minimum `recLSN` across all dirty pages, not the beginning of the log, which is the entire reason checkpoints exist.

**Redo.** Starting from that minimum `recLSN`, replay *every* logged change forward, for both committed and uncommitted transactions — this is ARIES's "repeat history" principle, and it's deliberately not selective, because figuring out ahead of time which changes are "needed" would itself require the state you're trying to reconstruct. Redo is skipped per-page whenever the log record's LSN is ≤ that page's current pageLSN (already reflected, thanks to the pairing above) — this is what makes redo idempotent and safe to run against a database that already has some (but not all) of these changes applied.

**Undo.** After redo, the database's in-memory/on-disk state exactly matches the instant before the crash — including the partial work of transactions that never committed. Undo now rolls those transactions back, in reverse LSN order, using **Compensation Log Records (CLRs)**: each undo action is itself logged, so that if the system crashes *again* during undo, recovery doesn't redo the undo's already-completed portion from scratch — CLRs point to the next record to undo, so undo of undo is also idempotent and crash-safe. This is the detail most people miss: undo is not exempt from crash safety, and ARIES's answer is to make the rollback process itself just another kind of forward-logged, redoable operation.

### Checkpoints and log truncation

A **checkpoint** writes a record capturing the current Transaction Table and Dirty Page Table (or, in a "fuzzy checkpoint," just enough bookkeeping to know where to start analysis, without stopping the world to build a perfectly consistent snapshot — real systems use fuzzy checkpoints because a stop-the-world checkpoint would itself hurt latency). Its only purpose is to bound recovery time: without checkpoints, analysis would have to scan from the very start of the log, however far back that is, and redo would need to replay the entire log's history, which for a system that's been running for months could mean hours of recovery time after a crash.

**Log truncation (log recycling)** can only discard log records older than the oldest `recLSN` still referenced by the current checkpoint's Dirty Page Table — you cannot delete a log record if a page still on disk depends on it not having been applied yet, or if a replica/backup hasn't consumed it. In Postgres terms: `checkpoint_completion_target` and `max_wal_size` govern how aggressively WAL segments get recycled, and a replication slot that's fallen behind (a disconnected replica, a stuck logical-replication consumer) will hold WAL segments from being recycled at all — **this is one of the most common causes of "disk full" incidents in production Postgres**: WAL directory grows unboundedly because a replication slot is retaining segments nobody is consuming.

### fsync, durability, and the lies that cause data loss

`fsync()` is supposed to mean "these bytes are on stable storage, survive a power loss." In practice, several layers can silently violate that:

- **Disk write-back caches** with volatile (non-battery/capacitor-backed) cache report the write as complete once it's in the drive's own RAM cache, not on the physical medium — a power loss loses that cache's contents despite the OS having called `fsync` successfully.
- **Virtualized/cloud block storage** has had real, documented incidents where an acknowledged write was not actually durable across the underlying replication/storage fabric before a failure — this is why cloud databases publish specific durability guarantees (e.g., "replicated across N availability zones before ack") rather than relying solely on guest-OS fsync semantics.
- **The infamous PostgreSQL fsync() error-handling bug (2018, widely discussed as "fsyncgate")**: on Linux, if `fsync()` fails, the kernel — in versions and configurations affected — cleared the dirty-page-error flag anyway, meaning a *subsequent* `fsync()` call would report success even though the earlier write was never actually flushed, silently discarding data the application believed was durable. This forced Postgres (and other databases) to add `PANIC`-on-fsync-failure behavior rather than retrying, because retrying a failed fsync could report false success.
- **`fdatasync` vs `fsync`**: `fdatasync` skips flushing metadata that doesn't affect how the file is read (e.g., mtime), which is faster and is what Postgres uses by default (`wal_sync_method`) — this is a legitimate optimization, not a lie, but it's worth knowing the distinction exists.

**Group commit.** Instead of one `fsync` per transaction commit, the database batches: multiple transactions' WAL records accumulate in the WAL buffer for a very short window (often single-digit milliseconds or less, adaptively), and one `fsync` call flushes all of them together, then all waiting transactions are acknowledged as committed simultaneously. This amortizes the fixed cost of an fsync call (dominated by the storage medium's flush latency, not by the number of bytes) across many transactions — the throughput gain can be an order of magnitude under concurrent load, at the cost of a small added latency for the transaction that would otherwise have committed immediately alone.

```python
# untested sketch — illustrates group commit batching logic
import threading, time

class GroupCommitWAL:
    def __init__(self, batch_window_ms=2):
        self.pending = []
        self.lock = threading.Lock()
        self.batch_window = batch_window_ms / 1000

    def commit(self, txn_log_records):
        event = threading.Event()
        with self.lock:
            self.pending.append((txn_log_records, event))
            is_leader = len(self.pending) == 1
        if is_leader:
            time.sleep(self.batch_window)   # let others join the batch
            with self.lock:
                batch, self.pending = self.pending, []
            self._write_and_fsync([rec for records, _ in batch for rec in records])
            for _, ev in batch:
                ev.set()                    # wake everyone in this batch at once
        else:
            event.wait()                    # wait for the batch leader to fsync

    def _write_and_fsync(self, records):
        ...  # append to log file, os.fsync(fd)
```

---

## Build it from scratch

A minimal WAL + crash recovery simulator: append log records with LSNs, simulate a crash mid-transaction, then run analysis/redo/undo against an in-memory page store.

```python
# untested sketch — mechanics only, not a real storage engine
import json, os

class WAL:
    def __init__(self, path):
        self.path = path
        self.next_lsn = 1

    def append(self, record: dict) -> int:
        lsn = self.next_lsn
        self.next_lsn += 1
        record["lsn"] = lsn
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())     # THE durability point
        return lsn

    def read_all(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]


def recover(wal: WAL, pages: dict, page_lsn: dict):
    records = wal.read_all()

    # ANALYSIS: find committed vs uncommitted (loser) transactions
    committed, active_updates = set(), {}
    for r in records:
        if r["type"] == "commit":
            committed.add(r["txn"])
        elif r["type"] == "update":
            active_updates.setdefault(r["txn"], []).append(r)

    # REDO: replay every update, committed or not — "repeat history".
    # Skip if already reflected (idempotent via LSN comparison).
    for r in records:
        if r["type"] != "update":
            continue
        if r["lsn"] <= page_lsn.get(r["page"], 0):
            continue                       # already applied; skip (idempotency)
        pages[r["page"]] = r["after"]
        page_lsn[r["page"]] = r["lsn"]

    # UNDO: roll back every transaction with no commit record ("losers"),
    # reverse LSN order, writing a Compensation Log Record for each undo.
    losers = [t for t in active_updates if t not in committed]
    for txn in losers:
        for r in sorted(active_updates[txn], key=lambda x: -x["lsn"]):
            pages[r["page"]] = r["before"]
            wal.append({"type": "clr", "txn": txn, "page": r["page"],
                        "undo_of_lsn": r["lsn"]})

    return pages
```

This demo shows the two non-negotiable ARIES properties: redo is blind/total (replays everything, filtered only by LSN-vs-pageLSN, never by "was this transaction committed") and undo is itself logged (CLRs), so a second crash mid-undo doesn't restart undo from scratch. Full version with checkpoints, a Dirty Page Table, and fuzzy-checkpoint recovery: **`(lab pending)`**.

---

## How it's done in production

**Postgres.** WAL records go to `pg_wal/` segments (default 16 MB each). `synchronous_commit` controls how much durability is guaranteed before ack (`on` = full fsync wait, `off` = return before fsync, `remote_write`/`remote_apply` = wait for a replica). Checkpoints are triggered by `checkpoint_timeout` (default 5 min) or `max_wal_size` being reached, whichever comes first; `checkpoint_completion_target` (default 0.9) spreads the checkpoint's I/O over most of that interval to avoid an I/O spike. `full_page_writes` (default on) additionally logs the entire page content on its first modification after a checkpoint, protecting against torn pages (a page write interrupted mid-write by a crash, leaving it partially old/partially new bytes) — this is a real, necessary cost (extra WAL volume right after each checkpoint) that surprises people sizing WAL throughput.

**MySQL/InnoDB.** The InnoDB redo log (`ib_logfile*` or, in modern MySQL, redo log files in `#innodb_redo/`) follows the same WAL-before-page-write discipline; `innodb_flush_log_at_trx_commit` is InnoDB's equivalent durability/performance knob: `1` = fsync every commit (full ACID durability), `2` = write to OS cache every commit but only fsync once per second (survives a MySQL crash, not an OS crash), `0` = write and fsync roughly once per second regardless of commits (fastest, least durable — can lose up to ~1 second of transactions on any crash).

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Data loss after an OS/power crash despite "clean" application logs | `fsync` silently no-op'd (write-back cache without battery backup, virtualization layer lying about durability, or the 2018-class fsync-error-handling bug) | Use storage with battery-backed/capacitor-backed write cache or verified cloud durability guarantees; ensure the DB `PANIC`s rather than retries on fsync failure; test with actual power-pull drills, not just `kill -9` |
| WAL/redo log directory grows until disk is full | A replication slot (physical or logical) is retaining WAL segments because the consumer is disconnected or stuck | Monitor replication slot lag; drop or fix stalled slots; alert on WAL directory size trend, not just absolute size |
| Recovery after a crash takes far longer than expected | Checkpoint interval too long, or checkpoint itself falling behind under heavy write load | Tune `checkpoint_timeout`/`max_wal_size` down for a recovery-time SLA; ensure checkpoint I/O isn't starved by foreground traffic |
| Commit throughput far below expected under high concurrency | No group commit, or group-commit batch window misconfigured too small | Verify `synchronous_commit` and group-commit batching are active; widen the batch window slightly if fsync-call count, not per-transaction latency, is the bottleneck |
| Torn-page corruption after a crash mid-write | `full_page_writes` disabled (Postgres) without an underlying storage guarantee of atomic page writes | Keep `full_page_writes` on unless the storage layer explicitly guarantees atomic sector/page writes (rare outside specialized hardware) |
| Undo/rollback appears to hang or repeat after a second crash during recovery | Undo wasn't itself made crash-safe (no CLR-equivalent logging) | This is a correctness bug in a from-scratch implementation, not a tuning issue — undo must log compensation records so a second crash mid-undo can resume, not restart |

---

## Tradeoffs & when NOT to use it

- **`synchronous_commit = off` is a real, defensible production choice** for workloads where losing the last ~200ms-1s of acknowledged commits on an OS crash (not a graceful shutdown) is acceptable — many analytics-adjacent or non-financial OLTP workloads make this tradeoff deliberately for throughput. It is the wrong choice for anything resembling a financial ledger or a system where "the client was told it committed" must be an absolute guarantee.
- **Do not assume cloud block storage's `fsync` behaves identically to bare-metal.** Verify the specific managed database or cloud disk's documented durability guarantee; some managed offerings decouple compute and storage in ways that change what "durable" means at the point of ack.
- **Checkpointing too rarely** optimizes steady-state I/O at the direct cost of recovery time — this is a real SLA tradeoff, not a pure win, and should be sized against your actual acceptable downtime, not left at a framework default.
- **Checkpointing too aggressively** thrashes disk I/O and can itself cause latency spikes in foreground traffic, ironically making the system less available while trying to make recovery faster.
- **WAL is the wrong mental model to reach for when the actual problem is analytical throughput, not durability** — see `15-oltp-vs-olap.md`; column stores and OLAP engines often use entirely different durability/commit models (batch-oriented, less frequent fsync) because the workload doesn't need per-row transactional durability at OLTP frequency.

---

## Interview questions

### Q1 — What is the write-ahead logging protocol, in one sentence?
**Testing:** baseline.
**Answer:** Every change must be recorded in a durable log record before the corresponding data page is allowed to reach disk, and the commit record must be durable before the client is told the transaction committed.
**Follow-up trap:** *"Why does the order matter — couldn't you write the page first and log it right after?"* — if the page reaches disk first and the system crashes before the log record is written, there's no record explaining that change, and recovery has nothing to reconstruct or undo from; the log must always be ahead of the data, never behind.

### Q2 — Walk through ARIES's three phases.
**Answer:** Analysis scans forward from the last checkpoint to reconstruct which transactions were active and which pages were dirty, finding the earliest LSN redo needs to start from. Redo replays every logged change forward from there — for committed and uncommitted transactions alike — skipping any change already reflected in a page (LSN ≤ pageLSN). Undo then rolls back transactions that never committed, in reverse order, using Compensation Log Records so a second crash mid-undo doesn't restart from scratch.
**Follow-up trap:** *"Why does redo replay uncommitted transactions' changes too?"* — because at analysis time you can't yet cheaply and correctly determine what's "needed" without the very state you're reconstructing; "repeat history" is deliberately blind, and it's undo's job (after redo restores the pre-crash state exactly) to remove the effects of transactions that never committed.

### Q3 — What is a checkpoint for, precisely?
**Answer:** Solely to bound recovery time. Without it, analysis would scan from the start of the log (however far back that is) and redo would replay the database's entire history. A checkpoint gives analysis a recent, sufficient starting point (the oldest `recLSN` of any dirty page as of the checkpoint) instead.
**Follow-up trap:** *"Does a checkpoint need to stop all transactions?"* — no, production databases use fuzzy checkpoints that capture bookkeeping without a full consistent stop-the-world snapshot, because a hard-stop checkpoint would itself hurt latency; fuzzy checkpoints are safe precisely because redo's idempotent, LSN-driven replay tolerates an inconsistent snapshot at checkpoint time.

### Q4 — What log records can be truncated, and what commonly prevents that?
**Answer:** Only log records older than the oldest `recLSN` still referenced by the current checkpoint's dirty-page bookkeeping — anything a page on disk still depends on, or that a replica/backup hasn't consumed, must stay. A disconnected or stuck replication slot (physical or logical) is the most common real-world cause of WAL retention growing unboundedly and filling disk.
**Follow-up trap:** *"How would you actually catch this before disk fills up?"* — monitor replication slot lag / retained WAL bytes as a first-class alert, not just total disk usage; by the time disk usage alone trips an alert, you may already be minutes from an outage, whereas slot-lag climbing is the earlier, more specific signal.

### Q5 — Explain a real fsync failure mode that causes silent data loss.
**Answer:** A disk's volatile write-back cache without battery/capacitor backing reports a write complete once it's in the drive's own cache, not the physical medium — a power loss loses it despite `fsync` having returned success. Separately, a documented Linux kernel behavior (surfaced publicly around 2018 and dubbed "fsyncgate" in the Postgres community) cleared the dirty-page error flag after a failed fsync, so a *subsequent* fsync call on the same file could report success even though the earlier write was never actually flushed.
**Follow-up trap:** *"How do databases defend against the kernel-level version of this?"* — by treating any fsync failure as unrecoverable and PANICing/crashing the process rather than retrying, because retrying risks reporting false success; this is a deliberate, defensive design choice, not an oversight, once the underlying kernel behavior became known.

### Q6 — What is group commit and why does it exist?
**Answer:** Instead of one fsync per transaction, the database batches multiple transactions' WAL records over a short window and issues one fsync for the whole batch, then acknowledges all of them together. It amortizes the fixed per-fsync-call latency (dominated by the storage medium, not byte count) across many transactions, often giving an order-of-magnitude throughput improvement under concurrency at the cost of a small added latency for transactions that would otherwise commit immediately.
**Follow-up trap:** *"Doesn't this hurt single-transaction latency?"* — yes, marginally, for the transaction that arrives alone; the batch window is usually tuned to be small enough (low single-digit milliseconds or adaptive) that the latency cost is negligible relative to the fsync's own baseline latency, and most production systems make this tradeoff by default.

### Q7 — Why must undo itself be logged, via Compensation Log Records?
**Answer:** Because a crash can happen *during* recovery's own undo phase; without logging the undo actions themselves, a second crash mid-undo would have no way to know which parts of the rollback already completed, and could either redo the undo (fine, since data-level redo is idempotent per page) or, worse, have no record at all of how far undo had progressed, risking repeating or skipping compensating actions incorrectly. CLRs make undo itself replayable and idempotent, matching the guarantees the forward log already has.
**Follow-up trap:** *"So does undo ever loop forever if it keeps crashing?"* — no, because each CLR records which original update it's undoing and points to the next one to process, so recovery after any number of crashes always resumes from exactly where undo left off, converging monotonically toward completion rather than restarting.

### Q8 — What's the difference between `synchronous_commit = on` and `off` in Postgres, and when would you choose `off`?
**Answer:** `on` guarantees the transaction's WAL record is fsynced to disk before the client is told it committed — full durability, higher per-commit latency. `off` returns success to the client before that fsync completes, risking loss of the last fraction-of-a-second of "committed" transactions if the OS or machine crashes (not a graceful DB shutdown, which still flushes). Choose `off` for workloads where that risk window is acceptable in exchange for throughput — high-volume analytics ingestion, non-financial event logging, caches-of-record — never for anything resembling a ledger.
**Follow-up trap:** *"If the whole machine loses power, what exactly is lost with `off`?"* — any transactions that returned "committed" to the client but whose WAL record hadn't yet been fsynced at the moment of power loss; this is a real, bounded, quantifiable risk window (typically well under a second in practice), not an unbounded one, which is exactly the tradeoff that makes it a legitimate choice for some workloads and not others.

### Q9 — What does `full_page_writes` protect against, and what does disabling it risk?
**Answer:** It protects against torn pages: if a crash interrupts a page write mid-flight, the page on disk can end up partly the old version and partly the new one, byte-for-byte inconsistent in a way normal WAL replay (which assumes a page is either fully old or fully new) can't repair. Postgres logs the entire page content the first time it's modified after a checkpoint specifically so recovery can restore a known-good full page rather than trying to patch a torn one. Disabling it without a storage layer that guarantees atomic page writes risks unrecoverable corruption on exactly the kind of crash WAL is supposed to protect against.
**Follow-up trap:** *"Doesn't this make WAL volume spike right after every checkpoint?"* — yes, and that's a real, expected cost that surprises people sizing `max_wal_size`/WAL throughput; the first write to each page after a checkpoint is disproportionately expensive, which is one input into checkpoint-interval tuning.

### Q10 — A production database takes 45 minutes to recover after a crash, and the SLA allows 5. Diagnose and fix.
**Answer:** Checkpoint interval is almost certainly too long relative to write volume, so redo has an enormous amount of log to replay from the last checkpoint forward. Fix by tightening `checkpoint_timeout`/`max_wal_size` (Postgres) or the equivalent InnoDB settings to force more frequent checkpoints, trading some steady-state I/O overhead for a bounded recovery time; verify the checkpoint itself isn't silently falling behind under load (check checkpoint completion time against the interval).
**Follow-up trap:** *"What if tightening the checkpoint interval causes new foreground latency spikes?"* — that's the real tradeoff: more frequent checkpoints cost more I/O in steady state; the fix there is spreading checkpoint I/O over the interval (`checkpoint_completion_target`) and ensuring dedicated I/O bandwidth, not just picking an interval and hoping — this is a capacity-planning conversation, not a single-knob fix.

### Q11 — How would you test that your database's durability guarantee actually holds?
**Answer:** A `kill -9` of the process is not a real test — it doesn't interrupt disk writes or lose OS page cache. A real test pulls power (or uses a fault-injection tool that simulates it) on the actual storage medium mid-write, then verifies every transaction the application observed as "committed" before the pull is present after recovery, and nothing beyond that. Chaos-style repeated power-pull drills against a busy write workload are the standard way vendors and serious operators validate this.
**Follow-up trap:** *"Your power-pull test passed on bare metal but you're moving to a cloud VM. Does the test still validate anything?"* — not automatically; the cloud storage layer's durability contract may differ from what a local disk's fsync means, so the test needs to be re-run against the actual production storage substrate (network-attached/virtualized disk), not assumed to transfer, precisely because of documented historical cases where virtualized storage did not honor fsync the way bare-metal disks do.

### Q12 — Compare shadow paging and WAL as crash-recovery strategies, and explain why WAL won.
**Answer:** Shadow paging never modifies a page in place — writes go to a fresh copy, and an atomic root-pointer swap commits the transaction, giving crash safety without any log replay needed for redo. But it destroys physical locality over time (pages scatter across disk as copies accumulate) and makes fine-grained concurrent transactions awkward, since effectively the whole modified path needs copy-on-write treatment. WAL keeps data pages in their original locations, updates in place, and relies on a separate sequential log for recovery, which preserves locality and allows much finer-grained concurrency control (row/page-level locking or MVCC) independent of the recovery mechanism.
**Follow-up trap:** *"Isn't an LSM-Tree's SSTable immutability basically shadow paging?"* — there's a real conceptual similarity (never overwrite in place, always create new immutable structures), but LSM still uses a WAL for the memtable's durability before flush, and its "recovery" story is closer to WAL-replay-into-memtable than a root-pointer-swap; it's fair to note the family resemblance but they solve different scoped problems (LSM: efficient writes to a sorted structure; shadow paging: whole-page/tree atomicity for recovery).

### Q13 — Why is redo required to be idempotent, and how does the pageLSN/LSN comparison achieve that?
**Answer:** Recovery itself might crash and need to restart, potentially re-running analysis and redo against a database that already has some of these changes applied (because a previous, interrupted recovery attempt got partway through). Idempotency means running redo twice produces the same result as running it once. The mechanism: every data page stores the LSN of the last log record it reflects (pageLSN); redo skips any log record whose LSN is ≤ the target page's current pageLSN, so already-applied changes are never reapplied.
**Follow-up trap:** *"What if the pageLSN itself is corrupted or missing after a crash?"* — this is exactly why full-page-writes-style protections and checksums matter; if the page's own bookkeeping can't be trusted, idempotent redo has no reliable signal to compare against, and recovery falls back to treating the page as unknown/needing full replacement from the log or a backup.

---

## Red flags that fail you

- Describing WAL as "just logging" without the ordering rule (log before data page, log before ack).
- Not knowing ARIES has three phases, or describing redo as "only replay committed transactions."
- Claiming checkpoints exist to save disk space rather than to bound recovery time.
- Believing `fsync` returning success always means the bytes are physically durable.
- Not knowing group commit exists, or thinking every commit requires its own fsync in a well-tuned system.
- Testing durability with `kill -9` and believing that validates anything about power-loss safety.
- Saying undo doesn't need its own crash safety.

---

## Cheat card

```
WAL RULE            log record durable BEFORE data page hits disk
                     commit log record durable BEFORE client told "committed"

ARIES 3 PHASES       ANALYSIS: scan from last checkpoint, build Transaction Table +
                       Dirty Page Table, find min recLSN to start redo from
                     REDO: replay ALL changes forward (committed + uncommitted) —
                       "repeat history" — skip if LSN <= page's current pageLSN (idempotent)
                     UNDO: roll back uncommitted ("loser") txns, reverse order,
                       via Compensation Log Records (CLRs) — undo is itself logged/crash-safe

LSN / pageLSN        LSN = monotonic id per log record. pageLSN = LSN of last change
                     reflected in that page. LSN <= pageLSN => already applied, skip.

CHECKPOINT           purpose = bound recovery time only, not disk space.
                     fuzzy checkpoint: no stop-the-world; safe because redo is idempotent
                     Postgres: checkpoint_timeout (default 5min), max_wal_size,
                       checkpoint_completion_target (default 0.9, spreads I/O)

LOG TRUNCATION       can only discard log < oldest recLSN still needed.
                     #1 real cause of WAL-fills-disk incidents: a stalled/disconnected
                     replication slot retaining segments nobody consumes.

FULL PAGE WRITES     Postgres: logs entire page on first write after checkpoint,
                     protects against torn pages. WAL volume spikes right after checkpoint.

FSYNC LIES           volatile write-back disk cache (no battery backing) can ack before
                     physical durability. 2018 Linux fsync-error bug: failed fsync could
                     silently clear error state so a LATER fsync reports false success ->
                     Postgres now PANICs on fsync failure rather than retrying.

GROUP COMMIT         batch many txns' WAL into ONE fsync call; amortizes fixed fsync
                     latency (~0.1-1ms NVMe, ~5-10ms old spinning disk) across many commits.

DURABILITY KNOBS     Postgres synchronous_commit: on=fsync before ack, off=ack before fsync
                     InnoDB innodb_flush_log_at_trx_commit: 1=fsync/commit, 2=fsync~1s
                       (survives mysqld crash not OS crash), 0=write+fsync~1s regardless

TEST DURABILITY      kill -9 tests nothing about power loss. Real test: pull power /
                     fault-inject mid-write, verify exactly what was acked survived.
```

## Sources

- [Write-ahead logging and the ARIES crash recovery algorithm — Kevin Sookocheff](https://sookocheff.com/post/databases/write-ahead-logging/) — accessed 2026-07-26
- [Algorithm for Recovery and Isolation Exploiting Semantics (ARIES) — GeeksforGeeks](https://www.geeksforgeeks.org/dbms/algorithm-for-recovery-and-isolation-exploiting-semantics-aries/) — accessed 2026-07-26
- [PostgreSQL 18 Documentation: WAL Configuration](https://www.postgresql.org/docs/current/wal-configuration.html) — accessed 2026-07-26
- [Database Crash Recovery: ARIES, WAL & Shadow Paging (2026)](https://perfectnotes.org/notes/dbms/crash-recovery) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
