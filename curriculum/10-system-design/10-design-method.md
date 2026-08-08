# Designing From Scratch: Requirements → Constraints → API → Data → Scale → Failure

> **Track:** T10 System Design · **Time:** 3h · **Prereqs:** `T10-distributed-fundamentals` · **Updated:** 2026-07-26
> **Module id:** `T10-design-method` · **Tags:** sprint, craft, critical

## The 30-second version

A system design round is a 45-minute test of whether you can drive an underspecified problem to a defensible design, and the interviewer is scoring the *sequence you moved in*, not the diagram you ended with. The sequence that works is fixed: restate the problem, separate functional from non-functional requirements, convert every vague ask into a number, write the API contract, design the data model, only then draw the architecture, then scale it against the numbers you already computed, then break it on purpose. The two failure modes that sink most candidates are both timing failures: spending 20 minutes on requirements so there is no time to scale anything, or drawing boxes at minute three so every later decision is unjustified. Hold to roughly 5 / 5 / 5 / 7 / 8 / 6 / 5 / 2 minutes across those phases, narrate the transition between each ("I have the read path bounded, moving to the write path"), and you will out-score candidates with more knowledge and less structure.

## Why this gets asked

The round exists because the interviewer has been on the receiving end of a design that was technically impressive and wrong: a service built for a consistency model nobody needed, a schema that made the primary query a scatter-gather, a queue added because queues are good rather than because the write path needed decoupling. All of those come from the same root cause, which is starting at the architecture. So the round is designed to be underspecified on purpose. "Design Twitter" has no answer; it has a *process* that produces an answer, and the interviewer's rubric is mostly about that process. Requirements gathering is typically weighted around 15% of the score and high-level architecture around 25%, with trade-off articulation around 20% at senior level ([DesignGurus rubric breakdown](https://designgurus.substack.com/p/the-complete-system-design-interview) — accessed 2026-07-26); the remaining weight sits in the last 10 to 15 minutes, on scale and failure, which is exactly the part candidates run out of time for.

