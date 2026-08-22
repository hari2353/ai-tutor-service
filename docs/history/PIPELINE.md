# Content Generation Pipeline — model-routed, chunked, reviewable

> Plan v1 · 2026-07-26, burn-down refreshed 2026-08-01 · **256 modules remaining of 401**
> The live number is always in `CONTENT-STATUS.md`, which regenerates on every build. This header will drift; that file will not.
> Orchestrator: Opus. Workers: Sonnet + Haiku. Review gate: Opus.

---

## 0. The routing principle

Route by **cost of being wrong**, not by volume.

| Model | Gets | Why |
|---|---|---|
| **Opus** (orchestrator, me) | Judgment-heavy modules · every `lineage` section that requires synthesis · anything where current-facts accuracy decides correctness · all "when NOT to use this" sections · system design · the final review gate | These are the sections that make you sound senior or get you rejected. A confidently wrong tradeoff claim is worse than no module. |
| **Sonnet** | The bulk of established technical material: DSA patterns, GoF patterns, database internals, networking, Docker/K8s, Rust, Go, testing, quantum, blockchain, RL math | Well-settled material with a clear format. Needs competence and care, not novel judgment. Sonnet is strong here and ~5× cheaper. |
| **Haiku** | Mechanical transforms only: flashcards from a written cheat card · drill sets from written interview questions · cheat-sheet extraction · cross-link insertion · index/changelog updates · `build_data.py` reruns | Deterministic-ish work with a written source of truth already in hand. Near-zero failure cost, very fast. |

**Hard rule:** Haiku never writes a module from scratch. It only transforms text that already passed review.

**Hard rule:** every Sonnet-written module gets an Opus review pass against a checklist before it counts as written.

---

## 1. Chunking

One agent task = **one weekend (3–4 modules) or one track section**. Not one module (too much cold-start overhead per unit of work) and not one whole track (context blows out, quality sags at the tail).

Each agent task receives:
- the exact module ids and titles from `app/data/curriculum.json`
- the house format spec (from the `tutor-deepdive` skill)
- the two written exemplars as the quality bar
- an explicit instruction to `WebSearch` for anything version-dependent, and to cite with access dates
- the flashcard/drill output contract

---

## 2. Waves

### Wave 1 — the sprint (30 modules, 10 tasks) ← **this is the one that matters**

| Task | WE | Modules | Model |
|---|---|---|---|
| 1.1 | 1 | ReAct raw *(agent loop + resilience already written)* | Opus — reasoning-pattern nuance |
| 1.2 | 2 | LangGraph I, LangGraph II, Tool engineering | Opus — checkpointer/durability claims must be current |
| 1.3 | 3 | Chunking, Vector index internals, Hybrid search, Latency/accuracy triangle | Sonnet + Opus review |
| 1.4 | 4 | Context engineering, Agent memory, Multi-agent topologies | Opus — heaviest judgment content in the curriculum |
| 1.5 | 5 | Attention, Inference serving, Distributed fundamentals | Sonnet + Opus review |
| 1.6 | 6 | Design method, Estimation, Diagramming | Opus — this is craft, not facts |
| 1.7 | 7 | LLM-as-judge, Agent eval, MVCC, Query planner | Sonnet + Opus review |
| 1.8 | 8 | Resume systems, STAR bank, Design communication, Company-specific | **Opus only** — built from your actual resume, cannot be delegated |
| 1.9 | 9 | Zero→production capstone, 20 GenAI designs | Opus |
| 1.10 | 10 | Harness engineering, Loop engineering, Claude architect | Opus — you asked for these specifically |

Plus 10 Haiku follow-up tasks: flashcards + drills + cheat sheets for each weekend once its modules pass review.

**Wave 1 output:** ~32 modules, ~450 flashcards, 10 cheat sheets, and the sprint fully readable end to end.

### Wave 2 — Phase A core (≈100 modules, ~28 tasks)
DSA 21 patterns + 5 graph modules (Sonnet, 3 langs each) · Networking & protocols (Sonnet) · Auth & appsec (Sonnet, Opus for the JWT-attack module) · Data engineering + EMR (Sonnet) · Testing (Sonnet) · Docker/K8s/debugging (Sonnet) · AI-assisted architecture (Opus) · AWS atlas (Sonnet) · remaining RAG and agentic modules (mixed).

### Wave 3 — Phase B depth (≈130 modules, ~35 tasks)
Computer systems (Sonnet) · Python/SWE craft (Sonnet) · Classical ML + Deep learning (Sonnet, Opus for backprop derivation) · RL (Sonnet) · Rust (Sonnet) · Polyglot backend (Sonnet) · DevOps/security (Sonnet) · MLOps (Sonnet) · SDE craft (Sonnet).

### Wave 4 — specialist tracks (≈50 modules, ~14 tasks)
Blockchain (Sonnet) · Quantum (Sonnet) · Finance/Basel/MRM (Sonnet, Opus for MRM governance) · Product/MBA (Opus — judgment) · Frontier AI (Opus — fast-moving, accuracy-critical) · Azure + GCP atlases (Sonnet).

