# Consensus (Raft), Leader Election, Lamport/Vector/HLC Clocks

> **Track:** T10 System Design · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T10-consensus-ordering` · **Tags:** fundamentals

## The 30-second version

Consensus exists because a distributed system with more than one node needs a way to agree on a single value (who is leader, what the next log entry is) even when nodes crash and messages are delayed or lost, and that agreement has to survive a genuine network split without two nodes each believing they're in charge. Raft solves it by decomposing the problem into leader election, log replication, and safety, and getting all of it via majority quorums (`2f+1` nodes tolerate `f` failures, so 3 nodes tolerate 1, 5 tolerate 2) and randomized election timeouts (150-300ms) that make split votes rare and self-resolving. It beat Paxos in adoption not because it's more powerful, they're equivalent in what they can guarantee, but because Ongaro and Ousterhout's 2014 user study showed it's measurably easier for engineers to implement correctly, which matters enormously when the algorithm underpins etcd, Consul, CockroachDB, and Kafka's KRaft controller. Underneath ordering, Lamport clocks give you a cheap total order with no causality guarantee, vector clocks give you exact causality at `O(n)` space per event, and hybrid logical clocks split the difference by riding on physical time, which is why HLC is what CockroachDB and MongoDB actually ship.

## Why this gets asked

Every interviewer who has run a stateful service in production has either lived through a split-brain incident (two nodes both accepting writes as "the leader" after a network blip) or has debugged a bug caused by assuming events happened in the order their timestamps suggested, when the clocks were skewed by seconds. The question tests whether you can name the actual mechanism that prevents split-brain (majority quorum, not "we use ZooKeeper") and whether you understand that "ordering" is not one concept: total order, causal order, and real-time order are different guarantees with different costs, and conflating them is how people ship correctness bugs into production ranking or billing pipelines.

## Lineage: past → present → future

**What came before.** Before Raft, production systems needing consensus used Paxos (Lamport, 1998) or ad hoc leader-election schemes bolted onto ZooKeeper/Chubby. Paxos is correct and has been proven so for over two decades, but the original paper is famously difficult to map onto an implementation: Lamport's own presentation separates "Basic Paxos" (agreeing on one value) from the multi-decree extension needed for a replicated log, and leaves huge gaps (how do you actually pick a leader, how do you handle log compaction, how do membership changes work) that every team had to solve independently and often incompatibly. The pain that killed "just implement Paxos" as the default answer was concrete: Google's own engineers wrote in the Paxos Made Live paper (2007) that a "significant gap exists between the description of the Paxos algorithm and the needs of a real-world system," and multiple teams building on the algorithm produced subtly different, hard-to-verify systems. Ongaro and Ousterhout's explicit design goal for Raft, stated in "In Search of an Understandable Consensus Algorithm" (USENIX ATC 2014), was understandability as a first-class engineering property, not just correctness ([In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf) — accessed 2026-08-01).

**Where it stands now.** Raft has become the default choice for new systems needing replicated-log consensus: etcd (and therefore Kubernetes' control plane), Consul, CockroachDB, TiKV, and Kafka's KRaft controller (replacing the ZooKeeper-based controller as of Kafka 4.0) all use it. The user study behind the original paper found 33 of 43 students scored better on Raft comprehension questions than Paxos questions after being taught both ([In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf) — accessed 2026-08-01), which is the concrete evidence for "won on comprehensibility, not power" — Raft and Paxos are proven equivalent in fault tolerance and the conditions under which they can make progress (both need a majority of nodes reachable). The live disagreement is less "which algorithm" and more "how much do you trust a leader-based design's availability characteristics" — Raft's strong single-leader model means all writes serialize through one node, which is simple to reason about but caps write throughput at what one leader can push, and EPaxos-style leaderless variants exist specifically to remove that bottleneck at the cost of real implementation complexity that almost nobody accepts in practice.

**Where it's heading.** High confidence: Raft continues displacing bespoke Paxos implementations for new greenfield systems, exactly because "the team can actually verify their implementation against a widely-tested reference" now outweighs any theoretical throughput ceiling for the large majority of use cases. Kafka's full migration off ZooKeeper onto KRaft (Raft-based) is the concrete 2024-2026 case study of an entire ecosystem swapping its consensus layer. On clocks: hybrid logical clocks are the settled answer for "give me ordering without atomic-clock hardware" and adoption (CockroachDB, MongoDB, YugabyteDB) is not slowing. More speculative: as globally-distributed OLTP systems become more common outside Google, expect more systems to expose an explicit clock-uncertainty bound to the application (à la Spanner's TrueTime, approximated via HLC + NTP) rather than hiding it, because correctness bugs from silently trusting wall-clock timestamps keep recurring.

---

## Mental model

```
LEADER ELECTION as a lease you have to keep renewing:

  Follower ──(no heartbeat for election_timeout, e.g. 150-300ms)──▶ becomes Candidate
  Candidate ──(votes for self, requests votes, increments TERM)──▶ waits for majority
  Candidate ──(gets majority of N nodes, e.g. 3 of 5)──▶ becomes Leader
  Leader ──(sends heartbeat/AppendEntries every ~50ms)──▶ keeps followers from timing out
  Leader ──(heartbeat stops: crash, GC pause, network partition)──▶ followers time out, re-elect

  TERM is a logical clock over LEADERSHIP itself: every election bumps it.
  A message carrying an old term is immediately rejected -- this is what
  makes it safe for an old, isolated leader to keep sending heartbeats to
  itself and nobody else: everyone else has moved to a higher term and
  will ignore it.

