# GCP Storage & Databases Deep: GCS, Cloud SQL, Spanner, Bigtable, Firestore, AlloyDB

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** C-GCP-iam · **Updated:** 2026-08-23
> **Module id:** `C-GCP-storage-db` · **Tags:** storage,critical

## The 30-second version

Six stores, one decision axis each: **GCS** is object storage where the game is class economics — Standard versus Nearline (30-day minimum), Coldline (90-day), Archive (365-day), or Autoclass letting access patterns decide. **Cloud SQL** is stock PostgreSQL/MySQL/SQL Server managed on VMs — the default answer until performance or scale says otherwise. **AlloyDB** is PostgreSQL-compatible with a disaggregated storage layer claiming ~4× transactional and up to 100× analytical speedups via its columnar engine. **Spanner** buys globally consistent ACID with hardware clocks: TrueTime bounds clock uncertainty to roughly a few milliseconds (worst-case bound ~7ms) and commit-wait converts that into external consistency — the thing CockroachDB approximates with hybrid logical clocks but cannot strictly guarantee without atomic-clock infrastructure. **Bigtable** is the petabyte-scale wide-column store whose entire performance story is row-key design (monotonic keys hot-spot; hashed/padded keys distribute). **Firestore** is the serverless document database with multi-region 99.999%-class availability. Pick by consistency requirement, scale ceiling, and access pattern — not by familiarity.

## Why this gets asked

Because database choice is where architecture interviews get concrete fast. The Spanner question has a precise technical core interviewers love: *how does it offer strict serializability globally without waiting on consensus everywhere* — the answer is TrueTime's bounded uncertainty plus commit-wait that usually overlaps Paxos quorum latency, and whether you can contrast it honestly with CockroachDB's HLC approach separates distributed-systems literacy from product familiarity. The GCS question probes cost intuition (early-deletion fees making wrong-class choices more expensive than Standard). The Bigtable question is almost always row-key design under load — "your writes cluster on one node, what did you do wrong?" And the Cloud SQL versus AlloyDB question checks whether you know AlloyDB is PostgreSQL-wire-compatible with a different storage engine underneath, not just "expensive Cloud SQL."

---

## Lineage: past → present → future

**What came before.** Google's internal lineage is Megastore and Bigtable: Megastore (2000s-era App Engine backing) offered synchronous replication across zones with an eventually-consistent flavor and painful cross-entity-group transactions; Bigtable (2006 paper) proved wide-column scale but offered only row-level atomicity. Spanner (OSDI 2012, public 2017) was the answer to "what if we wanted both global scale *and* strong transactions" — the insight being that bounded clock uncertainty (GPS receivers plus atomic clocks in every datacenter) turns time itself into a coordination primitive. On the relational side, Cloud SQL launched as straightforwardly managed MySQL/PostgreSQL because most enterprises needed nothing fancier; the pain points were its VM-shaped ceilings — vertical scale limits and analytics requiring ETL out.

**Where it stands now.** Spanner is the reference point every other geo-distributed SQL database measures against; the honest current comparison has CockroachDB offering serializability with HLC timestamps (no real-time ordering guarantee across nodes — the "new enemy problem" literature documents the difference), TiDB using a centralized timestamp oracle, and Spanner remaining the only one with hardware-bounded uncertainty. AlloyDB (GA 2022) fills the "Cloud SQL hit a wall" gap: same wire protocol, disaggregated log-structured storage, columnar engine for HTAP, ScaNN-based vector search, up to 128 TiB clusters (~). GCS added soft delete (default 7 days retention of deleted objects, ~) and Autoclass matured into a credible set-and-forget tiering policy. Firestore absorbed Firebase's realtime semantics and remains the default mobile/serverless document store with multi-region configurations targeting 99.999% availability. [Spanner TrueTime and external consistency](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency); accessed 2026-08-23. Live disagreement: whether HTAP-in-one-database (AlloyDB columnar engine) beats dedicated warehouse pipelines — at small-to-medium analytic volume it clearly wins on ops cost; at BigQuery scale the columnar engine isn't the tool.

**Where it's heading.** High confidence: vector search becoming table stakes in every operational store (AlloyDB AI's ScaNN indexes, Spanner vector types, Firestore vector support) as RAG moves into OLTP estates. High confidence: Spanner continuing to grow cheaper entry tiers (smaller instance shapes) to capture workloads that previously defaulted to Cloud SQL. Medium confidence: disaggregated-storage architectures becoming the norm across the relational line, blurring Cloud SQL/AlloyDB boundaries upward. Speculative: TrueTime-class precision trickling to commodity clouds via better NTP/PTP — if uncertainty bounds shrink enough without atomic clocks, Spanner's moat narrows; nobody should claim this has happened yet.

