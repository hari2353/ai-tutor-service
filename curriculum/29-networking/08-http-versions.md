# HTTP/1.1 vs HTTP/2 vs HTTP/3: Multiplexing, Head-of-Line Blocking, Server Push's Death

> **Track:** T29 Networking & Protocols · **Time:** 2h · **Prereqs:** T29-http-semantics, T29-tls · **Updated:** 2026-07-26
> **Module id:** `T29-http-versions` · **Tags:** http

## The 30-second version

HTTP/1.1 serializes responses on one TCP connection, so browsers work around head-of-line (HOL) blocking by opening 6 parallel connections per origin — expensive, and still blocking within each connection. HTTP/2 multiplexes many streams over a single TCP connection with binary framing and HPACK header compression, which kills the app-layer problem but exposes a worse one: TCP itself delivers bytes in order, so one lost segment stalls every multiplexed stream behind it, not just the one that owns the lost packet. HTTP/3 fixes that by dropping TCP entirely and running over QUIC (UDP), which gives each stream independent loss recovery and ordering — a lost packet only stalls its own stream. Server push, HTTP/2's other headline feature, is dead: Chrome disabled it by default in Chrome 106 (Oct 2022) because it couldn't know what the client had cached, wasted bandwidth pushing already-cached assets in practice, and has been superseded by 103 Early Hints for the one use case (early resource discovery) that actually mattered.

## Why this gets asked

Every candidate can recite "HTTP/2 has multiplexing." Almost nobody can explain why a multiplexed connection over a lossy WiFi or cellular network can be *slower* than six HTTP/1.1 connections — because that's a real production incident someone has debugged: p99 latency cratering on mobile networks after an HTTP/2 migration, traced to 1-2% packet loss stalling every request on the connection. The interviewer is checking whether you understand that HTTP/2 moved the HOL blocking problem down a layer rather than solving it, and whether you know what QUIC actually changed structurally (not just "it's UDP, so it's faster").

---

## Lineage: past → present → future

**What came before.** HTTP/1.0 opened a new TCP connection per request — three-way handshake plus (post-1994) TLS handshake, per resource, on a page that might reference 80 objects. HTTP/1.1 (RFC 2068, 1997) added persistent connections (`Connection: keep-alive`) so the TCP/TLS setup cost was paid once per connection instead of once per request, and it defined pipelining — send request 2 before response 1 arrives — as an optional optimization. Pipelining never became viable: responses still had to return in request order (the spec requires it), so one slow response head-of-line-blocked every response queued behind it, and a nontrivial fraction of middleboxes and servers on the real internet mishandled pipelined requests outright — some proxies would return responses out of order or merge them incorrectly. Firefox shipped pipelining disabled by default from the start and pulled the code entirely in Firefox 54 (2017); no other major browser ever enabled it by default. The workaround that actually shipped was parallelism: browsers opened 6 TCP connections per origin (Chrome, Firefox; historically some browsers used 2, IE8 used 6-8), each independently serialized but not blocking each other. That's expensive — 6× the TCP handshakes, 6× the TLS handshakes, 6× the slow-start penalty — and it only kicks the can: within any one of those 6 connections, HOL blocking is still there.

