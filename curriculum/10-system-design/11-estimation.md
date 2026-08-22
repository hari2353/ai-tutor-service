# Back-of-Envelope: Guesstimates, Latency/Throughput/Storage Math

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** `T10-design-method` · **Updated:** 2026-07-26
> **Module id:** `T10-estimation` · **Tags:** sprint, craft, critical

## The 30-second version

Back-of-envelope estimation is a four-step procedure, not a talent: state the assumption out loud, round every input to a power of ten, compute in one pass, then sanity-check the answer against a system whose scale is public. You need about fifteen numbers memorised (the latency ladder, seconds per day ≈ 10⁵, bytes per typical row, throughput per typical node) and one habit, which is announcing what each number is going to *decide* before you compute it. The point is never precision; an answer within one order of magnitude is a pass and an answer within 3× is indistinguishable from correct, because the decision it feeds (one Postgres primary or a sharded cluster, one cache node or twenty) only ever has a handful of discrete outcomes. The two things interviewers actually watch for are whether your peak number is derived from your average number rather than guessed, and whether you catch and recover from your own bad assumption mid-answer instead of defending it.

## Why this gets asked

Because the interviewer has approved a design whose author had never multiplied anything. The specific memory is usually one of two shapes: a service that was sharded from day one to handle a load a single machine would have absorbed, costing a year of complexity for nothing, or a service that shipped with a cache sized for the average and fell over on the first Monday-morning peak. Both are arithmetic failures dressed as architecture failures. So the round tests whether numbers are load-bearing in your reasoning or decorative. And in 2026 there is a second reason: interviewers now grade cost ([DesignGurus 2026 playbook](https://designgurus.substack.com/p/system-design-interviews-changed) — accessed 2026-07-26), and cost is pure back-of-envelope work. A candidate who cannot produce "$60k/month, dominated by egress" cannot participate in the conversation that senior engineers actually have.

---

## Lineage: past → present → future

**What came before.** The canonical artefact is Jeff Dean's "Numbers Everyone Should Know" slide from his 2009 LADIS/Stanford talks, later reproduced everywhere as Jonas Bonér's gist ([Latency Numbers Every Programmer Should Know](https://gist.github.com/jboner/2841832) — accessed 2026-07-26). Before it, capacity planning was a spreadsheet activity owned by a separate operations team, and application engineers routinely did not know that a disk seek was five orders of magnitude slower than an L1 hit. The specific pain that made this untenable was the mid-2000s shift to horizontally-scaled services: once a request fanned out to a hundred machines, the tail dominated the mean, and an engineer who could not reason about the ratios could not reason about the latency of their own endpoint at all. Dean's table made the ratios memorable, and Google's internal practice of requiring a written estimate before a design review made estimation a first-class engineering skill rather than an ops handoff.

**Where it stands now.** The absolute numbers in the 2009 table are badly out of date and quoting them verbatim is a mild negative signal. Two entries changed by orders of magnitude. NVMe collapsed the storage gap: a random read is now roughly 20 to 100 µs rather than the 150 µs the old table gave for SSD and nowhere near the 10 ms of a spinning seek ([simplyblock, NVMe latency](https://simplyblock.io/glossary/nvme-latency/) — accessed 2026-07-26). And datacenter networking got fast enough that a round trip across a 100 GbE fabric is now cheaper than reading a megabyte from disk, which inverts a comparison a whole generation of engineers internalised the other way round ([Latency Numbers You Should Know in 2026](https://omarish.com/latency-numbers-you-should-know) — accessed 2026-07-26). What has *not* changed, and what you should actually memorise, is the ratio structure: RAM is ~1000× faster than SSD, a same-datacenter round trip is ~1000× slower than RAM, and a cross-continent round trip is ~100-300× a same-datacenter one. Speed of light in fibre is the one number nobody can optimise.

The live disagreement is about how much estimation belongs in a 45-minute interview at all. One camp treats capacity numbers as the only thing that distinguishes a design from a drawing. The other treats five minutes of unused arithmetic as theatre, and some interviewers now explicitly say "assume it's large, skip the math". Both camps agree on the resolution in practice: compute only the numbers you are about to use, and say what each will decide. Instrumental arithmetic reads as engineering; ritual arithmetic reads as a memorised script.

**Where it's heading.** High confidence: **cost estimation becomes as standard as QPS estimation**, because cloud unit economics are public and because the 2026 rubrics grade it. The numbers you need to hold are shifting accordingly, toward $/GB-month of storage, $/GB of egress, $/M tokens, and $/GPU-hour. Medium confidence: **token and GPU arithmetic joins the core set**, since roughly half of design loops now include an ML-adjacent prompt and the dominant constraint in those designs is almost always cost per request rather than QPS. Speculative: as rounds move to shared text editors and canvases, expect interviewers to tolerate (or even hand you) a calculator, which shifts the score entirely onto *which* quantities you chose to compute and whether you sanity-checked them. That would be a good change, since the mental arithmetic was never the skill being tested.

---

## Mental model

Estimation is a funnel with a feedback loop, and the loop is the part candidates skip.

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │ 1. DECLARE      "I want peak write QPS, because it decides whether  │
  │                  one Postgres primary can take the write path."     │
  │                       ↓  (name the DECISION first)                  │
  │ 2. ASSUME       "50M DAU, 1 post/user/day. Marking that; if it's    │
  │                  10x I'll revisit."                                 │
  │                       ↓  (say it, don't think it)                   │
  │ 3. ROUND        86,400 s/day → 1e5.   50M → 5e7.   500 followers    │
  │                  → 5e2.  "I care about the exponent."               │
  │                       ↓                                             │
  │ 4. COMPUTE      5e7 / 1e5 = 5e2 = 500 writes/s avg                  │
  │                  × 3 peak  = 1.5e3 = 1,500 writes/s peak            │
  │                       ↓                                             │
  │ 5. SANITY       "1,500 write QPS is ~1 Postgres primary on NVMe,    │
  │    CHECK         not a distributed systems problem." ← compare to   │
  │                  something whose scale you KNOW                     │
  │                       ↓                                             │
  │ 6. USE IT       "So: single primary, read replicas. No sharding."   │
  │                       ↓                                             │
  │ 7. IF THE SANITY CHECK FAILED ──────────┐                           │
  │      → the assumption in step 2 is      │                           │
  │        wrong, not the arithmetic.       │                           │
  │        Go back to 2. Say so out loud. ──┘                           │
  └─────────────────────────────────────────────────────────────────────┘
```

**The single most common failure is skipping step 5**, producing "8 million QPS" for a product with 10M users, and building an architecture on it. The second most common is skipping step 1, producing four correct numbers that decide nothing.

Two framing rules that make the arithmetic tractable in your head:

```
  seconds per day  = 86,400  →  ROUND TO 1e5    (14% error, always in your favour:
                                                 it under-reports QPS slightly)
  1 million/day    = ~10 per second             ← memorise this single conversion
  1 billion/day    = ~10,000 per second           and most QPS math is one step

  powers:   2^10 = 1e3 (KB)   2^20 = 1e6 (MB)   2^30 = 1e9 (GB)
            2^40 = 1e12 (TB)  2^50 = 1e15 (PB)  2^60 = 1e18 (EB)
```

---

## How it actually works

### The numbers to know cold

**Latency ladder (2026 values).** Memorise the ratios; the absolute values are for sanity-checking.

| Operation | Latency | Ratio vs L1 | What it means for design |
|---|---|---|---|
| L1 cache reference | ~1 ns | 1× | Free. Never in your budget. |
| L2 cache reference | ~4 ns | 4× | Free. |
| L3 / LLC reference | ~10-15 ns | ~12× | Cross-core sharing costs this. |
| Branch mispredict | ~3-5 ns | ~4× | Only matters in tight loops. |
| Mutex lock/unlock (uncontended) | ~20 ns | 20× | Contended is 1000× worse. |
| Main memory (DDR5) reference | ~50-80 ns | ~65× | **The unit of "in RAM is free".** |
| Compress 1 KB (snappy/lz4) | ~1-3 µs | ~2,000× | Cheaper than the network. Always compress over the wire. |
| Read 1 MB sequentially from RAM | ~30-50 µs | ~40,000× | ≈ 20-30 GB/s memory bandwidth |
| **NVMe SSD random read (4 KB)** | **~20-100 µs** | ~50,000× | 3 orders better than 2009's SSD numbers |
| SATA SSD random read | ~100-200 µs | ~150,000× | Legacy; still in older fleets |
| **Same-datacenter round trip** | **~0.5 ms** (0.2-1 ms) | ~500,000× | **The unit of "one network hop"** |
| Read 1 MB sequentially from NVMe | ~200-500 µs | | ≈ 2-7 GB/s Gen4/Gen5 |
| Cross-AZ round trip | ~1-2 ms | ~1e6× | Sync replication across AZs costs this per write |
| HDD seek | ~5-10 ms | ~7e6× | Archive tier only |
| US East ↔ US West round trip | ~60-70 ms | ~6e7× | ~4,000 km at ~200,000 km/s in fibre, ×1.5 routing |
| US East ↔ Europe round trip | ~75-90 ms | | |
| US ↔ Singapore / Sydney round trip | ~170-230 ms | ~2e8× | **Three of these do not fit in any user-facing budget** |
| LLM first token (frontier model) | ~300-800 ms | ~5e8× | This is 1000 same-DC round trips. Never synchronous in a fast path. |

Sources: [Latency Numbers You Should Know in 2026](https://omarish.com/latency-numbers-you-should-know), [Azure network round-trip latency statistics](https://learn.microsoft.com/en-us/azure/networking/azure-network-latency), [simplyblock NVMe latency](https://simplyblock.io/glossary/nvme-latency/) — all accessed 2026-07-26.

**The three sentences to have ready:**
- "RAM is about a thousand times faster than SSD, and a same-datacenter round trip is about a thousand times slower than RAM."
- "A cross-continent round trip is 100 to 300 times a same-datacenter one, so a design with three sequential cross-region calls inside a 200 ms budget is dead on arrival."
- "Speed of light in fibre is ~200,000 km/s, so ~5 µs per km, so ~1 ms per 100 km one-way after routing overhead. That number is not negotiable by any amount of engineering."

**Throughput ladder.**

| Resource | Throughput | Derived limit |
|---|---|---|
| Memory bandwidth | 20-50 GB/s per socket | Rarely your bottleneck |
| NVMe Gen4 sequential | 3-7 GB/s; 500k-1M IOPS random 4 KB | A single NVMe absorbs a lot more than people assume |
| EBS gp3 | 125 MB/s / 3,000 IOPS baseline, up to 1,000 MB/s / 16,000 IOPS | **The number that surprises people: default EBS is ~40× slower than local NVMe** |
| 10 / 25 / 100 GbE NIC | 1.25 / 3.1 / 12.5 GB/s | 100 GbE ≈ 12.5 GB/s ≈ 12,500 × 1 MB/s |
| Postgres on NVMe, simple writes | ~5k-20k write TPS single primary | Sharding below this is usually premature |
| Redis, single instance/shard | ~100k ops/s (single-threaded); 1M+ with pipelining | Pipelining is a 10× lever, mention it |
| Kafka, per broker | ~100 MB/s-1 GB/s; partitions = max consumer parallelism | Partition count is the hard-to-change decision |
| Typical stateless HTTP/JSON service | ~1k-5k rps per core at 50-60% CPU | Use 2k/core as the default and say it's a guess |
| Cassandra / DynamoDB partition | ~1k-3k writes/s per partition, hard hot-key ceiling | Hot key ≠ hot partition; this is the ceiling |

**Bytes per thing.**

| Thing | Size | Note |
|---|---|---|
| ASCII char / UTF-8 latin | 1 B | Non-latin up to 4 B; matters for 22-locale systems |
| int32 / int64 / float32 / float64 | 4 / 8 / 4 / 8 B | |
| UUID | 16 B binary, 36 B as string | **Storing UUIDs as text is a 2.25× waste; say this** |
| Unix timestamp | 8 B (4 B until 2038) | |
| Narrow index/join row (ids + ts) | ~40-60 B | The right size for a hot precomputed table |
| Typical "entity" row (user, post) | ~200 B - 1 KB | Default to 500 B when you don't know |
| Row overhead in Postgres | ~23-28 B per tuple header + page overhead | Why 40 B logical becomes ~70 B on disk |
| Redis key overhead | ~50-100 B per key beyond the value | **The trap in every cache-sizing question** |
| JSON vs binary encoding | JSON ≈ 2-4× protobuf/avro for the same data | |
| Thumbnail / web image / hi-res photo | 10-50 KB / 100-500 KB / 2-5 MB | |
| 1080p video bitrate / 4K | ~5 Mbps / ~20 Mbps | 1080p ≈ 2.25 GB per hour |
| Embedding vector, 1024-dim float32 | 4 KB | int8 → 1 KB, binary → 128 B |
| LLM token | ~4 chars ≈ 0.75 words | 1,000-word doc ≈ 1,300-1,500 tokens |

**Availability arithmetic.** Convert nines to downtime instantly, because "highly available" is not a requirement and "99.95%" is.

| SLO | Downtime / year | / month | Implication |
|---|---|---|---|
| 99% | 3.65 days | 7.2 h | One machine, manual recovery |
| 99.9% | 8.76 h | 43 min | Single region, automated failover, humans in the loop |
| 99.99% | 52.6 min | 4.3 min | Multi-AZ, no human in the recovery path |
| 99.999% | 5.3 min | 26 s | Multi-region active-active; the deploy pipeline is now the risk |

And the composition rule that catches people: **serial dependencies multiply.** Five components each at 99.9% in series gives 0.999⁵ ≈ 99.5%, which is 43 hours a year. If your SLO is 99.99% and your request path has five hops, every hop needs ~99.998% or you need redundancy at each hop. State this when someone asks for four nines on a chain of microservices.

### Peak-to-average: the ratio that sizes everything

Average QPS has never sized a single piece of infrastructure. Peak does.

| Workload shape | Peak / average | Why |
|---|---|---|
| Global consumer web/social | **2-3×** | Diurnal cycle smeared across timezones |
| Single-region consumer app | 3-5× | One timezone means one sharp evening peak |
| B2B / enterprise SaaS | 4-8× | Business hours only: ~10 h of the 24 carry ~95% of load |
| Cron / batch-triggered | 10-100× | Everything at the top of the hour. The worst shape. |
| Event-driven (ticket sales, live sports, product launch) | 10-1000× | Instantaneous, and marketing controls the trigger |
| Notification campaign push | 50-500× | 10M in one minute against a 500/s baseline |

Derivation, if you want to justify the multiplier rather than assert it: if a fraction *f* of the day carries a fraction *p* of the traffic, then peak/average ≈ *p*/*f*. Business hours (f = 10/24 = 0.42) carrying 95% of load gives 0.95/0.42 ≈ 2.3× as a *sustained-hour* ratio, and the instantaneous peak within that hour is another 2-3× on top, which is where "4-8×" comes from. Saying that derivation out loud is worth more than the number.

**Say which peak you mean.** There are three and they size different things:
- **Peak sustained (hour)** sizes your steady-state fleet and your database.
- **Peak burst (second)** sizes your queue depth, connection pool, and rate limiter.
- **Peak concurrent** sizes memory, file descriptors, and WebSocket capacity. This is Little's Law: `concurrency = throughput × latency`. 15,000 rps × 20 ms = 300 in flight. 15,000 rps × 2 s = 30,000 in flight, which is an entirely different machine.

**Never size at 100% utilisation.** Basic queueing theory (M/M/1): wait time = service time × ρ/(1-ρ). At ρ = 0.5 the queueing wait equals one service time; at ρ = 0.9 it is 9×; at ρ = 0.95 it is 19×. This is why fleets are sized at 50-60% and why "we have 20% headroom" means "our p99 is about to triple". Say "I'm sizing at 60% utilisation because latency goes non-linear above ~70%" and you have banked a point.

### The 80/20 splits, and where they lie to you

Three heuristics that are fine as a starting assumption and dangerous as a conclusion:

1. **Read:write ratio.** Social feed ≈ 100:1. Messaging ≈ 1:1 (every message is written once and read once or twice). E-commerce browse ≈ 20:1. Analytics ingest ≈ 1:1000 the other way. Ad serving ≈ read-only at query time with a huge async write path. **Ask, do not assume**: 100:1 and 2:1 produce different architectures, and this is the single highest-value clarifying question in the round.
2. **80/20 on key popularity.** 20% of keys serve 80% of reads, which is what makes caching work. But real popularity is Zipfian, not a clean 80/20, and the tail is heavy: getting from an 80% to a 95% hit rate typically costs far more than 1.2× the memory because you are climbing the flat part of the distribution. And the top of the distribution is worse than average too: the single hottest key can be 1-5% of *all* traffic, which is a hot-partition problem no amount of hashing fixes.
3. **80/20 on data temperature.** ~80% of reads hit data written in the last ~20% of the retention window (often much sharper: 90% of feed reads touch the last 3 days). This is the justification for tiered storage, and stating the tier boundary as a number ("hot = 7 days in Redis, warm = 90 days in Cassandra, cold = S3/Parquet beyond") is what makes a retention answer concrete.

**The amplification factor that dwarfs all three.** The API-level write rate is almost never the number that breaks. The *amplified* write rate is: `logical writes/s × fanout`. 500 posts/s × 500 average followers = 250,000 timeline inserts/s. 1M notifications/s × 1.6 channels = 1.6M sends/s. 100B messages/day × average group size 5 = 500B deliveries/day. **Always compute the amplified number and name it as the one that matters.** Candidates who only compute API-level QPS conclude the system is easy and then design as if it were.

### Recovering when your assumption was wrong

This will happen, and how you handle it is graded more heavily than getting it right. Interviewers frequently *cause* it on purpose.

**The recovery script, in order:**

1. **Say it immediately and precisely.** "Hold on. I assumed 500 average followers, but if the distribution is heavy-tailed with accounts at 50M, the average is the wrong statistic entirely and my 250k inserts/s is a fantasy for the tail." Naming the *statistical* error, not just the number, is the difference between a stumble and a demonstration.
2. **Do not restart.** Identify precisely which decision the wrong number fed. Usually it is one or two. "This changes the fanout decision and the Redis sizing. It does not change the API, the schema, or the read path."
3. **Walk the branch, ideally one you already named.** "So: hybrid fanout with a threshold, and the threshold is now a real design parameter rather than an afterthought."
4. **State what you would measure to fix the assumption for real.** "I'd want the p99 and p99.9 of the follower-count distribution, not the mean, before committing to a threshold."
5. **Keep the old number visible and annotate it.** Crossing it out and writing the new one beside it shows the derivation survived; erasing it looks like you are hiding evidence.

**What not to do:** do not defend the number, do not silently change it and continue, and do not say "well it's just an estimate". The correct framing is that the estimate was fine and the *assumption* was wrong, which is a different and recoverable error.

**The pre-emptive version, which is better.** When you state an assumption, state its sensitivity at the same time: "500 average followers. If that's off by 10× the fanout-on-write approach stops working and I'd move to read-time merge." Now if the interviewer corrects you, you are executing a plan rather than recovering from a mistake. This costs eight words and is the single highest-leverage habit in this module.

---

## Build it from scratch

### Eight worked guesstimates

Each is written the way you would say it out loud, at the pace you would say it. Target: 60 to 90 seconds each.

---

#### G1 — Read and write QPS for a social feed (50M DAU)

*Decides:* whether the read path needs precomputation, and whether the write path needs a queue.

```
ASSUME  50M DAU · 10 feed opens/day · 1 post/day · 500 avg followees
        (marking "500 avg" — if heavy-tailed I revisit the fanout decision)

READS   5e7 × 10 = 5e8 /day  ÷ 1e5 s = 5e3 = 5,000 read QPS avg
WRITES  5e7 × 1  = 5e7 /day  ÷ 1e5 s = 5e2 =   500 write QPS avg
PEAK    ×3 (global consumer, timezone-smeared)
        → 15,000 read QPS · 1,500 write QPS peak
RATIO   10:1 at the API level

PAYLOAD 20 items × ~300 B = 6 KB/response
        15,000 × 6 KB = 9e7 B/s = 90 MB/s = 720 Mbps egress from the API tier

AMPLIFIED WRITE  ← the number that actually matters
        500 posts/s × 500 followers = 2.5e5 = 250,000 timeline inserts/s

SANITY  15k read QPS is one modest Redis cluster and ~15-20 stateless nodes.
        1,500 write QPS is ONE Postgres primary; do not shard it.
        250k inserts/s is a real throughput problem and is why fanout is async.
        Cross-check: Twitter reported ~6k tweets/s average at ~500M MAU, so
        500/s at 50M DAU is the right order. Good.

DECIDES Precompute the timeline (read:write is 10:1 at the API but the read is
        the latency-critical path). Async fanout via a queue. Single relational
        primary for posts/users/follows.
```

**The move to steal:** compute the API-level number, then say "but that's not the number that breaks", and compute the amplified one.

---

#### G2 — Storage, ingest bandwidth, and transcode compute for a video platform

*Decides:* storage tiering, transcode fleet size, and whether the CDN is the whole design.

```
ASSUME  500 hours of video uploaded per minute (the widely-cited YouTube figure)
        Transcode ladder: 240p/360p/480p/720p/1080p/4K
        1080p ≈ 5 Mbps; full ladder ≈ 3× the 1080p rendition; master ≈ 2× 1080p

CONTENT 500 hr/min × 6e1 min/hr × 2.4e1 hr/day ≈ 7.2e5 = 720,000 hours/day

PER HOUR OF SOURCE
        1080p:  5 Mbps × 3.6e3 s = 1.8e4 Mb = 2.25e3 MB ≈ 2.25 GB
        ladder: ~3× 1080p        ≈ 7 GB
        master: ~2× 1080p        ≈ 5 GB   (keep it: re-encoding needs the source)
        TOTAL ≈ 12 GB per source hour, round to 1e1 GB

STORAGE 7.2e5 hr/day × 1e1 GB = 7.2e6 GB = 7.2 PB/day
        × 365 ≈ 2.6 EB/year of new content, and it is append-only forever

INGEST  masters only: 7.2e5 × 5 GB = 3.6e6 GB/day ÷ 1e5 s = 36 GB/s = 288 Gbps
        sustained upload bandwidth. Peak ×2 → ~0.6 Tbps.

TRANSCODE  assume ~1 core-hour to produce the full ladder for 1 source hour
        (optimistic; hardware-accelerated, parallelised across renditions)
        7.2e5 core-hours/day ÷ 2.4e1 h = 3e4 = 30,000 cores running continuously
        ≈ 470 × 64-core instances. At ~$1.5/hr that's ~$500k/month of transcode.

SANITY  Exabytes per year of new storage matches public estimates of YouTube's
        footprint. 30k cores is a large but unremarkable fleet. Good.

DECIDES Object storage with lifecycle tiering (hot → IA → glacier by view decay),
        not a database. Transcode is an async queue-driven fleet on spot capacity,
        because a 2-hour transcode delay is acceptable and spot is ~70% cheaper.
        The 80/20 on views (a tiny fraction of videos get almost all views) means
        the CDN, not the origin, carries the read path — so DON'T pre-transcode the
        full ladder for everything; do 360p/720p eagerly and the rest on first demand.
```

**The move to steal:** that last line. Deriving a *lazy* transcode policy from the popularity distribution is the senior answer, and it falls straight out of the arithmetic.

---

#### G3 — Cost of an LLM feature (RAG support assistant)

*Decides:* whether the feature is viable at all, and which optimisation matters.

```
ASSUME  1M conversations/day · 6 turns each
        per turn: 4,000 input tokens (system prompt + retrieved chunks + history)
                    300 output tokens
        Model: Claude-Sonnet-class at $2 / $10 per M input / output
               (July 2026 published pricing)

TOKENS  input:  1e6 × 6 × 4e3 = 2.4e10 = 24,000 M tokens/day
        output: 1e6 × 6 × 3e2 = 1.8e9  =  1,800 M tokens/day

COST    input:  2.4e4 M × $2  = $48,000/day
        output: 1.8e3 M × $10 = $18,000/day
        TOTAL ≈ $66,000/day ≈ $2.0M/month     ← unviable, say so immediately

EMBEDDINGS (for retrieval)
        1e6 × 6 queries × ~50 tokens = 3e8 tokens/day at ~$0.02/M = $6/day
        → retrieval is free relative to generation. Never optimise this first.

LEVERS, in order of effect per unit of work
  1. PROMPT CACHING. ~80% of input is a stable system prompt + retrieved docs.
     Cache reads bill at ~10% of input. → 0.2×48k + 0.8×48k×0.1 = $13.4k/day (3.6×)
  2. CONTEXT DIET. 4,000 → 1,500 input tokens by reranking to top-3 chunks
     instead of top-10. → another ~2.7× on the input side.
  3. MODEL ROUTING. Send the ~70% of easy turns to a Flash-class model at
     ~$0.10/$0.40 per M (≈20× cheaper). → ~2.5× overall.
  4. BATCH API for anything not user-facing: flat 50% discount.
  5. Cut turns: a better first answer removes turns 2-6 entirely. Biggest lever,
     hardest to engineer, and it is a product change not an infra change.

  Composed: 3.6 × 2.7 × 2.5 ≈ 24× → ~$2,700/day ≈ $80k/month. Now viable.

SANITY  $2/user-conversation-month at 1M/day would be absurd for support;
        $0.0027 per conversation against a human support cost of $3-6 per
        contact is obviously viable. That comparison is the sanity check.

DECIDES Prompt caching and reranking are not optimisations, they are load-bearing
        architecture. Enforce a per-user daily token cap in code. Have a
        deterministic fallback for when the budget is exhausted.
```

Pricing: [LLM API Pricing, July 2026 — TLDL](https://www.tldl.io/resources/llm-api-pricing), [LLM API Pricing Comparison — CloudZero](https://www.cloudzero.com/blog/llm-api-pricing-comparison/) — accessed 2026-07-26.

**The move to steal:** compute the naive number first, declare it unviable out loud, then list levers with their multipliers and compose them. The composition is what demonstrates you have actually done this.

---

#### G4 — Cache memory for the feed (and the overhead trap)

*Decides:* Redis cluster size, timeline cap, and whether precomputation is affordable.

```
NAIVE   50M users × 800 timeline entries × 40 B/entry
        = 5e7 × 8e2 × 4e1 = 1.6e12 B = 1.6 TB

THE TRAP  That is the payload, not the memory. Redis costs ~50-100 B of overhead
        per key, and a sorted set above ~128 members becomes a skiplist + hash
        with roughly 80-120 B per member, not 40.
        Realistic: 5e7 × 8e2 × 1.1e2 ≈ 4.4e12 B ≈ 4.4 TB
        → the naive answer was ~3× low. Say this. It is the whole question.

REDUCE, in order
  1. Only cache active users. 7-day-active ≈ 60% of DAU-defined base, and 30-day
     tail rarely reads. Precompute lazily on first read for the rest.
        → 0.4 × 4.4 TB ≈ 1.8 TB
  2. Cut the cap: 800 → 200 entries covers ~10 pages of 20, which covers
     >95% of sessions; page deeper scrolls from Cassandra.
        → 4× → ~450 GB
  3. Pack the member: store an 8-byte (ts<<24 | post_id_low) instead of a
     40-byte tuple, hydrating author from the post row you fetch anyway.
        → member overhead drops toward ~60 B → ~250 GB

FINAL   ~250-450 GB → 6-12 Redis shards of 64 GB with replicas, not 100 nodes.
        Cost: order $3-6k/month instead of $60k/month.

HIT RATE  Assume 95%, and design for 0%: a cold shard restart means 2M users miss
        simultaneously. Single-flight coalescing + jittered warm-up, or the
        Cassandra tier takes the full unmitigated read rate.

SANITY  A 4.4 TB Redis footprint for 50M users is ~88 KB/user, which is absurd
        for a list of 800 ids. That absurdity is the signal that the encoding,
        not the arithmetic, is wrong.
```

**The move to steal:** the deliberate 3× correction for data-structure overhead. Almost nobody does this, and it is the difference between a cache-sizing answer and a cache-sizing *decision*.

---

#### G5 — CDN bandwidth and egress cost for an image service

*Decides:* whether egress dominates the bill (it usually does), and the required origin offload ratio.

```
ASSUME  500M DAU · 50 images viewed/day · 200 KB average after transform

VIEWS   5e8 × 5e1 = 2.5e10 image views/day ÷ 1e5 = 2.5e5 = 250,000 images/s avg
        peak ×3 → 750,000 images/s

BYTES   2.5e10 × 2e5 B = 5e15 B = 5 PB/day = ~150 PB/month
BANDWIDTH 5e15 ÷ 1e5 = 5e10 B/s = 50 GB/s = 400 Gbps avg; peak ~1.2 Tbps

EGRESS COST
        list CDN pricing ~$0.05-0.085/GB: 1.5e8 GB × $0.05 = $7.5M/month
        negotiated at scale ~$0.005-0.01/GB:               = $0.75-1.5M/month
        → the negotiated rate is a 5-10× swing. Say that the contract IS the
          architecture decision at this scale.

ORIGIN OFFLOAD  the number that matters more than any of the above
        At 95% CDN hit rate the origin serves 5% = 12,500 images/s, 2.5 GB/s.
        At 90% it serves 25,000/s, 5 GB/s — DOUBLE, for a 5-point hit-rate drop.
        Origin egress and origin compute both scale with (1 - hit_rate), so the
        sensitivity is brutal and non-obvious.

COMPARE Stateless compute for 750k req/s of CDN-cached content is ~nothing.
        Transform-on-demand for the misses: 12,500/s × ~30 ms CPU = 375 cores.
        → egress is 10-100× the compute bill. State this ordering explicitly.

SANITY  400 Gbps sustained is a top-tier CDN customer, consistent with a
        500M-DAU photo product. 150 PB/month is the right order.

DECIDES Signed URLs served directly from the CDN, never proxied through the app.
        Pre-generate 3-4 fixed sizes rather than arbitrary on-demand transforms
        (arbitrary sizes fragment the cache and destroy the hit rate — the real
        reason to restrict them, not aesthetics).
```

**The move to steal:** "egress is 10-100× the compute bill" plus the hit-rate sensitivity. Cost-ordering is the 2026 differentiator.

---

#### G6 — How many servers for 15,000 peak QPS

*Decides:* the fleet size number the interviewer is actually asking for.

```
ASSUME  p99 target 200 ms · measured service time 20 ms (10 ms cache RTT +
        ~5 ms CPU + ~5 ms serialisation) · ~5 ms CPU per request

LITTLE'S LAW (concurrency)
        concurrency = throughput × latency = 1.5e4 × 2e-2 = 3e2 = 300 in flight
        → 300 concurrent requests. Async runtime: trivial. Thread-per-request:
          300 threads live, so ~2-3 instances by threads alone even before CPU.

CPU-BOUND SIZING (the real constraint)
        1 core at 100% = 1 / 5e-3 = 200 rps
        size at 60% utilisation (latency goes non-linear above ~70%): 120 rps/core
        1.5e4 / 1.2e2 = 125 cores
        → 16 × 8-core instances, or 8 × 16-core

REDUNDANCY  survive the loss of one AZ of three → provision 1.5×
        → ~24 × 8-core instances across 3 AZs, round to 24

CROSS-CHECK the two methods disagree by 10× (3 instances vs 24). CPU wins,
        because Little's Law bounds concurrency, not throughput. If they had
        agreed I would be suspicious. Naming which constraint binds is the answer.

WHAT CHANGES IT
        latency 20 ms → 2 s (an LLM call): concurrency = 1.5e4 × 2 = 30,000 in
        flight. Thread-per-request is now impossible (30k threads ≈ 30 GB of
        stacks); you need async, and connection/FD limits become the binding
        constraint instead of CPU.

SANITY  24 instances for 15k QPS is ~600 rps/instance, which is unremarkable
        for JSON over HTTP. If I'd computed 3 instances at 5,000 rps each I'd
        want to justify it; if I'd computed 500 instances I'd look for the bug.

DECIDES Stateless horizontal tier, 3 AZs, HPA on CPU at 60% target. And: if the
        request does anything slow (LLM, external API), the concurrency model
        matters more than the core count.
```

**The move to steal:** compute it two ways, notice they disagree, and name which constraint binds. Also the LLM variant, because that is the 2026 question.

---

#### G7 — Messaging: storage and throughput (and the requirement that changes it 100×)

*Decides:* whether you need a petabyte store at all.

```
ASSUME  2B users · 100B messages/day (the reported WhatsApp order of magnitude)
        avg group size 5 for group messages, ~50% of traffic is group

THROUGHPUT
        1e11 /day ÷ 1e5 s = 1e6 = 1,000,000 messages/s average
        peak ×3 → 3,000,000 messages/s
        DELIVERIES (amplified): 1e11 × ~3 avg recipients = 3e11/day = 3e6/s avg,
        ~1e7/s peak.  ← the number that sizes the fanout tier

STORAGE IF YOU STORE EVERYTHING
        ~100 B text + ~200 B metadata (ids, ts, status, encryption header) ≈ 300 B
        1e11 × 3e2 B = 3e13 B = 30 TB/day
        × 3 replication = 90 TB/day = ~33 PB/year
        → a genuinely large, expensive, compliance-heavy store

STORAGE IF YOU DELETE ON DELIVERY  ← ask this question
        Only undelivered messages persist. If ~1% are undelivered at any moment
        with a ~1-day worst-case offline window:
        1e9 messages × 3e2 B = 3e11 B = 300 GB. Times 3 replicas: ~1 TB.
        → 30,000× smaller. It fits in RAM.

        THIS IS THE WHOLE DESIGN. One product requirement ("is server-side
        history required, or is the client the source of truth?") moves the
        storage answer by four orders of magnitude and changes the database
        from a 33 PB/year Cassandra fleet to a small Mnesia/Redis-class queue.
        WhatsApp's actual architecture takes the second branch; iMessage and
        Slack take the first.

CONNECTIONS  2B users, ~20% concurrently connected = 4e8 persistent connections.
        At ~50k connections/node → 8,000 connection-terminating nodes.
        Memory: 4e8 × ~10 KB/conn state = 4 TB spread across the fleet.

SANITY  1M messages/s at 300 B is 300 MB/s of raw ingest, which is 3 Kafka
        brokers' worth — trivially small. The hard parts are the 400M
        persistent connections and the fanout, not the byte volume.

DECIDES Ask about server-side history before designing anything. Then: persistent
        connection tier is the hard part, message store is either small (delete on
        delivery) or a wide-column store partitioned by (chat_id, time bucket).
```

**The move to steal:** an entire order-of-magnitude class of the design hinging on one clarifying question, and computing both branches to prove it.

---

#### G8 — Vector index sizing and cost for RAG over 100M chunks

*Decides:* whether the index fits in RAM, and therefore the whole serving topology.

```
ASSUME  100M chunks · 1024-dim embeddings · HNSW with M=32 · target recall@10 ≥ 0.95
        target p99 search latency 50 ms · 1,000 search QPS peak

RAW VECTORS (float32)
        1e8 × 1.024e3 × 4 B = 4.1e11 B = 410 GB

HNSW GRAPH OVERHEAD
        layer 0 stores up to 2M = 64 neighbour ids × 4 B = 256 B/node
        upper layers add ~1/(M) of that, call it ×1.2 → ~300 B/node
        1e8 × 3e2 = 3e10 B = 30 GB
        TOTAL ≈ 440 GB, and HNSW is only fast if it is resident in RAM
        → ~600 GB RAM with headroom → 3 × r7g.8xlarge (256 GB) minimum,
          realistically 4 shards for headroom and rebuild space

QUANTISATION (the actual production answer)
        int8 scalar quantisation: 4× → 102 GB vectors + 30 GB graph ≈ 132 GB
              → fits ONE 256 GB node. Recall loss typically ~1-2 points,
                recoverable by over-fetching top-50 and reranking.
        binary quantisation: 32× → 13 GB vectors. Search the binary index,
              rerank top-100 against float32 vectors on NVMe.
              → the index is now cache-resident; NVMe rerank adds ~1-5 ms.

COST    float32, 4 × r7g.8xlarge (~$1.7/hr on-demand) ≈ $5,000/month
        int8,   1 × r7g.8xlarge + 1 replica          ≈ $2,500/month
        binary, 2 × r7g.2xlarge + NVMe               ≈   $700/month
        → quantisation is a 7× cost lever with a ~1-2 point recall cost. That
          tradeoff is the answer to "how would you cut this bill".

BUILD COST (one-time, and the point is that it is negligible)
        1e8 chunks × ~400 tokens = 4e10 tokens at ~$0.02/M = $800 one-time
        → building the index is ~$800; serving it is $30k/year. Serving dominates
          by 40×, which is the opposite of most people's intuition.

QPS CAPACITY
        HNSW at ef_search=100 on a 25M-vector shard: ~2-5 ms single-threaded
        → ~1 core ≈ 200-400 qps; 1,000 QPS across 4 shards needs ~3-4 cores/shard
        → CPU is not the constraint. MEMORY is. This is why the sizing question
          is a memory question, and why "just add replicas" costs 132 GB each.

SANITY  410 GB for 100M vectors = 4.1 KB/vector, which is exactly one 1024-dim
        float32 vector. Arithmetic confirms itself. Good.

DECIDES int8 quantisation by default with float32 rerank on the top-50. Shard by
        a filterable attribute (tenant, language) so pre-filtering stays inside a
        shard — filtered ANN across shards is where recall silently collapses.
```

**The move to steal:** the build-vs-serve cost inversion, and identifying that the sizing question is a memory question rather than a throughput question.

---

### The 30-second drill format

Practise by writing only these five lines for any prompt. If you can produce them in 90 seconds you can do this phase in an interview.

```
DECIDES:  <the one architectural choice this number resolves>
ASSUME:   <2-3 inputs, each rounded to a power of ten, each marked>
COMPUTE:  <one line of arithmetic, exponents only>
AMPLIFY:  <× fanout, if there is any — usually the real number>
SANITY:   <compare to a system whose scale you know>
```

---

## How it's done in production

In production nobody guesses, and knowing the real replacement for each guess is a senior signal:

| Estimate | Production replacement | What the estimate is still for |
|---|---|---|
| Peak QPS | Prometheus/CloudWatch p99 over 90 days, with the annual peak | Sizing a system that does not exist yet |
| Row size | `pg_total_relation_size` / row count; `ANALYZE` output | Choosing between a narrow and wide table before you build it |
| Cache hit rate | `redis_keyspace_hits / (hits + misses)`, per key prefix | Deciding whether the cache tier is worth building |
| Cost | Cost Explorer with allocation tags; per-request unit cost dashboards | Killing a design before you build it |
| Server count | Load test to the knee of the latency curve, then HPA | Deciding the shape (async vs threaded) before load testing |
| Tail latency | OTel traces, span histograms, and per-hop attribution | Knowing that three cross-region hops cannot fit in 200 ms |
| LLM token spend | Provider usage API + per-tenant token accounting | Deciding whether a feature is viable at all |

**Unit economics is the artefact that matters.** The production version of this module is a dashboard showing **cost per request**, **cost per active user per month**, and **cost per tenant**, because those are the numbers that make architecture decisions decidable. "This endpoint costs $0.004 per call, of which $0.0031 is LLM tokens" ends an argument that could otherwise run for a quarter. Mentioning that you would instrument unit cost, not just latency and errors, is a staff-level signal.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Estimate is off by 1000× and you don't notice | Skipped the sanity check | Always compare to a known system before using the number |
| Estimate is off by exactly 3600 or 86400 | Unit slip between per-second, per-hour, per-day | Write the unit on every line; cancel them visually |
| Cache sized correctly, still OOMs at 3× the calculation | Ignored per-key and data-structure overhead | Add 2-3× for Redis; measure with `MEMORY USAGE` on a real key |
| System handles average load, dies every Monday 09:00 | Sized on average, not peak; B2B shape is 4-8× | Peak sustained for the fleet, peak burst for the queue |
| p99 triples when traffic grows 20% | Sized at ~85% utilisation; queueing is non-linear | Size at 50-60%; M/M/1 wait = service × ρ/(1-ρ) |
| Storage forecast wrong by 5× | Forgot replication factor, index overhead, or WAL/tombstones | `records × bytes × retention × replication × (1 + index)` |
| Cloud bill 10× the estimate | Egress and cross-AZ traffic were never in the model | Egress is often the largest line item; count every AZ hop |
| LLM feature ships, burns the quarterly budget in a week | No per-user token cap; estimated on average prompt length | Cap in code; estimate on p99 prompt length, not mean |
| Fleet sized right, dies on cold start | Estimated steady state only, hit rate assumed 100% | Model the cold-cache case explicitly; it is a different system |
| "We need 8M QPS" for a 10M-user product | Multiplied instead of divided by 86,400, no sanity check | 1M/day ≈ 10/s. Memorise that one conversion. |

---

## Tradeoffs & when NOT to use it

- **Do not estimate what you will not use.** Four correct numbers that decide nothing is worse than one number that decides the storage engine, because it burns 4 minutes of a 45-minute round and reads as a memorised ritual. If you cannot say what a number decides, do not compute it.
- **Do not estimate when the interviewer has said not to.** Some interviewers consider capacity arithmetic performative and will tell you to assume it is large. Take the instruction; keep one number if it is load-bearing and say why.
- **Order-of-magnitude estimation is the wrong tool for anything near a cliff.** If the answer is "we need 950 GB and the box has 1 TB", a 3× error decides the architecture. Latency budgets close to an SLO, memory near an instance boundary, and provider rate limits are all cliff-shaped. Say "this is close enough to the limit that I would measure rather than estimate."
- **It is the wrong tool for tail behaviour.** Estimation gives you averages and simple multipliers. It cannot give you p99.9, queueing dynamics under bursty arrival, GC pauses, lock contention, or coordinated omission in your load generator. Anything driven by variance rather than volume needs measurement, and claiming otherwise is where estimates cause real outages.
- **Cost estimates are the least reliable and swing the most.** Egress rates are negotiated (5-10× spread between list and enterprise pricing), spot pricing moves, reserved instances and committed-use discounts are 30-60%, and LLM prices have fallen sharply and repeatedly. Give an order of magnitude, name the dominant line item, and say which input you are least confident in.
- **Anchoring is a real hazard.** Once you have said "500 followers on average" you will keep using it, and heavy-tailed distributions make the mean actively misleading. For anything with a power-law shape (followers, file sizes, tenant size, key popularity, request cost) state that you want a percentile rather than a mean, and that the mean will understate the tail.
- **Do not perform mental arithmetic you cannot do reliably under stress.** Round harder. `5e7 / 1e5` is safe; `48,271,000 / 86,400` is a coin flip and a visible stumble. The rounding is not a shortcut, it is the technique.

---

## Interview questions

### Q1 — How many QPS does a service with 100M DAU and 20 requests per user per day handle?
**Testing:** the base conversion, and whether you go straight to peak.
**Answer:** 100M × 20 = 2 × 10⁹ requests/day. Divided by ~10⁵ seconds gives 2 × 10⁴ = 20,000 QPS average. Peak at 2-3× for a global consumer product gives 40-60k QPS. Sanity check: 20k QPS of simple JSON is roughly 20-40 stateless nodes, which is unremarkable.
**Follow-up trap:** *"Why 10⁵ and not 86,400?"* Because I care about the exponent, and 10⁵ is a 14% error in the conservative direction, meaning it slightly under-reports QPS and I will cover that with the peak multiplier anyway. If the answer landed within 15% of a decision boundary I would redo it precisely, and I would say so.

### Q2 — Estimate the storage for a system storing 1M records a day at 1 KB each for 5 years.
**Testing:** whether you multiply through the full chain rather than stopping at the logical size.
**Answer:** Logical is 10⁶ × 10³ B = 1 GB/day, × 365 × 5 ≈ 1.8 TB. Then the multipliers people forget: 3× replication → 5.5 TB, plus ~30% index overhead → ~7 TB, plus WAL and backups (often another 1-2× depending on retention) → call it 10-14 TB provisioned. Round to "order 10 TB". The formula is `records × bytes × retention × replication × (1 + index)`, and then a separate line for WAL and backups.
**Follow-up trap:** *"You provisioned 14 TB. Do you need it all on the same tier?"* No, and this is where the 80/20 on data temperature applies: ~90% of reads will hit the most recent months. Hot months on NVMe, older partitions on cheaper storage, and anything past the query horizon in S3/Parquet queried through an external table. Naming the tier boundary as a number and tying it to the read distribution is the answer; "we'd archive old data" is not.

### Q3 — A design requires three sequential cross-region API calls with a 200 ms p99 budget. Assess it.
**Testing:** whether the latency ladder is usable, not just memorised.
**Answer:** Dead on arrival. A US-to-Europe round trip is ~75-90 ms and US-to-Singapore is ~170-230 ms, so three sequential cross-region hops is 225 ms at absolute best and 600 ms realistically, before any processing. The budget is violated by the speed of light in fibre, which is ~200,000 km/s, so ~1 ms per 100 km one-way after routing overhead. No engineering fixes it. The options are: parallelise the calls so you pay one round trip instead of three, replicate the data so the calls become local, or renegotiate the SLO.
**Follow-up trap:** *"Parallelise them and you're at 90 ms. Are you done?"* No, because parallel fanout makes the *tail* your latency. If each call has a p99 of 90 ms, the p99 of the max of three is much worse than 90 ms: with independent calls, P(all three under p99) = 0.99³ ≈ 97%, so ~3% of requests exceed it, and the effective p99 of the combined call is closer to each call's p99.7. That is why hedged requests and per-call timeouts below the overall budget exist.

### Q4 — Estimate the monthly cost of an LLM feature: 1M conversations a day, 6 turns, 4k input and 300 output tokens per turn.
**Testing:** the 2026 addition. Whether you have token economics at hand.
**Answer:** Input is 1M × 6 × 4,000 = 2.4 × 10¹⁰ = 24,000 M tokens/day; output is 1.8 × 10⁹ = 1,800 M/day. At Sonnet-class pricing of $2/M input and $10/M output that is $48k + $18k = $66k/day, about $2M/month. That is unviable as stated, so the design has to change: prompt caching on the stable prefix at roughly 10% of input price gives ~3.6× if 80% of input is cacheable, reranking to top-3 chunks instead of top-10 cuts input another ~2.7×, and routing the easy 70% of turns to a Flash-class model at ~20× lower unit price gives ~2.5×. Composed, that is ~24× and lands near $80k/month.
**Follow-up trap:** *"Which of those levers would you not ship?"* Model routing, first, if quality is the product: it introduces a second quality distribution and a routing classifier that can be wrong, and a wrong route on a billing question is a support escalation. Prompt caching and context reduction are pure wins with no quality coupling, so they ship first. Ordering levers by quality risk rather than by size is the senior framing.

### Q5 — 15,000 peak QPS, 20 ms service time. How many servers?
**Testing:** Little's Law versus CPU-bound sizing, and whether you know which binds.
**Answer:** Two computations. Little's Law gives concurrency = 15,000 × 0.02 = 300 in flight, which is nothing for an async runtime and ~2-3 instances for thread-per-request. CPU-bound sizing at ~5 ms CPU per request gives 200 rps/core at full utilisation, 120 rps/core at a 60% target, so 125 cores, or ~16 × 8-core instances, and ~24 instances to survive losing one of three AZs. The two methods disagree by 10× and CPU wins, because Little's Law bounds concurrency, not throughput.
**Follow-up trap:** *"Now service time is 2 seconds because there's an LLM call."* Concurrency becomes 15,000 × 2 = 30,000 in flight. Thread-per-request is now impossible (30,000 threads at ~1 MB of stack is ~30 GB), so the concurrency model becomes the design constraint rather than the core count, and the binding limits shift to file descriptors, connection pool size, and the upstream provider's rate limit. This is precisely why LLM-backed endpoints are architecturally different, and why they belong behind a queue rather than a request thread.

### Q6 — You said 500 average followers. I'm telling you the top account has 200 million. What changes?
**Testing:** recovery from a broken assumption, deliberately induced.
**Answer:** The mean is the wrong statistic for a power-law distribution, so my 250k inserts/s is right for the body and meaningless for the tail. One post from a 200M-follower account is 200M timeline inserts, which at ~40 bytes is 8 GB of writes and, at 250k inserts/s of capacity, over 13 minutes of fanout for a single post, during which it also head-of-line blocks every other post in that partition. This changes exactly one decision: fanout strategy becomes hybrid. Fanout-on-write below a follower threshold (10k is a defensible line), fanout-on-read above it with a small per-celebrity post cache merged at query time. It does not change the API, the schema, or the read path.
**Follow-up trap:** *"How do you pick the threshold?"* Not from intuition. I want the follower-count distribution's percentiles: the threshold should sit where the marginal cost of a write-fanout exceeds the marginal cost of a read-merge, which depends on the account's post rate as well as its follower count. A 200M-follower account that posts once a week is cheap to fan out; a 50k-follower account posting 100 times a day may not be. So the real key is `followers × post_rate`, not followers alone, and that reframing is the answer they are looking for.

### Q7 — How much Redis do you need to cache 50M users' timelines at 800 entries each?
**Testing:** whether you account for data-structure overhead. Most candidates do not.
**Answer:** The naive payload figure is 50M × 800 × 40 B = 1.6 TB, and that answer is about 3× too low. Redis adds ~50-100 B of overhead per key, and a sorted set past roughly 128 members converts from a compact listpack to a skiplist plus hash table, costing something like 80-120 B per member rather than 40. Realistic memory is ~4.4 TB. Then reduce: cache only 7-day-active users (~40%) → 1.8 TB, cut the cap from 800 to 200 entries which still covers ten pages → ~450 GB, and pack the member into 8 bytes → ~250 GB. So 6-12 shards, not a hundred nodes.
**Follow-up trap:** *"How would you verify the per-member number instead of estimating it?"* `MEMORY USAGE <key>` on a representative key in a real instance, and `INFO memory` for the aggregate plus fragmentation ratio. I would also check `object encoding` to confirm whether the set is a listpack or a skiplist, because that single boundary (`zset-max-listpack-entries`, default 128) is what causes the 3× step change, and a cap of 100 versus 200 entries is a much larger memory difference than the 2× the numbers suggest.

### Q8 — Estimate the egress bill for a photo service: 500M DAU, 50 views a day, 200 KB each.
**Testing:** whether cost estimation is in your toolkit, and whether you know egress usually dominates.
**Answer:** 500M × 50 = 2.5 × 10¹⁰ views/day, × 200 KB = 5 PB/day, about 150 PB/month. At list CDN pricing of ~$0.05/GB that is $7.5M/month; at a negotiated $0.005-0.01/GB it is $0.75-1.5M/month, so the contract is a 5-10× lever and is itself an architecture decision at this scale. Bandwidth is 50 GB/s average, 400 Gbps, peaking near 1.2 Tbps. Compute is negligible by comparison: even transform-on-miss at a 95% hit rate is ~375 cores. Egress is 10-100× the compute bill.
**Follow-up trap:** *"Your CDN hit rate drops from 95% to 90%. What's the impact?"* Origin load doubles, because origin traffic scales with (1 − hit_rate) and 10% is twice 5%. That is 25,000 images/s and 5 GB/s hitting the origin instead of 12,500 and 2.5 GB/s. The non-obvious cause of such a drop is cache fragmentation from arbitrary on-demand image sizes: every distinct `?w=` value is a separate cache object, so a client that requests device-exact widths can quietly halve your hit rate. That is the real reason to restrict transforms to a fixed set of sizes.

### Q9 — WhatsApp-scale messaging: 100B messages a day. Size the storage.
**Testing:** whether you ask the question that changes the answer by four orders of magnitude.
**Answer:** Throughput first: 10¹¹/day ÷ 10⁵ = 1M messages/s average, 3M/s peak, and deliveries amplified by average recipient count of ~3 gives 3M/s average, ~10M/s peak. Storage depends entirely on one requirement. If server-side history is required: ~300 B per message × 10¹¹ = 30 TB/day, ×3 replication = 90 TB/day, ~33 PB/year. If the client is the source of truth and messages are deleted on delivery, only the undelivered backlog persists: ~1% outstanding over a one-day offline window is ~10⁹ × 300 B ≈ 300 GB, which fits in memory. So before designing anything I would ask whether server-side history is a product requirement, because the answer moves storage by roughly 30,000×.
**Follow-up trap:** *"You store nothing server-side. Now the user gets a new phone."* That is the actual cost of the branch, and it is a product decision, not an engineering one: either history is lost (WhatsApp's historical behaviour), or you add an opt-in encrypted backup to the user's own cloud storage, which moves the storage cost off your balance sheet and keeps you out of the plaintext. The engineering consequence is that the backup blob is opaque to you, so you cannot do server-side search, which is why products that want search (Slack, Teams) take the 33 PB branch.

### Q10 — Size a vector index: 100M chunks, 1024 dimensions. Does it fit in RAM?
**Testing:** ML-infrastructure estimation, now standard in roughly half of loops.
**Answer:** Raw float32 vectors are 100M × 1024 × 4 B = 410 GB. HNSW with M=32 adds roughly 300 B per node for neighbour lists across layers, so ~30 GB, totalling ~440 GB, and HNSW needs to be resident to hit single-digit-millisecond search. So no, not on one common instance: you need ~600 GB with headroom, so 3-4 shards of 256 GB. The production answer is quantisation: int8 gives 4× (down to ~132 GB, one node) for a 1-2 point recall cost recoverable by over-fetching top-50 and reranking against full-precision vectors; binary gives 32× (~13 GB, cache-resident) with a float32 rerank of the top-100 read from NVMe. Cost goes from ~$5,000/month to ~$700/month, so quantisation is a 7× cost lever.
**Follow-up trap:** *"Which is more expensive, building the index or serving it?"* Serving, by roughly 40×, and this surprises people. Embedding 100M chunks at ~400 tokens each is 4 × 10¹⁰ tokens, which at ~$0.02/M is about $800 one-time. Serving is $700-5,000 per month forever. So the optimisation target is memory footprint, not embedding throughput, and re-embedding the whole corpus with a better model is a cheap decision that people wrongly treat as expensive.

### Q11 — Peak-to-average: where does 3× come from, and when is it wrong?
**Testing:** whether the multiplier is a rule of thumb you understand or a number you repeat.
**Answer:** It comes from the diurnal cycle. If a fraction f of the day carries a fraction p of the load, the sustained peak ratio is roughly p/f, and the instantaneous peak inside that window adds another 2-3×. A global consumer product smears the peak across timezones and lands at 2-3×. It is wrong for single-region consumer apps (3-5×), for B2B where ten business hours carry 95% of load (4-8×), for cron-triggered work where everything fires at :00 (10-100×), and for event-driven load like ticket sales or a marketing push where the ratio can be 100-1000× and marketing controls the trigger.
**Follow-up trap:** *"Which peak sizes which component?"* Peak sustained over an hour sizes the fleet and the database, because those are what autoscaling and provisioning track. Peak burst over a second sizes the queue depth, connection pool, and rate limiter, because those absorb what the fleet cannot. Peak concurrent (Little's Law: throughput × latency) sizes memory, file descriptors, and WebSocket capacity. Using the wrong one is how you get a correctly-sized fleet behind an undersized connection pool.

### Q12 — You're mid-answer and realise you divided by 86,400 instead of multiplying. What do you do?
**Testing:** composure and the recovery script.
**Answer:** Say it immediately, in specific terms: "I inverted the conversion. Let me redo it: 5 × 10⁷ per day over 10⁵ seconds is 500 per second, not 5 × 10¹²." Then name what the corrected number changes, which is usually one decision: "500 write QPS means one Postgres primary, so the sharding I was about to describe is unnecessary." Keep the wrong number visible and crossed out, because that shows the derivation survived the correction. Then state the check that would have caught it: 1M/day ≈ 10/s, so any per-day-to-per-second conversion can be verified in one step.
**Follow-up trap:** *"Doesn't a basic arithmetic slip worry me?"* It should worry you less than the alternative, which is a candidate who does not sanity-check and builds a sharded architecture on a 10⁹× error. The habit that matters is the check, not the flawless multiplication, and in production this is exactly why capacity plans get reviewed. What should worry you is a candidate who cannot tell you which of their numbers they are least confident in.

### Q13 — Give me a number you would refuse to estimate.
**Testing:** knowing the limits of the technique. Almost nobody has an answer prepared.
**Answer:** p99.9 latency of anything, and anything driven by variance rather than volume. Estimation composes averages and multipliers; tail latency comes from queueing dynamics under bursty arrival, GC pauses, lock contention, noisy neighbours, and retry amplification, none of which are multiplicative. I will happily estimate mean throughput and total bytes; I will not estimate p99.9 or the knee of a latency curve, and if a design's viability depends on either I will say it needs a load test rather than arithmetic. Same for anything within 2-3× of a hard cliff: a memory limit, a provider rate limit, or an SLO boundary.
**Follow-up trap:** *"So how do you make a decision before you can measure?"* Estimate the mean, then design so the tail cannot hurt you regardless of its value: a timeout well inside the budget, a bulkhead so one slow dependency cannot consume the fleet, a queue so bursts become latency instead of errors, and a load-shedding rule. Design for tail-insensitivity rather than trying to predict the tail. That is the honest answer and it is also what senior engineers actually do.

### Q14 — Convert 99.99% availability into something a design decision can use.
**Testing:** whether the nines table is instant.
**Answer:** 52.6 minutes per year, 4.3 minutes per month. Four minutes a month means no human is in the recovery path: detection plus failover has to be automatic and fast, which implies multi-AZ with health-checked automatic failover, and it implies your deploy pipeline is now a primary risk since a bad deploy plus a manual rollback exceeds the entire monthly budget. Then the composition rule: serial dependencies multiply, so five components at 99.9% in series is 0.999⁵ ≈ 99.5%, or 43 hours a year. Four nines end to end over five hops needs ~99.998% per hop, or redundancy at each hop.
**Follow-up trap:** *"We have five services each at 99.99%. What's our SLO?"* About 99.95% if they are strictly serial and independent, which is 4.4 hours a year rather than 53 minutes, and independence is usually false anyway since they share a network, a control plane, and a deploy pipeline. Correlated failure means the real number is worse than the arithmetic. The fix is to remove hops from the critical path (cache, precompute, make calls optional with a fallback) rather than to try to make five hops each more reliable.

### Q15 — I'll give you 30 seconds. Rough QPS and storage for a URL shortener at 100M new links a day.
**Testing:** speed, and whether you catch the asymmetry.
**Answer:** Writes: 10⁸/day ÷ 10⁵ = 1,000 write QPS average, ~3,000 peak. Reads at a 10:1 redirect ratio: 10,000 QPS average, ~30,000 peak. Storage: ~500 B per row (short code, long URL up to ~2 KB but average ~100 B, plus owner, timestamps, and an index) → 10⁸ × 500 B = 50 GB/day, ~18 TB/year, ×3 replication ≈ 55 TB/year. Key space: base62 at 7 characters is 62⁷ ≈ 3.5 × 10¹², which at 10⁸/day lasts ~35,000 × 10³ days, so 7 characters is comfortably enough and 6 (5.7 × 10¹⁰) gives only ~570 days.
**Follow-up trap:** *"10,000 read QPS against 55 TB. What's the actual design?"* The asymmetry is the design: reads are point lookups on an immutable key, so this is a cache problem, not a database problem. Redis or a local in-process cache in front of a simple KV store, with a very high hit rate because link popularity is heavily Zipfian (a small fraction of links get almost all redirects). The database is then sized for writes and cold misses, and the interesting engineering is the key-generation scheme (pre-allocated ranges per node beats a central counter, and beats hashing because hashing needs collision handling).

### Q16 — What is the single most useful number in this whole module?
**Testing:** prioritisation.
**Answer:** `1 million per day ≈ 10 per second`. Almost every traffic estimate is one step from that conversion, it is impossible to get the exponent wrong with it, and it makes the sanity check automatic: if someone says a 10M-user product needs a million QPS, that is 10¹¹ requests a day, or 10,000 per user per day, which is visibly absurd. Second most useful is `same-datacenter round trip ≈ 0.5 ms`, because it is the unit that makes every latency budget decomposable into hops.
**Follow-up trap:** *"And the most dangerous number?"* Any average of a heavy-tailed quantity: average followers, average file size, average tenant size, average request cost, average prompt length. Those means are usually smaller than the values that actually determine your capacity, so an estimate built on them understates the peak in exactly the case where the peak is what breaks. When a quantity is power-law shaped, say you want a percentile and that the mean will mislead.

---

## Red flags that fail you

- Producing a number and never using it.
- Quoting the 2009 Jeff Dean latency table verbatim, including 150 µs for an SSD read.
- Sizing anything on average instead of peak.
- Multiplying instead of dividing by 86,400 and not noticing.
- Doing precise long division on stage instead of rounding to powers of ten.
- No sanity check against any known system.
- Computing API-level write QPS and never computing the amplified fanout number.
- Sizing a cache from payload bytes with no allowance for per-key overhead.
- Sizing a fleet at 90-100% utilisation.
- Forgetting replication factor and index overhead in a storage estimate.
- No cost number anywhere in 2026, or a cost number with no dominant line item named.
- Defending a wrong assumption instead of walking the branch.
- Treating a mean as meaningful for a power-law quantity.
- Saying "it's just an estimate" as an excuse rather than naming the sensitivity.

## Cheat card

```
PROCEDURE   declare what it DECIDES → assume out loud → round to 1e → compute
            → AMPLIFY by fanout → sanity-check vs a known system → use it

CONVERSIONS 1M/day ≈ 10/s      1B/day ≈ 10,000/s      86,400 s/day → 1e5
            2^10 KB · 2^20 MB · 2^30 GB · 2^40 TB · 2^50 PB
            1 hour of 1080p @5 Mbps ≈ 2.25 GB   ·   1 token ≈ 4 chars

LATENCY     L1 1ns · L2 4ns · L3 12ns · RAM 60ns · NVMe rand 20-100us
            same-DC RTT 0.5ms · cross-AZ 1-2ms · US-EU 80ms · US-APAC 200ms
            LLM first token 300-800ms
            RAM ~1000x SSD · same-DC RTT ~1000x RAM · cross-continent ~200x same-DC
            fibre: 5 us/km → ~1 ms per 100 km one-way after routing

THROUGHPUT  NVMe 3-7 GB/s, 500k IOPS · gp3 125 MB/s / 3k IOPS baseline (40x slower!)
            100 GbE = 12.5 GB/s · Postgres 5-20k write TPS · Redis 100k ops/s
            JSON service ~2k rps/core · Cassandra partition ~1-3k writes/s

BYTES       UUID 16B bin / 36B text · int64 8B · narrow row 40-60B
            entity row ~500B · Redis per-key overhead 50-100B  ← the cache trap
            zset >128 members flips listpack→skiplist: ~40B becomes ~100B/member
            1024-dim fp32 vector 4KB (int8 1KB, binary 128B)

PEAK/AVG    global consumer 2-3x · single region 3-5x · B2B 4-8x
            cron 10-100x · launch/event 10-1000x
            SIZE AT 60% UTIL: M/M/1 wait = service x rho/(1-rho); rho=.9 → 9x
            Little's Law: concurrency = throughput x latency

SPLITS      feed 100:1 R:W · messaging 1:1 · commerce 20:1 · ASK, don't assume
            80/20 keys, but Zipf: 80%→95% hit rate costs far more than 1.2x memory
            hottest single key can be 1-5% of ALL traffic (hash won't fix it)
            AMPLIFIED WRITE = logical writes x fanout   ← the number that breaks

NINES       99% 3.65d/yr · 99.9% 8.8h · 99.99% 53min · 99.999% 5min
            serial deps MULTIPLY: 5 x 99.9% = 99.5% = 43h/yr

STORAGE     records x bytes x retention x replication x (1 + index) + WAL/backups

COST 2026   egress $0.05/GB list, $0.005-0.01 negotiated  ← often the top line item
            LLM ~$2/$10 per M in/out (Sonnet-class); cache reads ~10% of input
            Flash-class ~$0.10/$0.40 (≈20x cheaper) · Batch API -50%
            r7g.8xlarge (256 GB) ~$1.7/hr ≈ $1,240/mo

RECOVERY    name it precisely → don't restart → identify the ONE decision it feeds
            → walk the branch you pre-named → say what you'd measure
            PRE-EMPT: state every assumption WITH its sensitivity ("if 10x off, I'd...")
```

## Sources

- [Latency Numbers Every Programmer Should Know (Bonér gist, after Jeff Dean)](https://gist.github.com/jboner/2841832) — accessed 2026-07-26
- [Latency Numbers You Should Know in 2026 — Omar Bohsali](https://omarish.com/latency-numbers-you-should-know) — accessed 2026-07-26
- [What Is NVMe Latency? Performance Benchmarks Explained — simplyblock](https://simplyblock.io/glossary/nvme-latency/) — accessed 2026-07-26
- [Azure network round-trip latency statistics — Microsoft Learn](https://learn.microsoft.com/en-us/azure/networking/azure-network-latency) — accessed 2026-07-26
- [Back-of-the-envelope Estimation — ByteByteGo](https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation) — accessed 2026-07-26
- [The 5-Step Capacity Estimation Worksheet — DesignGurus](https://designgurus.substack.com/p/the-5-step-capacity-estimation-worksheet) — accessed 2026-07-26
- [QPS Estimation Error: Average vs Peak Multiplier — TheCodeForge](https://thecodeforge.io/system-design/qps-queries-per-second/) — accessed 2026-07-26
- [System Design Interviews Changed in 2026 — DesignGurus](https://designgurus.substack.com/p/system-design-interviews-changed) — accessed 2026-07-26
- [LLM API Pricing (July 2026) — TLDL](https://www.tldl.io/resources/llm-api-pricing) — accessed 2026-07-26
- [LLM API Pricing Comparison In 2026 — CloudZero](https://www.cloudzero.com/blog/llm-api-pricing-comparison/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
