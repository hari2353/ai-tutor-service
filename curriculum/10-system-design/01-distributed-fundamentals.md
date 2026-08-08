# CAP/PACELC, Consistency Models, Replication, Partitioning

> **Track:** T10 System Design · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T10-distributed-fundamentals` · **Tags:** sprint, fundamentals, critical

## The 30-second version

CAP is precise but narrow: Gilbert and Lynch proved that when an actual network partition occurs, a system must choose between consistency (linearizability) and availability (every non-failing node responds) — it says nothing about the 99.99% of the time there is no partition, which is exactly why PACELC is the more useful framing for interviews: **if Partitioned, choose A or C; Else, choose Latency or Consistency.** Underneath that binary sits a spectrum, not a switch — linearizable, sequential, causal, and eventual consistency each permit progressively more staleness and reordering for progressively lower latency. Replication strategy (single-leader, multi-leader, or leaderless quorums with the R+W>N arithmetic) and partitioning strategy (range vs. hash, each with a distinct hot-partition failure mode) are the concrete levers that implement whatever point on that spectrum you choose, and real systems — Spanner, DynamoDB, Cassandra, Postgres — each sit at a deliberately different, nameable point.

## Why this gets asked

Because "CAP means pick two of three" is the single most common wrong answer in system design interviews, and it reveals whether a candidate actually understands that partitions are rare, transient events, not a permanent architectural stance — the interviewer has almost certainly had to explain to a junior engineer why their "CP" database was slow and stale-reading during completely normal, partition-free operation, which is a PACELC problem CAP has no vocabulary for. At staff/principal level, the follow-up is whether you can map these abstractions onto a real system's actual behavior and defend a concrete R/W/N configuration or partitioning key choice with numbers.

## Lineage: past → present → future

**What came before.** Pre-2000 distributed data systems mostly tried to give applications the illusion of a single machine — distributed transactions via two-phase commit, single-master replication with synchronous acknowledgment — because that was the model relational databases had trained everyone to expect. This worked at LAN scale but broke down as systems grew across data centers: synchronous cross-region coordination on every write meant every partition or high-latency link stalled the whole system, which was untenable at internet scale. Eric Brewer's 2000 PODC keynote named the tension explicitly (later formalized by Gilbert and Lynch in 2002), and Amazon's Dynamo paper (2007) was the concrete answer: give up strict consistency, use leaderless replication with tunable quorums, and stay available through partitions and node failures — the specific pain it killed was Amazon's own experience of losing sales during outages caused by strongly consistent systems that refused to serve traffic when any replica was unreachable.

**Where it stands now.** The field's current consensus is that CAP itself is under-specified for design decisions — it only describes behavior *during* a partition, and real systems spend the overwhelming majority of their operation in the no-partition case where Abadi's 2012 PACELC framing (Else: Latency vs. Consistency) is what actually governs day-to-day behavior. In practice, most large-scale systems are not purely CP or AP; they're tunable per operation (Cassandra's per-query consistency level, DynamoDB's optional strongly-consistent reads) or achieve strong consistency without sacrificing practical availability by engineering around the partition case specifically — Google Spanner's TrueTime-based external consistency is the most cited example, trading a few milliseconds of commit-wait latency for global linearizability rather than trading away availability. The live disagreement is less "CP vs AP" and more about where exactly to spend a latency budget: whether a given read path needs linearizable, causal, or merely eventual guarantees, and how much of that decision can be pushed to the application layer (session guarantees, client-side conflict resolution) versus the storage layer.

**Where it's heading.** Two things with reasonable confidence: first, "consistency as a per-request, per-workload tunable parameter" (already the norm in Cassandra/DynamoDB) continues displacing "consistency as a whole-database architectural choice," because most real applications need different guarantees for different operations (a payment write needs strong consistency; a view-count increment doesn't). Second, globally-distributed strongly-consistent systems are becoming more accessible outside Google specifically because TrueTime-like bounded-clock-uncertainty designs (and cheaper, more precise clock synchronization generally) are proliferating — CockroachDB and YugabyteDB both ship Spanner-inspired designs without requiring Google's atomic-clock infrastructure, using hybrid logical clocks and slightly larger uncertainty windows instead. More speculatively: as multi-region active-active applications become the default rather than the exception, expect more systems to expose consistency as an explicit, named contract per API rather than a single database-wide setting — this is a direction of travel, not yet a settled standard.

---

## Mental model

```
                          CAP: only asks "what happens DURING a partition?"
        ┌───────────────────────────────────────────────────────────────┐
        │  Partition occurs. A request arrives at a node that cannot    │
        │  reach some replicas. Two choices, pick one:                  │
        │                                                                │
        │   C  -- refuse/delay the request rather than risk returning   │
        │         stale or conflicting data (CP)                        │
        │   A  -- answer anyway, from whatever this node has (AP)       │
        └───────────────────────────────────────────────────────────────┘

                    PACELC: what happens the REST of the time (Else)
        ┌───────────────────────────────────────────────────────────────┐
        │  No partition. Every write still has to get acknowledged by   │
        │  some number of replicas before you call it durable. Two      │
        │  choices, pick one, continuously, on every operation:         │
        │                                                                │
        │   L  -- return fast, don't wait for every replica (lower C)   │
        │   C  -- wait for enough replicas to guarantee consistency     │
        │         (higher latency)                                     │
        └───────────────────────────────────────────────────────────────┘

  Spanner    = PC/EC  (pays latency always, for consistency always)
  Dynamo/    = PA/EL  (available and fast always, consistency is tunable/eventual)
  Cassandra
  Postgres   = single-leader: PC-ish in practice for the leader path /
   (single-region)   EC on the primary, but reads from a lagging replica are stale (EL-ish)