## Mental model

One decision tree covers the estate:

```
WHAT'S THE ACCESS SHAPE?
 ├─ blobs/files, ms-latency reads, no queries      -> GCS
 │    └─ access pattern?  hot -> Standard | ~monthly -> Nearline (30d min)
 │                         ~quarterly -> Coldline (90d) | yearly -> Archive (365d)
 │                         unknown -> Autoclass
 ├─ relational rows
 │    ├─ one region, modest scale                  -> Cloud SQL (stock engines on VMs)
 │    ├─ PostgreSQL + heavy OLTP/HTAP/vector       -> AlloyDB (disaggregated storage,
 │    │                                              columnar engine, read pool)
 │    └─ global strong consistency / horizontal writes -> Spanner (TrueTime+Paxos)
 ├─ key/value at petabyte scale, single-digit-ms   -> Bigtable (row-key design!)
 └─ hierarchical documents, offline sync, serverless -> Firestore
```

And the Spanner mechanism as a picture:

```
TrueTime API: TT.now() -> [earliest, latest], uncertainty ε (~1-7ms typical)

WRITE COMMIT:
  1. pick commit_ts = TT.now().latest
  2. replicate via Paxos quorum            <- network time overlaps...
  3. commit-wait until TT.now().earliest > commit_ts   <- ...the wait!
  4. ack client
=> any later transaction anywhere gets a LARGER timestamp
=> external consistency without extra consensus rounds

CockroachDB: HLC on commodity clocks - serializable, but "later in wall-clock"
             is only guaranteed per-node; no atomic-clock bound. Different
             guarantee, usually fine, occasionally not.
```

## How it actually works

### GCS: classes, minimums, and Autoclass mechanics

All classes share one API and millisecond access latency — there's no restore step like AWS archive tiers. The economics live in three numbers per class: storage price, retrieval price, minimum storage duration. Standard ~$0.02–0.026/GB-month with no retrieval fee; Nearline ~$0.010–0.016 with $0.01/GB retrieval and a **30-day** minimum; Coldline ~$0.004–0.007 with $0.02/GB retrieval, **90-day** minimum; Archive ~$0.0012–0.0025 with $0.05/GB retrieval, **365-day** minimum (regional variation applies). Deleting or reclassifying before the minimum triggers early-deletion fees — which is how a "cheap" lifecycle rule costs more than doing nothing.

Lifecycle rules transition by age/prefix/class conditions; up to 100 rules per bucket (~). **Autoclass** replaces guessing with observation: objects ≥128 KiB not accessed for 30 days move toward Nearline (default terminal class) or onward to Coldline at 90 days and Archive at 365 days when the terminal class is Archive; any access moves the object back to Standard. Access tracking counts `get`-method reads only. Autoclass charges a management fee plus one-time enablement charge but waives retrieval and early-deletion fees — designed so misprediction is cheap. Objects below 128 KiB never transition (fees would dwarf savings).

### Cloud SQL vs AlloyDB: what actually differs

Cloud SQL runs stock engines on Compute Engine VMs with managed backups, replicas, and maintenance. Enterprise Plus editions add data cache (local-SSD caching layer) and higher machine shapes for PostgreSQL. It's the right default until you hit its ceilings: vertical scale limits and analytics that must ETL out.

AlloyDB keeps PostgreSQL wire compatibility (versions 14–18 supported) but replaces the storage engine: a disaggregated, log-structured distributed storage layer with synchronous replication below the instance, ultra-fast caching, and a read pool of 1–20 nodes (~). Google's published claims: more than 4× faster transactional throughput versus standard PostgreSQL and up to 100× on analytical queries via the columnar engine, which maintains an in-memory columnar replica of chosen tables updated transactionally — HTAP without ETL. AlloyDB AI adds ScaNN-based vector indexes (claimed 2–10× faster than pgvector HNSW, ~) and embeddings integration. Clusters scale to ~128 TiB (~); instances are private-IP-only by design; PITR to 35 days. The honest caveat: those multipliers are Google's benchmarks against *unoptimized* standard PostgreSQL — your mileage depends entirely on whether your bottleneck was the engine or the disk underneath it.

