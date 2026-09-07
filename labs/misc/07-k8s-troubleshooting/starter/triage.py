"""Lab 07 — the failure-mode diagnostician. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. No cluster, no kubectl, no network.
  * Pods are plain dicts (shape in the README); diagnose never mutates them.
  * Deterministic: the same pod dict -> the same ranked hypotheses, every time.
  * No time.sleep() anywhere — nothing here is wall-clock dependent.

Exit-code semantics you are encoding (128+N = killed by signal N):
    1..128  the process chose to exit (app error)  -> CrashLoopBackOff, read --previous
    137     128+9  SIGKILL                         -> OOMKilled (or a grace-period kill)
    143     128+15 SIGTERM, handled                -> graceful, NOT a failure hypothesis
"""
from __future__ import annotations

from typing import List, Optional


RANK = {
    # Specificity order: the concrete cause outranks the generic symptom.
    "OOMKilled": 0,
    "CrashLoopBackOff": 1,
    "ImagePullBackOff": 2,
    "Evicted": 3,
    "ProbeFailure": 4,
    "Pending": 5,
}


def diagnose(pod: dict, node: Optional[dict] = None,
             limits: Optional[dict] = None) -> List[dict]:
    """Rank every classic failure that explains this pod.

    pod:    PodStatus dict — {"phase", "conditions", "container_statuses", "events"}.
    node:   optional {"allocatable_cpu_m": int, "allocatable_mem_mi": int}.
    limits: optional {"cpu_m": int, "mem_mi": int} — the pod's own resource ask.

    The six rules (each independently testable):
      1. OOMKilled         — any container with exit_code 137 (or reason "OOMKilled").
      2. CrashLoopBackOff  — waiting_reason "CrashLoopBackOff" AND a nonzero
                            exit_code that is not 137 (OOM) or 143 (graceful
                            SIGTERM): app codes 1..128 and segfaults like 139.
      3. ImagePullBackOff  — waiting_reason "ImagePullBackOff" or "ErrImagePull".
      4. Evicted           — an event with reason "Evicted" (node pressure —
                            the pod is usually the victim, not the cause).
      5. ProbeFailure      — waiting_reason "ContainerCreating" AND an "Unhealthy"
                            event whose message mentions a probe.
      6. Pending           — phase "Pending" AND a "FailedScheduling" event whose
                            message says "Insufficient cpu"/"Insufficient memory".
                            If node and limits are given and the ask exceeds
                            allocatable, the cause must say so — that pod can
                            never schedule on a node like this.

    Return ALL matching hypotheses as {"failure", "likely_cause", "runbook"},
    most specific first (RANK). Healthy, graceful (143), or unknown -> [].
    """
    # TODO(step 1): implement
    raise NotImplementedError


def next_commands(hypotheses: List[dict]) -> List[dict]:
    """The ordered kubectl runbook for a list of hypotheses.

    ALWAYS starts with `kubectl describe pod` — Events + Last State are
    usually 80% of the answer. Then one {"failure", "cmd", "why"} dict per
    hypothesis (deduped by failure name), in the hypotheses' ranked order:
      CrashLoopBackOff -> kubectl logs <pod> --previous
      ProbeFailure     -> kubectl get events ...
      Evicted          -> kubectl describe node ...
    """
    # TODO(step 2): implement
    raise NotImplementedError


def contributing_factors(events: List[dict]) -> List[dict]:
    """The postmortem "what fired most" chart.

    Count events by reason, dedupe, sort by count desc (ties alphabetical so
    the chart is deterministic). Return [{"reason", "count"}, ...]; [] if no events.
    """
    # TODO(step 3): implement
    raise NotImplementedError
