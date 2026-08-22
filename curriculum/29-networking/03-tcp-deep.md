# TCP Deep: Handshake, Session Lifecycle, State Machine, TIME_WAIT, Sequence Numbers

> **Track:** T29 Networking & Protocols · **Time:** 3h · **Prereqs:** T29-ip-layer · **Updated:** 2026-07-26
> **Module id:** `T29-tcp-deep` · **Tags:** tcp, critical

## The 30-second version

TCP's three-way handshake exchanges initial sequence numbers (ISNs) and confirms both directions are alive before any data moves: SYN(seq=x), SYN-ACK(seq=y, ack=x+1), ACK(ack=y+1) — after that, every byte transferred is numbered starting from those ISNs, so "sequence number" is a byte counter, not a packet counter. The full state machine has 11 states, and the two most misunderstood are CLOSE_WAIT (you've received a FIN but your application hasn't called close() yet — an accumulation of these means *your app* is leaking, not the network) and TIME_WAIT (the closing side waits 2×MSL after its final ACK specifically to absorb any duplicate segments from this exact connection that are still wandering the network, so they can't be misdelivered to a new connection that reuses the same 4-tuple). FIN means "I'm done sending, but I can still receive" (a graceful half-close); RST means "abort now, discard everything," sent for a connection to a closed port, a fatal protocol violation, or an application closing a socket with unread data still buffered. TIME_WAIT causes real production pain because on Linux it's hardcoded to 60 seconds regardless of any sysctl you tune, and a server accepting thousands of short-lived connections per second can pin thousands of sockets in TIME_WAIT simultaneously — the actual fix is almost never a kernel tunable, it's reducing connection churn via keep-alive and pooling.

## Why this gets asked

Because it's the cleanest test of whether someone has debugged a real TCP connection-state incident or just memorized the handshake diagram. Nearly everyone can draw SYN/SYN-ACK/ACK. Far fewer can explain why a server pinned at `ulimit`-adjacent socket counts is stuck in TIME_WAIT rather than ESTABLISHED, why a load balancer health check that half-closes a connection produces a pile of CLOSE_WAIT sockets in the backend, or what a sequence number wraparound actually implies on a 10Gbps link. The interviewer has almost certainly had an incident where `netstat -ant | awk '{print $6}' | sort | uniq -c` showed thousands of one state and they had to reason from the state machine to find the actual bug, and they want to see you reason the same way rather than recite RFC 793 from memory.

---

## Lineage: past → present → future

**What came before.** TCP was specified in RFC 793 (1981), formalizing a state machine designed for a world of long-lived, relatively few connections between trusted hosts — the handshake, the graceful four-segment close, and TIME_WAIT's 2×MSL wait were all sized around the assumption that connections were not churning at high rate and that "waiting a few minutes to be safe" was cheap. That assumption held for roughly two decades. The pain that broke it was the shift to short-lived, high-volume connections: HTTP/1.0's one-connection-per-request model, then the explosion of connection-per-request microservice and load-balancer traffic, meant servers and NAT gateways started accumulating TIME_WAIT sockets by the thousands, and the original RFC's 2×MSL=4-minute wait (assuming a 2-minute MSL) became a real capacity constraint rather than a safety margin nobody noticed.

**Where it stands now.** The industry response wasn't to change the protocol, it was to work around the wait: HTTP/1.1 keep-alive and HTTP/2 connection multiplexing directly reduce how often the handshake/teardown cycle happens at all, connection pooling in every serious client library (database drivers, HTTP clients, gRPC channels) reuses established connections instead of opening new ones per request, and Linux specifically hardcoded TIME_WAIT to 60 seconds (`TCP_TIMEWAIT_LEN` in kernel source, not RFC's theoretical 2×MSL) as a practical compromise, plus `tcp_tw_reuse` to let the *client* side safely recycle TIME_WAIT sockets for new outgoing connections when timestamps prove it's safe. The live disagreement, to the extent there is one, is about `tcp_tw_recycle` specifically — it existed as a more aggressive recycling option, and it's gone (removed in Linux 4.12, 2017) because its safety assumption (monotonically increasing per-peer timestamps) breaks completely behind NAT, where many hosts share one IP and their timestamps aren't coordinated, causing legitimate connections from NATed clients to be silently dropped. Anyone recommending `tcp_tw_recycle` today is giving 2015-era advice that's actively dangerous now.

