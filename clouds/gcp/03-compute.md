# GCP Compute Deep: Compute Engine, GKE, Autopilot, Cloud Batch

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2h · **Prereqs:** C-GCP-iam · **Updated:** 2026-08-23
> **Module id:** `C-GCP-compute` · **Tags:** compute

## The 30-second version

GCP's compute stack is four abstractions over one capacity pool: **Compute Engine** VMs (per-second billing, 1-minute minimum; machine families from cost-optimized E2 through general N2/N2D and compute-optimized C-series to GPU-heavy A-series), **GKE** in two modes whose real difference is the *billing model* — Standard bills node-hours whether or not pods run, Autopilot bills pod requests (roughly $0.0445/vCPU-hr plus $0.0049/GiB-hr) so idle costs nothing — **Cloud Batch** for job-shaped work that needs queueing and array jobs without owning a scheduler, and Cloud Run for request-driven work (covered separately). The pricing levers are specific and testable: sustained-use discounts apply automatically up to ~30% net for full-month usage but exclude E2 and GPU machines; committed-use discounts trade 1–3 year lock-in for up to ~57–70%; Spot VMs give 60–91% off with a 30-second eviction notice. The interview question underneath: given a workload shape, which abstraction and which discount stack do you pick, and can you defend the arithmetic?

## Why this gets asked

Because "we run Kubernetes" is where money silently evaporates. The interviewer has seen a Standard-mode cluster idling at 25% utilization because autoscaler lag kept nodes warm, an Autopilot migration that doubled the bill because pod resource requests were inflated by years of guesswork (Autopilot bills exactly what you request), and a batch pipeline that ran everything on-demand when 80% of it could have been Spot. They're probing whether you understand that choosing between Standard and Autopilot is choosing between paying for provisioned capacity versus requested capacity — the break-even sits somewhere around moderate-to-high sustained node utilization, and sources genuinely disagree on exactly where — and whether you know the hard limits that force decisions (no privileged containers or node SSH on Autopilot; no SUDs on E2; Spot's 30-second warning). Vague answers about "autoscaling" fail; arithmetic about vCPU-hours pass.

---

## Lineage: past → present → future

**What came before.** Compute Engine launched in 2012 (GA 2013), late to AWS's EC2 by six years, and competed by simplifying: per-second billing instead of hourly, automatic sustained-use discounts instead of negotiating reserved instances, and machine types as vCPU/memory bundles you could customize rather than fixed SKUs. Kubernetes itself was Google open-sourcing its internal Borg lessons in 2014; GKE shipped as hosted Kubernetes shortly after. The pain driving each step: EC2's hourly rounding wasted money on short jobs; reserved-instance purchasing was a negotiation-heavy procurement exercise; running your own Kubernetes control plane was operationally brutal before managed offerings matured around 2018.

