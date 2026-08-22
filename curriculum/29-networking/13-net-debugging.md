# Network Debugging: tcpdump, Wireshark, ss/netstat, dig, traceroute, mtr, curl -v

> **Track:** T29 Networking & Protocols · **Time:** 3h · **Prereqs:** T29-tcp-deep, T29-tls, T29-dns-lb · **Updated:** 2026-07-26
> **Module id:** `T29-net-debugging` · **Tags:** debugging, critical

## The 30-second version

Network debugging is pattern matching between a symptom and the layer that's lying to you: "connection refused" means something answered and said no (check the listener and firewall reject rules), "timed out" means silence (check reachability and firewall drop rules), "reset mid-stream" means something actively killed an established connection (check crashes, resource limits, stateful firewalls). `curl -w` timing splits a slow request into DNS/connect/TLS/TTFB/transfer so you stop guessing which phase is slow. `ss`/`netstat` tell you what's listening and what state your connections are in; `dig`/`+trace` tell you what DNS actually resolved to and from where; `tcpdump`/Wireshark show you the literal bytes when everything above lies. The discipline is: form a hypothesis about which layer is broken, then pick the one tool that would falsify it fastest, rather than opening Wireshark first for a problem `curl -v` would have shown in five seconds.

## Why this gets asked

Because whiteboard system design tests architecture and this tests whether you've actually been on call. The interviewer has spent 45 minutes going down the wrong path on a production incident because someone said "the network is slow" without isolating which hop, and they want to see you narrow a vague symptom to a specific broken component using the smallest number of tool invocations, in the right order.

---

## Lineage: past → present → future

**What came before.** Before tcpdump, network debugging meant `printf`/log statements sprinkled through application code and hoping the failure reproduced with logging turned up, plus vendor-specific packet analyzers that cost thousands of dollars and ran on dedicated hardware. Van Jacobson, Sally Floyd, Vern Paxson and Steven McCanne released tcpdump in 1988 out of Lawrence Berkeley National Laboratory, built on the BSD Packet Filter (BPF) they'd also written, and for the first time a working engineer could see the literal bytes on the wire on a general-purpose Unix box instead of inferring behavior from application-level log lines. Wireshark's lineage starts as Ethereal, released by Gerald Combs in 1998 (renamed Wireshark in 2006 after a trademark dispute), which added a GUI and protocol dissectors on top of the same capture model, turning "read the pcap by hand" into "click through a decoded, filterable timeline." The pain both tools killed: "check the logs" telling you the application's opinion of what happened, with no independent way to verify whether the network agreed — and that gap only widened as traffic became encrypted (so a capture showed ciphertext, not intent) and services became containerised (so "the box" stopped being a stable, single-process thing you could reason about from one vantage point).

