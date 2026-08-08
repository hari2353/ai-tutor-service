# GCS, Cloud SQL, Spanner, Bigtable, Firestore, AlloyDB

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** `C-GCP-iam`, `C-GCP-compute` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-storage-db` · **Tags:** storage, critical

## The 30-second version

GCS has four storage classes on one flat namespace — **Standard, Nearline (30-day minimum), Coldline (90-day minimum), Archive (365-day minimum)** — priced roughly **$0.020 / $0.010 / $0.004 / $0.0012 per GB-month**, with retrieval fees only below Standard (Nearline $0.01/GB, Coldline $0.02/GB, Archive $0.05/GB); **Autoclass** watches per-object access patterns and moves objects between tiers automatically with no early-deletion penalty, which is the thing to reach for instead of hand-rolled lifecycle rules. Cloud SQL is a straight RDS analog (MySQL/Postgres/SQL Server, single-region-primary, up to 64 TB storage, Enterprise Plus edition adds read pools and near-zero-downtime maintenance) — nothing exotic. **Spanner is the module's centerpiece**: a globally distributed, horizontally scalable relational database that gives **external consistency** (transactions appear to execute in real-time order, globally, even across continents) using **TrueTime**, an API backed by GPS and atomic clocks that bounds clock uncertainty to single-digit milliseconds and lets Spanner know when it's safe to commit without talking to every replica. There is no direct AWS or Azure equivalent — Aurora Global has replica lag, Cosmos DB gives you a tunable spectrum but nothing globally linearizable by default — and what TrueTime actually buys you is the ability to say "this write definitely happened before that read, everywhere, no caveats" without a global lock service. Bigtable is GCP's HBase-shaped wide-column store for petabyte-scale, high-throughput key-value workloads with no secondary indexes; Firestore is the document database for app backends with real-time sync; AlloyDB is Google's Aurora-shaped PostgreSQL-compatible engine with a columnar accelerator for hybrid transactional/analytical workloads. Picking the wrong one of these six is the fastest way to fail a GCP system-design round.

## Why this gets asked

The interviewer has watched someone default to Firestore for a workload that actually needed Spanner's transactional guarantees across shards, has explained why a startup's Nearline bucket got hit with a bigger bill than expected because objects were deleted at day 12, and has personally had to explain TrueTime to a skeptical AWS engineer who assumed "external consistency" was marketing language for "eventual consistency with better branding." They want proof you can map a workload's actual consistency and access-pattern requirements onto the right one of six genuinely different storage systems, not that you can recite feature lists.

---

## Lineage: past → present → future

**What came before.** Google's internal storage lineage runs through GFS (2003) and Bigtable's 2006 paper (the wide-column model that still ships today, largely unchanged), then **Megastore** (2008-2011), which bolted synchronous replication and limited transactions onto Bigtable using Paxos but paid for it with single-digit-write-per-second-per-entity-group throughput and complex, error-prone schema design around entity groups. The pain that killed Megastore as Google's answer to "give me a real relational database that scales": it was slow, it leaked its distributed-systems internals into application design, and it could not give cross-entity-group transactions the guarantees engineers actually wanted for a global system like AdWords. AWS's answer to the same pressure — Aurora (2014) — separated compute from a distributed storage log but stayed single-region-primary with async cross-region replicas; DynamoDB (2012) went the other direction entirely, giving up SQL and cross-partition transactions for horizontal scale.

**Where it stands now.** **Spanner** (published 2012, GA 2017) is Google's production answer: a globally distributed, strongly consistent relational database that uses **TrueTime** — an API returning a time interval `[earliest, latest]` guaranteed to contain the true current time, backed by GPS receivers and atomic clocks in every datacenter — to assign globally meaningful commit timestamps to transactions without a central sequencer. [TrueTime and external consistency — Google Cloud Docs](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency) — accessed 2026-08-08. The mechanism that makes this work is **commit-wait**: after a transaction's coordinator picks a commit timestamp `t`, Spanner waits out the *remaining* clock uncertainty (until TrueTime's `after(t)` is true) before making the transaction's writes visible, guaranteeing no other transaction can be assigned an earlier timestamp for something that happened later in real time. That uncertainty bound is typically **under 7ms** with atomic-clock-and-GPS-backed TrueTime, versus the tens-to-hundreds of milliseconds NTP-only clock sync would leave you with — which is exactly why nobody outside Google's own datacenter fleet can replicate this without dedicated time infrastructure. Bigtable, Firestore (which absorbed and superseded Datastore's underlying engine, now offered as "Firestore in Datastore mode" for legacy compatibility), and AlloyDB (2023, PostgreSQL-compatible with a **columnar engine** giving up to 100x faster analytical query performance by keeping an in-memory columnar representation of hot data alongside the row store) round out the current lineup, each solving a materially different problem rather than being redundant options.

**Where it's heading.** Spanner's direction is deeper integration with the Vertex AI / vector-search stack (Spanner already supports vector indexes and `ML.PREDICT` inline SQL calls to Vertex AI models) and **Spanner Omni**, letting Spanner's TrueTime-backed engine run outside Google's own datacenters on customer infrastructure — moderate confidence this matters for regulated/on-prem workloads, low confidence it changes mainstream cloud usage patterns near-term. AlloyDB's columnar engine and its **AlloyDB AI** integration (built-in vector search, `ScaNN` index type) point at Google's broader bet that hybrid transactional/analytical/vector workloads converge onto one engine rather than requiring a separate OLAP warehouse and vector database bolted on — moderate-to-high confidence given the pace of AlloyDB feature releases through 2025-2026. Firestore's real-time listener model continues expanding into more Gemini/agent-backend use cases as the default state store for agentic applications built on Firebase — speculative, worth a fresh check near interview time.

---

## Mental model

```
PICK BY SHAPE, NOT BY FAMILIARITY

  UNSTRUCTURED BLOBS, any size        -->  Cloud Storage (GCS)
    hot/warm/cold/frozen access       -->  Standard / Nearline / Coldline / Archive
    "I don't know the access pattern" -->  Autoclass (auto-tiers per object)

  RELATIONAL, single-region OK,       -->  Cloud SQL  (lift-and-shift RDS workload)
  <64TB, classic MySQL/Postgres/SQLServer

  RELATIONAL, needs GLOBAL strong     -->  Spanner
  consistency + horizontal scale +    (the "no direct AWS/Azure equivalent" answer)
  SQL, can tolerate commit-wait latency

  RELATIONAL, Postgres-compatible,    -->  AlloyDB
  wants HTAP (transactional +         (Aurora-shaped: separated storage,
  analytical in one engine)            + columnar accelerator)

  WIDE-COLUMN, petabyte-scale,        -->  Bigtable
  single-key lookups, NO secondary    (~HBase; time-series, IoT, ML feature stores)
  indexes, extreme throughput

  DOCUMENT, app backend, real-time    -->  Firestore
  sync to mobile/web clients          (~ DynamoDB + Realtime DB combined)

