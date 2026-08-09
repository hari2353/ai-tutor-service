# Storage: S3 (classes, consistency, events), EBS, EFS, FSx

> **Track:** C-AWS AWS Atlas · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-storage` · **Tags:** storage

## Why this gets asked

Storage looks boring until it isn't: the interviewer has watched a bill balloon from forgotten incomplete multipart uploads, has debugged a "duplicate processing" bug that turned out to be S3's at-least-once event delivery colliding with an idempotency assumption that wasn't actually there, and has personally been burned by an old "S3 is only eventually consistent" mental model that stopped being true in December 2020 but is still repeated in interviews today. They want to know whether your storage knowledge is current, whether you understand the actual retrieval-time and cost tradeoffs of the storage classes rather than just their names, and whether you know when a shared filesystem (EFS/FSx) is solving a problem that shouldn't exist in the first place.

---

## Lineage: past → present → future

**What came before.** S3 launched in 2006 as one of AWS's first two services, originally with eventual consistency for overwrite PUTs and deletes — a design choice inherited from the era's dominant distributed-systems thinking (Dynamo-style eventual consistency, CAP-theorem tradeoffs favoring availability). This forced a generation of application code to work around it: read-after-write races, S3-as-database anti-patterns papered over with careful retry logic, and entire consulting practices built around "S3 consistency gotchas." EBS and EFS came later (2008, 2015) to cover block and shared-file needs S3's object model never addressed.

**Where it stands now.** S3 delivered **strong read-after-write consistency automatically, for all requests, at no additional cost and no performance penalty**, announced December 2020 — a genuinely rare case of a distributed storage system removing a fundamental limitation without a new API or opt-in flag. [S3 strong consistency announcement](https://aws.amazon.com/about-aws/whats-new/2020/12/amazon-s3-now-delivers-strong-read-after-write-consistency-automatically-for-all-applications) — accessed 2026-08-01. This closed the single most commonly cited "gotcha" in S3 interview prep, and yet stale answers about eventual consistency persist because so much pre-2020 material is still in circulation. The current live tension is elsewhere: storage-class selection is genuinely complex (7+ classes with different retrieval times, minimum durations, and per-request costs), and Intelligent-Tiering's automatic movement between tiers is good but not free — it has its own monitoring fee that needs to be weighed against the savings it captures.

**Where it's heading.** Direction of travel, high confidence: further consolidation toward automated tiering (Intelligent-Tiering absorbing more of the manual lifecycle-rule use cases) and continued S3 feature convergence with database-like guarantees (conditional writes via `If-Match`, stronger consistency) that reduce the need for a separate metadata store just to coordinate S3 writes. More speculative: S3 increasingly serving as the substrate under vector search and table formats (Iceberg, S3 Tables) rather than purely being "object storage," which changes how prefix design and request-rate planning get taught.

---

## Mental model

Think of S3 storage classes as a single dial trading **retrieval latency and per-request cost** against **per-GB storage cost**, with a "minimum commitment" tax at the archive end:

```
FAST RETRIEVAL, EXPENSIVE/GB          SLOW RETRIEVAL, CHEAP/GB
├──────────────┬──────────────┬─────────────────┬──────────────────┬─────────────────┤
│  S3 Standard │ Standard-IA/ │ Glacier Instant  │ Glacier Flexible │ Glacier Deep     │
│  (ms, no min │ One Zone-IA  │ Retrieval        │ Retrieval        │ Archive          │
│  duration)   │ (ms, 30-day  │ (ms, 90-day min) │ (min-hours,      │ (12-48hr,        │
│              │ min)         │                  │ 90-day min)      │ 180-day min)     │
└──────────────┴──────────────┴─────────────────┴──────────────────┴─────────────────┘
     Intelligent-Tiering moves objects automatically between the first 3-4 tiers
     based on observed access pattern, for a small per-object monitoring fee
