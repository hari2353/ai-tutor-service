# Kafka Semantics, Exactly-Once Illusions, CDC, Stream Processing

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T10-messaging` · **Tags:** fundamentals

## The 30-second version

Kafka is an append-only, partitioned, replicated log: ordering is a per-partition guarantee only, never a per-topic one, so any requirement for ordered processing of a logical entity (a user, an order) has to be satisfied by partitioning on that entity's key, and skew in that key becomes skew in a specific consumer's load. "Exactly-once" is real but narrower than the name suggests: the idempotent producer (dedup by producer-id + sequence number) plus transactions (atomic multi-partition writes, including consumer offset commits) gives you effectively-once *inside Kafka*, but the instant a consumer writes a side effect to an external system (a database, an API call), you are back to needing idempotency at that boundary, because Kafka cannot make an external write transactional with its own commit. Consumer lag, not throughput, is the metric that tells you the system is actually falling behind, and a rebalance is a stop-the-world event for the affected partitions unless you're on the cooperative-sticky protocol. Debezium turns database writes into a Kafka log via the transaction log (not polling), which is what makes the outbox pattern practical, and stream processing frameworks (Kafka Streams, Flink) add windowed aggregation and stateful joins on top of that log, at the cost of needing to reason about watermarks and out-of-order data that batch processing never had to.

## Why this gets asked

Every engineer who has operated Kafka in production has been paged for consumer lag climbing during a rebalance storm, or has shipped a bug where "exactly-once" was assumed to extend past Kafka's own boundary into a database write that then duplicated on retry. The interviewer is testing whether you understand that Kafka's guarantees are narrower and more specific than marketing language suggests, and whether you can reason about ordering, delivery semantics, and consumer group mechanics as separate, composable properties rather than a single "Kafka handles it" black box.

## Lineage: past → present → future

**What came before.** Pre-2011 message queues (ActiveMQ, RabbitMQ, traditional JMS brokers) modeled messaging as point-to-point delivery with per-message acknowledgment and broker-side state tracking which consumer had seen which message. This worked at moderate throughput but the broker's per-message bookkeeping became the bottleneck at LinkedIn's activity-tracking and metrics-pipeline scale, the actual pain that motivated Kafka's creation (Kreps, Narkhede, Rao, 2011): a queue that acknowledges and deletes each message individually cannot sustain the write volume of a company logging every user action, and re-consuming already-processed data for reprocessing or a new downstream consumer was awkward or impossible once messages were deleted on ack. Kafka's answer was to invert the model: the broker keeps an append-only, immutable log per partition and consumers track their own read position (offset), turning "did this consumer see this message" from broker-side state into a single, cheap, consumer-side integer, and letting the same log serve arbitrarily many independent consumer groups without any extra broker cost.

**Where it stands now.** Kafka is the default choice for high-throughput, multi-consumer event streaming, and the ecosystem consensus has shifted from "Kafka vs. traditional queues" to "which managed or self-hosted log fits this specific throughput and ordering requirement." The live disagreement is mostly about operational model: Confluent-style self-managed/BYOC Kafka versus fully managed alternatives (MSK, Confluent Cloud) versus architecturally different systems (Pulsar's separated compute/storage tiers via BookKeeper, enabling independent scaling and tiered storage) versus simpler managed queues (SQS, Kinesis) for teams that don't need Kafka's replay/multi-consumer-group semantics at all. On exactly-once specifically, the field has converged on "effectively-once inside the broker, idempotency at every external boundary" as the honest framing, replacing early marketing that implied end-to-end exactly-once was simply a config flag.
As of Kafka 4.0, the exactly_once_v2 protocol (introduced 2.5) plus KRaft mode's removal of the ZooKeeper-based transaction coordinator path materially reduced transaction-commit overhead ([AutoMQ, Kafka Exactly-Once Semantics](https://github.com/AutoMQ/automq/wiki/What-is-Kafka-Exactly-Once-Semantics) — accessed 2026-08-01).

**Where it's heading.** High confidence: the industry keeps converging on "Kafka as the durable log of record, purpose-built stream/batch engines (Flink, Kafka Streams, Spark Structured Streaming) as the compute layer on top," rather than trying to make the broker itself do increasingly complex processing. Tiered storage (offloading older log segments to object storage, already default-architecture in Pulsar and increasingly available in Kafka via KIP-405-style tooling) continues displacing "just buy more local disk" as the answer to long retention. More speculatively: CDC-first architectures (treating the database's own transaction log as the source of truth event stream, rather than dual-writing to a queue) keep gaining ground as Debezium-style connectors mature, because dual-write consistency bugs are a well-understood, recurring failure class that CDC sidesteps structurally.

---

## Mental model

```
A TOPIC IS NOT ONE LOG. IT'S N INDEPENDENT LOGS (PARTITIONS).

  topic "orders", 4 partitions, key = order_id (hashed to choose partition)

  partition 0: [msg][msg][msg][msg]------------->  offset increases, append-only
  partition 1: [msg][msg]----------------------->
  partition 2: [msg][msg][msg]------------------->
  partition 3: [msg]------------------------------>

  ORDERING GUARANTEE: only WITHIN a partition. Messages with the same key
  always land on the same partition (same hash), so per-key order is
  preserved. Across partitions: NO ordering guarantee at all.