**Where it stands now.** GKE is the most mature managed Kubernetes of the big three, and the Autopilot/Standard split (Autopilot GA April 2021) is now the defining fork. Autopilot has progressively absorbed former blockers — GPUs, TPUs, Spot pods, Arm (T2A), DaemonSets without elevated privileges, Confidential Nodes all work in 2026 — leaving the true hard limits at privileged containers, node SSH, custom node OS, and Windows nodes. [GKE Autopilot vs Standard 2026](https://www.alekseialeinikov.com/en/blog/topics/cloud/gke-autopilot-vs-standard-2026); accessed 2026-08-23. Two live developments blur the binary: Standard clusters can mark individual workloads to run in Autopilot mode via ComputeClasses, and recent GKE versions unify the underlying container platform further. On raw VMs, the notable current shift is Google's own silicon: **Titanium** offload processors underpinning the N4/C4 generation, and the A3/A4 GPU lines for AI training/serving. The live disagreement is Autopilot economics: vendors selling optimization tools claim Standard wins above ~50% utilization, other analyses put crossover at 70–80% — both agree the answer depends on how well-packed your nodes actually stay, which most teams overestimate.

**Where it's heading.** High confidence: continued Autopilot-first posture from Google — new features land there first, and the mode line keeps blurring toward "Autopilot workloads inside any cluster." High confidence: GPU/accelerator management becoming a first-class scheduling concern everywhere as AI workloads dominate new compute demand. Medium confidence: Titanium-class custom offload spreading across more families, making family choice increasingly performance-per-dollar opaque without benchmarks. Speculative: deeper Borg-style bin-packing automation reaching Standard mode such that the utilization gap that justifies Standard narrows — treat claims of "automatic 90% packing" skeptically today.

---

## Mental model

One capacity pool, four doors, each with a different billing meter:

```
                    GOOGLE CAPACITY POOL
                            │
     ┌──────────────┬───────┴────────┬────────────────┐
     ▼              ▼                ▼                ▼
 COMPUTE ENGINE   GKE STANDARD    GKE AUTOPILOT    CLOUD BATCH
 bill = VM-seconds bill = node-hours bill = pod-request- bill = job-seconds
 (SUD auto ~30%)  (you pack bins) seconds            (+ Spot friendly)
                  + $0.10/h ctrl  ~$0.0445/vCPU-h   (queueing built in)
                  (1st zonal free) +$0.0049/GiB-h

 DISCOUNT STACK (apply in order of commitment):
   Spot VMs      60-91% off, 30s eviction notice  -> interruptible work
   SUD           automatic, up to ~30% net        -> long-running eligible fams
   CUD 1yr/3yr   ~28% / ~57%+                     -> stable baseline, lock-in
```

The mental shortcut: **who absorbs idle?** Compute Engine: you do (mitigated by SUD). GKE Standard: you do (nodes run whether packed or not). Autopilot: nobody — idle doesn't exist because unscheduled pods consume nothing. Batch: you pay while jobs run, and the service handles the waiting.

And the workload-shape decision tree:

```
request-driven HTTP?          -> Cloud Run (see serverless module)
long-running services, need K8s ecosystem?
  ├─ steady high utilization (>~60-70%), need privileged/SSH/custom OS?
  │    -> GKE Standard + CUD on baseline
  └─ variable load, small team, dev/test -> GKE Autopilot
finite jobs needing queueing/array semantics -> Cloud Batch (Spot inside)
one-off heavy compute, custom kernels -> Compute Engine directly
```

## How it actually works

### Compute Engine mechanics that matter

- **Billing granularity:** per-second after a 1-minute minimum. A 40-second boot-and-crash loop costs minutes, not hours — this is why ephemeral patterns are cheaper on GCP than hourly-billed competitors.
- **Resource-based pricing:** since 2018 every machine type bills as separate vCPU and memory SKUs, which is what makes custom machine types possible at ~5% premium over predefined shapes and what lets SUDs aggregate across heterogeneous VMs in a region.
- **Machine families:** E2 (cost-optimized, no SUD eligibility, no sustained discount), N2/N2D (general purpose, AMD variant N2D), C3/C4 (compute-optimized, Titanium offload in newer gens), M1–M3 (memory-optimized, up to 12+ TiB on M2/M3 shapes ~), A2/A3/A4 (GPU: A3 carries H100-class for training; A4 the B200-class), H-series/H4D (HPC). Pick family by workload bottleneck first, generation second.
- **Sustained use discounts, precisely:** automatic credits computed per region per vCPU/memory usage aggregated across all VMs of eligible families (N1/N2/N2D, C2, M1/M2, sole-tenant). Tiers: 0–25% of month full price, 25–50% incremental ~20% off, 50–75% more, 75–100% most — netting up to 30% for round-the-clock usage. Excluded: E2, GPU-attached workloads' accelerators, App Engine/Dataflow-created VMs, anything already covered by CUDs. [Sustained use discounts — Compute Engine docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts); accessed 2026-08-23.
- **Committed use discounts:** resource-based (commit specific vCPU/memory/RAM in a region, 1 or 3 years) or spend-based flexible (commit $/hour across services, applies even to Cloud Run/GKE). Resource-based 3-year reaches ~55–70% depending on family (~). Reservations combine with CUDs so committed capacity stays available.
- **Spot VMs:** same capacity, 60–91% below on-demand, reclaimed with only 30 seconds of warning (ACPI signal or termination via API); price adjusts at most monthly. The successor naming to preemptible VMs. Design requirement: checkpoint-and-resume semantics and tolerance for hard eviction mid-write.

### GKE Standard: you own the bins

Standard gives node pools you size, machine types you choose, DaemonSets unrestricted, SSH, any OS including Windows, and full control of upgrade surge behavior. Billing = node-hours + $0.10/hr control plane ($73/month, first zonal cluster free per billing account). The operational tax is bin-packing discipline: cluster autoscaler adds nodes when pods pend (1–3 min lag ~) and removes underutilized ones after cooldown, but real-world utilization typically lands 30–50% because headroom-for-spikes plus scheduling fragmentation strand capacity. That stranded fraction is precisely what Autopilot eliminates.

### GKE Autopilot: you own the requests

Google provisions and manages nodes; you declare pod resources. General-purpose pods bill at roughly $0.0445/vCPU-hr plus $0.0049/GiB-hr (~region-dependent), one-second granularity, with the management premium baked in — approximately 10–20% above raw VM-equivalent rates. Three subtleties worth knowing cold:

1. **Requests are the bill.** `resources.requests` inflating from habit directly multiplies cost; rightsizing precedes migration.
2. **Special hardware flips billing mode.** Pods selecting GPUs/TPUs/specific machine series bill per *node* plus premium, not per-pod — the "pay only for what I request" advantage evaporates exactly where costs are highest.
3. **The restriction list is now short:** no privileged containers, no node SSH, COS-only nodes, regional clusters only, Windows unsupported. gVisor sandboxing and Dataplane V2 are defaults, not options. Workload Identity Federation comes preconfigured.

Economics honestly stated: at low or bursty utilization Autopilot wins outright (idle costs nothing); at consistently high utilization Standard's per-node pricing undercuts it — analyses place crossover anywhere from ~50% to ~80% sustained utilization depending on packing assumptions and region. Nobody credible claims a single number; the defensible interview answer names the range and says "measure your actual p50 node utilization first."

### Cloud Batch: jobs without owning a scheduler

Batch sits on Compute Engine capacity and adds what raw VMs lack for job workloads: queueing, array/job-run semantics, dependency graphs between jobs, automatic provisioning of the right shape (including Spot and GPU), and region-level scheduling. You describe a job (task spec, task count, resource needs); it provisions VMs, runs tasks, tears down. It's the middle path between cron-on-a-VM and a full Airflow/Spark estate — no servers when idle, Spot-first by default in many configurations. Where it loses: streaming, low-latency serving, or anything needing the K8s ecosystem's sidecars/operators — that's GKE territory.

## Build it from scratch

The discount-stack decision is arithmetic; make yourself do it:

```python
# untested sketch - monthly cost model for one service tier
HOURS = 730

def vm_monthly(on_demand_hourly, utilization=1.0):
    """SUD net discount ~30% only at full-month usage; tiers below."""
    if utilization >= 0.75:
        return on_demand_hourly * HOURS * 0.70          # ~30% off
    return on_demand_hourly * HOURS * utilization        # rough lower-tier approx

def autopilot_monthly(vcpu_per_pod, pods, mem_gib_per_pod,
                      cpu_rate=0.0445, mem_rate=0.0049):
    pod_hours = pods * HOURS
    return (vcpu_per_pod * cpu_rate + mem_gib_per_pod * mem_rate) * pod_hours

def standard_monthly(nodes, node_hourly, ctrl=0.10):
    return nodes * node_hourly * HOURS + ctrl * HOURS    # idle included!

# 10 pods x (1 vCPU, 2 GiB) steady:
print(autopilot_monthly(1, 10, 2))                    # ~$396/mo
# Standard equivalent: 3 x n2-standard-4 (~$0.19/hr) packed at ~65%:
print(standard_monthly(3, 0.19))                      # ~$495/mo -> Autopilot wins
# Same cluster at 90% packing with CUD-3yr baseline (~45% off nodes):
print(standard_monthly(3, 0.19 * 0.55))               # ~$309/mo -> Standard wins
```

Provision the real things:

```bash
# GKE Autopilot cluster - note regional-only, minimal flags by design
gcloud container clusters create-auto prod-ap --region=europe-west3

# Spot-enabled MIG for interruptible workers, 30s eviction handled via
# termination handler draining into your checkpointing logic
gcloud compute instance-groups managed create worker-spot \
  --template=spot-worker-tpl --size=20 --zone=europe-west3-b

# Batch job: 500 array tasks, 2 vCPU/4GiB each, Spot preferred
gcloud batch jobs render-jobs --location=europe-west3 --config=job.json
```

## How it's done in production

Standard estate pattern: baseline capacity on CUD-backed N-series in GKE Standard (or Autopilot where teams shouldn't own infra), spiky overflow on cluster autoscaler, genuinely interruptible work (rendering, batch inference, CI runners) on Spot node pools/pods with checkpointing, GPU pools dedicated per model-generation to avoid fragmentation. Node management discipline: release channels (regular/steady), maintenance windows, surge upgrades configured so rollouts don't strand capacity; Workload Identity everywhere; Binary Authorization in regulated estates.

| Symptom | Cause | Fix |
|---|---|---|
| Autopilot bill doubled after migration | Inflated pod `requests` carried over from Standard sizing | Rightsize requests from actual usage; requests are the bill |
| Standard cluster costs flat while traffic dropped overnight | Nodes persist regardless of packing | Autoscaler scale-down rules, consolidate small node pools, or move variable services to Autopilot/Cloud Run |
| Batch jobs keep dying mid-write | Spot eviction without checkpointing | Checkpoint to GCS every N minutes; handle the 30-second ACPI notice |
| SUD line item missing despite 24/7 VMs | E2 family (excluded) or usage already under CUD | Move baseline to N2/N4 if SUD matters, or accept CUD coverage |
| Pods pending forever after scale event | Insufficient quota, or GPU shape unavailable in zone | Regional quotas review; spread across zones; consider A2 vs A3 availability |
| Monthly bill has surprise cross-region traffic | Nodes/zones talking across regions | Zonal affinity, topology-aware routing, keep state co-regional |

## Tradeoffs & when NOT to use it

- **Don't default to Autopilot for GPU fleets without doing the billing-mode math** — accelerator workloads flip to per-node billing plus premium there, so a well-managed Standard GPU pool with CUDs frequently wins.
- **Don't buy 3-year CUDs on workloads younger than a year.** The lock-in only pays when the baseline is measured and stable; spend-based flexible commitments are the hedge for evolving estates.
- **Don't run stateful singletons (databases, brokers) as ordinary GKE workloads** because "Kubernetes runs everything." Managed databases (Cloud SQL/Spanner/AlloyDB) carry the operational guarantees; self-running them on VMs is a cost decision that must survive an interview about RTO/RPO.
- **Spot is not for your API tier.** The 30-second eviction notice is fine for checkpointable batch and fatal for latency-facing serving unless you have genuine overflow capacity behind it.
- **E2's cheapness is real but discount-free:** no SUD eligibility, no CUD resource coverage in older configurations (~) — compare E2-on-demand against N2-with-discounts before assuming E2 wins.
- **When plain Compute Engine beats both GKE modes:** a handful of long-lived monoliths, licensed software with node-locking, or workloads whose operational model is "one VM, one service" — Kubernetes overhead buys nothing there.

---

## Interview questions

### Q1 — Standard vs Autopilot: how do you decide for a new production cluster?
**Testing:** whether the billing-model fork is understood, not just feature lists.
**Answer:** The modes differ in who manages nodes and what bills: Standard bills node-hours plus $0.10/hr control plane regardless of packing; Autopilot bills pod requests (~$0.0445/vCPU-hr + $0.0049/GiB-hr) so idle pods cost nothing but inflated requests inflate everything. Decide by utilization forecast and hard requirements: need privileged containers, node SSH, custom OS, or Windows -> Standard. Steady high utilization (>~60–70% packed) -> model Standard + CUDs. Variable load or teams not owning infra -> Autopilot.
**Follow-up trap:** *"Can't you switch later?"* — no, mode is fixed at cluster creation; migration means a parallel cluster. That permanence is why the decision deserves arithmetic up front, and why ComputeClasses letting Standard clusters run Autopilot-mode workloads matter.

### Q2 — Walk me through the exact sustained-use-discount mechanics and their exclusions.
**Testing:** precision on the automatic discount most candidates wave at vaguely.
**Answer:** SUDs are monthly credits computed per region by aggregating vCPU/memory usage across all eligible VMs: 0–25% of month full price, incremental ~20%/more/most discounts across 25–50/50–75/75–100 tiers, netting ~30% at full-month usage. Eligible families: N1/N2/N2D, C2, M1/M2, sole-tenant. Excluded: E2, GPU accelerators themselves, App Engine/Dataflow-created VMs, anything already discounted by CUDs.
**Follow-up trap:** *"So E2 is always cheaper anyway?"* — often yes at list price, but a full-month N2 baseline at ~30% off can close or invert the gap; compare discounted N-series against E2 for your actual shape rather than assuming.

### Q3 — Spot VMs: what do you get, what must your workload tolerate, and where do they fit?
**Testing:** eviction-aware architecture instincts.
**Answer:** Same capacity as on-demand at 60–91% below, reclaimable at any time with 30 seconds' ACPI warning; spot prices adjust at most once monthly per machine type in region. Workloads must checkpoint-and-resume and treat termination mid-write as normal. Fit: CI runners, rendering, batch inference, Spark executors (with checkpointing), any stateless fan-out. Not fit: serving tiers, stateful primaries, anything where restart costs exceed savings.
**Follow-up trap:** *"How is this different from AWS Spot?"* — same essential contract; GCP historically offers deeper headline discounts (up to 91%) and simpler pricing behavior (monthly adjustment vs continuous market pricing). The design discipline — handle two-minute warnings on AWS, 30-second here — transfers.

### Q4 — A team migrated to Autopilot and costs doubled. Diagnose.
**Testing:** the requests-are-the-bill insight.
**Answer:** Almost always inflated `resources.requests`: years of defensive sizing (4GiB requested, 300MB used) were free-ish on underutilized Standard nodes but bill line-by-line on Autopilot. Fix: profile actual usage per workload, set requests from p95-plus-headroom, use HPA-driven scaling instead of static over-provisioning, and check whether special-hardware pods flipped to per-node billing unexpectedly.
**Follow-up trap:** *"Requests lowered — anything else inflating?"* — yes: DaemonSets now bill if non-exempt (each node's worth of agents), ephemeral storage requests, and zone-skew (Autopilot is regional; uneven pod spread multiplies effective footprint).

### Q5 — Where does Cloud Batch fit against GKE jobs and raw VMs?
**Testing:** whether they know the middle abstraction exists and when it's the right one.
**Answer:** Batch is job-shaped compute on GCE capacity: queueing, array tasks, dependencies between jobs, automatic provisioning including Spot/GPU, zero idle servers. Choose it over cron-on-VM when you need parallel array semantics; over GKE jobs when there's no cluster worth owning for this workload or Spot-first scheduling matters more than ecosystem; over Dataflow when the work isn't a data-parallel pipeline with exactly-once semantics. It loses to GKE for anything needing sidecars/operators and to raw VMs for licensed node-locked software.
**Follow-up trap:** *"Batch vs Dataproc for ETL?"* — Dataproc is managed Hadoop/Spark (cluster lifecycle management, YARN-era semantics plus serverless Spark); Batch runs arbitrary containers as tasks. If your code is literally PySpark, Dataproc serverless usually fits better; if it's a container doing anything else, Batch.

### Q6 — Design capacity purchasing for: 40 vCPU steady baseline, bursty +60 vCPU daytime, nightly render farm.
**Testing:** discount-stack synthesis.
**Answer:** Baseline: resource-based CUD (1–3 year) covering ~40 vCPU N-series in-region, optionally with reservations so capacity is guaranteed. Daytime burst: autoscaled capacity at on-demand with SUD accruing naturally, or Autopilot pods if K8s-shaped. Nightly renders: Spot VMs/MIGs with checkpointing — expect evictions, size for throughput-after-evictions not raw speed. Never commit CUDs to burst or render components; never run renders on-demand.
**Follow-up trap:** *"What if steady baseline shrinks mid-year?"* — resource CUDs bill regardless of usage (that's their contract); mitigate by committing below measured baseline (80–90%), using spend-based flexible commitments where evolution is expected, and treating over-commitment as the cost of certainty.

### Q7 — What are Autopilot's hard limits in 2026, and which "limitations" are actually outdated?
**Testing:** currency — the list moved substantially.
**Answer:** Current hard limits: no privileged containers/elevated node access, no SSH into nodes, Container-Optimized OS only, regional clusters only, no Windows nodes. Outdated claims: GPUs/TPUs (via ComputeClass), Spot pods, Arm T2A, DaemonSets (non-elevated), Confidential Nodes, and gVisor sandboxing all work now. The elevated-access line is the real boundary — security agents needing kernel-level access stay on Standard.
**Follow-up trap:** *"Why does the privileged ban matter in practice?"* — common tooling that assumed host access (some CNI plugins, eBPF profilers, certain security agents) fails silently-ish; teams discover it during migration, which is why the pre-migration audit lists DaemonSets and admission-webhook tooling first.

### Q8 — Your Standard cluster's nodes average 35% utilization. Options ranked by effort-to-impact.
**Testing:** practical FinOps instincts inside compute.
**Answer:** 1) Fix packing: consolidate node pools, bin-pack requests, enable autoscaler scale-down tightening — cheap, immediate. 2) Move variable/bursty services off-cluster (Cloud Run/Autopilot) keeping only steady stateful/platform workloads. 3) If utilization stays structurally low because of spike headroom, migrate those workloads to Autopilot where headroom costs nothing. 4) Only after utilization is honest: right-size machine families and consider CUDs on what's left. Buying discounts on an underutilized estate just discounts waste.
**Follow-up trap:** *"Why not just add CUDs first?"* — committing to 65% utilization locks in paying for stranded capacity for 1–3 years. Discounts amplify whatever discipline already exists; they don't substitute for it.

