# Weekend 7 — Database Internals and Evaluation

This weekend decides interviews because MVCC/isolation and the query planner are where candidates either demonstrate they've read `EXPLAIN ANALYZE` output for real, or reveal they've only memorised isolation-level names — and LLM/agent eval is the parallel skill for anything non-deterministic, which is now most of what gets shipped.

## MVCC vs Locking, Isolation Levels, Every Anomaly, Write Skew

**30-sec:** MVCC lets readers never block writers by keeping multiple row versions and giving every transaction a consistent snapshot, instead of 2PL where shared/exclusive locks actually block each other. Postgres implements this with `xmin`/`xmax` and a visibility rule. The catch: snapshot isolation — what people loosely call "MVCC" — prevents dirty reads, dirty writes, and read skew, but **not write skew**, because two transactions can each read a stale-but-consistent snapshot, decide independently, and write to different rows in a way that jointly violates an invariant neither write alone violated. True serializable isolation (Postgres: SSI) is required whenever an invariant spans rows that concurrent transactions might each read-then-write.

**Visibility rule:** a row version is visible if its creator committed before your snapshot and it wasn't deleted by a transaction committed before your snapshot. Read Committed takes a new snapshot per statement; Repeatable Read/Serializable take one for the whole transaction.

**Anomalies, all six:** dirty read · dirty write · read skew (same row, two reads, different answers) · phantom (predicate result set changes mid-txn) · lost update (same-row read-modify-write clobbers) · write skew (different rows, disjoint writes jointly break an invariant).

