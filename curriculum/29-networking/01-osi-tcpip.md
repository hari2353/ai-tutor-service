# OSI vs TCP/IP Model: What Each Layer Actually Does, and Where Bugs Live

> **Track:** T29 Networking & Protocols · **Time:** 2h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T29-osi-tcpip` · **Tags:** fundamentals, critical

## The 30-second version

The OSI model is a 7-layer teaching and troubleshooting reference (Physical, Data Link, Network, Transport, Session, Presentation, Application); the TCP/IP model is what's actually implemented, with 4 layers (Link, Internet, Transport, Application) that collapse OSI's top three into one and don't separately implement Session or Presentation as protocols. Every packet on the wire is a stack of headers wrapped around the previous layer's output — encapsulation going down, de-encapsulation going up — and knowing that stack cold is what lets you look at a symptom and say "that's a layer 2 problem" instead of guessing. A 1500-byte Ethernet frame carrying a TCP payload spends 54 bytes on Ethernet+IP+TCP headers before a single application byte moves, and that arithmetic is the first thing that should come out of your mouth when someone asks about overhead. The real skill being tested is diagnostic: cabling and NICs live at L1, ARP and switching at L2, routing and ICMP at L3, ports and sockets at L4, everything about the shape of the payload at L7 — and most "networking is broken" tickets are actually a wrong assumption about which layer owns the failure.

## Why this gets asked

Because it's the fastest way to check whether someone can localize a fault instead of pattern-matching to "restart the pod." Every interviewer who has been on call has had the experience of an engineer spending an hour on an application-layer retry loop when `ethtool -S` showed CRC errors climbing on the NIC, or someone redeploying a service because "the network is slow" when a misconfigured MTU was causing silent fragmentation. They are probing whether you reach for `ping` → `traceroute` → `tcpdump` → `curl -v` in that order, mapped to layers 3 → 3 → 2-4 → 7, rather than treating "the network" as one undifferentiated blob.

---

## Lineage: past → present → future

**What came before.** The OSI model came out of ISO/IEC 7498 in 1984, designed by committee as a vendor-neutral reference architecture at a time when IBM's SNA, DECnet, and a half-dozen proprietary stacks were competing and nobody wanted to bet infrastructure on any one vendor's protocol suite. The plan was for real protocols (X.25, ISO's own connection-oriented transport, CLNP) to be built to fit each of the 7 layers precisely. Meanwhile TCP/IP grew organically out of ARPANET research, formalized in RFC 791 (IP) and RFC 793 (TCP) in 1981, with a much looser 4-layer structure that never bothered separating session management or data presentation into standalone protocols — those concerns got folded into whatever library or application needed them (TLS handles what OSI called presentation; nothing widely deployed handles OSI's session layer as a distinct protocol).

**Where it stands now.** TCP/IP won outright. The reason usually cited is "rough consensus and running code" beat "design by committee, standardize later" — OSI's protocols were still being finalized while TCP/IP was already running on real networks, and by the time OSI's transport and network protocols were ready, the internet had already been built on something else. The OSI 7-layer model survived anyway, not as running code but as shared vocabulary: "layer 2 switch" vs "layer 3 switch," "layer 4 load balancer" vs "layer 7 load balancer," "layer 7 firewall" are all industry-standard terms that only make sense with OSI's numbering, laid on top of a stack that is actually TCP/IP's 4 layers. The live disagreement, such as it is, is really just pedagogical: some texts insist on a 5-layer TCP/IP model (splitting Link into Physical + Data Link to make the Ethernet/ARP distinction explicit), others keep the classical 4. Neither is wrong; know both numberings.

**Where it's heading.** Layer boundaries are getting blurrier at the edges where performance matters. eBPF/XDP process packets in the kernel driver context before the normal L2/L3 stack even runs, which doesn't remove the layers conceptually but does mean "which layer handled this packet" is no longer a clean answer for high-performance data planes. QUIC (RFC 9000, the transport under HTTP/3) moves what used to be transport-layer responsibility (reliability, congestion control) into a user-space library running over UDP, which is functionally L4 work wearing an L7-looking wire format. Service meshes (Envoy/Istio sidecars) sit at what's nominally L4/L7 but intercept traffic transparently at L3/L4 via iptables or eBPF redirects. None of this changes what you need to know for an interview — the mental model still holds — but "which OSI layer is X" is increasingly a question with a "it depends on where you draw the box" answer for anything built in the last five years, and saying that out loud is a stronger answer than forcing a clean layer number onto something that deliberately doesn't have one.

---

## Mental model

```
 OSI (7)                TCP/IP (4/5)              Real protocols living here
 ─────────────────      ─────────────────         ─────────────────────────────
 7 Application    ┐                                HTTP, gRPC, DNS, SSH
 6 Presentation   ├──►   Application       ◄──     TLS record framing, encoding
 5 Session        ┘                                (rarely a separate protocol)
 4 Transport      ◄──►   Transport         ◄──     TCP, UDP, QUIC
 3 Network        ◄──►   Internet          ◄──     IP, ICMP, routing (BGP/OSPF)
 2 Data Link      ┐                                Ethernet, ARP, switches, VLANs
 1 Physical       ├──►   Link (Network      ◄──    NICs, cabling, radio, PHY chips
                  ┘        Access)
