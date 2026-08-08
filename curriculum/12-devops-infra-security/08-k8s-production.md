# Production K8s: Probes, PDBs, Requests/Limits, Rollouts, Multi-Tenancy, Cost

> **Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **Prereqs:** T12-k8s-scaling, T12-k8s-troubleshooting
> **Module id:** `T12-k8s-production` · **Tags:** k8s, critical
> **Lab:** `labs/k8s/08-k8s-production/`

## The 30-second version

Production-grade Kubernetes is mostly a discipline problem, not a features problem: the primitives (probes, PDBs, RollingUpdate, ResourceQuota) have been stable for years, and almost every real incident traces back to one of them being configured naively rather than mechanically understood. The single most common zero-downtime-deployment bug is a readiness probe that returns healthy before the app can actually serve traffic, or a rolling update that removes the old pod from the Service's endpoints *before* in-flight requests finish draining — the fix is a `preStop` hook that sleeps past the time it takes `kube-proxy`/the Endpoints controller to propagate the removal (commonly a few seconds), combined with the app itself catching `SIGTERM` and finishing in-flight work instead of dying immediately. A `PodDisruptionBudget` protects against *voluntary* disruptions only — node drains, cluster upgrades, `kubectl evict` — and is explicitly powerless against a node hard-crashing, a `HorizontalPodAutoscaler` scaling down, or an involuntary disruption of any kind; conflating "I have a PDB" with "I'm protected from downtime" is a real, common overclaim. Multi-tenancy in vanilla Kubernetes is soft isolation by default — a `Namespace` alone provides zero resource isolation; `ResourceQuota` (namespace-wide caps) and `LimitRange` (per-container defaults and ceilings) have to be applied together, and even then two tenants share a kernel, a network stack, and a scheduler unless something stronger (dedicated node pools, gVisor/Kata sandboxing, or genuinely separate clusters) is layered on top. Cost is a direct, measurable consequence of over-requesting: the median cluster in cost-optimization audits runs at roughly 10-30% actual CPU utilization against requested capacity, meaning most of the bill pays for headroom nobody's using, and the fix is closing the loop between VPA/observed usage data and what's actually requested, not just buying reserved capacity.

## Why this gets asked

Because "I've run Kubernetes in production" and "I've actually been on-call for a multi-tenant cluster during a bad rollout or a cost review" are very different claims, and this is the section of the interview built to tell them apart. The interviewer has personally lived through a rollout that silently dropped requests because nobody understood that readiness-probe-passing and endpoint-propagation aren't instantaneous, an eviction storm during a routine node upgrade that took down a service because its PDB was misconfigured (or missing), a noisy-neighbor incident where one tenant's runaway job starved another's latency-critical pods because no ResourceQuota existed, or a cloud bill that tripled year over year because nobody was watching the gap between requested and actually-used capacity. They want to hear you reason about the mechanism and the failure mode, not recite that PDBs and probes exist.

---

## Lineage: past → present → future

**What came before.** Early production Kubernetes (roughly 2016-2018) treated liveness and readiness as the same concept — many early deployments configured only a liveness probe, or configured liveness and readiness identically, which meant a temporarily slow-but-recovering pod (a GC pause, a cold cache warming) got killed and restarted by the liveness probe instead of just being pulled from load balancing by readiness while it recovered on its own — a self-inflicted restart storm under exactly the load conditions that most needed the pod to stay up. Node draining for upgrades before `PodDisruptionBudget` existed (added in Kubernetes 1.4, 2016, and matured through several releases after) had no way to express "don't evict more than N of these at once," so a cluster upgrade or a bad `kubectl drain` could legitimately take an entire stateful service's replica set down simultaneously if they all happened to land on the node(s) being drained together. Resource isolation had a similarly rough start: before `ResourceQuota`/`LimitRange` were standard practice, "multi-tenant Kubernetes" commonly meant "one big shared namespace with no caps," and the predictable failure mode was a single team's batch job or memory leak starving every other tenant on the same nodes with zero warning or attribution.

**Where it stands now.** `startupProbe` (GA since Kubernetes 1.20, 2020) closed the biggest remaining probe design gap: before it existed, teams handling slow-starting applications (a JVM with a large classpath, a model-loading inference service) had to set `initialDelaySeconds` on the liveness probe generously high to avoid killing a legitimately-still-starting pod, which meant a *genuinely* hung pod during normal steady-state operation also had to wait that same long delay before liveness would ever catch it — `startupProbe` decouples the two concerns entirely, gating liveness/readiness checks until startup succeeds, then handing off to fast, tightly-tuned liveness/readiness intervals once the app is actually running. The current consensus on rollouts is `maxUnavailable: 0` combined with a correctly-draining `preStop` + `SIGTERM` handler for anything that can't tolerate dropped requests during a deploy, though the live disagreement is real: `maxUnavailable: 0` combined with `maxSurge` above 0 means a rollout always briefly runs *more* replicas than the steady-state count, which costs real, if temporary, capacity, and some teams deliberately accept `maxUnavailable: 1` for cost reasons on services with enough replica count that losing one briefly is genuinely a non-event. Multi-tenancy today mostly means "shared cluster, namespace-per-tenant, ResourceQuota + LimitRange + NetworkPolicy as the enforced baseline," with harder isolation (dedicated node pools via taints, or full separate clusters) reserved for tenants with genuine compliance/blast-radius requirements — vanilla namespace isolation is explicitly understood industry-wide as *soft* isolation, not a security boundary on its own. Cost visibility matured significantly with Kubecost/OpenCost (OpenCost became a CNCF project, the open specification Kubecost is built on), which attribute cluster spend down to namespace/label/workload with commonly-cited accuracy in the ~97% range for on-demand cost allocation — turning "the cloud bill is high" from a guess into an actual per-team, per-workload number teams can act on.

