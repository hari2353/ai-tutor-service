# Agent Memory: Working, Episodic, Semantic, Procedural

> Sprint weekend 4 · source: `curriculum/07-agentic-ai/10-agent-memory.md`

```
FOUR TYPES (name all four, then differentiate)
  WORKING     = the prompt. volatile. re-sent every turn. bounded by window.
  EPISODIC    = past runs (task_sig, plan, OUTCOME, cost). append-only. TTL 30-90d.
  SEMANTIC    = facts (subject, predicate, value). upsert+supersede. months.
  PROCEDURAL  = rules/skills. files in git. biggest blast radius when wrong.
  different write path · retrieval key · decay rate · blast radius → different stores

WORKING MEMORY LADDER
  buffer O(n²) cost · window O(k) forgets · summary O(1) drops IDs/dates first
  → HYBRID: summary(old) + last-k verbatim + PINNED <state> block (IDs, obligations)
  → + externalise long artefacts to files; pinned block is never summarised

WRITE POLICY (default is NOOP)
  gate: "changes a FUTURE UNRELATED answer?" · conf >= 0.7 · no system-of-record facts
  target < 1 durable fact / 10 turns · hard per-user cap (200-500) forces eviction
  decisions: ADD / UPDATE(supersede) / DELETE / NOOP

RETRIEVAL RANK (say the formula)
  0.55·cosine + 0.20·0.5^(age/half_life) + 0.15·importance + 0.10·log1p(hits)
  PREFILTER (tenant, valid_to IS NULL) INSIDE the ANN query, never after
  over-fetch 50 → rerank → floor 0.35 → per-predicate diversity → k<=8
  render as: [2026-03-04, conf 0.9] <fact>   ← dates+provenance make it debuggable

WHY NAIVE VECTOR RECALL FAILS (5)
  turns not self-contained · embeddings = topic not truth ("cancel" ~ "not cancel")
  precision collapses at volume · no temporal reasoning · injected = authoritative

FORGETTING (need >1 mechanism)
  class TTL: identity ∞ · stable_pref 365d · entitlement 30d · project 14d · task 0
  contradiction → close valid_to (NEVER hard overwrite) · decay in ranking
  capacity eviction on lowest score · hard delete only for user/GDPR, cascade derived

BI-TEMPORAL = event_time + ingestion_time + [valid_from, valid_to)
  updated_at alone loses out-of-order supersession and historical reconstruction

NUMBERS
  Mem0 LOCOMO: 66.9% vs 52.9% (26% rel) · p95 1.44s vs 17.12s · 1.8K vs 26K tok
  Zep: DMR 94.8 vs 93.4 · LongMemEval +18.5% acc, ~90% lower latency
  Anthropic 2025-09-29: memory+context editing +39% · context editing alone +29%
  context rot: 20-50% accuracy drop 10k→100k+ tokens across 18 frontier models
  LangMem still pre-1.0 (0.0.30) · ConversationBufferMemory deprecated LC v0.3.1

WHEN NOT TO
  single-session → summarised window is enough
  facts have a schema → use typed columns, not embeddings
  system of record exists → CALL THE API, never remember it
  regulated domain w/o provenance trail → don't persist
  graph before you have multi-hop query traces → premature

EVAL OR DON'T SHIP
  A/B memory on/off on CROSS-SESSION golden tasks + adversarial superseded-fact slice
  track: injected-memory precision (alert < 0.7) · tokens added/turn · writes/1k turns
```
