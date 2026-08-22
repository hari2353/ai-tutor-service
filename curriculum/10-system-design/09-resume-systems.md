# Your Flagship Systems as Formal Design Docs

> **Track:** T10 System Design · **Time:** 3h · **Prereqs:** T10-distributed-fundamentals, T10-estimation · **Updated:** 2026-07-26
> **Module id:** `T10-resume-systems` · **Tags:** sprint, principal, critical

## The 30-second version

The system design round you are most likely to fail is not "design Twitter", it is "walk me through something you built", because it is the only round where the interviewer knows you cannot bluff and where every follow-up is answerable from ground truth you either have or do not. Five systems on your resume are strong enough to present cold: the **Skills Intelligence Platform** (54,486 skills, 22 locales, ClickHouse HNSW plus BGE reranking), the **8-service recommendation platform** (2M+ users, ~25% engagement uplift), the **A2A + FastMCP multi-agent content pipeline**, the **LLM serving platform** (self-hosted vLLM on SageMaker plus Bedrock batch), and **Query Crafter** (NL-to-SQL over Trino). This module writes each up in the shape a design review expects: context and constraints, requirements split functional from non-functional, an architecture diagram you can reproduce on a whiteboard in 90 seconds, decisions with the alternative you rejected and the cost you accepted, data model, scale numbers, failure modes with their observable symptoms, and what you would change now. Then the ten hardest questions per system with answers, because the score in this round comes from the follow-ups, not the diagram.

## Why this gets asked

Because "design a URL shortener" tests preparation and "walk me through your recommendation platform" tests authorship. The interviewer has hired someone who described a platform fluently, joined, and turned out to have owned one service; the deep-dive round exists to catch that. Concretely, they are checking four things: whether you can scope and frame the problem yourself rather than reciting the feature list, whether you name real alternatives and the cost you knowingly accepted rather than only the upside, whether you understand *why* the system is built that way rather than only *what* it does, and whether you can cleanly split your contribution from your team's ([staff-plus interview processes, StaffEng](https://staffeng.com/guides/staff-plus-interview-process/) — accessed 2026-07-26). The second reason is calibration: your written design doc is the artifact a promotion committee or a hiring committee actually reads, so a candidate who cannot produce one on a whiteboard probably has not produced one at work either.

---

## Lineage: past → present → future

**What came before.** Design documentation used to be either nothing or everything. The heavyweight end was the IEEE 1016 software design description and the associated waterfall SDD, a hundred-page artifact produced before implementation and stale within a month; the specific pain that killed it was that it was written for an approval gate rather than for a reader, so nobody read it and nobody updated it. The lightweight end was the reaction to that: Agile's "working software over comprehensive documentation" (2001), which in practice often meant no written design at all and architectural decisions living in the heads of whoever was on the team that quarter. Both failed for the same underlying reason, which is that the design decision and its *rationale* were not captured in a durable, reviewable, and cheap-to-write form.

**Where it stands now.** The convergent answer is the short, decision-focused document: Google's design doc culture (a 3-to-20-page markdown doc with explicit goals, non-goals, alternatives considered, and a review thread), the RFC model at Rust, Oxide and elsewhere, Amazon's PR/FAQ and six-pager for product framing, and Architecture Decision Records (Michael Nygard, 2011) for the atomic per-decision unit. The shared feature is that **alternatives considered and non-goals are mandatory sections**, because those are the parts that carry the reasoning and they are the parts you cannot reconstruct later. The live disagreement is about granularity: the ADR camp argues for many small immutable records with a status field, and the design-doc camp argues for one narrative document per project because a reader needs the connected story rather than forty decision fragments. In practice large orgs run both, a design doc per project and ADRs for decisions that outlive it, and the honest observation is that ADR discipline decays faster than design-doc discipline because nobody is the reviewer of record for an ADR. The second live disagreement is whether diagrams should be generated from code or drawn by hand; C4 with structurizr and Mermaid-in-repo have real adoption, but the whiteboard-legible hand diagram is still what an interview and an incident review both need.

**Where it's heading.** Three directions. High confidence: **design docs become the primary artifact fed to coding agents**, which changes what they must contain. A doc written for a human can leave interfaces implied; a doc used as agent context cannot, so expect explicit contracts, invariants and non-goals to get stricter rather than looser. Medium confidence: **generated first drafts, human-owned decisions**. LLMs are already good at producing the boilerplate sections (context, requirements, glossary) and bad at the two that matter (which alternative, and why you accepted its cost), so the doc's centre of gravity shifts further onto the rationale sections, which is also where interviews are already focused. Speculative: **executable design docs**, where the stated scale numbers and SLOs are linked to live dashboards and the doc fails CI when reality drifts from the claim. Prototypes of this exist in the SLO-as-code space; treat it as a direction, not a practice.

---

## Mental model

A design doc is a **defence in depth against the question "why"**. Each section answers a different "why", and an interviewer walks inward until you run out of answers. Where you run out is your level.

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │ CONTEXT      why does this system exist at all?                     │
   │  ┌──────────────────────────────────────────────────────────────┐   │
   │  │ REQUIREMENTS   what must be true, and what is explicitly     │   │
   │  │                out of scope (non-goals)?                      │   │
   │  │  ┌───────────────────────────────────────────────────────┐   │   │
   │  │  │ ARCHITECTURE   what are the boxes and why THESE boxes │   │   │
   │  │  │  ┌────────────────────────────────────────────────┐   │   │   │
   │  │  │  │ DECISIONS   what did you reject, and what      │   │   │   │
   │  │  │  │             cost did you knowingly accept?     │   │   │   │
   │  │  │  │  ┌─────────────────────────────────────────┐   │   │   │   │
   │  │  │  │  │ MECHANISM   how does the chosen thing   │   │   │   │   │
   │  │  │  │  │   actually work, one level below the    │   │   │   │   │
   │  │  │  │  │   name of the technology?               │   │   │   │   │
   │  │  │  │  │  ┌──────────────────────────────────┐  │   │   │   │   │
   │  │  │  │  │  │ NUMBERS  what did you measure?   │  │   │   │   │   │
   │  │  │  │  │  │ FAILURE  what broke, and what    │  │   │   │   │   │
   │  │  │  │  │  │   was the observable symptom?    │  │   │   │   │   │
   │  │  │  │  │  └──────────────────────────────────┘  │   │   │   │   │
   │  │  │  │  └─────────────────────────────────────────┘   │   │   │   │
   │  │  │  └────────────────────────────────────────────────┘   │   │   │
   │  │  └───────────────────────────────────────────────────────┘   │   │
   │  └──────────────────────────────────────────────────────────────┘   │
   └─────────────────────────────────────────────────────────────────────┘

   Senior stops around DECISIONS. Staff answers MECHANISM.
   Principal has the NUMBERS and volunteers the FAILURE unprompted.
```

The 90-second whiteboard rule: for each of these five systems you should be able to draw a diagram with **no more than 9 boxes** and narrate it in 90 seconds. If your diagram needs 20 boxes, you have drawn the deployment topology instead of the architecture. Draw the data flow, and put the thing the interviewer will want to drill into (the retrieval path, the event path) in the middle where there is room to expand it.

---

## How it actually works

### The template each system below follows

```
1  CONTEXT          the business situation and the constraint that made it hard
2  REQUIREMENTS     functional / non-functional / NON-GOALS
3  ARCHITECTURE     ASCII diagram + the decomposition criterion
4  KEY DECISIONS    D1..Dn, each: chose X over Y because Z, accepted cost C
5  DATA MODEL       the two or three entities that matter, with cardinality
6  SCALE            volumes, latencies, costs. Marked [CONFIRM] where unknown.
7  FAILURE MODES    symptom → cause → handling. Symptom first, always.
8  WHAT I'D CHANGE  specific, with the trigger that would make it necessary
9  TEN QUESTIONS    the hardest ones, with answers and traps
```

**Non-goals are the section that most signals seniority and the one nobody writes.** "This system does not do real-time skill inference from free text" tells the reader you knew where the boundary was and put it somewhere deliberately. A doc with no non-goals reads as a doc written after the fact.

**Symptom before cause in the failure table.** In an incident you have the symptom, not the cause. A failure table organised by cause is a design artifact; one organised by symptom is an operational one. Interviewers who have been on-call notice the difference immediately.

**Every `[CONFIRM: ...]` below is a real gap in what your resume states.** Fill them before presenting. An unfilled number is worse than an absent one, because you will be tempted to invent it under pressure.

---

# SYSTEM 1 — Skills Intelligence Platform

*Multi-tier skill resolution over 54,486 skills, 22 locales, 1.2M+ rows*

## 1. Context and constraints

Cornerstone OnDemand runs an enterprise learning and talent platform for 2M+ users. Everything downstream (recommendations, content gap detection, talent matching) is keyed on **skills**, and skills are a naming problem before they are an ML problem. Three taxonomies coexist: a tenant's own custom skills, purchased external taxonomy feeds, and a master taxonomy maintained internally. The same human capability exists under different names, in 22 languages, across all three. Before resolution, downstream signal was fragmented across duplicates, so a user who demonstrated "data analysis" and a course teaching "data analytics" did not connect.

Hard constraints:
- **Multi-tenant, with tenant vocabulary sovereignty.** If a tenant defines "Cloud Engineering" to mean something specific, that definition wins over a globally better semantic match. This is a product requirement, not an optimisation.
- **22 locales**, so every string operation is Unicode-correct and every model choice is multilingual.
- **1.2M+ skill rows** over 54,486 canonical skills, meaning roughly 22 rows per skill, which is the locale multiplier.
- Data already lives in **ClickHouse**, and the platform already has an operational footprint there.

## 2. Requirements

**Functional**
- F1. Given an input string plus tenant plus locale, return the canonical skill it denotes, or an explicit "unresolved".
- F2. Resolution respects precedence: **custom → external → master**.
- F3. Support all 22 locales, including cross-locale resolution (an English input resolving against a tenant's Portuguese custom skill) `[CONFIRM: whether cross-locale resolution is in scope or explicitly out]`.
- F4. Bulk resolution for ingestion and backfill, not only single lookups.

**Non-functional**
- N1. p99 resolution latency `[CONFIRM: target and achieved]`. For an interactive path this is single-digit-to-low-tens of milliseconds; for a batch path it is throughput-bound.
- N2. Precision prioritised over recall. A wrong resolution silently corrupts every downstream recommendation, whereas an "unresolved" is visible and recoverable.
- N3. Strict tenant isolation on every read path.
- N4. Reproducible: the same input plus the same index version yields the same output, which is what makes the golden baseline possible.

**Non-goals**
- Not a free-text skill extractor. It resolves candidate strings; it does not read a document and discover skills. That is upstream.
- Not a taxonomy editor. It consumes taxonomies, it does not curate them.
- Not real-time taxonomy updates. Index rebuilds are batch `[CONFIRM: rebuild cadence]`.

## 3. Architecture

```
                      resolve(text, tenant_id, locale)
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │  LOCALE RESOLUTION                        │
             │   x-Language → Accept-Language → en_us    │
             │   Unicode-aware normalisation (NFKC +     │
             │   locale-correct case folding)            │
             └───────────────────────────────────────────┘
                                   │  canonical locale tag
                                   ▼
             ┌───────────────────────────────────────────┐
             │  EMBED   Amazon Titan Embed v2, 512-dim   │
             └───────────────────────────────────────────┘
                                   │  query vector
                                   ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │  TIERED CANDIDATE RETRIEVAL  (ClickHouse, HNSW vector index)      │
   │                                                                   │
   │   TIER 1  custom     WHERE tenant_id = ? AND locale = ?           │
   │             │ candidates above threshold? ──── yes ──┐            │
   │             ▼ no                                      │            │
   │   TIER 2  external   WHERE feed_id IN (tenant feeds)  │            │
   │             │ candidates above threshold? ──── yes ──┤            │
   │             ▼ no                                      │            │
   │   TIER 3  master     global taxonomy                  │            │
   │             │                                         │            │
   │             └─────────────────────────────────────────┤            │
   └───────────────────────────────────────────────────────┼───────────┘
                                   │  top-k candidates     │
                                   ▼                       │
             ┌───────────────────────────────────────────┐ │
             │  RERANK  BGE-Reranker-Large (cross-enc.)  │ │
             │  scores (query, candidate) jointly        │ │
             └───────────────────────────────────────────┘ │
                                   │                       │
                                   ▼                       │
             ┌───────────────────────────────────────────┐ │
             │  DECIDE  score ≥ τ → canonical skill_id   │◀┘
             │          score <  τ → UNRESOLVED          │
             └───────────────────────────────────────────┘

   SIDE PATH — ingestion
     Parquet ──▶ staged in memory ──▶ PostgreSQL (async job)
                        │
                        └──▶ status polling + verification endpoint
     Embedding rebuild: ClickHouse ──paginated──▶ embed ──▶ HNSW index
```

**Decomposition criterion.** Locale resolution is separated from retrieval because it is a pure function with a single source of truth; retrieval is separated from reranking because they have different cost profiles (ANN is cheap and parallel, a cross-encoder is expensive and sequential in the number of candidates); and the tier cascade is control flow rather than three separate services, because the tiers share the same index and separating them would add network hops to a latency-critical path.

## 4. Key decisions

**D1 — Tiered cascade with tenant precedence, not one flat embedding space.**
Chose: an explicit precedence cascade where a tenant's own taxonomy is consulted first and, if it produces a candidate above threshold, wins outright.
Over: a single vector space containing all three taxonomies, taking the global argmax.
Because: the flat design silently overrides tenant vocabulary whenever the master taxonomy happens to score higher, and "the system renamed our skill" is the escalation enterprise admins actually make. Semantic similarity is not authority.
Accepted cost: a tenant with a poorly-curated custom taxonomy gets worse resolutions than the global space would give them, and the cascade is harder to evaluate because quality is now conditional on tenant data quality.

**D2 — ClickHouse HNSW rather than a dedicated vector database.**
Chose: index vectors in place, in ClickHouse.
Over: Weaviate (which you had already run in production, System 5's predecessor) or pgvector.
Because: three reasons in priority order. First, every real query is a **filtered** query (tenant, locale, tier), and keeping vectors adjacent to the relational columns makes the filter a native predicate rather than a metadata filter bolted onto an ANN index, which is where filtered vector search usually degrades: pre-filtering breaks HNSW's graph connectivity assumptions and post-filtering makes you over-fetch by the inverse of the selectivity. Second, at 1.2M rows and 512 dimensions the raw vector data is about 1.2M × 512 × 4 bytes ≈ **2.5 GB** as float32, which fits comfortably in memory on a single node, so a distributed vector store buys capacity that is not needed. Third, one fewer system to keep consistent, backfill and page on.
Accepted cost: ClickHouse's vector indexing is less mature than a purpose-built engine, with fewer knobs for the recall/latency curve and weaker support for hybrid lexical-plus-vector scoring. Stated migration trigger: roughly an order of magnitude more rows, or a second product needing the same vectors, or a hard requirement for hybrid BM25-plus-vector fusion.

**D3 — Two-stage retrieval: bi-encoder recall then cross-encoder rerank.**
Chose: Titan Embed v2 at 512 dimensions for recall, BGE-Reranker-Large as a cross-encoder over the top candidates.
Over: bi-encoder cosine similarity alone.
Because: a bi-encoder embeds query and document independently, so it cannot condition one on the other, and near-synonyms like "data analysis" and "data analytics" or "Java" and "JavaScript" sit close in that space. A cross-encoder reads both strings in one forward pass with full attention between them, which is exactly what is needed to separate them. The cost is that a cross-encoder cannot be pre-computed or indexed, so it must run per candidate at query time, which is why it sits behind a truncating recall stage.
Accepted cost: the reranker is the dominant latency term and it caps throughput. `[CONFIRM: top-k into the reranker. If it is above ~50 for an interactive path, that is a latency problem worth naming.]`

**D4 — 512 dimensions rather than a larger embedding.**
Chose: Titan Embed v2 at 512.
Over: 1024 dimensions, which Titan v2 also supports.
Because: skill names are short strings, a handful of tokens, and the marginal retrieval quality from doubling dimensionality on short text is small while the index memory, the distance-computation cost and the HNSW graph size all scale linearly in dimension. Doubling to 1024 would take the vector data from about 2.5 GB to about 5 GB for the same corpus.
Accepted cost: less headroom if the corpus later includes longer descriptions rather than names. `[CONFIRM: whether you actually measured recall at 512 vs 1024, or chose it on cost. Either answer is fine; say which.]`

**D5 — Explicit locale precedence chain as a single function.**
Chose: `x-Language` → `Accept-Language` → `en_us`, resolved once, in one place, with Unicode-aware normalisation, then used to route to language-specific NLP models.
Over: each service deciding locale for itself, and over auto-detecting language from the input text.
Because: locale decided in twenty places is twenty bugs. Auto-detection is unreliable on short strings, which is what a skill name is, and a wrong detection is silent whereas a missing header is diagnosable. Unicode-aware folding matters because ASCII `lower()` mishandles Turkish dotless i and similar cases, producing tags that fail exact-match lookup.
Accepted cost: callers must send a header or accept `en_us`. There is no clever fallback, which is the point.

**D6 — Precision-first thresholding with an explicit UNRESOLVED outcome.**
Chose: a score threshold below which the system returns "unresolved" rather than a best guess.
Over: always returning the top candidate.
Because: a wrong resolution propagates silently into every downstream recommendation, whereas an unresolved item is visible, countable and fixable. The metric that matters most operationally turned out to be the unresolved rate, because it is the system's own confession of ignorance.
Accepted cost: coverage. Some genuinely-correct resolutions fall below threshold. This is the correct trade for an enterprise data platform and the wrong one for a consumer search box.
`[CONFIRM: the actual thresholds per tier, and the unresolved rate in production.]`

## 5. Data model

```
skill                                  skill_alias  (the 1.2M+ rows)
  skill_id        UUID/int  PK           alias_id      PK
  taxonomy_tier   enum(custom|           skill_id      FK → skill
                       external|master)  locale        char(5)   e.g. pt_BR
  tenant_id       nullable ─────────┐    surface_form  text
                  (set iff custom)  │    embedding     Array(Float32) len 512
  feed_id         nullable          │    normalised    text  (Unicode-folded)
                  (set iff external)│
  canonical_name  text              │  INDEX: HNSW on embedding
                                    │  ORDER BY (tenant_id, locale, ...)
                                    │  ← ordering matters: the tenant+locale
                                    │    filter must be a prefix so ClickHouse
                                    │    can skip granules before ANN search
