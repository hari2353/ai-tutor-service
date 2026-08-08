# VPC, Shared VPC, Cloud Load Balancing, Cloud Armor, Interconnect

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.0h · **Prereqs:** `C-GCP-iam`, `C-GCP-compute` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-networking` · **Tags:** networking

## The 30-second version

The one fact that reorganizes everything else in this module: **a GCP VPC is a global resource**. One VPC has subnets in every region you choose, with no peering, no transit gateway, and no cross-region route propagation required to reach another subnet in the same VPC — traffic between a subnet in `us-central1` and one in `europe-west1` in the same VPC just routes, over Google's private backbone, by default. AWS and Azure virtual networks are regional; a multi-region AWS design needs VPC peering or Transit Gateway plus route tables per region to get the same reachability GCP gives for free inside one VPC. **Shared VPC** lets one host project own the network while multiple service projects attach and deploy resources into it — GCP's answer to "one network, many teams" without full VPC peering mesh complexity. **Cloud Load Balancing**'s external Application/proxy Network load balancers are **global anycast**: one IP address, announced from every Google PoP simultaneously, with traffic entering the network at the PoP closest to the user and riding Google's backbone to the nearest healthy backend — a fundamentally different architecture from AWS ALB/NLB, which are always regional and need Route 53 latency routing plus Global Accelerator to approximate the same effect. **Cloud Armor** is the WAF/DDoS layer sitting in front of those load balancers, priced per-rule (~$1/rule/month) with a separate Enterprise tier (~$3k/month) for Adaptive Protection and DDoS billing insurance. **Private Service Connect** is the modern replacement for VPC Service Controls-adjacent private connectivity patterns, giving private, non-peered access to a published service (yours or a third party's) via an internal IP in your own VPC. **Cloud Interconnect** (Dedicated 10/100Gbps ports, Partner for sub-10Gbps or third-party colocation) is the hybrid-connectivity answer, roughly Direct Connect/ExpressRoute-shaped. The multi-region design implication of VPC being global is the favorite question in this whole track: it changes whether you need transit infrastructure at all for typical multi-region GCP topologies.

## Why this gets asked

The interviewer has watched an AWS-native engineer draw a GCP architecture diagram with VPC peering connections between regions that didn't need to exist, has debugged a Shared VPC IAM misconfiguration where a service-project owner couldn't create a VM because `compute.networkUser` wasn't granted on the right subnet, and has explained to a customer why their global load balancer's single anycast IP was actually the fix for the multi-region failover problem they were trying to solve with DNS. They want to see whether "global VPC" is understood as an architectural consequence (fewer moving parts, different failure domains) rather than a trivia fact.

---

## Lineage: past → present → future

**What came before.** GCP's original (2012-era) networking model was **legacy networks**: flat, single global broadcast domain, no subnets, no regional structure at all — closer to a single giant flat L2-ish network than anything resembling AWS's VPC-per-region model. The pain: no meaningful segmentation, no per-region IP planning, and it didn't scale operationally as GCP added regions. AWS, born with EC2-Classic and then VPC (2009-2011), went the opposite direction from day one: strictly regional networks, requiring explicit peering or (much later, 2019) Transit Gateway to connect them, which became the standard hub-and-spoke pattern for multi-region and multi-account AWS topologies.

**Where it stands now.** GCP replaced legacy networks with the current **VPC model** (2016-2017 era, alongside the resource-hierarchy launch covered in `C-GCP-iam`): a VPC is explicitly a **global resource** that contains regional **subnets**, and routes/firewall rules apply network-wide by default unless scoped otherwise. [VPC networks overview — Google Cloud Docs](https://cloud.google.com/vpc/docs/vpc) — accessed 2026-08-08. This means two subnets in the same VPC in different regions are reachable from each other over Google's backbone with zero additional configuration — no peering connection, no route table entry, no transit gateway. **Shared VPC** (host project owns the network, service projects attach and deploy resources into shared subnets) is GCP's multi-team answer, governed by IAM roles (`compute.networkUser` at minimum) rather than a separate peering/routing construct. **Cloud Load Balancing**'s global tier (external Application Load Balancer, external proxy Network Load Balancer) uses a single **global anycast IP** — Google's edge network announces the same IP from every point of presence, and Google's software-defined edge picks the nearest healthy backend, which is architecturally closer to how Cloudflare or a CDN routes than to how a regional ALB works. [Choose a load balancer — Google Cloud Docs](https://docs.cloud.google.com/load-balancing/docs/choosing-load-balancer) — accessed 2026-08-08. **Private Service Connect** (GA 2021, expanded through 2024-2026 to cover more Google API surface and third-party SaaS publishing patterns) is the current recommended mechanism for private connectivity to both Google APIs and arbitrary published services, superseding older patterns like VPC peering to Google-managed services for many use cases.

**Where it's heading.** Private Service Connect continues absorbing more connectivity patterns — including private endpoints for Vertex AI online prediction (covered in `C-GCP-ai`) — moderate-to-high confidence this becomes the default private-connectivity primitive across GCP services rather than a networking-specific feature. **Cross-Cloud Interconnect** (direct, Google-provisioned links to AWS and Azure without a third-party colocation partner) is the newer hybrid/multi-cloud connectivity story, competing directly with AWS's own 2026 multicloud interconnect offerings — moderate confidence this becomes standard for serious multi-cloud shops given both hyperscalers are now building toward each other directly rather than only through neutral colocation. Cloud Armor's Adaptive Protection (ML-driven anomaly detection for L7 DDoS) is trending toward being bundled more aggressively into the Enterprise tier's default posture — moderate confidence, worth a pricing-page check near interview time since WAF/DDoS pricing shifts often.

---

## Mental model

```
GCP: ONE VPC = GLOBAL, subnets are REGIONAL, backbone-routed by default
┌──────────────────────── VPC (global resource) ─────────────────────────┐
│  subnet us-central1    subnet europe-west1    subnet asia-southeast1   │
│  10.0.1.0/24           10.0.2.0/24            10.0.3.0/24              │
│      │                      │                       │                  │
│      └──────────── Google's private backbone ───────┘                  │
│           (reachable with ZERO peering/transit config)                 │
└──────────────────────────────────────────────────────────────────────┘