FENCING TOKEN as the fix for the gap fencing token vs term doesn't close by itself:

  Client A acquires lease, gets token=34, pauses (GC, VM freeze) for 30s
  Lease expires. Client B acquires lease, gets token=35, writes to storage
  Client A wakes up, still thinks it holds the lease, writes to storage
      -- storage must REJECT A's write because 34 < 35 (last-seen token)
      -- this check has to live in the STORAGE layer, not the lock service,
         or the whole mechanism is decorative
```

**Ordering, three different guarantees, three different costs:**

```
Lamport clock:      total order, NO causality      O(1) per event -- one integer
Vector clock:       exact causality                O(n) per event -- one integer PER NODE
Hybrid Logical Clock: causality + wall-clock-close  O(1) per event -- one 64-bit value
                     (rides physical time; falls back to a logical counter on ties)
```

---

## How it actually works

### Raft: leader election

A cluster of `N` nodes (almost always odd: 3, 5, or 7) starts with every node a **follower**. Each follower runs a randomized election timer, chosen fresh on every reset from a fixed range, the paper's reference implementation uses **150-300ms** ([In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf) — accessed 2026-08-01). If a follower hears no `AppendEntries` RPC (which doubles as a heartbeat when it carries no new entries) before its timer fires, it:

1. Increments its **term** (a monotonically increasing integer that acts as a logical clock over leadership epochs).
2. Transitions to **candidate**, votes for itself, and sends `RequestVote` RPCs to every other node, each carrying its term and the index/term of its last log entry.
3. A node grants a vote only if the candidate's term is at least as high as its own and the candidate's log is at least as up-to-date as its own (this is the safety-critical part: it prevents electing a leader that's missing committed entries).
4. Each node votes at most once per term. The first candidate to collect votes from a **majority** (`⌊N/2⌋+1`) becomes leader for that term.

The randomization is what makes elections converge in practice: if timeouts were fixed, every follower would time out simultaneously and split the vote every single time. With a 150ms spread, one node almost always fires first and wins before others even become candidates. **Heartbeats** go out roughly every 50ms, an order of magnitude below the election timeout, giving comfortable margin against normal network jitter ([Raft Consensus Algorithm — raft.github.io](https://raft.github.io/) — accessed 2026-08-01). In production, the rule of thumb is: election timeout should be **at least 10x the round-trip time** between nodes, and heartbeat interval close to that RTT — over a WAN with 50ms RTT you need proportionally longer timeouts or you get spurious elections ([etcd FAQ](https://etcd.io/docs/v3.7/faq/) — accessed 2026-08-01).

**Quorum size and fault tolerance**, `2f+1` nodes tolerate `f` crash failures because a majority quorum is `f+1` and you need that quorum to survive with `f` nodes down:

| N | Quorum (majority) | Tolerated failures (f) |
|---|---|---|
| 3 | 2 | 1 |
| 4 | 3 | 1 |
| 5 | 3 | 2 |
| 7 | 4 | 3 |

Note 4 nodes buys you nothing over 3 (still tolerates only 1 failure) while costing an extra vote and extra replication traffic — this is why production etcd/Consul clusters are always odd ([Understanding etcd Quorum — labitlearnit](https://labitlearnit.com/2026/04/05/understanding-etcd-quorum-why-3-nodes-never-2-or-4/) — accessed 2026-08-01).

### Log replication and commit index

Once elected, the leader is the only node that accepts client writes. Each write becomes a log entry `(term, index, command)` appended to the leader's log, then replicated to followers via `AppendEntries`. The leader advances its **commit index** once an entry is stored on a majority of nodes, entries below the commit index are guaranteed durable and are applied to the state machine; entries above it are not yet safe and can still be overwritten. Followers only accept `AppendEntries` if the leader's claimed previous log index/term matches their own tail, this is the mechanism (a consistency check on every RPC) that prevents log divergence: any inconsistency forces the leader to walk backward and overwrite the follower's conflicting suffix.

### Safety: why this doesn't just work by "majority wins"

The subtlety that separates a correct implementation from a broken one: a newly elected leader must never overwrite an already-committed entry. Raft guarantees this via the **election restriction** — a candidate can only win a vote if its log is at least as up-to-date (compared by last-entry term, then index) as the voter's, so a node holding a committed entry the candidate lacks will simply refuse to vote for it. Combined with "committed = stored on a majority," this guarantees any future leader's log is a superset of all previously committed entries. This is the single most-missed detail candidates gloss over when they say "majority just means avoiding split-brain" — majority quorums also guarantee no committed data is silently lost across leader changes.

### Membership changes

Naively swapping the whole cluster configuration atomically is unsafe: mid-transition, a stale-configuration majority and a new-configuration majority could each independently elect a leader, producing two leaders simultaneously. Raft's original paper solves this with **joint consensus**: a transitional configuration where log entries require majorities from *both* the old and new node sets before committing, guaranteeing no single term can produce two leaders even during a reconfiguration. Simplified single-server-add/remove implementations (what etcd actually ships) sidestep the full joint-consensus machinery by only ever adding or removing one node at a time, since a majority of `N` and a majority of `N±1` are guaranteed to overlap.

### Split-brain and fencing tokens

Consensus prevents split-brain **at the leadership layer**: a stale leader isolated by a partition cannot get its writes committed because it cannot reach a majority, so its log entries stay uncommitted and are eventually overwritten. But this only holds *inside* the consensus protocol. The moment that stale leader talks directly to an external system (a storage backend, a payment API) without routing through the log, term/quorum checks don't apply anymore, and this is exactly the class of bug Martin Kleppmann's 2016 critique of Redlock highlighted: a lock or lease alone doesn't stop a paused, stale holder from writing after it thinks it still owns the lock, because pauses (GC, VM stop-the-world, swap) can exceed the lease TTL without the holder knowing ([How to do distributed locking — Kleppmann](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — accessed 2026-08-01). The fix is a **fencing token**: a monotonically increasing number handed out on every lease/leadership acquisition, which the storage layer itself checks and rejects if it's lower than the last token it has seen. The token has to be enforced where the actual state-changing write happens, not at the lock service, or a paused client can still race a valid write in after its lease expired.

### Logical clocks, derived

**Lamport clocks** (Lamport, 1978): every process keeps a counter `C`. On a local event, increment `C`. On sending a message, attach the current `C`. On receiving a message with timestamp `C_msg`, set `C = max(C, C_msg) + 1`. This gives a **total order** consistent with causality (`a → b` implies `C(a) < C(b)`), but the converse is false: `C(a) < C(b)` does **not** imply `a` happened before `b` or is even related to it — two fully concurrent, unrelated events on different nodes can get any relative counter values. This is the trap: people read "Lamport timestamp is lower" as "happened first," and it isn't a causality claim at all, just an arbitrary consistent tiebreak.

**Vector clocks** (Fidge/Mattern, 1988): each of `N` processes maintains a vector of `N` counters, incrementing its own slot on each local event and taking the element-wise max on message receipt (then incrementing its own slot). Two events are causally ordered if one vector clock is element-wise `≤` the other and not equal; if neither dominates, they're **concurrent**, and vector clocks are the only one of these three schemes that can detect that fact precisely. The cost is exactly the size problem: the vector is `O(n)` in the number of nodes, and it grows with every node that has ever participated, in large or churny clusters (many short-lived clients, not just fixed servers) this becomes a real bandwidth and storage cost, which is why systems like Dynamo that use vector clocks for conflict detection have to periodically prune or truncate them, accepting some loss of precision.

**Hybrid Logical Clocks** (Kulkarni, Demirbas, Madappa, Avva, Leone, OPODIS 2014): a single value combining a physical-time component `pt` (from NTP-synced wall clocks) and a logical counter `l`. On each event: if the local physical clock has advanced past the max of your last HLC and any received HLC, reset `l = 0` and use the new physical time; otherwise keep the higher physical component and increment `l` to break the tie. This gives you: (1) causal ordering, like Lamport clocks provide for total order, (2) a value that stays close to wall-clock time so it's human-readable and directly comparable to real time within the clock synchronization bound, and (3) constant, `O(1)`, space per event — none of the vector clock's per-node blowup. This is why HLC won over vector clocks for systems that need both causality tracking and a timestamp usable for snapshot/MVCC purposes: **CockroachDB** uses HLC for transaction ordering, with an uncertainty interval equal to the configured max clock offset (default 500ms) used to resolve ambiguous reads; **MongoDB** exposes it as `ClusterTime`/`operationTime` for causal consistency across its replica sets ([Hybrid Logical Clock — singhajit.com](https://singhajit.com/distributed-systems/hybrid-clock/) — accessed 2026-08-01; [Logical Physical Clocks — Kulkarni et al.](https://cse.buffalo.edu/tech-reports/2014-04.pdf) — accessed 2026-08-01).

### Leases and clock assumptions — what breaks when the clock is wrong

A **lease** is time-bounded ownership: "I am the leader/lock-holder until wall-clock time `T`." This only works if every party's assumptions about elapsed time hold: the lease-granter's clock, the lease-holder's clock, and the fact that a process paused for longer than the lease duration will notice it's stale before acting. What actually breaks:

- **Clock skew between nodes** makes a lease granted "for 10s" by one node's clock expire at a different wall-clock instant than the holder believes, if node A's clock runs 3s fast, A may think it still holds a lease that B has already reissued to someone else.
- **NTP step corrections** (a large, sudden jump rather than gradual `slew`) can make a clock jump backward or forward discontinuously, invalidating any code that assumes monotonic wall-clock progress; this is why lease/timeout code should use a **monotonic clock** (e.g. `CLOCK_MONOTONIC`, not wall-clock `gettimeofday`) for measuring elapsed durations, and wall-clock only for absolute human-facing timestamps.
- **A paused process** (stop-the-world GC, hypervisor live-migration freeze, swap thrashing) doesn't know time has passed at all until it resumes, this is the exact scenario fencing tokens exist for: the lease can correctly expire and be reassigned while the paused holder is frozen, and only a check at the point of write (the fencing token) catches it when it wakes up and tries to act as if nothing happened.

---

## Build it from scratch

A minimal, single-process simulation of Raft leader election over three in-memory nodes, no networking, enough to see the term/vote/quorum mechanics without a whole RPC layer:

```python
# untested sketch -- illustrates term/vote/quorum logic, not a real Raft implementation
import random

