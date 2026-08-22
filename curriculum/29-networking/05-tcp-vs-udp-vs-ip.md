# TCP vs UDP vs raw IP vs QUIC — What Each Guarantees and Costs

> **Track:** T29 Networking & Protocols · **Time:** 2h · **Prereqs:** T29-tcp-deep, T29-tcp-performance · **Updated:** 2026-07-26
> **Module id:** `T29-tcp-vs-udp-vs-ip` · **Tags:** fundamentals, critical

## The 30-second version

TCP guarantees ordered, reliable, flow-and-congestion-controlled delivery over a connection, and it charges for that with a handshake RTT, in-connection head-of-line blocking, and per-connection kernel state. UDP guarantees nothing beyond "this checksum-verified datagram arrived, demultiplexed to this port" — no ordering, no retransmission, no connection — which is a feature for anything where a stale retransmit is worse than a dropped packet: DNS, RTP media, gaming, and QUIC's substrate. QUIC runs over UDP specifically to escape kernel and middlebox ossification of TCP, and it fixes TCP's worst structural problem — one lost packet stalling every stream on the connection — by giving each stream independent loss recovery, at the cost of still having head-of-line blocking *within* a single stream, because a stream itself is still an ordered byte sequence.

## Why this gets asked

Because it's the fastest way to check whether a candidate reasons about tradeoffs mechanically or recites "TCP reliable, UDP fast" from a textbook. The interviewer has debugged a video call that froze for two seconds because a client-side proxy silently downgraded RTP to a TCP tunnel, or watched a naive migration put a leaderboard update over TCP and get 200ms of jitter from retransmit-triggered stalls that a lost UDP packet would never have caused. At staff level they're probing whether you understand *why* QUIC exists — not "it's HTTP/3's transport" but the specific ossification problem it solves and the specific problem it does not solve.

---

## Lineage: past → present → future

**What came before.** TCP (RFC 793, 1981) and UDP (RFC 768, 1980) were both built for a network where hosts were few, links were slow and lossy, and correctness mattered more than latency. TCP's job was to make an unreliable packet-switched network look like a reliable byte stream to the application, hiding loss, reordering, and duplication behind acknowledgment and retransmission. This worked so well that "network programming" for most engineers became synonymous with TCP sockets, and UDP was relegated to a handful of specialist domains — DNS queries that fit in one packet, and early VoIP. The pain that eventually mattered: TCP's reliability model is *fundamentally wrong* for real-time media and for multiplexed request/response protocols, because it enforces in-order delivery even when the application would rather have the next packet now than wait for a retransmitted old one.

**Where it stands now.** HTTP/2 (2015) tried to fix connection-level inefficiency by multiplexing many logical streams over one TCP connection — and inadvertently reintroduced head-of-line blocking at the transport level: one dropped TCP segment stalls every HTTP/2 stream sharing that connection, even the ones with no lost data. QUIC (originally a Google experiment starting 2012-2013, standardized as RFC 9000 in 2021, now the transport under HTTP/3 per RFC 9114) fixes this by moving stream multiplexing *into* the transport itself, built on UDP so it can iterate without waiting on OS kernel upgrades or middlebox vendors, most of which recognize and mangle anything that isn't classic TCP or UDP. The live disagreement: some engineering orgs still don't deploy QUIC/HTTP-3 broadly because it moves congestion control, loss recovery and flow control into userspace, which means CPU cost that used to be free in kernel/NIC offload is now paid in the application process, and debugging tooling (tcpdump-level visibility) is worse without decryption keys. What's actually deployed at scale: QUIC dominates traffic originated by the largest CDNs and browsers (Google, Cloudflare, Meta all run majority QUIC on suitable paths), but plenty of internal service-to-service traffic is still plain TCP/HTTP2/gRPC because the ops tooling and debuggability story for QUIC internally is still maturing.