```

Cardinality: 54,486 skills → ~1.2M alias rows → ~22 aliases per skill, which is the locale count. Vector payload ≈ 1.2M × 512 × 4B ≈ **2.5 GB** float32.

The load-bearing detail is the sort key. If `tenant_id` and `locale` are not a prefix of the ordering key, the tenant filter cannot prune granules, and you either scan the whole index or degrade to post-filtering. This is the single most common way filtered vector search gets slow, and it is a table-definition problem rather than an ANN problem.

## 6. Scale numbers

| Quantity | Value | Source |
|---|---|---|
| Canonical skills | 54,486 | resume |
| Alias rows | 1.2M+ | resume |
| Locales | 22 | resume |
| Embedding dimensions | 512 (Titan Embed v2) | resume |
| Raw vector bytes | ~2.5 GB float32 | derived |
| Platform users | 2M+ | resume |
| Golden baseline rows | 2,000+ | resume |
| Tests | 200+ unit/integration | resume |
| p99 resolution latency | `[CONFIRM]` | — |
| Resolution QPS, peak | `[CONFIRM]` | — |
| Recall@k of stage 1 | `[CONFIRM]` | — |
| Reranker top-k | `[CONFIRM]` | — |
| Unresolved rate | `[CONFIRM]` | — |
| Full index rebuild wall-clock | `[CONFIRM]` | — |

## 7. Failure modes

| Symptom (what you see) | Cause | How it was handled |
|---|---|---|
| Process killed with no Python traceback, exit 137 / pod `OOMKilled`, during full embedding rebuild | Whole ClickHouse result set materialised into Python objects, so peak memory scaled with corpus size not batch size | Paginated ClickHouse reads plus `gc.collect()` at page boundaries (between pages, not in the hot loop, so the pause amortises). Verified with a memory profile across a full run, not one page. |
| Non-English tenant intermittently receives English-model output | Inconsistent locale source across callers; some send `x-Language`, some `Accept-Language`, some nothing; casing/separator variants (`pt-BR` vs `pt_br`) failed exact match | One precedence chain in one function, Unicode-aware normalisation, locale-driven model routing |
| Tenant A's request returns tenant B's object | Object-level authorization enforced per endpoint rather than at object fetch (OWASP API1) | Enforcement moved to the object-fetch path keyed on the authenticated tenant. Fix at the class level, not per endpoint. |
| Resolution quality shifts across a release with no code change to logic | Model, threshold or prompt change altering thousands of resolutions silently | 2,000+ row golden baseline in CI, with aggregate-behaviour assertions rather than exact string equality, plus 200+ tests on the deterministic parts |
| Retrieval latency grows superlinearly as tenants are added | Tenant filter not a prefix of the ClickHouse ordering key, so no granule pruning; effectively post-filtering | Ordering key with `(tenant_id, locale, ...)` prefix |
| Tenant provisioning request times out at the gateway | Synchronous Parquet-to-Postgres load held the request for minutes | Async job with submit/poll status plus a separate verification endpoint that confirms the data is correct, not merely present |
| Everything resolves, but downstream recommendations get worse | Cascade always returns *something*, so error rate is invisible | Per-tier confidence thresholds with an explicit UNRESOLVED outcome and an unresolved-rate metric |
| SQL error or unexpected result on an unusual skill name | String-interpolated SQL, injection surface | Parameterized queries; allowlist for the dynamic-identifier cases that cannot be parameterized |

## 8. What I would change now

1. **Streaming embedding generation instead of pagination plus explicit GC.** `gc.collect()` compensates for allocator behaviour; generators with bounded batches mean no object graph that large ever exists. Add a memory-ceiling assertion in CI so the regression fails in a pipeline rather than at 3am.
2. **Unresolved rate and per-tier confidence as first-class metrics from day one.** These were added later than they should have been and they turned out to be the most useful numbers in the system.
3. **Negative authorization tests for every resource type**, asserting a tenant-A token receives 403/404 on a tenant-B object. Without them the authz fix is one refactor from regressing.
4. **Hybrid lexical plus vector scoring.** Exact and near-exact string matches should not have to travel through an embedding model at all; a lexical stage would be both cheaper and more precise for the large fraction of inputs that are exact matches, with the vector path reserved for the genuinely fuzzy tail.
5. **A written migration trigger for the vector store.** The crossover point at which ClickHouse HNSW stops being the right answer lived in my head. It should be a documented threshold.
6. **Idempotent ingestion keyed on (tenant, dataset version)** so a retried provisioning submission is safe by construction.

## 9. The ten hardest questions

### 1.Q1 — Why not a real vector database?
**Answer:** Because every query is filtered by tenant and locale, and colocating vectors with the relational columns makes those filters native predicates with granule pruning rather than a metadata filter layered onto an ANN index. At 1.2M rows and 512 dimensions the vector payload is about 2.5 GB, which fits in memory on one node, so a distributed store buys capacity I do not need while adding a system to keep consistent, backfill and page on. I have run Weaviate in production before, so this was a choice rather than unfamiliarity, and I documented the migration trigger: about 10x the rows, a second consumer of the same vectors, or a hard requirement for BM25-plus-vector fusion.
**Trap:** *"So you would be stuck if you hit 50M rows?"* Not stuck, but I would migrate, and the reason it is a clean migration is that resolution is behind an interface: callers pass text plus tenant plus locale and receive a skill id, so swapping the retrieval implementation does not change any caller. The thing I would actually have to redo is the filtering strategy, because a dedicated store handles tenant filtering differently and I would have to re-establish the recall numbers.

### 1.Q2 — Why a cross-encoder at all? Cosine similarity is cheap.
**Answer:** Because a bi-encoder embeds query and candidate independently and therefore cannot condition either on the other, so near-synonyms land close together in the space. "Data analysis" and "data analytics" are almost certainly within noise of each other under any general-purpose embedding, and for skill resolution those may be the same skill or two different ones depending on the taxonomy. A cross-encoder puts both strings in one forward pass with attention across them, which is the only way to score the pair rather than two points. The cost is that nothing can be precomputed, so it runs per candidate at query time, which is exactly why it sits behind a truncating recall stage.
**Trap:** *"How much did the reranker actually buy you?"* `[CONFIRM: this number.]` If you did not isolate it, say so and say how you would: hold the recall stage fixed, evaluate top-1 accuracy on the golden set with and without reranking, and compare against the added p99. A reranker you cannot justify numerically is a latency cost with a hypothesis attached, and that is the honest framing.

### 1.Q3 — The tier cascade means the same string can resolve differently for two tenants. Is that a bug?
**Answer:** It is the requirement. Tenant vocabulary sovereignty means a tenant's own definition beats a globally better semantic match, because the tenants are enterprises who curate taxonomies deliberately and "the platform renamed our skill" is a real escalation. The consequence is that resolution is a function of (text, tenant, locale) and never of text alone, which is also why cross-tenant caching of resolutions is unsafe and why the cache key must include tenant.
**Trap:** *"Then how do you evaluate quality globally?"* You cannot, with one number. Quality is conditional on tenant taxonomy quality, so the useful metrics are per-tenant unresolved rate and per-tier hit distribution, plus a global golden set that only exercises the master tier. A single accuracy figure across all tenants averages over a variable you do not control, and reporting it would be misleading.

### 1.Q4 — Walk me through what happens on a full index rebuild while serving live traffic.
**Answer:** `[CONFIRM: your actual rebuild strategy. The defensible design, and what you should say if this is what you did: build into a new index or a new table version, verify against the golden baseline, then atomically switch the read pointer, keeping the previous version for rollback.]` The property to protect is that reads never see a half-built index, because a partially populated ANN index does not error, it silently returns worse results. Blue-green on the index version gives you that plus a rollback that does not require a rebuild.
**Trap:** *"What if the new index is worse but not broken?"* That is exactly what the 2,000-row golden baseline is for, and it is why the assertions are on aggregate behaviour rather than exact strings: a semantic system that must return byte-identical output cannot be improved, but one with tolerance bands catches a regression that is within-format and out-of-quality. Gate the pointer switch on the baseline rather than on the build succeeding.

### 1.Q5 — 22 locales: do you have one index or 22?
**Answer:** One physical index with locale as a filter, made cheap by putting locale in the ordering key prefix so the filter prunes granules before the ANN search. Twenty-two separate indices would give better locality per query and would multiply operational surface by 22, with a worse tail: the small locales would each have too few vectors for a well-connected HNSW graph. The multilingual embedding model is what makes one space viable, since Titan Embed v2 places semantically equivalent strings across languages in nearby regions.
**Trap:** *"So an English query can match a Portuguese skill?"* Yes, and whether that is desirable is a product decision rather than a technical one. `[CONFIRM: whether cross-locale matching is intended.]` If it is not, the locale filter must be strict rather than a scoring preference, and the honest statement is that a shared multilingual space makes accidental cross-locale matching *possible*, so it has to be excluded explicitly rather than assumed away.

### 1.Q6 — You said precision over recall. Quantify the trade.
**Answer:** `[CONFIRM: the actual threshold and the resulting precision/recall/unresolved figures.]` The structural argument regardless of the numbers: a wrong resolution enters the skills graph and silently biases every downstream recommendation for that tenant, and the error is unattributable later because nothing recorded that a guess was made. An unresolved item is a counter you can watch, a queue you can work, and a metric you can set a target on. So the threshold is set where the marginal correct resolution stops being worth the marginal silent error, and in an enterprise data platform that point is conservative.
**Trap:** *"Who decided that threshold, you or the product owner?"* If it was you alone, that is a gap, because a precision/recall threshold is a product decision expressed as a number, and the right answer is that you presented the curve and the product owner chose the operating point. `[CONFIRM what happened.]` Saying "I chose it and in hindsight that should have been a product decision with the curve on the table" is a stronger answer than pretending it was jointly owned.

### 1.Q7 — How do you know a model upgrade did not break anything?
**Answer:** The 2,000+ row golden baseline covering the locale and tier matrix, run in CI, with aggregate assertions and tolerance bands rather than exact equality, plus 200+ unit and integration tests on the deterministic parts where exact assertions are correct: locale precedence, tenant scoping, pagination. The design decision that makes this work is separating "must never change" from "may drift within tolerance", because conflating them either blocks all improvement or catches nothing.
**Trap:** *"A new embedding model changes every vector. Your baseline diff will be enormous."* Correct, and that is why the baseline asserts on resolved skill ids and score orderings rather than on vectors or raw scores. An embedding change that preserves resolution decisions is a no-op at the assertion level. When the diff is genuinely large and intentional, it needs an explicit approval workflow with the baseline under version control, which is one of the things I would add: "the diff is expected" should be a reviewable act, not a Slack message.

### 1.Q8 — What was the actual root cause of the OOM, and why was raising the limit wrong?
**Answer:** The job materialised the entire ClickHouse result set into Python objects before embedding anything, so peak memory was a function of corpus size rather than batch size. Raising the limit therefore only relocates the failure to the next growth step, and the corpus grows by design. The symptom identified it: the process was killed with no traceback, which is the kernel OOM killer rather than a Python exception. Pagination made the working set a function of page size, and memory still ratcheted across pages because in CPython dropping a reference does not necessarily return arena memory to the OS and the cycle collector runs on its own schedule, so I added `gc.collect()` at page boundaries.
**Trap:** *"Isn't gc.collect() a hack?"* Yes. It compensates for allocator behaviour rather than removing the cause, and the structural fix is streaming with generators and bounded batches so no object graph large enough to matter ever exists. Placement still mattered: collecting inside the hot loop would have destroyed throughput, whereas at page boundaries the pause amortises over thousands of rows. Defending the workaround as elegant would lose the point the diagnosis just earned.

### 1.Q9 — Design the API. What does a caller send and get?
**Answer:** `POST /resolve` with a body of `{text, tenant_id, locale?}` returning `{skill_id | null, tier, score, alternatives[]}`. Three deliberate properties. The response carries the **tier** that matched, because a caller often needs to know whether this was the tenant's own skill or a global guess. It carries **score**, so a caller with a stricter precision requirement can raise the bar without a new endpoint. And it returns `null` with alternatives rather than an error on unresolved, because unresolved is a normal outcome, not a failure. Bulk resolution is a separate endpoint with its own limits rather than a loop over the single one, because the reranker batches and per-item calls waste that.
**Trap:** *"What is your caching strategy?"* Cache key must be (normalised text, tenant, locale, index version). Dropping tenant is a cross-tenant correctness bug, not just a cache miss; dropping index version serves stale resolutions after a rebuild. TTL alone is insufficient because a rebuild invalidates semantically, not temporally, which is why the version belongs in the key.

### 1.Q10 — If I gave you six months and a team, what would you build next?
**Answer:** Three things in order. First, hybrid lexical plus vector retrieval, because a large fraction of inputs are exact or near-exact matches that should never touch an embedding model, and that is both cheaper and more precise. Second, resolution feedback: capture when a human corrects a resolution and use it as supervision, because right now the system has no learning loop and every improvement is a model swap. Third, extraction upstream, turning free text into candidate skills, which is the explicit non-goal today and the largest adjacent value.
**Trap:** *"Which of the three would you cut if you had two months?"* Keep hybrid retrieval, cut the other two. Hybrid retrieval is bounded work with an immediate cost and precision win. The feedback loop is the highest ceiling and needs a labelling workflow, a store and a retraining path, so it is a quarter of work minimum. Extraction is a new system, not a feature. Sequencing by cost-to-value rather than by ambition is the answer.

---

# SYSTEM 2 — 8-Service AI Recommendation Platform

*2M+ users, ~25% engagement uplift, 307 commits, 178K+ net lines*

## 1. Context and constraints

The learning platform had no recommendation capability of its own. Greenfield: no event pipeline, no feature store, no user-context service, no serving path. 2M+ users across enterprise tenants, so multi-tenant isolation is a correctness requirement rather than a feature. Content is a learning catalogue plus a people graph, so recommendations are both content-based ("this course") and people-based ("this colleague has this skill"). The commercial expectation was a measurable engagement improvement, which meant the measurement path had to exist before the recommendation quality mattered.

## 2. Requirements

**Functional**
- F1. Serve ranked content and people recommendations per user per tenant.
- F2. Ingest user events at platform scale and reflect them in recommendations. `[CONFIRM: freshness target, e.g. within seconds, minutes, or next batch]`
- F3. Cold start: a new user or new tenant gets useful recommendations before any interaction history exists.
- F4. Search, as a first-class surface sharing the same retrieval substrate.
- F5. Generate content when the catalogue cannot satisfy demonstrated demand (System 3 adjacency).

**Non-functional**
- N1. Serving p99 under the page-render budget. `[CONFIRM: target and achieved]`
- N2. Tenant isolation on every path, including the vector index.
- N3. Event ingestion must not be able to degrade serving. Independent failure is a requirement.
- N4. Continuous improvement without a full retrain cycle, hence bandits rather than periodic supervised retraining.

**Non-goals**
- Not a general-purpose experimentation platform. `[CONFIRM: whether one existed, because this determines whether ~25% came from a holdout or pre/post.]`
- Not real-time model training. Learning is batch; serving reads the learned policy.
- Not cross-tenant collaborative filtering. Signal does not cross tenant boundaries.

## 3. Architecture

```
   client ──▶ ┌────────────────┐        ┌──────────────────┐
              │ FLOW SERVICE   │───────▶│ RECOMMENDATION   │
              │ orchestration, │        │ ENGINE           │
              │ surfaces, A/B  │◀───────│ CMAB scoring     │
              └────────────────┘        └──────────────────┘
                    │   ▲                    │        │
                    │   │                    ▼        ▼
                    │   │        ┌──────────────┐  ┌──────────────┐
                    │   │        │ VECTOR       │  │ USER CONTEXT │
                    │   │        │ SEARCH       │  │ features,    │
                    │   │        │ (shared      │  │ profile,     │
                    │   │        │  index)      │  │ skills       │
                    │   │        └──────────────┘  └──────────────┘
                    │   │              ▲                  ▲
                    ▼   │              │                  │
           ┌────────────────┐          │                  │
           │ SEARCH SERVICE │──────────┘                  │
           └────────────────┘                             │
                                                          │
           ┌──────────────────┐                           │
           │ COLLABORATION    │───────────────────────────┤
           │ AGENT            │   people-based recs       │
           └──────────────────┘                           │
                                                          │
   ═══════════════════ write / batch side ════════════════╪═════════
                                                          │
   events ──▶ ┌────────────────────┐                      │
              │ USER EVENT         │──────▶ store ────────┤
              │ PROCESSOR          │                      │
              │ (write-heavy)      │                      │
              └────────────────────┘                      │
                                                          │
              ┌────────────────────┐                      │
              │ USER-PROFILE DATA  │──────▶ MongoDB ──────┘
              │ PROCESSOR (batch)  │
              │ Python, was Java   │
              │ Spring Batch       │
              └────────────────────┘
                        ▲
                        │ CMAB reward attribution + feature build
              ┌────────────────────┐
              │ PySpark            │
              └────────────────────┘

   Cross-cutting: Redis (external-API hydration cache, 100+ content IDs
   per request), JWT TTL cache with automatic secret rotation (fleet-wide)
