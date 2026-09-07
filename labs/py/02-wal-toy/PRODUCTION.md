# Production notes — WAL & ARIES recovery

## What you'd actually use

| Your piece | Real thing | What it adds over yours |
|---|---|---|
| WAL append + fsync per record | Postgres `pg_wal/` (16 MB segments), InnoDB redo (`#innodb_redo/`), SQL Server transaction log | segment rotation, preallocation, checksums; group commit so N txns share one fsync |
| LSN per record | Postgres WAL byte offset as LSN; every heap page stores `pd_lsn` | pageLSN comparisons are byte offsets, not sequence numbers — same rule, finer granularity |
| BufferManager + pageLSN | Postgres shared buffers, InnoDB buffer pool, all with per-page LSN/dirty tracking | clock/LRU eviction with writeback, `full_page_writes` torn-page protection, background writeback throttling |
| `recover()` three passes | ARIES (Mohan et al. 1992) — the direct ancestor of Postgres/InnoDB/SQL Server/Oracle crash recovery | checkpoints bound the redo window; Dirty Page Table min-recLSN starts redo; physiological logging (page+undo info, not raw bytes) |
| CLR during undo | real CLRs with `undoNextLSN` pointers | a crash mid-undo resumes exactly where it stopped — your CLR is the same idea |
| `crash()` = drop buffers | real crashes: power pull, kernel panic, `kill -9` keeps OS page cache! | production durability drills literally pull power — `kill -9` tests nothing about fsync |

The systems to name in interviews: **Postgres WAL** (and `fsyncgate` — the 2018 Linux bug where a failed fsync's error state was cleared, so a later fsync reported false success; Postgres now PANICs on fsync failure), **ARIES** (the 1992 paper every RDBMS descends from), **InnoDB** `innodb_flush_log_at_trx_commit` (1 = fsync per commit, 2 = write per commit + fsync/sec, 0 = ~1s regardless — the classic durability knob).

## What the real ones add over yours

- **Group commit.** fsync latency is per-*call* (~0.1-1 ms NVMe, 5-10 ms spinning disk), not per-byte. Batching N transactions into one fsync is an order-of-magnitude throughput win at high concurrency — the most-tested production detail in this area.
- **Checkpoints bound recovery time.** Postgres runs one every `checkpoint_timeout` (5 min) or `max_wal_size`, spread via `checkpoint_completion_target` (0.9). Without them, redo replays the entire history — a 45-minute recovery after a crash, the interview question.
- **`synchronous_commit=off` is a real choice.** It acks before fsync: you can lose the last ~200 ms of commits on OS crash. Correct for many workloads, wrong for ledgers — the tradeoff interviewers want you to reason through.
- **Torn-page protection.** A crash mid-page-write leaves a page half-old/half-new; Postgres's `full_page_writes` logs the entire page on first touch after each checkpoint so redo restores a known-good full page. Cost: WAL volume spikes right after every checkpoint.
- **Log truncation rules.** A record can be dropped only if no page's recLSN and no replica/backup still needs it — the #1 cause of "WAL filled the disk" is a stalled replication slot retaining segments nobody consumes.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Acked commits missing after crash | fsync lied (volatile disk cache, virtualization, fsyncgate-class bug) | battery/cap-backed cache or verified cloud durability; PANIC on fsync failure rather than retry |
| WAL directory grows until disk-full | stalled replication slot retaining segments | alert on slot lag/WAL bytes trend, not just disk usage |
| Recovery takes longer than the SLA | checkpoint interval too long | shrink `checkpoint_timeout`/`max_wal_size`; checkpoint I/O isn't starved by foreground |
| Commit throughput low under concurrency | fsync-per-commit, no group commit | enable/widen the group-commit batch window |
| Torn-page corruption after crash | `full_page_writes` off | keep it on absent atomic-page hardware guarantees |
| Undo "hangs" after repeated crashes during recovery | undo not itself logged | CLRs with `undoNextLSN` — the exact bug your lab's CLR prevents |

## The 3 questions an interviewer asks after you describe this

1. *"Why must the log record hit disk *before* the page?"* — if the page arrives first and the crash hits before the log record, disk holds a change nothing explains: recovery can neither reconstruct nor roll it back. Log-first means recovery always has the complete history to reason from.
2. *"Why does redo replay uncommitted transactions too?"* — "repeat history" is deliberately blind: deciding what's "needed" would require the very state being reconstructed. Redo restores the exact pre-crash instant; undo then removes the losers' partial work.
3. *"Why is undo itself logged?"* — a crash during recovery's own undo would otherwise restart it from scratch, repeating or skipping compensations. CLRs record what's already undone so any number of crashes converges on completion. (This is the detail most implementations miss — it's why your recovery-idempotency test exists.)