### Spanner: TrueTime, Paxos, and where the latency goes

Data lives in tablets (key ranges) owned by Paxos groups replicated across zones (regional instances: 3 zones; multi-region: more, with witness replicas). The leader serializes writes via two-phase locking, replicates through Paxos quorum, assigns commit timestamp `TT.now().latest`, then **commit-waits** until `TT.now().earliest > commit_ts` before acknowledging. Because Paxos quorum communication happens in parallel with the wait, the uncertainty window is usually already absorbed — Google's own writeup stresses that most of the time commit-wait adds no extra latency beyond what replication cost anyway. Observed orders of magnitude: single-digit-millisecond local reads (~5ms ~), cross-zone commits tens of milliseconds (~50–100ms p99 ~), multi-region writes higher.

Reads come in flavors matching the dial: strong reads go through the timestamp machinery; stale/bounded-staleness snapshot reads at a past timestamp avoid locks entirely — because every committed transaction waited its timestamp into the global past, reading slightly behind `now().earliest` is guaranteed consistent without coordination. This is why Spanner can serve consistent reads from any replica anywhere.

The CockroachDB contrast, precisely: CRDB uses hybrid logical clocks on commodity hardware. It provides serializability but not *external* consistency — a transaction committing on node A after one commits on node B is only guaranteed ordered if clocks happened to agree closely enough; the "new enemy" anomaly class exploits exactly this gap. For most workloads the difference never surfaces; for audit-grade ordering ("this trade definitely executed after that one in wall-clock time") it can.

### Bigtable: row keys are the architecture

Bigtable scales by splitting the key space across servers (tablets). Everything follows from that: a monotonically increasing key (`timestamp-prefixed`, sequential IDs) routes writes to one tablet → one node saturates while the rest idle. The fixes are canonical: hash or reverse the high-cardinality component, salt hot prefixes, pad identifiers to fixed width for even distribution. Throughput scales roughly linearly with nodes (ballpark ~10k QPS per SSD node as a sizing heuristic, ~), latency stays single-digit milliseconds when keys distribute well. Replication supports multi-cluster routing for availability or isolation. It is not relational: no cross-row transactions (only single-row atomic mutations), no secondary indexes — you design tables around query patterns up front, denormalizing freely. Google Analytics-scale lineage; your billing pipeline probably qualifies, your product catalog doesn't.

### Firestore: documents with serverless semantics

Hierarchical document collections with real-time listeners, offline sync for mobile, and ACID transactions within constraints (transaction scope limited by design to keep them fast). Serverless pricing per read/write/storage with generous free tiers; multi-region locations (nam5/eur3) target 99.999% availability (~). TTL policies delete expired docs automatically. Its ceiling: queries are index-driven and constrained — no joins, aggregation limits, 1 MiB per-document cap (~). Beyond modest analytic needs you export to BigQuery. It shines exactly where Cloud Run functions live: per-user state at serverless scale with zero capacity management.

## Build it from scratch

A storage-class break-even calculator plus the Spanner commit-wait simulation:

```python
# untested sketch
def annual_cost(gb, cls_price_per_gib_mo):
    return gb * cls_price_per_gib_mo * 12

def best_class(accesses_per_year, gb=1000,
               prices={"STANDARD": 0.023, "NEARLINE": 0.013,
                       "COLDLINE": 0.006, "ARCHIVE": 0.002},
               retrieval={"STANDARD": 0.0, "NEARLINE": 0.01,
                          "COLDLINE": 0.02, "ARCHIVE": 0.05}):
    return min(prices, key=lambda c:
        annual_cost(gb, prices[c]) + accesses_per_year * gb * retrieval[c])

def spanner_commit_wait(epsilon_ms=7):
    """Commit-wait = wait until earliest > commit_ts (= latest at pick time).
    Expected extra wait ~ epsilon - (time spent in Paxos round)."""
    import random
    paxos_ms = random.uniform(2, 8)          # overlaps the wait window
    return max(0, epsilon_ms - paxos_ms)     # often 0: wait hidden in quorum RTT
```

Provisioning reality check:

```bash
# Lifecycle tiering done right - respect minimums or pay early-deletion fees
gcloud storage buckets update gs://logs --lifecycle-file=lifecycle.json

# Spanner: regional, 1 node to start; add nodes for throughput, watch CPU <50%
gcloud spanner databases create prod-db --instance=prod-inst

# Bigtable table with a HASHED key prefix designed upfront
cbt createtable events splits=row-000,row-400,row-800
```

