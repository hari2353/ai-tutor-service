"""Lab 07 — reference solution: the failure-mode diagnostician."""
from __future__ import annotations

from typing import Dict, List, Optional


RANK = {
    # Specificity order: the concrete cause outranks the generic symptom.
    "OOMKilled": 0,
    "CrashLoopBackOff": 1,
    "ImagePullBackOff": 2,
    "Evicted": 3,
    "ProbeFailure": 4,
    "Pending": 5,
}


# ------------------------------------------------------------------ accessors
def _containers(pod: dict) -> List[dict]:
    return pod.get("container_statuses") or []


def _events(pod: dict) -> List[dict]:
    return pod.get("events") or []


# ------------------------------------------------------------------ matchers
def _is_oomkilled(cs: dict) -> bool:
    """137 = 128+9 SIGKILL, or describe said the words out loud."""
    return cs.get("exit_code") == 137 or cs.get("reason") == "OOMKilled"


def _is_app_crashloop(cs: dict) -> bool:
    """CrashLoopBackOff around an exit the app layer caused: app codes 1..128
    plus signal deaths like 139 (SIGSEGV). 137 (OOMKilled) and 143 (SIGTERM
    handled gracefully) are ranked separately, not as app crashes."""
    code = cs.get("exit_code")
    return (cs.get("waiting_reason") == "CrashLoopBackOff"
            and isinstance(code, int) and code != 0 and code not in (137, 143))


def _is_image_pull_failure(cs: dict) -> bool:
    return cs.get("waiting_reason") in ("ImagePullBackOff", "ErrImagePull")


def _is_probe_blocked(cs: dict) -> bool:
    return cs.get("waiting_reason") == "ContainerCreating"


def _insufficient_resources(pod: dict) -> bool:
    """Pending + a FailedScheduling event naming insufficient cpu/memory."""
    if pod.get("phase") != "Pending":
        return False
    for e in _events(pod):
        if e.get("reason") != "FailedScheduling":
            continue
        msg = str(e.get("message", "")).lower()
        if "insufficient cpu" in msg or "insufficient memory" in msg:
            return True
    return False


def _exceeds_allocatable(node: dict, limits: dict) -> bool:
    """The pod's ask is bigger than any node like this can ever satisfy."""
    return (limits.get("cpu_m", 0) > node.get("allocatable_cpu_m", 0)
            or limits.get("mem_mi", 0) > node.get("allocatable_mem_mi", 0))


# ------------------------------------------------------------------ public API
def diagnose(pod: dict, node: Optional[dict] = None,
             limits: Optional[dict] = None) -> List[dict]:
    """Rank every classic failure that explains this pod.

    Returns ALL matching hypotheses as {"failure", "likely_cause", "runbook"},
    most specific first (RANK). Healthy, graceful (143), or unknown -> [].
    """
    containers = _containers(pod)
    events = _events(pod)
    hypotheses: List[dict] = []

    if any(_is_oomkilled(cs) for cs in containers):
        hypotheses.append({
            "failure": "OOMKilled",
            "likely_cause": "memory limit hit",
            "runbook": "raise limit or find leak (memray)",
        })

    if any(_is_app_crashloop(cs) for cs in containers):
        hypotheses.append({
            "failure": "CrashLoopBackOff",
            "likely_cause": "app error — check logs",
            "runbook": "kubectl logs --previous",
        })

    if any(_is_image_pull_failure(cs) for cs in containers):
        hypotheses.append({
            "failure": "ImagePullBackOff",
            "likely_cause": "wrong tag or registry auth",
            "runbook": "kubectl describe pod — Events names the exact pull failure",
        })

    if any(e.get("reason") == "Evicted" for e in events):
        hypotheses.append({
            "failure": "Evicted",
            "likely_cause": "node pressure (disk or memory)",
            "runbook": "kubectl describe node — check MemoryPressure/DiskPressure conditions",
        })

    if (any(_is_probe_blocked(cs) for cs in containers)
            and any(e.get("reason") == "Unhealthy"
                    and "probe" in str(e.get("message", "")).lower()
                    for e in events)):
        hypotheses.append({
            "failure": "ProbeFailure",
            "likely_cause": "failing probe — readiness/liveness never passes",
            "runbook": "kubectl get events — check probe thresholds and target",
        })

    if _insufficient_resources(pod):
        cause = "resource pressure or quota"
        if node and limits and _exceeds_allocatable(node, limits):
            cause = "pod ask exceeds node allocatable — it can never schedule"
        hypotheses.append({
            "failure": "Pending",
            "likely_cause": cause,
            "runbook": "kubectl describe node — allocatable vs pod requests",
        })

    hypotheses.sort(key=lambda h: RANK[h["failure"]])
    return hypotheses


_FAILURE_COMMANDS: Dict[str, str] = {
    "CrashLoopBackOff": "kubectl logs <pod> --previous",
    "OOMKilled": "kubectl top pod <pod> --containers",
    "ImagePullBackOff": "kubectl describe pod <pod> | grep -A5 Events",
    "Evicted": "kubectl describe node <node> | grep -A5 Conditions",
    "ProbeFailure": "kubectl get events --field-selector reason=Unhealthy",
    "Pending": "kubectl describe node <node> | grep -A10 Allocatable",
}

_FAILURE_WHY: Dict[str, str] = {
    "CrashLoopBackOff": "what the crashed instance said — not the current restart attempt",
    "OOMKilled": "usage right now; the trend needs a metrics backend",
    "ImagePullBackOff": "Events names the exact pull failure: typo, auth, or 429",
    "Evicted": "MemoryPressure / DiskPressure — it was the node, not the pod",
    "ProbeFailure": "which probe, which threshold, how often",
    "Pending": "requests vs allocatable — or a taint nobody tolerates",
}


def next_commands(hypotheses: List[dict]) -> List[dict]:
    """The ordered kubectl runbook: describe first, then one dict per hypothesis."""
    commands: List[dict] = [{
        "failure": "always",
        "cmd": "kubectl describe pod <pod>",
        "why": "Events + Last State — usually 80% of the answer",
    }]
    seen = set()
    for h in hypotheses:
        failure = h["failure"]
        if failure in seen or failure not in _FAILURE_COMMANDS:
            continue
        seen.add(failure)
        commands.append({
            "failure": failure,
            "cmd": _FAILURE_COMMANDS[failure],
            "why": _FAILURE_WHY[failure],
        })
    return commands


def contributing_factors(events: List[dict]) -> List[dict]:
    """The postmortem "what fired most" chart: count by reason, sort desc."""
    counts: Dict[str, int] = {}
    for e in events:
        reason = e.get("reason")
        counts[reason] = counts.get(reason, 0) + 1
    return [{"reason": reason, "count": count}
            for reason, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
