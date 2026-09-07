# Production notes — tool engineering

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Schema validation | Pydantic / jsonschema | Your lite spec maps to JSON Schema; validate at the boundary |
| Idempotency keys | Redis / DynamoDB with TTL | The ledger becomes a real store — same TTL'd-key shape |
| Retries | Tenacity with `retry_if_exception_type` | Retrying only the retryable is the whole point |
| Tool protocol | MCP (Model Context Protocol) | The registry becomes a server; clients discover tools by schema |

## What production adds over yours

- **Permission resolution**: every tool call passes a risk-tier check (read → reversible → destructive); the registry denies before dispatch, not after.
- **Rate limiting per tool**: a tool that fans out to a vendor API carries its own limiter — the agent's loop budget doesn't protect the vendor.
- **Timeouts as first-class**: each tool has a wall-clock cap and its own timeout policy; the ledger records cancelled vs completed vs orphaned.
- **Observability**: every dispatch logs tool, args-hash, latency, outcome — the args-hash (not raw args) is what keeps PII out of traces.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Duplicate side effects | Retried non-idempotent tool | Idempotency key BEFORE dispatch (lab's ledger) |
| "Write-file tool" wipes config | One generic tool, no risk tiers | Split tools by blast radius; ask for destructive ones |
| Tool errors never reach the model | Exceptions escape the loop | Errors-as-observations — the model can correct only what it sees |
| Registry sprawl — 60 tools, model picks wrong ones | Flat namespace | Group + curate; retrieval over tool descriptions for large sets |

## The one-liner to remember

The tool boundary is a distributed-systems boundary: idempotency keys,
retries classified by safety, errors as observations — the model is just
an unreliable client of your tools.