## How it's done in production

Standard estate: GCS buckets Terraform-managed with Autoclass on uncertain patterns and explicit lifecycle on known ones; versioning + soft delete on anything user-facing. OLTP defaults to Cloud SQL with HA + PITR; AlloyDB where analytics-on-operational-data or heavy vector workloads justify it; Spanner reserved for genuinely global or horizontal-write requirements (financial ledgers, multi-region SaaS control planes). Bigtable for telemetry/clickstream/metrics at volume with pre-designed keys. Firestore for mobile/serverless app state. Every store wrapped in VPC Service Controls perimeters and CMEK where compliance requires.

| Symptom | Cause | Fix |
|---|---|---|
| GCS bill higher than all-Standard baseline | Early-deletion fees from wrong-class lifecycle | Respect 30/90/365 minimums; use Autoclass when unsure |
| Spanner writes slow across regions | Commit-wait + quorum geography inherent | Regionalize data placement/interleaving; measure before blaming platform |
| Bigtable one node at 100% CPU, rest idle | Monotonic/hot row-key prefix | Salt/hash key component; redesign before scaling out |
| AlloyDB slower than promised | Bottleneck wasn't storage I/O; columnar engine not engaged | Check columnar engine coverage of queried tables; benchmark against tuned PG |
| Firestore costs exploded | Chatty listeners / N+1 doc reads | Batch gets, cache client-side, move aggregates to scheduled exports |
| Cloud SQL replica lag hours behind | Single-threaded replay of heavy write bursts | Right-size primary, offload long transactions, consider AlloyDB read pool |

## Tradeoffs & when NOT to use it

- **Don't reach for Spanner because "strong consistency" sounds good** — single-region Cloud SQL already gives you strong consistency cheaper; Spanner buys *global* consistency and horizontal write scale, and you pay for both even when using neither.
- **Don't use Bigtable for relational access patterns** — secondary-index-less design means every new query shape is a table redesign. If queries evolve, Firestore-with-exports or a real RDBMS wins despite lower raw throughput.
- **Autoclass is not free correctness** — management fees on huge hot buckets can exceed the tiering savings; if 95% of data is genuinely hot, Standard with lifecycle-only-for-cold-tail is simpler and cheaper.
- **AlloyDB's multipliers are benchmarks, not contracts** — against a well-tuned PostgreSQL on fast storage the gap narrows; the durable advantages are the read pool, columnar engine convenience, and SLA (99.99% including maintenance ~), not automatic speed.
- **Firestore is wrong for anything join-shaped or analytics-heavy** — its index model makes "simple" relational queries expensive or impossible; exporting to BigQuery is the escape hatch, not a workaround to rely on daily.
- **Cloud SQL is wrong when writes must scale horizontally** — read replicas don't distribute writes; if write throughput is the wall, that's Spanner's door, not a bigger Cloud SQL instance.

---

## Interview questions

### Q1 — How does Spanner deliver external consistency? Include the mechanism, not just the term.
**Testing:** distributed-systems depth under a product name.
**Answer:** TrueTime reports time as an interval [earliest, latest] with uncertainty ε bounded by GPS+atomic-clock infrastructure (typically low single-digit ms, worst-case bound ~7ms). A committing transaction takes `commit_ts = TT.now().latest`, replicates via Paxos, then commit-waits until `TT.now().earliest > commit_ts` before acknowledging. That wait guarantees no later transaction anywhere can receive an earlier timestamp, so timestamp order equals real-time order: external consistency (strict serializability). Because Paxos quorum communication overlaps the wait window, the added latency is usually near zero beyond replication cost itself.
**Follow-up trap:** *"So every write pays 7ms extra?"* — no: the wait runs in parallel with Paxos round-trips; only when quorum finishes faster than ε does any residual wait exist. The cost shows up as bounded worst-case, not constant overhead.