```

**The consistency spectrum, strongest to weakest:**

```
linearizable  >  sequential  >  causal  >  eventual
(real-time       (one global      (respects       (no ordering
 total order,     order, but not   causal          guarantee at all,
 as if one        tied to real     dependencies    only convergence
 copy)            time across      only)           given no new
                  processes)                        writes)
```

---

## How it actually works

### CAP, stated precisely (and the misstatements to avoid)

Gilbert & Lynch's 2002 formalization of Brewer's conjecture: in an asynchronous network, a distributed data store cannot simultaneously guarantee **Consistency** (linearizability — every read reflects the most recent completed write, as if there were only one copy of the data and operations happened atomically at some point between their invocation and response), **Availability** (every request to a non-failing node receives a non-error response), and **Partition tolerance** (the system continues to function despite arbitrary message loss/delay between nodes) — under an actual partition, you must give up C or A.

**Misstatement 1 — "pick two of three, always."** Partition tolerance isn't optional in a real distributed system spanning more than one machine — network partitions *will* happen — so in practice the only live choice is CP vs. AP, and only *during* the partition. Outside a partition, nothing stops a system from being fully consistent and fully available simultaneously, which is in fact the common case for the overwhelming majority of a system's uptime.

**Misstatement 2 — conflating CAP's "A" with an SLA uptime number.** CAP's availability means *every request that reaches a non-failing node gets a response* — it is not "99.99% uptime" and has nothing to say about latency; a system can technically satisfy CAP's A by responding instantly with an error only during the tiny fraction of time it's actually partitioned and still be "available" in the CAP sense.

**Misstatement 3 — conflating CAP's "C" with ACID's "C".** ACID consistency means transactions preserve application-defined invariants (foreign keys, uniqueness constraints). CAP consistency means all nodes agree on the current value of a piece of data (linearizability). Same letter, unrelated concepts — a system can be ACID-consistent and CAP-inconsistent (a single-node database with constraints, replicated asynchronously) or the reverse.

### PACELC: the more useful framing

Daniel Abadi's 2012 extension: **if Partitioned, choose Availability or Consistency; Else (normal operation), choose Latency or Consistency.** This directly closes CAP's blind spot — it forces you to state a system's behavior in the common case, not just the rare one.

Four quadrants:

| | Consistency during partition | Availability during partition |
|---|---|---|
| **Low latency, else** | PC/EL — rare; consistent under partition, but trades consistency for speed normally (some tunable multi-region configs) | **PA/EL** — Dynamo, Cassandra: always available and low-latency, consistency is a tunable knob you usually loosen |
| **Consistency, else** | **PC/EC** — Spanner: always consistent, always pays the latency cost, partition or not | PA/EC — uncommon; available during partitions but pays consistency latency normally |

Spanner is PC/EC: it pays a real, measured latency cost (TrueTime commit-wait, detailed below) on *every* write, partition or not, in exchange for global linearizability at all times. Dynamo-style systems are PA/EL: they're available and fast continuously, and consistency is whatever you configure per-request, trading it away by default for latency.

### The consistency spectrum: what each level actually permits

- **Linearizable** (Herlihy & Wing, 1990): every operation appears to take effect atomically at some instant between its invocation and its response, and that instant respects real-world time across *all* clients — the strongest practical guarantee, equivalent to there being exactly one copy of the data. Expensive: typically requires consensus (Paxos/Raft) or a bounded-uncertainty clock (Spanner's TrueTime) to implement across machines.
- **Sequential consistency**: all operations from all processes appear in *some* single total order, and each process's own operations appear in that order in the sequence it issued them — but that shared order does not have to match real-world wall-clock time across different processes. Weaker than linearizability specifically by dropping the real-time constraint, which is enough to allow cheaper implementations while still giving every observer a single agreed-upon history.
- **Causal consistency**: operations that are causally related (a read that observed a value, followed by a write based on it) must be seen in that order by every replica; concurrent, causally-unrelated operations may be seen in different orders by different replicas. This is the strongest model that remains available under partition (you can always tell whether two operations are causally related from vector clocks/version vectors without needing global coordination).
- **Eventual consistency**: the only guarantee is that if no new writes arrive, all replicas eventually converge to the same value — no guarantee about ordering, real-time recency, or even monotonicity of what any single client observes in the meantime.

**Session guarantees** (Terry et al., Bayou, 1994) — practical, client-scoped promises that are much cheaper than global linearizability but fix the specific complaints users actually notice:
- **Read-your-writes**: a client that just wrote a value will see that value (or a newer one) on its own subsequent reads, even if a read happens to hit a lagging replica.
- **Monotonic reads**: successive reads by the same client never go backward in time — you won't see a value, then later see an older value, even across different replicas.
- **Monotonic writes**: a client's writes are applied in the order it issued them.
- **Writes-follow-reads**: a write that's causally dependent on a prior read is guaranteed to be applied after whatever that read observed.

### Replication strategies

**Single-leader** (Postgres streaming replication, MySQL, most relational databases by default): all writes go to one leader, which streams a write-ahead log to followers. Simple to reason about — no write-write conflicts possible. Costs: the leader is both the write bottleneck and a single point of failure; asynchronous replication means followers can lag, so reads from a follower can be stale (an EL-leaning choice made per-read); failover requires promoting a follower, and if replication was asynchronous, in-flight writes acknowledged by the old leader but not yet replicated can be lost.

**Multi-leader** (Postgres with BDR extensions, CouchDB, multi-region setups generally): writes accepted at multiple nodes, each replicating to the others — useful when write latency across regions matters more than avoiding conflicts (a user in Tokyo shouldn't have to round-trip to a US-East leader for every write). Cost: write-write conflicts are now possible and must be resolved — last-write-wins (simple, silently loses data), CRDTs (mathematically guaranteed convergence for specific data structures), or application-level merge logic (correct but bespoke).

**Leaderless / quorum-based** (Dynamo, Cassandra, Riak): writes and reads go to `N` replicas; a write is considered successful once `W` replicas acknowledge, a read is considered successful once `R` replicas respond and their results are reconciled. The core arithmetic: if **`R + W > N`**, every possible read quorum and every possible write quorum share at least one common replica, so any read is guaranteed to overlap with the most recent completed write's replica set — this gives you consistency *without* a single leader. It does **not** by itself guarantee real-time recency for concurrent reads/writes (two operations can race even under quorum overlap), which is why leaderless systems layer read-repair (fixing stale replicas discovered during a read), hinted handoff (temporarily stashing a write meant for a down replica elsewhere, and delivering it once that replica recovers), and vector clocks or last-write-wins for conflict resolution on top. Dynamo's "sloppy quorum" deliberately relaxes strict `R+W>N` membership during a partition — trading consistency for availability exactly when CAP says you must choose — which is what makes it AP rather than CP.

### Partitioning strategies

**Range-based** (Bigtable, HBase, early CockroachDB/Spanner ranges): keys are split into contiguous ranges, each owned by one partition/tablet. Good for range scans (fetch keys between X and Y from one or a few partitions) and for locality of related data. Failure mode: **hot partitions** from monotonically increasing keys — a timestamp-prefixed or auto-incrementing ID concentrates all new writes on whichever partition currently owns the tail of the key space, while every other partition sits idle; this is a specifically range-partitioning problem, not partitioning in general.

**Hash-based** (DynamoDB, Cassandra by default, consistent hashing generally): a key's partition is determined by hashing it, spreading load roughly uniformly across partitions regardless of key ordering. Fixes the monotonic-key hot-partition problem, but kills efficient range queries (adjacent keys in the application's logical ordering land on unrelated, scattered partitions, forcing scatter-gather across the whole cluster for a range scan) and doesn't fully eliminate hot-spotting — a single wildly popular key (a viral post, a celebrity's row) still concentrates load on whichever one partition owns *that specific key*, regardless of hashing; no partitioning scheme fixes a single overloaded key, which needs caching, key-splitting/salting, or read replicas targeted at that specific hot key instead.

### Grounding in real systems

- **Google Spanner** — PC/EC. Uses TrueTime (GPS + atomic clocks giving a bounded uncertainty interval `ε`, typically single-digit milliseconds) plus Paxos per shard and two-phase commit across shards to achieve external consistency (strict serializability) globally. The commit-wait protocol makes the leader wait out the clock uncertainty window before acknowledging a commit — roughly 5-8ms measured commit-wait in single-region deployments, rising to on the order of 20ms+ for multi-region commits, which is the concrete, measured price of global linearizability ([Spanner: TrueTime and external consistency — Google Cloud docs](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency), accessed 2026-07-26).
- **Amazon DynamoDB** — descended from the 2007 Dynamo paper's leaderless, sloppy-quorum, vector-clock design (PA/EL), but the managed DynamoDB service (launched 2012) simplifies the exposed model: default reads are eventually consistent (effectively `R=1`), with an explicit option for strongly consistent reads that read from the partition's current leader-equivalent copy — the tunable-per-request quorum knobs from the original paper are mostly hidden behind this simpler binary choice in the managed product.
- **Apache Cassandra** — leaderless, tunable consistency **per query** via consistency levels: `ONE`, `QUORUM` (majority across all datacenters), `LOCAL_QUORUM` (majority within the coordinator's own datacenter only, avoiding cross-region latency), up to `ALL`. `R + W > N` gives strong consistency (e.g. `QUORUM` reads with `QUORUM` writes at `N=3` means `R=2, W=2`, `2+2=4>3`); using `ONE` for both drops to eventual consistency. Convergence is maintained via hinted handoff, read repair, and Merkle-tree-based anti-entropy between replicas. Partitioning is hash-based by default (Murmur3 partitioner); the classic Cassandra-specific failure mode is a wide partition — too much data or too many writes accumulating under one partition key, which is a data-modeling mistake, not a cluster-sizing one.
- **PostgreSQL** — single-leader by default. Streaming replication ships the WAL to followers; `synchronous_commit` controls the latency/durability tradeoff per transaction (`off`/`local`/`remote_write`/`on`/`remote_apply`, each waiting for progressively more replica acknowledgment before returning success to the client) — this is PACELC's "Else" axis made into a literal, named configuration knob. Logical replication and extensions (BDR, or sharding via Citus) are how Postgres reaches multi-leader or partitioned topologies, which are not native to vanilla single-node Postgres.

---

## Build it from scratch

A minimal simulation of quorum read/write reconciliation — enough to see why `R+W>N` guarantees overlap, and where it doesn't guarantee recency:

```python
# untested sketch -- illustrates quorum overlap arithmetic, not a real replicated store
import itertools