CONSUMER GROUP = one partition assigned to at most one consumer AT A TIME

  group "billing-service", 4 consumers, 4 partitions -> 1:1 mapping, max parallelism
  group "billing-service", 2 consumers, 4 partitions -> each consumer gets 2
  group "billing-service", 6 consumers, 4 partitions -> 2 consumers sit IDLE
                                                         (can't have more consumers
                                                          than partitions doing work)

CONSUMER LAG = the metric that actually tells you if you're falling behind

  latest_offset_in_partition - consumer_committed_offset = lag
  lag climbing linearly, not throughput dropping, is the production symptom
  of a consumer that can't keep up (slow processing, a stuck downstream call,
  or a rebalance storm repeatedly resetting progress)
```

**"Exactly-once" scope, drawn honestly:**

```
producer ──(idempotent + transactional)──▶ Kafka log ──(transactional read)──▶ consumer
   \_________________ EFFECTIVELY-ONCE, guaranteed BY KAFKA ITSELF __________/

                                                            consumer ──▶ external DB / API call
                                                               \___ NOT covered by Kafka's EOS.
                                                                    Needs its OWN idempotency
                                                                    (unique constraint, upsert,
                                                                     dedup key) at that boundary.
```

---

## How it actually works

### The log, partitions, offsets

A Kafka topic is split into partitions, each partition is a strictly ordered, append-only sequence of records, each identified by a monotonically increasing **offset** unique within that partition. Producers choose a partition per message, by explicit partition number, by a round-robin/sticky default when no key is given, or (the common case) by hashing the message **key**, guaranteeing every message with the same key lands on the same partition. This is the entire mechanism behind "ordered by key": it's not a special ordering feature, it's a side effect of hash-based routing plus in-partition append order. **Ordering is per-partition only.** If a downstream requirement is "process all events for user X in the order they occurred," the correct (and only) way to satisfy it is to key by user X's id, there is no topic-wide ordering guarantee to fall back on, and increasing partition count later changes the key-to-partition hash mapping, silently breaking ordering for in-flight or replayed data unless you use a custom partitioner that's stable across resizes.

### Consumer groups and rebalancing

Consumers in the same **consumer group** split a topic's partitions among themselves so each partition is consumed by exactly one group member at a time; partition count is therefore the hard ceiling on a group's consumption parallelism, more consumers than partitions means some sit idle. When group membership changes (a consumer joins, leaves, or is considered dead by the group coordinator after a missed heartbeat, default `session.timeout.ms` is commonly configured around 10-45s depending on version and workload), a **rebalance** reassigns partitions.

The original ("eager") rebalance protocol is **stop-the-world**: every consumer in the group gives up all its partitions and the group pauses entirely until reassignment completes, even for consumers whose partition assignment doesn't change. **Cooperative rebalancing** (KIP-429, the incremental cooperative rebalance protocol, generally available from Kafka 2.4+, using the `CooperativeStickyAssignor`) fixes this: it runs as a two-phase, incremental protocol where only the specific partitions actually moving are revoked, unaffected consumers keep processing throughout, and revocations happen one increment at a time rather than a full stop ([Cooperative Rebalancing in the Kafka Consumer — Confluent](https://www.confluent.io/blog/cooperative-rebalancing-in-kafka-streams-consumer-ksqldb/) — accessed 2026-08-01; [KIP-429 — Apache Kafka wiki](https://cwiki.apache.org/confluence/x/vAclBg) — accessed 2026-08-01). The observable symptom of a rebalance storm in production: consumer lag spikes sharply and repeatedly, correlated with consumer pod restarts/scaling events or overly aggressive `session.timeout.ms`/`max.poll.interval.ms` settings that cause consumers to be evicted for slow processing, which triggers another rebalance, which pauses processing further, a feedback loop.

### "Exactly-once" as an illusion, precisely stated

Kafka's exactly-once semantics (EOS, introduced in 0.11, refined via `exactly_once_v2` from 2.5) is built from two distinct mechanisms:

1. **Idempotent producer**: each producer gets a unique producer ID (PID); every message carries a per-partition sequence number. If a broker sees a sequence number it's already accepted (from a retried send after a timeout, for instance), it silently discards the duplicate and returns success. This solves **producer-retry duplication**, not application-level duplicate submission.
2. **Transactions**: a producer can atomically write to multiple partitions and, critically, atomically commit consumer offsets alongside output writes in a "consume-transform-produce" pipeline, so a consumer either sees the full transaction's writes or none of them (controlled via `isolation.level=read_committed`).

Together, these give you **effectively-once processing entirely within Kafka**: no duplicate input records are double-counted by producers, and downstream consumers reading with `read_committed` never see partial or duplicate transactional writes. This is genuinely a strong, useful guarantee, but it is scoped to Kafka's own write path. The moment a consumer's processing has a side effect outside Kafka, writing a row to Postgres, calling a payment API, sending an email, none of that is covered by Kafka's transaction. If the consumer commits its Kafka offset and then crashes before the external write completes (or vice versa), you get exactly the duplicate-or-lost-write problem EOS was supposed to solve, just moved one layer down. **The fix is the same idempotency toolkit you'd need without Kafka at all**: a unique constraint or upsert key at the external system, a dedup table keyed by a message's unique id, or (for the tightest coupling) an actual two-phase pattern like the transactional outbox. This is why "exactly-once" is better understood as **effectively-once inside Kafka, at-least-once plus your own idempotency everywhere else** ([Exactly-once Semantics is Possible — Confluent](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) — accessed 2026-08-01).

### Consumer lag: the metric and its symptom

**Lag** for a given partition and consumer group is `latest_offset - committed_offset`. It's the single most important operational metric for a streaming pipeline because it directly measures "how far behind is this consumer from real-time," in a way that raw throughput numbers don't: a consumer processing 10,000 messages/sec can still be catastrophically behind if the producer is writing 50,000/sec. **The symptom that shows up in monitoring**: lag climbing roughly linearly (not spiking and recovering) means sustained under-capacity, either the consumer's processing is genuinely too slow per message (a blocking downstream call, unbatched DB writes) or there simply aren't enough consumer instances for the partition count and throughput. A lag pattern where **one partition's lag is dramatically higher than the group average** is the specific symptom of **key skew**: a small number of hot keys (a popular user, a viral product) concentrated on one partition, which no amount of adding more consumers fixes, since that one partition can still only be served by one consumer at a time.

### Retention vs. compaction

Two independent, combinable cleanup policies, set via `cleanup.policy`:

- **`delete`** (the default): discards whole log segments once they age past `log.retention.hours` (default **168 hours / 7 days**) or exceed a size limit. This is "keep everything for N days, then drop it," appropriate for event streams where old events lose relevance (metrics, clickstream, logs).
- **`compact`**: retains only the **latest value per key**, regardless of age, by periodically rewriting segments and discarding superseded records for the same key. This turns a topic into a durable, replayable representation of "current state per key," the mechanism Kafka Streams and ksqlDB rely on for changelog topics backing state stores, and what CDC topics typically use so a consumer can always reconstruct current row state by replaying from the beginning. Deleting a key is done via a **tombstone** (a record with the key and a `null` value); tombstones themselves are retained for `delete.retention.ms` (default **24 hours**) after becoming eligible for cleanup, so downstream consumers have a window to observe the deletion before it disappears entirely, missing that window means a slow consumer can silently miss a delete.
- **`compact,delete`** (hybrid): compaction for the latest-value-per-key semantics plus a hard time-based cap, common for topics that need current state but also want to bound worst-case storage.

### CDC via Debezium

Debezium reads a database's **transaction log directly** (MySQL binlog, Postgres WAL, SQL Server CDC tables), not by polling application tables, which means zero extra load on the tables being captured and near-real-time propagation of every committed change (inserts, updates, deletes) as a Kafka record. It's deployed as a Kafka Connect source connector, producing one topic per captured table with before/after row images. This is the mechanism that makes the **transactional outbox pattern** practical: instead of an application dual-writing to its own database and a message broker in the same logical operation (a classic dual-write inconsistency, the database commit can succeed while the broker publish fails, or vice versa), the application writes an "outbox" row in the *same database transaction* as its business data, and Debezium's CDC stream on that outbox table is what actually reaches Kafka. This converts a distributed dual-write problem into a single-database ACID transaction plus a reliable, log-based relay, at the cost of an extra table and connector to operate.

### Stream processing: windowing, joins, state

Batch processing (a nightly Spark job over yesterday's Parquet files) operates on a bounded, complete dataset, so there's no ambiguity about "when is this aggregation final." Stream processing (Kafka Streams, Flink) operates on an unbounded, continuously arriving log, forcing a genuinely new set of decisions:

- **Windowing** groups unbounded data into finite chunks for aggregation. **Tumbling windows** are fixed-size, non-overlapping (each record belongs to exactly one window, e.g. "count events per 5-minute bucket"). **Hopping windows** are fixed-size but overlapping, advancing by a step smaller than the window size, so one record can fall into multiple windows (e.g. a 10-minute window advancing every 5 minutes, giving a smoothed, overlapping view). **Session windows** are dynamic, bounded by a gap of inactivity rather than a fixed clock, closing a window once no new record for that key arrives within the configured inactivity gap ([Windowing in Kafka Streams — Confluent](https://www.confluent.io/blog/windowing-in-kafka-streams/) — accessed 2026-08-01).
- **State stores** (backed by RocksDB locally in Kafka Streams, or Flink's equivalent state backends) hold the running aggregation/join state per key, and are themselves backed by a compacted Kafka changelog topic so state can be rebuilt after a crash without replaying the entire original input stream.
- **Joins** between two streams (or a stream and a compacted "table" topic) need a windowed bound for stream-stream joins, since without one, "join records within what time range" is undefined for unbounded data; stream-table joins don't need this because the table side is treated as always-current-as-of-processing-time.
- **Out-of-order data and watermarks**: a late-arriving record (network delay, a mobile client buffering offline) can arrive after its window has already been considered closed. Frameworks handle this via a **watermark**, an explicit or heuristic bound on "how late is too late," trading completeness (waiting longer catches more late data) against latency (closing windows sooner gives faster results). This is a genuinely new failure class batch jobs never had: a batch job's dataset is complete by definition; a streaming job's "complete" is a policy decision with a real accuracy/latency tradeoff.

### Kafka vs. SQS vs. Pulsar vs. Kinesis, honestly

| | Kafka | Amazon SQS | Amazon Kinesis (Data Streams) | Apache Pulsar |
|---|---|---|---|---|
| Model | Partitioned log, consumers track own offset, replay supported | Point-to-point queue, broker tracks visibility/delete state | Partitioned log via shards, similar replay model to Kafka | Partitioned log, but compute (broker) and storage (BookKeeper) are separated |
| Throughput per partition/shard | A single Kafka partition on decent NVMe routinely sustains 10-100+ MB/s | Not partition-based; scales via consumer concurrency, not raw per-unit throughput | A shard caps at **1 MB/s write, 2 MB/s read** ([Kafka vs Kinesis — tech-insider.org](https://tech-insider.org/kafka-vs-kinesis-2026/) — accessed 2026-08-01) | Comparable per-partition throughput to Kafka; storage tier scales independently |
| Multi-consumer replay | Native and cheap, any number of independent consumer groups re-read the same log | Not designed for this; a message is deleted once acknowledged by its consumer | Native, similar to Kafka, via independent shard iterators per consumer | Native, plus tiered storage for very long retention at lower cost |
| Ordering | Per-partition only | FIFO queues offer per-message-group ordering; standard queues offer none | Per-shard only, same shape as Kafka | Per-partition only |
| Operational model | Self-managed or managed (MSK, Confluent Cloud); real operational surface either way | Fully managed, zero infrastructure to run | Fully managed, but resharding takes time and temporarily disrupts throughput | Self-managed or Pulsar-as-a-service; more architecturally complex to operate than Kafka |
| Best fit | High-throughput, multi-consumer, replay-needed event streaming; the default for anything Kafka-shaped | Simple task/job decoupling, single consumer type, no replay need; SQS wins decisively below roughly 500-1,000 msg/s sustained on cost and zero-ops simplicity ([SQS vs Kafka — tech-insider.org](https://tech-insider.org/sqs-vs-kafka-2026/) — accessed 2026-08-01) | AWS-native pipelines wanting a managed Kafka-like log without operating Kafka; accept the 1 MB/s/shard ceiling | Multi-tenant platforms needing independent compute/storage scaling and built-in tiered storage |

---

## Build it from scratch

A minimal, in-memory simulation of a partitioned log with key-based routing and per-partition ordering, enough to see why cross-partition ordering doesn't exist and how a consumer group divides work:

```python
# untested sketch -- illustrates partition routing, offsets, and consumer-group
# assignment; not a real broker (no replication, no network, no persistence)
import hashlib
from collections import defaultdict

