# GCP Networking Deep: VPC, Shared VPC, Cloud Load Balancing, Cloud Armor, Interconnect

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2h · **Prereqs:** C-GCP-iam · **Updated:** 2026-08-23
> **Module id:** `C-GCP-networking` · **Tags:** networking,critical

## The 30-second version

A GCP VPC is a *global* resource spanning regions — subnets are the regional unit — and firewall rules attach to the VPC with tag/service-account targets rather than to subnets, which is the first mental-model correction everyone from AWS needs. **Shared VPC** splits ownership: a host project owns networks, service projects consume them, with `networkUser` IAM binding the two — the standard answer to multi-team IP chaos. The flagship load balancer is the global external Application LB: one **anycast VIP** announced from every Google front end (GFE), TLS terminated at the edge closest to the user, then carried over Google's backbone (Premium Tier's cold-potato routing) to your region; Standard Tier trades that for cheaper egress but loses anycast, global scope, and Cloud CDN eligibility. **Cloud Armor** sits on those same front ends as WAF/DDoS: preconfigured OWASP rules, rate-based bans, ML-driven Adaptive Protection, and since late 2025 hierarchical org/folder-level policies. Private connectivity to on-prem is **Dedicated Interconnect** (10/100 Gbps circuits) or Partner Interconnect, with HA VPN (two interfaces, two tunnels, 99.99% SLA) as the encrypted fallback. The interview core: can you explain what runs where — GFE at the edge, proxies, backends — and why firewall rules aren't subnet-scoped?

## Why this gets asked

Because networking mistakes are the expensive invisible ones: teams burn weeks debugging "why can't my service reach the database" that traces to Shared VPC IAM (`networkUser` missing on the service project), discover their "global" architecture silently degraded because someone picked Standard Tier for an external LB, or get surprised when a DDoS lands because Cloud Armor was attached to the wrong policy type (backend versus edge). Interviewers probe whether you understand GCP's actual traffic path — client → nearest GFE/PoP → backbone → regional proxy → backend — because capacity, security, and cost questions all resolve against that path. They also test cross-cloud literacy directly: AWS people assume per-subnet NACLs and regional VPCs; Azure people assume regional VNets; GCP breaks both assumptions deliberately.

---

## Lineage: past → present → future

**What came before.** Google's internal lineage is Jupiter (the datacenter fabric SDN paper, SIGCOMM 2015) and Andromeda (the network virtualization/control plane paper, NSDI 2014): software-defined overlays where load balancing, firewalls, and routing are programmed centrally rather than boxed into appliances. Public GCP networking launched with the classic model everyone else had — regional networks, hardware-ish semantics — then unified to global VPCs in 2014–2016 era precisely because Google's own fleet never treated geography as a network boundary. Early load balancing was either L3 passthrough (target-pool era) or the magic global HTTP LB whose GFE-fronting design predates comparable AWS offerings by years.