```

**Decomposition criterion, stated explicitly because this is the attack surface:** boundaries were drawn around **independent scaling and independent failure**, not around data entities. The serving path (recommendation engine, vector search, user context) is read-heavy and latency-bound. The user event processor is write-heavy and throughput-bound. The user-profile data processor is batch. Colocating those three means provisioning for the worst of the three and letting a bad batch run take down serving.

## 4. Key decisions

**D1 — Eight services rather than one well-factored monolith.**
Chose: eight independently deployable services.
Over: a modular monolith, which for a team of `[CONFIRM: size]` is a legitimate and frequently correct choice.
Because: the three scaling profiles above genuinely diverge, and multi-tenant isolation is easier to reason about and audit per service.
Accepted cost: eight deploy pipelines, eight dashboard sets, distributed tracing required to answer "why did this user get this recommendation", and network calls where a function call would do. **State this cost before the interviewer does.**
Revision: at least two of the eight would be merged today. `[CONFIRM which. The likely pair is user context and user event processor if they always change and deploy together.]` The rule: if two services always change and deploy together, they are one service plus a network hop.

**D2 — Event and context path built before the model path.**
Chose: ship ingestion, context and a measurable baseline first.
Over: building the ranking model first, which is the more interesting work.
Because: a recommender with no user context is a popularity list, and more importantly an unmeasurable platform cannot be steered. The event path is the prerequisite for every number the project was later judged on.
Accepted cost: the first visible output was weak, which is a real political cost on a project with a commercial expectation attached.

**D3 — Contextual multi-armed bandit rather than a supervised ranker.**
Chose: CMAB with PySpark for reward attribution and feature construction, scoring in real time.
Over: gradient-boosted or neural ranking on logged interactions.
Because: a supervised ranker trained on logged clicks learns the previous policy's preferences, and in a catalogue with content arriving continuously that feedback loop starves anything unseen. Framing it as exploration versus exploitation rather than as prediction is what makes new content reachable at all. `[CONFIRM: algorithm (LinUCB / Thompson sampling / epsilon-greedy) and the exploration parameter.]`
Accepted cost: bounded exploration means deliberately showing some users content the model is unsure about, and in an enterprise product a bad recommendation is a support ticket rather than just a lower metric, so the exploration rate is capped tighter than a consumer product would cap it. Also: offline evaluation of a bandit is genuinely harder, and a supervised model would have scored better on offline replay precisely because it optimises the logged policy.

**D4 — One shared vector search service.**
Chose: a single vector search service consumed by both the recommendation engine and the search service.
Over: each consumer maintaining its own index.
Because: two indices over the same content drift, and the drift shows up as search and recommendations disagreeing about what exists, which users notice and cannot report coherently.
Accepted cost: a shared service is a shared failure domain and a coordination point for schema changes.

**D5 — Distributed Redis cache in front of external content hydration.**
Chose: Redis, keyed per content id, so hydrating 100+ ids becomes a multi-get with a small miss set.
Over: in-process caching, and over asking the external team for a bulk endpoint (the better structural fix, not available in the timeframe `[CONFIRM]`).
Because: 100+ external calls per request dominated latency and made the external service the availability ceiling. Content metadata has a high read-to-write ratio, which is the workload a cache exists for. In-process caching multiplies misses by replica count and evaporates on deploy.
Accepted cost: a cache is a consistency compromise and another system in the path. `[CONFIRM: hit rate and TTL.]`
Revision: add bounded stale-while-revalidate, so an external outage degrades to slightly stale metadata rather than an error. A cache that helps latency but not availability is doing half its job.

**D6 — Java Spring Batch to Python for the user-profile data processor.**
Chose: rewrite, removing 3,447 lines of Java for an 812-line containerised Python service with direct MongoDB integration, explicit multi-tenant isolation, and a CSV-based historical migration.
Over: leaving it on the JVM, which was the zero-risk option.
Because: it was the only JVM service in a Python fleet, so it carried a second build pipeline, a second dependency treadmill and a second on-call runbook continuously and quietly. The 3,447-to-812 ratio is not a feature cut: most of the Java was Spring Batch scaffolding (readers, writers, processors, job and step configuration) and the actual transformation rules were a small fraction of it.
Accepted cost: migration risk, and a cutover to get right. CSV-based migration was chosen over live dual-write because for a batch job downtime is acceptable and a reproducible, inspectable artifact beats a lower-downtime, higher-risk path.
Revision: run old and new over the same input and diff outputs for a full cycle before cutover, rather than validating on samples. `[CONFIRM whether you did.]`

**D7 — Fleet-wide JWT TTL cache with automatic secret rotation.**
Chose: one shared mechanism, TTL tied to token lifetime, rotation automated, applied across the recommendation service fleet.
Over: per-service handling, and over no caching at all.
Because: the weakest service defines the fleet's credential-staleness window, so a per-service fix is not a fix. No caching is maximally safe and adds a token fetch to every request, which is a latency and rate-limit problem at this volume.
Accepted cost: a shared mechanism is a shared blast radius, and a change touching services other teams operate needs cross-team agreement.
Revision: alert on token-fetch failure rate and on rotation events. Silent rotation is good; invisible rotation is not, because the first sign of a broken rotation should not be a 401 storm.

## 5. Data model

```
user_event  (write-heavy, append-only)          user_context  (read-heavy)
  event_id        PK                              user_id + tenant_id  PK
  tenant_id       ── partition key                feature_vector
  user_id                                         skills[]            ← resolved
  content_id                                      recent_interactions[]
  event_type   view|start|complete|search|...     segment
  ts                                              updated_at
  context      JSON  (surface, locale, device)

content_vector  (shared index)         bandit_state
  content_id      PK                     arm_id  (content_id or policy id)
  tenant_scope    global | tenant_id     context_features
  embedding       vector                reward_stats  (counts, sums, or
  metadata        (cached in Redis)                    posterior params)
                                        updated_at   ← batch, PySpark
