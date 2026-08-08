# DNS Resolution, Load Balancer Internals (L4 vs L7), Proxies, CDN, Anycast

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-ip-layer, T29-tcp-deep · **Updated:** 2026-07-26
> **Module id:** `T29-dns-lb` · **Tags:** infra

## The 30-second version

DNS resolution is a cold cascade of up to 4 network round trips (stub → recursive resolver → root → TLD → authoritative) collapsed to zero on a warm cache hit, and every layer in that chain caches independently, which is why TTL-based failover is slow in practice — clients and resolvers routinely ignore or extend TTLs. Load balancers split into L4 (routes on IP/port, blind to HTTP, fast, can't do host/path routing) and L7 (terminates and parses HTTP, can route on path/header/cookie, costs latency and CPU for TLS termination and parsing). Consistent hashing matters because it remaps only `~1/n` of keys when a node joins or leaves, versus a naive modulo hash that remaps almost everything. Anycast routes to the BGP-nearest instance, which is a path-cost decision, not literal geographic distance — the same IP is announced from many locations and the internet's own routing picks one. CDNs make all of this fast by terminating both DNS and TCP/TLS at the edge and serving cached responses without ever touching origin.

## Why this gets asked

Because the interviewer has been paged for a DNS-related outage that took 30+ minutes to resolve when the actual fix took 30 seconds — because a client, a corporate resolver, or an old app kept a stale record cached well past its TTL. They've also watched a "least connections" load balancer make the wrong call under uneven request costs, or a sticky-session config silently break a rolling deploy. They want to know you understand *why* these systems behave the way they do under real caching and routing constraints, not just that you can define round-robin.

---

## Lineage: past → present → future

**What came before.** Before DNS (pre-1983), name-to-address mapping was a single flat `HOSTS.TXT` file maintained by SRI's Network Information Center and distributed to every machine on ARPANET by FTP. It didn't scale past a few thousand hosts — every rename was a manual, globally-synchronized edit, and by the early 1980s update lag and file size were breaking things. Paul Mockapetris's DNS (RFC 882/883, 1983) fixed this with a distributed, hierarchical, cacheable namespace — delegation meant nobody needed a global view, and caching with TTLs meant most lookups never hit the authoritative server at all. Load balancing's precursor was "round-robin DNS" alone (return multiple A records, let the client pick) — cheap, but blind to server health and slow to fail over because it inherits every problem TTL caching has.

**Where it stands now.** DNS is essentially unchanged in shape since the 1980s; what's changed is operational practice — most production DNS today sits behind managed services (Route 53, Cloudflare, NS1) that combine health-checked failover with short TTLs (30-60s is common for records that need to move) and, increasingly, DNS over HTTPS/TLS (DoH/DoT) for privacy rather than for the resolution mechanics themselves. Load balancing has converged on a layered architecture almost everywhere at scale: DNS or anycast picks a region/PoP, an L4 load balancer (or the network fabric itself) spreads TCP connections across a pool, and an L7 layer (ALB, Envoy, nginx) does host/path routing and TLS termination behind that. The live disagreement is where TLS termination and observability should live — sidecar-per-pod (service mesh model, Envoy/Istio/Linkerd) versus a shared L7 tier — trading per-request overhead against blast-radius and operational simplicity. Consistent hashing (Karger et al., 1997, originally for web caching) is now standard in any system that needs cache affinity at scale (CDN edge selection, sharded caches, Cassandra's own ring).

**Where it's heading.** Anycast + BGP-based routing is extending further down the stack — more services are anycast at L3 rather than routed only via DNS, because BGP failover (seconds) beats DNS TTL failover (minutes, in practice, due to caching that ignores TTL) for anything latency-sensitive; this is already how most large CDNs operate and the direction is firmly toward more of it. Adaptive/self-tuning load balancing (inferring capacity from observed latency rather than static weights, per Netflix's and Envoy's adaptive concurrency work) is shipping but not yet the default outside a handful of large operators — moderate confidence this becomes standard within a few years. DoH/DoT adoption for end-user privacy continues to grow but is a separate axis from the load-balancing mechanics covered here; treat that as orthogonal, not as changing how origin selection works.