**Where it's heading.** QUIC (RFC 9000), the transport under HTTP/3, sidesteps a chunk of this entirely by running over UDP with its own connection-ID-based session model instead of TCP's 4-tuple + state machine, so there's no TIME_WAIT-equivalent socket pinning at the OS level in the same way — connection migration (surviving an IP change, e.g. WiFi to cellular handoff) is also native in a way TCP fundamentally cannot do because TCP identity is the 4-tuple. This is real and shipping (most major browsers and CDNs support QUIC/HTTP3 today), but it doesn't replace TCP for the enormous surface of non-HTTP traffic (databases, internal RPC, SSH) that will keep running on TCP's state machine indefinitely — expect QUIC's share to keep growing at the HTTP edge while TCP internals remain exactly this mechanically relevant for everything else.

---

## Mental model

Think of TCP's lifecycle as two independent half-close ceremonies wrapped in one shared handshake at the start:

```
CLIENT                                          SERVER
  |-------- SYN seq=x ------------------------->|         SYN_SENT / LISTEN -> SYN_RECEIVED
  |<------- SYN seq=y, ack=x+1 -----------------|
  |-------- ACK ack=y+1 ------------------------>|         both ESTABLISHED
  |                                               |
  |<==================== data =================>|
  |                                               |
  |-------- FIN seq=x+n --------------------------->|      client: FIN_WAIT_1
  |<------- ACK ack=x+n+1 ------------------------- |      client: FIN_WAIT_2 / server: CLOSE_WAIT
  |            (server can still send data here)     |
  |<------- FIN seq=y+m ---------------------------- |      server: LAST_ACK
  |-------- ACK ack=y+m+1 -------------------------->|      client: TIME_WAIT / server: CLOSED
  |   (client waits 2*MSL, then) CLOSED               |
```

The key insight: FIN only closes *that direction*. The client saying "I'm done sending" (FIN_WAIT states) doesn't stop the server from sending more data back — that's the half-close, and it's why FIN_WAIT_2 can sit open for a while if the server keeps talking after the client's FIN.

---

## How it actually works

### The handshake, with real numbers

Client picks an Initial Sequence Number (ISN) — historically incrementing, now required to be effectively unpredictable per RFC 6528 to prevent blind connection-spoofing/hijacking. Say client ISN = **1000**, server ISN = **5000**:

1. Client → Server: `SYN, seq=1000` — "I want to talk, my byte stream starts at 1000."
2. Server → Client: `SYN, ACK, seq=5000, ack=1001` — "Acknowledged your byte 1000 (ack = seq+1 for a SYN, which consumes one sequence number even though it carries no payload), and my byte stream starts at 5000."
3. Client → Server: `ACK, ack=5001` — "Acknowledged your byte 5000."

After this, if the client sends 200 bytes of data, that segment carries `seq=1001` and the server acks with `ack=1201` (1001+200). Sequence numbers count **bytes**, not packets — a segment carrying zero payload bytes (a bare ACK) doesn't consume a sequence number, but SYN and FIN each consume exactly one, which is why the ack after a SYN or FIN is always seq+1.

### The full state machine

```
                              CLOSED
                            /         \
              (passive open)           (active open: send SYN)
                    |                              |
                 LISTEN                        SYN_SENT
                    |                              |
         (recv SYN, send SYN-ACK)          (recv SYN-ACK, send ACK)
                    |                              |
              SYN_RECEIVED  ------(recv ACK)------->|
                    |                                |
                     \--------------------------->  ESTABLISHED
                                                    /            \
                                    (recv FIN,                (active close:
                                     send ACK)                  send FIN)
                                        |                            |
                                  CLOSE_WAIT                   FIN_WAIT_1
                                        |                        /       \
                              (app calls close,        (recv ACK       (recv FIN,
                               send FIN)                 of FIN)        send ACK)
                                        |                    |               |
                                   LAST_ACK             FIN_WAIT_2       CLOSING
                                        |                    |               |
                                  (recv ACK)            (recv FIN,      (recv ACK)
                                        |                 send ACK)          |
                                     CLOSED                  |               |
                                                          TIME_WAIT <--------/
                                                              |
                                                     (2 * MSL timeout)
                                                              |
                                                          CLOSED
```