```

Partition and shard on `tenant_id` throughout. The reason is not only isolation: tenant is also the natural access pattern, since every query is scoped to one tenant, so tenant-first partitioning gives locality and isolation from the same choice.

The subtle modelling decision is that `bandit_state` is updated in batch by PySpark while being read in real time by the recommendation engine. That means serving reads a **snapshot of a policy**, not a live-updating model, and the freshness of that snapshot is a design parameter you must be able to state. `[CONFIRM: update cadence.]`

## 6. Scale numbers

| Quantity | Value | Source |
|---|---|---|
| Users served | 2M+ | resume |
| Services | 8 | resume |
| Commits | 307 | resume |
| Net lines of code | 178K+ | resume |
| Engagement uplift | ~25% | resume, **method `[CONFIRM]`** |
| Java lines removed | 3,447 | resume |
| Python replacement | 812 lines | resume |
| Content IDs hydrated per request | 100+ | resume |
| Serving p99 | `[CONFIRM]` | — |
| Peak events/sec | `[CONFIRM]` | — |
| Redis hit rate | `[CONFIRM]` | — |
| Recommendations served/day | `[CONFIRM]` | — |
| Team size | `[CONFIRM]` | — |

**Back-of-envelope for the estimation follow-up.** 2M+ users; if 10% are daily active, that is 200K DAU. At 5 recommendation-bearing page views per session, 1M recommendation requests per day, roughly 12 rps average and, with a working-hours-plus-timezone peak factor of 5-10x, something in the range of 60-120 rps peak. Each request hydrates 100+ content ids, so the uncached external call rate would have been 6,000-12,000 calls/sec, which is why the Redis layer was not optional. Present the arithmetic like this; the interviewer is scoring whether you can derive load rather than whether you memorised it.

## 7. Failure modes

| Symptom | Cause | How it was handled |
|---|---|---|
| Intermittent data anomalies on profile documents, only under peak | Concurrent read-modify-write on MongoDB across a network round trip is not atomic | Mutation moved into the database as an atomic update with a filter condition. Concurrency control lives where the data lives. `[CONFIRM: findOneAndUpdate with atomic operators / unique index / optimistic versioning]` |
| `Event loop is closed` / client attached to a different loop, load-dependent | Async client created on one event loop and used from another, or a module-level client outliving the loop that created it | Loop-scoped client lifecycle bound to application startup and shutdown, not broad exception handling |
| Recommendation p99 spikes under sustained load | 100+ external content-metadata calls per request; external service was the latency and availability ceiling | Distributed Redis cache keyed per content id, multi-get with a small miss set |
| 401 storms after a credential rotation | Stale cached credentials with no coordinated rotation across the fleet | Fleet-wide JWT TTL cache with automatic rotation, TTL tied to token lifetime |
| New content never gets shown | Supervised ranking on logged interactions reinforces the previous policy | Contextual bandit with bounded exploration |
| New users all see the same list | No interaction history, so collaborative filtering has nothing to work with | Content embeddings plus knowledge-graph traversal for cold start (see System 5's predecessor), blending toward CF as history accumulates |
| One dependency degrades and unrelated surfaces fail | Shared capacity across serving, ingestion and batch | Service boundaries drawn on independent failure; this is the payoff for D1's cost |
| Offline metrics improve, online metrics do not | Offline replay of a logged policy flatters supervised models and cannot evaluate exploration | Off-policy evaluation with inverse propensity scoring. **This was missing and is the main revision.** |
| Cannot answer "why did this user get this recommendation" | Eight services and no end-to-end trace | Distributed tracing. This is the recurring operational tax of D1. |

## 8. What I would change now

1. **Merge at least two services.** `[CONFIRM which.]` The evidence is deploy coupling: services that always ship together are one service plus latency. Start with fewer boundaries and split on observed evidence rather than on a diagram.
2. **Off-policy evaluation from the start.** Inverse propensity scoring on logged propensities, so a candidate policy can be compared to the live one without shipping it. Without this, every bandit change is an experiment in production.
3. **The measurement design before the platform.** `[CONFIRM whether ~25% came from a holdout, a staged rollout, or pre/post.]` If pre/post, say so plainly and name why a holdout was unavailable (tenant contracts, rollout mechanics, no experimentation platform). That answer scores better than a defensive one.
4. **Stale-while-revalidate on the Redis layer**, so the cache buys availability as well as latency.
5. **Parallel-run-and-diff for the Java to Python cutover** rather than sampled validation.
6. **Alerting on rotation events and token-fetch failures.**
7. **An explainability path on recommendations.** Enterprise buyers ask why, and in a bandit-driven system with exploration the honest answer sometimes is "we were exploring", which needs to be expressible rather than embarrassing.

## 9. The ten hardest questions

### 2.Q1 — Why eight services? Convince me this was not resume-driven architecture.
**Answer:** The criterion was independent scaling and independent failure, not tidy entities. Three profiles genuinely diverge: serving is read-heavy and latency-bound, event ingestion is write-heavy and throughput-bound, profile processing is batch. Colocating them means provisioning for the worst and letting a batch run take down serving. Having said that, eight is more than the criterion strictly justifies, and I would merge at least two today, because two of them always changed and deployed together, which means they were one service plus a network hop. The cost was real and continuous: eight pipelines, eight dashboard sets, and needing distributed tracing to answer a single-user question.
**Trap:** *"So you over-engineered it."* Partly, and the useful distinction is which boundaries were principled and which were aesthetic. The three-profile split I would make again. The boundaries that existed because they felt clean are the ones I would collapse. The generalisable lesson is that the cost of splitting a monolith later is real but bounded, while the cost of premature boundaries is paid on every deploy forever.

### 2.Q2 — Defend the ~25% engagement uplift. How was it measured?
**Answer:** `[CONFIRM: this is the most important gap in your prep. State the metric definition, the comparison design, the window, and the tenant scope.]` The structure of a good answer: metric definition first, comparison design second, confounders you could not remove third. Volunteer the method before being asked.
**Trap:** *"How do you know the platform caused it and not seasonality or a UI change?"* If you had a holdout, say so and describe the assignment unit (user or tenant) and why. If it was pre/post, the honest answer is that you cannot fully separate it, you can only bound it: name the confounders (seasonality, concurrent releases, tenant mix changes), say which you controlled for, and state that a holdout would have been the right design and why it was not available. Inventing a controlled experiment you did not run is the single highest-risk lie available in this round, because the follow-up questions about assignment and power will expose it.

### 2.Q3 — Why a bandit and not a ranking model? Bandits are harder to operate.
**Answer:** Because the catalogue grows continuously and a supervised ranker trained on logged clicks learns the previous policy's preferences, so unseen content is never shown and therefore never generates the data that would justify showing it. That is a self-reinforcing loop that offline metrics cannot detect, because offline replay scores you against the logged policy. Framing it as exploration versus exploitation makes new content reachable at all. I bounded the exploration rate tightly because in an enterprise product a bad recommendation is a support ticket, not just a lower metric.
**Trap:** *"How did you evaluate a candidate policy without shipping it?"* Honestly: not well enough. Off-policy evaluation with inverse propensity scoring on logged propensities is the right answer and it was missing, which meant policy changes were effectively live experiments. That is the main thing I would fix. Claiming rigorous offline evaluation of a bandit and then being unable to describe IPS or a doubly-robust estimator is a fast way to lose the round.

### 2.Q4 — How do you keep tenants isolated in a shared vector index?
**Answer:** Tenant is part of the partition and filter on every read, and it is a prefix of the physical ordering so the filter prunes before the ANN search rather than after. There is no code path that queries the index without a tenant scope, and that is enforced by making tenant a required, non-defaultable parameter rather than a convention, because a convention is a bug waiting for a refactor. Global content is a separate explicit scope rather than an absent tenant, so "no tenant" never means "all tenants".
**Trap:** *"What if a tenant has only 50 items? Your ANN index is useless for them."* Correct, and the right answer is that ANN is the wrong algorithm below a threshold. Below a few thousand vectors an exact scan is both faster and exact, so the retrieval path should choose by tenant cardinality. `[CONFIRM whether it did.]` Small tenants are also where HNSW graph connectivity degrades, so a shared index with a tenant filter is better for them than a per-tenant index would be, but exact search is better still.

### 2.Q5 — Walk me through one request end to end, with the latency budget.
**Answer:** Flow service receives the request, resolves tenant and user, and fans out: user context for features, vector search for candidates, recommendation engine for CMAB scoring over those candidates, then hydration of 100+ content ids through Redis with a small miss set going to the external API, then assembly and return. `[CONFIRM: the actual per-stage budget.]` The two facts to state without being asked: hydration was the dominant term before the cache, which is why the cache exists, and the fan-out is parallel rather than sequential, because serialising context and candidate retrieval would add their latencies rather than taking the max.
**Trap:** *"What happens when the external metadata API is down?"* Before the cache: the request fails. After the cache: cache hits are served and misses fail, so it degrades by hit rate, which is better but not a design. The answer I would give now is stale-while-revalidate with a bounded staleness, so an outage degrades to slightly old titles rather than an error, plus a circuit breaker so the miss path fails fast instead of consuming the request budget on a dead dependency.

### 2.Q6 — 3,447 lines of Java became 812 lines of Python. What did you drop?
**Answer:** Nothing functional. Most of the Java was Spring Batch scaffolding: item readers, item writers, processors, and job and step configuration. The business logic, the actual transformation rules, was a small fraction of the file count, and that is what got ported. The new service added things the old one lacked, specifically explicit multi-tenant isolation rather than the old implicit scoping, and containerisation.
**Trap:** *"How did you prove output equivalence?"* `[CONFIRM: row counts and checksums, sampled diffs, or a full parallel run.]` If you sampled, say so and name the parallel-run-and-diff over a full cycle as what you would do now. Then the rollback question: what the abort path was on day one if the new job was wrong. A migration story without a rollback story is incomplete, and interviewers who have done migrations ask for it specifically.

### 2.Q7 — Your Redis cache: what is the invalidation strategy?
**Answer:** Content metadata is high read-to-write, so TTL-based expiry carries most of the load, with the TTL chosen against how stale a title or description may acceptably be. `[CONFIRM: TTL and hit rate.]` Distributed rather than in-process, because with N replicas an in-process cache gives N times the misses and N times the external load, and it evaporates on every deploy exactly when you are already restarting things.
**Trap:** *"What about a thundering herd when a hot key expires?"* This is the real question. With 100+ ids per request and shared hot content, simultaneous expiry sends every replica to the external API for the same key. Mitigations, in the order I would apply them: jittered TTLs so keys do not expire in lockstep, single-flight or a short-lived lock per key so one fetch populates for all waiters, and stale-while-revalidate so waiters get the old value while one request refreshes. Naming jitter alone is a partial answer; the herd is a concurrency problem, not just a scheduling one.

### 2.Q8 — How would you scale this to 20M users?
**Answer:** Take the terms in order. Event ingestion is horizontal on tenant partitioning already, so it scales by partitions and consumer count; the risk is partition skew from a few very large tenants, which needs a composite key rather than tenant alone. Vector search at 10x needs the index sharded, and the natural shard is tenant, which is also the query scope, so it shards cleanly. The bandit state grows with arms times context buckets, which is where I would expect the real trouble, because a per-tenant policy at 10x tenants is a state-size and staleness problem rather than a compute one. The Redis layer scales by cluster, and the hit rate should *improve* with scale since hot content concentrates. And serving is stateless, so it scales on replicas until the databases behind it do not.
**Trap:** *"Which of those breaks first?"* Give a specific answer rather than a list. Most likely the bandit state and its batch update cadence, because it is the only component whose *update* path scales with both users and content and which is not horizontally partitioned by the same key as everything else. The follow-up value comes from naming the bottleneck and its symptom: policy snapshots getting staler under load, which shows up as recommendation quality quietly declining rather than as an error.

### 2.Q9 — What would you have cut if you had half the time?
**Answer:** The collaboration agent and the flow service's more elaborate orchestration, keeping content recommendations, the event path and measurement. The reason is that the event path and the measurement design are load-bearing for everything else: without them you cannot tell whether any of the rest worked, and a recommendation platform you cannot evaluate is a random number generator with a deployment pipeline. People-based recommendations are additional surface area on the same substrate, so they are deferrable in a way that measurement is not.
**Trap:** *"Would you have cut the bandit?"* Yes, for a first version, in favour of a simpler scored ranking with an explicit exploration slot, because the bandit's value is compounding over time and its operational and evaluation cost is front-loaded. Saying you would keep the most sophisticated component under time pressure is the wrong instinct and interviewers read it as attachment to the interesting work.

### 2.Q10 — If this were a company-wide platform, what would you have had to do differently?
**Answer:** Three things. Make the interfaces contracts rather than internal APIs, with versioning and deprecation policy, because a consumer you do not control cannot be migrated by editing their code. Publish the semantics of the numbers, since "engagement" means different things to different teams and a shared platform that exposes an ambiguous metric will have its numbers used in decks you never see. And separate the policy layer from the serving layer, so another team can bring its own ranking objective without forking the platform.
**Trap:** *"How would you have handled another team wanting a different ranking objective?"* Make the objective a parameter of the policy rather than a fork of the engine, and require them to bring their own reward definition and their own evaluation. The failure mode to name is the platform becoming a collection of special cases because each new consumer got a branch, which is how internal platforms die.

---

# SYSTEM 3 — A2A + FastMCP Multi-Agent Content Intelligence

*Replacing single-shot RAG for transcript processing, contextual chunking, and content gap detection at 2M+ users*

## 1. Context and constraints

The prior content intelligence system was a single-shot RAG pipeline: embed the query, retrieve chunks, stuff a prompt, return an answer. It could answer "what does this course cover". It could not do multi-step work: read a transcript, chunk it with awareness of surrounding context rather than by fixed window, and then reason about what the catalogue is missing relative to demonstrated demand. Those are three different tasks with three different failure modes and three different cost profiles, and no amount of query rewriting on a single-shot pipeline produces the third one.

Constraints: 2M+ enterprise users, multi-tenant, and the existing retrieval and skill-resolution capabilities (System 1) already worked and should be reused rather than reimplemented.

## 2. Requirements

**Functional**
- F1. Process transcripts into contextually chunked, retrievable units.
- F2. Detect content gaps: capabilities the catalogue does not cover relative to observed demand.
- F3. Reuse skill resolution and retrieval as capabilities rather than reimplementing them.
- F4. Steps must be independently retryable, because a transcript-processing failure should not force gap detection to rerun.

**Non-functional**
- N1. Bounded cost per transcript. Agentic systems fail commercially before they fail technically, because a loop with no step cap is an unbounded bill.
- N2. Observability per step: which agent, which tool, which tokens, which latency.
- N3. Tenant isolation preserved through every hop, including agent-to-agent messages.
- N4. Independent deployability of each agent.

**Non-goals**
- Not conversational. This is a pipeline that happens to be agentic, not a chatbot.
- Not autonomous action on the catalogue. Gap detection produces findings; publishing is a separate, gated concern (see System 2's content creator).
- Not a replacement for retrieval. Retrieval is a tool inside the loop.

## 3. Architecture

```
   transcript / catalogue event
              │
              ▼
   ┌────────────────────────┐     A2A      ┌────────────────────────┐
   │ TRANSCRIPT PROCESSING  │─────────────▶│ CONTEXTUAL CHUNKING    │
   │ AGENT                  │              │ AGENT                  │
   │  parse, segment,        │              │  boundary detection,   │
   │  normalise, locale       │              │  context carry-over,   │
   └────────────────────────┘              │  chunk + embed         │
              │                            └────────────────────────┘
              │                                       │
              │                                       │ A2A
              │                                       ▼
              │                            ┌────────────────────────┐
              └───────────────────────────▶│ CONTENT GAP DETECTION  │
                                           │ AGENT                  │
                                           │  demand vs coverage    │
                                           └────────────────────────┘
                                                      │
                                                      ▼
                                              gap findings ──▶ (gated)
                                                               content
                                                               generation

   ══════════════ shared capabilities, exposed as MCP servers ══════════════

   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ retrieval    │ │ skill        │ │ catalogue    │ │ LLM          │
   │ (vector +    │ │ resolution   │ │ metadata     │ │ inference    │
   │  rerank)     │ │ (System 1)   │ │              │ │ (System 4)   │
   └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
        FastMCP          FastMCP          FastMCP          FastMCP
        versioned tool contracts, reusable by any consumer

   Every agent step: step cap · token budget · per-tool timeout · trace id
```

**The two protocol roles, stated precisely because vagueness here is obvious to anyone who has used them.** MCP (Model Context Protocol, exposed here via FastMCP) is a **tool-surface contract**: it describes what a capability accepts and returns, which makes the capability versionable and reusable by a consumer that does not import your code. A2A (Agent-to-Agent) is **inter-agent messaging**: an agent boundary becomes a network boundary with its own retry, timeout and failure semantics. They solve different problems and using one does not imply the other.

## 4. Key decisions

**D1 — Three agents over A2A rather than one agent with all the tools.**
Chose: separate agents for transcript processing, contextual chunking and gap detection.
Over: a single ReAct agent with every tool attached, which was cheaper and would have shipped weeks earlier.
Because: the three have genuinely independent failure modes, cost profiles and deploy cadences. One agent with N tools has an N-way blast radius: a chunking prompt change degrades gap detection, and you cannot scale or roll back one behaviour without the others.
Accepted cost: network boundaries where function calls would do, a distributed failure model, and the need for tracing across hops to debug one run. **Say this before the interviewer says it**, because "most multi-agent systems are one agent with extra latency" is the standard and usually correct attack.
**The test to state:** separate agents only when failure modes, scaling profiles, or deploy cadences genuinely differ. Then show yours passes it.

**D2 — Shared capabilities as MCP servers rather than a shared library.**
Chose: FastMCP servers exposing retrieval, skill resolution, catalogue metadata and inference.
Over: an internal Python package imported by each agent.
Because: a library couples consumers to your release cycle and your runtime, whereas a tool contract can be versioned and consumed by anything, including a consumer written by another team in another language. Skill resolution in particular was already a production capability (System 1) and reusing it as a contract rather than a dependency meant no coupling in either direction.
Accepted cost: a network hop and a serialisation boundary on every tool call, plus the operational burden of running the servers. For a latency-critical inner loop this would be the wrong choice; for a pipeline measured in seconds per transcript it is not.

**D3 — Retrieval kept in the loop as a tool, not discarded.**
Chose: agents call retrieval as an MCP tool.
Over: replacing RAG entirely with long-context prompting or with fine-tuning.
Because: the problem with the old system was that RAG *was* the whole system, not that retrieval was wrong. Retrieval remains the cheapest way to ground a step, and long-context prompting over an enterprise catalogue is both expensive and worse at precision.
Accepted cost: retrieval quality is now a dependency of every agent rather than of one pipeline, so a retrieval regression has a wider blast radius.

**D4 — Contextual chunking rather than fixed-window chunking.**
Chose: boundaries determined with awareness of surrounding content.
Over: fixed token windows with overlap, the default.
Because: transcripts have semantic structure and a fixed window routinely splits a concept across two chunks, so neither chunk retrieves well for a query about that concept. This is the most common quality ceiling in a RAG system and it is upstream of every clever retrieval trick.
Accepted cost: chunking becomes a model-dependent, non-deterministic step, so it needs its own evaluation and its own golden set, and re-chunking the corpus is now an expensive operation rather than a cheap one. `[CONFIRM: how chunk boundaries are actually determined, and whether chunk quality is evaluated.]`

**D5 — Step caps and token budgets as the outermost control.**
Chose: hard step count and token budget per run, enforced outside the agent logic.
Over: trusting the loop to terminate.
Because: an agent loop's failure mode is not an exception, it is a bill. The step cap is two lines of code and it prevents the incident that is hardest to explain afterward.
Accepted cost: a run can be truncated mid-task, so truncation must be a first-class outcome with a resumable state rather than a silent partial result. `[CONFIRM: what your caps actually are, and whether a truncated run resumes or restarts.]`

## 5. Data model

```
run                                   step
  run_id        PK                      step_id     PK
  tenant_id                             run_id      FK
  trigger       transcript|event         agent       enum
  status        running|done|            tool_calls  [{tool, args_hash,
                truncated|failed                       latency_ms, tokens}]
  step_count                            input_ref   ← pointer, not payload
  token_spend                           output_ref
  trace_id      ← joins all steps        status
                                         attempt

chunk                                  gap_finding
  chunk_id      PK                       finding_id  PK
  source_ref    transcript/course        tenant_id
  tenant_id                              skill_id    → System 1
  locale                                 demand_signal
  text                                   coverage_score
  embedding     vector                   status      new|reviewed|actioned
  boundary_meta  why it ends here        run_id      FK  ← provenance
