# VNet, NSG vs ASG, Application Gateway, Front Door, Private Link

> **Track:** C-AZ Azure Atlas · **Time:** 2.0h · **Prereqs:** `C-AZ-identity`, `C-AZ-compute` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-networking` · **Tags:** networking

## The 30-second version

Azure networking mirrors AWS's shape (VNet~VPC, NSG~Security Group, Application Gateway~ALB, Front Door~CloudFront, Private Link~PrivateLink) but the mechanics diverge in ways that matter under load. A **VNet is regional, not global** — same as AWS, unlike GCP's global VPC — and connects to other VNets via **peering**, capped at **500 peering connections per VNet by default** (extensible to 1,000 via Azure Virtual Network Manager). **NSGs** filter traffic by IP/port/protocol at subnet or NIC level with a hard **2,000-rule ceiling** (custom + default combined); **Application Security Groups (ASGs)** solve the "IP address sprawl in rules" problem by letting you group NICs by role and reference the *group* in an NSG rule instead of hardcoding IPs — up to **10 ASGs per rule reference** — this is Azure's answer to AWS's security-group-referencing-security-group pattern, done as a separate object rather than allowing NSGs to reference each other directly. **Application Gateway** is a regional, VNet-integrated L7 load balancer with an integrated WAF (v2 SKU autoscaling, billed on gateway-hours plus capacity-units) — the direct analog to ALB+AWS WAF, scoped to one VNet's ingress. **Front Door** is Azure's global edge/CDN+L7 load balancer+WAF (Standard/Premium tiers, flat monthly base plus request volume) — the analog to CloudFront+AWS WAF+Global Accelerator combined, and the two products get confused constantly because both can terminate TLS and both can attach a WAF, but only Front Door operates at the global edge. **Private Link** creates a private, VNet-local IP for a PaaS service (or your own Private Link Service) so traffic never traverses the public internet — capped at **1,000 private endpoints per VNet**. The single biggest trap: Application Gateway and Front Door are **not interchangeable** — picking Application Gateway for global traffic distribution or Front Door for VNet-internal-only ingress is a design error that shows up as either unreachable-from-the-internet resources or absent global failover.

## Why this gets asked

The interviewer has debugged an NSG rule set that silently hit the 2,000-rule ceiling during a migration wave and started rejecting new rule creation with an opaque error, has explained to a team why their "global load balancer" (actually an Application Gateway, regionally scoped) didn't fail over when a region went down, has watched a Private Link rollout stall because a team didn't understand DNS resolution for private endpoints requires a Private DNS Zone wired up correctly, and has had to clarify — repeatedly — that ASGs are not a NSG replacement but a labeling mechanism NSGs consume. They want to see you reason about which layer (VNet, subnet, NIC, regional edge, global edge) a given control actually operates at.

---

## Lineage: past → present → future

**What came before.** Azure's early network security model (2013-2015 era) was NSGs only, IP-address-and-port-range rules with no grouping abstraction — every rule referencing a set of VMs required listing their IPs explicitly, and IP churn (VM redeployment, scale-set instance replacement) meant rules constantly needed manual updates. Load balancing before Application Gateway's L7 features matured meant most L7 concerns (SSL termination, path-based routing, WAF) were either handled by third-party VM-based appliances or not handled at all, mirroring the pre-ALB era of AWS relying on Classic ELB's L4-only feature set. Global traffic distribution had no first-class Azure product until Azure Traffic Manager (DNS-based, not a true edge proxy) and the original Azure CDN, both of which lacked integrated WAF and modern edge compute capability.

**Where it stands now.** **Application Security Groups** (GA years ago, now the standard pattern) decouple "which VMs does this rule apply to" from "what IP does this VM currently have" — VMs join an ASG by network interface, and NSG rules reference the ASG, so scaling a fleet up/down or replacing instances never requires touching rule definitions. **Application Gateway v2** (the current generation, v1 is legacy/deprecated-path) supports autoscaling, zone redundancy, and an integrated WAF v2 SKU, billed on a fixed gateway-hour rate (**~$0.443/hour**) plus variable capacity-unit consumption (**~$0.0144/capacity-unit-hour**). **Front Door** consolidated Azure's CDN and global L7 load balancing into one product line with two current tiers: **Standard** (~$35/month base, custom WAF rules) and **Premium** (~$330/month base, adds managed WAF rule sets and Private Link origin support), plus per-request/data-transfer charges. [Azure WAF pricing 2026](https://wafpricing.com/azure-waf-pricing) — accessed 2026-08-08. **Private Link** is now the standard pattern for PaaS-to-VNet private connectivity, with the live disagreement in the ecosystem being less "should we use Private Link" (settled — yes, for anything handling sensitive data) and more "Private Endpoint per-service vs. a hub-and-spoke shared Private Link architecture" for large estates trying to stay under the 1,000-endpoints-per-VNet ceiling.

**Where it's heading.** Azure Virtual Network Manager's centralized connectivity/security-rule management (letting you define peering topology and security baselines across many VNets from one control point, rather than configuring peering pairwise) is the clear direction for large estates — moderate-to-high confidence, since it's the mechanism that raises the 500-peering default ceiling to 1,000 and Microsoft is actively investing in it as the multi-VNet management story. Front Door and Application Gateway's feature sets continue to converge at the edges (Front Door Premium's Private Link origin support already blurs the "global edge can't reach VNet-private origins" line that used to force Application Gateway as a mandatory intermediary) — moderate confidence on how far this convergence goes before one product is clearly positioned as legacy.

---

## Mental model

```
GLOBAL EDGE (anycast, one config, many PoPs worldwide)
  ┌─────────────────────────────────────────────────┐
  │  FRONT DOOR (Standard/Premium)                    │
  │  CDN + global L7 LB + WAF + Private Link origin    │
  │  (Premium)                                          │
  └──────────────────────┬──────────────────────────┘
                          │  routes to regional origins
                          ▼
