# 30-Story STAR Bank Mined From Your Resume

> **Track:** T14 Behavioral & Principal · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T14-star-bank` · **Tags:** sprint, behavioral, critical

## The 30-second version

You have 7+ years and roughly 28 resume bullets; a behavioural loop will ask you 12 to 18 questions and every one of them is answerable from that set if you have pre-indexed it. This module converts each bullet into a story with a stated Situation, the Task you personally owned, the Actions in first person singular, a Result with a number, plus the two things most candidates omit and every senior interviewer scores: **the alternative you rejected and why**, and **what you would do differently now**. Each story carries a tag line mapping it to competencies and to the specific rubric language of Amazon, Google, Meta and Microsoft so that under pressure you retrieve by tag, not by memory. The bar is not "did something impressive"; it is "can articulate the decision, own the tradeoff, and quantify the outcome," and the failure mode is talking for four minutes without ever saying what *you* decided.

## Why this gets asked

Because a behavioural round is a fraud-detection exercise disguised as a conversation. The interviewer has hired someone who described a platform in "we" language, joined, and turned out to have written two of the eight services. So they probe: what exactly did *you* build, what did you decide versus receive, what broke, what did it cost, what would you change. Amazon formalises this with the Bar Raiser, an interviewer from outside the team who holds veto power and whose entire job is drilling past the rehearsed layer of your answer ([Exponent, 2026](https://www.tryexponent.com/blog/amazon-leadership-principles-interview) — accessed 2026-07-26). Google formalises it in the reverse direction: your interviewers write up quotable evidence and a hiring committee that never met you scores the *evidence*, not your charm ([ResumeAdapter, Google Interview Process 2026](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26). Both mechanisms punish the same thing, which is vagueness.

---

## Lineage: past → present → future

**What came before.** Unstructured interviewing was the default until the 1980s: the interviewer chatted, formed an impression, and hired on gut. The pain that killed it is well documented in the I/O psychology literature, most influentially Schmidt and Hunter's 1998 meta-analysis of 85 years of selection research, which put unstructured interviews at roughly half the predictive validity of structured ones and showed that the unstructured format mostly measured similarity to the interviewer. Behavioural Event Interviewing came out of David McClelland's competency work at McBer in the 1970s and formalised the premise that past behaviour under specific circumstances predicts future behaviour better than stated intent. STAR is the consulting-friendly packaging of that: Situation, Task, Action, Result. Amazon industrialised it in the 1990s and 2000s by pinning each interviewer to two or three named Leadership Principles so that a five-person loop covers the full rubric without overlap.

**Where it stands now.** Every large tech company runs a structured behavioural round with a written rubric, and the templates have converged: Amazon's 16 Leadership Principles, Google's four attributes (Role-Related Knowledge, General Cognitive Ability, Leadership, Googleyness), Meta's behavioural round known internally as "Jedi" scoring ownership, conflict, execution under ambiguity and learning from mistakes, Microsoft's per-round competency assignment ending in the "As Appropriate" round tailored to your earlier gaps. The live disagreement is about **weighting at staff-plus**. One camp treats behavioural as a screen you merely pass, with system design deciding the level. The other, more common at Amazon and increasingly at Meta E6+, treats it as the primary level-setting instrument, because scope and influence are things you can only evidence through narrative. The observable fact is that staff-plus rejections are more often written up as "insufficient evidence of impact beyond own team" than as technical failures, which tells you where the marginal point is. The second live disagreement is about STAR itself: a growing set of interviewers find rigid STAR recitation robotic and prefer a conversational deep dive, which is why you should internalise the *content* of STAR and deliver it as prose rather than announcing "the Situation was."

**Where it's heading.** Three directions. First, high confidence: **more resume-grounded probing, less hypothetical**. As LLMs made polished generic answers free, the discriminating signal moved to specifics that only the actual author of the work could produce, which is exactly why numbers like 3,447 deleted lines of Java are worth more in 2026 than they were in 2022. Second, medium confidence: **AI-assisted rounds bleed into behavioural**. Meta already runs an AI-assisted coding round at E6, and the stated intent is judging whether you can direct work including machine-generated work ([ClavePrep, Meta Interview Process 2026](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26); expect behavioural questions about when you overrode or trusted an agent. Have an answer. Third, speculative: structured written work samples (Anthropic-style take-homes and written reasoning exercises) partly displacing live behavioural rounds at AI labs, because writing is harder to fake in real time than speech. Treat that last one as a trend, not a plan.

---

## Mental model

A behavioural loop is a **sparse matrix lookup under a 5-second time limit**. Rows are your stories, columns are competencies. The interviewer names a column; you must return a row. If you built the matrix in advance, retrieval is instant. If you did not, you linearly scan seven years of memory while talking, which is what "um, let me think of a good one" sounds like.

```
            OWNER  AMBIG  CONFLICT  FAILURE  DATA   SIMPLIFY  DEPTH  CUSTOMER  FRUGAL
  S10 8svc    ##     ##       .        .      #        #        #       #         .
  S01 A2A     #      ##       #        .      .        ##       #       #         #
  S04 OOM     #      .        .        ##     #        .        ##      .         #
  S06 authz   ##     .        ##       #      .        .        #       ##        .
  S13 Java→Py #      .        #        .      #        ##       #       .         ##
  S15 vLLM    #      .        #        .      ##       .        #       .         ##
  S28 ETL     #      #        .        .      ##       #        #       #         #
              ↑
      each cell: ## = lead with this   # = usable   . = don't reach for it

  Retrieval rule: interviewer names a COLUMN → you return the ## row.
  Coverage rule: no column may be empty, and no single row may be the ## for
  more than three columns (otherwise you tell one story all loop and the
  panel's shared notes flag it).
```

The second half of the model is the **shape of a single answer**, and the shape is not symmetric:

```
   |----S----|----T----|--------------A--------------|---R---|--why not X--|--redo--|
     10%        10%                  50%               15%       10%          5%
     ~15s       ~15s                ~90s              ~25s      ~20s        ~10s
                                     ↑
              This is where the score is. First person singular.
              "I decided", not "we decided". "I benchmarked", not "it was benchmarked".
```

Candidates systematically invert this: 60% Situation (context they find interesting), 20% Action, no Result, no alternative. The interviewer's notes then read "could not determine candidate's personal contribution."

---

## How it actually works

### The six required parts, and the two optional ones that separate levels

| Part | Length | What it must contain | Failure if omitted |
|---|---|---|---|
| Situation | 1-2 sentences | System, scale, and the constraint that made it hard | Interviewer cannot calibrate difficulty |
| Task | 1 sentence | What *you* were accountable for, and whether you were assigned it or claimed it | Reads as "was staffed on a project" |
| Action | 60-90 seconds | 3-5 discrete decisions in first person, with mechanism | "Could not determine personal contribution" |
| Result | 20-30 seconds | A number, and how you measured it | "No evidence of impact" |
| **Alternative rejected** | 15-20 seconds | The design you did not pick and the cost you accepted | Reads as "found one thing that worked" |
| **What you would change** | 10 seconds | One specific, non-self-flagellating revision | Reads as "does not learn" |
| *Escalation* (optional) | when relevant | Who you had to convince and how | Required evidence at staff+ |
| *Blast radius* (optional) | when relevant | What else it affected and who else adopted it | The scope signal for principal |

**Claimed versus assigned is the level marker.** "My manager asked me to migrate the batch job" is senior work. "I noticed the Java batch job was the only JVM service in an otherwise Python fleet and was costing us a separate build pipeline and on-call runbook, so I proposed and ran the migration" is staff work. Same project. Different level. Go through every one of your bullets and mark A (assigned) or C (claimed), and lead with the C stories.

### Numbers hygiene

You have unusually good numbers. Protect them.

- **Every number needs a denominator or a baseline.** "~25% engagement uplift" invites "over what baseline, measured how, over what window, and was it a holdout or a pre/post?" If you cannot answer that, the number becomes a liability. Fill in the `[CONFIRM: ...]` markers below before your first loop.
- **Precise numbers beat round numbers.** 54,486 skills, 3,447 lines, 307 commits, 2,000+ golden rows. These are credible *because* they are odd. Never round them to "about fifty thousand."
- **Never inflate.** If you did not measure it, say "we did not instrument that, and in hindsight that was the gap." That answer scores higher than a fabricated number, and Bar Raisers are specifically trained to pull on numbers until they break.
- **Know the unit economics of your own systems.** If you self-hosted vLLM to save money, you will be asked how much. Have a defensible figure or say plainly that you optimised for throughput and data residency rather than a modelled dollar saving.

### The 30 stories

Format for each: verbatim source bullet, then S / T / A / R, then the rejected alternative, then the revision, then the tag line. `[CONFIRM: ...]` means the resume does not contain it and you must supply the real value before use. Do not invent.

---

#### S01 — Replacing the legacy RAG pipeline with an A2A + FastMCP multi-agent system
**Source bullet:** Architected an A2A (Agent-to-Agent) + FastMCP multi-agent system replacing legacy RAG pipelines, automating transcript processing, contextual chunking, and content gap detection for 2M+ enterprise users.
**S:** The learning platform's content intelligence ran on a single-shot RAG pipeline: retrieve chunks, stuff a prompt, return an answer. It could answer "what does this course cover" but could not do multi-step work like reading a transcript, chunking it with awareness of surrounding context, and then deciding what content the catalogue was missing. Scope was 2M+ enterprise users across a multi-tenant estate.
**T:** I owned the architecture decision for the replacement, not just the implementation.
**A:** I decomposed the work into agents with separate responsibilities (transcript processing, contextual chunking, gap detection) and connected them over A2A rather than making one large agent with many tools, because the failure modes are independent and I wanted them independently retryable and independently deployable. I exposed the shared capabilities as MCP servers using FastMCP so that tool surfaces were versioned contracts rather than in-process function calls, which meant a second consumer could reuse skill resolution without importing my code. I kept retrieval in the loop rather than throwing RAG away: the agents call retrieval as a tool, so the change was from "RAG is the system" to "retrieval is a capability."
**R:** The pipeline now automates transcript processing, contextual chunking and content gap detection end to end for 2M+ users, work that previously either did not happen or was manual. `[CONFIRM: gap-detection accuracy or coverage number, and latency/cost per transcript vs the old pipeline]`
**Rejected:** A single ReAct agent with all tools attached. Cheaper to build, and I would have shipped weeks earlier, but one agent with N tools has an N-way blast radius: a bad chunking change degrades gap detection, and you cannot scale or roll back one behaviour without the others. I also rejected keeping the single-shot pipeline and adding query rewriting, which would have improved answers but could not have done multi-step content-gap reasoning at all.
**Differently:** I would have put evaluation in before the architecture. I had a strong prior that multi-agent was right; I could not prove it numerically at decision time, and I should have built the offline eval set first so the choice was evidenced rather than argued.
**Tags:** architecture ownership, scope, simplification-vs-decomposition tradeoff, migration of a live system | **Amazon LP:** Think Big, Invent and Simplify, Ownership | **Google:** Role-Related Knowledge + Leadership (drove technical direction) | **Meta:** direction-setting, ambiguity | **Microsoft:** technical judgment, drive for results

#### S02 — Multi-tier skill resolution engine
**Source bullet:** Designed multi-tier skill resolution engine (custom → external → master) backed by ClickHouse HNSW vector indices, Amazon Titan Embed v2 (512-dim), and BGE-Reranker-Large semantic reranking, covering 54,486 skills across 22 locales (1.2M+ skill rows).
**S:** Enterprise tenants define their own skill taxonomies, buy external taxonomy feeds, and also need to map onto our master taxonomy. The same human skill can exist three times under three names in three languages, and downstream recommendations were splitting signal across duplicates.
**T:** I designed the resolution engine that decides, for an arbitrary input string, which canonical skill it means.
**A:** I built resolution as an explicit precedence cascade, custom then external then master, so tenant-specific vocabulary always wins over a global guess, which is the correct behaviour for a multi-tenant product even when the global match scores higher. Retrieval is vector recall over ClickHouse HNSW indices using Titan Embed v2 at 512 dimensions, then BGE-Reranker-Large as a cross-encoder over the top candidates, because bi-encoder cosine similarity is not sharp enough to separate near-synonyms like "data analysis" from "data analytics" and a cross-encoder that reads both strings together is. The corpus is 54,486 skills over 22 locales at 1.2M+ rows, so the reranker only ever sees a truncated candidate list `[CONFIRM: top-k into the reranker, e.g. 50 → 10]`.
**R:** One resolution path serving 54,486 skills in 22 locales with tenant precedence preserved. `[CONFIRM: resolution accuracy before/after, and p99 latency]`
**Rejected:** Pure lexical matching with a synonym dictionary, which was cheaper and fully explainable but does not survive 22 locales, and one flat embedding space with no tiering, which would have been simpler but silently overrides tenant vocabulary and is exactly the behaviour enterprise admins escalate about.
**Differently:** I would have added a per-tier confidence threshold with an explicit "unresolved" outcome earlier. A cascade that always resolves to *something* hides its own error rate.
**Tags:** ranking system design, multi-tenancy, i18n, precision/recall tradeoff | **Amazon LP:** Customer Obsession, Dive Deep, Are Right A Lot | **Google:** RRK depth, GCA | **Meta:** technical depth | **Microsoft:** design excellence

#### S03 — Choosing ClickHouse HNSW over a dedicated vector database
**Source bullet:** (same bullet as S02, different angle) ClickHouse HNSW vector indices ... 1.2M+ skill rows.
**S:** The skills data already lived in ClickHouse. The obvious 2026 default for vector search is a dedicated vector store, and I had shipped Weaviate previously, so choosing otherwise needed a reason.
**T:** I made and defended the storage decision for vector retrieval at 1.2M+ rows.
**A:** I chose to index in place with ClickHouse HNSW rather than stand up a separate vector service, on three grounds. First, at 1.2M rows and 512 dimensions the index is small enough that a dedicated distributed store buys capacity I do not need `[CONFIRM: measured index size and recall@k]`. Second, every real query is a *filtered* query, by tenant and by locale, and keeping vectors next to the relational columns means the filter is a native predicate rather than a metadata pre-filter bolted onto an ANN index, which is where filtered vector search usually goes wrong. Third, one fewer system means one fewer thing to keep consistent, backfill, and page someone about at 3am. I accepted the cost knowingly: ClickHouse's vector indexing is less mature than a purpose-built engine and I gave up features I would want at 100M rows.
**R:** Retrieval serves the resolution engine without a separate vector tier. `[CONFIRM: p99 retrieval latency and recall@10]`
**Rejected:** Weaviate, which I had already run in production for the search engine (S25), and pgvector. Weaviate would have been the safe résumé answer and better at 50M+ rows with heavy hybrid search; pgvector would have been fine but the data was not in Postgres. I would revisit at roughly an order of magnitude more rows, or the moment a second product needs the same vectors.
**Differently:** I would have written the crossover point down as a documented threshold at decision time rather than carrying it in my head, so the next engineer knows when to migrate.
**Tags:** build-vs-adopt, filtered ANN, operational simplicity, stated migration trigger | **Amazon LP:** Invent and Simplify, Frugality, Are Right A Lot | **Google:** GCA, RRK | **Meta:** technical judgment | **Microsoft:** technical depth

#### S04 — OOM during embedding generation over 1.2M multilingual rows
**Source bullet:** Fixed OOM on embeddings generation via paginated ClickHouse loading and gc.collect orchestration, enabling stable processing of 1.2M+ multilingual skill rows.
**S:** The embedding job died partway through a full rebuild of 1.2M+ multilingual skill rows. The observable symptom was the process being killed by the OS with no Python traceback `[CONFIRM: exact symptom, e.g. exit code 137 / OOMKilled in the pod events]`, which is the signature of the kernel OOM killer rather than an application exception.
**T:** I owned the fix, and the job was blocking the skill intelligence rollout.
**A:** I resisted the reflex fix, which was to raise the memory limit, because that only moves the failure to a larger row count. I established that the job materialised the full ClickHouse result set into Python objects before embedding, so peak memory scaled with corpus size and not with batch size. I converted the read to paginated loading so working-set memory became a function of page size, and then found that memory still ratcheted upward across pages, because in CPython freeing a reference does not necessarily return arena memory to the OS and the reference-cycle collector runs on its own schedule. I added explicit `gc.collect()` at page boundaries, deliberately placed between pages rather than inside the hot loop so the collector pause is amortised. I verified with a memory profile across a full run rather than declaring victory after one page.
**R:** Stable full-corpus processing of 1.2M+ rows. `[CONFIRM: peak RSS before vs after, and total wall-clock runtime]`
**Rejected:** Raising the container memory limit, which was a five-minute change and would have worked until the corpus grew. I said so explicitly at the time. I also considered rewriting the job in PySpark for distributed embedding, which is the right answer at 50M rows and unjustified overhead at 1.2M.
**Differently:** `gc.collect()` is a symptom-level fix. The structural fix is streaming with generators and bounded batches so no object graph large enough to matter ever exists, and I would design it that way from the start. I would also add a memory-ceiling assertion to the job so the next regression fails loudly in CI instead of at 3am.
**Tags:** production debugging, runtime internals, refusing the easy fix, honest about a workaround | **Amazon LP:** Dive Deep, Ownership, Insist on the Highest Standards | **Google:** GCA, RRK | **Meta:** debugging depth, ownership | **Microsoft:** engineering excellence
**Note:** this is one of your two best stories. It has a symptom, a wrong fix you rejected, a mechanism-level explanation, and an honest admission that the fix is not the ideal design. Lead with it for any "hardest bug" question.

#### S05 — Hardening 22-locale language inference
**Source bullet:** Hardened 22-locale language inference: implemented x-Language → Accept-Language → en_us header precedence chain, Unicode-aware locale normalization, and language-specific NLP model routing.
**S:** Language selection was inconsistent across callers. Some sent a custom `x-Language` header, some relied on the browser's `Accept-Language`, some sent nothing, and locale strings arrived in every casing and separator variant (`pt-BR`, `pt_br`, `PT_BR`). The result was non-English tenants intermittently getting English-model output, which looks like a broken product rather than a broken header.
**T:** I owned locale correctness for the skills intelligence platform across 22 locales.
**A:** I defined one explicit precedence chain, `x-Language` then `Accept-Language` then `en_us`, and put it in a single resolution function so there was exactly one place where locale is decided. I normalised Unicode-aware, which matters because case folding is not ASCII `lower()` once you have Turkish dotless i and similar; naive lowercasing produces locale tags that fail an exact-match lookup. Then I routed to language-specific NLP models off the resolved locale rather than letting each service decide, so a locale bug is one bug and not twenty-two.
**R:** Deterministic locale resolution across 22 locales with defined fallback. `[CONFIRM: reduction in locale-related tickets or mismatch rate]`
**Rejected:** Auto-detecting language from the input text, which sounds smarter and is what one reviewer suggested. I rejected it because detection on short strings, which is what a skill name is, is unreliable, and because a wrong auto-detection is silent whereas a missing header is diagnosable. I use detection as a signal, never as the source of truth.
**Differently:** I would have shipped a metric on fallback rate from day one. "How often are we silently falling back to `en_us`" turned out to be the single most useful number and I added it later than I should have.
**Tags:** i18n correctness, single source of truth, silent-failure prevention, defensive API design | **Amazon LP:** Customer Obsession, Insist on the Highest Standards, Dive Deep | **Google:** Googleyness (user empathy), RRK | **Meta:** quality bar | **Microsoft:** customer focus, global readiness

#### S06 — Cross-tenant object-level authorization bypass
**Source bullet:** Remediated OWASP Top-10 vulnerabilities: replaced string-interpolated SQL with parameterized queries and closed cross-tenant object-level authorization bypass across the skills intelligence platform.
**S:** In a multi-tenant enterprise platform, I found that object-level authorization was not enforced consistently, meaning a request carrying a valid token for tenant A could reference an object ID belonging to tenant B and be served. This is OWASP API1 Broken Object Level Authorization, and in a B2B contract it is not a bug, it is a breach.
**T:** Nobody assigned this to me. I found it, and I owned deciding how loudly to escalate it.
**A:** I wrote it up as a security finding with a concrete reproduction rather than a vague concern, because "I think our authz might be weak" gets deprioritised and "here is a request that returns another tenant's data" does not. I escalated immediately rather than quietly patching, since a silent fix leaves nobody able to assess exposure `[CONFIRM: who you escalated to, and whether a formal incident/security review was opened]`. Then I fixed it at the right layer: enforcement on the object-fetch path keyed on the authenticated tenant, so authorization is not something each endpoint has to remember. In the same pass I replaced string-interpolated SQL with parameterized queries across the platform, which closes injection and, as a side effect, improves plan reuse.
**R:** Cross-tenant bypass closed and the injection surface removed across the skills intelligence platform. `[CONFIRM: number of endpoints/queries changed, and whether any actual cross-tenant access occurred in logs]`
**Rejected:** Patching only the endpoints I had found. Faster, and it would have passed review, but the class of bug is "authorization decided per-endpoint," and fixing instances of a class leaves the class. I also rejected a middleware-only fix, because middleware can see the route and the token but generally cannot see which object IDs the handler is about to load.
**Differently:** I would have added a negative test to the regression suite that asserts a tenant-A token receives 403/404 for a tenant-B object, on every resource type. The fix without that test is one refactor away from regressing.
**Differently (second-order):** I would have asked why the class existed, which is that tenant scoping was a convention rather than a type. Making tenant identity a required parameter that cannot be defaulted is the design fix.
**Tags:** security ownership, uncomfortable escalation, fixing classes not instances, multi-tenant isolation | **Amazon LP:** Earn Trust, Insist on the Highest Standards, Ownership, Have Backbone | **Google:** Googleyness (does the right thing unasked), Leadership | **Meta:** ownership, integrity | **Microsoft:** security-first, accountability
**Note:** this is your strongest "highest standards" and "earn trust" story, and it doubles as "tell me about a time you disagreed" if the escalation met resistance. Be careful with confidentiality: describe the class of bug and your process, not exploitable specifics.

#### S07 — Parameterized queries, and the fact that you published on SQL injection
**Source bullet:** ... replaced string-interpolated SQL with parameterized queries ... plus: Published Researcher, "SQL Injection Detection", Springer International Journal.
**S:** The codebase built SQL by string interpolation in multiple places. I had previously published peer-reviewed work on SQL injection detection, so I knew both the detection side and how ordinary the failure is.
**T:** I owned removing the injection surface rather than adding a scanner on top of it.
**A:** I converted interpolated SQL to parameterized queries rather than adding input sanitisation, because sanitisation is a denylist problem and parameterization is a structural one: the driver sends the statement and the values separately, so there is no string for an attacker to escape out of. Where dynamic SQL was genuinely needed, such as dynamic column or table identifiers, which cannot be parameterized, I used a strict allowlist rather than interpolating user input. I then went looking for the same pattern everywhere rather than only where the scanner flagged it.
**R:** Injection surface removed across the skills intelligence platform. `[CONFIRM: count of call sites changed; whether a SAST tool now gates this in CI]`
**Rejected:** A WAF rule plus input sanitisation, which is what gets proposed when the deadline is close. It reduces exploitability without removing the defect and it produces false confidence.
**Differently:** I would have added a lint rule or SAST gate in CI in the same pull request. A one-time cleanup without a gate re-accumulates within two quarters.
**Tags:** structural vs superficial fixes, research-to-practice, prevention over detection | **Amazon LP:** Insist on the Highest Standards, Learn and Be Curious, Dive Deep | **Google:** RRK, Googleyness | **Meta:** quality | **Microsoft:** security-first

#### S08 — Building the regression golden baseline nobody asked for
**Source bullet:** Established 2,000+ row regression golden baseline and 200+ unit/integration tests, improving release confidence for the skill intelligence service.
**S:** The skill resolution service had a behaviour that is hard to test conventionally: its output is a ranking produced by embeddings and a reranker, so a "correct answer" is fuzzy and any model, threshold, or prompt change can silently shift thousands of resolutions. Releases were being gated on manual spot-checks.
**T:** I decided this was the blocker on release velocity and took it on alongside feature work.
**A:** I built a golden baseline of 2,000+ rows covering the locale and tier matrix, then wrote assertions on aggregate behaviour rather than exact string equality, because a semantic system that must return byte-identical output cannot be improved. I paired that with 200+ unit and integration tests covering the deterministic parts (locale precedence, tenant scoping, pagination) where exact assertions *are* correct. The key design decision was separating "this must never change" from "this may drift within tolerance."
**R:** 2,000+ row golden baseline and 200+ tests, and release confidence improved to the point that model and threshold changes could ship without manual review. `[CONFIRM: prior release cadence vs after; any escaped-defect count before/after]`
**Rejected:** Higher line-coverage targets on unit tests, which is the usual answer and would have measured nothing about ranking quality. I also rejected a full RAGAS/DeepEval harness at that moment as too slow to gate every PR; the golden baseline runs in CI, the heavier eval runs nightly `[CONFIRM: whether you actually split it this way]`.
**Differently:** I would have version-controlled the baseline with an explicit approval workflow for intentional changes from the start, so "the diff is expected" is a reviewable act rather than a Slack message.
**Tags:** testing non-deterministic systems, investing in velocity, claimed not assigned | **Amazon LP:** Insist on the Highest Standards, Ownership, Deliver Results | **Google:** Leadership, RRK | **Meta:** quality bar, ownership | **Microsoft:** engineering excellence

#### S09 — Skillmaster ingestion: async load with status polling
**Source bullet:** Built Skillmaster ingestion pipeline (Parquet → PostgreSQL in-memory, async load with status polling and verification endpoints) integrated into the multi-tenant provisioning platform.
**S:** Provisioning a new tenant required loading a large Parquet skills dataset into PostgreSQL. Done synchronously in the request, this either times out at the gateway or holds a connection for minutes, and the provisioning platform is not tolerant of either.
**T:** I owned the ingestion contract and its integration into multi-tenant provisioning.
**A:** I made the load asynchronous with an explicit job resource: submit returns an identifier, the caller polls status, and a separate verification endpoint confirms the loaded data is actually correct rather than merely present. The verification endpoint was the decision I had to argue for; "the load returned success" and "the data is right" are different claims, and provisioning needs the second one. I read from Parquet rather than CSV because of columnar reads and typed schema, and staged in memory before the Postgres write to keep the transaction short.
**R:** Tenant provisioning does skills ingestion without blocking, with verifiable completion. `[CONFIRM: dataset size per tenant, load duration, and whether idempotent retry is supported]`
**Rejected:** Synchronous load with a raised gateway timeout, and fire-and-forget with no status. The first fails at the largest tenant, which is the tenant you least want to fail on. The second turns every provisioning question into a log-diving exercise.
**Differently:** I would have made the job idempotent by construction, keyed on tenant plus dataset version, so a retried submission is safe. `[CONFIRM: whether it already is]`
**Tags:** async API design, long-running job patterns, operability, verification vs completion | **Amazon LP:** Dive Deep, Deliver Results, Customer Obsession | **Google:** RRK | **Meta:** execution | **Microsoft:** design excellence

#### S10 — Designing and delivering an 8-service recommendation platform from the ground up
**Source bullet:** Designed and delivered 8-service AI recommendation microservices platform from the ground up (307 commits, 178K+ net lines of code): vector search, user context, user event processor, recommendation engine, collaboration agent, search service, user-profile data processor, and flow service, serving 2M+ users with ~25% engagement uplift.
**S:** The learning platform had no recommendation capability of its own. 2M+ users, multi-tenant, and no existing feature store, event pipeline, or serving path to build on. Greenfield with a business expectation attached.
**T:** I owned the platform architecture end to end and the delivery, not one service within it.
**A:** I drew the seam lines around independent scaling and independent failure rather than around data entities. Vector search and the recommendation engine are read-heavy and latency-bound; the user event processor is write-heavy and throughput-bound; the user-profile data processor is batch. Putting those in one process means you scale for the worst of the three and a bad batch job takes down serving. I built the event and context path before the model path, because a recommender with no user context is a popularity list, and I sequenced delivery so something shipped and was measurable before the full eight existed `[CONFIRM: which service shipped first and what the first measurable win was]`. I kept a shared vector search service rather than letting each consumer embed its own, so the recommendation engine and the search service resolve against one index.
**R:** Eight services in production serving 2M+ users, 307 commits and 178K+ net lines, ~25% engagement uplift `[CONFIRM: engagement metric definition, measurement method (holdout vs pre/post), and window]`.
**Rejected:** A single well-factored monolith, which for a team of `[CONFIRM: team size]` is a defensible and often correct choice, and I want to be explicit that eight services is a real cost: eight deploys, eight sets of dashboards, cross-service tracing, and network calls where a function call would do. I chose it because the scaling profiles genuinely diverge and because multi-tenant isolation is easier to reason about per-service. I also rejected buying a recommendations vendor, which would have been faster to first value but could not see our proprietary skills graph.
**Differently:** I would merge two of the eight. `[CONFIRM: which two, most likely user context and user event processor if they always deploy together]` If two services always change and deploy together, they are one service with extra latency. I would also have built the offline evaluation harness before the third service rather than after.
**Tags:** greenfield architecture, service decomposition, scope, sequencing for early value, stated cost of own decision | **Amazon LP:** Ownership, Think Big, Deliver Results, Invent and Simplify | **Google:** Leadership, RRK, GCA | **Meta:** direction-setting, scope, ownership | **Microsoft:** technical leadership, drive for results
**Note:** this is your headline story. It is also the one most likely to be attacked on "why eight services", so the rejected-alternative paragraph above is the load-bearing part. Never present the decomposition as obviously correct.

#### S11 — Defending (and criticising) the eight-service split
**Source bullet:** (same as S10, used for "tell me about a decision you would make differently" / "tell me about over-engineering")
**S:** Same platform. Six months in, the operational cost of eight services was visible: eight pipelines, cross-service failures, and debugging that requires distributed tracing to answer "why did this user get this recommendation."
**T:** I owned the honest reassessment of my own architecture.
**A:** I went back to the decomposition criterion I had used, independent scaling and independent failure, and tested each boundary against it rather than defending the whole. Services whose scaling profiles genuinely diverge stayed. The boundaries that existed because they felt tidy were the candidates to collapse. I made the criterion explicit so the conversation was about evidence rather than taste.
**R:** `[CONFIRM: whether any consolidation actually happened; if not, say "I documented the recommendation and the trigger conditions" and describe that]`
**Rejected:** Defending the original design because I made it. That is the failure mode this story exists to disprove.
**Differently:** Start with fewer services and split on evidence. The cost of splitting a monolith later is real but bounded; the cost of eight premature boundaries is paid every single deploy.
**Tags:** intellectual honesty, revisiting own decisions, cost awareness | **Amazon LP:** Are Right A Lot (seek to disconfirm), Invent and Simplify, Earn Trust | **Google:** Googleyness (intellectual humility) | **Meta:** growth mindset | **Microsoft:** growth mindset
**Note:** Google's "Googleyness" explicitly scores intellectual humility ([Prepfully Googleyness guide](https://prepfully.com/interview-guides/googles-googleyness-interview) — accessed 2026-07-26). This is the story for it. Have it ready and do not fake humility with a trivial regret.

#### S12 — The ~25% engagement uplift, and how it was measured
**Source bullet:** ... serving 2M+ users with ~25% engagement uplift.
**S:** The platform's justification rested on an engagement number. A number without a measurement method is an opinion.
**T:** I owned being able to defend the figure.
**A:** `[CONFIRM: this whole section must be your real method. Which metric (sessions? content starts? completions?), which comparison (holdout group / staged rollout / pre-post), which window, which tenants, and who validated it.]` The senior framing regardless of method: I state the metric definition first, the comparison design second, the confounders I could not remove third.
**R:** ~25% engagement uplift on `[CONFIRM: metric]` measured by `[CONFIRM: method]` over `[CONFIRM: window]`.
**Rejected:** Reporting the raw pre/post delta with no control if in fact there was a control available; and conversely, if there was no control, claiming there was.
**Differently:** `[CONFIRM]` If it was pre/post, say plainly that a holdout would have been better and name why it was not available (tenant contracts, rollout mechanics, no experimentation platform). Interviewers respect that answer.
**Tags:** metric integrity, experimentation literacy, business impact | **Amazon LP:** Deliver Results, Dive Deep, Are Right A Lot | **Google:** GCA, RRK | **Meta:** impact, data judgment | **Microsoft:** results
**Warning:** this is the single most likely place for a Bar Raiser to break your story. Prepare it before anything else in this module.

#### S13 — Java Spring Batch to Python: deleting 3,447 lines
**Source bullet:** Migrated Java Spring Batch → Python for the user profile data processor: removed 3,447 lines of Java, delivered 812-line containerized Python service with MongoDB integration, multi-tenant isolation, and CSV-based historical data migration.
**S:** The user profile data processor was the only JVM service in an otherwise Python fleet: separate build tooling, separate dependency management, separate on-call knowledge, and a Spring Batch job configuration that few people on the team could safely change.
**T:** I owned proposing and executing the migration, including the data migration.
**A:** I read the 3,447 lines and found that most of it was Spring Batch scaffolding (readers, writers, processors, job and step configuration) rather than business logic; the actual transformation rules were a fraction of it. That is why 812 lines of Python is a faithful replacement and not a simplification of behaviour, and it is the number to lead with when someone assumes I dropped features. I containerised it, integrated MongoDB directly, and enforced multi-tenant isolation in the new service rather than inheriting the old implicit scoping. For historical data I did a CSV-based migration so the cutover had a reproducible, inspectable artifact rather than a live dual-write.
**R:** 3,447 lines of Java removed, 812-line containerized Python service in production, one runtime for the fleet. `[CONFIRM: correctness validation method for the cutover (row-count/checksum parity?), and any change in job runtime or cost]`
**Rejected:** Leaving it in Java, which was the zero-risk choice and my manager would have accepted `[CONFIRM]`. I rejected it because polyglot cost is paid continuously and quietly. I also rejected a live dual-write cutover, which is lower-downtime and higher-risk; with a batch job the CSV path was verifiable and downtime was acceptable.
**Differently:** I would have run the old and new job in parallel over the same input and diffed outputs for a full cycle before cutover, rather than validating on samples. `[CONFIRM: whether you did]`
**Tags:** legacy migration, code deletion as a result, polyglot cost, safe cutover | **Amazon LP:** Invent and Simplify, Ownership, Bias for Action, Frugality | **Google:** Leadership, RRK | **Meta:** simplification, ownership | **Microsoft:** engineering excellence
**Note:** "I made the system smaller" is a rarer and stronger claim than "I built a new thing." Use this for Invent and Simplify.

#### S14 — Contextual multi-armed bandits instead of a supervised ranker
**Source bullet:** Implemented CMAB (Contextual Multi-Armed Bandit) Reinforcement Learning with PySpark for real-time recommendation scoring, dynamically optimizing people and skill-based content delivery.
**S:** Recommendation scoring needed to improve continuously, but a supervised ranker trained on logged interactions learns from a policy that only ever showed users what the previous model liked. In a catalogue with new content arriving constantly, that feedback loop starves anything unseen.
**T:** I owned the scoring approach.
**A:** I framed it as an exploration problem rather than a prediction problem and implemented a contextual bandit, so each recommendation is an arm choice conditioned on user context and the model updates from observed reward. I ran it on PySpark because the context features and reward attribution are batch-shaped even though serving is real time `[CONFIRM: which algorithm, LinUCB / Thompson sampling / epsilon-greedy, and the exploration parameter]`. I explicitly bounded the exploration rate, because unbounded exploration in an enterprise learning product means showing a paying tenant's employees irrelevant content, and the cost of that is a support ticket, not just a lower metric.
**R:** Real-time scoring that adapts without a full retrain cycle, contributing to the platform's engagement result. `[CONFIRM: uplift attributable to CMAB specifically vs the platform overall, and the cold-start improvement]`
**Rejected:** A gradient-boosted or neural ranker on logged clicks, which would likely have scored better on offline replay of historical data precisely because it optimises the logged policy, and which would have had no answer for new content. I also rejected non-contextual bandits, which cannot personalise at all.
**Differently:** I would have built off-policy evaluation (inverse propensity scoring on the logged propensities) into the pipeline from the start. Without it you cannot compare a candidate policy to the live one without shipping it.
**Tags:** ML judgment, exploration/exploitation, offline/online metric divergence, business-bounded experimentation | **Amazon LP:** Are Right A Lot, Think Big, Customer Obsession | **Google:** RRK depth, GCA | **Meta:** ML depth | **Microsoft:** technical depth

#### S15 — Self-hosting vLLM on SageMaker instead of calling an API
**Source bullet:** Self-hosted vLLM inference on AWS SageMaker (ml.4xlarge, g4.2xlarge, g5.xlarge) for Phi-4 and LLaMA-8B, enabling high-throughput cost-optimized on-prem LLM serving.
**S:** Multiple services needed LLM inference at volume against a 2M+ user platform. Per-token API pricing scales linearly with usage and, in an enterprise multi-tenant product, some tenants have data-handling expectations that a third-party API complicates.
**T:** I owned the serving decision and the deployment.
**A:** I chose to self-host open-weight models (Phi-4 and LLaMA-8B) on SageMaker with vLLM rather than calling a hosted API. vLLM specifically, because the workload was many concurrent short requests, and continuous batching plus PagedAttention is what turns GPU utilisation from single-digit into useful throughput; a naive server batches by request and leaves the GPU idle between them. I benchmarked across instance families rather than picking the biggest GPU `[CONFIRM: exact instance identifiers. The resume lists "ml.4xlarge" and "g4.2xlarge", which are not valid SageMaker instance names. The real ones are almost certainly ml.g4dn.2xlarge and ml.g5.xlarge. Fix this on the resume before an AWS-literate interviewer catches it.]` I accepted the tradeoff explicitly: self-hosting means I own the capacity, the cold starts, the model upgrades and the on-call.
**R:** High-throughput self-hosted serving for the platform's LLM workloads. `[CONFIRM: tokens/sec or requests/sec achieved, GPU utilisation, and cost per million tokens vs the API alternative. This number will be asked for.]`
**Rejected:** Bedrock or a commercial API for everything. Lower operational burden, better frontier-model quality, and the right choice for low or spiky volume. I kept Bedrock for the offline batch path (S17), which is the honest version of the answer: I did not choose "self-host everything," I split the workload by shape.
**Differently:** I would have modelled the break-even volume in dollars before building, and written it down. I optimised for throughput and control and can defend it, but a cost model would have made the decision reviewable by a finance-minded stakeholder rather than only by engineers.
**Tags:** build-vs-buy, cost engineering, inference internals, workload segmentation | **Amazon LP:** Frugality, Are Right A Lot, Ownership, Dive Deep | **Google:** RRK, GCA | **Meta:** technical judgment, impact | **Microsoft:** technical depth, business acumen

#### S16 — Instance selection: benchmarking rather than guessing
**Source bullet:** (same as S15, GPU instance families) for the "tell me about a data-driven decision" question.
**S:** GPU instances differ by an order of magnitude in cost and are not ordered by price on throughput-per-dollar for a given model size. Guessing here is expensive in a way that compounds monthly.
**T:** I owned the instance choice for Phi-4 and LLaMA-8B serving.
**A:** I benchmarked candidate families against the actual request distribution rather than a synthetic single-stream test, because with continuous batching the metric that matters is throughput at a target p99 under realistic concurrency, not single-request latency. `[CONFIRM: your measured numbers, the concurrency levels tested, and the p99 target]`
**R:** `[CONFIRM: chosen instance per model and the throughput-per-dollar delta versus the runner-up]`
**Rejected:** Sizing by GPU memory alone, which gets you a model that fits and a KV cache that does not, so you hit throughput collapse at concurrency instead of a clean OOM at load time.
**Differently:** I would have kept the benchmark as a repeatable script so a new instance family or a vLLM version bump could be re-evaluated in an hour instead of re-litigated from memory.
**Tags:** data-driven decisions, benchmarking methodology, cost per unit of work | **Amazon LP:** Frugality, Dive Deep, Are Right A Lot | **Google:** GCA | **Meta:** rigour | **Microsoft:** technical depth

#### S17 — Bedrock batch inference for the offline path
**Source bullet:** Engineered Amazon Bedrock batch inference pipeline processing JSONL payloads from S3, writing scored outputs back to S3 for large-scale offline content generation.
**S:** Large-scale offline content generation is throughput-bound and latency-indifferent: nothing is waiting on any individual response. Running it through the same real-time serving path as user requests would have contended with interactive traffic for GPU capacity.
**T:** I owned the offline inference path.
**A:** I separated it entirely: JSONL payloads in S3, Bedrock batch inference, scored outputs back to S3. This is the decision people miss, that "we self-host on vLLM" and "we use Bedrock batch" are not contradictory, they are the correct answer to two different workload shapes. Batch endpoints are cheaper per token and have no capacity coupling to the serving fleet, so a 1M-row generation job cannot degrade a user-facing recommendation.
**R:** Offline generation runs at scale without touching serving capacity. `[CONFIRM: volume per run, wall-clock, and cost per run vs the same work on the online path]`
**Rejected:** Reusing the real-time vLLM endpoint for batch, which needs no new code and is exactly how you cause a latency incident from a scheduled job. Also rejected: streaming batch work through a queue into the online endpoint at a throttled rate, which works but is strictly more machinery for a worse cost.
**Differently:** I would have added explicit output validation on the batch results before they are consumed downstream. Batch inference fails partially, and a job that is 99% complete is not the same thing as a complete job.
**Tags:** workload segmentation, cost/latency tradeoff, isolation of batch from serving | **Amazon LP:** Frugality, Invent and Simplify, Dive Deep | **Google:** RRK | **Meta:** technical judgment | **Microsoft:** design excellence

#### S18 — Real-time GenAI content creator for catalogue gaps
**Source bullet:** Built Real-Time GenAI Content Creator that auto-generates missing courses using LLM inference based on user search intent, closing critical content catalog gaps.
**S:** Users searched for topics the catalogue did not contain. The search returned nothing useful, the user left, and the only signal we kept was a failed query. In a learning platform, a repeated empty search is a churn precursor.
**T:** I owned building the response to that signal.
**A:** I turned failed search intent into a generation trigger: when demand exists and content does not, generate the content. The important design decision was not the LLM call, it was scoping *when* generation is allowed to fire, because auto-generating a course into an enterprise catalogue is a content-quality and liability question, not just an engineering one `[CONFIRM: the actual guardrails, e.g. human review before publish, tenant opt-in, demand threshold before triggering, provenance labelling]`. I treated demand as the gate, so generation is driven by observed user intent rather than by speculative coverage.
**R:** Catalogue gaps closed from real search demand rather than manual curation guesses. `[CONFIRM: number of generated items, review/acceptance rate, and any engagement number on generated vs curated content]`
**Rejected:** Surfacing "no results, request this topic" and routing to human curation. Honest, cheap, and slow: the user who searched is already gone by the time a course exists. I also rejected pre-generating content for a predicted long tail, which burns inference on demand that may never arrive.
**Differently:** I would have insisted on provenance labelling and an explicit review state from version one if it was not there. Generated content that is indistinguishable from curated content is a trust problem waiting to become an incident.
**Tags:** product thinking from a failure signal, GenAI risk management, demand-gated generation | **Amazon LP:** Customer Obsession, Think Big, Bias for Action, Success and Scale Bring Broad Responsibility | **Google:** Googleyness, Leadership | **Meta:** product impact | **Microsoft:** customer focus, responsible AI

#### S19 — JWT TTL cache with automatic secret rotation
**Source bullet:** Implemented JWT TTL cache with automatic secret rotation across the recommendation service fleet, eliminating credential-staleness security vulnerabilities.
**S:** Services across the recommendation fleet cached credentials with no coordinated rotation, so a rotated secret left stale credentials in caches until they happened to expire. That is both a security exposure window and an availability risk, because rotation could break callers.
**T:** I owned credential handling across the fleet, which meant a change in more than one team's service `[CONFIRM: how many services, and whether other people owned any of them]`.
**A:** I implemented a TTL cache tied to token lifetime rather than an arbitrary interval, with rotation handled automatically so no service holds a credential past its validity. Doing it as a shared mechanism across the fleet rather than per service was the point; a per-service fix leaves the weakest service defining your exposure window. The reason a cache exists at all is that minting or fetching a token per request is a latency and rate-limit problem, so this is a security fix that had to not regress performance.
**R:** Credential staleness eliminated across the recommendation service fleet. `[CONFIRM: services touched, and whether rotation is now automated end to end with no manual step]`
**Rejected:** No caching at all, which is maximally safe and adds a fetch to every request; and long-lived static secrets in configuration, which is what many fleets still do and is the actual thing being fixed.
**Differently:** I would have added an alert on token-fetch failure rate and on rotation events. Silent rotation is good; invisible rotation is not, because the first sign of a broken rotation should not be a 401 storm.
**Tags:** cross-service change, security/latency tradeoff, fleet-wide standardisation | **Amazon LP:** Ownership, Earn Trust, Insist on the Highest Standards | **Google:** Leadership (influence across services) | **Meta:** ownership beyond own service | **Microsoft:** security-first

#### S20 — Redis caching layer and the 100+ content-ID bottleneck
**Source bullet:** Engineered Redis distributed caching layer for external API calls, resolving 100+ content-ID performance bottlenecks and reducing recommendation latency under sustained load.
**S:** Serving a recommendation set meant hydrating details for 100+ content IDs from an external API. Under sustained load that dominated latency, and the external service also became the availability ceiling for our own.
**T:** I owned recommendation latency under load.
**A:** I put a distributed Redis cache in front of the external calls, keyed per content ID so hydration for a set of 100+ IDs becomes a multi-get against Redis with a small miss set going to the API, instead of 100+ external calls per request. Content metadata has a high read-to-write ratio, which is precisely the workload a cache is for. `[CONFIRM: hit rate achieved, TTL chosen, latency before/after, and whether you batch the miss set]` I chose distributed rather than in-process because with N replicas an in-process cache gives you N times the misses and N times the external load.
**R:** Recommendation latency reduced under sustained load and external API dependence cut. `[CONFIRM: p99 before and after, and the cache hit rate]`
**Rejected:** In-process caching, which is faster per hit and does not survive horizontal scaling or deploys. Also rejected: asking the external team for a bulk endpoint, which would have been the better structural fix and was not on their roadmap in my timeframe `[CONFIRM]`.
**Differently:** I would have paired the cache with a bounded stale-while-revalidate path, so an external outage degrades to slightly stale metadata rather than an error. A cache that only helps latency and not availability is doing half its job.
**Tags:** caching design, latency optimisation, dependency isolation, distributed vs local | **Amazon LP:** Deliver Results, Dive Deep, Customer Obsession | **Google:** RRK | **Meta:** execution, impact | **Microsoft:** performance engineering

#### S21 — MongoDB race conditions and async event loop closure errors
**Source bullet:** Fixed MongoDB race conditions and async event loop closure errors, hardening concurrent recommendation request handling under peak traffic.
**S:** Under peak traffic the recommendation service produced two distinct intermittent failures: data anomalies consistent with concurrent read-modify-write on MongoDB documents, and `Event loop is closed` / `RuntimeError: attached to a different loop` style errors from the async stack `[CONFIRM: exact error strings you saw]`. Both were load-dependent, which means they did not reproduce in staging.
**T:** I owned making concurrent request handling correct under peak load.
**A:** For the race, I stopped treating it as a retry problem. Read-modify-write across a network round trip is not atomic, so I moved the mutation into the database as an atomic update operator with a filter condition, so the concurrency control lives where the data lives rather than in application sequencing `[CONFIRM: whether you used `findOneAndUpdate` with atomic operators, an upsert with a unique index, or optimistic versioning]`. For the loop errors, the underlying cause in async Python is almost always a client or connection created on one event loop and used from another, or module-level clients that outlive the loop that made them; the fix is loop-scoped client lifecycle tied to application startup and shutdown, not sprinkling `try/except`. I reproduced both under synthetic concurrency before claiming a fix, because an intermittent bug that stops appearing is not the same as a fixed one.
**R:** Concurrent handling hardened under peak traffic. `[CONFIRM: error rate before/after, and how you verified under load]`
**Rejected:** Application-level locking around the read-modify-write, which serialises a hot path and moves the problem to lock contention; and broad exception handling on the loop errors, which converts a correctness bug into a silent one.
**Differently:** I would have added a concurrency test to CI that runs the hot path at parallelism above production peak. Both classes of bug are invisible at parallelism one, which is exactly the parallelism most test suites use.
**Tags:** concurrency correctness, async runtime internals, reproduce-before-fix, refusing symptom suppression | **Amazon LP:** Dive Deep, Insist on the Highest Standards, Ownership | **Google:** RRK, GCA | **Meta:** debugging depth | **Microsoft:** engineering excellence

#### S22 — PySpark + EMR customer intelligence pipeline
**Source bullet:** Built PySpark + AWS EMR customer intelligence pipeline: ClickHouse → S3 → MongoDB, with LLM-based chat-engagement analysis, freemium/premium skill extraction modes, async LLM rate limiting, and EMR egg-file deployment.
**S:** Customer intelligence required joining behavioural data in ClickHouse with LLM-derived analysis of chat engagement, then landing results where product services could read them. Three storage systems, a distributed compute layer, and a rate-limited external model in one pipeline.
**T:** I owned the pipeline end to end including its deployment mechanics.
**A:** I staged through S3 rather than moving ClickHouse to MongoDB directly, so the expensive extract is checkpointed and a downstream failure does not re-run it, and so the intermediate is inspectable when the output looks wrong. I implemented two extraction modes, freemium and premium, so the depth of analysis matches the commercial tier instead of burning premium-grade inference on every user. I handled EMR dependency deployment via egg files, which is unglamorous and is where these pipelines actually fail: the job runs locally, then the cluster has a different dependency set and you get an import error twenty minutes into a paid cluster run.
**R:** Production pipeline delivering customer intelligence from behavioural plus LLM-derived signals. `[CONFIRM: row volume, run duration, cluster size and cost per run]`
**Rejected:** A direct ClickHouse-to-MongoDB job with no staging, which is fewer moving parts and no checkpoint, so any failure re-runs everything; and running LLM analysis inline per record with no concurrency control, which is how you get throttled and fail the whole job.
**Differently:** I would have made the LLM analysis stage independently re-runnable from the S3 checkpoint with idempotent output keys, so a prompt or model change reprocesses without re-extracting.
**Tags:** distributed data pipelines, checkpointing, cost-tiered processing, deployment reality | **Amazon LP:** Deliver Results, Frugality, Dive Deep | **Google:** RRK | **Meta:** execution | **Microsoft:** drive for results

#### S23 — Async LLM rate limiting
**Source bullet:** ... async LLM rate limiting ... (from the EMR pipeline bullet)
**S:** The pipeline called an LLM for a large number of records from a distributed Spark job. Naive concurrency means every executor issues requests simultaneously, you exceed the provider's rate limit, and you get 429s across the whole job at once.
**T:** I owned making the external model call survive distributed concurrency.
**A:** I bounded concurrency explicitly rather than relying on retries, because retrying into a rate limit is amplification: the limit is a throughput constraint, so exceeding it and retrying produces more requests at exactly the wrong moment. I implemented async rate limiting so in-flight requests stay under the budget, with backoff for the 429s that still occur `[CONFIRM: the limiter mechanism and the concurrency ceiling, and whether the budget is per-executor or global. Per-executor is the common trap: 20 executors each staying under 10 concurrent is 200 concurrent.]`
**R:** LLM-dependent stages complete without throttling failures. `[CONFIRM: throttle-error rate and effective throughput]`
**Rejected:** Retry-only with exponential backoff, which works for transient errors and fails for a sustained rate ceiling; and reducing executor count to reduce concurrency, which throttles the whole job to fix one stage.
**Differently:** A global token budget coordinated outside the executors, since per-executor limits multiply by the executor count. That is a distributed rate limiter, so I would use a shared counter rather than build it from scratch.
**Tags:** rate limiting, distributed concurrency, retry amplification | **Amazon LP:** Dive Deep, Frugality, Deliver Results | **Google:** RRK, GCA | **Meta:** technical depth | **Microsoft:** technical depth

#### S24 — Query Crafter: natural language to federated SQL
**Source bullet:** Developed Query Crafter, a production NL-to-SQL system (RAG pipeline + GPT-4 + Trino) that translated natural-language business questions into federated analytical queries, reducing report turnaround by 50% for non-technical stakeholders.
**S:** Non-technical stakeholders needed analytical answers and had to queue behind data engineers to get them. Turnaround was measured in days, and the queue was the bottleneck, not the query complexity.
**T:** I owned building a system that let them ask directly.
**A:** I used RAG over schema and business metadata rather than putting the whole schema in the prompt, because an LLM cannot write correct SQL against a warehouse it cannot see and it also cannot see a warehouse that does not fit in context; retrieving the relevant tables, columns and prior queries makes the generation tractable. Trino as the execution layer, because the questions crossed sources and a federated engine answers them without building a new pipeline per question. The decisions that mattered for trust were showing the generated SQL to the user rather than only the answer, and bounding what the generated query is allowed to do `[CONFIRM: guardrails, e.g. read-only credentials, row/scan limits, query timeout, allowlisted schemas]`. An NL-to-SQL system that silently returns a wrong number is worse than no system, because the number gets into a deck.
**R:** 50% reduction in report turnaround for non-technical stakeholders. `[CONFIRM: baseline turnaround, how the 50% was measured, and adoption, i.e. how many users and queries]`
**Rejected:** Building a curated dashboard set, which is the standard answer and covers known questions while doing nothing for ad hoc ones; and fine-tuning a model on our SQL, which is more work than retrieval and goes stale every time the schema changes.
**Differently:** I would have tracked query correctness as a first-class metric, not just adoption. Adoption of a tool that is sometimes wrong is a risk, not a win.
**Tags:** RAG applied to structured data, stakeholder enablement, trust and guardrails, business impact | **Amazon LP:** Customer Obsession, Invent and Simplify, Deliver Results | **Google:** Leadership, RRK | **Meta:** impact beyond own team | **Microsoft:** customer focus

#### S25 — Weaviate plus knowledge graph for cold start
**Source bullet:** Built AI-Powered Search Engine using Weaviate vector database and Knowledge Graphs, applying collaborative filtering and content embeddings to solve the cold-start problem for new platform users.
**S:** New users have no interaction history, so collaborative filtering has nothing to collaborate on. Search and discovery for a brand-new user degraded to global popularity, which is the same experience for everyone.
**T:** I owned discovery quality for users with no history.
**A:** I combined content embeddings in Weaviate with a knowledge graph, so a new user's minimal signal (a role, a stated interest, one interaction) is enough to traverse to related content through relationships rather than through co-occurrence statistics we do not have. The hybrid was deliberate: collaborative filtering where interaction data exists, content and graph where it does not, with the blend shifting as history accumulates `[CONFIRM: how the blend was weighted and at what interaction count it shifted]`.
**R:** Cold-start discovery improved for new users. `[CONFIRM: metric, e.g. CTR or first-session engagement for new users, before and after]`
**Rejected:** Popularity-only fallback, which is trivial and gives every new user the same list; and asking new users to complete an onboarding interest survey, which produces good data from the minority who finish it and worse coverage overall.
**Differently:** I would have measured the graph's marginal contribution over content embeddings alone. Both were in the design and I cannot cleanly attribute the improvement between them, which means I cannot tell you whether the graph was worth its maintenance cost.
**Tags:** cold start, hybrid retrieval, knowledge graphs, attribution honesty | **Amazon LP:** Customer Obsession, Are Right A Lot, Invent and Simplify | **Google:** RRK, GCA | **Meta:** ML depth | **Microsoft:** technical depth

#### S26 — Support chatbot with Mistral, Elasticsearch and Jira routing
**Source bullet:** Deployed AI Customer Support Chatbot using Mistral models and Elasticsearch with automated Jira-based ticket routing, reducing support escalation and churn.
**S:** Support volume included a large share of repeat questions that were answerable from existing documentation, and misrouted tickets added latency to the ones that genuinely needed a human.
**T:** I owned the automation, including the part that decides when a human is needed.
**A:** I paired Mistral for generation with Elasticsearch for retrieval over the support corpus, and designed the escalation path as a first-class outcome rather than a failure: when the bot cannot answer confidently, it creates and routes a Jira ticket with the conversation attached, so the human starts with context instead of from scratch. That framing matters, because a support bot optimised purely for containment rate learns to stall users who need a person, which increases churn while improving the dashboard.
**R:** Reduced support escalation and churn. `[CONFIRM: containment/deflection rate, routing accuracy, and the churn measurement, which is the weakest link in this claim]`
**Rejected:** A rules-based FAQ bot, cheap and brittle across phrasing; and full automation with no escalation path, which is the failure mode above.
**Differently:** I would have tracked resolution quality on escalated tickets, not just deflection, so I could tell whether the bot was helping humans or hiding work from them.
**Tags:** human-in-the-loop design, metric gaming awareness, retrieval-grounded generation | **Amazon LP:** Customer Obsession, Bias for Action, Deliver Results | **Google:** Googleyness, RRK | **Meta:** product judgment | **Microsoft:** customer focus

#### S27 — Modernising ETL off legacy Jenkins onto BigQuery and Airflow
**Source bullet:** Optimized ETL pipelines in Google BigQuery and Apache Airflow, modernizing legacy Jenkins workflows and reducing query complexity for LMS data models serving millions of tenant records.
**S:** Data pipelines were orchestrated by Jenkins jobs, which gives you cron and shell but no dependency graph, no backfill semantics, no per-task retry and no lineage. Failures required reading console output, and a mid-pipeline failure meant re-running from the top.
**T:** I owned the migration and the query work.
**A:** I moved orchestration to Airflow, so dependencies became an explicit DAG and retries and backfills became properties of the scheduler rather than something a human does by hand. Separately I reduced query complexity on the LMS data models rather than only lifting the queries as-is, because moving a bad query to a better platform buys you a faster bad query. Millions of tenant records, so the shape of the model dominates cost in BigQuery, where you pay for bytes scanned.
**R:** Pipelines on Airflow with reduced query complexity over millions of tenant records. `[CONFIRM: runtime and BigQuery cost before/after, and failure rate change]`
**Rejected:** Keeping Jenkins and adding scripting around it, which requires no migration and reimplements a worse scheduler; and a full rewrite of the data models, which was the right long-term answer and larger than the mandate `[CONFIRM]`.
**Differently:** I would have migrated one high-pain DAG end to end first and used it as the reference pattern, rather than migrating breadth-first. `[CONFIRM: what you actually did]`
**Tags:** orchestration migration, legacy modernisation, cost-aware data modelling | **Amazon LP:** Invent and Simplify, Ownership, Frugality | **Google:** RRK | **Meta:** execution | **Microsoft:** engineering excellence

#### S28 — 4.5 hours to 30 minutes at Expedia
**Source bullet:** Reduced ETL workflow latency from 4.5 hours to 30 minutes (~89% reduction) by engineering scalable pipelines on AWS and Qubole, enabling faster marketing optimization cycles.
**S:** A marketing data workflow took 4.5 hours. That is not merely slow, it sets the cadence of the business process on top of it: a 4.5-hour pipeline means one optimisation cycle per working day, so the pipeline runtime was the constraint on how fast marketing could react.
**T:** I owned the runtime.
**A:** I profiled before optimising and rebuilt on AWS with Qubole for scalable Spark-based processing rather than tuning the existing job in place `[CONFIRM: what dominated the 4.5 hours, e.g. sequential stages, non-partitioned reads, a skewed join, single-node processing. This is the most important detail in the story and it is missing from the resume.]` The result was 30 minutes, an ~89% reduction. I sold it internally on cycle time rather than on runtime, because "the pipeline is 9x faster" is an engineering fact and "marketing can now optimise several times a day instead of once" is the reason anyone funded it.
**R:** 4.5 hours to 30 minutes, ~89% reduction, and multiple marketing optimisation cycles per day instead of one. `[CONFIRM: cost change, since faster is sometimes achieved by spending more on compute and you should know which]`
**Rejected:** Incremental tuning of the existing pipeline, which was lower risk and, given the shape of the bottleneck, capped at a fraction of the win. I also considered running it more frequently on partial data, which improves freshness without fixing the underlying runtime.
**Differently:** I would have instrumented per-stage timings from the start so the bottleneck was visible in a dashboard rather than found by investigation, and so a future regression is immediately attributable.
**Tags:** performance engineering, profiling before optimising, framing impact in business terms | **Amazon LP:** Deliver Results, Dive Deep, Customer Obsession, Think Big | **Google:** RRK, Leadership | **Meta:** impact | **Microsoft:** drive for results
**Note:** cleanest number on your resume, ~89% with a clear baseline. Ideal for "biggest impact" and "most quantifiable result." Fill in the bottleneck before using it, because the immediate follow-up is "what was actually slow?"

#### S29 — Market risk pipelines at Credit Suisse
**Source bullet:** Automated Market Risk data pipelines using Python and RPA, streamlining E2E data flow from trade origination through risk calculation engines and eliminating manual reconciliation. Transformed and applied complex business rules on transaction data, improving data quality for downstream regulatory risk reporting.
**S:** Market risk data flowed from trade origination through calculation engines to regulatory reporting, with manual reconciliation steps in between. Manual reconciliation in a regulated reporting chain is both a labour cost and an audit finding waiting to happen. I was in a Business Analyst role, so I had no engineering mandate.
**T:** I took on automating the flow, which meant doing engineering work from a non-engineering seat.
**A:** I automated with Python and RPA rather than waiting for a platform team, choosing RPA specifically where the upstream systems had no API and screen-driven interaction was the only integration surface available. I encoded the business rules explicitly rather than leaving them in analysts' heads, because in a regulatory chain the rule and its provenance both have to be reproducible. I eliminated the manual reconciliation step rather than making it faster, which is the difference between an efficiency gain and removing an error class.
**R:** End-to-end automated flow from trade origination to risk calculation with manual reconciliation removed. `[CONFIRM: hours saved per cycle, error rate before/after, and who else adopted it]`
**Rejected:** A formal platform request through the engineering roadmap, which was the sanctioned path and measured in quarters; and improving the reconciliation checklist, which optimises a step that should not exist.
**Differently:** RPA is a bridge, not a destination. It breaks when an upstream UI changes and it has weak observability. I would have documented the API-based replacement path and the trigger for building it, so my expedient solution did not become permanent architecture.
**Tags:** initiative outside role scope, regulated environment, pragmatism with a stated exit plan, influence without authority | **Amazon LP:** Ownership, Bias for Action, Earn Trust, Deliver Results | **Google:** Googleyness (bias to action), Leadership | **Meta:** ownership, ambiguity | **Microsoft:** drive for results, growth mindset

#### S30 — The career arc: finance degree to Principal AI Engineer, and two Springer papers
**Source bullet:** PGDM in Finance, IMT Ghaziabad 2019-2021; B.Tech CS, Amrita 2013-2017; Published Researcher: "SQL Injection Detection" and "Hardware Trojan Diagnosis", Springer International Journal. Career path: Data Engineer (2017) → Business Analyst (2021) → Data Engineer (2022) → Senior Data Engineer (2023) → Senior AI/ML Engineer (2024) → Principal AI Engineer (2026).
**S:** I have a non-linear path: CS undergrad with two published security papers, data engineering at Expedia, a finance postgrad and a Business Analyst role in investment banking, then back into engineering and up to Principal AI Engineer over four years.
**T:** The implicit question in every loop is why the detour and what it bought.
**A:** I use the same three-beat answer every time. The finance and BA period is why I frame engineering work in business terms by default; S28 is 89% faster as an engineering fact and "several optimisation cycles a day" as a business one, and that translation is a skill I learned outside engineering. The published research is why I default to mechanism over recipe; I have written peer-reviewed work on SQL injection detection, which is why S07 is parameterization rather than sanitisation. And the four-year climb from Senior Data Engineer to Principal AI Engineer happened during the LLM shift, which I treated as a reason to go deep on internals (vLLM, embeddings, agent protocols) rather than to learn an API surface.
**R:** Principal AI Engineer at a 2M+ user platform, plus two Springer publications. `[CONFIRM: whether you want to discuss the specific reason for the finance detour; have one honest sentence ready and do not over-explain]`
**Rejected:** Framing the detour apologetically, which invites the interviewer to treat it as a gap. It is not a gap, it is where the business-translation skill came from.
**Differently:** I would have kept publishing. Two papers and then none reads as an interest I dropped rather than a practice I have.
**Tags:** narrative coherence, learning trajectory, non-linear path framed as an asset | **Amazon LP:** Learn and Be Curious, Ownership, Think Big | **Google:** Googleyness, GCA | **Meta:** growth | **Microsoft:** growth mindset, learn-it-all

---

## Practical exercise (replaces "Build it from scratch")

This module is a playbook, not an implementation, so the from-scratch section is a rehearsal protocol. Do it in this order; it is roughly 3 hours.

**Block 1 (40 min) — Close the CONFIRM list.** There are about 45 `[CONFIRM: ...]` markers above. Sort them by how likely they are to be asked: S12 (the 25% measurement) first, then S10 (team size, first shipped service), S15 (instance names and cost), S28 (what was actually slow), S04 (peak RSS), S20 (cache hit rate). Anything you genuinely cannot recover, plan to answer with "we did not instrument that" rather than a guess. Write the real values into this file.

**Block 2 (30 min) — Fix the resume bug.** `ml.4xlarge` and `g4.2xlarge` are not valid SageMaker instance types. Correct them to the real identifiers. An interviewer who runs SageMaker will spot this in ten seconds and it costs you credibility on your strongest technical story.

**Block 3 (50 min) — Record the top 8 at both lengths.** Use the scripts below. Record audio on your phone. Time yourself. Targets: 60-second version between 55 and 75 seconds, 3-minute version between 2:40 and 3:20. Listen back for three specific defects: "we" where it should be "I", Situation running past 20 seconds, and trailing off without a number.

**Block 4 (40 min) — Adversarial pass.** For each of the top 8, write the three hardest follow-ups an interviewer could ask and answer them in one sentence each. The three that are always available: "what would you have done with half the time", "what did that cost", and "who disagreed with you". If a story has no answer to the third, it may not be a staff-level story.

**Block 5 (20 min) — Coverage audit.** Fill in the matrix at the end of this module for real. Any column with no `##` is a hole; find or build a story for it before your first loop.

---

## The top 8 stories at 60 seconds and 3 minutes

The 60-second version is what you open with. The 3-minute version is what you give when they say "tell me more" or when the question is clearly the centrepiece of the round. Never give the 3-minute version unprompted; a monologue with no checkpoint is a junior signal.

Structural rule for the 60-second version: one sentence of situation, one of task, three of action, one of result, one of the rejected alternative. Nine sentences. Then stop and let them steer.

---

### T1 · S10 — The 8-service recommendation platform
**Use for:** biggest impact, largest scope, greenfield design, "tell me about a project you're proud of."

**60 seconds.**
"Our learning platform served 2M+ users and had no recommendation capability of its own, no event pipeline, no user context, no serving path. I owned the architecture and delivery end to end, not one service in it. I drew service boundaries around independent scaling and failure rather than around data entities, so the latency-bound serving path, the throughput-bound event ingestion, and the batch profile processing could scale and fail separately. I built the event and context path before the model path, because a recommender without user context is just a popularity list. And I kept one shared vector search service so search and recommendations resolved against the same index instead of drifting. It ended up as eight services, 307 commits, about 178,000 net lines, and roughly a 25% engagement uplift. The alternative I turned down was a single well-factored monolith, which for a team our size is a legitimate choice, and I want to be clear that eight services is a real cost: eight deploys and eight sets of dashboards. I took it because those three scaling profiles genuinely diverge."

**3 minutes.** Add, in this order:
1. **The sequencing decision (30s).** Which service shipped first and what it made measurable. Why you did not build all eight before shipping any: an unmeasurable platform cannot be steered, and the event path was the prerequisite for measuring anything at all.
2. **The measurement (30s).** The metric definition behind ~25%, the comparison design, and the confounder you could not remove. Say the method out loud before anyone asks; volunteering it is the senior move.
3. **The boundary you got wrong (30s).** Name the two services you would merge and the rule that tells you: if two services always change and deploy together, they are one service plus a network hop. Note that you found this out from deploy coupling, not from a diagram.
4. **The hardest sub-problem (30s).** Pick one and go a level deep: multi-tenant isolation in the vector index, or cold-start for new tenants, or the Redis hydration layer from S20. Whichever, close on mechanism.
5. **Checkpoint (5s).** "I can go deeper on the serving path or on how we handled multi-tenancy, whichever is more useful."

---

### T2 · S01 — A2A + FastMCP replacing the legacy RAG pipeline
**Use for:** technical direction, Think Big, current-technology depth, "tell me about your most recent architecture."

**60 seconds.**
"Our content intelligence ran on single-shot RAG: retrieve, stuff a prompt, answer. It could tell you what a course covered but it could not read a transcript, chunk it with context, and then reason about what the catalogue was missing. I owned the architecture for the replacement. I split it into separate agents for transcript processing, contextual chunking and gap detection, connected over A2A instead of building one large agent with many tools, because those three have independent failure modes and I wanted them independently retryable and deployable. I exposed the shared capabilities as MCP servers with FastMCP, so tool surfaces became versioned contracts and a second consumer could reuse skill resolution without importing my code. And I deliberately kept retrieval in the loop as a tool rather than throwing RAG away. It runs for 2M+ enterprise users. What I turned down was a single ReAct agent with all the tools attached, which I could have shipped weeks earlier but which gives you an N-way blast radius, where a chunking change degrades gap detection and you cannot roll one back without the others."

**3 minutes.** Add:
1. **Why multi-agent is usually wrong (35s).** Most multi-agent systems are one agent with extra latency and an ambiguous failure mode. State your test: separate agents only when the failure modes, the scaling profiles, or the deploy cadences genuinely differ. Then show yours passes it. This inoculates you against the standard attack.
2. **What A2A and MCP actually buy (35s).** MCP is a tool-surface contract, which means versioning and reuse across consumers. A2A is inter-agent messaging, which means an agent boundary is a network boundary with its own retry and timeout. Be precise; these are new enough that vagueness is obvious.
3. **The honest gap (30s).** You had a strong prior that multi-agent was right and could not prove it numerically at decision time. You should have built the offline eval set first. This is the intellectual-humility beat and it is genuinely true.
4. **Failure handling (30s).** What happens when the chunking agent fails mid-transcript: partial state, retry semantics, whether the run resumes or restarts. `[CONFIRM: your actual answer. If it restarts, say so and name checkpointing as the fix.]`
5. **Checkpoint.**

---

### T3 · S04 — The OOM on 1.2M multilingual rows
**Use for:** hardest bug, Dive Deep, technical depth, "tell me about a time you debugged something difficult."

**60 seconds.**
"The embedding job for our skills corpus died partway through a full rebuild of 1.2 million multilingual rows, and it died with no Python traceback, just killed by the OS, which tells you it is the kernel OOM killer and not an application exception. The obvious fix was to raise the memory limit, and I said out loud that I would not do that, because it only moves the failure to a bigger corpus. I found the job was materialising the entire ClickHouse result set into Python objects before embedding anything, so peak memory scaled with corpus size rather than batch size. I converted it to paginated loading so the working set became a function of page size. Memory still ratcheted up across pages, because in CPython dropping a reference does not necessarily return arena memory to the OS and the cycle collector runs on its own schedule, so I added explicit garbage collection at page boundaries, between pages rather than inside the hot loop so the pause is amortised. Then I verified with a memory profile across a full run instead of declaring victory after one page. Stable full-corpus processing after that."

**3 minutes.** Add:
1. **How you localised it (40s).** The sequence: symptom says OOM killer, so look at RSS over time, not at the traceback. Then the question is whether growth is proportional to input or unbounded over time, because the first is a batching bug and the second is a leak. Walk that fork explicitly. This is the part that shows method rather than luck.
2. **Why gc.collect() is a smell (30s).** You are compensating for allocator behaviour with a manual call. Say so. The structural fix is generators and bounded batches so no object graph that large ever exists.
3. **Placement matters (20s).** Collecting inside the hot loop would have destroyed throughput. At page boundaries, the pause amortises over thousands of rows. Small detail, strong signal.
4. **Prevention (25s).** A memory-ceiling assertion in CI so the regression fails in a pipeline instead of at 3am.
5. **What you would do at 50M rows (25s).** Distributed embedding on PySpark. Also name why that is wrong at 1.2M: the coordination overhead exceeds the work.

---

### T4 · S06 — The cross-tenant authorization bypass
**Use for:** highest standards, earn trust, doing the right thing, conflict, "tell me about a time you found a serious problem."

**60 seconds.**
"On a multi-tenant enterprise platform I found that object-level authorization was not enforced consistently, so a request holding a valid token for one tenant could reference an object ID belonging to another and be served. That is OWASP broken object-level authorization, and in a B2B contract it is not a bug, it is a breach. Nobody assigned this to me; I found it and I had to decide how loudly to escalate. I wrote it up as a finding with a concrete reproduction, because 'I think our authz might be weak' gets deprioritised and 'here is a request that returns another tenant's data' does not. I escalated immediately rather than quietly patching, because a silent fix leaves nobody able to assess exposure. Then I fixed it at the object-fetch layer keyed on the authenticated tenant, rather than patching the endpoints I happened to have found, because the class of bug is 'authorization decided per endpoint' and fixing instances leaves the class. In the same pass I replaced string-interpolated SQL with parameterized queries. What I would add now is a negative test asserting a tenant-A token gets a 403 on a tenant-B object for every resource type, because without that the fix is one refactor from regressing."

**3 minutes.** Add:
1. **The escalation (40s).** Who, how, what resistance. If there was pushback about timing or severity, this becomes your conflict story too: you can hold a position on a security finding and still be respectful about the schedule consequences. `[CONFIRM: what actually happened.]`
2. **Why middleware is not enough (30s).** Middleware sees the route and the token; it usually cannot see which object IDs the handler is about to load. Authorization has to happen where the object is fetched. This is a genuinely sharp technical point.
3. **The design fix behind the code fix (30s).** The class existed because tenant scoping was a convention rather than a type. Make tenant identity a required, non-defaultable parameter and the class becomes unrepresentable.
4. **Blast-radius assessment (20s).** How you determined whether real cross-tenant access had occurred. `[CONFIRM]`
5. **Confidentiality note.** Describe the class and your process, not an exploit. If asked for specifics, say you will describe the pattern rather than the payload. That restraint is itself a signal.

---

### T5 · S13 — Deleting 3,447 lines of Java
**Use for:** Invent and Simplify, migration, reducing complexity, "tell me about a time you simplified something."

**60 seconds.**
"Our user profile data processor was the only JVM service in an otherwise Python fleet: separate build tooling, separate dependency management, separate on-call knowledge, and a Spring Batch configuration few people could safely change. I proposed and ran the migration; it was not assigned. I read all 3,447 lines and found that most of it was Spring Batch scaffolding, readers, writers, processors, job and step config, rather than business logic. The actual transformation rules were a small fraction, which is why the replacement is 812 lines of Python and still a faithful port, not a feature cut, and that is the number I lead with when someone assumes I dropped functionality. I containerised it, integrated MongoDB directly, and enforced multi-tenant isolation explicitly rather than inheriting the old implicit scoping. For historical data I did a CSV-based migration so the cutover produced a reproducible, inspectable artifact instead of a live dual-write. Net: 3,447 lines of Java gone, 812 lines of Python in, one runtime for the whole fleet. The alternative was to leave it alone, which was zero risk, and I rejected it because polyglot cost is paid continuously and quietly."

**3 minutes.** Add:
1. **How you sold it (35s).** A migration with no new feature is hard to fund. The argument is not "Python is better", it is the concrete carrying cost: a second build pipeline, a second dependency-upgrade treadmill, a second on-call runbook, and a bus factor of `[CONFIRM]` on Spring Batch.
2. **Correctness of the cutover (40s).** How you proved the new job produced the same output. Row counts and checksums, sampled diffs, or a parallel run. If you only sampled, say so and name the parallel-run-and-diff approach as what you would do now.
3. **Why CSV not dual-write (25s).** Dual-write minimises downtime and maximises risk. For a batch job, downtime was acceptable, so the verifiable path wins. Choosing the boring option for a stated reason is a senior signal.
4. **Rollback (20s).** What the abort path was if the new job was wrong on day one. `[CONFIRM]`
5. **The generalisation (20s).** Deleting code is a result. Most engineers only count code added.

---

### T6 · S28 — 4.5 hours to 30 minutes
**Use for:** quantified impact, Deliver Results, performance work, "what's the biggest improvement you've made."

**60 seconds.**
"A marketing data workflow at Expedia took 4.5 hours, and the real problem was not that it was slow, it was that the runtime set the cadence of the business process on top of it: 4.5 hours means one optimisation cycle per working day. I owned the runtime. I profiled before touching anything, and the bottleneck was `[CONFIRM: the actual bottleneck]`. Rather than tuning the existing job in place, I rebuilt the pipeline on AWS with Qubole for scalable distributed processing, because the shape of the bottleneck capped what in-place tuning could achieve. It went from 4.5 hours to 30 minutes, about an 89% reduction. The thing I would call out is how I sold it: internally I pitched cycle time, not runtime, because '9x faster pipeline' is an engineering fact and 'marketing can now optimise several times a day instead of once' is why it got funded. The alternative was incremental tuning, which was lower risk and, given where the time was actually going, capped well below what we got."

**3 minutes.** Add:
1. **The profile (45s).** Where the 4.5 hours went, stage by stage. This is currently the weakest part of the story and it is the first follow-up you will get. Reconstruct it honestly before your loop.
2. **The cost side (30s).** Did 9x faster also mean more expensive? Distributed compute usually trades money for wall-clock. Knowing your own answer here separates engineers from optimisers.
3. **What you did not do (25s).** Running more frequently on partial data would have improved freshness without fixing runtime. Naming a cheaper alternative you considered and declined shows you were choosing, not just building.
4. **Instrumentation gap (20s).** No per-stage timings existed, so finding the bottleneck was investigation rather than a dashboard lookup. You would add stage timings first now.
5. **Durability (20s).** Whether it stayed at 30 minutes. Optimisations decay; if you do not know, say you do not know and that a regression alarm on runtime was the missing piece.

---

### T7 · S15 — Self-hosting vLLM instead of paying per token
**Use for:** Frugality, build-vs-buy, cost engineering, LLM infrastructure depth.

**60 seconds.**
"Multiple services on a 2M+ user platform needed LLM inference at volume, and per-token API pricing scales linearly with usage while some enterprise tenants have data-handling expectations that a third-party API complicates. I owned the serving decision. I self-hosted open-weight models, Phi-4 and LLaMA-8B, on SageMaker with vLLM. vLLM specifically because the workload was many concurrent short requests, and continuous batching with PagedAttention is what takes GPU utilisation from single digits to something worth paying for; a naive server batches per request and leaves the GPU idle in between. I benchmarked across GPU instance families rather than picking the largest GPU, because throughput per dollar is not ordered by price. And I want to be explicit about what I took on: self-hosting means I own capacity planning, cold starts, model upgrades and the on-call. The honest version of the tradeoff is that I did not choose 'self-host everything', I split by workload shape and kept Bedrock batch inference for the offline generation path."

**3 minutes.** Add:
1. **The break-even (40s).** Where self-hosting starts winning, in tokens per month, and where it does not. If you did not model it in dollars, say so and say that is the gap; the cost model is what makes the decision reviewable outside engineering. `[CONFIRM]`
2. **Mechanism depth (40s).** Why PagedAttention matters: KV cache fragmentation is the binding constraint on concurrency, and paging the cache in blocks is what lets you hold many sequences at once. Then the practical consequence: you size for KV cache, not for weights, and sizing by weights alone gives you throughput collapse under concurrency rather than a clean OOM.
3. **When you would not do this (30s).** Low or spiky volume, a small team with no ML-infra on-call, or a quality requirement that only a frontier model meets. Say plainly that self-hosting is usually the wrong call below a volume threshold.
4. **Operational reality (25s).** Cold starts, capacity headroom, and how you handled a model upgrade without downtime. `[CONFIRM]`
5. **Checkpoint.**

---

### T8 · S21 — MongoDB races and closed event loops under peak load
**Use for:** concurrency depth, production incident, "tell me about a bug that only happened in production."

**60 seconds.**
"Under peak traffic our recommendation service produced two intermittent failures: data anomalies consistent with concurrent read-modify-write on MongoDB documents, and async event-loop errors about the loop being closed or a client being attached to a different loop. Both were load-dependent, so neither reproduced in staging, which is the interesting part. For the race, I stopped treating it as a retry problem: read-modify-write across a network round trip is not atomic, so I moved the mutation into the database as an atomic update with a filter condition, putting concurrency control where the data lives instead of in application sequencing. For the loop errors, the cause in async Python is almost always a client created on one event loop and used from another, or a module-level client outliving the loop that made it, so the fix is loop-scoped client lifecycle tied to app startup and shutdown, not sprinkling try/except. I reproduced both under synthetic concurrency before claiming a fix, because an intermittent bug that stops appearing is not the same as a fixed one. What I would add is a CI test that runs the hot path above production peak parallelism, because both classes are invisible at parallelism one, which is what most test suites use."

**3 minutes.** Add:
1. **Why locking was wrong (35s).** An application-level lock around the read-modify-write serialises a hot path and converts a correctness bug into a contention bug. Atomic operators keep concurrency and correctness.
2. **The specific mechanism (40s).** Which MongoDB construct and why: `findOneAndUpdate` with atomic operators, a unique index for the upsert race, or optimistic versioning with a version field in the filter. Name the one you used and what it guarantees. `[CONFIRM]`
3. **Async lifecycle in detail (30s).** Where the client should be created (application startup, not import time), why module-level clients break under multi-worker servers, and what shutdown must do. This is a very common production bug and being crisp about it reads as real experience.
4. **How you reproduced it (25s).** Synthetic concurrency at what level, and how you knew you had reproduced the same failure rather than a different one.
5. **The general lesson (20s).** Staging that runs at parallelism one cannot find load-dependent correctness bugs. Concurrency has to be a test dimension, not an environment property.

---

## How it's done in production

**The loop-level mechanics you are actually being scored inside.**

| Company | Behavioural mechanism | What that means for your prep |
|---|---|---|
| Amazon | 4-5 back-to-back interviews, each interviewer assigned 2-3 LPs, plus a Bar Raiser from outside the team with veto power | You will be asked ~12-15 LP questions. Every one gets follow-ups until something breaks. Prepare 2 stories per LP, not 1. |
| Google | Interviewers write up evidence; a hiring committee that never met you scores the packet | Optimise for *quotable specifics*. "54,486 skills across 22 locales" survives transcription; "large-scale multilingual system" does not. |
| Meta | 45-minute behavioural round scoring ownership, conflict, execution under ambiguity, learning from mistakes; E6+ adds a Leadership Assessment before the onsite | Have a real failure story with a real cost. Meta explicitly scores learning from mistakes. |
| Microsoft | Competencies distributed across rounds, ending in the "As Appropriate" round tailored to your earlier gaps | Assume your weakest earlier answer gets re-examined. Note where you were thin and prepare the second-pass version. |
| Netflix | Conversational, often no whiteboard; culture-memo alignment and the keeper test | Prepare to describe systems verbally with no diagram. Practise T1 and T2 with your hands behind your back. |

**Story hygiene across a loop.** Interviewers share written notes. Three consequences: do not tell the same story twice unless you explicitly reframe it for the new competency ("I mentioned the platform earlier, so let me take the security angle instead"); do not contradict a number between rounds, which means memorising your figures rather than estimating them fresh each time; and expect the last interviewer to have read the earlier feedback, especially at Microsoft, where that is the explicit design of the AA round.

### Failure-mode table

| Symptom (what the interviewer writes down) | Cause | Fix |
|---|---|---|
| "Could not determine candidate's personal contribution" | "We" throughout the Action section | First person singular in every Action sentence. Say "I decided", "I benchmarked", "I rejected". |
| "No evidence of impact" | Story ends at "we shipped it" | Every story ends on a number or an explicit "we did not measure that, and here is why that was a gap". |
| "Insufficient scope for the level" | All stories are inside one service and one team | At least 4 stories must involve another team, another service, or a decision you were not asked to make. S06, S19, S24, S29. |
| "Shallow when probed" | Result memorised, mechanism not | For each story, be able to go two levels below the summary. If you cannot explain *why* the fix worked, drop the story. |
| "Rehearsed / evasive under follow-up" | Script with no adversarial prep | Block 4 of the exercise. Three hardest follow-ups per story, answered in one sentence. |
| Interviewer interrupts to redirect | Situation ran past 30 seconds | Two sentences of Situation. Hard stop. Interruption is data: it means you are on the wrong part. |
| "Numbers did not hold up" | Metric with no measurement method | S12. Do this one before anything else. |
| Same story appears in three write-ups | No coverage matrix | The matrix below. No story is the lead for more than 3 competencies. |
| "No genuine failure story" | Every "mistake" is a humblebrag | S11 and the "differently" line in S25. Pick a real one with a real cost. |

---

## Tradeoffs & when NOT to use it

**When rigid STAR is the wrong format.**

- **A deep dive is a conversation, not a recitation.** If the interviewer says "walk me through the recommendation platform", they want to interrupt. Give the 60-second version, then stop and let them steer. Delivering a memorised 3-minute block over an interruption reads worse than a weaker story delivered collaboratively.
- **Do not announce the structure.** "So, the Situation was..." is a tell. Deliver it as prose. The interviewer's rubric has the boxes; your job is to fill them without naming them.
- **Hypotheticals are not STAR.** "How would you handle a disagreement with a PM" wants your framework, not a story, though a story as evidence *after* the framework is strong. Answer the form of the question you were asked.
- **Small companies and startups often do not run structured behavioural rounds.** At an AI startup the equivalent round is usually "what have you built and why" plus a founder's judgment call about pace. Over-structured STAR can read as corporate there. Same content, looser delivery.
- **Never use a story you cannot be probed on.** A borrowed accomplishment or a project you only observed collapses at the second follow-up, and the collapse is worse than not having the story. If your role was reviewer rather than author, say "I reviewed and pushed back on X" and own that framing.
- **Confidentiality has limits.** Do not disclose exploitable security specifics (S06), customer identities, or unreleased roadmap. Describe classes and mechanisms. Interviewers respect the boundary; the ones who push on it are telling you something about the company.
- **Stop when your value drops.** If a story is not landing after 90 seconds, the interviewer's face will tell you. Close it with the result and offer a different one. Persisting is a self-awareness failure, which is separately scored.

---

## Interview questions

These are the questions your stories must answer. Each maps to specific stories above.

### Q1 — Tell me about the most complex system you have designed.
**Testing:** scope, whether you can compress a large system into a navigable summary, and whether "complex" means "large" or "hard" to you.
**Answer:** S10 at 60 seconds. Lead with the constraint (2M+ users, no existing event pipeline, multi-tenant), then the decomposition criterion (independent scaling and failure, not data entities), then the sequencing decision, then the numbers, then the alternative rejected. Stop at 60 seconds and offer a direction.
**Follow-up trap:** *"Why eight services and not one?"* Never defend it as obviously right. Name the real cost (eight deploys, eight dashboards, distributed tracing to answer one question), state your criterion, and volunteer the two boundaries you would collapse. Candidates who defend every boundary read as attached to their own design; the score is in the honest reassessment.

### Q2 — Tell me about a time you had to make a decision without enough data.
**Testing:** ambiguity, and whether you can act while stating your uncertainty.
**Answer:** S01. You had a strong prior that multi-agent was right for three genuinely independent failure modes, and no offline eval to prove it. You made the reversible parts reversible (MCP tool contracts mean a consumer can be re-pointed) and named the irreversible ones. Then the honest close: you should have built the eval set first.
**Follow-up trap:** *"How did you know you were right?"* You did not, and that is the correct answer. Follow it with what you did instead: identified which parts of the decision were cheap to reverse, and named the observation that would have told you it was wrong. Claiming certainty you did not have is the failure.

### Q3 — Tell me about the hardest bug you have debugged.
**Testing:** Dive Deep, method versus luck, whether you understand your runtime.
**Answer:** S04 (OOM) or S21 (races and event loops). Prefer S04 for mechanism depth, S21 for concurrency depth. Both have a symptom, a rejected easy fix, and a mechanism-level cause.
**Follow-up trap:** *"Why not just raise the memory limit?"* This is the whole question. Because peak memory scaled with corpus size, not batch size, so the limit is a function of data volume and the failure returns at the next growth step. Then the second trap: *"Isn't gc.collect() a hack?"* Yes, and say so. It compensates for allocator behaviour; the structural fix is streaming with bounded batches. Candidates who defend the workaround as elegant lose the point they had just won.

### Q4 — Tell me about a time you disagreed with your manager or a senior engineer.
**Testing:** backbone with respect, and whether disagreement was about substance or ego.
**Answer:** S06 if the escalation met resistance, S13 if the migration was questioned, S05 if the auto-detect suggestion came from a reviewer. Structure: what they proposed, why it was reasonable, the specific evidence you brought, the outcome, and what you did if you lost.
**Follow-up trap:** *"Tell me about a time you disagreed and were wrong."* You must have one. Without it, every disagreement story reads as "I was right and they came around." The Amazon framing is explicit: Have Backbone; Disagree and Commit is two clauses, and most candidates only evidence the first ([Exponent LP guide](https://www.tryexponent.com/blog/amazon-leadership-principles-interview) — accessed 2026-07-26).

### Q5 — Tell me about a time you failed.
**Testing:** whether you have calibrated self-assessment or a rehearsed humblebrag.
**Answer:** S11 (the over-decomposition, with the cost you paid every deploy) or the attribution gap in S25 (you cannot say whether the knowledge graph earned its maintenance cost, because you shipped it alongside content embeddings and never isolated it).
**Follow-up trap:** *"What did that cost?"* A failure with no cost is not a failure. Have the number or the concrete consequence: extra deploy overhead, a component you cannot justify, time spent. "It taught me a lot" without a cost is the answer that fails this question.

### Q6 — Tell me about a time you influenced a decision without authority.
**Testing:** staff-plus scope, whether your impact requires a title.
**Answer:** S29 (engineering automation from a Business Analyst seat at Credit Suisse) or S19 (a credential-handling change across a fleet you did not own alone) or S13 (a migration you proposed rather than received).
**Follow-up trap:** *"What if they had said no?"* Have the answer. For S29 it is: the manual reconciliation stays, the audit risk stays, and I would have documented the exposure so the decision was explicit rather than default. Escalation and documented-disagreement are legitimate answers; "I would have done it anyway" is not.

### Q7 — Walk me through a technical tradeoff you made that you would make differently now.
**Testing:** whether you revisit your own decisions, which is the specific thing Google labels intellectual humility under Googleyness.
**Answer:** S11, S03 (revisit ClickHouse HNSW at an order of magnitude more rows) or S04 (gc.collect as a symptom fix). Name the decision, the information you did not have, and the specific different choice.
**Follow-up trap:** *"So you were wrong?"* Distinguish "wrong given what I knew" from "wrong given what I know now." Most good decisions look wrong in hindsight and were correct at the time. Being able to hold that distinction is the senior signal; collapsing into either "I was wrong" or "I was right actually" loses it.

### Q8 — What is the most expensive mistake you have prevented?
**Testing:** proactivity, whether you find problems or receive them.
**Answer:** S06 (cross-tenant authorization bypass, unassigned, found by you) or S23 (bounding LLM concurrency before the rate limit took the whole job down).
**Follow-up trap:** *"How do you know it would have been expensive?"* For S06: the cost of a cross-tenant data exposure in a B2B contract is contractual and reputational, not just an engineering fix, and enterprise customers audit this. Do not invent a dollar figure. Naming the *category* of cost precisely beats a fabricated number, and a Bar Raiser will pull on a fabricated number.

### Q9 — Tell me about a time you had to deliver with an aggressive deadline. What did you cut?
**Testing:** Bias for Action versus recklessness. The question is what you cut, not that you delivered.
**Answer:** S09 (async ingestion where the verification endpoint was the thing you insisted on keeping) or S26 (support chatbot where escalation was non-negotiable). The pattern: name what you cut, name what you refused to cut, and name why the line was there.
**Follow-up trap:** *"What did cutting that cost you later?"* Every cut has a bill. Name it. If you claim you cut nothing and hit the deadline, either the deadline was not aggressive or you are not telling the whole story, and the interviewer will assume the second.

### Q10 — How do you decide between building and buying?
**Testing:** commercial judgment, whether you have a framework or a preference.
**Answer:** S15 with S17 as the pair. The framework: volume and its growth curve, whether the differentiator is the thing itself or what it enables, data-residency and compliance constraints, and the operational cost you are taking on. Then show you applied it non-uniformly, self-hosted vLLM for the high-volume online path, Bedrock batch for the offline path. Splitting the decision by workload shape is what a staff answer looks like.
**Follow-up trap:** *"What did self-hosting actually save?"* If you did not model it in dollars, say so and say that is the gap: you optimised for throughput and control and can defend both, but a cost model would have made the decision reviewable by a finance stakeholder. Do not invent a percentage.

### Q11 — Tell me about a time you improved something nobody asked you to improve.
**Testing:** ownership beyond the assigned ticket.
**Answer:** S08 (the 2,000-row golden baseline and 200+ tests, built alongside feature work because release confidence was the actual blocker) or S06.
**Follow-up trap:** *"How did you justify spending time on that instead of features?"* Have the argument: releases were gated on manual spot-checks, so every model or threshold change cost a human review cycle, and the baseline converted that into a CI step. Framing it as velocity rather than as quality is what makes it fundable. "It was the right thing to do" is a weak answer to a prioritisation question.

### Q12 — Tell me about the most difficult person you have worked with.
**Testing:** whether you can describe conflict without contempt.
**Answer:** Whichever real one you have `[CONFIRM: pick one and write it out. If the escalation in S06 or the migration pitch in S13 involved friction, use that.]` Rules: describe their position as reasonable from their vantage point, describe what you changed in your own approach, and do not reveal identifying details.
**Follow-up trap:** *"What was your part in it?"* If your answer has no contribution from you, you have failed the question. There is always a part: you did not bring evidence early enough, you escalated before trying once more one-on-one, you assumed shared context you did not have.

### Q13 — Why are you leaving? / Why us?
**Testing:** whether your motivation is coherent and whether you will leave them for the same reason.
**Answer:** Forward-looking and specific. Scale, problem class, or a domain you cannot reach where you are. Never criticise Cornerstone; you built a platform for 2M+ users there and disparaging it devalues your own stories. `[CONFIRM: your actual reason, written out in two sentences.]`
**Follow-up trap:** *"What would have kept you?"* An honest, non-grievance answer. Something structural (scope of problems available, technical direction) rather than personal (a manager, a review cycle). Grievance answers make the interviewer model you as the person who will have the same grievance about them in eighteen months.

### Q14 — You have described a lot of systems. What are you actually best at?
**Testing:** self-knowledge, and whether you know your own shape rather than claiming everything.
**Answer:** Pick one and defend it with two stories. The defensible claim from this resume: taking an ambiguous AI capability and turning it into a production system with boundaries, tests and cost characteristics, evidenced by S10 and S01. Then name what you are *not*: `[CONFIRM: your honest answer. Candidates who claim no weakness are scored as lacking self-awareness.]`
**Follow-up trap:** *"What are you weakest at?"* Must be real and must not be load-bearing for the role. Then say what you are doing about it with a specific action, not an intention. "I am working on it" is not an answer; "I built the golden baseline in S08 partly because evaluation rigour was a gap I knew I had" is.

### Q15 — Amazon-style: tell me about a time you dove deep into data to find a root cause.
**Testing:** Dive Deep specifically, which is one of the LPs most heavily weighted in engineering loops.
**Answer:** S04 (memory profile across a full run, not one page) or S28 (profiled before rebuilding) or S20 (identified 100+ external calls per request as the latency source before adding a cache).
**Follow-up trap:** *"What did the data tell you that you did not expect?"* Have a genuine surprise. For S04 it is that pagination alone did not fix it, because memory still ratcheted across pages, which pointed at allocator and GC behaviour rather than at the query. A story where the data confirmed your first guess does not evidence Dive Deep; it evidences a lucky guess.

### Q16 — Tell me about a time you had to say no.
**Testing:** judgment about scope and the ability to hold a line.
**Answer:** S05 (rejecting language auto-detection as the source of truth, and saying why: detection on short strings is unreliable and a wrong detection is silent) or S07 (rejecting a WAF-plus-sanitisation approach in favour of parameterization).
**Follow-up trap:** *"They insisted. Then what?"* Have the escalation path and the commit path. You can disagree, escalate once with evidence, lose, and then implement well while documenting the risk. That sequence is precisely Disagree and Commit and most candidates only rehearse the disagree half.

### Q17 — What is the largest number of people you have influenced with a technical decision?
**Testing:** the principal-level scope question, asked obliquely.
**Answer:** Reach for blast radius, not headcount. S19 (a mechanism adopted across the recommendation service fleet), S02 (a resolution engine other services consume), S01 (MCP tool contracts that other consumers reuse without importing your code). `[CONFIRM: how many engineers and teams actually consume these. This is the number that sets your level and it is not on your resume.]`
**Follow-up trap:** *"Did they adopt it because you convinced them or because you owned it?"* The honest answer is usually both, and the interesting part is what you did to make adoption easy: a versioned contract rather than a shared library, documentation, a migration path. Adoption you had to mandate is weaker evidence than adoption people chose.

### Q18 — Tell me about a time you worked with an incomplete or wrong requirement.
**Testing:** whether you push back on the problem statement, which is a defining staff behaviour.
**Answer:** S18 (the requirement was "improve search results"; the actual problem was that failed searches produced no product response at all, so you built generation from demand signal) or S24 (the ask was faster reports; the constraint was the human queue, not query speed).
**Follow-up trap:** *"How did you know the stated requirement was wrong?"* Evidence, not intuition. For S24 it is that turnaround was dominated by queue time rather than by query authoring, so making queries faster would not have moved the number. Reframing a requirement without evidence is how staff engineers build the wrong thing confidently.

---

## Red flags that fail you

- "We" throughout the Action section. The single most common cause of a no-hire on an otherwise strong story.
- A four-minute Situation. If the interviewer has not learned what you did by 45 seconds in, you have lost the round.
- A result with no number and no acknowledgement that there is no number.
- No rejected alternative anywhere in the loop. It reads as "found one thing that worked" rather than "chose."
- A "failure" story with no cost, or a "weakness" that is secretly a strength.
- Inflating a metric and then being unable to explain how it was measured. Bar Raisers are trained to pull on exactly this.
- Telling the same story to three interviewers without reframing. They share notes.
- Criticising your current employer or teammates. Every interviewer models you doing it to them next.
- Claiming credit for a system you reviewed rather than built. It collapses at the second follow-up.
- Answering a hypothetical with a story, or a behavioural question with a framework. Answer the form asked.
- Reciting "Situation, Task, Action, Result" out loud.
- Saying `ml.4xlarge` or `g4.2xlarge`. These are not real SageMaker instance types. Fix the resume.

---

## Cheat card

```
ANSWER SHAPE      S 10% · T 10% · A 50% · R 15% · why-not-X 10% · redo 5%
                  60-sec version = 9 sentences. Then STOP and offer a direction.
                  First person singular in every Action sentence. "I decided."

TOP 8             T1 S10 8-service platform      biggest scope / greenfield
                  T2 S01 A2A + FastMCP           technical direction / recent
                  T3 S04 OOM on 1.2M rows        hardest bug / dive deep
                  T4 S06 cross-tenant authz      highest standards / earn trust
                  T5 S13 -3,447 Java +812 Py     invent and simplify
                  T6 S28 4.5h → 30min (~89%)     quantified impact
                  T7 S15 vLLM self-host          frugality / build-vs-buy
                  T8 S21 Mongo race + loop       concurrency depth

NUMBERS (never round these)
   2M+ users · 8 services · 307 commits · 178K+ net LOC · ~25% engagement
   54,486 skills · 22 locales · 1.2M+ skill rows · Titan Embed v2 512-dim
   3,447 Java lines removed → 812-line Python service
   2,000+ golden baseline rows · 200+ tests · 100+ content-IDs cached
   50% report turnaround (Query Crafter) · 4.5h → 30min = ~89% (Expedia)
   7+ years · 2 Springer papers

LOOPS             Amazon 4-5 rounds, 2-3 LPs each, Bar Raiser has veto
                  Google interviewers write evidence → hiring committee scores packet
                  Meta 45-min "Jedi": ownership, conflict, ambiguity, mistakes
                  Microsoft competencies split by round → "As Appropriate" probes gaps
                  Netflix conversational, often no whiteboard, culture memo

MUST-HAVE STORIES you cannot enter a loop without
                  disagreed AND WAS WRONG · real failure with a real COST
                  said no and lost · influenced without authority
                  reframed a wrong requirement · prevented an expensive mistake

DO FIRST          S12: define the ~25% metric + measurement method (weakest link)
                  Fix resume: ml.4xlarge / g4.2xlarge are not real instance types
                  S28: reconstruct what was actually slow in the 4.5 hours

KILL SWITCHES     "we" · no number · no rejected alternative · 4-min situation
                  costless failure · same story twice · bad-mouthing employer
```

## Sources

- [Amazon's 16 Leadership Principles: Interview Guide (2026) — Exponent](https://www.tryexponent.com/blog/amazon-leadership-principles-interview) — accessed 2026-07-26
- [Amazon Leadership Principles: Resume Application, Interview Probe, Bar Raiser Read (2026) — ResumeAdapter](https://www.resumeadapter.com/companies/amazon/leadership-principles) — accessed 2026-07-26
- [Google Interview Process 2026: Loop & Committee — ResumeAdapter](https://www.resumeadapter.com/companies/google/interview-process) — accessed 2026-07-26
- [Google's Googleyness & Leadership Interview Guide — Prepfully](https://prepfully.com/interview-guides/googles-googleyness-interview) — accessed 2026-07-26
- [Meta Interview Process 2026: Rounds, AI-Assisted Coding & Behavioral Rubric Explained — ClavePrep](https://claveprep.com/blog/meta-interview-process-2026-guide) — accessed 2026-07-26
- [How software engineering behavioral interviews are evaluated at Meta — interviewing.io](https://interviewing.io/blog/how-software-engineering-behavioral-interviews-are-evaluated-meta) — accessed 2026-07-26
- [Behavioral interview round for Staff Engineer — Dilip Kumar](https://dilipkumar.medium.com/behavioral-interview-round-for-staff-engineer-f750eef6c438) — accessed 2026-07-26
- [Staff-plus interview processes — StaffEng](https://staffeng.com/guides/staff-plus-interview-process/) — accessed 2026-07-26
- [Project deep dive questions — ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide/blob/main/interview/questions/03-project-deep-dive.md) — accessed 2026-07-26
- [Microsoft Interview Process 2026: AA Loop, Questions & Timeline — OphyAI](https://ophyai.com/blog/company-guides/microsoft-interview-guide) — accessed 2026-07-26
- [Netflix Interview Process 2026: The Keeper Test, Culture Deck & How to Get Hired — ClavePrep](https://claveprep.com/blog/netflix-interview-process-2026-keeper-test-culture-deck) — accessed 2026-07-26
- [The 30 most common software engineer behavioral interview questions — Tech Interview Handbook](https://www.techinterviewhandbook.org/behavioral-interview-questions/) — accessed 2026-07-26

---

## Appendix: story → competency matrix

`##` = lead with this. `#` = usable if the lead is taken. Blank = do not reach for it.

| # | Story (short) | Owner­ship | Ambi­guity | Con­flict | Fail­ure | Data/­metrics | Simpl­ify | Depth | Cust­omer | Frug­ality | Influ­ence | Secur­ity | Deliv­ery |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | A2A + FastMCP multi-agent | # | ## | # |  |  | ## | # | # | # | # |  | # |
| S02 | Multi-tier skill resolution | # | # |  |  | # | # | ## | ## |  |  |  | # |
| S03 | ClickHouse HNSW over Weaviate |  | # | # |  | # | ## | ## |  | ## |  |  |  |
| S04 | OOM on 1.2M rows | # |  |  | # | # |  | ## |  | # |  |  | # |
| S05 | 22-locale inference | # |  | # |  |  | # | # | ## |  |  |  | # |
| S06 | Cross-tenant authz bypass | ## |  | ## | # |  |  | # | ## |  | # | ## |  |
| S07 | Parameterized SQL | # |  |  |  |  | # | # |  |  |  | ## |  |
| S08 | Golden baseline + 200 tests | ## |  |  | # | # |  | # |  |  | # |  | ## |
| S09 | Skillmaster async ingestion | # | # |  |  |  | # | # | # |  |  |  | ## |
| S10 | 8-service platform | ## | ## |  |  | # | # | # | # |  | # |  | ## |
| S11 | Critiquing own decomposition | # |  |  | ## |  | ## | # |  | # |  |  |  |
| S12 | The ~25% uplift measurement |  |  |  |  | ## |  | # | # |  |  |  | ## |
| S13 | Java → Python, -3,447 lines | ## |  | # |  | # | ## | # |  | ## | # |  | # |
| S14 | CMAB bandits |  | ## |  |  | ## |  | ## | # |  |  |  | # |
| S15 | vLLM self-host on SageMaker | # |  | # |  | ## |  | ## |  | ## |  |  | # |
| S16 | GPU instance benchmarking |  |  |  |  | ## |  | # |  | ## |  |  |  |
| S17 | Bedrock batch inference |  |  |  |  | # | ## | # |  | ## |  |  | # |
| S18 | GenAI content creator | # | ## |  |  | # |  | # | ## |  |  | # | # |
| S19 | JWT TTL + secret rotation | ## |  |  |  |  | # | # |  |  | ## | ## |  |
| S20 | Redis cache, 100+ IDs |  |  |  |  | # | # | ## | # | # |  |  | ## |
| S21 | Mongo race + event loop | # |  |  | # |  |  | ## |  |  |  |  | # |
| S22 | PySpark EMR pipeline | # | # |  |  | # |  | # |  | ## |  |  | ## |
| S23 | Async LLM rate limiting |  |  |  | # | # |  | ## |  | ## |  |  | # |
| S24 | Query Crafter NL-to-SQL | # | # |  |  | ## | ## | # | ## |  | ## | # | ## |
| S25 | Weaviate + KG cold start |  | ## |  | # | # | # | ## | # |  |  |  | # |
| S26 | Support chatbot + Jira | # |  |  |  | # |  | # | ## |  |  |  | ## |
| S27 | BigQuery/Airflow off Jenkins | # |  |  |  | # | ## | # |  | ## |  |  | # |
| S28 | 4.5h → 30min (~89%) | # | # |  |  | ## | # | ## | # | # | # |  | ## |
| S29 | Credit Suisse market risk | ## | ## | # |  | # | # |  | # |  | ## |  | ## |
| S30 | Career arc + Springer papers | # | # |  | # |  |  | # |  |  |  |  |  |

**Coverage check.** Every column has at least two `##`. The thinnest columns are **Conflict** (only S06 leads, so the second one must come from the escalation detail in S13 or S05, or from Q12 which you still have to write) and **Failure** (only S11 leads; strengthen with the attribution gap in S25). Those are your two gaps. Fill them before your first loop.

## Changelog
- 2026-07-26 — created
