"""K8s scaling decision logic: HPA, VPA, KEDA, cluster autoscaler, error budgets."""
import math


def hpa_decide(metrics, config):
    """metrics: {currentReplicas, currentCPUUtilizationPercentage}
    config: {minReplicas, maxReplicas, targetCPUUtilizationPercentage}
    Returns {replicas, reason}."""


def vpa_decide(pod_requests, p99_latency_ms, slo_ms):
    """pod_requests: {"cpu": "250m", "memory": "512Mi"}. Returns same format."""


def keda_decide(queue_depth, config):
    """config: {minReplicas, maxReplicas, targetPerReplica}."""


def pending_pods(pods_requested, nodes):
    """nodes: [{"capacity_pods": int, "usage_pods": int}]. Free = sum(cap-usage)."""


def scale_in(nodes):
    """Return indices of nodes fully relocatable into others' free capacity."""


def error_budget_burn(errors, total, slo_availability_percent):
    """Returns {budget_fraction, multiplier}."""


def _parse_cpu(s):
    """'250m' -> 250; '2' -> 2000 (cores to milli)."""


def _parse_mem(s):
    """'512Mi' -> 512; '1Gi' -> 1024 (to Mi)."""
