# Azure Compute Deep: VMs, VMSS, App Service, Container Apps, AKS

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-compute` · **Tags:** compute,critical

## The 30-second version

Azure's compute portfolio is a control-versus-operations dial: raw VMs give total control and total patch burden; VMSS adds fleet orchestration (uniform for stateless scale sets, flexible for mixed-size HA topologies); App Service runs code with zero container concerns but a rigid runtime contract; Container Apps gives serverless containers with KEDA scale-to-zero and immutable revisions without owning a cluster; AKS hands you full Kubernetes with its full operational tax — support window N-2 plus an N-3 platform-support grace, one-minor-version-at-a-time upgrades, and real subnet/IP planning because Azure CNI assigns pod IPs from your VNet. The numbers that decide designs: App Service premium tiers scale to ~20-30 instances while VMSS reaches 1000; Container Apps defaults to max 10 replicas per app until you raise it toward 1000; and the classic outage pattern is pods stuck Pending not from missing capacity but from subnet IP exhaustion under Azure CNI.

## Why this gets asked

Because service selection is the daily staff-level decision on Azure, and every wrong pick has a signature failure the interviewer has lived through: teams adopting AKS for three services and drowning in upgrade/observability overhead they didn't budget; App Service apps that mysteriously lose config after slot swaps because connection strings were slot-sticky; Container Apps workloads that thrash between 0 and 1 replicas because someone set scale-to-zero on a latency-sensitive endpoint; VMSS fleets that lost SLA coverage because someone chose uniform orchestration with a marketplace image that caps instance counts. The probe underneath: do you match workload shape (stateful/stateless, bursty/steady, containerized/not) to platform contracts, and can you articulate the operational cost of each tier rather than defaulting to "Kubernetes because career."

---

## Lineage: past → present → future

**What came before.** Azure's first decade was VM-shaped: Cloud Services (web/worker roles, 2009-ish) abstracted the OS but locked you into a rigid packaging model and died slowly as everything moved to IaaS ARM VMs post-2014. App Service (2015, from Azure Websites) killed "FTP a folder onto an IIS box" for web workloads. Scale sets arrived in 2015-2016 as the autoscaling VM story, initially uniform-only — every identical VM, one model — which broke down for stateful and mixed-criticality fleets. ACS then AKS (GA 2017) brought managed Kubernetes after Microsoft conceded that fighting the ecosystem's gravity was pointless.

**Where it stands now.** The current lineup reflects two decades of consolidation: VMSS Flexible orchestration (GA 2021) unifies VM and scale-set semantics — mixed sizes, spread across zones/fault domains, count-based SLA like availability sets — while Uniform remains for simple stateless fleets; App Service settled on PremiumV3/MV3 SKUs as the sensible floor for production; Container Apps (GA 2021) emerged as the "Kubernetes without Kubernetes" answer, built on AKS internals but exposing only apps, revisions, and KEDA scalers — now carrying AI-specific features like dynamic sessions and GPU workload profiles; AKS matured into free/Standard/Premium tiers with N-2 version support, platform support at N-3, node autoprovisioning (Karpenter-based) and AKS Automatic as the opinionated production default. The live disagreement: Container Apps versus AKS for new microservices — CA covers most teams' actual needs (HTTP apps, queue workers, jobs) while AKS earns its cost only when you need the ecosystem: custom CRDs/operators, service mesh, strict multi-tenancy, GPU scheduling beyond what CA exposes.

**Where it's heading.** High confidence: convergence of the serverless-container line — Flex Consumption functions and Container Apps already share substrate (`Microsoft.App` resource provider, same subnet delegation), and expect further unification of scale semantics around concurrency-driven models. Medium confidence: Karpenter-style node autoprovisioning becoming AKS default rather than opt-in, and AKS Automatic absorbing more "boring production cluster" decisions. Speculative-but-loud: AI inference workloads reshaping the whole stack — GPU node pools, session pools for code execution, model-serving add-ons — treat specific product names there as moving targets and verify before quoting them in interviews.

---

## Mental model

One dial: how much of the stack you own versus rent:

```
 OWN MORE ◀──────────────────────────────────────────────▶ OPERATE LESS
 
 VMs            VMSS             App Service        Container Apps      AKS
 ─────          ────             ───────────        ──────────────      ───
 OS+runtime     OS+runtime       runtime only       container image     anything K8s
 you patch      you patch        platform patches   platform patches    you own cluster
 manual scale   autoscale        autoscale ~20-30   scale-to-zero       HPA/KEDA/CA +
                ~1000 inst       inst, slots        revisions, KEDA     cluster-autoscaler
 full licensing full licensing   fixed runtimes     any container       any workload
                                 no sidecars        sidecars(Dapr)      
                                                      no vertical scale
 
 SLA anchor: zones > availability sets (VMSS-Flexible) > single-instance
