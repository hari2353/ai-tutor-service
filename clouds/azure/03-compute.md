# Compute: VMs, VMSS, App Service, Container Apps, AKS

> **Track:** C-AZ Azure Atlas · **Time:** 2.0h · **Prereqs:** `C-AZ-identity`, `C-AZ-functions` · **Updated:** 2026-08-08
> **Module id:** `C-AZ-compute` · **Tags:** compute

## The 30-second version

Azure's compute stack is a ladder of decreasing control and increasing abstraction: **Virtual Machines** (full OS control, you patch it), **VM Scale Sets / VMSS** (identical VMs, fleet-managed, now mostly deployed in **Flexible orchestration mode** which mixes VM sizes and Spot/on-demand in one scale set), **App Service** (PaaS web app hosting, plan-based fixed capacity, zero container orchestration knowledge required), **Container Apps** (serverless containers on a managed Kubernetes/KEDA/Envoy substrate you never touch, scales to zero, billed per vCPU-second), and **AKS** (full Kubernetes, you own the control plane's configuration even though Azure runs the control plane's infrastructure). The decision axis that actually matters in an interview is not "which is more powerful" — AKS is always more powerful — it's **how much orchestration complexity the team is willing to own** against **how much control the workload genuinely needs**. The 2026 default pattern: stateless web apps and APIs go to App Service or Container Apps depending on whether they're already containerized; event-driven bursty workloads go to Container Apps (via KEDA scalers) or Functions; anything needing custom schedulers, service mesh, DaemonSets, or genuine multi-team platform engineering goes to AKS, increasingly **AKS Automatic** which removes most of the node-pool and control-plane tuning that used to make AKS a full-time job; and VMs/VMSS remain for lift-and-shift, licensing-locked software, or workloads that need kernel-level or GPU-passthrough control nothing above them offers. The single biggest trap for an AWS engineer: App Service's App Service Plan is a **shared capacity unit billed regardless of app count**, closer to running several apps on one EC2 Auto Scaling Group than to Lambda-style per-invocation billing — sizing it wrong either wastes money (over-provisioned plan for one small app) or throttles every app on it (under-provisioned plan for many apps).

## Why this gets asked

The interviewer has watched a team lift-and-shift a monolith onto VMs "temporarily" and never migrate off, has debugged an App Service plan where five unrelated apps shared one instance and a traffic spike on one starved the others, has explained to a platform team why AKS Automatic's opinionated defaults are a feature not a limitation for a team of four without a dedicated SRE, and has seen a Container Apps deployment silently hit its `minReplicas` cold-start tax because someone assumed "serverless container" meant "instant." They want to see you reason about the actual operational burden each option transfers to your team, not recite a features table.

---

## Lineage: past → present → future

**What came before.** Azure launched IaaS Virtual Machines in 2012 (general availability), years after AWS's EC2 (2006) had already normalized rentable compute — Azure's VM story started catching up rather than leading. Cloud Services (Web/Worker Roles, 2010) was Azure's first PaaS attempt, a clunky precursor to App Service that required a specific packaging model (`.cspkg`) and was retired in favor of App Service's simpler model. Early container orchestration on Azure was equally scattered: Azure Container Service (ACS, 2015) let you choose between Mesos, Docker Swarm, or Kubernetes as the underlying orchestrator before Kubernetes' ecosystem dominance made that choice obviously moot, and ACS was replaced outright by AKS (GA 2018) once Kubernetes had won.

**Where it stands now.** The 2026 landscape is a genuine four-way split that AWS's Fargate/App Runner/EKS/EC2 stack maps onto reasonably cleanly (see cross-cloud table below), but with real mechanical differences. **AKS Automatic** (GA in 2025, actively maturing through 2026) is Microsoft's answer to "AKS is too much to operate" — it defaults to Node Auto-Provisioning (NAP, Karpenter-based bin-packing and just-in-time node scaling), managed system node pools, and a **financially-backed pod readiness SLA** (99.9% of qualifying pod scheduling operations complete within 5 minutes). The live disagreement is "Container Apps vs. AKS Automatic" for greenfield containerized workloads — Container Apps is simpler and scales to zero, AKS Automatic gives you the real Kubernetes API surface (CRDs, operators, service mesh) with much of the operational burden removed, and reasonable engineers land on different defaults depending on whether the team already has Kubernetes expertise sitting idle. VMSS **Flexible orchestration mode** is now the default recommendation over the older Uniform mode, since Flexible allows mixing up to 5 different VM sizes (including Spot alongside on-demand) in a single scale set and integrates with Azure Load Balancer/Application Gateway the same way a plain VM does, closing a real gap that used to force teams onto individually-managed VMs for heterogeneous fleets. [VM Scale Sets orchestration modes — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-orchestration-modes) — accessed 2026-08-08.

