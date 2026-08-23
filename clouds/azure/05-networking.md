# Azure Networking Deep: VNet, NSG, App Gateway, Front Door, Private Link

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-networking` · **Tags:** networking,critical

## The 30-second version

Azure's load-balancing stack splits by layer and scope, and the interview lives in that split: **Load Balancer** is regional Layer-4 (TCP/UDP, ultra-low latency, the Basic SKU retired September 30, 2025 leaving Standard as the answer); **Application Gateway** is regional Layer-7 HTTP(S) with WAF, path-based routing, and autoscaling up to ~125 units; **Front Door** is global anycast Layer-7 doing TLS termination at the edge, caching, and cross-region failover with 99.99%-class SLA; Traffic Manager is just DNS. Under everything sits VNet plumbing whose two most misunderstood facts are that peering is **non-transitive** (hub-and-spoke needs explicit routing through the hub) and that each subnet reserves 5 IP addresses. The production killers worth knowing cold: private-endpoint DNS split-brain in hybrid environments, and outbound SNAT port exhaustion when fleets scale without a NAT Gateway — both produce intermittent timeouts that look like application bugs.

## Why this gets asked

Because Azure networking failures masquerade as application failures. Interviewers have spent days chasing "random" 502s that were actually Front Door health-probe misconfigurations, "slow databases" that were SNAT exhaustion on a scale set, and security reviews failing because someone confused service endpoints (traffic still public-originating with identity claims) with private endpoints (actual private IPs). The staff-level question is never "what is an NSG" — it's designing ingress for a multi-region web estate (Front Door → locked-down App Gateway → private backend), explaining exactly which hop terminates TLS and why, and knowing where packets physically travel versus what the diagram implies.

---

## Lineage: past → present → future

**What came before.** Azure's original model was Cloud Services VIPs: one public IP per deployment, load-balanced at L4 with ACLs instead of NSGs, no overlay networking customers could shape. VNet arrived (2014-era ARM transition) bringing CIDR-defined address space, subnets, UDRs, and network security groups borrowed conceptually from AWS Security Groups but rule-based like firewall ACLs (priority-ordered). Application Gateway (2016) added regional L7; Traffic Manager had carried global traffic via DNS since early days; the original Azure CDN (Verizon partnerships) handled edge caching separately. Everything global-but-dumb (TM) or smart-but-regional (App GW) forced awkward compositions.

**Where it stands now.** Front Door's 2020-2022 rebuild into the Microsoft edge unified global L7 routing, TLS, caching, and WAF under one product with Standard/Premium tiers, and Private Link origins let it route into VNets without public exposure. The portfolio consolidated decisively: Basic Load Balancer retired September 30, 2025 (existing instances keep running unsupported, no SLA), pushing everyone to Standard LB with zone redundancy and secure-by-default posture; App Gateway v2 became the only supported version with autoscaling; Application Gateway for Containers emerged as the AKS-native evolution of the ingress controller story. Service endpoints are effectively legacy guidance — private endpoints are the recommended pattern everywhere despite their cost and DNS overhead. The live disagreement: whether every architecture needs Front Door (its fixed monthly-plus-per-GB cost is hard to justify for single-region internal apps) or whether App Gateway alone suffices until global distribution is real.

**Where it's heading.** High confidence: continued consolidation of the edge portfolio around Front Door and of container ingress around Application Gateway for Containers; private-endpoint-everything as the zero-trust default with the DNS complexity permanently attached; NAT Gateway as the universal answer to outbound problems. Medium confidence: deeper post-quantum-TLS and QUIC/HTTP-3 support reaching GA across the edge products. Speculative: AI-driven WAF policy tuning and anomaly-based routing changes — treat vendor demos skeptically. The durable truth regardless: L7-global versus L7-regional versus L4 decisions will keep being made by humans who understand what each layer can and cannot see.

---

## Mental model

```
                        GLOBAL INGRESS STACK

 Internet ──anycast──▶ FRONT DOOR (global, L7)
                       TLS @ edge · cache · WAF · geo/failover routing
                              │
                              ▼ (Private Link origin / public host)
                       APP GATEWAY v2 (regional, L7)
                       WAF(OWASP CRS) · path rules · cookie affinity
                              │
                              ▼
                       BACKEND POOL / VMSS / CA / AKS ingress
                              │
        ──────────────────────┼──────────────────────────
        INTERNAL EAST-WEST    │          OUTBOUND
        ▼                     │          ▼
   NSG (subnet+NIC,           │     NAT GATEWAY (dedicated SNAT ports,
   stateful, priority rules)  │      kills SNAT exhaustion)
   Azure Firewall (L4-L7,     │     OR Load Balancer outbound rules
   IDPS/threat-intel, hub)    │
   Private Link ◀─────────────┘  (PaaS via private IP, DNS privatelink zones)

 L4 = Load Balancer (regional/cross-region, TCP/UDP, no payload visibility)
 DNS-only global = Traffic Manager (caches TTL, slowest failover)
