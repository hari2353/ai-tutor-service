# Production notes — layered guardrails

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| PII detection | Presidio (`presidio-analyzer`) | NER + checksum validators; far past regex on names/addresses |
| Validator framework | Guardrails AI | Pydantic-shaped `Guard` with per-validator `on_fail` |
| Rail system | NeMo Guardrails | input/output/dialog/retrieval/execution rails, Colang flows |
| Managed cloud layer | Bedrock Guardrails / Azure Content Safety / Model Armor | Uniform + auditable, no framework context |

## What production adds over yours

- **Streaming retraction**: you cannot un-ship a token already streamed; production buffers sentences and retracts retroactively where the channel allows.
- **Fail-open ≠ free**: every `on_error: log` is an SLA decision — a PII scan failing open for five minutes during a deploy is a calculated risk, logged and alarmed.
- **Tool gates, not text gates**: the guard that matters most sits on the *action* (a refund tool with its own permission check), not the text — a jailbroken model with no refund tool cannot refund.
- **Canary rotation**: real canaries are per-session and rotated; a static one leaks once and is burned.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Guard latency dominates p99 | Seven synchronous classifiers in the input path | Parallelise, cache by content hash, move non-critical rails async |
| Redaction mangles JSON tool args | Regex ran over a serialized payload | Guard per modality — parse, then walk fields |
| False positives block every legit email | One classifier, one threshold, all traffic | Per-tenant thresholds + `fix`/`log` before `block` |
| `hydrate` leaks across users | Pseudonym map reused between requests | One `GuardState` per request, destroyed after render |

## The one-liner to remember

The model sees pseudonyms, the user sees reals, and the guard that matters
most is on the action — not the text.
