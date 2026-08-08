# Boss: System Design Round

> **Track:** T15 Interview Simulator · **Time:** 1h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T15-round-design` · **Tags:** boss

**Runs under `tutor-mock` as round type `design`, driven by the `T10-design-method` procedure.**

## The round in 30 seconds

45 minutes, one open-ended prompt, no reference answer — the interviewer is scoring the sequence the candidate moves in, not the diagram at the end. A pass looks like: requirements converted into numbers before any box is drawn, an API contract and data model committed to before the architecture, a partition key that's derived rather than guessed, and at least one deliberate failure introduced and handled with a stated user-visible symptom and recovery. A fail looks like boxes drawn at minute three with the requirements retrofitted to justify them, no numbers anywhere in the design, or a candidate who cannot recover after being told twice that a component won't work under the stated load. In 2026, a design with no dollar figure attached reads as junior regardless of architectural correctness — cost is now a first-class non-functional requirement.

## Format

- **45 minutes**, one prompt, shared whiteboard/doc.
- **Minute-by-minute timeboxing**, derived from `T10-design-method`:
  - 0:00–2:00 — restate the problem and the scope contract (what's in scope, what's explicitly not, and the plan for how the 45 minutes will be spent).
  - 2:00–7:00 — functional and non-functional requirements, converted to numbers only where a number changes a downstream decision.
  - 7:00–12:00 — constraints/estimation: 2-3 numbers actually used, no more (QPS, storage growth, payload size).
  - 12:00–17:00 — API contract: 3-6 signatures with types and idempotency stated.
  - 17:00–24:00 — data model: tables/collections and, explicitly, the partition key and why.
  - 24:00–32:00 — architecture: the box diagram, derived from everything above, not recalled from a template.
  - 32:00–38:00 — scale: name the bottleneck the stated numbers actually produce, fix it.
  - 38:00–43:00 — failure modes: what breaks, what the user sees, how it recovers.
  - 43:00–45:00 — wrap: what you'd cut, what you'd build first.
- **What the interviewer does:** lets the candidate drive; interrupts scope creep and drift; pushes for a number whenever "it scales" or "it's fast" is asserted without one; asks "why this and not X" for at least two major decisions; introduces a twist mid-round (a 10x traffic spike, a new compliance requirement, a component going down) to see the recovery.
- **What the interviewer does not do:** draw anything; supply the requirements unprompted; let a wrong data-model decision go unchallenged if it will visibly break the stated access pattern; confirm the design is "good" before the round ends.
- **The interrupt lines**, used exactly as a real interviewer would:
  - At minute 20 with no API or data model yet: *"We're almost halfway through and I don't have a data model. Let's move."*
  - At minute 30 with boxes still being added with no derivation: *"Why does this box exist? Which requirement produced it?"*
  - At minute 33 if no number has been stated: *"Give me a QPS number. Just estimate it."*
  - At minute 40 if failure modes haven't started: *"We have 5 minutes left and no data model yet"* is the template failure-mode version of this — used verbatim if the round is genuinely about to run out of time on the highest-weighted section. *"Assume the primary database just went down. What does the user see, right now?"*
  - If the candidate drifts into unscoped territory: *"That's a good question but out of scope for our 45 minutes — park it and keep moving."*

## What is actually being tested

Not whether the final architecture matches a reference design — there isn't one. What's actually scored:

1. **Whether the sequence is derived or recalled.** A candidate who has memorized "recommendation system = feature store + model server + cache" and recites it regardless of the stated constraints is exposed the moment the interviewer changes one number (multi-tenant instead of single-tenant, 200 users instead of 200 million) and the candidate doesn't adjust the design.
2. **Whether requirements convert to numbers that get used.** Five minutes of capacity math that never influences a single downstream decision is theater; the interviewer is watching whether each number is introduced with a stated purpose ("I need QPS to decide whether one Postgres primary can take the write path") and then actually referenced later.
3. **Whether the API and data model come before the architecture.** An API signature forces the read/write split into the open; a schema commits to an access pattern, which determines the partition key, which determines whether the later scaling story is even coherent. Boxes drawn before this exist have nothing to be derived from.
4. **Whether cost is a first-class requirement.** A design that is technically correct and never mentions its dollar cost, especially anything GPU-adjacent, reads as incomplete in 2026 — the interviewer expects an order-of-magnitude monthly figure, not precision.
5. **Recovery under an interrupt.** The single highest-signal moment in the round is what happens after the interviewer says "that won't work at the stated load" or introduces a twist. A candidate who defends the original design past two direct challenges is failing regardless of how good the original idea was.

## Question bank

Twelve prompts, organized so the interviewer can pick one matched to the candidate's background. Each entry: the prompt as it would actually be given, what a strong opening 10 minutes looks like, what a weak one looks like, and the follow-up trap sprung mid-round.

### Warmup-weight prompts (used to calibrate, or for phone-screen-length versions)

**Q1 — Design a URL shortener.**
- **Strong:** Clarifies custom aliases vs. random, read:write ratio (typically read-heavy, ~100:1), and whether analytics/click tracking is in scope before designing. States that the core hard problem is short-code generation without collision at scale (base62 encoding of an auto-incrementing ID, or a pre-generated pool of codes, not random-and-retry which degrades as the keyspace fills), and that redirects are a cache-first read path (a CDN or in-memory cache in front of the datastore, since the redirect must be fast and is looked up far more than it's written).
- **Weak:** Jumps straight to "hash the URL with MD5" without addressing collisions, or spends 15 minutes on requirements for a genuinely simple system.
- **Follow-up trap:** *"Now a customer wants a custom vanity alias, and they want analytics with a 1-second freshness SLA on click counts. What changes?"* Tests whether the candidate can adapt a strong-consistency requirement (alias uniqueness check) alongside a separate, much looser one (click-count freshness, better served by an async counter pipeline than by synchronous writes to the primary record).

**Q2 — Design a rate limiter.**
- **Strong:** Names at least two algorithms (token bucket, sliding window log/counter) and states the actual tradeoff: token bucket allows controlled bursts and is memory-cheap; sliding window log is precise but memory-expensive per user; sliding window counter approximates the log cheaply. States where state lives for a distributed rate limiter (a shared store like Redis, with the race condition of concurrent check-and-increment across nodes as the thing that actually breaks a naive per-node implementation).
- **Weak:** Designs a single-node in-memory rate limiter and never addresses what happens with multiple API servers behind a load balancer, which is the entire point of the question at senior level.
- **Follow-up trap:** *"Two requests hit two different API servers in the same millisecond, both check the Redis counter, both see it under the limit, both proceed. You just let the limit be exceeded. Fix it."* Wants an atomic check-and-increment (a Lua script in Redis, or `INCR` with an expiry, evaluated atomically) rather than a separate GET-then-SET, which is the actual race.

### Mid-weight prompts

**Q3 — Design a news feed / social timeline (fan-out on write vs. fan-out on read).**
- **Strong:** States the actual tradeoff explicitly: fan-out-on-write (push a new post into every follower's precomputed timeline at post time) gives fast reads but breaks down for celebrity accounts with millions of followers (a single post triggers millions of writes); fan-out-on-read (compute the timeline at read time by merging each followed account's recent posts) avoids the celebrity write-amplification problem but makes every read expensive. States the real production answer: a hybrid, fan-out-on-write for normal accounts, fan-out-on-read (or a special-cased merge) for accounts above a follower-count threshold.
- **Weak:** Picks one strategy and never addresses the celebrity/hot-key case, which is the actual reason this question is asked.
- **Follow-up trap:** *"Your average user follows 50,000 accounts instead of 200. Does your design still work?"* This inverts the celebrity problem to a celebrity-follower problem — even fan-out-on-read now means merging 50,000 sources per page load, which forces a different structure (pre-aggregated shards, ranking before full merge, or a materialized top-N per source) and tests whether the candidate re-derives rather than defends the original answer.

**Q4 — Design a distributed rate-limited API gateway for a multi-tenant SaaS product, including per-tenant quotas.**
- **Strong:** Data model keyed on tenant, not just user, since the quota boundary is the tenant; states the isolation requirement explicitly (one tenant's burst must not starve another's quota, which some naive shared-counter designs get wrong); names the noisy-neighbor failure mode and a mitigation (per-tenant token buckets rather than one global counter).
- **Weak:** Designs a single global rate limiter with no tenant dimension, missing the entire point of "multi-tenant."
- **Follow-up trap:** *"A tenant with 2,000 users and a tenant with 2 users share your Redis cluster. The 2,000-user tenant's traffic is causing hot-key contention on their counter key. What do you do?"* Wants sharding the per-tenant counter across multiple keys (with a small accuracy tradeoff) or a local-approximate-then-reconcile pattern, not "just get a bigger Redis instance."

**Q5 — Design a distributed job scheduler (cron-as-a-service) that must not double-execute a job even if the scheduler node crashes mid-dispatch.**
- **Strong:** Names the exactly-once illusion problem directly: true exactly-once execution across a network is not achievable in the general case, so the real design goal is at-least-once execution plus idempotency at the consumer, or a distributed lock with a lease/fencing token to prevent two schedulers from both believing they own a job. States the specific failure this prevents: a scheduler acquiring a lock, crashing before releasing it, and a naive design either deadlocking forever (lock never released) or double-executing (a second scheduler grabs the job while the first is still actually running, just slow).
- **Weak:** Says "use a distributed lock" with no mention of lease expiry, fencing tokens, or the idempotency requirement on the job itself — leaving the double-execution problem structurally unsolved.
- **Follow-up trap:** *"Your lock has a 30-second lease. The job actually takes 45 seconds under load. Walk me through exactly what goes wrong."* The lease expires mid-execution, a second scheduler acquires the lock believing the first is dead, and now two instances of the job are running concurrently — the fix is either a heartbeat/lease-renewal mechanism from the still-alive worker, or accepting the job must be idempotent regardless, and stating which one is a real design decision, not a detail.

**Q6 — Design a real-time leaderboard for a game with 10M daily active users, needing top-100 and a user's own rank on demand.**
- **Strong:** Names a sorted-set data structure (Redis ZSET or equivalent) as the natural fit — O(log n) insert/update, O(log n + k) range query for top-k, O(log n) rank lookup for an arbitrary user — and states why a naive "sort the whole table on read" or "recompute rank with a SQL window function per request" fails at this write volume (every score update would require a full re-sort or an expensive ranked query against a live table).
- **Weak:** Proposes a relational table with a `rank` column recomputed via a batch job, and can't explain what a user sees if they check their rank between batch runs (stale data with no stated staleness bound).
- **Follow-up trap:** *"Now you need separate leaderboards per game mode and per region — 200 leaderboards total, some with 10 users, some with 2 million. Does one Redis sorted set per leaderboard still work?"* Tests whether the candidate recognizes this is now a sharding/resource-allocation problem (200 sorted sets of wildly different sizes on shared infrastructure) rather than a single-leaderboard scaling problem, and can propose a reasonable allocation (small leaderboards colocated, large ones isolated or further partitioned).

### Staff / Principal-weight prompts

**Q7 — Design a RAG-based customer support answer system for an enterprise product, including the cost model.**
(Draws on `T10-genai-designs`; use if the candidate's background is GenAI-heavy.)
- **Strong:** Requirements split cleanly: functional (answer support queries grounded in product docs, cite sources), non-functional (latency budget for a support UI, typically a few seconds is acceptable unlike a search box), and the GenAI-specific ones the classic framework doesn't have — a token/cost budget per query, an eval strategy for correctness (since a wrong-but-fluent answer returns 200 OK and looks fine in every conventional dashboard), and a stated blast radius for a hallucinated answer in a support context (a wrong troubleshooting step could damage a customer's system, so the design should include a confidence threshold below which the system defers to a human rather than answering). States a cost estimate with the arithmetic shown: retrieval cost (embedding + vector search, cheap) plus generation cost (dominant, roughly $X per 1K queries at Y tokens per query) and names what drives it (context length, model choice, whether reranking is included).
- **Weak:** Draws the standard retrieve-then-generate diagram with no cost figure, no eval mention, and no answer for what happens when the system doesn't know — silently generating a plausible-sounding wrong answer being treated as an acceptable default rather than a named failure mode.
- **Follow-up trap:** *"Support ticket volume triples overnight because of an outage. Your GenAI cost triples with it and finance is asking why. What do you do?"* Wants a real answer: caching for repeated/similar queries (semantic cache keyed on query embedding, not exact match), a cheaper model for a first-pass triage with escalation to the expensive model only when needed, or a hard per-tenant/per-hour budget ceiling with graceful degradation — not "just pay for it," which is the naive answer that gets flagged.

**Q8 — Design the eight-service decomposition for a recommendation platform serving 2M+ users, and defend or critique your own seam lines.**
(This is a resume-adjacent design prompt — see `curriculum/10-system-design/09-resume-systems.md` and `T14-star-bank` S10/S11 for the underlying real system this pattern is drawn from.)
- **Strong:** Draws seams around independently-varying scaling and failure profiles (a read-heavy, latency-bound vector search service; a write-heavy, throughput-bound event processor; a batch-shaped profile builder) rather than around data entities, and states this criterion explicitly before drawing anything. When asked to critique, applies the same criterion honestly: any two services that always deploy together and never scale independently are one service with a network hop, and names a real merge candidate rather than defending all eight as equally justified.
- **Weak:** Draws eight boxes because the prompt said eight, with no criterion for why the lines are where they are, and defends the decomposition as obviously correct when pushed.
- **Follow-up trap:** *"Your event processor and your user-context service always deploy together and have never once scaled independently in six months of data. Why are they still two services?"* The strong answer either produces a real justification (their failure isolation genuinely matters even though scaling doesn't diverge) or honestly concedes the merge — "I'd need six more months of data before I'd defend keeping them separate" is a legitimate staff-level answer; defending the split with no evidence is not.

**Q9 — Design a multi-tenant vector search service backed by a shared index, serving 1M+ rows across 22 locales with per-tenant precedence rules.**
(Resume-adjacent — draws on the skill-resolution engine pattern.)
- **Strong:** States the filtered-ANN problem explicitly: every real query here is filtered by tenant and locale, and a metadata pre-filter bolted onto an ANN index (filter after retrieving top-k, which can return zero valid results if the top-k happens to be entirely the wrong tenant) is a common, real bug — the fix is a native filtered index or filtering that's structurally part of the retrieval, not applied after. Names the precedence cascade (tenant-custom, then external, then master/global) as an explicit design decision with a stated reason (tenant-specific vocabulary must win over a better-scoring global match, which is the opposite of what a flat single embedding space would do by default).
- **Weak:** Designs a single flat vector index with tenant ID as a metadata field filtered post-retrieval, without noticing this can silently return degraded or wrong results when the top-k candidates skew toward a different tenant.
- **Follow-up trap:** *"At what row count or QPS would you stop indexing in place (e.g., in your existing OLAP store) and move to a dedicated vector database, and why haven't you done it yet?"* Wants a stated, defensible threshold (an order of magnitude more rows, or a second product needing the same vectors) rather than either extreme ("never migrate" or "always use a dedicated vector DB") — the seniority signal is having written the crossover trigger down rather than carrying it as a vague intuition.

**Q10 — Design the failure-handling and cost controls for a self-hosted LLM serving platform (vLLM on GPU instances) that must serve both interactive and batch workloads without one starving the other.**
(Resume-adjacent — draws on the vLLM/SageMaker + Bedrock-batch split.)
- **Strong:** Separates the two workload shapes onto different infrastructure explicitly rather than sharing a serving path: interactive traffic needs low, predictable latency and should never be capacity-contended by a large batch job; a 1M-row offline generation job is latency-indifferent and throughput-bound, and belongs on a separate batch path (a managed batch inference service, or a separate GPU pool) so it structurally cannot starve interactive capacity. States the mechanism that makes self-hosted serving efficient in the first place (continuous batching plus PagedAttention-style KV-cache management, which is what turns single-digit GPU utilization into useful throughput for many concurrent short requests) and the actual cost lever (instance family chosen by measured throughput-per-dollar at realistic concurrency, not by GPU memory size alone, which can hide a KV-cache-driven throughput collapse under load that a memory-fit check wouldn't catch).
- **Weak:** Puts batch and interactive traffic through the same serving endpoint with "we'll just add more instances if it's slow," with no isolation and no cost lever named.
- **Follow-up trap:** *"Finance asks for the actual dollar cost per million tokens served, split by interactive vs. batch. You don't have that number. What's your first move, and what should have existed already?"* Wants a real answer: per-workload cost attribution requires the batch and interactive paths to be separately instrumented and, ideally, separately billed infrastructure from day one — retrofitting cost attribution onto a shared, unlabeled pool of GPU instances after the fact is expensive and imprecise, and a candidate who has actually operated this system should know that.

**Q11 — Design a system that must support both a hard real-time consistency requirement (inventory count during checkout) and a much looser one (product recommendation freshness) in the same product.**
- **Strong:** Explicitly refuses to apply one consistency model to the whole system: inventory during checkout needs strong consistency or an explicit reservation/lock mechanism (oversell is a real, costly, customer-facing failure), while recommendation freshness can tolerate eventual consistency measured in minutes with no customer-visible harm. States the actual mechanism for the strict path (a database transaction with row-level locking or a reservation token with a short TTL, released if checkout doesn't complete) versus the loose path (an async pipeline, cache with a stated staleness bound).
- **Weak:** Applies a single consistency model to the whole system — either everything eventually consistent (risking oversell) or everything strongly consistent (paying a latency/throughput tax on the recommendation path for no benefit).
- **Follow-up trap:** *"Two customers add the last unit of an item to their cart within 50ms of each other. Walk me through exactly what happens in your design, step by step, and tell me what the losing customer sees."* Forces a precise mechanical trace (who acquires the reservation, what the second request's actual response is, whether it's an honest "out of stock" or a race that silently oversells) rather than a hand-wave — "the database handles it" is not an answer.

**Q12 — Design an agent-based system that can take actions on a user's behalf (e.g., booking, purchasing, sending communications), including the safety and rollback design.**
(Draws on `T10-genai-designs` and the agentic trust-boundary material in `T15-round-genai`.)
- **Strong:** Treats "can take actions" as the load-bearing requirement and designs around it from the start: privileged/irreversible actions gated by a policy layer outside the model (an explicit allowlist, spend limits, or human-in-the-loop confirmation for anything above a stated risk threshold), full action logging with enough detail to reconstruct why the agent decided to act, and a rollback or compensation path for actions that can be partially undone (a cancellable booking, a refundable purchase) versus an explicit acknowledgment for the subset that cannot (a sent email cannot be unsent, so the confirmation gate for that action class must be stricter). States the blast-radius question directly: what's the worst single action this agent could take, and is that action gated proportionally to its cost.
- **Weak:** Designs the agent's reasoning loop in detail and treats "take the action" as a simple tool call with no separate authorization layer, no logging design, and no distinction between reversible and irreversible actions.
- **Follow-up trap:** *"The agent's tool-call arguments were generated based on a webpage the agent was asked to summarize, and that webpage contained a prompt injection instructing it to change the shipping address on an order. Where, specifically, in your design does this get caught?"* Wants a precise answer pointing at a specific enforcement point (a code-level check that the shipping address change matches an allowlisted pattern, or requires a fresh user confirmation, independent of what the model claims its intent is) — not "the model would recognize the injection and refuse," which is exactly the un-enforceable assumption this question exists to catch.

## Rubric

| Dimension | 1-2 | 3 | 4-5 |
|---|---|---|---|
| Correctness / depth | Architecture doesn't match the stated requirements; data model doesn't support the primary access pattern (e.g., no partition key, or one that forces a scatter-gather on the hot query); no numbers anywhere | Architecture broadly matches requirements; partition key exists but its consequence for the hot query isn't stated; some numbers present but not all connected to a decision | Every major component traces to a specific requirement or number stated earlier; partition key is derived from the access pattern and its cost is named explicitly; numbers are used, not decorative |
| Structure / method | Draws boxes before requirements or API; no API contract or data model produced without heavy prompting; ignores interrupt lines and keeps going down the same path | Follows requirements → API → data model → architecture with prompting to move between phases; responds to interrupts but loses time doing so | Drives the sequence unprompted, narrates the transition between phases ("I have the read path bounded, moving to the data model"); self-checkpoints against the clock without being told to |
| Communication | Names technologies without grounding them in the stated problem ("we'll use Kafka" with no reason); cannot be followed without the interviewer re-asking basic questions | Explains choices when asked; occasionally over-explains basics the interviewer already knows, or under-explains a genuinely novel choice | Explains at the right altitude for a staff-plus peer; states reasoning structure before diving in ("there are three constraints, I'll take them in order of how much they narrow the design") |
| Seniority signals | Never states a tradeoff or a rejected alternative; treats every technology choice as obviously correct; defends the original design after being told twice it won't work at the stated load | States one tradeoff when asked; adapts the design after an interrupt but needs it repeated | States tradeoffs and rejected alternatives unprompted; states cost explicitly, including for non-GenAI systems where relevant; recovers from an interrupt within one exchange and explicitly names what changed and why |

## Score bands

- **17-20 — STRONG HIRE.** Requirements-to-numbers-to-API-to-data-model-to-architecture sequence is self-driven with no prompting between phases; every box on the diagram traces to something said earlier; cost is stated with real arithmetic; recovers from an interrupt or a "why not X" challenge within one exchange, updating the design rather than defending it. This is the design-review peer a staff+ hiring committee is trying to identify.
- **13-16 — HIRE.** Sequence is right with occasional prompting to move phases; numbers are present and mostly used; recovers from an interrupt with one nudge; states at least one real tradeoff unprompted.
- **9-12 — LEAN HIRE.** Gets to a reasonable architecture but the sequence was recalled more than derived — requirements were thin or retrofitted, the data model's partition key wasn't stated until asked directly. Defends the original design somewhat before adapting to an interrupt.
- **5-8 — NO HIRE.** Boxes drawn early with no derivation; no numbers, or numbers that are never referenced again; cannot answer "why this and not X" for any major decision; struggles to recover from an interrupt even after a second prompt.
- **0-4 — STRONG NO HIRE.** No requirements gathered at all; architecture is a memorized reference design that doesn't fit the stated constraints and the candidate doesn't notice; defends the design after being told directly, twice, that it fails at the stated load.

## Red flags that end the round

- Drawing the architecture diagram in the first 5 minutes.
- No number produced anywhere in the round, even after a direct prompt ("just estimate it").
- No partition/sharding key named for the primary data store, or one that visibly doesn't support the stated hot query.
- Defending a design after the interviewer has stated twice, plainly, that it will not work at the given load.
- No cost figure for a GenAI or GPU-adjacent design when directly asked.
- Treating every named technology as interchangeable trivia ("we could use Postgres or MongoDB, doesn't really matter") with no access-pattern-driven reason for either.
- Not noticing or responding to an interrupt line at all — continuing to add unscoped detail after being told time is short.

## Time-management failures

- **Spending 20+ minutes on requirements with no architecture time left.** The inverse failure — endless clarifying questions that never convert into a number — is just as damaging as skipping requirements entirely, and it is a documented, common failure mode at this level.
- **Drawing boxes at minute 3 and spending 25 of the 45 minutes on the high-level diagram.** Reported as the single most common pacing failure across FAANG-style loops: everyone knows the four-step framework, and most candidates still spend the majority of the round on the step that should take 8-10 minutes, leaving almost nothing for the deep dive that actually carries the score weight.
- **No time reserved for failure modes.** A design with excellent architecture and zero minutes left for "what breaks and what does the user see" reads as incomplete regardless of how good the first 40 minutes were, because failure-mode reasoning is explicitly part of what's being scored, not a bonus round.
- **Getting stuck defending a partition key choice instead of re-deriving it.** When an interrupt reveals the partition key doesn't support the stated access pattern, the fast recovery is re-deriving from the access pattern, not arguing that the original choice was "probably fine."
- **Chasing a component depth-first the interviewer didn't ask for.** Spending 10 minutes designing the internals of a message queue when the interviewer named it and moved on is a classic Google-style trap (naming a component is not always an invitation to build it) — read the room, or ask directly whether depth here is wanted.

## Cheat card

```
SEQUENCE (don't skip, don't reorder): restate → requirements → numbers (2-3,
  each with a stated USE) → API (3-6 sigs, idempotency) → data model
  (tables + PARTITION KEY, stated why) → architecture (derived, not recalled)
  → scale (name the bottleneck the numbers actually produce) → failure
  (what breaks, what user sees, recovery) → wrap (cut / build-first)
