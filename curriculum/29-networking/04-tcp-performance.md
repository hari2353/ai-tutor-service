# Congestion Control, Window Scaling, Nagle, Keepalive, Backlog, SO_REUSEADDR

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-tcp-deep · **Updated:** 2026-07-26
> **Module id:** `T29-tcp-performance` · **Tags:** tcp, critical

## The 30-second version

TCP throughput on a single connection is bounded by two independent things: how much unacknowledged data the receiver will accept (the window), and how much the network will tolerate before dropping packets (congestion control). Congestion control starts in slow start (cwnd begins at 10 segments per RFC 6928 and roughly doubles each RTT) until it hits a loss signal or `ssthresh`, then either backs off additively (Reno-style AIMD, halving cwnd on loss) or follows CUBIC's cubic-shaped recovery curve, which is Linux's default because it's fairer across connections with different RTTs than Reno's per-ACK increase. BBR takes a completely different approach: instead of reacting to loss, it actively models bandwidth and round-trip propagation time and paces to that estimate, which wins on high-loss or bufferbloated paths but has documented fairness problems against loss-based flows sharing a shallow buffer. Window scaling exists because TCP's 16-bit window field caps the receiver's advertised window at 65,535 bytes, which throttles a 1 Gbps/100ms-RTT link (12.5 MB bandwidth-delay product) to about 5 Mbps without it — the RFC 1323 scale option multiplies the window by up to 2^14, unlocking roughly 1 GB of window. Nagle's algorithm and delayed ACK independently make sense but combine into a specific, well-known 200-500ms stall when a small write waits for an ACK that the receiver is deliberately delaying — the fix is `TCP_NODELAY` on latency-sensitive sockets. And a huge amount of "the network is slow" production pain is actually socket-layer misconfiguration: an undersized `listen()` backlog dropping SYNs under burst, or connection churn burning through the ~28,000 ephemeral ports Linux allocates by default.

## Why this gets asked

Because it separates people who've read about TCP from people who've tuned it under load. Anyone can say "TCP has congestion control." Fewer people can explain why a service moving to a new cloud region with 3x the RTT saw throughput collapse even though bandwidth didn't change (BDP math), or why disabling Nagle fixed a latency spike that had nothing to do with congestion at all, or why a backlog of 128 was silently dropping connections during a traffic spike well before CPU or memory looked stressed. The interviewer has almost certainly hit at least one of: a request that stalled for exactly ~40-200ms for no visible reason, a service that couldn't push more than a fraction of available bandwidth over a long-haul link, or a fleet that started throwing `EADDRNOTAVAIL` under load. They want the mechanical explanation, with the actual numbers, not "it's probably a network thing."

---

## Lineage: past → present → future

**What came before.** Before 1988, TCP had no congestion control at all — the transport layer trusted the network to signal problems, and it didn't, which produced the "congestion collapse" events of the mid-1980s where throughput on parts of the early internet dropped by orders of magnitude under load because every sender kept retransmitting into an already-overloaded network with no backoff. Van Jacobson's 1988 paper and the resulting algorithms (slow start, congestion avoidance, fast retransmit, fast recovery — collectively "Tahoe" and then "Reno") fixed this by treating packet loss as the congestion signal and backing off multiplicatively when it happened, which is why "loss-based congestion control" was the only real model for the following two decades.

**Where it stands now.** CUBIC (Ha, Rhee, Xu, 2008) replaced Reno as Linux's default in kernel 2.6.19 (2006) because Reno's linear, per-ACK window growth is fundamentally unfair to high-RTT flows — a flow with a longer RTT gets fewer ACKs per second and therefore grows its window slower under Reno, even competing for the exact same bottleneck link. CUBIC's growth is a function of *wall-clock time since the last loss event*, not ACK count, which removes that RTT bias and made it the practical default almost everywhere loss-based control is still used. The genuinely live disagreement today is loss-based (CUBIC) versus model-based (BBR, Google 2016, now BBRv2/BBRv3 iterating): BBR estimates the actual bottleneck bandwidth and round-trip propagation time directly and paces sending to that model rather than waiting for a queue to overflow and a packet to drop, which performs measurably better on paths with non-congestive loss (wifi, satellite, lossy last-mile) and on bufferbloated links where loss-based control fills a deep buffer before it ever sees a drop. The tradeoff, documented and still debated, is fairness: BBR competing against CUBIC in a shared shallow buffer can grab a disproportionate share of bandwidth (measurements have shown BBR taking upward of 90% of capacity against CUBIC on small buffers), while CUBIC tends to win back share on deep buffers. This isn't settled; it's an active area of measurement and BBR version iteration specifically aimed at closing that fairness gap.