**Where it's heading.** Expect Container Apps to keep absorbing AKS-adjacent capability (it already supports KEDA-based scaling on 60+ event sources, Dapr sidecars, and now workload profiles for GPU/dedicated-node scenarios) — moderate-to-high confidence, since Microsoft's own positioning increasingly frames Container Apps as "Kubernetes-powered without the YAML" for teams that don't need the raw API. AKS Automatic's node-auto-provisioning model (essentially Karpenter under an Azure-branded name) is the direction all three clouds are converging on for cluster autoscaling — EKS Auto Mode and GKE Autopilot are the same bet — high confidence this becomes the default AKS creation path within 1-2 years, low confidence on exact GA timelines for every regional/SKU gap that still routes teams to manual AKS today.

---

## Mental model

```
CONTROL  ───────────────────────────────────────────────►  ABSTRACTION
(you patch it)                                          (you never see a node)

  VIRTUAL MACHINE          VMSS (Flexible)        APP SERVICE       CONTAINER APPS         AKS
  ┌──────────────┐        ┌───────────────┐      ┌───────────┐    ┌───────────────┐   ┌──────────────┐
  │ full OS      │        │ fleet of VMs, │      │ PaaS web  │    │ serverless     │   │ full K8s API │
  │ you own      │───────►│ mixed sizes,  │─────►│ hosting,  │───►│ containers,    │──►│ you own the  │
  │ patching,    │        │ up to 1000    │      │ App Svc   │    │ scale to 0,    │   │ workload     │
  │ scaling      │        │ instances     │      │ Plan =    │    │ KEDA scalers,  │   │ config; Azure│
  │ manually     │        │               │      │ shared    │    │ Dapr sidecars  │   │ runs control │
  │              │        │               │      │ capacity  │    │                │   │ plane infra  │
  └──────────────┘        └───────────────┘      └───────────┘    └───────────────┘   └──────────────┘
   lift-and-shift,         heterogeneous          simple web        event-driven,       multi-team
   licensing-locked,       fleets, custom          apps/APIs,        bursty, mixed       platforms,
   GPU passthrough,        health probes,          no container      containerized       CRDs, mesh,
   kernel access           legacy workloads        knowledge         workloads           custom sched
```

---

## How it actually works

### Virtual Machines and VMSS

A VM is billed per-second by size family (Bsv2 burstable, Dv5/Dsv5 general purpose, Ev5/Esv5 memory-optimized, Fsv2 compute-optimized, NCv/NDv GPU families) plus attached managed disk cost, separate from compute. **Reserved Instances** (1-3yr commit) and **Azure Savings Plans for compute** (hourly $ commitment, flexible across VM families/regions, closer to AWS Savings Plans than to RIs) are the discount levers; unlike GCP, Azure does not apply automatic sustained-use discounts — you must actively commit.

VMSS **Flexible orchestration mode** (the 2026 default recommendation over legacy Uniform mode) supports up to **1,000 VM instances** for standard marketplace/custom images via Azure Compute Gallery, dropping to **600 instances** if using a plain managed image, and lets you mix **up to 5 different VM sizes** (including Spot instances alongside on-demand) in one scale set — this closes the gap that used to force teams onto hand-managed individual VMs for genuinely heterogeneous fleets. [VM Scale Sets overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/overview) — accessed 2026-08-08.

```bash
# untested sketch — az CLI, Flexible orchestration VMSS with mixed instance types
az vmss create \
  --name my-flex-vmss \
  --resource-group my-rg \
  --orchestration-mode Flexible \
  --instance-count 3 \
  --vm-sku Standard_D4s_v5 \
  --image Ubuntu2204 \
  --zones 1 2 3 \
  --load-balancer my-lb
```

### App Service