```

Two modelling decisions worth defending. Steps store **references** to inputs and outputs rather than the payloads, because agent payloads are large and storing them inline makes the run table unusable within weeks. And `gap_finding` carries `run_id`, so every finding is traceable to the run and the model version that produced it, which is what makes a bad batch of findings retractable rather than permanent.

## 6. Scale numbers

| Quantity | Value | Source |
|---|---|---|
| Users served by the platform | 2M+ | resume |
| Agents | 3 (transcript, chunking, gap detection) | resume bullet |
| Shared MCP capabilities | retrieval, skill resolution, catalogue, inference | derived |
| Transcripts processed per day | `[CONFIRM]` | — |
| Tokens per transcript, p50 / p99 | `[CONFIRM]` | — |
| Cost per transcript | `[CONFIRM]` | — |
| Step cap per run | `[CONFIRM]` | — |
| End-to-end latency per transcript | `[CONFIRM]` | — |
| Gap findings per week, and acceptance rate | `[CONFIRM]` | — |

**Reliability arithmetic to have ready.** With three sequential agent steps at 95% per-step success, end-to-end success is 0.95³ ≈ 86%. At ten steps it is 0.95¹⁰ ≈ 60%, and at 85% per-step reliability ten steps completes only about 20% of the time. This is the number that justifies checkpointing over retry tuning, and it is the calculation that separates people who have run agents in production from people who have read about them.

## 7. Failure modes

| Symptom | Cause | How it is handled |
|---|---|---|
| Run consumes far more tokens than expected, no error | Agent loops without converging; retries inside the loop compound | Hard step cap and token budget enforced outside agent logic; truncation as an explicit outcome |
| Chunk retrieval quality drops after a chunking change, no code change to retrieval | Chunking is non-deterministic and model-dependent; boundaries shifted | Chunk-level golden set and evaluation. `[CONFIRM whether this exists. If not, it is the top gap.]` |
| One agent fails and the whole run restarts | No checkpoint; state lives in the loop | Per-step persisted state so a run resumes from the last good step. `[CONFIRM: whether it resumes or restarts. If it restarts, say so and cite the 0.95ⁿ arithmetic as why that is not acceptable at more steps.]` |
| Tool call succeeds but returns semantically wrong data, agent proceeds confidently | A tool returning "no results" is not an error, so retry and error handling do not fire | Tools return structured outcomes distinguishing empty from failed, and the agent is prompted to treat empty as a fact rather than a retry trigger |
| Retrying a tool that is rate-limited makes it worse | Retry amplification against a throughput ceiling | Bounded concurrency plus backoff, not retry alone (same lesson as System 4's batch path) |
| Cross-tenant leakage in an agent hop | Tenant context not propagated through A2A messages | Tenant identity is part of the message envelope and required at every tool boundary, not carried implicitly in a session |
| Cannot explain why a gap finding was produced | No provenance | `run_id` on every finding; steps carry a shared `trace_id` |
| Findings arrive but nobody acts on them | Gap detection with no downstream workflow | Findings have a status lifecycle. A detection system without a workflow is a dashboard. |

## 8. What I would change now

1. **Build the evaluation set before the architecture.** This is the honest headline. There was a strong prior that multi-agent was correct and no numerical proof at decision time. An offline eval set for each agent's task would have made the choice evidenced rather than argued, and it would also have made the "is this actually better than the old pipeline" question answerable.
2. **Checkpointed, resumable runs** if they are not already. The 0.95ⁿ arithmetic makes this the highest-value reliability investment, well above retry tuning.
3. **Chunk-quality evaluation as a gate.** Contextual chunking is the largest quality lever in the system and currently the least measured.
4. **Per-agent cost attribution.** Knowing total cost per transcript is useful; knowing which agent spends it is what lets you optimise.
5. **A stated policy on when to collapse an agent.** The same discipline as System 2's service boundaries: if two agents always change together, they are one agent.

## 9. The ten hardest questions

### 3.Q1 — Most multi-agent systems are one agent with extra latency. Why is yours different?
**Answer:** State the test first, then show it passes. Separate agents are justified when failure modes, scaling profiles or deploy cadences genuinely differ. Transcript processing is I/O and parsing bound and fails on malformed input; contextual chunking is model-bound and fails by producing bad boundaries, which is a quality failure rather than an error; gap detection is analysis over the whole catalogue and fails by producing findings nobody accepts. Those are three different on-call responses and three different rollback decisions, and one agent with all three tools means a chunking prompt change can degrade gap detection with no way to roll back independently.
**Trap:** *"Which of the three would you merge?"* Have an answer rather than defending all three. Transcript processing and contextual chunking are the candidate pair, since they always run in sequence on the same input and a change to one usually implies a change to the other. If I merged them I would keep gap detection separate, because it runs on a different trigger and a different cadence. Refusing to name a merge candidate reads as attachment.

### 3.Q2 — What does MCP actually give you that a shared library does not?
**Answer:** Versioned contracts and consumer independence. A library couples every consumer to your release cycle, your language and your runtime, so a breaking change is a coordinated upgrade across every importer. A tool contract can be versioned, so a consumer can stay on v1 while another moves to v2, and a consumer in a different language or a different process can use it without vendoring anything. Concretely, skill resolution was already a production capability, and exposing it as an MCP server meant the agents consumed it without either side depending on the other's code.
**Trap:** *"You added a network hop and serialisation to every tool call. Was that worth it?"* For this workload, yes, because runs are measured in seconds per transcript and the hop is noise against an LLM call. For a latency-critical inner loop it would be the wrong choice, and I would say so plainly. The general rule: MCP where the boundary buys reuse or independent versioning, in-process where the call is hot. Presenting MCP as universally correct is the failure.

### 3.Q3 — Walk me through what happens when the chunking agent fails on transcript 4,000 of 10,000.
**Answer:** `[CONFIRM: your actual behaviour.]` The defensible design: per-item processing with per-item status, so a failure marks one transcript failed and the batch continues, plus per-step persisted state so the failed item resumes from its last good step rather than from the beginning. The property to protect is that partial success is representable, because a batch that is all-or-nothing at 10,000 items will never complete.
**Trap:** *"What if it fails on 4,000 items because the model provider is degraded?"* Then per-item retry is the wrong response, because you are retrying into a systemic failure and amplifying load on a struggling dependency. That needs a circuit breaker at the batch level: detect that the failure rate across items has crossed a threshold, stop the batch, and preserve the completed work. Retrying individual items when the dependency itself is down is the classic retry-storm mistake transplanted into an agent pipeline.

### 3.Q4 — How do you evaluate this? "It works" is not an answer.
**Answer:** Three levels, and be honest about which existed. Per-agent task-level evaluation, so chunking is scored on retrieval quality of the resulting chunks and gap detection on acceptance rate of its findings. End-to-end, on whether content gaps that were detected were real, which requires human labels. And operational: cost per transcript, step distribution, truncation rate, failure rate by agent. `[CONFIRM which of these you had.]` The one that matters most and is hardest is chunk quality, because it is upstream of everything and its failures are silent.
**Trap:** *"You said you should have built the eval set first. Why didn't you?"* Because the architecture decision felt urgent and the eval set felt like something you could add later, which is the standard trap and I fell into it. The specific cost was that I could not prove the multi-agent design was better than a well-tuned single-shot pipeline, only argue it. That is the answer; do not dress it up.

### 3.Q5 — What stops a run from costing $500?
**Answer:** A hard step cap and a token budget enforced outside the agent's own logic, because a limit the agent can reason about is a limit the agent can talk itself past. Truncation is an explicit outcome with resumable state rather than a silent partial. `[CONFIRM: the actual caps.]` The framing: an agent loop's characteristic failure is not an exception, it is a bill, and the cost controls are two lines each while being the difference between a bad afternoon and a conversation with finance.
**Trap:** *"What if the cap truncates a legitimately long transcript?"* Then the cap is wrong for that input class, and the fix is a per-class budget rather than a global one, plus a metric on truncation rate so you find out from a dashboard rather than from a user. The wrong fix is raising the global cap, for the same reason raising a memory limit was the wrong fix for the OOM: it converts a bounded failure into an unbounded one.

### 3.Q6 — Tenant isolation across A2A hops. How?
**Answer:** Tenant identity is part of the message envelope and is a required parameter at every tool boundary, not something carried implicitly in a session or inferred from the caller. The reason to be strict is that an agent hop is a place where context gets rebuilt, and anything implicit gets dropped exactly there. Making tenant non-defaultable means a hop that forgets it fails loudly instead of resolving against the wrong scope.
**Trap:** *"How do you test that?"* Negative tests: a run initiated for tenant A must not be able to retrieve tenant B's content at any hop, asserted per tool and per agent boundary. This is the same lesson as the cross-tenant authorization finding in System 1, and the general principle is that isolation without a negative test is an intention. Saying "we're careful about it" is the answer that fails.

### 3.Q7 — Why not just use a long context window and skip the agents?
**Answer:** Because the task is not "read this and answer", it is "process, transform, and then reason across the whole catalogue". Long context handles the first part of that and does nothing for the third, since the catalogue does not fit and would not be worth the tokens if it did. Also cost and precision: retrieval over a well-chunked corpus is dramatically cheaper per query than a large context, and precision on a specific lookup is better with retrieval than with a model attending over a large irrelevant span.
**Trap:** *"Context windows keep getting bigger and cheaper. Does your design survive that?"* Partly, and be honest about which part. The retrieval-for-cost argument weakens as context gets cheaper. The multi-step argument does not, because gap detection is a different task from summarisation regardless of window size, and the state and control flow it needs are not a context-length problem. The parts of the design most exposed to cheaper long context are the chunking sophistication and the retrieval stage, and I would expect those to simplify.

### 3.Q8 — Three sequential steps. What is your end-to-end success rate?
**Answer:** Multiplicative. At 95% per step, 0.95³ ≈ 86%, so roughly one in seven runs fails somewhere even with individually reliable steps. That arithmetic is the argument for checkpointing rather than for better retries, because retry improves per-step reliability by a bounded amount while checkpointing removes the multiplication entirely by making the failed step the only work to redo. At ten steps and 85% reliability, the completion rate is about 20%, which no retry tuning fixes.
**Trap:** *"So what is your actual per-step success rate?"* `[CONFIRM.]` If you do not have it, say so, and say what you would instrument: success and failure per agent per attempt, which is the minimum needed to compute the product. An engineer who can do the arithmetic but has not measured the inputs is in a much better position than one who has neither, and admitting it is far better than guessing a number that will not survive the next question.

### 3.Q9 — The old system was RAG. How did you migrate without a regression?
**Answer:** `[CONFIRM: your actual migration approach.]` The defensible design: run the new pipeline alongside the old on the same inputs, compare outputs on the tasks the old system could do, and only cut over per-capability rather than all at once. The subtlety is that the new system does strictly more, so on the overlapping tasks it must be at least as good, and the non-overlapping tasks have no baseline at all, which is a different kind of risk: there is nothing to regress against and therefore nothing to catch a bad result.
**Trap:** *"What if the new system was worse on the overlapping tasks?"* Then it does not ship for those tasks, and the honest position is that "it can also do new things" does not license a regression on existing ones. That is a decision worth having made explicitly, because the pressure in a rewrite is always to accept a small regression in exchange for new capability, and accepting it silently is how rewrites lose user trust.

### 3.Q10 — Where does this design break?
**Answer:** Four places, in order of likelihood. Agent count: at three, distributed debugging is annoying; at ten, it dominates. Chunk quality: it is upstream of everything and the least measured, so a silent degradation there degrades every downstream output with no alarm. Cost: per-transcript cost is bounded by the step cap, but total cost scales with catalogue and transcript volume, and there is no per-agent attribution to optimise against. And the gap-finding workflow: findings without an accept/reject loop become a dashboard nobody opens, which is a product failure rather than a technical one.
**Trap:** *"Which of those have you actually seen happen?"* Answer only from experience. If you have not seen a chunk-quality degradation, say that it is the risk you rate highest and have not observed, and that its absence of an alarm is itself the concern. Claiming to have lived through a failure you predicted is a claim the next three questions will test.

---

# SYSTEM 4 — LLM Serving and Inference Platform

*Self-hosted vLLM on SageMaker for Phi-4 and LLaMA-8B, plus Bedrock batch for the offline path*

## 1. Context and constraints

Multiple services across a 2M+ user platform needed LLM inference: recommendation-adjacent generation, content creation, chat-engagement analysis in the customer intelligence pipeline, and the agents in System 3. Two forces pushed away from a pure API approach. Per-token pricing scales linearly with usage, so at platform volume the bill grows with success. And some enterprise tenants have data-handling expectations that a third-party API complicates.

Two workload shapes existed and they were not the same problem. Online: many concurrent short requests, latency-sensitive, user-facing. Offline: large-scale generation and scoring, throughput-bound, nothing waiting.

## 2. Requirements

**Functional**
- F1. Serve open-weight models (Phi-4, LLaMA-8B) for online inference across multiple internal consumers.
- F2. Run large-scale offline generation and scoring without touching serving capacity.
- F3. Support model upgrades without downtime.

**Non-functional**
- N1. Throughput per dollar as the primary optimisation target for the online path.
- N2. p99 latency under a stated target at a stated concurrency. `[CONFIRM both]`
- N3. Offline jobs must not be able to degrade online latency. Capacity isolation is a requirement.
- N4. Cost per million tokens known and tracked. `[CONFIRM]`

**Non-goals**
- Not a frontier-model replacement. Tasks needing frontier quality use a hosted API; this platform is for the volume tier.
- Not multi-tenant model hosting for external customers.
- Not training or fine-tuning infrastructure. `[CONFIRM: PEFT is on your skills list. If fine-tuning ran on this platform, it belongs in requirements rather than non-goals.]`

## 3. Architecture

```
   ONLINE PATH                                    OFFLINE PATH

   internal consumers                             batch producer
   (recs, agents, content gen)                          │
          │                                             ▼
          ▼                                     ┌───────────────┐
   ┌──────────────────┐                         │ S3            │
   │ inference client │                         │ JSONL payloads│
   │  (retry, timeout,│                         └───────────────┘
   │   budget)        │                                 │
   └──────────────────┘                                 ▼
          │                                     ┌───────────────────┐
          ▼                                     │ Amazon Bedrock    │
   ┌────────────────────────────────┐           │ batch inference   │
   │ SageMaker real-time endpoint   │           └───────────────────┘
   │ ┌────────────────────────────┐ │                   │
   │ │ vLLM                       │ │                   ▼
   │ │  · continuous batching     │ │           ┌───────────────┐
   │ │  · PagedAttention KV cache │ │           │ S3            │
   │ │  · Phi-4 / LLaMA-8B        │ │           │ scored output │
   │ └────────────────────────────┘ │           └───────────────┘
   │ GPU instances: g4dn / g5 class │
   │ [CONFIRM exact identifiers]    │           no capacity coupling
   └────────────────────────────────┘           to the online fleet
          │
          ▼
   autoscaling on concurrency / queue depth
   [CONFIRM: what you actually scaled on]

   SEPARATE CONCERN — rate limiting for LLM calls from distributed jobs
   PySpark/EMR executors ──▶ bounded async concurrency ──▶ provider
   (per-executor limits multiply by executor count: 20 × 10 = 200)
```

**Why the two paths are separate and this is the central decision.** They are not the same system with a different flag. An offline job pushed through the online endpoint contends for the same GPU capacity as user traffic, so a scheduled 1M-row generation becomes a latency incident. Splitting them decouples capacity, and it also lets each path pick its economics: batch endpoints are cheaper per token, real-time endpoints are provisioned for p99.

## 4. Key decisions

**D1 — Self-host open weights rather than call an API for the volume tier.**
Chose: Phi-4 and LLaMA-8B on SageMaker with vLLM.
Over: Bedrock or a commercial API for everything.
Because: per-token pricing scales linearly with usage, and some tenants' data-handling expectations complicate a third-party API. At platform volume, the fixed cost of owned GPU capacity beats marginal per-token cost above a break-even.
Accepted cost: you now own capacity planning, cold starts, model upgrades, and the on-call. This is a real and continuing cost and it is the honest half of the answer.
Missing: **the break-even in dollars was not modelled before building.** `[CONFIRM whether it was.]` Optimising for throughput and control is defensible; a cost model would have made the decision reviewable outside engineering, and that is the gap.

**D2 — vLLM rather than a naive model server.**
Chose: vLLM.
Over: a simple FastAPI-wrapped transformers server, or TorchServe.
Because: the workload is many concurrent short requests, and the binding constraint on that workload is not FLOPs, it is KV cache. A server that batches per request leaves the GPU idle between requests and holds a contiguous KV allocation per sequence sized to the maximum length, which fragments memory and caps concurrency far below what the hardware could do. vLLM's continuous batching admits new sequences into an in-flight batch as others finish, and PagedAttention allocates KV cache in fixed-size blocks like OS paging, so memory is allocated as sequences actually grow rather than reserved for the worst case. The practical consequence is that concurrency is limited by aggregate KV blocks rather than by per-sequence worst-case reservations.
Accepted cost: vLLM is a moving target with its own version-specific behaviour, and it is another component whose upgrades you own.

**D3 — Size instances for KV cache, not for weights, and benchmark rather than guess.**
Chose: benchmark candidate GPU families against the real request distribution at realistic concurrency, targeting throughput at a p99 bound.
Over: picking by GPU memory or by price tier.
Because: an 8B model in fp16 is roughly 16 GB of weights, so "it fits" is satisfied by many instances, and then throughput is decided by how much memory is left for KV cache. Sizing on weights alone gives you a server that loads fine and collapses under concurrency, which presents as throughput degradation rather than a clean OOM. Also, throughput per dollar is not monotonic in instance price.
Accepted cost: benchmarking time up front. `[CONFIRM: measured throughput, concurrency levels tested, p99 target, chosen instance per model, and the delta to the runner-up.]`
**Resume defect:** the resume lists `ml.4xlarge` and `g4.2xlarge`, which are not valid SageMaker instance identifiers. The real ones are almost certainly `ml.g4dn.2xlarge` and `ml.g5.xlarge`. Fix this before an AWS-literate interviewer reads it.

**D4 — Bedrock batch inference for the offline path.**
Chose: JSONL in S3, Bedrock batch inference, scored output back to S3.
Over: reusing the real-time vLLM endpoint for batch work, and over queueing batch work through the online endpoint at a throttled rate.
Because: batch is cheaper per token and, more importantly, has no capacity coupling to the serving fleet, so a large generation job cannot degrade a user-facing request. Throttled queueing works and is strictly more machinery for worse economics.
Accepted cost: a second inference provider in the architecture, and batch's own failure semantics, which are partial rather than clean.
Revision: explicit output validation before downstream consumption, because a batch job that is 99% complete is not a complete job, and the missing 1% is silent.

**D5 — Bounded concurrency, not retry, for LLM calls from distributed jobs.**
Chose: async rate limiting with an explicit in-flight ceiling, plus backoff for residual 429s.
Over: retry with exponential backoff alone.
Because: a rate limit is a throughput ceiling, so exceeding it and retrying is amplification, generating more requests at exactly the moment the provider is refusing them. Retry handles transient errors; it does not handle a sustained ceiling.
Accepted cost: bounded throughput on the LLM stage, which becomes the pipeline's critical path.
**The trap in your own design:** if the concurrency budget is enforced per executor, it multiplies by executor count. Twenty executors each holding ten in flight is two hundred in flight. `[CONFIRM whether your budget was global or per-executor.]` A global budget requires a shared counter, which is a distributed rate limiter, and the right move is to use one rather than build one.

## 5. Data model

There is little persistent state here, which is worth saying explicitly because it is a design property rather than an omission.

```
inference_request  (observability, not durable state)
  request_id     PK
  consumer       which internal service
  model          phi-4 | llama-8b | bedrock model id
  path           online | batch
  input_tokens, output_tokens
  latency_ms, queue_time_ms      ← queue time separated from compute
  status
  tenant_id                      ← for cost attribution per tenant

