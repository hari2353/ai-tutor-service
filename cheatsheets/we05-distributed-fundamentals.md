# CAP/PACELC, Consistency Models, Replication, Partitioning

> Sprint weekend 5 · source: `curriculum/10-system-design/01-distributed-fundamentals.md`

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