TRUETIME / EXTERNAL CONSISTENCY, mechanically:
  TrueTime.now() returns an INTERVAL [earliest, latest], never a point
      |----------- uncertainty (~1-7ms) -----------|
  Commit timestamp T chosen inside that interval.
  Spanner WAITS ("commit wait") until TrueTime guarantees real time has
  passed T, before exposing the write.
  Result: if txn A committed before txn B started (real wall-clock time),
  A's timestamp is guaranteed < B's timestamp -- globally, no exceptions.
  This is what "external consistency" buys that MVCC + Paxos alone cannot:
  ordering that matches REAL TIME, not just a logical clock.
```

---

## How it actually works

### GCS storage classes, mechanically

Four classes on one bucket namespace (class is a per-object attribute, not a bucket-only setting): **Standard** ($0.020/GB-mo in the US multi-region tier, no minimum duration, no retrieval fee — the default for actively-served data), **Nearline** ($0.010/GB-mo, 30-day minimum storage duration, $0.01/GB retrieval — monthly-accessed data, backups), **Coldline** ($0.004/GB-mo, 90-day minimum, $0.02/GB retrieval — quarterly access), **Archive** ($0.0012/GB-mo, 365-day minimum, $0.05/GB retrieval — compliance/legal hold, effectively GCS's answer to Glacier Deep Archive). [Cloud Storage pricing 2026 — CloudZero](https://www.cloudzero.com/blog/gcp-storage-pricing/) — accessed 2026-08-08. The **minimum storage duration** is the trap: delete or overwrite an object before its class's minimum window elapses and you're billed for the full minimum period anyway — a lifecycle rule that moves objects to Archive too early on frequently-churned data quietly inflates the bill. **Autoclass** removes the guesswork: enable it on a bucket and GCS monitors each object's actual access pattern and transitions it between Standard/Nearline/Coldline (and optionally Archive) automatically, with **no early-deletion fee for auto-migrated objects** — this is the practical default recommendation over hand-written Object Lifecycle Management rules unless you have a very predictable, uniform access pattern across the whole bucket. **Soft delete** (default 7-day retention of deleted objects/buckets, separate from and complementary to Object Versioning) is on by default for new buckets since 2024 — a change worth knowing since it silently changes storage cost accounting for high-churn buckets if not tuned down. [Soft delete overview — Google Cloud Docs](https://docs.cloud.google.com/storage/docs/soft-delete) — accessed 2026-08-08.

### Cloud SQL — the boring, correct choice for lift-and-shift

MySQL, PostgreSQL, or SQL Server, single-region with a synchronous HA standby (regional persistent disk-backed failover, not a distributed storage layer) and optional cross-region read replicas. Storage scales up to **64 TB**, though Google's own docs flag that pushing an instance toward that ceiling increases backup and other maintenance-operation latency — a real operational signal, not just a number to memorize. [Cloud SQL storage options — Google Cloud Docs](https://cloud.google.com/sql/docs/mysql/storage-options-overview) — accessed 2026-08-08. **Enterprise Plus** edition (the pricier of the two Cloud SQL editions) adds **read pools** — a pool of read replicas behind one endpoint with load balancing, available only on the newer network architecture — plus near-zero-downtime planned maintenance and better point-in-time recovery granularity. [Cloud SQL editions overview — Google Cloud Docs](https://docs.cloud.google.com/sql/docs/postgres/editions-intro) — accessed 2026-08-08. There is nothing exotic here: this is the RDS-equivalent answer, and if a candidate's whole GCP relational-database story is "Cloud SQL for everything," that's a signal they haven't needed Spanner or AlloyDB yet, not that Cloud SQL is wrong.

### Spanner — TrueTime and external consistency, mechanically

Spanner replicates data via **Paxos** across a configurable set of replicas (a **regional** config keeps replicas in one region for lower latency at the cost of regional-only durability; a **multi-region** config spans continents for the strongest availability and the "no direct equivalent" external-consistency story). Every read-write transaction, at commit time, is assigned a timestamp drawn from **TrueTime.now()**, which returns not a single value but an **interval `[earliest, latest]`** bounding true UTC time with the residual uncertainty from GPS/atomic-clock drift and network sync — typically **under 7ms**. [TrueTime and external consistency — Google Cloud Docs](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency) — accessed 2026-08-08. Before Spanner exposes a committed write to any reader, it performs **commit-wait**: it waits until TrueTime guarantees the chosen commit timestamp is definitely in the past, everywhere. This is the entire trick — instead of a global lock or a single sequencer (both bottlenecks at planet scale), Spanner uses bounded clock uncertainty plus a short wait to guarantee that if transaction A's real-world commit happened before transaction B's real-world start, A's timestamp is provably smaller than B's, globally, without either transaction needing to talk to the other's replica set.

**Compute is billed in processing units (PU)**: 1 node = 1000 PU, minimum purchase is **100 PU**, provisioned in 100 PU increments up to 1000 PU and 1000 PU increments beyond that — this granular sizing (added after Spanner's early node-only pricing) is what makes Spanner viable for a workload that doesn't need a full node's throughput. Pricing sits around **$0.90/node-hour (~$657/node-month)** for regional on-demand compute, with **Standard edition** at roughly $0.030/100 PU/hour/replica and **Enterprise** at roughly $0.041/100 PU/hour/replica for workloads needing Enterprise-tier features. [Compute capacity, nodes and processing units — Google Cloud Docs](https://docs.cloud.google.com/spanner/docs/compute-capacity) — accessed 2026-08-08; [Cloud Spanner pricing — Google Cloud](https://cloud.google.com/spanner/pricing) — accessed 2026-08-08. Storage is roughly **4TB per node** (doubled from 2TB in a prior release), which sets a practical floor on how many nodes a large dataset needs regardless of query throughput. **Interleaved tables** (a child table physically co-located with its parent's rows, e.g. `Orders` interleaved in `Customers`) are Spanner's mechanism for keeping related data on the same split so joins and transactions across parent/child rows stay cheap — get the interleave key wrong and you either create a giant hot split or lose the co-location benefit entirely.

```sql
-- untested sketch: Spanner DDL showing interleaving, the schema-design lever
-- that determines whether related rows are colocated on the same split
CREATE TABLE Customers (
  CustomerId STRING(36) NOT NULL,
  Name STRING(256),
) PRIMARY KEY (CustomerId);