**Where it's heading.** Kubernetes 1.34-1.36 (the 2026 release line) continues incremental hardening of the disruption/eviction API surface and multi-tenancy primitives, but nothing here is undergoing the kind of foundational rework autoscaling or GPU scheduling are — this is the mature, stable part of the platform. The bigger live movement is in cost tooling maturity: continuous rightsizing (VPA recommendations feeding automated, low-risk request adjustments rather than purely advisory dashboards) and FinOps-for-Kubernetes practices are becoming default expectations at mid-size-and-up companies rather than a specialized extra, though "fully automated, safe rightsizing with no human review" remains something to be honestly skeptical of in an interview answer — treat it as directionally real and increasingly common, not a solved problem everywhere yet.

---

## Mental model

```
ROLLOUT SAFETY, layered:
  ┌──────────────────────────────────────────────────────────────┐
  │ 1. startupProbe   — gates everything below until app is UP     │
  │ 2. readinessProbe — controls Service endpoint membership        │
  │                      (pulled OUT of LB before traffic stops)     │
  │ 3. livenessProbe  — controls restart, only for GENUINELY hung   │
  │                      processes, tuned looser than readiness       │
  └──────────────────────────────────────────────────────────────┘
             │
             ▼  a deploy replaces pods under RollingUpdate:
  maxUnavailable: 0   -> never drop below current replica count
  maxSurge: 1 (or N)  -> temporarily run MORE than steady-state count
             │
             ▼  and PREVENTS too many going away at once during
                VOLUNTARY disruption (drain / upgrade / evict):
  PodDisruptionBudget: minAvailable / maxUnavailable
     PROTECTS AGAINST: node drain, cluster upgrade, kubectl evict
     DOES NOT PROTECT AGAINST: node crash, HPA scale-down, OOM-kill,
                                any INVOLUNTARY disruption

MULTI-TENANCY, layered (weakest -> strongest isolation):
  Namespace alone         -> naming/RBAC scope only, ZERO resource isolation
  + ResourceQuota          -> namespace-wide caps (total cpu/mem/pvc count/etc.)
  + LimitRange              -> per-container default + max request/limit
  + NetworkPolicy            -> network-level isolation between tenants
  + dedicated node pools      -> physical separation via taints/tolerations
  + separate clusters          -> full blast-radius isolation (most expensive)

COST: bill ≈ Σ(node cost), independent of whether requests are USED
  gap between REQUESTED and ACTUALLY USED = the money you're burning
  -> this is exactly what VPA (scaling module) + Kubecost/OpenCost measure
```

---

## How it actually works

### Probes, precisely

Three probe types, each answering a different question, and conflating them is the single most common production mistake in this module:

- **`startupProbe`** answers "has this container finished starting yet at all." While it's configured and failing, `livenessProbe` and `readinessProbe` are **not executed** — the kubelet defers to `startupProbe` exclusively during this phase. Once `startupProbe` succeeds once, it's never checked again for that container's lifetime, and liveness/readiness take over with their own independently-tuned schedules. This is the mechanism that lets a slow-starting JVM or model-loading service have a generous startup allowance (`failureThreshold: 30, periodSeconds: 10` = up to 5 minutes to start) without that same generous tolerance leaking into steady-state liveness checking.
- **`readinessProbe`** answers "should this pod currently receive traffic." A failing readiness probe removes the pod from the Service's `Endpoints`/`EndpointSlice` — **no restart happens**, the container keeps running, it's simply pulled out of load balancing until it passes again. This is the correct tool for "temporarily can't serve traffic" (warming a cache, a downstream dependency briefly unavailable, graceful shutdown draining).
- **`livenessProbe`** answers "is this process hopelessly stuck and needs to be killed and restarted." A failing liveness probe triggers a container restart (subject to the `CrashLoopBackOff` mechanics from the troubleshooting module). This should be tuned *looser* than readiness — a process that's briefly slow (a GC pause, a burst of legitimate load) should fail readiness (pulled from traffic) well before it would ever fail a liveness check (restarted), because restarting a merely-slow-but-recovering process is strictly worse than just not sending it new traffic for a few seconds.

**The zero-downtime deploy sequence, mechanically, and where it actually breaks:**