```

Encapsulation is nested envelopes: the application payload gets a TCP header wrapped around it, that gets an IP header wrapped around it, that gets an Ethernet header (and trailer) wrapped around it. Each layer only reads its own envelope and hands the unopened inner envelope up or down. A switch never looks past the Ethernet header; a router never looks past the IP header (ignoring deep packet inspection middleboxes, which are a deliberate layer violation).

---

## How it actually works

### The header stack, with real byte counts

For a TCP/IPv4 packet over Ethernet with no VLAN tag and no IP/TCP options:

| Layer | Header | Size |
|---|---|---|
| L2 | Ethernet header (dst MAC 6B + src MAC 6B + EtherType 2B) | 14 bytes |
| L3 | IPv4 header (no options) | 20 bytes |
| L4 | TCP header (no options) | 20 bytes |
| — | payload | up to 1460 bytes on a 1500-byte-MTU link |
| L2 trailer | Ethernet FCS (CRC-32) | 4 bytes |

Total non-payload overhead: **54 bytes of header + 4 bytes of trailer = 58 bytes** riding along with every segment. On a standard 1500-byte Ethernet MTU, that leaves **1460 bytes** of usable TCP payload (1500 − 20 IP − 20 TCP), which is exactly why the default TCP MSS (maximum segment size) on a 1500-MTU network is 1460, not 1500. Add an 802.1Q VLAN tag and the Ethernet header grows by 4 bytes (frame max becomes 1522). Add TCP options (timestamps, SACK permitted, window scale) and the TCP header can grow up to 60 bytes max (20 base + 40 options), eating directly into payload space. UDP's header is a flat 8 bytes (2B src port, 2B dst port, 2B length, 2B checksum) regardless of options, because UDP has none — this is a real interview number, know that UDP header is 8 bytes and TCP's minimum is 20.

IPv6's header is a fixed 40 bytes (no options field at all; extensions are chained separately), versus IPv4's variable 20–60 bytes. That fixed size is a deliberate simplification: routers can process it without a length check on every hop.

### Where a bug concretely lives at each layer

| Layer | What lives here | Concrete failure you'd actually see |
|---|---|---|
| **L1 Physical** | Cabling, NICs, transceivers, radio | `ethtool -S eth0` shows rising `rx_crc_errors`; a bad SFP or a half-duplex/full-duplex mismatch causes late collisions that show up as throughput collapsing to a fraction of link speed with no obvious error in application logs |
| **L2 Data Link** | Ethernet framing, ARP, switching, VLANs, STP | `arp -n` shows an incomplete or wrong MAC for a gateway IP; a switching loop without STP convergence causes broadcast storms; a VLAN tag mismatch drops frames silently at the switch, invisible from either host's perspective |
| **L3 Network** | IP addressing, routing, fragmentation, ICMP | `traceroute` dies at a specific hop; `ping` gets "Destination Host Unreachable" (ICMP type 3) or nothing at all if ICMP is filtered; asymmetric routing causes one direction of a flow to work and the other not to |
| **L4 Transport** | Ports, sockets, TCP state, UDP | connection `refused` (RST from a closed port) vs connection `timeout` (nothing listening or firewall silently dropping) — this distinction alone tells you whether the destination is up but not listening, versus unreachable |
| **L7 Application** | HTTP semantics, TLS handshake, DNS resolution, serialization | a 200 OK with malformed JSON, a TLS handshake failing on cipher mismatch, a DNS query returning a stale cached A record — none of these are "the network," but they get reported as network tickets constantly |

**Named failure mode, concrete symptom:** a **duplex mismatch** (one end of a link auto-negotiates full-duplex, the other is forced to half-duplex, common on old switch ports or misconfigured NIC drivers) is an L1/L2 problem that shows up as a specific, checkable signature: `ethtool eth0` reports the duplex setting, and `ethtool -S eth0` or `ifconfig` shows a climbing counter of **late collisions** and **FCS/CRC errors** on the half-duplex side, while application-level symptoms are just "intermittently slow," which is exactly vague enough that people spend hours looking at the wrong layer before checking the interface counters.

### Encapsulation/de-encapsulation walkthrough

Sending an HTTP request:

1. **L7** application builds an HTTP request, e.g. 300 bytes of request line + headers + body.
2. **L4** TCP wraps it in a 20-byte TCP header (source port, dest port, sequence number, ack number, flags, window, checksum) → segment.
3. **L3** IP wraps the segment in a 20-byte IPv4 header (source IP, dest IP, TTL, protocol=6 for TCP, header checksum) → packet.
4. **L2** Ethernet wraps the packet in a 14-byte header (dest MAC, src MAC, EtherType=0x0800 for IPv4) plus a 4-byte FCS trailer → frame.
5. **L1** the frame is serialized onto the physical medium as an electrical/optical/radio signal.

The receiving host reverses this exactly: L1 recovers bits into a frame, L2 checks the FCS and strips the Ethernet header/trailer, L3 checks the IP header (TTL, checksum, is this address mine or do I route it) and strips it, L4 reassembles/orders TCP segments and strips the TCP header, L7 gets the original 300 bytes back. Every "why is this bug happening" question that starts with "let me check the application logs" and should have started with "let me check which layer this actually is" costs you time in a real incident and costs you credibility in an interview.

---

## Build it from scratch

The clearest way to prove you understand the stack is to parse a raw frame by hand instead of trusting a library to do it for you.

```python
# untested sketch — requires CAP_NET_RAW / root, Linux only
import socket
import struct