Eleven distinct states total: CLOSED, LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED, FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT, CLOSING, LAST_ACK, TIME_WAIT. (CLOSED appears twice in the diagram because it's both the start and the terminal state, not a twelfth state.) CLOSING is the simultaneous-close path — both sides sent FIN before either had acked the other's, rare but legal.

### FIN vs RST — different meanings to the peer

- **FIN** is a graceful, orderly shutdown signal that says "I have no more data to send, but I can still receive." It's part of the normal state machine, consumes a sequence number, and gets acked like any other segment. A half-close (one side FINs, keeps reading; the other keeps sending, then eventually FINs back) is fully legal and used deliberately — e.g., a client uploading a large request body, calling `shutdown(SHUT_WR)`, then reading the response while the server is still receiving the tail of the upload.
- **RST** is an abort — "this connection is invalid, stop immediately, discard any buffered data." It carries no promise of delivery and doesn't get a graceful ack-and-wait cycle. RST is sent when: a SYN arrives for a port nothing is listening on (immediate, fast rejection — this is why "connection refused" is instantaneous while "connection timeout" is slow, the RST case actively tells you, the timeout case is silence); an application calls `close()` on a socket that still has unread data in its receive buffer (the OS sends RST instead of FIN because a graceful close would silently discard that unread data, and RST at least signals to the peer that data was lost rather than pretending everything transferred cleanly — the classic symptom is a client seeing "Connection reset by peer" after posting a large body to a server that rejected it early without reading the rest); or an application explicitly wants to abort (setting `SO_LINGER` with a zero timeout forces RST instead of the normal FIN sequence on close).

### TIME_WAIT — why it exists, and why it hurts

**Why it exists.** After the active closer sends its final ACK (acknowledging the peer's FIN), it moves to TIME_WAIT rather than straight to CLOSED, and waits **2×MSL** (Maximum Segment Lifetime — RFC 793 assumes MSL=2 minutes, so the "textbook" wait is 4 minutes; Linux hardcodes it to a flat **60 seconds** regardless, `TCP_TIMEWAIT_LEN` in kernel source, which is a real deviation from the RFC that's worth stating explicitly if asked). Two concrete reasons for the wait, both worth naming:
1. **Absorb duplicate segments from this exact connection.** A network can still be carrying a delayed duplicate of an old segment (retransmission, or a genuinely stray packet) when a *new* connection reuses the identical 4-tuple (same src IP:port, dst IP:port). Without TIME_WAIT, that stray old segment could be misdelivered into the new connection and misinterpreted as legitimate data or an ack for the new incarnation.
2. **Make sure the final ACK actually lands.** If that last ACK is lost, the peer (still in LAST_ACK) will retransmit its FIN. If the active closer had already moved on and closed the socket, the retransmitted FIN would hit a closed port and get an RST back instead of the ACK the peer needed — so TIME_WAIT keeps the state around just long enough to retransmit the ACK if the FIN shows up again.

**Why it hurts in production.** A server handling high connection churn (a load balancer talking to a backend fleet with connections opened and closed per request rather than kept alive, or any service under a naive-client-library default of one-connection-per-request) can accumulate an enormous number of sockets in TIME_WAIT — since each is pinned for a flat 60 seconds on Linux regardless of tuning, at 10,000 closes/sec you can have up to 600,000 sockets sitting in TIME_WAIT at once. **On the client/outbound side specifically**, this directly collides with ephemeral port exhaustion: each outbound connection consumes a unique local port for the duration it's open *and* for the 60 seconds it sits in TIME_WAIT afterward, and Linux's default ephemeral range (`net.ipv4.ip_local_port_range`, commonly `32768–60999`, roughly 28,000 ports) can run out under sustained high-churn outbound traffic, producing `connect()` failures with `EADDRNOTAVAIL` — the observable symptom is intermittent outbound connection failures that spike under load and correlate exactly with the TIME_WAIT count shown by `ss -tan state time-wait | wc -l`.

**Actual mitigations, correctly scoped:**
- `SO_REUSEADDR` lets a **server** rebind to a local address/port combination that has sockets in TIME_WAIT — its real purpose is letting a restarted server bind its listening port immediately instead of getting `EADDRINUSE`, not a general TIME_WAIT fix for connection churn.
- `net.ipv4.tcp_tw_reuse` (a sysctl, safe and recommended) lets the **client** side reuse a TIME_WAIT socket's port for a *new outgoing* connection when TCP timestamps prove it's safe to do so — this is the actual lever for client-side ephemeral port pressure, and it's on by default in many modern distributions.
- `tcp_tw_recycle` is **removed** (Linux 4.12+) and should never be recommended — its safety check assumed monotonically increasing timestamps per remote peer, which is false when multiple NATed clients share one source IP, causing legitimate connections to be dropped.
- `SO_LINGER` with a zero timeout forces an immediate RST-based close instead of the graceful FIN/TIME_WAIT sequence — this avoids TIME_WAIT entirely but at the cost of the two guarantees TIME_WAIT provides (data-loss risk if unacked data is still in flight, and no protection against duplicate-segment misdelivery), so it's a targeted tool for very specific high-churn internal scenarios, not a default.
- **The actual production fix is almost always reducing churn**, not tuning kernel parameters: HTTP keep-alive, connection pooling (database connection pools, persistent gRPC channels, HTTP client connection reuse), and load balancer configurations that maintain persistent backend connections rather than opening one per request. "Reducing MSL" is not something you control — it's not exposed as a tunable, and even if you shrink `tcp_fin_timeout` (which actually governs how long an *orphaned* socket sits in FIN_WAIT_2, a related but distinct knob, default 60s) that doesn't touch TIME_WAIT's fixed 60-second wait at all.

### Sequence number wraparound

The sequence number field is 32 bits, wrapping at 2^32 ≈ 4.29 billion. On a slow link this never matters within a connection's lifetime. On a fast one it can happen fast enough to be a real correctness concern: at 10 Gbps, 2^32 bytes × 8 bits/byte ÷ 10×10^9 bits/sec ≈ **3.4 seconds** to wrap the entire sequence space. This is exactly why **PAWS (Protection Against Wrapped Sequence numbers, RFC 7323)** exists: it uses the TCP timestamp option (a monotonically increasing per-connection timestamp carried on every segment) to disambiguate an old, wrapped-around segment from a legitimate new one with a coincidentally identical sequence number — sequence numbers alone stop being a reliable ordering signal at high enough bandwidth, so timestamps back them up. This is also why window scaling (needed to keep high-bandwidth-delay-product links full, covered in the performance module) and timestamps are both TCP options that matter far more on modern fast links than they did when RFC 793 was written for links many orders of magnitude slower.

### Retransmission, briefly (full mechanics in the performance module)

A segment is retransmitted if its ACK doesn't arrive within the current **RTO (Retransmission Timeout)**, computed from smoothed RTT and RTT variance (RFC 6298), with an initial RTO of **1 second** and exponential backoff on each subsequent unacknowledged retransmit of the same segment. Linux's `tcp_retries2` (default **15**) governs how many retransmit attempts happen before the OS gives up and reports the connection as dead to the application — with exponential backoff this stretches out to roughly 15–30 minutes in the worst case before a truly dead connection is reported as failed, which is a real, occasionally surprising number when someone expects a "network fault" to surface in seconds.

---

## Build it from scratch

The mechanical piece worth being able to write is the sequence/ack arithmetic and state transitions, not a full TCP stack — but a minimal state-machine simulator proves the model is actually understood rather than memorized as a diagram:

```python
# untested sketch — pure simulation, no real sockets
from enum import Enum, auto

class TCPState(Enum):
    CLOSED = auto(); LISTEN = auto(); SYN_SENT = auto(); SYN_RECEIVED = auto()
    ESTABLISHED = auto(); FIN_WAIT_1 = auto(); FIN_WAIT_2 = auto()
    CLOSE_WAIT = auto(); CLOSING = auto(); LAST_ACK = auto(); TIME_WAIT = auto()

class TCPConnection:
    def __init__(self, isn: int):
        self.state = TCPState.CLOSED
        self.seq = isn
        self.peer_seq = None

    def active_open(self):
        assert self.state == TCPState.CLOSED
        self.state = TCPState.SYN_SENT
        return {"flags": "SYN", "seq": self.seq}

    def recv_syn_ack(self, peer_seq: int, ack: int):
        assert self.state == TCPState.SYN_SENT
        assert ack == self.seq + 1, "peer acked the wrong byte"
        self.peer_seq = peer_seq
        self.seq += 1
        self.state = TCPState.ESTABLISHED
        return {"flags": "ACK", "ack": peer_seq + 1}

    def active_close(self):
        assert self.state == TCPState.ESTABLISHED
        self.state = TCPState.FIN_WAIT_1
        segment = {"flags": "FIN", "seq": self.seq}
        self.seq += 1                      # FIN consumes one sequence number
        return segment

    def recv_ack_of_fin(self):
        assert self.state == TCPState.FIN_WAIT_1
        self.state = TCPState.FIN_WAIT_2

    def recv_fin(self):
        if self.state == TCPState.FIN_WAIT_2:
            self.state = TCPState.TIME_WAIT
        elif self.state == TCPState.ESTABLISHED:
            self.state = TCPState.CLOSE_WAIT
        else:
            raise ValueError(f"unexpected FIN in state {self.state}")

conn = TCPConnection(isn=1000)
print(conn.active_open())                       # {'flags': 'SYN', 'seq': 1000}
print(conn.recv_syn_ack(peer_seq=5000, ack=1001))# {'flags': 'ACK', 'ack': 5001}
print(conn.state)                                # ESTABLISHED
print(conn.active_close())                       # {'flags': 'FIN', 'seq': 1001}
conn.recv_ack_of_fin()
conn.recv_fin()
print(conn.state)                                # TIME_WAIT
```

This is small on purpose — the point is that the assertions (`ack == self.seq + 1`, FIN consuming a sequence number, only certain states accepting a FIN) are exactly the mechanical details an interviewer will probe if you claim to understand the state machine, and writing them out forces you to get the off-by-one details right instead of hand-waving them.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Server has thousands of sockets stuck in `CLOSE_WAIT` (`ss -tan state close-wait`) | Peer sent FIN, kernel acked it, but the **application** never called `close()` on its side — this is an app bug, not a network issue | Fix the app: ensure every code path (including error paths) closes the socket; a leaking connection pool or a missed `finally`/`with` is the usual culprit |
| Server has thousands of sockets stuck in `TIME_WAIT` | Expected under high request-churn if connections aren't reused | Enable `tcp_tw_reuse`, but the real fix is keep-alive/connection pooling to reduce churn in the first place |
| Outbound `connect()` calls intermittently fail with `EADDRNOTAVAIL` under load | Ephemeral port exhaustion — TIME_WAIT sockets plus in-flight connections exceed the local port range | Widen `net.ipv4.ip_local_port_range`, enable `tcp_tw_reuse`, reduce churn via pooling, or use multiple source IPs |
| Client sees "Connection reset by peer" after uploading a large body | Server closed the socket (e.g., rejected the request early) while unread data was still sitting in its receive buffer, so the kernel sent RST instead of a clean FIN | Have the server fully read (or explicitly drain) the request body before closing, or send the rejection response and let the client see it before the connection tears down |
| A connection appears alive but data never flows in either direction | Half-open connection — one side crashed/rebooted without sending FIN (e.g., a VM killed hard, or a stateful firewall dropped conntrack state) and the other side has no idea | TCP keepalive (covered in the performance module) or, more reliably, an application-level heartbeat with a much shorter timeout than the ~2-hour kernel keepalive default |
| A load-balancer health check produces a burst of `CLOSE_WAIT` on the backend right after each check | Health checker opens a connection, gets a response, then closes without a graceful shutdown sequence the backend expects, or the backend app isn't closing promptly after detecting the peer's FIN | Confirm the backend closes its side promptly on detecting EOF/FIN from a read returning 0 bytes; don't rely on the OS to clean this up for you |

---

## Tradeoffs & when NOT to use it (i.e., when TCP's model is the wrong fit)

- **Don't use TCP's reliable, ordered, connection-oriented model for latency-sensitive, loss-tolerant traffic** (real-time video/audio, some multiplayer game state) — head-of-line blocking on a lost segment stalls everything behind it even if later data has already arrived; UDP-based protocols (RTP, QUIC's per-stream independence) exist precisely because TCP's ordering guarantee is sometimes the wrong guarantee to pay for.
- **Don't rely on TCP keepalive as your liveness detector** for anything latency-sensitive — the ~2-hour default before the first probe (detailed in the performance module) is far too slow for detecting a dead peer in an interactive system; that's an application-heartbeat problem, not something TCP's own keepalive is positioned to solve at those timescales.
- **Don't fight TIME_WAIT with `tcp_tw_recycle`** — it's removed for a reason (breaks under NAT), and reaching for it signals outdated knowledge rather than a real understanding of the tradeoff.
- **Don't treat every `CLOSE_WAIT` accumulation as a network problem** — it is almost always an application resource-management bug (not calling `close()`), and looking at kernel tunables first wastes the time that should go into an application-level connection leak audit.
- **Don't set `SO_LINGER` to zero as a default "performance" tweak** — skipping the graceful close saves you TIME_WAIT at the cost of losing the guarantees TIME_WAIT exists to provide (unacked data can be silently dropped, and duplicate-segment misdelivery protection is gone); it's a targeted tool for specific high-churn internal scenarios where those risks are acceptable, not a blanket default.

---

## Interview questions

### Q1 — Walk me through the three-way handshake with actual sequence numbers.
**Testing:** baseline, but with real arithmetic rather than "SYN, SYN-ACK, ACK."
**Answer:** Client sends SYN with ISN=1000. Server responds SYN-ACK with its own ISN=5000 and ack=1001 (client's ISN+1, since SYN consumes one sequence number). Client sends ACK with ack=5001 (server's ISN+1). Both sides now agree on where each byte stream starts, and ESTABLISHED begins.
**Follow-up trap:** *"Why ack = seq + 1 for a SYN carrying zero payload bytes?"* — SYN and FIN each consume exactly one sequence number by convention even though they carry no data, specifically so the handshake and teardown have an unambiguous byte to acknowledge; a bare data-free ACK, by contrast, consumes none.

### Q2 — Draw the full TCP state machine and tell me what CLOSE_WAIT means.
**Testing:** whether all 11 states are known, and whether CLOSE_WAIT's actual meaning (an app bug signal) is understood.
**Answer:** CLOSED, LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED, FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT, CLOSING, LAST_ACK, TIME_WAIT. CLOSE_WAIT means the kernel has received and acked a FIN from the peer, but the local application hasn't called `close()` yet — the kernel is waiting on the application, not the network.
**Follow-up trap:** *"You see 5,000 sockets in CLOSE_WAIT. What's your first hypothesis?"* — an application resource leak: some code path (very often an exception path) never closes the socket after the peer disconnects. This is essentially never a network problem, and jumping to kernel tunables here wastes the incident.

### Q3 — Why does TIME_WAIT exist, precisely?
**Answer:** Two reasons. First, to absorb any delayed duplicate segment from this exact connection that's still in flight, so it can't be misdelivered into a new connection that happens to reuse the identical 4-tuple. Second, to make sure the final ACK is retransmittable — if the peer's LAST_ACK-state FIN retransmission arrives because the original ACK was lost, the closer needs to still be around to resend the ACK, rather than having already torn down and now answering with an RST to a FIN it no longer recognizes.
**Follow-up trap:** *"What's 2×MSL, and does Linux actually implement that?"* — RFC 793 assumes MSL=2 minutes, so the textbook value is 4 minutes; Linux hardcodes TIME_WAIT to a flat 60 seconds (`TCP_TIMEWAIT_LEN`) regardless of any MSL assumption or sysctl, which is a real, quotable deviation from the RFC's theoretical model.

### Q4 — Your server is running out of ephemeral ports under load. Diagnose and fix it.
**Answer:** Check `ss -tan state time-wait | wc -l` — if it's large and correlates with the failure rate, high-churn outbound connections are pinning ports in TIME_WAIT for 60 seconds each, exhausting the default ~28,000-port ephemeral range (`32768–60999`). Enable `net.ipv4.tcp_tw_reuse` so the client side can safely recycle those ports for new connections, but the durable fix is reducing churn: connection pooling, HTTP keep-alive, persistent gRPC channels.
**Follow-up trap:** *"Would `tcp_tw_recycle` fix it faster?"* — it's removed from the kernel (since 4.12) specifically because its safety check assumed each remote peer's TCP timestamps increase monotonically, which is false when multiple NATed clients share a source IP — enabling it (on an old kernel, or recommending it) causes legitimate connections from NATed clients to be silently dropped. Recommending it is a red flag, not a fix.

### Q5 — What's the difference between FIN and RST, and when does the OS choose RST over a graceful close?
**Answer:** FIN is a graceful, ordered "I'm done sending, still listening" signal that's part of the normal handshake-and-teardown state machine. RST is an abrupt abort with no delivery guarantee. The OS sends RST instead of a clean FIN when an application calls `close()` on a socket that still has unread data sitting in its receive buffer — a graceful close would silently discard that data, so the kernel signals the abnormal termination via RST instead, which is exactly the mechanism behind the "Connection reset by peer" error a client sees when a server rejects a request without draining the body first.
**Follow-up trap:** *"Is `SO_LINGER(0)` the same as this?"* — related but deliberate: `SO_LINGER` with a zero timeout is the application *choosing* to force an RST-based abort on close instead of the default graceful FIN sequence, trading away TIME_WAIT's protections for immediacy. The unread-buffer case is the kernel doing this automatically because a clean close would lose data either way.

### Q6 — A 10Gbps link: how long until TCP sequence numbers wrap, and why does that matter?
**Answer:** 2^32 bytes × 8 bits ÷ 10×10^9 bits/sec ≈ 3.4 seconds. It matters because a sequence number alone stops being a reliable way to tell "new data" from "an old, wrapped-around duplicate" at that rate, which is exactly why PAWS (RFC 7323) exists — it uses the TCP timestamp option, a monotonically increasing value carried on every segment, to disambiguate what raw sequence numbers can no longer distinguish on fast links.
**Follow-up trap:** *"Was this a real concern when RFC 793 was written in 1981?"* — no, links were orders of magnitude slower, so a 4.29-billion-byte wrap took a genuinely long time and duplicate-segment collision after a wrap was a non-issue in practice; PAWS (RFC 7323, part of the same TCP extensions package as window scaling) is a retrofit that became necessary as link speeds grew, which is worth naming as an example of a protocol assumption that aged out.

### Q7 — What's a half-close, and give a real use case for it.
**Answer:** One side sends FIN (stops sending, can still receive) while the connection stays open in the other direction — `shutdown(SHUT_WR)` in socket APIs, distinct from `close()` which tears down both directions. Real use case: a client uploading a large file body over a single connection calls `shutdown(SHUT_WR)` once the upload is fully sent, signaling "no more data from me," then reads the server's response on the same connection while the server may still be processing/reading the tail of what was sent.
**Follow-up trap:** *"What state is the client in during this, and can it still receive?"* — FIN_WAIT_2 (after the server acks the client's FIN), and yes, it can still receive data — that's the entire point of a half-close, and confusing FIN_WAIT_2 with "the connection is basically dead" is a common but wrong assumption; it's alive in one direction until the server also FINs.

### Q8 — How does an RTO get computed, and what happens if a connection dies but the socket keeps retrying?
**Answer:** RFC 6298: RTO is derived from a smoothed RTT estimate (SRTT) and RTT variance (RTTVAR), with an initial RTO of 1 second before any samples exist, and it doubles (exponential backoff) on each successive retransmission of the same unacknowledged segment. Linux's `tcp_retries2` (default 15) caps how many retransmission attempts happen before the kernel gives up and surfaces an error to the application — with exponential backoff, this can stretch to roughly 15–30 minutes in the worst case before a genuinely dead connection is reported as failed.
**Follow-up trap:** *"Why would a well-designed service ever want an application-level timeout shorter than that?"* — because 15-30 minutes is completely unacceptable for anything user-facing; the kernel's retry budget exists to survive genuinely transient network blips, not to be the failure-detection mechanism for a live system, which is exactly why application-level timeouts and circuit breakers (see the resilience catalogue) sit on top of, not instead of, TCP's own retransmission behavior.

### Q9 — Two hosts send FIN to each other at nearly the same time. What happens?
**Answer:** Simultaneous close — both sides move ESTABLISHED → FIN_WAIT_1 on sending their own FIN, then each receives the other's FIN before receiving an ACK of its own FIN, transitioning FIN_WAIT_1 → CLOSING (rather than the usual FIN_WAIT_2 path), send an ACK for the peer's FIN, then once that ACK is received both move to TIME_WAIT and eventually CLOSED. It's a rare but fully legal path through the state machine, not an error condition.
**Follow-up trap:** *"Do both sides end up in TIME_WAIT simultaneously, or just one?"* — both, in the simultaneous-close case — unlike the normal asymmetric close where only the active closer sees TIME_WAIT, simultaneous close puts both peers through CLOSING into TIME_WAIT, because each side needed to both send and receive a FIN it hadn't yet acked.

### Q10 — A connection sits ESTABLISHED on both ends' socket tables, but no data has moved in hours, and one side actually crashed and rebooted without ever sending a FIN. How does the surviving side find out?
**Answer:** It doesn't, promptly, on its own — this is a half-open connection, and without something actively probing it, the surviving side's socket looks perfectly healthy until it tries to send data (gets no ACK, eventually times out via retransmission/RTO) or until TCP keepalive (if enabled) sends its own probe after its configured idle period and gets no response, eventually tearing the connection down.
**Follow-up trap:** *"What's wrong with relying on keepalive for this in a latency-sensitive system?"* — the Linux keepalive defaults are roughly a 2-hour idle period before the first probe, 75 seconds between probes, 9 probes before giving up — on the order of 2+ hours before detection, which is far too slow for anything that needs to fail over quickly. An application-level heartbeat with a timeout measured in tens of seconds is the actual fix, and this is exactly why "TCP keepalive" and "connection is alive" are not the same claim.

### Q11 — Why does an RST arrive instantly for a connection attempt to a closed port, but a connection attempt to a filtered port just hangs?
**Answer:** A closed port with nothing listening generates an immediate kernel-level RST in response to the SYN — the OS actively knows nothing is there and says so right away. A firewall/security-group rule that silently drops the SYN produces no response at all, so the connecting side just waits out its own SYN retransmission timer and eventual connection-attempt timeout, which is a much longer, silent failure. The RST case is fast because something is actively rejecting; the silent case is slow because nothing is answering at all.
**Follow-up trap:** *"Which is more informative for debugging, and why might a security team prefer the slower one anyway?"* — RST is far more informative (instant, unambiguous "nothing's listening here"); silently dropping is deliberately chosen by some security policies specifically because it doesn't confirm to a port-scanner that a host exists at all, trading operator debuggability for a marginal reduction in reconnaissance value — a real, defensible tradeoff worth naming rather than assuming silent-drop is simply a misconfiguration.

---

## Red flags that fail you

- Describing the handshake as "SYN, SYN-ACK, ACK" with no actual sequence number arithmetic when asked to go one level deeper.
- Listing fewer than the full 11 TCP states, or omitting CLOSING/LAST_ACK entirely.
- Treating CLOSE_WAIT accumulation as a network issue instead of an application-level `close()` bug.
- Recommending `tcp_tw_recycle` as a TIME_WAIT fix.
- Claiming TIME_WAIT's duration is configurable via a documented sysctl on Linux (it isn't — it's hardcoded at 60 seconds).
- Confusing `tcp_fin_timeout` (governs orphaned FIN_WAIT_2 sockets) with TIME_WAIT duration (a different, non-tunable state).
- Not knowing why RST is sent on close-with-unread-data, or conflating it with a normal graceful close.

---

## Cheat card

```
HANDSHAKE: SYN(seq=x) -> SYN-ACK(seq=y, ack=x+1) -> ACK(ack=y+1)
  SYN and FIN each consume 1 sequence number; bare ACKs consume 0
  ISN must be effectively unpredictable (RFC 6528) — anti-spoofing

11 STATES: CLOSED, LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED,
           FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT, CLOSING, LAST_ACK, TIME_WAIT

CLOSE_WAIT pileup = APP BUG (peer FINed, your app never called close())
TIME_WAIT   = active closer's post-close wait, protects against:
              (1) delayed dup segment misdelivery into a reused 4-tuple
              (2) losing the final ACK (peer's LAST_ACK FIN needs an ACK resend)
              RFC793 theory: 2xMSL, MSL=2min -> 4min. LINUX REALITY: hardcoded 60s
              (TCP_TIMEWAIT_LEN, NOT tunable via sysctl)
  tcp_fin_timeout (default 60s) = DIFFERENT knob, governs orphaned FIN_WAIT_2 only

TIME_WAIT PAIN: churny servers pin thousands of sockets x 60s each
  client-side collides w/ ephemeral port range (~28K ports, 32768-60999 default)
  -> connect() EADDRNOTAVAIL under load
  FIX: tcp_tw_reuse (safe, client-side) > widen port range > REAL FIX: pooling/keep-alive
  tcp_tw_recycle: REMOVED (4.12+), breaks under NAT — never recommend it

FIN vs RST: FIN = graceful, "no more from me", half-close legal, consumes 1 seq#
  RST = abort now, no delivery guarantee. Sent for: SYN to closed port (instant),
  close() with unread data still buffered ("connection reset by peer"), SO_LINGER(0)

SEQ WRAPAROUND: 2^32 bytes wraps in ~3.4s at 10Gbps -> PAWS (RFC7323, uses timestamps)
                to disambiguate old wrapped dupes from new data

RTO: RFC6298, initial 1s, exp backoff per retransmit, tcp_retries2=15 default
     -> ~15-30min worst case before kernel reports connection dead
```

## Sources

- RFC 793 — Transmission Control Protocol (state machine, 2xMSL)
- RFC 6298 — Computing TCP's Retransmission Timer
- RFC 6528 — Defending against Sequence Number Attacks (unpredictable ISN)
- RFC 7323 — TCP Extensions for High Performance (timestamps, PAWS, window scaling)
- [TCP TIME_WAIT Port Exhaustion: When Connection Pooling Isn't Enough — Michal Drozd](https://www.michal-drozd.com/en/blog/tcp-time-wait-port-exhaustion/) — accessed 2026-07-26
- [TCP TIME_WAIT and conntrack Exhaustion: The High-Throughput Linux Cliff — DevOpsBeast](https://devopsbeast.com/blog/tcp-time-wait-conntrack-exhaustion) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
