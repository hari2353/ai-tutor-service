# HPA/VPA/KEDA, Cluster Autoscaler, GPU Scheduling & Node Pools, Mesh

> **Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **Prereqs:** T12-k8s-core, T12-k8s-networking · **Updated:** 2026-08-02
> **Module id:** `T12-k8s-scaling` · **Tags:** k8s
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Kubernetes autoscaling is three independent, layered loops that must be coordinated, not left to fight each other: HPA/KEDA scale pod *count* against a metric, VPA right-sizes each pod's resource *requests*, and Cluster Autoscaler or Karpenter scale *node count* underneath both. The trap that catches almost everyone at least once: a CPU limit isn't a smoothed average cap, it's enforced via the kernel's CFS quota over discrete **100ms periods**, so a container can show a low average CPU utilization graph over a minute while still being throttled — literally paused mid-execution — dozens of times within that same minute, because one bursty 100ms window blew its quota even though the surrounding periods were idle. That's the actual mechanism behind "my p99 latency is terrible but the CPU graph looks fine," and it's why many teams deliberately omit CPU limits on latency-sensitive services entirely, keeping only a memory limit (which is a hard OOM-kill ceiling, an entirely different, non-throttling enforcement mechanism). GPUs are not fungible resources the way CPU/memory are: they're requested as whole, non-fractional units via the device plugin framework by default, sit behind taints on dedicated node pools, and only become shareable via MIG (hardware-level partitioning) or time-slicing (software-level, no isolation) — treating a GPU node pool with the same autoscaling instincts as a CPU fleet is a common, costly mistake given GPU provisioning lead time and cost.

## Why this gets asked

Because "set up HPA" is a five-minute YAML exercise and every senior interviewer knows it — what they're actually testing is whether you've debugged the failure modes that only show up under real load: a service throttled into terrible tail latency while every dashboard says it's fine, an HPA and VPA quietly fighting each other and oscillating replica counts, a cluster autoscaler that never scales up because nobody set resource requests on the pods that need it, or a GPU pod stuck `Pending` for a reason that has nothing to do with GPU availability at all. These are exactly the incidents that separate "configured autoscaling once" from "understands the mechanism well enough to diagnose it under pressure."

---

## Lineage: past → present → future

**What came before.** Before autoscaling existed as a mature primitive, capacity planning meant either static overprovisioning (paying for peak capacity around the clock, real and continuous waste) or static underprovisioning that broke under any traffic spike beyond the planned baseline — the classic e-commerce flash-sale outage story. HPA (present in beta form early, matured with the `autoscaling/v2` API adding multi-metric and custom-metric support well beyond the original CPU-only model) was the first real answer, but it only ever scaled pod *count*, reactively, against whatever metric it was pointed at — and CPU/memory utilization, its original and still most common signal, lags real demand and has no concept of an external queue backing up. Cluster Autoscaler filled the node-level gap, but was built against explicit, pre-defined node groups (AWS ASGs, GCP MIGs) with a provisioning time bound by real cloud API latency plus node bootstrap — historically landing in the **4-8 minute** range from "pod unschedulable" to "new node Ready," a genuinely slow response for spike-shaped traffic.

**Where it stands now.** KEDA (a CNCF project) closed HPA's biggest structural gap: it's not a replacement for HPA, it's an **HPA metrics-adapter plus scale-to-zero controller** — it translates 60-plus external "scalers" (Kafka consumer lag, SQS queue depth, a raw Prometheus query, even a cron schedule) into a standard HPA object under the hood, and critically adds `minReplicaCount: 0` scale-to-zero, something plain HPA structurally cannot do at all (HPA needs at least one running replica to compute a ratio against). VPA matured with **in-place pod resizing** (avoiding the older eviction-and-recreate cycle its updater used to require to apply a new recommendation), though VPA and HPA configured against the *same* metric remains a well-known anti-pattern — both loops reacting to CPU simultaneously can oscillate against each other, and the safe pattern is splitting responsibility (VPA sizing memory or running in recommend-only mode, HPA driving scale-out off a different, business-meaningful metric). Karpenter displaced Cluster Autoscaler as the default recommendation for AWS-native teams wanting materially faster response — **45-60 seconds** from unschedulable pod to a new node online, calling cloud provisioning APIs directly rather than working through pre-shaped node groups, with continuous "consolidation" (proactively replacing underutilized nodes for tighter bin-packing) as an added, ongoing cost optimization Cluster Autoscaler doesn't do the same way. The CPU-throttling-via-CFS-quota trap is now widely documented after years of teams discovering it the hard way in production, though the counter-argument — that CPU limits still provide real, legitimate noisy-neighbor protection in genuinely shared/multi-tenant clusters — is a live, unresolved disagreement, not a settled "never set limits" consensus.