CREATE TABLE Orders (
  CustomerId STRING(36) NOT NULL,
  OrderId STRING(36) NOT NULL,
  Amount NUMERIC,
) PRIMARY KEY (CustomerId, OrderId),
  INTERLEAVE IN PARENT Customers ON DELETE CASCADE;
-- Orders rows for a given CustomerId are physically stored adjacent to
-- that customer's row -- reads/transactions spanning a customer and their
-- orders stay within one split instead of fanning out across the cluster.
```

### Bigtable — wide-column at extreme scale

A single sparse, sorted map keyed by row key, with columns grouped into **column families** and no secondary indexes at all — every access pattern has to be designable as a row-key lookup or range scan, which is the single biggest mental shift for someone coming from a SQL or even DynamoDB background (DynamoDB at least gives you GSIs). Nodes are billed per hour (**~$0.65/node-hour** standard) regardless of query volume, and **autoscaling** (GA) adjusts node count against a configurable CPU-utilization target and min/max bounds, with storage-utilization targets defaulting to 50% (2.5TB for SSD clusters, 8TB for HDD clusters) before triggering a scale event. [Bigtable pricing — Pump.co 2026](https://www.pump.co/blog/gcp-bigtable-pricing/) — accessed 2026-08-08; [Autoscaling — Google Cloud Docs](https://docs.cloud.google.com/bigtable/docs/autoscaling) — accessed 2026-08-08. SSD storage is the default for latency-sensitive workloads; HDD is roughly an order of magnitude cheaper per GB and viable for large, less latency-sensitive datasets like historical time-series. **Row-key design is everything**: a monotonically increasing key (timestamp, auto-increment ID) creates a hot spot on the tail node handling all recent writes — the standard fix is a hashed or reversed-timestamp prefix to spread writes across the key space, exactly the same lesson DynamoDB and HBase engineers already know.

### Firestore — document database, two modes, one engine

**Firestore in Native mode** is the default for new applications: a document/collection model with real-time listeners (clients subscribe to a query and get pushed live updates — no equivalent in DynamoDB without bolting on Streams + something else) and strong consistency for single-document reads. **Firestore in Datastore mode** exists for backward compatibility with the original App Engine Datastore API and lacks real-time listeners, which is why it is not the default choice for new work. Both modes share a **hard 1 MiB (1,048,576 bytes) document size limit** — Datastore mode entities are capped at 1,048,572 bytes (4 bytes less). [Storage size calculations — Firebase Docs](https://firebase.google.com/docs/firestore/storage-size) — accessed 2026-08-08. Composite indexes are required for most multi-field queries and must be explicitly created (Firestore will return an error with a direct link to auto-create the missing index in the console) — this trips people who assume Firestore indexes everything automatically the way DynamoDB's base table does for its primary key.

### AlloyDB — Aurora-shaped Postgres with a columnar accelerator

Storage-and-compute separation (like Aurora, like Spanner) atop PostgreSQL wire-compatible engine, priced at roughly **$0.066/vCPU-hour**, database storage around **$0.0004/GiB-hour (~$0.30/GB-month)**, backup storage around **$0.0001/GiB-hour (~$0.10/GB-month)**, with a minimum viable primary instance (2 vCPU) landing around **$100/month**. [AlloyDB pricing — Google Cloud](https://cloud.google.com/alloydb/pricing) — accessed 2026-08-08. The differentiator is the **columnar engine**: an in-memory, automatically-maintained columnar representation of frequently-scanned data sitting alongside the normal row store, giving reported **up to 100x** faster analytical query performance on the same instance serving OLTP traffic, without a separate ETL pipeline into a warehouse. [AlloyDB for PostgreSQL Columnar Engine — Google Cloud Blog](https://cloud.google.com/blog/products/databases/alloydb-for-postgresql-columnar-engine) — accessed 2026-08-08. AlloyDB also ships **AlloyDB AI** with native vector search (`ScaNN` index), positioning it as a genuine alternative to bolting pgvector onto vanilla Postgres when the workload also needs the columnar HTAP story. **AlloyDB Omni** is the downloadable, self-managed version for on-prem/other-cloud deployment of the same engine.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| S3 | Blob Storage | Cloud Storage | GCS's 4-tier ladder + Autoclass vs. Azure's 5-tier + lifecycle policies — different minimum-duration numbers |
| RDS | Azure SQL | Cloud SQL | All three are the "boring, single-region, lift-and-shift" tier |
| Aurora | Azure SQL Hyperscale | **AlloyDB** | All three separate compute from a distributed storage layer; AlloyDB adds a columnar HTAP engine none of the others have natively |
| Aurora Global | Cosmos DB (SQL API) | **Spanner** | Aurora Global has replica lag (seconds); Cosmos gives 5 tunable levels; Spanner alone gives global external consistency via TrueTime — no substitute exists |
| DynamoDB | Cosmos DB | Firestore / Bigtable | Firestore ~ DynamoDB + real-time sync; Bigtable ~ HBase, no secondary indexes, extreme scale |
| Redshift | Synapse | BigQuery | Not this module — see `C-GCP-data` |

---

## Build it from scratch

Minimal illustration of the Spanner commit-wait concept and a Bigtable row-key design fix, matching `labs/python/04-storage-db/`:

```python
# untested sketch -- Spanner client showing a read-write transaction;
# the commit-wait / TrueTime machinery is entirely inside the service,
# invisible to the client, which is the point: you get external
# consistency without doing anything special in application code.
from google.cloud import spanner