### Q9 — Explain how GKE autoscaling behaves under a sudden 3x traffic spike.
**Testing:** operational realism about lag and headroom.
**Answer:** HPA scales pods within seconds against existing node capacity; once pods pend for lack of resources, cluster autoscaler provisions nodes — typically 1–3 minutes to schedulable (~), longer for GPU shapes. During the gap you serve from existing headroom, which is exactly the buffer that makes Standard expensive. Autopilot shortens pod-to-capacity provisioning but new special-hardware nodes still take minutes. Scale-down trails traffic on utilization cool-downs, so cost lags demand in both directions.
**Follow-up trap:** *"How do you survive the gap without paying all day?"* — global LB across clusters/regions, pre-warming before known events, and moving request-driven tiers to Cloud Run where instances start in seconds.

### Q10 — What is Titanium and why does machine-family generation matter?
**Testing:** awareness of GCP's hardware differentiation.
**Answer:** Titanium is Google's custom offload infrastructure — dedicated processors taking storage/networking/security work off the CPU — introduced with the N4/C4 generation (2024). Effect: better price-performance and steadier behavior at high IOPS on newer families. Generation matters because equal-vCPU machines differ materially on throughput-sensitive workloads; benchmark your shape instead of trusting spec sheets.
**Follow-up trap:** *"Always pick newest family then?"* — new families often start without SUD eligibility, thinner CUD coverage, and limited regional availability (~). Discount stack plus workload profile decides; N2 remains a defensible discounted baseline until coverage matures.

