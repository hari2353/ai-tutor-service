# Network Failure Modes: Partitions, Timeouts vs Resets, Retries, Split Brain, MTU Blackholes

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-tcp-deep, T29-dns-lb, T29-net-debugging · **Updated:** 2026-07-26
> **Module id:** `T29-net-failures` · **Tags:** resilience, critical

## The 30-second version

Networks don't fail cleanly; they fail in ways that are ambiguous by construction, and the entire skill is reading the ambiguity correctly. A timeout means silence and tells you nothing about where the failure is. An RST means something actively answered and killed the connection, which does tell you something. A silent drop with no error at all is usually a security-group/NACL misconfiguration or asymmetric routing. TCP retries at its own layer with exponential backoff before the application ever sees a failure, which means "the client timed out" and "the write never happened" are independent facts you cannot infer from each other — a server can complete a write and have its ACK lost, leaving the client believing it failed. Split brain happens when a partition lets two sides both believe they're the leader, and the only real fix is fencing — physically or logically guaranteeing the old leader can't act, not just electing a new one and hoping. MTU blackholes are the classic "small requests work, big ones hang forever" bug, caused by a firewall eating the ICMP message that would have told the sender to shrink its packets.

## Why this gets asked

Because "the network is down" is almost never true — what's actually true is one specific, diagnosable failure mode, and the interviewer wants to know if you reach for the right one instead of restarting things and hoping. They've been paged for a split-brain data-corruption incident, a connection pool that silently filled up over hours, or a mysterious hang that turned out to be an MTU blackhole three hops into a VPN — and they want to hear you reconstruct the diagnostic path, not just recite the vocabulary.

---

## Lineage: past → present → future

**What came before.** Peter Deutsch (and later James Gosling) at Sun Microsystems articulated the "Fallacies of Distributed Computing" starting in 1994 — "the network is reliable," "latency is zero," "bandwidth is infinite," "the network is secure," "topology doesn't change," among others — naming assumptions that early distributed systems baked in by default because they were built by people who'd mostly reasoned about single machines or trusted local networks. The pain that list was responding to: systems designed as if a remote call behaved like a local one failed in production in ways their designers hadn't considered, because a local call can't partially fail or hang indefinitely, and a remote one can do both, routinely.

**Where it stands now.** Partition tolerance is no longer an edge case to design around eventually; CAP-aware design — accepting that partitions will happen and deciding in advance what to sacrifice, consistency or availability, when they do — is baseline practice for anything distributed. The unresolved, structurally hard problem: a timeout is the only real failure detector available, and a timeout cannot distinguish a genuinely dead peer from one that's merely slow. This isn't a tooling gap that better monitoring eventually closes — it's a fundamental property of asynchronous networks (see the FLP impossibility result, 1985, for why consensus can't be solved with a guaranteed bound in the general asynchronous case). The live disagreement in practice is over how aggressively to time out: a short timeout gets faster failure detection at the cost of false positives against a peer that's merely slow; a long timeout avoids false positives at the cost of slower failover.

**Where it's heading.** Failure detectors are getting more adaptive — phi-accrual failure detection (used in Cassandra and Akka) replaces a fixed timeout threshold with a continuously updated suspicion level derived from observed heartbeat variance, which is real and deployed today, not speculative. The more speculative direction is a broader shift toward durable execution (Temporal, Restate, and similar durable-workflow engines) that reframes the problem entirely: instead of detecting failure faster, make partial failure safe to resume from by persisting execution state, so a retry continues a workflow rather than restarting it blind or corrupting it. Adoption is real but early enough that calling it industry consensus would overstate where things actually stand in mid-2026.

---

## Mental model

The three-way ambiguity below is the root of every retry-safety problem in this module: the client sees exactly one observable event — a timeout — and that single event is consistent with three completely different things having happened server-side.

```
                       CLIENT                              SERVER
                         |                                    |
                         |------ request -------X             |   (1) REQUEST LOST
                         |        (never arrives)              |       server runs nothing at all
                         |                                    |
                         |------ request ------------------->|   (2) RESPONSE LOST
                         |                              [runs, commits the write]
                         |<----- response -------X            |       write happened, ack never arrives
                         |                                    |
                         |------ request ------------------->|   (3) PEER SLOW
                         |                              [running... still running...]
                         |         (client's timeout fires here, before any response)
                         |<----- response --------------------|   arrives eventually, too late to matter
                         |                                    |

        client's observable event in ALL THREE cases: TIMEOUT, nothing else.
        the three scenarios are indistinguishable from the client's side --
        that indistinguishability is the root of every retry-safety problem.
```

The consequence: "retry on timeout" is only safe if the retried operation is idempotent, because a retry after case (2) or (3) risks double-applying a write that may have already landed. Nothing observable to the client tells it which case it's in — it has to assume the worst (case 2/3) and defend against it structurally, not detect its way out of the ambiguity.

---

## How it actually works

### What actually causes partitions in practice

