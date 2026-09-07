"""Lab 07 tests. Fixtures are kubectl-shaped dict snapshots; nothing sleeps."""
import pytest


# ------------------------------------------------------------------ fixtures
def running_container(**overrides):
    status = {"state": "running", "reason": None, "exit_code": None,
              "waiting_reason": None}
    status.update(overrides)
    return status


def healthy_pod():
    return {
        "phase": "Running",
        "conditions": [{"type": "Ready", "status": "True"},
                       {"type": "ContainersReady", "status": "True"}],
        "container_statuses": [running_container()],
        "events": [],
    }


def pod_with_containers(*containers, events=None, phase="Running"):
    return {
        "phase": phase,
        "conditions": [{"type": "Ready", "status": "False"}],
        "container_statuses": list(containers),
        "events": events or [],
    }


BIG_NODE = {"allocatable_cpu_m": 4000, "allocatable_mem_mi": 16000}
MODEST_LIMITS = {"cpu_m": 500, "mem_mi": 512}


# ------------------------------------------------------------------ the six failures
def test_crashloop_diagnosed(T):
    """CrashLoopBackOff with exit code 1 — the app chose to die."""
    pod = pod_with_containers(
        running_container(state="waiting", waiting_reason="CrashLoopBackOff",
                          exit_code=1),
        events=[{"reason": "BackOff", "message": "Back-off restarting failed container"}],
    )
    hyps = T.diagnose(pod)
    crash = [h for h in hyps if h["failure"] == "CrashLoopBackOff"]
    assert crash, "exit code 1 in a CrashLoopBackOff must be diagnosed"
    assert crash[0]["runbook"] == "kubectl logs --previous"
    assert "logs" in crash[0]["runbook"]


def test_crashloop_exit_139_is_still_app_layer(T):
    """139 = 128+11 SIGSEGV. It is a genuine app crash -> CrashLoop, not OOM."""
    pod = pod_with_containers(
        running_container(state="terminated", reason="Error", exit_code=139,
                          waiting_reason="CrashLoopBackOff"),
    )
    hyps = T.diagnose(pod)
    assert [h["failure"] for h in hyps] == ["CrashLoopBackOff"]
    assert not any(h["failure"] == "OOMKilled" for h in hyps)


def test_imagepull_diagnosed(T):
    """ImagePullBackOff AND ErrImagePull both map to wrong tag/registry auth."""
    for reason in ("ImagePullBackOff", "ErrImagePull"):
        pod = pod_with_containers(
            running_container(state="waiting", waiting_reason=reason),
            events=[{"reason": "Failed", "message": "Error: ImagePullBackOff"}],
        )
        hyps = T.diagnose(pod)
        pull = [h for h in hyps if h["failure"] == "ImagePullBackOff"]
        assert pull, f"{reason} must be diagnosed"
        cause = pull[0]["likely_cause"].lower()
        assert "tag" in cause or "registry" in cause or "auth" in cause


def test_oomkilled_diagnosed(T):
    """137 = 128+9 SIGKILL. Failure name, cause, and runbook (memray) all checked."""
    pod = pod_with_containers(
        running_container(state="terminated", reason="OOMKilled", exit_code=137),
        events=[{"reason": "OOMKilling", "message": "Memory cgroup out of memory"}],
    )
    hyps = T.diagnose(pod)
    oom = [h for h in hyps if h["failure"] == "OOMKilled"]
    assert oom, "exit code 137 must be diagnosed as OOMKilled"
    assert "memory" in oom[0]["likely_cause"].lower()
    assert "raise" in oom[0]["runbook"].lower()
    assert "memray" in oom[0]["runbook"].lower()