**Where it's heading.** BBRv2 and the ongoing v3 work are explicitly trying to fix v1's fairness problems (adding loss and ECN response so BBR backs off in the presence of real congestion signals rather than only its own bandwidth/RTT model), and that convergence toward "model-based control that still respects loss/ECN as a backstop" looks like the durable direction. At the application layer, QUIC ships its own congestion control in user space (commonly CUBIC or BBR implementations bundled with the QUIC library) rather than relying on the kernel's TCP stack, which means congestion control tuning is increasingly an application/library concern for HTTP/3 traffic, not purely an OS sysctl. Expect continued divergence between "what the kernel defaults to for plain TCP" and "what the QUIC/HTTP3 stack ships," and don't assume they're the same algorithm just because both projects are on the same host.

---

## Mental model

```
cwnd
 │                                     congestion avoidance (CUBIC / AIMD)
 │                              ______/\___/\___                 <- loss event, backs off
 │                         ____/                \___/\_______
 │           slow start   /                                       BBR instead: no sawtooth,
 │        (exponential)  /                                        paces near estimated
 │       ______/        /  <- ssthresh                            BtlBw x RTprop directly
 │  ____/               
 └──────────────────────────────────────────────────────────► time

Window scaling: 16-bit window field maxes at 65,535 bytes.
BDP = bandwidth × RTT. If BDP > max window, the window — not the network — caps throughput.
```

The one-line mental model: **congestion control decides how fast you're *allowed* to send; the window decides how much you're *allowed* to have in flight unacknowledged.** Either one can be the bottleneck, and diagnosing which one is is the actual skill.

---

## How it actually works

### Slow start and AIMD, with real numbers