```

And the scaling-brain comparison:

```
 App Service:   CPU/memory rules -> add instance (manual or autoscale)
 VMSS:          metric thresholds -> add VM from image
 Container Apps: KEDA polls event sources every ~30 s
                 desiredReplicas = ceil(metric / target), cooldown ~300 s
 AKS:           HPA (metrics) + cluster-autoscaler/Karpenter (nodes)
```

**The one-liner:** pick the leftmost service whose constraints you can actually live with — every step right removes operations and removes control simultaneously.

---

## How it actually works

### VMs and VMSS

Sizing families worth knowing by letter: D-series general purpose (~4 GB RAM/vCPU), E-series memory-optimized (~8 GB/vCPU), F-series compute-optimized (~2 GB/vCPU, best price-per-ACU), N-series/GPU and HPC lines. ACU (Azure Compute Unit) benchmarks relative CPU with 100 as the baseline. Two cost levers dominate: **Spot VMs** (evictable capacity, discounts often ~60-90% off pay-as-you-go, 30-second eviction notice via scheduled events — fine for stateless batch, fatal for single-instance stateful) and **reservations/savings plans** for steady state (commit 1 or 3 years).

Availability mechanics: regions expose 3 availability zones; within a zone-less or zonal design, availability sets give fault domains (~2-3 typical, up to 5 region-dependent) and update domains (5 by default, up to 20). VMSS has two orchestration modes: **Uniform** — identical instances, one provisioning model, scales to ~1000 instances (some marketplace-image cases historically lower) — and **Flexible** — treats VMs as first-class (mixed sizes, attach existing VMs, spread across zones/fault domains like availability sets), the recommended default for new deployments, also up to ~1000 VMs. Upgrade policies differ accordingly: automatic/rolling/manual for Uniform; Flexible manages updates per-VM.

### App Service

You deploy *code* (or a container) into a plan whose SKU fixes everything: Basic (~1-3 instances, no slots), Standard (up to ~10 instances, 5 slots), PremiumV3/MV3 (up to ~20-30 instances depending on SKU, ~20 slots), Isolated/ASE for single-tenant. Production behaviors that matter:

- **Always On**: without it the worker process idles out and cold requests eat ~tens-of-seconds JIT warmup; Functions on Dedicated requires it.
- **Slots**: stage/prod pairs with warm-up — swap warms the target slot before flipping routing; settings marked *slot-sticky* (connection strings, some app settings) stay with the slot, so a swap that flips code but not config produces the classic "works in staging, breaks in prod" inversion. Auto-swap exists but is discouraged for production.
- **Networking**: regional VNet integration routes egress into your VNet; private endpoints give inbound private access; nothing arbitrary runs alongside your app — no daemons, no sidecars.

### Container Apps

An **environment** (shared networking boundary backed by `Microsoft.App`) hosts apps. Each app deploys **revisions** — immutable snapshots of container config, image, and scale rules; keep ~100 inactive revisions by default. Single-revision mode does zero-downtime rollouts (old revision keeps traffic until the new one passes startup/readiness probes and matches replica counts); multiple-revision mode enables traffic splitting percentages for blue-green and canary. Scaling is KEDA all the way down:

| Knob | Default | Range/notes |
|---|---|---|
| Min replicas | 0 | scale-to-zero default |
| Max replicas | 10 | configurable to 1000 |
| Polling interval | 30 s | non-HTTP/TCP rules |
| Cool-down period | 300 s | last event → scale to min |
| Scale-up stabilization | 0 s | immediate |
| Scale-down stabilization | 300 s | prevents flapping |
| Scale-up steps | 1, 4, 8, 16, ... | doubling to configured max |

Rules: HTTP concurrency, TCP connections, or custom scalers (Service Bus queue length, Event Hubs, Kafka, Redis, CPU/memory). Documented limitations that bite: **no vertical scaling** (change size = new revision), replica counts are targets not guarantees, and Dapr actor state doesn't tolerate scale-to-zero. Jobs handle batch/event-driven one-shot workloads; dynamic sessions provide ephemeral sandboxes (the AI code-interpreter pattern). Platform SLA 99.95%.

### AKS

Control plane is free; **Standard tier** (~$0.10/hr) buys the 99.95% API-server uptime SLA; Premium adds longer-term support. Version policy: N-2 supported (three GA minors), with an extra **platform-support** window at N-3 (Microsoft supports the platform, not Kubernetes components). Upgrades must respect skew — you cannot skip more than one minor version per hop, so laggard clusters face sequential upgrades; plan cadence quarterly or fall behind compounding. Node pools split **system** (CoreDNS, tunnels, metrics) from **user** pools; scaling via cluster-autoscaler, or node autoprovisioning (Karpenter) which provisions right-sized nodes per pending-pod requirements; AKS Automatic bundles these defaults plus KEDA.

Networking is where designs die: **kubenet** bridges pods (pod IPs virtual, conserve VNet space, ~110 pods/node default) but needs route-table management; **Azure CNI Overlay** gives pods routable overlay IPs without consuming subnet addresses (250 pods/node default) — the current sane default; plain **Azure CNI** assigns every pod a real VNet IP — great for direct reachability, catastrophic in small subnets because pod IPs exhaust and new nodes can't join (pods Pending with "FailedCreatePodSandBox" is the signature). Cilium (eBPF) is available as the dataplane option on CNI Overlay. Workload identity (federated credentials), Key Vault CSI driver, and managed NGINX/app-routing ingress round out the standard add-on set.

### Capacity arithmetic interviewers actually want

Little's Law applies everywhere: steady 200 rps at 150 ms p50 means ~30 concurrent requests; with 64-concurrency HTTP rules that's 1 replica steady-state — provision 3-4x for bursts. For VMSS: peak-rps x per-instance-capacity ÷ utilization-target = instance count, then verify against quota (regional vCPU quotas are the silent blocker on scale-out, not the scale rule).

---

## Build it from scratch

A replica calculator reproducing Container Apps' documented scaling behavior:

```python
# untested sketch — KEDA-style replica math incl. stabilization & cool-down
import math, time

