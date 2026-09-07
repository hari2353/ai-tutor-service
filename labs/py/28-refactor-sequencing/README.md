# Lab 28: Large-Scale Refactors — Sequenced, Batched, Checkpointed

**Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2.5h · **XP:** 50
**Module:** `T28-agentic-refactor`

**You will build:** a refactor sequencer — dependency graph → deterministic topological order → size-capped batches where every file lands strictly after its imports → a strangler-fig cutover plan → checkpoints that tell you exactly what to revert, and when it is too late.

**You will be able to answer:** *"You're replacing 40 files in a live system. Walk me through the order, the batching, and what happens when batch 7 fails mid-flight."*

## Setup

```bash
cd labs/py/28-refactor-sequencing
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`build_change_graph(files, imports)`** — `files: list[str]`, `imports: {file: [imported filenames]}`. Return `{file: [its imports]}`, keeping only imports that are in `files`. Raise `RefactorCycleError` if the graph contains a cycle (DFS).
2. **`safe_order(graph)`** — topological order via Kahn's algorithm: dependencies before dependents. Deterministic: sort ready nodes by name at every step.
3. **`batch(order, graph, max_batch_size)`** — split `order` into batches of at most `max_batch_size` where each file lands strictly after all its imports' batches. Greedy: give each file (in `order`) the earliest batch that has room and is strictly after every import's batch.
4. **`StranglerPlan(old_files, mapping)`** — `old_files` is the change graph over the old files; `mapping: {old_file: new_file}`. `phases()` returns `{"phase": "parallel_run", "files": [all new files, sorted]}`, then one `{"phase": "cutover", "files": [its new file]}` per old file in dependency order (dependencies cut over first, dependents last), then `{"phase": "cleanup", "files": [all old files, sorted]}`.
5. **`checkpoint(plan_state, batch_index)`** — snapshot dict taken before applying batch `batch_index` (0-based).
6. **`can_rollback(cp, current_batch)`** — `True` iff `current_batch <=` the checkpoint's batch: nothing later than the checkpoint has started.
7. **`rollback(cp, batches)`** — the files changed after the checkpoint: flatten every batch past the checkpoint's index.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Batches as a DAG of PRs** — emit one PR per batch with `depends-on` links; CI refuses to merge a PR before its parents. *(Interview: "how do you enforce merge order without a human gate?")*
2. **Blast-radius sizing** — weight files by ownership, traffic and test coverage instead of count: batch 1 might be 3 files, batch 9 might be 25.
3. **Traffic-shaped cutover** — extend `StranglerPlan` with per-phase rollout percentages (1% → 10% → 100%) and make `can_rollback` aware of exposure, not just batch index.
4. **Replan after failure** — given the rollback list and the graph, compute the smallest set of batches that must be redone (re-topo-sort over the affected subgraph only).
