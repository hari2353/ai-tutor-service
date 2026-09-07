"""K8s scaling decision logic: HPA, VPA, KEDA, cluster autoscaler, error budgets."""
import math


def _parse_cpu(s):
    if s.endswith("m"):
        return int(s[:-1])
    return int(float(s) * 1000)


def _parse_mem(s):
    if s.endswith("Mi"):
        return int(s[:-2])
    if s.endswith("Gi"):
        return int(s[:-2]) * 1024
    return int(s) // (1024 * 1024)


def _fmt_cpu(m):
    return f"{m}m"


def _fmt_mem(mi):
    if mi % 1024 == 0 and mi >= 1024:
        return f"{mi // 1024}Gi"
    return f"{mi}Mi"


def hpa_decide(metrics, config):
    cur = metrics["currentReplicas"]
    cpu = metrics["currentCPUUtilizationPercentage"]
    target = config["targetCPUUtilizationPercentage"]
    lo, hi = config["minReplicas"], config["maxReplicas"]
    desired = math.ceil(cur * cpu / target)
    reason = f"ceil({cur} * {cpu}/{target})"
    if desired < lo:
        desired, reason = lo, f"clamped to min {lo}"
    elif desired > hi:
        desired, reason = hi, f"clamped to max {hi}"
    return {"replicas": desired, "reason": reason}


def vpa_decide(pod_requests, p99_latency_ms, slo_ms):
    cpu = _parse_cpu(pod_requests["cpu"])
    mem = _parse_mem(pod_requests["memory"])
    base_cpu, base_mem = cpu, mem
    if p99_latency_ms > slo_ms:
        # headroom up, but never beyond 4x the CURRENT request (absolute cap
        # per recommendation — a caller re-feeding recommendations compounds,
        # which is exactly why real VPA restarts pods rather than resizes)
        cpu = max(min(int(cpu * 1.5), base_cpu * 4), cpu)
        mem = max(min(int(mem * 1.5), base_mem * 4), mem)
        why = "p99 breach: +50% headroom"
    elif p99_latency_ms < slo_ms * 0.5:
        cpu = min(max(int(cpu * 0.75), int(base_cpu * 0.5)), cpu)
        mem = min(max(int(mem * 0.75), int(base_mem * 0.5)), mem)
        why = "slack: -25%"
    else:
        why = "deadband: unchanged"
    return {"cpu": _fmt_cpu(cpu), "memory": _fmt_mem(mem), "reason": why}


def keda_decide(queue_depth, config):
    per = config["targetPerReplica"]
    desired = math.ceil(queue_depth / per)
    return max(config["minReplicas"], min(config["maxReplicas"], desired))


def pending_pods(pods_requested, nodes):
    free = sum(max(0, n["capacity_pods"] - n["usage_pods"]) for n in nodes)
    return max(0, pods_requested - free)


def scale_in(nodes):
    """Conservative single-pass: a node is removable iff its pods fit into the
    free slots of nodes that are NOT themselves being removed this pass.
    We do one removal per node in index order, and relocated pods must land on
    nodes that survive the whole pass — so we only relocate into nodes with
    strictly more free capacity than needed, and never into nodes we removed
    or will remove later in this pass (conservative: nodes after i in the
    order are treated as staying, so only nodes BEFORE i are safe targets if
    they were kept; a kept node is one we did not remove)."""
    removable = []
    free = [max(0, n["capacity_pods"] - n["usage_pods"]) for n in nodes]
    for i, n in enumerate(nodes):
        if n["usage_pods"] == 0:
            removable.append(i)
            free[i] = -1
            continue
        # candidate targets: every OTHER node that is not removed (-1) —
        # but a later node might itself get removed after hosting relocated
        # pods, which would be a double-count. To stay conservative we only
        # allow relocation into nodes we have already passed over and KEPT.
        need = n["usage_pods"]
        ok = True
        tentative = list(free)
        tentative[i] = -1
        for j in range(len(nodes)):
            if j == i or j > i or tentative[j] < 0:
                continue          # only earlier kept nodes are safe targets
            take = min(need, tentative[j])
            tentative[j] -= take
            need -= take
            if need == 0:
                break
        if need == 0:
            removable.append(i)
            free = tentative
        else:
            # keep node i alive: its free slots are safe targets for later nodes
            pass
    return removable


def error_budget_burn(errors, total, slo_availability_percent):
    budget = 1 - slo_availability_percent / 100.0
    observed = errors / total if total else 0.0
    mult = observed / budget if budget > 0 else float("inf")
    return {"budget_fraction": budget, "multiplier": mult}