class ReplicaCalculator:
    def __init__(self, target: float, min_r: int = 0, max_r: int = 10,
                 down_stabilization_s: int = 300, cooldown_s: int = 300):
        self.target, self.min_r, self.max_r = target, min_r, max_r
        self.down_win, self.cooldown = down_stabilization_s, cooldown_s
        self.replicas, self.last_event, self.pending_down = 0, None, None

    def tick(self, metric_value: float, now: float) -> int:
        if metric_value > 0:
            self.last_event = now
        desired = self.min_r
        if metric_value > 0 or now - (self.last_event or now) < self.cooldown:
            # scale-up: ceil division, immediate (0 s stabilization)
            wanted = math.ceil(metric_value / self.target) if metric_value else 1
            desired = max(self.min_r, min(wanted, self.max_r))
            self.pending_down = None
        else:
            # scale-down: candidate must persist for the stabilization window
            if self.pending_down is None or self.pending_down[0] != desired:
                self.pending_down = (desired, now)
            elif now - self.pending_down[1] >= self.down_win:
                desired = self.pending_down[0]
                self.pending_down = None
            else:
                return self.replicas
        self.replicas = desired
        return desired

calc = ReplicaCalculator(target=50.0)              # 50 concurrent reqs per replica
for m, t in [(120, 0.0), (120, 10.0), (10, 400.0), (0, 900.0)]:
    print(f"metric={m} t={t}s -> replicas={calc.tick(m, t)}")