class Node:
    def __init__(self, node_id, peers):
        self.id = node_id
        self.peers = peers          # list of Node, filled in after construction
        self.term = 0
        self.voted_for = {}         # term -> node_id voted for
        self.state = "follower"
        self.log = []                # list of (term, command)

    def last_log_term(self):
        return self.log[-1][0] if self.log else 0

    def request_vote(self, candidate_id, candidate_term, candidate_last_log_term, candidate_last_log_len):
        if candidate_term < self.term:
            return False, self.term
        if candidate_term > self.term:
            self.term = candidate_term
            self.state = "follower"
        already_voted = self.voted_for.get(self.term)
        log_ok = (candidate_last_log_term > self.last_log_term() or
                  (candidate_last_log_term == self.last_log_term() and
                   candidate_last_log_len >= len(self.log)))
        if (already_voted is None or already_voted == candidate_id) and log_ok:
            self.voted_for[self.term] = candidate_id
            return True, self.term
        return False, self.term

    def start_election(self):
        self.term += 1
        self.state = "candidate"
        self.voted_for[self.term] = self.id
        votes = 1  # vote for self
        for peer in self.peers:
            granted, peer_term = peer.request_vote(
                self.id, self.term, self.last_log_term(), len(self.log))
            if peer_term > self.term:
                self.term = peer_term
                self.state = "follower"
                return False
            if granted:
                votes += 1
        majority = len(self.peers) // 2 + 1  # +1 self counted separately above; peers+self = N
        won = votes >= (len(self.peers) + 1) // 2 + 1
        if won:
            self.state = "leader"
        return won