1. New pod starts, passes `startupProbe`, then `readinessProbe` starts passing → added to the Service's `Endpoints`.
2. Old pod is selected for termination (by the rolling update controller). Kubernetes sends `SIGTERM` and, **simultaneously**, begins removing the pod from `Endpoints`/`EndpointSlice`.
3. **The race**: `Endpoints` removal is not instantaneous — it has to propagate through the Endpoints controller to every `kube-proxy` (or equivalent dataplane) on every node, which takes real, measurable time (commonly low single-digit seconds, more under load or with a large cluster). If the container process dies (from `SIGTERM`) *before* that propagation finishes, some fraction of in-flight and freshly-routed requests hit a pod that's already gone, producing connection resets or 5xx errors during every single deploy.
4. **The fix**: a `preStop` hook that sleeps for slightly longer than worst-case endpoint-propagation time (a `sleep 5`-`sleep 15` is a common, workload-dependent range) *before* the container actually receives `SIGTERM` — the pod stays in `Terminating` state, still accepting connections, for that window, letting propagation catch up before the process actually starts shutting down. The application itself must also handle `SIGTERM` gracefully (stop accepting new connections, finish in-flight ones, then exit) rather than dying immediately — a `preStop` sleep alone doesn't help if the app ignores `SIGTERM` or treats it as instant-death.

```yaml
# untested sketch — the full pattern together
spec:
  containers:
  - name: api
    startupProbe:
      httpGet: { path: /healthz, port: 8080 }
      failureThreshold: 30
      periodSeconds: 10          # up to 5 min to start before liveness ever engages
    readinessProbe:
      httpGet: { path: /ready, port: 8080 }
      periodSeconds: 5
      failureThreshold: 2         # pulled from traffic fast when genuinely not ready
    livenessProbe:
      httpGet: { path: /healthz, port: 8080 }
      periodSeconds: 10
      failureThreshold: 5         # looser — restart only when truly stuck
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 10"]   # outlast endpoint propagation
    terminationGracePeriodSeconds: 40           # must exceed preStop sleep + app drain time
```

`terminationGracePeriodSeconds` (default **30s**) has to be large enough to cover the `preStop` sleep *plus* however long the app itself needs to drain in-flight requests after receiving `SIGTERM` — if the grace period expires first, the kubelet sends `SIGKILL` regardless of whether the app was mid-drain, silently truncating exactly the graceful shutdown the whole pattern was built to guarantee.

### PodDisruptionBudget — what it actually guarantees, and what it never claims to

A PDB (`minAvailable` or `maxUnavailable`, mutually exclusive on one PDB object) is checked by the **Eviction API** — the mechanism `kubectl drain` and cluster-autoscaler-driven node consolidation both go through. When an eviction request would violate the PDB (would drop available replicas below `minAvailable`, or above `maxUnavailable` gone), the eviction is **rejected**, and the caller (`kubectl drain`, the node upgrade tooling) has to wait and retry, not forced through.

```yaml
# untested sketch
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: api-pdb }
spec:
  minAvailable: 2       # at least 2 matching pods must remain Available at all times
  selector:
    matchLabels: { app: api }
```