**Where it stands now.** The current stack is Envoy-flavored: the newer external/internal Application LBs are explicitly proxy-based (Envoy at GFEs or regionally), replacing the "classic" variants which Google has been migrating customers off (~). Cloud Armor matured from IP allowlists into a full WAF platform: preconfigured ModSecurity-derived rulesets covering OWASP Top 10, bot management with reCAPTCHA Enterprise integration, Adaptive Protection's per-endpoint ML baselines, and hierarchical organization/folder policies GA October 2025. Network Connectivity Center became the hub-and-spoke control plane tying VPN, Interconnect, and VPC spokes together. The live disagreement: hybrid connectivity economics — Dedicated Interconnect's fixed cost only beats HA VPN + NAT at sustained multi-Gbps volumes, and teams genuinely argue about the crossover point because Partner Interconnect pricing complicates it. [Google Cloud global external HTTPS LB deep dive](https://cloud.google.com/blog/topics/developers-practitioners/google-cloud-global-external-https-load-balancer-deep-dive); accessed 2026-08-23. [Cloud Armor WAF/DDoS cheat sheet](https://jayendrapatil.com/google-cloud-armor/); accessed 2026-08-23.

**Where it's heading.** High confidence: full migration from classic LBs to the managed-proxy generation, and continued absorption of network functions into software (Service Extensions let you run custom logic at LB edges via WASM/plugins now). High confidence: hierarchical/network-wide security policy expanding — org-level Armor policies and org-scoped address lists signal where firewall management is going. Medium confidence: deeper AI-assisted DDoS/WAF tuning (Adaptive Protection auto-deploy of suggested rules already exists in Enterprise). Speculative: true universal anycast L4 (global external passthrough NLB remains preview-stage ~); treat claims about globally load-balanced UDP/TCP passthrough at GA scale as unverified until documented.

---

## Mental model

The traffic path explains everything:

```
CLIENT (anywhere)
   │ DNS -> single anycast VIP
   ▼
NEAREST GFE / PoP  ──────────────►  TLS terminates here (edge cert)
   │ Cloud Armor evaluates HERE (before your backend pays anything)
   │ Cloud CDN caches HERE
   ▼
GOOGLE BACKBONE (Premium Tier: cold-potato -> ride private fiber)
   │                (Standard Tier: hot-potato -> exit public internet ASAP,
   ▼                 cheapest egress, no anycast/global features)
REGIONAL PROXY (Envoy) -> URL map / path routing / health checks
   ▼
BACKENDS: instance groups, NEG-zonal (VM IPs), NEG-serverless
          (Cloud Run/Functions endpoints), hybrid NEGs (on-prem)
```

And the VPC ownership picture:

```
ORGANIZATION
 └─ HOST PROJECT: owns VPC + subnets (regional!) + firewall rules
     ├─ SERVICE PROJECT A: VMs/Run/GKE attach to shared subnets
     │    └─ its SAs need roles/compute.networkUser on host subnets
     ├─ SERVICE PROJECT B: ...
     └─ Shared VPC admin attaches projects; network admins manage routes/firewall
```

Three corrections that unstick most candidates: (1) VPCs are global, so peering/VPC-to-VPC works across regions without VPN; (2) subnets are regional — an instance lives in a zone but its IP belongs to a regional subnet CIDR; (3) firewall rules live at VPC level with `targetTags`/`targetServiceAccounts`, not per-subnet like AWS NACLs.

## How it actually works

### VPC fundamentals, precisely

- **Subnets are regional CIDR blocks** (e.g., `10.0.0.0/20` in europe-west3). Primary range for instance IPs plus optional secondary ranges — secondary ranges are how GKE maps pods/services to native VPC addressing (alias IP ranges), a genuinely different design from AWS CNI overlays.
- **Routes** are VPC-global; system routes derive from subnets automatically. Custom routes with instance tags steer traffic (e.g., default route 0.0.0.0/0 → NAT or appliance).
- **Firewall rules**: stateful, allow-or-deny, ordered by priority (lowest number wins, 65534 implied deny-ingress / allow-egress defaults), targeting network tags (`web-server`) or service accounts, with source specified as ranges/tags/SAs. Logging per-rule with sampling.
- **VPC peering** connects VPCs privately across projects/orgs and regions; non-transitive by design (A↔B, B↔C does not imply A↔C) — needing transitivity is the signal to look at Network Connectivity Center hub-and-spoke instead.
- **Private Service Access / Private Google Access**: the two "no internet" patterns people conflate — PSA carves a subnet from your CIDR for managed services (Cloud SQL private IP); PGA lets VMs *without* external IPs reach Google APIs over Google's network.

### Shared VPC mechanics

One host project holds networks/subnets/firewalls; service projects host workloads attaching to those subnets. The wiring: an org-level Shared VPC admin enables the host project, attaches service projects, then grants `roles/compute.networkUser` on specific subnets (or the whole project) to the service project's principals, and `roles/compute.xpnAdmin`-adjacent rights handle attach operations. The classic failure: workload deployers in service project B can create instances but get PERMISSION_DENIED referencing the subnet — that's missing networkUser on the host side, and no amount of service-project IAM fixes it. GKE on Shared VPC adds another layer: cluster SA and node SA need networkUser on the subnets hosting pods/services.

### Cloud Load Balancing: pick by scope × protocol

| LB | Scope | Proxy? | Use |
|---|---|---|---|
| Global external Application LB | Global anycast VIP, Premium Tier | Envoy/GFE L7 | Public web/APIs, CDN, Armor |
| Regional external/internal Application LB | Regional | Envoy L7 | Internal APIs, regional exposure |
| External passthrough Network LB | Regional (global in preview ~) | No — passthrough L4 | UDP, preserved client IPs |
| Internal passthrough NLB | Regional | No — L4 | Internal TCP/UDP, DB frontends |

The global external ALB's superpower: one anycast IP announced worldwide; TLS at the nearest GFE; health-checked failover across regions in tens of seconds without DNS changes. Backends attach via backend services pointing at zonal NEGs (GCE_VM_IP_PORT), serverless NEGs (Cloud Run/Functions directly as backends), hybrid NEGs (on-prem endpoints), internet NEGs (external SaaS), or backend buckets (GCS via CDN). Cross-region capacity: balancing mode + capacity scaler per backend decide spill-over when a region saturates.

### Premium vs Standard Tier

Premium: traffic enters/exits at the PoP nearest the user and rides Google's private backbone (cold-potato) to your region — lowest latency, required for global LBs/CDN/BYOIP/global IPv6 (~$0.12/GB NA egress under 1TB ~). Standard: traffic exits at the region's internet peering closest to your resource (hot-potato) — cheaper (~$0.085/GB ~), regional-only features, higher and more variable latency for distant users. Tier is set per-resource or project-default; reserved IPs are tier-locked and cannot convert.

### Cloud Armor

Security policies attach to backend services (backend policies) or CDN/backend-bucket edges (edge policies). Rules: priority-ordered match expressions (CEL-based custom language), actions allow/deny(status)/throttle/rate-based-ban/redirect, with preview mode logging what *would* fire before enforcement. Building blocks:

- **Preconfigured WAF rules**: ModSecurity CRS-derived signature sets covering OWASP Top 10 (SQLi, XSS, LFI/RFI, RCE, scanner detection), individually sensitize-able to cut false positives.
- **Rate limiting**: keys by IP/header/cookie/JWT claims; throttle caps rate, rate-based ban blocks offenders for a configured interval after threshold breaches.
- **Adaptive Protection** (Enterprise): ML baselines per backend service detect anomalous traffic patterns, raise alerts (Standard tier) or full detection + suggested rules + auto-deploy option (Enterprise).
- **Enterprise** (formerly Managed Protection Plus): ~$3,000/month annual per billing account or $200/month paygo per project (~), bundling WAF usage, Threat Intelligence lists, advanced network DDoS protection, hierarchical org/folder policies (GA Oct 2025).
- Always-on L3/L4 volumetric DDoS absorption is inherent to sitting on Google's edge — you never see the flood; Armor fights the L7-shaped part.

### Hybrid connectivity

- **Dedicated Interconnect**: physical 10 or 100 Gbps circuits into a Google colo; pair them across availability domains for 99.99%-class SLA; VLAN attachments carve BGP sessions; private routing to VPCs without traversing the internet.
- **Partner Interconnect**: provider's fabric delivers equivalent logical connectivity at smaller increments (50 Mbps upward ~) — the answer when you don't have colo presence or need <10 Gbps granularity.
- **HA VPN**: IPsec over two tunnels on separate interfaces/regions for 99.99% SLA; the encrypted path where compliance demands it, and the sensible starting point before traffic justifies circuits.
- **Router/BGP** underlies all three; Network Connectivity Center organizes spokes/hubs for larger topologies.

## Build it from scratch

The pieces of a hardened public endpoint, minimal:

```bash
# 1. VPC + regional subnet with secondary ranges for GKE
gcloud compute networks create prod-vpc --subnet-mode=custom
gcloud compute networks subnets create app-eu --network=prod-vpc \
  --region=europe-west3 --range=10.10.0.0/20 \
  --secondary-range=pods=10.20.0.0/16,services=10.30.0.0/20

# 2. Least-privilege firewall: tag-targeted, source-scoped
gcloud compute firewall-rules create allow-https-to-web \
  --network=prod-vpc --allow=tcp:443 --target-tags=web --source-ranges=0.0.0.0/0
gcloud compute firewall-rules create deny-all-ingress-else \
  --network=prod-vpc --deny=all --priority=65500

# 3. Global anycast IP + managed TLS cert
gcloud compute addresses create web-vip --global --ip-version=IPV4
gcloud compute ssl-certificates create web-cert --domains=api.example.com

# 4. Armor policy: OWASP rules in preview, then enforce
gcloud compute security-policies create edge-policy
gcloud compute security-policies rules create 1000 --security-policy=edge-policy \
  --expression="evaluatePreconfiguredWaf('sqli-v33-stable')" --action=deny-403
```

And the Shared VPC IAM that actually makes it work:

```bash
# host project side - THIS is the grant people forget
gcloud projects add-iam-policy-binding HOST_PROJECT \
  --member=serviceAccount:deployer@svc-project.iam.gserviceaccount.com \
  --role=roles/compute.networkUser
```

A sizing sketch for hybrid bandwidth decisions:

```python
# untested sketch - Interconnect vs HA VPN monthly cost intuition
def interconnect_monthly(gbps_needed, circuits_10g_price=1750, vlan_price=0.05):
    circuits = -(-gbps_needed // 10)          # ceil to 10Gbps circuits (2 for HA)
    return 2 * circuits * circuits_10g_price # + VLAN attachment + egress

def ha_vpn_monthly(gbps_sustained, tunnel_overhead=1.04):
    return None   # tunnels cheap; the real cost is egress + CPU encrypting at VMs
# Rule of thumb: sustained >1-2 Gbps or latency-critical -> Dedicated;
# bursty/backup/small offices -> HA VPN; colo-less mid-size -> Partner.
```

## How it's done in production

Reference estate: one host project per environment holding Shared VPCs; service projects per team/domain attaching via networkUser grants; private-only workloads (no external IPs org-wide via org policy) reaching APIs through Private Google Access and egressing via Cloud NAT; public surface exclusively through global external ALB + Cloud CDN + Cloud Armor (preconfigured WAF enforced, custom rules previewed first); internal east-west traffic on internal ALBs; hybrid via redundant Partner/Dedicated Interconnects with HA VPN backup; everything flow-logged into VPC Flow Logs → BigQuery for reachability audits.

| Symptom | Cause | Fix |
|---|---|---|
| Service-project deploy fails referencing subnet | Missing `compute.networkUser` on host project subnet | Grant to deploying SA/group; check both cluster SA and node SA for GKE |
| "Global" LB behaves regionally, no CDN | Standard Tier forwarding rule | Global LBs require Premium; re-plan IPs (tier-locked) |
| DDoS/WAF rule blocking legit users | Overbroad preconfigured signature sensitivity | Sensitize rules, run preview mode first, tune per-path exclusions |
| Cross-region latency spikes between VMs | Assuming peering is transitive | Add direct peering/NCC hub for A↔C paths |
| On-prem can't reach private Cloud SQL | No Private Service Access range allocated | Allocate PSA range, enable private path on instance |
| NAT costs explode | Chatty egress through Cloud NAT per-instance | Route Google API traffic via PGA (free-ish), review retry storms |

## Tradeoffs & when NOT to use it

- **Shared VPC is not free simplicity** — it centralizes network ownership, which is exactly right for platform teams and exactly wrong for startups where every team deploying needs a ticket against the host project. Peering per-team VPCs is the looser alternative when autonomy beats consistency.
- **Don't use Cloud Armor as your only WAF story for non-HTTP protocols** — Armor rides proxy LBs; raw TCP/UDP passthrough endpoints get L3/L4 DDoS absorption and (Enterprise) advanced network protection, but not OWASP rule inspection.
- **Standard Tier saves egress money and costs you the global model** — no anycast VIP, no CDN on that path, higher tail latency for far users. Right for bulk regional transfer; wrong for user-facing global surfaces.
- **VPC peering's non-transitivity bites growing estates** — every new peering is O(n) manual work; past ~5-6 networks, hub-and-spoke via Network Connectivity Center or Shared VPC consolidation wins.
- **Dedicated Interconnect before traffic justifies it is waste** — fixed circuit costs run thousands monthly; start HA VPN, measure sustained Gbps, upgrade when the arithmetic says so.
- **When to skip Google's LB entirely:** single-region simple apps behind Cloud Run already have TLS/scaling built in; adding an external ALB buys URL maps/CDN/Armor — if you need none of those, don't pay the hop.

---

## Interview questions

### Q1 — Is a GCP VPC global or regional? What about subnets? Where do firewall rules attach?
**Testing:** the foundational mental-model check that trips AWS/Azure converts.
**Answer:** The VPC is global — one object spanning all regions. Subnets are regional CIDR blocks within it; instances draw IPs from their regional subnet regardless of zone. Firewall rules attach at the VPC level, stateful, priority-ordered, targeting instance tags or service accounts with source ranges/tags/SAs — there is no per-subnet NACL concept.
**Follow-up trap:** *"So how do I scope firewall access to one subnet?"* — you don't scope rules to subnets directly; compose: target tags/SAs identify destination instances, source ranges express origins (which may be a subnet CIDR). Design tags deliberately because they're your security boundary syntax.

### Q2 — Explain what happens, hop by hop, when a user in Tokyo hits api.example.com backed by VMs in us-central1 behind a global external ALB.
**Testing:** whether the GFE/backbone/proxy/backend path is real to them.
**Answer:** DNS returns the anycast VIP; Tokyo routes to the nearest GFE/PoP announcing it. The GFE terminates TLS with your managed cert (edge), evaluates Cloud Armor policy, checks Cloud CDN cache (miss assumed), then forwards over Google's private backbone (Premium cold-potato) to the regional Envoy proxy layer near us-central1, which applies URL map routing and health-check-selected backends, delivering to a VM IP in the zonal NEG. Response reverses the path. Failover: region health failing redirects new requests elsewhere without any DNS change — tens of seconds typically (~).
**Follow-up trap:** *"Where exactly does Armor run relative to CDN?"* — both at the edge/GFE layer; edge security policies can inspect before cache fill for CDN-enabled backends, backend policies guard post-cache misses. Ordering matters for cache poisoning defense.

### Q3 — Your team's service project can't deploy instances into the shared subnet. Debug.
**Testing:** Shared VPC IAM fluency — the most common real failure.
**Answer:** Shared VPC requires host-project grants even when service-project IAM looks perfect: the deploying principal (or SA) needs `roles/compute.networkUser` on the specific subnet or host project; GKE additionally needs it for the cluster and node SAs on pod/service subnets. Check who created the attachment (`xpnAdmin`), confirm subnet-level vs project-level grant scope, and read the exact PERMISSION_DENIED resource reference — it names the subnet.
**Follow-up trap:** *"Granting networkUser org-wide — problems?"* — it explodes blast radius: anyone with that role in any service project can consume any subnet. Scope grants per-subnet-per-service-project; treat host-project IAM as production-sensitive.

### Q4 — Premium vs Standard Tier: mechanics, costs, and three things Standard loses.
**Testing:** tier understanding beyond "one is cheaper."
**Answer:** Premium routes user traffic into the nearest PoP then across Google's backbone to your region (cold-potato, lowest latency); Standard exits into public internet at your region's peering (hot-potato, cheaper egress ~$0.085 vs ~$0.12/GB NA under-1TB ballpark ~). Standard loses: global anycast VIPs (global LBs require Premium), Cloud CDN eligibility, BYOIP announcements, global IPv6 forwarding rules (~). Tier binds at resource creation; IPs are tier-locked.
**Follow-up trap:** *"Does tier affect internal VM-to-VM traffic?"* — no; intra-VPC and Interconnect traffic always uses Google's network regardless of tier. Tier governs only paths touching the public internet.

### Q5 — Design DDoS/WAF protection for a public API: layers, tiers, rollout discipline.
**Testing:** Armor composition knowledge plus operational maturity.
**Answer:** Layers: inherent L3/L4 absorption by sitting on Google edge (always-on), Cloud Armor backend policy on the ALB with preconfigured OWASP rulesets (SQLi/XSS/LFI/RCE/scanners) sensitize-tuned, rate limiting keyed by IP+header/JWT claim with throttle then rate-based-ban escalation, Adaptive Protection (Enterprise) for L7 anomaly detection with suggested-rule auto-deploy option, reCAPTCHA bot management for login/signup flows. Rollout: every new rule starts preview mode, review logged would-deny matches for false positives, then enforce; hierarchical policies push baselines org-wide under Enterprise.
**Follow-up trap:** *"Attack targets a TCP passthrough NLB — does Armor help?"* — L7 Armor doesn't apply to passthrough; you get volumetric absorption inherently plus advanced network DDoS protection only under Enterprise enrollment. Knowing which policy type attaches to which endpoint class is the tested detail.

### Q6 — On-prem datacenter needs private connectivity: 800 Mbps steady now, 5+ Gbps in 18 months. Choose and justify.
**Testing:** hybrid economics reasoning.
**Answer:** Now: Partner Interconnect at 1 Gbps increment (or 2×500Mbps for redundancy ~) — no colo buildout, month-scale commitment. At sustained multi-Gbps with colo presence: Dedicated Interconnect pairs (2×10Gbps across availability domains for 99.99%-class SLA) beat Partner pricing at scale. HA VPN throughout as encrypted backup path. All BGP via Cloud Router; keep routes summarized to avoid churn.
**Follow-up trap:** *"Why not just HA VPN at 800 Mbps?"* — viable! Tunnels are cheap and 99.99% SLA exists; the honest tradeoff is IPsec overhead/CPU and throughput ceilings versus circuit cost. If compliance demands encryption-in-transit, VPN *is* the answer; Interconnect is plaintext private transport unless layered with VPN encryption.

### Q7 — Why is VPC peering non-transitive, and what do you do when you need transitivity?
**Testing:** topology literacy beyond feature lists.
**Answer:** Peering is point-to-point route exchange by design — A↔B exchanges A/B routes only, keeping routing domains composable and avoiding route-leak blast radios. Transitivity needs a router: Network Connectivity Center hub-and-spoke (the current answer), or pre-NCC patterns like custom routes via NVAs. Also note peering shares no IAM/admin boundary — each side administers its own network.
**Follow-up trap:** *"Peering vs Shared VPC for multi-team?"* — peering preserves full team autonomy at O(n²)-ish growth; Shared VPC centralizes subnets/firewalls with clean IAM delegation and zero peer-mesh. Platform-team maturity decides.

### Q8 — How do GKE pods get VPC-native addressing, and why does it matter?
**Testing:** alias-IP design comprehension.
**Answer:** Subnets carry secondary ranges (pods, services); GKE with VPC-native clustering allocates pod/service IPs from those alias ranges directly — every pod has an address routable inside the VPC, visible to flow logs, firewall rules, and peers without NAT/overlay indirection. Capacity planning shifts to CIDR math: /16 pods range supports ~4k nodes × 110 pods-ish (~); secondary ranges are immutable after node-pool creation choices, so undersized CIDRs become migrations.
**Follow-up trap:** *"Dataplane V2 changes this?"* — no: Dataplane V2 (eBPF-based networking/policy) changes enforcement and observability machinery, not addressing. VPC-native remains the substrate either way.

### Q9 — Private Service Access vs Private Google Access — distinguish precisely.
**Testing:** the two "no-internet" patterns people conflate constantly.
**Answer:** Private Google Access lets VMs *without external IPs* reach Google APIs/services (storage.googleapis.com etc.) over Google's network — it's about consuming Google's API surface privately. Private Service Access allocates a dedicated CIDR range (via service networking API peering) so managed services *with private IPs*, like Cloud SQL/AlloyDB/Memorystore, live inside your network's address space reachable over private paths.
**Follow-up trap:** *"Do you need PSA for PGA?"* — no, independent features. A VM can hit Cloud Storage privately (PGA) while Cloud SQL sits on PSA-assigned private IP; both coexist on the same subnet.

### Q10 — An attacker floods your HTTP API with 2M rps of valid-looking GETs. Walk through detection and response.
**Testing:** incident-shaped application of the Armor stack.
**Answer:** Inherent edge absorption handles volumetric component; the L7 shape needs Armor: Adaptive Protection flags the anomalous pattern against baseline and suggests a rule (Enterprise auto-deploy optional — review first). Identify discriminators from request logs (header absence, URI distribution, geo/IP concentration): apply rate-based bans on those keys, throttle legitimate-shared-signature traffic, geo-block if attack geography excludes customers. Preview first even mid-incident (minutes of logging), then enforce; watch backend saturation during analysis since valid-shaped traffic still consumes backends until blocked at edge.
**Follow-up trap:** *"Attack comes from residential proxies with perfect headers."* — then IP/rate signatures weaken: lean on behavioral signals (session/token validation via reCAPTCHA Enterprise bot scores, per-account rate limits, cache-first serving for anonymous GETs). Honest answer includes "this becomes a business-layer problem too," not pure network heroics.

### Q11 — When would you deliberately NOT put a load balancer in front of something?
**Testing:** judgment against reflexive architecture.
**Answer:** Direct-to-backend cases: gRPC microservices inside a mesh using client-side balancing; long-lived WebSocket servers needing sticky affinity where LB session-affinity is best-effort anyway (design reconnect instead); batch/queue consumers pulling from Pub/Sub rather than being pushed to; single-region internal tools where Cloud Run's built-in endpoint suffices. Each skips a paid hop whose features go unused.
**Follow-up trap:** *"WebSockets behind global ALB — actually supported?"* — yes, with caveats worth stating: idle timeout defaults (~10 min region-dependent ~) force keepalives, session affinity is best-effort not guaranteed, so protocol must tolerate instance loss regardless.

## Red flags that fail you

- Treating VPCs as regional or firewall rules as per-subnet (AWS/Azure mental-model leakage).
- Not knowing Shared VPC requires `networkUser` grants on the host project side.
- Claiming Standard Tier supports global anycast LBs or Cloud CDN.
- Describing VPC peering as transitive.
- Confusing Private Google Access with Private Service Access.
- Attaching L7 Armor policies to passthrough NLBs and expecting WAF inspection.
- Recommending Dedicated Interconnect for sub-Gbps workloads without pricing the circuits.

---

## Cheat card

```
VPC:      GLOBAL object; subnets REGIONAL CIDRs (+secondary ranges for GKE
          alias IPs); routes VPC-global; firewall VPC-level, stateful,
          priority low-wins, target tags/service accounts; implied deny-ingress
          priority 65534. Peering non-transitive. NCC = hub-and-spoke answer.

SHARED VPC: host project owns network; service projects attach workloads;
          service principals need roles/compute.networkUser on host subnets;
          GKE needs it for cluster+node SAs too. xpnAdmin attaches projects.

GLOBAL EXTERNAL ALB: anycast VIP at every GFE/PoP -> TLS edge ->
          Cloud Armor -> Cloud CDN -> backbone (Premium cold-potato) ->
          regional Envoy -> URL map -> backends (zonal/serverless/hybrid NEGs)
          cross-region failover in seconds w/o DNS changes.
LB MATRIX: global ext App (L7 proxy) | regional ext/int App | passthrough NLB
          (L4, client IP preserved) | internal passthrough.

TIERS:    Premium = anycast + backbone + CDN + BYOIP (~$0.12/GB NA egress ~)
          Standard = hot-potato regional egress cheaper (~$0.085/GB ~),
          NO global LB/CDN/anycast. Tier locked into reserved IPs.

ARMOR:    backend policies on ALB backends; EDGE policies for CDN/buckets.
          preconfigured OWASP WAF sets (ModSecurity CRS), sensitize to tune,
          preview mode first. rate limiting: throttle / rate-based-ban keyed
          IP/header/JWT. Adaptive Protection: ML L7 anomaly (Std=alert,
          Ent=full+suggest+auto-deploy). Enterprise ex-MPP: ~$3k/mo annual
          or ~$200/mo paygo (~). Hierarchical org/folder policies GA Oct 2025.
          L3/L4 floods absorbed by Google edge inherently.

HYBRID:   Dedicated Interconnect 10/100Gbps circuits (pair for 99.99% SLA);
          Partner Interconnect from ~50Mbps increments (~);
          HA VPN 2 tunnels/interfaces 99.99% SLA encrypted.
          PGA = VMs w/o external IP reach Google APIs privately.
          PSA = dedicated CIDR peered for private-IP managed services.
```

## Sources

- [Google Cloud Global External HTTP(S) Load Balancer deep dive — Google Cloud blog](https://cloud.google.com/blog/topics/developers-practitioners/google-cloud-global-external-https-load-balancer-deep-dive); accessed 2026-08-23
- [External Application Load Balancer overview — Cloud Load Balancing docs](https://docs.cloud.google.com/load-balancing/docs/https); accessed 2026-08-23
- [Cloud Armor WAF, DDoS protection and rate limiting reference](https://jayendrapatil.com/google-cloud-armor/); accessed 2026-08-23
- [Network Service Tiers: Premium vs Standard — examlab PCNE notes](https://examlab.net/en/certs/gcp/pcne/topics/pcne-network-service-tiers); accessed 2026-08-23
- [Cloud Load Balancing overview — Google Cloud docs](https://docs.cloud.google.com/load-balancing/docs/load-balancing-overview); accessed 2026-08-23
- [GCP global load balancing: anycast and failover explained](https://cloudwebschool.com/docs/gcp/networking/global-load-balancing/); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