```

The one-liner: **each layer routes on what it can read** — DNS sees names, L4 sees ports, L7 sees paths/headers/cookies — so capability questions ("can it do path-based routing?") resolve by asking "what can this layer see?"

---

## How it actually works

### VNet fundamentals people get wrong

Address space is CIDR you define per VNet; subnets carve it, and **every subnet reserves 5 addresses** (first 4 plus last) — a /29 gives you 3 usable hosts, which surprises nobody who planned capacity assuming 8. Peering connects VNets privately over the Microsoft backbone with no encryption-by-default caveat needed (traffic stays on backbone), but it is **non-transitive**: spoke-to-spoke traffic requires the hub to forward (NVA or gateway transit), because peered VNets don't automatically learn routes through each other. Service tags (`Sql`, `Storage`, `AzureFrontDoor.Backend`) encode Microsoft-maintained CIDR groups for use in NSG/UDRs — the mechanism behind "only allow Front Door" patterns. Effective security is the union evaluation of NSGs at subnet AND NIC level (both must allow for most flows), plus ASGs grouping NICs by role instead of managing IP lists.

### NSG mechanics

Stateful, priority-ordered (custom rules occupy 100-4096; lower number wins; implicit deny-all inbound at 4096+), applied at subnet and/or NIC. Rules match tuple + source/destination ASG/IP/tag + port ranges + protocol. What NSGs cannot do: L7 inspection, FQDN filtering, threat intelligence, logging depth beyond flow logs. That gap is Azure Firewall/NVA territory: managed L4-L7 with DNAT/SNAT, FQDN-based egress rules, IDPS (Premium), and structured logs — deployed in hub VNets for enterprise east-west and egress control. Flow logs + Traffic Analytics give the "who talked to what" evidence chain for both debugging and audits.

### The load-balancing decision tree

| Need | Answer | Why |
|---|---|---|
| Global users, HTTP(S), edge TLS/cache/WAF | **Front Door** (Standard/Premium) | Anycast edge POPs, ~99.99% SLA, instant failover |
| Regional L7, internal or single-region | **Application Gateway v2** | Path/host routing, WAF OWASP CRS, autoscale 0-~125 units |
| Non-HTTP protocols, highest throughput | **Standard Load Balancer** | L4 TCP/UDP, zone-redundant, ~99.99% SLA |
| Multi-protocol global steering, tolerate DNS TTL | Traffic Manager | No traffic path, DNS answers only |

Basic Load Balancer retired September 30, 2025: surviving instances run without support or SLA; migration scripts exist but the Standard SKU changes behavior — secure-by-default (NSG required for inbound), outbound access blocked unless explicitly ruled, static public IPs mandatory during upgrade.

### Front Door specifics

Anycast enters nearest POP; routing rules match host+path then select origin group with health-probe-driven weighting/priority. Probes matter more than teams expect: wrong probe path (returns 404) marks all origins unhealthy and produces mysterious 502s; probe traffic also bills. Premium tier adds Private Link origins — the backend receives traffic via private endpoint, nothing public exposed. The standard lock-down pattern for FD→AGW backends: App Gateway allows only `AzureFrontDoor.Backend` service tag plus validates the `X-Azure-FDID` header (your unique FD ID) so attackers can't bypass the edge and hit App Gateway's public IP directly.

### Private Link and the DNS problem

A private endpoint injects a NIC with a private IP into your subnet bound to one specific resource instance. Traffic to the PaaS endpoint resolves (via privatelink DNS zones) to that IP and traverses the backbone privately; data exfiltration protection ties endpoints to approved resources. Costs: small hourly charge per endpoint plus per-GB data processing (~pennies class — verify current rates). The operational tax is DNS: hybrid environments split-brain when on-prem resolvers answer `vault.azure.net` with public IPs while VNets expect private answers. Correct pattern: privatelink private DNS zones linked to every resolving VNet, conditional forwarders on-prem pointing at Azure DNS (or vice versa), and treating DNS records as infrastructure-as-code — because a missing A-record breaks auth flows in ways that look like identity bugs.

### Outbound: SNAT exhaustion, the silent killer

Instances without explicit outbound config get SNAT ports carved from the public IP associated with their load balancer — allocation scales with instance count (algorithmically from ~1024 ports/small instances up toward ~64k/large). Each outbound connection consumes a port for its duration; fleets opening thousands of short-lived connections (HTTP APIs, SDKs without connection pooling) exhaust ports and hang intermittently — symptoms are random connection resets/timeouts correlated with scale-out events. Fix: **NAT Gateway** (dedicated static SNAT ports per instance, 64k ports/IP, zonal) or explicit LB outbound rules sized deliberately. This should be default configuration for anything scaling past a handful of instances.

### ExpressRoute and hybrid

ExpressRoute gives private BGP-peered circuits (1 Gbps-10 Gbps classes, FastPath bypassing gateways for high throughput) versus S2S VPN (IPsec over internet, ~1-10 Gbps-class ceiling varies by SKU, cheaper, faster to stand up). Hybrid DNS and asymmetric routing (Microsoft-peering advertisements fighting public paths) are the standing foot-guns.

---

## Build it from scratch

A minimal L7 router matching how App Gateway/Front Door evaluate rules:

```python
# untested sketch — path+host routing & health-aware origin selection
from dataclasses import dataclass, field