def test_oom_vs_app_crash_distinguished_by_exit_code(T):
    """137 -> OOMKilled. 1 -> CrashLoopBackOff. The exit code is the disambiguator."""
    oom_pod = pod_with_containers(
        running_container(state="terminated", reason="OOMKilled", exit_code=137,
                          waiting_reason="CrashLoopBackOff"),
    )
    app_pod = pod_with_containers(
        running_container(state="terminated", reason="Error", exit_code=1,
                          waiting_reason="CrashLoopBackOff"),
    )
    oom_hyps = T.diagnose(oom_pod)
    app_hyps = T.diagnose(app_pod)
    assert [h["failure"] for h in oom_hyps] == ["OOMKilled"]
    assert [h["failure"] for h in app_hyps] == ["CrashLoopBackOff"]


def test_exit_143_sigterm_is_graceful_not_failure(T):
    """143 = 128+15 SIGTERM handled — a graceful stop. No failure hypothesis."""
    pod = pod_with_containers(
        running_container(state="terminated", reason="Completed", exit_code=143,
                          waiting_reason="CrashLoopBackOff"),
    )
    assert T.diagnose(pod) == []


def test_pending_diagnosed(T):
    """Pending, no containers scheduled, FailedScheduling insufficient cpu."""
    pod = pod_with_containers(
        phase="Pending",
        events=[{"reason": "FailedScheduling",
                 "message": "0/12 nodes are available: 12 Insufficient cpu."}],
    )
    # pod_with_containers(phase="Pending") still has zero container entries
    pod["container_statuses"] = []
    hyps = T.diagnose(pod)
    pend = [h for h in hyps if h["failure"] == "Pending"]
    assert pend, "Pending + FailedScheduling insufficient cpu must be diagnosed"
    assert "resource" in pend[0]["likely_cause"].lower() or "quota" in pend[0]["likely_cause"].lower()


def test_pending_names_allocatable_mismatch_when_ask_exceeds_node(T):
    """Pending + node/limits given + ask > allocatable -> cause names it."""
    pod = pod_with_containers(
        phase="Pending",
        events=[{"reason": "FailedScheduling",
                 "message": "0/3 nodes are available: 3 Insufficient memory."}],
    )
    pod["container_statuses"] = []
    hyps = T.diagnose(pod, node=BIG_NODE, limits={"cpu_m": 8000, "mem_mi": 512})
    pend = [h for h in hyps if h["failure"] == "Pending"]
    assert pend
    assert "exceeds" in pend[0]["likely_cause"].lower() or "allocatable" in pend[0]["likely_cause"].lower()


def test_evicted_diagnosed(T):
    """Evicted event -> node pressure (disk/memory) — the pod is the victim."""
    pod = pod_with_containers(
        running_container(),
        events=[{"reason": "Evicted",
                 "message": "The node was low on resource: memory."}],
    )
    hyps = T.diagnose(pod)
    ev = [h for h in hyps if h["failure"] == "Evicted"]
    assert ev, "an Evicted event must be diagnosed"
    assert "node" in ev[0]["likely_cause"].lower()
    assert "node" in ev[0]["runbook"].lower()


def test_probe_failure_diagnosed(T):
    """ContainerCreating + Unhealthy event with a probe message -> failing probe."""
    pod = pod_with_containers(
        running_container(state="waiting", waiting_reason="ContainerCreating"),
        events=[{"reason": "Unhealthy",
                 "message": "Readiness probe failed: dial tcp: connection refused"}],
    )
    hyps = T.diagnose(pod)
    probe = [h for h in hyps if h["failure"] == "ProbeFailure"]
    assert probe, "ContainerCreating + Unhealthy probe event must be diagnosed"
    assert "probe" in probe[0]["likely_cause"].lower()
    assert "events" in probe[0]["runbook"].lower()


def test_probe_failure_requires_probe_message(T):
    """ContainerCreating + Unhealthy without 'probe' in the message is ambiguous -> no hypothesis."""
    pod = pod_with_containers(
        running_container(state="waiting", waiting_reason="ContainerCreating"),
        events=[{"reason": "Unhealthy", "message": "something unrelated"}],
    )
    assert T.diagnose(pod) == []