The **App Service Plan** is the fundamental billing/scaling unit — it's a set of VM instances of a chosen size/tier, and every app deployed to that plan **shares** its capacity. This is the trap: deploying 10 small internal tools to one Standard-tier plan means a traffic spike on tool #3 starves the other 9, because they're all sharing the same underlying instance pool, unlike Lambda/Functions where each invocation is isolated. Tiers run Free/Shared (no SLA, CPU minutes capped) → Basic (manual scale, no autoscale/slots) → Standard (autoscale, 5 deployment slots) → Premium v3 (faster processors, higher memory-to-core ratio — 2x Premium v2's — VNet integration, up to 30 instances, up to 20 deployment slots) → Isolated v2 (dedicated App Service Environment, single-tenant, for the highest compliance/networking isolation requirements). Premium v3 and above support **deployment slots** for zero-downtime blue-green swaps — a slot is a fully separate live app sharing the plan's compute, and a swap exchanges routing (and warms up the target slot first) rather than redeploying code.

### Container Apps

Built on a managed Kubernetes/KEDA/Envoy/Dapr substrate you never directly touch — no `kubectl`, no node management. Billing (Consumption plan, mid-2026 East US rates): **~$0.000024/vCPU-second and $0.000003/GiB-second active**, dropping to **~$0.000008/vCPU-second and $0.000001/GiB-second idle** for replicas kept warm below `minReplicas` but not currently handling traffic, plus **$0.40 per million requests** after a 2 million/month free allotment, with a monthly free grant of **180,000 vCPU-seconds and 360,000 GiB-seconds** per subscription. [Container Apps billing — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/billing) — accessed 2026-08-08. Scaling is entirely KEDA-driven: HTTP concurrency, CPU/memory, or any of **60+ event-source scalers** (Service Bus queue depth, Cosmos DB change feed, Kafka topic lag, cron schedule) can each trigger scale-out, and `minReplicas: 0` gives true scale-to-zero — the first request after idle pays a cold-start tax proportional to image size and startup work, mechanically the same tradeoff as Cloud Run and structurally different from Fargate, which has no scale-to-zero concept at all.

```yaml
# untested sketch — Container Apps scale rule via Bicep-adjacent YAML shape
scale:
  minReplicas: 0
  maxReplicas: 10
  rules:
    - name: queue-based-scale
      custom:
        type: azure-servicebus
        metadata:
          queueName: orders
          messageCount: "5"    # scale out one replica per 5 queued messages
```

**Workload profiles** (Consumption vs. Dedicated) let you pin specific container apps to dedicated, non-shared compute (including GPU-enabled profiles) within the same Container Apps environment, closing the gap for workloads needing predictable performance without jumping to full AKS.

### AKS and AKS Automatic

Standard AKS gives you the full Kubernetes API on a control plane Azure operates (patches, upgrades the control plane) while you own node pool sizing, cluster autoscaler configuration, upgrade orchestration for nodes, and everything above the API server. Real numbers: **max 5,000 nodes per cluster** across all node pools, **max 100 node pools per cluster**, **max 1,000 nodes per individual VMSS-backed node pool**, and **max 5,000 managed clusters per subscription** — and as of **September 2025**, AKS began enforcing region-level **quota on managed clusters and node VM SKUs**, meaning a subscription that previously created clusters freely can now hit a quota wall that has nothing to do with the per-cluster limits above. [AKS quotas, SKUs, regions — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/quotas-skus-regions) — accessed 2026-08-08.

Pricing tiers for the **control plane itself** (separate from node VM cost, which bills as standard VMs): **Free tier** ($0/hr, no SLA, recommended max ~10 nodes, fine for dev/learning only), **Standard tier** (~$0.10/cluster/hour, 99.95% uptime SLA), **Premium tier** (~$0.60/cluster/hour, adds Long Term Support for extended Kubernetes version support windows). [AKS pricing tiers — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/free-standard-pricing-tiers) — accessed 2026-08-08.

**AKS Automatic** (GA 2025, maturing through 2026) removes most of that operational surface: **Node Auto-Provisioning (NAP)**, Karpenter-based, watches for unschedulable ("pending") pods and provisions right-sized nodes just-in-time rather than requiring pre-configured node pools and a separate cluster autoscaler — mechanically the same bet EKS Auto Mode and GKE Autopilot are making. It ships with a **financially-backed pod readiness SLA**: 99.9% of qualifying pod scheduling/node-provisioning operations complete within 5 minutes. Managed system node pools run cluster add-ons on isolated "surge" capacity so system workloads can't starve user workloads, and NAP-enabled clusters mark the default node pool `mode: user` specifically to stop pending system pods from triggering unwanted user-node scale-up. [AKS Automatic managed system node pools — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/automatic/aks-automatic-managed-system-node-pools-about) — accessed 2026-08-08; [Node auto-provisioning overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/node-auto-provisioning) — accessed 2026-08-08.

### Cross-cloud mapping

| AWS | Azure | GCP | Watch out |
|---|---|---|---|
| EC2 | Virtual Machines | Compute Engine | GCP applies automatic sustained-use discounts; Azure requires an explicit Reservation/Savings Plan commit |
| ASG | VM Scale Sets (Flexible mode) | Managed Instance Group | Flexible-mode VMSS mixes up to 5 VM sizes + Spot in one set, closer to a heterogeneous fleet than a classic ASG |
| Elastic Beanstalk | App Service | App Engine | App Service Plan = shared capacity across every app on it; sizing it is a fleet decision, not a per-app one |
| Fargate / App Runner | Container Apps | Cloud Run | Fargate has no scale-to-zero; Container Apps and Cloud Run both do, and both pay a cold-start tax on the first post-idle request |
| EKS | AKS / AKS Automatic | GKE / GKE Autopilot | All three converged on Karpenter-style just-in-time node provisioning as the 2025-2026 default (EKS Auto Mode, AKS Automatic NAP, GKE Autopilot) |

---

## Build it from scratch

Minimal Container Apps deployment showing the scale-to-zero + KEDA shape end to end, matching what a lab under `labs/bicep/03-compute/` would exercise:

```bash
# untested sketch — az CLI, Container Apps Consumption plan with scale-to-zero
az containerapp env create \
  --name my-env \
  --resource-group my-rg \
  --location eastus

az containerapp create \
  --name my-api \
  --resource-group my-rg \
  --environment my-env \
  --image myregistry.azurecr.io/my-api:latest \
  --target-port 8080 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 10 \
  --scale-rule-name http-scale \
  --scale-rule-type http \
  --scale-rule-http-concurrency 50
```

The mechanical shape: `minReplicas 0` means the environment tears down the last replica after an idle window, `scale-rule-http-concurrency 50` tells KEDA's HTTP scaler to add a replica once average concurrent requests per existing replica exceeds 50, and the first request arriving during the zero-replica state blocks on a cold start (image pull if not cached, container start, app init) before being served — the same mechanical tradeoff as Cloud Run, and the reason latency-SLA-bound synchronous APIs on Container Apps almost always set `minReplicas >= 1`.

---

## How it's done in production

A typical production compute layout: **App Service** (Premium v3, multiple deployment slots) hosts the customer-facing monolith or a small number of well-understood services with predictable traffic, using slot-swap for zero-downtime deploys. **Container Apps** hosts newly-built microservices and event-driven workers (queue consumers, webhook processors) where scale-to-zero saves real money on spiky internal traffic. **AKS** (increasingly AKS Automatic) is reserved for the platform team's shared multi-tenant cluster running services that genuinely need CRDs, a service mesh, custom schedulers, or GPU node pools with fine-grained bin-packing control. **VMSS in Flexible mode** covers anything stateful-adjacent or licensing-locked that can't containerize cleanly (some legacy Windows/.NET Framework workloads, specialized network appliances, GPU workloads needing direct driver access outside a container runtime).

| Symptom | Cause | Fix |
|---|---|---|
| One app's traffic spike degrades unrelated apps on the same host | Multiple apps sharing one under-sized App Service Plan | Split high-traffic apps onto their own plan, or move to a higher tier with more instances; App Service Plans are a shared-fleet resource, not per-app isolation |
| Container Apps first request after idle takes multiple seconds | `minReplicas: 0` scale-to-zero cold start (image pull + container start + app init) | Set `minReplicas >= 1` for latency-SLA-bound synchronous paths, or pre-warm via scheduled traffic; accept the cold start for genuinely async/queue-driven workers |
| AKS cluster creation suddenly fails with a quota error nobody expected | Subscription hit the September-2025-introduced regional quota on managed clusters or node VM SKUs, separate from the per-cluster node limits | Request a quota increase for the specific cluster/SKU quota in that region; this is a newer gate teams built before late 2025 often don't know exists |
| AKS pods stuck `Pending` for minutes during a traffic spike | Cluster autoscaler (or NAP) waiting on new node provisioning, node image pull, or hitting the region's VM SKU capacity | For AKS Automatic, this is covered by the pod-readiness SLA (99.9% within 5 min); for manual AKS, pre-scale node pools ahead of known traffic patterns or add a second VM SKU as a fallback pool |
| VMSS Flexible-mode deployment fails past a few hundred instances using a plain managed image | Managed-image-based VMSS caps at 600 instances vs. 1,000 for Compute-Gallery/marketplace images | Migrate the custom image into Azure Compute Gallery to unlock the higher 1,000-instance ceiling |
| Deployment slot swap on App Service causes a brief spike in errors despite "zero-downtime" swap | Swap didn't wait for the target slot's warm-up (custom warm-up path/health check not configured) before routing traffic | Configure `applicationInitialization` warm-up in the slot settings so the swap only routes traffic once the target slot responds healthy |

---

## Tradeoffs & when NOT to use it

- **Don't default to AKS because it's "the real Kubernetes."** A four-person team without dedicated platform engineering will spend more time operating AKS (even Automatic) than the workload is worth if Container Apps or App Service would have done the job — AKS's power is a cost, not a free upgrade.
- **Don't put a latency-SLA-bound synchronous API on Container Apps with `minReplicas: 0`.** Scale-to-zero economics and a hard p99 latency guarantee are structurally in tension, same as Azure Functions Consumption; either pay for a warm floor or accept the cold-start risk.
- **Don't share an App Service Plan across unrelated apps with independent, unpredictable traffic profiles.** It's shared fleet capacity, not per-app isolated billing — noisy neighbors are a real, frequently-hit failure mode.
- **Don't reach for VMs/VMSS by default for anything that can containerize cleanly.** The operational tax of OS patching, security baseline management, and manual scaling logic is real and avoidable; VMs are the right call specifically when something needs kernel access, unsupported licensing models, or hardware passthrough nothing above them offers.
- **Don't assume Container Apps' 60+ KEDA scalers cover every event source you need.** It's deep within scalers KEDA supports but isn't a universal integration layer the way Lambda's ~200+ native event sources are; verify the specific scaler exists before committing to the design.
- **Don't run AKS Free tier for anything production-adjacent.** No SLA and a recommended 10-node cap make it explicitly a dev/learning tier, not a cost-optimization for small production clusters.

---

## Interview questions

### Q1 — Walk through Azure's compute options from most to least control, and where you'd draw the line for a new containerized microservice.
**Testing:** whether the control-vs-abstraction axis is understood as the actual decision driver.
**Answer:** VMs (full OS control) → VMSS (fleet-managed VMs) → App Service (PaaS, plan-based shared capacity) → Container Apps (serverless containers, scale-to-zero, KEDA-driven) → AKS (full Kubernetes API, Azure runs control-plane infra only). For a new containerized microservice with no need for CRDs, service mesh, or custom scheduling, Container Apps is the default: no cluster to operate, scale-to-zero for cost, KEDA scalers cover most event-driven triggers. AKS only enters if the team already runs a shared platform cluster or the workload genuinely needs raw Kubernetes API access.
**Follow-up trap:** *"What if the team already operates an AKS cluster for other services?"* — then adding one more service to the existing cluster is usually cheaper operationally than standing up a second compute paradigm (Container Apps) purely for this one service; the "default to Container Apps" answer assumes no existing platform investment, and a good answer says so explicitly.

### Q2 — Explain why deploying five unrelated apps to one App Service Plan is risky, and how you'd fix it.
**Testing:** the shared-capacity model that trips people coming from a per-function/per-container billing mental model.
**Answer:** An App Service Plan is a set of provisioned VM instances; every app deployed to it shares that instance pool's CPU/memory. A traffic spike on one app competes directly for the same resources as the other four, unlike Lambda-style isolated-per-invocation billing. Fix: split apps with independent or unpredictable traffic profiles onto separate plans, or move genuinely bursty apps to Container Apps where scaling is per-app and billing is per-execution.
**Follow-up trap:** *"Doesn't Standard/Premium tier autoscaling fix this?"* — autoscaling adds more instances to the *whole plan*, which does help, but it scales for the aggregate load of all apps on the plan, not selectively for the one app spiking — a genuinely isolated-scaling requirement still points to separate plans or a different compute option entirely.

### Q3 — What's the real difference between VMSS Flexible orchestration mode and the legacy Uniform mode?
**Testing:** currency on the 2026-recommended default and the mechanical reason it matters.
**Answer:** Uniform mode requires every instance in the scale set to be identical (same VM size/image), managed as a single logical unit through the VMSS-specific API. Flexible mode allows mixing up to 5 different VM sizes (including Spot alongside on-demand) within one scale set, treats each instance more like an individually-addressable VM under shared scale-set management, and integrates with standard Load Balancer/Application Gateway backend pools the same way individual VMs do. Flexible is the 2026-recommended default specifically because it closes the heterogeneous-fleet gap that used to force teams onto hand-managed individual VMs.
**Follow-up trap:** *"Does Flexible mode support every feature Uniform mode has?"* — no, some legacy features (certain rolling-upgrade automation paths, specific extension sequencing behaviors) are more mature in Uniform mode; verify feature parity for a specific requirement before assuming Flexible is a strict superset.

### Q4 — A team wants Container Apps for a customer-facing synchronous API needing sub-300ms p99. Design it and name the cost tradeoff.
**Testing:** the same scale-to-zero-vs-latency-SLA tension tested in the Functions module, applied to Container Apps.
**Answer:** Set `minReplicas >= 1` (or higher, based on expected concurrent load) so the app never scales to zero and never pays a cold-start tax on the customer-facing path; scale-out rules (HTTP concurrency or CPU) handle traffic growth above the warm floor. The cost tradeoff: `minReplicas >= 1` bills the idle rate (~$0.000008/vCPU-second, ~$0.000001/GiB-second) continuously for at least one replica even at zero traffic, forfeiting the pure scale-to-zero economics that make Container Apps attractive for bursty internal workloads.
**Follow-up trap:** *"Could workload profiles (Dedicated) help here instead?"* — Dedicated workload profiles give predictable, non-shared compute (useful for GPU or performance-sensitive workloads) but don't inherently solve cold start any differently than a Consumption-plan app with `minReplicas >= 1`; the fix for cold-start-sensitive latency SLAs is the warm-floor setting, not the profile type.

### Q5 — Explain AKS Node Auto-Provisioning (NAP) and how it changes what a platform team has to operate compared to classic AKS.
**Testing:** whether the Karpenter-style just-in-time provisioning mechanism is understood, not just the marketing name.
**Answer:** Classic AKS requires pre-configuring node pools (VM SKU, min/max size) and a cluster autoscaler that scales within those pre-defined pools. NAP instead watches for unschedulable ("pending") pods and provisions right-sized nodes just-in-time based on actual pending-pod resource requirements, without requiring pre-configured node pool shapes — the same architectural bet as Karpenter on EKS. This removes the "guess the right node pool SKU mix ahead of time" operational burden; AKS Automatic bundles NAP by default along with managed system node pools and a financially-backed pod-readiness SLA (99.9% within 5 minutes).
**Follow-up trap:** *"Does NAP eliminate the need to think about node pools at all?"* — no, you still configure constraints via `AKSNodeClass` (allowed VM families, disk types, network settings) that bound what NAP is allowed to provision; it removes pre-sizing guesswork, not configuration entirely.

### Q6 — A subscription that has created AKS clusters freely for years suddenly can't create a new one. What changed, and how do you diagnose it?
**Testing:** currency on the September 2025 AKS quota rollout, a genuinely recent and easy-to-miss change.
**Answer:** Starting September 2025, AKS began enforcing region-level quota on both the number of managed clusters and the specific node VM SKUs a subscription can use — separate from the well-known per-cluster limits (5,000 nodes/cluster, 100 node pools/cluster). A subscription that never hit those older per-cluster ceilings can still be blocked by the newer managed-cluster or VM-SKU quota. Diagnose by checking the specific quota error against the AKS quota documentation rather than assuming it's the familiar node-count limit.
**Follow-up trap:** *"Is this quota raisable the way a support-ticket quota increase usually works?"* — yes, unlike Azure RBAC's hard 4,000-role-assignment ceiling, AKS managed-cluster/SKU quota is a standard raisable Azure quota via support request, but the request needs to specify the right quota dimension (cluster count vs. specific VM SKU family) to be actionable quickly.

### Q7 — Compare Container Apps to AWS Fargate on the one architectural property that most changes cost modeling for spiky workloads.
**Testing:** the scale-to-zero distinction, a recurring cross-cloud interview probe already tested for Cloud Run/Functions.
**Answer:** Container Apps scales to zero replicas (and to zero cost, minus any configured warm floor) during idle periods; Fargate has no scale-to-zero concept — the minimum running task count is 1 whenever the service is "on," so idle periods still bill for provisioned vCPU/memory. For genuinely spiky, low-average-utilization services, this is a large realized cost delta in Container Apps' favor, at the price of accepting cold-start latency on the first request after an idle gap.
**Follow-up trap:** *"Does App Runner close this gap on AWS?"* — App Runner supports a form of automatic pause/scale-down for idle apps, closer to Container Apps' model than Fargate's, but its cold-start and pricing mechanics differ from both; don't conflate "AWS serverless containers" as a single undifferentiated category — Fargate and App Runner behave differently here.

### Q8 — Why would a team deliberately choose AKS over Container Apps for a workload Container Apps could technically run?
**Testing:** a real "when NOT to use the simpler option" answer, not a reflexive "AKS is more powerful."
**Answer:** Legitimate reasons: the workload needs custom Kubernetes CRDs/operators (a service mesh like Istio/Linkerd with fine-grained traffic policy, a database operator managing StatefulSets with specific storage class behavior), needs DaemonSets for node-level agents, needs precise control over pod scheduling/affinity beyond what KEDA/Container Apps expose, or the team already operates AKS for other services and consolidating avoids a second compute paradigm. "AKS is more powerful" alone isn't sufficient justification given the added operational surface.
**Follow-up trap:** *"Doesn't AKS Automatic remove most of that operational surface, making this an easy default?"* — it removes node-provisioning operational burden specifically, not the cognitive and tooling overhead of the full Kubernetes API surface (RBAC, admission controllers, CRD lifecycle, upgrade coordination for the *application* layer even if node upgrades are automated) — AKS Automatic lowers the bar, it doesn't eliminate the tradeoff.

### Q9 — Design compute for a system with a stable, predictable customer-facing web tier and a bursty, unpredictable background-job tier that spikes 20x during nightly batch windows.
**Testing:** synthesizing multiple compute options into one coherent architecture rather than picking one option for everything.
**Answer:** Web tier: App Service (Premium v3) with deployment slots for zero-downtime releases — predictable load makes a fixed-capacity plan cost-efficient and slot-based deploys give safe rollouts. Background-job tier: Container Apps with `minReplicas: 0` and a queue-depth KEDA scale rule (Service Bus or Storage Queue), since the 20x nightly spike is exactly the profile scale-to-zero economics are built for — near-zero cost the other 23 hours, fast horizontal scale-out during the batch window. Mixing compute paradigms deliberately by workload shape, rather than forcing one option to cover both, is the senior signal here.
**Follow-up trap:** *"Why not run the batch tier on AKS with a horizontal pod autoscaler instead?"* — viable, but AKS's minimum footprint (at least a small always-on node pool for the control-plane-adjacent system pods, even with NAP) doesn't hit true zero-cost-when-idle the way Container Apps' Consumption plan does, making Container Apps the cheaper default for this specific 23-hours-idle/1-hour-spike shape unless the team already runs AKS for other reasons.

### Q10 — A VMSS Flexible-mode deployment using a custom managed image fails once it approaches 600 instances. Diagnose and fix.
**Testing:** the specific, easy-to-miss instance-count ceiling tied to image type.
**Answer:** Managed-image-based VMSS instances cap at 600, versus 1,000 for images distributed through Azure Compute Gallery (or standard marketplace images) — this is a documented but frequently-missed distinction, since "VMSS supports 1,000 instances" is the headline number most people remember without the image-type caveat. Fix: migrate the custom image into Azure Compute Gallery, which also brings image versioning and regional replication benefits beyond just unlocking the higher instance ceiling.
**Follow-up trap:** *"Is 1,000 instances a hard ceiling even via Compute Gallery, or can it be raised?"* — verify against current documentation near interview time; scale-set instance limits have shifted upward over Azure's history and treating any specific number as permanently fixed without checking current docs is itself a red flag in how you communicate limits.

### Q11 — Explain the deployment slot swap mechanism on App Service and one way it silently causes production errors if misconfigured.
**Testing:** the mechanical detail of "zero-downtime" swaps and the specific failure mode tied to warm-up.
**Answer:** A deployment slot is a fully separate, live instance of the app sharing the plan's underlying compute; a "swap" exchanges the routing so what was staging becomes production (and vice versa) without redeploying code, and Azure's swap operation warms up the target slot (running configured `applicationInitialization` warm-up requests) before flipping traffic — in principle giving zero-downtime deploys. Misconfiguration: if warm-up isn't configured or the app's actual startup work (cache priming, connection pool init, JIT warm-up) exceeds what Azure's default warm-up probes cover, traffic gets routed to a technically-running-but-not-actually-ready instance the moment the swap completes, producing a burst of errors or elevated latency right after what looked like a clean swap.
**Follow-up trap:** *"Does a failed swap automatically roll back?"* — App Service supports swap-with-rollback patterns (swap, verify, swap back if issues detected) but this isn't automatic by default — it requires explicit health-check-gated automation in the deployment pipeline, not something App Service does unprompted.

---

## Red flags that fail you

- Recommending AKS as the default for a small team without naming the operational cost it adds over Container Apps or App Service.
- Treating Container Apps and Azure Functions as interchangeable "serverless" options without distinguishing the container-vs-function execution model and their different scaling triggers.
- Not knowing App Service Plans are shared capacity across every app deployed to them.
- Claiming Fargate has scale-to-zero the same way Container Apps/Cloud Run do.
- Not knowing the September 2025 AKS managed-cluster/SKU quota rollout exists as a distinct gate from per-cluster node limits.
- Confusing VMSS Uniform and Flexible orchestration modes, or not knowing Flexible is the 2026-recommended default.
- Assuming a deployment slot swap is automatically zero-downtime without mentioning warm-up configuration.

---

## Cheat card

```
LADDER (control -> abstraction): VM -> VMSS -> App Service -> Container Apps -> AKS

VMSS: Flexible mode = 2026 default, mixes up to 5 VM sizes + Spot, 1000 instances
  (Compute Gallery/marketplace image) / 600 (managed image). Uniform mode = legacy,
  identical instances only.

APP SERVICE: App Service Plan = SHARED capacity across every app on it (noisy-neighbor
  risk). Tiers: Free/Shared -> Basic -> Standard (autoscale, 5 slots) -> Premium v3
  (VNet, up to 30 instances, 20 slots) -> Isolated v2 (dedicated ASE).
  Slot swap = warm target slot first, then flip routing -- misconfigured warm-up =
  errors right after "zero-downtime" swap.

CONTAINER APPS: KEDA-driven (60+ scalers), scale-to-zero via minReplicas:0.
  Pricing (mid-2026): ~$0.000024/vCPU-s + $0.000003/GiB-s active,
  ~$0.000008/vCPU-s + $0.000001/GiB-s idle, $0.40/M requests (2M free/mo),
  free grant 180K vCPU-s + 360K GiB-s/mo. Cold start on first post-idle request.
  Workload profiles: Consumption vs Dedicated (incl. GPU).

AKS: max 5000 nodes/cluster, 100 node pools/cluster, 1000 nodes/single node pool,
  5000 clusters/subscription. Control plane tiers: Free ($0, no SLA, ~10 node cap) /
  Standard (~$0.10/hr, 99.95% SLA) / Premium (~$0.60/hr, LTS).
  SEPT 2025: new region-level quota on managed clusters + node VM SKUs (separate
  from per-cluster limits) -- easy to get blocked by even with room under old limits.

AKS AUTOMATIC: NAP (Karpenter-style, just-in-time node provisioning from pending
  pods) + managed system node pools + pod readiness SLA (99.9% within 5 min).

CROSS-CLOUD: VM~=EC2/Compute Engine. VMSS~=ASG/MIG. App Service~=Beanstalk/App Engine.
  Container Apps~=Fargate,App Runner/Cloud Run (Fargate has NO scale-to-zero).
  AKS~=EKS/GKE. NAP~=Karpenter/EKS Auto Mode~=GKE Autopilot (all converged 2025-26).
```

## Sources

- [Azure Virtual Machine Scale Sets overview — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/overview) — accessed 2026-08-08
- [Orchestration modes for Virtual Machine Scale Sets — Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-orchestration-modes) — accessed 2026-08-08
- [Billing in Azure Container Apps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/container-apps/billing) — accessed 2026-08-08
- [Azure Container Apps Pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/) — accessed 2026-08-08
- [Limits for resources, SKUs, and regions in AKS — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/quotas-skus-regions) — accessed 2026-08-08
- [AKS Free, Standard, and Premium pricing tiers — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/free-standard-pricing-tiers) — accessed 2026-08-08
- [Overview of Node Auto-Provisioning (NAP) — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/node-auto-provisioning) — accessed 2026-08-08
- [Overview of AKS Automatic managed system node pools — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/automatic/aks-automatic-managed-system-node-pools-about) — accessed 2026-08-08
- [Introduction to AKS Automatic — Microsoft Learn](https://learn.microsoft.com/en-us/azure/aks/intro-aks-automatic) — accessed 2026-08-08
- [App service configure premium v3 tier — Microsoft Learn](https://learn.microsoft.com/en-us/azure/app-service/app-service-configure-premium-v3-tier) — accessed 2026-08-08
- [Azure Container Apps vs AKS: The 2026 Decision Matrix](https://www.dataa.dev/2026/05/08/azure-container-apps-vs-aks-the-2026-decision-matrix/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
- 2026-08-09 — Application Routing with Gateway API reaches GA on AKS, bringing the Kubernetes Gateway API standard to AKS ingress as an alternative to the older Ingress API ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
- 2026-08-09 — AKS Prepared Image Specification reaches public preview — pre-stages container images/init work on nodes to cut startup latency for large AI/GPU/Windows node pools ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
- 2026-08-09 — Deprecation: Nested confidential (cc_v5) VM series retires September 1, 2026 — unresized affected VMs are deallocated on that date ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