@dataclass
class Origin:
    name: str
    healthy: bool = True

@dataclass
class RouteRule:
    host: str | None          # None = wildcard
    path_prefix: str
    origin_pool: list         # list[(Origin, weight)]
    protocol: str = "https"

class EdgeRouter:
    def __init__(self, rules: list[RouteRule]):
        self.rules = sorted(rules, key=lambda r: len(r.path_prefix), reverse=True)

    def route(self, host: str, path: str) -> str:
        # longest-prefix match wins (same as AGW path maps / FD route precedence)
        for r in self.rules:
            if r.host in (None, host) and path.startswith(r.path_prefix):
                pool = [o for o, w in r.origin_pool if o.healthy]
                if not pool:
                    raise RuntimeError("502: no healthy origins")   # FD returns 502 here
                total = sum(w for o, w in r.origin_pool if o.healthy)
                pick = hash(path) % total                            # naive weighted pick
                acc = 0
                for o, w in r.origin_pool:
                    if not o.healthy: continue
                    acc += w
                    if pick < acc:
                        return o.name
        raise RuntimeError("404: no route matched")

router = EdgeRouter([
    RouteRule("api.example.com", "/v2", [Origin("gw-east"), Origin("gw-west", True)]),
    RouteRule(None, "/", [Origin("static-cdn")]),
])
print(router.route("api.example.com", "/v2/users"))   # -> gw-east or gw-west
print(router.route("www.example.com", "/about"))       # -> static-cdn
```

Every managed feature — weighted pools, priority failover, health gating, longest-prefix matching — reduces to this loop plus probe state; understanding it makes probe misconfiguration bugs legible.

## How it's done in production

Reference topology: Front Door Premium (WAF + Private Link origins) globally, App Gateway v2 (WAF, zone-redundant) regionally locked to FD via service tag + FD-ID header validation, backends private-endpoint-only; hub-spoke VNets with Azure Firewall Premium controlling east-west and egress by FQDN; NAT Gateways on every spoke subnet needing outbound; privatelink DNS zones as code with hybrid conditional forwarders documented; flow logs + Traffic Analytics feeding SIEM; NSGs generated from policy (no hand-edits) with ASGs for role groups.

| Symptom | Cause | Fix |
|---|---|---|
| Random 502s from Front Door, backends fine | Health probes hitting wrong path/port returning errors | Align probe path with real health endpoint; monitor probe-failure metrics |
| Intermittent outbound timeouts after scale-out | SNAT port exhaustion on default outbound | NAT Gateway (or sized LB outbound rules); alert on SNAT port usage |
| On-prem clients hit PaaS publicly, bypassing private endpoint | DNS split-brain: on-prem resolver lacks privatelink forwarding | Conditional forwarders to Azure DNS; automate privatelink zone records |
| Attacker reaches App Gateway directly, skipping FD WAF | Backend accepts arbitrary sources | Allow `AzureFrontDoor.Backend` tag only + validate `X-Azure-FDID` header |
| Spoke VMs can't reach other spoke | Peering non-transitivity assumed otherwise | Hub NVA/gateway-transit forwarding + correct UDRs (and return-path symmetry) |
| Post-Basic-LB-migration everything blocked inbound | Standard SKU is secure-by-default (needs NSG allow) | Add explicit NSG rules as part of migration runbook |

---

## Tradeoffs & when NOT to use it

- **Front Door is overkill for single-region internal apps** — fixed monthly cost plus per-GB charges buy global anycast you don't use; App Gateway (or nothing, for internal-only) is the honest answer until multi-region is real. The reverse also holds: bolting AGW onto a Front Door design "for WAF" duplicates L7 hops when FD Premium's WAF suffices — two WAFs means two false-positive tuning surfaces.
- **Private endpoints aren't free simplicity** — each endpoint is hourly-plus-data-processing cost, DNS records must be managed as code, and hybrid DNS complexity scales with endpoint count. Service endpoints remain defensible for simple single-VNet cases where identity-based auth already limits exposure; the zero-trust default is still private endpoints.
- **NSGs are not firewalls.** No FQDN rules, no L7, no IDPS; teams that treat them as the complete perimeter story fail audits. Conversely, Azure Firewall for a 3-VM startup is cost and complexity theater — NSGs plus discipline suffice at small scale.
- **Don't put App Gateway in the hub as a shared resource** — CAF guidance treats it per-workload: shared gateways create RBAC coupling (every team sees whole config), limit-table exhaustion, and blast-radius sharing across unrelated apps.
- **Traffic Manager fails slow by design** — DNS TTLs mean minutes-level failover; anything latency-sensitive uses Front Door instead. TM survives only for non-HTTP steering or as belt-and-braces behind FD.
- **ExpressRoute isn't automatically better than VPN** — for modest bandwidth needs (<1 Gbps class) with bursty usage, S2S VPN's near-zero idle cost beats circuit pricing; ER earns its keep on predictable high-throughput private connectivity and compliance-mandated isolation.

---

## Interview questions

### Q1 — When do you choose Front Door versus Application Gateway? Give the decision factors, not definitions.
**Testing:** the core portfolio question; wants reasoning about scope and layer.
**Answer:** Decide by scope first: users/origins spanning regions → Front Door (anycast edge, cross-region failover, edge TLS/caching); single-region or internal → App Gateway. Then features: both do L7 routing and WAF; only FD caches and terminates at POPs; only AGW does deep regional integration (private backends without Private Link tier requirements). Cost shape differs: FD has monthly+GB charges that punish low-traffic internal apps; AGW is capacity-priced. Common production answer: FD → locked-down AGW when you need both global steering AND regional path-routing/WAF depth.
**Follow-up trap:** *"Why not always both?"* — two L7 layers double TLS handshakes, add hop latency, duplicate WAF tuning/false-positive surfaces, and complicate debugging; adopt the second layer only when a concrete requirement demands it.

### Q2 — Explain VNet peering transitivity and how spoke-to-spoke actually flows in hub-spoke.
**Testing:** the single most common networking misconception.
**Answer:** Peering connects exactly two VNets; routes don't propagate through peers — spoke A cannot reach spoke B via hub unless the hub forwards. Real flow: A→hub (peered), hub NVA/gateway routes to B (peered), requiring UDRs on A pointing spoke ranges at firewall/NVA and matching return routes — asymmetry here causes one-way failures. Gateway transit lets spokes use hub's VPN/ER gateways without owning their own.
**Follow-up trap:** *"Does Azure Firewall see everything automatically then?"* — only if UDRs force 0.0.0.0/0 and inter-spoke CIDRs to it, AND the firewall subnet allows forwarded traffic; default setup without explicit UDRs bypasses inspection silently.

### Q3 — Service endpoint vs private endpoint — what actually differs on the wire?
**Testing:** precision on a perpetually confused pair.
**Answer:** Service endpoint: traffic leaves your VM toward the PaaS *public* endpoint but rides an optimized Azure route carrying identity claims — the service sees your VNet/subnet identity and can allowlist it; source IP becomes the private IP; but the service still HAS a public presence and other protections depend on service-side config. Private endpoint: a NIC with a real private IP bound to ONE resource instance inside YOUR subnet; traffic never touches public space; access control collapses to network + resource IAM; requires privatelink DNS so names resolve privately.
**Follow-up trap:** *"Which prevents data exfiltration?"* — private endpoints with data-exfiltration protection policies; service endpoints don't stop a compromised VM from copying data to a different storage account's public endpoint since SEs are per-service not per-resource.

### Q4 — Design the lockdown making App Gateway reachable ONLY through Front Door.
**Testing:** practical defense-in-depth pattern knowledge.
**Answer:** Three layers: (1) AGW frontend allows inbound only from `AzureFrontDoor.Backend` service tag via NSG on its subnet; (2) validate `X-Azure-FDID` header equals your Front Door ID in a custom WAF/routing rule, dropping others; (3) optionally remove AGW public IP entirely using FD Premium Private Link origin, making the backend unreachable publicly at all. Verify with curl direct-to-AGW-IP expecting drop.
**Follow-up trap:** *"What breaks when Microsoft updates FD infrastructure?"* — service-tag-dependent rules update automatically (tags are maintained), but hard-coded CIDR allowlists rot silently; header validation covers gaps since it's ID-based, not IP-based.

### Q5 — Your scale set shows random outbound connection resets under load. Diagnose fully.
**Testing:** SNAT mechanics, the classic hidden failure.
**Answer:** Default outbound SNAT allocates ports per instance inversely to instance count (~1024 ports/small instances scaling up toward ~64k/large); every outbound connection holds a port for its lifetime. Scale-out SHRINKS per-instance allocation while SDK/API connection storms grow demand → exhaustion manifests as resets/hangs correlating with instance count and connection churn. Confirm via SNAT port-usage metrics/LB resource health. Fix permanently with NAT Gateway (dedicated ports, static IPs, zonal) or sized LB outbound rules; mitigate short-term with connection pooling/timeouts.
**Follow-up trap:** *"Why didn't this happen at half the fleet size?"* — allocation is per-instance-count-driven: doubling instances halved per-instance ports while aggregate connections roughly doubled — the math crosses the cliff non-linearly.

### Q6 — Walk through what happens, packet-wise, when an on-prem app calls a Key Vault with private endpoint enabled.
**Testing:** end-to-end hybrid DNS + private path fluency.
**Answer:** App resolves `vault.azure.net`: on-prem resolver conditional-forwards the privatelink zone to Azure DNS (or hosts synced records); answer returns the PE's private IP (e.g., 10.x.x.x). Packet routes via ExpressRoute/S2S into the hub/spoke VNet where the PE NIC sits; NSG on PE subnet gates sources; traffic reaches Key Vault front end privately, authorization via Entra token as usual. If forwarding is missing, resolver returns the PUBLIC IP — traffic egresses internet, possibly blocked by firewall, producing confusing intermittent auth/network errors depending on client location.
**Follow-up trap:** *"Which side usually breaks?"* — DNS, overwhelmingly: missing forwarders, stale A-records after PE recreation, split-brain where some resolvers answer publicly. Debug with nslookup FROM THE FAILING CLIENT'S vantage point.

### Q7 — Basic Load Balancer retired September 2025 — what changed functionally with Standard beyond deprecation?
**Testing:** currency on a completed migration wave.
**Answer:** Standard is zone-redundant by default, secure-by-default (inbound blocked absent NSG allow — Basic was open-by-default), adds SLA ~99.99%, HTTPS probes, HA Ports rule, outbound rules replacing ad-hoc NAT semantics, and diagnostics via multidimensional metrics. Migration gotchas: all associated public IPs must be Standard/static (dynamic Basic IPs get lost if disassociated carelessly), backend pools moved from NIC-association semantics toward IP-based pools, outbound connectivity stops working until explicitly configured.
**Follow-up trap:** *"Do retired Basic LBs stop working?"* — no, they run unsupported without SLA; risk is operational (no fixes, silent drift from supported configurations), which is why migration tooling pushed hard rather than hard cutover.

### Q8 — Design ingress for a 3-region web app with compliance-mandated WAF and private backends.
**Testing:** synthesis of FD + AGW + Private Link under constraints.
**Answer:** Front Door Premium with WAF policy (OWASP CRS + custom rules) globally; per-region origin groups pointing at Private Link-enabled App Gateways (or PLS-typed origins); AGW v2 zone-redundant doing path routing to AKS/CA backends via private endpoints, itself locked to FD via tag+FD-ID validation. Health probes tuned per region; FD priority/weight handles regional failover (active-active weights or active-passive priorities); certificates managed at edge (managed certs) plus AGW KV-backed certs internally. DNS apex via alias record to FD. Test regional kill: disable one region's origins, verify RTO seconds-class.
**Follow-up trap:** *"Session affinity across regions?"* — FD supports cookie-based affinity per origin group but cross-region stickiness fights failover; stateless designs or external session stores (Redis) beat affinity gymnastics.

### Q9 — How does WAF false-positive management work without weakening protection?
**Testing:** operational security maturity.
**Answer:** Start in prevention-with-monitoring: tune via exclusion rules scoped narrowly (specific headers/args/selectors) rather than disabling rule IDs broadly; use anomaly scoring mode's per-rule scores to identify offenders; custom rules for known-good patterns (API clients posting JSON-ish payloads trigger CRS SQLi rules — exclude request-body inspection selectively for authenticated API paths only). Never set mode to detection globally to "reduce noise." Log every block/exclusion decision; review monthly against attack patterns.
**Follow-up trap:** *"Business insists on disabling CRS entirely for their endpoint."* — offer compensating controls: strict schema validation at app layer, rate limiting custom rules, bot-manager-style checks, time-boxed exception with expiry — document accepted risk rather than silently hollowing the WAF.

### Q10 — When would you deliberately choose ExpressRoute over VPN, and when is that wasteful?
**Testing:** hybrid-connectivity economics honesty.
**Answer:** ER earns keep: sustained multi-Gbps private throughput, compliance requiring physical isolation from internet paths, latency-sensitive ERP/database replication where jitter matters, thousands of branches needing predictable routing (ER + SD-WAN). Wasteful: dev/test environments, sub-Gbps sporadic needs (S2S VPN costs near-nothing idle), short-lived projects where circuit provisioning lead-times (weeks) dwarf project timelines. Also consider P2S VPN for individual remote admin scenarios before building anything heavier.
**Follow-up trap:** *"FastPath?"* — bypasses the ER gateway data path directly to VMs' NICs for >high-Gbps circuits, cutting hop latency; requires specific circuit SKUs and topology support — worth naming to prove depth but rarely the deciding factor.

### Q11 — What visibility does each layer give during an incident, and which telemetry do you configure preemptively?
**Testing:** observability mapped to the stack they claim to design.
**Answer:** FD: access logs (front-end latency, cache status, WAF action, origin chosen), probe health metrics. AGW: access logs incl. backend-pool response, WAF logs with matched rules; connection metrics. LB: connection/SNAT metrics, health-probe states. Network Watcher: connection troubleshooter, effective-security-routes dumps, packet capture. Preemptive config: diagnostic settings streaming ALL of these to Log Analytics, Traffic Analytics on flow logs, alerts on FD 5xx-rate, AGW unhealthy-host-count, LB SNAT usage. The skill is knowing which layer OWNS a symptom: 502-at-edge vs timeout-at-L4 vs reset-at-host route to completely different fixes.
**Follow-up trap:** *"Where do you look FIRST for 'site is down'?"* — FD access logs: are requests arriving? Are origins marked healthy? Is WAF blocking? Edge logs triage in minutes what backend log-diving takes hours to find.

### Q12 — Argue the case AGAINST private-endpoint-everything, then give the counterargument.
**Testing:** steel-manning both directions on current orthodoxy.
**Answer:** Against PE-everything: hourly+data costs multiply across hundreds of resources; DNS records become critical-path infrastructure where one missing record breaks auth flows opaquely; hybrid forwarding complexity grows linearly; service endpoints + Entra-only auth + storage firewalls achieve most of the exposure reduction at fraction of ops cost. Counter: zero-trust posture eliminates entire exfiltration classes (public endpoints reachable from compromised anywhere), audit/compliance increasingly mandates private-only data paths, and the DNS pain is one-time IaC investment amortized forever; orgs regret public exposure incidents far more than DNS tickets. Verdict: PE-default for data services (SQL/Storage/KV), selective elsewhere, DNS-as-code mandatory either way.
**Follow-up trap:** *"How do you keep DNS from becoming the permanent incident source?"* — automate privatelink zone linking per VNet in landing-zone policy, sync records via Event Grid on PE creation, and synthetic-monitor resolution from every network segment continuously.

---

## Red flags that fail you

- Describing peering as transitive or drawing spoke-to-spoke arrows through hub without forwarding components.
- Confusing service endpoints with private endpoints ("both make it private").
- Recommending retired Basic Load Balancer or being unaware of the Sept 30, 2025 retirement.
- No mention of health-probe correctness when debugging edge 502s.
- Designing FD→AGW chains without the lock-down pattern (tag + X-Azure-FDID).
- Treating NSGs as sufficient enterprise perimeter (no FQDN/L7 awareness).
- Ignoring SNAT/port math in any scaled-out fleet discussion.
- Hand-managing DNS records outside IaC in hybrid estates.

---

## Cheat card

```
LAYER MAP: DNS=TrafficManager(global, TTL-slow) · L4=LoadBalancer(regional,
           ~99.99% SLA std) · L7-regional=AppGateway v2 · L7-global=FrontDoor