**Where it's heading.** GPU scheduling is the fastest-moving part of this space right now, driven directly by the AI/ML workload boom: Dynamic Resource Allocation (DRA), a newer Kubernetes API generalizing well beyond the original device-plugin model, is under active development specifically to make fractional and topology-aware hardware requests (partial GPU slices, NUMA-aware placement, multi-GPU interconnect topology) a first-class scheduler concept, rather than something bolted on after the fact via vendor-specific device plugin configuration and manual MIG/time-slicing setup. Expect the gap between "how CPU/memory scheduling works" and "how GPU scheduling works" to narrow over the next several Kubernetes releases, though it remains meaningfully behind today.

---

## Mental model

```
   ┌─────────────────────────────────────────────────────────┐
   │  KEDA (event-driven, scale-to-zero)  or  HPA (metric-driven)│
   │      -> scales POD COUNT                                    │
   └─────────────────────────────────────────────────────────┘
                              │  drives replica count up/down
                              ▼
   ┌─────────────────────────────────────────────────────────┐
   │  VPA (recommender + updater + admission webhook)            │
   │      -> right-sizes EACH POD'S resource requests/limits      │
   │      DO NOT point both HPA and VPA at the same metric —       │
   │      they'll oscillate against each other                     │
   └─────────────────────────────────────────────────────────┘
                              │  determines how much room each pod needs
                              ▼
   ┌─────────────────────────────────────────────────────────┐
   │  Cluster Autoscaler (node-group based, ~4-8min)               │
   │      or Karpenter (direct cloud API, ~45-60s, bin-packing-    │
   │         aware, continuous consolidation)                       │
   │      -> scales NODE COUNT to fit what's actually pending       │
   │      IGNORES pods with NO resource requests entirely            │
   └─────────────────────────────────────────────────────────┘

CPU LIMIT ENFORCEMENT (the throttling trap):
  cgroup CFS quota/period, default period = 100ms
  limit = 0.5 CPU -> quota = 50ms of CPU time PER 100ms PERIOD
  container bursts past 50ms in ONE period -> THROTTLED for the rest of THAT period
  -> can happen dozens of times/minute while the 60s AVERAGE still looks low
  MEMORY limit enforcement is completely different: hard ceiling, kernel OOM-kills the
  cgroup immediately on exceeding it (exit 137) — no throttling, no grace period
```

---

## How it actually works

### Requests vs limits: two entirely different enforcement mechanisms

**Requests** are what the scheduler uses for bin-packing — the sum of all pods' CPU/memory requests on a node must not exceed that node's allocatable capacity, and requests also set the cgroup's CPU **shares** (a relative weight used only when the node is actually under CPU contention, not a ceiling of any kind). **Limits** are enforced completely differently depending on the resource:

- **CPU limits** map to the cgroup's CFS (Completely Fair Scheduler) **quota and period** — by default a **100ms period**, with quota computed as `limit × period` (a 0.5 CPU limit becomes a 50ms quota per 100ms period). If a container's CPU usage exceeds its quota within any single period, the kernel **throttles** it — literally pauses that cgroup's processes — for the remainder of that period, resuming only in the next one. This is the mechanism, and it's why `container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total` (available via cAdvisor/Prometheus) is the metric that actually reveals throttling, while a 60-second average CPU utilization graph can look completely healthy the entire time — a single bursty 100ms window (JSON deserialization, a GC pause catch-up, one goroutine spike) is enough to trigger a throttle event that a coarse average simply averages away.
- **Memory limits** are enforced by the kernel's cgroup OOM killer as a hard ceiling — exceed it, and the container is killed immediately (**exit code 137**), no throttling, no grace period, no partial degradation. This is a fundamentally different failure mode from CPU throttling, and conflating the two ("just set limits like you set requests") misses that CPU limits degrade latency silently while memory limits fail loudly and immediately.