# 120/50 -> 3 replicas instantly; drop to 10 waits out 300 s stabilization;
# zero traffic holds replicas until the 300 s cool-down expires, then -> min
```

The point: scale-down is deliberately slower than scale-up everywhere on this platform — stabilization windows prevent flapping, and any custom autoscaler you build should copy that asymmetry.

## How it's done in production

Reference patterns: landing-zone spoke per workload with App Service/CA VNet-integrated and dependencies behind private endpoints; VMSS Flexible with zones for legacy lift-and-shift plus reservations covering baseline; Container Apps for the majority of new microservices (revisions + traffic splitting as the deploy mechanism, jobs for batch, Dapr where pub/sub abstractions pay); AKS reserved for genuine Kubernetes needs — Standard tier, system/user pool separation, CNI Overlay, quarterly upgrade cadence automated through maintenance windows, workload identity everywhere, KEDA for event-driven consumers, node autoprovisioning for heterogeneous GPU/CPU mixes.

| Symptom | Cause | Fix |
|---|---|---|
| Pods Pending with FailedCreatePodSandBox | Subnet IP exhaustion under plain Azure CNI (every pod takes a VNet IP) | Move to CNI Overlay, or expand subnet; monitor subnet free IPs as an SLO |
| Staging-tested change breaks prod immediately after release | Slot swap flipped code but connection strings were slot-sticky | Audit sticky-settings list; make config explicit env-injected, not slot-bound |
| CA app thrashes 0→1→0 constantly | Scale-to-zero on latency-sensitive endpoint + 300 s cooldown mismatch | Set minReplicas=1 (idle billing) or accept cold-start latency consciously |
| VMSS won't grow past N instances despite autoscale rules | Regional vCPU quota exhausted, not a scale-rule problem | Check quota before debugging rules; request increase proactively in IaC |
| AKS upgrade blocked mid-chain | Skipped more than one minor version (not allowed) | Sequential hops N→N+1→N+2; automate cadence to never exceed N-2 |
| Spot instances kill nightly batch halfway | Eviction during 30-second-notice window | Checkpoint/resume logic, max-price + eviction-rate alerts, fallback to regular capacity |

---

## Tradeoffs & when NOT to use it

- **Don't pick AKS by default.** For a team shipping 3-10 services without dedicated platform engineering, Container Apps delivers revisions, KEDA scaling, ingress, and managed certs with a fraction of the operational surface; AKS's cost isn't the ~$0.10/hr control plane, it's upgrades, security posture, RBAC design, and observability you now own.
- **Don't use App Service when you need sidecars or arbitrary processes.** The runtime contract is strict: one app, no daemons, no custom init; if the workload wants a sidecar proxy or background worker process, CA/AKS fit and App Service fights you.
- **Container Apps can't scale vertically** — resizing means new revision and restart; stateful workloads needing in-place resource growth belong on VMs/VMSS or AKS with careful PDBs.
- **Spot is wrong for anything stateful or latency-sensitive.** Evictions arrive on ~30-second notice; databases, single-replica queues consumers, and anything mid-write are bad tenants of spot capacity. Use it for batch, CI runners, and fault-tolerant fan-out only.
- **Availability sets are legacy glue, not strategy.** New VM designs use zones + VMSS Flexible; availability sets persist for older tooling compatibility, not because they're better (no zone spread, fixed domain counts).
- **Uniform VMSS still makes sense** for simple identical stateless fleets where per-VM customization is noise — flexible mode adds semantics (and some API behaviors) you may not need; just don't reach for uniform out of habit for mixed workloads.

---

## Interview questions

### Q1 — Pick compute services for: (a) legacy .NET Framework site, (b) bursty image-resize queue consumer, (c) 40-service microservices estate with platform team, (d) licensed Windows server app. Justify each.
**Testing:** portfolio fluency under scenario pressure.
**Answer:** (a) App Service — but note .NET Framework requires Windows plans (Flex is Linux-only); PremiumV3 for slots/scaling. (b) Container Apps with a Service Bus/KEDA scaler, min 0 max N — pay-per-use fits bursty. (c) AKS Standard: ecosystem needs (mesh, multi-tenancy, GPU pools) justify operations at that count, with node autoprovisioning. (d) Single VM (or VMware-level lift via Azure VMware if estate-scale) — containers/platforms add risk to a licensing-bound binary; keep it boring, back it with backups and Azure Update Manager.
**Follow-up trap:** *"Why not AKS everywhere for consistency?"* — consistency tax: four unrelated workloads would inherit upgrade cadence, security reviews, and on-call complexity; heterogeneity is cheaper than uniformity here.

### Q2 — Uniform vs Flexible orchestration in VMSS: mechanics and defaults?
**Testing:** whether they know the 2021+ model, not the 2016 one.
**Answer:** Uniform: all instances from one model, single provisioning flow, scales to ~1000 instances, automatic/rolling/manual upgrades, best for pure stateless fleets. Flexible: VMs are individual resources — mixed sizes, zones/fault-domain spreading like availability sets, attach/detach existing VMs, count-based SLA; recommended default for new deployments; up to ~1000 VMs. Upgrade management differs (per-VM on flexible).
**Follow-up trap:** *"Which supports availability-set-style SLA?"* — Flexible; Uniform's SLA comes from zone spread instead. Also marketplace-image instance-count caps historically differed between modes — verify current limits before quoting.

### Q3 — Explain slot-swap mechanics in App Service and two ways teams break production with them.
**Testing:** warm-up and sticky-settings depth beyond "slots = staging."
**Answer:** Swap routes production traffic to the target slot after warming it (the target boots, passes warm-up checks), then flips hostnames; settings marked deployment-slot-sticky (connection strings, handlers) travel with the slot rather than swapping. Breakages: (1) sticky config inversion — code swaps, config doesn't, so new code reads old slot's secrets; (2) cold-start masquerading as swap success — warm-up passed but first real requests JIT-load paths never exercised in staging, spiking p99 post-swap.
**Follow-up trap:** *"How do you make swaps safe?"* — exercise real dependency paths during warm-up (custom warm-up initialization), minimize sticky settings, verify config parity pre-swap, and prefer traffic-weighted strategies where supported.

### Q4 — Container Apps scale-to-zero: what actually happens on an incoming request after idle, and when must you set minReplicas=1?
**Testing:** activation path knowledge.
**Answer:** With zero replicas the revision sits in "Scale to 0" state; ingress holds the connection while KEDA/environment activates one replica (pull image if needed, start container, pass readiness) — latency spans image pull + startup, potentially seconds to tens-of-seconds for heavy images. Set minReplicas=1 when: p99 commitments exist, Dapr actors are used (scale-to-zero unsupported), or long-lived connections/websockets make reactivation disruptive. Idle replicas bill at reduced rates; zero-active bills no usage charges.
**Follow-up trap:** *"Does the HTTP scaler react within its polling interval?"* — HTTP/TCP rules don't wait on the ~30 s poller like custom scalers; they're evaluated continuously at the ingress layer — but activation of a stopped revision still costs startup time regardless.

### Q5 — AKS version support and upgrade constraints — walk through a cluster two minors behind today.
**Testing:** operational currency on the exact thing that bites teams annually.
**Answer:** Supported window: N-2 (three GA minors); falling further puts the cluster into platform-support (N-3: Azure-platform issues only, no Kubernetes component fixes). Upgrades can't skip more than one minor: from N-2 to current requires sequential hops with control-plane-then-node-pool per hop, surge/max-surge nodes controlling disruption, plus API-breakage review between minors. Consequence: quarterly cadence minimum; automate via maintenance windows and canary clusters.
**Follow-up trap:** *"What breaks most during these hops?"* — deprecated APIs removed upstream (manifests/operators pinned to old versions) and Helm charts pinning images incompatible with newer kubelets; a dry-run against the next minor catches both.

### Q6 — Compare kubenet, Azure CNI Overlay, and plain Azure CNI. Which and why?
**Testing:** networking-model comprehension, the top AKS design question.
**Answer:** Plain Azure CNI: every pod gets a routable VNet IP from your subnet — direct connectivity, but subnet IP consumption explodes (nodes x max-pods addresses reserved); fine in huge address spaces, catastrophic otherwise. CNI Overlay: pods get overlay IPs not drawn from VNet subnets — VNet space conserved (~250 pods/node default), traffic still reaches private endpoints/NAT correctly; current default recommendation. Kubenet: bridge-based, route-table-managed, oldest model, lower pod-density limits (~110/node default). Cilium eBPF dataplane layers L7 policy/performance on Overlay.
**Follow-up trap:** *"When is plain CNI genuinely right?"* — workloads requiring pod IPs be directly addressable/routable by external systems or strict source-IP preservation into appliances; even then, size subnets nodes-x-maxpods with headroom or plan IP exhaustion incidents.

### Q7 — Design HA across zones for: a stateless API fleet, a PostgreSQL database, a queue consumer.
**Testing:** zone-awareness applied per service type.
**Answer:** Stateless API: VMSS Flexible/App Service/CA spread instances across zones automatically or via zone-redundant configuration; front with zone-redundant load balancer/Front Door. PostgreSQL Flexible Server: zone-redundant HA deploys synchronous standby in another zone (~99.99% SLA tier vs 99.95% same-zone). Queue consumer: run ≥2 replicas/instances with zone spread; Storage/SB queues are already zone-redundant (ZRS). Key discipline: capacity planning assumes losing one zone — headroom sized so remaining zones absorb 100%.
**Follow-up trap:** *"Your 'zone-redundant' app failed completely when a zone went down — what was missed?"* — zonal resources inside (a zonal public IP, zonal disk, single-zone backend pool) pinning the chain; redundancy must be verified end-to-end, component by component.

### Q8 — When is Spot VM usage irresponsible, and how do you run batch on spot safely?
**Testing:** eviction-model honesty.
**Answer:** Irresponsible: single-instance stateful roles, anything holding locks/leases mid-critical-section, latency-sensitive user-facing serving without fallback. Safe batch pattern: checkpointed work units (idempotent steps resumable), eviction handling via Scheduled Events (30 s notice) to drain gracefully, eviction-rate monitoring per pool, blend of spot baseline + regular-capacity ceiling, retry-on-evict at orchestrator level. Discounts commonly ~60-90% off PAYG make CI/batch/rendering near-free, which is why the discipline pays.
**Follow-up trap:** *"Eviction notice is 30 s — what do you actually do in it?"* — stop accepting new work, flush checkpoints, release leases cleanly; 30 s is enough only if the drain path is tested regularly, not discovered during the first eviction.

### Q9 — Blue-green deploy on Container Apps versus App Service slots versus Kubernetes — compare mechanisms honestly.
**Testing:** deployment-strategy transfer across platforms.
**Answer:** CA: multiple-revision mode with traffic-split percentages — true blue-green with instant rollback (re-point 100% to old revision); revision immutability guarantees config drift-free rollbacks. App Service slots: warm-up then atomic swap — simpler, but sticky-settings and shared-plan resources blur isolation; rollback is another swap. Kubernetes: no built-in blue-green — you compose Deployments+Services or use Argo Rollouts/Flagger for progressive delivery; maximum flexibility, more moving parts. CA's model is arguably the best default for small teams; K8s wins when canary analysis (metrics-driven promotion) is required.
**Follow-up trap:** *"Where does database migration fit in all three?"* — none handle schema; expand-contract migrations must be forward-compatible with both versions regardless of platform, since blue-green means two code versions hit one schema simultaneously.

### Q10 — Argue against AKS for a specific realistic workload, then argue against your own argument.
**Testing:** steel-manning both directions, senior signal.
**Answer:** Against: a 4-service Python API + worker team, no K8s experience — CA gives them revisions, KEDA, ingress, managed TLS; AKS adds upgrade ops, security hardening, RBAC, cluster observability nobody's paid to own. Counter: that team will need GPU inference soon, and CA's GPU story/workload profiles may constrain scheduling flexibility AKS offers natively; also existing company standards (policy engines, mesh, GitOps controllers) assume a cluster. Resolution: start CA, define explicit promotion criteria (GPU needs, CRD dependencies, compliance tooling) for AKS adoption — reversible decision beats speculative platform investment.
**Follow-up trap:** *"Isn't migration later expensive?"* — less expensive than operating AKS prematurely; both consume the same container images, so porting cost is mostly ingress/config plumbing, deliberately kept thin.

### Q11 — Your AKS pods sit Pending; nodes have free CPU/memory. Diagnose systematically.
**Testing:** structured debugging, not guess-shuffle.
**Answer:** Check events in order: (1) FailedCreatePodSandBox / IP allocation failures → subnet exhausted (classic CNI) or NSG blocking; (2) taints/tolerations mismatch → pods landing on tainted pools; (3) topology constraints — zone/anti-affinity rules impossible with current node spread; (4) PVC binding failures — storage class/zonal disk mismatch with node zone; (5) quota — regional vCPU or per-VM limits blocking cluster-autoscaler despite node capacity appearing free.
**Follow-up trap:** *"Cluster-autoscaler shows 'waiting for scale-up' forever."* — autoscaler requested nodes but VM provisioning failed: quota, capacity restrictions (size unavailable in zone), or SKU family restrictions — read autoscaler logs, not pod events, at that point.

### Q12 — Cost-optimize a mixed estate (VMs, App Service, CA, AKS) without SLA damage. Give the levers in priority order.
**Testing:** practical FinOps sequencing.
**Answer:** 1) Right-size from utilization data (Azure Monitor metrics over 30 days) — biggest immediate win. 2) Reservations/savings plans on steady-state VM baseline (1-3 yr commits). 3) Spot for batch/CI. 4) Scale-to-zero/min-replica tuning on CA dev/test environments; separate dev/prod subscriptions for clean budgets. 5) AKS: consolidate onto fewer larger nodes where utilization allows, autoprovisioning to kill idle node-class sprawl, scale-down of non-prod overnight. 6) Delete orphaned disks/IPs/images. Never lead with reservations before right-sizing — committing to waste locks it in for years.
**Follow-up trap:** *"Which lever do people misuse most?"* — auto-shutdown policies on prod-adjacent resources and aggressive scale-to-zero on latency-sensitive prod endpoints: cost tools applied where SLA lives; tag discipline (env=critical) prevents exactly this class of mistake.

---

## Red flags that fail you

- Recommending legacy Cloud Services or availability sets for new designs instead of VMSS Flexible + zones.
- Not knowing Flex Consumption/Container Apps require Linux (Windows constraint).
- Claiming App Service slots migrate configuration along with code by default.
- Scale-to-zero everywhere without discussing activation latency or Dapr actor exceptions.
- Quoting AKS support as indefinite, or attempting to skip multiple minor versions in upgrades.
- Plain Azure CNI in small subnets with no IP-exhaustion story.
- Treating spot evictions as rare edge cases rather than routine events needing drain logic.

---

## Cheat card

```
DIAL (control -> ops): VM > VMSS > App Service > Container Apps > (AKS = full K8s)

