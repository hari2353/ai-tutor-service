# Compute Engine, GKE, Autopilot, Batch

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.0h · **Prereqs:** `C-GCP-iam` · **Updated:** 2026-08-08
> **Module id:** `C-GCP-compute` · **Tags:** compute

## The 30-second version

Compute Engine's discount story has two independent, stackable layers: **sustained-use discounts (SUDs)** — automatic, no commitment, up to 30% off resources you run for more than 25% of a billing month, scaling in steps at 25/50/75/100% usage — and **committed-use discounts (CUDs)**, which require a 1- or 3-year commitment in exchange for up to 55% off (up to 70% for memory-optimized) via resource-based commitments, or 28%/46% (1yr/3yr) via the newer, more flexible spend-based **compute flexible CUDs** that work across Compute Engine, GKE, and Cloud Run without pinning you to a machine type or region. The trap: **SUDs only apply to older machine families (N1, N2, N2D, C2, M1, M2)** — newer generations (E2, C3, C4, N4, and friends) get **zero automatic sustained-use discount**, full stop; the only way to discount them is a CUD. This is a fast-moving, frequently-tested fact because it inverts the intuition that "just running things longer saves money automatically" — on modern machine families it doesn't, you have to commit. On Kubernetes: **GKE Standard** gives you full node-level control (node pools, custom machine types, DaemonSets, privileged pods) and bills you for the underlying Compute Engine instances; **GKE Autopilot** removes node management entirely and bills per-Pod resource *request* (CPU/memory/ephemeral storage, one-second increments, no minimum duration) for general-purpose workloads, switching to node-based billing plus a management premium only when a Pod explicitly requests specific hardware (GPUs, a named machine series). Every GKE cluster, Standard or Autopilot, also pays a flat **$0.10/hour cluster management fee**, partially offset by a $74.40/month free-tier credit equivalent to one free zonal Standard or Autopilot cluster.

## Why this gets asked

The interviewer has watched a FinOps review discover a fleet of C3 or E2 instances running 24/7 for a year, receiving precisely 0% sustained-use discount because nobody knew newer machine families aren't eligible, and separately has debugged a GKE Autopilot deployment where a team assumed "serverless Kubernetes" meant "cost scales with actual usage" without understanding Pod-based billing bills on *requested*, not consumed, resources — an over-requested Pod costs the same whether it's idle or maxed out.

---

## Lineage: past → present → future

**What came before.** Compute Engine launched (2013) with a pricing model built around the assumption that AWS's Reserved Instances — pay upfront or commit long-term for a discount, with no reward for simply running things for a while without committing — left money on the table for customers who ran workloads continuously but didn't want to commit years in advance. Google's answer, sustained-use discounts, shipped as an automatic, no-commitment alternative baked into on-demand pricing itself. Kubernetes on GCP started as GKE (2015) in a form that still required real node-pool management — sizing, patching, and scaling nodes was the operator's job, structurally identical to running self-managed Kubernetes just with a managed control plane, the same operational shape as EKS.

**Where it stands now.** SUDs remain automatic and commitment-free, but Google has **not extended them to its newer machine generations** — the SUD-eligible list is frozen at N1/N2/N2D/C2/M1/M2/sole-tenant nodes and GPUs on N1, while E2, C3, C3D, C4, C4A, C4D, N4, N4D, N4A, H3, H4D, Z3 and other current-generation families get no automatic discount at all. [Sustained use discounts — Google Cloud docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts) — accessed 2026-08-08. CUDs split into **resource-based** (pin a specific machine type/region/quantity, up to 55%/70% off, billed for the committed resources whether used or not) and **compute flexible CUDs** (spend-based, no machine-type/region pinning, 28% at 1 year and 46% at 3 years for most general-purpose families, extending across Compute Engine, GKE, *and* Cloud Run spend from one commitment). [About commitments and CUDs — Google Cloud docs](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview) — accessed 2026-08-08. GKE Autopilot (GA 2021) is the current default recommendation for new clusters — Google's own guidance steers new workloads toward Autopilot first, Standard only when a specific need (DaemonSets, privileged workloads, very fine-grained node control, certain GPU/TPU configurations) requires it. The live disagreement: Autopilot's Pod-based billing is simpler to reason about but punishes over-requesting resources directly and immediately in a way Standard's node-bin-packing model can partially absorb across a shared node pool; teams with tightly-tuned resource requests do better on Autopilot, teams that historically over-request "to be safe" often find Standard cheaper until they fix their requests.