class QuorumStore:
    def __init__(self, n_replicas: int, w: int, r: int):
        assert w + r > n_replicas, "R+W>N required for quorum consistency"
        self.n, self.w, self.r = n_replicas, w, r
        self.replicas = [{} for _ in range(n_replicas)]   # each replica: {key: (value, version)}

    def write(self, key, value, replica_subset):
        """Write to W replicas from the given subset; caller must supply >= W reachable replicas."""
        targets = replica_subset[: self.w]
        if len(targets) < self.w:
            raise RuntimeError(f"only {len(targets)} replicas reachable, need W={self.w}")
        version = max((self.replicas[i].get(key, (None, 0))[1] for i in range(self.n)), default=0) + 1
        for i in targets:
            self.replicas[i][key] = (value, version)
        return version

    def read(self, key, replica_subset):
        """Read from R replicas, return the highest-version value (last-write-wins reconciliation)."""
        targets = replica_subset[: self.r]
        if len(targets) < self.r:
            raise RuntimeError(f"only {len(targets)} replicas reachable, need R={self.r}")
        candidates = [self.replicas[i].get(key) for i in targets if key in self.replicas[i]]
        if not candidates:
            return None
        return max(candidates, key=lambda vv: vv[1])   # highest version wins

    def demonstrate_overlap_guarantee(self, key):
        """Proves R+W>N: every W-subset and every R-subset share at least one replica."""
        all_idx = list(range(self.n))
        for w_subset in itertools.combinations(all_idx, self.w):
            for r_subset in itertools.combinations(all_idx, self.r):
                assert set(w_subset) & set(r_subset), "quorum overlap violated -- R+W>N was not satisfied"
        return True