**What it protects against (voluntary disruptions only):** `kubectl drain` for node maintenance, cluster/node-pool upgrades, Cluster Autoscaler/Karpenter consolidating nodes, manual `kubectl evict` calls. **What it does not protect against at all:** a node hard-crashing or becoming `NotReady` unexpectedly (no eviction request is ever made — the pods are just gone), a `HorizontalPodAutoscaler` deliberately scaling down replica count (that's the Deployment controller reducing desired replicas directly, not an eviction), an `OOMKilled` or `CrashLoopBackOff` pod dying on its own, or a `kubectl delete pod --force`. This distinction — voluntary vs. involuntary disruption — is the exact thing that separates a real understanding of PDBs from "I added a PDB so we're covered," and it's worth stating explicitly and unprompted in an interview answer.

A subtle, real operational trap: a PDB with `minAvailable` set equal to (or too close to) the Deployment's total replica count can **permanently block node drains** — if `minAvailable: 3` and the Deployment only ever runs 3 replicas, no eviction can ever succeed without violating the budget, and `kubectl drain` (or an automated node upgrade) will hang indefinitely waiting for an eviction that structurally can never be granted.

### Requests/limits and QoS in a multi-tenant cluster

Covered mechanically in the scaling module (CFS quota throttling, OOM-kill semantics, QoS eviction order) — the production-specific addition here is **enforcement across tenants**, not just within one workload:

- **`ResourceQuota`** caps total consumption *within a namespace* — `requests.cpu`, `requests.memory`, `limits.cpu`, `limits.memory`, object counts (`count/pods`, `count/persistentvolumeclaims`), and more. Critically, **once any `ResourceQuota` exists in a namespace covering compute resources, every pod created in that namespace must explicitly specify requests/limits for the covered resources, or its creation is rejected outright** — this is the mechanism that forces "always set requests" from a best-practice into an actually-enforced rule at the namespace level.
- **`LimitRange`** sets **defaults** (`default`, `defaultRequest`) applied automatically to any container that doesn't specify its own, plus **min/max bounds** on what any single container in the namespace is allowed to request — this is what stops one careless pod spec from requesting an entire node's worth of memory even in a namespace with an overall generous quota.
- Used together (a `LimitRange` alone, with no `ResourceQuota`, still lets the *aggregate* across all pods in the namespace be unbounded — only per-container bounds exist) they turn "please set reasonable requests" into an actually-enforced platform guarantee rather than a code-review convention.

### Rollout strategies, mechanically

`RollingUpdate` (the default `Deployment` strategy) is governed by `maxSurge` (how many *extra* pods above desired replica count can exist during the rollout) and `maxUnavailable` (how many *fewer* than desired replica count is tolerated during the rollout) — both accept absolute numbers or percentages, and both default to **25%** if unset. `maxUnavailable: 0` guarantees full capacity is maintained throughout the rollout (relying entirely on `maxSurge` to create new pods before removing old ones), at the direct cost of running above steady-state replica/resource consumption for the rollout's duration — a real, if temporary, cost and capacity consideration, not a free safety win. `Recreate` (the other built-in strategy) kills all existing pods before creating any new ones — genuinely simpler, but with real downtime by design, appropriate only for workloads that structurally can't run two versions simultaneously (a singleton with exclusive resource ownership, some stateful migrations).

Beyond the two built-in strategies, **progressive delivery** (canary, blue/green, automated analysis-gated rollout) is handled by tooling layered on top of the base primitives — Argo Rollouts or Flagger — not by `Deployment` itself, which has no native concept of "shift 10% of traffic, watch error rate, proceed or automatically roll back." This distinction matters in an interview: claiming "Kubernetes does canary deployments" without naming that it's an add-on (covered in depth in the CI/CD module) is a common imprecision.

---

## Build it from scratch

```yaml
# untested sketch — full production pattern: probes, PDB, ResourceQuota, LimitRange
# for a namespace hosting one tenant's API deployment
apiVersion: v1
kind: ResourceQuota
metadata: { name: team-checkout-quota, namespace: team-checkout }
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    count/pods: "100"
    count/persistentvolumeclaims: "10"
---
apiVersion: v1
kind: LimitRange
metadata: { name: team-checkout-limits, namespace: team-checkout }
spec:
  limits:
  - type: Container
    default: { cpu: "500m", memory: "512Mi" }        # applied if a pod omits limits
    defaultRequest: { cpu: "250m", memory: "256Mi" }   # applied if a pod omits requests
    max: { cpu: "4", memory: "8Gi" }                    # no single container can exceed this
    min: { cpu: "50m", memory: "64Mi" }
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: api-pdb, namespace: team-checkout }
spec:
  maxUnavailable: 1          # never more than 1 of these pods gone at once from a drain
  selector: { matchLabels: { app: checkout-api } }
---
apiVersion: apps/v1
kind: Deployment
metadata: { name: checkout-api, namespace: team-checkout }
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 2, maxUnavailable: 0 }   # full capacity maintained,
                                                           # briefly runs up to 8 pods
  selector: { matchLabels: { app: checkout-api } }
  template:
    metadata: { labels: { app: checkout-api } }
    spec:
      terminationGracePeriodSeconds: 40
      containers:
      - name: api
        image: myrepo/checkout-api:v12
        resources:
          requests: { cpu: "500m", memory: "1Gi" }
          limits: { memory: "1Gi" }              # deliberately no CPU limit — see scaling module
        startupProbe:
          httpGet: { path: /healthz, port: 8080 }
          failureThreshold: 30
          periodSeconds: 10
        readinessProbe:
          httpGet: { path: /ready, port: 8080 }
          periodSeconds: 5
          failureThreshold: 2
        livenessProbe:
          httpGet: { path: /healthz, port: 8080 }
          periodSeconds: 10
          failureThreshold: 5
        lifecycle:
          preStop: { exec: { command: ["sh", "-c", "sleep 10"] } }
```

---

## How it's done in production

Real production platforms wrap these primitives in policy enforcement (OPA Gatekeeper or Kyverno admission webhooks rejecting any pod spec missing requests/limits or probes, rather than relying on `ResourceQuota`'s reactive rejection alone) and cost observability (Kubecost/OpenCost scraping actual usage against requested capacity, attributing cost per namespace/label/team, and — increasingly — feeding VPA recommendations back as a request for the owning team to act on rather than pure dashboard reporting). A commonly cited operational target: **keep ResourceQuota "hit rate" below roughly 5%** in steady state — a quota that's constantly being bumped up in response to rejected pod creations means it was sized too tight and is actively blocking legitimate work, not protecting anything; a quota that's never approached at all is providing no real signal and might as well not exist, so it's periodically re-tuned against actual observed peak usage (commonly peak-plus-a-safety-margin in the 30-40% range) rather than set once and forgotten.

| Symptom | Cause | Fix |
|---|---|---|
| Every deploy causes a brief burst of 502/connection-reset errors | No `preStop` hook, or `preStop` sleep shorter than real Endpoints propagation time; app doesn't handle SIGTERM gracefully | Add `preStop: sleep N` tuned to actual propagation latency in that cluster; ensure the app stops accepting new work and drains in-flight requests on SIGTERM, not on process death |
| A node upgrade / `kubectl drain` hangs indefinitely on one namespace | PDB's `minAvailable` is set equal to (or too close to) the Deployment's actual replica count, so no eviction can ever satisfy it | Lower `minAvailable`/raise `maxUnavailable` relative to real replica count, or increase replica count to give the PDB real room |
| A team's runaway batch job degrades an unrelated team's latency-critical service on the same cluster | No `ResourceQuota` on the batch team's namespace, or shared nodes with no isolation stronger than namespaces | Apply ResourceQuota + LimitRange on every tenant namespace; consider dedicated node pools (taints/tolerations) for genuinely noisy or untrusted workloads |
| Pods restart repeatedly during legitimate slow startup (large JVM, model load) even though the app is healthy once up | No `startupProbe`; liveness probe's own `initialDelaySeconds` is too short for real startup time, or was set generously and now masks genuinely hung steady-state processes | Add a dedicated `startupProbe` with a generous `failureThreshold × periodSeconds`, and tune liveness independently and tighter for steady-state |
| Cloud bill keeps climbing despite no real traffic growth | Requests set once, never revisited, drifting further from actual usage as the app or traffic pattern changes; no cost attribution to make the gap visible to the owning team | Deploy Kubecost/OpenCost for namespace/workload-level attribution; feed VPA (recommend-only) observations back into periodic, human-reviewed request rightsizing |
| A canary rollout "works" in the demo but production traffic never actually shifts gradually | Assuming `Deployment`'s `RollingUpdate` does traffic-weighted canary analysis — it doesn't, it's just pod-count-based replacement with no traffic-shaping or metric-gated logic | Adopt Argo Rollouts or Flagger for genuine traffic-percentage canary with automated analysis and rollback (covered in the CI/CD module) |

---

## Tradeoffs & when NOT to use it

- **Don't set `maxUnavailable: 0` reflexively on every Deployment.** It guarantees full capacity during rollouts but always costs real, if temporary, extra resource consumption via `maxSurge`; for a service with high replica count and genuine tolerance for briefly running one fewer pod, `maxUnavailable: 1` is a legitimate, cheaper default.
- **Don't treat a PDB as a substitute for genuine redundancy.** A PDB with `minAvailable: 1` on a 2-replica Deployment "protects" you from a drain taking both down at once, but it does nothing for the far more likely failure mode of one replica already being unhealthy when the drain starts — PDBs manage *voluntary* disruption pacing, they don't create availability that isn't already there.
- **Don't rely on namespace isolation alone for genuinely untrusted or compliance-sensitive multi-tenancy.** A shared kernel, shared node network stack, and shared scheduler mean a sufficiently motivated or sufficiently buggy tenant can still affect others (noisy-neighbor CPU/network contention even under quota, or a container-escape-class vulnerability) — dedicated node pools, sandboxed runtimes (gVisor/Kata), or fully separate clusters are the actual answer once "soft isolation is good enough" stops being true for a given tenant.
- **Don't chase `Recreate` deploys "for simplicity" on anything user-facing.** The downtime is real and by design; reserve it for the narrow set of workloads that genuinely can't run two versions concurrently, and default to `RollingUpdate` for everything else even if it's marginally more configuration to get right.
- **Don't buy more reserved/committed cloud capacity as the first response to a high bill** before checking the requested-vs-actually-used gap. Reserved capacity locks in a discount on waste you haven't yet identified; rightsizing requests first, then committing capacity against the *corrected* baseline, is the right order of operations.

---

## Interview questions

### Q1 — Walk me through the exact mechanism by which a rolling deploy can cause dropped requests, even with a passing readiness probe.
**Testing:** whether the endpoint-propagation race is actually understood, not just "use readiness probes."
**Answer:** When a pod is terminated, `SIGTERM` is sent and `Endpoints`/`EndpointSlice` removal begins at roughly the same time — but propagating that removal to every node's `kube-proxy` (or equivalent) takes real, non-zero time. If the container process actually dies before that propagation completes, some in-flight or newly-routed requests hit a pod that's already gone. The fix is a `preStop` hook that delays actual shutdown past worst-case propagation time, combined with the app gracefully draining on `SIGTERM` rather than exiting immediately.
**Follow-up trap:** *"If you set `preStop: sleep 30` and `terminationGracePeriodSeconds: 30` (the default), what happens?"* — the kubelet sends `SIGKILL` at the grace period boundary regardless of whether the `preStop` hook or the app's own shutdown has finished, because the grace period budget covers *both* the `preStop` hook and the app's post-SIGTERM drain time combined — `terminationGracePeriodSeconds` must exceed `preStop` sleep plus real app drain time, not just accommodate one or the other.

### Q2 — What's the mechanical difference between readinessProbe failing and livenessProbe failing?
**Testing:** the most basic but most frequently confused distinction in this module.
**Answer:** A failing readiness probe removes the pod from Service `Endpoints` — no restart, the container keeps running, it's just pulled from load balancing until it passes again. A failing liveness probe triggers a container restart. Readiness should be tuned tighter/faster than liveness, since a briefly-slow-but-recovering process should be pulled from traffic well before it's ever considered "stuck enough to restart."
**Follow-up trap:** *"What actually goes wrong if you configure liveness and readiness with identical, tight thresholds?"* — a transient slowdown (GC pause, brief downstream dependency hiccup) that should have just meant "pull from traffic for a few seconds" instead triggers a restart, which is strictly worse — you lose the in-memory state/connections/warm caches of a process that was about to recover on its own, exactly the self-inflicted restart-storm pattern that was common before `startupProbe` and proper probe separation became standard practice.

### Q3 — What does `startupProbe` solve that couldn't be solved by just setting a generous `initialDelaySeconds` on liveness?
**Testing:** understanding why this feature exists rather than treating it as a syntax variant.
**Answer:** Before `startupProbe`, a generous `initialDelaySeconds` on liveness (needed to avoid killing a legitimately slow-starting app) applied to *every* liveness check for that container's entire lifetime, not just the startup window — meaning a genuinely hung process during normal steady-state operation also had to wait that same long delay before liveness would catch it. `startupProbe` gates liveness/readiness entirely until it succeeds once, letting startup have a generous allowance while steady-state liveness stays tightly tuned to catch real hangs fast.
**Follow-up trap:** *"Once `startupProbe` succeeds, is it ever checked again?"* — no, it succeeds once and is never re-evaluated for that container's lifetime; if the app were to somehow re-enter a startup-like state later (which shouldn't normally happen), only liveness/readiness would be evaluating it from that point forward, with no re-engagement of the startup allowance.

### Q4 — Explain precisely what a PodDisruptionBudget protects against, and what it explicitly does not.
**Testing:** the single most commonly overclaimed guarantee in this module.
**Answer:** It protects against voluntary disruptions only — `kubectl drain`, cluster/node upgrades, Cluster Autoscaler/Karpenter consolidation, manual eviction — all of which go through the Eviction API, which checks the PDB and rejects an eviction that would violate it. It provides zero protection against involuntary disruption: a node crashing outright, an `OOMKilled` pod, a `CrashLoopBackOff`, or an HPA/Deployment controller deliberately reducing replica count — none of those go through the Eviction API at all.
**Follow-up trap:** *"A team says 'we have a PDB so we're covered for availability.' What's the gap in that statement?"* — a PDB says nothing about whether the surviving replicas are actually healthy or sufficient to serve load — it only paces *how fast* voluntary disruptions can remove replicas, it doesn't create redundancy that wasn't already designed in, and it provides zero protection for the (often more common in practice) involuntary disruption cases.

### Q5 — A PDB with `minAvailable: 3` is applied to a Deployment that also runs exactly 3 replicas. What breaks, and when?
**Testing:** a specific, real operational trap, not just definitional knowledge.
**Answer:** No eviction can ever succeed without violating the budget — any voluntary eviction attempt (a node drain, a cluster upgrade) will be rejected indefinitely by the Eviction API, and `kubectl drain` or automated node-upgrade tooling will hang waiting for an eviction that structurally can never be granted, since dropping even one replica violates `minAvailable: 3` when only 3 exist.
**Follow-up trap:** *"How would you actually notice this before it blocks a real production maintenance window?"* — proactively check that `minAvailable`/`maxUnavailable` leaves real room relative to actual current replica count as part of PDB review, not just at creation time — replica counts can shrink over time (a deliberate scale-down, or an HPA reducing minimum replicas) while the PDB stays static, silently creating this exact deadlock later.

### Q6 — Why does a `ResourceQuota` existing in a namespace change pod creation behavior even for pods that don't reference it directly?
**Testing:** the enforcement mechanism, not just the definition.
**Answer:** Once any `ResourceQuota` covering compute resources exists in a namespace, every pod created in that namespace must explicitly specify requests/limits for the resources the quota covers, or the API server rejects pod creation outright — this is what turns "please set requests" from a code-review convention into an actually-enforced platform rule.
**Follow-up trap:** *"If a pod's requests aren't explicitly set but a `LimitRange` with `defaultRequest` exists in the namespace, does creation still fail?"* — no — `LimitRange` defaults are applied via admission *before* the `ResourceQuota` check runs, so a pod that omits requests still gets valid values injected automatically and passes; this is exactly why `LimitRange` and `ResourceQuota` are meant to be deployed together, not either alone.

### Q7 — What's the actual difference between `ResourceQuota` and `LimitRange`, and why do you need both?
**Testing:** whether the aggregate-vs-per-container distinction is clear.
**Answer:** `ResourceQuota` caps aggregate consumption across the whole namespace (total requested/limited CPU/memory, object counts). `LimitRange` sets per-container defaults and min/max bounds. A `LimitRange` alone doesn't cap the aggregate — many small, individually-compliant containers can still sum to an unbounded total. A `ResourceQuota` alone doesn't stop one careless pod spec from requesting an outsized share of the namespace's entire budget in one shot. Together, they bound both the individual and the aggregate.
**Follow-up trap:** *"A namespace has generous ResourceQuota headroom but a pod creation still fails with a quota-exceeded error. Why might that be, given headroom exists?"* — `ResourceQuota` can also cap object counts (`count/pods`, `count/persistentvolumeclaims`), not just compute — the namespace might have plenty of CPU/memory headroom left but have hit its pod-count or PVC-count ceiling, which is a completely separate dimension from the compute-resource numbers usually checked first.

### Q8 — Why is `maxUnavailable: 0` not simply "the correct default for everything"?
**Testing:** the senior "what's the real tradeoff" instinct.
**Answer:** `maxUnavailable: 0` forces the rollout to rely entirely on `maxSurge` to create new pods before removing old ones, meaning the cluster genuinely runs above steady-state replica count (and resource consumption) for the rollout's duration — real, if temporary, extra cost and required headroom. For a service with high replica count where briefly running one fewer pod is a genuine non-event, `maxUnavailable: 1` is a legitimate, cheaper choice; treating zero-unavailability as a universal default ignores that tradeoff.
**Follow-up trap:** *"Does `maxSurge` have any downside beyond cost?"* — yes — a large `maxSurge` on a resource-constrained cluster can itself cause new pods to go `Pending` if there isn't enough spare node capacity to actually run the surge pods alongside the still-running old ones, which can stall a rollout entirely rather than speeding it up, especially interacting badly with a slow cluster autoscaler if capacity isn't already available.

### Q9 — Does `Deployment`'s built-in `RollingUpdate` do canary/traffic-percentage rollouts?
**Testing:** a common, specific overclaim.
**Answer:** No — `RollingUpdate` replaces pods based on replica *count*, with no concept of traffic-percentage weighting, metric-gated progression, or automated rollback based on error rates. Genuine canary/progressive delivery requires additional tooling layered on top — Argo Rollouts or Flagger — which introduce their own CRDs (`Rollout`, `Canary`) and integrate with a service mesh or ingress controller's traffic-splitting capability plus a metrics source (Prometheus) for automated analysis.
**Follow-up trap:** *"If a team says 'we do canary deploys with Kubernetes,' how would you probe whether they actually mean traffic-weighted canary or just a rolling update with a fancy name?"* — ask specifically what decides to proceed or roll back, and on what signal — a genuine canary system references specific metrics/analysis templates and traffic percentages; if the answer is really just "we deploy a few pods first and watch dashboards manually," that's an informal rolling update, not automated progressive delivery, and the distinction matters for how much you can trust the safety claim under pressure.

### Q10 — A cluster's cloud bill has grown steadily with no corresponding traffic growth. Where do you start investigating?
**Testing:** whether cost is approached mechanically (requested vs. used) rather than just "buy reserved instances."
**Answer:** Start with the gap between requested and actually-used capacity per namespace/workload — Kubecost/OpenCost (or equivalent) attribution makes this visible directly; a cluster where actual CPU utilization sits well below requested capacity (commonly cited in the 10-30% range in unoptimized clusters) is paying for headroom nobody's using. The fix is closing that gap via VPA-informed rightsizing, not immediately buying more reserved capacity, which locks in a discount on the same waste.
**Follow-up trap:** *"A team resists lowering their requests even after seeing low utilization data — why might that be a legitimate concern, not just resistance to change?"* — bursty or seasonal workloads can show low *average* utilization while genuinely needing the requested headroom for real, if infrequent, peak load — the fix there isn't blindly cutting requests to match the average, it's checking peak usage specifically (not just average) before rightsizing, and possibly pairing lower baseline requests with autoscaling (HPA/VPA) to handle the bursts instead of static over-provisioning.

### Q11 — What's the difference in isolation strength between "separate namespaces" and "separate node pools," and when do you actually need the stronger option?
**Testing:** the tiered multi-tenancy mental model, and judgment about when soft isolation is insufficient.
**Answer:** Separate namespaces (even with ResourceQuota/LimitRange/NetworkPolicy) still share the same underlying nodes — same kernel, same node-level network stack, same scheduler making bin-packing decisions across tenants — meaning quota limits are enforced, but genuine noisy-neighbor effects (network contention, node-level resource pressure interactions) and any container-escape-class vulnerability can still cross tenant boundaries. Separate node pools (via taints/tolerations, or dedicated infrastructure) provide real physical separation. The stronger option is warranted once a tenant has genuine compliance requirements (data residency, regulatory isolation), is untrusted (a customer-facing multi-tenant SaaS platform running arbitrary tenant workloads), or has a business-critical blast-radius requirement that soft isolation's residual risk doesn't satisfy.
**Follow-up trap:** *"Does NetworkPolicy close the noisy-neighbor gap namespaces alone leave open?"* — no — `NetworkPolicy` controls which pods can talk to which over the network, it says nothing about CPU/memory/disk I/O contention on a shared node, which is a resource-scheduling isolation problem, not a network isolation problem; the two are commonly conflated but solve entirely different classes of cross-tenant risk.

### Q12 — Why might a team with a well-configured PDB and probes still experience downtime during a routine node upgrade?
**Testing:** staff-level synthesis — connecting PDB/probe correctness to a scenario where they're both right but still insufficient.
**Answer:** If the Deployment's replicas are unevenly distributed and a disproportionate number happen to land on the specific node(s) being drained simultaneously (no anti-affinity or topology spread constraint in place), the PDB can still permit an eviction sequence that, combined with poor pod distribution, leaves the *surviving* replicas concentrated in a way that a subsequent, unrelated failure (or the next node in a rolling upgrade sequence) tips availability below what's actually needed — the PDB was respected the whole time, but topology wasn't accounted for.
**Follow-up trap:** *"What's the specific primitive that addresses the pod-distribution half of this, separate from PDBs?"* — `topologySpreadConstraints` (or pod anti-affinity) at the Deployment/pod-template level, ensuring replicas are actually spread across nodes/zones rather than incidentally clustering — PDBs pace disruption rate, topology spread constraints control the starting distribution disruption is being paced against, and both are needed together for a real availability guarantee during maintenance.

---

## Red flags that fail you

- Claiming a PodDisruptionBudget protects against node crashes, OOM-kills, or HPA scale-down.
- Configuring liveness and readiness probes identically, or not knowing the mechanical difference between them (restart vs. endpoint removal).
- Not knowing that `startupProbe` gates liveness/readiness entirely until it succeeds once.
- Claiming `Deployment`'s `RollingUpdate` performs traffic-weighted canary analysis natively.
- Recommending "just add more reserved capacity" as a first response to a rising cloud bill without checking requested-vs-used utilization first.
- Treating namespace isolation alone as sufficient for genuinely untrusted or compliance-sensitive multi-tenancy.
- Not knowing that `ResourceQuota` forces explicit requests/limits on every pod in a covered namespace once it exists.

---

## Cheat card

```
PROBES: startupProbe gates liveness+readiness until it succeeds ONCE, then never rechecked
  readinessProbe FAIL -> pulled from Endpoints, NO restart, container keeps running
  livenessProbe  FAIL -> container RESTART (CrashLoopBackOff mechanics apply)
  tune readiness TIGHTER/faster than liveness (pull from traffic before you'd ever restart)

ZERO-DOWNTIME DEPLOY RACE: SIGTERM + Endpoints removal start ~simultaneously, but
  Endpoints propagation to every kube-proxy takes real seconds -> dying before propagation
  finishes drops in-flight/newly-routed requests
  FIX: preStop { sleep N > worst-case propagation } + app drains gracefully on SIGTERM
  terminationGracePeriodSeconds (default 30s) MUST exceed preStop sleep + app drain time

PDB: minAvailable | maxUnavailable, enforced via the EVICTION API
  PROTECTS: kubectl drain, node/cluster upgrade, autoscaler consolidation (VOLUNTARY only)
  DOES NOT PROTECT: node crash, OOMKill, CrashLoopBackOff, HPA/Deployment scale-down
  TRAP: minAvailable == current replica count -> NO eviction can ever succeed, drain hangs

ROLLOUT: RollingUpdate default maxSurge=25%, maxUnavailable=25% if unset
  maxUnavailable:0 = full capacity maintained, but runs ABOVE steady-state cost via maxSurge
  Recreate = kills all before creating any, real downtime, only for true singletons
  Deployment RollingUpdate has NO traffic-% canary — that's Argo Rollouts/Flagger, add-on

MULTI-TENANCY (weak->strong): Namespace alone = ZERO resource isolation
  + ResourceQuota (namespace-wide caps, ONCE PRESENT forces explicit requests/limits on
    every pod) + LimitRange (per-container default + min/max) -> use BOTH together
  + NetworkPolicy (network isolation only, does NOT solve CPU/node noisy-neighbor)
  + dedicated node pools / separate clusters for compliance/untrusted tenants

COST: bill scales with REQUESTED capacity, not USED. unoptimized clusters commonly run
  ~10-30% actual CPU utilization vs requested. Kubecost/OpenCost (CNCF spec) attribute
  cost per namespace/label, ~97% accuracy cited for on-demand allocation.
  target: ResourceQuota hit-rate <5% steady-state (too high = quota too tight and blocking
  work; never hit = quota provides no real signal)
```

## Sources

- [Kubernetes production readiness checklist — learnkube.com](https://learnkube.com/production-best-practices) — accessed 2026-08-03
- Kubernetes documentation — Pod Lifecycle, Configure Liveness/Readiness/Startup Probes, Disruptions, Specify a Disruption Budget, Resource Quotas, Limit Ranges
- [Kubernetes Zero-Downtime Deployments — Nerd Level Tech](https://nerdleveltech.com/kubernetes-zero-downtime-deployments-tutorial) — accessed 2026-08-03
- [Kubernetes Multi-Tenancy: Resource Quotas, Namespace Isolation, and the Cost of Getting It Wrong — zop.dev](https://zop.dev/resources/blogs/kubernetes-multi-tenancy-resource-quotas-namespace-isolation/) — accessed 2026-08-03
- [Kubernetes Cost Optimization: 2026 Guide to Cutting Cloud Spend — ScaleOps](https://scaleops.com/blog/kubernetes-cost-optimization/) — accessed 2026-08-03
- OpenCost project documentation (CNCF) — cost allocation model and accuracy methodology

## Changelog
- 2026-08-03 — created