REGIONAL, VNET-SCOPED
  ┌─────────────────────────────────────────────────┐
  │  APPLICATION GATEWAY v2 (per-VNet, per-region)     │
  │  L7 LB + WAF v2, path routing, SSL termination     │
  └──────────────────────┬──────────────────────────┘
                          │
                          ▼
VNET  (regional, NOT global -- unlike GCP)
  ┌─────────────┐  peering (up to 500/VNet default,   ┌─────────────┐
  │  VNet A     │◄────1000 via vNet Manager)──────────►│  VNet B     │
  │  subnets    │                                       │  subnets    │
  │   NSG (2000 rule cap, subnet or NIC scope)           │
  │   ASG (groups NICs by role, up to 10 refs/rule)      │
  └─────────────┘                                       └─────────────┘
        │
        ▼
PRIVATE LINK (private IP for a PaaS service inside your VNet)
  Private Endpoint (consumer side, up to 1000/VNet) <--> Private Link Service
  (provider side, up to 8 NAT IPs) -- traffic never touches the public internet
```

---

## How it actually works

### VNet and peering

A VNet is a regional construct with a defined address space (RFC 1918 or Azure-allocated public ranges); subnets carve that space within the region. **Peering** connects two VNets (same or different regions — "Global VNet Peering" spans regions) with low-latency, private, Microsoft-backbone connectivity, but peering is **non-transitive**: if A peers with B and B peers with C, A cannot reach C through B without an explicit A-C peering or a hub router (Azure Firewall, NVA, or Virtual Network Manager mesh). Peering limits: **200 subnets per side of a single peering link, 1,000 total subnets across all peering links for one VNet**, and **500 total peering connections per VNet by default**, extensible to **1,000 via Azure Virtual Network Manager's connectivity configuration**. [Virtual network peering overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview) — accessed 2026-08-08.

### NSG vs ASG — the distinction that gets conflated

An **NSG** is a stateful L3/L4 packet filter: a prioritized list of allow/deny rules matching on source/destination IP (or IP range/service tag), port, and protocol, attached to a **subnet**, a **NIC**, or both — and if attached to both, Azure evaluates **both** and traffic must pass both (the more restrictive union wins). The hard ceiling: **2,000 rules per NSG**, custom and default rules combined — "augmented security rules" (multiple IP ranges/ports collapsed into one rule via comma-separated lists or service tags) are the standard mitigation when a rule count approaches that ceiling rather than trying to raise it. [NSG and ASG design guide — Microsoft Learn](https://learn.microsoft.com/en-us/azure/networking/design-guide/network-application-security-groups) — accessed 2026-08-08.

An **ASG** is not a firewall — it's a **label**. You assign a VM's network interface to one or more ASGs (e.g., `asg-web-tier`, `asg-db-tier`), and then an NSG rule references the ASG as its source or destination instead of a hardcoded IP or CIDR range. A rule can reference **up to 10 ASGs** as source and 10 as destination. The mechanical benefit: when a VM is redeployed, scaled, or replaced (a VMSS instance churns, a VM gets a new IP), its ASG membership is what matters, not its current IP — the NSG rule never needs to change. This is architecturally similar to AWS security groups referencing other security groups as a source, except Azure splits it into two objects (NSG for rules, ASG for grouping) rather than letting the filtering object reference itself.

```bash
# untested sketch — az CLI, ASG-based NSG rule instead of hardcoded IPs
az network asg create --name asg-web-tier --resource-group my-rg
az network nic update --name web-vm-nic --resource-group my-rg \
  --application-security-groups asg-web-tier