```

This deliberately does *not* model concurrent writes racing each other, network partitions triggering sloppy quorums, or vector-clock-based sibling detection — those are exactly the parts that make real leaderless systems (Dynamo, Cassandra, Riak) much more involved than the arithmetic alone suggests. Full lab with simulated partition injection and read-repair: **`labs/py/10-distributed-fundamentals/`** (create if not present — not yet in this repo).

---

## How it's done in production

| System | Replication | Partitioning | Consistency posture |
|---|---|---|---|
| Google Spanner / CockroachDB / YugabyteDB | Paxos/Raft per shard, leader per range | Range-based (Spanner), range or hash (Cockroach/Yugabyte) | PC/EC — external consistency via bounded-clock-uncertainty commit-wait |
| Amazon DynamoDB | Leaderless quorum internally, simplified to eventual-by-default / strong-by-request externally | Hash-based (consistent hashing over partition key) | PA/EL by default, opt-in strong reads per request |
| Apache Cassandra | Leaderless, tunable per-query consistency level | Hash-based (Murmur3 partitioner) by default | PA/EL by default; tunable to effectively CP-like per query via `QUORUM`/`ALL` |
| PostgreSQL (vanilla) | Single-leader, WAL streaming | None natively (sharding via extensions/Citus) | Leader path is linearizable for its own reads; replica reads are eventual/causal depending on `synchronous_commit` |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| User submits a form, refreshes, and doesn't see their own write | Read routed to a lagging asynchronous replica | Implement read-your-writes (route post-write reads to the leader, or track a client-side version watermark) |
| Dashboard shows a metric that goes backward in time on refresh | No monotonic-read guarantee; consecutive reads hit different, differently-lagged replicas | Sticky sessions to one replica, or a version-vector check that rejects a read older than the client's last-seen version |
| Two regions both accept a write to the same record and one silently overwrites the other | Multi-leader replication with last-write-wins conflict resolution | Move to CRDTs for mergeable data types, or application-level conflict resolution with explicit versioning |
| One partition is at 10x the load of every other partition | Range partitioning with a monotonically increasing key (timestamp, auto-increment ID) | Hash-based partitioning, or a range key with a randomized/sharded prefix |
| A single key inside a hash-partitioned table is overwhelmed despite even overall load | Celebrity/hot-key problem — one key, not the whole partitioning scheme, is overloaded | Key-splitting/salting for that specific key, dedicated caching, or a read-replica fan-out targeted at it |
| A "consistent" quorum store still returns stale data under concurrent access | R+W>N guarantees overlap, not real-time recency — two concurrent operations can still race | Use vector clocks/version vectors to detect concurrent writes explicitly rather than assuming quorum alone orders them |
| Global write latency triples after adding a third region | PC/EC design (Spanner-style) paying real commit-wait cost across more/farther replicas | Confirm this is an accepted, deliberate tradeoff for the consistency guarantee, or move latency-insensitive-to-consistency writes to a different, more relaxed data path |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a Spanner-style globally-consistent design by default.** The commit-wait latency cost is real and paid on every write, everywhere, partition or not — the right call for financial ledgers and inventory counts, the wrong call for a comment counter or a view-count increment where eventual consistency is imperceptible to users and far cheaper.
- **Don't use `QUORUM`/`ALL` consistency levels everywhere in Cassandra "to be safe."** Every additional replica you require to ack raises write latency and reduces availability during any replica outage; tune consistency level per query type, not globally.
- **Range partitioning is the wrong default for high-write, monotonic-key workloads** (event logs, time-series ingestion with a timestamp-leading key) — you will hot-spot on the newest range; use hash partitioning or a randomized key prefix instead, accepting the range-scan cost that comes with it.
- **Hash partitioning is the wrong default when range scans are the primary access pattern** (time-range queries, ordered pagination) — you'll pay scatter-gather cost across the whole cluster for every scan; range partitioning (or a hybrid, hash-then-range within a bucket) fits better.
- **Multi-leader replication is not worth its conflict-resolution complexity unless you actually need multi-region write latency.** If all your writers are in one region anyway, single-leader is simpler and has one fewer class of bug (write-write conflicts) to reason about.
- **Session guarantees (read-your-writes, monotonic reads) are not a substitute for real consistency when correctness genuinely depends on global ordering** (e.g. a ledger balance) — they fix specific, common user-facing symptoms cheaply, but they are not linearizability and shouldn't be sold as such.

---

## Interview questions

### Q1 — State CAP theorem precisely. What's wrong with "you can only pick two of three"?
**Testing:** whether you actually understand the theorem or memorized a slogan.
**Answer:** Under an actual network partition, a distributed system must choose between consistency (linearizability) and availability (every non-failing node responds) — you cannot have both during that partition. "Pick two of three" is wrong because partition tolerance isn't optional in any real multi-node system (partitions will happen), and the tradeoff is only forced *during* a partition — the rest of the time, a system can be both fully consistent and fully available.
**Follow-up trap:** *"So is a single-node database exempt from CAP?"* — yes, trivially: CAP only describes tradeoffs that arise from *distribution* across nodes that can be partitioned from each other; a single node has nothing to partition from.

### Q2 — What's the difference between CAP's "availability" and a 99.99% uptime SLA?
**Answer:** CAP's availability is binary and instantaneous per-request: every request to a non-failing node gets *some* non-error response, with no statement about how fast. An SLA uptime number is a statistical, time-averaged measure of successful requests over a period, and typically implies a latency bound too. A system can be CAP-available while being commercially unacceptable — instantly returning errors during a partition still satisfies CAP's A if that's the deliberate CP choice made *during* the partition specifically.
**Follow-up trap:** *"Then what should I actually track operationally if not CAP's definition?"* — track latency percentiles and error rates continuously (which is what PACELC's Latency-vs-Consistency axis is actually about), because that's what determines real user experience during the 99.99% of time you're not partitioned, which CAP has nothing to say about.

### Q3 — Explain PACELC and why it's more useful in practice than CAP alone.
**Answer:** PACELC: if Partitioned, choose Availability or Consistency; Else (normal operation), choose Latency or Consistency. It's more useful because real systems spend nearly all their time in the "Else" branch, and CAP is entirely silent about what happens there — PACELC forces you to also state the latency/consistency tradeoff made during totally normal operation, which is where most day-to-day user-facing behavior actually comes from.
**Follow-up trap:** *"Classify Spanner and DynamoDB in PACELC terms."* — Spanner is PC/EC: consistent during a partition (by design, it prioritizes correctness and will delay), and it pays a latency cost for consistency even with no partition (TrueTime commit-wait on every write). DynamoDB is PA/EL by default: available during a partition (sloppy quorums), and low-latency by default otherwise (eventually consistent reads unless you explicitly request strong consistency).

### Q4 — CAP's "C" and ACID's "C" share a letter. Are they the same thing?
**Answer:** No. ACID consistency means a transaction preserves application-level invariants (foreign keys, uniqueness, business rules) — it's about correctness relative to schema/application rules. CAP consistency means linearizability — all nodes agree on the current value of a given piece of data, as if there were only one copy. A system can satisfy one without the other: a single-node database with strict constraints but asynchronous, unread replicas is ACID-consistent and CAP-inconsistent.
**Follow-up trap:** *"Give a concrete example where a system is CAP-consistent but ACID-inconsistent."* — a distributed key-value store that guarantees linearizable reads/writes on individual keys (CAP-consistent) but has no concept of multi-key transactions or foreign-key-like constraints at all (nothing preventing an "invalid" combination of values across two keys) — CAP consistency says nothing about cross-key application invariants.

### Q5 — Rank linearizable, sequential, causal, and eventual consistency, and state precisely what each permits that the stronger one doesn't.
**Answer:** Linearizable (strongest): every operation appears atomic at a single real-time instant, respecting wall-clock order across all clients. Sequential: all operations appear in one shared total order consistent with each process's own program order, but that shared order need not match real wall-clock time across different processes — permits some reordering invisible to any single observer. Causal: only causally-related operations must be seen in the same order by everyone; concurrent, unrelated operations can be observed in different orders by different replicas — permits reordering of anything not causally linked. Eventual (weakest): the only guarantee is convergence given no new writes — permits arbitrary temporary staleness and reordering in the meantime.
**Follow-up trap:** *"Which of these can remain available under a network partition, and why?"* — causal and eventual can; a replica can always determine whether two operations it already knows about are causally related (via vector clocks) without needing to coordinate with an unreachable node, whereas linearizable and (in general) sequential consistency require coordination that a partition prevents.

### Q6 — Explain the R+W>N arithmetic and what it actually guarantees versus what it doesn't.
**Answer:** With `N` replicas, a write acknowledged by `W` of them and a read confirmed by `R` of them: if `R+W>N`, any write quorum and any read quorum are guaranteed to share at least one common replica, so a read is guaranteed to see the most recent completed write. It does **not** guarantee real-time recency for concurrent operations — two writes or a read racing a write can still produce ambiguous results that need reconciliation (vector clocks, last-write-wins, application-level merge); it also says nothing about the durability or ordering of writes that haven't yet completed.
**Follow-up trap:** *"Give me `R` and `W` for `N=3` that satisfies the arithmetic, and then one that doesn't."* — `R=2, W=2` satisfies it (`2+2=4>3`, and this is Cassandra's typical `QUORUM`/`QUORUM` setup). `R=1, W=1` does not (`1+1=2`, not `>3`) — this is a valid, faster, eventually-consistent configuration, but reads are no longer guaranteed to see the latest write.

### Q7 — Compare single-leader, multi-leader, and leaderless replication. When would you pick each?
**Answer:** Single-leader: simplest, no write-write conflicts, but the leader is a write bottleneck and single point of failure, and asynchronous replicas can serve stale reads — pick it when all writers are naturally close to one region and you want operational simplicity (most relational-database deployments). Multi-leader: accepts writes in multiple places, better write latency across regions, but requires conflict resolution — pick it when genuine multi-region write latency matters more than the complexity of resolving conflicts. Leaderless/quorum: no single point of failure for either reads or writes, tunable consistency per operation via R/W/N — pick it for high-write-availability workloads that can tolerate (and resolve) occasional conflicting/concurrent writes, like Dynamo/Cassandra-style key-value workloads.
**Follow-up trap:** *"Your multi-leader setup just had a conflict on the same row from two regions. Walk me through resolving it."* — depends on the data type: for a simple last-write-wins field, compare timestamps/version and pick one (accepting silent data loss on the other); for something mergeable (a counter, a set), use a CRDT that merges both without loss; for anything with business meaning (two conflicting inventory decrements), surface it to application logic rather than silently auto-resolving, since silent auto-resolution there is a correctness bug waiting to happen.

### Q8 — Range vs. hash partitioning: what's each good for, and what's each one's hot-spot failure mode?
**Answer:** Range partitioning keeps contiguous keys together, which is efficient for range scans and ordered access, but a monotonically increasing key (timestamp, auto-increment ID) concentrates all new writes on whichever partition currently owns the tail of the key range — every other partition idles while one gets hammered. Hash partitioning spreads keys roughly uniformly via a hash function, eliminating the monotonic-key hot-spot, but destroys range-scan locality (adjacent logical keys land on unrelated physical partitions, forcing scatter-gather) and still can't protect against a single wildly popular key overloading the one partition that owns it.
**Follow-up trap:** *"Your hash-partitioned table is evenly loaded overall but one node is at 5x CPU. Diagnose it."* — this looks like a hot-key problem, not a partitioning-scheme problem: check whether one specific key (a viral item, a celebrity account) is receiving disproportionate traffic within an otherwise well-balanced partition — fixed by key-specific caching or salting, not by re-partitioning the whole table.

### Q9 — What does read-your-writes actually fix, and how would you implement it cheaply?
**Answer:** It fixes the specific, very common user complaint of submitting a write and then not seeing it on an immediate subsequent read, caused by that read landing on a replica that hasn't caught up yet. Cheap implementations: route a client's reads to the leader (or to the same replica that served its last write) for some window after a write, or track a version/LSN watermark client-side and reject/retry a read from any replica that hasn't reached that watermark yet.
**Follow-up trap:** *"Does read-your-writes give you monotonic reads for free?"* — no, they're independent guarantees — read-your-writes only concerns a client's own writes; a client could still see a *different* value go backward in time on unrelated data if consecutive reads hit differently-lagged replicas without a separate monotonic-read mechanism (sticky sessions or a version check on every read, not just post-write reads).

### Q10 — Explain how Spanner achieves external consistency, and what it costs.
**Answer:** TrueTime exposes clock uncertainty as an explicit bounded interval (not a single timestamp) using GPS and atomic clock references; when committing a transaction, the leader waits out that uncertainty window (commit-wait) before acknowledging, guaranteeing the assigned timestamp has genuinely passed in real time before any other transaction can observe its effects — this is what makes Spanner's consistency externally (not just internally) consistent, i.e., linearizable across the whole global system, not just within one shard. Cost: measured commit-wait is on the order of 5-8ms for single-region deployments and can rise to 20ms+ for multi-region commits — a real, permanent latency tax paid on every write, not just during partitions.
**Follow-up trap:** *"Why can't every database just do this?"* — it requires genuinely tight, bounded clock uncertainty across all machines (historically Google-specific atomic-clock/GPS infrastructure); systems without that infrastructure approximate it with hybrid logical clocks and a larger, more conservative uncertainty bound (CockroachDB, YugabyteDB), which is workable but pays either a larger latency cost or accepts a slightly weaker guarantee than Spanner's original design.

### Q11 — Design the replication and partitioning strategy for a global multi-region e-commerce inventory system. What are you optimizing for and what would you actually pick?
**Testing:** synthesis under a realistic constraint with real consequences for being wrong.
**Answer:** Inventory decrements are exactly the kind of operation where overselling (two regions both believing 1 unit is available and both selling it) is a real business cost, so this pushes toward stronger consistency for the *decrement* operation specifically — either a single-leader-per-SKU-shard design (accepting some cross-region write latency for that SKU) or a Spanner/CockroachDB-style globally consistent counter for high-contention items, while low-contention catalog/browse data (product descriptions, images) can be eventually consistent and cached aggressively since staleness there is harmless. Partition by SKU/product ID with hashing to avoid hot-spotting on popular categories, but recognize that a single viral product is still a hot-key problem hashing alone won't fix — that needs a dedicated fast-path (a small, tightly-consistent counter service, or optimistic decrement with compensation) for specifically hot SKUs.
**Follow-up trap:** *"What if a network partition isolates one region during a flash sale?"* — that's the actual CAP moment: decide explicitly whether that region fails closed (refuses sales rather than risk overselling — CP) or fails open (keeps selling from potentially stale inventory counts, reconciling and possibly cancelling/refunding overselling after the fact — AP) — and this should be a stated business decision, not something the database's default settings decide by accident.

### Q12 — A candidate says "we use Cassandra so we're an AP system, full stop." What's wrong with that framing?
**Answer:** Cassandra's consistency is tunable per query, not fixed at the system level — you can run `QUORUM`/`QUORUM` reads and writes (`R+W>N`) and get effectively strong, CP-like behavior for specific operations while other operations on the same cluster use `ONE` for AP-like speed. Calling the whole system "AP" erases that per-operation tunability, which is precisely the thing an interviewer wants to hear you articulate — the interesting design decision is *which* operations get which consistency level and why, not a single label for the whole database.
**Follow-up trap:** *"So is there ever a case where Cassandra genuinely can't give you consistency, regardless of the consistency level you request?"* — yes: during a partition severe enough that not even a quorum subset (`W` or `R` replicas) is reachable from a given coordinator, no consistency level configuration saves you — at that point the request simply fails or falls back to a sloppy quorum (if enabled), which is the real, unavoidable CAP moment underneath all the tunability.

---

## Red flags that fail you

- Saying "CAP means you pick two of three" without qualifying that it only applies during an actual partition.
- Conflating CAP's availability with an uptime SLA number.
- Conflating CAP's "C" with ACID's "C."
- Being unable to state PACELC's four quadrants or classify a real system into one.
- Claiming R+W>N guarantees real-time recency for concurrent operations.
- Recommending hash partitioning as a universal fix for hot partitions without acknowledging the single-hot-key case it doesn't fix.
- Describing Cassandra or DynamoDB as strictly "AP" with no mention of their tunable, per-operation consistency levels.
- Not knowing that Spanner's consistency has a real, measured latency cost (commit-wait), treating it as a free win.

---

## Cheat card

```
CAP (Gilbert-Lynch 2002, formalizing Brewer 2000)
  C = linearizability (NOT ACID's C)   A = every non-failing node responds (NOT an SLA%)
  P = survives arbitrary partition       -- only forces C-vs-A choice DURING a partition
  MISCONCEPTION: "pick 2 of 3" always -- wrong; P isn't optional, tradeoff is partition-only

PACELC (Abadi 2012) -- the useful one
  if Partitioned: choose Availability or Consistency
  Else (normal operation, ~99.99% of the time): choose Latency or Consistency
  Spanner = PC/EC   Dynamo/Cassandra = PA/EL (tunable)   Postgres leader = ~PC/EC path, replica reads ~EL

CONSISTENCY SPECTRUM (strong -> weak)
  linearizable (real-time total order) > sequential (total order, no real-time tie)
  > causal (only causal deps ordered) > eventual (convergence only, no ordering)
  session guarantees: read-your-writes, monotonic reads, monotonic writes, writes-follow-reads

REPLICATION
  single-leader: simple, no write conflicts, leader = bottleneck + SPOF, async replicas can be stale
  multi-leader: better cross-region write latency, needs conflict resolution (LWW/CRDT/app-merge)
  leaderless/quorum: R+W>N -> read & write quorums always overlap -> read sees latest completed write
    R+W>N guarantees OVERLAP, not real-time recency of concurrent ops
    Cassandra QUORUM/QUORUM at N=3: R=2,W=2 (4>3); LOCAL_QUORUM = majority in coordinator's DC only
    Dynamo: sloppy quorum + hinted handoff relaxes R+W>N during partition -> AP tradeoff made explicit

PARTITIONING
  range: great for scans, HOT PARTITION on monotonic keys (timestamp/auto-incr concentrates on tail)
  hash: even load, kills range scans (scatter-gather), does NOT fix a single hot/celebrity key

REAL SYSTEMS
  Spanner: PC/EC, TrueTime bounded clock uncertainty, commit-wait ~5-8ms single-region, 20ms+ multi-region
  DynamoDB: leaderless Dynamo lineage, managed service defaults to eventual reads (R=1), opt-in strong read
  Cassandra: leaderless, per-query consistency level, Murmur3 hash partitioner, hinted handoff+read repair
  Postgres: single-leader, WAL streaming, synchronous_commit levels = the L-vs-C PACELC knob, literally
```

## Sources

- [Strict Serializability and External Consistency in Spanner — Google Cloud Blog](https://cloud.google.com/blog/products/databases/strict-serializability-and-external-consistency-in-spanner) — accessed 2026-07-26
- [Spanner: TrueTime and external consistency — Google Cloud Documentation](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency) — accessed 2026-07-26
- [Dynamo — Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/cassandra/architecture/dynamo.html) — accessed 2026-07-26
- [Consistency Levels in Cassandra — Baeldung](https://www.baeldung.com/cassandra-consistency-levels) — accessed 2026-07-26
- [Read/Write Quorums and the Algebra of Consistency — Java Code Geeks](https://www.javacodegeeks.com/2026/07/read-write-quorums-and-the-algebra-of-consistency-why-n-r-and-w-arent-just-configuration-knobs.html) — accessed 2026-07-26
- [The CAP Theorem Question Every Senior System Design Interview Asks — DEV Community](https://dev.to/gabrielanhaia/the-cap-theorem-question-every-senior-system-design-interview-asks-425m) — accessed 2026-07-26
- [CAP Theorem vs PACELC — DesignGurus](https://www.designgurus.io/blog/system-design-interview-basics-cap-vs-pacelc) — accessed 2026-07-26
- [PACELC Theorem Explained In System Design — System Design Handbook](https://www.systemdesignhandbook.com/guides/pacelc-theorem/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