**Where it's heading.** QUIC as the default transport for anything browser-facing is close to settled — confidence high. Extending QUIC-style multiplexing benefits to internal RPC (gRPC over QUIC, "grpc-quic" experiments) is directional but not yet consensus; most production gRPC is still HTTP/2-over-TCP as of mid-2026. Kernel and NIC offload for QUIC (to recover the CPU cost paid for moving to userspace) is an active area — some NICs now offer partial QUIC crypto/segmentation offload, but this is not universal. Treat "QUIC will fully replace TCP for RPC" as a speculative claim, not a settled one.

---

## Mental model

```
TCP:  one ordered pipe, in-order delivery enforced end to end
      [1][2][3][4][5]  →  loss of 2 blocks delivery of 3,4,5 to the app
                            even though they already arrived intact

HTTP/2 over TCP: many logical streams, one TCP connection
      streamA: [a1][a2][a3]
      streamB: [b1][b2][b3]   ─┐
      streamC: [c1][c2][c3]   ─┼─▶ one TCP byte stream ─▶ loss anywhere stalls A, B, and C

QUIC over UDP: many independent streams, each with its own loss recovery
      streamA: [a1][a2][a3]  ─▶ independent delivery/retransmit
      streamB: [b1][b2][b3]  ─▶ independent delivery/retransmit  } multiplexed over
      streamC: [c1][c2][c3]  ─▶ independent delivery/retransmit  } one UDP 4-tuple
      loss of a2 stalls ONLY stream A; B and C keep delivering

      but within stream A itself: [a1][a2][a3] is still ordered —
      losing a2 still blocks a3 from being delivered to the app on THAT stream
```

The one thing to internalize: TCP's ordering guarantee is scoped to *the connection*; QUIC moves that scope down to *the stream*. It didn't remove head-of-line blocking, it shrank the blast radius.

---

## How it actually works

### What TCP actually guarantees, and the mechanism behind each

| Guarantee | Mechanism |
|---|---|
| Ordered delivery | Sequence numbers on every byte; receiver buffers out-of-order segments and only releases to the app in order |
| Reliability | Cumulative ACK + retransmission timeout (RTO), plus fast retransmit on 3 duplicate ACKs |
| Flow control | Receive window (`rwnd`) advertised by the receiver — caps how much unacked data the sender can have in flight, protects a slow receiver |
| Congestion control | `cwnd`, grown via slow start (exponential, doubling per RTT until `ssthresh`) then congestion avoidance (linear, +1 MSS per RTT), shrunk on loss — protects the *network*, not just the receiver |
| Connection state | Full-duplex byte stream with explicit setup (3-way handshake) and teardown (FIN/ACK, or RST) |

**What that costs:**

