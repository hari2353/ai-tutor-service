# IP: Addressing, Subnets/CIDR, Routing, Fragmentation, NAT, IPv4 vs IPv6

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-osi-tcpip · **Updated:** 2026-07-26
> **Module id:** `T29-ip-layer` · **Tags:** fundamentals, critical

## The 30-second version

IP addressing is bits: a /24 gives you 256 addresses (254 usable hosts), a /27 gives you 32 (30 usable), and you should be able to do that arithmetic in your head using the block-size trick (256 minus the last octet of the mask) rather than converting to binary every time. Routing is longest-prefix match — the router picks the *most specific* matching route, not the first one, full stop. Fragmentation is legacy: modern stacks avoid it via Path MTU Discovery (PMTUD), and when PMTUD breaks — usually because a middlebox drops the ICMP "fragmentation needed" message — you get a specific, recognizable failure: small packets flow fine, large ones vanish silently. NAT (specifically PAT/NAPT, the many-to-one flavor everyone actually means when they say "NAT") multiplexes thousands of internal hosts behind one public IP by rewriting the port along with the address, and it breaks two categories of things: unsolicited inbound connections, and any protocol that embeds an IP address inside its payload (FTP active mode, SIP/SDP) unless something (an ALG, or explicit configuration) rewrites the payload too. IPv6 isn't just bigger addresses — it removes in-network fragmentation entirely, replaces ARP with multicast-based NDP, and drops the header checksum, none of which are optional details in a real production migration.

## Why this gets asked

Because subnet math and longest-prefix-match are the two things every backend/infra engineer is assumed to have internalized, and the gap between "I know what CIDR stands for" and "I can compute the host range for a /27 in fifteen seconds" is enormous and immediately visible. The interviewer has almost certainly debugged a PMTUD black hole personally — it's one of the most maddening production networking failures because everything *looks* fine (TCP connects, small requests work) until a payload crosses the MTU threshold and just hangs, no error, no RST, nothing in the app logs. They're also checking whether you understand NAT well enough to explain why a webhook callback to an internal service behind a NAT gateway needs a specific inbound rule, not just "the NAT should handle it."

---

## Lineage: past → present → future

**What came before.** Original IPv4 addressing (RFC 791, 1981) used classful addressing — Class A/B/C fixed the network/host boundary at byte boundaries (/8, /16, /24) with no flexibility, so an organization needing 300 addresses had to take a full Class B (65,536 addresses) or several Class Cs, wasting enormous swaths of address space. By the early 1990s this waste, combined with routing table growth from all those individually-announced Class C blocks, was on a trajectory to exhaust both the address space and router memory well before anyone expected. CIDR (Classless Inter-Domain Routing, RFC 1519, 1993) killed classful addressing by decoupling the network/host boundary from byte boundaries entirely — any prefix length from /1 to /32 became valid, letting allocations match actual need and letting routes aggregate (supernet) to keep routing tables from exploding.

**Where it stands now.** CIDR is universal; nobody deploys classful addressing today except as a historical footnote (you'll still hear "Class C" used loosely to mean "/24," which is technically imprecise but ubiquitous jargon). IPv4 address exhaustion is not a future risk, it already happened — IANA's free pool exhausted in 2011, and the regional registries (ARIN, RIPE, APNIC) followed over the next several years, which is why NAT/PAT and CGNAT (carrier-grade NAT) are load-bearing infrastructure rather than a workaround. IPv6 has been standardized since 1998 (RFC 2460, obsoleted by RFC 8200 in 2017) and dual-stack deployment is real but uneven — mobile carriers and some hyperscalers are heavily IPv6, a large fraction of enterprise internal networks are still IPv4-only behind NAT, and the practical reality most engineers live in is dual-stack at the edge with IPv4 still dominant internally. The live disagreement isn't technical, it's economic: IPv6-only deployment is cheaper to operate at scale (no NAT state to manage) but the transition cost and the tail of IPv4-only dependencies keep pushing full cutover out.

**Where it's heading.** Expect continued growth of IPv6-only backends with NAT64/DNS64 or 464XLAT translating for the remaining IPv4-only clients and services, rather than a hard cutover — that pattern (T-Mobile's IPv6-only mobile network with 464XLAT is the reference deployment) is what's actually shipping today, not full dual-stack forever. Within the IPv4 world, CGNAT will keep growing because RIR-allocated IPv4 space is a fixed, expensive resource and most residential/mobile ISPs cannot justify buying enough public IPv4 for every customer. Treat "IPv6 will fully replace IPv4 within N years" claims as speculative; the honest position is that translation layers at the edge are the durable pattern, not a full migration.