### Q11 — A stateful Kafka on GKE loses brokers during node upgrades. Diagnose.
**Testing:** whether they fix YAML or question the platform.
**Answer:** Likely stack: no PodDisruptionBudget blocking simultaneous broker drains, missing zonal anti-affinity, ephemeral local storage dying with nodes, surge upgrades evicting multiple brokers at once. If staying: PDB maxUnavailable=1, zonal spread, StatefulSets with regional persistent disks, maintenance windows. The senior addendum: quorum systems couple their availability to node churn; managed messaging or dedicated VMs exist precisely to decouple that.
**Follow-up trap:** *"Doesn't StatefulSet solve it?"* — it provides stable identity and storage hooks only; without disruption budgets, affinity rules, and the right storage class it's a naming convention, not a safety mechanism.

### Q12 — GKE vs EKS vs AKS control-plane economics in one pass.
**Testing:** cross-cloud literacy for a polyglot profile.
**Answer:** EKS: ~$0.10/hr per cluster, no free tier. AKS: free control plane tier historically (paid SLA tiers exist). GKE: $0.10/hr ($73/month) but first zonal cluster free per billing account, and Autopilot folds management into pod rates. Real cost differences live around the control plane: node utilization discipline, autoscaling quality, and ancillary services — GKE's bin-packing reputation and Autopilot option are its differentiators, AKS's free control plane wins many-small-cluster estates.
**Follow-up trap:** *"Which would you standardize on?"* — follow workload gravity and team skills: the managed-Kubernetes layers are converging; migration costs between them are dominated by identity, networking, and operational tooling differences, not Kubernetes itself.