client = spanner.Client(project="my-project")
instance = client.instance("my-instance")
database = instance.database("my-database")

def transfer_funds(transaction, from_id, to_id, amount):
    from_row = transaction.execute_sql(
        "SELECT Balance FROM Accounts WHERE AccountId = @id",
        params={"id": from_id}, param_types={"id": spanner.param_types.STRING},
    )
    balance = list(from_row)[0][0]
    if balance < amount:
        raise ValueError("insufficient funds")
    transaction.execute_update(
        "UPDATE Accounts SET Balance = Balance - @amt WHERE AccountId = @id",
        params={"amt": amount, "id": from_id},
        param_types={"amt": spanner.param_types.NUMERIC, "id": spanner.param_types.STRING},
    )
    transaction.execute_update(
        "UPDATE Accounts SET Balance = Balance + @amt WHERE AccountId = @id",
        params={"amt": amount, "id": to_id},
        param_types={"amt": spanner.param_types.NUMERIC, "id": spanner.param_types.STRING},
    )
    # Commit timestamp assigned here via TrueTime; commit-wait happens
    # inside the service before this call returns success.

database.run_in_transaction(transfer_funds, from_id="a1", to_id="a2", amount=100)
```

```python
# untested sketch -- Bigtable row key anti-pattern vs fix
# BAD: monotonic timestamp prefix -> all recent writes hit the same
# tablet/node, creating a hot spot on whichever node owns the tail of
# the key space.
bad_row_key = f"{int(time.time())}#{device_id}"