**Where it's heading.** Compute flexible CUDs extending across Compute Engine, GKE, *and* Cloud Run from a single spend-based commitment is Google's clear direction — consolidating discount management away from per-service, per-machine-type resource commitments toward one flexible spend commitment an organization manages centrally — high confidence, since this is already how Google frames CUDs as the forward path. Whether SUD eligibility ever expands to newer machine families is genuinely uncertain; Google has had years to add E2/C3/C4 to the SUD list and hasn't, which reads as a deliberate choice to push customers toward committing rather than rewarding uncommitted longevity on current-generation hardware — low-to-moderate confidence this changes, treat it as durable for interview purposes but verify before quoting as permanent.

---

## Mental model

```
COMPUTE ENGINE DISCOUNT STACK (two independent layers, can combine)
┌────────────────────────────────────────────────────────────────────┐
│ SUSTAINED USE DISCOUNT (SUD) — automatic, NO commitment            │
│   Eligible: N1, N2, N2D, C2, M1, M2, sole-tenant nodes,             │
│             GPUs attached to N1 only                                │
│   NOT eligible: E2, C3/C3D, C4/C4A/C4D, N4/N4D/N4A, H3/H4D, Z3,     │
│                 T2A/T2D  ← the interview trap                       │
│   Max 20% (N2/N2D/C2) or 30% (N1/M1/M2/f1-micro/g1-small)          │
│   Ramps at usage thresholds: 25% → 50% → 75% → 100% of the month   │
├────────────────────────────────────────────────────────────────────┤
│ COMMITTED USE DISCOUNT (CUD) — 1yr or 3yr commitment, billed       │
│   whether used or not, cannot cancel after purchase                │
│   RESOURCE-BASED: pin machine type + region + quantity             │
│     up to 55% (most families) / up to 70% (memory-optimized)       │
│     + OS license commitments: SLES up to 79%, RHEL up to 20%       │
│   COMPUTE FLEXIBLE (spend-based): no pinning, works across          │
│     Compute Engine + GKE + Cloud Run from ONE commitment            │
│     general purpose: 28% (1yr) / 46% (3yr)                         │
│     memory-optimized (M1-M4): 0% (1yr, no discount!) / 63% (3yr)   │
└────────────────────────────────────────────────────────────────────┘

GKE STANDARD vs AUTOPILOT
  STANDARD: you manage node pools (machine type, size, autoscaling
    bounds). Billed for underlying Compute Engine instances — SUD/CUD
    apply exactly as they would to any Compute Engine VM.
    + $0.10/hr flat cluster management fee.

  AUTOPILOT: no node management at all.
    General-purpose Pods → POD-BASED billing: charged for what the Pod
      REQUESTS (CPU/memory/ephemeral storage), 1-second increments, no
      minimum. Idle-but-requested capacity still costs money.
    Pods requesting specific hardware (GPU, named machine series) →
      NODE-BASED billing: Compute Engine price + Autopilot management
      premium, billed for the WHOLE node Autopilot provisions to fit
      the request (may be larger than what you asked for).
    + $0.10/hr flat cluster management fee (same as Standard).
    Free tier: $74.40/month credit ≈ one free zonal Standard OR
      Autopilot cluster/month, credit only applies to zonal/Autopilot,
      never to regional cluster fees or compute charges.
```

---

## How it actually works

### Sustained-use discounts: the ramp, mechanically