TIMEBOX (45 min): 2 / 5 / 5 / 5 / 7 / 8 / 6 / 5 / 2
EVERY BOX must trace to a requirement or number stated earlier — if it can't,
  cut it or explain why it's there
NUMBERS RULE: compute only what you're about to USE, state the use before
  computing ("I need QPS to decide if one Postgres primary suffices")
PARTITION KEY comes from the ACCESS PATTERN, always. State the cost
  ("hot partition for the largest tenant, mitigated by a composite key")
COST is now a first-class NFR — state a monthly dollar figure, order of
  magnitude is fine, for anything GPU/LLM-adjacent especially
INTERRUPT RESPONSE: don't defend, re-derive. "Given that constraint, the
  partition key changes to X because..." — adapt within one exchange
FAN-OUT: write (fast read, breaks on celebrity/hot-key) vs. read (slow read,
  handles hot-key) — real systems use a HYBRID with a threshold
IDEMPOTENCY: exactly-once across a network doesn't exist — design for
  at-least-once + idempotent consumer, or a lease+fencing token
CONSISTENCY IS NOT ONE SETTING: strong where oversell/money is at risk,
  eventual everywhere else — name which is which explicitly
GenAI-SPECIFIC NFRs: token/cost budget, eval strategy (200 OK ≠ correct),
  hallucination blast radius, confidence threshold for human handoff