class Partition:
    def __init__(self):
        self.log = []  # list of (offset, key, value)

    def append(self, key, value):
        offset = len(self.log)
        self.log.append((offset, key, value))
        return offset


class Topic:
    def __init__(self, num_partitions):
        self.partitions = [Partition() for _ in range(num_partitions)]

    def _partition_for_key(self, key):
        if key is None:
            return 0  # untested sketch: real Kafka round-robins/stickies null-key sends
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return h % len(self.partitions)

    def produce(self, key, value):
        p = self._partition_for_key(key)
        offset = self.partitions[p].append(key, value)
        return p, offset


class ConsumerGroup:
    """Assigns partitions to consumers round-robin; tracks per-partition committed offsets."""
    def __init__(self, topic, consumer_ids):
        self.topic = topic
        self.committed = defaultdict(int)  # partition_idx -> next offset to read
        self.assignment = defaultdict(list)  # consumer_id -> [partition_idx]
        for i, p in enumerate(range(len(topic.partitions))):
            self.assignment[consumer_ids[i % len(consumer_ids)]].append(p)

    def poll(self, consumer_id, max_records=10):
        records = []
        for p in self.assignment[consumer_id]:
            log = self.topic.partitions[p].log
            start = self.committed[p]
            for offset, key, value in log[start:start + max_records]:
                records.append((p, offset, key, value))
        return records

    def commit(self, partition_idx, offset):
        self.committed[partition_idx] = offset + 1