def parse_ethernet(frame: bytes):
    dst, src, ethertype = struct.unpack("!6s6sH", frame[:14])
    return {
        "dst_mac": dst.hex(":"),
        "src_mac": src.hex(":"),
        "ethertype": hex(ethertype),   # 0x0800 = IPv4, 0x0806 = ARP, 0x86dd = IPv6
        "payload": frame[14:],
    }

def parse_ipv4(packet: bytes):
    version_ihl = packet[0]
    ihl = (version_ihl & 0x0F) * 4          # header length in 32-bit words -> bytes
    ttl, proto = packet[8], packet[9]
    src_ip = socket.inet_ntoa(packet[12:16])
    dst_ip = socket.inet_ntoa(packet[16:20])
    return {
        "header_len": ihl, "ttl": ttl, "protocol": proto,  # 6=TCP, 17=UDP, 1=ICMP
        "src_ip": src_ip, "dst_ip": dst_ip,
        "payload": packet[ihl:],
    }

def parse_tcp(segment: bytes):
    src_port, dst_port, seq, ack, offset_flags = struct.unpack("!HHIIH", segment[:14])
    data_offset = (offset_flags >> 12) * 4   # header length in 32-bit words -> bytes
    flags = offset_flags & 0x01FF
    return {"src_port": src_port, "dst_port": dst_port,
            "seq": seq, "ack": ack, "header_len": data_offset,
            "payload": segment[data_offset:]}

sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
while True:
    raw, _ = sock.recvfrom(65535)
    eth = parse_ethernet(raw)
    if eth["ethertype"] == "0x800":
        ip = parse_ipv4(eth["payload"])
        if ip["protocol"] == 6:
            tcp = parse_tcp(ip["payload"])
            print(ip["src_ip"], tcp["src_port"], "->", ip["dst_ip"], tcp["dst_port"],
                  f"app_payload={len(tcp['payload'])}B")