**Where it stands now.** HTTP/2 (RFC 7540, 2015, derived from Google's SPDY) solved the *application-layer* HOL problem by introducing a binary framing layer: a single TCP connection carries many independent streams, each request/response broken into HEADERS and DATA frames tagged with a stream ID, interleaved and reassembled by the receiver. One slow response no longer blocks a fast one at the HTTP layer. It also added HPACK (RFC 7541) header compression, which matters more than it sounds: modern requests carry large, highly repetitive headers (cookies, auth bearer tokens, user-agent, accept-* negotiation) on every single request, and HPACK's static table (61 predefined common header fields) plus a per-connection dynamic table (default 4096 bytes) mean repeated headers are sent as a couple of bytes referencing a table entry rather than the full string every time. But HTTP/2 runs on TCP, and TCP guarantees in-order byte delivery on the connection as a whole — it has no concept of "stream" at all, that's an HTTP-layer construct built on top. So when one TCP segment is lost, the kernel withholds *everything* after it from the application until retransmission completes and the gap is filled, even though the withheld bytes belong to streams that have nothing to do with the lost packet. This is called **transport-layer HOL blocking**, and it's the real, current, live gotcha in HTTP/2 deployments on lossy networks (cellular, congested WiFi, satellite). It is genuinely worse in some conditions than HTTP/1.1's 6 parallel connections, because a lost packet on any one HTTP/1.1 connection only stalls that connection's own request, not five others sharing it. This is exactly why HTTP/3 exists, and it's not a hypothetical: production telemetry from CDNs on mobile networks with 1-3% loss consistently shows this pattern.

**Where it's heading.** HTTP/3 (RFC 9114, 2022) runs over QUIC (RFC 9000, 2021) instead of TCP. QUIC is built on UDP but reimplements TCP's reliability, congestion control, and — critically — stream multiplexing *inside* QUIC itself rather than as an HTTP-layer overlay. Each QUIC stream has its own delivery ordering and loss-recovery state; a lost UDP packet carrying data for stream 7 only stalls stream 7, streams 1-6 and 8+ keep delivering. QUIC also folds the TLS 1.3 handshake into its own handshake (1-RTT for a new connection versus TCP+TLS 1.3's minimum 2 RTT, with 0-RTT resumption for repeat connections), and it decouples the connection identity from the (IP, port) tuple via connection IDs, so a client switching from WiFi to cellular can keep the same QUIC connection without a fresh handshake — TCP can't do that at all. Adoption is real, not speculative: HTTP/3 was used by roughly two-thirds of Chrome's HTTPS requests by the mid-2020s and is the default at every major CDN. The reason TCP couldn't just be patched to fix HOL blocking is protocol ossification — TCP is implemented in kernels and middleboxes across the entire internet, and evolving it requires deploying new kernels everywhere; QUIC sidesteps this by encrypting almost the entire packet (including most header fields) so middleboxes can't meddle with it, which is also why QUIC was designed as a userspace library rather than a kernel protocol. The open question is less "will HTTP/3 win" (it already has, for the parts of the stack that matter) and more how quickly enterprise middleboxes, corporate proxies, and some load balancers catch up — UDP-based protocols still get blocked or throttled on some corporate networks, which is why clients must fall back to HTTP/2 gracefully (via `Alt-Svc` advertisement, not a hard requirement).

---

## Mental model

```
HTTP/1.1  (6 connections, each serialized)
  conn1: [-- req A response --][-- req D response --]
  conn2: [-- req B response --]
  conn3: [-- req C response --]
  app-layer HOL blocking WITHIN each connection; parallelism hides it across 6

HTTP/2  (1 TCP connection, N multiplexed streams)
  TCP:   [S1|S2|S1|S3|S1|S2|S3|S2|...] one ordered byte stream
                    ▲
                    one lost segment here stalls S1, S2 AND S3
                    even though only S1's data was actually lost
  app-layer HOL: SOLVED (streams interleave freely)
  transport-layer HOL: NOT solved (TCP delivers in order, no exceptions)

HTTP/3  (1 QUIC connection over UDP, N independent streams)
  UDP:   [S1 pkt|S2 pkt|S1 pkt|S3 pkt|...] each stream has its OWN
                    ▲              sequence space and own loss recovery
                    lost S1 packet stalls ONLY S1; S2, S3 keep flowing
  app-layer HOL: solved · transport-layer HOL: solved
```

The one sentence that survives any follow-up: **HTTP/2 moved HOL blocking from the application layer to the transport layer; it didn't eliminate it. HTTP/3 eliminates it at both layers by making streams a transport-native concept.**

---

## How it actually works

### HTTP/1.1: keep-alive, pipelining's death, and the 6-connection workaround

Persistent connections (default in 1.1, opt-in via `Connection: keep-alive` in 1.0) amortize the TCP handshake (1 RTT) and TLS handshake (1-2 RTT depending on TLS version and resumption) across multiple requests instead of paying them per-request. Pipelining would have let a client send request 2 without waiting for response 1, but the spec still requires responses to come back **in the same order the requests were sent** — so if request 1 hits a slow endpoint, request 2's already-computed response sits in a server-side queue behind it. Combined with real-world middlebox bugs (transparent proxies that buffered, reordered, or corrupted pipelined responses), no browser shipped it enabled by default, and it was formally abandoned. The workaround was brute-force parallelism: 6 TCP connections per origin, each independently serialized. Cost: 6× connection setup, 6× TLS handshakes, 6× slow-start ramp-up (each new TCP connection starts at a small congestion window, typically 10 segments per RFC 6928, and takes several RTTs to ramp up), and 6× the server-side resources (sockets, TLS session state) per client. Domain sharding (splitting assets across `img1.example.com`, `img2.example.com`) was a common trick to multiply this past 6 — and it's precisely the anti-pattern HTTP/2 made obsolete, because with real multiplexing you want *fewer* connections, not more.

### HTTP/2: binary framing, streams, and HPACK

Every HTTP/2 message is broken into frames on a single connection: a HEADERS frame (compressed request/response headers) and one or more DATA frames (body), each tagged with a 31-bit stream ID. Odd stream IDs are client-initiated, even are server-initiated (for the now-dead push). The receiver demultiplexes by stream ID and reassembles. `SETTINGS_MAX_CONCURRENT_STREAMS` caps how many streams can be open at once — servers commonly default to 100 — and stream prioritization (a weighted dependency tree) lets a client hint which responses matter more, though most real deployments barely use it.

HPACK compresses headers using two tables: a **static table** of 61 common header field name/value pairs baked into the spec (`:method: GET`, `:status: 200`, etc.) referenced by index, and a per-connection **dynamic table** (default max size 4096 bytes, negotiable) that both sides populate as headers are actually sent, so a repeated `cookie` or `authorization: Bearer <token>` header — often several hundred bytes — gets sent once in full and referenced by a 1-2 byte index on every subsequent request on that connection. This matters more than it sounds: a typical API client sends the same auth header and several other stable headers on every call, and over a connection carrying hundreds of requests, HPACK turns kilobytes of redundant header bytes into a handful of index references.

### HTTP/2's HOL blocking gotcha, concretely

TCP has no concept of "this segment belongs to stream 3." It is one ordered byte stream. If the OS's TCP stack is holding back bytes 50,000-60,000 waiting for a retransmit, and those bytes happen to be a small piece of stream 3's data, the application layer cannot deliver *any* buffered bytes past that gap — including fully-arrived, complete frames for streams 1, 2, and 4 that are sitting later in the TCP receive buffer. This is why HTTP/2 over a network with even modest loss (1-3%, common on cellular) can underperform HTTP/1.1's 6 connections: losing a packet on connection 3 of 6 only stalls connection 3; losing a packet on the single HTTP/2 connection stalls everything.

### Why server push died

Server push let a server proactively send a response the client hadn't asked for yet (`PUSH_PROMISE` frame, e.g., push `style.css` alongside `index.html` before the browser parses the HTML and requests it). It sounded good and worked badly in practice for one structural reason: **the server cannot know what the client already has cached.** A naive push implementation re-pushes assets the browser already has, wasting bandwidth on every single page load rather than saving a round trip — and empirically, this is what happened at scale. Chrome's own telemetry showed push was used by a small fraction of sites and, where used, frequently hurt rather than helped. Chrome announced removal in an Intent to Deprecate (2022) and disabled it by default starting in Chrome 106 (October 2022); other browsers and CDNs largely followed. The actual replacement for push's one legitimate use case — hinting resources early so the client can start fetching them before the full response is ready — is **103 Early Hints** (RFC 8297): the server sends an informational 103 response with `Link: <style.css>; rel=preload` headers while it's still computing the real response, and the client can start the resource fetch immediately over its own connection, respecting its own cache state. It gets most of the latency win without the cache-pollution failure mode.

---

## Build it from scratch

You won't hand-roll HTTP/2 framing in an interview, but you should be able to demonstrate the layer-by-layer HOL difference concretely:

```python
# untested sketch — demonstrates the difference in observed behavior,
# not a protocol implementation
import socket, ssl, time

# HTTP/1.1: 6 connections, request in parallel, each independently blocking
def fetch_h1_parallel(host, paths, n_conns=6):
    import concurrent.futures
    def one(path):
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443)) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                tls.send(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
                return tls.recv(65536)
    with concurrent.futures.ThreadPoolExecutor(n_conns) as pool:
        return list(pool.map(one, paths))

# HTTP/2: use httpx or hyper-h2 to open ONE connection and issue
# concurrent streams — the point is to show that a single packet drop
# injected via `tc qdisc add ... loss 3%` stalls all of them together,
# which you cannot show without a real network-loss test harness (Toxiproxy
# or `tc netem` on Linux). This is the demo worth describing in an interview
# even if you don't have the harness in front of you.
```

The realistic lab exercise: run `tc qdisc add dev eth0 root netem loss 2%` (Linux) against a local HTTP/2 server serving N concurrent large responses, and compare total page load time against the same content over 6 HTTP/1.1 connections. That's the experiment that makes the transport-HOL claim undeniable rather than theoretical.

---

## How it's done in production

Nginx, Envoy, and every major CDN (Cloudflare, Fastly, Akamai) negotiate HTTP version via **ALPN** during the TLS handshake (the client advertises `h2`, `http/1.1`; for HTTP/3 the server advertises support via an `Alt-Svc: h3=":443"` response header on an HTTP/1.1 or HTTP/2 response, since QUIC needs its own UDP-based discovery path — there's no ALPN-equivalent for the initial connection, the client has to already be talking some HTTP version first, or try QUIC speculatively). Browsers cache which origins support h3 and try QUIC directly on the next visit.

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency spikes on mobile/cellular after HTTP/2 rollout, but not on wired | Transport-layer HOL blocking: packet loss on one stream stalls the shared TCP connection | Enable HTTP/3 (QUIC) so loss recovery is per-stream; verify via `Alt-Svc` and QUIC negotiation logs |
| Server push configured but pages load slower | Push re-sends assets already in browser cache; wastes bandwidth and delays the actually-needed response | Remove push; use 103 Early Hints or `<link rel="preload">` |
| Corporate/enterprise clients never negotiate h3 | UDP blocked or throttled by a corporate firewall/proxy | Ensure clean fallback to h2/h1.1 over TCP; don't assume h3 universally reachable |
| Connection-per-origin count still very high in HAR waterfall despite h2 enabled | Domain sharding left over from an HTTP/1.1-era optimization | Consolidate to fewer origins; sharding actively hurts h2 (defeats single-connection multiplexing and HPACK's shared dynamic table) |
| HPACK dynamic table thrashing — headers not shrinking despite repetition | Table size negotiated too small, or connections cycling too fast to build table state | Increase `SETTINGS_HEADER_TABLE_SIZE`; keep connections warm/reused |
| gRPC or other h2-only service silently falls back to failing rather than degrading | Client speaks h1.1 only; server requires h2 (see T29-grpc) | Detect ALPN negotiation failure explicitly; don't assume h2 is universally available end-to-end (some middleboxes still strip it) |

---

## Tradeoffs & when NOT to use it

- **Don't blame "HTTP/2 is slow" without checking packet loss first.** On a clean network HTTP/2 is a strict win over HTTP/1.1; on lossy mobile networks it can genuinely be worse, and the fix is HTTP/3, not reverting to HTTP/1.1.
- **Don't keep domain sharding under HTTP/2/3.** It was a defensible HTTP/1.1 hack; under HTTP/2 it fragments HPACK's shared compression state and gives you more, not fewer, TCP handshakes and slow-start penalties.
- **Don't add server push to a new design in 2026.** It's disabled by default in the dominant browser and offers no benefit that 103 Early Hints or `<link rel=preload>` doesn't already cover more safely.
- **HTTP/3 isn't free.** QUIC's per-packet crypto overhead and userspace implementation (versus TCP's kernel-optimized, often hardware-offloaded path) can mean higher CPU cost per connection on the server for very high-throughput internal services — which is one reason gRPC's internal service-to-service traffic still runs mostly on HTTP/2 rather than racing to HTTP/3, and why some CDNs still primarily route origin-to-CDN traffic over HTTP/2 while using HTTP/3 only client-facing.
- **UDP can be actively blocked.** Some enterprise networks and captive portals block or heavily throttle non-standard UDP traffic; don't assume HTTP/3 reachability without a fallback path, and don't make HTTP/3 a hard dependency for a public-facing service.

---

## Interview questions

### Q1 — What problem does HTTP/2 multiplexing actually solve, and what does it not solve?
**Testing:** whether you understand HOL blocking exists at multiple layers.
**Answer:** It solves application-layer HOL blocking: multiple requests/responses interleave as independent streams over one TCP connection instead of queuing behind each other. It does not solve transport-layer HOL blocking: TCP delivers bytes in order across the whole connection, so one lost segment stalls every stream's data sitting behind it in the TCP receive buffer, even streams unrelated to the loss.
**Follow-up trap:** *"So is HTTP/2 ever worse than HTTP/1.1?"* — yes, on lossy networks. Six independently-serialized HTTP/1.1 connections each stall independently on their own loss; one shared HTTP/2 connection stalls everything on any loss. This is a real, measured effect on cellular networks with 1-3% loss, not a theoretical footnote.

### Q2 — Why did HTTP/1.1 pipelining fail, mechanically?
**Testing:** whether you know the spec constraint, not just "it was buggy."
**Answer:** Responses must return in the same order requests were sent. A slow response head-of-line-blocks every faster response queued behind it on that connection, so pipelining only removed the *request*-side round trips, not the response-side blocking that actually caused perceived latency. Combined with widespread middlebox/proxy bugs that mishandled pipelined traffic, no major browser shipped it enabled.
**Follow-up trap:** *"Then how did browsers get parallelism before HTTP/2?"* — 6 parallel TCP connections per origin, each independently serialized (so still HOL-blocked within itself), at the cost of 6× handshake and slow-start overhead, sometimes multiplied further via domain sharding.

### Q3 — What does HPACK actually compress, and why does it matter more than people think?
**Answer:** A static table of 61 common header fields plus a per-connection dynamic table (default 4096 bytes) that both peers populate as headers are actually sent. Repeated headers — cookies, `authorization: Bearer <token>`, `user-agent` — get sent in full once and referenced by a small index afterward. It matters because real API traffic resends the same several-hundred-byte auth/cookie headers on every request; over a connection handling hundreds of requests, that's kilobytes saved per request, not a rounding error.
**Follow-up trap:** *"Does HPACK have a known attack surface?"* — yes, compression-oracle attacks (CRIME/BREACH-style) are a concern when compressed content includes attacker-influenced and secret data together; HPACK's design (no Huffman-of-arbitrary-bytes across trust boundaries mixing secrets) mitigates but doesn't eliminate this, which is why sensitive header values shouldn't be naively concatenated with attacker-controlled data in compressed contexts.

### Q4 — Why did HTTP/2 server push die?
**Answer:** It couldn't know what the client already had cached, so naive implementations re-pushed assets the browser already had, wasting bandwidth rather than saving a round trip — and that's what happened at scale, not a hypothetical. Chrome disabled it by default in Chrome 106 (October 2022) after its own data showed low adoption and no consistent performance win. The one legitimate use case, early resource hinting, is now served by 103 Early Hints, which lets the client decide what to fetch based on its own cache state.
**Follow-up trap:** *"Is `<link rel=preload>` the same thing?"* — no, that's a same-response hint the browser reads after receiving the HTML; 103 Early Hints delivers the hint *before* the full response is ready, closer to what push was trying to achieve, but without server-side cache blindness.

### Q5 — Why does HTTP/3 need a new transport (QUIC) instead of just patching TCP?
**Answer:** TCP is implemented in OS kernels and countless middleboxes across the internet; evolving its core semantics (like adding per-stream framing) requires deploying new behavior everywhere, which doesn't happen at internet scale — this is protocol ossification. QUIC sidesteps it by running over UDP (already universally passable, if sometimes rate-limited) and implementing its own reliability and multiplexing in encrypted userspace payload that middleboxes can't inspect or meddle with.
**Follow-up trap:** *"Doesn't running reliability in userspace cost more CPU than kernel TCP?"* — yes, per-packet crypto and the lack of hardware/kernel offload common for TCP means measurably higher CPU per connection on the server side, which is a real, cited reason some very high-throughput internal services stay on HTTP/2 rather than racing to adopt HTTP/3.

### Q6 — How does QUIC solve transport-layer HOL blocking?
**Answer:** Each QUIC stream has its own independent sequence space and loss-recovery/acknowledgment state, unlike TCP's single ordered byte stream for the whole connection. A lost UDP packet belongs to exactly one stream; only that stream stalls waiting for retransmission, while frames for other streams that already arrived are delivered to the application immediately.
**Follow-up trap:** *"Does this mean QUIC never blocks anything?"* — no, it just moves blocking to the correct granularity: the stream that actually lost data blocks, not the whole connection. If your application logic has cross-stream dependencies (stream B's processing waits on stream A's result), that's an application-level ordering choice, not something QUIC can fix.

### Q7 — What's the RTT cost difference for a fresh connection: HTTP/1.1+TLS 1.2, HTTP/2+TLS 1.3, HTTP/3?
**Answer:** TCP+TLS 1.2 needs roughly 1 RTT for the TCP handshake plus 2 RTT for the TLS 1.2 handshake before any application data flows (~3 RTT total). TCP+TLS 1.3 collapses the TLS handshake to 1 RTT (~2 RTT total). QUIC integrates the handshake so a new connection is ~1 RTT, and with 0-RTT resumption for a previously-visited server it can send application data on the very first flight (0 RTT for data, at the cost of replay-attack exposure for that first flight, which is why 0-RTT data is typically restricted to idempotent requests).
**Follow-up trap:** *"Why can't you use 0-RTT for a POST?"* — the first-flight 0-RTT data can be replayed by an attacker who captured it, since there's no fresh handshake proof yet; safe only for operations that are idempotent/safe to duplicate (GET-like), not for a payment or write.

### Q8 — Your team migrated to HTTP/2 and mobile p99 latency got worse. Diagnose.
**Answer:** Check packet loss on the mobile network path first — this is the classic transport-layer HOL symptom: with one shared TCP connection, any loss stalls every in-flight stream, whereas the prior HTTP/1.1 setup spread risk across 6 independent connections. Confirm via connection-level metrics (retransmit counts, RTT variance) correlated with request latency spikes across concurrent streams on the same connection, not isolated to one endpoint.
**Follow-up trap:** *"What's the fix, revert to HTTP/1.1?"* — no, that reintroduces 6× handshake/slow-start cost and doesn't scale as a long-term answer. The fix is enabling HTTP/3, which gives per-stream loss isolation while keeping single-connection efficiency.

### Q9 — What's `SETTINGS_MAX_CONCURRENT_STREAMS` and why does it exist?
**Answer:** A per-connection cap (commonly defaulted to 100 by servers) on how many HTTP/2 streams can be open simultaneously, protecting server-side resource usage (each open stream consumes memory/state) from a client opening unbounded concurrent requests on one connection.
**Follow-up trap:** *"What happens when a client exceeds it?"* — the client must wait for an existing stream to close before opening a new one, or the server can reject with a stream error; well-behaved clients track the server's advertised limit from the SETTINGS frame and self-throttle rather than relying on the server to reject.

### Q10 — Explain ALPN and how HTTP/3 discovery differs from HTTP/2's.
**Answer:** ALPN (Application-Layer Protocol Negotiation) is a TLS extension where the client advertises supported protocols (`h2`, `http/1.1`) during the TLS handshake and the server picks one — this works because both sides are already doing a TCP+TLS handshake. HTTP/3 has no equivalent bootstrap: since QUIC is a separate UDP-based connection, the client has to already know or guess the server supports h3. In practice, a server advertises `Alt-Svc: h3=":443"` in a response header over an existing HTTP/1.1 or HTTP/2 connection, and the client caches that and tries QUIC directly on the next visit.
**Follow-up trap:** *"What if the very first request to a server ever is for h3?"* — it can't be guaranteed; the client either falls back to h2/h1.1 for that first request or (with some pre-shared knowledge like HTTPS DNS records advertising `alpn=h3`) attempts QUIC speculatively with a TCP fallback in parallel — a pattern called "Happy Eyeballs" for QUIC.

### Q11 — Why does gRPC require HTTP/2 and can't run on HTTP/1.1?
**Answer:** gRPC needs true bidirectional streaming and multiplexing of many concurrent RPCs over one connection without one call blocking another — exactly what HTTP/2's independent streams and framing (HEADERS/DATA/trailers) provide natively. HTTP/1.1 has no concept of concurrent streams on one connection; you'd be back to one-request-in-flight-per-connection, which defeats the entire design (see T29-grpc for the framing detail).
**Follow-up trap:** *"Could gRPC run on HTTP/3 instead?"* — architecturally yes, and there's active work on gRPC-over-HTTP/3, but it isn't the mainstream deployed path yet for internal service mesh traffic; most production gRPC today is HTTP/2.

### Q12 — Is domain sharding still a good idea?
**Answer:** No, and it's actively counterproductive under HTTP/2 and HTTP/3. It was a way to get more than 6 parallel connections under HTTP/1.1; under HTTP/2 it fragments the single-connection multiplexing benefit and HPACK's shared dynamic table, and forces multiple TCP/TLS handshakes and slow-start ramps you'd otherwise avoid.
**Follow-up trap:** *"Is there ever a reason to still shard?"* — cross-origin resource isolation for security/CORS reasons, or genuinely serving from geographically different CDN edges, are legitimate reasons unrelated to the old connection-count hack; conflating the two in a design review is the mistake to avoid.

---

## Red flags that fail you

- Saying "HTTP/2 fixed head-of-line blocking" with no mention of the transport layer.
- Recommending server push for a new project in 2026.
- Describing pipelining as "browsers just didn't implement it" without the response-ordering constraint.
- Not knowing HTTP/3 runs on UDP, or claiming it's "just HTTP/2 but faster."
- Recommending domain sharding as an HTTP/2/3 performance optimization.
- Confusing ALPN (TLS-negotiated, TCP-based) with how HTTP/3 is discovered (`Alt-Svc`, separate UDP path).

---

## Cheat card

```
HTTP/1.1   keep-alive = persistent conn; pipelining dead (resp must return in
           request order + middlebox bugs); workaround = 6 parallel conns/origin
           (cost: 6x handshake + 6x TLS + 6x slow-start)

HTTP/2     binary framing: HEADERS + DATA frames tagged by stream ID, 1 TCP conn
           HPACK: static table 61 entries + dynamic table (default 4096B)
           SETTINGS_MAX_CONCURRENT_STREAMS commonly 100
           app-layer HOL: SOLVED · transport-layer HOL: NOT solved (TCP = 1 ordered
           byte stream; 1 lost segment stalls ALL streams behind it)

SERVER PUSH  dead: Chrome 106 (Oct 2022) disabled by default
             why: can't know client cache -> re-pushes cached assets, wastes bw
             replacement: 103 Early Hints (Link header sent before full response)

HTTP/3     runs on QUIC (UDP, RFC 9000); TLS 1.3 folded into handshake
           new conn ~1 RTT; 0-RTT resumption for repeat visits (not safe for
           non-idempotent writes -> replay risk)
           per-stream sequence + loss recovery -> lost pkt stalls ONLY its stream
           app-layer HOL: solved · transport-layer HOL: solved
           discovery: Alt-Svc header (no ALPN-equivalent bootstrap over UDP)

WHY NOT JUST FIX TCP   ossification: kernels + middleboxes everywhere; QUIC
                       encrypts almost everything so middleboxes can't meddle

RTT COST (fresh conn)  TCP+TLS1.2 ~3 RTT · TCP+TLS1.3 ~2 RTT · QUIC ~1 RTT (0 w/ 0-RTT)
```

## Sources

- [Head-of-Line Blocking in QUIC and HTTP/3: The Details](https://github.com/rmarx/holblocking-blogpost) — accessed 2026-07-26
- [HTTP/3 and QUIC — prioritization and head-of-line blocking, APNIC Blog](https://blog.apnic.net/2022/11/30/http-3-and-quic-prioritization-and-head-of-line-blocking/) — accessed 2026-07-26
- [Remove HTTP/2 Server Push from Chrome — Chrome for Developers](https://developer.chrome.com/blog/removing-push) — accessed 2026-07-26
- [Chrome to remove HTTP/2 Push — Ctrl blog](https://www.ctrl.blog/entry/http2-push-chromium-deprecation.html) — accessed 2026-07-26
- [The state of HTTP in 2022 — The Cloudflare Blog](https://blog.cloudflare.com/the-state-of-http-in-2022/) — accessed 2026-07-26
- [HTTP/1.1 pipelining is long dead — LWN.net](https://lwn.net/Articles/725319/) — accessed 2026-07-26
- [HTTP pipelining — Wikipedia](https://en.wikipedia.org/wiki/HTTP_pipelining) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