# ------------------------------------------------------------------ ranking
def test_specific_ranks_above_generic_oom_vs_pending(T):
    """A Pending pod whose failed container was OOMKilled: OOMKilled ranks first."""
    pod = pod_with_containers(
        phase="Pending",
        events=[{"reason": "FailedScheduling",
                 "message": "0/2 nodes are available: 2 Insufficient memory."}],
    )
    oom_cs = running_container(state="terminated", reason="OOMKilled", exit_code=137)
    pod["container_statuses"] = [oom_cs]
    hyps = T.diagnose(pod)
    failures = [h["failure"] for h in hyps]
    assert "OOMKilled" in failures and "Pending" in failures
    assert failures.index("OOMKilled") < failures.index("Pending")
    assert T.RANK["OOMKilled"] < T.RANK["Pending"]


# ------------------------------------------------------------------ healthy
def test_healthy_pod_no_hypotheses(T):
    """Running, ready, no waiting/terminated states, no events -> no hypotheses."""
    assert T.diagnose(healthy_pod()) == []


def test_unknown_state_no_hypotheses(T):
    """An unclassifiable blob (e.g. init:0/1 at 30%) -> no guesses."""
    pod = pod_with_containers(
        running_container(state="waiting", waiting_reason="PodInitializing"),
    )
    assert T.diagnose(pod) == []


# ------------------------------------------------------------------ next_commands
def test_describe_pod_first_always(T):
    """Whatever fires, kubectl describe pod is command #1."""
    pod = pod_with_containers(
        running_container(state="terminated", reason="OOMKilled", exit_code=137),
    )
    cmds = T.next_commands(T.diagnose(pod))
    assert cmds[0]["cmd"].startswith("kubectl describe pod")


def test_crashloop_commands_give_previous_logs(T):
    """CrashLoopBackOff -> kubectl logs --previous appears in the runbook."""
    pod = pod_with_containers(
        running_container(state="terminated", reason="Error", exit_code=1,
                          waiting_reason="CrashLoopBackOff"),
    )
    cmds = T.next_commands(T.diagnose(pod))
    crash = [c for c in cmds if c["failure"] == "CrashLoopBackOff"]
    assert crash and "--previous" in crash[0]["cmd"]


def test_probe_commands_include_get_events(T):
    """ProbeFailure -> kubectl get events appears in the runbook."""
    pod = pod_with_containers(
        running_container(state="waiting", waiting_reason="ContainerCreating"),
        events=[{"reason": "Unhealthy", "message": "Liveness probe failed"}],
    )
    cmds = T.next_commands(T.diagnose(pod))
    probe = [c for c in cmds if c["failure"] == "ProbeFailure"]
    assert probe and "get events" in probe[0]["cmd"]


# ------------------------------------------------------------------ postmortem
def test_contributing_factors_dedupes_and_sorts(T):
    """Reasons counted and deduped, most frequent first."""
    events = [
        {"reason": "BackOff", "message": "restart 1"},
        {"reason": "Unhealthy", "message": "probe 1"},
        {"reason": "BackOff", "message": "restart 2"},
        {"reason": "BackOff", "message": "restart 3"},
        {"reason": "Pulled", "message": "image ok"},
    ]
    chart = T.contributing_factors(events)
    assert chart == [
        {"reason": "BackOff", "count": 3},
        {"reason": "Pulled", "count": 1},
        {"reason": "Unhealthy", "count": 1},
    ]


def test_contributing_factors_sorted_desc_then_alpha(T):
    """Tie on count -> alphabetical, so the chart is deterministic."""
    events = [
        {"reason": "Pulled", "message": "a"},
        {"reason": "BackOff", "message": "b"},
        {"reason": "BackOff", "message": "c"},
        {"reason": "Pulled", "message": "d"},
    ]
    chart = T.contributing_factors(events)
    assert [c["reason"] for c in chart] == ["BackOff", "Pulled"]
    assert chart[0]["count"] == 2


def test_contributing_factors_empty(T):
    """No events -> empty chart."""
    assert T.contributing_factors([]) == []