# FIX: salt with a hash prefix (or reverse the timestamp) to spread
# writes across the key space while keeping per-device range scans
# workable by also storing device_id in the row.
import hashlib
salt = hashlib.md5(device_id.encode()).hexdigest()[:4]
good_row_key = f"{salt}#{device_id}#{int(time.time())}"
```

---

## How it's done in production

A typical GCP data layer: **GCS** with Autoclass on for anything without a predictable access pattern, explicit lifecycle rules only for well-understood, uniform-pattern buckets (build artifacts, log archives with a known retention policy). **Cloud SQL** for the majority of transactional workloads that fit comfortably in one region under 64TB. **Spanner** reserved specifically for the subset of workloads that need global strong consistency with horizontal write scale — financial ledgers, global inventory, multi-region session state where "eventually consistent" is a correctness bug, not a UX nit — because Spanner's cost floor (100 PU minimum, ~$0.90/node-hour equivalent) and operational complexity (interleaving, hot-split avoidance) aren't worth paying without that specific requirement. **Bigtable** for time-series, IoT telemetry, and ML feature stores at throughput levels where even Spanner's per-node cost becomes uneconomical relative to Bigtable's raw key-value throughput. **Firestore** as the default app-backend database for anything mobile/web-real-time-sync-shaped. **AlloyDB** where a team wants Postgres compatibility plus HTAP without standing up a separate BigQuery pipeline for analytics on live transactional data.

| Symptom | Cause | Fix |
|---|---|---|
| Nearline/Coldline bucket bill is higher than expected despite "moving cold data off Standard" | Objects deleted/overwritten before the class's minimum storage duration (30/90/365 days) elapsed — full minimum-duration charge applies anyway | Use Autoclass instead of manual lifecycle rules for unpredictable access patterns; audit lifecycle rule timing against actual churn rate |
| Spanner write latency spikes on a specific key range | Hot split from a monotonically increasing primary key (auto-increment ID, timestamp) concentrating writes on one split | Use a UUID, hashed prefix, or bit-reversed sequential ID as the leading key column to spread writes |
| Bigtable read latency degrades unevenly across the cluster | Row-key design creates a hot tablet (sequential timestamp-prefixed keys) | Salt/hash the row-key prefix; redesign for range-scan needs separately from write-distribution needs |
| Firestore query throws a "requires an index" error in production it didn't throw in testing | A multi-field query needs a composite index that wasn't created before deploy | Create the composite index (console link in the error, or pre-declare in `firestore.indexes.json`) before shipping any new query shape |
| Cloud SQL instance backup/maintenance operations get slow | Storage approaching or past the ~64TB practical ceiling | Consider sharding across instances, moving to Spanner/AlloyDB if horizontal scale or HTAP is the actual need, or archive cold data out of the primary instance |
| AlloyDB analytical query on live transactional data unexpectedly slow | Columnar engine not enabled or the query pattern doesn't trigger it (columnar engine activates for recognized analytical scan patterns, not all queries) | Confirm columnar engine is enabled on the instance and check `EXPLAIN` to verify the columnar path is actually chosen |

---

## Tradeoffs & when NOT to use it

- **Don't reach for Spanner by default.** The 100 PU minimum, per-node storage ceiling (~4TB), and interleaving/hot-split design burden are real costs. If the workload fits in one region and under 64TB, Cloud SQL is cheaper and simpler — Spanner earns its keep specifically when global strong consistency or horizontal write scale beyond a single Cloud SQL instance is a hard requirement, not a nice-to-have.
- **Don't use Bigtable for anything needing secondary indexes, ad-hoc queries, or multi-row transactions.** It gives you none of that. If the access pattern isn't cleanly expressible as a row-key lookup or range scan, Bigtable is the wrong tool regardless of scale.
- **Don't put Archive-tier objects on data with any realistic chance of being touched inside a year.** The 365-day minimum and $0.05/GB retrieval fee make early access expensive twice over.
- **Don't assume Firestore's real-time listeners scale to arbitrary fan-out for free.** Each active listener is a standing connection with its own cost and quota implications at high concurrent-user counts — validate against Firestore's connection and query-rate quotas before assuming it's free real-time infrastructure.
- **Don't pick AlloyDB purely for the columnar engine if the analytical workload is genuinely large-scale OLAP.** BigQuery's separate compute/storage and massive parallel scan model still wins for true data-warehouse-scale analytics; AlloyDB's columnar engine is for HTAP on data that's fundamentally transactional-first.
- **Don't assume TrueTime-grade external consistency is replicable outside Spanner.** Self-hosting "a Spanner-like system" without dedicated atomic-clock/GPS time infrastructure means falling back to NTP-bounded uncertainty in the tens-to-hundreds of milliseconds — commit-wait at that scale either kills latency or the consistency guarantee, which is exactly why this is a genuinely hard-to-replicate moat, not just clever software.

---

## Interview questions

### Q1 — Explain what TrueTime actually is and how Spanner uses it to achieve external consistency.
**Testing:** whether the candidate understands the mechanism, not just the marketing term.
**Answer:** TrueTime is an API, backed by GPS receivers and atomic clocks in Google's datacenters, that returns a bounded *interval* `[earliest, latest]` guaranteed to contain true UTC time, rather than a single timestamp — typical uncertainty is under 7ms. Spanner assigns each transaction a commit timestamp drawn from within that interval, then performs **commit-wait**: it delays exposing the transaction's writes until TrueTime guarantees the chosen timestamp is definitely in the past everywhere. This guarantees that if transaction A committed (in real wall-clock time) before transaction B started, A's assigned timestamp is provably smaller — giving external consistency (real-time ordering) without a global lock or sequencer.
**Follow-up trap:** *"Why can't you get the same guarantee with NTP-synchronized clocks and a similar wait?"* — NTP-only synchronization leaves clock uncertainty in the tens-to-hundreds of milliseconds range rather than single-digit milliseconds; commit-wait scaled to that uncertainty would either add unacceptable latency to every transaction or force accepting a much weaker consistency guarantee. TrueTime's advantage is specifically the *tightness* of the bound, which only dedicated time infrastructure (atomic clocks + GPS, cross-checked) delivers.

### Q2 — A team wants to migrate from DynamoDB to GCP and picks Firestore reflexively. When is that wrong, and what should they use instead?
**Testing:** whether the candidate maps requirements onto the right of six services rather than pattern-matching on "NoSQL key-value."
**Answer:** Firestore is the right analog for DynamoDB workloads that are document-shaped, need real-time client sync, and stay within Firestore's per-document 1MiB limit and query-index model. It's the wrong choice if the workload actually needs wide-column, extreme-throughput, single-key access at petabyte scale with no need for secondary indexes (Bigtable is the closer match, more HBase-shaped than DynamoDB-shaped), or if it needs cross-partition ACID transactions with global consistency (Spanner, not Firestore).
**Follow-up trap:** *"Does Firestore support transactions across documents the way DynamoDB supports transactions across items?"* — yes, Firestore supports multi-document ACID transactions, but they're scoped and rate-limited differently than DynamoDB's; the deeper trap is assuming Firestore transactions give the same global, cross-region ordering guarantee Spanner gives — they don't, they're consistent within Firestore's own replication model, not externally-consistent in the TrueTime sense.

### Q3 — Design the row key for a Bigtable table storing IoT sensor readings, given millions of devices reporting every few seconds.
**Testing:** hot-spotting, the single most common Bigtable production incident.
**Answer:** A naive `timestamp#device_id` key concentrates all current writes on the tablet owning the newest timestamp range — a severe hot spot. The fix is to lead with something high-cardinality and roughly uniform, like a hash or the device_id itself (if device count is large and reads are typically per-device), e.g. `device_id#reverse_timestamp`, which spreads writes across the key space while keeping per-device time-range scans efficient (reverse timestamp keeps latest-first ordering within a device's range).
**Follow-up trap:** *"Doesn't hashing the device_id break efficient range scans across all devices for a given time window?"* — yes, that's the real tradeoff: optimizing for per-device time-range scans (device-first key) sacrifices efficient global time-window scans across all devices, and vice versa for a timestamp-first key; the schema has to pick which access pattern is primary, or maintain a second table/materialized view for the other pattern.