The 2026 wrinkle: the bar moved. AI and LLM infrastructure prompts have migrated into general engineering loops (roughly half of loops now include an ML-adjacent question, up from about one in ten in 2024), and **interviewers now grade cost** ([DesignGurus 2026 playbook](https://designgurus.substack.com/p/system-design-interviews-changed) — accessed 2026-07-26). A design with no dollar figure attached reads as junior in 2026 in a way it did not in 2023.

---

## Lineage: past → present → future

**What came before.** Through the 2010s the system design round was largely unstructured and the prevailing candidate strategy was pattern recall: memorise the reference architectures for a URL shortener, a news feed, a chat system, a rate limiter, and hope the prompt matched one. The pain that killed it was **interviewer-visible brittleness**. A candidate who had memorised "Twitter = fanout-on-write to a Redis timeline cache" would recite it confidently and then collapse the moment the interviewer said "now the average user follows 50,000 accounts" or "this is for a B2B product with 2,000 tenants", because the recalled architecture carried no derivation. Interviewers responded by deliberately mutating the classic prompts, which made pattern recall a liability rather than a shortcut. The first widely-adopted counter was Alex Xu's four-step framework (*System Design Interview*, 2020: scope, high-level design, deep dive, wrap up), which fixed the "starts drawing immediately" problem but left the middle underspecified: it did not say to write the API before the architecture, and it treated capacity estimation as optional garnish.

**Where it stands now.** The consensus procedure in 2026 is more granular and puts two artefacts before the boxes: **the API contract** and **the data model**. That ordering is the current centre of gravity because it is falsifiable. An API signature commits you to what the client sends and what it gets back, which forces the read/write split into the open; a schema commits you to the access pattern, which determines the partitioning key, which determines whether your scaling story is even possible. Stripe-style rounds score these hardest and explicitly penalise hand-waving the data model ([Exponent, Stripe system design](https://www.tryexponent.com/blog/stripe-system-design-interview) — accessed 2026-07-26). Google-style rounds differ in that naming a component is an invitation to implement it: say "message queue" and you may be asked to build one, so the procedure has to leave slack for an unplanned depth excursion ([Exponent, Google system design](https://www.tryexponent.com/blog/google-system-design-interview) — accessed 2026-07-26).

There are two live disagreements worth knowing because interviewers sit on both sides. The first is **whether to do capacity estimation at all**. One camp holds that numbers are the only thing separating a design from a drawing; the other holds that five minutes of arithmetic that never gets used is theatre, and some interviewers now say "assume it's large, skip the math". The resolution that satisfies both: compute only the two or three numbers you are about to *use*, and say what each will decide ("I need QPS to decide whether one Postgres primary can take the write path"). The second is **breadth versus depth**: Meta-style rounds reward covering the whole system and then going deep on one or two components under the interviewer's steering; Amazon-style rounds interleave leadership-principle probing and reward operational depth. Both punish the same thing, which is 25 minutes on the high-level architecture with no time left for deep dives.

**Where it's heading.** Three directions. First, high confidence: **cost becomes a first-class non-functional requirement**, alongside latency and availability. Expect to be asked "what does this cost per month at 10M users" and to have a defensible number. Second, high confidence: **LLM-in-the-loop prompts become standard** ("design a recommendation feed with an LLM-generated summary", "design safeguards for an agent that takes actions on a user's behalf"), which adds three requirements categories the classic procedure never had (token budget, non-determinism/eval, prompt-injection and blast radius) ([KORE1, senior system design questions 2026](https://www.kore1.com/system-design-interview-questions/) — accessed 2026-07-26). Third, more speculative: rounds are drifting from whiteboard to shared collaborative canvas or a plain text editor, which changes the craft (you can type an OpenAPI stub and a `CREATE TABLE` in seconds, so the bar for API and schema specificity rises). Treat that last one as a trend, not a settled fact, and ask at the start which medium the round uses.

---

## Mental model

One 45-minute clock, eight phases, each producing an artefact the next phase consumes. If a phase produces nothing the next phase needs, you skipped it wrong.

```
 0:00                                                                   45:00
  │                                                                        │
  ├─0 RESTATE ────────┐ 2 min   artefact: one sentence + scope contract
  ├─1 REQUIREMENTS ───┐ 5 min   artefact: 3-5 FRs (in scope) + NFR table
  ├─2 CONSTRAINTS ────┐ 5 min   artefact: 3 numbers you will actually USE
  ├─3 API ────────────┐ 5 min   artefact: 3-6 signatures w/ types + idempotency
  ├─4 DATA MODEL ─────┐ 7 min   artefact: tables/collections + PARTITION KEY
  ├─5 ARCHITECTURE ───┐ 8 min   artefact: the box diagram (derived, not recalled)
  ├─6 SCALE ──────────┐ 6 min   artefact: bottleneck named + fix per component
  ├─7 FAILURE ────────┐ 5 min   artefact: what dies, what the user sees, recovery
  └─8 WRAP ───────────┘ 2 min   artefact: what you'd cut, what you'd build first

  Each arrow is a THING YOU SAY OUT LOUD:
     "...so the NFRs are latency-critical read path, tolerant writes."
     "...which means ~18k peak read QPS. That's what sizes the cache."
     "...GET /v1/feed?cursor= — cursor, not offset, because of insert skew."
     "...partition by user_id, so the feed read is single-partition."
     "...now the boxes, and every box exists because of one line above."
```

**The load-bearing property: each phase's artefact constrains the next.** That is why the order is not arbitrary and not swappable.

```
  requirements ──▶ tells you WHICH numbers matter
     numbers   ──▶ tells you whether one machine suffices (often it does)
       API     ──▶ tells you the read/write split and the payload sizes
    data model ──▶ tells you the partition key
   partition key ▶ tells you which queries are cheap and which are scatter-gather
   architecture ▶ is now DERIVED. Every box traces to a line above it.
      scale    ──▶ attacks the specific number that breaks the specific box
     failure   ──▶ attacks the specific box whose loss is worst
```

Run it backwards and you get the classic failure: boxes first, then a hunt for requirements that justify the boxes you already drew. Interviewers can see this happening in real time, because the requirements you "discover" are suspiciously exactly the ones your recalled architecture needs.

---

## How it actually works

### Phase 0 — Restate and set the scope contract (0:00 to 2:00)

Two sentences, then one question.

1. **Restate in your own words**, including the thing that is ambiguous. "So: a service where users post short text, follow other users, and read a merged reverse-chronological feed of the people they follow. I am reading 'feed' as home timeline, not search or explore."
2. **Name the scope contract.** "I'll aim for requirements and numbers by minute 12, API and schema by 24, then architecture, then scaling and failure. Stop me and redirect whenever you want."

That second sentence is disproportionately valuable. It signals time-awareness (a graded behaviour) and it gives the interviewer a cheap way to steer you, which they will use. If they say "actually I care most about the write path", you just saved yourself 20 minutes.

Then the one question: **"Is there a specific area you want me to go deep on, or should I drive?"** At staff/principal level the expected answer is that you drive, but asking costs 5 seconds and occasionally saves the round.

### Phase 1 — Requirements: functional vs non-functional (2:00 to 7:00)

Two lists, drawn as two lists, because the visual separation is itself a signal.

**Functional requirements** are user-visible capabilities, phrased as verbs. Cap the in-scope list at 3 to 5. Explicitly push the rest out loud: **"Out of scope unless you want it: search, DMs, media upload, ads, moderation."** Declaring out-of-scope items is worth more than declaring in-scope ones, because it proves you know the surface area is larger than you can build in 45 minutes.

**Non-functional requirements** are the ones that determine the architecture. Do not free-associate; walk a fixed checklist so you never miss one under pressure. The mnemonic is **SCALD-CoM**:

| | NFR | The question that extracts it | Why it changes the design |
|---|---|---|---|
| **S** | Scale | "DAU, and how many actions per user per day?" | Sizes everything downstream |
| **C** | Consistency | "If a follower reads 2 seconds after I post and misses it, is that a bug or fine?" | Decides sync vs async fanout, quorum settings |
| **A** | Availability | "What's the SLO? Is a read-only degraded mode acceptable?" | Decides multi-region, failover posture |
| **L** | Latency | "p99 target for the read? Is the write allowed to be slow?" | Decides caching and precomputation |
| **D** | Durability | "Can we ever lose a write? Post vs. view-count increment?" | Decides WAL/replication/ack semantics |
| **Co** | Cost | "Rough budget, or is this cost-insensitive?" | 2026: graded. Have a number. |
| **M** | Multi-tenancy / compliance | "Consumer or B2B? Data residency? PII? GDPR delete?" | Can invalidate a whole architecture |

Ask five or six of these, not all seven, and pick based on the prompt. Then **write the answers down as a table** and refer back to it later by name. Referring back ("this is the durability requirement from earlier, so I can't ack before the WAL fsync") is one of the highest-signal behaviours in the round.

**The clarifying questions that actually earn points** are the ones whose answer would change your design. Compare:

| Low-value question | Why it's low value | High-value replacement |
|---|---|---|
| "How many users?" | Answer is "a lot"; you learn nothing actionable | "What's the read:write ratio?" — 100:1 vs 2:1 are different systems |
| "Should it be scalable?" | Rhetorical | "What's the fanout distribution? Do we have accounts with 50M followers?" |
| "Do we need a database?" | Insulting | "Is the feed strictly reverse-chronological or ranked? Ranked kills precomputation." |
| "Any tech constraints?" | Too broad | "Is there an existing auth service and object store I should assume?" |
| "Mobile or web?" | Rarely load-bearing | "Do clients need real-time push, or is pull-on-open enough?" |
| — | | "What's the retention policy? 30 days vs forever is a 100× storage difference." |
| — | | "Is this global? Cross-region writes change the consistency story entirely." |

The pattern: **a good clarifying question names two concrete alternatives and states that they lead to different designs.** That framing forces a useful answer and demonstrates that you know why you asked.

**When the interviewer refuses to answer** (common, and deliberate): state an assumption, mark it, and move. "I'll assume 100:1 read:write, which is typical for social. If it's closer to 2:1 the precomputed-timeline approach stops paying for itself and I'd flip to read-time merge." Now you have converted a blocked question into a demonstrated tradeoff, which scores better than the answer would have.

### Phase 2 — Constraints: turn vague asks into numbers (7:00 to 12:00)

Rules for this phase:

1. **Compute only numbers you will use, and say what each decides.** Three or four numbers, maximum. Announce the purpose before the arithmetic: "I want peak read QPS, because that decides whether a single cache tier is enough."
2. **Round aggressively.** 86,400 seconds per day becomes 100,000. 50M DAU × 10 reads becomes 5 × 10⁸. Say "I'm rounding to powers of ten; I care about the exponent, not the mantissa."
3. **Peak, not average.** Average QPS never sized anything. Multiply by 2 to 3× for a general web workload, 5 to 10× for spiky ones (ticket sales, live events, cron-triggered pushes).
4. **End with a sanity check.** Compare the result to a system whose scale is public. "18k peak read QPS is roughly one mid-size Redis cluster, not a research problem."

Worked micro-example, spoken in ~45 seconds:

```
50M DAU · 10 feed opens/day  → 5×10^8 reads/day ÷ 1×10^5 s ≈ 5,000 read QPS avg
50M DAU · 1 post/day         → 5×10^7 writes/day ÷ 1×10^5 ≈   500 write QPS avg
peak ×3                      → ~15,000 read QPS · ~1,500 write QPS
read:write ≈ 10:1 at the API, but with fanout-on-write, amplified writes =
   500 writes/s × 500 avg followers = 250,000 timeline inserts/s   ← THE number
```

That last line is the whole point of the phase. The API-level write rate is trivially small; the *amplified* write rate is the thing that will break, and naming it at minute 11 makes your entire architecture look inevitable rather than recalled. Full estimation mechanics live in `T10-estimation`.

### Phase 3 — API contract before architecture (12:00 to 17:00)

Write the signatures. Three to six of them. This is the phase most candidates skip and it is the cheapest score in the round.

```
POST /v1/posts
  headers: Authorization, Idempotency-Key: <uuid>
  body:    { text: string(<=280), client_ts: int64 }
  → 201    { post_id: string, created_at: int64 }
  errors:  400 invalid, 401, 409 duplicate idempotency key, 429 rate limited

GET  /v1/feed?limit=20&cursor=<opaque>
  → 200    { items: [{post_id, author_id, text, created_at}], next_cursor: string|null }
  cursor is an opaque base64 of (created_at, post_id) — NOT an offset

POST /v1/follows   { target_user_id }        → 202 (async fanout backfill)
DELETE /v1/follows/{target_user_id}          → 204
```

Five things in that block are each worth a point, and all five are cheap:

- **Versioned path** (`/v1/`). Shows you expect the contract to change.
- **Idempotency key on the write.** Pre-empts the "what if the client retries" follow-up. State the server behaviour: store `(key → response)` with a TTL longer than the client's retry window, return the stored response on repeat.
- **Cursor, not offset.** Offset pagination on an insert-heavy list duplicates and skips rows as new items shift the window. Say that sentence; it is a classic trap.
- **`202` on follow.** Encodes that fanout is asynchronous, before you have drawn a single queue. The architecture then explains an API decision rather than the reverse.
- **Explicit error codes including `429`.** Rate limiting exists in your design because the contract says so.

Then say the sentence that justifies the phase: **"The API tells me the read path is one query returning ~20 rows of ~300 bytes, so ~6 KB per response, and the write path is small but fans out. That asymmetry is what the architecture has to reflect."**

For gRPC or event-driven systems the same rules apply: write the proto message and the topic schema, and state delivery semantics (at-least-once with an idempotent consumer is the default correct answer; exactly-once needs you to say "effectively-once via dedup keys" and mean it).

### Phase 4 — Data model before scaling (17:00 to 24:00)

Schema first, then the one line that matters: **the partition key.**

```
users(user_id PK, handle UNIQUE, created_at)
posts(post_id PK, author_id, text, created_at)            -- partition: post_id (hash)
follows(follower_id, followee_id, created_at)              -- partition: follower_id
        PK (follower_id, followee_id)
        secondary index / inverted table on (followee_id)  -- needed for fanout
timeline(user_id, created_at DESC, post_id, author_id)     -- partition: user_id
        PK (user_id, created_at, post_id)                  -- the precomputed feed
```

Say out loud, for each table, **which query it serves and whether that query is single-partition**:

- Feed read: `SELECT * FROM timeline WHERE user_id = ? AND created_at < ? LIMIT 20` — single partition, ordered on disk, ~1 seek. This is why `timeline` exists and why it is partitioned by `user_id`.
- Fanout write: needs "who follows X", which is the *reverse* of the `follows` partition key. Hence the inverted table. **Naming the fact that a relationship table needs indexing in both directions is a strong signal**; most candidates write one table and silently assume both lookups are cheap.
- `posts` partitioned by `post_id` because the only access is by id; author-scoped listing is a separate secondary access pattern that you should note and defer.

Then state the sizing, in one line each:

```
post row:    ~16B id + 8B author + 280B text (~3B/char worst case UTF-8) + 8B ts
             ≈ 320B logical, call it 500B with overhead
timeline row: ids + ts only ≈ 40B  ← deliberately narrow: this is the hot table
             250k inserts/s × 40B ≈ 10 MB/s ≈ 850 GB/day of raw timeline writes
             → so timelines MUST be capped (keep newest ~800 entries/user) and TTL'd
```

That derivation, from schema to a cap on the timeline length, is the kind of thing that reads as production experience. The alternative version ("we'd store timelines in Redis") is the same architecture with none of the credit.

**Choose the storage engine here, with a reason tied to the access pattern**, not to fashion:

| Access pattern in this design | Choice | Reason |
|---|---|---|
| Users, posts, follows: relational, needs uniqueness + transactions | Postgres | 500 write QPS is nothing; do not distribute what fits on one primary |
| Timeline: append-heavy, single-partition range scan, capped | Redis sorted set (hot) + Cassandra (cold) | 250k inserts/s is a write-throughput problem, not a query problem |
| Media blobs (out of scope, mentioned) | S3 + CDN | Never put blobs in a row store |

The senior move here is the middle column's second entry: **explicitly say that the relational part fits on one machine.** Candidates reflexively shard everything; the interviewer is often testing whether you know when not to.

### Phase 5 — Architecture, derived (24:00 to 32:00)

Now draw. Every box must be traceable to a line from phases 1 to 4, and you should say the trace as you draw it. Drawing craft, ordering, and edge labelling are the subject of `T10-diagramming`; the *method* rule is one sentence: **draw the happy-path read first, end to end, then the write path, then the async path.**

```
                         ┌────────────┐
   client ──HTTPS/JSON──▶│    CDN     │ static + media only
                         └─────┬──────┘
                               ▼
                         ┌────────────┐   TLS term, authn, 429 rate limit
                         │  API GW /  │   (429 is in the contract, phase 3)
                         │     LB     │
                         └──┬──────┬──┘
              read path     │      │   write path
        ┌───────────────────┘      └────────────────┐
        ▼                                            ▼
  ┌───────────┐  hit ~95%   ┌──────────┐      ┌──────────────┐
  │ Feed Read │────────────▶│  Redis   │      │ Post Service │
  │  Service  │             │ ZSET per │      └──────┬───────┘
  └─────┬─────┘◀── miss ────│  user    │        sync │ append to posts (Postgres)
        │                   └──────────┘             │ then emit event
        ▼ hydrate                                    ▼
  ┌───────────┐                              ┌──────────────┐
  │  posts    │                              │ Kafka  topic │  async boundary
  │ (Postgres │                              │  post.created│  ── dashed = async
  │  + read   │                              └──────┬───────┘
  │  replicas)│                                     ▼
  └───────────┘                              ┌──────────────┐
        ▲                                    │ Fanout Worker│ 250k inserts/s
        └────────── cold timeline ───────────│  (consumer)  │──▶ Redis ZSET
                    (Cassandra)              └──────────────┘    + Cassandra
```

Narrate the derivation as you go: "CDN because media was out of scope but static assets are free to offload. Rate limiter because the contract returns 429. Redis sorted set because phase 4 said the feed read is a single-partition range scan of ~20 narrow rows. Kafka because the follow endpoint returns 202, so fanout is already async by contract. Fanout worker because the amplified write rate from phase 2 is 250k/s and it cannot be on the user's request path."

**Handle the celebrity problem here, not later, and only because a number forced it.** From phase 1's fanout-distribution question: if an account has 50M followers, fanout-on-write inserts 50M rows for one post, which at 40B is 2 GB of writes and minutes of lag. So: **hybrid.** Fanout-on-write for the ~99.9% of accounts below a follower threshold (10k is a reasonable line to state), and fanout-on-read for the rest, merged at query time from a small per-celebrity cache. Say the threshold as a number and say it is tunable.

### Phase 6 — Scale (32:00 to 38:00)

Not "add more servers". Walk the diagram component by component and, for each, name the specific limit and the specific fix. Six components, six sentences.

| Component | Limit it hits first | Number | Fix |
|---|---|---|---|
| API/LB | Connections, TLS handshakes | ~50k conns/node | Horizontal, stateless, DNS/anycast; L4 before L7 |
| Feed read service | CPU on JSON serialisation | ~2-5k rps/core-ish | Horizontal; it is stateless by construction |
| Redis timelines | Memory, then single-thread CPU | 50M users × 800 entries × 40B ≈ 1.6 TB | Cluster-shard by `user_id`; cap list length; TTL inactive users |
| Postgres (posts) | Write IOPS then vacuum | 500 write QPS is fine; 5,000 is not | Read replicas first, then partition by time, shard only if forced |
| Kafka | Partition count = max consumer parallelism | 250k msg/s at ~100B ≈ 25 MB/s, trivial | Partition by `author_id`; over-provision partitions early, they are hard to add |
| Fanout workers | Downstream write throughput, not CPU | 250k inserts/s | Batch the inserts (pipeline 100 per round trip), scale consumers to partitions |

Two rules for this phase. **First, name the bottleneck order.** "In this design the first thing to break under 10× is Redis memory, not the database, because the timeline table is the amplified one." Being able to rank bottlenecks is the difference between mid and senior here. **Second, attach a cost number**, because 2026 rubrics grade it: "1.6 TB of Redis is roughly 25 × r7g.4xlarge equivalents; on-demand that is order $20-25k/month, which is the single biggest line item and the first thing I'd attack, probably by dropping the cap to 200 entries and paging older pages from Cassandra."

### Phase 7 — Failure modes (38:00 to 43:00)

Do not wait to be asked. Kill each component out loud and state (a) what the user sees, (b) what the on-call sees, (c) recovery.

| Kill this | User sees | Operator sees | Design response |
|---|---|---|---|
| Redis shard | Feed loads slow or empty for 1/N users | Cache hit rate drops a step, Cassandra QPS spikes | Fall back to Cassandra read path; serve stale; never fail the request |
| Kafka lag | New posts appear in feeds minutes late | Consumer lag metric climbing linearly | Alert on lag, not on throughput; backpressure the fanout, prioritise recent |
| Fanout worker crash mid-post | Some followers have the post, some don't | Partial fanout; offset not committed | At-least-once + idempotent insert (`ZADD` is naturally idempotent on member) |
| Postgres primary | Writes 503, reads fine | Replication lag → 0 after promotion; a lag window of writes at risk | Sync replica for RPO 0, or accept RPO ≈ replica lag and say the number |
| Whole region | Total outage for that region's users | Health checks failing globally | Active-passive with async replication: state RTO (minutes) and RPO (seconds) |
| Celebrity posts | Fanout queue head-of-line blocks everyone | One partition's lag diverges from the rest | Separate high-fanout topic/priority lane; this is why the hybrid split exists |

Then say the sentence that closes the round strongly: **"The failure I'd actually expect in production is none of those. It's the thundering herd when a Redis shard restarts cold and 2M users all miss at once, which shows up as a Cassandra latency spike and a knock-on timeout cascade in the read service. Mitigation is request coalescing per key plus a jittered warm-up."** A specific, named, non-obvious failure mode with its observable symptom is the single highest-value thing you can volunteer in the last five minutes.

### Phase 8 — Wrap (43:00 to 45:00)

Three sentences, prepared in advance:

1. **What you'd build first.** "Week one: posts table, read-time merge, no fanout at all. It handles the first million users and it's 200 lines."
2. **The biggest risk you're accepting.** "The hybrid fanout threshold is a tuning parameter I've guessed at; I'd instrument the follower distribution before committing to 10k."
3. **What you'd cut.** "If the timeline cost is the problem, drop precomputation for inactive users, which is probably 70% of them."

This maps to the "operability" dimension that separates senior from staff. Skipping rollout, testing, and monitoring caps you below the staff bar ([Exponent, system design guide](https://www.tryexponent.com/blog/system-design-interview-guide) — accessed 2026-07-26).

---

## Build it from scratch

### Full worked example: "Design a notification service. 10M users, email + SMS + push, and it must not double-send."

This is a currently-reported 2026 prompt ([AlgoMaster, notification service](https://algomaster.io/learn/system-design-interviews/design-notification-service) — accessed 2026-07-26). Timings below are what the run actually looks like.

**0:00-2:00 Restate.** "A service other backend services call to deliver a message to a user across email, SMS, and push, with per-user channel preferences, templating, and delivery tracking. Non-goals I'll assume: composing the content, in-app inbox UI, marketing campaign scheduling. I'll be at requirements and numbers by 12, API and schema by 24, then architecture, scale, failure. Redirect me anytime."

**2:00-7:00 Requirements.**

Functional (4, capped): (1) producer services enqueue a notification for a user by template id + params; (2) fan out to the channels that user has enabled; (3) respect user preferences and quiet hours; (4) expose delivery status per notification.
Out of scope, stated: campaign scheduling, A/B testing, in-app inbox, unsubscribe pages.

NFRs, extracted by SCALD-CoM with the answers I got:

| NFR | Answer | Consequence I named |
|---|---|---|
| Scale | 10M users, ~5 notifications/user/day, bursty (a product launch pushes 10M at once) | Burst is 10-50× average, so this is a queue-shaped problem |
| Consistency | Preferences must be respected as of send time, ±seconds is fine | Preferences can be cached with short TTL |
| Availability | 99.9% for enqueue; delivery may lag | Enqueue must never block on a provider |
| Latency | Transactional (OTP, password reset) p99 < 5s end to end; marketing can take 30 min | **Two priority classes. This is the key requirement.** |
| Durability | Never lose a transactional notification. Losing a marketing one is acceptable. | Durable queue + at-least-once for the transactional lane |
| Cost | SMS is the dominant cost | SMS unit economics will decide the design of the retry policy |
| Compliance | Quiet hours, opt-out is legally binding, PII in payloads | Preference check must be non-bypassable, payloads encrypted at rest |

**7:00-12:00 Numbers.**

```
10M users × 5/day = 5×10^7/day ÷ 1×10^5 s ≈ 500 notifications/s average
burst: 10M in one campaign, drained over 30 min (1.8×10^3 s) ≈ 5,500/s  ← sizes the queue
channel fanout ≈ 1.6 channels/notification → ≈ 900 sends/s avg, 9,000/s burst
provider limits (state as unknown-but-real): SMS ~100-500/s per account,
   APNs/FCM effectively unlimited, SES default 14/s until raised
   → SMS is 20-50× below the burst rate. THE bottleneck is the provider, not us.
storage: 5×10^7/day × ~300B status row ≈ 15 GB/day ≈ 5.5 TB/yr before replication
   → 90-day hot retention (1.4 TB) + archive to S3/Parquet. Retention is a requirement,
     not an afterthought.
cost sanity: SMS at ~$0.007/msg. If 10% of 5×10^7/day is SMS: 5×10^6 × $0.007
   = $35k/day ≈ $1M/month. That number alone reshapes the product.
```

That last line is the moment the round is won. The cost estimate reveals that the interesting engineering problem is *not* throughput, it is channel selection and deduplication, because a bug that double-sends SMS costs a million dollars a month. Stating this converts you from "candidate scaling a queue" to "engineer who found the actual risk."

**12:00-17:00 API.**

```
POST /v1/notifications
  headers: Authorization (service token), Idempotency-Key: <uuid, required>
  body: { user_id, template_id, params: {...}, priority: "transactional"|"bulk",
          channels_override?: ["sms"], dedup_key?: string, ttl_seconds?: int }
  → 202 { notification_id }        ← 202, not 201: we accepted, not delivered
  errors: 400, 401, 409 (idempotency replay → returns original notification_id),
          422 (unknown template), 429

GET /v1/notifications/{id}
  → 200 { notification_id, status: "queued"|"sent"|"delivered"|"failed"|"suppressed",
          attempts: [{channel, provider, ts, status, provider_code}] }

PUT /v1/users/{user_id}/preferences
  body: { email: bool, sms: bool, push: bool, quiet_hours: {tz, start, end},
          categories: { marketing: bool, security: true } }   -- security not opt-outable
  → 200

Internal (async) contract:
  topic notifications.transactional  (32 partitions, key = user_id)
  topic notifications.bulk           (128 partitions, key = user_id)
  topic notifications.dlq
  at-least-once delivery; consumers MUST be idempotent on (dedup_key, channel)
```

Points banked: `202` encodes async; `Idempotency-Key` **required** rather than optional, justified by the $1M/month SMS number; `dedup_key` distinct from `Idempotency-Key` (one protects against client retries of the same call, the other against two different callers asking for the same logical notification — say this distinction, it is a real one most candidates miss); `ttl_seconds` because a password-reset SMS delivered 40 minutes late is worse than not delivered; two priority lanes surfaced in the contract, not invented later; `security: true` hardcoded because legally you may not let a user opt out of security alerts.

**17:00-24:00 Data model.**

```
users_prefs(user_id PK, email_enabled, sms_enabled, push_enabled,
            quiet_start, quiet_end, tz, categories JSONB, updated_at)
            -- Postgres. 10M rows × ~200B = 2 GB. Fits in RAM. Do not overthink.

device_tokens(user_id, platform, token, last_seen_at)
            -- PK (user_id, token); prune tokens unused > 90d or rejected by APNs

templates(template_id PK, version, channel, subject_tmpl, body_tmpl, created_at)
            -- versioned and immutable: never mutate a template, publish a new version,
               so a delivery record can be replayed exactly

notifications(notification_id PK, user_id, template_id, template_version,
              priority, dedup_key, created_at, ttl_at, status)
            -- partition by hash(notification_id) for point reads;
               ALSO need "all notifications for user in last 30d" →
               secondary table notifications_by_user(user_id, created_at DESC, notification_id)

attempts(notification_id, channel, attempt_no, provider, provider_msg_id,
         status, provider_code, ts)
            -- PK (notification_id, channel, attempt_no); this is the append-only audit log

dedup(dedup_key, channel, user_id, sent_at)   -- Redis SETNX with TTL = 24h, plus a
            -- durable copy; the TTL must exceed the max retry window or you re-send
```

Say the two load-bearing lines: **"`attempts` is append-only and separate from `notifications` because status is a projection of attempts, and I want the audit trail to be immutable for the compliance requirement."** And: **"the dedup store is the single most important table in this design, because the cost model says a double-send is the expensive failure."**

**24:00-32:00 Architecture.**

```
producer services
      │ POST /v1/notifications  (sync, must return in <50ms)
      ▼
┌──────────────────┐   1. validate template exists
│  Ingest API      │   2. idempotency check (Redis SETNX on Idempotency-Key)
│  (stateless)     │   3. write notifications row  ← durable BEFORE ack
└────────┬─────────┘   4. produce to lane topic
         │                 (transactional outbox: same txn as step 3, or
         ▼                  Kafka-first with the row written by the consumer.
┌─────────────────────────────────┐   Pick one and say why.)
│ Kafka                            │
│  notifications.transactional  32p│ ─── separate lane = no head-of-line blocking
│  notifications.bulk          128p│      from a 10M-user campaign
└───────┬─────────────────────────┘
        ▼
┌──────────────────┐  preference check (Redis cache of users_prefs, TTL 60s,
│ Router / Policy  │  invalidated on PUT) → quiet hours → category opt-out
│    Worker        │  → dedup check (SETNX dedup_key:channel) → channel selection
└───────┬──────────┘  emits one message per selected channel
        ▼
┌─────────────────────────────────────────────┐
│ per-channel queues (separate, because the    │  ← the design's key insight:
│ providers have wildly different rate limits) │     rate limits are per-provider
│   channel.push  · channel.email · channel.sms│
└──┬──────────────┬───────────────────┬───────┘
   ▼              ▼                   ▼
┌────────┐   ┌─────────┐        ┌──────────┐  each: token-bucket rate limiter
│ APNs / │   │  SES /  │        │ Twilio / │  sized to the PROVIDER's limit,
│  FCM   │   │Sendgrid │        │  Sinch   │  + circuit breaker + retry w/ jitter
└───┬────┘   └────┬────┘        └────┬─────┘  + DLQ after N attempts
    └─────────────┴──────────────────┘
                  ▼
      webhook ingest ──▶ attempts table (delivered / bounced / complaint)
                     ──▶ suppression list (hard bounces, complaints) ← non-bypassable
```

Narrate: "Per-channel queues rather than one queue, because the SMS provider caps me at a few hundred per second while push is effectively unlimited; a shared queue means SMS backpressure delays push. Separate transactional and bulk topics because the burst requirement says a 10M campaign would otherwise put a password reset behind 10M marketing messages, and the latency NFR says that reset has a 5-second budget. Suppression list fed by provider webhooks because a hard bounce that you keep retrying gets your sending domain blocked, which is an outage you cannot fix with code."

**32:00-38:00 Scale.** First bottleneck is the SMS provider at ~100-500/s against a 9,000/s burst: the queue absorbs it, so state the drain time (9,000 burst ÷ 300/s ≈ 30 s of backlog per second of burst, so a 10M SMS campaign is *hours*, which means the product requirement "10M in 30 minutes" is impossible over SMS and you should say so). Second is the router worker's preference lookups: 9,000/s against Postgres is fine but wasteful, so cache with a 60s TTL and invalidate on write, and note the 60s staleness window against the "preferences as of send time" requirement (acceptable, because it was specified as ±seconds; if it had been strict, you would need write-through). Third is the `attempts` table write rate: ~1,500 rows/s sustained, 15 GB/day, which is why it is a wide-column store or a partitioned Postgres table with a 90-day retention job, not an unbounded table.

**38:00-43:00 Failure.**

| Kill this | User sees | Operator sees | Response |
|---|---|---|---|
| Twilio 5xx for 10 min | SMS arrive late or on a fallback channel | SMS queue depth climbing, circuit breaker open | Circuit breaker per provider, secondary provider, fall back to push/email for transactional |
| Router worker dies after dedup SETNX but before enqueue | Notification never sent, and dedup blocks a retry | Gap between `notifications` rows and `attempts` rows | **This is the real bug.** Dedup must be committed *with* the enqueue (outbox), or the dedup key must be released on failure, or you accept it and reconcile with a sweeper that finds `queued` rows older than TTL |
| Kafka consumer rebalance storm | Duplicate sends | Repeated offset resets, duplicate `attempts` rows | Idempotent consumer keyed on `(notification_id, channel)`; `INSERT ... ON CONFLICT DO NOTHING` and check affected rows |
| Preference cache serves stale `sms_enabled=true` after opt-out | User gets an SMS after opting out | Nothing, until a complaint | Legally serious: opt-out writes bypass the cache (write-through + immediate invalidate), and the final send-time check reads the durable suppression list |
| Template bug renders empty body | 10M blank emails | Bounce/complaint rate spike | Canary the first 1,000 sends of any campaign and require a manual promote; this is a rollout control, not a code fix |

Then the volunteered one: **"The failure I'd expect is a retry storm interacting with the dedup TTL. If the dedup TTL is 24 hours but a DLQ replay happens 26 hours later, every message re-sends and you pay for 5M duplicate SMS. So the TTL has to be greater than the maximum possible replay window, and the DLQ replay tool has to be idempotent independently of the TTL. That is a runbook bug, and it is the kind that costs money rather than uptime."**

**43:00-45:00 Wrap.** "Build first: ingest API, Postgres, one worker, push only, no bulk lane. Two weeks, handles 500/s. Biggest accepted risk: the outbox-vs-Kafka-first choice at ingest, which I'd resolve by measuring whether producers can tolerate the extra 5ms of a transactional outbox write. First thing I'd cut under cost pressure: SMS as a default channel, given the $1M/month figure."

---

## How it's done in production

The method is a compressed version of how architecture actually gets done, and the analogy is worth stating in the round because it makes you sound like someone who has shipped:

| Interview phase | Real-world equivalent | What is compressed |
|---|---|---|
| Requirements + NFRs | PRD + SLO definition | Weeks of product negotiation → 5 minutes |
| Constraints/numbers | Capacity plan, cost model | Load tests and billing data → arithmetic |
| API contract | RFC / design doc / OpenAPI spec review | Days of review → 5 minutes |
| Data model | Schema review, migration plan | Migration risk → a `CREATE TABLE` sketch |
| Architecture | ADR (architecture decision record) | Alternatives-considered section → said out loud |
| Scale | Load test + bottleneck analysis | Real profiling → Little's Law |
| Failure | Failure mode analysis, game day, runbook | Chaos experiments → a table |
| Wrap | Rollout plan, phased delivery | Quarters of roadmap → three sentences |

**Company variation, and how to adapt without abandoning the method** ([Exponent Meta guide](https://www.tryexponent.com/blog/meta-system-design-interview), [Exponent Google guide](https://www.tryexponent.com/blog/google-system-design-interview), [DesignGurus by-company breakdown](https://designgurus.substack.com/p/faang-system-design-interviews-by) — all accessed 2026-07-26):

| Company style | Emphasis | Method adjustment |
|---|---|---|
| Meta | 45 min, breadth then interviewer-steered depth; product-flavoured prompts | Keep phases 1-5 tight, protect 15 minutes for the steered deep dive |
| Google | Will ask you to *implement* what you name | Name fewer components; be ready to build the queue/limiter you mention |
| Amazon | Operational excellence, ownership, cost; LP probing interleaved | Expand phase 7 and phase 8; have monitoring/oncall specifics ready |
| Stripe | API design and data model scored hardest; correctness and idempotency | Expand phase 3 to 8 minutes; money means exactly-once semantics discussion |
| Uber/Lyft-style | Geospatial, real-time matching, ML in the path | Phase 4 gains a geo-index decision (S2/H3/geohash); state cell size |
| AI-infra prompts (2026) | Token cost, non-determinism, eval, prompt-injection blast radius | Add three NFR rows: token budget, eval/regression, agent action scope |

### What breaks at scale (in the interview, not the system)

| Symptom | Cause | Fix |
|---|---|---|
| Minute 30 and you're still on requirements | Asking questions without a checklist or a cap | SCALD-CoM, 6 questions max, then assume out loud and move |
| Interviewer keeps interrupting to redirect | You're narrating breadth they don't care about | Ask at minute 2 what they want deep; announce transitions so they can steer cheaply |
| You draw a component and can't justify it | Recalled architecture, not derived | Every box must trace to a phase 1-4 line; say the trace aloud |
| Runs out of time before failure modes | High-level architecture expanded past 8 minutes | Hard-stop phase 5; you can always come back |
| "How would you scale this?" and you say "add servers" | No per-component limit analysis | Table of component → first limit → number → fix |
| Follow-ups keep landing on things you hand-waved | You said "cache" / "queue" / "shard" without parameters | Every named component gets one number: size, TTL, partition count, key |
| Design is technically fine, feedback says "not staff level" | No cost, no rollout, no monitoring, no risk statement | Phase 8 exists for exactly this |
| Contradicting yourself in the deep dive | Requirements weren't written down and referred back to | Keep the NFR table visible; cite it by name |

---

## Tradeoffs & when NOT to use it

**The procedure is a default, not a law, and applying it rigidly is its own failure mode.**

- **The interviewer has an agenda: follow it.** If they say "assume the requirements, I want to talk about the storage layer", running phases 1 and 2 anyway is not thoroughness, it is not listening. Compress to 90 seconds ("then I'll assume 10M DAU, read-heavy, 99.9%") and jump to phase 4.
- **Product/architecture-lite rounds punish it.** Some rounds (front-end system design, "design the developer experience for X", platform strategy rounds) are about component decomposition, API ergonomics, and migration paths, with no QPS anywhere. Spending 5 minutes on capacity estimation there signals you pattern-matched the round type wrong.
- **ML/AI system design rounds need a different phase 2 and 4.** The numbers that matter are training data volume, feature freshness, model latency budget, tokens per request, and cost per thousand requests; the "data model" phase becomes feature store and index design. The skeleton survives, the contents change. If the prompt is "design a vector search service for RAG", phase 4 is index type, dimension, and recall target, not `CREATE TABLE`.
- **Deep-dive rounds ("here is our architecture, find the problem") invert it.** You are doing phase 6 and 7 only, on someone else's phase 5. Do not try to re-derive requirements they already have.
- **Estimation can be a trap when the interviewer has said it does not matter.** Some interviewers explicitly consider capacity arithmetic performative. The safe form is to compute only what you will use and to say what each number decides, so the arithmetic is visibly instrumental.
- **The method does not substitute for knowing things.** It gets you to the right question 10 minutes earlier; it does not answer "what happens to your Cassandra read latency when a tombstone-heavy partition is scanned". Process gets you to a passing bar. Depth gets you the offer at staff and above.
- **Over-narrating the framework itself is a smell.** Saying "now I will enter the non-functional requirements phase" three times sounds like you learned a script. Say the transitions in engineering language ("read path is bounded, moving to writes"), not in process language.

---

## Interview questions

### Q1 — "Design Twitter." Go.
**Testing:** whether you start with boxes. This is a filter, not a question.
**Answer:** Restate and constrain first. "Home timeline, not search or DMs. Post text, follow users, read a merged reverse-chronological feed. Before I design: what's the read:write ratio, is the feed chronological or ranked, and do we have accounts with tens of millions of followers?" Then the NFR table, then numbers, then API, then schema, then boxes. Reach the architecture at roughly minute 24 with every component justified.
**Follow-up trap:** *"We don't have time for all that, just draw the architecture."* Do not abandon the derivation, compress it: "Then I'll assume 50M DAU, 100:1 read:write, chronological, and yes to celebrity accounts, which means hybrid fanout. Here's the diagram, and I'll flag where those assumptions are load-bearing." Compressing while keeping the assumptions explicit scores; dropping them does not.

### Q2 — What's the difference between a functional and a non-functional requirement, and which matters more here?
**Testing:** whether the distinction is operational for you or vocabulary.
**Answer:** Functional requirements are user-visible verbs and they determine the API surface. Non-functional requirements are the quantified properties (scale, consistency, availability, latency, durability, cost, compliance) and they determine the architecture. Functional requirements are usually easy and mostly given; non-functional ones are usually withheld and are where the design decisions live. Two systems with identical functional requirements and different consistency requirements are different systems.
**Follow-up trap:** *"Give me a case where a non-functional requirement invalidates an entire architecture."* Data residency. A design with a single global primary and read replicas is fine until "EU user data must not leave the EU", at which point you need per-region primaries, which means either partition-by-region routing at the edge or multi-primary with conflict resolution, which changes every other decision. Compliance NFRs are the ones that delete architectures rather than tune them.

### Q3 — Why write the API before drawing the architecture?
**Testing:** whether you understand the derivation chain or just memorised the order.
**Answer:** Because the API is falsifiable and the architecture is not. A signature commits to the payload size, the read/write ratio, the pagination model, and the sync/async boundary. Once `POST /follows` returns `202`, the async fanout is already implied and the queue in the diagram is justified by the contract instead of being an unexplained box. It also flushes out the requirements you missed: you cannot write the feed endpoint without deciding cursor versus offset, and you cannot write the post endpoint without deciding idempotency.
**Follow-up trap:** *"Isn't that backwards? Real teams design the system, then the API."* No, and this is worth pushing back on: real teams write the RFC and the interface contract first precisely because it is the cheapest artefact to change. The implementation follows the contract; changing a shipped public API is the expensive direction. If they persist, concede the narrow case: for an internal batch pipeline with no external consumers, the data model genuinely does come first.

### Q4 — I'll give you no numbers at all. Now what?
**Testing:** whether you freeze when the interviewer withholds.
**Answer:** State assumptions with their consequences and mark them as revisitable. "I'll assume 10M DAU and 100:1 read:write. That makes this cache-shaped: the read path gets precomputation and the write path stays simple. If it's actually 2:1, precomputation stops paying and I'd move to read-time merge." Then design against the assumption. The assumption is not the risk; an *unmarked* assumption is.
**Follow-up trap:** *"Your assumption is wrong, it's 2:1."* Take the branch you already named, out loud, without restarting: "Then the timeline precomputation is the wrong call, because I'd be doing 250k inserts/s to serve a read rate only twice as high. I'd drop the fanout entirely, index posts by `(author_id, created_at)`, and merge at read time across the follow set with a per-author limit. The cache becomes a query-result cache with a short TTL rather than a materialised timeline." Recovering by walking a pre-named branch is worth more than getting it right first time.

### Q5 — How do you allocate 45 minutes?
**Testing:** time management, which is directly graded.
**Answer:** Roughly 2 restate, 5 requirements, 5 numbers, 5 API, 7 data model, 8 architecture, 6 scale, 5 failure, 2 wrap. The hard constraint is that the architecture must be on the board by minute 32, because the last 10 to 15 minutes are where senior candidates differentiate on scale, failure, and operations. Announce the plan at minute 2 so the interviewer can redirect cheaply.
**Follow-up trap:** *"You're at minute 35 and haven't finished the high-level design. What do you drop?"* Drop breadth in the architecture, not the last two phases. Declare one component as "assume standard" (auth, CDN, object storage), get a coherent end-to-end read path on the board even if the write path is a single box, and spend the remaining time on the bottleneck and one failure mode. A complete narrow design that is scaled and broken beats a broad design that is neither.

### Q6 — Walk me through how you'd turn "it should be fast" into something designable.
**Testing:** vague-to-numeric conversion, which is most of phase 1.
**Answer:** Decompose into three questions: fast for *whom* (which endpoint), at which *percentile*, and under what *load*. "Fast" becomes "p99 of `GET /feed` under 200ms at 15k peak QPS, measured server-side at the API gateway". Then check it against physics before designing: 200ms is fine for one intra-region round trip plus a cache hit (~1-2ms) but not for three sequential cross-region calls at ~150ms each. If the requirement and the topology conflict, say so immediately, because that is a design-invalidating finding, not a tuning problem.
**Follow-up trap:** *"Why p99 and not average?"* Because averages hide the failure the user actually experiences, and because at fanout the tail dominates: if a request touches 100 shards and each has a 1% chance of exceeding p99, the probability that the slowest component determines your response is roughly 1 - 0.99¹⁰⁰ ≈ 63%. That is why tail latency is the number that matters in a fanout architecture, and why hedged requests exist.

### Q7 — You've drawn a cache. I'm going to ask you five things about it.
**Testing:** whether named components carry parameters.
**Answer:** Pre-empt all five when you draw it: what's the key (`timeline:{user_id}`), what's the value and size (sorted set, capped at 800 entries × 40B ≈ 32KB), what's the TTL and eviction (7-day TTL for inactive users, `allkeys-lru` within a memory cap), what's the invalidation (write-through on fanout; delete-on-unfollow), and what's the hit rate you're assuming (95%, and the design must survive 0% during a cold restart). A cache with no stated hit rate is not a design decision, it is a wish.
**Follow-up trap:** *"The cache is cold after a restart. What happens?"* Thundering herd: every request misses simultaneously, the origin sees the full unmitigated read rate, latency spikes, timeouts trigger retries, and the retries amplify. Mitigation is request coalescing (single-flight per key so N concurrent misses become one origin read), jittered TTLs so keys do not expire in lockstep, and a warm-up that populates the top-K active users before taking traffic. Say "single-flight" explicitly.

### Q8 — What do you do when you realise at minute 30 that your data model is wrong?
**Testing:** whether you can revise without collapsing. Interviewers create this situation deliberately.
**Answer:** Say it plainly, name the specific consequence, and state the minimal fix. "The `follows` table is partitioned by `follower_id`, which serves 'who do I follow' but makes the fanout query 'who follows X' a scatter-gather across every partition. That's the wrong shape for the write path. Minimal fix is an inverted table keyed by `followee_id`, which doubles the write cost on follow (two writes, and now I need them to be consistent, so either a transaction or accept eventual convergence with a repair job). I'd take that trade because follows are rare and fanout is constant."
**Follow-up trap:** *"Doesn't finding that at minute 30 mean you should have caught it at minute 20?"* Yes, and the honest answer is that the check you skipped is "for each table, list every query that touches it and confirm each is single-partition." Naming the missing *check*, rather than apologising, converts the mistake into evidence of a method. Interviewers weight recovery heavily; a candidate who never errs and a candidate who errs and self-corrects with a rule score similarly, and both beat one who defends a broken schema.

### Q9 — Your design has six components. Which one breaks first at 10× traffic, and why that one?
**Testing:** bottleneck ranking. This is a staff-level discriminator.
**Answer:** Name it, quantify it, and explain why it beats the runners-up. "Redis memory. At 50M users × 800 entries × 40B I'm at ~1.6 TB, so 10× users is 16 TB, and memory is the constraint that scales linearly with users rather than with traffic. Postgres is second but further away: 500 write QPS to 5,000 is survivable on one primary with a faster disk. The stateless tiers don't break, they just cost more. So the ordering is memory-bound state first, single-writer state second, stateless last."
**Follow-up trap:** *"Fix Redis without adding memory."* Three levers, in increasing pain: cut the cap (800 to 200 entries covers the first 10 pages and pages the rest from Cassandra, a 4× reduction for a small p99 regression on deep scrolls); stop precomputing for inactive users (likely 60-70% of the base, so precompute lazily on their first read and accept a slower first load); and compress the entry (40B to ~16B by storing a packed `(post_id, ts)` and dropping `author_id`, which you re-hydrate anyway). Notice all three trade latency or complexity for memory rather than adding hardware, which is the point of the question.

### Q10 — What's the cost of this system per month?
**Testing:** the 2026 addition. Interviewers now grade cost.
**Answer:** Give a structured order-of-magnitude with the dominant line item named, not a precise total. "Redis at 1.6 TB is the dominant line, order $20-25k/month. Cassandra for cold timelines at ~100 TB with 3× replication is order $10-15k/month in storage plus instances. Stateless compute for 15k QPS at ~2k rps/node is maybe 15-20 nodes, low thousands. Egress is often the surprise: 15k QPS × 6 KB is ~90 MB/s ≈ 230 TB/month, which at ~$0.05-0.09/GB is $12-20k, comparable to the database. So: order $60-80k/month, dominated by Redis and egress, and the first optimisation is the timeline cap because it hits the biggest line."
**Follow-up trap:** *"Which of those numbers are you least confident in?"* Egress, because it depends on payload size and CDN offload ratio, both of which I guessed, and it is the line item most likely to be wrong by 3×. Naming your own weakest estimate is a strong signal; claiming uniform confidence in a back-of-envelope cost model is not.

### Q11 — When would you deliberately NOT follow this procedure?
**Testing:** whether the method is a tool or a script.
**Answer:** When the interviewer names the area they want (follow them, compress the rest to stated assumptions); when the round has no scale dimension (front-end design, developer-experience, migration strategy) so capacity arithmetic is noise; when you are handed an existing architecture to critique, which is phases 6 and 7 only; and when the prompt is ML-shaped, where phase 2 becomes token/latency/cost budgets and phase 4 becomes feature store and index design. The invariant that survives all four is "derive before you draw"; the specific phase list does not.
**Follow-up trap:** *"So the framework is optional?"* The ordering constraint is not optional, the phase budget is. You may compress or skip a phase, but you may not draw a component before you can say which requirement or number produced it. That is the property being scored, and everything else is scaffolding to make it habitual under stress.

### Q12 — Design a recommendation feed with an LLM-generated summary at the top.
**Testing:** the 2026 hybrid prompt. Whether the method transfers to a stack where cost and non-determinism are first-class.
**Answer:** Same skeleton, three added NFR rows. Scale/latency: the LLM call is 500-2000ms p99, so it cannot be synchronous inside a 200ms feed budget — the summary is generated asynchronously and cached per (user, feed-version), with the feed rendering without it and filling in progressively. Cost: at 10M DAU × 1 summary/day, 2k input tokens and 200 output tokens at Claude-Sonnet-class pricing of roughly $2/M input and $10/M output ([TLDL LLM pricing, July 2026](https://www.tldl.io/resources/llm-api-pricing) — accessed 2026-07-26) is 10M × (2000×$2 + 200×$10)/10⁶ = 10M × $0.006 = **$60k/day**, which is immediately unaffordable, so the design must cache aggressively, generate only for engaged users, batch through the Batch API at a 50% discount, or use a small model. Eval/non-determinism: you need a regression suite and an online quality metric because the output is not deterministic, plus a deterministic fallback (extractive summary) when the model or budget fails.
**Follow-up trap:** *"Cut that $60k/day by 100×."* Generate summaries only on demand at first open rather than for all DAU (removes the 40-70% who never scroll), cache per feed-version with an hour-scale TTL so re-opens are free, degrade to a cheap model tier at roughly a 20× lower unit cost for non-premium users, and truncate the input context from 2k to 500 tokens by summarising item titles only. Those compose to roughly 100×. The senior framing is that the LLM is a **budgeted resource**, so there must be a per-user and per-day token cap enforced in code, not a hope.

### Q13 — How do you know when you're done with the requirements phase?
**Testing:** whether you have a stopping rule, since the phase has no natural end.
**Answer:** Three tests. (1) You can name the read path and the write path and say which is the hard one. (2) Every NFR row has either an answer or an explicitly stated assumption. (3) You know which number you are about to compute and what it will decide. If all three hold, stop, even if you have more questions. If you cannot state which number comes next, you are collecting requirements for their own sake.
**Follow-up trap:** *"You missed a requirement and it surfaces at minute 35."* Handle it as a scoped amendment rather than a restart: name which decision it invalidates, state the smallest change that accommodates it, and say what it costs. "Multi-region residency changes the routing layer and forces per-region primaries; the timeline design survives because it's already partitioned by `user_id`, so the change is a region field in the partition key and edge routing on it. Cost is losing cross-region follows without an async replication path." Scoped amendment beats restart, always.

### Q14 — Two candidates produce the same final diagram. One passes, one fails. What separates them?
**Testing:** whether you have internalised that the process is the score.
**Answer:** The order of derivation and the traceability of decisions. The passing candidate's timeline table exists because the read path was quantified at 15k QPS with a single-partition access pattern; the failing candidate's exists because they remembered that Twitter has one. Under mutation the difference becomes visible: change the follower distribution or the read:write ratio and the first candidate adjusts one decision while the second has no derivation to adjust, so they either defend the recalled answer or start over. Interviewers mutate the prompt specifically to find this out.
**Follow-up trap:** *"So a candidate with the wrong architecture but a good process passes?"* Not automatically, but often, yes: a defensible derivation with a suboptimal conclusion is a hire signal for anything below principal, because process transfers to novel problems and a memorised answer does not. It stops being sufficient at principal level, where you are also expected to reach the good conclusion, and where "I'd measure the follower distribution before choosing" has to be followed by "and here is what I'd expect to find, and here is the design for each case."

### Q15 — What's the single highest-value sentence you can say in a 45-minute round?
**Testing:** judgement about signal density.
**Answer:** A named, non-obvious failure mode with its observable symptom, volunteered rather than extracted. "The failure I'd actually expect here is a cold-cache thundering herd after a Redis restart, which shows up as a Cassandra p99 spike and a timeout cascade in the read tier, and the mitigation is single-flight coalescing plus a jittered warm-up." It demonstrates production experience, ownership of the failure surface, and knowledge of what an operator sees, all in one sentence, and almost no candidates volunteer it.
**Follow-up trap:** *"Give me a second one."* A cost-driven design change: "$1M/month of SMS means the expensive failure is a double-send, not downtime, so the dedup store is the most important component in the diagram." Any sentence that reprioritises the architecture on the basis of a number you computed is high-signal, because it proves the arithmetic in phase 2 was load-bearing rather than performative.

### Q16 — You finish the design with 8 minutes left. What do you do?
**Testing:** whether you can use surplus time or waste it.
**Answer:** Do not add components. In order: (1) volunteer a failure mode and its mitigation; (2) give the cost breakdown and name the dominant line item; (3) state the migration or rollout plan, since "how do you ship this to an existing system with live traffic" is a staff question with a real answer (dual-write, shadow read, compare, cut over, keep the rollback path); (4) name the one thing you would measure first in production and the alert you would set. Then ask what they would like to go deeper on.
**Follow-up trap:** *"Nothing more? Then let's talk about the thing you skipped."* Expect this, and know your own skips. Have one prepared answer for each thing you explicitly deferred (auth, media, search, moderation), even a shallow one, so a deferral does not read as a gap. Saying "I deferred moderation; the shape is an async classifier on the write path with a human review queue and a shadow-ban state on the post row" turns a skip into a demonstration of scope control.

---

## Red flags that fail you

- Drawing boxes in the first three minutes.
- Asking "how many users" and then never using the answer.
- Reciting a memorised architecture that does not respond to the prompt's specific mutation.
- Presenting non-functional requirements as adjectives: "highly available, scalable, fast", with no numbers.
- Naming a cache, queue, or shard with no key, size, TTL, or partition count.
- Reaching minute 40 without having discussed a single failure mode.
- Answering "how would you scale this" with "add more servers" or "use Kubernetes".
- Sharding a database that would comfortably fit on one primary, and not noticing.
- Offset pagination on an insert-heavy list.
- No idempotency story on a write endpoint that a client can retry.
- Defending a broken schema instead of naming the check you skipped.
- Zero mention of cost in 2026.
- Narrating the framework by name instead of narrating the engineering.

## Cheat card

```
TIME BUDGET (45 min):
  0-2   restate + scope contract + "anywhere you want me deep?"
  2-7   requirements: 3-5 FRs (cap it), NFR table, say what's OUT of scope
  7-12  numbers: 3 you will USE, say what each decides, peak = avg x 3
  12-17 API: 3-6 signatures, /v1/, Idempotency-Key, cursor not offset, 202 = async
  17-24 data model: tables + PARTITION KEY + row bytes + "is this query 1-partition?"
  24-32 architecture: read path first, then write, then async. Every box traces up.
  32-38 scale: per-component first-limit + number + fix; RANK the bottlenecks
  38-43 failure: kill each box; user sees / operator sees / recovery
  43-45 wrap: build-first, biggest risk, what you'd cut

NFR CHECKLIST = SCALD-CoM
  Scale · Consistency · Availability · Latency · Durability · Cost · Multi-tenancy

GOOD CLARIFYING QUESTION = names 2 alternatives + says they lead to different designs
  read:write ratio? · fanout distribution (celebrity accounts)? · chronological or ranked?
  retention? · real-time push or pull? · global/residency? · SLO + p99 target?

HARD RULES
  no box before a requirement or number that produced it
  every named component gets ONE number (size / TTL / partitions / key)
  interviewer scores the PROCESS; mutation-resistance is the thing being tested
  blocked question -> state assumption + its consequence + move on
  wrong assumption at min 30 -> walk the branch you already named, do NOT restart
  architecture on the board by minute 32, no exceptions

2026 ADDITIONS
  cost is graded: name the dominant line item + a number
  LLM in the loop: token budget NFR, async + cached, deterministic fallback, eval suite
  half of loops now have an ML-adjacent prompt

HIGHEST-VALUE VOLUNTEERED SENTENCE
  named failure mode + observable symptom + mitigation
  e.g. cold-cache thundering herd -> Cassandra p99 spike -> single-flight + jittered warm-up
```

## Sources

- [System Design Interviews Changed in 2026. Here's the New Playbook. — DesignGurus](https://designgurus.substack.com/p/system-design-interviews-changed) — accessed 2026-07-26
- [How to Prepare for System Design Interviews in 2026 — DesignGurus](https://designgurus.substack.com/p/the-complete-system-design-interview) — accessed 2026-07-26
- [System Design Interview Expectations by Company and Level — DesignGurus](https://designgurus.substack.com/p/faang-system-design-interviews-by) — accessed 2026-07-26
- [Rubric for System Design Interviews — Exponent](https://www.tryexponent.com/courses/system-design-interviews/system-design-interview-rubric) — accessed 2026-07-26
- [Meta System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/meta-system-design-interview) — accessed 2026-07-26
- [What to Expect in Google's System Design Interview (2026) — Exponent](https://www.tryexponent.com/blog/google-system-design-interview) — accessed 2026-07-26
- [Stripe System Design Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/stripe-system-design-interview) — accessed 2026-07-26
- [System Design Interview Questions for Senior Engineers 2026 — KORE1](https://www.kore1.com/system-design-interview-questions/) — accessed 2026-07-26
- [System Design Interview Rubric: What's Actually Graded — Beyz AI](https://beyz.ai/blog/system-design-interview-rubric-whats-actually-graded) — accessed 2026-07-26
- [Design Notification Service — AlgoMaster.io](https://algomaster.io/learn/system-design-interviews/design-notification-service) — accessed 2026-07-26
- [LLM API Pricing (July 2026) — TLDL](https://www.tldl.io/resources/llm-api-pricing) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
