# Lab 07: K8s Troubleshooting — CrashLoops, OOMKills, Evictions

**Track:** T12 DevOps, Infra & Security · **Time:** 3h · **XP:** 50
**Module:** `T12-k8s-troubleshooting`

**You will build:** a failure-mode diagnostician — `diagnose(pod)` takes a `kubectl`-shaped pod snapshot and returns every matching classic failure (OOMKill, CrashLoop, ImagePull, Eviction, probe failure, Pending) ranked most-specific-first, plus the ordered kubectl runbook for each and a postmortem "what fired most" chart.

**You will be able to answer:** *"A pod is in CrashLoopBackOff — walk me through your exact diagnostic sequence, why the order matters, and how the exit code changes your first hypothesis."*

## Setup

```bash
cd labs/misc/07-k8s-troubleshooting
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

A **PodStatus** is a plain dict — what `kubectl get pod -o json` gives you, distilled:

```python
{
  "phase": "Pending" | "Running" | ...,
  "conditions": [{"type", "status"}],
  "container_statuses": [
     {"state": "waiting" | "running" | "terminated",
      "reason": str | None,
      "exit_code": int | None,
      "waiting_reason": str | None}
  ],
  "events": [{"reason", "message"}],
}
```

1. **`diagnose(pod, node=None, limits=None)`** → ranked hypotheses. Detect the six classic failures:
   1. **CrashLoopBackOff** — a container with `waiting_reason: "CrashLoopBackOff"` and a nonzero `exit_code` that is **not** 137/143 (app codes 1..128, segfaults like 139 — the process died at the application layer). Hypothesis: `{"failure": "CrashLoopBackOff", "likely_cause": "app error — check logs", "runbook": "kubectl logs --previous"}`.
   2. **ImagePullBackOff** — `waiting_reason` `"ImagePullBackOff"` or `"ErrImagePull"` → wrong tag or registry auth.
   3. **OOMKilled** — `exit_code` 137 (= 128+9, SIGKILL from the cgroup OOM killer) → memory limit hit; runbook: raise limit or find the leak (**memray**).
   4. **Pending** — `phase "Pending"` + no container statuses + a `FailedScheduling` event whose message says **insufficient cpu/memory** → resource pressure or quota. If `node` (`{"allocatable_cpu_m", "allocatable_mem_mi"}`) and `limits` (`{"cpu_m", "mem_mi"}`) are passed and the ask exceeds allocatable, the cause must name it — that pod can never schedule on a node like this.
   5. **Evicted** — an event with reason `"Evicted"` → node pressure (disk/memory) — the pod is usually the victim, not the cause.
   6. **ProbeFailure** — `waiting_reason "ContainerCreating"` + an `"Unhealthy"` event whose message mentions a probe → failing probe.
2. **Return ALL matches, ranked by specificity**: OOMKilled > CrashLoop > ImagePull > Evicted > Probe > Pending — the concrete cause outranks the generic symptom. Each hypothesis carries `failure` + `likely_cause` + `runbook`. Healthy, graceful (exit 143 = SIGTERM), or unknown state → **empty list** — never guess.
3. **`next_commands(hypotheses)`** → ordered kubectl commands: **always** starts with `kubectl describe pod` (Events + Last State are 80% of the answer), then one `{"failure", "cmd", "why"}` dict per hypothesis — `logs --previous` (crash), `get events` (probe), `describe node` (eviction), in ranked order.
4. **`contributing_factors(events)`** → the postmortem chart for a PM: count events by `reason`, dedupe, sorted by count desc (ties alphabetical). `[]` when there are no events.
5. Determinism: same pod dict → same ranked hypotheses, same commands, same chart. Pure stdlib; `diagnose` never mutates the pod.

## Run the tests

```bash
python -m pytest tests -q                 # against starter/ → FAILS. Make them pass.
python -m pytest tests -q --solution      # the reference — all green
```

## Stretch goals

1. **Grace-period kill** — exit 137 *without* reason `OOMKilled`: surface it as a separate hypothesis from OOM ("slow shutdown past `terminationGracePeriodSeconds`") so the fix is a longer grace period, not more memory. *("137 — is it always OOM?")*
2. **QoS-aware eviction** — compute the pod's QoS class from its requests/limits (`Guaranteed`/`Burstable`/`BestEffort`) and rank eviction hypotheses accordingly — BestEffort neighbors are the usual root cause. *("Why is the innocent pod the one that got evicted?")*
3. **Node-pressure ordering** — parse the Evicted message: `disk` > `memory` > `pid` ordering, with the right fix per pressure type. *("The node said 'low on resource' — which resource, and why does the order matter?")*
4. **A real cluster drill** — apply the module's three demo YAMLs (crash / oom / pending) to a local cluster and confirm each hypothesis your tool returns matches what `kubectl describe` actually shows. *("Show me you've done this at 2am.")*