batch_job
  job_id         PK
  input_uri      s3://...   (JSONL)
  output_uri     s3://...
  row_count, rows_completed, rows_failed   ← partial completion is normal
  status
```

Separating `queue_time_ms` from `latency_ms` is the load-bearing detail. Under continuous batching, a latency regression is usually queueing rather than slower generation, and a single latency number cannot distinguish "the GPU got slower" from "there are more requests than slots". Without that split you will misdiagnose every capacity problem as a performance problem.

## 6. Scale numbers

| Quantity | Value | Source |
|---|---|---|
| Models served | Phi-4, LLaMA-8B | resume |
| Instance classes | g4dn / g5 class `[CONFIRM exact]` | resume (with defects) |
| 8B model weights, fp16 | ~16 GB | derived |
| Serving framework | vLLM | resume |
| Offline path | Bedrock batch, S3 JSONL in/out | resume |
| Throughput, tokens/sec | `[CONFIRM]` | — |
| p99 latency at target concurrency | `[CONFIRM]` | — |
| Cost per 1M tokens, self-hosted vs API | `[CONFIRM]` | — |
| GPU utilisation | `[CONFIRM]` | — |
| Break-even volume | `[CONFIRM: was not modelled]` | — |

**Derivation to have ready.** An 8B model at fp16 is about 16 GB of weights. On a 24 GB GPU that leaves roughly 6-7 GB for KV cache after framework overhead. KV cache per token is approximately `2 × layers × kv_heads × head_dim × 2 bytes`; for an 8B-class model that is on the order of 100-200 KB per token of context, so 6 GB supports very roughly 30,000-60,000 tokens of aggregate context, which at 2,000 tokens per sequence is 15-30 concurrent sequences. Present it as an order-of-magnitude derivation with the assumptions named, not as a precise figure: the point is that you know concurrency is a KV-cache budget, and the exact number depends on the model's attention configuration.

## 7. Failure modes

| Symptom | Cause | How it is handled |
|---|---|---|
| Throughput collapses as concurrency rises, latency climbs, no error | KV cache exhausted; requests queue or get preempted | Size for KV cache not weights; cap admitted concurrency; monitor queue time separately from generation latency |
| p99 spikes on a schedule | A batch job sharing capacity with online serving | Separate paths entirely: Bedrock batch for offline. This is D4's purpose. |
| 429 storm from the provider mid-job, whole stage fails | Distributed executors each retrying into a throughput ceiling | Bounded in-flight concurrency plus backoff; global budget rather than per-executor |
| First request after a scale-out or deploy is very slow | Cold start: model load and CUDA graph or engine warmup | Warm pool or provisioned concurrency, and a health check that does not pass until the model is loaded |
| Batch job reports success, downstream data is incomplete | Batch inference fails partially; 99% complete is not complete | Explicit output validation and row-count reconciliation before downstream consumption |
| Cost rises with no traffic change | A consumer changed prompt length or model, or a retry loop is silently re-inferring | Per-consumer and per-tenant token accounting; alert on cost per request rather than only total cost |
| Model upgrade degrades one consumer while improving others | Shared endpoint, per-consumer prompt sensitivity | Versioned model endpoints with per-consumer pinning and a migration window `[CONFIRM whether this existed]` |
| Agent or pipeline hangs waiting on inference | No timeout, or a timeout longer than the caller's own budget | Per-call timeout derived from the *caller's* total budget, not from the model's typical latency |

## 8. What I would change now

1. **Model the break-even in dollars, and keep it current.** The decision is defensible on throughput and control; without a cost model it is not reviewable by anyone outside engineering, and that limits how far the argument travels.
2. **Keep the benchmark as a repeatable script.** New instance families and vLLM version bumps should be re-evaluated in an hour rather than re-argued from memory.
3. **Batch output validation as a gate**, not a downstream discovery.
4. **Per-consumer cost attribution and alerting on cost per request.** Total cost tells you there is a problem; per-consumer tells you whose.
5. **Global rather than per-executor rate budgets** for LLM calls from distributed jobs.
6. **A documented policy for what belongs on which tier.** Self-hosted for high-volume routine tasks, batch for offline, hosted frontier API for tasks that genuinely need it. Without a written policy this drifts, and every new consumer relitigates it.

## 9. The ten hardest questions

### 4.Q1 — Justify self-hosting. Most teams should not.
**Answer:** Agreed, and the qualifier matters: below a volume threshold self-hosting is the wrong call and I would say so. Here the case was per-token pricing scaling linearly with a growing platform plus tenant data-handling expectations that a third-party API complicates. What makes it defensible rather than dogmatic is that I did not self-host everything: the offline generation path runs on Bedrock batch, and tasks genuinely needing frontier quality use a hosted API. The decision was made per workload shape, not once for the company.
**Trap:** *"What did it save?"* If you did not model it in dollars, say so directly: I optimised for throughput and control and can defend both, and the gap is that I never produced a cost model, which is what would have made the decision reviewable by a finance stakeholder. Do not invent a percentage. An interviewer who runs GPU capacity knows the numbers and will test yours.

### 4.Q2 — Why vLLM? What does it actually do?
**Answer:** Two mechanisms. Continuous batching admits new sequences into an in-flight batch as others complete, instead of forming a batch, running it to completion, and forming the next one, which leaves the GPU idle on every straggler. PagedAttention allocates KV cache in fixed-size blocks rather than a contiguous per-sequence allocation sized to the maximum length, so memory is consumed as sequences actually grow. The consequence that matters operationally is that concurrency becomes a function of aggregate KV blocks rather than of worst-case per-sequence reservations, which is a large multiple in practice on short-request workloads.
**Trap:** *"So what limits your concurrency?"* KV cache, not FLOPs. Then the derivation: an 8B model at fp16 is about 16 GB of weights, on a 24 GB card that leaves 6-7 GB for cache after overhead, and at roughly 100-200 KB per token for an 8B-class attention configuration that is tens of thousands of tokens of aggregate context, so tens of concurrent sequences at 2,000 tokens each. Give it as an order-of-magnitude derivation with assumptions stated. Answering "the GPU" without naming KV cache is the answer that fails this question.

### 4.Q3 — Why Bedrock batch and self-hosted online? Pick one.
**Answer:** No, because they are answers to different questions. Online is latency-bound with concurrent short requests, so it wants owned capacity provisioned for p99 and a server optimised for continuous batching. Offline is throughput-bound with nothing waiting, so it wants the cheapest per-token option and, critically, must not share capacity with serving. Running a 1M-row generation job through the real-time endpoint is how you cause a latency incident from a scheduled job. Splitting by workload shape is the decision; treating "which vendor" as the question is the mistake.
**Trap:** *"Two providers is two integrations, two failure modes, two bills. Was that worth it?"* Yes here, because the coupling it removes is capacity contention on a user-facing path, which is the failure I most wanted to make structurally impossible. It would not be worth it if offline volume were small, and the honest threshold is whether an offline job is large enough to move online p99. Below that, one path with a priority queue is simpler and correct.

### 4.Q4 — How did you choose instance types?
**Answer:** By benchmarking against the real request distribution at realistic concurrency, with throughput at a p99 bound as the objective, rather than by GPU memory or price tier. The reason memory alone misleads is that an 8B model fits on many instances, and what decides throughput is how much memory remains for KV cache; sizing on weights gives you a server that loads cleanly and degrades under load. And throughput per dollar is not ordered by instance price, so the biggest GPU is frequently not the best value for an 8B model.
**Trap:** *"Give me the numbers."* `[CONFIRM.]` If you do not have them, say what you measured and that you did not retain the figures, then describe the methodology precisely: concurrency levels swept, p99 target, tokens/sec at each, and cost per million tokens as the comparison metric. Methodology without numbers is recoverable; numbers you invent are not.

### 4.Q5 — Model upgrade with no downtime. Walk me through it.
**Answer:** `[CONFIRM: your actual process.]` The defensible design: versioned endpoints, deploy the new version alongside, shift traffic gradually with per-consumer opt-in, monitor per-consumer quality and latency, and keep the old version until every consumer has migrated. The reason per-consumer matters is that consumers have prompt-level dependencies on model behaviour, so an upgrade that improves aggregate quality can degrade one specific consumer, and an aggregate metric will not show it.
**Trap:** *"How do you know the new model is better before shifting traffic?"* Offline evaluation on task-specific sets per consumer, not a general benchmark, because a general benchmark improving says nothing about your extraction or classification prompt. If per-consumer eval sets did not exist, say so; that is the same gap as System 3's missing eval set and admitting the pattern is stronger than pretending to two different answers.

### 4.Q6 — A consumer says inference is slow. How do you diagnose it?
**Answer:** First split queue time from generation time, because under continuous batching a latency regression is usually queueing, and the two have completely different fixes: queueing is capacity, generation is model or configuration. Then check whether input or output token counts changed, since latency is roughly linear in output tokens and a prompt change upstream can present as an infrastructure problem. Then GPU utilisation and KV cache occupancy, to distinguish "not enough capacity" from "capacity is there but the cache is full". Only then look at the instance and the vLLM configuration.
**Trap:** *"Utilisation is 40% and it is still slow. Now what?"* That combination points at KV cache exhaustion rather than compute: the GPU is not busy because it cannot admit more sequences, so requests are waiting for cache blocks. The fixes are reducing max sequence length, reducing max concurrent sequences so admitted requests actually make progress, or moving to an instance with more memory. Reading 40% utilisation as spare capacity and adding traffic is exactly the wrong move and it is the common one.

### 4.Q7 — Your PySpark job calls the LLM from 20 executors. How do you not get rate limited?
**Answer:** Bound in-flight concurrency rather than relying on retry, because a rate limit is a throughput ceiling and retrying into it amplifies load precisely when the provider is refusing. Backoff handles the residual 429s that still occur. The trap in this design, which I want to name because it is the one I would check first in anyone else's code, is that a per-executor budget multiplies by executor count: twenty executors each holding ten in flight is two hundred in flight against a limit set for one process. `[CONFIRM whether yours was global.]`
**Trap:** *"So how do you enforce a global budget across 20 executors?"* That is a distributed rate limiter, which means a shared counter with atomic decrement, typically Redis, and it comes with its own failure mode: if the counter is unavailable you have to choose between failing closed, which stalls the job, and failing open, which is the problem you were preventing. My preference is fail-closed with a short timeout, because a stalled job is recoverable and a throttled provider affecting other consumers is not. Reducing executor count to control concurrency is the wrong fix, since it throttles the whole job to constrain one stage.

### 4.Q8 — Estimate the cost of serving 100M tokens a month both ways.
**Answer:** Do the arithmetic aloud with assumptions stated. Self-hosted: a g5-class instance is on the order of $1 to $1.50 per hour on demand `[CONFIRM current pricing]`, so about $750 to $1,100 per month per instance running continuously, and at a measured throughput of T tokens/sec one instance delivers T × 2.6M seconds per month. If T is 500 tokens/sec, that is roughly 1.3B tokens per month per instance, so 100M tokens is a small fraction of one instance and the fixed cost dominates. API: at a per-million-token price of P, 100M tokens costs 100 × P. The conclusion to draw out loud is that at 100M tokens per month the API is probably cheaper unless you need the capacity for other reasons, and the break-even is where API cost crosses the fixed cost of the minimum viable instance footprint including redundancy.
**Trap:** *"So self-hosting was wrong at your volume?"* This is the honest hard question. Give the volume, the redundancy requirement, and the non-cost reasons (data handling, latency predictability, no per-request quota) that carry weight independently of the arithmetic. If the arithmetic alone does not justify it at your volume, say that and say the non-cost reasons were the real drivers. That is a much stronger answer than defending a cost claim you cannot support.

### 4.Q9 — Batch job says success, downstream data is wrong. What happened?
**Answer:** Batch inference fails partially. Individual rows can fail on content filtering, malformed input, or length limits, and the job completes with a lower row count than it started with. If downstream consumes the output without reconciling counts, missing rows look like absent data rather than failed processing, which is silent and looks like a data problem rather than an inference problem. The fix is explicit validation as a gate: row-count reconciliation between input and output, a failure manifest, and a downstream contract that refuses partial input rather than absorbing it.
**Trap:** *"How would you find out today that this happened last month?"* Only from the job's own records if you kept them, which is why `row_count` and `rows_failed` belong in the job table rather than only in provider logs. If you cannot answer, the correct response is that you could not detect it retroactively, which is itself the argument for the validation gate. Silent partial failure is the characteristic failure of batch inference and being able to name it is a strong signal.

### 4.Q10 — When should someone not build this?
**Answer:** Below a volume threshold where owned GPU capacity is amortised, which for a small team is most of the time. Without an on-call rotation that can handle GPU capacity and model-loading failures, since the failure modes are unfamiliar and the mean time to diagnosis is long. When the task genuinely needs frontier quality, because an 8B open model is not a substitute and pretending otherwise ships worse product. And when demand is spiky rather than sustained, since you pay for provisioned capacity at the peak and idle it the rest of the time, which is exactly the case per-token pricing is good at.
**Trap:** *"Given all that, would you build it again?"* Yes for the sustained high-volume routine tasks, no for the whole surface, and that is the same answer as the original decision: split by workload shape. Saying you would build it all again unconditionally is a worse answer than a qualified one, because the qualifier is the evidence that you understand the tradeoff rather than the tool.

---

# SYSTEM 5 — Query Crafter: NL-to-SQL over a Federated Warehouse

*RAG plus GPT-4 plus Trino, 50% reduction in report turnaround*

## 1. Context and constraints

Non-technical stakeholders needed analytical answers and had to queue behind data engineers. The binding constraint was **the queue**, not query authoring difficulty, which is the reframe that determined the whole design: a faster query engine would not have moved the number, and a curated dashboard set would only have covered questions already known. Data spanned multiple sources, so answering a real business question often meant joining across them.

## 2. Requirements

**Functional**
- F1. Accept a natural-language business question and return an answer plus the SQL that produced it.
- F2. Execute against multiple sources without building a per-question pipeline.
- F3. Show the generated SQL to the user, always.

**Non-functional**
- N1. Wrong answers must be visible, not silent. A confidently wrong number ends up in a deck and is worse than no system.
- N2. Bounded blast radius: read-only, with limits on scan and runtime.
- N3. Latency tolerable for interactive use. `[CONFIRM]`

**Non-goals**
- Not a replacement for curated reporting on known questions. Dashboards remain correct for those.
- Not a write path. Read-only, by construction.
- Not schema management. It reads the schema; it does not change it.

## 3. Architecture

```
   natural-language question
              │
              ▼
   ┌──────────────────────────────────────┐
   │ SCHEMA + METADATA RETRIEVAL (RAG)    │
   │  · table and column descriptions     │
   │  · business glossary / metric defs   │
   │  · prior successful queries          │  ← highest-value corpus
   │  vector search over a schema corpus  │
   └──────────────────────────────────────┘
              │  relevant subset of schema, not the whole warehouse
              ▼
   ┌──────────────────────────────────────┐
   │ GENERATE  GPT-4 → SQL                │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ GUARDRAIL / VALIDATE                 │
   │  · read-only credential              │
   │  · parse + reject DDL/DML            │
   │  · allowlisted schemas               │
   │  · scan limit, row limit, timeout    │
   │  [CONFIRM which of these existed]    │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ TRINO  federated execution           │
   │   connector A · connector B · ...    │
   └──────────────────────────────────────┘
              │
              ▼
   result + THE GENERATED SQL shown to the user