def simulate():
    nodes = [Node(i, []) for i in range(5)]
    for n in nodes:
        n.peers = [p for p in nodes if p is not n]
    candidate = random.choice(nodes)
    won = candidate.start_election()
    print(f"node {candidate.id} term={candidate.term} won={won} state={candidate.state}")

simulate()
```

This omits the randomized-timeout-driven trigger (a real implementation needs a timer per node and a network layer with realistic delay/loss injection), log replication, and the joint-consensus membership-change protocol. A full lab with a simulated network (dropped/delayed messages, partition injection, and log replication through to commit index) belongs at `(lab pending)` (not yet in this repo).

---

## How it's done in production

| System | Consensus | Notes |
|---|---|---|
| etcd (Kubernetes control plane) | Raft (etcd-io/raft library) | 3 or 5 node clusters standard; election timeout tuned to ≥10x inter-node RTT |
| HashiCorp Consul | Raft | Server pool typically 3 or 5; separate gossip layer (Serf/SWIM) for failure detection among the larger agent fleet |
| CockroachDB | Raft per range (one consensus group per data shard) | Thousands of independent Raft groups in a large cluster; HLC for transaction timestamp ordering |
| Apache Kafka (KRaft, 4.0+) | Raft, replacing ZooKeeper-based controller | Controller quorum (typically 3 nodes) now stores cluster metadata directly in a Raft-replicated log |
| Google Spanner / Chubby | Paxos | Predates Raft; still Paxos because the systems and their operational knowledge predate 2014 and rewriting a proven consensus core is rarely worth it |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Cluster repeatedly re-elects, no stable leader ("election storm") | Election timeout too close to actual network RTT, or GC pauses exceeding timeout | Raise election timeout to ≥10x measured RTT; tune GC/heap; separate consensus traffic onto its own network path |
| Two nodes both act as leader briefly after a network blip | Old leader hasn't yet noticed a higher term exists (message still in flight) and keeps serving until it tries to commit | Not actually split-brain if writes go through the log correctly, uncommitted writes from the stale leader are simply never acknowledged; but any *external* side effect issued by the stale leader before it steps down is the real danger, hence fencing tokens |
| A stale, paused lock/lease holder writes to storage after another node already acquired the lease | No fencing token, or token not checked at the point of write | Enforce a monotonically increasing token at the storage layer itself, reject any write with a token below the last seen |
| Vector-clock payloads grow unbounded in size and network cost | Long-lived cluster with high node churn; every node that ever participated keeps a slot | Prune/garbage-collect stale node entries, or switch to HLC if you don't need exact concurrent-event detection |
| Two events that are actually unrelated get treated as "A happened before B" because of Lamport timestamps | Conflating "Lamport clock is lower" with "causally precedes" | Use vector clocks or HLC-with-explicit-causality-tracking when you need to *detect* concurrency, not just get *some* total order |
| A distributed lock "expires" but the old holder's write still lands | Wall-clock-based lease with no fencing check, holder was paused past the lease TTL | Fencing tokens at the storage layer; use monotonic clocks for measuring lease duration |

---

## Tradeoffs & when NOT to use it

- **Don't build a custom Raft implementation for a new system unless you genuinely need a replicated log and no existing library or managed service fits.** etcd, Consul, and battle-tested libraries (etcd-io/raft, hashicorp/raft) exist precisely because getting the safety proofs right (the election restriction, the commit-index visibility rules) is easy to get subtly wrong under load, and subtle wrongness here means silent data loss, not a crash you'd notice.
- **Don't reach for full Raft/Paxos consensus when you only need leader election, not a replicated log of application commands.** A lease-based leader election on top of a managed coordination service (etcd, ZooKeeper, DynamoDB conditional writes) is simpler and sufficient if you don't need every state transition to be an ordered, durable log entry.
- **Vector clocks are the wrong default when you don't actually need to detect concurrent, conflicting writes.** If last-write-wins or application-level merge (CRDTs) is acceptable, a simpler timestamp or HLC avoids the O(n) blowup entirely.
- **A single-leader consensus design caps your write throughput at what one machine can process**, because every write serializes through the leader's log. If write throughput genuinely needs to scale past one node (not just read throughput, which followers can serve), you need sharding (multiple independent consensus groups, like CockroachDB's per-range Raft groups) rather than a bigger single Raft cluster.
- **Fencing tokens are worthless if the storage layer doesn't check them.** Adding a token to your lock library without plumbing the check into every write path that matters is a false sense of safety, worse than no token, because it looks solved.
- **Lamport clocks are the wrong tool whenever you need to know if two events are actually related**, not just some arbitrary consistent order. Use them only when you need *a* total order for a purpose like conflict tiebreaking, not when the ordering claim itself needs to be meaningful.

---

## Interview questions

### Q1 — Why do you need a majority quorum, not just "more than one node agrees"?
**Testing:** whether you understand the overlap guarantee, not just the vocabulary.
**Answer:** A majority quorum guarantees that any two quorums (e.g., the quorum that elected the old leader and the quorum that elects a new one) share at least one node. That shared node is what prevents two disjoint groups from each independently believing they have a valid leader or a valid commit, i.e. split-brain. Any quorum smaller than a majority (say, any 2 nodes out of 5 chosen arbitrarily) doesn't guarantee overlap, so two different groups of "2 out of 5" could both proceed independently and diverge.
**Follow-up trap:** *"Why must N be odd in production?"* — it isn't a hard requirement (4 nodes still have well-defined majorities), but 4 nodes tolerate the same 1 failure as 3 nodes while costing an extra replica and vote, so odd sizes are the efficient choice; N even never buys you anything over N-1.

### Q2 — Walk through exactly what happens when a Raft leader is network-partitioned from the majority.
**Testing:** mechanical understanding of the election-restriction and commit-index rules together.
**Answer:** The isolated leader keeps trying to send heartbeats and accept client writes, but since it can't reach a majority, it can never advance its commit index past whatever was already committed, any new entries it appends stay uncommitted. Meanwhile the majority partition times out on that leader, elects a new one (term increments), and continues committing entries under the new term. When the partition heals, the old leader discovers a higher term in a message, steps down to follower, and its uncommitted log tail is overwritten to match the new leader's log.
**Follow-up trap:** *"What if a client already got a success response from the old, isolated leader before the partition?"* — that response should never have been sent: a correct implementation only acknowledges a write to the client after the entry is committed (majority-replicated), and an isolated leader can't reach that majority, so it can't legitimately ack. If it acked anyway (bug), that's exactly the kind of correctness bug fencing tokens and "never ack before commit" discipline exist to prevent.

### Q3 — What specifically did Raft do differently from Paxos to be more "understandable," and is it more powerful?
**Testing:** whether you know this is a comprehensibility claim, not a capability claim.
**Answer:** Not more powerful, they are proven equivalent in the failure conditions under which they can make progress (both need a live majority). Raft's difference is structural: it decomposes the problem into independently-explainable subproblems (leader election, log replication, safety) and enforces stronger invariants that reduce the number of cases you have to reason about, for instance, the election restriction that only lets up-to-date candidates win, versus Paxos's more general approach that requires separately reasoning about proposal numbers and acceptor state. The 2014 user study (43 students, taught both algorithms) found most scored better on Raft comprehension questions, which is the actual evidence base for the comprehensibility claim.
**Follow-up trap:** *"So why do Spanner and Chubby still use Paxos?"* — because they predate Raft (Chubby: mid-2000s, Spanner: 2012) by years, and a proven, deeply understood consensus core inside a system already running in production is not something you rip out for a comprehensibility win; the cost of a subtle bug in a rewrite vastly outweighs the benefit.

### Q4 — Explain the difference between "committed" and "replicated" in Raft's log.
**Testing:** precision on the safety-critical vocabulary.
**Answer:** An entry is replicated once it's been appended to a follower's log via AppendEntries, that can happen to a minority. An entry is committed once it's been replicated to a **majority**, at which point the leader can safely apply it to its state machine and acknowledge the client, because majority-replication guarantees it will survive any future leader election (the election restriction ensures a future leader's log is a superset of all committed entries).
**Follow-up trap:** *"Can an uncommitted entry ever be committed later after a leader change?"* — an entry from an *earlier* term that's only replicated to a minority can be overwritten by a new leader; Raft explicitly does not commit entries from previous terms by counting replicas directly, it only does so indirectly by committing a later entry in its own term that comes after them in the log, a detail (Figure 8 in the original paper) that trips up most people who think they understand commit rules.

### Q5 — What's a fencing token and what specific failure does it prevent that a lease alone doesn't?
**Testing:** whether "we use locks" is backed by actual understanding of the gap.
**Answer:** A fencing token is a monotonically increasing number issued every time a lock/lease is granted. It prevents a stale lease holder, one that was paused (GC, VM freeze) past its lease TTL without knowing it, from corrupting shared state after another node has already acquired the lease and is acting on it. The check has to happen at the point of the actual write (the storage system rejects any write carrying a token lower than the highest it's seen), not at the lock service, because the lock service has no way to intercept the stale client's write once it wakes up.
**Follow-up trap:** *"Doesn't Redlock (Redis-based distributed locking) already solve this?"* — no; Kleppmann's critique is specifically that Redlock provides mutual exclusion under a timing assumption (bounded clock drift and pause time) but produces no fencing token at all, so even if the mutual-exclusion guarantee holds, there's nothing to stop a stale holder's write from landing at the storage layer unless you separately add a fencing mechanism there.

### Q6 — Lamport timestamp of event A is less than event B's. What can you conclude?
**Testing:** the classic trap on the difference between total order and causality.
**Answer:** Almost nothing about their relationship. If `A → B` (A causally precedes B, e.g. A is a send and B is the corresponding receive, or they're on the same process in program order), then `C(A) < C(B)` is guaranteed. But the converse doesn't hold: two fully concurrent, unrelated events on different processes can end up with `C(A) < C(B)` purely from the arbitrary tie-breaking in the algorithm, with no causal relationship at all.
**Follow-up trap:** *"So how would you actually detect two events are concurrent, not causally related?"* — you can't with Lamport clocks alone; you need vector clocks (compare component-wise; neither dominates the other means concurrent) or an explicit causality-tracking scheme layered on top.

### Q7 — Why do vector clocks not scale, and what's the practical consequence?
**Testing:** whether the O(n) cost is just a fact you memorized or something you understand the impact of.
**Answer:** A vector clock carries one counter per participating node, so every message and every stored version carries O(n) space and every comparison is O(n) time, where n is the number of distinct nodes/clients that have ever contributed to that data's causal history. In a system with high client churn (many short-lived writers, not just a fixed set of servers), n keeps growing and never naturally shrinks unless you actively prune it, this shows up as growing metadata size per object (Dynamo's classic "sibling" version vectors bloating over time) and real bandwidth/storage overhead.
**Follow-up trap:** *"How would you fix it without losing causality tracking entirely?"* — prune entries for nodes that haven't contributed in some bounded window (accepting a small risk of false-concurrent detection for very old, inactive nodes), or switch to hybrid logical clocks if you can accept losing exact concurrent-write detection in exchange for O(1) space and still get causal ordering for the common case.

### Q8 — Explain how a Hybrid Logical Clock actually computes its next value.
**Testing:** mechanical depth, not just "it combines physical and logical time."
**Answer:** HLC keeps a pair `(pt, l)`: a physical-time component and a logical counter. On a local event or send: if the current wall-clock reading is greater than the max of the node's last HLC physical component and the max seen in received messages, adopt the new wall-clock value and reset `l = 0`; otherwise keep the higher physical component unchanged and increment `l` to break the tie between events that arrive in the same physical instant. On receiving a message with HLC `(pt_m, l_m)`, the node takes the max of its own physical time, its last HLC, and the message's HLC as the new physical component, incrementing `l` appropriately when physical components tie. This guarantees the resulting value both respects causality (like a Lamport clock) and stays within a bounded distance of true wall-clock time, unlike a pure logical clock which can drift arbitrarily far from real time.
**Follow-up trap:** *"What happens if a node's physical clock is badly skewed, say running 10 minutes fast?"* — HLC doesn't hide this, that node's `pt` values will dominate the max computation everywhere it sends messages, effectively poisoning downstream HLC values with its wrong physical time; this is why HLC-based systems (CockroachDB) also enforce a bounded max clock offset assumption (default 500ms) and treat exceeding it as a correctness-threatening condition, not something the clock scheme silently absorbs.

### Q9 — Design leader election with lease-based ownership for a job scheduler that must guarantee exactly one active scheduler at a time. What breaks first under what condition?
**Testing:** synthesis, and whether you spontaneously bring up fencing without being asked.
**Answer:** Use a coordination service (etcd/ZooKeeper/a Raft-backed KV store) with a TTL-based lease: the scheduler acquires a lease key with a short TTL and must renew it before expiry to remain active; on renewal failure it must stop scheduling immediately (fail closed) rather than assume it's still leader. Every action the scheduler takes that touches external state should carry the lease's fencing token, incrementing on every acquisition, checked by whatever system executes the scheduled jobs. What breaks first: a scheduler process that gets a long GC pause or is preempted by the OS for longer than the lease TTL will keep believing it's leader when it wakes up; without a fencing check downstream, it can dispatch a duplicate job run concurrently with the new leader's dispatch of the same job.
**Follow-up trap:** *"What TTL would you pick and why?"* — short enough that failover is fast (user-visible unavailability is bounded), long enough that normal GC pauses and network jitter don't cause spurious lease loss and thrashing between two schedulers each briefly believing they're leader; concretely, something like 10-30s with renewal attempted at a third of that interval is a typical starting point, tuned against measured GC pause p99 and network RTT, and you should say you'd measure rather than guess in production.

### Q10 — A candidate says "we use Raft, so we're split-brain proof." What's wrong with that claim?
**Testing:** the staff-level distinction between protocol-internal safety and system-wide safety.
**Answer:** Raft's guarantees hold for the log it manages: it prevents two leaders from both getting entries committed in the same term, and it prevents committed data from being lost across leader changes. It says nothing about a stale leader's **side effects issued outside the log**, if the old leader talks directly to an external payment gateway or writes to a separate database without routing that action through consensus, no term or quorum check protects that action. Split-brain "within Raft" being impossible doesn't mean split-brain-adjacent bugs in the surrounding system are impossible.
**Follow-up trap:** *"Give a concrete example of this exact bug."* — a job scheduler backed by Raft-elected leadership calls out to a third-party API to send an email on every scheduled tick; during a network partition the isolated old leader (not yet aware it's lost leadership) still fires the external call because that call isn't gated by the Raft log's commit index, only by in-memory leader-state, which can be stale for as long as the partition lasts before the heartbeat timeout triggers a step-down.

### Q11 — How would you decide between building a leaderless (EPaxos-style) system versus accepting Raft's single-leader write bottleneck?
**Testing:** staff/principal-level judgment about real-world tradeoffs, not textbook knowledge of EPaxos.
**Answer:** Almost never build leaderless consensus yourself; the complexity of correctly handling conflicting concurrent commands without a leader (EPaxos's dependency-graph based ordering) is substantial, and very few teams have the appetite to verify it. If the single leader is genuinely the write bottleneck, the standard, well-trodden fix is sharding into multiple independent Raft groups (like CockroachDB's per-range design), each with its own leader, so write throughput scales with shard count rather than trying to remove the single-leader constraint within one group.
**Follow-up trap:** *"What if the workload can't be sharded, e.g., a single hot counter everyone writes to?"* — that's a fundamentally different problem than consensus algorithm choice; the fix is usually at the data-modeling layer (batching/coalescing writes, CRDT-based counters that merge, or accepting eventual consistency for that specific counter) rather than switching consensus protocols, since no consensus algorithm makes a single logical resource's serialization point disappear.

### Q12 — Your monitoring shows commit latency p99 spiking every time a particular node in the Raft cluster is under CPU load, even though it's not the leader. Why would a follower's load affect commit latency?
**Testing:** whether you understand that commit requires a majority, so slow followers matter.
**Answer:** Commit requires acknowledgment from a majority, not all nodes, but if that slow follower is one of the nodes the leader is waiting on to reach the majority threshold for a given write (which follower ack completes the majority is effectively random/round-robin depending on network timing), its slowness directly delays that write's commit. With N=5, you need 3 acks; if 2 followers are consistently the fastest and the leader is unlucky enough that a slow follower is needed to complete the third ack for a batch of writes, that shows up as intermittent p99 spikes correlated with the slow node's load.
**Follow-up trap:** *"How would you make this less sensitive to one slow follower?"* — this is inherent to majority-quorum designs to some degree, but you can reduce impact by keeping the cluster geographically/network-topology-uniform so no node is a consistent straggler, monitoring per-node replication lag as a leading indicator, and in some Raft implementations, using "pre-vote" and priority-based leader placement to avoid electing or routing load toward historically slow nodes.

---

## Red flags that fail you

- Saying "Raft prevents split-brain" without qualifying that this holds for the consensus log itself, not for arbitrary side effects the leader triggers outside it.
- Claiming Raft is "more powerful" than Paxos rather than more understandable, they are equivalent in what they guarantee.
- Treating a Lamport timestamp comparison as a causality claim.
- Not knowing vector clocks are O(n) in the number of participants, or why that's a real operational cost.
- Recommending a distributed lock without mentioning fencing tokens when asked about stale-holder safety.
- Confusing "replicated" with "committed" in a Raft log.
- Not being able to state quorum size arithmetic (`⌊N/2⌋+1`) cold.
- Assuming NTP-synced wall clocks alone are sufficient for lease correctness without addressing pause/skew scenarios.

---

## Cheat card

```
RAFT
  quorum = floor(N/2)+1. N=3->2 (tolerates 1 fail). N=5->3 (tolerates 2). N=7->4 (tolerates 3).
  4 nodes buys nothing over 3 -- always use odd N in production
  election timeout: randomized 150-300ms (reference impl); heartbeat ~50ms (~10x margin)
  production rule: election timeout >= 10x measured inter-node RTT
  TERM = logical clock over leadership epochs; stale-term messages always rejected
  committed = replicated to MAJORITY (safe to apply/ack); replicated != committed
  election restriction: candidate must have log >= as up-to-date as voter's log
  membership changes: joint consensus (old+new majority both required) or one-at-a-time add/remove