SUDs apply automatically to eligible resources used for more than 25% of a billing month, with the discount ramping at four thresholds — 25%, 50%, 75%, 100% — so a resource run for exactly half the month gets roughly half the maximum available discount, not the full rate. For a 30%-max-eligible resource (N1, M1, M2): 50% month usage → ~10% effective discount; 75% → ~20%; 100% → the full 30%. [Sustained use discounts — Google Cloud docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts) — accessed 2026-08-08. SUDs are credited automatically at month-end with no configuration required, aggregate usage across the same machine family/region even across separate VM instances (stopping and restarting a VM within the month doesn't reset the counter), and **do not apply to usage already covered by a CUD** — the two discounts don't stack on the same hour of usage; CUD coverage takes priority and SUD applies only to the remaining uncommitted usage. SUDs also explicitly exclude VMs created by App Engine and Dataflow — only Compute Engine- and GKE-created VMs qualify.

### CUDs: resource-based vs compute flexible

Resource-based commitments pin a specific machine series, region, and quantity of vCPU/memory/GPU/local-SSD/sole-tenant-node capacity; you're billed for the committed amount every month for the full term regardless of actual usage, and **cannot cancel after purchase**. In exchange: up to 55% off for most machine series, up to 70% for memory-optimized (M1/M2/M3/M4). Separate software license commitments discount premium OS images: up to 79% for SLES, up to 63% for SLES for SAP, up to 20% for RHEL. [About commitments and CUDs — Google Cloud docs](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview) — accessed 2026-08-08.

**Compute flexible CUDs** are the more forgiving option: a spend-based commitment (commit to a dollar amount of eligible compute spend per hour, not a specific machine type) that applies automatically across whichever eligible machine series, region, and even *service* (Compute Engine, GKE, Cloud Run) you actually use.

| Service / resource | 1-year | 3-year |
|---|---|---|
| C2, C2D, C3, C3D, C4, C4A, C4D, E2, N1, N2, N2D, N4, N4D, N4A | 28% | 46% |
| C4N | 28% | 54% |
| H3, H4D | 17% | 38% |
| M1, M2, M3, M4 (memory-optimized) | **no discount** | 63% |
| Local SSD disks | 28% | 46% |
| Sole-tenancy premium | 28% | 46% |
| GKE (Standard and Autopilot) | 28% | 46% |

The memory-optimized row is a real trap: a **1-year compute flexible commitment on M-series VMs gives you zero discount** — spend burns down the commitment with no benefit at all, and only a 3-year term unlocks the 63% rate. [About commitments and CUDs — Google Cloud docs](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview) — accessed 2026-08-08.

### GKE Autopilot billing, mechanically

```yaml
# untested sketch — a Pod spec that determines Autopilot's billing path
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: api
    resources:
      requests:
        cpu: "2"        # billed: 2 vCPU-seconds per second this Pod runs
        memory: "4Gi"    # billed: 4 GiB-seconds per second this Pod runs
      limits:
        cpu: "2"
        memory: "4Gi"
  # No accelerator/machine-series selector -> Pod-based billing.
  # Add nodeSelector/compute class requesting a GPU or specific machine
  # series -> Autopilot switches to NODE-based billing: you pay for the
  # entire node it provisions to fit the request, not just what you asked
  # for, plus a management premium on top of standard Compute Engine price.
```

Autopilot bills only Pods in `Running` or `ContainerCreating` state — Pods waiting to be scheduled or already terminated aren't charged, and system DaemonSet Pods, OS overhead, and unallocated node space are never billed to you, which is the actual cost advantage over Standard's model of paying for whatever capacity a node pool provisions regardless of bin-packing efficiency. [GKE pricing — Google Cloud docs](https://cloud.google.com/kubernetes-engine/pricing) — accessed 2026-08-08.

---

## Build it from scratch

Minimal cost-aware GKE Autopilot deployment plus a resource-based CUD purchase for a steady-state Compute Engine fleet.

```bash
# untested sketch — GKE Autopilot cluster, general-purpose Pod-based billing
gcloud container clusters create-auto my-autopilot-cluster \
  --region=us-central1

kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: gcr.io/my-project/order-api
        resources:
          requests:
            cpu: "500m"      # tuned tight -- Autopilot bills exactly this
            memory: "512Mi"
EOF

# untested sketch — resource-based CUD for a steady, predictable N2 fleet
gcloud compute commitments create my-3yr-commitment \
  --region=us-central1 \
  --plan=THREE_YEAR \
  --resources=vcpu=64,memory=256GB \
  --type=general-purpose
```

---

## How it's done in production

A mature GCP compute footprint: steady-state, predictable workloads on older-generation-eligible machine families (N2, N1) or explicitly committed via resource-based CUDs on newer families since SUDs won't help there; bursty or hard-to-predict spend covered by compute flexible CUDs rather than resource-based commitments, since flexible CUDs don't lock in a machine type the team might migrate away from mid-term; GKE Autopilot as the default for new services with tightly-specified resource requests (validated against actual usage via GKE's own recommendation tooling), GKE Standard reserved for workloads with a specific documented need Autopilot can't meet.

| Symptom | Cause | Fix |
|---|---|---|
| A fleet of C3 or E2 instances has run 24/7 for a year with zero sustained-use discount applied | Newer machine families (E2, C3-and-later generations) are not on the SUD-eligible list at all | Purchase a resource-based or compute flexible CUD for that steady-state fleet; SUD will never apply regardless of runtime duration on these families |
| A 1-year compute flexible CUD on memory-optimized VMs shows no cost reduction | Compute flexible CUDs give 0% discount on M-series for 1-year terms by design; only 3-year terms unlock the 63% rate | Either commit to 3 years if the workload is genuinely long-lived, or use a resource-based commitment instead for a shorter, machine-type-pinned discount |
| GKE Autopilot costs are higher than expected for a workload with modest actual CPU/memory use | Pods are over-requesting resources (a common lift-and-shift habit from node-based capacity planning); Autopilot bills the request, not actual consumption | Right-size resource requests using GKE's workload recommendation tooling against real utilization data; Autopilot rewards accurate requests directly |
| A CUD commitment is underutilized and the team wants to reduce the bill | Resource-based commitments are billed for the full committed amount regardless of usage and cannot be canceled | Look into merging/splitting or upgrading the commitment term (supported operations) rather than assuming cancellation is possible; plan future commitments more conservatively |
| A workload requesting a specific GPU type on GKE Autopilot costs far more than the equivalent Pod-based estimate suggested | Requesting specific hardware switches Autopilot from Pod-based to node-based billing — you pay for the whole node provisioned (which may exceed the request) plus a management premium | Confirm whether the general-purpose Pod-based compute classes (Balanced, Scale-Out) can meet the requirement before reaching for hardware-specific selectors; if specific hardware is genuinely required, budget for full-node billing plus premium, not per-Pod-request pricing |
| SUD credits appear lower than expected after moving a project between Cloud Billing accounts | Sustained resource usage time resets to zero on the new billing account; it isn't carried forward | Time billing account changes for the first day of a month if maximizing SUD credit matters, and expect a temporary dip in discount rate immediately after any such move |

---

## Tradeoffs & when NOT to use it

- **Don't assume "we run this 24/7" automatically means a good discount.** On any current-generation machine family (E2, C3, C4, N4, and later), it means exactly 0% automatic discount — SUD eligibility is frozen on older families, and only a CUD helps.
- **Don't purchase a resource-based CUD for a workload whose machine type or region might change within the commitment term.** You're billed for it regardless of use and cannot cancel; compute flexible CUDs exist specifically to avoid this lock-in for less predictable footprints.
- **Don't purchase a 1-year compute flexible CUD expecting a discount on memory-optimized (M-series) spend.** It gives zero discount at 1 year by design; only 3-year terms unlock any M-series benefit.
- **Don't default to GKE Standard "for control" without a concrete need Autopilot can't meet.** Google's own default recommendation is Autopilot first; Standard's operational overhead (node pool sizing, patching cadence, upgrade orchestration) is real and unnecessary for most workloads that don't need DaemonSets, privileged pods, or very specific node-level tuning.
- **Don't lift-and-shift node-based resource requests into GKE Autopilot without re-tuning them.** Pod-based billing charges exactly what's requested; habits from node-bin-packing planning (over-requesting "to be safe") translate directly into wasted spend under Autopilot in a way they didn't under Standard's shared-node-pool absorption.

---

## Interview questions

### Q1 — Explain the difference between sustained-use discounts and committed-use discounts, and which current-generation machine families get neither automatically.
**Testing:** the single most-tested compute cost fact — that SUD eligibility is frozen on older machine families.
**Answer:** SUDs are automatic, commitment-free discounts (up to 30% or 20% depending on machine family) that ramp with usage across a billing month, requiring no upfront commitment. CUDs require a 1- or 3-year commitment (resource-based, pinned to a machine type/region, up to 55-70% off; or compute flexible, spend-based, 28%/46% for most families) and are billed whether used or not. SUD eligibility is limited to N1, N2, N2D, C2, M1, M2, sole-tenant nodes, and GPUs on N1 — newer families like E2, C3, C4, N4, H3, and Z3 get **zero automatic SUD**, regardless of how continuously they run; a CUD is the only discount lever available for them.
**Follow-up trap:** *"If a team has run E2 instances 24/7 for a year, shouldn't they have accumulated some discount by now?"* — no; SUD ramping is per-month, not cumulative across months, and E2 was never SUD-eligible to begin with, so a full year of continuous E2 usage produces exactly $0 in automatic discount unless a CUD was separately purchased.

### Q2 — A team purchases a 1-year compute flexible CUD expecting savings on their memory-optimized (M2) fleet. What happens?
**Testing:** the specific memory-optimized 1-year exception, a real documented gotcha.
**Answer:** Nothing — compute flexible CUDs give 0% discount on memory-optimized machine series (M1-M4) at the 1-year term; the eligible spend still burns down the commitment amount, but with no discount applied at all. Only a 3-year compute flexible commitment unlocks a discount (63%) on memory-optimized spend.
**Follow-up trap:** *"Would a resource-based CUD avoid this problem?"* — yes; resource-based commitments offer up to 70% off memory-optimized machine series at both 1-year and 3-year terms, since the 1-year-no-discount restriction is specific to the compute flexible (spend-based) CUD model, not resource-based commitments.

### Q3 — Explain GKE Autopilot's two billing models and what determines which one applies to a given Pod.
**Testing:** the Pod-based vs node-based billing distinction and its consequence.
**Answer:** General-purpose Pods — those using the default Autopilot container-optimized platform or the Balanced/Scale-Out compute classes — are billed per Pod resource *request* (CPU, memory, ephemeral storage) in one-second increments with no minimum duration; you pay for what you request, not what a node happens to have available. Pods that request specific hardware via selectors or a hardware-specific compute class (a named GPU, a specific machine series) switch to node-based billing: Autopilot provisions a real Compute Engine node sized to fit the request (which can be larger than the request itself) and bills for the whole node plus an Autopilot management premium on top.
**Follow-up trap:** *"So is Pod-based billing always cheaper than node-based?"* — not necessarily; Pod-based billing is efficient specifically when requests are well-tuned to actual need, but node-based billing on hardware-specific workloads is unavoidable when specific accelerators are genuinely required — the comparison isn't "which is cheaper" in the abstract, it's "does the workload need specific hardware or not," which determines the billing model, not a cost-optimization choice you make directly.

### Q4 — What is the GKE cluster management fee, and does it differ between Standard and Autopilot?
**Testing:** a flat, easily-missed fee that applies uniformly regardless of cluster mode.
**Answer:** A flat $0.10 per cluster per hour, charged in one-second increments, applies to every GKE cluster — Standard or Autopilot, zonal or regional — irrespective of size or topology. The GKE free tier provides $74.40 in monthly credits per billing account (equivalent to covering one zonal Standard or Autopilot cluster's management fee for a full month), but this credit applies only to zonal and Autopilot cluster fees, never to regional cluster management fees or to any compute charges.
**Follow-up trap:** *"Does the free tier credit cover a regional cluster's management fee?"* — no; the credit explicitly cannot be applied to regional cluster fees, only zonal and Autopilot clusters — a team running a single regional cluster gets no free-tier offset on the management fee at all.

### Q5 — When would you choose GKE Standard over Autopilot for a new workload?
**Testing:** the real "when NOT to use Autopilot" judgment, since Google's default guidance is Autopilot-first.
**Answer:** When the workload genuinely needs capabilities Autopilot restricts or doesn't support well: privileged containers or hostPath volume access (Autopilot enforces stricter security defaults by design), custom DaemonSets beyond what Autopilot permits, very fine-grained node-level tuning (custom kernel parameters, specific node OS configurations), or certain GPU/TPU configurations and node pool topologies that need direct node control. For the large majority of stateless-to-moderately-stateful application workloads without these specific needs, Autopilot is the better default given Google's own guidance and the operational overhead it removes.
**Follow-up trap:** *"Isn't Standard always going to be cheaper since you control bin-packing directly?"* — not necessarily; Standard's cost advantage from tighter bin-packing across a shared node pool has to be weighed against the real operational cost of managing node pools, patching, and scaling — and a team with poorly-tuned resource requests often does *worse* on Standard than on Autopilot, since Autopilot's Pod-based billing at least makes over-requesting visible and directly costly, forcing the fix, whereas Standard can mask waste inside underutilized nodes.

### Q6 — Design the compute discount strategy for a company with a steady-state core platform (constant for 3+ years) and a rapidly-evolving ML training fleet (machine types change quarterly).
**Testing:** applying resource-based vs compute flexible CUDs to two different workload shapes — a staff-level cost strategy question.
**Answer:** The steady-state core platform, if it's on an older SUD-eligible family (N2 is a common steady-state choice), can lean on SUD automatically plus a resource-based 3-year CUD for the predictable baseline capacity, capturing up to 55% off with no risk of the commitment going stranded since the machine type genuinely won't change. The ML training fleet, with machine types changing quarterly (likely across newer families like C4 or accelerator-attached instances), is a poor fit for resource-based commitments — a compute flexible CUD lets the team commit spend without pinning machine type or region, capturing 28-46% depending on term while retaining freedom to shift machine families as training hardware needs evolve.
**Follow-up trap:** *"Why not just use resource-based CUDs everywhere for the higher discount percentage?"* — the higher percentage only pays off if the committed resources are actually consumed at the committed type/region for the full term; a stranded resource-based commitment (wrong machine type after a migration, wrong region after an org restructure) is a pure loss, since it can't be canceled — compute flexible CUDs trade some discount percentage for materially lower stranding risk, which is the correct trade for volatile workloads.

### Q7 — A FinOps review finds SUD credits dropped sharply the month after a project was moved between Cloud Billing accounts. Explain why.
**Testing:** a specific, easily-missed operational detail about SUD calculation continuity.
**Answer:** Sustained resource usage time is tracked per Cloud Billing account, not per project or per VM independent of billing account. Moving a project to a new billing account resets sustained usage time to zero in the new account — Google doesn't carry forward accumulated usage time across the move — so the month of the transition (and potentially the following month, depending on timing) sees a temporary drop in the effective SUD rate as usage time re-accumulates from scratch.
**Follow-up trap:** *"Is there a way to avoid this reset entirely?"* — not entirely, but the practical mitigation Google documents is to make billing account changes on the first day of a calendar month, which at least aligns the reset with a natural SUD-calculation boundary rather than losing partial-month accumulated usage mid-cycle.

### Q8 — Compare GKE's Pod-based Autopilot billing to how Fargate bills a task, and explain why the two models produce different incentives.
**Testing:** cross-cloud synthesis connecting this module to the serverless module's Fargate discussion.
**Answer:** Fargate bills per-task based on the vCPU/memory *provisioned* for that task for however long it runs, continuously, regardless of whether the task's actual load fluctuates below its provisioned size. GKE Autopilot's Pod-based billing bills per-Pod based on the resource *request* in one-second increments with no minimum, and only while the Pod is actually Running or being created — closer in spirit but not identical, since both ultimately charge for requested/provisioned capacity rather than measured consumption, but Autopilot's finer billing granularity (one-second vs Fargate's per-second-with-one-minute-minimum for the underlying Compute Engine equivalent) and its stricter "don't get billed for unscheduled or terminated Pods" rule produce a tighter link between actual workload lifecycle and cost than Fargate's continuously-provisioned model.
**Follow-up trap:** *"Does this mean Autopilot is basically 'Cloud Run for Kubernetes' in terms of billing philosophy?"* — directionally yes in that both bill closer to actual resource commitment than to raw wall-clock provisioning, but Autopilot doesn't scale a workload to zero the way Cloud Run does — a Deployment with `replicas: 0` isn't billed, but Autopilot has no automatic "scale my Pods to zero when idle" behavior built in the way Cloud Run's request-triggered scaling does; that has to be implemented separately (e.g. via KEDA-style event-driven autoscaling) if true zero-traffic-zero-cost behavior is required on GKE.

### Q9 — Explain why resource-based CUDs cannot be canceled, and what operational discipline that requires.
**Testing:** the practical consequence of the "billed whether used or not, non-cancelable" rule.
**Answer:** A resource-based commitment is a binding financial agreement — Google prices in the discount specifically because the customer commits to paying for the resource regardless of actual usage, which is what allows the discount to be as deep as 55-70%; allowing cancellation would undermine that pricing basis. The operational discipline required: forecasting steady-state capacity conservatively before committing (better to under-commit and pay standard/SUD rates for overflow than over-commit and strand spend), preferring compute flexible CUDs for anything with real uncertainty in machine type or region, and using Google's own commitment-merge/split/upgrade tooling to adjust exposure within the constraints the platform does allow rather than assuming any form of cancellation is possible.
**Follow-up trap:** *"If a team over-commits and can't cancel, is there truly no recourse at all?"* — commitments can be merged, split, or have their term upgraded in some cases (e.g. extending a 1-year commitment's term), and resource-based CUDs can be shared automatically across projects under the same billing setup to absorb usage from elsewhere in the org, which is the realistic mitigation — but none of these paths refund or cancel a fundamentally over-sized commitment.

### Q10 — A workload's actual measured CPU utilization on a GKE Standard node pool is 35%. Is moving it to Autopilot with tightly-tuned requests guaranteed to reduce cost?
**Testing:** staff-level nuance — resisting an oversimplified "always migrate" answer.
**Answer:** Not guaranteed. If the 35% utilization reflects genuinely over-provisioned node pool sizing that can be right-sized on Standard just as easily (smaller machine types, better autoscaler tuning, tighter bin-packing across the shared pool), the savings might be achievable without migrating at all. Migrating to Autopilot only clearly wins when the underlying cause is per-Pod over-requesting that Standard's shared-node-pool model was masking (the waste was real but distributed across the pool in a way that didn't force a fix) — in that case Autopilot's direct request-to-bill linkage forces the right-sizing and captures the savings automatically. The honest first step is diagnosing *why* utilization is 35% — pool-level over-provisioning vs Pod-level over-requesting — before assuming a platform migration is the fix rather than a configuration fix on the current platform.
**Follow-up trap:** *"Wouldn't Autopilot at least force better hygiene even if the root cause is unclear?"* — it would, but forcing hygiene through a platform migration is a heavier, riskier intervention (application compatibility with Autopilot's stricter security defaults, potential need to remove privileged workloads or DaemonSets) than simply auditing and tuning Pod resource requests and node pool configuration on the existing Standard cluster first — migration should be a deliberate choice, not a default reflex for a utilization problem that might be fixable in place.

---

## Red flags that fail you

- Claiming a workload run continuously automatically earns a sustained-use discount, without checking whether its machine family is SUD-eligible.
- Not knowing that E2, C3, C4, N4, and other current-generation families are excluded from SUD entirely.
- Recommending a 1-year compute flexible CUD for memory-optimized workloads without knowing it yields zero discount.
- Recommending a resource-based CUD for a workload with genuine machine-type/region volatility without flagging the stranding risk.
- Describing GKE Autopilot as "no billing for idle capacity" without qualifying that Pod-based billing charges the *request*, not actual consumption.
- Recommending GKE Standard "for control" as a default without naming a specific capability Autopilot lacks.
- Not knowing the $0.10/hour flat cluster management fee applies to every GKE cluster regardless of mode.

---

## Cheat card

```
SUSTAINED USE DISCOUNTS (SUD): automatic, no commitment. Eligible ONLY:
  N1, N2, N2D, C2, M1, M2, sole-tenant nodes, GPUs on N1.
  NOT eligible: E2, C3/C3D, C4/C4A/C4D, N4/N4D/N4A, H3/H4D, Z3, T2A/T2D.
  Max 20% (N2/N2D/C2) or 30% (N1/M1/M2/f1-micro/g1-small).
  Ramps at 25%/50%/75%/100% of billing month. Doesn't stack with CUD-
  covered usage. Doesn't apply to App Engine/Dataflow VMs.
COMMITTED USE DISCOUNTS (CUD): 1yr or 3yr, billed regardless of use, NO
  cancellation.
  RESOURCE-BASED (pins machine type+region+qty): up to 55% most families,
    up to 70% memory-optimized (M1-M4). OS license commits: SLES up to
    79%, SLES-SAP up to 63%, RHEL up to 20%.
  COMPUTE FLEXIBLE (spend-based, works across Compute Engine+GKE+Cloud
    Run, no pinning): general purpose 28%(1yr)/46%(3yr). C4N 28%/54%.
    H3/H4D 17%/38%. M1-M4: 0%(1yr, NO discount!)/63%(3yr). GKE: 28%/46%.
GKE CLUSTER FEE: flat $0.10/cluster/hour, ALL clusters (Standard +
  Autopilot, zonal + regional). Free tier: $74.40/month credit = ~1 free
  zonal Standard or Autopilot cluster; NOT applicable to regional fees.
GKE AUTOPILOT BILLING: general-purpose Pods = POD-BASED (billed on
  request, 1-sec increments, no minimum, only while Running/
  ContainerCreating). Pods requesting specific hardware (GPU, named
  machine series) = NODE-BASED (whole node + management premium).
STANDARD vs AUTOPILOT: Standard = full node control, DaemonSets,
  privileged pods, billed as regular Compute Engine (SUD/CUD apply
  normally). Autopilot = no node mgmt, stricter security defaults,
  Google's default recommendation for new clusters.
CROSS-CLOUD: GCP bills per-second w/ automatic SUD; AWS needs Savings
  Plans/RIs for any commitment-based discount, no free automatic-longevity
  discount equivalent to SUD exists on AWS.
```

## Sources

- [Sustained use discounts — Google Cloud docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts) — accessed 2026-08-08
- [About commitments and committed use discounts (CUDs) — Google Cloud docs](https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview) — accessed 2026-08-08
- [Google Kubernetes Engine pricing — Google Cloud](https://cloud.google.com/kubernetes-engine/pricing) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