az network nsg rule create \
  --nsg-name my-nsg --resource-group my-rg \
  --name allow-web-to-db \
  --priority 100 \
  --source-asgs asg-web-tier \
  --destination-asgs asg-db-tier \
  --destination-port-ranges 5432 \
  --access Allow --protocol Tcp
```

### Application Gateway v2

A regional, VNet-deployed L7 reverse proxy: path-based routing, SSL/TLS termination and re-encryption, cookie-based session affinity, and an integrated **WAF v2** SKU (OWASP Core Rule Set managed rules plus custom rules). v2 SKUs autoscale (add/remove instances based on load) and support zone redundancy across availability zones within the region. Pricing: a fixed **~$0.443/gateway-hour** plus variable **~$0.0144/capacity-unit-hour** (a capacity unit bundles compute, throughput, and connection-count consumption). [Application Gateway pricing — Microsoft Learn](https://learn.microsoft.com/en-us/azure/application-gateway/understanding-pricing) — accessed 2026-08-08. Because it's VNet-deployed, Application Gateway is the natural choice when the backend is entirely private (no public internet exposure needed for the origin) and traffic is single-region.

### Front Door

A global anycast-edge service: TLS termination and WAF enforcement happen at the nearest Microsoft PoP to the client, then traffic is routed over the Microsoft global backbone to the best-available regional origin (with health-probe-based automatic failover across origins/regions). Two tiers: **Standard** (~$35/month base, custom WAF rules only, no managed rule set) and **Premium** (~$330/month base, includes managed WAF rule sets and **Private Link origin support** — letting Front Door Premium reach an origin that has no public IP at all, via a Private Endpoint). Both add per-request and data-transfer charges on top of the base. [Azure WAF pricing 2026](https://wafpricing.com/azure-waf-pricing) — accessed 2026-08-08.

**The decision that actually matters**: Application Gateway answers "how do I load-balance and inspect traffic within one region's VNet ingress." Front Door answers "how do I give global users a fast, resilient entry point with automatic regional failover." A common production pattern layers both: Front Door Premium at the edge (global failover, WAF, CDN caching), each regional origin behind its own Application Gateway (VNet-internal path routing, a second WAF layer, private backend connectivity).

### Private Link

**Private Endpoint** (consumer side): a NIC with a private IP from your VNet's address space, mapped to a specific PaaS resource (a storage account, a Cosmos DB account, a Key Vault) or to a Private Link Service. DNS resolution for the PaaS resource's FQDN must resolve to that private IP inside the VNet — this requires either a **Private DNS Zone** linked to the VNet (the standard, automatable pattern) or manual hosts-file-style overrides, and forgetting this step is the most common Private Link rollout failure: the endpoint exists and works, but clients still resolve the public FQDN and hit the public endpoint instead. **Private Link Service** (provider side, for exposing your own service to consumers): supports up to **8 NAT IP addresses**. Real ceilings: **1,000 private endpoints per virtual network**, and **400 Key Vaults with private endpoints per subscription**. [Azure Private Link FAQ — Microsoft Learn](https://learn.microsoft.com/en-us/azure/private-link/private-link-faq) — accessed 2026-08-08.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| VPC | VNet | VPC (global, not regional) | GCP VPCs are global with per-region subnets; AWS and Azure VNets/VPCs are regional |
| Security Group (self-referencing) | NSG + ASG (two separate objects) | Firewall rules + target tags | Azure splits "filter rule" (NSG) from "group label" (ASG); AWS lets a security group reference itself directly |
| ALB + AWS WAF | Application Gateway v2 (+ WAF v2 SKU) | Cloud Load Balancing (regional) | Both are regional, VNet/VPC-scoped L7 proxies with integrated WAF |
| CloudFront + AWS WAF + Global Accelerator | Front Door (Standard/Premium) | Cloud CDN + global external LB | Front Door bundles CDN, global L7 LB, and WAF into one product; AWS splits this across three |
| PrivateLink (VPC endpoint) | Private Link (Private Endpoint) | Private Service Connect | Azure Private Endpoint requires explicit Private DNS Zone wiring — DNS doesn't "just work" the way it can with some AWS interface endpoint configurations |

---

## Build it from scratch

Minimal end-to-end shape combining a Private Endpoint with correct DNS resolution, matching `labs/bicep/05-networking/`:

```bash
# untested sketch — az CLI: Private Endpoint + Private DNS Zone wiring
# 1. Create the private endpoint targeting a storage account
az network private-endpoint create \
  --name pe-storage \
  --resource-group my-rg \
  --vnet-name my-vnet \
  --subnet my-subnet \
  --private-connection-resource-id /subscriptions/.../storageAccounts/mystorage \
  --group-id blob \
  --connection-name pe-storage-conn