### Q2 — CockroachDB claims Spanner-like guarantees without atomic clocks. What actually differs?
**Testing:** whether they can compare honestly instead of repeating marketing from either side.
**Answer:** CRDB uses hybrid logical clocks on commodity hardware and delivers serializability plus snapshot reads, but not external consistency: ordering across nodes depends on clock agreement within uncertainty bounds that aren't hardware-enforced, leaving anomalies where wall-clock-later transactions get earlier timestamps across nodes (documented "new enemy" class). For most applications irrelevant; for audit-grade real-time ordering it's a genuine semantic gap. CRDB counters with portability (any cloud/bare metal) versus GCP-only managed Spanner.
**Follow-up trap:** *"Which would you pick for a fintech ledger?"* — if the ledger must be globally consistent with real-time ordering evidence and lives on GCP anyway: Spanner. If multi-cloud deployment dominates and serializability suffices: CRDB defensibly. State which guarantee the regulator actually requires.

### Q3 — Your GCS costs tripled after enabling lifecycle rules. Diagnose.
**Testing:** class-economics fluency.
**Answer:** Almost certainly early-deletion fees: objects transitioned into Nearline/Coldline/Archive classes deleted before their 30/90/365-day minimums incur charges for remaining days, and reclassifying hot objects back to Standard incurs retrieval fees per GB. Also check rule interactions — overlapping transitions churn classes repeatedly. Fix: align transitions with actual minimums, use Autoclass for unpredictable patterns (it waives retrieval/early-deletion fees by design), audit with storage-class distribution metrics.
**Follow-up trap:** *"When would Autoclass be the wrong answer?"* — uniformly hot buckets (management fee buys nothing) or compliance-mandated fixed retention schedules where deterministic lifecycle beats observation-based transitions.

### Q4 — Bigtable: writes cluster on one node at 100% CPU while the cluster idles. What happened and what do you do?
**Testing:** the row-key design instinct that defines Bigtable competence.
**Answer:** The key space isn't distributing: a monotonically increasing component (timestamp prefix, sequential ID) routes all new writes to one tablet. Fixes in order: hash or reverse a high-cardinality key component, salt hot prefixes (e.g., `hash#id#timestamp`), pad variable-length identifiers so lexicographic order distributes evenly. Scaling nodes out does nothing — tablets don't split under single-hotspot load. Prevention is schema review before launch; the split points you choose at table creation are your first defense.
**Follow-up trap:** *"Why not just add nodes anyway?"* — because the bottleneck is one tablet on one server; extra nodes take idle tablets. You'd pay linearly for zero throughput gain until the hotspot itself splits, which monotonic keys prevent.

### Q5 — Cloud SQL vs AlloyDB for a PostgreSQL app hitting 90% CPU on its primary. Walk through the decision.
**Testing:** whether upgrade paths are understood as engineering choices.
**Answer:** First ask what's saturated: if it's read load, Cloud SQL read replicas may suffice (accepting replication lag). If write/CPU-bound with VM-shaped ceilings, AlloyDB offers: disaggregated storage removing I/O bottlenecks, bigger compute shapes, read pool up to ~20 nodes for horizontal reads, data caching, and if any queries are analytical, the columnar engine offloads them without ETL. Wire compatibility means no application changes. Counterweights: higher cost, private-IP-only networking to plan for, and multipliers being benchmark claims rather than promises.
**Follow-up trap:** *"Why not just scale Cloud SQL vertically?"* — you can, until edition ceilings; vertical scaling also carries failover-sized cost 24/7 and doesn't fix storage-layer throughput. Knowing *which* ceiling you hit decides between the paths.

### Q6 — Design global user-profile storage: users worldwide, low-latency reads everywhere, strong consistency on updates.
**Testing:** Spanner vs alternatives synthesis.
**Answer:** Spanner multi-region instance with the profile table primary-regioned near write traffic; reads served strong from nearby replicas or bounded-staleness where UX allows. Alternative honestly considered: Firestore multi-region (99.999%-class) if access is document-shaped and transactions simple — cheaper at small scale, weaker query power; Cassandra/Bigtable rejected immediately because tunable/eventual consistency fails "strong on update." Schema note: interleave dependent rows (profiles↔settings) for locality; watch hotspots on sequential user IDs.
**Follow-up trap:** *"What does this cost versus regional Postgres?"* — multiples; make the interviewer see you'd price it: if actual users concentrate in one region, a regional database plus CDN-cacheable reads beats Spanner economics every time. Global consistency is a requirement check, not a default.

### Q7 — Explain GCS consistency and why there's no "eventual" footnote anymore.
**Testing:** historical literacy prevents cargo-cult caveats.
**Answer:** GCS has offered strong read-after-write consistency globally since 2010 (the old US-only eventual window closed years ago): once a write returns, any reader anywhere sees it, including list operations. Object metadata and ACLs included. What remains non-transactional: no cross-object atomicity — multi-object coordination belongs in your application or a different store.
**Follow-up trap:** *"So can I use GCS as a queue?"* — technically consistent, practically wrong tooling: listing costs, latency floors, no consumer semantics. Pub/Sub exists; reach for it.

