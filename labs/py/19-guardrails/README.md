# Lab 19: Layered Guardrails From Scratch

**Track:** T07 Agentic AI · **Time:** 2h · **XP:** 50
**Module:** `T07-guardrails`

**You will build:** the guard pipeline every production agent runs —
input guards (PII redaction with reversible pseudonymisation, jailbreak
detection), output guards (JSON schema validation, system-prompt canary),
per-guard fail policies (`block` / `fix` / `log` / `escalate`) with the
fail-open-vs-fail-closed decision made explicit per guard, and a hydrate
step that restores real values exactly once at render time.

**You will be able to answer:** *"A guardrail itself throws an exception
mid-request. What happens?"* — and why the answer differs for a PII scan
vs a jailbreak detector.

## Setup

```bash
cd labs/py/19-guardrails
pip install pytest                                # only dependency
```

## The spec

1. **`redact(text, st)`** — replace SSN / card / email matches with
   deterministic tokens (`<ssn:0>`); the pseudonym map is keyed by token
   and never enters the audit trail.
2. **`jailbreak_stub(text, st)`** — marker-based detector (the stub you
   swap for a classifier in production).
3. **`has_canary(text, st)`** — system-prompt leak detection.
4. **`schema_ok(text, st)`** — structured output: parseable JSON with
   required keys.
5. **`run_guards(text, guards, st)`** — the engine. A guard that returns
   a reason is a violation (apply `on_violation`); a guard that THROWS
   is an error (apply `on_error`). `fix` reruns the guard, `block` raises,
   `escalate` demands a human, `log` records and continues.
6. **`hydrate(text, st)`** — restore real values for tokens, exactly once,
   at render — never inside the model loop.
7. **`handle(user_msg, agent)`** — the whole pipeline: input guards →
   agent (sees pseudonyms only) → output guards (pre-hydration, so the
   leak scan sees what will actually ship) → hydrate.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Streaming** — guards on partial chunks with an async retraction path.
2. **Per-guard latency budget** — `cost_ms` accounting against a cap.
3. **Real Presidio** — swap the three regexes for the actual NER engine.