# demonstrate: same key always -> same partition -> per-key order preserved,
# but interleaving across different keys' partitions has NO global order
topic = Topic(num_partitions=3)
for i in range(5):
    topic.produce(key="user-42", value=f"event-{i}")   # all land on the SAME partition
for i in range(5):
    topic.produce(key="user-7", value=f"event-{i}")    # likely a DIFFERENT partition

group = ConsumerGroup(topic, consumer_ids=["c0", "c1"])
print(group.poll("c0"))
print(group.poll("c1"))
```

This omits replication, leader election per partition, the actual rebalance protocol (eager vs. cooperative), transactions, and compaction entirely, those are exactly the parts that make a real broker a large distributed system rather than a hash map. A full lab covering the outbox pattern end-to-end (Postgres + Debezium + Kafka Connect + a consumer with an idempotent upsert) belongs at `labs/py/10-messaging/` (not yet in this repo).

---

## How it's done in production

| Concern | What the framework/managed version adds |
|---|---|
| Exactly-once beyond Kafka's boundary | Kafka Streams' `exactly_once_v2` covers stream-to-stream processing pipelines that stay entirely within Kafka; anything exiting to an external sink (a JDBC sink connector, an HTTP call) still needs sink-side idempotency (upsert semantics, dedup keys) |
| CDC operationally | Debezium via Kafka Connect, with per-table topics, schema registry integration for evolving row schemas, and snapshot mode for initial full-table capture before streaming incremental changes |
| Stream state at scale | RocksDB-backed local state stores in Kafka Streams (changelog-backed for recovery); Flink's state backends (RocksDB or heap) plus checkpointing to durable storage (S3/HDFS) for exactly-once state recovery |
| Rebalance impact | Cooperative sticky assignor (KIP-429) as the default for new consumer groups; static group membership (`group.instance.id`) to avoid triggering a rebalance on brief restarts entirely |
| Retention economics | Tiered storage (offload cold segments to S3-class storage) to decouple retention length from local broker disk cost, native in Pulsar's architecture, increasingly available as a Kafka feature |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| One consumer's lag is far higher than the rest of the group | Key skew: a hot key concentrates traffic on one partition | Salt/split the hot key, or route it to a dedicated high-throughput partition/topic; adding consumers doesn't help since one partition still serves one consumer |
| Lag spikes sharply and repeatedly, correlated with pod scaling/restarts | Rebalance storm on the eager protocol, or too-aggressive `session.timeout.ms`/`max.poll.interval.ms` evicting slow-but-alive consumers | Switch to `CooperativeStickyAssignor`; use static group membership for planned restarts; tune timeout/poll-interval to actual processing time |
| Same logical message processed twice downstream despite Kafka's exactly-once config | Side effect outside Kafka's write path (external DB write, API call) isn't covered by Kafka transactions | Add idempotency at that boundary: unique constraint/upsert keyed on a message id, or a dedup table with a TTL |
| A consumer replaying from the start of a compacted topic misses a deletion that happened long ago | Tombstone already past `delete.retention.ms` (default 24h) and physically removed | Don't rely on tombstone visibility beyond the retention window; treat "key absent from a full compacted replay" as the actual signal of deletion, not "I saw a tombstone" |
| Downstream aggregation is missing data for records that arrived late | No watermark/lateness handling, or the allowed lateness window is too short | Configure grace period / allowed lateness explicitly, and decide, out loud, the latency-vs-completeness tradeoff for that specific aggregation |
| Producer throughput collapses under retries after a broker blip | Producer not idempotent, retried sends create duplicates that downstream logic then has to filter, or worse, doesn't | Enable the idempotent producer (`enable.idempotence=true`, default since Kafka 3.0 for new producers); it's nearly free and eliminates retry-caused duplication |

---

## Tradeoffs & when NOT to use it

- **Don't reach for Kafka when you have a single consumer type, low throughput (well under ~500-1,000 msg/s sustained), and no need for replay.** SQS is simpler, fully managed, and cheaper at that scale; running a Kafka cluster (or paying for a managed one) to decouple a background job queue is over-engineering.
- **Don't assume "exactly-once" means end-to-end exactly-once through your whole pipeline.** It means effectively-once inside Kafka's own write/read path. Any external side effect still needs its own idempotency, and saying otherwise in a design review is the kind of claim that causes a production duplicate-charge incident.
- **Don't add partitions casually to fix throughput without checking your ordering requirements first.** Changing partition count changes the key-to-partition hash mapping for a hash-based partitioner, silently reordering future messages relative to already-processed ones for the same key.
- **Compaction is the wrong retention policy for event/fact streams where history matters** (audit logs, immutable event sourcing), it only keeps the latest value per key by design; use time-based `delete` retention (or `compact,delete` hybrid) when the full history, not just current state, is the point.
- **Stream processing (windowing, watermarks, stateful joins) is more operational complexity than most problems need.** If your aggregation window is "once per day over a complete, bounded dataset," a batch job is simpler to reason about and debug than a streaming job fighting late data and watermark tuning for no latency benefit anyone asked for.
- **CDC via Debezium is the wrong choice when the source database's transaction log isn't accessible or stable** (some managed databases restrict binlog/WAL access, or the schema changes too chaotically for schema-registry evolution to track cleanly), application-level dual-write with the transactional outbox pattern is the fallback, accepting the extra table and relay process it requires.

---

## Interview questions

### Q1 — Kafka guarantees ordering. True or false, and why does the qualification matter?
**Testing:** whether "Kafka is ordered" is understood precisely or as a slogan.
**Answer:** False as stated; Kafka guarantees ordering only within a single partition, never across partitions of the same topic. Messages with the same key always land on the same partition (via hashing), which is how per-entity ordering is actually achieved, it's a side effect of routing, not a topic-wide property. A consumer reading two different partitions has no guarantee about the relative order of records between them.
**Follow-up trap:** *"You increase partition count from 4 to 8 to fix a throughput problem. What breaks?"* — the key-to-partition hash mapping changes for a percentage of keys, so messages for the same key produced before and after the resize can land on different partitions, breaking per-key ordering across that boundary unless you use a partitioner explicitly designed to be stable across resizing (rare) or accept the discontinuity.

### Q2 — Explain exactly what Kafka's "exactly-once semantics" actually guarantees, and where it stops.
**Testing:** the core illusion this module is built around.
**Answer:** It guarantees effectively-once processing within Kafka's own write and read path: the idempotent producer deduplicates retried sends via producer-id plus sequence number, and transactions make multi-partition writes (including offset commits) atomic, so a `read_committed` consumer never sees partial or duplicate transactional output. It does not extend to side effects outside Kafka, a database write, an API call, a file write, none of that is covered by the transaction, so duplicates or lost writes can still occur at that boundary on consumer crash/retry.
**Follow-up trap:** *"So how do you actually get exactly-once behavior when writing to Postgres from a consumer?"* — you don't get transactional exactly-once across the boundary; you get idempotent effectively-once via a unique constraint or upsert keyed on a stable message identifier (or the Kafka partition+offset itself), so a retried write has no effect the second time.

### Q3 — What's the difference between an eager and a cooperative consumer group rebalance?
**Testing:** operational depth beyond "rebalancing reassigns partitions."
**Answer:** Eager rebalancing is stop-the-world: every consumer in the group revokes all its partitions and the entire group pauses until reassignment finishes, even consumers whose assignment doesn't change. Cooperative rebalancing (KIP-429, `CooperativeStickyAssignor`) is incremental and two-phase: only the specific partitions actually moving are revoked, unaffected consumers keep processing the whole time, which drastically reduces the blast radius of scaling events or restarts.
**Follow-up trap:** *"Your consumer group rebalances every time a pod restarts during a rolling deploy, even though the same consumer comes right back. How do you stop that?"* — use static group membership (`group.instance.id` configured per consumer instance), which lets the coordinator recognize a returning consumer within a grace period and skip triggering a rebalance at all for a planned, brief restart.

### Q4 — Consumer lag is climbing steadily for one partition while the rest of the group looks fine. Diagnose it.
**Testing:** whether lag is understood as a leading operational signal with a specific, nameable cause.
**Answer:** This is the classic symptom of key skew: a disproportionate share of traffic is keyed to values that hash to that one partition, so the single consumer serving it can't keep up no matter how many other consumers or partitions exist, since Kafka assigns at most one consumer per partition at a time. Adding more consumers to the group does nothing once you already have as many consumers as partitions, and even before that, it doesn't help the specific overloaded partition.
**Follow-up trap:** *"The team's first instinct is to add partitions. Why might that not fix it, or make things worse temporarily?"* — adding partitions changes the hash mapping for existing keys, so the hot key might just move to a different (now equally overloaded) partition rather than being split; the actual fix is salting the hot key (appending a random suffix and fanning out reads) or routing known-hot keys to a dedicated higher-capacity path, and repartitioning also risks the ordering discontinuity from Q1.

### Q5 — Explain log compaction and what a tombstone actually does.
**Testing:** whether compaction is understood as a distinct mechanism from time-based retention, not a variant of it.
**Answer:** Compaction (`cleanup.policy=compact`) retains only the latest value for each key regardless of age, by periodically rewriting log segments to drop superseded records, turning the topic into a durable, replayable snapshot of "current value per key" rather than a time-bounded event history. A tombstone is a record with a `null` value for a key, signaling deletion; it's retained for `delete.retention.ms` (default 24 hours) after becoming eligible for compaction so slow consumers have a window to observe the delete before it's physically removed.
**Follow-up trap:** *"A consumer replays a compacted topic from the beginning three days after a key was deleted. Does it see the tombstone?"* — no, if the tombstone is past its retention window it's already been physically removed during compaction; the key is simply absent from the replay. A consumer relying on "seeing a tombstone" to know something was deleted needs to have been consuming continuously within that window, not doing a fresh replay later.

### Q6 — What problem does the transactional outbox pattern solve, and how does Debezium fit into it?
**Testing:** whether the dual-write problem is understood as the actual motivation.
**Answer:** An application that writes to its own database and separately publishes to a message broker in the "same" logical operation has a dual-write problem: the database commit and the broker publish are not atomic with each other, one can succeed while the other fails, leaving the system in an inconsistent state with no clean recovery. The outbox pattern fixes this by writing an outbox row in the *same database transaction* as the business data, making that write atomic by construction (it's a single-database ACID transaction). Debezium then captures that outbox table's changes via the database's transaction log (not polling) and relays them to Kafka, so the actual cross-system propagation happens through a reliable, replayable CDC stream instead of a second, non-atomic write from the application.
**Follow-up trap:** *"Why not just poll the outbox table instead of using Debezium/CDC?"* — polling adds load and latency proportional to poll interval, and duplicate/missed reads are easy to get wrong under concurrent writes and deletes; log-based CDC gets near-real-time propagation with zero extra load on the table because it reads the transaction log the database already writes for its own durability, not the table itself.

### Q7 — Design the partitioning strategy for an order-processing topic where per-order-id ordering matters and one customer places 40% of orders.
**Testing:** synthesis of ordering, key skew, and a stated tradeoff.
**Answer:** Partition by `order_id`, not `customer_id`, if the actual ordering requirement is per-order (state transitions of a single order must be processed in sequence) rather than per-customer, this immediately avoids concentrating the heavy customer's traffic on one partition, since each of their orders gets its own hash. If the requirement is genuinely per-customer ordering (all of one customer's orders must be processed in sequence relative to each other), then key by `customer_id` and accept that the heavy customer's partition will run hotter, mitigating it with a dedicated partition or topic for known high-volume customers rather than trying to spread their traffic (which would break the ordering requirement that justified the keying in the first place).
**Follow-up trap:** *"The interviewer says it's actually per-customer ordering that matters, and this customer is 40% of volume no matter how you partition. What do you do?"* — accept that this specific hot key needs asymmetric infrastructure: a dedicated partition (or entire topic) sized for that one customer's throughput, with the general partitioning scheme unaffected for everyone else, rather than trying to solve it purely through hashing, which cannot split a single key's traffic without breaking the ordering guarantee that key needs.

### Q8 — What's the difference between a tumbling window and a hopping window, and when would you use each?
**Testing:** precise mechanical recall plus judgment.
**Answer:** A tumbling window is fixed-size and non-overlapping, every record belongs to exactly one window (a 5-minute tumbling window: 0:00-0:05, 0:05-0:10, no overlap). A hopping window is fixed-size but advances by a step smaller than its size, so windows overlap and a single record can contribute to multiple windows (a 10-minute window advancing every 5 minutes means each record falls into two overlapping windows). Use tumbling for discrete, non-overlapping reporting periods (hourly counts); use hopping when you want a smoothed, more continuously updating view (a moving 10-minute rate updated every minute) at the cost of extra compute since each record is processed into multiple windows.
**Follow-up trap:** *"When would a session window be the right choice instead of either?"* — when the natural grouping boundary is a gap in activity, not a fixed clock interval, e.g. grouping a user's clickstream into "browsing sessions" defined by 30 minutes of inactivity; tumbling/hopping windows would arbitrarily cut a continuous session in half at a clock boundary that has no relationship to the user's actual behavior.

### Q9 — Why does stream processing need watermarks and batch processing doesn't?
**Testing:** understanding of the fundamental new problem unbounded data introduces.
**Answer:** A batch job operates over a complete, bounded dataset, so "is this aggregation final" has an unambiguous answer: yes, once the whole input has been read. A streaming job operates over data that never definitively "ends," and individual records can arrive late (network delay, offline mobile buffering) relative to their event time, so the system needs an explicit policy for "how long do I wait for stragglers before considering a window closed and emitting a result." A watermark is that policy, a heuristic or explicit bound on acceptable lateness, and it's a genuine accuracy-vs-latency tradeoff that has no equivalent in batch processing, where the dataset's completeness is a given, not a decision.
**Follow-up trap:** *"A record arrives after its window's watermark has already passed. What are your options, concretely?"* — drop it (accepting incompleteness for speed), route it to a separate "late data" side output for a corrective batch reprocessing pass later, or configure an explicit allowed-lateness grace period that keeps the window open longer at the cost of delaying the "final" result; which one is correct depends entirely on whether the downstream consumer needs low latency or high completeness more.

### Q10 — Kafka, SQS, or Kinesis for a pipeline receiving 200 events/sec from a single producer type, consumed by exactly one downstream service, no replay needed?
**Testing:** judgment about when the more powerful tool is the wrong tool.
**Answer:** SQS. At 200 events/sec with a single consumer type and no replay requirement, none of Kafka's actual differentiators (multi-consumer-group replay, per-partition high throughput, long retention as a first-class feature) are being used, you'd be paying the operational cost (or managed-service cost) of a distributed log for a workload that's a textbook point-to-point queue. SQS is fully managed, essentially zero-ops, and priced for exactly this shape of workload, and its request-based pricing wins decisively below roughly 500-1,000 msg/s sustained.
**Follow-up trap:** *"Six months later, product wants to add a second, independent consumer that needs to process the same events for a different purpose, and also wants 30 days of replay for backfills. Do you switch?"* — yes, this is exactly the point where SQS's model (message deleted once acknowledged by its one consumer) stops fitting, and you'd migrate to Kafka or Kinesis specifically because the new requirements (multiple independent consumer groups, replay) are Kafka's actual value proposition, not because of a throughput problem, this should be evaluated as a fit change, not "SQS wasn't good enough."

### Q11 — Your idempotent producer is enabled, but a customer reports being charged twice for one order. Where do you look?
**Testing:** the ability to locate the boundary where Kafka's guarantee actually ends.
**Answer:** The idempotent producer only deduplicates retried *sends from the producer to Kafka*, based on producer-id and sequence number, it has nothing to do with what happens downstream. The duplicate charge is almost certainly at the consumer's side effect: the consumer processed the message, called the payment API, then crashed or lost connectivity before committing its Kafka offset, so on restart it re-read the same message (a legitimate at-least-once redelivery) and called the payment API again without any idempotency key on that call.
**Follow-up trap:** *"The consumer does commit the offset before calling the payment API instead. Does that fix it?"* — no, it moves the failure mode rather than removing it: now a crash between the offset commit and the payment call means the message is never retried at all (an under-charge / lost payment, worse for a payment flow than a duplicate). The actual fix is making the payment call itself idempotent via an idempotency key derived from the message (order id, or Kafka partition+offset), independent of whichever order the offset commit and the external call happen in.

### Q12 — Compare Kafka and Pulsar's architecture at the storage layer, and what that difference actually buys you.
**Testing:** staff-level knowledge of why an alternative exists, not just that it does.
**Answer:** Kafka couples compute (the broker) and storage (the broker's local disk holding partition segments) in the same process; scaling storage capacity and scaling broker/consumer throughput are the same operation. Pulsar separates them: brokers are stateless and handle client protocol and routing, while BookKeeper (a separate distributed log storage layer) holds the actual data, which lets you scale broker fleet size and storage capacity independently and makes tiered storage (offloading old segments to object storage) a more natural, built-in architectural feature rather than a bolt-on.
**Follow-up trap:** *"So is Pulsar strictly better? Why hasn't it displaced Kafka?"* — no; the separated architecture is genuinely more complex to operate (two distributed systems to run and reason about instead of one), and Kafka's ecosystem maturity (Kafka Connect, Kafka Streams, ksqlDB, the sheer number of existing operational playbooks and engineers who know it) is a real, large switching cost that Pulsar's architectural advantage doesn't automatically overcome for most teams; Pulsar wins specifically for multi-tenant platforms that need the independent-scaling and tiered-storage properties as first-class requirements, not as a general Kafka replacement.

---

## Red flags that fail you

- Saying "Kafka guarantees ordering" without the per-partition qualifier.
- Claiming "exactly-once" applies to any external side effect a consumer performs, not just Kafka's own write path.
- Not knowing that a rebalance can be stop-the-world, or not knowing the cooperative-sticky fix exists.
- Confusing consumer lag with throughput, or not identifying key skew as the cause of one hot partition.
- Treating log compaction as a variant of time-based retention rather than a distinct "latest value per key" mechanism.
- Recommending Kafka by default for a low-throughput, single-consumer, no-replay workload without considering SQS.
- Not knowing that a tombstone has its own retention window and can silently disappear before a slow consumer sees it.
- Describing stream processing as "just batch processing but faster," missing that unbounded data and lateness are a genuinely different problem.

---

## Cheat card

```
KAFKA CORE
  topic = N independent partitions; ORDERING = per-partition ONLY, never topic-wide
  key -> hash -> partition, deterministic; resizing partitions changes the mapping
  consumer group: 1 partition <= 1 consumer at a time; more consumers than partitions = idle ones
  default retention: 168h/7 days (cleanup.policy=delete); compaction keeps latest value/key
  tombstone (null value) retained delete.retention.ms, default 24h, then physically gone