```

Everything to the right trades speed for a lower $/GB-month, and every class except Standard/Standard-IA/One Zone-IA charges a retrieval fee per GB pulled back — the trap is choosing a cheap-to-store class for data you actually retrieve often, which flips the retrieval fees into costing more than Standard would have.

---

## How it actually works

### S3 storage classes — retrieval time and minimum duration, precisely

| Class | Retrieval time | Minimum storage duration | Notes |
|---|---|---|---|
| Standard | Milliseconds | None | Default, highest $/GB |
| Standard-IA | Milliseconds | 30 days | Per-GB retrieval fee |
| One Zone-IA | Milliseconds | 30 days | Single AZ — no AZ-failure resilience |
| Glacier Instant Retrieval | **Milliseconds** | 90 days | Cheapest class with millisecond access |
| Glacier Flexible Retrieval | Expedited 1-5 min, Standard 3-5 hrs, Bulk 5-12 hrs (free) | 90 days | Three speed/cost tiers within one class |
| Glacier Deep Archive | 12 hrs (standard) or 48 hrs | 180 days | Cheapest storage, longest retrieval |

[S3 Glacier storage classes — AWS](https://aws.amazon.com/s3/storage-classes/glacier/) — accessed 2026-08-01. **The minimum-duration charge matters even if you delete early**: deleting a Standard-IA object at day 10 still bills the remaining 20 days to hit the 30-day minimum; the same applies at 90 and 180 days for the Glacier tiers. This is the most common storage-class cost surprise — someone lifecycle-rules objects to Glacier Deep Archive expecting to delete some of them within weeks and gets billed the full 180-day minimum anyway.

**Intelligent-Tiering** automatically moves objects between Frequent, Infrequent, Archive Instant Access, and (if opted in) Archive/Deep Archive Access tiers based on 30/90/180+ day access-pattern thresholds, for a small monthly monitoring fee per object. It pays off when access patterns are genuinely unpredictable; it does not pay off for data with a known, stable access pattern where a manual lifecycle rule to a fixed class is simply cheaper (no monitoring fee, no automatic-tiering overhead).

### Strong read-after-write consistency — what changed and what didn't

**What changed (December 2020):** after any successful PUT of a new object or overwrite of an existing one, any subsequent GET or LIST immediately reflects that write, region-wide, with **no performance penalty, no additional cost, and no opt-in required** — this applies automatically to every bucket, including ones created years before the announcement.

**What did NOT change:** this is read-after-write consistency for the object store's own API semantics, not a transaction or locking system — two concurrent writers to the same key still race, and the last write wins with no built-in conflict detection unless you're using versioning (which then keeps both versions, but doesn't merge them). It also doesn't make S3 suitable as a general-purpose database with multi-key transactional guarantees — a single PUT is atomic, but there's no cross-object transaction primitive. And it doesn't affect **cross-region replication lag** — a replica in another region still catches up asynchronously, on its own timeline.

If a candidate still says "S3 is eventually consistent, so you need to handle stale reads after a write," that's a 2020-and-earlier answer; the correct framing today is "reads are strongly consistent after write, but concurrent writers to the same key still race, and cross-region replicas still lag."

### Prefix performance and request-rate limits

A single **partitioned prefix** can sustain **at least 3,500 PUT/COPY/POST/DELETE and 5,500 GET/HEAD requests per second**, and these limits scale linearly with the number of distinct prefixes — spreading load across many prefixes multiplies effective throughput with no hard ceiling on prefix count. [S3 request rate performance](https://aws.amazon.com/about-aws/whats-new/2018/07/amazon-s3-announces-increased-request-rate-performance) — accessed 2026-08-01. **The catch**: these per-prefix rates only apply once S3 has automatically partitioned that prefix based on sustained traffic — a cold prefix suddenly hit with a burst of traffic can throttle (`503 SlowDown`) before partitioning catches up. For predictable high-throughput access, pre-warming (gradually ramping traffic) or deliberately designing prefix structure (e.g., a hash prefix rather than a sequential timestamp prefix, which used to matter more before partitioning became automatic and per-prefix rather than lexicographic-range-based) reduces the risk of an early throttling window.

### Multipart upload and the incomplete-upload cost leak

Any upload split into parts (recommended above 100MB, required above 5GB) that never completes — client crash, network failure, abandoned upload — leaves already-uploaded parts sitting in the bucket, **billed as storage indefinitely**, invisible to `aws s3 ls` and the console's normal object listing. The fix is a lifecycle rule with the `AbortIncompleteMultipartUpload` action and a `DaysAfterInitiation` value (commonly 7 days), which is not enabled by default on new buckets and has to be explicitly configured. [S3 multipart upload cost leak](https://www.doit.com/blog/aws-s3-multipart-uploads-avoiding-hidden-costs-from-unfinished-uploads) — accessed 2026-08-01.

```json
// untested sketch — lifecycle rule JSON
{
  "Rules": [{
    "ID": "abort-incomplete-mpu",
    "Status": "Enabled",
    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
  }]
}
```

### Versioning, lifecycle, replication, Object Lock

- **Versioning** keeps every write as a distinct version rather than overwriting in place; a "delete" just adds a delete-marker version, and the actual data is only removed by a permanent delete of that specific version ID — this is what makes accidental-overwrite and accidental-delete recovery possible, at the storage cost of retaining every version.
- **Lifecycle rules** transition objects between storage classes or expire them based on age, prefix, or tag filters — the mechanism behind both cost optimization (move to IA/Glacier after N days) and the multipart-upload cleanup above.
- **Cross-Region Replication (CRR)** and **Same-Region Replication (SRR)** asynchronously copy objects to another bucket (different region or same region respectively) as they're written, for disaster recovery, compliance data residency, or reducing latency for geographically distributed readers — replication is not synchronous and not retroactive by default (existing objects need Batch Replication to backfill).
- **Object Lock** provides WORM (write-once-read-many) enforcement in either Governance mode (can be overridden by users with special permission, for internal policy enforcement) or Compliance mode (cannot be overridden by anyone, including the root account, until the retention period expires — used for regulatory retention requirements like SEC 17a-4).

### S3 events — at-least-once delivery and the notification-loss edge case

S3 event notifications (to SQS, SNS, Lambda, or EventBridge) are delivered **at least once**, meaning duplicate notifications for the same event are possible and consumers must be idempotent regardless. The less-discussed edge case: **on rare occasions, notifications can be lost entirely** — not just duplicated — which is why any system where missing an event is unacceptable (billing triggers, compliance archival) should not rely on S3 events as the sole signal; a periodic reconciliation job comparing bucket contents against what was actually processed is the belt-and-suspenders fix. A related, more common issue is **out-of-order delivery when the same key is overwritten multiple times in quick succession**: if a slower consumer is still processing an older version's notification when a newer one arrives, without using the event's `sequencer` field to detect and discard out-of-order events, a consumer can overwrite a newer processing result with an older one. [S3 Event Notifications ordering and duplicates](https://aws.amazon.com/blogs/storage/manage-event-ordering-and-duplicate-events-with-amazon-s3-event-notifications/) — accessed 2026-08-01.

### Presigned URLs

A presigned URL lets you grant time-limited access to a specific S3 operation (typically GET or PUT) without the requester needing AWS credentials at all — the URL itself encodes a signature computed from your credentials, valid until expiration (max 7 days for SigV4 with temporary credentials, or up to the underlying credential's own expiration if shorter). Common production use: browser-direct-to-S3 uploads that avoid routing large file bodies through your application servers, or time-limited download links for private content. The signature does not itself enforce content-type or size restrictions unless you build those into a **presigned POST** policy document instead of a simple presigned URL — a bare presigned PUT URL will accept whatever the client sends.

### EBS volume types — IOPS and throughput

| Type | Baseline | Max IOPS | Max throughput | Use case |
|---|---|---|---|---|
| gp3 | **3,000 IOPS, 125 MiB/s**, independent of volume size | 16,000 | 1,000 MiB/s (extra cost above baseline) | Default choice for most workloads |
| gp2 | 3 IOPS/GiB (min 100), burst to 3,000 via credits on volumes <1TB | 16,000 | 250 MiB/s | Legacy; burst-credit model makes performance size-dependent and less predictable |
| io2 Block Express | Provisioned | up to 256,000 | up to 7,500 MiB/s | High-performance databases needing guaranteed IOPS |
| st1 (HDD) | Throughput-optimized | N/A (throughput-based) | 500 MiB/s | Big sequential workloads (big data, log processing) |
| sc1 (HDD) | Cold, cheapest | N/A | 250 MiB/s | Infrequently accessed data |

[EBS gp3 vs gp2 — CloudZero](https://www.cloudzero.com/blog/aws-gp2-vs-gp3/) — accessed 2026-08-01. **The gp3 vs gp2 change that matters**: gp3 decoupled IOPS/throughput from volume size entirely, giving a flat 3,000 IOPS/125 MiB/s baseline regardless of how small the volume is, and letting you provision more of either independently for an incremental cost — gp2's burst-credit model meant a small volume's performance was unpredictable once burst credits were exhausted. Migrating from gp2 to gp3 is close to a free win for most workloads: roughly 20% cheaper per GiB at the same or better baseline performance, with no application-visible difference besides eliminating burst-credit risk.

### EFS vs FSx — and when a shared filesystem is the wrong idea

- **EFS**: NFS-based, POSIX-compliant, elastic (grows/shrinks automatically, pay for what's stored), Linux-native. Good for shared config, home directories, and Linux workloads genuinely needing POSIX file semantics shared across many compute nodes.
- **FSx for Lustre**: high-throughput, low-latency, purpose-built for HPC/ML training and analytics, and specifically designed to sit in front of an S3 bucket as a fast POSIX cache layer for training jobs reading the same dataset repeatedly.
- **FSx for NetApp ONTAP / FSx for Windows File Server**: multi-protocol (NFS, SMB, iSCSI) with enterprise data-management features (snapshots, dedup, cross-region replication) for workloads that specifically need ONTAP's feature set or native Windows SMB shares.

**When a shared filesystem is the wrong idea**: reaching for EFS/FSx as a substitute for proper service decoupling — using a shared filesystem as an ad-hoc message queue or shared mutable state between microservices reintroduces the tight coupling and lock-contention problems that led people away from shared-disk architectures in the first place. If the actual need is "many readers, occasional writer, object-shaped data," S3 is almost always the better fit at lower cost and with better throughput scaling; reach for EFS/FSx specifically when POSIX file semantics (random-access reads/writes to the same file, directory locking, `fsync` guarantees) are a hard requirement, not a convenience.

---

## Build it from scratch

Minimal idempotent S3-event consumer that defends against both duplicate delivery and out-of-order delivery via the sequencer:

```python
# untested sketch
import json