```

Doing this once, even badly, is what separates "I know the OSI model" from "I've actually looked at bytes on the wire." `struct.unpack("!6s6sH", ...)` for the Ethernet header and the bit-shifting for IHL/data-offset are exactly the kind of mechanical detail an interviewer probing past the textbook answer will ask you to derive live.

---

## How it's done in production

Nobody parses raw frames by hand in production; you reach for the tool matched to the layer you suspect:

| Symptom | Cause | Fix |
|---|---|---|
| Throughput collapses to ~10% of link speed, no app errors | L1/L2 duplex mismatch | `ethtool eth0` to check duplex/speed on both ends; force matching settings or fix auto-negotiation |
| `ping` works, TCP connect times out | L3 routes but L4 port unreachable or filtered | Check `iptables`/security group rules; distinguish RST (port closed, fast) from silent drop (filtered, times out) |
| Intermittent packet loss only under load | L2 switch buffer overrun or L1 cable/CRC issue | Check switch port counters and `ethtool -S` for `rx_crc_errors`, `rx_dropped` |
| One direction of a flow works, the other doesn't | L3 asymmetric routing, often through firewalls that only see half the flow | `traceroute` in both directions; check for stateful firewall dropping return traffic that took a different path |
| DNS resolves to the wrong/stale IP | L7 caching, not a network fault at all | Check resolver cache TTL, `dig +trace` to see the actual chain of delegation |
| TLS handshake fails with cipher/version mismatch | L7 (technically presentation-ish), not L3/L4 | `openssl s_client -connect host:443` to see the actual handshake failure reason |

The production instinct that separates senior engineers: **localize before you fix.** `ping` (L3 reachability) → `traceroute`/`mtr` (L3 path) → `nc -zv host port` or `curl -v` (L4 reachability, does something answer on the port) → `tcpdump`/Wireshark (see the actual bytes at whichever layer is suspect) → application logs (L7) last, not first. Most outages get diagnosed backwards — someone stares at application logs for twenty minutes before running `ping`.

---

## Tradeoffs & when NOT to use it

This isn't a technology with a wrong context — it's a mental model — but there is a real failure mode in *how* people use it:

- **Don't force a clean OSI layer number onto something that deliberately spans layers.** QUIC, service mesh sidecars, and eBPF-based data planes don't map cleanly to one OSI layer, and insisting they do in an interview signals memorization over understanding.
- **Don't use "it's a layer 7 problem" as a way to avoid learning the lower layers.** Most application engineers can debug L7 and are lost below it; that gap is exactly what this module is for, and claiming L7 expertise as a substitute for L2/L3 literacy is a common gap at the senior level.
- **The 7-layer model is not useful as an implementation guide** — nobody builds a system with a literal Session layer object. Use it as a shared vocabulary and a diagnostic checklist, not an architecture template.

---

## Interview questions

### Q1 — What are the 7 OSI layers, and how do they map to TCP/IP's 4?
**Testing:** baseline recall, but also whether you can do the mapping instead of reciting two disconnected lists.
**Answer:** Physical, Data Link, Network, Transport, Session, Presentation, Application. TCP/IP collapses Session+Presentation+Application into one Application layer, keeps Transport and Internet(=Network) as-is, and collapses Physical+Data Link into one Link layer (some texts split it back into 5 to make Ethernet/ARP explicit).
**Follow-up trap:** *"Where does TLS live in this mapping?"* — functionally it does what OSI called Presentation (encryption, formatting) but it's implemented as a library sitting between the application and the transport socket, not as a standalone OSI Presentation-layer protocol. There isn't a clean "layer 6 box" in a real stack.

### Q2 — Why did TCP/IP win over OSI's own protocol suite?
**Answer:** "Rough consensus and running code" — TCP/IP was deployed and iterating on real networks (ARPANET, then NSFNET) years before OSI's own transport and network protocols (X.25, CLNP) were finalized. By the time OSI's protocols were ready, the internet had already been built on something else, and the switching cost of replacing a working, growing network was higher than the theoretical benefits of the OSI suite.
**Follow-up trap:** *"So is the OSI model dead?"* — the protocols are, the vocabulary isn't. "Layer 3 switch," "layer 7 load balancer," "layer 4 firewall" are all industry-standard terms built on OSI's numbering, describing devices that operate on a TCP/IP stack. The model survived as a shared language, not as running code.

### Q3 — Walk me through the header overhead for a TCP packet on a standard Ethernet network.
**Testing:** whether the numbers are memorized or derived on the spot.
**Answer:** 14-byte Ethernet header + 20-byte IPv4 header (no options) + 20-byte TCP header (no options) = 54 bytes, plus a 4-byte Ethernet FCS trailer = 58 bytes of overhead. On a 1500-byte MTU, that leaves 1460 bytes of TCP payload, which is exactly the default MSS on a 1500-MTU path.
**Follow-up trap:** *"What changes with a VLAN tag or TCP options?"* — an 802.1Q tag adds 4 bytes to the Ethernet header (max frame becomes 1522); TCP options (timestamps, SACK-permitted, window scale) can grow the TCP header up to 60 bytes total, directly reducing payload capacity within the same MTU.

### Q4 — A user reports "the network is slow." Where do you start?
**Answer:** Localize the layer before touching anything. `ping` for L3 reachability and rough latency, `traceroute`/`mtr` for the L3 path and where latency/loss appears, `nc -zv` or `curl -v` for L4 reachability, `tcpdump` if you suspect L2/L3 framing or retransmission issues, application logs last. Most people start at application logs and work backwards, which is slower.
**Follow-up trap:** *"Ping is fine but the app times out — what does that tell you?"* — L3 reachability is fine, so the problem is L4 (port not listening, firewall silently dropping, backlog full) or L7 (app hung, slow query). Distinguish RST (fast, port actively refused, something's listening on the box but not that port) from no response at all (something's silently dropping it — firewall, or nothing on the interface).

### Q5 — What's the difference between a switch dropping a frame and a router dropping a packet, in terms of what caused it?
**Answer:** A switch operates at L2 and drops frames for reasons like a full MAC address table, VLAN mismatch, or physical errors (bad CRC) — it never looks at the IP header. A router operates at L3 and drops packets for reasons like TTL expiry, no matching route, or an ACL/firewall rule matching on IP/port — it never looks past the IP (and sometimes L4) headers unless it's doing deep packet inspection, which is a deliberate layer violation.
**Follow-up trap:** *"What tells you which one happened?"* — TTL-expiry drops generate an ICMP Time Exceeded back to the sender, visible in `traceroute`. Switch-level drops are usually silent from the host's perspective — you'd need switch port counters, not host-side tools, to see them.

### Q6 — What is duplex mismatch, and how would you actually catch it in production?
**Testing:** whether you know a real named L1/L2 failure with an observable signature, not just the concept of "physical layer problems."
**Answer:** One end of an Ethernet link auto-negotiates full-duplex while the other is forced (or falls back) to half-duplex. The half-duplex side can't detect the other side transmitting simultaneously the way collision detection expects, so you get late collisions and a throughput collapse that looks nothing like a duplex problem from the application side — it just looks like intermittent slowness.
**Follow-up trap:** *"What command proves it, and what would you see?"* — `ethtool eth0` shows the negotiated duplex/speed on each end; `ethtool -S eth0` shows a climbing `rx_crc_errors` or a nonzero late-collision counter on the half-duplex side. Application logs show nothing useful because the failure is below where the application can observe it.

### Q7 — Why is UDP's header 8 bytes and TCP's is 20?
**Answer:** UDP has no connection state, sequencing, acknowledgment, or flow control to carry, so its header is just source port (2B), dest port (2B), length (2B), checksum (2B) = 8 bytes flat, no options field. TCP's 20-byte base header carries sequence number, ack number, flags, window size, and a checksum, and can grow to 60 bytes with options (timestamps, SACK, window scale) because it's carrying all the state needed for reliable, ordered, flow-controlled delivery.
**Follow-up trap:** *"Does that mean UDP is always more efficient?"* — for the header, yes, always 12 bytes less. For the application, no — if you need reliability you reimplement acks/retransmission/ordering in the application layer, which usually costs more bytes and more engineering than TCP's header ever did. That tradeoff (QUIC, RTP) is why "just use UDP for efficiency" without accounting for what you have to rebuild is a red flag answer.

### Q8 — Give a real bug you'd expect at each layer from L1 to L7.
**Answer:** L1: bad cable/SFP causing CRC errors. L2: ARP cache poisoning or a switching loop causing a broadcast storm. L3: a missing or wrong route causing `traceroute` to die at a hop, or MTU/fragmentation issues. L4: a firewall silently dropping SYNs (looks like the service is down when it's actually the network path), or backlog queue overflow under load. L7: a service returning 200 with a malformed body, or DNS serving a stale cached record.
**Follow-up trap:** *"Which of these is hardest to diagnose and why?"* — L2 and silent L3/L4 drops, because they produce no error back to the client — the connection just times out — versus an explicit RST or 4xx that tells you something. Silence is always harder to diagnose than an explicit failure, and that's true at every layer, not just networking.

### Q9 — Why doesn't the internet actually implement OSI's Session and Presentation layers as separate protocols?
**Answer:** Because TCP/IP's Application layer absorbed those responsibilities pragmatically — session management (if needed at all) is handled inside the application protocol itself (HTTP cookies/sessions, WebSocket's own framing) and presentation concerns (encoding, encryption, compression) are handled by libraries layered just above the transport socket (TLS, gzip) rather than by a standalone protocol with its own wire format. There was never enough independent value in a separate, universal Session or Presentation protocol to justify one, whereas Transport (TCP/UDP) and Network (IP) had a clear, universal job.
**Follow-up trap:** *"So where would you put gRPC's use of HTTP/2 streams for multiplexing — is that session-layer behavior?"* — functionally, yes, it's doing something session-like (managing multiple logical conversations over one connection), but it's implemented entirely within an application-layer protocol (HTTP/2), not as a separate OSI-numbered layer. This is the general pattern: session-like and presentation-like *behavior* exists everywhere, it's just never been worth standardizing as its own protocol layer.

### Q10 — A packet capture shows a client sending a SYN and getting nothing back, ever — not even a timeout error, just a hang. Which layer, and what do you check?
**Answer:** This is almost always L3/L4: something between client and server is silently dropping the SYN (a stateful firewall, a security group, an ACL) rather than actively refusing it. If the destination actively refused (nothing listening on that port), you'd get an immediate RST, not silence. Check `traceroute` to see how far the packet actually gets, then check firewall/security-group rules on the path, then confirm with `tcpdump` on both ends to see whether the SYN arrives at all.
**Follow-up trap:** *"The traceroute completes all the way to the destination IP. Does that rule out a firewall on that host?"* — no. `traceroute` typically uses UDP or ICMP probes with incrementing TTL, which tells you the L3 path is reachable, but a host-based firewall or security group can still be filtering TCP port 443 specifically while responding to ICMP/UDP traceroute probes just fine. Reachability at L3 says nothing about a specific L4 port being open.

---

## Red flags that fail you

- Reciting the 7 OSI layers from memory but being unable to say which layer owns a given real bug.
- Claiming OSI's Session and Presentation layers exist as running protocols in a modern stack.
- Saying "the network is slow" is meaningfully diagnosed by checking application logs first.
- Not knowing the actual header byte counts (guessing "IP header is like 40 bytes" instead of knowing it's 20 without options, up to 60 with).
- Treating QUIC/service-mesh/eBPF as cleanly mapping to one OSI layer instead of acknowledging they span boundaries.
- Confusing an RST (active refusal) with a silent timeout (filtered or unreachable) — these mean opposite things about the destination's state.

---

## Cheat card

```
OSI (7): Physical, Data Link, Network, Transport, Session, Presentation, Application
TCP/IP (4): Link, Internet, Transport, Application   (5-layer variant splits Link into Phys+DataLink)