---

## Mental model

```
32 bits, split at the prefix length:

   /24  → 11111111.11111111.11111111.00000000
           └──────── network ────────┘└ host ┘
           3 octets fixed, 1 octet free = 256 addresses, 254 usable

Block-size trick for any mask: 256 − (last nonzero mask octet value) = block size
   /27 → mask 255.255.255.224 → 256 − 224 = 32   → 32 addresses per subnet, 30 usable
   /22 → mask 255.255.252.0   → 256 − 252 = 4    → 4 × 256 = 1024 addresses, 1022 usable
```

Longest prefix match is: given several routes that all technically match a destination, take the one whose prefix has the *most* bits specified — it's the routing table's version of "the most specific rule wins."

---

## How it actually works

### Subnet math, worked fast

Given an IP and a mask, three questions always: network address, broadcast address, usable host range, host count.

**/24 — 10.0.5.0/24**
- Block size 256, network 10.0.5.0, broadcast 10.0.5.255
- Usable: 10.0.5.1 – 10.0.5.254 → **254 hosts** (256 − network − broadcast)

**/27 — 10.0.5.64/27**
- Mask 255.255.255.224, block size 256−224=32
- Subnet boundaries land on multiples of 32: ..0, ..32, **..64**, ..96, ...
- Network 10.0.5.64, broadcast 10.0.5.95, usable 10.0.5.65–10.0.5.94 → **30 hosts**

**/22 — 10.0.4.0/22**
- Mask 255.255.252.0, block size in the third octet 256−252=4
- Spans four /24s: 10.0.4.0 through 10.0.7.255
- Network 10.0.4.0, broadcast 10.0.7.255, usable count = 1024 − 2 = **1022 hosts**

