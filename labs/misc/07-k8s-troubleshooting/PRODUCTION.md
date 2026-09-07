# Production notes — pod triage

## What you'd actually use

| Need | Tool |
|---|---|
| The state, the restarts | `kubectl get pods` |
| The cause, ~80% of the time | `kubectl describe pod` — Events + Last State |
| What the crashed instance said | `kubectl logs <pod> --previous` |
| No shell in the image | `kubectl debug` — ephemeral container (stable ~1.25) |
| The pod's processes, from the host | `kubectl debug node/<n>` → `nsenter` into the host namespaces |

Your lab ranks hypotheses from one snapshot. Production adds **alerts on the symptom pattern** so you find out before the pager-holding customer does: `kube_pod_container_status_restarts_total` rate (CrashLoop), `reason="ImagePullBackOff"` waiting-reason gauges, `container_oom_events_total` / `last_terminated_reason{reason="OOMKilled"}` (OOM), sustained `phase="Pending"`, and an eviction *rate* — not any single Evicted event, which is often a planned drain (see the module's Q8).

## Exit-code decoding — the part interviews actually probe

Exit codes 128+N mean **killed by signal N**; anything 1..127 is the process's own choice:

| Code | Signal | Meaning | First hypothesis |
|---|---|---|---|
| 1 | — | app-level exit (config, missing env var, startup exception) | CrashLoopBackOff — read `--previous`, the line is usually right there |
| 137 | 128+9 | SIGKILL | **OOMKilled** (cgroup limit) OR a **liveness-probe kill** OR slow shutdown past `terminationGracePeriodSeconds` |
| 139 | 128+11 | SIGSEGV | genuine native crash — often a build/runtime shared-library mismatch |
| 143 | 128+15 | SIGTERM, handled | graceful stop — *not* a failure; if it loops, something external keeps sending it |

**137 vs the two impostors.** Your lab treats every 137 as OOMKilled; production reads `Last State: Terminated, Reason: OOMKilled` in `describe pod` before believing it. A liveness-probe kill shows the same 137 but reason is the probe failing — check `Unhealthy` events. A grace-period kill shows plain `Error` with no OOM reason: the fix is a longer `terminationGracePeriodSeconds` or a faster shutdown path, and **raising memory does nothing**. This is the follow-up trap on the module's Q2, and conflating them is how a memory "fix" ships while the pod keeps dying.

## Probe tuning — where ProbeFailure hypotheses come from

Most failing-probe incidents are threshold misconfigurations, not broken apps:

- **Liveness**: `initialDelaySeconds` shorter than real startup (the classic slow-JVM-killed-at-90s), or a probe checking *dependencies* (DB) instead of *process liveness* — every DB blip restarts every pod, which is a self-inflicted outage.
- **Readiness** can be strict (pull the pod from Service while unhealthy — no restart); **liveness must be loose** (a false positive kills the container). `startupProbe` (GA 1.20) solves the slow-starter case far better than a huge initial delay.
- The rule of thumb for thresholds: `failureThreshold × periodSeconds` should be ~10s for liveness (fast recovery, tolerant of one or two missed probes), and the probe timeout under the endpoint's p99.

## Eviction — node pressure, and the order it bites

Node-pressure eviction is **ordered**: the kubelet evicts BestEffort first, then Burstable, Guaranteed last. The pressure signals are checked in this order — **disk (`nodefs`, `imagefs`) > memory > pid** — and the fix differs per pressure type: `DiskPressure: True` usually means unbounded `emptyDir`/logs (fix: `ephemeral-storage` limits, log rotation) while `MemoryPressure` means some neighbor's unbounded heap (fix: set limits on the *offender*, not the victim). Your lab's "Evicted" hypothesis says "node pressure — check the node's Conditions"; production reads *which* condition and names the culprit pod via `kubectl top pod`.

## Ephemeral containers & `kubectl debug`

The distroless-image problem ("no shell to exec into") is solved by attaching a debug container into the *target pod's namespaces* — `kubectl debug -it <pod> --image=busybox --target=<container>` — process namespace shared, no change to the pod spec or image. For node-level investigation: `kubectl debug node/<n>` drops you into a pod with the host's filesystem mounted at `/host`, and `nsenter -t 1 -m -u -i -n -p` gets you the host's actual processes — this is the modern replacement for the old "SSH to the node" workflow the module's lineage section describes.

## What production adds over your lab

- **Dashboards on restart counts and `container_oom_events_total`** — trend lines, not snapshots: an OOM working set that *plateaus* wants a higher limit; one that *climbs monotonically* is a leak, and raising the limit just buys a bigger blast radius (memray/tracemalloc *before* touching the limit).
- **OOM paging alerts scoped to rate** — one OOMKill during a rollout is noise; three in an hour on one deployment is a page. The threshold encodes Kubernetes' own self-healing: a few restarts mid-rollout is normal.
- **Cluster-wide correlation** — dozens of Evicted pods on one node *pool* is a node-level incident (the module's Q10), and triage starts at the node, not at any individual pod. Your per-pod `diagnose()` is one row of that story; the incident is the pattern.
