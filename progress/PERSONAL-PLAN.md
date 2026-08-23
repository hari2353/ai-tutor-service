# Personal Operating Plan (self-paced)

> For: Hari Siva Rami Dwarampudi · Principal AI Engineer, 7 yrs · mode: self-paced,
> works even when life happens. Companion docs: `ROADMAP.md` (sprint skeleton),
> `LEARNING-PATH.md` (prereq tiers), `CONTENT-STATUS.md` (what's written),
> `progress/CONFIRM-CHECKLIST.md` (184 personal facts).
> Generated 2026-08-23. Nothing else in the repo was modified.

---

## 0. Where you actually stand today

Evidence, not vibes. Checked against the repo on 2026-08-23.

| Signal | Value | Source |
|---|---|---|
| Curriculum written | **399 / 452 modules (88.3%)** | `CONTENT-STATUS.md` |
| Sprint weekends W1–W10 | **all ✅ written** | `CONTENT-STATUS.md` sprint table |
| Tracks still at 0% | Azure Atlas (C-AZ 0/8) · GCP Atlas (C-GCP 0/8) · Blockchain (T22 0/8) · Quantum (T23 0/7) · Financial Eng (T24 0/10) · Product/MBA (T25 0/8) | `LEARNING-PATH.md` tiers |
| Flashcards/drills | **28 resilience flashcards seeded** (Weekend-1 review block). Everything else: not started | `ROADMAP.md` WE-1 |
| Labs built | **exactly 1**: `labs/py/01-circuit-breaker` (solution + passing tests) | repo tree |
| Cheatsheets | **0** | repo-wide glob |
| Mocks logged | **ZERO. Not one scored round, ever.** | no progress logs |
| CONFIRM facts open | **184** (92 in T10-resume-systems · 76 in T14-star-bank · 13 in T14-company-specific · 3 in T15-round-hm) | `CONFIRM-CHECKLIST.md` |
| JD queue unpicked | 18 postings, all `prep_done: false`, oldest 2026-07-26; two **score-88 Siemens/Brightly** rows sit at the top | `interview_prep_queue.json` |

### Brutal honesty

1. You own an excellent **reference library** and almost **no proof of skill**. 88.3%
   written ≠ 88.3% learned. Zero mocks means your 70/80/88 band is unknown — you may
   be a 62 today. You won't know until you pay for one full loop.
2. The **184 CONFIRMs are the real bottleneck**, not content. Your strongest material
   (recsys platform, ClickHouse HNSW stack, OOM fix, OWASP, 89% ETL cut) currently has
   placeholder holes exactly where a hiring manager drills. Reading more modules while
   these stay open is procrastination dressed as work.
3. **One lab in four weeks** breaks ROADMAP Rule 2 (*a module isn't done until its lab
   tests pass*). Most weekend blocks so far were consumed as reading.
4. The best-matched job (Siemens Brightly, score 88) has been sitting in the queue for
   **four weeks untouched**. Prep packs exist precisely for this; not using them wastes
   the scoring work already done.
5. Resume defect flagged in CONFIRMs: invalid SageMaker instance names (`ml.4xlarge`,
   `g4.2xlarge`) — fix before any AWS-literate interviewer sees them (T14-star-bank L246).

---

## 1. Non-negotiables this month (ranked, hour-priced)

| # | Commitment | Hours | When | Why it outranks everything else |
|---|---|---|---|---|
| 1 | **Fill all 184 CONFIRMs** in `curriculum/10-system-design/09-resume-systems.md`, `curriculum/14-behavioral-principal/01-star-bank.md`, `04-company-specific.md`, `15-interview-simulator/06-round-hm.md`; re-run `scripts/gen_confirm_checklist.py` until 0 | ~12–14h total: 2× weekend 4h blocks + 6× 45-min weekday slices | **Scheduled NOW as Weekend-8 material**, pulled forward ahead of repair work | Single highest-ROI block in the plan. An invented number in a STAR story is what gets caught on follow-up. No new content beats this hour. |
| 2 | **First scored mock loop** — `/tutor-mock full-loop` (5 rounds) + written debrief into progress log | ~5h (4h loop + 1h debrief) | End of this week, even with CONFIRMs half-done | Establishes the baseline band (70 senior / 80 staff / 88 principal). Every later decision keys off this number. ROADMAP Rule 3: log every score. |
| 3 | **Siemens-Brightly prep pack** — `/tutor-company` on the score-88 JD pair (queued 2026-07-26, `prep_done: false`) | ~6h (3h pack build + 3h gap repair) | Next weekend after the mock | Highest-fit target sitting unpicked for a month. JD demands RAG+guardrails+eval harness, LoRA/QLoRA lifecycle, AWS prod, MLOps governance — see §3 gap-list. |

Total: ~23–25h ≈ 2.5 weekends. Everything else this month is optional.

---

## 2. The self-paced weekly loop (works even when life happens)

| Slot | Default | Fallback when the day collapses |
|---|---|---|
| Weekday ×5 | **20-min flashcard rule**: one card set from the app, nothing more | Do it at 10 min if needed — never skip entirely (no-zero days) |
| Weekend core | **9h block copied verbatim from ROADMAP**: 3h AI depth · 2h design/principles · 2h DSA · 1.5h databases/cloud · 0.5h review | Protect the 3h AI-depth slice first; it maps to boss battles |
| Weekly boss battle | One `/tutor-mock <type>` per weekend (coding → genai → design → behavioral/hm rotation per ROADMAP WE-2/4/6/7) | If the weekend dies, run the 1h boss module from T15 instead of skipping |
| Monthly | Full `/tutor-mock full-loop`, scored, logged | Never skipped — reschedule within 7 days |

### Catch-up protocol

- **Never stack >1 weekend of debt.** If a weekend is lost, don't double up next week.
- Instead: **re-baseline**. Run `/tutor-progress`, take the weakest signal, and fold the
  missed topics into flashcards + the next weekend's review block. Debt converts to
  spaced repetition, not a bigger pile.
- Interviewing this week? ROADMAP Rule 1 wins: drop breadth, do the boss battle + repair.

### Streak psychology

- **No-zero days**: the only failure state is a day with zero flashcards. A 20-min
  weekday streak is what makes a weekend-only cadence survive two lost weekends.
- Rule 5 applies: a module that feels easy becomes a flashcard, not a session.

---

## 3. Phase plan from YOUR resume outward

You are not learning these topics; you are converting production scars into
interview-grade articulation. Rehearsal beats reading.

### 3a. Leverage-list — scars → modules (rehearse, don't re-read)

| # | Resume bullet (the scar) | Convert to articulation via |
|---|---|---|
| 1 | A2A + FastMCP multi-agent system replacing legacy RAG, 2M+ users | `T07 mcp-deep-dive` · `T07 a2a-protocol` · `T07 multi-agent-topologies` · `T07 agent-zero-to-prod` |
| 2 | Skill resolution: ClickHouse HNSW + Titan Embed v2 (512-dim) + BGE-Reranker-Large, 54,486 skills / 22 locales / 1.2M rows | `T06 vector-index-internals` · `T06 rerankers` · `T06 metadata-filtering` · `T17 vector-db-compare` · `T17 clickhouse` |
| 3 | 22-locale hardening: x-Language → Accept-Language → en_us precedence, Unicode normalization, per-locale NLP routing | `T06 multilingual-embeddings` (cross-lingual retrieval, 22-locale reality) |
| 4 | OOM fix: paginated ClickHouse loading + gc.collect orchestration on 1.2M rows | `T01 memory-oom` (GC, tracemalloc, memray) · `T17 clickhouse` |
| 5 | OWASP Top-10 remediation: parameterized SQL + cross-tenant object-level authz bypass closed | `T30 sql-injection` · `T30 api-security` (BOLA/IDOR) · `T12 owasp` · `T12 rbac-authz` |
| 6 | JWT TTL cache with automatic secret rotation across the recsys fleet | `T30 jwt-deep` · `T30 access-refresh-rotation` · `T12 secrets-jwt-ttl` |
| 7 | MongoDB race conditions + async event-loop closure fixes under peak load | `T17 mongodb` · `T01 asyncio` (cancellation, TaskGroups) |
| 8 | CMAB with PySpark for real-time rec scoring; Redis cache for 100+ content-ID bottleneck | `T03 bandits` (LinUCB/Thompson/CMAB) · `T09 spark-tuning` · `T17 redis` · `T10 caching-layers` |
| 9 | vLLM self-hosted on SageMaker (Phi-4, LLaMA-8B) + Bedrock batch JSONL pipeline | `T05 inference-serving` (KV-cache math, PagedAttention, continuous batching) · `T09 gpu-cost` · `T09 bedrock-vs-sagemaker` |
| 10 | Query Crafter NL-to-SQL (RAG + GPT-4 + Trino, −50% report turnaround) | `T10 genai-designs` · `T17 query-planner` · `T07 prompt-injection-guardrails` (read-only guardrails trap) |
| 11 | PySpark + EMR customer-intelligence pipeline; Skillmaster Parquet→Postgres async ingestion; Java→Python migration (−3,447 LOC) | `T18 emr-deep` · `T18 batch-ingestion-backfills` · `T13 refactoring-strangler-legacy` |
| 12 | 2,000-row golden regression baseline + 200+ tests; Weaviate + KG cold-start search; 89% ETL cut (Expedia/Qubole) | `T19 regression-golden-baselines` · `T07 testing-agents` · `T17 knowledge-graphs` · `T18 pyspark-from-scratch` · `T10 back-of-envelope` |

**Leverage-list mapping count: 12** bullets → ~30 module ids. These feed
`T10-resume-systems` design docs and the `T14-star-bank` stories — which is exactly why
Non-negotiable #1 comes first: the CONFIRMs live inside those two modules.

### 3b. Gap-list — claimed-but-thin or JD-demanded

Cross-ref: `progress/JD-SKILL-GAP.md` does **not exist yet** — generate it with
`/tutor-company` when you run Non-negotiable #3. Until then, this is my direct scan of
`interview_prep_queue.json` (18 JDs, all unprepped):

| # | Gap | JD evidence (queue) | Close via |
|---|---|---|---|
| 1 | Fine-tuning lifecycle: LoRA/QLoRA training + A/B testing owned end-to-end | Siemens Brightly ×2 (explicit); you list PEFT as a skill but ship no story | `T05 lora-qlora-decision-tree` + turn one real PEFT attempt into a STAR story in `T14-star-bank` |
| 2 | Eval harnesses as a productized gate (CI eval gates, responsible-AI controls) | Siemens Brightly, Epicor AI Enablement Architect | `T08 eval-harness-design` · `T08 ragas-deepeval` → feeds `rag-eval-kit` artifact (§4) |
| 3 | OTel instrumentation of GenAI spans (latency/cost/quality) | Siemens Brightly (explicit OpenTelemetry), nan JD (monitoring) | `T08 otel-genai` + add spans to `mini-agent-harness` (§4) |
| 4 | MLOps registries & model/prompt CI-CD (MLflow, Kedro, SageMaker Pipelines, lineage) | Siemens Brightly, Epicor | `T09 mlflow-registries` · `T09 model-cicd` · `T09 feature-stores` |
| 5 | EDA discipline named as a competency (structured + unstructured) | Siemens Brightly lists EDA as a standalone responsibility | `T03 eda-distributions` — cheap win, rehearse on your own pipeline data |
| 6 | Principal-level people evidence: consumers of your contracts, mentoring, interviews run | Google (2 yrs tech leadership), Optum VP, Regilient (lead jr + 4 interns), Microsoft Principal | `T14 scope-influence` · `T14 company-specific` — blocked on CONFIRMs L118/L129/L141/L679 (consumer counts, mentoring stories) |
| 7 | Cloud breadth past AWS: Azure ML/Databricks, GCP Vertex/BigQuery | ZF (Azure ML + Databricks), SAP AI Architect (Dubai), Unilever ×3 | `C-AZ ai-foundry` · `C-GCP vertex-ai` · `C-GCP bigquery` — tracks are **0/8 written**; request via `/tutor-deepdive` only when a target JD needs them (Rule 4: say "update") |
| 8 | Multimodal/voice + reasoning models | Microsoft Teams Sr Applied Scientist (multimodal, recsys, LLM eval) | `T26 voice-whisper` · `T26 reasoning-models` — Frontier track is 6/10 written |
| 9 | Databricks depth (Delta, Unity Catalog) behind the Azure ask | ZF, Unilever data-platform roles | `T18 databricks` (module ✅ written) — lab it once, then flashcards |
| 10 | Public proof-of-work — github.com/hari2353 cited in CONFIRMs as needing "a repo, a write-up… costs a weekend" | T14-company-specific L335; also helps Epicor "enablement materials" | §4 artifact portfolio below |

Priority order: 1→4 are the Siemens pack (do with Non-negotiable #3); 6 is unlocked by
finishing the 184 CONFIRMs; 7–8 are pull-based per JD, never speculative.

---

## 4. Self-verification engine (proving skill, not consuming content)

### Per-module exit criteria (all four, in order)

1. **Read** the module (`/tutor-deepdive <id>` if unwritten).
2. **Lab passes** — the matching `labs/py/*` test suite green; if no lab exists, write
   the smallest repro script that exercises the claim.
3. **Drill ≥80%** — app flashcard set for that topic at ≥80% correct.
4. **3 traps aloud** — answer the three classic traps for the topic out loud, recorded,
   without notes. Fail any → back to step 2, not step 1.

A module with steps 1–2 done is *studied*. Steps 3–4 make it *owned*. Only owned
modules count toward DONE (§6).

### Cadence

| Layer | Cadence | Instrument |
|---|---|---|
| Boss battle | weekly, rotating type | `/tutor-mock coding|genai|design|behavioral|hm` |
| Full loop | monthly, scored | `/tutor-mock full-loop` — bands: **70** senior · **80** staff · **88** principal (ROADMAP bar) |
| Score logging | every mock | progress log — `/tutor-progress` picks repair targets (Weekend-8 pattern) |
| Teach-back ritual | after each leverage row (§3a) | explain the system to a rubber duck/recording in ≤10 min using the `T14 design-communication` 45-min framework compressed; where you stall is the next flashcard seed |
| Cheatsheets | one per completed leverage row | `cheatsheets/` is empty today; target ≥6 by month-end (they are the pre-mock warm-up) |

### Artifact portfolio — 3 public repos, sized for interviews

| Repo | Acceptance criteria (definition of shippable) | Interview questions it proves |
|---|---|---|
| **mini-agent-harness** | Agent loop from scratch (no LangChain): tool registry with schemas, retry+jitter, circuit breaker (reuse `labs/py/01-circuit-breaker`), checkpoint/resume to SQLite, budget caps, kill switch, OTel spans on every LLM/tool call. README shows a trace screenshot + cost/step table. Tests green. | "How does the agent loop work?" · "What breaks at scale?" · "How do you make runs resumable?" (T07 agent-loop/react/langgraph-durable, T07 harness-engineering, T08 otel-genai) |
| **rag-eval-kit** | CLI over any doc set: chunking profiles (fixed/recursive/semantic), HNSW index, retrieval@k, MRR/nDCG, RAGAS-style faithfulness via judge, golden-set runner exit-codes for CI. Demoed on a public dataset; README states recall@k before/after reranking. | "How do you evaluate a RAG system?" · "Reranker worth the latency?" · "How would you gate a prompt change?" (T06 vector-index-internals/rerankers/squeezing-accuracy, T08 llm-as-judge/ragas) |
| **spark-gotchas** | 6–8 notebook-backed case studies: skew fix, AQE on/off bench, broadcast join threshold, UDF vs native cost, rate-limited async writes (your LLM-throttle pattern), EMR egg packaging. Each: symptom → diagnosis (Spark UI evidence) → fix → measured delta. | "Walk me through a Spark perf war story" · "How did you cut the 4.5h job?" (T09 spark-tuning, T18 pyspark/emr, T03 bandits-pipeline) |

Each repo doubles as the public-proof item in `T14-company-specific` (CONFIRM L335)
and as fresh STAR stories. One repo per month, ALL-IN mode only (§5).

---

## 5. Pace dials

Borrowed from ROADMAP §Rules. Pick one mode per week; announce it Sunday night.

| Mode | Hours/wk | What it contains | What drops |
|---|---|---|---|
| **CRUISE** | 6h | 5×20-min weekdays + one 4h weekend core (AI depth + review) | DSA block, second design hour, boss battle becomes a 1h T15 module |
| **SPRINT** (default) | 9h | Full ROADMAP weekend block + daily flashcards + weekly boss battle | Nothing structural; social calendar absorbs variance |
| **ALL-IN** | 14h | SPRINT + artifact-repo night (§4) + second mock or JD prep pack | Sleep discipline and non-interview hobbies drop instead — time-boxed, only when a loop is scheduled or an artifact ships |

Mode rules: interviewing this week ⇒ forced ALL-IN on boss battle + repair (Rule 1);
missed weekend ⇒ drop to CRUISE and re-baseline (§2), never attempt 18h recovery weeks.

---

## 6. Definition of DONE for this plan

| # | Condition | Check |
|---|---|---|
| 1 | All CONFIRMs = **0** | `python scripts/gen_confirm_checklist.py` reports 0 open |
| 2 | **≥6 logged mocks with rising band**, incl. ≥2 full loops at ≥80 (one at 88 if targeting principal bars like Google/Optum/Microsoft rows) | progress log |
| 3 | Sprint **✅100%** meaningfully: every W1–W10 module through all four exit criteria (§4) — labs green, not just pages read | labs dir + drill scores |
| 4 | **3 portfolio artifacts public** (mini-agent-harness · rag-eval-kit · spark-gotchas), each meeting acceptance criteria | github.com/hari2353 |
| 5 | **PATTERNS.md fed by ≥2 real debriefs** — recurring mock failures promoted to patterns and drilled to extinction | PATTERNS.md git history |

DONE is a floor, not a ceiling: Phase B (ROADMAP WE-9–26) continues after, but every
week past DONE should be paid for by a scheduled loop, not by anxiety.

---

*Self-paced covenant: the library is built (88.3%). From here the only currencies are
filled CONFIRMs, green labs, logged scores, and public repos. Everything else is
consumption.*