processed_versions = {}  # key -> highest sequencer seen; use DynamoDB in production

def handler(event, context):
    for record in event["Records"]:
        key = record["s3"]["object"]["key"]
        sequencer = record["s3"]["object"].get("sequencer", "")
        # Reject anything older than what we've already processed for this key —
        # defends against both duplicate delivery and out-of-order delivery.
        if key in processed_versions and sequencer <= processed_versions[key]:
            continue
        processed_versions[key] = sequencer
        process_object(key)

def process_object(key):
    print(f"processing {key}")
```

Production version stores `processed_versions` in DynamoDB with a conditional write (`sequencer > :current`) rather than an in-memory dict, since Lambda execution environments aren't shared across all invocations.

---

## How it's done in production

A typical production setup layers: **S3 Standard** for hot data with a lifecycle rule transitioning to **Intelligent-Tiering** or a fixed IA/Glacier class based on known access patterns, **`AbortIncompleteMultipartUpload`** enabled on every bucket as a default hygiene rule, **versioning + Object Lock (Governance mode)** on anything requiring accidental-deletion protection, **CRR** for disaster recovery or compliance residency requirements, **gp3** as the default EBS volume type unless a workload specifically needs io2's guaranteed IOPS ceiling, and **EventBridge** (not raw S3-to-SQS) as the event routing layer once more than one consumer needs the same event, since EventBridge supports content-based filtering and multiple targets without bucket-notification-config contention (a bucket can only have one notification configuration, which becomes a bottleneck with multiple independent consumers).

| Symptom | Cause | Fix |
|---|---|---|
| S3 bill has a mysterious storage line item with no matching visible objects | Incomplete multipart uploads accumulating, invisible to normal listing | `aws s3api list-multipart-uploads`, then lifecycle rule with `AbortIncompleteMultipartUpload` |
| `503 SlowDown` errors on a newly created prefix under sudden load | Prefix not yet auto-partitioned by S3 for the new traffic level | Ramp traffic gradually, or pre-warm by distributing initial load across multiple prefixes |
| Event-driven pipeline processes an old version of an object after a rapid overwrite | Consumer processed events out of order, no sequencer check | Compare `sequencer` field, discard events older than the last processed one per key |
| A batch job deletes Glacier Deep Archive objects "early" and the bill doesn't drop | Minimum storage duration (180 days) still bills the remainder regardless of actual deletion date | Plan retention against the minimum duration before choosing the class, not after |
| gp2 volume performance degrades under sustained load | Burst credits exhausted on a small volume, falling back to baseline 3 IOPS/GiB | Migrate to gp3 for a flat, predictable 3,000 IOPS baseline independent of size |
| Two microservices sharing an EFS mount develop subtle race conditions on the same file | Shared filesystem used as ad-hoc coordination/state instead of a proper queue or database | Replace with S3 + event notification, or a real message queue, or a database with proper locking |
| Presigned upload URL used maliciously to upload a huge or wrong-content-type file | Bare presigned PUT URL has no content constraints | Use a presigned POST with an explicit policy document constraining content-type and size |

---

## Tradeoffs & when NOT to use it

- **Don't pick a cold storage class for data with an unpredictable but non-trivial retrieval frequency** — Intelligent-Tiering's monitoring fee is cheaper than guessing wrong and eating repeated retrieval fees from an overly-cold manual tier.
- **Don't treat S3's strong consistency as a substitute for real coordination.** Two writers racing the same key still produces last-write-wins with no merge; if you need compare-and-swap semantics, use S3's conditional writes (`If-Match`/`If-None-Match` on PUT) explicitly, don't assume consistency alone prevents races.
- **Don't rely solely on S3 event notifications where a missed event is unacceptable** — at-least-once delivery with a documented rare-loss edge case means anything compliance- or billing-critical needs a reconciliation fallback, not just an event subscriber.
- **Don't use EFS/FSx as a substitute for service decoupling.** If the real need is "pass data between services," S3 plus events, or a queue, or a database is almost always the better architecture than a shared POSIX filesystem, which reintroduces coupling and lock contention.
- **Don't default to gp2 for new volumes** — gp3 is cheaper and has more predictable performance for the overwhelming majority of workloads; there's essentially no reason to provision new gp2 volumes today.
- **Glacier's minimum-duration charges make it a bad fit for data with uncertain or short retention needs** — model the actual expected lifetime against the 90/180-day minimums before committing.

---

## Interview questions

### Q1 — Is S3 eventually consistent?
**Testing:** whether the candidate's knowledge is post-2020 or stuck in an old mental model.
**Answer:** No, not since December 2020 — S3 delivers strong read-after-write consistency automatically, for all requests, in all regions, at no additional cost or performance penalty. A GET or LIST immediately after a successful PUT or overwrite reflects that write. This applies to every bucket automatically, including ones that existed before the change.
**Follow-up trap:** *"So does that mean S3 is safe to use as a coordination mechanism between two writers?"* — no, strong read-after-write consistency doesn't give you transactional or compare-and-swap semantics by default; two concurrent writers to the same key still race with last-write-wins unless you explicitly use conditional writes (`If-Match`/`If-None-Match`).

### Q2 — Walk through the S3 storage class options and their retrieval-time/minimum-duration tradeoffs.
**Testing:** whether the numbers are known, not just the class names.
**Answer:** Standard and Standard-IA/One Zone-IA all retrieve in milliseconds; the IA tiers add a 30-day minimum storage duration and a per-GB retrieval fee. Glacier Instant Retrieval also retrieves in milliseconds but at a lower storage cost, with a 90-day minimum. Glacier Flexible Retrieval has three speed tiers — expedited (1-5 min), standard (3-5 hrs), and free bulk (5-12 hrs) — also with a 90-day minimum. Glacier Deep Archive is cheapest to store but takes 12-48 hours to retrieve, with a 180-day minimum.
**Follow-up trap:** *"A team deletes Glacier Deep Archive objects after 30 days to save money. Does that work?"* — no, the 180-day minimum storage duration still bills for the remaining 150 days regardless of actual deletion date; early deletion from any class with a minimum duration doesn't reduce the bill below that minimum.

### Q3 — What are the S3 request-rate limits per prefix, and what's the gotcha?
**Testing:** the specific numbers plus the less-known caveat.
**Answer:** At least 3,500 PUT/COPY/POST/DELETE and 5,500 GET/HEAD requests per second per partitioned prefix, scaling linearly with the number of distinct prefixes used. The gotcha: these rates only apply once S3 has automatically partitioned that prefix based on sustained traffic — a cold prefix suddenly hit with a burst can throttle with `503 SlowDown` before partitioning catches up, so predictable high-throughput access benefits from gradual ramp-up or pre-distributing initial load across multiple prefixes.
**Follow-up trap:** *"Does prefix naming still matter for performance the way it used to (avoiding sequential timestamp prefixes)?"* — much less than pre-2018, since S3 now partitions per-prefix automatically rather than by lexicographic key-range; it's not zero-impact for sudden bursts on a cold prefix, but the old advice to reverse timestamps or add random hash prefixes for steady-state throughput is largely obsolete.

### Q4 — Explain the incomplete multipart upload cost leak and how you'd catch it in an existing account.
**Testing:** whether this specific, easy-to-miss cost bug is known.
**Answer:** A multipart upload that never completes (client crash, network failure, abandoned client) leaves already-uploaded parts billed as storage indefinitely, and they're invisible to `aws s3 ls` and the console's default object view. `aws s3api list-multipart-uploads` surfaces them directly. The fix going forward is a lifecycle rule with `AbortIncompleteMultipartUpload` and a `DaysAfterInitiation` value, which isn't on by default for new buckets.
**Follow-up trap:** *"Why would a well-behaved client ever leave an incomplete multipart upload?"* — any interrupted upload where the client doesn't explicitly call `AbortMultipartUpload` on failure — a crashed process, a killed container, a network partition mid-upload — leaves the parts orphaned server-side with no automatic cleanup unless the lifecycle rule exists.

### Q5 — Design an idempotent, order-safe S3 event consumer for a pipeline where objects get overwritten frequently.
**Testing:** synthesizing at-least-once delivery, duplicate handling, and the ordering edge case into one design.
**Answer:** Track the highest `sequencer` value processed per key (in DynamoDB with a conditional write, not in-memory, since consumers may not be a single persistent process) and discard any incoming event whose sequencer is less than or equal to the stored value — this defends against both duplicate delivery (same sequencer, discard) and out-of-order delivery (an older version's notification arriving after a newer one already processed). Because S3 events can rarely be lost entirely, pair this with a periodic reconciliation job comparing bucket state against what's been recorded as processed, for any pipeline where a silently missed event is unacceptable.
**Follow-up trap:** *"Why not just use the object's LastModified timestamp instead of sequencer?"* — timestamps have coarser resolution and clock-skew risk across S3's distributed backend; the sequencer is specifically designed as a monotonically comparable hex value per key for exactly this ordering purpose and doesn't have those failure modes.

### Q6 — gp2 vs gp3 — what actually changed, and is there ever a reason to still provision gp2?
**Testing:** currency on a genuinely useful, low-risk migration most candidates should know cold.
**Answer:** gp3 decoupled IOPS and throughput from volume size, giving a flat 3,000 IOPS / 125 MiB/s baseline regardless of volume size, with the ability to provision more of either independently at incremental cost, and it's roughly 20% cheaper per GiB than gp2. gp2's performance instead scales with size (3 IOPS/GiB, minimum 100) and relies on a burst-credit model for small volumes, meaning performance can degrade unpredictably once credits are exhausted. There's essentially no reason to provision new gp2 volumes today; migrating existing gp2 to gp3 is close to a free win with no application-visible change besides eliminating burst-credit risk.
**Follow-up trap:** *"Is there any workload where gp2's burst model is actually preferable?"* — not really preferable, but a legacy consideration: if an existing pipeline has hard-coded assumptions around gp2's burst-credit CloudWatch metrics for capacity alerting, migrating requires updating that monitoring, which is an operational cost, not a technical reason to prefer gp2.

### Q7 — Two microservices need to exchange large files. A teammate proposes mounting a shared EFS volume between them. What's your reaction?
**Testing:** the "when a shared filesystem is the wrong idea" judgment.
**Answer:** Push back unless there's a hard POSIX requirement (random-access read/write to the same file, directory locking, fsync guarantees) — a shared filesystem for inter-service data exchange reintroduces the tight coupling and lock-contention problems service decoupling is meant to avoid. S3 with event notifications (or a queue) gives the same "pass a file between services" capability with better throughput scaling, no shared-mount failure domain, and services that don't need to coordinate on filesystem semantics at all.
**Follow-up trap:** *"What if the files are small and frequent, wouldn't S3's per-request cost add up?"* — S3 request costs are genuinely low at typical volumes and the request-rate limits (3,500-5,500/sec/prefix, scaling with prefix count) accommodate high-frequency small-file patterns; the crossover where a shared filesystem's per-GB-month cost model wins over S3's storage-plus-request model is rare and worth actually calculating rather than assuming.

### Q8 — When would FSx for Lustre be the right choice over both S3 and EFS?
**Testing:** the ML/HPC-specific use case, relevant to the student's SageMaker/EMR background.
**Answer:** When a training job repeatedly reads the same large dataset across many compute nodes and needs POSIX file semantics with much higher throughput and lower latency than S3 provides natively, and EFS's throughput/latency profile isn't sufficient for the access pattern. FSx for Lustre specifically supports linking directly to an S3 bucket as its backing data repository, acting as a fast POSIX cache layer in front of S3 for exactly this training-data-access pattern, without requiring a full copy-and-manage-separately workflow.
**Follow-up trap:** *"If it's just caching S3, why not read directly from S3 in the training job?"* — for workloads with heavy random access or requiring POSIX semantics (memory-mapped files, certain data loaders), direct S3 SDK reads either don't fit the access pattern or add meaningful per-object request overhead at the read volumes involved; FSx for Lustre's POSIX interface and caching removes that overhead for those specific access patterns, at the cost of provisioning and paying for the filesystem layer.

### Q9 — Explain Object Lock's Governance vs Compliance modes and when each is appropriate.
**Testing:** precision on a compliance-relevant feature that's easy to get subtly wrong.
**Answer:** Governance mode enforces WORM retention but can be overridden by a user with the specific `s3:BypassGovernanceRetention` permission — appropriate for internal policy enforcement where an authorized admin might legitimately need an exception. Compliance mode cannot be overridden by anyone, including the root account, until the retention period naturally expires — appropriate for actual regulatory retention mandates (like SEC 17a-4) where "an admin can always override it" would defeat the entire compliance purpose.
**Follow-up trap:** *"If Compliance mode can't be overridden by root, how do you fix a mistake — like locking the wrong bucket for 7 years?"* — you generally can't undo it before expiration; this is a deliberate design choice reflecting genuine regulatory requirements, which is exactly why Compliance mode should only be applied after careful review, not as a default "safer" choice over Governance mode.

### Q10 — A presigned URL for uploads was abused to upload a 50GB file when the app only expected small images. What went wrong and how do you fix it?
**Testing:** knowing presigned URLs have no built-in constraints unless deliberately added.
**Answer:** A bare presigned PUT URL only constrains the specific object key and expiration — it doesn't constrain content-type, content-length, or any other property of what gets uploaded; whatever the client sends, S3 accepts under that signature. The fix is a presigned POST with an explicit policy document specifying content-length-range and content-type conditions, which S3 enforces server-side before accepting the upload, rather than relying on client-side validation that an attacker can simply skip.
**Follow-up trap:** *"Does a presigned POST policy protect against a malicious file's actual content, like a virus in a valid-sized image slot?"* — no, size and content-type constraints don't validate content; that requires a separate scan step (e.g., triggering a Lambda via S3 event to run antivirus/content validation) after upload, before treating the object as trusted.

### Q11 — Design cost-optimal storage for a dataset with 6 months of hot access, then unpredictable but occasional access afterward.
**Testing:** synthesizing storage-class knowledge into a real lifecycle design, not just naming classes.
**Answer:** Standard for the first 6 months given the confirmed hot-access pattern (no benefit from IA/Intelligent-Tiering's monitoring fee during a period access is already known to be frequent), then transition via lifecycle rule to Intelligent-Tiering rather than a fixed cold class, since post-6-month access is explicitly described as unpredictable — Intelligent-Tiering's automatic movement and monitoring fee is cheaper than guessing a fixed class wrong and eating either excess storage cost (too hot a class) or excess retrieval fees (too cold a class) from mispredicted access frequency.
**Follow-up trap:** *"What if 'unpredictable but occasional' actually means less than once a quarter for most objects?"* — that access frequency is exactly what Intelligent-Tiering's Archive Instant Access and deeper archive tiers are designed to capture automatically once it opts into them, without you needing to model or guess the exact frequency distribution across the whole dataset upfront.

---

## Red flags that fail you

- Saying S3 is eventually consistent — stale since December 2020.
- Not knowing Glacier's minimum storage duration charges apply even to early deletion.
- Treating presigned URLs as inherently safe without knowing bare presigned PUT has no content constraints.
- Recommending EFS/FSx as a default inter-service data exchange mechanism instead of S3 or a queue.
- Not knowing gp3 exists or defaulting to gp2 for new volumes with no justification.
- Assuming S3 events are guaranteed exactly-once or never lost.
- Confusing Object Lock's Governance and Compliance modes.
- Not knowing what causes the incomplete multipart upload cost leak.

---

## Cheat card

```
S3 CONSISTENCY: strong read-after-write, ALL requests, since Dec 2020, no cost/perf penalty, no opt-in.
  Does NOT give: cross-writer coordination (still last-write-wins; use If-Match for CAS),
                 cross-region replication sync (still async, still lags)