### Q8 — Where does Firestore break, concretely?
**Testing:** knowing the failure modes of the comfortable default.
**Answer:** Query model: index-driven only — no joins, limited aggregations, inequality-range restrictions per query; complex reads become client-side stitching or exports to BigQuery. Cost model: per-document-read pricing means N+1 patterns multiply bills invisibly (a list rendering 100 docs = 100+ reads); real-time listeners keep reading on every change even when UIs are backgrounded. Transaction constraints limit scope; document size caps at ~1 MiB (~). It excels for per-user hierarchical state with offline sync needs.
**Follow-up trap:** *"How do you catch runaway Firestore costs?"* — per-collection read metrics, alert on read-rate anomalies, move aggregates to scheduled functions writing summary docs, and cache aggressively client-side.

### Q9 — What does the AlloyDB columnar engine actually do, and when does it not help?
**Testing:** HTAP understanding beyond the 100x headline.
**Answer:** It maintains a transactionally-consistent in-memory columnar replica of selected tables/columns alongside row storage; a columnar-aware planner routes analytical scans/joins/aggregations to it, so OLAP queries run against live operational data without ETL. Doesn't help: point-lookup-heavy OLTP (row path anyway), workloads where analytic tables aren't registered in the column store, or queries hitting columns outside its configuration — and it can't substitute for a real warehouse at BigQuery-scale data volumes or complex multi-source analytics.
**Follow-up trap:** *"Why not just replicate into BigQuery?"* — that's the ETL path with freshness lag (minutes+) and pipeline ops; columnar engine buys seconds-fresh analytics inside one system. The trade is scope: single-database analytics versus warehouse-scale joins across sources.

### Q10 — A compliance rule demands objects survive accidental deletion for 90 days minimum. Design it.
**Testing:** GCS protection features composition.
**Answer:** Layered: object versioning keeps prior versions on overwrite/delete; soft delete retains deleted objects (default 7 days, configurable ~) recoverable by any admin; bucket retention policies make objects undeletable until age N — set 90 days; retention-policy lock makes even admins unable to shorten it (irreversible). For legal holds, per-object holds override everything until released. IAM/org-policy public-access-prevention runs underneath.
**Follow-up trap:** *"Retention policy vs versioning overlap?"* — they compose: versioning preserves noncurrent versions; retention applies age-based immutability to each object/version. Deleting before retention expiry simply fails once policy is enforced.

### Q11 — Compare Firestore, Bigtable, and Spanner pricing models as an architecture input.
**Testing:** whether cost structure shapes design choices in their head.
**Answer:** Firestore bills per operation (read/write/delete) plus storage plus bandwidth — design minimizes document touches (batching, caching). Bigtable bills per node-hour provisioned throughput — you pay for capacity, incentivizing dense keys and steady load; idle clusters cost full price. Spanner bills per node-hour (regional/multi-region tiers) — expensive floor, so consolidation of instances matters more than per-query tuning. Consequence: spiky small-state fits Firestore's metered model; sustained heavy key-value fits Bigtable nodes; global ACID justifies Spanner's floor.
**Follow-up trap:** *"Which gets surprise-billed most often?"* — Firestore: chatty listeners and N+1 reads are invisible until the invoice; Bigtable surprises come from over-provisioning for peaks that never came; Spanner surprises are architectural (too many instances/regions), visible early.