AWS/Azure: EACH VPC/VNet = REGIONAL, cross-region needs explicit plumbing
┌── VPC us-east-1 ──┐        ┌── VPC eu-west-1 ──┐
│  10.0.1.0/24      │◄──────►│  10.0.2.0/24      │   Peering / Transit
└───────────────────┘  needs └───────────────────┘   Gateway required,
                        explicit                       per pair or hub

SHARED VPC: one HOST project owns the network, N SERVICE projects attach
  HOST PROJECT (network-admin owns subnets, firewall, routes)
    │  compute.networkUser granted per service project / subnet
    ├── SERVICE PROJECT A (deploys VMs INTO host's subnets)
    ├── SERVICE PROJECT B (deploys VMs INTO host's subnets)
    └── SERVICE PROJECT C
  (closer to AWS's "shared VPC via RAM" than to a peering mesh)

CLOUD LOAD BALANCING: GLOBAL ANYCAST vs REGIONAL
  GLOBAL (ext. Application LB / proxy Network LB):
    ONE anycast IP, announced from every Google PoP simultaneously.
    User → nearest PoP (short hop) → Google backbone → nearest healthy
    backend (any region). No DNS-based geo-routing needed for failover.
  REGIONAL (internal LBs, regional external NLB):
    IP + forwarding rule scoped to ONE region; backends must be in
    that region.
```

---

## How it actually works

### VPC — global by default, and why that changes design

A VPC network itself has no IP range; **subnets** do, and subnets are strictly regional. Auto-mode VPCs create one subnet per region automatically (convenient for quick starts, usually wrong for production IP planning); custom-mode VPCs start empty and require deliberate subnet creation, which is the production default. Because the VPC is global, **firewall rules and routes are network-scoped by default** — a firewall rule created without a target scope applies to every instance in the VPC, in every region, unless explicitly scoped with target tags or service accounts. This is the exact opposite of the AWS mental model where a security group is inherently tied to instances within one VPC's region, and it's the single most common source of an over-permissive firewall rule when an AWS engineer writes GCP firewall rules for the first time assuming regional scoping that doesn't exist. **VPC Network Peering** still exists (for connecting two *separate* VPCs, e.g., across organizations or projects that aren't using Shared VPC) but is fundamentally optional infrastructure for cross-region reachability *within* a single organization's design — most GCP multi-region topologies need zero peering because they just use subnets of the same VPC.

### Shared VPC — one network, many teams

The **host project** owns the VPC, its subnets, routes, and firewall rules. **Service projects** attach to the host and deploy compute/GKE/serverless resources *into* the host's subnets, without owning any networking resources themselves. Attachment and per-subnet access are both IAM-governed: a service-project user needs `roles/compute.networkUser` (or a custom role with `compute.subnetworks.use` and related permissions) granted either project-wide on the host or scoped to specific subnets — the classic "service project can create a VM in this subnet but not that one" pattern for isolating, say, a data-science team's subnet from a production-services team's subnet within one shared network. This is architecturally closer to AWS's newer VPC-sharing-via-Resource-Access-Manager (RAM) pattern than to VPC peering — the network is one resource with delegated usage rights, not multiple networks stitched together.

### Cloud Load Balancing — global anycast vs. regional, mechanically

The **global external Application Load Balancer** (the modern name for what used to be called the HTTP(S) load balancer) provisions a single **global forwarding rule** bound to a **global anycast IP address**. Google's edge announces that same IP from every point of presence worldwide via BGP anycast — a user's request enters Google's network at the nearest PoP and then travels over Google's private backbone (Premium Tier networking, required for global LBs) to whichever backend, in whichever region, is closest and healthy. [Global External Application Load Balancer deep dive — Google Cloud Blog](https://cloud.google.com/blog/topics/developers-practitioners/google-cloud-global-external-https-load-balancer-deep-dive) — accessed 2026-08-08. This gives automatic geographic routing and near-instant regional failover (health-checked backends removed from rotation without any DNS TTL to wait out) as a structural property of the load balancer, not a feature bolted on with Route 53 latency-based routing and a Global Accelerator subscription the way AWS achieves the same outcome. **Regional** load balancers (internal Application/proxy/passthrough LBs, and the regional variant of the external LB) have an IP and forwarding rule scoped to one region, with backends required to be in that region — the right choice for data-residency-constrained workloads, active-passive DR designs needing explicit regional control, or simply when all traffic genuinely originates from one geography and global anycast's cost premium isn't worth paying.

### Cloud Armor — WAF and DDoS in front of the LB

Cloud Armor attaches to backend services behind an external Application Load Balancer (global or regional) and evaluates security policies — preconfigured WAF rules (OWASP-based), custom rules (CEL-expression match conditions), and **rate limiting** (throttle or ban a client by request volume per configurable time window, the standard defense against brute-force and "denial of wallet" scenarios). [Rate limiting overview — Google Cloud Armor Docs](https://docs.cloud.google.com/armor/docs/rate-limiting-overview) — accessed 2026-08-08. Pricing is roughly **$1 per rule per month** on the Standard (pay-as-you-go) tier, with an **Enterprise tier** around **$3,000/month** adding **Adaptive Protection** (ML-based anomaly detection tuned to the specific backend's traffic baseline) and **DDoS bill protection** (credits covering the cost spike a volumetric attack would otherwise generate). [Google Cloud Armor pricing — Pump.co](https://www.pump.co/blog/google-cloud-armor/) — accessed 2026-08-08. Cloud Armor is GCP's closest AWS WAF analog but sits natively at Google's edge in front of the global anycast IP, which means a volumetric L3/L4 attack against a global LB is absorbed across Google's entire edge network rather than concentrated at one region's ingress point — a structural DDoS-resilience advantage that comes from the same global-anycast architecture, not a separate feature.

### Private Service Connect — private access without peering

PSC lets a consumer VPC reach a published service (a Google API, another team's internal service, or a third-party SaaS vendor's service) via an **internal IP address inside the consumer's own VPC**, without VPC peering, without the service being exposed to the public internet, and without the producer and consumer networks needing overlapping-IP-avoidance coordination the way peering requires. A **service attachment** on the producer side is published; the consumer creates a **PSC endpoint** (a forwarding rule pointing at the service attachment) inside their own subnet. Consumer accept lists on the producer side can cap the total number of endpoint/backend connections accepted from a given consumer project or network — endpoint-based accept lists specifically don't support per-endpoint connection limits, since only one endpoint matches a given URI. [Private Service Connect security — Google Cloud Docs](https://docs.cloud.google.com/vpc/docs/private-service-connect-security) — accessed 2026-08-08. There's no PSC-imposed bandwidth ceiling beyond whatever the source/destination VM interfaces themselves support. PSC is the direct analog to AWS PrivateLink and Azure Private Link, and the same "publish once, many consumers attach privately" pattern applies across all three.

### Cloud Interconnect — hybrid connectivity

**Dedicated Interconnect** provisions a direct physical circuit into a Google colocation facility at **10Gbps or 100Gbps** port speed, with VLAN attachments (individual logical connections carved out of that physical port) configurable from 50Mbps up to 50Gbps each. **Partner Interconnect** goes through a supported service provider for sub-10Gbps needs or when a direct colocation presence isn't practical, billed on capacity plus egress. **Cross-Cloud Interconnect** is the newer direct-to-other-hyperscaler option (Google-provisioned links straight to AWS/Azure infrastructure, no third-party colocation partner needed), competing with the "cross-cloud direct connect" offerings other hyperscalers have started shipping in the same period. [Cloud Interconnect pricing — Google Cloud](https://cloud.google.com/network-connectivity/docs/interconnect/pricing) — accessed 2026-08-08.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| VPC (regional) | VNet (regional) | **VPC (global)** | GCP needs zero peering/transit for cross-region reachability within one VPC — AWS/Azure always need explicit cross-region plumbing |
| VPC Sharing (RAM) | — | **Shared VPC** | Same "one network, many teams" goal; GCP's is IAM-governed subnet-level delegation |
| ALB / NLB (regional) + Route 53 + Global Accelerator | Application Gateway / Front Door | **Cloud Load Balancing (global anycast)** | GCP gives global anycast as the LB's native architecture, not a bolted-on multi-service combination |
| AWS WAF | Front Door WAF | Cloud Armor | Cloud Armor's edge placement inherits the global-anycast DDoS-absorption property |
| PrivateLink | Private Link | Private Service Connect | Conceptually identical publish/consume model across all three |
| Direct Connect | ExpressRoute | Cloud Interconnect | Port speeds and partner-vs-dedicated split are broadly analogous |

---

## Build it from scratch

Minimal demonstration of the "no peering needed" property and a Shared VPC IAM grant, matching `labs/gcloud/05-networking/`:

```bash
# untested sketch -- one VPC, two regional subnets, reachable with zero
# peering config because the VPC itself is a global resource
gcloud compute networks create prod-vpc --subnet-mode=custom

gcloud compute networks subnets create prod-us \
  --network=prod-vpc --region=us-central1 --range=10.0.1.0/24

gcloud compute networks subnets create prod-eu \
  --network=prod-vpc --region=europe-west1 --range=10.0.2.0/24

# A VM in prod-us and a VM in prod-eu can reach each other over Google's
# backbone right now -- no peering connection, no route table entry,
# no transit gateway. Only a firewall rule (network-scoped by default)
# could block this.
gcloud compute firewall-rules create allow-internal \
  --network=prod-vpc --direction=INGRESS \
  --source-ranges=10.0.0.0/16 --allow=tcp,udp,icmp

# Shared VPC: host project exposes a subnet to a service project
gcloud compute shared-vpc enable HOST_PROJECT_ID

gcloud compute shared-vpc associated-projects add SERVICE_PROJECT_ID \
  --host-project=HOST_PROJECT_ID

# Grant the service project's default compute service account (or a
# specific group) the ability to USE (not own) a specific host subnet
gcloud projects add-iam-policy-binding HOST_PROJECT_ID \
  --member="serviceAccount:SERVICE_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/compute.networkUser" \
  --condition=None
```

---

## How it's done in production

A typical GCP multi-region deployment: **one VPC per environment** (prod, staging, dev — not one VPC per region), with regional subnets sized for that region's workload and firewall rules scoped with target tags/service accounts rather than left network-wide. **Shared VPC** with a platform team owning the host project and product teams as service projects, each granted `compute.networkUser` scoped to their specific subnet(s) only — never project-wide on the host unless the team genuinely needs cross-subnet access. **Global external Application Load Balancer** as the default internet-facing entry point for anything multi-region, giving automatic nearest-PoP routing and instant health-check-driven failover without DNS dependency; regional LBs reserved for genuinely single-region or data-residency-constrained services. **Cloud Armor** on every internet-facing backend service at minimum with rate limiting and preconfigured WAF rules; Enterprise tier reserved for services with real DDoS exposure history or compliance requirements around Adaptive Protection. **Private Service Connect** for any cross-team or cross-org service consumption that shouldn't touch the public internet or require IP-overlap coordination. **Cloud Interconnect** (Partner for most workloads, Dedicated only once sustained bandwidth genuinely justifies a 10/100Gbps port) for hybrid connectivity to on-prem.

| Symptom | Cause | Fix |
|---|---|---|
| A firewall rule intended for one region's instances is blocking/allowing traffic in every region | Firewall rules are VPC-scoped (global) by default, not region-scoped — no target tag/service account filter was applied | Add explicit target tags or target service accounts to scope the rule to the intended instances only |
| Service project engineer can't create a VM, gets a permission error referencing the host project's subnet | Missing `compute.networkUser` (or equivalent custom role) grant on the specific subnet or host project for that principal | Grant `roles/compute.networkUser` scoped to the specific subnet (preferred) or the host project |
| Global external Application Load Balancer traffic isn't reaching the nearest region despite healthy backends there | Backend service/health check misconfiguration causing that region's backends to be marked unhealthy, or Premium Tier networking not enabled (falls back to different routing behavior) | Verify health check status per backend, confirm Premium Tier networking is active on the LB |
| Cross-region latency inside one VPC is higher than expected despite "global VPC, no peering needed" | Traffic path or backend selection issue (e.g., internal LB scoped to wrong region, route misconfiguration), not actually a VPC-global limitation | Trace actual packet path; global-VPC reachability doesn't mean zero-latency — physical distance and backbone routing still apply |
| Cloud Armor rate limiting isn't blocking an obvious abuse pattern | Rate limit rule's match condition or threshold doesn't actually match the abusive traffic's characteristics (e.g., rotating source IPs defeating a per-IP threshold) | Layer Adaptive Protection (Enterprise tier) for anomaly-based detection instead of relying solely on static per-IP thresholds |
| PSC endpoint creation fails with a connection-limit error | Producer's consumer accept list connection limit reached for that consumer project/network | Request a higher limit from the service producer, or reduce the number of concurrent endpoint/backend connections from that consumer |

---

## Tradeoffs & when NOT to use it

- **Don't build VPC peering or Shared VPC infrastructure "for multi-region" reflexively.** If all the resources belong to one org/environment, they likely just need to be subnets of the same VPC — peering is for connecting genuinely separate VPCs (different orgs, different Shared VPC hosts), not a default multi-region pattern.
- **Don't leave firewall rules unscoped in a multi-team VPC.** The global-by-default scoping that makes cross-region reachability easy is exactly what makes an unscoped firewall rule dangerous — always use target tags or service accounts once more than one team shares a VPC.
- **Don't default to the global external Application Load Balancer for a single-region, latency-insensitive internal service.** It costs more than a regional LB and the anycast/global-failover benefits are wasted on a workload that was never going multi-region.
- **Don't rely on Cloud Armor's Standard tier alone for a service with real DDoS exposure history.** Static per-IP rate limiting is defeated by botnets and rotating IPs; that's specifically what Adaptive Protection (Enterprise tier) exists to catch.
- **Don't reach for Dedicated Interconnect before validating sustained bandwidth need.** The 10/100Gbps port commitment and colocation requirement are real fixed costs; Partner Interconnect covers most workloads below that threshold more cheaply and with faster provisioning.
- **Don't assume Private Service Connect eliminates all IP-planning work.** The PSC endpoint still consumes an IP in the consumer's subnet, and connection-limit accept lists on the producer side are a real constraint at high consumer counts — validate scale requirements against documented limits before assuming PSC scales infinitely for free.

---

## Interview questions

### Q1 — Explain why GCP VPCs are global and what that changes about multi-region design compared to AWS.
**Testing:** the single most-probed fact in this module.
**Answer:** A GCP VPC is a global resource; its subnets are regional, but the VPC itself spans every region you choose, with routes and (by default) firewall rules applying network-wide. Two subnets in different regions within the same VPC are reachable over Google's backbone with zero additional configuration — no peering, no transit gateway. AWS and Azure virtual networks are strictly regional, so multi-region reachability always requires explicit plumbing (VPC peering, Transit Gateway, or VNet peering/vWAN). The design consequence: a GCP multi-region topology within one org typically needs one VPC with multiple regional subnets, not N regional VPCs stitched together.
**Follow-up trap:** *"Does that mean GCP has no use for VPC Network Peering at all?"* — no; peering is still necessary for connecting genuinely separate VPCs (different Shared VPC hosts, different organizations, M&A integration scenarios) — the point isn't that peering is obsolete, it's that peering isn't required for ordinary multi-region reachability within a single org's network the way it is on AWS/Azure.

### Q2 — A firewall rule meant to allow SSH only to bastion hosts in `us-central1` is unexpectedly allowing SSH to instances in `europe-west1` too. Diagnose.
**Testing:** the practical consequence of global-by-default firewall scoping.
**Answer:** GCP firewall rules are scoped to the VPC (a global resource) by default — without an explicit target (tags, service accounts, or a specific subnet-level scope), a rule applies to every matching instance in the entire VPC, in every region. The fix is adding a target tag or target service account matching only the intended bastion instances, not relying on any implicit regional scoping, because none exists.
**Follow-up trap:** *"If I want a rule that only applies within one region, is there a native region-scoped firewall construct?"* — firewall rules don't have a native region-scope filter directly; the correct approach is to scope by target tag/service account applied only to instances in that region, or use hierarchical firewall policies at the folder/project level combined with careful tagging — there's no first-class "region" field on a VPC firewall rule the way there might be an expectation of one coming from a regional-network mental model.

### Q3 — Design the Shared VPC IAM structure for a platform team hosting network infrastructure for three product teams that must not see each other's subnets' traffic.
**Testing:** applied IAM + Shared VPC design, not just definitions.
**Answer:** One host project owned by the platform team, with one subnet per product team (or per environment per team). Each product team's principals get `roles/compute.networkUser` scoped specifically to their own subnet(s) — not project-wide on the host — via IAM conditions or subnet-level IAM bindings. Firewall rules are scoped with target tags/service accounts per team so cross-team traffic is denied by default, since network-wide default-scoped rules would otherwise let every team's instances reach every other team's instances (the VPC-is-global trap applied to a multi-tenant scenario).
**Follow-up trap:** *"If two teams' subnets are in the same VPC, is any network-level isolation possible without separate VPCs?"* — yes, via firewall rules scoped to specific tags/service accounts denying inter-team traffic by default (deny-by-default plus explicit allow rules for legitimate cross-team paths), but this requires deliberate rule design — the platform doesn't isolate subnets from each other automatically just because they're logically assigned to different teams.

### Q4 — Compare the global external Application Load Balancer's anycast model to how AWS achieves comparable global routing and failover.
**Testing:** cross-cloud precision on a favorite question.
**Answer:** GCP's global LB uses one anycast IP announced from every Google PoP; routing to the nearest healthy backend is a structural property of the load balancer itself, with failover driven by health checks with no DNS TTL dependency. AWS has no native global-anycast Application/Network Load Balancer — ALB/NLB are always regional — so equivalent behavior requires combining Route 53 latency-based or geolocation routing (DNS-level, subject to TTL/caching delays) with AWS Global Accelerator (which does provide anycast IPs and Google-backbone-like routing over AWS's network) sitting in front of regional ALBs/NLBs in each region.
**Follow-up trap:** *"Doesn't Global Accelerator make this a non-issue on AWS?"* — Global Accelerator closes much of the gap (it does give anycast IPs and fast health-check-based failover), but it's a separate service billed and configured independently, layered on top of regional load balancers rather than being the load balancer's native architecture — the operational and cost model still differs from GCP's global LB being one integrated resource.

### Q5 — Explain Private Service Connect and why it's preferred over VPC peering for exposing a service to another team or a third party.
**Testing:** the PSC value proposition versus the alternative it's replacing.
**Answer:** PSC lets a consumer reach a published service via a private IP inside the consumer's own VPC, without peering the two networks together — no IP-overlap coordination needed between producer and consumer, no transitive-reachability risk (peering exposes the whole peered network's routes by default unless carefully scoped with custom routes), and the producer controls exactly which consumers can connect via accept lists on the service attachment. VPC peering, by contrast, creates a much broader network-level relationship that's harder to constrain to "just this one service."
**Follow-up trap:** *"If PSC only exposes one service, how do you publish multiple services from the same producer VPC?"* — each service gets its own service attachment (and consumers create separate PSC endpoints per service they want to reach), so publishing N services means N service attachments — PSC doesn't collapse a producer's entire VPC into one exposed surface, which is exactly the fine-grained control that differentiates it from peering.

### Q6 — When would you choose a regional load balancer over the global external Application Load Balancer, even for an internet-facing service?
**Testing:** the "when NOT to" judgment, not just knowing the global option exists.
**Answer:** Data-residency requirements mandating traffic never leave a specific jurisdiction's routing path, active-passive DR designs needing explicit manual/scripted control over which region serves traffic rather than automatic nearest-PoP routing, genuinely single-region user bases where the global anycast's cost premium buys nothing, or workloads needing Standard Tier (internet-routed, cheaper) networking instead of the Premium Tier backbone routing that global LBs require.
**Follow-up trap:** *"Does using a regional LB mean losing all DDoS resilience benefits Cloud Armor provides?"* — no, Cloud Armor attaches to regional external LBs too, but the specific *edge-absorption* advantage of a global anycast IP (attack traffic distributed across every PoP simultaneously rather than concentrated at one region's ingress) is lost — Cloud Armor's rule-based mitigation still works, but the underlying architecture provides less inherent volumetric-attack dilution.

### Q7 — A workload needs to consume a SaaS vendor's API privately, without traversing the public internet, and the vendor also runs on GCP. What's the right connectivity pattern, and what would make it wrong?
**Testing:** applying PSC in the realistic "not both your own infra" scenario.
**Answer:** If the vendor publishes a Private Service Connect service attachment, the right pattern is creating a PSC endpoint in the consumer's VPC pointing at that service attachment — private IP, no internet transit, no IP-overlap coordination, and the vendor controls access via their own accept list. It's the wrong pattern if the vendor doesn't support PSC publishing at all (some SaaS vendors only offer public API endpoints or VPN-based access) — in that case, the fallback is Cloud VPN or Interconnect plus vendor-side IP allowlisting, or simply accepting public-internet-with-TLS access if the vendor genuinely has no private option.
**Follow-up trap:** *"If the vendor is on AWS instead of GCP, does PSC still work?"* — no, PSC is a GCP-native construct; cross-cloud private connectivity to an AWS-hosted vendor requires either the vendor exposing an AWS PrivateLink endpoint reachable via Cross-Cloud Interconnect, or a more traditional VPN/Interconnect-based hybrid path — PSC itself doesn't bridge to another cloud's private-endpoint construct.

### Q8 — Explain Cloud Armor's rate limiting and why static per-IP thresholds fail against a real botnet attack.
**Testing:** understanding the layered defense model, not just the feature list.
**Answer:** Cloud Armor rate limiting throttles or bans a client based on request volume over a configurable window, keyed typically by IP address (or other configurable keys like a cookie or header). Against a distributed botnet using thousands of rotating source IPs, a per-IP threshold never triggers for any individual IP even though aggregate load on the backend is severe — each attacking IP individually looks like normal traffic. This is exactly the gap **Adaptive Protection** (Enterprise tier) is built to close: ML-based anomaly detection against the backend's own traffic baseline, flagging aggregate pattern shifts rather than relying on any single dimension like per-IP volume.
**Follow-up trap:** *"Could you just lower the per-IP threshold aggressively to compensate?"* — that trades false negatives for false positives, likely blocking legitimate users behind shared NATs or CGNAT (common for mobile carriers, corporate networks) whose aggregate legitimate traffic from one IP now exceeds the lowered threshold — it's not a free fix, it shifts the failure mode rather than eliminating it.

### Q9 — Walk through what changes operationally when a team migrates a two-region AWS Transit-Gateway-based topology to GCP.
**Testing:** synthesizing the whole module into a migration scenario.
**Answer:** The Transit Gateway (and its route tables, attachments, and per-VPC routing propagation rules) largely disappears — if both regions' resources belong to the same org/environment, they become subnets of one GCP VPC with reachability by default. What replaces Transit Gateway's centralized routing control is disciplined firewall-rule scoping (since the default is now permissive-within-VPC rather than requiring explicit route propagation) and, if multiple teams need isolation, Shared VPC with per-subnet IAM grants instead of separate VPCs stitched by Transit Gateway attachments. The operational shift is from "explicitly wire reachability, implicitly get isolation" (AWS default) to "implicitly get reachability, explicitly wire isolation" (GCP default) — exactly inverted, and worth stating plainly in an interview.
**Follow-up trap:** *"Does this make GCP's model strictly simpler?"* — simpler for connectivity, but it shifts real security burden onto firewall-rule discipline; a team that doesn't internalize the inverted default can end up with a flatter, more permissive network than they intended, which is precisely the failure mode interviewers are probing for when they ask this question.

### Q10 — Why is Dedicated Interconnect's minimum port speed (10Gbps) often the wrong choice for a mid-size enterprise's hybrid connectivity, and what's the alternative?
**Testing:** cost/complexity judgment on hybrid connectivity sizing.
**Answer:** A 10Gbps Dedicated Interconnect port plus the colocation facility presence it requires is a large fixed commitment relative to what many mid-size workloads actually sustain — Partner Interconnect, going through a supported service provider, offers sub-10Gbps VLAN attachments (down to 50Mbps) without requiring the customer to have their own colocation presence, at lower entry cost and faster provisioning. Dedicated Interconnect's economics only win once sustained bandwidth utilization is high enough that its lower per-GiB egress rate and lack of provider fees offset the higher fixed port cost — a specific crossover point worth validating against actual traffic volume, not assumed.
**Follow-up trap:** *"If the workload later grows past what Partner Interconnect economically supports, is migrating to Dedicated disruptive?"* — it requires provisioning new circuits and a cutover, which is a real project, not a config change — this is exactly why bandwidth forecasting matters at the initial sizing decision, since under-provisioning Partner Interconnect and needing an early migration to Dedicated has real switching costs.

### Q11 — A candidate says "Cloud Armor is basically AWS WAF, just renamed." What's the one architectural detail that makes this an incomplete answer?
**Testing:** precision under a deliberately reductive framing, common interview pattern.
**Answer:** Functionally, both provide L7 WAF rules, rate limiting, and bot/DDoS mitigation attached to a load balancer or CDN — that part of the comparison is fair. What's missing: Cloud Armor's placement in front of GCP's **global anycast** load balancer means volumetric attacks are absorbed and distributed across Google's entire edge network by the underlying LB architecture itself, before Cloud Armor's rules even need to fire — AWS WAF attached to a regional ALB doesn't get that same structural dilution unless paired separately with Global Accelerator or CloudFront in front of it. The WAF rule engines are comparable; the network architecture underneath them isn't.
**Follow-up trap:** *"Does that mean Cloud Armor is strictly better at DDoS mitigation than AWS WAF?"* — not as a blanket claim; AWS WAF paired with CloudFront (which is also a globally distributed anycast-backed edge network) gets a comparable structural advantage — the fair comparison is Cloud Armor+global-LB versus AWS-WAF+CloudFront, not Cloud Armor versus a bare regional-ALB deployment of AWS WAF, which is the comparison that makes Cloud Armor look disproportionately better than it structurally is.

---

## Red flags that fail you

- Not knowing that GCP VPCs are global — describing them as regional like AWS/Azure.
- Assuming firewall rules are automatically region-scoped.
- Confusing VPC Network Peering with Shared VPC (different mechanisms, different use cases).
- Not knowing the global external Application Load Balancer uses a single anycast IP.
- Describing Cloud Armor as identical to AWS WAF with no mention of the underlying edge/anycast architecture difference.
- Recommending Dedicated Interconnect reflexively without checking actual sustained bandwidth need.
- Not knowing Private Service Connect avoids IP-overlap coordination the way peering requires it.

---

## Cheat card

```
VPC: GLOBAL resource. Subnets = REGIONAL. Cross-region reachability inside
  one VPC needs ZERO peering/transit config -- routed over Google backbone.
  Firewall rules + routes are VPC-(global)-scoped by DEFAULT -- use target
  tags/service accounts to scope, or they apply network-wide, every region.

SHARED VPC: host project owns network; service projects attach + deploy
  INTO host's subnets. IAM-governed: roles/compute.networkUser per subnet
  (preferred) or project-wide on host. ~AWS VPC-sharing-via-RAM, not peering.

CLOUD LOAD BALANCING:
  GLOBAL (ext. App LB / proxy Network LB): ONE anycast IP from every
  Google PoP. User -> nearest PoP -> Google backbone -> nearest healthy
  backend, any region. Needs Premium Tier. No DNS-based failover needed.
  REGIONAL: IP+rule scoped to 1 region, backends must be in-region.
  Use for data residency / active-passive DR / genuinely single-region.

CLOUD ARMOR: WAF+DDoS at the edge, in front of LB. ~$1/rule/month
  Standard tier. Enterprise ~$3k/mo = Adaptive Protection (ML anomaly
  detection) + DDoS bill insurance. Static per-IP rate limits fail against
  rotating-IP botnets -- that's what Adaptive Protection is for.

PRIVATE SERVICE CONNECT: private IP in consumer VPC -> producer's service
  attachment. No peering, no IP-overlap coordination, producer controls
  accept lists. ~AWS PrivateLink / Azure Private Link.

CLOUD INTERCONNECT: Dedicated = 10Gbps/100Gbps port, own colocation,
  VLAN attachments 50Mbps-50Gbps. Partner = sub-10Gbps via provider, no
  colocation needed, faster provisioning, higher per-GiB egress at scale.
  Cross-Cloud Interconnect = direct Google-provisioned link to AWS/Azure.

FAVORITE QUESTION: "GCP VPCs are global, AWS/Azure are regional" -- changes
  whether multi-region needs peering/transit AT ALL (GCP: usually no).
```

## Sources

- [VPC networks overview — Google Cloud Docs](https://cloud.google.com/vpc/docs/vpc) — accessed 2026-08-08
- [Subnets — Google Cloud Docs](https://docs.cloud.google.com/vpc/docs/subnets) — accessed 2026-08-08
- [Shared VPC — Google Cloud Docs](https://cloud.google.com/vpc/docs/shared-vpc) — accessed 2026-08-08
- [Choose a load balancer — Google Cloud Docs](https://docs.cloud.google.com/load-balancing/docs/choosing-load-balancer) — accessed 2026-08-08
- [Global External Application Load Balancer deep dive — Google Cloud Blog](https://cloud.google.com/blog/topics/developers-practitioners/google-cloud-global-external-https-load-balancer-deep-dive) — accessed 2026-08-08
- [Rate limiting overview — Google Cloud Armor Docs](https://docs.cloud.google.com/armor/docs/rate-limiting-overview) — accessed 2026-08-08
- [Google Cloud Armor pricing — Pump.co](https://www.pump.co/blog/google-cloud-armor/) — accessed 2026-08-08
- [Private Service Connect security — Google Cloud Docs](https://docs.cloud.google.com/vpc/docs/private-service-connect-security) — accessed 2026-08-08
- [Private Service Connect — Google Cloud Docs](https://docs.cloud.google.com/vpc/docs/private-service-connect) — accessed 2026-08-08
- [Cloud Interconnect pricing — Google Cloud](https://cloud.google.com/network-connectivity/docs/interconnect/pricing) — accessed 2026-08-08
- [Dedicated Interconnect overview — Google Cloud Docs](https://docs.cloud.google.com/network-connectivity/docs/interconnect/concepts/dedicated-overview) — accessed 2026-08-08
- `clouds/CROSS-CLOUD-MAP.md` — internal cross-cloud equivalence reference

## Changelog
- 2026-08-08 — created