# 2. THE STEP TEAMS FORGET: without this, clients still resolve the
#    public FQDN and bypass the private endpoint entirely.
az network private-dns zone create \
  --resource-group my-rg \
  --name privatelink.blob.core.windows.net

az network private-dns link vnet create \
  --resource-group my-rg \
  --zone-name privatelink.blob.core.windows.net \
  --name my-vnet-link \
  --virtual-network my-vnet \
  --registration-enabled false

az network private-endpoint dns-zone-group create \
  --resource-group my-rg \
  --endpoint-name pe-storage \
  --name default \
  --private-dns-zone privatelink.blob.core.windows.net \
  --zone-name blob
```

---

## How it's done in production

A typical production edge-to-backend path: **Front Door Premium** at the global edge for TLS termination, managed WAF rule set enforcement, CDN caching of static assets, and health-probe-driven regional failover; each region's backend sits behind its own **Application Gateway v2** (zone-redundant, autoscaling, a second WAF layer scoped to that region's specific application paths) which routes to backend pools that are themselves reachable only via **Private Endpoints** to PaaS services (databases, storage, Key Vault) — no PaaS resource has a public endpoint exposed. **NSGs with ASG-based rules** enforce east-west segmentation between tiers (web, app, data) within each VNet, and **VNet peering** (increasingly managed via Azure Virtual Network Manager for estates approaching the 500-peering default ceiling) connects hub (shared services: firewall, DNS, bastion) to spoke VNets per environment or team.

| Symptom | Cause | Fix |
|---|---|---|
| New NSG rule creation fails with an opaque error during a migration wave | NSG hit the 2,000-rule ceiling (custom + default combined) | Consolidate rules using augmented security rules (comma-separated IP ranges/ports in one rule) or ASG-based grouping instead of individual IP-based rules |
| A client can still reach a PaaS resource's public endpoint despite a Private Endpoint being configured | Private DNS Zone not linked to the VNet, or `registration-enabled` misconfigured — client is still resolving the public FQDN | Verify the Private DNS Zone link and confirm `nslookup` from inside the VNet resolves to the private IP, not the public one |
| "Global load balancer" doesn't fail over when a region goes down | Application Gateway was used for what should have been a Front Door deployment — Application Gateway is regional, not global | Put Front Door in front of per-region Application Gateways for genuine global failover; Application Gateway alone has no cross-region awareness |
| VNet peering requests start failing once a hub VNet approaches many spoke connections | Hit the default 500-peering-per-VNet ceiling | Migrate to Azure Virtual Network Manager connectivity configuration to raise the ceiling to 1,000, or restructure into a multi-hub topology |
| ASG-based NSG rule doesn't apply to a newly deployed VM in the intended tier | VM's NIC was never added to the ASG (ASG membership is explicit, not automatic based on naming or tags) | Confirm the NIC's ASG assignment as part of the VM provisioning template/pipeline, not a manual post-deploy step |
| Front Door Standard tier WAF misses attacks a team assumed were covered | Standard tier only includes custom WAF rules, not the managed OWASP rule set — that's Premium-only | Upgrade to Front Door Premium if managed rule set coverage is a real requirement, or replicate specific managed-rule protections as custom rules on Standard |

---

## Tradeoffs & when NOT to use it

- **Don't use Application Gateway when you need genuine global failover or edge caching.** It's regional and VNet-scoped by design; reach for Front Door for anything needing multi-region resilience or CDN behavior.
- **Don't use Front Door Standard and assume you have managed WAF rule set protection.** Standard is custom-rules-only; the OWASP managed rule set specifically requires Premium.
- **Don't hardcode IPs in NSG rules for anything that scales or gets redeployed.** ASGs exist precisely to avoid this churn; an NSG rule set built on raw IPs is a maintenance trap waiting for the next scale-out event.
- **Don't assume creating a Private Endpoint alone routes traffic privately.** Without correct Private DNS Zone wiring, clients keep resolving the public endpoint and the private endpoint sits unused — this is the single most common Private Link deployment failure.
- **Don't rely on VNet peering for transitive routing.** Peering is explicitly non-transitive; a hub-and-spoke topology needs an actual router (Azure Firewall, NVA, or a mesh via Virtual Network Manager) if spoke-to-spoke traffic is required.
- **Don't provision an Application Gateway per tiny microservice reflexively.** Each gateway carries its own fixed gateway-hour cost; for many small internal services, a shared Application Gateway with path-based routing or Container Apps' built-in ingress may be more cost-effective than one gateway per service.

---

## Interview questions

### Q1 — Explain the structural difference between an NSG and an ASG, and why Azure split them into two objects instead of letting NSGs reference each other.
**Testing:** whether the label-vs-filter distinction is understood mechanically.
**Answer:** An NSG is the actual filter — a prioritized allow/deny rule list evaluated against IP/port/protocol, attached to a subnet and/or NIC. An ASG is not a filter at all; it's a group label assigned to NICs, which an NSG rule can then reference as its source or destination instead of a hardcoded IP. This decoupling means a rule stays valid as VM IPs churn (scale-out, redeployment) since what matters is ASG membership, not current IP — mechanically similar in intent to AWS security groups referencing other security groups, but implemented as two distinct object types rather than allowing a filtering object to reference itself.
**Follow-up trap:** *"If a VM's NIC is never explicitly added to an ASG, does it inherit any protection from rules referencing that ASG?"* — no, ASG membership is fully explicit and must be assigned to the NIC; there's no implicit membership based on naming, tags, or subnet location, which is exactly why forgetting this step in a provisioning pipeline is a common real incident.

### Q2 — A team's NSG rule creation starts failing with an opaque error during a large migration. Diagnose.
**Testing:** the specific 2,000-rule hard ceiling.
**Answer:** Check the NSG's total rule count (custom plus default rules) against the hard 2,000-rule ceiling per NSG — a migration wave that creates many narrow, IP-specific rules can approach this quickly. Fix: consolidate using augmented security rules (multiple IP ranges or ports collapsed into one rule via lists or service tags) or move to ASG-based grouping so fewer, broader rules cover more resources.
**Follow-up trap:** *"Can the 2,000-rule limit be raised via a support request the way some Azure quotas can?"* — no, this is a hard architectural ceiling, not a raisable quota; the fix is always rule consolidation, never a limit increase request.

### Q3 — Explain why Application Gateway and Front Door are not interchangeable, and describe a production topology using both.
**Testing:** the regional-vs-global distinction, the most commonly conflated pair in Azure networking.
**Answer:** Application Gateway is a regional, VNet-deployed L7 proxy — it has no awareness of other regions and cannot fail over across them. Front Door is a global anycast-edge service that terminates TLS at the nearest PoP and routes to the best-available regional origin with automatic health-probe-driven failover. A common production topology: Front Door Premium at the global edge (WAF, CDN, cross-region failover), with each region's origin sitting behind its own Application Gateway v2 (VNet-internal path routing, a second regional WAF layer, private backend connectivity).
**Follow-up trap:** *"Since Front Door already has a WAF, why would you add a second WAF layer at Application Gateway?"* — defense in depth and separation of concerns: Front Door's WAF protects the global edge against broad attack patterns, while an Application Gateway WAF layer can enforce application-specific or region-specific rules closer to the actual backend, and some compliance frameworks specifically require WAF enforcement at the VNet boundary regardless of edge-level protection.

### Q4 — Walk through what actually breaks if a team creates a Private Endpoint but never configures Private DNS.
**Testing:** the most common real Private Link deployment failure.
**Answer:** The Private Endpoint itself is created successfully and has a valid private IP, but DNS resolution for the target PaaS resource's FQDN (e.g., `mystorage.blob.core.windows.net`) still resolves to the **public** IP unless a Private DNS Zone (`privatelink.blob.core.windows.net`) is created and linked to the VNet, mapping that FQDN to the private endpoint's IP specifically for clients inside the VNet. Without that link, clients inside the VNet still route to the public endpoint — the private endpoint exists but is effectively unused, and traffic never gets the private-connectivity benefit the team intended.
**Follow-up trap:** *"If NSGs or firewall rules block the public endpoint entirely, wouldn't that force traffic onto the private path?"* — no, it would just break connectivity entirely (clients resolve the public IP, then get blocked reaching it) rather than route them to the private IP; DNS resolution and network reachability are separate failure modes, and fixing one doesn't fix the other.

### Q5 — Compare VNet peering's transitivity model to how routing works in a typical AWS Transit Gateway hub-and-spoke setup.
**Testing:** the non-transitive peering trap and the architectural implication.
**Answer:** VNet peering is explicitly non-transitive: if VNet A peers with hub VNet B, and hub VNet B peers with VNet C, A cannot reach C through B without an explicit A-C peering or an actual router in the path (Azure Firewall, an NVA, or Virtual Network Manager's mesh connectivity). This differs from a Transit Gateway-based AWS hub-and-spoke, where the Transit Gateway itself functions as a router providing transitive routing between attached VPCs by design. Azure's raw peering primitive requires you to build the router yourself if spoke-to-spoke transitivity is needed.
**Follow-up trap:** *"Does Azure have a direct Transit Gateway equivalent that provides transitive routing out of the box?"* — Azure Virtual WAN is the closer analog, providing a managed hub with transitive routing between connected VNets, but plain VNet peering (the more commonly deployed primitive) does not include this behavior — conflating the two is a real design mistake.

### Q6 — A hub VNet approaches its VNet peering connection limit as new spoke VNets are added. What's the fix?
**Testing:** the specific 500-peering default ceiling and its resolution path.
**Answer:** Default VNet peering supports up to 500 peering connections per VNet. Once approached, the fix is adopting Azure Virtual Network Manager's connectivity configuration, which both raises the ceiling to 1,000 peered VNets and centralizes peering/security-rule management across the estate rather than configuring each peering pairwise.
**Follow-up trap:** *"Is 1,000 a hard ceiling even with Virtual Network Manager, or is it also extensible?"* — verify against current documentation near interview time; treating any specific Azure limit as permanently fixed without a "check current docs" caveat is itself a signal to avoid, since these ceilings shift as the platform evolves.

### Q7 — Explain Application Gateway v2's pricing model and why it can surprise a team used to AWS ALB's simpler per-LCU-hour model.
**Testing:** the fixed-plus-variable billing shape and its cost-modeling implication.
**Answer:** Application Gateway v2 bills a fixed gateway-hour rate (~$0.443/hour) that accrues regardless of traffic, plus variable capacity-unit consumption (~$0.0144/capacity-unit-hour) that scales with actual compute/throughput/connection load. This means an idle or low-traffic Application Gateway still carries a meaningful fixed cost floor, unlike scale-to-zero compute options — a team provisioning one gateway per small internal service across many services can accumulate a surprising fixed-cost floor even with minimal aggregate traffic.
**Follow-up trap:** *"Would consolidating multiple small services behind one shared Application Gateway with path-based routing reduce this cost?"* — yes, that's the standard mitigation: one gateway's fixed cost is amortized across many backend services via path-based or host-based routing rules, rather than provisioning a dedicated gateway per service.

### Q8 — Design network segmentation for a three-tier application (web, app, data) using NSGs and ASGs.
**Testing:** synthesizing the NSG/ASG relationship into an actual security design.
**Answer:** Create three ASGs (`asg-web`, `asg-app`, `asg-data`), assign each tier's VM/VMSS NICs to the corresponding ASG. NSG rules reference ASGs as source/destination: allow `asg-web` → `asg-app` on the app's listening port, allow `asg-app` → `asg-data` on the database port, and explicitly deny (or simply don't allow) `asg-web` → `asg-data` directly, enforcing that web-tier traffic can only reach data through the app tier. As instances scale or get replaced within each tier, ASG membership (not IP-based rules) keeps the segmentation correct with zero rule changes.
**Follow-up trap:** *"Is this segmentation sufficient on its own, or does it need to be paired with subnet-level controls?"* — ASG/NSG rules at the NIC level are necessary but often paired with subnet-level NSGs and subnet delegation as defense in depth; relying solely on NIC-level ASG rules without any subnet boundary is a weaker posture than layering both, since a misconfigured or bypassed NIC-level rule has no subnet-level backstop.

### Q9 — Why would a Front Door Premium deployment specifically enable an origin with no public IP at all, and what makes that possible?
**Testing:** the Private Link origin support feature, a genuinely differentiating Premium capability.
**Answer:** Front Door Premium supports **Private Link origins** — the global edge service can reach a regional backend via a Private Endpoint even though that backend has zero public network exposure, closing what used to be a hard requirement that anything behind Front Door must have at least some public reachability (even if firewalled down to Front Door's IP ranges). This lets a team achieve both global edge distribution/WAF/CDN benefits and a fully private backend with no public attack surface at all.
**Follow-up trap:** *"Does Front Door Standard support this same Private Link origin capability?"* — no, Private Link origin support is Premium-only, alongside the managed WAF rule set — this is one of the concrete, testable differences between the two tiers beyond just the base monthly price.

### Q10 — A security review finds a PaaS resource (a Key Vault) with a Private Endpoint configured but still reachable from the public internet. Diagnose.
**Testing:** the distinction between having a private endpoint and actually disabling public access.
**Answer:** A Private Endpoint being configured doesn't automatically disable the resource's public network access — that's a separate setting on the resource itself (e.g., Key Vault's "Public network access" toggle, or a firewall/network-rules configuration denying all public traffic). A team that creates the private endpoint but never disables public access has added a private path without removing the public one, leaving both reachable.
**Follow-up trap:** *"Is disabling public access always safe once a private endpoint exists?"* — only if every legitimate client path has been migrated to route through the VNet (directly, via peering, or via VPN/ExpressRoute); disabling public access before confirming all consumers have private connectivity is a common way to cause a self-inflicted outage during a Private Link rollout.

### Q11 — Compare Azure's VNet-is-regional model to GCP's global VPC model and explain the concrete multi-region design implication.
**Testing:** the cross-cloud networking fact most likely to come up when comparing architectures.
**Answer:** A GCP VPC spans all regions globally with per-region subnets under one VPC object, so multi-region connectivity within a GCP VPC requires no peering at all — it's inherent to the VPC's scope. Azure VNets (like AWS VPCs) are regional; multi-region connectivity requires explicit VNet peering (Global Peering across regions) or a hub service like Azure Virtual WAN. This means a GCP-to-Azure architecture migration has to introduce an entirely new connectivity layer (peering, or Virtual WAN) that simply didn't need to exist under GCP's global VPC model.
**Follow-up trap:** *"Does this make GCP's networking model strictly simpler for multi-region designs?"* — simpler for basic multi-region reachability, yes, but it also means IP address planning and regional isolation boundaries work differently — a GCP VPC's global scope requires more upfront care in subnet CIDR planning across all regions at once, versus Azure/AWS's regional VNets/VPCs where each region's address space can be planned more independently.

---

## Red flags that fail you

- Describing an ASG as "just another kind of NSG" rather than naming the label-vs-filter distinction.
- Recommending Application Gateway for global traffic distribution or cross-region failover.
- Not knowing Front Door Standard lacks the managed WAF rule set that Premium includes.
- Claiming a Private Endpoint alone guarantees private-only traffic without mentioning DNS wiring or the separate public-access-disable step.
- Assuming VNet peering is transitive.
- Not knowing the 2,000-rule NSG ceiling or the 500-peering default VNet ceiling.
- Confusing Azure's regional VNet model with GCP's global VPC model.

---

## Cheat card

```
VNET: regional (not global, unlike GCP VPC). Peering non-transitive.
  Peering limits: 200 subnets/side per peering link, 1000 total subnets/VNet,
  500 peering connections/VNet default (1000 via Azure Virtual Network Manager).