**QoS classes** fall directly out of how requests and limits are set, and determine eviction order under node memory pressure: **Guaranteed** (every container's requests equal its limits, for both CPU and memory) is evicted last; **Burstable** (requests set but differing from limits on at least one resource) is evicted next, ordered by how far over its requests a pod's actual usage is; **BestEffort** (no requests or limits set at all) is evicted first. This is a real, practical reason to always set at least requests, independent of the autoscaling implications below.

### HPA — the algorithm and the flapping problem

The `autoscaling/v2` API computes `desiredReplicas = ceil(currentReplicas × (currentMetricValue / desiredMetricValue))`, polling the metrics source (metrics-server for CPU/memory, or a custom/external metrics API adapter — which is exactly the extension point KEDA plugs into) on a sync interval (**15 seconds by default**). Without tuning, this can flap — scale up in response to a brief spike, then immediately scale back down, repeatedly — which is why `behavior.scaleDown.stabilizationWindowSeconds` (defaulting to a much longer window, commonly **300 seconds**, versus a near-immediate default for scale-up) exists specifically to require a metric to stay elevated (or depressed) for a sustained period before acting, and `behavior` policies more broadly let you cap the rate of change per direction (e.g. "never add more than 4 pods or double the fleet in any 60-second window") to prevent both flapping and runaway scale-out from a metric spike that's actually a transient blip.

### VPA — recommend, don't blindly automate

VPA has three components: the **recommender** (analyzes historical usage and computes suggested requests/limits), the **updater** (under `updateMode: Auto` or `Recreate`, evicts pods whose current requests are significantly off from the recommendation so they get recreated with new values — historically the only mechanism, though in-place resizing without eviction has since landed to avoid this churn), and an **admission webhook** (injects recommended values into new pods at creation time). `updateMode: Off` runs VPA purely as a sizing advisor with zero automated action — a genuinely safe way to use it in production without risking eviction-driven instability on stateful or latency-sensitive workloads. The critical anti-pattern: **VPA and HPA configured against the same metric fight each other** — VPA raising a pod's CPU request changes the utilization percentage HPA is computing against, which can trigger HPA to scale replica count in a way that then changes VPA's own usage observations, an oscillating feedback loop. The safe combination splits responsibility: VPA sizing memory (a dimension HPA typically isn't tracking) or running in recommend-only mode, while HPA drives horizontal scale-out off a genuinely independent signal (requests-per-second, queue depth, a custom business metric).

### KEDA — event-driven scaling and scale-to-zero

A KEDA `ScaledObject` wraps an existing Deployment/StatefulSet and, under the hood, creates and manages a standard HPA object — KEDA itself is the metrics adapter feeding that HPA external, event-source-derived values (Kafka consumer group lag, SQS `ApproximateNumberOfMessages`, a raw Prometheus query result, a cron-based schedule) instead of just CPU/memory. The capability plain HPA fundamentally cannot provide: `minReplicaCount: 0`. HPA's ratio-based algorithm requires at least one running replica to compute a scaling ratio against; KEDA adds a separate, lightweight polling mechanism that watches the external event source directly while the Deployment sits at zero replicas, and scales it up from zero the moment there's real work to do — a genuine cost win for spiky, idle-most-of-the-time workloads, at the direct cost of cold-start latency on whatever request or event triggers that first scale-up.

### Cluster Autoscaler vs Karpenter, mechanically

**Cluster Autoscaler** watches for `Pending` pods that failed scheduling due to insufficient resources, and scales a matching pre-defined node group (an AWS ASG, a GCP managed instance group) — it's bound by the node group's pre-configured instance type/shape and by real cloud provisioning + node bootstrap time, commonly landing in the **4-8 minute** range before the new node is `Ready` and schedulable. **Karpenter** (AWS-native, now expanding elsewhere) skips node groups as a concept entirely: it directly calls cloud provisioning APIs for whatever specific instance type best fits the actual pending pod's resource requirements from a broad allowed set, typically online in **45-60 seconds**, and continuously **consolidates** — proactively identifying underutilized nodes and replacing or removing them for tighter bin-packing, an ongoing cost optimization loop rather than a purely reactive one. Both approaches share one critical dependency: **a pod with no resource requests set is invisible to both** — neither tool can determine that a zero-request pod is genuinely unschedulable due to resource shortage (as opposed to some other scheduling constraint entirely), so it simply never triggers a scale-up decision, which is why "set requests on everything" is as much an autoscaling-correctness requirement as a scheduling one.

### GPU scheduling — non-fungible by default

GPUs are exposed to Kubernetes via the **device plugin framework** as extended resources (`nvidia.com/gpu`), requested exclusively as a **limit** (`resources.limits: {nvidia.com/gpu: 1}` — there's no meaningful "GPU request" separate from the limit the way there is for CPU/memory, since GPUs aren't shareable via the scheduler's normal fractional bin-packing logic at all by default). A pod requesting `1` gets exactly one whole physical GPU; the device plugin framework has no built-in concept of fractional allocation. Genuine GPU sharing requires an explicit, additional mechanism: **time-slicing** (multiple pods logically share one physical GPU's compute time in software, with no memory isolation between them and real contention risk if workloads actually overlap in their busy periods) or **MIG** (Multi-Instance GPU, hardware-level partitioning available on A100/H100-class NVIDIA cards, splitting one physical GPU into multiple fully isolated instances with dedicated memory and compute, the materially safer sharing mechanism but requiring MIG-capable hardware and static partition configuration decided ahead of time). GPU node pools are near-universally **tainted** (commonly something like `nvidia.com/gpu=present:NoSchedule`) to keep ordinary CPU-only workloads off expensive GPU nodes, which means any pod that actually needs a GPU must carry the matching **toleration** or it silently never schedules there — the exact same mechanic covered for DaemonSets, applying here with real cost stakes if a team forgets it and wonders why a GPU workload sits `Pending` despite GPU nodes clearly existing and having capacity.

### Where service mesh fits into this picture

A service mesh's sidecar proxy (Envoy in Istio/Linkerd-style deployments) adds its own CPU/memory footprint to every pod it's injected into, and that overhead is easy to leave out of capacity planning: HPA computing CPU utilization against a pod's *total* container CPU usage (app container plus sidecar) means sidecar overhead directly shifts when scale-out triggers, and VPA recommendations for the app container alone can undercount real pod-level resource needs if the sidecar's footprint isn't accounted for separately. This isn't a reason to avoid a mesh, but it is a real, commonly-missed line item in the requests/limits math covered above — a mesh-injected fleet needs its autoscaling metrics and resource sizing to explicitly account for sidecar resource consumption, not just the application container's own numbers, or HPA/VPA both end up making decisions against an incomplete picture of what's actually consuming the pod's resources.

---

## Build it from scratch

```yaml
# untested sketch — HPA tuned against flapping, plus a KEDA ScaledObject for
# a queue-driven worker that should scale to zero when idle
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: api }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: api }
  minReplicas: 3
  maxReplicas: 30
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: { type: Utilization, averageUtilization: 70 }
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # require 5 min of sustained low usage before
                                          # scaling down, prevents flapping on brief dips
      policies:
      - { type: Pods, value: 2, periodSeconds: 60 }  # never remove more than 2 pods/min
    scaleUp:
      stabilizationWindowSeconds: 0      # react to spikes immediately
      policies:
      - { type: Percent, value: 100, periodSeconds: 60 }  # can double the fleet in 60s
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: { name: order-worker }
spec:
  scaleTargetRef: { name: order-worker }
  minReplicaCount: 0        # <- the thing plain HPA cannot do at all
  maxReplicaCount: 50
  cooldownPeriod: 120        # seconds of zero-triggering activity before scaling to 0
  triggers:
  - type: aws-sqs-queue
    metadata:
      queueURL: https://sqs.us-east-1.amazonaws.com/123456789/orders
      queueLength: "5"        # target ~5 messages per replica
```

```yaml
# untested sketch — GPU pod with correct toleration, deliberately omitting a CPU
# limit for a latency-sensitive inference container while keeping a memory limit
apiVersion: v1
kind: Pod
metadata: { name: inference }
spec:
  tolerations:
  - { key: "nvidia.com/gpu", operator: "Exists", effect: "NoSchedule" }
  containers:
  - name: inference
    image: myrepo/inference:v4
    resources:
      requests: { cpu: "2", memory: "8Gi" }
      limits: { memory: "8Gi", nvidia.com/gpu: 1 }   # no CPU limit — avoid CFS throttling
                                                        # on a latency-critical path; memory
                                                        # limit stays for OOM protection
```

---

## How it's done in production

Real production autoscaling stacks combine all three layers deliberately rather than enabling each independently: VPA in recommend-only mode informing periodic, human-reviewed adjustments to baseline requests; HPA (or KEDA for anything queue-shaped) driving replica count off a business-meaningful metric rather than raw CPU; Karpenter or Cluster Autoscaler underneath, sized against real headroom rather than running at the ragged edge. For genuinely latency-critical services, many teams deliberately set `requests == limits` for memory (Guaranteed-adjacent sizing, predictable OOM behavior) while omitting a CPU limit entirely, accepting the tradeoff of losing hard noisy-neighbor CPU ceiling protection in exchange for eliminating CFS-quota throttling risk on the exact workloads where tail latency matters most.

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency is bad, but CPU utilization dashboards show comfortable headroom | CFS quota throttling within individual 100ms periods, invisible to a smoothed average | Check `container_cpu_cfs_throttled_periods_total` ratio in Prometheus/cAdvisor; raise or remove the CPU limit for that workload |
| HPA replica count oscillates up and down repeatedly under steady load | No/insufficient `stabilizationWindowSeconds` on scale-down, or a noisy underlying metric | Tune `behavior.scaleDown.stabilizationWindowSeconds` (commonly 300s+); consider smoothing or switching to a less noisy metric |
| VPA and HPA are both active on a Deployment, replica count and per-pod sizing both drift unpredictably | Both configured against the same metric (commonly CPU), creating a feedback loop | Split responsibility: VPA on memory or `updateMode: Off` (recommend-only), HPA on a genuinely independent scale-driving metric |
| Cluster autoscaler/Karpenter never scales up despite pods stuck `Pending` for resource reasons | Pods have no resource requests set — both tools ignore pods with zero requests entirely, since they can't determine the pod is unschedulable due to resource shortage | Set explicit `resources.requests` on every workload; treat missing requests as a scheduling *and* autoscaling correctness bug |
| A traffic spike causes a real multi-minute outage window before new capacity comes online | Cluster Autoscaler against slow-bootstrapping node groups (4-8 min typical) can't keep pace with the spike's actual timescale | Migrate to Karpenter (45-60s typical) for faster response, or maintain deliberate warm/buffer capacity for the specific bursty paths that can't tolerate multi-minute cold-start delay |
| GPU pod stuck `Pending` despite GPU nodes existing with visible free capacity | Missing toleration for the GPU node pool's taint | Add the matching `tolerations` entry to the pod spec |
| Two GPU-inference pods land on the same GPU node and one fails with an out-of-GPU-memory error | GPUs aren't fractionally shared by default; both pods assumed sharing "just worked" | Configure MIG partitions (hardware-isolated, safer) or explicit time-slicing (software-shared, no isolation) rather than assuming co-scheduling on one physical GPU is automatically safe |

---

## Tradeoffs & when NOT to use it

- **Don't set a CPU limit reflexively "for safety" on latency-sensitive services** without understanding CFS quota mechanics — for many workloads, the limit itself is the thing causing the tail-latency problem, not protecting against one; this is a genuine, actively-debated tradeoff against noisy-neighbor protection in shared clusters, not a universal rule either way.
- **Don't run VPA in `Auto`/`Recreate` mode on stateful or eviction-sensitive workloads.** The eviction-driven resize cycle (pre-in-place-resize) causes real disruption; `Off` (recommend-only, human-reviewed) is the safer default for most production services, reserving automated action for workloads that genuinely tolerate frequent restarts.
- **Don't reach for KEDA scale-to-zero on anything with meaningful cold-start latency** — a JVM warming up, a large ML model loading into memory — the cost savings of scaling to zero are directly paid for by the first request after idle being slow, sometimes unacceptably so for user-facing paths; scale-to-zero fits background/batch/internal-queue workloads far better than latency-sensitive request paths.
- **Don't adopt Karpenter without accounting for its AWS-centric maturity and the operational learning curve of a genuinely different provisioning model** — teams on multi-cloud, or on clouds where Karpenter's support is less mature, may be better served by Cluster Autoscaler's more uniform (if slower) behavior across providers.
- **Don't autoscale GPU node pools with the same aggressive scale-down instincts used for CPU fleets.** GPU capacity is scarce, expensive, and often has real provisioning lead time; for bursty ML/inference workloads, keeping a deliberate warm buffer can be cheaper and more reliable than accepting the latency and cost of constant GPU node churn.

---

## Interview questions

### Q1 — Explain, mechanically, why a container can be badly throttled while its CPU usage graph shows plenty of headroom.
**Testing:** the core CFS quota/period mechanism, the single most-tested fact in this module.
**Answer:** A CPU limit is enforced via the cgroup's CFS quota over discrete periods, default 100ms — a 0.5 CPU limit becomes a 50ms quota per 100ms period. If the container's usage exceeds that quota within any single period, it's throttled (paused) for the rest of that period, resuming next period. A 60-second average utilization graph smooths this completely away — dozens of brief, real throttle events can occur within a minute that looks fine on average, because the average doesn't reveal per-period spikes, only the mean across many periods.
**Follow-up trap:** *"What metric actually reveals this, and what would you do about it?"* — `container_cpu_cfs_throttled_periods_total` divided by `container_cpu_cfs_periods_total` (Prometheus/cAdvisor) shows the real throttle ratio; the fix is raising or removing the CPU limit for that specific workload, since the limit itself is the direct cause, not some separate capacity problem.

### Q2 — Why is a memory limit a fundamentally different kind of enforcement than a CPU limit?
**Testing:** whether the two are understood as mechanically distinct rather than "limits are limits."
**Answer:** A CPU limit throttles — a soft, repeated, silent degradation via CFS quota enforcement, no process termination. A memory limit is a hard ceiling enforced by the kernel's cgroup OOM killer: exceed it, and the container is killed immediately (exit code 137), with no throttling, no partial degradation, no grace period. Conflating the two — treating "set limits" as one uniform practice — misses that CPU limits fail silently into bad tail latency while memory limits fail loudly and immediately.
**Follow-up trap:** *"Does this mean you should always set a memory limit even when avoiding a CPU limit?"* — generally yes, for most services: an unbounded memory leak with no limit can consume an entire node's memory and cause the kubelet itself to become unstable or trigger broader node-pressure eviction of unrelated pods, whereas a bounded memory limit contains the blast radius to just the offending container, a real and different safety property worth keeping even while deliberately omitting the CPU limit.

### Q3 — What determines a pod's QoS class, and why does it matter under node memory pressure?
**Testing:** the practical consequence of requests/limits configuration choices.
**Answer:** Guaranteed (every container's requests equal its limits, both CPU and memory), Burstable (requests set but differ from limits on at least one resource), BestEffort (neither requests nor limits set). Under node memory pressure, eviction order is BestEffort first, then Burstable (ordered by how far actual usage exceeds requests), Guaranteed last — so QoS class is a direct, practical consequence of how requests/limits are configured, not a separate setting.
**Follow-up trap:** *"Is Guaranteed QoS strictly the best choice for every workload?"* — no: it requires setting CPU limits equal to requests, which reintroduces the CFS throttling risk discussed above for exactly the latency-sensitive workloads that might otherwise most want eviction priority — there's a real tension between "protect this pod from eviction" (favors Guaranteed) and "avoid CPU throttling" (favors no CPU limit at all, which is Burstable at best), and the right choice depends on which failure mode is worse for that specific workload.

### Q4 — Why is running HPA and VPA against the same metric considered an anti-pattern?
**Testing:** understanding of the feedback-loop mechanism, not just "you're not supposed to do that."
**Answer:** VPA adjusting a pod's CPU request changes the denominator HPA uses to compute utilization percentage against that same metric, which can trigger HPA to change replica count, which changes per-pod load and thus VPA's own observed usage, which can trigger another VPA recommendation change — an oscillating feedback loop where neither controller has a stable signal to converge against. The safe pattern splits responsibility: VPA sizing a dimension HPA isn't tracking (commonly memory) or running in recommend-only mode, with HPA driving scale-out off an independent, ideally business-meaningful metric.
**Follow-up trap:** *"If VPA is set to `updateMode: Off`, is it now safe to also run HPA on CPU?"* — yes, and this is exactly the recommended safe combination: `Off` mode means VPA never actually changes anything automatically, it only produces recommendations for humans to review and apply deliberately, so there's no live feedback loop between the two controllers even though both are technically "watching" related signals.

### Q5 — What can KEDA do that plain HPA fundamentally cannot, and why?
**Testing:** the scale-to-zero mechanism specifically, and why it's structurally impossible for HPA alone.
**Answer:** Scale a Deployment to zero replicas when idle and scale it back up from zero the moment there's real work. HPA's algorithm computes `desiredReplicas` as a ratio against `currentReplicas`, which requires at least one running replica to have a metric to compute against in the first place — there's no way for HPA alone to observe "should I scale from 0 to 1" since zero replicas means zero metric data. KEDA adds a separate, lightweight polling mechanism watching the external event source directly (independent of any running pod), which is what enables the zero-to-something transition, then hands off to a standard HPA object it manages once replicas are back above zero.
**Follow-up trap:** *"What's the real cost of using scale-to-zero for a user-facing API path?"* — cold-start latency on whatever request triggers the scale-up from zero — the first request has to wait for a full pod (and possibly container image pull, app initialization, connection pool warmup) to become ready before it can even be routed, which can be seconds to tens of seconds depending on the workload, a real and sometimes unacceptable latency hit for a genuinely user-facing, latency-sensitive path even though it's a good fit for internal/batch/queue-consumer workloads.

### Q6 — Cluster Autoscaler/Karpenter aren't scaling up even though pods are stuck `Pending`. What's the most common root cause?
**Testing:** the zero-requests trap, a very real and common production bug.
**Answer:** The pending pods have no `resources.requests` set. Both tools decide whether to scale up by determining that a pod is unschedulable specifically due to insufficient resources across existing nodes — a pod with zero requests provides no signal that resource shortage is the actual blocker, so it's simply invisible to the scale-up decision logic, and the pods sit `Pending` indefinitely with no new capacity ever provisioned in response.
**Follow-up trap:** *"If the team fixes this by adding requests, is that sufficient, or could something else still block scale-up?"* — adding requests is necessary but not always sufficient — check whether the pending pods also have affinity/taint requirements no available node group/provisioner configuration can satisfy (e.g. requiring a specific instance type or zone the autoscaler isn't configured to provision), since that's a separate class of blocker that setting requests alone doesn't resolve.

### Q7 — Compare Cluster Autoscaler and Karpenter's actual provisioning mechanics, with real numbers.
**Testing:** currency and precision on a genuinely fast-moving part of the ecosystem.
**Answer:** Cluster Autoscaler watches for unschedulable pods and scales a pre-defined node group (ASG/MIG), bound by that group's fixed instance type/shape and real cloud provisioning plus node bootstrap time — commonly 4-8 minutes to a `Ready` node. Karpenter skips node groups entirely, calling cloud provisioning APIs directly for whatever specific instance type best fits the actual pending pod's requirements from a broad allowed set, typically online in 45-60 seconds, and continuously consolidates (proactively replacing underutilized nodes) as an ongoing bin-packing optimization Cluster Autoscaler doesn't perform the same way.
**Follow-up trap:** *"Given Karpenter is faster and cheaper via consolidation, why would anyone still choose Cluster Autoscaler today?"* — multi-cloud consistency and relative operational maturity outside AWS — Karpenter's support and community maturity is strongest on AWS, and a team running the same autoscaling approach uniformly across AWS/GCP/Azure, or simply more familiar with and better tooled around Cluster Autoscaler's behavior, may reasonably prioritize that consistency over the raw speed/cost advantage on any single cloud.

### Q8 — Why is a GPU request expressed only as a limit, and what does "1 GPU" actually get you?
**Testing:** understanding of the device plugin framework's non-fractional default behavior.
**Answer:** GPUs are exposed as extended resources via the Kubernetes device plugin framework, requested via `resources.limits` (there's no separate meaningful "GPU request" the way CPU/memory have distinct request-vs-limit semantics, since the scheduler's normal fractional bin-packing logic doesn't apply to GPUs by default). Requesting `nvidia.com/gpu: 1` gets exactly one whole physical GPU — the device plugin framework has no built-in fractional allocation mechanism at all.
**Follow-up trap:** *"How would you actually share one physical GPU across multiple pods, and what's the tradeoff between the two real options?"* — MIG (hardware-level partitioning on A100/H100-class cards into fully isolated instances with dedicated memory and compute — safer, but requires MIG-capable hardware and static partition configuration decided ahead of time) or time-slicing (software-level sharing of one GPU's compute time across pods, with no memory isolation and real contention risk if workloads' busy periods actually overlap) — MIG trades flexibility for isolation, time-slicing trades isolation for flexibility and broader hardware compatibility.

### Q9 — A GPU pod is stuck `Pending` and `kubectl describe node` shows a GPU node with visible free GPU capacity. What's the most likely cause?
**Testing:** direct application of the taint/toleration mechanic to GPU scheduling specifically, tying back to the DaemonSet module.
**Answer:** Missing toleration for the GPU node pool's taint — GPU nodes are near-universally tainted (e.g. `nvidia.com/gpu=present:NoSchedule`) to keep ordinary CPU-only workloads off expensive GPU capacity, and a pod without the matching toleration is excluded from scheduling there exactly like any other tainted-node exclusion, regardless of whether it's requesting a GPU resource itself.
**Follow-up trap:** *"If the toleration is added and the pod still won't schedule, what's the next thing to check?"* — whether the pod's GPU resource request can actually be satisfied given other pods already occupying GPU capacity on that node (GPUs are whole-unit allocations by default, so a node with 8 GPUs and 8 single-GPU pods already running has zero free GPU capacity left regardless of how much CPU/memory headroom remains), and whether any node affinity/selector requirements match the actual labels present on that specific GPU node pool.

### Q10 — When would you deliberately choose not to set a CPU limit on a workload, and what are you giving up by doing that?
**Testing:** the senior "when NOT to" call, applied to the module's central trap.
**Answer:** For latency-sensitive services where tail latency matters more than strict per-pod CPU ceiling enforcement — omitting the CPU limit avoids CFS-quota throttling entirely for that workload, letting it burst above its request when the node has spare capacity, which is often exactly the behavior wanted for handling occasional load spikes without artificial pauses. What's given up: hard noisy-neighbor protection — without a CPU limit, that workload can consume spare node capacity that another co-located workload might have wanted, and in a genuinely resource-constrained or multi-tenant shared cluster, that tradeoff can be the wrong one, which is why this isn't a universal recommendation.
**Follow-up trap:** *"How do you reconcile 'no CPU limit' with wanting predictable capacity planning at the node/cluster level?"* — capacity planning still works off requests, not limits, since requests are what the scheduler bin-packs against — the node-level guarantee is "every pod gets at least its requested CPU share under contention," and omitting the limit only affects whether a pod can burst *above* its request when spare capacity exists, which is a separate concern from whether enough aggregate capacity was provisioned in the first place.

---

## Red flags that fail you

- Explaining CPU limits without mentioning CFS quota/period mechanics, or claiming a limit is a smoothed average cap.
- Not knowing the difference in failure mode between a CPU limit (throttling) and a memory limit (OOM kill).
- Recommending HPA and VPA both track the same metric without flagging the oscillation risk.
- Claiming HPA can scale to zero on its own, without KEDA or an equivalent event-driven mechanism.
- Not knowing why zero-resource-request pods are invisible to Cluster Autoscaler/Karpenter.
- Assuming GPUs are fractionally shareable by default, or not knowing the difference between MIG and time-slicing.
- Recommending scale-to-zero for a latency-sensitive, user-facing request path without acknowledging cold-start cost.

---

## Cheat card

```
REQUESTS: scheduler bin-packing input + cgroup CPU SHARES (relative weight, not ceiling)
LIMITS: CPU = CFS quota/period (default 100ms period, quota = limit x period). Exceed
  quota within ONE period -> THROTTLED that period. 60s avg CPU can look fine while
  throttled dozens of times/min -> check container_cpu_cfs_throttled_periods_total ratio
  MEMORY = hard ceiling, kernel OOM-kills immediately on exceed (exit 137), NOT throttled

QoS: Guaranteed (req==limits both cpu+mem, evicted LAST) > Burstable (req set, differs
  from limits) > BestEffort (neither set, evicted FIRST under node pressure)

HPA: autoscaling/v2, desiredReplicas = ceil(current * (currentMetric/desiredMetric))
  sync interval 15s default. scaleDown stabilizationWindowSeconds default 300s (prevents
  flapping), scaleUp near-immediate default. CANNOT scale to 0 (needs >=1 replica for ratio)

VPA: recommender + updater + admission webhook. updateMode: Off = recommend-only (SAFE
  default for prod). Auto/Recreate = evicts to apply (churn risk) — in-place resize
  reduces this. NEVER point VPA + HPA at the SAME metric -> oscillating feedback loop

KEDA: wraps/creates a standard HPA under the hood, adds 60+ external scalers (Kafka lag,
  SQS depth, Prometheus query, cron) + minReplicaCount: 0 (scale-to-zero HPA can't do)
  tradeoff: cold-start latency on first request after scaling from zero

CLUSTER AUTOSCALER: node-group based (ASG/MIG), ~4-8min provision time
KARPENTER: direct cloud API, no node groups, ~45-60s provision, continuous consolidation
  BOTH ignore pods with NO resource requests set entirely — set requests or no scale-up

GPU: device plugin framework, nvidia.com/gpu extended resource, LIMIT only, WHOLE units
  by default (not fractional). Sharing needs MIG (hardware partition, A100/H100-class,
  isolated) or time-slicing (software, no isolation). GPU node pools TAINTED — need
  explicit tolerations or pod silently never schedules there despite free GPU capacity

MESH: sidecar CPU/mem overhead counts toward HPA's total-pod-CPU calc and VPA sizing —
  account for it separately, not just the app container's own numbers
```

## Sources

- [Karpenter vs Cluster Autoscaler: Which to Use in 2026 — CAST AI](https://cast.ai/blog/karpenter-vs-cluster-autoscaler/) — accessed 2026-08-02
- [Karpenter vs Cluster Autoscaler: 2026 Comparison Guide for EKS Teams — ScaleOps](https://scaleops.com/blog/karpenter-vs-cluster-autoscaler/) — accessed 2026-08-02
- Kubernetes documentation — Horizontal Pod Autoscaling, Vertical Pod Autoscaler (`autoscaling.k8s.io`), Resource Management for Pods and Containers
- KEDA official documentation, `keda.sh` — scalers reference and ScaledObject spec
- NVIDIA documentation — GPU device plugin, Multi-Instance GPU (MIG), time-slicing configuration
- CFS scheduler / cgroup v2 quota-period semantics — Linux kernel documentation

## Changelog
- 2026-08-02 — created
