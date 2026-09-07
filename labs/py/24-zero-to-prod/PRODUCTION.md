# Production notes — zero → production

## What this lab is the skeleton of

Component-by-component, what a real production agent service adds:

| Lab part | Production version |
|---|---|
| FakeLLM | A real model behind a gateway: retries, fallback chains, prompt caching, streaming tokens |
| tools dict | Sandboxed executors (containers/WASM), JSON-Schema validation, capability tokens, per-tool rate limits |
| cost guard | Real metering from API usage fields; $ ceilings per run AND per workspace; budget alerts |
| error observations | Structured error taxonomy feeding the retry policy (retryable vs not — see lab 01) |
| checkpoint/resume | Postgres-backed checkpointer; resume across process death (lab 07) — the dict here is its toy form |
| events + validate | OTel spans with GenAI conventions; the invariants here become CI eval gates on golden trajectories |

## The deploy checklist this lab implies

1. Loop terminates under every stop condition — tested.
2. Tool failures never crash the run — they become observations — tested.
3. Cost is bounded and observable mid-run — tested.
4. A killed run resumes exactly where it stopped — tested.
5. The event log is self-consistent (validate()) — tested.

Everything else (authn, quotas, canary evals, dashboards) is infrastructure
around exactly these five guarantees.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Resumed run re-executes a tool | Snapshot taken before observation appended | Checkpoint after append; idempotent tools (lab 03) as belt-and-braces |
| Cost cap "trips" at 2x | Charged per turn not per call, or cap checked after the call | Reserve before, charge after |
| Events lie | Observations logged from a different turn than the call | validate() in CI on every golden run |