NSG vs ASG: NSG = actual filter (IP/port/protocol, subnet or NIC scope, BOTH
  evaluated if attached to both). Hard cap: 2000 rules/NSG (custom+default).
  ASG = LABEL only, not a filter. NIC joins ASG explicitly (no auto-membership).
  NSG rule references up to 10 ASGs as source, 10 as destination.
  Fix for rule-count pressure: augmented rules (IP/port lists) or ASG grouping,
  NEVER a raisable limit.

APP GATEWAY v2: REGIONAL, VNet-scoped L7 LB + WAF v2 (OWASP CRS + custom rules).
  Autoscaling, zone-redundant. Pricing: ~$0.443/gateway-hour + ~$0.0144/capacity-
  unit-hour (fixed + variable).

FRONT DOOR: GLOBAL anycast edge, CDN + L7 LB + WAF, cross-region auto-failover.
  Standard (~$35/mo base, CUSTOM WAF rules only) vs Premium (~$330/mo base,
  MANAGED WAF rule set + Private Link origin support -- reach a backend with
  ZERO public IP). Both + per-request/data-transfer charges.
  App Gateway != Front Door: regional ingress vs global edge -- not interchangeable.

PRIVATE LINK: Private Endpoint (consumer, private IP in your VNet) vs Private
  Link Service (provider, up to 8 NAT IPs). Limits: 1000 private endpoints/VNet,
  400 Key-Vault-with-PE/subscription.
  #1 FAILURE: endpoint created but Private DNS Zone not linked to VNet -> clients
  still resolve PUBLIC FQDN, private endpoint sits unused. Also: PE existing does
  NOT auto-disable public access -- that's a separate resource-level toggle.