```

## 4. Key decisions

**D1 — RAG over schema and metadata rather than the whole schema in the prompt.**
Chose: retrieve the relevant tables, columns, glossary entries and prior queries.
Over: putting the full schema in context, or fine-tuning on the organisation's SQL.
Because: a warehouse schema does not fit in a prompt, and even when a subset does, irrelevant tables actively hurt, since the model will happily join something plausible and wrong. Fine-tuning is more work than retrieval and goes stale on every schema change, whereas a retrieval corpus is updated by re-indexing.
Accepted cost: retrieval quality becomes the ceiling on generation quality. If the right table is not retrieved, no amount of prompt engineering recovers it, and that failure looks like a model failure while being a retrieval failure.

**D2 — Trino as the execution layer.**
Chose: federated execution over multiple sources.
Over: building a pipeline per question into a single warehouse.
Because: real business questions cross sources, and a per-question pipeline reintroduces exactly the engineering queue the system exists to remove.
Accepted cost: federated joins can be extremely expensive, and a generated query does not know which join is cheap. This is why scan and runtime limits are not optional here in a way they might be on a single warehouse.

**D3 — Always show the generated SQL.**
Chose: surface the SQL alongside the answer.
Over: returning only the number, which is the better user experience.
Because: an NL-to-SQL system that silently returns a wrong number is worse than no system, since the number goes into a deck and gets acted on. Showing the SQL means a wrong answer is inspectable by anyone who can read SQL, which includes the people who will be asked to verify it.
Accepted cost: it exposes complexity to non-technical users and can undermine confidence. Correct trade.

**D4 — Prior successful queries as retrieval corpus.**
Chose: index queries that worked, not only the schema.
Because: a prior query encodes join paths, filter conventions and business logic that the schema does not contain. A schema tells you a column exists; a prior query tells you that everyone filters out internal test tenants.
Accepted cost: it propagates the conventions of past queries, including their mistakes, and a wrong prior query becomes a wrong template. `[CONFIRM whether prior queries were in the corpus. If not, this is the highest-value addition.]`

## 5. Data model

```
schema_doc  (retrieval corpus)          query_log
  doc_id      PK                          query_id      PK
  kind        table|column|glossary|      question      text
              prior_query                 generated_sql text
  source      connector/schema/table      executed      bool
  text        description + context       row_count
  embedding   vector                      runtime_ms
  updated_at  ← staleness matters         user_verified bool  ← the signal
                                          error         nullable