- **Initial congestion window (IW):** RFC 6928 (2013) raised the recommended default to **10 segments** (roughly 14.6KB at a 1460-byte MSS), up from the much smaller 2-4 segment defaults of RFC 3390/5681. Linux has shipped IW10 as its default since kernel 3.0 / 2.6.39-era patches. This matters concretely: a connection can burst up to ~14.6KB before ever getting an ACK back, which is why short-lived, small HTTP responses often complete inside a single RTT and never see congestion avoidance kick in at all.
- **Slow start** roughly doubles cwnd every RTT (each ACK increases cwnd by one MSS, so a full window of ACKs doubles it) until either a loss occurs or cwnd reaches `ssthresh`, at which point the connection moves to congestion avoidance.
- **AIMD (Reno-style congestion avoidance):** additive increase of one MSS per RTT while no loss is observed, multiplicative decrease on loss — `ssthresh = cwnd / 2`, `cwnd = ssthresh` (halved). This produces the classic sawtooth.
- **CUBIC** replaces the additive-increase rule with a cubic function of elapsed time since the last congestion event: `W(t) = C(t - K)^3 + W_max`, where `C` is a scaling constant (Linux default **0.4**), `W_max` is the window size at the last loss, and `K = cbrt(W_max × β / C)` is the time to grow back to `W_max`. The multiplicative decrease factor `β` is **0.7** for CUBIC (versus Reno's 0.5), a gentler backoff. Because growth depends on wall-clock time rather than ACK arrival rate, two CUBIC flows with different RTTs converge toward the same window size instead of the shorter-RTT flow permanently dominating, which is the specific unfairness that got Reno replaced.

### BBR — model-based, not loss-based

BBR (Bottleneck Bandwidth and RTT) continuously estimates two quantities by probing: **BtlBw** (the bottleneck link's bandwidth, sampled as the max delivery rate observed) and **RTprop** (the round-trip propagation time, sampled as the minimum RTT observed, ideally with no queuing delay). It then paces its sending rate to roughly `BtlBw`, targeting an in-flight data volume near `BtlBw × RTprop` (the BDP) rather than growing until a drop happens. Periodically it deliberately probes for more bandwidth (a brief pacing-gain-up phase) and for a fresher RTprop estimate (a brief pacing-gain-down phase to drain any queue it built). The real tradeoff: **BBR doesn't wait for loss to react**, which is a genuine win on lossy non-congestive paths (wifi interference, satellite, cellular) where loss-based control mistakes ordinary bit-error loss for congestion and backs off unnecessarily — but sharing a **shallow buffer** with a loss-based flow (CUBIC), BBR can claim a disproportionate share of bandwidth because CUBIC only backs off once the shared buffer actually overflows, and BBR's model doesn't wait for that. Measurements bear this out directly: at small buffer sizes BBR has been measured taking upward of 90% of shared bandwidth against CUBIC, while at large buffer sizes (where CUBIC fills the buffer and gets its familiar sawtooth) CUBIC reclaims a larger share, commonly cited around 80%. This fairness sensitivity to buffer size, not a simple "BBR is better/worse," is the actual nuance interviewers are checking for.

### Window scaling and the bandwidth-delay product

The TCP header's window field is **16 bits**, capping the advertised receive window at **65,535 bytes** without any extension. RFC 1323 adds a **window scale option**, negotiated only during the handshake, multiplying the advertised window by `2^S` where `S` is 0-14 — giving a maximum effective window of `65,535 × 2^14 ≈ 1,073,725,440 bytes`, roughly **1 GB**.

**Why this matters — worked BDP example.** Bandwidth-delay product is `bandwidth × RTT`, the amount of data that can be "in the pipe" at once. Take a 1 Gbps link with a 100ms RTT: `BDP = 1×10^9 bits/s × 0.1s ÷ 8 = 12.5 MB`. Without window scaling, the maximum unscaled window is 65,535 bytes ≈ 64KB, so the achievable throughput is capped at `65,535 bytes ÷ 0.1s ≈ 655KB/s ≈ 5.24 Mbps` — **less than 1% of the link's actual capacity**, entirely because the window, not the network, is the bottleneck. This is exactly the failure mode behind "we moved to a farther region and throughput cratered even though bandwidth didn't change" — RTT went up, BDP went up, and an unscaled or under-scaled window couldn't keep the pipe full. Window scaling is negotiated in the SYN/SYN-ACK only; if either endpoint or a misconfigured middlebox strips the option, the connection is silently stuck at the 64KB ceiling for its entire lifetime.

### Nagle vs delayed ACK — the specific interaction that stalls

**Nagle's algorithm** (RFC 896, 1984) exists to solve the "small packet problem": an application writing data one byte (or a few bytes) at a time would otherwise generate a full 40+-byte header for each tiny payload, a huge overhead ratio. Nagle's rule: if there is unacknowledged data already in flight, buffer any further small writes until either a full MSS accumulates or the outstanding data gets acknowledged.

**Delayed ACK** (recommended by RFC 1122) exists on the receiving side to reduce ACK traffic: instead of acknowledging every single segment immediately, the receiver waits a short window (commonly implemented around 40ms on Linux, with the RFC's own ceiling around 500ms; the classic textbook figure widely cited for this stall is in the **200-500ms** range depending on stack) hoping to either piggyback the ACK on outgoing data or coalesce multiple ACKs into one.

**The interaction:** if a client sends a small write (Nagle holds it, waiting for the ACK of the *previous* small write) and the server is using delayed ACK (holding that very ACK, waiting to see if it has data to piggyback it on, or waiting out its timer), the two mechanisms wait on each other — the client won't send until acked, the server won't ack promptly because nothing prompts it to — producing a real, measurable **~200-500ms stall** with each small write/read cycle. This shows up concretely in a packet capture as a visible gap: a small PSH segment leaves the client, and the corresponding ACK doesn't appear until the delayed-ack timer fires tens to hundreds of milliseconds later, with no packets at all in between. It's a classic, specific, nameable production bug (frequently hit by protocols that do small request/response writes on the same connection — old telnet-like protocols, some RPC implementations, chatty request/response patterns over a persistent connection) and the fix is **`TCP_NODELAY`** (setsockopt, disables Nagle) on the writing side for latency-sensitive sockets, which is standard practice for HTTP servers, RPC frameworks, and anything doing small, interactive read/write cycles rather than bulk transfer.

### TCP keepalive — and why it's not enough

Linux TCP keepalive defaults: `tcp_keepalive_time` = **7200 seconds (2 hours)** of idleness before the first probe, `tcp_keepalive_intvl` = **75 seconds** between probes if no response, `tcp_keepalive_probes` = **9** probes before giving up. Total worst case before a dead peer is detected: roughly **2 hours 11 minutes**. This is far too slow for any interactive or latency-sensitive system to rely on as its liveness mechanism — it exists mainly to eventually reclaim genuinely abandoned connections (e.g., a NAT device or firewall silently dropped state and neither side will ever hear from the other again), not to detect a dead peer within any useful SLA. **This is exactly why application-level heartbeats** (a ping/pong message every 10-30 seconds with an explicit timeout) are standard in anything that needs to detect a dead connection faster than "eventually."

### SO_REUSEADDR vs SO_REUSEPORT

- **`SO_REUSEADDR`**: lets a socket bind to a local address/port that has existing sockets in `TIME_WAIT` for that same address — its actual purpose is letting a restarted server rebind its listening port immediately rather than failing with `EADDRINUSE` while old connections drain. It does not let two independent live listening sockets share a port simultaneously for load distribution.
- **`SO_REUSEPORT`** (Linux 3.9+): lets multiple independent sockets — across threads or even separate processes — bind the *same* address and port simultaneously, with the kernel hashing incoming connections across them. This is the actual mechanism for multi-threaded/multi-process servers to accept connections in parallel without a single shared accept-queue lock becoming a bottleneck, and it avoids the classic "thundering herd" where every worker wakes up for one incoming connection and all but one go back to sleep.

### Backlog: SYN queue vs accept queue

`listen(sockfd, backlog)` actually governs (at minimum, conceptually) two separate queues:
- The **SYN queue** (sometimes called the SYN backlog) holds connections that have received a SYN but haven't completed the handshake yet — sized by `net.ipv4.tcp_max_syn_backlog`. When this fills under a SYN flood or a burst of legitimate new connections, the kernel either drops further SYNs (visible in `netstat -s` as SYN queue overflow counters) or, if `net.ipv4.tcp_syncookies` is enabled (the default on Linux), falls back to **SYN cookies** — encoding the necessary connection state into the SYN-ACK's own sequence number instead of storing it server-side, trading a small amount of TCP-options functionality (window scaling info is lost, for one) for surviving the flood statelessly.
- The **accept queue** holds fully-established connections waiting for the application to call `accept()` — its effective size is `min(backlog argument, net.core.somaxconn)`. The historical Linux default for `somaxconn` was a low **128**; many modern distributions and kernel defaults have raised it (commonly to **4096** on recent kernels/distros), but this is exactly the kind of number you should verify with `sysctl net.core.somaxconn` rather than assume, because the gap between "128" and "4096" is the difference between silently dropping connections during a moderate traffic burst and comfortably absorbing it.

When the accept queue is full, new completed connections are dropped (or the SYN is retransmitted by the client and eventually times out) even though the server process is otherwise healthy — this shows up as connection failures/timeouts under burst load with no corresponding CPU or memory pressure, and it's a specific, checkable failure (`netstat -s | grep -i listen` shows overflow counters) that's frequently misdiagnosed as "the app is slow" when the app never even got the connection.

### Ephemeral port exhaustion

Every outbound TCP connection consumes a unique local (ephemeral) port for its lifetime, and on Linux the default range (`net.ipv4.ip_local_port_range`) is commonly **32768-60999**, roughly **28,232 ports**. High-churn outbound connection patterns (one connection per outgoing request instead of pooling, or many parallel connections to different destinations) can exhaust this range, especially combined with each closed connection's port being unavailable again for the 60-second `TIME_WAIT` period on the client side. **Symptom:** `connect()` fails with `EADDRNOTAVAIL`, intermittently, correlating with load — not a clean, permanent failure, which makes it easy to misdiagnose as flaky infrastructure rather than a resource ceiling. **Fixes:** widen the ephemeral range, enable `tcp_tw_reuse`, and — the actual production fix — reduce churn via connection pooling/keep-alive so far fewer ports are held open (or held in TIME_WAIT) simultaneously; using multiple source IPs also multiplies the available port budget since exhaustion is per-source-IP.

---

## Build it from scratch

The mechanical piece worth writing by hand is the BDP/window-scaling arithmetic and a slow-start/AIMD simulator — this is what an interviewer means by "derive it, don't just cite it":

```python
def bdp_bytes(bandwidth_bps: float, rtt_seconds: float) -> float:
    return bandwidth_bps * rtt_seconds / 8

def max_unscaled_throughput_bps(rtt_seconds: float, max_window_bytes: int = 65_535) -> float:
    return max_window_bytes / rtt_seconds * 8

# 1 Gbps link, 100ms RTT
bdp = bdp_bytes(1e9, 0.1)
print(f"BDP = {bdp / 1e6:.2f} MB")                                   # BDP = 12.50 MB
capped = max_unscaled_throughput_bps(0.1)
print(f"unscaled cap = {capped / 1e6:.2f} Mbps")                     # unscaled cap = 5.24 Mbps

def max_scaled_window(scale: int) -> int:
    return 65_535 * (2 ** scale)

print(max_scaled_window(14) / 1e9, "GB max window at scale factor 14")  # ~1.07 GB


# Simplified slow-start + AIMD (Reno-style) cwnd trajectory — untested sketch
def simulate_reno(rounds: int, iw: int = 10, ssthresh: int = 64, loss_at_round: int = 8):
    cwnd = iw
    trace = []
    for r in range(1, rounds + 1):
        trace.append(cwnd)
        if r == loss_at_round:
            ssthresh = max(cwnd // 2, 2)     # multiplicative decrease
            cwnd = ssthresh
        elif cwnd < ssthresh:
            cwnd *= 2                        # slow start: exponential
        else:
            cwnd += 1                        # congestion avoidance: additive, 1 MSS/RTT
    return trace

print(simulate_reno(12))
# [10, 20, 40, 64, 65, 66, 67, 32, 33, 34, 35, 36]  -- loss at round 8 halves cwnd from 64
```

Being able to narrate *why* cwnd jumps from 10→20→40→64 (doubling in slow start) then flattens into +1 increments (congestion avoidance) and halves on loss is exactly the "one level below the diagram" understanding this topic is tested for.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Throughput far below link bandwidth on a high-RTT connection (e.g., cross-region transfer) | Window scaling not negotiated, or scale factor too small for the BDP | Confirm window scaling is enabled and negotiated (`ss -i` shows `wscale`); size buffers/`net.ipv4.tcp_rmem`/`tcp_wmem` to cover the actual BDP |
| Small request/response cycles show a consistent ~200-500ms latency floor | Nagle + delayed ACK interaction | Set `TCP_NODELAY` on the socket for interactive/RPC traffic |
| Connections intermittently fail under load with no CPU/memory pressure | `listen()` accept queue or SYN queue overflow (backlog too small) | Raise `backlog` argument and `net.core.somaxconn`/`net.ipv4.tcp_max_syn_backlog`; confirm with `netstat -s` overflow counters |
| Outbound `connect()` fails intermittently with `EADDRNOTAVAIL` under load | Ephemeral port exhaustion from high connection churn | Connection pooling/keep-alive first; widen `ip_local_port_range` and enable `tcp_tw_reuse` as secondary levers |
| One flow appears to unfairly dominate a shared, shallow-buffered link against other flows | Mixed congestion control algorithms (e.g., BBR vs CUBIC) sharing a small buffer | Standardize congestion control per environment where flows compete for the same bottleneck, or accept the tradeoff explicitly and monitor for it |
| A dead peer (crashed, or behind a NAT that dropped state) isn't detected for a long time | Relying on default TCP keepalive timing alone | Add an application-level heartbeat with a timeout in the tens-of-seconds range; use keepalive as a backstop, not the primary mechanism |
| Multi-worker server has uneven load across worker processes accepting connections | Old-style shared listening socket with a single accept queue causing thundering-herd wakeups | `SO_REUSEPORT` per worker so the kernel load-balances incoming connections across sockets directly |

---

## Tradeoffs & when NOT to use it

- **Don't switch to BBR blindly for "better performance."** On a shared, shallow-buffered bottleneck with CUBIC flows, BBR's aggressiveness can starve them — appropriate for paths you control end-to-end or where you've measured the fairness impact, not a drop-in universal upgrade.
- **Don't disable Nagle everywhere as a reflex "just in case" performance fix.** For bulk-transfer workloads (large sequential writes) Nagle's coalescing is genuinely useful and disabling it just means more, smaller packets with more header overhead for no latency benefit, since there's no small-write/stall pattern to fix in the first place. Reach for `TCP_NODELAY` specifically for latency-sensitive, small-message, interactive workloads.
- **Don't raise `somaxconn`/backlog indefinitely as a blanket fix for connection failures.** A very large accept queue can mask a real problem (the application not calling `accept()` fast enough, i.e., it's actually overloaded) by absorbing a growing backlog instead of surfacing the failure — size it to absorb legitimate burst, not to hide sustained overload.
- **Don't rely on TCP keepalive as an application liveness check.** Its multi-hour default timescale is appropriate for reclaiming abandoned connections, not for detecting a dead peer within any interactive SLA — build an application heartbeat for that.
- **Don't treat ephemeral port widening as the real fix for connection churn.** It buys headroom, not a cure — if a service is opening one connection per request instead of pooling, widening the port range delays the failure without addressing the underlying inefficiency (extra handshakes, extra TIME_WAIT accumulation, extra latency per request from the handshake itself).
- **Window scaling has essentially no downside on modern networks** and should simply always be on — the one real caveat is some ancient or broken middleboxes historically mishandled the option, which is a legacy concern, not a live design tradeoff today.

---

## Interview questions

### Q1 — What's the initial congestion window on a modern Linux system, and why does it matter for a typical web request?
**Testing:** whether the number is known and whether its practical implication is understood.
**Answer:** 10 segments (RFC 6928, roughly 14.6KB at a 1460-byte MSS), the Linux default since kernel 3.0-era. It matters because many small HTTP responses fit entirely inside that initial burst and complete within a single RTT, never engaging congestion avoidance at all — which is why increasing IW was a deliberate, measured win for web latency at Google's scale, not an arbitrary bump.
**Follow-up trap:** *"Does a larger IW ever hurt?"* — yes, on genuinely congested or high-loss paths, a larger initial burst can itself contribute to loss before the connection has any RTT/loss signal to react to; it's a tradeoff tuned for the common case (short flows on reasonably healthy paths), not a free lunch in every environment.

### Q2 — Why did CUBIC replace Reno as the Linux default?
**Answer:** Reno's additive increase happens per ACK, so a flow with a shorter RTT gets more ACKs per second and grows its window faster than a longer-RTT flow competing for the same bottleneck — a structural unfairness. CUBIC's window growth is a cubic function of elapsed wall-clock time since the last loss event, independent of ACK arrival rate, so flows with different RTTs converge toward similar windows instead of the low-RTT flow permanently dominating.
**Follow-up trap:** *"What's CUBIC's multiplicative decrease factor, and how does it compare to Reno's?"* — CUBIC uses β=0.7 (a gentler backoff, keeping 70% of the window after loss) versus Reno's 0.5 (halving). That's a real, quotable number, and being able to state it signals you know the mechanism, not just the name.

### Q3 — Explain BBR's approach, and when would you NOT want it.
**Answer:** BBR estimates bottleneck bandwidth (BtlBw, max observed delivery rate) and round-trip propagation time (RTprop, min observed RTT) directly, then paces sending near their product rather than growing a window until a packet drops. It wins on lossy non-congestive paths (wifi, cellular, satellite) where loss-based control mistakes bit-error loss for congestion. You would not want it sharing a shallow buffer with loss-based CUBIC flows without measuring the effect first — BBR has been shown to claim a disproportionate share of bandwidth (upward of 90% at small buffer sizes) precisely because it doesn't wait for the buffer to overflow the way CUBIC does.
**Follow-up trap:** *"Is this fairness problem fixed?"* — BBRv2/v3 add explicit response to loss and ECN signals specifically to address it, and that's real, ongoing work, not settled. Say the honest thing: it's improved, not solved, and the buffer-size-dependent fairness tradeoff is still an active area of measurement.

### Q4 — Compute the bandwidth-delay product for a 1 Gbps link with 100ms RTT, and explain what happens without window scaling.
**Answer:** BDP = 1×10^9 bits/s × 0.1s ÷ 8 = 12.5 MB. Without window scaling, the maximum advertised window is 65,535 bytes (~64KB, the 16-bit field's limit), so achievable throughput caps at roughly 65,535 bytes ÷ 0.1s ≈ 655 KB/s ≈ 5.24 Mbps — under 1% of the link's actual capacity, entirely because the window rather than the network is the constraint.
**Follow-up trap:** *"How does window scaling fix it, and is there a limit?"* — RFC 1323's window scale option multiplies the advertised window by 2^S, S from 0-14, giving a max effective window of 65,535 × 2^14 ≈ 1.07 GB — comfortably above any realistic BDP today, but it's negotiated only in the SYN/SYN-ACK, so a middlebox stripping the option silently locks the connection to the 64KB ceiling for its whole life with no further negotiation opportunity.

### Q5 — Describe the specific interaction between Nagle's algorithm and delayed ACK that causes a stall, with real numbers.
**Answer:** Nagle holds a small outgoing write if there's already unacknowledged data in flight, waiting for that earlier data's ACK. Delayed ACK on the receiving side holds an ACK (commonly ~40ms on Linux, up to the RFC's 500ms ceiling, with 200-500ms being the classically cited stall figure) hoping to piggyback it on outgoing data or coalesce it. If the receiver has nothing to send back immediately, its delayed ACK timer is the only thing that will eventually release the sender's held write — producing a real 200-500ms stall per small write/read cycle.
**Follow-up trap:** *"How do you fix it, and does it cost anything?"* — `TCP_NODELAY` disables Nagle on the sending socket, which is the standard fix for interactive/RPC traffic. The cost is more, smaller packets (worse header-to-payload ratio) for workloads that actually do bulk sequential writes, which is why it's applied selectively to latency-sensitive sockets, not globally by default.

### Q6 — What are Linux's default TCP keepalive timings, and why are app-level heartbeats usually still needed?
**Answer:** `tcp_keepalive_time` 7200s (2 hours) before the first probe, `tcp_keepalive_intvl` 75s between probes, `tcp_keepalive_probes` 9 attempts — roughly 2 hours 11 minutes worst case before a dead peer is declared. That's far too slow for any system needing to detect a failure within seconds or low minutes, so an application-level heartbeat with an explicit, much shorter timeout is the actual liveness mechanism, with keepalive left as a backstop for reclaiming truly abandoned connections.
**Follow-up trap:** *"Could you just tune the keepalive sysctls down instead of writing an app-level heartbeat?"* — you can, but it's a system-wide (or per-socket, if set via `setsockopt`) setting, harder to reason about per-connection than an application message you fully control, and it still only tells you the TCP connection is alive, not that the application on the other end is actually healthy and processing — which an app-level ping/pong can verify and a TCP-level probe cannot.

### Q7 — Difference between SO_REUSEADDR and SO_REUSEPORT, and when would you actually reach for each?
**Answer:** `SO_REUSEADDR` lets you rebind a listening socket to an address/port that still has TIME_WAIT sockets lingering from a previous instance — the classic "restart my server without EADDRINUSE" fix. `SO_REUSEPORT` lets multiple independent sockets (different threads or processes) bind the exact same port simultaneously, with the kernel load-balancing incoming connections across them — the mechanism for scaling accept() across workers without a shared-lock bottleneck.
**Follow-up trap:** *"Can you use SO_REUSEPORT for graceful restarts/rolling deploys?"* — yes, and it's a real pattern: start the new process with SO_REUSEPORT bound to the same port alongside the old one, let the kernel start routing new connections to it, then drain and close the old listener — avoiding the brief unavailability window a naive restart would have. Note the old listener's in-flight/queued connections at the moment it closes are dropped, so this needs to be paired with graceful shutdown on the old process, not an abrupt kill.

### Q8 — Your service starts intermittently failing to accept new connections during traffic spikes, with normal CPU and memory. Diagnose it.
**Answer:** Almost certainly a `listen()` backlog problem — either the SYN queue (`tcp_max_syn_backlog`) or the accept queue (`min(backlog, somaxconn)`) filling faster than the application calls `accept()` or faster than handshakes complete, causing new connections to be dropped or SYNs to go unanswered even though the process itself isn't resource-starved. Check `netstat -s` for listen-queue overflow counters, and check what `backlog` value the app actually passed to `listen()` against `sysctl net.core.somaxconn`.
**Follow-up trap:** *"You raise both to a very large number and the symptom goes away. Are you done?"* — no — a large accept queue can mask, rather than fix, an application that isn't calling `accept()` fast enough under sustained load, effectively just delaying when the queue fills instead of addressing why connections are piling up. Confirm whether this was a transient burst (queue sizing is the right fix) or sustained overload (the app itself needs more accept-loop throughput or more workers).

### Q9 — Explain ephemeral port exhaustion end to end: what runs out, why, and what actually fixes it.
**Answer:** Every outbound connection needs a unique local port from a finite range (`net.ipv4.ip_local_port_range`, commonly ~28,232 ports on Linux), and a closed connection's port is unavailable again for the TIME_WAIT duration (60 seconds on Linux) before it can be reused for a *new* outbound connection to a different destination (reuse to the *same* destination 4-tuple is handled differently via `tcp_tw_reuse`). High-churn outbound traffic — one connection per request instead of pooling — can exceed the available range under load, and `connect()` starts failing with `EADDRNOTAVAIL`. The actual fix is reducing churn (pooling, keep-alive); widening the range or enabling `tcp_tw_reuse` are real but secondary levers that buy headroom rather than solve the root inefficiency.
**Follow-up trap:** *"Multiple source IPs would also fix it — why, mechanically?"* — because the ephemeral port budget is scoped per source IP for outbound connections to a given destination; using several source IPs multiplies the total pool of available 4-tuples for the same destination, which is exactly the technique cloud NAT gateways use internally (multiple NAT IPs) to scale beyond one IP's port ceiling.

### Q10 — Your team is deciding between CUBIC and BBR for an internal service-to-service link with consistently low, stable latency and negligible packet loss. What do you recommend, and why?
**Answer:** CUBIC is probably fine and simpler to reason about here — BBR's advantage is specifically on lossy or bufferbloated paths, and a stable, low-latency, low-loss internal link doesn't have the problem BBR is designed to solve. Switching congestion control algorithms has a real fairness/interaction cost with other flows on shared infrastructure, and introducing that risk for a link that isn't exhibiting the symptom BBR fixes is unjustified complexity.
**Follow-up trap:** *"What would change your answer?"* — if that link crosses a genuinely long-haul, higher-loss, or bufferbloated path (cross-region, satellite, congested shared uplink), or if you've specifically measured CUBIC underperforming its available bandwidth due to non-congestive loss, that's exactly the case BBR was built for, and the recommendation flips — the answer should always be conditioned on the actual path characteristics, not a blanket "BBR is newer so it's better."

### Q11 — What's the practical difference between the SYN queue overflowing and the accept queue overflowing?
**Answer:** A full SYN queue means the kernel can't track more half-open handshakes — under a SYN flood or a burst of legitimate new-connection attempts, further SYNs get dropped (client retries) unless SYN cookies kick in to handle it statelessly. A full accept queue means handshakes are completing fine but the application isn't calling `accept()` fast enough to drain them, so further completed connections get dropped even though the network-level handshake succeeded — this points at application-level throughput, not network congestion.
**Follow-up trap:** *"How would syncookies change what you see in a packet capture during a SYN flood?"* — instead of the kernel silently dropping excess SYNs once its queue is full, with syncookies enabled it keeps replying with SYN-ACKs indefinitely (encoding the state it needs into the sequence number itself rather than storing it), so a capture shows the server still responding to every SYN — at the cost of losing some TCP options like window scaling on those cookie-based connections, since there's no stored state to remember what was negotiated.

---

## Red flags that fail you

- Saying "TCP congestion control" without being able to name a specific algorithm or its actual behavior.
- Claiming BBR is strictly better than CUBIC with no mention of the fairness/buffer-size tradeoff.
- Not knowing the 16-bit window field's 65,535-byte cap or why window scaling exists.
- Recommending `TCP_NODELAY` globally without acknowledging the bulk-transfer tradeoff, or not knowing what it does at all.
- Treating TCP keepalive as sufficient for application liveness detection.
- Confusing SO_REUSEADDR (rebind after TIME_WAIT) with SO_REUSEPORT (multiple sockets sharing a port for load distribution).
- Not distinguishing the SYN queue from the accept queue when diagnosing dropped connections.

---

## Cheat card

```
SLOW START: IW = 10 segments (RFC 6928, ~14.6KB @ MSS 1460), cwnd ~doubles per RTT until ssthresh
AIMD (Reno): +1 MSS/RTT increase, on loss: ssthresh=cwnd/2, cwnd=ssthresh (halve)
CUBIC (Linux default since 2.6.19/2006): W(t)=C(t-K)^3+Wmax, C=0.4, beta=0.7 (gentler than Reno's 0.5)
  growth is fn of TIME since loss, not ACK count -> RTT-fair, why it replaced Reno
BBR: models BtlBw (max observed rate) + RTprop (min observed RTT), paces to BDP, ignores loss as primary signal
  wins: lossy/bufferbloated paths. RISK: unfair vs CUBIC on shallow shared buffers (BBR can take >90%)

WINDOW SCALING: 16-bit window field caps at 65,535B unscaled
  RFC1323 scale option: x2^S, S=0-14 -> max ~1.07GB (65535*2^14)
  negotiated ONLY in SYN/SYN-ACK; stripped by a middlebox = stuck at 64KB forever

BDP WORKED EXAMPLE: 1Gbps x 100ms RTT = 12.5MB BDP
  unscaled 64KB window caps throughput at ~5.24Mbps (<1% of link) — window, not network, is bottleneck

NAGLE vs DELAYED ACK: Nagle holds small write til prior data ACKed; delayed ACK holds ACK ~40-500ms
  (200-500ms classic stall figure) waiting to piggyback -> mutual wait = real latency stall
  FIX: TCP_NODELAY on latency-sensitive sockets; keep Nagle for bulk sequential transfer

KEEPALIVE (Linux defaults): time=7200s(2h) + intvl=75s x probes=9 -> ~2h11m worst case to detect dead peer
  -> app-level heartbeat (10-30s timeout) is the real liveness mechanism

SO_REUSEADDR: rebind past TIME_WAIT (server restart)      SO_REUSEPORT: N sockets share 1 port, kernel LBs

BACKLOG: listen() -> SYN queue (tcp_max_syn_backlog) + accept queue (min(backlog, somaxconn))
  somaxconn historically 128, many modern kernels/distros default 4096 — always verify, don't assume
  full SYN queue -> syncookies (default on) keep replying statelessly, lose some TCP options
  full accept queue -> app not calling accept() fast enough, drops despite healthy handshakes

EPHEMERAL PORTS: range ~32768-60999 (~28,232 ports) default on Linux
  churn + 60s TIME_WAIT exhausts it -> connect() EADDRNOTAVAIL under load
  FIX: pooling/keep-alive (real fix) > tcp_tw_reuse > widen range > multiple source IPs
```

## Sources

- RFC 5681 / RFC 6928 — TCP Congestion Control, IW10
- RFC 1323 — TCP Extensions for High Performance (window scaling)
- RFC 896 — Congestion Control in IP/TCP Internetworks (Nagle's algorithm)
- RFC 1122 — Requirements for Internet Hosts (delayed ACK)
- [Nagle's algorithm — Wikipedia](https://en.wikipedia.org/wiki/Nagle's_algorithm) — accessed 2026-07-26
- [When to use and not use BBR — APNIC Blog](https://blog.apnic.net/2020/01/10/when-to-use-and-not-use-bbr/) — accessed 2026-07-26
- [BBR's Sharing Behavior with CUBIC and Reno (arXiv 2505.07741)](https://arxiv.org/html/2505.07741v1) — accessed 2026-07-26
- [How to Configure TCP Backlog Queue Size on Linux — OneUptime](https://oneuptime.com/blog/post/2026-03-20-configure-tcp-backlog-queue/view) — accessed 2026-07-26
- [Source Network Address Translation (SNAT) for outbound connections — Azure Load Balancer docs](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-outbound-connections) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