REBALANCE
  eager = stop-the-world, ALL consumers pause even if their assignment is unchanged
  cooperative (KIP-429, CooperativeStickyAssignor, Kafka 2.4+): incremental, only moving
    partitions revoked, unaffected consumers keep processing
  static membership (group.instance.id): skip rebalance entirely on brief planned restarts

EXACTLY-ONCE, THE ILLUSION
  idempotent producer: dedups by (producer_id, seq_num) -- fixes PRODUCER RETRY dupes only
  transactions: atomic multi-partition write + atomic offset commit -- read_committed consumers
    never see partial/duplicate transactional output
  = EFFECTIVELY-ONCE INSIDE KAFKA. Any external side effect (DB write, API call) is back
    to at-least-once + YOUR OWN idempotency (unique constraint / upsert / dedup key)

CONSUMER LAG = latest_offset - committed_offset
  climbing linearly = sustained under-capacity (slow processing or too few consumers)
  ONE partition's lag >> group average = key skew, not a capacity problem;
    adding consumers does NOT fix it once consumers >= partitions

CDC / OUTBOX
  Debezium reads the DB TRANSACTION LOG (binlog/WAL), not polling -- zero extra table load
  outbox pattern: write outbox row in SAME DB txn as business data -> CDC relays it to Kafka
    -> converts a cross-system dual-write problem into one ACID txn + a reliable relay

