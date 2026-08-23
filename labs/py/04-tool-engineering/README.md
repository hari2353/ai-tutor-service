# Lab 04: Tool Engineering From Scratch

**Track:** T07 Agentic AI · **Time:** 2h · **XP:** 50
**Module:** `T07-tool-engineering`

**You will build:** the tool-boundary primitives the module keeps insisting on: a json-schema-lite `ToolSpec`, a `ToolRegistry` whose errors are observations instead of exceptions, an `IdempotencyLedger` with TTL'd keys on an injectable clock, and a `retryable` wrapper that retries only what is safe to retry.

**You will be able to answer:** *"Why must a tool registry validate before it executes — and how do you make a mutating tool safe to retry?"*

## Setup

```bash
cd labs/py/04-tool-engineering
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`ToolSpec(name, description, parameters, fn)`** — json-schema-lite validator: top level `{"type": "object", "properties": {...}, "required": [...]}`; per-property `type` (`string|integer|number|boolean|array|object|null`) and optional `enum`. `validate(args)` returns a list of readable problems; empty list == valid. **Strict:** any key absent from `properties` is an error. Guard the Python trap: `bool` subclasses `int`, so a boolean must not satisfy `integer`/`number`.
2. **`ToolRegistry`** — `register(spec)` raises `DuplicateToolError` on a repeated name. `dispatch(name, args)` NEVER raises for caller mistakes: unknown name → `{"error": "unknown_tool", "details": [...]}`; failed validation → `{"error": "invalid_args", "details": [...]}` — computed **before** the tool runs, so a malformed call costs zero side effects; success → `{"ok": True, "result": ...}`, with args passed as a copy.
3. **`IdempotencyLedger(ttl, clock)`** — `execute(key, fn, *a, **kw)` returns `Outcome(result, replayed)`. Same **live** key → cached result, `replayed=True`, fn does not run again. Distinct keys execute independently. Entries expire after `ttl` on the injected `Clock` (lazy eviction plus `purge()`), after which the key executes fresh. Only successes are cached; a raising fn leaves no trace.
4. **`retryable(fn, attempts, retry_on, sleep, base_delay)`** — retries only on the `retry_on` tuple, sleeping `base_delay * 2**attempt` between tries **through the injected sleep callable** (tests pass `FakeClock.sleep`; nothing calls `time.sleep()` directly). Exhausted → `RetriesExhausted(attempts, last)`, chained `from last`, carrying `.last`. Anything outside `retry_on` propagates immediately and unslept. Wrapper records `.attempts_used`.

Nothing here may call `time.monotonic()` or `time.sleep()` directly except `SystemClock` and the default `sleep` argument — injectability is the whole point. *(Tests that sleep are broken tests.)*

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Harness-supplied idempotency keys** — `dispatch(..., idempotency_key=...)` routing through a ledger, deriving keys deterministically from execution identity: `f"{run_id}:{step}:{name}:{hash(args)}"`. *(Interview: why must the harness, not the model, supply the key?)*
2. **Confusable-name lint** — refuse registration of name pairs above ~0.90 `difflib.SequenceMatcher` ratio; near-identical names are a top cause of wrong-tool selection.
3. **Risk tiers** — a `tier` field on `ToolSpec`; the dispatcher refuses `financial`/`destructive` without an approval token, and an *unclassified* tool defaults to `destructive`. Fail closed.
4. **In-flight dedup** — two concurrent `execute` calls on one live key currently both miss and both run; fix it with per-key locks or futures. *(This is the hard case: 409-and-back-off or block on the key.)*