### Q4 — Why doesn't AWS or Azure have a direct equivalent to Spanner, and how would you answer a system-design question that seems to call for one?
**Testing:** cross-cloud honesty — knowing the gap is real, not something to paper over.
**Answer:** Aurora Global Database gives cross-region replication with typically sub-second but non-zero, non-bounded-guarantee replica lag — it's asynchronous, not externally consistent. Cosmos DB gives five tunable consistency levels including Strong, but Strong in Cosmos DB is scoped differently (single-region-authoritative writes with configurable multi-region consistency, not TrueTime-style global commit-wait) and costs 2x RUs. Neither gives Spanner's specific guarantee: globally distributed, multi-region *write* availability with external consistency backed by hardware time infrastructure. In a system-design interview, the honest answer is to name the requirement precisely (does the workload need writes accepted in multiple regions with real-time global ordering, or would regional-primary-plus-async-replica suffice) rather than assuming every "global database" question wants a Spanner-shaped answer.
**Follow-up trap:** *"Could you approximate Spanner's guarantee on AWS using DynamoDB Global Tables plus application-level conflict resolution?"* — you can approximate *availability* and *eventual convergence*, but not external consistency — Global Tables use last-writer-wins conflict resolution based on timestamps without TrueTime-grade bounded uncertainty, so two near-simultaneous writes in different regions can resolve in an order that doesn't match real-world causality. It's a materially weaker guarantee dressed in similar-sounding language.

### Q5 — Walk through why the minimum storage duration on Nearline/Coldline/Archive can make a "cost optimization" migration backfire.
**Testing:** whether cost numbers are understood mechanically, not just as a tier list.
**Answer:** Each class below Standard has a minimum storage duration (30/90/365 days) — deleting or overwriting an object before that window elapses still incurs the full minimum-duration charge, as if the object had been stored for the whole period. A team moving frequently-churned data (e.g., staging artifacts rebuilt weekly) to Coldline "to save money" can end up paying more than Standard would have cost, because every object gets billed for 90 days of storage regardless of actual retention.
**Follow-up trap:** *"Does Autoclass avoid this problem entirely?"* — largely yes for the class-transition cost (no early-deletion fee for auto-migrated objects), but Autoclass doesn't override the *retrieval* fee structure or make a genuinely short-lived object free — the fix for high-churn data is keeping it on Standard, not any auto-tiering feature, since auto-tiering only helps once an object has demonstrated infrequent access.