VMs:   families D(gen ~4GB/vCPU) E(mem ~8GB/vCPU) F(compute ~2GB/vCPU) N(GPU)
       Spot ~60-90% off · ~30 s eviction notice · batch/CI only
       zones = 3/region · avail set: FDs ~2-3(5 max region-dep) UD 5 def/20 max
VMSS:  Uniform (identical, ~1000 inst) vs Flexible (mixed sizes, zone spread,
       avail-set-like SLA) — Flexible recommended default
APPSVC: B ~3 inst/no slots · S ~10 inst/5 slots · Pv3/Pmv3 ~20-30 inst/~20 slots
        Always On or idle timeout · slot-sticky settings DON'T swap
CA:     env(Microsoft.App) > apps > immutable REVISIONS (keep ~100 inactive)
        KEDA: poll 30 s · cooldown 300 s · down-stabilization 300 s · up 0 s
        desired = ceil(metric/target) · default max 10 (configurable 1000)
        NO vertical scaling · Dapr actors != scale-to-zero · SLA 99.95%
AKS:    free ctl-plane · Standard ~$0.10/h -> 99.95% API SLA · Premium = LTS
        support N-2 (+N-3 platform-support) · upgrades skip <=1 minor per hop
        system/user node pools · CNI Overlay default (~250 pods/node)
        plain CNI = pod IPs eat subnet -> Pending pods on exhaustion
        cluster-autoscaler / Karpenter(NAP) / Automatic bundles defaults

CAPACITY: Little's Law conc = rps x lat_s · instances = peak/(cap*util-target)
          check REGIONAL vCPU QUOTA before debugging autoscale rules
HA:      stateless spread zones · PG Flexible ZRS-HA standby other zone
         size headroom to lose 1 full zone
COST ORDER: right-size -> reservations(baseline only) -> spot(batch) ->
            scale-to-zero(dev/test) -> prune orphans
```

## Sources

- [Scaling in Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/scale-app); accessed 2026-08-23
- [Azure Container Apps product page (SLA, scale-to-zero, Express) — Microsoft Azure](https://azure.microsoft.com/en-us/products/container-apps); accessed 2026-08-23
- [Update and deploy changes in Azure Container Apps (revisions) — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/revisions); accessed 2026-08-23
- [Supported Kubernetes versions in AKS (N-2, platform support) — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions); accessed 2026-08-23
- [Kubernetes Event-driven Autoscaling (KEDA) in AKS — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/keda-about); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
