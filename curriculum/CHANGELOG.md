# AI-stack curriculum changelog

Newest first. Each entry: what changed, why it matters for an interview answer, source, access date.

---

## 2026-08-09
Window: 2026-07-26 → 2026-08-09 · first run (runs was 0)

### MCP spec 2026-07-28 — final release, supersedes 2025-11-25
The Model Context Protocol specification shipped its 2026-07-28 revision as final. This is a large, breaking change to the protocol core:
- **Stateless core**: the `initialize`/`notifications/initialized` handshake and the `Mcp-Session-Id` header are gone. Every request now carries its own protocol version and client capabilities in `_meta`. A new `server/discover` RPC lets a client ask a server what it supports before making any other call.
- **Subscriptions redesigned**: the HTTP GET endpoint and `resources/subscribe`/`resources/unsubscribe` are replaced by a single long-lived `subscriptions/listen` stream that clients opt into per notification type.
- **Removed**: `ping`, `logging/setLevel`, `notifications/roots/list_changed`, SSE stream resumability (`Last-Event-ID`).
- **Deprecated (12-month window)**: Roots, Sampling, and Logging features; the HTTP+SSE transport; OAuth Dynamic Client Registration (replaced by Client ID Metadata Documents).
- **New pattern**: Multi Round-Trip Requests (MRTR) — servers return `InputRequiredResult` (`resultType: "input_required"`) instead of issuing server-initiated requests like the old `sampling/createMessage`; the client retries the original call with `inputResponses`.
- Servers **SHOULD** now return `tools/list` in deterministic order (helps LLM prompt-cache hit rates), and results carry `ttlMs`/`cacheScope` for client-side caching.

**Why it matters:** any existing answer describing MCP's session lifecycle via `initialize`/`Mcp-Session-Id`, or describing Sampling/Roots as the way a server asks the client for help, is now describing a deprecated or removed mechanism. ([src](https://modelcontextprotocol.io/specification/2026-07-28/changelog)) — accessed 2026-08-09

Patched: `curriculum/07-agentic-ai/04-mcp-deep-dive.md`

### LangGraph 1.0 — general availability
LangGraph reached its first stable 1.0 major release after over a year of production use (Uber, LinkedIn, Klarna cited as adopters). The only breaking change is deprecation of `langgraph.prebuilt`, with prebuilt agent helpers moving to `langchain.agents`; durable execution (the `exit`/`async`/`sync` durability modes) and checkpointing are now GA-supported, not preview. ([src](https://changelog.langchain.com/announcements/langgraph-1-0-is-now-generally-available)) — accessed 2026-08-09

Patched: `curriculum/07-agentic-ai/06-langgraph-core.md`, `curriculum/07-agentic-ai/07-langgraph-durable.md`

### OpenTelemetry GenAI semantic conventions — still not stable
As of this pass, no `gen_ai.*` span, event, metric, or attribute is marked Stable. The `gen_ai.*` conventions were moved (v1.42.0, 2026-06-12) out of the main OpenTelemetry semantic-conventions repo into a dedicated GenAI-conventions repo — an organizational split, not a stability graduation. No committed stabilization timeline exists as of 2026-07-17. ([src](https://john-hodge.com/blog/opentelemetry-genai-semantic-conventions/)) — accessed 2026-08-09

Patched: `curriculum/08-eval-observability/05-otel-genai.md`

### Frontier model releases
- **Claude Opus 5** (Anthropic) — tuned for agentic coding and cybersecurity work; GA on Amazon Bedrock and Azure Databricks AI Model Serving within days of each other. ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-july-27-2026/)) — accessed 2026-08-09
- **GPT-5.6 pricing cut on Amazon Bedrock** — effective July 30: Luna variant -80% ($0.20/M input, $1.20/M output tokens), Terra variant -20%. ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-price-reduction-of-gpt-models-in-bedrock-cloudwatch-managed-collectors-for-prometheus-metrics-and-more-august-3-2026/)) — accessed 2026-08-09
- **Gemini 3 Flash / Gemini 3.1 Flash Image** — public preview on Gemini Enterprise Agent Platform (the post-rebrand name for Vertex AI's generative AI services). ([src](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes)) — accessed 2026-08-09

Patched: `curriculum/26-frontier-ai/10-frontier-landscape.md`

### Vertex AI → Gemini Enterprise Agent Platform (rebrand confirmation)
Vertex AI's dedicated release-notes page is now frozen ("no longer being updated"); Google directs all new AI-platform documentation to Gemini Enterprise Agent Platform. Treat "Vertex AI" as the legacy brand name for the same underlying service in any answer going forward — GCP release notes from this window already use "Gemini Enterprise Agent Platform Model Garden" as the standard term (e.g. API Gateway model-routing feature, 2026-08-03). ([src](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes)) — accessed 2026-08-09

Patched: `clouds/gcp/07-ai.md` (cloud-side page; noted here because it affects any curriculum cross-reference to "Vertex AI")

### Not yet material this window
- **PyTorch**: 2.10 shipped 2026-01-21 (Python 3.14 support for `torch.compile`, reduced Inductor kernel-launch overhead, `varlen_attn()`); 2.9 is slated for October 2026. Neither lands inside this run's window — noted for the next pass.
- **transformers / peft / trl**: TRL 1.8.0 shipped 2026-07-09 (GRPOTrainer per-example environment selection, KTOTrainer graduated to stable API) — just outside the 2026-07-26 watermark, carried forward for the next run.
- **vLLM**: production-scale Kimi K3 support (KDA-aware prefix caching, fused kernels, optimized MXFP4 MoE) shipped 2026-07-22 — also just outside the watermark.
- **RAGAS / DeepEval / Langfuse**: no dated, verifiable release found in this window that changes an evaluation-framework answer; RAGAS's own commit cadence has visibly slowed (last default-branch commit noted as 2026-02-24 by a third-party comparison, unverified against the repo directly) — worth checking directly next run rather than trusting the secondhand claim.