---

## Mental model

```
COLD DNS LOOKUP (client has nothing cached)

 client ──▶ stub resolver ──▶ recursive resolver (ISP/Route53/8.8.8.8)
                                    │
                        (not cached) ▼
                              root server        ──▶ "ask .com TLD at X"
                                    │
                                    ▼
                              TLD server (.com)   ──▶ "ask ns1.example.com"
                                    │
                                    ▼
                              authoritative NS    ──▶ "A record = 1.2.3.4, TTL 300"
                                    │
                              (cached for 300s at every hop above)
                                    ▼
                              answer flows back to client

  Cold: up to 4 round trips (recursive→root→TLD→authoritative), often 20-120ms+
  Warm (cached at recursive resolver): 1 round trip, often <5ms
  Negative caching: NXDOMAIN answers are cached too (SOA-defined TTL) so a
  typo'd or not-yet-propagated name doesn't get re-queried on every request


LOAD BALANCER LAYERS

  Internet ──▶ [Anycast IP / GeoDNS]         picks a region
                   │
                   ▼
              [ L4 LB ]  sees IP:port only, no HTTP parsing
                   │      fast, cheap, can't route on path/host
                   ▼
              [ L7 LB / reverse proxy ]  terminates TLS, parses HTTP
                   │                     routes on path, host, header, cookie
                   ▼
              backend pool (round robin / least-conn / consistent hash)
```

---

## How it actually works

### DNS: the round trips, precisely