The formula that generalizes all of this: usable hosts = 2^(32 − prefix) − 2. The minus 2 is the network address and the broadcast address, both unusable for hosts (a /31, RFC 3021, is the special case used for point-to-point router links where both addresses are usable and there's no broadcast — worth knowing this exception exists).

**The interview move**: narrate the block-size trick out loud rather than converting to binary — "256 minus 224 is 32, so subnets fall on multiples of 32, this address falls in the block starting at 64" — it's fast, it's visibly correct, and it signals you've done this under pressure before.

### Routing table lookup — longest prefix match, worked

Given a routing table:

```
10.0.0.0/8      via gateway A   (covers all of 10.x.x.x)
10.1.0.0/16     via gateway B   (covers 10.1.x.x)
10.1.2.0/24     via gateway C   (covers 10.1.2.x)
0.0.0.0/0       via gateway D   (default route)
```

A packet to **10.1.2.5** matches all four entries. The router picks the entry with the longest prefix that matches — /24 (gateway C) beats /16 (gateway B) beats /8 (gateway A) beats the default /0. A packet to **10.1.5.5** matches /8 and /16 but not the /24, so it goes to gateway B. A packet to **8.8.8.8** matches only the default route, gateway D. This is the entire mechanism — no "first match wins," no priority field beyond specificity (equal-prefix routes then break ties on metric/AD, but that's a second-order detail).

### Fragmentation: why it's mostly avoided today

IPv4 fragmentation mechanics: the IP header carries an **Identification** field (16 bits, same value across all fragments of one original packet), a 13-bit **Fragment Offset** (in units of 8 bytes, so max offset represents 65,528 bytes in), and flags **DF** (Don't Fragment) and **MF** (More Fragments). A router facing a packet larger than the outgoing link's MTU either fragments it (splitting into pieces each with their own IP header, same Identification, incrementing offsets) or, if DF is set, drops it and sends back **ICMP Type 3, Code 4** ("Fragmentation Needed and DF Set").

That ICMP message is the entire mechanism behind **Path MTU Discovery (PMTUD, RFC 1191)**: a sender sets DF on every packet, and if some router along the path can't forward it without fragmenting, that ICMP comes back telling the sender the next-hop MTU, and the sender retries smaller. This is why fragmentation is largely avoided in practice — PMTUD lets the endpoints agree on the right size without any router actually fragmenting anything, which is faster (fragmentation and reassembly cost CPU) and safer (fragmented packets are harder for stateful firewalls to inspect and are a known DoS/evasion vector).

**Named failure mode, concrete symptom — the PMTUD black hole**: many firewalls and security groups block *all* ICMP as a blanket "security" policy, including type 3 code 4. When that happens, the router that needed to signal "packet too big" instead just silently drops the oversized packet — no ICMP gets back to the sender, so the sender never learns to shrink its packets. The observable symptom is exact and recognizable: a TCP connection completes its handshake fine (small SYN/SYN-ACK/ACK packets), small requests work, but as soon as a payload crosses the effective MTU threshold, the connection hangs — you see a large packet leave in `tcpdump`, get no ACK, and the sender just keeps retransmitting the same large segment until it eventually times out. This is a classic "TLS handshake works, but the certificate chain response (bigger than one MTU) hangs" bug. The standard mitigation is **TCP MSS clamping** at the border router/firewall — rewrite the MSS option in the SYN packets to a safe value so TCP never tries to send a segment that would need fragmentation on that path in the first place, sidestepping the broken ICMP path entirely.

### MTU numbers to know cold

| Link type | MTU |
|---|---|
| Standard Ethernet | **1500** bytes |
| PPPoE (adds an 8-byte PPPoE header) | **1492** bytes |
| Jumbo frames (data center / storage networks) | **9000** bytes (sometimes 9216 including overhead) |
| IPv6 minimum guaranteed | **1280** bytes (every link on the path must support at least this; IPv6 hosts can rely on it without discovery) |

### NAT: SNAT/DNAT and PAT/NAPT

- **SNAT (Source NAT)** rewrites the source address of outbound packets — typically many internal private IPs going out through one public IP. This is what lets your laptop and everyone else on your home network share one public IP.
- **DNAT (Destination NAT)** rewrites the destination address of inbound packets — port forwarding, load balancer VIP-to-backend translation.
- **PAT/NAPT (Port Address Translation / Network Address and Port Translation)** is the mechanism that makes many-to-one SNAT actually work: since multiple internal hosts share one public IP, the NAT device also rewrites the **source port** to keep connections distinguishable, and maintains a translation table keyed by the full 4-tuple (or 5-tuple with protocol) so return traffic gets mapped back to the correct internal host. This is what people actually mean 99% of the time they say "NAT" on a home router or cloud NAT gateway.

**What breaks under NAT:**
1. **Inbound connections to a NATed host** don't work by default — there's no entry in the translation table for a connection nobody inside initiated, so the NAT device has nothing to route the inbound SYN to. This is why port forwarding / DNAT rules or a load balancer with an explicit listener are required for anything that needs to accept unsolicited connections from outside.
2. **Protocols that embed IP addresses or ports inside their payload** break because NAT only rewrites headers, not application data, unless something specifically parses and rewrites the payload too (an Application Layer Gateway, ALG). Classic examples: **FTP active mode**, where the client tells the server "connect back to me at IP:port" inside the FTP control channel payload — if that embedded IP is the internal private address, the server tries to connect to an address that means nothing from outside the NAT. **SIP/SDP** (VoIP signaling) embeds media IPs/ports in the SDP body for the RTP stream to use, with the identical problem. Fixes: NAT ALGs (built into many routers, often unreliable), STUN/TURN/ICE (the modern fix used by WebRTC and SIP to discover and communicate the actual public-facing address instead of relying on the NAT to fix it up), or FTP passive mode (which reverses the direction so the client, already NAT-translated correctly by the connection it initiated, opens the data channel instead of the server trying to connect in).

### IPv4 vs IPv6: what actually matters

| Aspect | IPv4 | IPv6 |
|---|---|---|
| Address size | 32 bits, ~4.3 billion addresses | 128 bits, effectively inexhaustible (~3.4×10^38) |
| Exhaustion | IANA free pool exhausted 2011; RIRs followed | Not a concern at any realistic allocation scale |
| Neighbor resolution | ARP — broadcast "who has this IP" | NDP (Neighbor Discovery Protocol) — ICMPv6 Neighbor Solicitation/Advertisement over multicast, no broadcast at all |
| Fragmentation | Routers along the path can fragment | **Routers never fragment.** Only the originating host may fragment (via an IPv6 Fragment extension header); routers just drop oversized packets and send back ICMPv6 Packet Too Big — PMTUD is not optional, it's the only mechanism |
| Header | Variable, 20–60 bytes with options | Fixed 40 bytes; options moved to chained extension headers, and mid-path routers only need to parse the fixed part |
| Header checksum | Present, recomputed at every hop (since TTL decrements) | **Removed entirely** — relies on link-layer and upper-layer (TCP/UDP) checksums instead, since recomputing a whole-packet checksum at every hop for negligible benefit was judged not worth the router CPU cost |
| Address config | DHCP (stateful) | SLAAC (stateless autoconfig from router advertisements) or DHCPv6, coexisting |
| Deployment reality | Still dominant internally at most enterprises, behind NAT | Real and growing at the edge (mobile carriers especially), often via NAT64/464XLAT to bridge to IPv4-only-only services rather than a clean full cutover |

The header-checksum removal is one of the most commonly missed facts: people assume IPv6 just "does the same things, bigger addresses," and miss that IPv6 deliberately pushed integrity checking down to the layers that already do it (Ethernet FCS, TCP/UDP checksum) rather than duplicating it at every router hop.

---

## Build it from scratch

The subnet math is the part worth being able to derive live, not code — but a quick script proves you know the formula, and is a fair thing to be asked to write:

```python
import ipaddress

def subnet_info(cidr: str) -> dict:
    net = ipaddress.ip_network(cidr, strict=False)
    hosts = list(net.hosts())
    return {
        "network": str(net.network_address),
        "broadcast": str(net.broadcast_address) if net.version == 4 else None,
        "prefix": net.prefixlen,
        "total_addresses": net.num_addresses,
        "usable_hosts": len(hosts),          # ipaddress already excludes net/broadcast for IPv4
        "first_usable": str(hosts[0]) if hosts else None,
        "last_usable": str(hosts[-1]) if hosts else None,
    }

def longest_prefix_match(dest: str, routes: dict[str, str]) -> str:
    """routes: {'10.1.2.0/24': 'gatewayC', ...} -> returns the gateway for the longest matching prefix."""
    ip = ipaddress.ip_address(dest)
    candidates = [(ipaddress.ip_network(cidr), gw) for cidr, gw in routes.items()]
    matches = [(net, gw) for net, gw in candidates if ip in net]
    if not matches:
        raise ValueError("no route to host")
    best = max(matches, key=lambda pair: pair[0].prefixlen)
    return best[1]

print(subnet_info("10.0.5.64/27"))
# {'network': '10.0.5.64', 'broadcast': '10.0.5.95', 'prefix': 27,
#  'total_addresses': 32, 'usable_hosts': 30, 'first_usable': '10.0.5.65', 'last_usable': '10.0.5.94'}

routes = {"10.0.0.0/8": "A", "10.1.0.0/16": "B", "10.1.2.0/24": "C", "0.0.0.0/0": "D"}
print(longest_prefix_match("10.1.2.5", routes))   # "C"
print(longest_prefix_match("8.8.8.8", routes))    # "D"
```

Using `ipaddress` here is fine in production; the value in an interview is deriving the block-size arithmetic and the longest-prefix-match logic yourself first, then knowing the library exists so you don't hand-roll it in real code.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| TLS handshake completes, transfer of a larger payload hangs indefinitely | PMTUD black hole — ICMP "frag needed" blocked by a firewall | TCP MSS clamping at the border (`iptables -j TCPMSS --clamp-mss-to-pmtu`), or allow ICMP type 3 code 4 through the firewall |
| Inbound webhook/callback to an internal service never arrives | No NAT/port-forward rule for unsolicited inbound; NAT only tracks connections it saw originate | Explicit DNAT / port-forward rule, or route the callback through a load balancer with a public listener |
| VoIP call connects but has no audio | SIP/SDP embedded the internal NATed IP for the RTP stream; no ALG rewrote it | STUN/TURN/ICE to discover and signal the actual reachable address, or a SIP-aware ALG |
| A subnet you provisioned as /27 runs out of IPs almost immediately | Underestimated host count — /27 is only 30 usable | Recompute from expected host count using 2^(32−prefix)−2, size up, or use a supernetting/VPC-peering approach instead of subdividing further |
| One route works, a more specific one you just added is being ignored | Route table caching, or the new route wasn't actually installed (a typo prefix length) | Verify with `ip route get <dest>`; confirm the new prefix length actually matches and is longer than the existing route |
| IPv6-enabled service unreachable from some clients but not others | Missing PMTUD support along an IPv6 path, or a client/network still IPv4-only with no NAT64/dual-stack path | Confirm the 1280-byte minimum MTU guarantee holds end to end; provide NAT64/464XLAT or dual-stack for IPv4-only clients |

**Cloud realities worth naming**: AWS/GCP/Azure VPC subnets are CIDR blocks exactly like the math above, and cloud NAT gateways are PAT devices with a hard, documented port limit per public IP (commonly cited around the 64,000-ephemeral-port ceiling per IP, split across whatever backend instances share that gateway) — provisioning too few NAT gateway IPs for a large fleet of instances making many outbound connections is a real, recurring "why are outbound connections randomly failing" production incident, not a theoretical one.

---

## Tradeoffs & when NOT to use it

- **Don't over-subdivide subnets "for organization."** Every subnet boundary you add costs usable addresses (2 per subnet minimum) and adds routing table entries. A flat /22 with security groups doing the isolation work is often better than eight tightly-carved /27s that all need their own route entries and inevitably run out of room when a team needs one more host than planned.
- **Don't disable ICMP wholesale for "security."** Blocking all ICMP, including type 3 code 4, is the single most common cause of PMTUD black holes, and the "security" benefit is marginal (ICMP is not a significant attack surface on modern stacks) against the cost of a whole class of silent, hard-to-diagnose failures.
- **Don't assume NAT is a security boundary.** NAT was designed for address conservation, not security — the fact that it also happens to block unsolicited inbound connections is a side effect, not a design guarantee, and relying on "it's behind NAT" instead of an explicit firewall policy is a common and wrong assumption.
- **Don't reach for fragmentation-friendly designs when PMTUD is available and working.** Deliberately sending oversized packets and letting the network fragment them costs CPU on every router in the path and complicates stateful inspection; let PMTUD do its job and size to the discovered MTU instead.
- **IPv6-only is not yet the right default for most enterprise internal networks** given the tail of IPv4-only legacy dependencies — dual-stack or IPv4-with-good-NAT is still the pragmatic choice for internal infrastructure that doesn't need to talk to the public IPv6 internet directly.

---

## Interview questions

### Q1 — How many usable hosts are in a /27? Derive it, don't just state it.
**Testing:** whether the arithmetic is real or memorized.
**Answer:** /27 leaves 5 host bits (32−27), so 2^5 = 32 total addresses, minus network and broadcast = **30 usable hosts**. Block size via the shortcut: mask is 255.255.255.224, 256−224=32, confirming the block size directly.
**Follow-up trap:** *"What about a /31?"* — RFC 3021 special-cases /31 for point-to-point links: both addresses are usable, no broadcast address exists, because a two-host link has no ambiguity about which is which. It's the one place the "usable = total−2" rule doesn't apply.

### Q2 — You have 10.0.4.0/22. What's the range, and how many /24s does it cover?
**Answer:** Mask 255.255.252.0, block size in the third octet is 256−252=4, so it spans 10.0.4.0 through 10.0.7.255 — four contiguous /24 blocks, 1024 total addresses, 1022 usable.
**Follow-up trap:** *"Could you carve this into eight equal subnets? What prefix?"* — 1024/8=128 addresses each → /25 per subnet (2^(32−25)=128). Confirm by checking 25−22=3 extra bits, 2^3=8 subnets. This kind of "carve N ways" follow-up is common and just requires knowing how many bits you're borrowing.

### Q3 — Explain longest prefix match with an example that has an ambiguous-looking match.
**Answer:** Given routes for 10.0.0.0/8, 10.1.0.0/16, and 10.1.2.0/24, a packet to 10.1.2.5 matches all three, but the router picks /24 because it's the most specific (longest) prefix that matches — the /8 and /16 entries are ignored even though they technically match too. It's never "first match" or "insertion order," always specificity first.
**Follow-up trap:** *"What if two routes have the exact same prefix length and both match?"* — that's the actual tie-break case: administrative distance (route source priority — a directly connected route beats a static route beats an OSPF route beats BGP, roughly) and then route metric/cost within the same source. Longest-prefix-match settles ties in specificity; AD/metric settles ties in equal specificity.

### Q4 — What's Path MTU Discovery, and how does it actually work end-to-end?
**Answer:** The sender sets the DF (Don't Fragment) bit on outgoing packets. If a router on the path can't forward the packet without fragmenting it (because the next hop's MTU is smaller), and DF is set, it drops the packet and returns ICMP Type 3 Code 4, which includes the next-hop MTU. The sender uses that to shrink subsequent packets (or, for TCP, to lower the effective MSS) and retries. No fragmentation ever actually happens on the path; the endpoints converge on a size that fits.
**Follow-up trap:** *"What happens if that ICMP message is blocked?"* — that's the PMTUD black hole: the sender never learns to shrink, keeps sending oversized packets, they keep getting silently dropped, and the connection hangs on any payload larger than the actual path MTU while small packets (including the handshake) work fine. Fix with TCP MSS clamping at the border rather than relying on ICMP getting through.

### Q5 — Why does IPv6 not allow routers to fragment packets?
**Answer:** It's a deliberate design change to push the cost of fragmentation entirely onto the sending host (via an IPv6 Fragment extension header, only ever added by the originating node) and off of every router in between, because in-network fragmentation costs router CPU on every hop and it turned out endpoints doing PMTUD from the start was strictly better. Routers that get an oversized packet just drop it and send back an ICMPv6 Packet Too Big message — mechanically similar to IPv4's ICMP type 3 code 4, but mandatory rather than best-effort, because there's no fallback.
**Follow-up trap:** *"What's the one MTU number IPv6 guarantees regardless of PMTUD?"* — 1280 bytes. Every link on an IPv6 path must support at least a 1280-byte MTU, which is why IPv6 hosts can always send at least that size without doing PMTUD first, as a safety floor.

### Q6 — Explain SNAT vs DNAT vs PAT and where each shows up in a real architecture.
**Answer:** SNAT rewrites source addresses on outbound traffic — a NAT gateway giving a private subnet a shared public IP for outbound internet access. DNAT rewrites destination addresses on inbound traffic — port forwarding, or a load balancer translating a public VIP to an internal backend IP. PAT (also called NAPT) is what makes many-to-one SNAT actually work by also rewriting the source port so the gateway can disambiguate return traffic for many internal hosts sharing one public IP, tracked by a stateful translation table keyed on the connection's 4-tuple.
**Follow-up trap:** *"Your NAT gateway has one public IP and thousands of instances behind it making lots of outbound connections. What breaks first?"* — port exhaustion on that public IP: PAT only has roughly 64,000 ports to allocate across every simultaneous outbound connection sharing that IP, and cloud NAT gateways document a hard per-IP port allocation. Fix is more NAT gateway IPs, or reducing connection churn (pooling/keep-alive) so fewer ports are held open simultaneously.

### Q7 — Why does FTP break under NAT, and how do modern protocols avoid the same problem?
**Answer:** FTP's active mode has the client tell the server, inside the FTP control-channel payload, an IP:port to connect back to for the data channel — NAT only rewrites packet headers, not application payload, so if that embedded address is the client's private internal IP, the server tries to connect to an address meaningless from outside the NAT, and the data connection fails (even though the control connection, which the client initiated outward, works fine). Modern protocols like WebRTC use ICE/STUN/TURN, which explicitly discover and exchange the actual public-facing reachable address rather than assuming a NAT device will fix up embedded addresses for them.
**Follow-up trap:** *"Does passive FTP fix this without an ALG?"* — mostly yes, because passive mode reverses the direction — the client, whose own NAT translation is already correctly established by a connection it initiated, opens the data connection to the server instead of the server trying to connect inbound to the client. It doesn't fix the case where the *server* is behind NAT for the data port, which is a rarer but real remaining gap.

### Q8 — What's the single biggest mechanical difference between ARP and NDP?
**Answer:** ARP (IPv4) resolves an IP to a MAC address using a broadcast "who has this IP" request that every device on the segment receives and processes. NDP (IPv6) does the equivalent using ICMPv6 Neighbor Solicitation/Advertisement messages sent to a **solicited-node multicast address** derived from the target's IP, so only devices that could plausibly own that address (and devices already snooping that multicast group) process it, instead of every device on the broadcast domain.
**Follow-up trap:** *"Does that actually reduce load on a large L2 segment?"* — yes, meaningfully, on switches doing IGMP/MLD snooping, because multicast frames only get forwarded to ports that joined that group rather than flooded everywhere like a broadcast. On a segment without multicast snooping configured, the practical benefit shrinks, which is a real operational gotcha people miss when they assume NDP is "free."

### Q9 — Design the addressing for a new VPC that needs to support 3 environments (dev/staging/prod), each with roughly 500 hosts, with room to grow.
**Answer:** 500 hosts needs at least 2^9=512 addresses (2^9−2=510 usable), so /23 per environment at minimum; give each environment a /22 (1022 usable) for growth headroom, and allocate the three /22s out of a parent block sized to fit all three plus spare capacity — a /20 (4096 addresses) comfortably fits three /22s (3×1024=3072) with room for a fourth environment later without renumbering.
**Follow-up trap:** *"Would you subdivide each /22 further by AZ or tier?"* — usually yes in a real cloud VPC, splitting each environment's /22 into per-AZ /24s (4 AZs × 256 = 1024, matching the parent) so subnet-per-AZ-per-tier design stays clean; the tradeoff is more route table entries and more IPs consumed by network/broadcast/reserved addresses per subnet (cloud VPCs typically also reserve a handful of addresses per subnet beyond the standard network/broadcast, which eats further into usable count — always check the specific cloud's reserved-address count before finalizing sizing).

### Q10 — What actually goes wrong when IPv4 exhaustion meets a growing fleet, mechanically?
**Answer:** There's no more IPv4 address space to hand out from the RIRs at any meaningful scale, so growth has to happen behind NAT/PAT (adding hosts behind existing public IPs) or via CGNAT at the ISP level (multiple customers sharing one public IP, each customer further NATed on their own router — a double NAT). Both increase the number of hosts sharing a finite pool of ~64K ports per public IP, which is exactly the mechanism that causes port exhaustion incidents as fleets scale, independent of any TCP/OS-level tuning.
**Follow-up trap:** *"Does IPv6 fully solve this or just move the problem?"* — it removes the address-exhaustion cause entirely (128-bit space is not going to run out), but it doesn't remove NAT-adjacent problems for the tail of clients/services still IPv4-only — those need NAT64/464XLAT translation layers, which reintroduce state and port-mapping concerns, just at a smaller scale and typically only at the network edge rather than throughout the internal fleet.

### Q11 — A service behind a corporate firewall can `ping` a host fine but `curl` to it hangs on any response body over a few KB. Diagnose it.
**Answer:** Classic PMTUD black hole signature — `ping`'s default payload is small and fits under any real-world MTU, so ICMP echo succeeding tells you nothing about whether larger TCP segments make it through. The TCP handshake (small packets) and small responses work; once a response segment needs to be close to the path MTU, if any router along the path needed to signal "too big" via ICMP and that ICMP is being dropped by the firewall, the connection just hangs with no error.
**Follow-up trap:** *"How do you confirm this without access to the firewall config?"* — from the client, run `tracepath` (which actively discovers the path MTU and reports it, unlike plain `traceroute`), or use `ping -M do -s <size>` sweeping sizes to find exactly where it breaks; from a packet capture, look for a large outbound segment with no corresponding ACK and no ICMP response at all, versus a normal fragmentation-needed ICMP which would at least show you the mechanism working correctly (just possibly still needing a fix at the endpoint).

---

## Red flags that fail you

- Guessing subnet host counts instead of deriving them from 2^(32−prefix)−2.
- Describing longest prefix match as "the first matching route" or "the most recently added route."
- Saying fragmentation "just works fine" without knowing PMTUD exists or that it can silently break.
- Claiming NAT is a security feature by design rather than an address-conservation mechanism with a security side effect.
- Not knowing IPv6 removes in-network fragmentation and the header checksum.
- Confusing CGNAT/PAT port exhaustion with a purely application-level bug.

---

## Cheat card

```
SUBNET MATH: usable hosts = 2^(32−prefix) − 2   (except /31, RFC 3021: both usable, no broadcast)
  block-size trick: 256 − (mask's last nonzero octet) = block size
  /24 → 254 hosts   /27 → 32 addrs, 30 hosts, block 32   /22 → 1024 addrs, 1022 hosts, spans 4×/24

ROUTING: longest prefix match wins, always — most specific route beats any less-specific match
  tie (equal prefix length) → administrative distance, then metric

FRAGMENTATION / PMTUD
  IPv4 header: Identification(16b) + Fragment Offset(13b, units of 8B) + flags DF/MF
  DF set + oversized → ICMP Type 3 Code 4 "frag needed" (RFC 1191 PMTUD)
  BLACK HOLE: firewall blocks that ICMP → large payloads hang, small ones work fine
  FIX: TCP MSS clamping at the border, not relying on ICMP getting through

MTU: Ethernet 1500 · PPPoE 1492 · jumbo 9000(-9216) · IPv6 minimum guaranteed 1280

NAT
  SNAT = rewrite source (outbound sharing)   DNAT = rewrite destination (port-forward/LB)
  PAT/NAPT = SNAT + port rewrite, ~64K ports per public IP, state table keyed on 4-tuple
  BREAKS: unsolicited inbound (no state entry) · embedded-IP protocols (FTP active, SIP/SDP)
  without ALG or STUN/TURN/ICE to fix the embedded address

IPv4 vs IPv6
  32-bit (~4.3B, exhausted 2011) vs 128-bit (~3.4e38, not exhausting)
  ARP (broadcast) vs NDP (ICMPv6 multicast Neighbor Solicitation/Advertisement)
  router fragmentation allowed vs NEVER (host-only frag header; ICMPv6 Packet Too Big)
  20-60B variable header vs 40B FIXED header, checksum REMOVED (relies on L2/L4 checksums)
  reality: NAT64/464XLAT bridging, not a clean full cutover
```

## Sources

- RFC 1519 — Classless Inter-Domain Routing (CIDR)
- RFC 1191 — Path MTU Discovery
- RFC 3021 — Using 31-Bit Prefixes on IPv4 Point-to-Point Links
- RFC 8200 — Internet Protocol, Version 6 (IPv6) Specification
- [Introduction to Subnetting — ITT Systems](https://www.ittsystems.com/introduction-to-subnetting/) — accessed 2026-07-26
- [Source Network Address Translation (SNAT) for outbound connections — Azure Load Balancer docs](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-outbound-connections) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