HEADER SIZES (memorize)
  Ethernet header  14B (6+6+2)     + FCS trailer 4B
  802.1Q VLAN tag  +4B  (max frame 1518 -> 1522)
  IPv4 header      20B no options, up to 60B with
  IPv6 header      40B FIXED, no options field (extension headers chained separately)
  TCP header       20B no options, up to 60B with (timestamps, SACK, window scale)
  UDP header       8B flat (src port, dst port, length, checksum) — never grows

OVERHEAD EXAMPLE: Eth(14)+IP(20)+TCP(20)+FCS(4) = 58B non-payload
  on 1500 MTU -> 1460B usable TCP payload = default MSS

DIAGNOSTIC LADDER (localize before fixing)
  ping (L3 reachability) -> traceroute/mtr (L3 path)
  -> nc -zv / curl -v (L4 reachability) -> tcpdump (raw bytes)
  -> application logs (L7) LAST, not first

RST vs silent timeout: RST = port actively refused (something's up, wrong port/service)
                        silent timeout = filtered or truly unreachable

DUPLEX MISMATCH (named L1/L2 failure): ethtool -S shows rx_crc_errors / late collisions
  climbing; app-level symptom is just vague intermittent slowness

WHY TCP/IP WON: running code beat design-by-committee (OSI protocols finished too late)
OSI SURVIVES AS: vocabulary only — "layer 3 switch", "layer 7 LB", not running protocols
```

## Sources

- [25 OSI Model Interview Questions (With Answers And Tips) — Indeed](https://in.indeed.com/career-advice/interviewing/osi-model-interview-questions) — accessed 2026-07-26
- [Top 20 OSI Model Interview Questions and Answers (2026) — PyNetLabs](https://www.pynetlabs.com/osi-model-interview-questions-and-answers/) — accessed 2026-07-26
- RFC 791 — Internet Protocol (1981)
- RFC 793 — Transmission Control Protocol (1981)
- RFC 1323 / RFC 7323 — TCP options (timestamps, window scale)

## Changelog
- 2026-07-26 — created