---

## Red flags that fail you

- Claiming SUDs apply automatically to everything including E2 and GPUs.
- Not knowing Autopilot bills pod requests while Standard bills node-hours.
- Saying "Kubernetes everywhere" for stateful stores without discussing PDB/affinity/storage discipline or managed alternatives.
- Recommending Spot for latency-facing serving without an overflow story.
- Treating the 30-second Spot eviction notice as "enough time" without checkpointing design.
- Buying 3-year CUDs on an unmeasured baseline as step one of cost optimization.

## Cheat card

```
COMPUTE ENGINE: per-second billing, 1-min minimum; resource-based (vCPU+RAM SKUs)
  families: E2 cheap (NO SUD) | N2/N2D general (SUD yes) | C3/C4 compute (Titanium)
            M1-M3 memory | A2/A3/A4 GPU (H100/B200 class) | H-series HPC
  SUD: automatic, region-aggregated, tiers -> up to ~30% net at full month
       excludes E2, GPUs, AppEngine/Dataflow VMs, CUD-covered usage
  CUD: resource-based 1y/3y (~28%/~57%+) or spend-based flexible; bill regardless
  Spot VMs: 60-91% off, eviction with 30s ACPI notice, price adjusts <= monthly
  custom machine types ~5% premium over predefined

GKE BOTH MODES: control plane $0.10/hr ($73/mo); first zonal cluster free/account
STANDARD:   you manage node pools; bill = node-hours (idle included)
            real-world utilization typically 30-50% -> stranded capacity
AUTOPILOT:  Google manages nodes; bill = pod requests
            ~$0.0445/vCPU-hr + ~$0.0049/GiB-hr (+10-20% mgmt premium, ~)
            GPU/TPU/special shapes flip to PER-NODE billing + premium
            NO: privileged pods, node SSH, custom OS, Windows. Regional only.
            YES now: GPUs/TPUs via ComputeClass, Spot pods, Arm T2A,
                     DaemonSets (non-elevated), gVisor default, DPv2 default
  crossover Standard-vs-Autopilot: ~50-80% sustained utilization (sources disagree;
  measure p50 node utilization before deciding). Mode fixed at cluster creation.

CLOUD BATCH: job queueing + array tasks + deps on GCE capacity; Spot/GPU aware;
             zero idle servers; not for streaming/low-latency serving

DISCOUNT ORDER: Spot (interruptible) > CUD-3yr (stable baseline) > SUD (automatic)
RIGHTSIZING BEFORE DISCOUNTS - committing to waste just discounts it
```

## Sources

- [Spot VMs — Compute Engine docs](https://docs.cloud.google.com/compute/docs/instances/spot); accessed 2026-08-23
- [Sustained use discounts — Compute Engine docs](https://docs.cloud.google.com/compute/docs/sustained-use-discounts); accessed 2026-08-23
- [GKE Autopilot vs Standard 2026: which mode should you pick](https://www.alekseialeinikov.com/en/blog/topics/cloud/gke-autopilot-vs-standard-2026); accessed 2026-08-23
- [GKE Standard vs Autopilot pricing math — c3x.dev](https://c3x.dev/blog/gke-standard-vs-autopilot/); accessed 2026-08-23
- [GKE Pricing Explained: Autopilot vs Standard — CloudZero](https://www.cloudzero.com/blog/gke-pricing/); accessed 2026-08-23
- [Google Cloud discounts: SUDs, CUDs, Spot — ProsperOps](https://www.prosperops.com/blog/google-cloud-discounts/); accessed 2026-08-23
- [GCP cost optimisation: CUDs, Spot VMs, FinOps strategies — Devopsity](https://devopsity.com/blog/gcp-cost-optimisation-committed-use-discounts-spot-vms-finops-strategies); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