STORAGE CLASSES (retrieval time / min duration):
  Standard            ms / none
  Standard-IA/1Zone-IA ms / 30 days
  Glacier Instant      ms / 90 days
  Glacier Flexible     1-5min(exp)/3-5hr(std)/5-12hr(bulk,free) / 90 days
  Glacier Deep Archive 12-48hr / 180 days
  Early delete still bills the remaining minimum-duration days.

PREFIX LIMITS: >=3,500 PUT/COPY/POST/DELETE, >=5,500 GET/HEAD per SEC per partitioned prefix.
  Scales with # prefixes. Cold prefix + sudden burst -> 503 SlowDown before auto-partition catches up.

MULTIPART UPLOAD LEAK: incomplete uploads bill storage forever, invisible to normal `ls`.
  Fix: lifecycle rule AbortIncompleteMultipartUpload, DaysAfterInitiation (not default -- must add)

EVENTS: at-least-once delivery. Rare total loss possible (not just duplicates).
  Ordering: use `sequencer` field, discard events <= last processed per key.
  Multiple consumers -> route through EventBridge, not raw bucket notification (1 config/bucket limit)

OBJECT LOCK: Governance = overridable w/ special perm. Compliance = NEVER overridable, even by root.

PRESIGNED URL: bare PUT = no content-type/size constraint. Use presigned POST + policy doc to constrain.