### Q6 — Explain interleaved tables in Spanner and what happens if the interleave hierarchy is designed wrong.
**Testing:** applied Spanner schema design, a common staff-level probe.
**Answer:** Interleaving physically co-locates a child table's rows with its parent row on the same split (e.g., `Orders` interleaved in `Customers` on `CustomerId`), so reads and transactions spanning a customer and their orders stay within one split instead of requiring a distributed multi-split transaction. Designed wrong — interleaving a high-write-volume child under a low-cardinality or hot parent key — it recreates a hot-split problem: all of that child's writes concentrate on whichever split holds the hot parent, defeating Spanner's horizontal scale-out.
**Follow-up trap:** *"If two tables are frequently joined but don't have a natural parent-child cardinality relationship, should you still interleave them?"* — no; interleaving is specifically for genuine parent-child (1-to-many, keyed on the parent's key prefix) relationships. Forcing an interleave onto tables without that shape either doesn't help query performance the way expected or actively creates the hot-split risk without the colocation benefit it's meant to buy.

### Q7 — When would you choose AlloyDB over both Cloud SQL and BigQuery for a workload that has both transactional and analytical needs?
**Testing:** whether HTAP tradeoffs are understood as a spectrum, not a binary choice.
**Answer:** AlloyDB fits when the analytical queries need to run against *live* transactional data with low staleness (the columnar engine keeps an automatically-maintained in-memory columnar copy of hot data, giving up to 100x faster scan/aggregate performance than row-store Postgres) and the analytical workload's scale doesn't require BigQuery's massively parallel, serverless architecture. It's the wrong choice once the analytical side is genuinely warehouse-scale (many-TB historical aggregation, ad-hoc analyst queries across the whole history) — at that point ETL/CDC into BigQuery and accepting some staleness is the better-fitting architecture, since BigQuery's compute model is built for that scale in a way a single (even well-provisioned) AlloyDB instance isn't.
**Follow-up trap:** *"Doesn't the columnar engine mean AlloyDB never needs a separate warehouse?"* — no; the columnar engine accelerates analytical queries against the *live operational dataset size*, not against years of accumulated historical data at warehouse scale — conflating "faster analytics on transactional data" with "replaces a data warehouse" is exactly the kind of overclaim that fails a staff-level design review.

### Q8 — A Cloud SQL instance is approaching 60TB and both backup time and failover time have degraded. What are the real options?
**Testing:** recognizing Cloud SQL's practical ceiling and reasoning about migration paths, not just citing the 64TB number.
**Answer:** Google's own guidance flags increasing latency for operations like backups as storage approaches the 64TB range — this isn't a hard error but a real degradation signal. Options: shard the data across multiple Cloud SQL instances (real application-level complexity), archive/cold-tier historical data out of the primary instance to shrink it, or — if the underlying driver is that the workload has outgrown a single-primary relational model entirely — evaluate Spanner (if horizontal write scale with strong consistency is the actual need) or AlloyDB (if the Aurora-style separated-storage architecture alone, without Spanner's global-consistency machinery, solves the ceiling problem).
**Follow-up trap:** *"Is AlloyDB's storage ceiling meaningfully higher than Cloud SQL's, given both separate compute from storage?"* — AlloyDB's separated storage layer does give it a materially higher and more elastic storage ceiling than Cloud SQL's classic attached-disk model, similar to how Aurora outgrows classic RDS — but the honest answer in an interview is to verify AlloyDB's current documented limits rather than assume "separated storage" alone answers the question, since specific numeric ceilings shift across releases.

### Q9 — Compare Bigtable's consistency model to Spanner's, and explain why you'd never use Bigtable where Spanner is required.
**Testing:** precise understanding of what each system does and doesn't guarantee.
**Answer:** Bigtable gives strong consistency for single-row reads/writes within a single cluster, and eventual consistency across clusters in a multi-cluster replication setup — there is no cross-row transactional guarantee at all (no multi-row ACID transactions), and definitely no TrueTime-style external consistency. Spanner gives multi-row, multi-table, cross-region ACID transactions with external consistency. A workload needing "increment this counter and decrement that other row atomically, globally, in order" cannot be correctly built on Bigtable regardless of how the row keys are designed — that's a transactional guarantee Bigtable's data model doesn't offer, not a performance-tuning problem.
**Follow-up trap:** *"Bigtable does support single-row atomic read-modify-write operations — doesn't that cover most transactional needs?"* — single-row atomicity covers a narrower class of problems (counters, single-entity updates) than multi-row transactions (funds transfer between two accounts, inventory decrement plus order creation) — conflating the two is the exact mistake that leads teams to discover a correctness bug in production after scaling past the cases where single-row atomicity happened to be sufficient.

### Q10 — Explain the GCS Standard/Nearline/Coldline/Archive retrieval fee structure and design a lifecycle policy for a media company storing user-uploaded video.
**Testing:** applying the numbers to a realistic policy design, not just reciting the price table.
**Answer:** Recently uploaded video (first 30 days, high view probability) stays on Standard (no retrieval fee, no minimum duration). After 30 days of declining views, transition to Nearline ($0.010/GB-mo, $0.01/GB retrieval) — still cheap to serve occasionally. After 90 days with minimal views, Coldline ($0.004/GB-mo, $0.02/GB retrieval). Content flagged for long-term retention but essentially never re-served (e.g., after account deletion grace period) moves to Archive at 365 days. In practice, enabling Autoclass instead of hand-tuning these transition ages is the pragmatic default, since real view-decay curves rarely match a clean 30/90/365 schedule exactly.
**Follow-up trap:** *"If a video unexpectedly goes viral after being moved to Coldline, what's the cost impact?"* — the $0.02/GB retrieval fee applies per access, which at high view volume on a large file can dwarf the storage savings that justified moving it to Coldline in the first place — this is exactly the scenario Autoclass's per-object access monitoring is designed to catch and reverse automatically, while a static lifecycle rule would not until the next scheduled review.

### Q11 — A candidate claims "Spanner is just Cloud SQL that auto-shards." What's wrong with that framing, and what's the correct one-sentence distinction?
**Testing:** precision under a deliberately sloppy prompt — a very common interview pattern.
**Answer:** That framing misses the actual hard problem Spanner solves: sharding alone (splitting data across nodes) doesn't give you cross-shard ACID transactions with global ordering — plenty of sharded relational setups exist without that guarantee (Citus, manually-sharded MySQL). The correct distinction: Spanner combines horizontal sharding *with* TrueTime-backed external consistency, giving cross-shard, cross-region ACID transactions that behave, from an ordering perspective, as if they ran on a single machine — that combination, not sharding by itself, is what nothing else offers.
**Follow-up trap:** *"So is Citus-sharded PostgreSQL basically Spanner without the marketing?"* — no; Citus gives horizontal scale and requires real schema redesign around distribution keys, but cross-shard transactions in Citus don't carry Spanner's external-consistency guarantee — they're subject to the same distributed-transaction tradeoffs (two-phase commit costs, weaker cross-shard isolation guarantees in some configurations) that Spanner's TrueTime-based design specifically avoids.

### Q12 — How would you decide between Bigtable and BigQuery for a large clickstream dataset?
**Testing:** the operational-vs-analytical database line, a frequent point of confusion between this module and the data module.
**Answer:** Bigtable fits the *ingestion and serving* side — extremely high write throughput, low-latency single-key lookups (e.g., "give me this user's last N events" keyed by user_id), no need for ad-hoc analytical queries against arbitrary columns. BigQuery fits the *analysis* side — ad-hoc SQL aggregation across the whole dataset, joins, scan-based billing suited to occasional large queries rather than constant low-latency point lookups. In practice, clickstream architectures often use both: Bigtable (or Pub/Sub + Bigtable) for the real-time serving path, with a pipeline (Dataflow) continuously loading the same data into BigQuery for analysis.
**Follow-up trap:** *"Could you just query Bigtable directly for analytics instead of maintaining two systems?"* — Bigtable has no SQL query engine or secondary indexes; any analytical query beyond a row-key range scan requires either a full table scan client-side or an external query layer (BigQuery has a Bigtable external-table connector for exactly this), which is slower and more limited than querying data already loaded into BigQuery's native columnar storage — maintaining both systems is usually still the right call despite the duplication.

---

## Red flags that fail you

- Describing Spanner's external consistency as "basically eventual consistency but faster."
- Not knowing TrueTime returns an interval, not a point-in-time value.
- Recommending Bigtable for a workload needing secondary indexes or multi-row transactions.
- Not knowing GCS's minimum storage durations, or claiming Autoclass eliminates all cost-tuning need.
- Treating Firestore and Bigtable as interchangeable "GCP's NoSQL option."
- Claiming AlloyDB's columnar engine replaces the need for a data warehouse at any scale.
- Not knowing Cloud SQL's practical storage ceiling exists and has operational consequences.

---

## Cheat card

```
GCS CLASSES (US, per GB-mo / min duration / retrieval fee):
  Standard  $0.020 / none  / none
  Nearline  $0.010 / 30d   / $0.01/GB
  Coldline  $0.004 / 90d   / $0.02/GB
  Archive   $0.0012/ 365d  / $0.05/GB
  Autoclass = auto per-object tiering, no early-deletion fee. Soft delete
  default 7 days (separate from Object Versioning).

CLOUD SQL: MySQL/Postgres/SQLServer, single-region primary, up to 64TB
  (ops slow down approaching ceiling). Enterprise Plus = read pools +
  near-zero-downtime maintenance. The boring RDS-equivalent answer.

SPANNER: global relational, TrueTime = interval [earliest,latest], ~<7ms
  uncertainty. Commit-wait = delay exposing write until TrueTime proves
  timestamp is past -> EXTERNAL CONSISTENCY (real-time global ordering).
  Billing: 1 node = 1000 PU, min 100 PU, ~4TB storage/node,
  ~$0.90/node-hr regional. Standard ~$0.030/100PU/hr, Enterprise ~$0.041.
  Interleaved tables = child co-located with parent split; wrong hierarchy
  = hot split. NO direct AWS/Azure equivalent -- Aurora Global has lag,
  Cosmos gives tunable levels, neither gives TrueTime-grade global order.

BIGTABLE: wide-column, ~HBase, NO secondary indexes. ~$0.65/node-hr.
  Autoscaling on CPU target + storage target (default 50%: 2.5TB SSD /
  8TB HDD trigger). Row-key design = everything; monotonic keys hot-spot.

FIRESTORE: Native mode (real-time listeners, default) vs Datastore mode
  (legacy, no real-time). Hard 1MiB doc/entity limit. Composite indexes
  required for multi-field queries, must be pre-created.

ALLOYDB: Postgres-compatible, Aurora-shaped (separated storage) +
  COLUMNAR ENGINE (up to 100x faster analytics on live txn data).
  ~$0.066/vCPU-hr, ~$0.30/GB-mo storage, ~$100/mo min (2vCPU primary).
  AlloyDB AI = built-in ScaNN vector index.

CROSS-CLOUD: GCS~S3. Cloud SQL~RDS. AlloyDB~Aurora (+columnar, unique).
  Spanner~nothing (closest: Aurora Global lag / Cosmos tunable levels).
  Firestore~DynamoDB+realtime. Bigtable~HBase.
```

## Sources

- [Cloud Storage pricing 2026 — CloudZero](https://www.cloudzero.com/blog/gcp-storage-pricing/) — accessed 2026-08-08
- [Soft delete overview — Google Cloud Docs](https://docs.cloud.google.com/storage/docs/soft-delete) — accessed 2026-08-08
- [Autoclass — Google Cloud Docs](https://docs.cloud.google.com/storage/docs/autoclass) — accessed 2026-08-08
- [TrueTime and external consistency — Google Cloud Docs](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency) — accessed 2026-08-08
- [Strict Serializability and External Consistency in Spanner — Google Cloud Blog](https://cloud.google.com/blog/products/databases/strict-serializability-and-external-consistency-in-spanner) — accessed 2026-08-08
- [Compute capacity, nodes and processing units — Google Cloud Docs](https://docs.cloud.google.com/spanner/docs/compute-capacity) — accessed 2026-08-08
- [Cloud Spanner pricing — Google Cloud](https://cloud.google.com/spanner/pricing) — accessed 2026-08-08
- [Cloud SQL storage options — Google Cloud Docs](https://cloud.google.com/sql/docs/mysql/storage-options-overview) — accessed 2026-08-08
- [Cloud SQL editions overview — Google Cloud Docs](https://docs.cloud.google.com/sql/docs/postgres/editions-intro) — accessed 2026-08-08
- [Bigtable pricing — Pump.co](https://www.pump.co/blog/gcp-bigtable-pricing/) — accessed 2026-08-08
- [Autoscaling — Bigtable — Google Cloud Docs](https://docs.cloud.google.com/bigtable/docs/autoscaling) — accessed 2026-08-08
- [Storage size calculations — Firestore/Firebase Docs](https://firebase.google.com/docs/firestore/storage-size) — accessed 2026-08-08
- [Limits — Datastore — Google Cloud Docs](https://docs.cloud.google.com/datastore/docs/concepts/limits) — accessed 2026-08-08
- [AlloyDB pricing — Google Cloud](https://cloud.google.com/alloydb/pricing) — accessed 2026-08-08
- [AlloyDB for PostgreSQL Columnar Engine — Google Cloud Blog](https://cloud.google.com/blog/products/databases/alloydb-for-postgresql-columnar-engine) — accessed 2026-08-08
- `clouds/CROSS-CLOUD-MAP.md` — internal cross-cloud equivalence reference

## Changelog
- 2026-08-08 — created
