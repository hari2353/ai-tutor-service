# NIC → Kernel → Socket: How a Packet Becomes Bytes in Your Process

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.5h · **Prereqs:** T16-io-models · **Updated:** 2026-08-03
> **Module id:** `T16-networking-stack` · **Tags:** networking

## The 30-second version

A packet's journey from wire to your application crosses four distinct layers, each with real, measurable cost: the NIC DMAs the frame into a fixed-size RX ring buffer in RAM and fires a hardware interrupt (hardIRQ) — but instead of interrupting the CPU per-packet under load (which would collapse the machine at high packet rates), NAPI switches the driver into polling mode after the first interrupt, draining up to a `budget` of 64 packets per softIRQ pass; from there the packet climbs `netif_receive_skb()` → `ip_rcv()` → `tcp_v4_rcv()` → the socket's receive queue, at which point a blocked `recv()`/`epoll_wait()` call in your process wakes up. On top of that raw delivery sits TCP (reliable, ordered, connection-oriented — the state machine and TIME_WAIT mechanics are covered in the TCP-deep module), then optionally TLS (an extra 1-2 round trips of handshake before any application data moves — TLS 1.3 cut this from 2-RTT to 1-RTT, and session resumption/0-RTT can eliminate it entirely at the cost of replay risk), then the application protocol: HTTP/1.1 (one request in flight per TCP connection without pipelining, so browsers open 6+ parallel connections per origin to compensate), HTTP/2 (multiplexes many streams over one TCP connection, but a single dropped packet stalls every stream behind it — TCP-level head-of-line blocking, because TCP guarantees byte order across the *whole* connection, not per-stream), and HTTP/3 over QUIC (runs over UDP with its own per-stream loss recovery, so one dropped packet only stalls its own stream — real, shipping, and reported to cut mobile latency by roughly 30% and page-load time from ~3s to ~0.8s under lossy conditions versus HTTP/1.1 in reported benchmarks). Before any of this, DNS resolution typically costs one extra round trip (cached) to tens of milliseconds (cold, recursive resolution through the chain), which is why connection reuse and DNS prefetching are real, measurable latency levers, not micro-optimizations.

## Why this gets asked

Because "my API has a 200ms p99 and I don't know why" is one of the most common real incidents, and the honest answer is almost always somewhere in this stack, not in application code — a TLS handshake being paid on every request because keep-alive isn't configured, HTTP/1.1 connection-limit contention when a client library caps concurrent connections per host, DNS resolution stalling because a resolver's TTL-respecting cache expired at the worst moment, or a NIC interrupt storm degrading an entire host's throughput because interrupt coalescing wasn't tuned for the traffic pattern. The interviewer wants to know whether you can place a latency number at the correct layer (kernel packet processing vs. TCP handshake vs. TLS handshake vs. DNS vs. application logic) rather than reflexively blaming "the network," and whether you understand what each protocol generation actually fixed versus what it's often incorrectly credited with fixing.

---

## Lineage: past → present → future

