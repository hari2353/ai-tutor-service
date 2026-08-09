# Weekend 6 — The Craft of System Design: Estimation, Diagramming, Method

This weekend decides interviews because the 45-minute design round is scored on *process*, not knowledge — candidates with more facts and less structure lose to candidates who move through requirements → numbers → API → data → architecture → scale → failure in order and narrate every transition.

## Back-of-Envelope: Guesstimates, Latency/Throughput/Storage Math

**30-sec:** Estimation is a four-step procedure, not a talent: state the assumption out loud, round to a power of ten, compute in one pass, sanity-check against a system whose scale is public. You need ~15 memorised numbers and one habit — announce what each number *decides* before computing it. Precision is not the point: within one order of magnitude is a pass, within 3× is indistinguishable from correct, because the decision it feeds only has a handful of discrete outcomes. Interviewers watch whether your peak is *derived* from your average, and whether you catch and recover from a bad assumption mid-answer.

**Procedure:** declare what it decides → assume out loud → round to 1e → compute → amplify by fanout → sanity-check vs a known system.

**Conversions:** 1M/day ≈ 10/s. 1B/day ≈ 10,000/s. 86,400s/day → 1e5. 1 token ≈ 4 chars.

**Latency ladder:** L1 1ns · L2 4ns · L3 12ns · RAM 60ns · NVMe random 20–100μs · same-DC RTT 0.5ms · cross-AZ 1–2ms · US–EU 80ms · US–APAC 200ms · LLM first token 300–800ms. RAM is ~1000× SSD; same-DC RTT is ~1000× RAM.

**Peak/avg ratios:** global consumer 2–3× · single region 3–5× · B2B 4–8× · cron 10–100× · launch/event 10–1000×. Hottest single key can be 1–5% of *all* traffic — hashing won't fix that.

**Nines:** 99% = 3.65d/yr · 99.9% = 8.8h · 99.99% = 53min · 99.999% = 5min. Serial dependencies *multiply*: 5 services at 99.9% = 99.5% = 43h/yr.

**Recovery from a wrong assumption:** name it precisely → don't restart → identify the one decision it feeds → walk the branch you pre-named → say what you'd measure.

## How to Draw a System: C4, Sequence, Dataflow, Deployment

**30-sec:** Four diagram types answer four different questions — C4 answers "what exists and where does it live" (interviews almost always want level 2, container), sequence answers "what happens in order," dataflow answers "how does data transform," deployment answers "what infrastructure runs it." The single most common failure is one diagram trying to be all four, where a box could be a service, a library, a process, or a machine. Discipline: pick a type, announce it, cap at 12–15 boxes, label every edge with protocol + sync/async, draw the happy-path read end to end first.

**C4 levels:** L1 context (5–8 boxes, only if scope is contested) · L2 container (8–15 boxes) — *the* interview diagram · L3 component (deep dive only) · L4 code — never.

**Edge grammar:** protocol/format · sync|async · payload · rate-or-latency. Solid = sync (sums into the latency budget); dashed = async (needs at-least-once + idempotent consumer).

**Scale pass (second pass only):** rate on hot edges, size on stateful boxes, replica counts ("×12, 3 AZ"), bottleneck double-boxed with its binding constraint, partition key on every sharded store, and a "not drawn:" line converting omissions into explicit scoping decisions.

**Leave out and say once, don't draw:** authn/authz, observability, CI/CD, DNS/TLS, secrets, internal LBs, mesh sidecars, individual replicas.

## Designing From Scratch: Requirements → Constraints → API → Data → Scale → Failure

**30-sec:** A design round is a 45-minute test of whether you can drive an underspecified problem to a defensible design, scored on the *sequence* you moved through, not the final diagram. Restate the problem → separate FR from NFR → convert every vague ask into a number → write the API contract → design the data model → only then draw the architecture → scale it against your own numbers → break it on purpose. The two failure modes that sink most candidates are both timing failures: 20 minutes on requirements leaving no time to scale, or boxes on the board at minute 3 with every later decision unjustified.

**Time budget (45 min):** 0–2 restate · 2–7 requirements (3–5 FRs capped, NFR table) · 7–12 numbers (3 you'll use, say what each decides) · 12–17 API (Idempotency-Key, cursor not offset, 202=async) · 17–24 data model (partition key + row bytes) · 24–32 architecture (read path, then write, then async) · 32–38 scale (rank the bottlenecks) · 38–43 failure (kill each box) · 43–45 wrap.

**NFR checklist:** Scale · Consistency · Availability · Latency · Durability · Cost · Multi-tenancy (SCALD-CoM).

**Hard rules:** no box appears before the requirement or number that produced it; every named component gets one number (size/TTL/partitions/key); a wrong assumption at minute 30 means walking the branch you already named, not restarting.

**Highest-value volunteered sentence:** named failure mode + observable symptom + mitigation — e.g. "cold-cache thundering herd → Cassandra p99 spike → single-flight + jittered warm-up."

## If you remember nothing else

1. Estimation is a procedure (assume→round→compute→sanity-check), not a talent — within 1 order of magnitude is a pass, 3× is fine.
2. Peak must be *derived* from average via a stated ratio (2–3× consumer, up to 1000× for launches), never guessed independently.
3. Serial dependencies multiply availability down: five 99.9% services in series = 99.5% (43h/yr downtime).
4. Draw one diagram type at a time — mixing them is the single most common whiteboard failure. C4 level 2 (container) is the default.
5. Cap every diagram at 12–15 boxes; everything left out gets said once out loud, never drawn.
6. A wrong assumption mid-design gets walked to its named consequence, never a restart — that recovery *is* the signal being scored.
7. No box goes on the board before the number or requirement that justifies it — architecture must be on the board by minute 32, no exceptions.
8. The highest-value sentence in any design round: failure mode → observable symptom → mitigation, stated unprompted.

## Numbers table

| Fact | Value |
|---|---|
| 1M requests/day / 1B requests/day | ≈10/s / ≈10,000/s |
| RAM vs NVMe random read | 60ns vs 20–100μs |
| Same-DC RTT vs cross-continent | 0.5ms vs 80–200ms |
| LLM time-to-first-token | 300–800ms |
| Peak:avg — global consumer / B2B / launch | 2–3× / 4–8× / 10–1000× |
| Nines: 99.9% / 99.99% / 99.999% downtime/yr | 8.8h / 53min / 5min |
| 5-service chain at 99.9% each | 99.5% (43h/yr) |
| Diagram box cap | 12–15 |
| C4 container diagram whiteboard time | ~8 min |
| Design round time budget | 5/5/5/7/8/6/5/2 min across phases (~45 total) |
| NVMe throughput / EBS gp3 baseline | 3–7 GB/s, 500k IOPS / 125 MB/s, 3k IOPS |
| 1024-dim fp32 vector size | 4KB (int8: 1KB, binary: 128B) |