```

`query_log.user_verified` is the important field and the one that usually does not exist. Without it there is no correctness metric, only an adoption metric, and adoption of a sometimes-wrong tool is a risk rather than a win.

## 6. Scale numbers

| Quantity | Value | Source |
|---|---|---|
| Report turnaround reduction | 50% | resume |
| Baseline turnaround | `[CONFIRM]` | — |
| How the 50% was measured | `[CONFIRM]` | — |
| Users / queries per week | `[CONFIRM]` | — |
| Query correctness rate | `[CONFIRM: probably not measured]` | — |
| Sources federated | `[CONFIRM]` | — |
| p50 / p99 question-to-answer latency | `[CONFIRM]` | — |

## 7. Failure modes

| Symptom | Cause | How it was handled |
|---|---|---|
| SQL is valid, runs, returns a plausible but wrong number | Wrong table or wrong join retrieved; the model cannot know it is wrong | Show the SQL. Retrieval quality is the real lever. `user_verified` is the missing metric. |
| A generated query scans the warehouse and costs a fortune | Federated join with no selectivity; the model has no cost model | Scan limits, row limits, query timeout, read-only credential `[CONFIRM which existed]` |
| Answers degrade after a schema change | Retrieval corpus stale relative to the warehouse | Re-index on schema change; track corpus `updated_at` against schema version |
| Users stop trusting it after one bad answer | No verification signal, so bad answers are found by users rather than by the system | Verification capture, plus showing SQL so errors are attributable rather than mysterious |
| Popular question answered differently on two days | Non-determinism in generation, plus retrieval variance | Cache question-to-SQL for verified questions and promote them to templates |
| A user asks something the data cannot answer, gets a number anyway | No "I cannot answer this" path | Explicit refusal when retrieval confidence is low, same principle as System 1's UNRESOLVED |

## 8. What I would change now

1. **Correctness as a tracked metric, not adoption.** Capture verification, measure the rate, and publish it. Adoption of an unmeasured tool is the failure mode here.
2. **Promote verified question-to-SQL pairs into templates.** The highest-value queries should stop being generated at all.
3. **A refusal path.** Low retrieval confidence should produce "I do not have the data to answer this" rather than a plausible query, for exactly the reason System 1 has an UNRESOLVED outcome.
4. **Cost estimation before execution.** Trino can explain a plan; a generated query with an estimated scan above a threshold should require confirmation.
5. **Prior successful queries in the retrieval corpus** if they are not already, since they carry the join and filter conventions the schema cannot.

## 9. The ten hardest questions

### 5.Q1 — NL-to-SQL demos well and fails in production. Why did yours not?
**Answer:** Be careful with this claim. What I can defend is that the design assumed it would sometimes be wrong and made that visible: the SQL is always shown, execution is read-only and bounded, and the reframe at the start was that the bottleneck was the human queue rather than query authoring, so the bar was "faster than waiting three days for a data engineer" rather than "correct like a curated dashboard". Whether correctness held up I cannot fully claim, because correctness was not tracked as a metric, and that is the honest answer.
**Trap:** *"So you shipped something you could not verify?"* Yes, with a specific mitigation, which was inspectability rather than measurement. That is a defensible interim position and a bad permanent one, and the fix is capturing verification so correctness becomes a number. Claiming it was rigorously validated invites a question about the validation method that will not go well.

### 5.Q2 — Why RAG over the schema instead of just putting the schema in the prompt?
**Answer:** Because the schema does not fit, and more importantly because irrelevant tables actively degrade generation: given fifty tables when three are relevant, the model will find a plausible join through the wrong ones. Retrieving the relevant subset raises precision. The corpus is not only DDL, it is table and column descriptions, business glossary and metric definitions, and prior successful queries, and that last category is the most valuable because it encodes join paths and filter conventions that no schema contains.
**Trap:** *"What happens when retrieval misses the right table?"* Generation cannot recover, and the failure presents as a model error while being a retrieval error, which is the single most important diagnostic distinction in this system. The mitigation is showing the SQL, so a human sees the wrong table immediately, plus a refusal path when retrieval confidence is low. Debugging this class of failure by tuning the prompt is the standard wasted week.

### 5.Q3 — What stops a generated query from taking down the warehouse?
**Answer:** Read-only credentials, so no DDL or DML is even expressible; SQL parsing to reject anything that is not a SELECT rather than relying on the model to comply; allowlisted schemas; and scan, row and runtime limits. `[CONFIRM which of these existed.]` The reason limits matter more here than on a hand-written query is that a federated join has no natural cost intuition and the model has no cost model at all, so the guardrail has to be structural rather than advisory.
**Trap:** *"A user could still write a legitimate query that scans everything."* Correct, and the answer is cost estimation before execution rather than a hard limit: use the engine's plan estimate and require confirmation above a threshold, so a legitimate expensive query is possible but deliberate. A pure hard limit makes some real questions unanswerable, which pushes users back into the queue you removed.

### 5.Q4 — Defend the 50% turnaround reduction.
**Answer:** `[CONFIRM: baseline, measurement method, and scope.]` The structurally important point is what the 50% is measuring: turnaround was dominated by queue time waiting for a data engineer, not by query authoring, so the improvement came from removing a queue rather than from making anything faster. That reframe is the reason the project worked, and it is what I would lead with.
**Trap:** *"Did the data engineers' workload actually drop, or did people just ask more questions?"* Both are plausible and they have different implications: if question volume rose, the 50% is a latency number and not a capacity number, and total data-engineering load may be unchanged. `[CONFIRM.]` Being able to distinguish "we removed a bottleneck" from "we induced demand" is the analytical rigour this question is testing, and either answer is fine as long as you know which one you have.

### 5.Q5 — Why show the SQL? Most users cannot read it.
**Answer:** Because the failure mode I most needed to prevent is a confidently wrong number entering a decision. Most users cannot read SQL, but the person who will be asked "where did this number come from" can, and showing it makes an error attributable and correctable rather than mysterious. It also changes user behaviour: people who see the query start to notice when a filter they expected is missing, even without deep SQL knowledge.
**Trap:** *"Doesn't that undermine confidence in the tool?"* Somewhat, and I accepted it. The alternative is unearned confidence, which is worse, and in an analytical tool trust should track correctness rather than exceed it. The framing I would use with a product owner is that a tool trusted more than it deserves generates decisions you will have to unwind.

### 5.Q6 — How do you handle a schema change?
**Answer:** Re-index the retrieval corpus, and track corpus freshness against schema version so staleness is visible rather than inferred from bad answers. This is the main operational advantage over fine-tuning: a schema change is a re-index, not a retraining run. The subtler problem is prior queries in the corpus that reference dropped or renamed columns, which become actively harmful templates, so the corpus needs validation against the current schema and not only refresh.
**Trap:** *"How do you know a schema change happened?"* Ideally an event from the catalogue or CI, not a scheduled poll, because between the change and the re-index every answer touching that table may be wrong. If it was scheduled, name the window as the exposure and say that event-driven invalidation is the fix. This is the same shape as the cache-invalidation problem in System 2: temporal expiry is a weak proxy for semantic invalidation.

### 5.Q7 — Trino federates. Was that the right choice or a constraint you inherited?
**Answer:** It was the right choice for this problem, because real business questions crossed sources and the alternative was building a pipeline per question, which recreates the engineering queue the project existed to eliminate. The cost I accepted is that federated joins can be very expensive and the generated query has no way to know which ones, which is precisely why the execution limits are structural.
**Trap:** *"Would you have preferred everything in one warehouse?"* For query performance and cost predictability, yes, and that is a data-platform project measured in quarters rather than a feature. The honest framing is that federation was the right choice given the platform I had, and consolidating the sources would have been the right choice given a mandate to change the platform. Distinguishing "best given constraints" from "best in principle" is the answer.

### 5.Q8 — What is the failure you never solved?
**Answer:** Correctness measurement. The system was inspectable but not measured, so I can tell you adoption and turnaround and I cannot tell you the rate at which it produced wrong answers. Everything else, cost controls, refusal paths, template promotion, follows from having that number, and without it you are prioritising by anecdote.
**Trap:** *"How would you measure it now, retroactively?"* Sample historical questions, have a data engineer produce ground-truth SQL independently, and compare result sets rather than query text, since two different queries can be equally correct. That gives a point estimate for the period sampled. Then add verification capture going forward. Proposing to compare generated SQL to reference SQL textually is the wrong answer and a common one.

### 5.Q9 — Would an LLM agent with tool access be better than this pipeline today?
**Answer:** Possibly for the hard tail, and probably not for the common case. An agent that can inspect the schema, run an exploratory query, look at the result, and revise handles the questions a single-shot generation gets wrong, and that is a real gain. It also costs more per question, takes longer, and has a much wider blast radius on the warehouse since it now issues multiple queries including exploratory ones. The design I would actually build is single-shot generation for the common case with an agentic escalation path when validation or user feedback says the first attempt failed.
**Trap:** *"You built the multi-agent system in System 3. Why not here?"* Because the criterion is the same one I used there: separate agents or multi-step loops when the failure modes genuinely differ and the extra steps buy something. Here most questions are answerable in one generation given good retrieval, so a loop mostly adds cost and warehouse load. Applying the fashionable architecture uniformly is the mistake, and being able to say "I built multi-agent there and would not here, for this reason" is a stronger signal than consistency.

### 5.Q10 — What would you build first if you restarted this?
**Answer:** Verification capture and a correctness metric, before any generation quality work, because every other decision depends on knowing the error rate. Then prior verified queries as both retrieval corpus and promotable templates, which is the highest-leverage quality improvement and costs almost nothing. Then a refusal path. Generation quality work last, because without a correctness number you cannot tell whether prompt changes helped.
**Trap:** *"That is a lot of measurement before any value."* Verification capture is a boolean and a log write, which is hours of work, not weeks, and it can ship alongside the first version. The mistake is treating measurement as a phase rather than as part of the first feature. That framing is what makes it fundable.

---

## Practical exercise (replaces "Build it from scratch")

There is nothing to implement here; the systems exist. Replace it with the rehearsal that actually gates this round. About 3 hours.

**Block 1 (45 min) — Whiteboard reps.** For each of the five systems, draw the diagram from memory on paper in under 90 seconds and narrate it out loud. Constraint: **no more than 9 boxes**. If you cannot draw it in 90 seconds, your diagram is wrong for an interview, not your memory. Do each system twice.

**Block 2 (40 min) — Close the CONFIRM list.** There are roughly 60 `[CONFIRM: ...]` markers above. Priority order: the ~25% measurement method (System 2), the SageMaker instance identifiers (System 4, this is a resume defect), p99 latencies for Systems 1 and 2, the reranker top-k (System 1), whether agent runs resume or restart (System 3), and whether the LLM rate budget was global or per-executor (System 4).

**Block 3 (35 min) — Estimation drill.** Without notes, derive: requests per second for System 2 at 2M users, the KV cache concurrency limit for an 8B model on a 24 GB GPU, the vector index size for 1.2M rows at 512 dimensions, and end-to-end success for a 3-step and a 10-step agent pipeline at 95% per step. These four derivations cover most of the quantitative follow-ups across all five systems.

**Block 4 (40 min) — The hostile pass.** For each system, pick the three questions above you least want to be asked and answer them out loud, timed at 90 seconds each. For System 2 those are almost certainly 2.Q1 (why eight services), 2.Q2 (the 25%) and 2.Q3 (bandit evaluation).

**Block 5 (20 min) — Write the non-goals.** For each system, write three non-goals from memory. This is the section interviewers use to test whether you designed the boundary or discovered it, and it is the one nobody rehearses.

---

## How it's done in production

**What a real design doc contains that an interview version compresses.** A production doc adds: an explicit reviewer list and sign-off, a rollout and rollback plan, an SLO section with error budget, a security and privacy review, a cost model, an operational runbook link, and a testing strategy. In an interview you compress all of that into two sentences each when asked, but knowing they exist is itself signal: a candidate who volunteers "the rollback plan was X" without being asked is describing a system they actually shipped.

**Templates worth matching.** Google's design doc (context, goals, non-goals, actual design, alternatives considered, cross-cutting concerns), the RFC form used at Rust and Oxide (motivation, guide-level explanation, reference-level explanation, drawbacks, rationale and alternatives, prior art, unresolved questions), and ADRs (context, decision, status, consequences) for the atomic decision unit. All three make **alternatives** and **consequences** mandatory, which is the same thing interviews score.

**Diagram discipline.** C4 levels 1 and 2 (system context, then containers) are what an interview needs. Level 3 (components) is usually too much detail for 45 minutes, and level 4 (code) never belongs. The practical rule is one diagram per zoom level, and never mix deployment topology with data flow on the same picture: the interviewer cannot tell which one they are looking at and neither can you halfway through explaining it.

### Failure-mode table for the presentation itself

| Symptom | Cause | Fix |
|---|---|---|
| Interviewer interrupts your diagram to ask something you had planned to cover later | You front-loaded context instead of getting to the architecture | 60 seconds of context maximum, then draw. Answer their question where they asked it; do not say "I was getting to that". |
| "Can you go deeper on X" and you cannot | Memorised the summary, not the mechanism | For each system, know one level below every box. Systems 1, 3 and 4 have the deepest mechanisms available. |
| You cannot answer a numbers question | Unfilled CONFIRM | Fill them, and where you cannot, practise "we did not instrument that" as a complete sentence. It scores better than a guess. |
| Diagram becomes unreadable halfway through | Too many boxes, no layout plan | 9 boxes, left-to-right data flow, drill-down target in the middle with space around it. |
| Every decision sounds obviously correct | No alternatives stated | Every decision gets "over Y, because Z, accepting cost C". If nothing was rejected, no decision was made. |
| The interviewer starts leading and you follow | You stopped driving | Offer directions explicitly: "I can go deeper on the retrieval path or on multi-tenancy, whichever is more useful." |
| "What was your specific contribution?" | "We" language throughout | First person for what you decided, "the team" only where genuinely shared, and be able to name the split. |
| Story contradicts a number you gave in an earlier round | Estimating figures fresh each time | Memorise the number table. Interviewers share notes. |

---

## Tradeoffs & when NOT to use it

**When presenting a resume system is the wrong move.**

- **When the interviewer asked for a generic design.** If they said "design a rate limiter", do not answer with your recommendation platform. Bridging to your own system is only appropriate when it is genuinely analogous, and "I've built something similar, may I use it as the example?" is a question, not a statement.
- **When you cannot go deep.** A system you contributed to but did not architect will collapse at the third follow-up. Better to present a smaller system you own completely. System 5 fully owned beats System 2 half-owned.
- **When the numbers are unconfirmed.** An unfilled CONFIRM under pressure becomes an invented number, and invented numbers fail in the follow-up. Present the systems whose numbers you have.
- **When the domain does not transfer.** For an infrastructure or systems role, an enterprise learning platform's engagement metrics land weakly. Lead with System 4 (GPU serving, KV cache, cost) or the OOM and concurrency work, not with the ~25% uplift.
- **When confidentiality binds.** The authorization finding in System 1 is a strong story told at the level of the bug class and your process. Do not describe an exploit. If pressed, say you will describe the pattern rather than the payload; the restraint is itself a signal.
- **Do not present all five.** In 45 minutes you will cover one, or one plus a shallow second. Pick by what the role needs and by which one you can defend deepest, then go deep. Breadth across five systems reads as a tour rather than as ownership.
- **Do not present the diagram you drew for your team.** An internal architecture diagram has 30 boxes because its readers already know the domain. An interview diagram has 9 because its reader does not.

---

## Interview questions

The 50 questions above are per system. These are the cross-cutting ones that arrive regardless of which system you present.

### Q1 — Pick one system and give me the two-minute version.
**Testing:** compression, and whether you know what matters in your own work.
**Answer:** 20 seconds of context and the constraint that made it hard, 40 seconds of architecture with the decomposition criterion, 30 seconds on the single most interesting decision including the alternative rejected, 20 seconds of numbers, 10 seconds offering a direction to go deeper.
**Follow-up trap:** *"You skipped the part I care about."* Expected, and the recovery is to go there immediately without defending your ordering. A two-minute version is a table of contents, not a summary, and the interviewer choosing a chapter is the round working as designed.

### Q2 — What was the hardest technical decision in that system?
**Testing:** whether you can identify difficulty, and whether "hard" means technically intricate or genuinely uncertain.
**Answer:** Pick a decision where the alternatives were close, not one where the answer was obvious in hindsight. Strongest available: ClickHouse HNSW versus a dedicated vector store (System 1 D2), eight services versus a monolith (System 2 D1), multi-agent versus single agent (System 3 D1), self-host versus API (System 4 D1). Each has a real cost you accepted.
**Follow-up trap:** *"What information would have changed your mind?"* Have a specific answer, because this is the question that separates a decision from a preference. For System 1 D2 it is measured recall degradation from ClickHouse's filtering strategy, or a second consumer appearing. Naming the disconfirming evidence proves you were choosing rather than justifying.

### Q3 — What is the weakest part of this design?
**Testing:** whether you can criticise your own work specifically.
**Answer:** Name one and be concrete. System 1: no hybrid lexical stage, so exact matches pay for an embedding model. System 2: no off-policy evaluation, so every policy change was a live experiment. System 3: chunk quality is unmeasured and upstream of everything. System 4: no cost model. System 5: no correctness metric.
**Follow-up trap:** *"Why did you not fix it?"* Answer in terms of sequencing and cost, not in terms of time. "It was not the binding constraint that quarter and here is what was" is a real answer; "we did not have time" is not, since nobody has time and you shipped other things.

### Q4 — How did you validate the system worked?
**Testing:** measurement discipline, which is where most candidates are thinnest.
**Answer:** Distinguish three layers explicitly: correctness (tests, golden baselines), quality (task-level evaluation), and impact (business metrics). System 1 has all three. System 2 has the third but was weak on the second. Say which you had.
**Follow-up trap:** *"How would you know if it silently degraded tomorrow?"* This is the strongest version of the question. Golden baselines in CI catch model and threshold drift; unresolved-rate and fallback-rate metrics catch silent behaviour change; and where you have neither, say so. Silent degradation without an alarm is the failure that ends up in a post-mortem, and naming which of your systems is exposed to it is a senior answer.

### Q5 — What would you change if traffic grew 10x?
**Testing:** whether you can identify the binding constraint rather than list scaling techniques.
**Answer:** Name the component that breaks first and why, with a symptom. System 1: the cross-encoder reranker, because it cannot be precomputed and scales linearly in candidates, presenting as p99 growth before any error. System 2: bandit state and its batch update cadence, presenting as recommendation quality quietly declining as policy snapshots get staler. System 4: KV cache, presenting as throughput collapse at moderate GPU utilisation.
**Follow-up trap:** *"And at 100x?"* The answer changes qualitatively rather than quantitatively, and saying so is the point: at 10x you tune and shard, at 100x the architecture assumptions themselves break, so System 1 would need a dedicated vector store, tiered indices and probably a distilled reranker. Continuing to list the same techniques at both scales is what a junior answer looks like.

### Q6 — Who else worked on this, and what did you personally do?
**Testing:** the credit-attribution question, asked directly.
**Answer:** Be specific and generous. Name what you decided, what you implemented, what you reviewed, and what others owned. `[CONFIRM: team composition per system. You need this and it is not on your resume.]`
**Follow-up trap:** *"What did you get wrong that a teammate caught?"* Have one. It evidences that review actually happened and that you are describing a team rather than a solo effort. A candidate who has never been corrected either did not work with anyone or is not telling you the whole story, and the interviewer will assume the second.

### Q7 — How did you decide what not to build?
**Testing:** non-goals, and whether the boundary was deliberate.
**Answer:** Pull directly from the non-goals sections. System 1 does not extract skills from free text. System 3 does not publish to the catalogue autonomously. System 5 does not replace curated dashboards. For each, name the reason the boundary is there.
**Follow-up trap:** *"Did anyone push for the thing you excluded?"* Almost certainly yes, and that makes this a conflict story as well. Describe their case as reasonable, describe the evidence you brought, and describe the outcome including the case where you lost. "Nobody asked for it" is a suspiciously convenient answer.

### Q8 — Walk me through an incident in one of these systems.
**Testing:** operational experience, which cannot be faked.
**Answer:** Symptom first, always. "The process was killed with no traceback" or "data anomalies only under peak load" or "p99 spiked on a schedule". Then how you localised it, then the fix, then the prevention. Systems 1 (OOM) and 2 (Mongo races, event loop, cache) have the strongest material.
**Follow-up trap:** *"What was the customer impact?"* Know it, or say you do not. Candidates who describe an incident with no impact assessment are describing a bug, not an incident, and the distinction is exactly what this question is checking.

### Q9 — If you were the interviewer, what would you probe?
**Testing:** self-awareness about your own weak spots, which is a genuinely hard question to fake.
**Answer:** Name your real gaps: the ~25% measurement method, the absent off-policy evaluation, the unmodelled break-even, the unmeasured chunk quality. Naming them first is disarming and it converts a gap into evidence of calibration.
**Follow-up trap:** *"So you know the gaps and did not close them."* The distinction that matters is gaps you identified and deprioritised deliberately versus gaps you only saw in hindsight. Be honest about which is which. The second category is normal; claiming everything was in the first category is not credible.

### Q10 — This is a lot of AI systems. Convince me you can do plain backend engineering.
**Testing:** whether the AI work rests on real engineering, which is a live concern for AI-heavy resumes in 2026.
**Answer:** Reach for the non-AI material and be concrete: the concurrency and atomicity work on MongoDB, the async client lifecycle bug, the caching design and its thundering-herd handling, the multi-tenant authorization fix, the Java to Python migration with its cutover strategy, the Airflow migration off Jenkins, the 4.5-hours-to-30-minutes pipeline rebuild. None of that is AI work and all of it is the reason the AI systems stayed up.
**Follow-up trap:** *"What is the hardest non-AI system you have built?"* Have one ready. The strongest candidate is the recommendation platform's serving and event infrastructure, described without the model: multi-tenant, caching, atomic updates under concurrency, distributed batch. Reaching for an AI story again after being asked for a non-AI one is the failure.

### Q11 — Estimate the infrastructure cost of one of these systems.
**Testing:** cost literacy, which most engineers lack and which is expected at principal level.
**Answer:** Derive rather than recall. System 1: 2.5 GB of vectors is a memory line item, and the reranker is the compute cost, scaling with QPS times candidates. System 4: GPU hours are the dominant term, so instance count times hourly rate times utilisation, plus the batch path per token. State assumptions out loud and give a range.
**Follow-up trap:** *"What is the biggest cost line and how would you cut it in half?"* For System 4 it is GPU hours, and the honest levers are higher utilisation through better batching, a smaller or quantised model where quality permits, and moving eligible traffic to the batch path. Say which of those you would try first and why, rather than listing all three.

### Q12 — Which of your systems are you least proud of?
**Testing:** honesty, and whether your self-assessment is calibrated rather than uniform.
**Answer:** Pick one and give a real reason. The defensible answer is System 5, because it shipped without a correctness metric and its value rested on inspectability rather than measurement, which is a defensible interim position and a bad permanent one.
**Follow-up trap:** *"Would you ship it again?"* Yes, with verification capture from day one, which is hours of work rather than weeks. The distinction to draw is between shipping something imperfect and shipping something unmeasurable. The first is normal engineering; the second is what you would not repeat.

---

## Red flags that fail you

- Presenting a system as obviously correct with no alternative rejected.
- Being unable to go one level below any box on your own diagram.
- Inventing a number when asked for one. Every interviewer has watched a fabricated figure collapse two questions later.
- Saying `ml.4xlarge` or `g4.2xlarge`. Not real SageMaker instance types. Fix the resume.
- Claiming a controlled experiment you did not run.
- Describing failures by cause instead of by symptom, which tells the interviewer you have not been on call.
- "We" throughout, with no ability to name your specific decisions.
- A diagram with 25 boxes.
- Defending eight services as obviously correct, or defending multi-agent as obviously correct. Both are the standard attack and both need the cost stated first.
- No non-goals. It reads as a design discovered rather than chosen.
- Claiming rigorous evaluation and then being unable to name the metric or the method.
- Saying "we didn't have time" as the reason a gap exists, rather than naming what was more important.

---

## Cheat card

```
DOC SHAPE   context → requirements (+NON-GOALS) → architecture → decisions
            (chose X over Y because Z, accepted cost C) → data model →
            scale numbers → failure modes (SYMPTOM first) → what I'd change

DIAGRAM     ≤9 boxes · 90 seconds · left-to-right data flow
            drill-down target in the middle with space around it
            never mix deployment topology with data flow

S1 SKILLS   54,486 skills · 22 locales · 1.2M+ rows · Titan v2 512-dim
            ClickHouse HNSW (filtered ANN, tenant+locale in ORDER BY prefix)
            BGE-Reranker-Large cross-encoder · tiers custom→external→master
            vectors ≈ 1.2M × 512 × 4B ≈ 2.5 GB float32
            OOM: exit 137, no traceback → paginate + gc.collect at page bounds

S2 RECS     8 services · 307 commits · 178K+ LOC · 2M+ users · ~25% uplift
            boundary criterion = independent SCALING + FAILURE, not entities
            CMAB not supervised (logged policy starves new content)
            Redis multi-get for 100+ content IDs · Java 3,447 → Python 812
            gaps: no off-policy eval (IPS), merge ≥2 services

S3 AGENTS   3 agents over A2A · shared capabilities as FastMCP servers
            MCP = versioned TOOL CONTRACT · A2A = inter-agent MESSAGING
            step cap + token budget OUTSIDE agent logic
            reliability: 0.95³≈86% · 0.95¹⁰≈60% · 0.85¹⁰≈20% → CHECKPOINT

S4 SERVING  vLLM: continuous batching + PagedAttention (KV in blocks)
            concurrency limited by KV CACHE not FLOPs
            8B fp16 ≈ 16 GB weights; 24 GB card → ~6-7 GB KV → tens of seqs
            size for KV not weights · split queue_time from latency
            Bedrock batch offline (no capacity coupling) · vLLM online
            rate limit: bound CONCURRENCY, don't retry; per-executor × N!

S5 QUERY    RAG over schema+glossary+PRIOR QUERIES → GPT-4 → guardrail → Trino
            ALWAYS show the SQL · read-only + scan/row/time limits
            50% turnaround = removed a QUEUE, not faster queries
            gap: correctness never measured, only adoption

DO FIRST    the ~25% measurement method · fix SageMaker instance names
            p99s for S1 and S2 · reranker top-k · resume-or-restart for S3
            global vs per-executor LLM rate budget

KILL SWITCH no alternative rejected · invented number · 25-box diagram
            "we" with no personal decision · no non-goals · cause-first failures
```

## Sources

- [Staff-plus interview processes — StaffEng](https://staffeng.com/guides/staff-plus-interview-process/) — accessed 2026-07-26
- [Project deep dive questions — ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide/blob/main/interview/questions/03-project-deep-dive.md) — accessed 2026-07-26
- [The Staff Engineer's System Design Playbook: How to Pass an L6+ Interview — DesignGurus](https://designgurus.substack.com/p/the-staff-engineers-system-design) — accessed 2026-07-26
- [5 Keys to Staff-Level System Design Interviews — Hello Interview](https://www.hellointerview.com/blog/staff-level-system-design) — accessed 2026-07-26
- [RAG System Design Interview Questions and Answers — Sanjay Kumar](https://skphd.medium.com/rag-system-design-interview-questions-and-answers-6c0b2865062e) — accessed 2026-07-26
- [Top Interview Questions on RAG for Data Science and AI Engineer Roles — BuildML](https://buildml.substack.com/p/top-interview-questions-on-rag-for) — accessed 2026-07-26
- [Why Senior Engineers Fail System Design Interviews — Deep Engineering](https://deepengineering.substack.com/p/why-senior-engineers-fail-system-design-interviews) — accessed 2026-07-26
- [A Senior Engineer's Guide to the System Design Interview — interviewing.io](https://interviewing.io/guides/system-design-interview) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