- **Handshake RTT.** A bare TCP connection costs 1 RTT before any data flows (SYN, SYN-ACK, then data piggybacked on the final ACK per RFC 7413 TCP Fast Open, or 1 full RTT without it). Add TLS on top and you're at 1-2 more RTTs depending on version (see the TLS module). On a 150ms transpacific link, that's 150-450ms before your first request byte is even processed.
- **Head-of-line blocking within the connection.** A single lost segment blocks delivery of every byte after it to the application, even bytes belonging to logically independent requests multiplexed on that connection (HTTP/2's problem exactly).
- **Per-connection state.** Each TCP connection consumes a kernel socket buffer, a slot in the connection table, sequence number state, congestion window state. At scale (a load balancer terminating hundreds of thousands of connections) this is real memory and CPU, and it's why connection pooling and keep-alive matter operationally.
- **Ossification.** Because TCP's behavior lives in kernel space, evolving it requires an OS upgrade on every endpoint on the path, and middleboxes (NATs, firewalls, some load balancers) inspect and sometimes rewrite TCP options they don't recognize, silently breaking new extensions. This is the specific pain QUIC was built to escape.

### What UDP actually guarantees, and why that's a feature

UDP (RFC 768) guarantees exactly two things: a checksum (optional in IPv4, mandatory in IPv6) that lets the receiver detect (not correct) corruption, and demultiplexing by port number. That's it — no ordering, no retransmission, no connection setup, no congestion control, no flow control. A UDP socket can send a datagram to a host that doesn't exist and get no error back beyond an ICMP port-unreachable if the OS bothers to surface it.

Why that absence is a feature, with concrete numbers:

- **DNS.** A query fits in one packet (historically ≤512 bytes without EDNS0, up to 4096 with it). One packet out, one packet back, no handshake — a DNS lookup over UDP is 1 RTT total versus 2-3 RTTs if forced over TCP (TCP handshake + query + response). At a resolver doing tens of thousands of queries per second, avoiding per-query connection state is the difference between a stateless service and a connection-table bottleneck.
- **RTP/media (video calls, VoIP).** A 20ms-old audio frame is worse than useless if it arrives after the 40ms-old frame that TCP would've held it behind — the codec has already concealed the gap by the time a TCP retransmit would deliver it. Real-time jitter buffers typically tolerate 20-60ms of jitter; a single TCP retransmit round-trip on a 100ms-RTT path blows that budget by 2-5x and manifests as a stutter or freeze, not a smooth degradation. UDP just drops the late frame and the codec conceals it — audibly/visibly worse for one frame, imperceptible over a call; the TCP alternative is a multi-hundred-millisecond stall that *is* perceptible.
- **Gaming.** Same argument — a stale position update retransmitted 150ms late is actively wrong (the player has moved), so games send unreliable UDP state updates at a fixed tick rate and let the next tick correct any loss, rather than paying for guaranteed delivery of stale data.
- **QUIC's substrate.** UDP gives QUIC an escape hatch from kernel ossification — QUIC is implemented entirely in userspace libraries (e.g. Google's QUICHE, Facebook's mvfst), so new congestion control algorithms or loss recovery tweaks ship in an application/library update, not an OS kernel update.

### Raw IP sockets

A raw socket (`SOCK_RAW`, requires `CAP_NET_RAW`/root) lets a process construct or read IP packets directly, bypassing the OS's TCP/UDP demultiplexing entirely. Real use cases: `ping` and `traceroute` (crafting ICMP echo requests and reading TTL-exceeded responses directly), custom routing daemons, packet capture and injection tools (scapy, hping3), implementing a transport protocol other than TCP/UDP (OSPF runs directly over IP protocol number 89, no port at all), and VPN/tunnel implementations that need to see or forge IP headers. This is not a general application-layer tool — it requires elevated privileges and you are responsible for everything IP normally delegates, including fragmentation handling.

### QUIC (RFC 9000, transport; RFC 9001, TLS integration; RFC 9114, HTTP/3 mapping)

QUIC is a transport protocol built on top of UDP that reimplements, in userspace, most of what made TCP useful, plus stream multiplexing and mandatory encryption:

- **Independent streams.** Each QUIC stream has its own flow control and its own loss-recovery sequence space. Frame headers carry a stream ID, and the receiver can deliver a fully-received stream to the application even if a different stream is still waiting on a retransmit.
- **Connection migration.** A QUIC connection is identified by a Connection ID, not the traditional 4-tuple (src IP, src port, dst IP, dst port). This lets a connection survive a client's IP address changing (Wi-Fi to cellular handoff) without a fresh handshake — something impossible for TCP, where the connection *is* the 4-tuple.
- **TLS 1.3 is mandatory and integrated into the handshake**, not layered on top — QUIC's handshake completes the transport and crypto handshake in a single round trip (1-RTT for a fresh connection, 0-RTT for a resumed one), versus TCP+TLS 1.3's own 1 RTT for the TCP handshake plus 1 RTT for TLS.
- **Loss recovery and congestion control move to userspace**, implemented per QUIC library rather than per OS kernel — this is exactly what buys the fast-iteration property but also means CPU cycles that used to be free NIC/kernel work are now paid for in the application process. Measured overhead in early large-scale deployments (Google's own reporting on QUIC rollout) showed real but manageable CPU cost increases versus TCP, which is why widespread QUIC adoption tracked kernel/NIC offload support maturing over several years, not an instant cutover.

**Where QUIC still has head-of-line blocking:** within a single stream. A stream is still an ordered byte sequence — QUIC guarantees in-order delivery *of that stream's own bytes* to the application, so a lost packet carrying stream-A data still blocks later stream-A data from being delivered, exactly like TCP would, it just no longer blocks streams B and C. If your workload is a single large download over a single stream, QUIC's HOL-blocking fix buys you nothing; the benefit is specifically for concurrent independent streams multiplexed over one connection ([Head-of-Line Blocking in QUIC and HTTP/3: The Details](https://github.com/rmarx/holblocking-blogpost) — accessed 2026-07-26).

---

## Build it from scratch

Minimal illustration of the guarantee difference — a UDP echo that drops every third packet, versus TCP which would silently retransmit and stall:

```python
# untested sketch
import socket, time

def udp_server(drop_every=3):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 9999))
    n = 0
    while True:
        data, addr = sock.recvfrom(1024)
        n += 1
        if n % drop_every == 0:
            continue          # simulate loss: no retransmit, no recovery, gone
        sock.sendto(data, addr)   # echo back immediately, no ordering guarantee

def udp_client(n=10):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.2)       # short timeout: a real client decides itself
    for i in range(n):         # whether a missing reply matters
        sock.sendto(str(i).encode(), ("127.0.0.1", 9999))
        try:
            print("got", sock.recvfrom(1024)[0])
        except socket.timeout:
            print("dropped", i, "- app's problem to decide what to do, if anything")
```

Contrast: the equivalent over `socket.SOCK_STREAM` (TCP) would never show a "dropped" packet to the application — the kernel would retransmit transparently and the *next* read would simply block until recovery completed, which is exactly the behavior that's wrong for a real-time workload and invisible until you measure tail latency, not throughput.

---

## How it's done in production

| Layer | What it adds |
|---|---|
| **TCP** (via OS sockets, `httpx`, `requests`, JDBC drivers) | Kernel handles handshake, retransmission, congestion control (default: CUBIC on Linux, BBR increasingly common on high-BDP paths); application never sees a dropped packet, only latency |
| **UDP** (raw sockets, `aiortc` for WebRTC, `dnspython` for DNS) | Application owns retry/ordering/congestion policy entirely, or explicitly opts out of all three |
| **QUIC** (via `quic-go`, Cloudflare `quiche`, Meta `mvfst`, browser/CDN built-ins) | Library reimplements TCP-equivalent reliability per-stream, adds connection migration, mandatory TLS 1.3 |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Video call freezes for ~1-2s then catches up | Media accidentally tunneled over TCP (corporate proxy, misconfigured relay) — one lost packet stalls the whole stream | Force UDP/RTP path; if blocked, use a TURN relay over UDP, not a TCP fallback, for real-time media |
| One slow HTTP/2 request stalls unrelated requests on the same connection | TCP head-of-line blocking — HTTP/2 multiplexes streams above a transport that doesn't | Move to HTTP/3 (QUIC), or open a second TCP connection as a workaround |
| QUIC/HTTP-3 traffic silently drops or times out for a subset of users | Middlebox (corporate firewall, older NAT) blocks or throttles UDP/443, since QUIC is newer than most middlebox UDP allowlists | Always ship a TCP/HTTP-2 fallback path; browsers already do this automatically via Alt-Svc negotiation |
| DNS resolution intermittently fails only for large responses | UDP response exceeds path MTU or the 512-byte non-EDNS0 limit and gets truncated (TC bit set) | Client must retry over TCP on truncation — this is in the DNS spec, not a bug; verify EDNS0 is negotiated to raise the UDP limit first |
| High CPU on QUIC-terminating edge nodes after a TCP→QUIC migration | Loss recovery and crypto moved from kernel/NIC to userspace | Enable QUIC crypto/segmentation NIC offload where available; budget CPU headroom before flipping the traffic percentage |
| Server-side "phantom" connections after client disappears (mobile network drop) | UDP has no connection teardown signal — nothing tells the server the client is gone | Application-level idle timeout / heartbeat; QUIC has this built in via PING frames and idle timeout |

---

## Tradeoffs & when NOT to use it

- **Don't use raw UDP for anything that needs correctness by default.** If you're about to hand-roll retries, ordering, and congestion backoff on top of UDP, you're rebuilding TCP badly — use QUIC or TCP instead unless you have a specific, measured reason (typically: real-time media, or a bespoke protocol where TCP's ordering is actively harmful).
- **Don't put real-time media over TCP**, even under pressure to "simplify the stack" or route through a corporate proxy that only allows TCP/443. The failure mode (multi-second freezes under loss) is worse than the UDP failure mode (brief, concealable glitches) for this workload specifically.
- **Don't assume QUIC is a free upgrade.** It costs CPU (userspace crypto/loss-recovery) and it costs debuggability (payloads are encrypted end-to-end including most transport metadata, so classic `tcpdump`-based triage needs QUIC-aware tooling or exported keys). For high-volume internal RPC where you already control both ends and don't need connection migration or independent-stream HOL avoidance, plain HTTP/2-over-TCP-over-TLS is still the pragmatic default in mid-2026.
- **Don't reach for raw IP sockets in application code.** They require elevated privileges, bypass the OS's demultiplexing entirely, and put you on the hook for fragmentation and reassembly. They're a systems/network-tooling primitive, not an app-layer one.
- **QUIC's HOL-blocking fix only pays off with genuinely concurrent independent streams.** A single large sequential transfer over one stream gets none of that benefit — you're just paying QUIC's per-packet crypto overhead for TCP-equivalent behavior.

---

## Interview questions

### Q1 — What does TCP guarantee that UDP doesn't?
**Testing:** baseline correctness of the mental model.
**Answer:** Ordered delivery (sequence numbers, receiver reorders/buffers), reliability (ACK + retransmission on loss), flow control (receiver-advertised window), congestion control (sender-side window grown/shrunk based on observed loss/latency), and connection state (explicit handshake and teardown). UDP guarantees only a checksum and port-based demultiplexing.
**Follow-up trap:** *"Is UDP's checksum mandatory?"* — Optional in IPv4 (can be all-zero, meaning "not computed"), mandatory in IPv6. Saying "UDP has no checksum" is wrong and a quick way to lose credibility on this exact question.

### Q2 — Why would you ever choose UDP over TCP given TCP does more?
**Answer:** Because "more" here specifically means "enforces in-order, complete delivery," which is actively harmful for workloads where a late/stale packet is worse than a dropped one — real-time audio/video, gaming state updates, and DNS (where the simplicity of no connection setup matters more than guaranteed delivery, and the application layer can retry over TCP on truncation anyway).
**Follow-up trap:** *"Give me a number."* — A jitter buffer typically tolerates 20-60ms; a single retransmit round trip on a 100ms RTT path already blows past that, so TCP's "fix" (wait and retransmit) produces a worse user-visible outcome (a stall) than UDP's failure mode (one dropped/concealed frame).

### Q3 — Walk me through TCP's three-way handshake and what it costs.
**Answer:** SYN → SYN-ACK → ACK, establishing sequence number state in both directions before any application data flows. Costs 1 RTT minimum before the first data byte (unless TCP Fast Open, RFC 7413, is negotiated, letting data ride on the initial SYN for a previously-seen client). On a 150ms transpacific link that's 150ms of pure setup latency before anything else — TLS adds more on top.
**Follow-up trap:** *"Does the handshake protect against anything besides synchronizing sequence numbers?"* — It's also the mechanism behind SYN cookies as a defense against SYN-flood DoS: the server doesn't need to allocate state until the final ACK if it encodes what it needs into the SYN-ACK's sequence number itself.

### Q4 — What specifically is "head-of-line blocking" and where does it occur in TCP, HTTP/2, and QUIC?
**Testing:** whether you understand this is a *scoping* problem, not a binary present/absent property.
**Answer:** TCP enforces in-order byte delivery to the application; a single lost segment blocks every later byte on that connection from being delivered, even if they arrived intact. HTTP/2 multiplexes many logical streams onto one TCP connection, so TCP's HOL blocking now stalls every HTTP/2 stream sharing that connection — this is "HTTP/2 over TCP" HOL blocking, and it's a transport-level artifact, not an HTTP/2 design flaw per se. QUIC gives each stream independent sequencing and loss recovery, so a lost packet only stalls the stream it belonged to; other streams keep delivering. QUIC still has HOL blocking *within* a stream, because a stream is still an ordered sequence.
**Follow-up trap:** *"So QUIC eliminates HOL blocking?"* — No — it shrinks its scope from "the connection" to "the stream." If your workload is one stream, you get zero benefit.

### Q5 — Why does QUIC run over UDP instead of being a new IP-layer protocol?
**Answer:** Ossification. A genuinely new transport protocol (new IP protocol number) would be silently dropped or mishandled by a huge fraction of middleboxes, NATs, and firewalls deployed across the internet that only recognize TCP and UDP, and rolling out kernel-level support for a new protocol requires an OS upgrade on every endpoint. UDP is already universally passable, so QUIC piggybacks on it and implements everything else — reliability, ordering, congestion control, encryption — in userspace libraries that can ship and iterate at application-release speed.
**Follow-up trap:** *"Doesn't that mean QUIC pays a CPU tax?"* — Yes, real and measured: loss recovery and crypto that used to be kernel/NIC work now run in the application process. This is why widescale QUIC rollout tracked the maturity of userspace crypto optimizations and, later, NIC-level QUIC offload, rather than happening overnight.

### Q6 — Design the transport choice for a multiplayer game server sending 20 position updates/sec per player.
**Testing:** applying the guarantees-and-costs framing to a concrete workload.
**Answer:** UDP, unreliable and unordered by design, because a stale position update delivered late via retransmission is actively wrong — the player has already moved by the time it arrives, so the next tick's update supersedes it anyway. Add a thin sequence number in the payload so the client can discard out-of-order arrivals without transport-level retransmission machinery, and reserve TCP (or a reliable channel layered selectively over UDP) only for state that must not be lost — inventory changes, chat, match results.
**Follow-up trap:** *"What if a critical event, like a kill confirmation, needs to be reliable but everything else doesn't?"* — This is exactly why some game engines run a hybrid: unreliable UDP for high-frequency ephemeral state, plus a lightweight reliable-UDP layer (custom ACK+retry for specific message types, e.g. ENet, or QUIC's reliable streams for the rest) rather than opening a second TCP connection, which reintroduces handshake cost and a second congestion-control domain.

### Q7 — What's a raw IP socket and who actually uses one?
**Answer:** A socket (`SOCK_RAW`) that bypasses the kernel's TCP/UDP demultiplexing, letting a process construct or inspect IP packets directly — requires elevated privileges. Used by `ping`/`traceroute` (ICMP construction), packet crafting/capture tools (scapy, hping3), custom routing protocols that run directly over IP (OSPF, protocol number 89, no port at all), and VPN/tunneling implementations.
**Follow-up trap:** *"Would you ever use one in an application service?"* — Essentially never. It's a systems-programming/network-tooling primitive; an application service that needs custom transport semantics should build on UDP (staying inside normal socket privilege and portability) rather than raw IP.

### Q8 — Why does DNS use UDP, and when does it fall back to TCP?
**Answer:** A query and response both fit in one packet in the overwhelming majority of cases (historically ≤512 bytes without EDNS0, up to 4096 with it negotiated), so UDP avoids a handshake entirely — 1 RTT total. It falls back to TCP when the response would be truncated (server sets the TC bit) — typically large record sets, DNSSEC-signed responses, or zone transfers (AXFR/IXFR, which are TCP-only by spec).
**Follow-up trap:** *"What breaks if a client doesn't implement the TCP fallback correctly?"* — It silently gets a truncated, incomplete answer (e.g., a partial list of MX or TXT records) instead of an error, which is a real and hard-to-diagnose class of production bug — the query "succeeds" with wrong data rather than failing loudly.

### Q9 — Explain QUIC connection migration and why TCP can't do it.
**Answer:** A QUIC connection is identified by a Connection ID chosen at handshake time, not by the traditional 4-tuple (source/destination IP and port). If a client's IP changes — Wi-Fi to cellular handoff — the connection ID stays valid and the QUIC connection survives without a new handshake. TCP has no equivalent because a TCP connection *is* the 4-tuple; change any element and the kernel sees it as an entirely different connection, with no adjacent-layer construct to reattach state to.
**Follow-up trap:** *"Is this pure upside?"* — No — surviving IP changes also expands the threat model: an off-path attacker who observes a Connection ID could attempt connection hijacking if the migration validation isn't done correctly, which is why QUIC's spec requires path validation (a challenge/response) before fully trusting a new path.

### Q10 — Your team is deciding whether to move internal gRPC traffic from HTTP/2 to QUIC/HTTP-3. What do you ask first?
**Testing:** senior-level tradeoff reasoning, not "QUIC is newer so yes."
**Answer:** First: do we actually have workloads suffering from TCP-level HOL blocking today — multiple concurrent streams per connection with meaningfully independent loss patterns? If most RPC connections carry one dominant call at a time, there's little to gain. Second: what's our debugging tooling story — can we decrypt and inspect QUIC traffic in our existing observability stack, or are we signing up for blind spots during incidents? Third: what's the CPU headroom, since loss recovery and crypto move from kernel/NIC to userspace. If the answer to the first question is "no, we don't have that pattern," this is solving a problem we don't have at the cost of debuggability and CPU we do have.
**Follow-up trap:** *"What if leadership just wants it because 'HTTP/3 is faster'?"* — Push back with the actual mechanism: QUIC's latency win comes from combining the transport and TLS handshake into one RTT and from independent-stream loss recovery — neither applies uniformly to already-warm, connection-pooled internal RPC the way it does to a browser opening a cold connection to a public CDN edge.

### Q11 — What is TCP Fast Open and why isn't it universally enabled?
**Answer:** RFC 7413 — lets a client that has previously connected to a server include a cookie in its initial SYN, allowing the server to accept data in that same SYN without waiting for the final ACK, saving 1 RTT on repeat connections. It isn't universal because it requires both client and server support, a cookie exchange on the first connection (so it doesn't help cold starts), and it has had a history of middlebox interference (some NATs/firewalls drop SYNs carrying unrecognized data), plus replay-risk considerations similar in spirit to TLS 0-RTT.
**Follow-up trap:** *"How does that risk compare to TLS 0-RTT replay?"* — Same category of problem: data riding on the very first packet of a resumed connection can be replayed by a network attacker before the full handshake completes, so both are restricted in practice to idempotent operations.

### Q12 — A dropped packet on a TCP connection carrying an HTTP/2 multiplexed API gateway causes p99 latency to spike but p50 stays flat. Explain.
**Testing:** connecting the mechanical HOL-blocking model to an observable symptom.
**Answer:** Most requests on that connection are unaffected in absolute terms — they arrived fine — but they're all sitting behind the one stream that needs a retransmit, because TCP won't release *any* later bytes on that connection to the application until the gap is filled. That produces a stall affecting a subset of concurrent requests (visible in p99, since it's intermittent and tied to loss events) without moving the median, since most connections at any instant aren't experiencing loss.
**Follow-up trap:** *"How would you confirm this diagnosis without guessing?"* — Correlate p99 spikes with retransmission counters (`netstat -s`, `ss -ti` showing `retrans`) on the affected hosts; if spikes track retransmit events 1:1, it's HOL blocking, not application-side slowness. If it doesn't correlate, look elsewhere before touching the transport.

### Q13 — Does moving to QUIC eliminate the need for HTTP-level timeouts and retries?
**Answer:** No — QUIC solves transport-level HOL blocking and handshake RTT, but it says nothing about application-level failure: a slow or wedged upstream service still needs request timeouts, and a genuinely failed request still needs an idempotency-aware retry policy. Transport reliability and application-level resilience are orthogonal; QUIC only affects the former.
**Follow-up trap:** *"So what class of latency problem does QUIC actually fix?"* — Specifically: connection-establishment latency (1-RTT vs TCP+TLS's 2+ RTTs) and loss-recovery blast radius when multiple independent streams share a connection. It does nothing for a backend that's simply slow to compute a response.

### Q14 — Explain why TCP's congestion control (not just flow control) matters, and what breaks without it.
**Answer:** Flow control protects the *receiver* from being overwhelmed (bounded by its buffer); congestion control protects the *network path* from being overwhelmed by all the flows sharing it, inferred indirectly via loss or (with newer algorithms like BBR) measured delay. Without congestion control, a sender would blast data at line rate regardless of path conditions, and on a shared, congested link that causes cascading loss across every flow sharing the bottleneck — the original "congestion collapse" problem that 1980s-era TCP (Van Jacobson's algorithms, 1988) was built specifically to prevent.
**Follow-up trap:** *"UDP has none of this. So doesn't a UDP flood just take down the network?"* — Exactly the risk, and exactly why any UDP-based protocol used at scale (QUIC included) is required to implement its own congestion control in userspace, and why unmetered raw UDP traffic is a classic DoS vector network operators rate-limit aggressively.

---

## Red flags that fail you

- Saying "TCP is reliable, UDP is fast" and stopping there, with no mechanism.
- Claiming UDP has no checksum at all (it's optional in IPv4, mandatory in IPv6).
- Describing QUIC as "eliminating head-of-line blocking" without the "within a stream" caveat.
- Not knowing QUIC runs over UDP, or not knowing *why* (ossification, not "because it's simpler").
- Recommending TCP for real-time media without acknowledging the jitter/stall tradeoff.
- Treating raw IP sockets as a normal application-layer tool.
- Assuming QUIC is a strictly free performance upgrade with no CPU or debuggability cost.

---

## Cheat card

```
TCP guarantees: order (seq nums) · reliability (ACK+retransmit) · flow control (rwnd)
                congestion control (cwnd: slow start ×2/RTT, then +1MSS/RTT) · conn state
TCP costs:      1 RTT handshake (TFO can save it) · connection-scoped HOL blocking
                per-conn kernel state (memory+CPU at scale) · ossified (kernel-level changes)

UDP guarantees: checksum (optional IPv4, mandatory IPv6) + port demux. Nothing else.
UDP wins when: stale data is worse than lost data — DNS (1 RTT, ≤512B/4096B EDNS0),
                RTP/media (jitter budget ~20-60ms; one TCP retransmit RTT blows it),
                gaming (position ticks superseded by next tick anyway)

RAW IP sockets: SOCK_RAW, needs CAP_NET_RAW/root. ping/traceroute, packet crafting,
                OSPF (proto 89, no port), VPN tunnels. Not an app-layer tool.

QUIC (RFC 9000/9001, HTTP/3=RFC 9114): UDP substrate to dodge kernel/middlebox
                ossification. Per-stream loss recovery: 1 lost pkt stalls ONLY that
                stream, not the connection. Still HOL-blocked WITHIN a stream.
                Conn ID (not 4-tuple) → survives IP change (Wi-Fi→cellular).
                TLS 1.3 integrated: 1-RTT handshake, 0-RTT on resume.
                Cost: crypto/loss-recovery now in userspace = real CPU tax.

DECISION: single ordered stream, no jitter sensitivity → TCP. Real-time/lossy-ok
          → UDP. Many concurrent independent streams, want migration/fast resume
          → QUIC. Need raw packet construction → raw IP (rare, privileged).
```

## Sources

- [Head-of-Line Blocking in QUIC and HTTP/3: The Details](https://github.com/rmarx/holblocking-blogpost) — accessed 2026-07-26
- [HTTP/3 and QUIC — prioritization and head-of-line blocking, APNIC Blog](https://blog.apnic.net/2022/11/30/http-3-and-quic-prioritization-and-head-of-line-blocking/) — accessed 2026-07-26
- [QUIC and HTTP/3 in 2026: from Google experiment to IETF standard](https://ma.ttias.be/quic-http3-in-2026/) — accessed 2026-07-26
- RFC 793 (TCP), RFC 768 (UDP), RFC 9000 (QUIC transport), RFC 9001 (Using TLS to Secure QUIC), RFC 9114 (HTTP/3), RFC 7413 (TCP Fast Open) — IETF datatracker, accessed 2026-07-26
- [Amazon/Google/Cisco Glassdoor TCP vs UDP interview questions](https://www.glassdoor.com/Interview/Describe-the-difference-between-TCP-and-UDP-QTN_181437.htm) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