Partitions are rarely "the network cable got cut." In practice: a switch or top-of-rack failure isolates a rack; a BGP misconfiguration (a bad route announcement, a route leak, a session flap) makes one region unreachable from another while both are individually healthy; a security group or NACL rule change — often an unintentional one during a routine deploy — blocks traffic between two previously-connected services; a cross-AZ or cross-region link degrades or fails, which is common enough that every multi-AZ architecture has to assume it will happen; or a NAT gateway/load balancer runs out of capacity (connection tracking table full) and starts silently dropping new connections while existing ones continue to work, which looks like a partial partition rather than a clean one.

The practically important point: **most real partitions are partial and asymmetric.** A can reach B but B can't reach A (asymmetric routing, a one-directional firewall rule), or 90% of traffic gets through and 10% silently doesn't (a flaky link, a partially-failed NIC). Design and testing that only considers a clean, total, symmetric partition misses the failure modes that actually happen.

---

## The diagnostic triad: timeout vs RST vs silent drop

This is the single most load-bearing distinction in the whole module, because each one localizes the failure differently.

**Timeout** — no response at all within your wait window. This means packets are going nowhere and getting no answer, which is consistent with: a firewall silently dropping the packet (`DROP`, not `REJECT`), the destination genuinely being unreachable (host down, no route), or the destination being alive but so overloaded it never processes the SYN. **A timeout gives you zero information about which of these it is** — that's the defining property of silence as a signal. You have to actively probe (traceroute/mtr, checking from a different vantage point) to localize it.

**RST (reset)** — something on the path actively rejected or killed the connection and told you so. Two flavors: rejected at connection time (no listener on that port — the OS itself sends the RST — or a firewall explicitly configured to `REJECT`), or reset mid-connection (the server process crashed, a stateful firewall/load balancer decided the connection was invalid or idle and killed it, or a backlog queue overflow triggered a reset instead of a silent drop on some stacks). An RST is informative: it tells you a device on the path is alive, reachable, and made an active decision.

