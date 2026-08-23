# Weekend 4 — Agent Memory, Context Engineering, Multi-Agent Topologies

This weekend decides interviews because "should this be multi-agent" and "how does your agent remember anything" are the two questions where reaching for the fashionable answer (yes, and a vector store) instead of the disciplined one (no, and a write policy) is the single clearest signal of seniority.

## Agent Memory: Working, Episodic, Semantic, Procedural

**30-sec:** The model is stateless, so "memory" is always a retrieval system you build, split four ways by *what* and *when*: working memory is the context window; episodic is what happened on past runs; semantic is durable facts; procedural is rules/skills. The hard part isn't storage, it's the **write policy** and **retrieval ranking** — naive vector search over past turns fails because dialogue isn't self-contained, embeddings encode topic not truth, and cosine similarity doesn't know a fact was superseded. Every design needs an answer to "how does a wrong memory die" (TTL, contradiction-triggered supersession, decay), because stale memory actively injects confident falsehoods. Most shipped "agent memory" is a structured user-profile row + a summary + last N turns — not a temporal knowledge graph.

**Four types, name all:** working (volatile, re-sent every turn) · episodic (append-only, TTL 30–90d) · semantic (upsert+supersede, months) · procedural (files in git, biggest blast radius when wrong).

**Working memory ladder:** buffer O(n²) → window O(k) forgets → summary O(1) drops IDs/dates first → hybrid: summary(old) + last-k verbatim + pinned `<state>` block (IDs, obligations), never summarised.

**Write policy default is NOOP.** Gate: does it change a future unrelated answer? Confidence ≥0.7. Target <1 durable fact per 10 turns, hard per-user cap forces eviction.

**Retrieval ranking formula:** `0.55·cosine + 0.20·0.5^(age/half_life) + 0.15·importance + 0.10·log1p(hits)`. Prefilter (tenant, valid_to IS NULL) *inside* the ANN query, never after.

**Forgetting needs >1 mechanism:** class-based TTL (identity ∞, stable_pref 365d, entitlement 30d, task 0) + contradiction closes `valid_to` (never hard overwrite) + decay in ranking + capacity eviction on lowest score.

**Bi-temporal:** event_time + ingestion_time + [valid_from, valid_to). `updated_at` alone loses out-of-order supersession.

## Context Engineering: Budgets, Compaction, Editing, Subagents

**30-sec:** Context is a budget with diminishing returns, not a buffer to fill. Attention is finite (n² pairwise cost, training skewed short) so accuracy degrades on a gradient well before the hard limit — Chroma measured 20–50% accuracy drops between 10k and 100k+ tokens across 18 frontier models. The counterintuitive core claim: **adding tokens usually makes an agent worse**. Four levers in order: truncate at the tool boundary, clear stale tool results, compact older turns into a structured recap (never touching task/constraints/IDs/open items), and isolate via subagents that burn tokens privately and return a distilled 1–2k summary.

**Cost arithmetic is quadratic:** `cumulative_input = turns·base + growth·turns(turns-1)/2`. 6k base + 4k/turn × 40 turns = 3.36M tokens; cutting growth to 1k/turn drops that to 1.02M for the same task. Keep the prefix byte-stable — cache read ≈0.1× input cost.

**Context editing (real API):** `clear_tool_uses_20250919`, trigger default 100k tokens, keep default 3 pairs. Alone: +29% and −84% tokens over a 100-turn task. Plus the memory tool: +39%.

**Compaction rules:** trigger at 55–65% (not 95% — the summary needs headroom), never mid tool_use/tool_result pair, verify mechanically (regex IDs must survive) or don't compact. Cap compactions per run (~4).

**Never compact (7):** task + success criteria, hard constraints, open obligations, identifiers/exact values, last user correction, pending tool call, approval/permission state.

**Subagents:** Anthropic research measured +90.2% vs single-agent Opus 4 at ~15× tokens. Return contract: Answer + Evidence(file:line/url) + Confidence + "not checked." Writes stay single-threaded.

## Multi-Agent Topologies (and When NOT To)

**30-sec:** Five topologies differ on two axes — who decides what happens next, and what context crosses the boundary. Supervisor centralises routing (visible trace). Hierarchical nests supervisors. Swarm/handoff is fast but hard to reason about. Blackboard removes messaging for shared state. Debate has mixed evidence. **The senior line: a single agent with good tools beats a poorly decomposed multi-agent system almost always** — decomposition adds routing errors, lossy handoffs, multiplied latency and cost, and a debugging surface where the failure is in the seam. Berkeley's MAST work (1,600+ traces, 7 frameworks) found dominant failure categories are system design and inter-agent misalignment — not model capability.

**The five costs (recite unprompted):** routing errors (0.92³≈78% success over 3 hops) · handoff loss (full history = no isolation; summary = undetectable loss) · latency multiplication (fan-out p50 ≈ branches' p90) · cost multiplication (~15× tokens of a normal chat) · debugging surface (failure lives in the seam).

**What justifies splitting (need ≥1):** parallel read-heavy subtasks with small returns · mandatory context isolation · different permission/trust tier · different model/latency tier · independent deployment ownership · untrusted content quarantine. **Not reasons:** 30 tools, the org chart, a tidy diagram.

**Debate specifically:** N agents × (R+1) rounds costs 2.1–3.4× tokens for ≈ or worse accuracy, with sycophantic conformity risk. Prefer self-consistency (independent samples + vote) or one verifier.

**Decision order:** one prompt → workflow/DAG → one agent (default) → fix tools/context → orchestrator + read-only subagents → add a verifier → prove with an eval.

## If you remember nothing else

1. "Memory" is always a retrieval system you build — name working/episodic/semantic/procedural and their different write paths, decay rates, and blast radii.
2. The default write policy is NOOP; write only what changes a future unrelated answer, at confidence ≥0.7.
3. More tokens usually makes an agent worse (Chroma: 20–50% accuracy drop 10k→100k+ tokens) — the job is the smallest high-signal set, not the largest.
4. Never compact the task, hard constraints, identifiers, or open obligations — everything else is fair game.
5. Context editing alone gives +29% and −84% tokens over 100 turns; adding the memory tool brings it to +39%.
6. A single agent with good tools beats a poorly decomposed multi-agent system almost always — MAST found failures are design issues, not model capability.
7. Multi-agent's real costs are routing errors, lossy handoffs, multiplied latency/cost, and a seam that's hard to debug — ~15× tokens for the Anthropic research system.
8. Splitting is justified by parallelism, isolation, or a trust boundary — never by tool count or an org chart.

## Numbers table

| Fact | Value |
|---|---|
| Chroma context degradation | 20–50% accuracy loss, 10k→100k+ tokens, 18 models |
| Effective window rule of thumb | ≈40–50% of nominal for mid-context recall |
| Context editing alone | +29% accuracy, −84% tokens (100-turn task) |
| Context editing + memory tool | +39% |
| Compaction trigger | 55–65% of window |
| Compaction cap per run | ~4 |
| Subagent token efficiency | ~50k spent privately → 1–2k returned (~30×) |
| Multi-agent research system perf | +90.2% vs single-agent, ~15× tokens |
| Routing error compounding | 0.92³ ≈ 78% success over 3 hops |
| Debate token cost | 2.1–3.4× for ≈/worse accuracy |
| Mem0 LOCOMO accuracy | 66.9% vs 52.9% baseline (26% relative) |
| Mem0 latency | p95 1.44s vs 17.12s |
| Episodic memory TTL | 30–90 days |
| Semantic write target | <1 durable fact / 10 turns |