**Where it stands now.** tcpdump and Wireshark remain the definitive source of truth when something above them is lying — an application log can be wrong, missing, or written by code that never ran the failing path; a packet capture cannot lie about what was actually on the wire. But they are also now frequently the slowest way to get an answer. eBPF-based tools (bpftrace, Cilium's Hubble, Pixie) can answer "which service, which syscall, which container" without a capture file at all, and service-mesh telemetry (Envoy/Istio access logs, distributed traces) increasingly answers the question before anyone opens a terminal. The live tension: packet-level truth is unambiguous but requires you to already suspect the network; eBPF and trace telemetry are faster and more convenient but are themselves software that can have blind spots or bugs of their own, so for anything security-sensitive or genuinely mysterious, experienced engineers still reach for a capture to arbitrate between competing stories.

**Where it's heading.** eBPF-based continuous profiling and always-on network observability (Cilium, Pixie, Parca) are pushing toward "the trace already exists before you knew to ask" rather than "capture now and hope it reproduces" — this is real and shipping today, not speculative. What is genuinely reshaping the field is that encrypted traffic keeps closing off tcpdump's traditional visibility (TLS 1.3 encrypts more of the handshake itself than TLS 1.2 did, and QUIC/HTTP3 encrypts transport-layer metadata that used to be plainly visible to a packet capture), which is pushing more debugging effort up into application-layer instrumentation — structured logging, tracing, and mesh sidecars that see plaintext before it's encrypted. How far this goes, and whether packet capture becomes a genuine last-resort niche tool rather than a routine one, is the speculative part; the more defensible claim is that it stays this mechanically relevant for anything below the application layer (routing, MTU, raw TCP behavior) for a long time yet, even as its share of day-to-day debugging keeps shrinking.

---

## Mental model

Symptom triage is a bisection over layers, not a guess: you ask "which layer is lying" in order, and each tool exists to answer exactly one layer's question and no more.

```
                     "it's slow" / "it's broken"  (vague symptom)
                                     |
                                     v
                     bisect the stack -- don't guess, confirm each
                     layer before blaming the next one
                                     |
      +---------------+---------------+---------------+----------------+
      |               |               |               |                |
   DNS layer       TCP layer       TLS layer       HTTP layer      app logic
      |               |               |               |                |
 "did the name   "did the byte   "did the       "did the           "did the
  resolve, and    stream get      handshake      response arrive    handler
  to the right    established?"   negotiate a    with the right     itself
  IP?"                            cipher/cert?"  status/body,       misbehave
      |               |               |          how fast?"        or hang?"
      v               v               v               v                v
 dig +trace      nc -zv host    openssl         curl -v /          app logs,
 dig @resolver    port          s_client         curl -w            tracing,
 (bypass cache)   (TCP only,    -servername      (splits DNS/       APM,
                  no TLS/HTTP)  (chain, verify    connect/TLS/       distributed
                                return code)      TTFB/transfer)     traces

 tcpdump/Wireshark only enter the picture once every layer above has
 answered "not me" and you need the literal bytes to arbitrate between them.
```

The principle: work outward-in, confirming one layer at a time, so "it's slow" becomes "DNS resolved in 3ms, TCP connected in 1ms, TLS took 40ms, TTFB was 4.2s" — and now you know exactly which layer to point at without ever opening a capture.

---

## Playbook: symptom → tool → what to look for

### Symptom: "Connection refused"

**What it means:** Something at the destination *actively* rejected the connection attempt — either no process is listening on that port (the OS itself sends a TCP RST in response to the SYN), or a firewall rule is configured to `REJECT` (not `DROP`) and sends the RST on the firewall's behalf. Either way, you got an answer, fast.

**Tool:** `ss -tlnp` (or `netstat -tlnp` if `ss` isn't available) on the target host to check if anything is actually listening.
```
ss -tlnp | grep :8080
# empty output = nothing is listening; that's your answer already
```
If something *is* listening but you still get refused from a different host, check firewall rules (`iptables -L`, security groups, NACLs) for an explicit reject.

### Symptom: "Connection timed out"

**What it means:** Silence. Either the packet never reached the destination (routing issue, no route, host truly unreachable) or it reached a firewall configured to `DROP` (not reject) — a dropped SYN gets no response at all, so the client just waits out its own connect timeout (often 30-75s depending on OS/app defaults) and gives up. Critically, a timeout tells you *nothing* about the far end — you cannot distinguish "host is down" from "firewall silently dropped it" from this symptom alone.

**Tool:** `traceroute`/`mtr` to see how far the packets get before responses stop; `nc -zv host port` to confirm without full protocol overhead.
```
mtr -rw -c 20 target-host          # report mode, 20 packets, see where it stops
nc -zv target-host 443             # -z scan mode, -v verbose; times out if silently dropped
```

### Symptom: "Connection reset"

**What it means:** The connection was **established** (SYN/SYN-ACK/ACK completed) and then actively killed with an RST mid-stream — different from refused, where nothing was ever accepted. Causes: the server process crashed or was killed while a connection was open, a stateful firewall/load balancer decided the connection was idle or invalid and killed it, or the server explicitly reset (e.g., a backlog queue overflow triggers a RST on some stacks instead of silently dropping).
**Tool:** application/server logs correlated by timestamp with the client-observed reset (did the process restart, OOM, or crash at that moment); `tcpdump` capturing the RST itself to see which side sent it and whether it carried any of the connection's prior data.
```
tcpdump -i any 'tcp[tcpflags] & tcp-rst != 0' -n
```

### Symptom: "Slow request, don't know why"

**Tool:** `curl -w` with a timing format string, isolating each phase.
```
curl -o /dev/null -s -w \
  "dns:%{time_namelookup} connect:%{time_connect} tls:%{time_appconnect} \
ttfb:%{time_starttransfer} total:%{time_total}\n" \
  https://example.com/api
```
Read it as deltas, not absolutes: `time_namelookup` alone is DNS; `time_connect - time_namelookup` is TCP handshake; `time_appconnect - time_connect` is TLS handshake; `time_starttransfer - time_appconnect` is server think-time (this is almost always where the problem is — the server received the request and took a long time to start responding, i.e. TTFB); `time_total - time_starttransfer` is transfer time (large payload or slow client link). A high `time_namelookup` alone points you straight at DNS, not the application.

### Symptom: "Intermittent packet loss"

**Tool:** `mtr`, not a one-shot `traceroute` — you need loss *over time* per hop, not a single snapshot.
```
mtr -rw -c 100 target-host
```
Look at the `Loss%` column per hop. A hop showing loss that *disappears* at the next hop is usually an ICMP rate-limiting artifact on that router, not real loss (routers commonly deprioritize ICMP responses to themselves while forwarding the actual traffic fine) — real loss is loss that *persists* from a hop onward to the destination. One-shot `traceroute` gives you a single sample per hop, which can't distinguish a transient blip from sustained loss.

### Symptom: "TLS handshake failing"

**Tool:** `openssl s_client` for a raw manual handshake, `curl -v` for the higher-level view including cert chain.
```
openssl s_client -connect example.com:443 -servername example.com
# read: certificate chain, verify return code, negotiated protocol/cipher

curl -v https://example.com 2>&1 | grep -A5 "certificate"
```
Look for: `verify return code` other than `0 (ok)` (chain/trust problem), a certificate `CN`/SAN mismatch against the hostname you connected to, an expired `notAfter` date, or a protocol version mismatch (client offering only TLS 1.3, server capped at 1.2 or vice versa — visible in `curl -v`'s handshake log as an immediate failure with no cert exchanged at all).

### Symptom: "High connection count / port exhaustion"

**Tool:** `ss -s` for a state summary, `ss -tan` for the full breakdown by state, counting `TIME_WAIT`.
```
ss -s                              # summary: total, tcp, established, etc.
ss -tan state time-wait | wc -l    # count of sockets stuck in TIME_WAIT
```
A large `TIME_WAIT` count on a client making many short-lived outbound connections (common in a service hammering a downstream with a new connection per request instead of pooling) exhausts the ephemeral port range (default range is often ~32768-60999, roughly 28,000 ports on Linux) and manifests as `EADDRNOTAVAIL`/connect failures once exhausted. Fix is connection pooling/reuse, not a bigger port range as the primary answer, though `net.ipv4.tcp_tw_reuse` can help on the specific box.

### Symptom: "Is the process actually listening?"

**Tool:** `ss -tlnp` (or `netstat -tlnp`), which shows listening TCP sockets with the owning process.
```
ss -tlnp
# State LISTEN, Local Address:Port 0.0.0.0:8080, Process users:(("myapp",pid=1234,fd=6))
```
`0.0.0.0` means listening on all interfaces; `127.0.0.1` means loopback only — a very common "works locally, unreachable from another host" bug is a service bound to loopback instead of `0.0.0.0` or the actual interface IP.

### Symptom: "Which process owns this connection?"

**Tool:** `ss -tp` (shows PID for established connections too, not just listeners) or `lsof -i` for a per-file-descriptor view.
```
ss -tp state established '( dport = :443 )'
lsof -i :443
```

### Symptom: "DNS resolving to the wrong/stale IP"

**Tool:** `dig +trace` to see the actual resolution path from root down, and `dig @specific-resolver` to bypass your local cache and compare.
```
dig +trace example.com
dig @8.8.8.8 example.com                 # query a specific public resolver directly
dig example.com +noall +answer           # just the answer, with the TTL shown
```
If `dig @8.8.8.8` returns a different (correct) answer than your local resolver, the problem is a stale cache somewhere between you and that resolver — check the TTL in the answer, and check your OS/app-level DNS cache next (some app runtimes cache independently of the OS).

### Symptom: "Need to see the actual bytes on the wire"

**Tool:** `tcpdump` for capture (with a filter, not everything — capturing unfiltered on a busy interface is both slow and produces an unreadable amount of data), Wireshark for interactive analysis of the resulting capture.
```
# tcpdump filter syntax, real examples:
tcpdump -i eth0 host 10.0.0.5 and port 443 -w capture.pcap
tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0' -n   # SYN only, no ACK = new connection attempts
tcpdump -i eth0 'tcp[tcpflags] & tcp-rst != 0' -n                                     # resets only
tcpdump -i eth0 'port 53' -n                                                          # DNS traffic
```
Equivalent Wireshark display filters (applied after capture, or live):
```
tcp.flags.syn==1 && tcp.flags.ack==0        # new connection attempts (SYN only)
tcp.flags.reset==1                          # resets
http.response.code >= 400                   # HTTP errors
tls.handshake.type==1                       # TLS ClientHello
tls.handshake.type==2                       # TLS ServerHello
dns.flags.rcode != 0                        # DNS errors (NXDOMAIN, SERVFAIL, etc.)
```

### Symptom: "Test if a port is reachable without curl"

**Tool:** `nc -zv host port` (zero-I/O scan mode, verbose) — confirms TCP reachability without invoking any application protocol.
```
nc -zv example.com 443
# Connection to example.com 443 port [tcp/https] succeeded!
```

### Symptom: "Reproduce a raw TCP/TLS session manually"

**Tool:** `nc` for raw TCP, `openssl s_client` for TLS, both letting you type the application protocol by hand and see exactly what's sent/received.
```
nc example.com 80
GET / HTTP/1.1
Host: example.com

# (blank line required to terminate the request)

openssl s_client -connect example.com:443 -servername example.com -quiet
GET / HTTP/1.1
Host: example.com

```
This is the single best tool for isolating "is this an application bug or a network/TLS bug" — if you can complete an HTTP exchange by hand with `nc`/`openssl s_client` but your application client fails, the bug is in the client's protocol handling, not the network.

---

## How it actually works (the mechanics behind the symptoms)

**RST vs silent drop, at the packet level.** A `REJECT` firewall rule or an OS with no listener responds to an inbound SYN with a TCP RST — this is a real packet, visible in a `tcpdump` capture, and it's why "refused" is fast (one round trip, then a definitive failure). A `DROP` rule does nothing at all — no packet leaves the firewall in response — so the client's own retransmission and connect-timeout logic is the only thing that eventually gives up, and this is why "timed out" is slow and gives you zero information about where the problem is: the packet could have vanished at the first hop or the last one.

**TIME_WAIT exists for a correctness reason**, not as a bug: after actively closing a connection, the closing side holds the socket in `TIME_WAIT` for 2×MSL (maximum segment lifetime, commonly resulting in ~60s on Linux defaults) so that any delayed/duplicate packets from the old connection can't be misattributed to a new connection that happens to reuse the same 4-tuple. The operational pain is real even though the mechanism is correct: a client opening a new outbound connection per request accumulates `TIME_WAIT` sockets faster than they expire, consuming ephemeral ports.

**`curl -w` timers are cumulative, not per-phase**, which is the detail people get wrong reading the output cold — `time_starttransfer` is measured from the start of the request, not from when TLS finished, so you must subtract the previous phase's value to get that phase's actual duration.

---

## Build it from scratch

Not a from-scratch implementation module — the tools themselves are the artifact. What belongs here instead is the decision tree to run in an actual incident, in order:

1. `curl -v` (or `-w` timing) first, always — cheapest, highest signal-to-effort ratio, tells you DNS/connect/TLS/TTFB/transfer in one shot.
2. If DNS looks wrong: `dig +trace` and `dig @specific-resolver` to localize whether it's your cache or the authoritative chain.
3. If connect/TLS looks wrong: `nc -zv` to isolate TCP reachability from TLS specifically, then `openssl s_client` if TCP is fine but TLS fails.
4. If it's intermittent: `mtr` over enough packets/time to separate transient ICMP deprioritization from real sustained loss.
5. Only reach for `tcpdump`/Wireshark when the above haven't localized the problem, or when you need to see something none of them expose (malformed payload content, unexpected retransmissions, out-of-order segments) — it's the highest-fidelity tool and also the slowest to get signal from.

---

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `curl` hangs, no error, for exactly the timeout duration | Firewall silently dropping SYN (not rejecting) | Confirm with `mtr`/`nc -zv`; fix the drop rule or route, don't just raise the client timeout |
| Intermittent 502/504 from a load balancer | Backend closing idle keep-alive connections the LB still thinks are open | Align backend idle timeout to be *longer* than the LB's, not shorter |
| `EADDRNOTAVAIL` under load on an outbound-heavy service | Ephemeral port exhaustion from many short-lived unpooled connections stuck in `TIME_WAIT` | Connection pooling/keep-alive reuse; `ss -s`/`ss -tan state time-wait \| wc -l` to confirm before changing anything |
| TLS handshake fails only from one specific network | A middlebox (corporate proxy, old firewall) stripping or mishandling a TLS extension (commonly SNI or a newer cipher list) | `openssl s_client` from inside vs outside that network to compare ClientHello handling; check for a proxy intercepting TLS |
| DNS answer is correct from `dig @8.8.8.8` but wrong from the app | Stale OS-level or app-runtime DNS cache | Check app-level DNS cache TTL settings; restart/flush the specific cache layer, not just wait |
| One hop in `mtr` shows 30% loss, everything past it shows 0% | ICMP rate-limiting/deprioritization on that router, not real loss | Confirm actual application traffic isn't affected (test the real protocol, not just ICMP) before treating it as a real network problem |
| `tcpdump` capture file is enormous and unusable | No filter applied on a busy interface | Always filter by host/port at minimum; write to file and analyze in Wireshark rather than watching unfiltered live output |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `tcpdump`/Wireshark first.** It's the slowest tool to get an answer from for most symptoms — `curl -v`, `dig`, and `nc -zv` answer the majority of "is it reachable / is it DNS / is it TLS" questions in seconds with far less noise.
- **Don't run `mtr`/`traceroute` unfiltered as your only diagnostic for application-layer slowness.** A perfectly clean network path (0% loss, low latency) says nothing about whether the *application* on the other end is slow — that's what `curl -w`'s TTFB isolates.
- **Don't capture packets on a production interface without a filter and a plan for the file size** — an unfiltered capture on a busy host can itself impact performance and fills disk fast.
- **`nc -zv` tells you TCP reachability, nothing about the application protocol.** A port can be open and accepting TCP connections while the service behind it is completely broken at the HTTP/TLS layer — don't stop at "the port is reachable" and call it healthy.
- **One-shot `traceroute` is the wrong tool for intermittent loss** — a single sample can't distinguish a one-time blip from a sustained problem; use `mtr` in report mode over enough packets.

---

## Interview questions

### Q1 — A client reports "connection refused." What does that tell you, and what's your first command?
**Testing:** whether refused/timeout/reset are understood as distinct, informative signals, not synonyms for "broken."
**Answer:** Refused means something at the destination actively answered no — either no listener on that port (OS sends RST) or a firewall explicitly rejecting. First command: `ss -tlnp` on the target to confirm whether anything is actually listening on that port and interface.
**Follow-up trap:** *"The process is listening on `127.0.0.1:8080` and the client is a different host. Explain the refusal."* — the service is bound to loopback only, so it's genuinely not reachable from outside that host regardless of firewall state; the fix is binding to `0.0.0.0` or the specific interface IP, not a firewall change.

### Q2 — Contrast "connection timed out" with "connection refused" in terms of what each tells you about the failure location.
**Answer:** Refused is fast and informative — you got a real response (an RST), so you know the destination is reachable and something there actively said no. Timed out is slow and uninformative — silence could mean the packet never left your network, was dropped anywhere along the path, or the destination is genuinely unreachable; you cannot localize the failure from the symptom alone.
**Follow-up trap:** *"Client waited exactly 30 seconds then failed — is that a network problem?"* — that's the client's own connect-timeout firing, not a network-reported failure; it tells you nothing except that no response arrived in time, so the next step is `mtr`/`nc -zv` to see how far packets actually get, not adjusting the client timeout as a fix.

### Q3 — Walk me through diagnosing a slow API endpoint using only `curl`.
**Answer:** `curl -o /dev/null -s -w` with a format string printing `time_namelookup`, `time_connect`, `time_appconnect`, `time_starttransfer`, `time_total`. Subtract consecutive values to get each phase's actual duration: DNS, TCP connect, TLS handshake, server think-time (TTFB), and transfer. In the overwhelming majority of real "slow API" cases, the gap between `time_appconnect` and `time_starttransfer` (server processing time) dominates.
**Follow-up trap:** *"`time_namelookup` is 2 seconds on every request, even repeated ones. What does that tell you?"* — DNS resolution is happening fresh on every single request rather than being cached — check whether the client is honoring DNS TTL/caching at all (a common bug in naive HTTP clients that resolve on every call), since 2s repeated on every request is not what a cache hit looks like.

### Q4 — How do you tell the difference between transient packet loss and a real, sustained network problem?
**Answer:** Use `mtr` in report mode over a meaningful sample size (dozens to hundreds of packets), not a one-shot `traceroute`. Look for loss that *persists* from a given hop through to the destination versus loss that appears at one hop and disappears at the next — the latter is usually ICMP deprioritization on that specific router (it's slow to respond to probes about itself while forwarding real traffic just fine), not actual loss affecting your traffic.
**Follow-up trap:** *"The loss disappears at the next hop — are you confident that's just ICMP rate limiting and not real loss?"* — confirm by testing the actual application protocol (not ICMP) end-to-end — if real traffic (a TCP connection, an HTTP request) shows no degradation, the ICMP loss reading was a red herring; if the app-level traffic is also affected, treat it as real.

### Q5 — A TLS handshake fails only for users on one corporate network. How do you isolate the cause?
**Answer:** `openssl s_client -connect host:443 -servername host` from both inside and outside that network to compare what each side's handshake actually negotiates — look for a mismatched or truncated cipher/protocol list, or a proxy substituting its own certificate (visible as an unexpected issuer in the cert chain). This is the classic signature of a corporate TLS-inspecting proxy or an old firewall stripping a modern TLS extension like SNI.
**Follow-up trap:** *"`curl -v` shows a cert chain that doesn't match what you expect at all — a totally different issuer."* — that's a middlebox performing TLS interception (a corporate proxy re-signing traffic with its own CA); the fix isn't on your server at all, it's a client-network-side certificate trust configuration, and you should say so rather than chase a server-side TLS bug that doesn't exist.

### Q6 — Explain what `TIME_WAIT` is for, and how it causes port exhaustion.
**Answer:** After actively closing a connection, the closer holds the socket in `TIME_WAIT` for roughly 2×MSL (often ~60s on Linux) so any stray/delayed packets from the old connection can't be misdelivered to a new connection reusing the same 4-tuple — it's a correctness mechanism, not a bug. The operational problem: a service opening a new short-lived outbound connection per request accumulates `TIME_WAIT` sockets faster than they expire, exhausting the ephemeral port range (commonly ~28,000 ports) and causing new outbound connects to fail.
**Follow-up trap:** *"How do you confirm this is actually your problem before changing anything?"* — `ss -s` for an overall count and `ss -tan state time-wait | wc -l` for the specific count, correlated with connect failures in time; the fix is connection pooling/reuse in the application, not blindly tuning `tcp_tw_reuse` as a first response.

### Q7 — Give the `tcpdump` filter for capturing only new outbound TCP connection attempts, and the Wireshark equivalent.
**Answer:** `tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0 and tcp[tcpflags] & tcp-ack == 0'` — SYN set, ACK not set, which is exactly a new connection attempt (not the SYN-ACK reply). Wireshark equivalent: `tcp.flags.syn==1 && tcp.flags.ack==0`.
**Follow-up trap:** *"How would you capture just the resets, and why might you want that specifically?"* — `tcpdump 'tcp[tcpflags] & tcp-rst != 0'` / Wireshark `tcp.flags.reset==1` — useful to correlate an application-level "connection reset" error with exactly which side sent the RST and at what point in the exchange, which application logs alone often can't show you.

### Q8 — `dig` against your local resolver returns a stale IP. What do you check next?
**Answer:** `dig @8.8.8.8 example.com` (or another public resolver) to see if the stale answer is specific to your local/corporate resolver's cache or if it's actually the authoritative record that hasn't updated. If the public resolver has the right answer, the problem is a cache between you and it (your OS resolver, a local DNS cache, or your ISP's resolver) that hasn't honored or has overridden the TTL.
**Follow-up trap:** *"Both `dig @8.8.8.8` and your local resolver show the correct new IP, but your application still connects to the old one."* — the application runtime itself (or a library) has its own independent DNS cache separate from the OS resolver — this is common in JVM-based and some connection-pooling HTTP clients — check and flush/restart at that layer specifically.

### Q9 — What does `ss -tlnp` show that `ss -tp` doesn't, and vice versa?
**Answer:** `ss -tlnp` (`-l` for listening) shows sockets in the `LISTEN` state with their owning process — answers "is anything actually listening on this port." `ss -tp` without `-l` shows established connections with owning process — answers "which process owns this specific active connection," useful for tracking down what's holding a connection open or generating unexpected traffic.
**Follow-up trap:** *"`ss -tlnp` shows nothing for a port you know the service uses. What are the possibilities?"* — the service isn't actually running, it crashed after startup, it's listening on a different interface/port than expected (check for `127.0.0.1` vs `0.0.0.0` binding), or you're checking on the wrong host/container/namespace entirely (a common miss in containerized environments where `ss` inside one container doesn't see another's sockets).

### Q10 — You need to prove whether a bug is in your HTTP client library or in the network/server. How do you isolate it with just `nc`?
**Answer:** Manually reproduce the raw exchange: `nc host 80`, type a well-formed `GET / HTTP/1.1` request with a `Host` header and a trailing blank line, and see if you get a valid HTTP response back. If the manual raw exchange succeeds but your client library fails against the same host, the bug is in the client's request construction or protocol handling, not the network or server.
**Follow-up trap:** *"The target is HTTPS, not HTTP — does `nc` still work?"* — not directly for the TLS layer; use `openssl s_client -connect host:443 -servername host -quiet` instead, which handles the TLS handshake and then lets you type the HTTP request over the now-encrypted channel exactly the same way.

### Q11 — A load balancer intermittently returns 502s to clients. Where do you look first, and what's the likely cause?
**Answer:** Check backend and LB idle/keep-alive timeout configuration first — the classic cause is the backend closing an idle keep-alive connection *before* the LB's own idle timeout, so the LB attempts to reuse a connection the backend has already torn down, and the backend responds with an RST to the reused attempt, which the LB surfaces as a 502. Confirm with `tcpdump` on the backend capturing RSTs correlated with the 502 timestamps.
**Follow-up trap:** *"You've confirmed the timeout mismatch. Which side do you fix — LB or backend?"* — set the backend's idle timeout to be longer than the LB's, not the other way around; if the backend's timeout is shorter, the LB will always occasionally race against a connection the backend is about to close.

### Q12 — Explain why `curl -v` output showing a completed TLS handshake but zero HTTP response bytes, hanging indefinitely, points at a specific known failure mode.
**Testing:** whether the candidate connects debugging symptoms to the MTU blackhole failure mode covered in the failures module.
**Answer:** Small packets (handshake messages) succeeding while a larger post-handshake payload hangs is the signature of a Path MTU Discovery blackhole — a path element is dropping large DF-set packets and also dropping the ICMP "fragmentation needed" message that would tell the sender to shrink its segment size, so the sender just keeps retransmitting the same oversized packet into the void.
**Follow-up trap:** *"How would you confirm that specifically, rather than assuming it?"* — send progressively larger pings with `DF` set (`ping -M do -s <size> host` on Linux) to find the exact size threshold where it starts failing, and/or capture with `tcpdump` to see the retransmissions of the same large segment with no ICMP response ever arriving back.

---

## Red flags that fail you

- Treating "timeout" and "refused" as interchangeable symptoms.
- Reaching for Wireshark/`tcpdump` before `curl -v`/`dig`/`nc` for a problem those would answer in seconds.
- Not knowing `curl -w` timing fields are cumulative and need subtraction between phases.
- Confusing one-shot `traceroute` loss readings with sustained loss without running `mtr` over multiple samples.
- Not knowing what `TIME_WAIT` is for before calling it a bug.
- Capturing packets unfiltered on a production interface.

---

## Cheat card

```
SYMPTOM → MEANING
  refused        active reject (no listener OR firewall REJECT) -- fast, informative
  timed out      silence (drop OR unreachable) -- slow, tells you NOTHING re: location
  reset mid-conn established then killed -- crash, stateful FW, backlog overflow

curl -w TIMING (cumulative -- subtract phases!)
  time_namelookup   DNS
  time_connect      + TCP handshake
  time_appconnect   + TLS handshake
  time_starttransfer + server think time (TTFB) <- usually where the problem is
  time_total        + transfer

ss/netstat
  ss -tlnp             who's listening (0.0.0.0 vs 127.0.0.1 matters)
  ss -tp                who owns an established connection
  ss -s / ss -tan       state summary; count TIME_WAIT for port exhaustion

DNS
  dig +trace                 root->TLD->authoritative path
  dig @8.8.8.8 host           bypass local cache, compare
  dig host +noall +answer     answer + TTL only

LOSS
  mtr -rw -c 100 host    loss OVER TIME per hop; one-shot traceroute is not enough
  loss that clears next hop = ICMP rate-limit artifact, not real loss (verify w/ real traffic)

TLS
  openssl s_client -connect host:443 -servername host   manual handshake, cert chain
  curl -v                                                cert chain + handshake log

PORT REACHABILITY
  nc -zv host port         TCP only, no app protocol -- port open != service healthy

RAW SESSION
  nc host 80                    then type: GET / HTTP/1.1\nHost: host\n\n
  openssl s_client ... -quiet    same, over TLS

tcpdump filters                          Wireshark equivalents
  host X and port Y                      ip.addr==X && tcp.port==Y
  tcp[tcpflags]&tcp-syn!=0 && !ack        tcp.flags.syn==1 && tcp.flags.ack==0
  tcp[tcpflags]&tcp-rst!=0                tcp.flags.reset==1
  port 53                                 dns
                                          http.response.code >= 400
                                          tls.handshake.type==1  (ClientHello)

TIME_WAIT: 2xMSL (~60s Linux) after active close, correctness not a bug;
  exhausts ~28k ephemeral ports under high short-lived-connection churn -> pool, don't just tune sysctls
```

## Sources

- [Wireshark & tcpdump: A Debugging Power Couple — Javarevisited](https://medium.com/javarevisited/wireshark-tcpdump-a-debugging-power-couple-c4242cc7c052) — accessed 2026-07-26
- [Connection Refused vs Reset vs Timed Out: What They Mean — Webalert](https://web-alert.io/blog/connection-refused-reset-timed-out-errors-explained) — accessed 2026-07-26
- [HTTP Transaction Timing with Curl — NetBeez](https://netbeez.net/blog/http-transaction-timing-breakdown-with-curl/) — accessed 2026-07-26
- [How to measure request timing with cURL — simplified.guide](https://www.simplified.guide/curl/request-measure-timing) — accessed 2026-07-26
- [How to Troubleshoot Path MTU Discovery (PMTUD) Failures — OneUptime](https://oneuptime.com/blog/post/2026-03-20-troubleshoot-pmtud-failures/view) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
