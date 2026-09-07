# Production notes — sequenced large-scale refactors

## What you'd actually use

| Layer | Tool |
|---|---|
| Ordering | `depends-on` in CI (GitHub required workflows, GitLab DAG pipelines) — topology enforced by the merge queue, not the reviewer |
| Batching | One PR per batch; bots (merge queue, bors) merge in dependency order |
| Cutover | Feature flags (LaunchDarkly, OpenFeature), traffic shifting (Envoy/Istio weighted routing) |
| Rollback | Migrations that expand/contract (parallel-change), flag kill-switch, DB-backed config |

## The strangler fig (Fowler)

Grow the new system around the old. Traffic flows to new code while old code still exists; cutover one slice at a time; delete old code only when the last slice is over. The lab's `parallel_run → cutover... → cleanup` phases are the pattern in miniature. The point interviewers probe: **the two systems coexist**, so every phase must be independently shippable and independently reversible.

## What the real thing adds over yours

- **The change graph is inferred, not hand-written** — import analysis from the language server or tooling (JS: `madge`, `dependency-cruiser`; Python: `grimp`, import-linter), so the graph can't drift from reality.
- **CI gates per batch** — a batch PR merges only with green tests, benchmarks and (for the AI-assisted loop) a review threshold. Batch 2 rebases onto batch 1: failures surface at the seam, not in prod.
- **Feature flags / traffic shifting in production** — cutover isn't a deploy, it's a config flip: 1% of traffic, watch error budget, ramp. Reverting a bad cutover is a kill-switch, not a redeploy.
- **Rollback as a first-class artifact** — the plan emits a runbook per phase: what to flip, what to delete, what the validation signal is. `can_rollback` in the lab is boolean; in production it's "how much traffic already saw the new path".

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Merge order violated despite the plan | Humans bypass CI | The merge queue is the only merge path; `depends-on` makes CI the enforcer |
| Batch 3 blocked on a flaky batch-2 test | Gates not isolated per batch | Batch-local test selection; don't re-run the world for every batch |
| Cutover "done" but old path still takes traffic | Flag cleanup forgotten | Track flag ownership + a sunset date; the cleanup phase is on the calendar the day cutover ends |
| Rollback plan is a wiki page from months ago | No rehearsal | Rollback must be exercised (game days) and generated with the plan, not written after |
| One batch is 3 quiet files; another is 30 hot ones | Count-based batching | Weight by ownership, traffic, and test coverage (see stretch goal 2) |

## Cost & latency

The sequencing itself is a build-time concern (your Python runs in milliseconds; a topo sort over 10k nodes is trivial with a heap-based Kahn — your `ready.sort()` is O(n log n) per step, fine here, a heap in real tooling). The cost is in wall-clock calendar time and the discipline overhead: roughly 1.2× the engineering time of the big-bang rewrite, in exchange for a risk profile that never has "all paths broken at once" as a state. In an interview, that trade — calendar time for reversibility — is the argument to make.

## The 3 questions an interviewer asks after you describe this

1. *"What if two batches conflict between planning and merge?"* — the graph is rebuilt from the actual code at each batch PR; drift detected is drift fixed, not a plan failure.
2. *"How do you know cutover is safe before flipping?"* — parallel run with shadow traffic and diffed outputs; the new path proves itself on real requests before it takes them.
3. *"Batch 7 failed and you're rolled back — now what?"* — the affected subgraph gets re-planned and re-sequenced as a delta, not the whole migration (see stretch goal 4).
