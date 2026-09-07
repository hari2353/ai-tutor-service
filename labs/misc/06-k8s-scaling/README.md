# Lab 06: K8s Scaling — HPA, VPA, KEDA, Cluster, SLO Budgets

**Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **XP:** 50
**Module:** `T12-k8s-scaling`

**You will build:** the four autoscalers' decision logic — HPA's utilization formula, VPA's SLO-driven headroom, KEDA's queue math, the cluster autoscaler's bin-packing — plus error-budget burn math.

**You will be able to answer:** *"HPA says 12, VPA says the pods are 2× too big — what actually happens in a cluster with both, and why?"*

## Setup

```bash
cd labs/misc/06-k8s-scaling
pip install pytest
```

## The spec

1. **`hpa_decide(metrics, config)`** — `desired = ceil(current × cpu / target)`, clamped to `[minReplicas, maxReplicas]`.
2. **`vpa_decide(pod_requests, p99_ms, slo_ms)`** — parse `250m`/`512Mi`; breach → ×1.5 (cap 4×); slack (< 0.5×SLO) → ×0.75 (floor 0.5×); deadband → unchanged.
3. **`keda_decide(queue_depth, config)`** — `ceil(depth / targetPerReplica)`, clamped.
4. **`pending_pods(requested, nodes)` / `scale_in(nodes)`** — free slots = Σ(capacity−usage); pending = deficit; scale_in removes only nodes that can be *fully* relocated into others' free slots.
5. **`error_budget_burn(errors, total, slo_pct)`** — budget = 1 − SLO; multiplier = observed/budget (2 = burning twice as fast as allowed).

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Multi-metric HPA** — CPU and memory both reported; HPA takes the max of the two desires (the real algorithm's worst-of behavior).
2. **Stabilization window** — HPA that refuses to scale down within N seconds of the last scale-up (FakeClock).
3. **Bin-packing policy** — Least-requested vs spreading; which scale-in finds more removable nodes?