**Silent drop** — often a security group or NACL misconfiguration (traffic allowed one direction but not the return path, which is an easy mistake with stateless NACLs specifically, since unlike security groups they don't automatically allow return traffic), or an asymmetric routing issue where the request reaches its destination but the reply takes a different path that's blocked. From the client's perspective this looks identical to a timeout — the difference is diagnostic, not observable from the client alone: a timeout with a security-group cause is a config bug you can find and fix in the console; a timeout from genuine unreachability requires a routing/infrastructure investigation.

---

## Retries and idempotency at the network layer, specifically

This is distinct from application-level retry logic (covered in the resilience catalogue) — TCP has its own retry mechanism operating beneath anything your application code decides to do.

**TCP's own retransmission.** When a segment isn't ACKed within the current retransmission timeout (RTO), TCP retransmits it, then doubles the RTO (exponential backoff) for the next attempt. The initial RTO is computed from measured RTT (commonly starting around 1 second if there's no prior RTT sample, then adapting), and the OS gives up after a bounded number of retries — on Linux, controlled by `tcp_retries2` (default commonly 15, though the actual elapsed time depends on the backoff curve and is roughly 15-30 minutes for an established connection with no response at all before the application sees `ETIMEDOUT`; the SYN-only case, controlled by `tcp_syn_retries`, gives up far sooner, typically under 2 minutes). The application only learns about failure after the OS exhausts its own retry budget — which is often far longer than any sane application-level timeout, meaning application timeouts almost always fire first and the OS-level retry becomes moot for anything user-facing.

**Why you need both layers to be idempotency-aware, precisely.** A client can send a write, the server can fully complete it (commit the row, send the customer an email, whatever the side effect is), and then the ACK carrying that success back to the client can be lost — the client sees a timeout and has no way to distinguish "the request never arrived" from "the request completed but the confirmation didn't make it back." If the client retries (at the application layer) assuming the first attempt failed, and the operation isn't idempotent, you get a duplicate charge, a duplicate email, a duplicate row — a real and common production bug class. The network layer's retry (TCP retransmitting an unacked *segment*) is safe because TCP guarantees a byte stream is either delivered exactly once or the connection fails entirely; the danger is entirely at the layer above, where "did my request logically complete" and "did I get a response" are not the same fact once a connection outcome is ambiguous.

---

## Split brain

**What it is.** During a partition, two sides of a cluster can each conclude they're isolated from the other and — depending on the consensus protocol's configuration — both proceed to act as leader/primary. Both sides accept writes, both believe they're authoritative, and once the partition heals you have two divergent histories that need reconciling, which is sometimes impossible without data loss.

**Why it's dangerous specifically for leader election.** A correctly implemented consensus protocol (Raft, Paxos, ZAB) with proper quorum requirements shouldn't allow this — a minority partition can't win an election because it can't reach quorum. Split brain in practice happens when quorum requirements are misconfigured (an even number of voting members letting a 50/50 split occur), a "sticky" old leader doesn't step down promptly because it hasn't yet detected the partition (it keeps believing it holds a lease that's actually expired from the other side's perspective), or an operator manually intervenes during an incident and forces a failover without confirming the old primary is actually down (as opposed to just unreachable from the operator's vantage point, which are not the same thing).

**Fencing / STONITH.** The actual fix isn't "elect a new leader and move on" — it's guaranteeing the old leader physically or logically cannot act before the new one starts. STONITH ("shoot the other node in the head") does this at the hardware/infrastructure level: forcibly power off or reboot the suspected node via an out-of-band channel (IPMI, a cloud provider's terminate-instance API) that doesn't depend on the node's own cooperation — a partitioned-but-alive node can't defend itself against being powered off, which is exactly why this is more reliable than asking it nicely to step down. Softer fencing mechanisms include storage-level fencing (revoke the old leader's access to shared disk) and lease/token-based fencing (a monotonically increasing fencing token that downstream storage checks and rejects writes from an old, superseded token — Chubby/ZooKeeper-style leases work this way). The principle in all cases: don't just elect a new leader, actively prevent the old one from acting.

---

## MTU blackholes

**The mechanism, precisely.** A sender sets the DF (Don't Fragment) bit on outbound packets (standard for TCP) and relies on Path MTU Discovery: if a router along the path can't forward a packet because it exceeds that hop's MTU, it's supposed to send back an ICMP "Fragmentation Needed" message (Type 3, Code 4) so the sender learns the smaller MTU and shrinks its segment size. The blackhole occurs when a firewall or security device along the path drops that ICMP message (a common and historically well-intentioned but harmful firewall default — blocking "all ICMP" as a blanket security measure) — the sender never learns to shrink its packets, keeps sending the same oversized ones, and they're silently dropped by whatever device couldn't forward them, forever, with no error surfaced anywhere.

**The classic symptom, exactly as it presents:** the TCP handshake completes fine (SYN/SYN-ACK/ACK are small, well under any real-world MTU), small HTTP requests work, but a TLS handshake with a large certificate chain, or any request/response with a large payload, hangs indefinitely — because those are the first packets large enough to hit the MTU ceiling on some hop, and the retransmissions of that same oversized packet just keep vanishing.

**Diagnosis.** Confirm the size threshold by sending progressively larger ICMP echo requests with DF set (`ping -M do -s <size> host` on Linux) and finding where it starts failing; capture with `tcpdump` to see the same large segment retransmitted repeatedly with no ICMP response ever arriving. **Fix:** ideally, allow ICMP Type 3 Code 4 through every firewall on the path — the "correct" fix but one you frequently don't control (a middlebox or a customer's firewall you don't own). The practical, more commonly deployed fix is **MSS clamping**: a router or firewall you *do* control rewrites the TCP MSS option in the SYN/SYN-ACK to a smaller value, forcing both ends to negotiate smaller segments from the start rather than relying on ICMP feedback that might never arrive. This is standard practice on VPN gateways and tunnel endpoints specifically because tunneling overhead (IPsec, GRE) shrinks the effective MTU below the outer interface's MTU, making this exact blackhole extremely common on VPN paths.

---

## Connection pool exhaustion

**Symptom:** requests hang waiting to acquire a connection from the pool (commonly surfacing as an explicit "timeout waiting for connection from pool" error, or just generalized latency creeping up as more requests queue behind a full pool), even though the downstream database or service itself isn't necessarily under heavy load.

**Two distinct causes that look identical from the outside but need different fixes.** First, a **leaked connection**: code acquires a connection and, due to a missing `finally`/`try-with-resources`/context-manager, fails to return it to the pool on an exception path — the pool's available count silently shrinks over time (often over hours, since the leak rate depends on how often the buggy path executes) until nothing's left. The signature here is a pool that's exhausted while actual load on the downstream is normal or low — the connections are lost, not busy. Second, **genuine capacity below load**: the pool size was set for an estimated traffic level and real traffic (or real per-query latency, e.g. from a missing index) now exceeds what the pool can serve concurrently — here the downstream is legitimately busy and the fix is capacity (bigger pool, faster queries, more instances), not a code fix.

**Distinguishing them:** check whether connections are actually busy executing queries (visible in the database's own connection/process list — e.g. Postgres's `pg_stat_activity` showing `active` vs `idle` vs `idle in transaction`) or just held and idle. A pool full of connections sitting `idle in transaction` for minutes is a leak; a pool full of connections all showing genuinely long-running active queries is a capacity or query-performance problem.

---

## DNS failure modes

**Resolver timeout/unreachable** — the configured recursive resolver itself isn't answering (network issue to the resolver, or the resolver service is down); the client's DNS library has its own timeout and retry behavior, and if misconfigured (e.g., only one resolver configured, no fallback) this becomes a hard dependency failure for literally every outbound call the service makes, since almost nothing works without name resolution first.

**Stale cached record after a failover** — covered in the DNS/LB module: a record changed, but a cache between the client and the authoritative server (OS resolver, app-runtime cache, corporate resolver) kept serving the old answer past its TTL, because TTL is advisory, not enforced end-to-end.

**NXDOMAIN vs SERVFAIL — different implications.** NXDOMAIN means the authoritative server responded and the name genuinely doesn't exist in that zone — a real "this record was never created, or was deleted, or you have a typo" signal. SERVFAIL means the resolver couldn't get a valid answer at all — the authoritative server is unreachable, timed out, or returned something the resolver couldn't validate (a common cause post-DNSSEC: a validation failure surfaces as SERVFAIL, not as a clear "signature invalid" message) — this points at an infrastructure/reachability problem with the DNS chain itself, not a missing record.

**Split-horizon DNS misconfiguration** — a zone intentionally returns different answers depending on whether the query originates internally or externally (e.g., internal clients get a private IP for a service, external clients get a public one, for the same name). Misconfigured, this causes exactly the class of "works from my machine, not from the client's" bugs that waste hours — an internal engineer testing from inside the VPN gets the internal view and can't reproduce what an external client (or a service running in a different network context, like a CI runner or a different cloud account) actually sees.

---

## Build it from scratch

The mental model above claims a client cannot distinguish "the write never happened" from "the write happened but the ack was slow/lost," and that this is exactly why naive retries are unsafe. Don't take that on faith — build the smallest possible server/client pair that proves it, then add the one fix (an idempotency key) that makes retrying safe regardless of which case actually occurred.

**Runnable, stdlib only (tested on CPython 3.11: `socket`, `threading`, `json`, `time`).**

```python
import json
import socket
import threading
import time

HOST, PORT = "127.0.0.1", 8765

committed = {}                 # server-side "database": key -> result
committed_lock = threading.Lock()

def handle_client(conn):
    with conn:
        data = conn.recv(4096)
        if not data:
            return
        req = json.loads(data.decode())
        key, amount = req["idempotency_key"], req["amount"]
        simulate_slow = req.get("simulate_slow", False)

        with committed_lock:
            if key in committed:
                # Same key seen before: replay the prior result, do NOT
                # apply the write again.
                result = committed[key]
                conn.sendall(json.dumps(
                    {"status": "ok", "duplicate": True, "result": result}).encode())
                return
            # The write commits HERE, unconditionally -- before we decide
            # how long the response takes. Commit and reply are two
            # separate network events; only one is guaranteed to arrive
            # inside the client's timeout window.
            result = {"charged": amount}
            committed[key] = result

        if simulate_slow:
            time.sleep(2.0)     # longer than the client's 0.5s timeout below
        try:
            conn.sendall(json.dumps(
                {"status": "ok", "duplicate": False, "result": result}).encode())
        except OSError:
            pass                # client already gave up and closed its socket

def serve():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT)); srv.listen()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

def send_charge(idempotency_key, amount, simulate_slow=False, timeout=0.5):
    """Returns ('ok', body) or ('timeout', None). A timeout here is the
    ambiguous case: the client cannot tell whether the server never ran,
    or ran and committed but the response didn't make it back in time."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        s.sendall(json.dumps({"idempotency_key": idempotency_key,
                               "amount": amount, "simulate_slow": simulate_slow}).encode())
        return "ok", json.loads(s.recv(4096).decode())
    except socket.timeout:
        return "timeout", None
    finally:
        s.close()

def naive_retry():
    # BUG: retry uses a FRESH key. Attempt 1 times out client-side but the
    # server already committed it. The retry, with a new key, looks like a
    # brand-new charge to the server -> double commit.
    status, body = send_charge("naive-first", 100, simulate_slow=True)
    print("  attempt 1:", status, body)
    if status == "timeout":
        status2, body2 = send_charge("naive-retry", 100)   # different key
        print("  naive retry (new key):", status2, body2)

def safe_retry():
    # FIX: retry reuses the SAME key. The server recognizes it already
    # committed that key and replays the cached result -- safe regardless
    # of how slow or lost the first response was.
    key = "order-42-charge"
    status, body = send_charge(key, 100, simulate_slow=True)
    print("  attempt 1:", status, body)
    if status == "timeout":
        status2, body2 = send_charge(key, 100)              # same key
        print("  safe retry (same key):", status2, body2)

if __name__ == "__main__":
    threading.Thread(target=serve, daemon=True).start()
    time.sleep(0.2)
    print("--- naive retry: fresh idempotency key per attempt ---")
    naive_retry()
    time.sleep(2.2)   # let the slow first response land in the background
    print("--- safe retry: same idempotency key reused ---")
    safe_retry()
    time.sleep(2.2)
    with committed_lock:
        print("distinct writes committed server-side:", len(committed))
        for k, v in committed.items():
            print(" ", k, "->", v)
```

Actual output from a real run:

```
--- naive retry: fresh idempotency key per attempt ---
  attempt 1: timeout None
  naive retry (new key): ok {'status': 'ok', 'duplicate': False, 'result': {'charged': 100}}
--- safe retry: same idempotency key reused ---
  attempt 1: timeout None
  safe retry (same key): ok {'status': 'ok', 'duplicate': True, 'result': {'charged': 100}}
distinct writes committed server-side: 3
  naive-first -> {'charged': 100}
  naive-retry -> {'charged': 100}
  order-42-charge -> {'charged': 100}
```

Read the output, not just the code: in the naive case, the client observes exactly `timeout` then `ok` — from the client's side that looks like "it failed, then it worked" — but the server actually ran the write **twice** (`naive-first` and `naive-retry` are two separate committed entries for what was meant to be one logical charge). In the safe case, the client sees the identical observable sequence (`timeout` then `ok`), but only one write (`order-42-charge`) exists server-side, because the server recognized the retried key and replayed the cached result instead of re-executing. The client-observed behavior is indistinguishable between the two runs; only the idempotency key changes whether the ambiguity is harmless or a duplicate charge.

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Request hangs for the full client timeout, no error until then | Firewall silently dropping (not rejecting) or genuine unreachability | `mtr`/traceroute to localize; check security groups/NACLs for asymmetric rules before assuming "network is just down" |
| Two nodes both accepting writes after a network blip | Split brain — quorum misconfigured, or old leader hasn't detected the partition and stepped down | Odd-numbered quorum sizing, fencing (STONITH or lease/token-based) so the old leader is guaranteed unable to act, not just "probably" demoted |
| TLS handshake or large payload transfer hangs forever, small requests fine | MTU blackhole — firewall drops both oversized DF packets and the ICMP message that would fix it | MSS clamping at your gateway/tunnel endpoint; separately, push for ICMP Type 3 Code 4 to be allowed end-to-end where you control the path |
| Requests hang waiting for a DB connection, DB itself is idle | Connection leak — missing `finally`/context manager on an exception path | Audit for try/finally or use context managers universally; check `idle in transaction` vs `active` in the DB's own connection view |
| Requests hang waiting for a DB connection, DB is genuinely busy | Pool sized below real concurrent load, or slow queries holding connections longer than expected | Right-size the pool via Little's Law (`concurrency = throughput × latency`), fix the slow query, don't just enlarge the pool blindly |
| Client gets a duplicate charge/email after "the request timed out" | Server completed the write but the ACK/response was lost; client retried a non-idempotent operation | Idempotency keys on every mutating endpoint, checked atomically before executing |
| Service works for internal engineers testing from the VPN, fails for external users or CI | Split-horizon DNS returning different answers to internal vs external queries | Explicitly test from the actual network context users/CI are in, not just from inside the VPN; audit split-horizon zone config for consistency |
| DNS lookups intermittently fail across the fleet, seemingly at random | Single configured resolver with no fallback, resolver itself flaky or rate-limiting | Configure multiple resolvers with fallback; monitor resolver latency/error rate as its own SLO-relevant dependency |

---

## Tradeoffs & when NOT to use it

- **Don't treat every timeout as "the network is down."** It's the least informative signal available — spend the two minutes on `mtr`/`nc -zv` to at least narrow it to "reachable but silent" versus "not reachable at all" before escalating.
- **Don't rely on "elect a new leader" alone as your split-brain defense.** Without fencing, you've reduced the probability of split brain, not eliminated it — the old leader can still act if it hasn't detected the partition, and "probably fine" is not the same guarantee as "physically cannot act."
- **Don't blanket-block ICMP at the firewall as a security default.** This is the single most common self-inflicted cause of MTU blackholes; ICMP Type 3 Code 4 specifically needs to pass for Path MTU Discovery to function, and blocking it trades a theoretical security benefit for a very real, very confusing production failure mode.
- **Don't assume application-level retry logic alone makes an operation safe.** It only does if the operation is actually idempotent — retry without idempotency is how a network-layer ambiguity (did the write happen or not) becomes a business-layer bug (duplicate charge).
- **Don't scale a connection pool up as the default fix for exhaustion** without first checking whether it's a leak — a bigger pool just delays the same leak from exhausting it again, and hides the actual bug for longer.

---

## Interview questions

### Q1 — A request times out. What does that tell you, and what doesn't it tell you?
**Testing:** whether timeout is understood as an uninformative signal, not treated as equivalent to "server is down."
**Answer:** It tells you no response arrived within your wait window — nothing more. It does not tell you whether the packet reached the destination, whether a firewall dropped it, whether the destination is overloaded, or whether the response was sent but lost on the way back. You have to actively probe (traceroute/mtr from the actual failing vantage point, checking firewall rules) to localize it.
**Follow-up trap:** *"The same request succeeds from your laptop but times out from a CI runner in a different VPC. What's your hypothesis?"* — asymmetric security group/NACL rules or routing specific to that VPC/network path, not "the server is flaky" — the fact that it's reproducible from one vantage point and not another localizes it to something path- or origin-specific, which a genuinely down server wouldn't produce.

### Q2 — Contrast RST and silent drop as failure signatures.
**Answer:** An RST means a device on the path is alive, reachable, and actively decided to reject or kill the connection — informative, and it happens fast. A silent drop produces the exact same symptom to the client as a genuine unreachability problem (no response, eventual timeout), and the two are indistinguishable from the client side alone — you need to check the actual path (security groups, NACLs, routing) to tell them apart.
**Follow-up trap:** *"Why would a stateless NACL cause a silent drop that a security group wouldn't?"* — NACLs are stateless, so an inbound rule allowing traffic in doesn't automatically allow the return traffic out — you need an explicit outbound rule too, and a common misconfiguration bug is allowing the request direction while forgetting the reply direction, which manifests as a silent drop on the return path specifically.

### Q3 — Explain why a client can receive a timeout while the server actually completed the write, and why this matters for retry safety.
**Answer:** The write and the acknowledgment are two separate network events — the server can commit the write and send a success response, and that response (or the ACK covering it) can be lost on the way back, or arrive after the client has already given up waiting. The client has no way to distinguish "my request never arrived" from "it arrived, completed, and the confirmation got lost." If the client blindly retries a non-idempotent operation on that assumption, it duplicates the effect.
**Follow-up trap:** *"Doesn't TCP guarantee delivery, so how can this happen?"* — TCP guarantees the byte stream is delivered reliably *while the connection is up and functioning*; the ambiguity here is at the layer above — the application-level "did my logical operation succeed" question — which TCP's guarantee doesn't answer once the connection itself times out or is torn down before the response arrives. TCP's reliability is about bytes on an established connection, not about giving the application a definitive success/failure verdict when the connection itself fails.

### Q4 — Design a fencing mechanism for a leader-election-based system and explain why "elect a new leader" alone is insufficient.
**Answer:** Electing a new leader without fencing leaves open the possibility that the old leader hasn't yet detected the partition (its lease looks valid from its own perspective) and continues accepting writes — you now have two leaders. Fencing guarantees the old one physically or logically can't act: STONITH forcibly powers off the suspected node via an out-of-band channel that doesn't depend on its cooperation, or a monotonically increasing fencing token is attached to every write and the downstream storage layer rejects any write carrying a token older than the latest one it's seen (a Chubby/ZooKeeper-lease-style approach) — regardless of which node believes it's the leader.
**Follow-up trap:** *"STONITH powers off a node that turns out to have actually been fine, just slow to respond to a health check. Was that the right call?"* — yes, in the sense that the alternative (both nodes possibly writing) is worse than an unnecessary, recoverable reboot of a healthy node; fencing decisions should be biased toward safety over avoiding a false-positive fence, and the node coming back up cleanly afterward is the entire point of choosing STONITH over something less reversible.

### Q5 — A TLS handshake completes but the connection then hangs indefinitely on larger payloads. Diagnose it.
**Answer:** Classic MTU blackhole signature — small packets (the handshake) succeed, larger ones (post-handshake payload, or a big certificate chain during the handshake itself) are silently dropped by a hop that can't forward an oversized DF-set packet, while the ICMP "fragmentation needed" message that should tell the sender to shrink packets is also being dropped by a firewall along the path, so the sender never learns and keeps retransmitting the same oversized segment forever.
**Follow-up trap:** *"You don't control the firewall dropping the ICMP message. What do you do?"* — MSS clamping at whatever gateway/tunnel endpoint you do control, forcing both ends to negotiate a smaller segment size from the start rather than depending on ICMP feedback from a path you don't own; this is why MSS clamping is standard practice on VPN/tunnel endpoints specifically.

### Q6 — Why are VPN and tunnel endpoints especially prone to MTU blackholes?
**Answer:** Tunneling protocols (IPsec, GRE, etc.) add their own header overhead on top of the payload, which shrinks the effective MTU available for the original packet below the outer interface's advertised MTU. A sender using the outer interface's MTU as its assumption sends packets that are actually too large once tunnel overhead is added, and if the network along the path (or a security device) also blocks the ICMP feedback that would correct this, the blackhole is essentially guaranteed rather than occasional.
**Follow-up trap:** *"Is raising the outer interface's MTU (jumbo frames) a fix?"* — only if every hop on the path supports the larger frame size consistently, which is rarely true end-to-end across the internet; MSS clamping at the tunnel endpoint is the more robust fix because it doesn't depend on every intermediate hop cooperating.

### Q7 — Connection pool exhaustion: how do you tell a leak from genuine under-capacity, and why does it matter which one it is?
**Answer:** Check the downstream's own connection/session view (e.g., Postgres `pg_stat_activity`) for whether the held connections are `active` (genuinely executing queries — capacity problem) or `idle`/`idle in transaction` for an extended period (leaked — code bug). It matters because the fixes are different and one of them is a trap: enlarging the pool "fixes" a leak's symptom temporarily (buys more headroom before it fills again) without touching the actual bug, so the leak recurs at a larger scale and takes longer to notice.
**Follow-up trap:** *"You've confirmed it's a leak. Where do you look in the code first?"* — every code path that acquires a connection outside a guaranteed-cleanup construct (missing `finally`/`try-with-resources`/context manager), especially exception paths that skip the normal cleanup — the leak rate is usually proportional to how often that specific error path executes, which is why it often takes hours to become visible rather than failing immediately.

### Q8 — NXDOMAIN vs SERVFAIL — what does each imply about where to look next?
**Answer:** NXDOMAIN means an authoritative server answered and the name genuinely doesn't exist in that zone — check for a typo, a record that was never created, or one that was deleted; the DNS infrastructure itself is working correctly. SERVFAIL means the resolver couldn't get a valid answer at all — the authoritative server is unreachable/timing out, or (increasingly common) a DNSSEC validation failure — which points at an infrastructure or configuration problem in the resolution chain itself, not a missing record.
**Follow-up trap:** *"You just created the record and you're getting NXDOMAIN. Is that necessarily a real problem?"* — not necessarily; negative caching means a prior NXDOMAIN answer for that name can still be cached (per the zone's SOA negative-cache TTL) even after the record now exists, so the correct next step is checking whether you're hitting a cached negative answer versus the authoritative server genuinely not having the record yet — not assuming the zone update failed.

### Q9 — Explain the interaction between TCP's own retransmission timers and application-level retry logic, and why an application needs both to be idempotency-aware.
**Answer:** TCP retransmits an unacked segment with its own exponential backoff, giving up only after a bounded number of attempts (governed by sysctls like `tcp_retries2`), which on an established connection can take many minutes — far longer than most application-level timeouts, so in practice the application usually times out and takes its own action long before TCP would have given up on its own. Both layers matter for idempotency because either one's failure-and-retry can result in the operation appearing to fail to the caller while having actually completed on the server, and a naive application-level retry on top of that ambiguity is what turns a network hiccup into a duplicated business-level effect.
**Follow-up trap:** *"If TCP already retransmits reliably, why isn't that enough — why do you need application-level idempotency too?"* — TCP's retransmission operates *within* one connection's lifetime and guarantees byte-level delivery on that connection; it says nothing about what happens when the *connection itself* fails and the application decides to open a *new* connection and resend the logical request — at that point you're squarely in application-level retry territory, and TCP's guarantee doesn't extend across that boundary.

### Q10 — A cluster has an even number of voting nodes and just experienced split brain during a network partition. What's the design flaw?
**Answer:** An even-numbered quorum makes a 50/50 partition possible, where neither side can be mathematically certain it holds the majority, and depending on the consensus implementation's tie-breaking behavior (or lack thereof), both sides can conclude they're authoritative. The fix is an odd number of voting members (or a designated tie-breaker/witness node) so a majority is always uniquely determined on one side of any partition.
**Follow-up trap:** *"You've moved to an odd number of voters. Are you now safe from split brain entirely?"* — safer against the quorum-math failure mode specifically, but not safe from every split-brain cause — a leader that hasn't yet detected the partition and hasn't stepped down, or an operator manually forcing a failover without confirming the old primary is truly down, can still produce two active writers even with correct quorum math; fencing is still the actual guarantee, quorum sizing just reduces one specific failure path.

### Q11 — Your service works fine when engineers test from the VPN but fails for real external users. What's your first hypothesis and how do you confirm it?
**Answer:** Split-horizon DNS returning a different (often private/internal) answer to queries originating inside the VPN versus what external users' resolvers get — the engineer's "it works for me" is testing a different resolution path entirely. Confirm by running `dig` from outside the VPN (or from the actual external network context, like a CI runner or a cloud shell outside your VPC) and comparing the resolved IP against what's resolved from inside.
**Follow-up trap:** *"The IPs match from both vantage points. What else could explain internal-works, external-fails?"* — a security group or firewall rule scoped to the VPN's IP range specifically, or a load balancer configured to only accept traffic from internal CIDR blocks — check the actual reachability path (not just DNS) from each vantage point once DNS is ruled out.

### Q12 — Rank timeout, RST, and silent drop by how much diagnostic information each gives you, and justify the order.
**Answer:** RST gives the most information — it confirms a live, reachable device on the path made an active decision, letting you immediately check listener/process state or explicit firewall reject rules. Silent drop and timeout are functionally identical from the client's perspective and give the least information — both require active probing (mtr, checking security groups/NACLs, testing from multiple vantage points) to even begin localizing, because the client-observed symptom (nothing happened) is the same whether the cause is a misconfigured rule, genuine unreachability, or an overloaded destination that never got to the SYN.
**Follow-up trap:** *"So should you configure firewalls to always REJECT instead of DROP, since REJECT is more informative?"* — there's a real security tradeoff here: REJECT confirms to a potential attacker that a host exists and a specific rule is blocking them (useful for their reconnaissance), while DROP gives no information back at all, which is why security-sensitive perimeters often deliberately choose DROP despite it being harder to debug — the informativeness that helps you during an incident is the same informativeness that helps an attacker during reconnaissance, and reasonable teams land on different sides of this depending on threat model.

---

## Red flags that fail you

- Treating every timeout as equivalent to "the server/network is down."
- Not knowing that a client-observed timeout gives no information about whether a write on the server side actually completed.
- Proposing "just elect a new leader" as a complete split-brain fix with no fencing mechanism.
- Not recognizing "small packets work, big ones hang" as the MTU blackhole signature.
- Recommending a bigger connection pool as the first fix for exhaustion without checking for a leak.
- Confusing NXDOMAIN (record doesn't exist) with SERVFAIL (resolution chain broken).

---

## Cheat card

```
CAUSES OF REAL PARTITIONS
  switch/ToR failure · BGP misconfig/route leak · security-group/NACL change
  cross-AZ/region link failure · NAT/LB conn-table exhaustion (silent partial drop)
  MOST REAL PARTITIONS ARE PARTIAL + ASYMMETRIC, not clean/total/symmetric

TIMEOUT vs RST vs SILENT DROP
  timeout      silence -- ZERO info on location; probe (mtr/nc) to localize
  RST          active reject/kill -- informative; check listener/FW REJECT rules
  silent drop  often SG/NACL misconfig or asymmetric routing; looks == timeout

TCP-LAYER RETRY
  RTO starts ~1s (RTT-derived), doubles each retry (exponential backoff)
  gives up after bounded retries (tcp_retries2, ~15-30min on established conns)
  app timeout almost always fires FIRST -- OS retry budget rarely matters to app
  client timeout != "write didn't happen" -- ACK can be lost after server commits
  => idempotency keys needed at APP layer regardless of TCP's own reliability

SPLIT BRAIN
  partition -> both sides believe they're leader -> divergent writes
  causes: even quorum size, stale leader hasn't detected partition,
          manual failover without confirming old primary is down
  FIX = FENCING, not just re-election:
    STONITH (out-of-band power-off, IPMI/cloud terminate API)
    fencing tokens (monotonic, storage rejects stale token) -- Chubby/ZK style

MTU BLACKHOLE
  DF-set oversized packet dropped + ICMP frag-needed (type3/code4) also dropped
  symptom: handshake/small reqs fine, large TLS/payload hangs FOREVER
  diagnose: ping -M do -s <size> to find threshold; tcpdump for retrans+no ICMP
  fix: MSS clamping at your gateway/tunnel (VPN/IPsec/GRE esp. prone -- overhead
       shrinks effective MTU); allow ICMP 3/4 end-to-end where you control it

CONN POOL EXHAUSTION
  leak: idle/idle-in-transaction connections piling up, DB itself not busy
        -> missing finally/context-manager on an exception path
  capacity: connections genuinely ACTIVE/busy, DB load or slow query is real
        -> Little's Law resize (concurrency = throughput x latency) or fix query
  check DB's own session view (pg_stat_activity) to tell which one it is

DNS FAILURE MODES
  resolver unreachable/timeout -> single resolver w/ no fallback = hard dependency
  stale record post-failover -> TTL advisory, caches ignore/extend it
  NXDOMAIN = record genuinely absent (or cached negative -- check SOA neg-TTL)
  SERVFAIL = resolution chain broken (unreachable authoritative, DNSSEC fail)
  split-horizon misconfig -> internal(VPN) works, external/CI fails identically-named lookup
```

## Sources

- [How to Diagnose MTU Black Hole Issues — OneUptime](https://oneuptime.com/blog/post/2026-03-20-diagnose-mtu-black-hole/view) — accessed 2026-07-26
- [What Nobody Tells You About Path MTU Discovery — Loke.dev](https://loke.dev/blog/path-mtu-discovery-icmp-black-holes) — accessed 2026-07-26
- [Path MTU Discovery and network ACLs — AWS VPC docs](https://docs.aws.amazon.com/vpc/latest/userguide/path_mtu_discovery.html) — accessed 2026-07-26
- [How to Build Split-Brain Prevention — OneUptime](https://oneuptime.com/blog/post/2026-01-30-split-brain-prevention/view) — accessed 2026-07-26
- [How to Build STONITH Implementation — OneUptime](https://oneuptime.com/blog/post/2026-01-30-stonith-implementation/view) — accessed 2026-07-26
- [Troubleshooting Connection Pool Exhaustion — DoHost](https://dohost.us/index.php/2025/08/01/troubleshooting-connection-pool-exhaustion/) — accessed 2026-07-26
- [Connection Refused vs Reset vs Timed Out — Webalert](https://web-alert.io/blog/connection-refused-reset-timed-out-errors-explained) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