### Q12 — You need millisecond-latency feature lookups for a realtime ML service at 200k QPS. Which store and why?
**Testing:** matching access pattern to engine under pressure.
**Answer:** Bigtable: wide-column key-value at single-digit-ms latencies, scales horizontally by adding nodes (~10k QPS/node SSD heuristic ~), purpose-built exactly for this shape (Google's own feature-serving lineage). Key design: `feature-set#entity-id` hashed prefix for distribution. Alternatives honestly rejected: Memorystore (Redis) if dataset fits memory and persistence semantics acceptable — lower latency still, but capacity ceiling and cost at scale; Firestore — per-op pricing ruinous at 200k QPS; Spanner — paying global-transaction premium for point lookups.
**Follow-up trap:** *"What's your fallback when Bigtable has a regional issue?"* — replication with multi-cluster routing app-profiles serving from healthy clusters, client-side cache absorbing short gaps, and accepting staleness bounds rather than failing requests.

---

## Red flags that fail you

- Describing Spanner as "just globally replicated MySQL" without TrueTime/commit-wait mechanics.
- Claiming CockroachDB is "identical to Spanner" — HLC versus hardware clocks is a real semantic difference.
- Not knowing GCS minimum storage durations (30/90/365) or that early deletion costs money.
- Designing Bigtable tables with timestamp-first keys then blaming the platform for hotspots.
- Treating AlloyDB benchmark multipliers as guaranteed production speedups.
- Recommending Firestore for join-heavy relational workloads.
- Using GCS Archive class for monthly-access data because "it's the cheapest tier."

## Cheat card

```
GCS: one API, ms latency, all classes. Standard / Nearline(30d min) /
     Coldline(90d) / Archive(365d). Early deletion = pay remaining days.
     Autoclass: per-object, >=128KiB only, 30d no-access -> Nearline default
     terminal (optional Archive: 90d->Coldline, 365d->Archive); access -> Standard;
     get-method reads only; mgmt fee but no retrieval/early-deletion fees.
     Strong read-after-write consistency globally (since 2010).

CLOUD SQL: stock MySQL/Postgres/SQLServer on VMs. Enterprise Plus = data cache.
     Default answer until ceilings: vertical scale, analytics need ETL.

ALLOYDB: PG-wire-compatible 14-18; disaggregated log-structured storage;
     ~4x OLTP, up to 100x OLAP vs standard PG (Google benchmarks);
     columnar engine = in-memory columnar replica, HTAP w/o ETL;
     read pool 1-20 nodes (~); ScaNN vectors 2-10x pgvector HNSW (~);
     ~128 TiB max (~); private-IP-only; PITR 35 days; 99.99% SLA incl maint.

SPANNER: tablets owned by Paxos groups; TrueTime [earliest,latest], eps ~1-7ms
     commit_ts = TT.now().latest; commit-wait until earliest > commit_ts
     wait overlaps Paxos RTT -> usually ~0 extra latency
     => external consistency = strict serializability + real-time order
     reads: strong or bounded-staleness snapshot at past ts (no locks)
     local read ~5ms (~), cross-zone commit p99 ~50-100ms (~)
     CRDB contrast: HLC on commodity clocks -> serializable, NOT external-consistent

BIGTABLE: wide-column, petabyte scale, single-digit ms. NO secondary indexes,
     single-row atomicity only. Key design IS the architecture:
     monotonic keys = hotspot; hash/reverse/salt/pad prefixes. Nodes scale
     throughput roughly linearly (~10k QPS/node SSD heuristic ~).

FIRESTORE: serverless documents, realtime listeners, offline sync,
     multi-region 99.999%-class SLA (~); index-driven queries only, no joins;
     ~1MiB/doc cap (~); bill per op - N+1 reads are the budget killer.

PICK BY: consistency scope > scale ceiling > query shape > cost meter
```

## Sources

- [Spanner: TrueTime and external consistency — Google Cloud docs](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency); accessed 2026-08-23
- [Strict serializability and external consistency in Spanner — Google Cloud blog](https://cloud.google.com/blog/products/databases/strict-serializability-and-external-consistency-in-spanner); accessed 2026-08-23
- [The one crucial difference between Spanner and CockroachDB — AuthZed](https://authzed.com/blog/prevent-newenemy-cockroachdb); accessed 2026-08-23
- [Spanner internals: TrueTime, Paxos groups, external consistency](https://systeminternals.dev/spanner); accessed 2026-08-23
- [AlloyDB for PostgreSQL columnar engine — Google Cloud blog](https://cloud.google.com/blog/products/databases/alloydb-for-postgresql-columnar-engine); accessed 2026-08-23
- [About the AlloyDB columnar engine — Google Cloud docs](https://docs.cloud.google.com/alloydb/docs/columnar-engine/about); accessed 2026-08-23
- [Autoclass — Cloud Storage docs](https://docs.cloud.google.com/storage/docs/autoclass); accessed 2026-08-23
- [GCS storage classes and lifecycle management guide](https://cloudtoolstack.com/learn/gcp-storage-classes-lifecycle); accessed 2026-08-23
- [AlloyDB vs Cloud SQL comparison](https://www.netcomlearning.com/blog/alloydb-vs-cloudsql); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