AGENT ACTIONS: privileged/irreversible actions gated by CODE outside the
  model (allowlist, spend limit, human confirm) — never by prompt alone
NEVER: draw before requirements exist. NEVER: assert "it scales" with no number.
NEVER: defend a design after being told twice it fails at the stated load.
```

## Sources

- [Designing From Scratch: Requirements → Constraints → API → Data → Scale → Failure — `curriculum/10-system-design/10-design-method.md`](../10-system-design/10-design-method.md) — internal, cites [DesignGurus rubric breakdown](https://designgurus.substack.com/p/the-complete-system-design-interview) and [DesignGurus 2026 playbook](https://designgurus.substack.com/p/system-design-interviews-changed) — accessed 2026-07-26
- [The 45-Minute System Design Communication Framework — `curriculum/14-behavioral-principal/03-design-communication.md`](../14-behavioral-principal/03-design-communication.md) — internal, cites [DesignGurus, 45-minute framework](https://designgurus.substack.com/p/how-to-design-any-system-in-45-minutes) and [Deep Engineering, why senior engineers fail](https://deepengineering.substack.com/p/why-senior-engineers-fail-system-design-interviews) — accessed 2026-07-26
- [Your Flagship Systems as Formal Design Docs — `curriculum/10-system-design/09-resume-systems.md`](../10-system-design/09-resume-systems.md) — internal, resume-adjacent design prompts source
- [GenAI and Agent System Designs — `curriculum/10-system-design/07-genai-designs.md`](../10-system-design/07-genai-designs.md) — internal, GenAI-specific NFR framing source
- [Netflix System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/netflix-system-design-interview) — accessed 2026-07-26
- [Google system design interview — Exponent](https://www.tryexponent.com/blog/google-system-design-interview) — accessed 2026-07-26
- [Stripe system design interview — Exponent](https://www.tryexponent.com/blog/stripe-system-design-interview) — accessed 2026-07-26

## Changelog
- 2026-08-01 — created