RAFT vs PAXOS: equivalent POWER (both need live majority). Raft won on COMPREHENSIBILITY
  (2014 user study, 43 students, most scored better on Raft). Decomposes into election/
  replication/safety as separate concerns.

SPLIT-BRAIN: prevented WITHIN the consensus log by quorum overlap.
  NOT prevented for side effects issued outside the log by a stale, not-yet-stepped-down leader.

FENCING TOKEN: monotonically increasing number per lease acquisition.
  Checked at the STORAGE/WRITE layer, not the lock service, or it's decorative.
  Redlock (Kleppmann 2016 critique): no fencing token produced -- mutual exclusion != safety here.

LOGICAL CLOCKS
  Lamport: 1 int, O(1) space, TOTAL order, NO causality guarantee (C(a)<C(b) proves nothing)
  Vector: 1 int PER NODE, O(n) space, exact causality + concurrency detection
  HLC (Kulkarni/Demirbas 2014): (physical_time, logical_counter), O(1) space,
       causal order + stays close to wall clock. Used by CockroachDB (txn ordering,
       default 500ms max-offset uncertainty window) and MongoDB (ClusterTime).

LEASES: use MONOTONIC clock for elapsed-time checks, not wall clock (NTP step jumps break it).
  A paused process (GC/VM freeze) doesn't know time passed -- fencing token is the only real fix.