**Level→anomaly table:** Read Committed prevents dirty read/write only. Repeatable Read adds read-skew prevention. Snapshot Isolation (Postgres's "Repeatable Read") adds phantom + lost-update prevention — write skew still possible. Serializable prevents everything.

**Defaults:** Postgres/Oracle/SQL Server → Read Committed. MySQL/InnoDB → Repeatable Read. Gotcha: Oracle's "Serializable" is actually snapshot isolation — write skew still possible.

**Fix write skew:** `SELECT ... FOR UPDATE` on invariant-backing rows, or an atomic conditional `UPDATE ... WHERE cond`, or run at true Serializable (costs retry rate + SIREAD overhead).

## Parse→Plan→Cost→Execute, Join Algorithms, EXPLAIN ANALYZE

**30-sec:** A query goes parse → rewrite → plan enumeration → cost estimation → execute, and the result quality depends entirely on step four: the planner picks the cheapest-*looking* plan, only as good as its statistics. Nested loop wins when one side is tiny/indexed, hash join wins on large unsorted equi-joins, merge join wins when both sides are already sorted on the join key. `EXPLAIN ANALYZE` shows estimated vs actual rows at every node — when they diverge by 10× or more, everything above that node is operating on wrong assumptions, and the plan *shape* is usually wrong, not just its cost.

**Postgres cost constants:** seq_page_cost 1.0, random_page_cost 4.0 (lower to 1.1–2.0 on SSD), cpu_tuple_cost 0.01.

**Stats:** MCV list + histogram + null fraction + n_distinct per column. Independence assumption multiplies per-predicate selectivity — wrong on correlated columns, fix with `CREATE STATISTICS`.

**Join complexities:** nested loop O(N×M) or O(N log M) with index. Hash join O(N+M), builds on the smaller side. Merge join O(N+M) if pre-sorted, else + sort cost.

**Fix order:** EXPLAIN ANALYZE first, always → estimate wrong? fix stats before adding indexes → estimate right but no access path? add the index → still slow? check query shape (function-wrapped predicates defeat index use).

**GEQO:** Postgres switches from exhaustive plan enumeration to a genetic algorithm past `geqo_threshold` (default 12 tables) — no longer guaranteed-optimal join order.

## LLM-as-Judge and Its Failure Modes; Judge Calibration

**30-sec:** LLM-as-judge is the only way to eval free-text generation at production volume, but the judge has the failure modes of the thing it's judging plus new ones: position bias (swapping answer order flips 10–15pp of win rate), verbosity bias (15–30pp preference for longer answers regardless of quality), self-preference (a model scores its own family 10–25% higher). This doesn't mean don't use it — it means calibrate against human labels before trusting it, report agreement via Cohen's kappa/Krippendorff's alpha, and re-calibrate on any rubric or judge-model change.

**Calibration procedure:** 100–300 real traces → 2–3 humans label, same rubric → compute inter-annotator agreement → judge scores same traces → judge-vs-human kappa. Thresholds: <0.4 rubric ambiguous, 0.4–0.6 weak, >0.6 ship, >0.8 strong.

**Mitigations:** position bias → run both orderings, flip = tie. Verbosity → explicit rubric line + length-bucketed analysis. Self-preference → judge from a *different* model family than any candidate.

**Red flag:** judge-vs-human kappa suspiciously high (>0.9) → audit for collusion on a superficial correlate.

## Trajectory Eval, Tool-Call Accuracy, Task Completion, Cost/Step

**30-sec:** Outcome-only eval is insufficient for agents — an agent can reach the right answer via a path that fails tomorrow (wrong tool, lucky retry, 10× budget burn). Real agent eval scores the trajectory across four layers: tool-call accuracy, trajectory match against golden calls, task completion vs *actual state* (never the agent's own summary), and cost/steps per task. Frontier agents on realistic multi-turn benchmarks (tau-bench) succeed on well under half of tasks and are inconsistent across retries on the *same* task — treat results as a distribution, not pass/fail.

**Nondeterminism:** pass@1 = success in ≥1 of k tries (optimistic). pass^k = *all* k tries succeed (honest reliability). Reported gap: pass^1 ~70–80% → pass^8 <25% on tau-bench retail tasks. Run N≥3–5 repeats before calling anything a regression.

**CI gates:** hard-gate deterministic checks; statistical-gate judge-based checks on a drop across a run-set, not one trace; pin agent *and* judge model versions; quarantine known-flaky tasks.

## If you remember nothing else

1. Snapshot isolation (Postgres's "Repeatable Read") prevents phantoms and lost updates but *not* write skew — the classic interview trap.
2. Fix write skew with `SELECT ... FOR UPDATE`, an atomic `UPDATE ... WHERE`, or true Serializable — know all three options.
3. Oracle's "Serializable" is snapshot isolation, not true serializable — write skew still possible.
4. `EXPLAIN ANALYZE` divergence of 10×+ between estimated and actual rows means the whole plan above that node is built on a false premise.
5. Fix statistics before adding an index — a bad estimate isn't fixed by more indexes.
6. LLM judges carry position bias (10–15pp), verbosity bias (15–30pp), and self-preference (10–25%) — calibrate against humans before trusting any judge score.
7. Outcome-only agent eval misses paths that succeed by luck — trajectory eval (tool calls, argument correctness, actual end-state) is what's real.
8. pass^k (all k tries succeed) can be <25% even when pass@1 looks fine at 70–80% — report the honest number, not the optimistic one.

## Numbers table

| Fact | Value |
|---|---|
| Postgres random_page_cost default / SSD-tuned | 4.0 / 1.1–2.0 |
| Postgres geqo_threshold | 12 tables |
| EXPLAIN ANALYZE divergence red flag | 10×+ estimated vs actual rows |
| Join complexities | nested loop O(N×M); hash/merge O(N+M) |
| LLM judge position-bias swing | 10–15pp |
| LLM judge verbosity-bias swing | 15–30pp |
| LLM judge self-preference | +10–25% |
| Calibration kappa thresholds | <0.4 bad, 0.4–0.6 weak, >0.6 ship, >0.8 strong |
| Judge calibration sample size | 100–300 traces |
| tau-bench pass@1 → pass^8 | ~70–80% → <25% |
| Minimum eval repeats before calling a regression | N ≥ 3–5 |