STREAM PROCESSING
  tumbling = fixed, non-overlapping. hopping = fixed, overlapping (advance < size).
  session = gap-of-inactivity bounded, not clock bounded
  state stores: RocksDB-backed locally (Kafka Streams), changelog topic backs recovery
  watermark = policy for "how late is too late" -- an accuracy/latency tradeoff batch never has

KAFKA vs SQS vs KINESIS vs PULSAR
  Kafka: 10-100+ MB/s per partition, multi-consumer replay native, most operational surface
  SQS: fully managed, zero-ops, wins below ~500-1000 msg/s, NO replay (deleted on ack)
  Kinesis: shard caps at 1 MB/s write / 2 MB/s read, AWS-native managed log
  Pulsar: compute/storage separated (BookKeeper) -- independent scaling + native tiered storage,
    but two distributed systems to operate instead of one
```

## Sources

- [Exactly-once Semantics is Possible: Here's How Apache Kafka Does it — Confluent](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/) — accessed 2026-08-01
- [What is Kafka Exactly Once Semantics — AutoMQ wiki](https://github.com/AutoMQ/automq/wiki/What-is-Kafka-Exactly-Once-Semantics) — accessed 2026-08-01
- [Cooperative Rebalancing in the Kafka Consumer, Streams & ksqlDB — Confluent](https://www.confluent.io/blog/cooperative-rebalancing-in-kafka-streams-consumer-ksqldb/) — accessed 2026-08-01
- [KIP-429: Kafka Consumer Incremental Rebalance Protocol — Apache Kafka wiki](https://cwiki.apache.org/confluence/x/vAclBg) — accessed 2026-08-01
- [Windowing in Kafka Streams — Confluent](https://www.confluent.io/blog/windowing-in-kafka-streams/) — accessed 2026-08-01
- [Outbox Pattern with Debezium — thorben-janssen.com](https://thorben-janssen.com/outbox-pattern-with-cdc-and-debezium/) — accessed 2026-08-01
- [Kafka vs Kinesis 2026 — tech-insider.org](https://tech-insider.org/kafka-vs-kinesis-2026/) — accessed 2026-08-01
- [SQS vs Kafka 2026: Throughput, Pricing & Migration — tech-insider.org](https://tech-insider.org/sqs-vs-kafka-2026/) — accessed 2026-08-01
- [Kafka topic configuration reference (cleanup.policy) — Apache Kafka docs](https://kafka.apache.org/30/generated/topic_config.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