PRODUCTION: etcd/Consul (Raft, 3-5 node quorums), CockroachDB (Raft per range + HLC),
  Kafka KRaft (Raft, replaced ZooKeeper controller), Spanner/Chubby (Paxos, pre-2014 legacy)
```

## Sources

- [In Search of an Understandable Consensus Algorithm (Extended Version) — Ongaro & Ousterhout, USENIX ATC 2014](https://raft.github.io/raft.pdf) — accessed 2026-08-01
- [Raft Consensus Algorithm — raft.github.io](https://raft.github.io/) — accessed 2026-08-01
- [CONSENSUS: BRIDGING THEORY AND PRACTICE — Ongaro PhD Dissertation, Stanford](https://web.stanford.edu/~ouster/cgi-bin/papers/OngaroPhD.pdf) — accessed 2026-08-01
- [etcd FAQ — etcd.io](https://etcd.io/docs/v3.7/faq/) — accessed 2026-08-01
- [Understanding etcd Quorum — Why 3 Nodes, Never 2 or 4](https://labitlearnit.com/2026/04/05/understanding-etcd-quorum-why-3-nodes-never-2-or-4/) — accessed 2026-08-01
- [How to do distributed locking — Martin Kleppmann's blog](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — accessed 2026-08-01
- [Logical Physical Clocks and Consistent Snapshots in Globally Distributed Databases — Kulkarni, Demirbas, Madappa, Avva, Leone (2014)](https://cse.buffalo.edu/tech-reports/2014-04.pdf) — accessed 2026-08-01
- [Hybrid Logical Clock in Distributed Systems — singhajit.com](https://singhajit.com/distributed-systems/hybrid-clock/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