BASIC LB RETIRED 2025-09-30 -> Standard: zone-redundant, secure-BY-DEFAULT
           (needs NSG allow!), outbound rules explicit, static std IPs only
APPGW v2:  autoscale 0-~125 units · WAF OWASP CRS · path/host maps ·
           cookie affinity · deploy PER-WORKLOAD (not shared hub)
FRONT DOOR: anycast edge · TLS@edge · cache · WAF(Premium tiers) ·
           probes drive origin selection (bad probe path = mystery 502s)
           lock AGW: NSG allow AzureFrontDoor.Backend tag + check X-Azure-FDID
VNET:      subnet reserves 5 IPs · peering NON-TRANSITIVE (hub forwards via
           NVA/gw-transit + symmetric UDRs) · ASGs group roles not IPs
NSG:       stateful · priority 100-4096 lower wins · subnet AND NIC both apply
           NO FQDN/no L7 -> Azure Firewall for FQDN egress/IDPS/threat-intel
PRIVATE ENDPOINT: NIC w/ private IP per RESOURCE · needs privatelink DNS zones
           hybrid = conditional forwarders or split-brain · ~hourly+per-GB cost
           data-exfil protection ties PE->resource approval
SNAT:      default outbound ports scale INVERSELY w/ instances (~1024 small)
           exhaustion = random resets after scale-out -> NAT GATEWAY default
ER vs VPN: ER = private BGP, 1-10 Gbps class, FastPath bypasses gateway
           S2S VPN = IPsec internet, cheap idle, days-not-weeks to stand up
TELEMETRY: FD access logs · AGW unhealthy hosts · LB SNAT usage ·
           Traffic Analytics · debug order: edge logs -> probe state -> WAF
```

## Sources

- [Load balancing options — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/load-balancing-overview); accessed 2026-08-23
- [Upgrading from Basic Load Balancer — Microsoft Learn](https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-basic-upgrade-guidance); accessed 2026-08-23
- [Azure Load Balancer SKUs — Microsoft Learn](https://learn.microsoft.com/en-us/azure/load-balancer/skus); accessed 2026-08-23
- [Plan for application delivery — Cloud Adoption Framework](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/plan-for-app-delivery); accessed 2026-08-23
- [Secure application delivery patterns and design considerations — Microsoft Learn](https://learn.microsoft.com/en-us/azure/networking/secure-application-delivery); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