**What came before.** The early web ran on HTTP/1.0 (1996) with one TCP connection per request — every single resource on a page paid a fresh TCP handshake (1 RTT) plus, once HTTPS became standard, a fresh TLS handshake (originally 2 RTT under TLS 1.2) before a single byte of actual content moved. The pain was direct and measurable: a page with 50 assets meant up to 50 sequential connection setups, an obviously unacceptable multiplier on latency as pages grew richer through the 2000s. HTTP/1.1 (1997) added persistent connections (keep-alive, reusing one TCP connection for multiple requests) and optional pipelining (send multiple requests without waiting for each response) — keep-alive was adopted everywhere and remains foundational, but pipelining was largely abandoned in practice because a single slow response still blocked every response queued behind it on that connection (head-of-line blocking baked into the protocol's strict in-order response requirement), so browsers instead worked around HTTP/1.1's one-request-in-flight-per-connection limitation by opening 6-8 parallel TCP connections per origin — which itself created new problems (TCP's congestion control state, and TLS handshake cost, is now paid 6-8 times over per origin).

**Where it stands now.** HTTP/2 (2015, based on Google's SPDY) fixed the application-layer problem directly: true multiplexing of many logical streams over a *single* TCP connection, with header compression (HPACK) cutting redundant header bytes on every request. This is now the majority deployment for HTTP traffic on the web. But it inherited a structural problem it couldn't fix without changing the transport: TCP guarantees strict, in-order delivery for the *entire connection*, so if one packet carrying stream A's data is lost, TCP will not deliver *any* later-arriving bytes — including unrelated stream B's — until the lost packet is retransmitted and arrives, a phenomenon universally called "TCP head-of-line blocking" even though it's really "TCP's ordering guarantee is a connection-wide property, and HTTP/2's per-stream abstraction is built on top of it, not underneath it." QUIC/HTTP-3 (RFC 9000, standardized 2021, now default in Chrome/Firefox/Safari and served by most major CDNs) is the current resolution: it runs over UDP and implements its own reliability and per-stream loss recovery in userspace, so a lost packet only stalls the specific stream it belonged to — real head-of-line-blocking elimination, not a workaround. TLS 1.3 (2018) is a parallel, now-near-universal improvement: it cut the handshake from TLS 1.2's 2 round trips to 1, and added a 0-RTT resumption mode for repeat connections (send application data in the very first flight, at the cost of losing replay protection for that first flight specifically — a real security tradeoff most deployments accept only for idempotent requests).

**Where it's heading.** QUIC/HTTP-3 adoption keeps climbing at the CDN/browser edge (major cloud providers and CDNs report majority QUIC traffic on served content today), and its connection-migration property (surviving a client's IP change, e.g. WiFi-to-cellular handoff, because QUIC identifies a connection by a connection ID rather than the TCP 4-tuple) is a capability TCP fundamentally cannot retrofit. What's genuinely unresolved: QUIC's userspace implementation (versus TCP's decades of in-kernel, hardware-offload-friendly optimization) means it currently costs more CPU per byte on the server side in many deployments, and kernel-level QUIC offload support is still maturing — so "is QUIC strictly better" is not a settled yes, it's a real ongoing tradeoff between structural head-of-line-blocking elimination and server-side CPU cost, actively being narrowed by ongoing kernel and NIC offload work rather than already solved.

---

## Mental model

```
WIRE
  |
  v
[NIC] --DMA--> RX RING BUFFER (fixed-size, in RAM, holds skb descriptors)
  |
  v
HARDIRQ (fires once, minimal work: "something arrived, schedule the rest")
  |
  v
NAPI POLL (softirq context, ksoftirqd) -- drains ring buffer, budget=64 pkts/pass
  |         avoids one hardIRQ per packet under load (interrupt-storm defense)
  v
netif_receive_skb() -> GRO (coalesce fragments) -> ip_rcv() -> tcp_v4_rcv()
  |
  v
SOCKET RECEIVE QUEUE  (per-connection buffer)
  |
  v
recv()/epoll_wait() in YOUR PROCESS wakes up  <-- this is where "userspace" starts

Layered on top of raw TCP delivery, in order, each with its own RTT cost:
  DNS  -> (resolve hostname to IP; 0 RTT cached, ~tens of ms cold recursive lookup)
  TCP  -> (1 RTT handshake: SYN, SYN-ACK, ACK)
  TLS  -> (1 RTT under TLS 1.3, 0-RTT if resumed w/ replay caveat; was 2 RTT under 1.2)
  HTTP -> (1.1: 1 req/conn, needs 6-8 parallel conns to compensate
           2.0: multiplexed streams/1 conn, but TCP-wide HOL blocking on packet loss
           3.0: multiplexed streams/1 QUIC-over-UDP conn, PER-STREAM loss recovery)
```

The throughline: every layer up through TCP is about **reliable delivery of an ordered byte stream**; every layer above it is about **how many independent logical things get to share that one connection**, and how badly a single lost packet punishes all of them.

---

## How it actually works

### NIC to socket: the kernel receive path, with real mechanics

A frame arrives on the wire; the NIC DMAs it directly into a pre-allocated RX ring buffer in host RAM (no CPU involvement for the copy itself) and raises a hardware interrupt. Under low traffic, a hardIRQ-per-packet model is fine — but under high packet rates (tens of thousands of packets/sec or more), interrupting the CPU for every single packet would spend more cycles context-switching into interrupt handlers than doing useful work, a phenomenon literally called a "receive livelock." **NAPI (New API, merged in kernel 2.6, still the model today)** is the fix: the first packet triggers a real hardIRQ, but the hardIRQ handler does almost nothing except disable further interrupts from that device and schedule a softIRQ (`NET_RX_SOFTIRQ`); the softIRQ handler (running in `ksoftirqd` or inline) then **polls** the device's ring buffer in a loop, draining up to a configurable `budget` (default 64) packets per pass before yielding the CPU back, and only re-enables hardware interrupts once the ring is drained below a threshold. This converts a per-packet-interrupt cost into an amortized, batched cost — the single most important optimization making modern multi-gigabit packet rates survivable on general-purpose CPUs. Many NICs additionally support **interrupt coalescing** (`ethtool -c`), delaying the interrupt until either a timeout (`rx-usecs`) or a packet count (`rx-frames`) is reached, trading a small amount of added latency for a large reduction in interrupt rate under sustained load — a real, tunable production lever, and a common cause of "why does this NIC add a few hundred microseconds of jitter under load" investigations when coalescing settings are more aggressive than a latency-sensitive workload can tolerate.

From the ring buffer, the driver builds an `sk_buff` (skb, the kernel's packet data structure) and hands it up through `netif_receive_skb()`, which may first pass it through **GRO (Generic Receive Offload)** — coalescing multiple physically-received TCP segments that are part of the same logical stream into one larger skb before handing it to the IP layer, reducing the per-segment processing cost further up the stack. From there: `ip_rcv()` (IP layer, routing/reassembly decisions) → `tcp_v4_rcv()` (TCP layer: sequence number validation, ACK generation, reassembly per the TCP-deep module's state machine) → the data lands in the destination socket's receive buffer, and `sock_def_readable()` wakes any process blocked in `recv()` or registered via `epoll`/`io_uring` waiting on that socket. This is precisely the boundary where the io-models module's discussion of epoll/io_uring picks up — everything below the socket receive queue is what this module covers, everything above it is how your application gets notified and reads the bytes.

### TLS: what the handshake actually buys, and its real RTT cost

TLS 1.2's full handshake required 2 round trips before any application data could be sent: ClientHello → ServerHello+certificate+key exchange → client key exchange+Finished → server Finished, and only then could the first HTTP request go out. TLS 1.3 (RFC 8446, 2018) restructured the handshake to 1 RTT by having the client guess the server's preferred key-exchange group and send its key share in the *first* flight (ClientHello + key share), letting the server respond with everything needed (ServerHello, certificate, Finished) in one flight back — application data can follow immediately after. **Session resumption with 0-RTT** goes further for repeat connections to a server you've talked to recently: the client can send encrypted application data in its very first flight, using a previously-established session ticket/PSK — but this data has no forward-secrecy-equivalent replay protection for that first flight specifically (an attacker who captures and replays the 0-RTT flight can potentially cause the server to process it twice), which is exactly why production deployments (browsers, CDNs) restrict 0-RTT to idempotent requests (typically GET) or disable it outright for anything with a side effect.

### HTTP/1.1 vs 2 vs 3: what changed and what didn't

HTTP/1.1's fundamental limitation is one in-flight request per connection at a time (pipelining exists in the spec but is essentially unused in practice due to head-of-line blocking at the application layer plus historically broken proxy implementations) — browsers compensate with 6-8 parallel connections per origin, each paying its own TCP + TLS handshake cost, and each competing independently for bandwidth (meaning TCP congestion control's fairness assumptions get distorted by running 6-8 flows to the same destination instead of one). HTTP/2 fixes the application-layer multiplexing problem directly: many logical streams share one TCP connection via a binary framing layer, with each frame tagged by stream ID, so the server can interleave responses instead of strictly serializing them, plus HPACK header compression removes a genuinely significant amount of redundant per-request byte overhead (cookies and standard headers repeated on every request compress extremely well across a connection's lifetime). But because it's still one TCP connection, TCP's connection-wide ordering guarantee means a single lost packet — however small — stalls delivery of every stream's data behind it in the TCP receive buffer until retransmission completes, even though logically those streams have nothing to do with each other. This is TCP-level head-of-line blocking, and it's the single most-cited HTTP/2 shortcoming that HTTP/3 was built to fix. HTTP/3 over QUIC restructures the transport itself: QUIC multiplexes streams *below* the reliability layer, each with independent loss detection and retransmission, so a lost packet belonging to stream A's data only delays stream A — stream B's already-arrived data is delivered to the application immediately, no connection-wide stall. Reported benchmarks show HTTP/3 reducing page load time under lossy network conditions substantially versus HTTP/1.1 (roughly 3s → 0.8s in one widely cited comparison) and roughly 30% latency reduction specifically on mobile networks (Akamai, 2025) where packet loss and network switching are common — QUIC's benefits are disproportionately concentrated on exactly the lossy, mobile, high-latency conditions where TCP's assumptions strain hardest.

### DNS: the often-skipped first cost

Before any TCP handshake begins, the hostname must resolve to an IP address. A **cached** resolution (in the OS resolver cache, or the browser's own cache) costs effectively 0 extra RTT. A **cold** resolution walks a recursive chain — client's configured resolver (often the OS default or a public resolver like 1.1.1.1/8.8.8.8) queries the root, then the TLD server, then the authoritative nameserver, each potentially a full round trip if not already cached at that level — realistically adding tens of milliseconds on a cold lookup, and considerably more on a badly-configured or geographically distant resolver chain. This is exactly why DNS TTL tuning, DNS prefetching (`<link rel="dns-prefetch">`), and keeping connections alive to avoid repeat resolution are real, measurable levers in latency-sensitive services — and why a sudden latency regression correlating with a DNS provider's TTL or an expired cache entry is a real, recurring production incident category, distinct from anything happening in your application or even in TCP/TLS.

---

## Build it from scratch

The mechanically honest "build it from scratch" here is tracing an actual packet's path with tools that expose each layer, rather than writing a kernel network stack — that's not a reasonable from-scratch exercise, but instrumenting and observing every layer above is:

```bash
# untested sketch — observe every layer discussed above on a real request

# 1. DNS: cold vs warm resolution cost
time dig +noall +answer example.com                 # cold-ish (may hit resolver cache)
time dig +noall +answer example.com                  # warm, should be near-instant

# 2. TCP handshake + TLS handshake timing breakdown, per-phase
curl -w "dns:%{time_namelookup} tcp:%{time_connect} tls:%{time_appconnect} \
ttfb:%{time_starttransfer} total:%{time_total}\n" \
  -o /dev/null -s https://example.com

# 3. Watch the actual NAPI/softirq activity under load on the receiving host
watch -n1 'cat /proc/net/softnet_stat'   # column 2 = dropped packets (ring overflow)
ethtool -c eth0                           # current interrupt coalescing settings
ethtool -S eth0 | grep -i drop            # per-NIC drop counters

# 4. See which HTTP version was actually negotiated
curl -w "http_version:%{http_version}\n" -o /dev/null -s https://example.com
```

`curl -w`'s per-phase timing breakdown is the single most useful diagnostic habit from this module — it directly attributes latency to DNS, TCP connect, TLS handshake, or time-to-first-byte, which is exactly the layering this module teaches you to reason about. A fuller lab (packet capture with `tcpdump`/Wireshark correlated against these timings, and a minimal HTTP/1.1 vs HTTP/2 comparison against a local server) belongs in `labs/shell/11-networking-stack/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency includes a consistent extra ~100-300ms on a fraction of requests, correlates with new client IPs/cold caches | Cold DNS resolution or fresh TCP+TLS handshake (no connection reuse) | Ensure client libraries/load balancers reuse connections (keep-alive, connection pooling); check DNS TTL and resolver cache behavior; consider DNS prefetching for known upcoming hosts |
| Server CPU spikes and packet drops appear under traffic bursts, `cat /proc/net/softnet_stat` shows rising drop column | RX ring buffer overflow — NAPI budget or ring size too small for the burst rate, or interrupt coalescing tuned for throughput at the cost of burst absorption | Increase ring buffer size (`ethtool -G`), tune NAPI `budget`/`netdev_budget`, review `rx-usecs`/`rx-frames` coalescing settings against the actual traffic pattern |
| HTTP/2 service shows unexpectedly high tail latency specifically on lossy client networks (mobile, poor WiFi) versus HTTP/1.1 with multiple connections | TCP head-of-line blocking: one lost packet stalls every multiplexed stream on that single HTTP/2 connection, whereas HTTP/1.1's parallel connections isolate the stall to just one of several | Enable HTTP/3/QUIC where client and server support it — its per-stream loss recovery specifically targets this scenario; this is the textbook case QUIC exists to fix |
| A latency-sensitive internal service pays a full TLS handshake on every request despite talking to the same backend repeatedly | Client library not reusing TLS sessions/connections, or a load balancer terminating and re-establishing TLS per request without session resumption | Enable/verify TLS session resumption (session tickets or PSK) and connection pooling; measure with `curl -w` per-phase timing to confirm the handshake cost is actually being paid repeatedly |
| A CDN/edge deployment enables 0-RTT and later discovers duplicate side-effecting requests under replay | 0-RTT data has no protection against an attacker (or a buggy retry mechanism) replaying the first flight | Restrict 0-RTT to idempotent requests (GET) only, or disable 0-RTT for any endpoint with side effects |
| Long-lived streaming/interactive connection drops when a mobile client switches from WiFi to cellular | TCP identifies a connection by the 4-tuple (src/dst IP:port); an IP change breaks that identity entirely, forcing a full reconnect | Use QUIC/HTTP-3 where the client/server support it — QUIC's connection ID survives an IP change natively, a capability TCP structurally cannot retrofit |

---

## Tradeoffs & when NOT to use it

- **Don't assume HTTP/3/QUIC is a strict upgrade for every service.** Its userspace implementation currently costs more server-side CPU per byte than TCP's decades-optimized, often hardware-offloaded kernel path in many deployments — for a CPU-bound, low-latency-loss internal service (same datacenter, reliable network), the head-of-line-blocking elimination QUIC provides may not be worth the CPU cost versus a well-tuned HTTP/2-over-TCP setup.
- **Don't enable TLS 0-RTT by default without auditing which endpoints it applies to.** The replay-protection gap is a real, exploitable property, not a theoretical footnote — restricting it to idempotent operations is a deliberate design decision, not an afterthought.
- **Don't tune interrupt coalescing purely for throughput on a latency-sensitive service.** Aggressive coalescing (`rx-usecs` batching packets before interrupting) improves throughput and CPU efficiency under sustained load but adds real, measurable per-packet latency and jitter — the right setting depends entirely on whether the workload prioritizes throughput or tail latency, and it's a real, per-service tuning decision, not a global default.
- **Don't blame "the network" before checking which layer actually added the latency.** `curl -w`'s phase breakdown (DNS/connect/TLS/TTFB) takes seconds to run and immediately tells you whether you're looking at a DNS problem, a handshake problem, or an actual application/backend problem — guessing wastes far more time than measuring.
- **Don't assume HTTP/2 multiplexing eliminates the value of connection pooling/keep-alive.** It reduces the *number* of connections needed, but a fresh HTTP/2 connection still pays the full TCP+TLS handshake cost once; reusing that one connection across requests is still essential, just at a 1-connection-per-origin scale instead of 6-8.

---

## Interview questions

### Q1 — Walk a packet from the wire to your application's `recv()` call.
**Testing:** whether the full kernel receive path is understood as discrete, named stages, not "the kernel handles it."
**Answer:** NIC DMAs the frame into an RX ring buffer in RAM and raises a hardIRQ; the hardIRQ handler does minimal work and schedules a softIRQ; NAPI's poll routine (running in softirq context) drains the ring buffer in batches (default budget 64 packets) instead of interrupting per-packet; the driver builds an skb and passes it up through `netif_receive_skb()` → `ip_rcv()` → `tcp_v4_rcv()` into the destination socket's receive queue, which wakes a blocked `recv()`/`epoll_wait()` call in the application.
**Follow-up trap:** *"Why not just interrupt the CPU for every packet — wouldn't that be lower latency?"* — at low packet rates it would be marginally lower latency, but at high rates it causes a receive livelock: the CPU spends more time context-switching into interrupt handlers than doing useful packet processing, which is exactly the failure mode NAPI's batched-polling design exists to prevent.

### Q2 — What does interrupt coalescing trade off, and when would you tune it differently?
**Testing:** whether a real, tunable production knob is understood as a genuine tradeoff, not a "just enable it" checkbox.
**Answer:** `ethtool -c` settings like `rx-usecs`/`rx-frames` delay the hardware interrupt until either a timeout or a packet-count threshold is hit, batching more work per interrupt and reducing CPU interrupt overhead under sustained high-throughput load — at the cost of added per-packet latency and jitter, since the first packet in a coalescing window waits for the batch to fill or the timer to fire. A throughput-oriented bulk-transfer service benefits from aggressive coalescing; a latency-sensitive service (trading systems, real-time interactive workloads) often wants coalescing tuned down or disabled.
**Follow-up trap:** *"Would you expect this to show up in application-level metrics or infrastructure metrics?"* — it typically shows up as unexplained jitter/tail latency at the network layer that application-level tracing won't directly attribute — you'd need `ethtool -c`/`-S` and NIC-level counters to actually see it, which is why it's a commonly missed cause of "mystery" latency variance.

### Q3 — What actually changed between TLS 1.2 and TLS 1.3's handshake, in round trips?
**Testing:** concrete RTT numbers, not just "TLS 1.3 is faster."
**Answer:** TLS 1.2's full handshake required 2 round trips before application data could be sent. TLS 1.3 restructured the handshake so the client sends its key share speculatively in the first flight (ClientHello + key share), letting the server respond with everything needed in one flight back — cutting the full handshake to 1 RTT, plus an optional 0-RTT resumption mode for repeat connections using a previously established session ticket/PSK.
**Follow-up trap:** *"What's the catch with 0-RTT?"* — the first flight of 0-RTT application data has no protection against replay; an attacker capturing and resending it can cause the server to process it twice, which is why production deployments restrict 0-RTT to idempotent requests (GET) or disable it for anything with a side effect.

### Q4 — Explain "TCP head-of-line blocking" in HTTP/2, precisely — what guarantee is actually causing it?
**Testing:** whether the candidate can name the exact mechanism rather than repeating the phrase.
**Answer:** TCP guarantees strictly ordered, reliable delivery for the entire connection as a single byte stream — it has no concept of independent "streams" at all; HTTP/2's multiplexed streams are an application-layer abstraction layered on top of that single ordered stream. So if a packet carrying stream A's bytes is lost, TCP will not deliver any later-arriving bytes to the application — including unrelated stream B's already-arrived data — until the lost segment is retransmitted and the connection's byte order is restored, even though logically stream B has nothing to do with stream A's loss.
**Follow-up trap:** *"Why can't you just fix this by having HTTP/2 use multiple TCP connections again, like HTTP/1.1 did?"* — you could, and it would reduce the blast radius, but you'd reintroduce the multiple-handshake-cost problem HTTP/2 was built to eliminate, and you'd lose HPACK's connection-lifetime header compression efficiency; QUIC's actual fix is moving multiplexing *below* the reliability layer within a single connection, not multiplying connections.

### Q5 — How does QUIC solve TCP head-of-line blocking, mechanically?
**Testing:** the structural difference between QUIC and "HTTP/2 but faster."
**Answer:** QUIC implements its own reliability and loss-recovery in userspace over UDP, with independent per-stream sequencing rather than one connection-wide ordered byte stream. A lost packet belonging to stream A is detected and retransmitted independently, and stream B's already-arrived, already-in-order data is delivered to the application immediately — no connection-wide stall, because there's no single connection-wide ordering guarantee to violate in the first place.
**Follow-up trap:** *"Does that mean QUIC is strictly better and TCP is obsolete?"* — no; QUIC's userspace implementation currently costs meaningfully more server-side CPU per byte in many deployments than TCP's decades-optimized, often hardware-offloaded kernel path, so for CPU-bound services on reliable, low-loss networks (same-datacenter internal RPC), the head-of-line-blocking fix may not be worth the CPU tradeoff — this is a genuinely live, unresolved-in-general tradeoff, not settled.

### Q6 — Why do browsers open 6-8 parallel connections per origin under HTTP/1.1, and what did that cost?
**Testing:** understanding the practical workaround HTTP/1.1's limitation forced, and its side effects.
**Answer:** HTTP/1.1 allows only one request in flight per connection at a time in practice (pipelining is spec-legal but essentially unused due to head-of-line blocking and broken intermediary support), so browsers compensate by opening multiple parallel TCP connections to the same origin to get real request parallelism. The cost: each connection pays its own TCP handshake and (over HTTPS) its own TLS handshake, multiplying that fixed cost by 6-8x per origin, and running that many concurrent flows to one destination distorts TCP's per-connection congestion-control fairness assumptions.
**Follow-up trap:** *"Does HTTP/2 eliminate the need for connection reuse/keep-alive entirely?"* — no; it reduces connection *count* to roughly one per origin, but that one connection still needs its handshake cost amortized across many requests via keep-alive/reuse — the optimization moves from "reduce per-connection overhead by parallelizing" to "reduce total connection count," not "eliminate the need to reuse connections."

### Q7 — A service's p99 latency has a consistent extra 150ms that doesn't show up in application tracing. What layers would you check, in order, and how?
**Testing:** the diagnostic discipline of attributing latency to the correct layer with real tools.
**Answer:** Use `curl -w` (or equivalent per-phase timing in the actual client) to split total latency into DNS resolution, TCP connect, TLS handshake, and time-to-first-byte — this immediately tells you which layer the 150ms belongs to. If it's DNS: check resolver cache/TTL behavior. If it's TCP/TLS connect: check whether connections are being reused (keep-alive/pooling) or re-established per request. If it's TTFB after a fast connect: the problem is likely genuinely in the application/backend, not the network stack this module covers.
**Follow-up trap:** *"What if the 150ms only appears intermittently, not on every request?"* — that pattern points more toward cold-cache/cold-connection events (a connection pool exhausting and opening a fresh connection, a DNS TTL expiring) rather than a constant per-request cost, so you'd specifically want to correlate the spikes against connection-pool/DNS-cache metrics rather than assuming a uniform per-request overhead.

### Q8 — What is GRO (Generic Receive Offload) and why does it matter for CPU efficiency?
**Testing:** a specific, less commonly known kernel networking optimization.
**Answer:** GRO coalesces multiple physically-received TCP segments that belong to the same logical stream into a single larger skb before handing it up to the IP/TCP processing layers, reducing the number of times the more expensive upper-layer processing (IP routing decisions, TCP sequence validation) has to run per byte of actual data received — it's an amortization technique similar in spirit to NAPI's batched interrupt handling, but applied to per-segment processing cost rather than interrupt cost.
**Follow-up trap:** *"Does GRO change what the application sees?"* — no, it's purely a kernel-internal processing optimization; the application still sees the same ordered byte stream via `recv()`, GRO just reduces the CPU cost of getting bytes there, which is why it's safe to enable broadly and is on by default on most modern NIC drivers.

### Q9 — Design question: you're building a mobile app backend where clients frequently switch between WiFi and cellular mid-session. What protocol-level design choice directly addresses this, and why can't TCP do it?
**Testing:** applying QUIC's connection-migration property to a concrete, realistic scenario, and understanding *why* TCP structurally can't match it.
**Answer:** Use HTTP/3/QUIC. TCP identifies a connection by the 4-tuple (source IP:port, destination IP:port) — when a mobile client's IP address changes (WiFi to cellular handoff), that identity is broken entirely and the connection must be fully re-established, including a new handshake. QUIC identifies a connection by a connection ID independent of IP address, so it can survive an IP change with the same live connection state (no full reconnect, no lost in-flight streams), a property TCP cannot retrofit without literally changing what a "connection" means at the protocol level.
**Follow-up trap:** *"Is this purely a QUIC feature, or does something have to be designed into your application to benefit from it?"* — the client and server both need QUIC support (increasingly standard in mobile OS networking stacks and CDNs), and the application needs to actually be using HTTP/3 rather than falling back to HTTP/2 — many deployments negotiate HTTP/3 opportunistically (via Alt-Svc) with an HTTP/2 fallback, so verifying which protocol actually got negotiated (via `curl -w "%{http_version}"` or equivalent) matters before assuming the migration benefit is in effect.

### Q10 — What's the mechanical difference between HPACK (HTTP/2) header compression and just gzipping headers?
**Testing:** whether the specific compression mechanism, not just "headers are compressed," is understood.
**Answer:** HPACK maintains a stateful, shared dynamic table between client and server across the *lifetime of the connection* — a header sent once can be referenced by a short index on subsequent requests rather than resent at all, plus a static table of common header name/value pairs indexed from the spec. This is fundamentally different from stateless per-message compression (gzip on each header block independently), which can't exploit cross-request redundancy the way a connection-lifetime shared table can, and per-message gzip on headers was in fact explicitly avoided in HTTP/2's design because it enabled the CRIME/BREACH-style compression side-channel attacks against TLS-protected data.
**Follow-up trap:** *"Why does that security concern (CRIME/BREACH) matter specifically for header compression and not body compression?"* — compression ratio leaks information about whether attacker-controlled and secret data share substrings when both are compressed together in a way an attacker can probe repeatedly (e.g., injecting guesses via a controlled request field and observing compressed size); HPACK's design specifically avoids compressing attacker-influenceable and secret values together in a way that leaks that signal, which was a deliberate lesson learned from earlier compression-based TLS attacks.

### Q11 — Your team is deciding whether to migrate an internal, same-datacenter microservice mesh from HTTP/2 to HTTP/3. Make the case for and against.
**Testing:** staff-level judgment weighing a real, currently-live tradeoff rather than reflexively recommending "the newer protocol."
**Answer:** For: eliminates TCP-level head-of-line blocking entirely, and QUIC's built-in connection migration is a genuine robustness win if any mesh traffic crosses network boundaries with IP changes (rare internally, but real for hybrid/multi-region setups). Against: internal, same-datacenter traffic typically has very low packet loss and very low latency already, meaning the head-of-line-blocking problem QUIC solves barely manifests in this environment, while QUIC's userspace implementation cost (more CPU per byte than TCP's kernel-optimized, often hardware-offloaded path) is a real, immediate tax on every service in the mesh — for a low-loss, high-request-volume internal mesh, that tradeoff frequently favors staying on HTTP/2-over-TCP, reserving HTTP/3 for the actual internet-facing edge where loss and mobile network variability are real and constant.
**Follow-up trap:** *"What would change your recommendation?"* — evidence of actual measured packet loss or connection-migration events within the mesh (cross-region hops, unreliable network segments), or kernel/NIC-level QUIC offload maturing enough to close the CPU-cost gap — naming the specific conditions that would flip the decision is the senior signal, not picking a permanent side.

---

## Red flags that fail you

- Saying "the network is slow" without using any tool (`curl -w`, tcpdump) to attribute latency to a specific layer.
- Claiming HTTP/2 eliminates head-of-line blocking (it eliminates *application-layer* HOL blocking, not TCP-level).
- Claiming HTTP/3/QUIC is unconditionally faster with no mention of its server-side CPU cost tradeoff.
- Not knowing that TLS 0-RTT has a replay-protection gap.
- Describing NAPI/interrupt handling as "the kernel just processes packets" with no mention of the hardIRQ/softIRQ split or why per-packet interrupts don't scale.
- Confusing DNS resolution cost with TCP/TLS handshake cost when diagnosing latency.

---

## Cheat card

```
RECEIVE PATH: NIC DMA -> RX ring buffer -> hardIRQ (minimal, schedules softirq)
  -> NAPI poll (softirq/ksoftirqd, budget=64 pkts/pass, avoids interrupt storm)
  -> skb -> GRO (coalesce same-stream segments) -> netif_receive_skb()
  -> ip_rcv() -> tcp_v4_rcv() -> socket recv queue -> wakes recv()/epoll_wait()
  interrupt coalescing (ethtool -c: rx-usecs/rx-frames): throughput vs latency knob

TLS: 1.2 = 2 RTT full handshake. 1.3 (RFC8446, 2018) = 1 RTT (key share in 1st
  flight). 0-RTT resumption: app data in 1st flight, NO replay protection ->
  restrict to idempotent (GET) requests only.

HTTP/1.1: 1 req in flight/conn (pipelining unused) -> browsers open 6-8 conns/
  origin, each pays own TCP+TLS handshake
HTTP/2 (2015, from SPDY): multiplex streams/1 conn + HPACK header compression
  (stateful shared table, NOT stateless gzip -- gzip on headers enabled
  CRIME/BREACH-style attacks) -- but TCP-wide HOL blocking: 1 lost pkt stalls
  ALL streams (TCP's ordering guarantee is connection-wide, not per-stream)
HTTP/3 (RFC9000, 2021, QUIC/UDP): per-stream loss recovery, NO connection-wide
  HOL stall. Connection ID (not 4-tuple) -> survives IP change (WiFi->cellular)
  Tradeoff: more server CPU/byte than TCP's kernel-optimized path (unresolved)
  Reported: ~30% mobile latency cut (Akamai 2025); ~3s->0.8s lossy-net pageload

DNS: cached = ~0 extra RTT. cold recursive = tens of ms (root->TLD->auth chain)

DIAGNOSTIC: curl -w "dns:%{time_namelookup} tcp:%{time_connect} \
  tls:%{time_appconnect} ttfb:%{time_starttransfer}" -- attribute latency
  to the correct layer before guessing
```

## Sources

- [How a packet travels through Linux Kernel — Nishant, Medium](https://medium.com/@nishujangra27/how-a-packet-travels-through-linux-kernel-82787820cf9d) — accessed 2026-08-03
- [Tracing a Packet in the Linux Kernel: Wire to Socket — Meriah Abderrahim, Medium](https://medium.com/@m-ibrahim.research/tracing-a-packet-in-the-linux-kernel-wire-to-socket-part-4-bfaba725ddd1) — accessed 2026-08-03
- [Red Hat Enterprise Linux Network Performance Tuning Guide](https://access.redhat.com/sites/default/files/attachments/20150325_network_performance_tuning.pdf) — accessed 2026-08-03
- [HTTP/1.1 vs HTTP/2 vs HTTP/3: The Ultimate Performance Guide for 2025 — Medium](https://medium.com/@ntiinsd/http-1-1-vs-http-2-vs-http-3-the-ultimate-performance-guide-for-2025-670b1f1eabf5) — accessed 2026-08-03
- [HTTP/2 vs. HTTP/3 — Catchpoint/LogicMonitor](https://www.catchpoint.com/http3-vs-http2) — accessed 2026-08-03
- RFC 8446 — The Transport Layer Security (TLS) Protocol Version 1.3
- RFC 9000 — QUIC: A UDP-Based Multiplexed and Secure Transport

## Changelog
- 2026-08-03 — created