A fully cold lookup for `www.example.com` from a resolver with an empty cache: query root (told where `.com` TLD servers are — this step is often skipped in practice because root and TLD hints are pre-seeded and cached for days, root NS records commonly have TTLs in the days-to-week range), query the `.com` TLD server (told where `example.com`'s authoritative nameservers are, TLD delegation TTL commonly 1-2 days so this too is usually cached), query the authoritative server for the actual A record. In the worst real case that's 3 round trips before the client even gets an answer; in the common case, root and TLD delegation are already cached at the recursive resolver and only the authoritative query happens — 1 round trip, often single-digit to double-digit milliseconds. A warm cache hit at the recursive resolver itself costs 0 additional network round trips beyond client-to-resolver.

**Who honors TTL, and why this hurts you.** The authoritative server sets a TTL (e.g., 300s) on each record. Recursive resolvers are supposed to evict the cached entry after TTL expires and re-query. In practice: many client-side stacks and OS-level resolvers cache more aggressively or for longer than instructed (JVM's default DNS cache historically defaulted to caching successful lookups *forever* until process restart, unless `networkaddress.cache.ttl` was explicitly set), some corporate/ISP resolvers cap or extend TTLs for their own load reasons, and browsers keep their own short-lived DNS caches independent of the OS. The practical consequence: **DNS-based failover that assumes "TTL 60s means the whole world sees the new IP within 60s" is wrong** — real propagation to 100% of clients can take many minutes to hours because caches you don't control ignore your TTL. This is why anycast/BGP failover (seconds) is preferred over DNS failover for anything latency-sensitive, and why DNS-based failover needs a low TTL set *well in advance* of a planned migration, not at the moment of the incident.

**Negative caching.** An NXDOMAIN (name doesn't exist) or NODATA response is cached too, governed by the TTL in the zone's SOA record (the `minimum`/negative-cache-TTL field), commonly a few minutes to an hour. This means if you query a name before its DNS record propagates, you can get a cached "doesn't exist" answer that outlives the record's actual creation — a common cause of "I just created the record, why is it still failing" confusion.

**Record types that matter:**

| Type | Purpose | Gotcha |
|---|---|---|
| A / AAAA | hostname → IPv4/IPv6 | multiple records = simple DNS round robin, no health awareness |
| CNAME | alias one name to another | **cannot coexist with any other record at the same name** (including at the zone apex, where you also need SOA/NS records) — this is why you can't CNAME your root domain |
| ALIAS / ANAME | vendor-specific workaround | resolves like a CNAME but is flattened to an A record at the DNS provider's edge, so it can legally sit at the apex alongside NS/SOA/MX |
| MX | mail routing | has a priority field; multiple MX records for failover |
| TXT | arbitrary text | used for SPF (`v=spf1 ...`), DKIM public keys, domain ownership verification (e.g., `google-site-verification=`) |
| NS | delegates a zone to nameservers | wrong NS records = the classic "it works from my resolver but not from Google's" |
| SRV | service location (host+port+priority+weight) | used by protocols like SIP, XMPP, some service discovery; rare in plain web stacks |

### L4 vs L7 load balancing, concretely

**L4 (e.g., AWS Network Load Balancer)** operates on IP and TCP/UDP headers only. It doesn't terminate TLS and doesn't parse HTTP — it makes a per-connection (or per-flow) forwarding decision and then gets out of the way, passing packets through with minimal added latency (NLBs are commonly cited at low double-digit microseconds of added latency, and can handle millions of connections per LB). It cannot route `/api/*` to one pool and `/static/*` to another, because it never looks past the TCP header. Use it when you need raw throughput, need to preserve client IP without extra headers, or are load-balancing a non-HTTP protocol.

**L7 (e.g., AWS Application Load Balancer, nginx, Envoy)** terminates the client's TLS connection, parses the HTTP request line and headers, and can route on path, host header, cookie value, or arbitrary header content. This is what lets one LB front multiple services on one domain (`example.com/api` → service A, `example.com/app` → service B) or route based on an `Authorization` header. Cost: it does real CPU work (TLS handshake crypto, HTTP parsing) per request, adding measurable latency (single-digit milliseconds typically) and requiring the LB to scale with request rate, not just connection count.

Concrete combined pattern (common at scale): anycast/GeoDNS picks a region, an NLB (L4) absorbs raw connection volume and spreads it across a fleet of L7 proxies, and the L7 tier (ALB/Envoy) does host/path routing, TLS termination, and application-aware health checks. This is layered specifically because L4 is cheap enough to put in front of everything, and L7 is expensive enough that you want exactly as many of them as you need for routing logic, not more.

### Load balancing algorithms

- **Round robin** — simplest, ignores server load; fine when requests are uniform cost and servers are homogeneous.
- **Least connections** — routes to the backend with fewest active connections; better under uneven request duration, but "fewest connections" isn't the same as "least loaded" if connections vary wildly in cost.
- **Weighted (round robin or least-conn)** — accounts for heterogeneous instance sizes or canary traffic percentages.
- **Consistent hashing** — hashes both the key (e.g., client ID, cache key, session ID) and the servers onto a ring; a request goes to the next server clockwise from its hash position. **Why it matters:** with naive `hash(key) % n`, adding or removing one server changes `n` and remaps almost every key to a different server — for a cache, that's a near-total cache wipe. Consistent hashing bounds the remap to roughly `1/n` of keys when one node joins or leaves, because only the keys between the new/removed node's ring position and its immediate neighbor move. This is why it's the default for anything needing cache affinity: CDN edge selection, sharded caches (memcached client-side hashing), Cassandra's own partitioner.

### Health checks

**Active** — the LB itself periodically probes each backend (`GET /healthz` every N seconds) and removes failures from rotation. **Passive** — the LB observes real traffic outcomes (a backend returning 5xx or timing out on live requests) and ejects it without a dedicated probe. The tuning tension: an aggressive check interval (e.g., every 1-2s with a low failure threshold) detects failures fast but risks a **thundering herd** — if a health check interval is short and many backends briefly blip together (a GC pause, a deploy, a shared dependency hiccup), the LB can eject a large fraction of the fleet simultaneously, concentrating all remaining traffic onto the survivors and cascading the failure. Mitigation: require multiple consecutive failures before ejection (not one), stagger check intervals across backends, and cap how much of the fleet can be ejected at once (outlier detection with a max-ejection-percentage, as Envoy implements).

### Sticky sessions

Cookie-based affinity (LB sets a cookie routing subsequent requests to the same backend) or IP-hash affinity (hash client IP to a backend) both pin a client to one instance. This fights horizontal scaling directly: you can't freely add/remove backends without disrupting pinned sessions, a rolling deploy has to drain sticky sessions gracefully rather than just cycling instances, and IP-hash affinity breaks when many clients sit behind one NAT/corporate proxy (they all hash to the same backend, causing an uneven hot spot). The better long-term fix is usually externalizing session state (Redis, a shared store) so any backend can serve any request, removing the need for affinity entirely — but that's a real engineering cost, which is why sticky sessions persist in practice for legacy stacks.

### Anycast

The same IP prefix is announced via BGP from multiple physical locations. Internet routers pick a path based on BGP's own path-selection algorithm (shortest AS-path, local preference, and other policy attributes) — this converges toward "fewer network hops," not literal geographic proximity. A user in Brazil can, due to peering and transit arrangements, end up routed to a PoP in the US if that path has a better BGP cost than a geographically closer PoP with worse peering. This is used for DNS root servers (13 logical root server addresses, each anycast from dozens to hundreds of physical sites) and CDN edge networks. Failover is fast: withdraw the BGP announcement from a failing site and traffic shifts to the next-best route within the normal BGP convergence window (seconds, versus DNS TTL's minutes-to-hours).

### CDN behavior

An edge node caches responses keyed by a **cache key** that the CDN operator configures — by default often just the URL path, but query params, specific headers (`Accept-Encoding`, `Authorization` presence), and cookies can all be included or explicitly excluded from the key. Getting this wrong is a classic incident: forgetting to vary the cache key on `Accept-Language` serves the wrong locale to everyone; including a per-user header in the key when it shouldn't matter fragments the cache into one entry per user and defeats caching entirely. **Purge/invalidation** is either instant-but-expensive (purge-everything, used sparingly) or tag/surrogate-key based (purge only entries tagged with a specific product ID, cheaper and more surgical, requires the origin to emit the right tags). **Origin shielding** designates one CDN PoP as the sole one allowed to fetch from origin on a cache miss, so N edge PoPs experiencing simultaneous misses for the same object collapse into one origin request instead of N — this is the direct fix for "thundering herd on cache expiry across edges."

---

## Build it from scratch

A minimal consistent-hashing ring, the piece of this module most likely to be asked as a whiteboard/coding exercise:

```python
import bisect
import hashlib

class ConsistentHashRing:
    def __init__(self, nodes=None, vnodes=150):
        self.vnodes = vnodes          # virtual nodes per real node smooth out load
        self.ring = {}                # hash -> node
        self.sorted_keys = []
        for node in nodes or []:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.vnodes):
            h = self._hash(f"{node}#{i}")
            self.ring[h] = node
            bisect.insort(self.sorted_keys, h)

    def remove_node(self, node: str):
        for i in range(self.vnodes):
            h = self._hash(f"{node}#{i}")
            del self.ring[h]
            self.sorted_keys.remove(h)

    def get_node(self, key: str) -> str:
        if not self.ring:
            raise RuntimeError("empty ring")
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]
```

Adding or removing a node only touches the `~1/n` fraction of keys whose ring position falls in that node's arc — verify this experimentally by hashing 10,000 keys, recording their node assignment, adding one node, and counting how many keys changed assignment (should land close to `10000/n`, not near 10000). Virtual nodes (150 per physical node above) exist because a single hash position per node produces uneven arc sizes on the ring; multiple virtual positions per node smooth the load distribution.

---

## How it's done in production

| Concern | Managed/framework tool | What it adds |
|---|---|---|
| DNS with health-checked failover | Route 53, Cloudflare, NS1 | Combines DNS answers with active health checks; can fail over in the time it takes clients to re-query (bounded by TTL, not instant) |
| L4 load balancing | AWS NLB, GCP Network LB, IPVS | Millions of connections per LB, near-zero added latency, preserves client IP |
| L7 load balancing / API gateway | AWS ALB, nginx, Envoy, HAProxy | Host/path routing, TLS termination, WAF integration, request-level observability |
| Service mesh L7 | Istio/Linkerd (Envoy sidecar) | Per-service outlier detection, consistent-hash-based load balancing for cache affinity, mTLS between services |
| CDN | Cloudflare, Fastly, CloudFront, Akamai | Anycast edge network, origin shielding, tag-based purge, edge compute |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Failover took 20 minutes despite a 60s TTL | Clients/resolvers ignoring or overriding TTL (stale OS/app-level DNS cache) | Lower TTL well before the migration window; prefer anycast/BGP failover for latency-sensitive services; verify with `dig` against multiple public resolvers |
| One backend gets far more traffic than its peers | IP-hash affinity with many clients behind one corporate NAT | Switch to cookie-based affinity or remove affinity and externalize session state |
| LB ejects half the fleet simultaneously | Health check interval too aggressive, single-failure threshold, correlated blips (GC pause across the fleet) | Require N consecutive failures, stagger check timing, cap max-ejection-percentage |
| Cache hit rate near zero despite caching enabled | Cache key includes a header/cookie that varies per request unnecessarily (e.g. full `Authorization` or per-user cookie) | Strip irrelevant headers/cookies from the cache key; separate personalized from cacheable content |
| Users briefly see another user's cached page | Personalized response cached at a shared (non-private) cache layer | `Cache-Control: private` on personalized responses; fetch personalization client-side |
| Rolling deploy disrupts sessions, users get logged out mid-session | Sticky sessions pinned to instances being cycled | Drain sticky connections before terminating an instance; move to externalized session state |
| Cannot point apex domain at a load balancer's hostname | CNAME not allowed at zone apex alongside required NS/SOA records | Use ALIAS/ANAME (provider-specific flattening) or an A record with the LB's static/anycast IP if available |
| CDN origin gets hammered right when a popular object's TTL expires | Many edge PoPs miss simultaneously and each fetches independently | Enable origin shielding so only one PoP fetches on miss, others get it from the shield |

---

## Tradeoffs & when NOT to use it

- **Don't rely on DNS TTL for time-critical failover.** Caches you don't control (OS resolvers, corporate proxies, old JVMs) routinely ignore or extend TTLs; use anycast/BGP-based failover or a health-checked proxy layer for anything where minutes of stale routing is unacceptable.
- **Don't put an L7 load balancer where an L4 one would do.** If you're not routing on HTTP content, the TLS termination and HTTP parsing cost of L7 is pure overhead — use L4 for raw TCP/UDP fan-out and reserve L7 for where host/path/header routing is actually needed.
- **Don't use sticky sessions as a substitute for fixing statelessness.** They work, but they permanently couple your scaling and deploy story to session placement; externalizing session state is more work up front and pays for itself the first time you need to scale or deploy without disruption.
- **Don't cache personalized responses at a shared cache layer** without `Cache-Control: private` or equivalent — this is a data leak, not just a performance bug.
- **Don't assume anycast means "routed by physical distance."** BGP path cost, not geography, decides — if you need guaranteed regional routing (data residency, compliance), anycast alone doesn't give you that; you need explicit region pinning.

---

## Interview questions

### Q1 — Walk through a cold DNS lookup, with round-trip counts.
**Testing:** whether the caching hierarchy is actually understood, not memorized as a diagram.
**Answer:** Stub resolver asks the recursive resolver; if nothing is cached there, it queries a root server (usually already cached for days via seed hints), then the TLD server (usually cached ~1-2 days from prior delegation lookups), then the authoritative server for the actual record. In the fully cold case that's up to 3-4 network round trips; in the common case, root/TLD are already cached and it's 1 round trip to the authoritative server. A warm hit at the recursive resolver costs 0 additional round trips beyond client-to-resolver.
**Follow-up trap:** *"Where does the client itself cache, separately from the recursive resolver?"* — the OS resolver cache and often the browser's own DNS cache, both independent of whatever TTL the recursive resolver honors, which is exactly why "I updated the TTL" doesn't guarantee fast propagation to end users.

### Q2 — Why is DNS-based failover often slower in practice than its TTL suggests?
**Answer:** Because TTL is advisory, not enforced — many resolvers and client stacks cache longer than instructed (historically the JVM cached indefinitely unless configured otherwise), corporate/ISP resolvers sometimes extend TTLs for their own load reasons, and browsers keep independent short caches. A 60s TTL is a best case, not a guarantee, across a population of clients you don't control.
**Follow-up trap:** *"So how do you get fast failover for a latency-sensitive service?"* — anycast at the IP layer with BGP withdrawal on failure (seconds to converge), not DNS record changes, because BGP convergence isn't subject to arbitrary client-side caching the way DNS is.

### Q3 — Why can't you put a CNAME at your zone apex (the bare domain, no subdomain)?
**Answer:** DNS requires the apex to also hold NS records (delegating the zone) and typically SOA, and the spec disallows any other record type coexisting at a name that has a CNAME. Since you can't have a CNAME-only apex without breaking zone delegation, most registrars/DNS providers reject it outright.
**Follow-up trap:** *"How do people point their apex domain at a CDN or LB hostname anyway?"* — ALIAS/ANAME records (provider-specific, not a real DNS RR type), which resolve like a CNAME internally at the DNS provider's edge but are flattened into an A/AAAA record before being served, so they can legally coexist with NS/SOA at the apex.

### Q4 — What's the actual difference between L4 and L7 load balancing, mechanically?
**Answer:** L4 makes its routing decision from the IP header and TCP/UDP port only — it never parses the HTTP payload, so it's fast (near-zero added latency, huge connection throughput) but can't route on path, host header, or cookie. L7 terminates TLS and parses the HTTP request, so it can route `/api` to one pool and `/static` to another, inspect headers/cookies, and do content-based decisions — at the cost of real CPU work per request.
**Follow-up trap:** *"Give a concrete example of each from a major cloud provider."* — AWS NLB (L4) versus AWS ALB (L7); NLB preserves client source IP and handles millions of connections with microsecond-scale added latency, ALB does host/path-based routing and needs the TLS cert.

### Q5 — Why does consistent hashing matter for a distributed cache, specifically?
**Answer:** With `hash(key) % n`, changing `n` (adding or removing a server) remaps nearly every key to a different server — for a cache that means a near-total wipe of hit rate right when you're scaling. Consistent hashing places both keys and servers on a ring; adding/removing one server only remaps the keys in that server's arc of the ring, roughly `1/n` of all keys, leaving the rest of the cache warm.
**Follow-up trap:** *"Why use virtual nodes instead of one ring position per server?"* — a single position per physical node produces uneven arc sizes (some servers get a disproportionate share of the keyspace by chance); adding ~100-200 virtual positions per physical node smooths the distribution close to uniform.

### Q6 — Your health check interval is 1 second with a 1-failure threshold. What can go wrong?
**Answer:** A brief correlated blip across many backends at once — a shared dependency hiccup, a GC pause, a deploy — can eject a large fraction of the fleet simultaneously, dumping all remaining traffic onto whatever's left and potentially cascading the failure (thundering herd via health checking).
**Follow-up trap:** *"How do you fix it without slowing down real failure detection?"* — require multiple consecutive failures (e.g., 3) before ejection rather than 1, stagger check timing across backends so they don't all probe (and potentially fail) in the same instant, and cap the maximum percentage of the fleet that can be ejected at once (Envoy's outlier detection supports this directly).

### Q7 — What does sticky-session affinity cost you, architecturally?
**Answer:** It couples client requests to a specific backend instance, which fights horizontal scaling (you can't add/remove instances freely without disrupting pinned sessions) and complicates deploys (a rolling restart has to drain sticky connections gracefully instead of just cycling instances). IP-hash affinity specifically also breaks down when many clients share one NAT/corporate IP, hot-spotting one backend.
**Follow-up trap:** *"What's the alternative and why isn't it always done?"* — externalize session state (Redis, a shared store) so any backend can serve any request; it's not always done because it's real upfront engineering work and legacy stacks were often built session-per-instance from the start.

### Q8 — Explain anycast, and correct the claim "anycast routes to the nearest server."
**Answer:** The same IP prefix is announced from multiple physical locations via BGP; the network routes each client to whichever announcement has the best BGP path cost from its perspective — shortest AS-path and other policy attributes, not physical/geographic distance. A client can end up routed to a farther-away site if that path has better peering.
**Follow-up trap:** *"Does that mean anycast can't be used for something requiring regional data residency?"* — correct, anycast alone gives you no guarantee of which physical region actually serves a given client; regional pinning requires explicit routing logic (GeoDNS-based region selection, or application-level region enforcement) layered on top, not anycast by itself.

### Q9 — A CDN's cache hit rate on a personalized page suddenly matches its miss rate at scale — what's the likely cause and what's the risk?
**Answer:** Most likely the cache key includes something that varies per user (a session cookie or the full `Authorization` header) fragmenting the cache into effectively one entry per user, or — more dangerously — the response is being cached at a shared cache layer *without* `Cache-Control: private`, in which case the risk isn't just poor hit rate, it's that another user could be served your personalized/session data from cache.
**Follow-up trap:** *"How would you actually verify which of those two it is?"* — check whether cached entries are being reused across different user sessions (a real leak, urgent) versus each user simply generating their own unique, never-reused cache entry (a hit-rate problem, not a security incident) — inspect the cache key configuration and correlate served content with the requesting session.

### Q10 — Why do large systems layer anycast/GeoDNS, then L4, then L7, instead of picking one?
**Answer:** Each layer is solving a different, cheaper-at-its-own-scope problem: anycast/GeoDNS picks a region cheaply (BGP-level, no per-request cost), L4 absorbs raw connection volume within that region at near-zero per-connection cost, and L7 does the expensive routing logic (TLS termination, path/host routing) only for the fraction of decisions that actually need HTTP awareness. Collapsing all of it into one L7 tier means paying HTTP-parsing cost for traffic that never needed content-based routing.
**Follow-up trap:** *"Where would you add a service mesh (Envoy sidecar) into that stack, and why?"* — inside the L7 tier's domain, at the service-to-service hop rather than at the edge — it adds per-service outlier detection, mTLS, and consistent-hash-based routing for cache affinity between internal services, which the edge-facing L7 layer isn't positioned to do since it doesn't see internal east-west traffic.

### Q11 — Design DNS + load-balancing for a service that must fail over across regions within 10 seconds of a region going down.
**Answer:** DNS TTL alone can't guarantee 10 seconds given client-side caching behavior outside your control, so anchor failover on anycast: announce the service IP from multiple regions via BGP, and withdraw the announcement from the failed region on health-check failure — BGP convergence is typically seconds. Use DNS (short TTL, health-checked) as a secondary/coarser mechanism, not the primary failover path, for clients or resolvers that don't sit behind the anycast network.
**Follow-up trap:** *"What if you don't control the network layer enough to do BGP anycast (e.g., you're built entirely on a single cloud's managed LB)?"* — use the cloud provider's own global load-balancing/anycast product (e.g., a global anycast frontend with regional backends) rather than building BGP yourself, and treat DNS failover purely as the fallback for anything outside that provider's anycast network.

### Q12 — What's origin shielding and what specific failure does it prevent?
**Answer:** Designating one CDN PoP as the only one allowed to fetch from origin on a cache miss; other PoPs fetch from the shield instead of origin directly. It prevents the thundering-herd case where a popular object's TTL expires and dozens/hundreds of edge PoPs simultaneously experience a miss and all hit origin at once, spiking origin load momentarily to something it wasn't provisioned for.
**Follow-up trap:** *"Does shielding add latency for the common case?"* — a small amount for shield-to-origin hops on the rare cache-miss path, which is a reasonable trade since the alternative is protecting origin from a load spike that could otherwise cause a real outage; the added latency only applies on miss, not on the (much more common) edge cache hit.

---

## Red flags that fail you

- Saying DNS failover is "instant once the TTL expires."
- Describing L4 and L7 load balancing as differing only in "speed" without explaining *why* (HTTP parsing/TLS termination).
- Claiming anycast routes by literal geographic distance.
- Not knowing why a CNAME can't sit at the zone apex.
- Recommending sticky sessions as a first choice rather than naming the tradeoff against horizontal scaling.
- Configuring (or describing) a CDN cache key without considering personalization/security implications.

---

## Cheat card

```
DNS LOOKUP   cold: stub→recursive→root→TLD→authoritative, up to 3-4 RTT
             warm (recursive cache hit): 1 RTT or less
             TTL is ADVISORY -- clients/resolvers routinely ignore/extend it
             negative caching: NXDOMAIN cached too, via SOA minimum TTL

RECORDS      A/AAAA: addr, multi = naive round robin
             CNAME: alias; CANNOT coexist w/ other records at same name/apex
             ALIAS/ANAME: apex workaround, flattens to A at provider edge
             MX: mail + priority · TXT: SPF/DKIM/verification · NS: delegation
             SRV: host+port+priority+weight (service discovery)

LB LAYERS    L4 (NLB): IP/TCP only, no HTTP visibility, microsec latency,
                       can't route on path/host
             L7 (ALB/nginx/Envoy): terminates TLS, parses HTTP,
                       routes path/host/header/cookie, real CPU cost/req

ALGORITHMS   round robin (uniform cost) · least-conn (uneven duration)
             weighted (heterogeneous/canary)
             consistent hashing: node change remaps ~1/n keys, not ~all
                       (vs modulo hash which remaps nearly everything)
                       virtual nodes (~100-200/node) smooth load

HEALTH CHECK active (LB probes) vs passive (observes live traffic)
             aggressive interval + 1-failure threshold = thundering herd
             fix: N consecutive failures, staggered checks, max-eject %

STICKY       cookie or IP-hash; fights horizontal scaling + complicates
             deploys; IP-hash hot-spots behind shared NAT

ANYCAST      same IP, many sites, BGP picks path -- "nearest" = lowest
             BGP cost, NOT geographic distance; failover = seconds (BGP
             withdrawal) vs DNS minutes-hours (client cache behavior)

CDN          cache key = URL + configured headers/params/cookies
             wrong key => wrong-locale/wrong-user leaks or near-0 hit rate
             origin shielding: 1 PoP fetches on miss, others hit the shield
```

## Sources

- [How CDN Edge Routing Works: Anycast, GeoDNS, and BGP — Stackademic](https://blog.stackademic.com/how-cdn-edge-routing-works-anycast-geodns-and-bgp-for-system-designers-1f026b898297) — accessed 2026-07-26
- [Networking Essentials for System Design Interviews — Hello Interview](https://www.hellointerview.com/learn/system-design/core-concepts/networking-essentials) — accessed 2026-07-26
- [System Design: Load Balancer Architecture — L4 vs L7 — techinterview.org](https://www.techinterview.org/post/3233474140/system-design-load-balancer-architecture-l4-l7-nginx-haproxy-round-robin-least-connections-health-checks-ssl-termination/) — accessed 2026-07-26
- [How to Set Up Session Affinity with Consistent Hashing — OneUptime](https://oneuptime.com/blog/post/2026-02-17-how-to-set-up-session-affinity-with-consistent-hashing-on-gcp-load-balancer/view) — accessed 2026-07-26
- [DNS Anycast: Concepts and Use Cases — Catchpoint](https://www.catchpoint.com/dns-monitoring/dns-anycast) — accessed 2026-07-26
- [Path MTU Discovery and network ACLs — AWS VPC docs](https://docs.aws.amazon.com/vpc/latest/userguide/path_mtu_discovery.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