EBS:
  gp3: 3,000 IOPS / 125 MiB/s baseline, FLAT regardless of size. Extra IOPS/throughput = incremental $.
  gp2: 3 IOPS/GiB (min 100), burst credits on <1TB -- unpredictable once exhausted. ~20% pricier than gp3.
  io2 Block Express: up to 256,000 IOPS, 7,500 MiB/s -- guaranteed-IOPS databases.
  Default to gp3. No reason to provision new gp2.

EFS vs FSx: EFS = NFS, POSIX, Linux shared storage. FSx Lustre = HPC/ML training, S3-backed cache layer.
  FSx ONTAP/Windows = multi-protocol (NFS/SMB/iSCSI) + enterprise data mgmt features.
  Shared filesystem as inter-service message-passing = usually the wrong architecture; use S3+events or a queue.
```

## Sources

- [Amazon S3 now delivers strong read-after-write consistency — AWS announcement](https://aws.amazon.com/about-aws/whats-new/2020/12/amazon-s3-now-delivers-strong-read-after-write-consistency-automatically-for-all-applications) — accessed 2026-08-01
- [Secure archive storage — Amazon S3 Glacier storage classes](https://aws.amazon.com/s3/storage-classes/glacier/) — accessed 2026-08-01
- [Amazon S3 Announces Increased Request Rate Performance](https://aws.amazon.com/about-aws/whats-new/2018/07/amazon-s3-announces-increased-request-rate-performance) — accessed 2026-08-01
- [Best practices design patterns: optimizing S3 performance — AWS docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html) — accessed 2026-08-01
- [S3 Multipart Uploads — Avoiding Hidden Costs — DoiT](https://www.doit.com/blog/aws-s3-multipart-uploads-avoiding-hidden-costs-from-unfinished-uploads) — accessed 2026-08-01
- [Configuring a bucket lifecycle for incomplete multipart uploads — AWS docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html) — accessed 2026-08-01
- [Manage event ordering and duplicate events — AWS Storage Blog](https://aws.amazon.com/blogs/storage/manage-event-ordering-and-duplicate-events-with-amazon-s3-event-notifications/) — accessed 2026-08-01
- [AWS EBS: gp2 vs gp3 performance and cost — CloudZero](https://www.cloudzero.com/blog/aws-gp2-vs-gp3/) — accessed 2026-08-01
- [AWS FSx for Lustre vs EFS: Head to Head — NetApp](https://www.netapp.com/blog/aws-fsxo-blg-aws-fsx-for-lustre-vs-efs-head-to-head/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
- 2026-08-09 — Amazon S3 Tables adds the Variant data type from the Apache Iceberg V3 spec, giving a native way to store semi-structured payloads (IoT/logs) in a table without JSON-blob workarounds ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-price-reduction-of-gpt-models-in-bedrock-cloudwatch-managed-collectors-for-prometheus-metrics-and-more-august-3-2026/))

## The 30-second version

S3 has delivered strong read-after-write consistency automatically for every request since December 2020, so a stale "S3 is eventually consistent" answer is now itself stale, though concurrent writers to the same key still race with last-write-wins unless you use conditional writes. Storage classes trade retrieval latency and per-request cost against per-GB storage cost, with real minimum-duration charges (30/90/180 days) that bill even on early deletion — Intelligent-Tiering earns its monitoring fee specifically when access patterns are genuinely unpredictable, not as a default. S3 events are at-least-once with a rare total-loss edge case, so idempotency plus a sequencer-based ordering check plus a reconciliation fallback for anything critical is the correct defensive design, not an afterthought. EBS gp3 has fully superseded gp2 with flat, predictable baseline performance decoupled from volume size at a lower cost. A shared filesystem like EFS or FSx is the right tool only when POSIX file semantics are a hard requirement — using one as inter-service message passing reintroduces the coupling problems service decoupling exists to avoid.