CROSS-CLOUD: VNet~=VPC (regional, both AWS+Azure; GCP VPC is GLOBAL).
  NSG+ASG~=Security Group (self-referencing) -- Azure splits filter from label.
  App Gateway~=ALB+WAF. Front Door~=CloudFront+WAF+Global Accelerator combined.
  Private Link~=PrivateLink/VPC endpoint.
```

## Sources

- [Network security groups and application security groups — Microsoft Learn](https://learn.microsoft.com/en-us/azure/networking/design-guide/network-application-security-groups) — accessed 2026-08-08
- [Azure Application Security Groups overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-network/application-security-groups) — accessed 2026-08-08
- [Virtual Network Peering overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-peering-overview) — accessed 2026-08-08
- [Understanding pricing — Application Gateway — Microsoft Learn](https://learn.microsoft.com/en-us/azure/application-gateway/understanding-pricing) — accessed 2026-08-08
- [What is Azure Application Gateway v2? — Microsoft Learn](https://learn.microsoft.com/en-us/azure/application-gateway/overview-v2) — accessed 2026-08-08
- [Azure WAF Pricing 2026 — wafpricing.com](https://wafpricing.com/azure-waf-pricing) — accessed 2026-08-08
- [Azure Private Link frequently asked questions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/private-link/private-link-faq) — accessed 2026-08-08
- [What is Azure Private Link service? — Microsoft Learn](https://learn.microsoft.com/en-us/azure/private-link/private-link-service-overview) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
- 2026-08-09 — Azure Virtual Network routing appliance reaches GA — a managed, specialized-hardware alternative to NVAs for private cross-VNet connectivity with lower latency and higher throughput ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
- 2026-08-09 — Azure Enclave reaches public preview across commercial and Government clouds — a new confidential-computing product for streamlined isolated-environment deployment for sensitive workloads ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