### Wave 5 — labs, problems, integration
~40 labs (Sonnet, tests verified by execution) · 250 tagged LeetCode problems (Haiku from a curated list) · cross-linking pass (Haiku) · full verification (Opus).

---

## 3. Review gate — the checklist every module must pass

Opus checks each Sonnet-written module for:

1. **30-second version exists and is actually 3–5 sentences**, no hedging.
2. **Lineage has all three parts** — what it replaced *and the pain that killed it*, current consensus vs what's merely published, direction of travel with uncertainty flagged.
3. **Numbers, not adjectives.** At least 5 concrete figures (latencies, defaults, thresholds, complexities).
4. **A named failure mode with its observable symptom** in the production section.
5. **10+ interview questions, each with a follow-up trap.**
6. **A real "when NOT to use this"** — not a token paragraph.
7. **Sources cited with access dates** for anything version-dependent.
8. **Code runs** or is explicitly marked as an untested sketch.
9. **No marketing voice.** If a tool is usually the wrong choice, it says so.
10. **Cheat card is genuinely one screen** and atomic enough to become flashcards.

Fail any of 1–7 → sent back with specific notes, not rewritten by me. Rewriting by hand defeats the routing.

---

## 4. Throughput and honesty

- Wave 1 is realistically **2–3 sessions**. Not one.
- Waves 2–5 are **~10–15 further sessions** at good quality.
- A scheduled weekly task can run one wave-task unattended, so content accrues without you asking.
- `CONTENT-STATUS.md` regenerates on every build, so the burn-down is always visible and honest.

**What I will not do:** produce 397 thin files so the tracker reads 100%. You set the bar with the resilience module; a green tracker full of filler is worse than an honest 30%.

---

## 4b. Where the burn-down actually stopped — 2026-08-01

218 / 425 written, review gate 218/218. Waves 1 and 2 completed; wave 3 was cut
short mid-flight by a monthly spend limit, not by a content problem. Complete
tracks: T18, C-AWS, T15, T02, T29, T30.

**Resume here. One agent per row, Sonnet, Opus review gate after each wave.**

| Batch | Track | Modules |
|---|---|---|
| A | T07 | react-agent-internals, framework-matrix *(mcp-deep-dive, a2a-protocol done)* |
| B | T07 | production-agent-loops, agent-cost-routing, structured-output, prompt-versioning |
| C | T07 | guardrails, risk-taxonomy, harness-evals *(agent-safety, agent-testing done)* |
| D | T06 | semantic-search, multilingual, accuracy-tuning, metadata-design, semantic-caching, data-structuring |
| E | T10 | consensus-ordering, messaging, caching-ratelimiting |
| F | T10 | principal-layer, tech-selection, poc-to-prod |
| G | T10 | classic-designs, ml-designs, case-studies |
| H | T17 | wide-column-kv, redis, clickhouse, elasticsearch *(sqlserver done)* |
| I | T17 | vector-db-compare, sql-mastery |
| J | T05 | alignment, finetuning, quantization, embeddings-training, multimodal |
| K | T08 | eval-harness, ragas-deepeval, otel-genai, obs-platforms, classic-obs |
| L | T21 | resilience-advanced, outbox-saga-cqrs, architecture-styles, ddd, anti-patterns |
| M | T28 | mcp-authoring, ai-arch-review, agent-skills-arch, harness-comparison, when-not-to |
| N | mixed | T14 ×2, T19 ×2, T27 ×2 |

That closes Phase A. Phase B (~160) follows: T12, T31, T16, T11, T24, T04, T26,
T25, T22, T20, T03, T01, T23, T13, T09, C-AZ, C-GCP.

**Two lessons worth keeping, both learned the expensive way:**

1. **State `## The 30-second version` is REQUIRED in every agent prompt.** The
   spec says write it last, so a long-running agent drops it. Six T18 modules
   did, in one batch. Cheaper to prevent than to send back.
2. **Check whether a gate failure is the module or the gate.** Three separate
   times the gate was wrong, not the content: T15 boss rounds have no lineage by
   design, a 40-question SQL bank formatted as `**Qn**` counted as 3 questions,
   and the full-loop round has no question bank because it orchestrates the other
   five. `review_gate.py` now carries a BOSS profile and counts both question
   forms. Sending good work back is worse than not checking.

Non-module gaps, untouched: 250 problems (`app/data/problems.json` is empty, so
the Problems tab renders blank), ~39 labs, 0 cheatsheets, Azure + GCP atlases.

**184 `[CONFIRM: ]` placeholders** sit in the resume-defence block
(`T10-resume-systems`, `T14-star-bank`, `T14-company-specific`, `T15-round-hm`).
No agent can fill those. They need the student's real numbers, and that hour
beats any amount of new content if a loop lands first.

---

## 5. Ordering rule that overrides everything

If a real interview appears, the pipeline pauses and `/tutor-company` plus the relevant weekend jumps the queue. The pipeline serves the loops, never the reverse.
