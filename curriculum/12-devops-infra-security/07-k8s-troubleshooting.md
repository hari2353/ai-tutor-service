# Debugging K8s: CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending, Evicted

> **Track:** T12 DevOps, Infra & Security Â· **Time:** 3h Â· **Prereqs:** T12-k8s-core, T12-k8s-networking, T12-k8s-storage-config
> **Module id:** `T12-k8s-troubleshooting` Â· **Tags:** k8s, critical
> **Lab:** `labs/misc/07-k8s-troubleshooting/`

## The 30-second version

Every Kubernetes failure state is a symptom, not a diagnosis, and the fastest path to root cause is always the same funnel: `kubectl get pods` for the state, `kubectl describe pod` for the Events section (which tells you *why* the scheduler or kubelet did what it did), then `kubectl logs` (add `--previous` for a container that already died) for what the application itself said before it went down. `CrashLoopBackOff` means the container starts and exits repeatedly, with the kubelet backing off retries exponentially (10s, 20s, 40s, 80s, 160s, capped at 300s) â€” the state itself is agnostic about cause, which is almost always either an application crash (check `--previous` logs), a failing liveness probe killing an otherwise-healthy process, or `OOMKilled` (exit code 137, a `SIGKILL` from the cgroup OOM killer, visible in `describe pod`'s `Last State` block, not the logs, because the process never got to log anything). `ImagePullBackOff` is a pull failure that happens *before* the container ever starts â€” wrong tag, private registry with no `imagePullSecrets`, or a rate limit â€” and is diagnosed entirely from Events, never from `kubectl logs` since no container has run yet. `Pending` means the scheduler cannot place the pod at all: insufficient resources, an unsatisfiable affinity/taint rule, or a PVC that will never bind, and `describe pod`'s Events will name the exact predicate that failed. `Evicted` means the kubelet proactively killed a pod to protect node stability under memory, disk, or PID pressure â€” different from OOMKilled, because eviction is the kubelet defending the *node*, while OOM-kill is the kernel defending the *cgroup*. DNS failures are usually not CoreDNS being down at all; they're the well-documented conntrack race condition that makes UDP DNS queries intermittently take a full 5 seconds, or `ndots:5`'s default search-domain expansion silently multiplying every external lookup into up to five queries.

## Why this gets asked

Because reciting what CrashLoopBackOff means is trivial and every candidate has memorized it; what the interviewer actually wants is to watch you run the funnel under pressure â€” `describe` before `logs`, `--previous` when the current logs are empty because the container that's running now hasn't failed yet, `Last State` and not `State` for a container that OOM-killed instants ago. They have personally been paged for a fleet-wide CrashLoopBackOff that turned out to be a bad ConfigMap rollout, an Evicted storm that turned out to be a log file filling `/var/lib/docker` on every node, or a DNS timeout that had nothing to do with CoreDNS being unhealthy and everything to do with a kernel-level conntrack race no amount of restarting CoreDNS would fix. They want to see whether you reason from symptom to mechanism, or guess and restart things until it goes away.

---

## Lineage: past â†’ present â†’ future

**What came before.** Early Kubernetes (pre-1.6-ish, mid-2010s) debugging leaned almost entirely on `kubectl logs`, `kubectl describe`, and SSHing onto nodes to run `docker inspect`/`docker logs` directly against the container runtime, because there was no in-cluster ephemeral debugging primitive at all â€” if a container crashed too fast to `exec` into, or a distroless image had no shell to `exec` into in the first place, you were stuck reading whatever the app happened to log before it died, full stop. The pain this caused was acute as minimal/distroless images (covered in the Docker module) became standard practice for security reasons: a `scratch`-based or distroless production image with no shell, no `ps`, no `curl` gave you a genuinely secure container and a genuinely undebuggable one at the same time, and the standard workaround â€” rebuilding a "debug" variant of the image with a shell baked in just to troubleshoot it â€” was slow and defeated half the point of minimal images.

**Where it stands now.** Ephemeral containers (`kubectl debug`, GA since Kubernetes 1.25) solved the distroless-debugging problem directly: `kubectl debug -it <pod> --image=busybox --target=<container>` injects a temporary debug container into a *running* pod's namespaces (sharing its network and, with `--target`, its process namespace) without modifying the pod spec or requiring a restart, giving you a shell and tools against a container that itself has none. This is now the standard tool for anything beyond "read the logs," alongside `kubectl top` (metrics-server-backed, for a fast resource-pressure read) and `kubectl events --for pod/<name>` (a filtered events view, cleaner than scrolling through a full `describe`). The live disagreement isn't about the tools so much as about observability strategy: teams increasingly push toward *not* needing live `kubectl exec`/`debug` sessions at all in production, favoring structured logging shipped to a central store, metrics with alerting on the exact signals covered below (`container_cpu_cfs_throttled_periods_total`, OOM-kill counters, restart counts), and distributed tracing â€” live debugging into a running prod pod is increasingly treated as a last resort or explicitly disallowed in regulated environments, not a first move.
â€‹
**Where it's heading.** Kubernetes 1.34 (released August 2026) and the broader 1.34â€“1.36 line continue expanding structured, machine-readable diagnostics â€” richer `Events` reasons, and continued maturation of the Node Problem Detector pattern for surfacing node-level hardware/kernel issues as first-class Kubernetes conditions rather than requiring an operator to correlate `dmesg` output by hand. Expect the debugging funnel described here to remain the mechanical core of the skill for the foreseeable future â€” the states and their causes are stable, well-understood parts of the kubelet/scheduler contract â€” while the tooling around *surfacing* the right signal faster (AI-assisted log/event correlation in commercial observability platforms, more automated root-cause suggestion) keeps improving; treat any specific claim about an AI-driven "auto-fix" tool as unproven in production at scale rather than a replacement for understanding the mechanism yourself.

---

## Mental model

```
kubectl get pods -o wide
        â”‚
        â–¼
   what's the STATE column actually saying?
        â”‚
        â”œâ”€â”€ ImagePullBackOff / ErrImagePull â”€â”€â–º pod never started a container at all
        â”‚                                        â†’ look at Events, NOT logs (nothing ran)
        â”‚
        â”œâ”€â”€ CrashLoopBackOff â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º container starts, then exits, repeatedly
        â”‚                                        â†’ kubectl logs --previous (last attempt)
        â”‚                                        â†’ describe pod: Last State + Exit Code
        â”‚                                             137 = SIGKILL  (often OOMKilled)
        â”‚                                             1   = app-level error
        â”‚                                             0   = clean exit (probe killing a
        â”‚                                                    healthy process is common)
        â”‚
        â”œâ”€â”€ Pending â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º scheduler never placed it at all
        â”‚                                        â†’ describe pod Events: which PREDICATE
        â”‚                                          failed (resources / affinity / taints /
        â”‚                                          unbound PVC)
        â”‚
        â”œâ”€â”€ Running, but Evicted later â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º kubelet killed it to protect the NODE
        â”‚                                        â†’ describe pod: Status.Reason = Evicted
        â”‚                                        â†’ check node conditions: MemoryPressure /
        â”‚                                          DiskPressure / PIDPressure
        â”‚
        â””â”€â”€ Running, app-level DNS timeouts â”€â”€â”€â”€â–º almost never "CoreDNS is down"
                                                   â†’ conntrack UDP race (~5s stalls) or
                                                     ndots:5 search-domain amplification
```

The one discipline that separates fast diagnosis from guesswork: **never run `kubectl logs` before `kubectl describe pod`.** Describe tells you which of these five buckets you're in and why the kubelet/scheduler made the decision it made; logs only ever tell you what the application itself printed, which is useless or misleading for ImagePullBackOff, Pending, and most Evicted cases since the application never ran or never got a chance to log anything.

---

## How it actually works

### CrashLoopBackOff â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** `kubectl get pods` shows `STATUS: CrashLoopBackOff`, restart count climbing.

The kubelet applies exponential backoff between restart attempts for a container in a loop: **10s, 20s, 40s, 80s, 160s, capped at 300s (5 minutes)**, resetting the backoff counter only after the container has stayed up for **10 minutes** straight. This means a fleet of pods that all start crash-looping at once (a bad rollout, a bad ConfigMap) doesn't retry-storm your dependencies â€” that's a deliberate design choice, not a bug â€” but it also means "just wait for it to come back" can genuinely mean waiting 5 minutes between attempts once the backoff has climbed, which is worth knowing before assuming a stuck-looking pod is actually stuck.

Root causes, in the order to actually check them:

1. **App crashes on startup.** `kubectl logs <pod> --previous` (or `-p`) â€” the current container instance, if it's mid-crash-loop, may have empty or truncated logs; `--previous` retrieves the log of the *last terminated* instance, which is almost always where the real error is (stack trace, missing env var, failed DB connection at boot).
2. **OOMKilled.** `kubectl describe pod <pod>` and read the `Last State` block, not `State` â€” a container that was OOM-killed shows `Reason: OOMKilled`, `Exit Code: 137`. **137 = 128 + 9**, the Linux convention for "killed by signal N," and signal 9 is `SIGKILL`, sent unconditionally by the kernel's cgroup OOM killer with no chance for the process to catch it or log a final message â€” which is exactly why the answer isn't in the logs at all, it's in `describe`.
3. **Liveness probe killing an otherwise-healthy process.** `kubectl describe pod` Events will show `Liveness probe failed` immediately before a `Killing container` event. This produces `Exit Code: 0` (clean exit, the process was sent `SIGTERM` and shut down normally) or the app's own signal-handling exit code â€” the container itself may have been perfectly healthy, just slow to answer a probe that was tuned too aggressively (too-short `timeoutSeconds`, a probe hitting an endpoint with cold-start latency the probe schedule didn't account for).
4. **Missing config/secret causing an immediate fatal error.** Same as #1 mechanically (`--previous` logs show it), but worth checking explicitly: `kubectl describe pod` also shows failed `envFrom`/`valueFrom` references as pod-level warnings if the referenced ConfigMap/Secret key doesn't exist at all.

**Command sequence that actually finds it, in order:**
```bash
kubectl get pod <pod> -o wide                       # restart count, node, age
kubectl describe pod <pod>                           # Events + Last State + Exit Code
kubectl logs <pod> --previous --tail=200              # what the app said before it died
kubectl logs <pod> --previous --previous              # NOT valid â€” only one prior instance
                                                        # is retained; use -c <container> in
                                                        # multi-container pods
```

### ImagePullBackOff / ErrImagePull â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** `STATUS: ImagePullBackOff` or `ErrImagePull`, restart count stays at 0 â€” because no container has ever started.

This is diagnosed entirely from `kubectl describe pod`'s Events, since `kubectl logs` returns nothing (there is no container to have logged anything). Real causes, in likelihood order:

1. **Wrong image name or tag** â€” a typo, or a tag that was never pushed (very common right after a CI pipeline change). Events show `Failed to pull image "...": rpc error: ... not found` or similar.
2. **Private registry with no (or wrong) `imagePullSecrets`.** Events show a 401/403-flavored error from the registry. Fix: `kubectl create secret docker-registry <name> --docker-server=... --docker-username=... --docker-password=...` and reference it in the pod spec's `imagePullSecrets`, or on the ServiceAccount so every pod using that SA inherits it.
3. **Registry rate limiting** â€” Docker Hub's anonymous/free-tier pull rate limits are a classic silent cause of intermittent `ImagePullBackOff` across a whole node that just happens to be pulling a lot of images at once (a large scale-up event, a node replacement). Events show a `429`-flavored error. Fix: authenticate pulls (even to Docker Hub, an authenticated pull has a higher limit than anonymous), or mirror images to a private registry/pull-through cache.
4. **Node can't reach the registry at all** â€” network policy, egress firewall, or a private VPC with no NAT/endpoint for the registry. Events show a generic timeout rather than an auth or not-found error, which is the tell that this is network-layer, not image-layer.

```bash
kubectl describe pod <pod> | grep -A5 Events         # exact failure reason
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].image}'  # confirm exact image:tag
kubectl get sa <serviceaccount> -o yaml               # check imagePullSecrets is actually attached
```

### OOMKilled â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** Pod shows `CrashLoopBackOff` (if it keeps happening) or `OOMKilled` directly as the last state reason; exit code **137**.

The mechanism: a container's memory usage crossed its cgroup memory limit, and the kernel's OOM killer sent `SIGKILL` to the process **immediately**, with no grace period, no chance to flush a log line, no chance to catch the signal â€” a fundamentally different, harder failure than a CPU limit's throttling (covered in the scaling module). This is a hard ceiling, not a soft one.

```bash
kubectl describe pod <pod> | grep -A3 "Last State"   # confirms OOMKilled + exit code 137
kubectl top pod <pod> --containers                    # current usage vs. requests/limits
kubectl get pod <pod> -o jsonpath='{.spec.containers[*].resources}'  # what the limit actually is
```

Root causes: a genuine memory leak (usage climbs steadily over the pod's lifetime, visible in a Prometheus graph of `container_memory_working_set_bytes` over hours/days, not a single spike); an undersized limit for a legitimately memory-hungry workload (a JVM with a heap sized close to or above the container's memory limit â€” the JVM's own GC/heap sizing needs headroom above its heap for metaspace, thread stacks, and off-heap buffers, and setting `-Xmx` equal to the container limit is a very common self-inflicted OOM-kill); or a sudden spike from an unbounded batch operation (loading an entire large file/dataset into memory at once instead of streaming it). The fix is never "just raise the limit" as a first instinct â€” check `container_memory_working_set_bytes` history first to distinguish a genuine leak (needs a code fix) from legitimate but undersized peak usage (needs a limit increase, ideally informed by VPA recommendations from the scaling module).

### Pending â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** `STATUS: Pending`, pod never gets a node assigned (`kubectl get pod -o wide` shows no `NODE`).

This means the scheduler evaluated every node and found none that satisfied the pod's requirements â€” always diagnosed from `kubectl describe pod`'s Events, which name the exact predicate:

1. **Insufficient resources** â€” Events show `0/N nodes are available: N Insufficient cpu` (or `memory`). Either the cluster genuinely has no room (autoscaler should be provisioning â€” see the scaling module's zero-requests trap if it isn't), or the pod is requesting more than any single node's allocatable capacity can ever satisfy (a request larger than the biggest instance type in any node pool â€” no amount of scaling fixes this, it's a request-sizing bug).
2. **Unsatisfiable node affinity / anti-affinity / taints.** Events show `0/N nodes are available: N node(s) didn't match Pod's node affinity/selector` or `N node(s) had untolerated taint`. Check `kubectl get nodes --show-labels` against the pod's `nodeSelector`/`affinity`, and `kubectl describe node <node>` for its taints against the pod's `tolerations`.
3. **PVC will never bind.** Events show `pod has unbound immediate PersistentVolumeClaims`. Check `kubectl get pvc` â€” if it's stuck `Pending` itself, the underlying `StorageClass` provisioning is failing (wrong zone for `WaitForFirstConsumer` topology, quota exhausted, or a StorageClass that doesn't exist at all â€” a common typo-class bug).
4. **PodDisruptionBudget or resource quota blocking creation** in the namespace â€” Events show a quota-exceeded message directly (`exceeded quota: <name>, requested: ..., used: ..., limited: ...`) rather than a scheduling predicate failure, a useful distinction: this failure happens *before* scheduling is even attempted.

```bash
kubectl describe pod <pod> | grep -A10 Events         # exact predicate that failed
kubectl get nodes -o custom-columns=NAME:.metadata.name,ALLOC-CPU:.status.allocatable.cpu,ALLOC-MEM:.status.allocatable.memory
kubectl describe node <node> | grep Taints
kubectl get resourcequota -n <namespace>
```

### Evicted â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** Pod's `STATUS` shows `Evicted` directly (not `CrashLoopBackOff` â€” it's terminal, the pod won't restart on its own; a controller like a Deployment will create a replacement).

Eviction is the kubelet **proactively** killing pods to protect the node itself, triggered by node-level pressure, checked against default hard thresholds:

| Signal | Default hard threshold |
|---|---|
| `memory.available` | `100Mi` |
| `nodefs.available` | `10%` |
| `imagefs.available` | `15%` |
| `nodefs.inodesFree` | `5%` |
| `imagefs.inodesFree` | `5%` |

Crossing a **hard** threshold triggers immediate eviction with no grace period; **soft** thresholds (configurable, off by default on some of these) allow a grace period before evicting. Eviction order follows the same QoS-class logic covered in the scaling module: BestEffort pods first, then Burstable ordered by how far usage exceeds requests, Guaranteed last â€” a node under memory pressure evicts the pods with the weakest resource guarantees first, which is a direct, practical reason to always set requests even on workloads that don't need aggressive autoscaling.

```bash
kubectl get pod <pod> -o jsonpath='{.status.reason}{"\n"}{.status.message}'
kubectl describe node <node> | grep -A5 Conditions    # MemoryPressure/DiskPressure/PIDPressure True?
kubectl get events --field-selector reason=Evicted -A
```

Real, common root cause worth naming explicitly: **unbounded log growth filling node disk** â€” a container logging at high volume to stdout with no log rotation configured at the node/runtime level fills `/var/lib/docker` (or equivalent containerd path) until `nodefs.available` or `imagefs.available` crosses the hard threshold, evicting every BestEffort/Burstable pod on that node regardless of whether they had anything to do with the log growth â€” the "innocent bystander" eviction pattern that makes root-causing an eviction storm from Events alone insufficient; you also need to check node-level disk usage, not just the evicted pod's own state.

### DNS failures â€” symptom â†’ cause â†’ command â†’ fix

**Symptom:** Intermittent slow lookups (requests hang for exactly ~5 seconds before succeeding or failing) or outright failed resolution for external or in-cluster names, often *not* correlated with CoreDNS pod health looking fine.

Two distinct, well-known root causes, and they are not the same bug:

1. **The conntrack UDP race (~5-second stalls).** When two DNS queries (commonly a pod's glibc resolver firing an A and an AAAA query nearly simultaneously) go out over UDP from the same source port at almost the same instant, there's a known race in the kernel's conntrack table insertion that can cause one of the two packets to be dropped rather than correctly tracked, and the client-side resolver then waits out its full UDP timeout (commonly **5 seconds**) before retrying or giving up. This is a kernel-level race, not a CoreDNS bug â€” restarting CoreDNS does nothing for it. Mitigations: force TCP for DNS (some resolvers/libraries support `use-vc`), reduce concurrent A/AAAA lookups (disabling AAAA lookups for IPv4-only environments), or use the `--single-request-reopen`/`single-request` resolver options where available.
2. **`ndots:5` search-domain amplification.** Kubernetes' default pod DNS config sets `ndots:5`, meaning any queried name with fewer than 5 dots gets the cluster's search domains appended and tried *before* the name is ever tried as an absolute/external lookup. A pod calling `api.stripe.com` (2 dots) tries `api.stripe.com.<namespace>.svc.cluster.local`, `api.stripe.com.svc.cluster.local`, `api.stripe.com.cluster.local`, and the cluster's configured search domains, each a failed NXDOMAIN round-trip, *before* finally trying `api.stripe.com.` as an absolute name and succeeding â€” meaning every single external call pays for up to 4-5 wasted DNS queries. This isn't intermittent breakage, it's a steady, often-unnoticed latency tax that becomes visible as elevated p99s on any service making frequent external calls. Fix: for pods that mostly call external services, either use a fully-qualified name with a trailing dot (`api.stripe.com.`, skipping search-domain expansion entirely) or explicitly set `dnsConfig.options` with a lower `ndots` value on the pod spec.

```bash
kubectl exec -it <pod> -- cat /etc/resolv.conf         # confirm ndots and search domains
kubectl run -it --rm dnsdebug --image=busybox:1.36 --restart=Never -- nslookup kubernetes.default
kubectl get pods -n kube-system -l k8s-app=kube-dns     # CoreDNS pod health, restarts
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100  # CoreDNS-side errors (separate from the race)
```

---

## Build it from scratch

The mechanical skill worth being able to demonstrate live is the ephemeral-debug-container workflow against a distroless/shell-less image, since that's the exact scenario the old SSH-and-`docker exec` workflow couldn't handle at all:

```bash
# untested sketch â€” assumes a running pod "api-7d9f-x2j4k" built from a distroless image
# with no shell, and you need to inspect its filesystem/network from the inside

# 1. inject an ephemeral debug container sharing the target's network namespace,
#    and (with --target) its process namespace too, without touching the pod spec
kubectl debug -it api-7d9f-x2j4k --image=busybox:1.36 --target=api -- sh

# inside the ephemeral container:
ps aux                       # see the target container's processes (via shared PID namespace)
cat /proc/1/status | grep VmRSS   # actual memory usage of PID 1 in the target, bypassing
                                    # the target's own lack of a shell/tools entirely
wget -qO- http://localhost:8080/healthz   # hit the target's own health endpoint locally

# 2. a node-level debug session for node-wide disk/memory pressure investigation
kubectl debug node/<node-name> -it --image=busybox:1.36 -- chroot /host sh
# now inside a container with the HOST's root filesystem mounted at /, chrooted in:
df -h /var/lib/containerd     # real disk pressure check backing an Evicted node
```

A minimal reproduction worth running once by hand to internalize the OOM-kill mechanics rather than trust them from memory:

```yaml
# untested sketch â€” deliberately triggers OOMKilled to see exit code 137 firsthand
apiVersion: v1
kind: Pod
metadata: { name: oom-repro }
spec:
  containers:
  - name: stress
    image: polinux/stress
    resources:
      limits: { memory: "50Mi" }
    args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
    # requests 150Mi of memory against a 50Mi limit -> OOM-killed almost immediately
```
```bash
kubectl apply -f oom-repro.yaml
kubectl get pod oom-repro -w                              # watch it cycle
kubectl describe pod oom-repro | grep -A5 "Last State"     # Reason: OOMKilled, Exit Code: 137
```

---

## How it's done in production

Production troubleshooting practice leans on never needing to reach the manual `kubectl describe`/`logs` funnel at all for the common cases: alerting fires directly on the underlying signal (container restart-count rate, `container_cpu_cfs_throttled_periods_total`, OOM-kill event counters scraped from `kube-state-metrics`, node condition changes) rather than waiting for a human to notice a `CrashLoopBackOff` in a dashboard. `kube-state-metrics` exposes exactly the object-state signals (`kube_pod_status_phase`, `kube_pod_container_status_restarts_total`, `kube_pod_container_status_last_terminated_reason`) that turn this whole manual funnel into a Prometheus alert rule, and most teams wire `OOMKilled`/`Evicted` counts and `CrashLoopBackOff` restart-rate directly into paging rather than relying on someone running `kubectl get pods` and noticing.

| Symptom | Cause | Fix |
|---|---|---|
| Fleet-wide `CrashLoopBackOff` immediately after a deploy | Bad rollout â€” new image/config crashes on startup for every replica | `kubectl rollout undo deployment/<name>`; confirm via `--previous` logs before diagnosing further, don't investigate mid-incident |
| Single pod `OOMKilled` repeatedly, others in the same Deployment are fine | Uneven load distribution, or the failing pod happens to handle a memory-heavy request pattern (large batch, big payload) others don't | Check request routing/sharding for skew before assuming it's a uniform sizing problem; raise the limit only after confirming it's not a leak |
| `ImagePullBackOff` across an entire node, unrelated pods, right after a scale-up event | Registry rate limiting hit during a burst of simultaneous pulls | Authenticate registry pulls, or run a pull-through cache/mirror in-cluster to absorb burst pulls without hitting the upstream registry's limit |
| Pods `Pending` cluster-wide despite Cluster Autoscaler/Karpenter enabled and healthy | Pods have no `resources.requests` (see the scaling module) â€” invisible to the autoscaler's scale-up decision | Set explicit requests on every workload; treat missing requests as a correctness bug, not an optimization |
| Sudden wave of `Evicted` pods across several nodes, no obvious memory culprit | A verbose logging bug filling node disk (`nodefs`/`imagefs`) rather than memory pressure | Check node disk usage directly, not just the evicted pod's own resource usage; fix log volume/rotation, not just the symptom pod |
| p99 latency spikes exactly 5 seconds for a subset of external calls, intermittently | Conntrack UDP race dropping one of a simultaneous A/AAAA query pair | Force TCP DNS or disable AAAA lookups where IPv6 isn't in use; this is a kernel race, restarting CoreDNS does nothing |
| Steady elevated latency (not intermittent) on every external API call from in-cluster services | `ndots:5` default causing 4-5 wasted search-domain queries before the real external lookup succeeds | Use trailing-dot FQDNs for external calls, or set a lower `ndots` via `dnsConfig.options` on pods that call external services heavily |

---

## Tradeoffs & when NOT to use it

- **Don't `kubectl exec`/`kubectl debug` into production pods as a first-line habit.** In regulated environments (PCI, HIPAA, SOC2 scopes) live shell access to a running production container is itself an audit finding waiting to happen; invest in structured logging and metrics that answer the question without a live session, and treat `kubectl debug` as an escalation tool, not routine practice.
- **Don't reflexively raise memory limits in response to every OOMKilled event.** Check `container_memory_working_set_bytes` history first â€” a steadily climbing line over hours/days is a leak that a bigger limit only delays, not fixes; only genuinely spiky-but-bounded usage patterns justify a limit increase as the actual fix.
- **Don't treat `tcp_tw_recycle`-style "just tune a kernel sysctl" fixes for the DNS conntrack race as a first move.** It's a real kernel-level race with narrow, specific mitigations (TCP DNS, disabling unnecessary AAAA lookups); broad kernel tuning without understanding the exact race risks side effects elsewhere on the node, the same lesson as the TIME_WAIT module's `tcp_tw_recycle` warning.
- **Don't lower `ndots` cluster-wide as a blanket fix.** A pod that legitimately does a lot of short-name in-cluster service lookups (`myservice` resolving via search-domain expansion to `myservice.namespace.svc.cluster.local`) depends on `ndots:5`'s default behavior working correctly; the fix belongs on the specific pods making heavy external calls, via `dnsConfig`, not as a cluster-wide CoreDNS/kubelet default change that could break in-cluster short-name resolution elsewhere.
- **Don't assume every `Evicted` pod's own resource usage is the culprit.** The "innocent bystander" pattern (log-driven disk pressure evicting unrelated pods) is common enough that node-level disk/memory investigation should happen before or alongside investigating the specific evicted pod.

---

## Interview questions

### Q1 â€” A pod shows `CrashLoopBackOff`. Walk me through your exact diagnostic sequence.
**Testing:** whether the describe-before-logs discipline is real habit or you'll guess.
**Answer:** `kubectl describe pod` first, to see `Last State`, `Exit Code`, and recent Events â€” this immediately tells you whether it's `OOMKilled` (137), a probe kill, or an app-level crash, without guessing. Then `kubectl logs <pod> --previous` to see what the last terminated instance actually printed before dying, since the currently-running instance (if mid-loop) may have empty or misleadingly short logs.
**Follow-up trap:** *"The Exit Code is 137. Is that necessarily OOMKilled?"* â€” 137 = 128+9 = killed by SIGKILL, and the OOM killer is the most common source, but any external SIGKILL (a manual `kubectl delete --force`, a node running `systemd-oomd` at the OS level outside the container's own cgroup limit) produces the same code â€” check `Reason: OOMKilled` specifically in the `Last State` block, don't infer OOM purely from the exit code number.

### Q2 â€” What's the actual backoff schedule for CrashLoopBackOff, and why does it exist?
**Testing:** whether you know real numbers, not just the name.
**Answer:** 10s, 20s, 40s, 80s, 160s, capped at 300s (5 minutes) between restart attempts, resetting after the container stays up 10 minutes straight. It exists so a fleet-wide crash-loop (bad rollout, bad shared config) doesn't retry-storm downstream dependencies at full restart rate.
**Follow-up trap:** *"A pod's been crash-looping for 20 minutes. How many restart attempts has it made?"* â€” enough to have hit the 300s cap already (10+20+40+80+160=310s to reach the cap, roughly 5 minutes in), so most of those 20 minutes were spent at the 300s ceiling â€” meaning "just wait a bit" can genuinely mean multi-minute gaps between attempts, worth knowing before assuming a pod is unresponsive rather than mid-backoff.

### Q3 â€” Why does `kubectl logs` show nothing useful for an `ImagePullBackOff` pod?
**Testing:** the distinction between pre-start and post-start failures.
**Answer:** No container has ever started â€” the failure happens entirely in the image-pull phase, before the container runtime creates and runs anything. `kubectl logs` reads a running or previously-run container's stdout/stderr; there's nothing to read. `kubectl describe pod`'s Events is the only place the failure reason (auth, not-found, rate-limit, network) is recorded.
**Follow-up trap:** *"How do you tell a rate-limit failure apart from a genuinely wrong image name, just from Events?"* â€” the error text differs: a not-found/wrong-tag error names the specific manifest/tag as missing; a rate-limit error surfaces a 429-flavored message from the registry; an auth failure surfaces a 401/403-flavored message. Reading the actual Events text matters more than pattern-matching on the state name alone.

### Q4 â€” Explain the mechanical difference between a pod being `OOMKilled` and a pod being `Evicted`.
**Testing:** whether cgroup-level vs. node-level failure domains are actually understood.
**Answer:** OOMKilled is the kernel's cgroup OOM killer defending that specific container's memory cgroup after it exceeded its own limit â€” a container-scoped, immediate `SIGKILL`, exit code 137. Eviction is the kubelet proactively killing pods to defend the *node* as a whole under memory/disk/PID pressure, evicting in QoS order (BestEffort first), and can happen to a pod that never itself exceeded any limit of its own â€” it's simply on a node where aggregate pressure crossed a threshold.
**Follow-up trap:** *"Could a Guaranteed-QoS pod ever be Evicted?"* â€” yes, though it's evicted last, not never â€” if node pressure is severe enough (e.g. a runaway BestEffort pod that itself has no limit consuming unbounded memory before anything stops it), eviction can still reach Guaranteed pods once everything with a weaker guarantee is already gone; QoS class changes eviction *order*, not immunity.

### Q5 â€” What are the default kubelet hard eviction thresholds, and what's the difference between a hard and soft threshold?
**Testing:** real numbers, not just "the kubelet evicts under pressure."
**Answer:** `memory.available: 100Mi`, `nodefs.available: 10%`, `imagefs.available: 15%`, `nodefs.inodesFree: 5%`, `imagefs.inodesFree: 5%`. Hard thresholds trigger immediate eviction with no grace period; soft thresholds (separately configurable, often unset by default) allow a grace period before evicting, giving pods a chance to naturally finish or be rescheduled before the kubelet forces the issue.
**Follow-up trap:** *"A node shows `DiskPressure: True` but no pods have been evicted yet. Why?"* â€” either the threshold crossed is a soft one still inside its grace period, or the pressure condition just flipped and eviction hasn't executed yet on the kubelet's next sync â€” `DiskPressure: True` is a leading indicator, not proof evictions have already happened; check `kubectl get events --field-selector reason=Evicted` to confirm actual evictions versus just the condition.

### Q6 â€” A node shows a wave of Evicted pods, but the evicted pods themselves show low, unremarkable memory usage. What's your hypothesis?
**Testing:** the "innocent bystander" pattern â€” do you look past the evicted pod itself.
**Answer:** Likely disk pressure (`nodefs`/`imagefs`), not memory pressure, and likely caused by something unrelated to the evicted pods themselves â€” a high-volume logger filling `/var/lib/containerd` (or Docker's equivalent), or an unrelated pod's ballooning ephemeral storage usage. Eviction under disk pressure removes pods in QoS order regardless of whether they contributed to the disk usage.
**Follow-up trap:** *"How do you find the actual disk hog without SSHing onto the node?"* â€” `kubectl debug node/<node> -it --image=busybox -- chroot /host sh` gives you a shell into the host's real filesystem via an ephemeral container, from which `du`/`df` against `/var/lib/containerd` or `/var/log` finds the real consumer without needing direct node SSH access.

### Q7 â€” A pod is stuck `Pending`. `kubectl describe pod` shows `0/12 nodes are available: 12 Insufficient memory`. The cluster has Cluster Autoscaler enabled and healthy. Why isn't a new node being provisioned?
**Testing:** connects back to the scaling module's zero-requests trap, tests cross-module synthesis.
**Answer:** Either the pod genuinely requests more memory than any configured node group's instance type can ever provide (a request-sizing bug, no amount of scaling helps), or â€” the more common case â€” the autoscaler is correctly triggering but hasn't finished yet (4-8 minutes for classic Cluster Autoscaler against node groups) and the pod is transiently Pending while capacity is being provisioned, which is expected behavior, not a bug.
**Follow-up trap:** *"How do you tell those two cases apart quickly?"* â€” check `kubectl get events -n kube-system` for Cluster Autoscaler/Karpenter's own scale-up events referencing this pending pod; if a scale-up was triggered, it's just provisioning latency; if no scale-up event exists at all, the request is likely unsatisfiable by any available node group and needs a resource-sizing fix, not more patience.

### Q8 â€” Why does a pod calling `api.stripe.com` sometimes have noticeably higher latency than the same call made from outside the cluster, even though DNS "works fine"?
**Testing:** `ndots:5` amplification, a subtle but common real cost.
**Answer:** Kubernetes' default pod DNS config sets `ndots:5` â€” any queried name with fewer than 5 dots gets the cluster's search domains tried first. `api.stripe.com` (2 dots) triggers several failed in-cluster search-domain lookups (`api.stripe.com.svc.cluster.local`, etc.) before the resolver finally tries the name as absolute and succeeds â€” a steady latency tax on every external call, not an intermittent failure.
**Follow-up trap:** *"Is this the same bug as the '5 second DNS delay' people talk about?"* â€” no, and conflating them is a real interview miss: `ndots` amplification is a steady, multi-query latency tax from search-domain expansion; the "5 second delay" is a separate, kernel-level conntrack race dropping one of a simultaneous UDP A/AAAA query pair, causing an intermittent full-timeout stall. Different mechanisms, different fixes (trailing-dot FQDN or lower `ndots` vs. forcing TCP DNS or disabling AAAA).

### Q9 â€” Explain the actual kernel-level mechanism behind the well-known "5 second Kubernetes DNS delay."
**Testing:** staff-level depth â€” do you know the mechanism or just the folklore name.
**Answer:** A race condition in the Linux kernel's conntrack table when two UDP DNS queries (typically a simultaneous A and AAAA lookup from glibc's resolver) go out from the same source port at nearly the same instant â€” one packet's conntrack entry can clobber or fail to properly register against the other, causing that packet (and its response) to be effectively dropped. The client-side resolver then has no reply for that query and waits out its full timeout, commonly 5 seconds, before retrying or failing outright. It's a kernel networking bug pattern, not a CoreDNS application bug.
**Follow-up trap:** *"Does restarting CoreDNS fix it?"* â€” no, and answering "restart CoreDNS" here is the exact wrong instinct the interviewer is checking for â€” CoreDNS's own health is irrelevant to a client-side kernel conntrack race; the fix has to happen on the querying side (forcing TCP DNS, disabling unnecessary AAAA queries) or at the kernel/CNI level, not by touching the DNS server at all.

### Q10 â€” What does `kubectl debug` actually do differently from the older `kubectl exec` + rebuild-a-debug-image workflow?
**Testing:** whether the ephemeral containers feature (GA 1.25) is understood mechanically, not just as a name.
**Answer:** `kubectl debug --target=<container>` injects a temporary ephemeral container into an *already-running* pod, sharing that pod's network namespace and (with `--target`) the target container's process namespace, without modifying the pod spec, without a restart, and without needing the original image to contain any debugging tools at all. The older workflow required either the production image itself to have a shell/tools (defeating minimal/distroless image security goals) or maintaining a separate debug-variant image and swapping it in, which meant a restart and a different running artifact than what's actually in production.
**Follow-up trap:** *"If the target container has crashed and is gone, does `kubectl debug --target` still work?"* â€” no â€” `--target` requires the target container to actually be running so its namespaces exist to attach to; against a crashed/terminated container you're back to `kubectl logs --previous` and `describe pod`, or `kubectl debug node/<node>` for host-level investigation, since there's no live process namespace left to share.

### Q11 â€” A JVM-based service keeps getting OOMKilled shortly after startup, even though its memory limit "should" be plenty for the app's actual working set. What's the likely misconfiguration?
**Testing:** a specific, real, very common production bug.
**Answer:** `-Xmx` (max heap) set equal to or too close to the container's memory limit, leaving no headroom for the JVM's off-heap usage â€” metaspace, thread stacks, direct buffers, JIT-compiled code cache, GC bookkeeping â€” all of which sit outside the heap but still count against the cgroup's total memory limit. The JVM can be OOM-killed by the kernel while its own heap usage looks nowhere near `-Xmx`, because the container-level limit was crossed by off-heap usage the heap-focused view doesn't show.
**Follow-up trap:** *"Doesn't the JVM detect the container's memory limit automatically now?"* â€” modern JVMs (container-aware since Java 10+, with cgroup v2 support maturing further since) do read the cgroup limit and size default heap fractions against it automatically, which helps but doesn't eliminate the problem if `-Xmx` is set explicitly and aggressively rather than left to the JVM's own container-aware defaults â€” an explicit `-Xmx` overrides the auto-sizing safety margin entirely.

### Q12 â€” Two pods in the same Deployment, same image, same resource requests/limits â€” one is `Pending`, the other is `Running`. How is that possible?
**Testing:** understanding that scheduling is per-pod and per-node, not per-Deployment.
**Answer:** The scheduler evaluates each pod independently against current node capacity and constraints at the moment it tries to schedule that specific pod â€” if the first pod consumed the last available capacity satisfying some constraint (a specific node's remaining allocatable memory, a topology spread constraint, an anti-affinity rule keeping replicas apart), the second pod can genuinely have nowhere left to go even with identical requests, until more capacity appears (autoscaler) or the constraint is relaxed.
**Follow-up trap:** *"If it's a topology spread constraint, what would Events show for the Pending one specifically?"* â€” a message referencing the topology constraint by name (e.g. `didn't satisfy existing pods anti-affinity rules` or a topology-spread-specific unschedulable reason), distinguishable from a plain resource-insufficiency message â€” the fix there is adjusting `maxSkew`/constraint strictness or adding capacity in the specific topology domain that's full, not just "add more nodes anywhere."

### Q13 â€” Your on-call gets paged for a fleet-wide `CrashLoopBackOff` immediately after a deploy. What's your first action, before you start reading logs?
**Testing:** incident-response judgment, not just diagnostic mechanics.
**Answer:** Roll back first (`kubectl rollout undo deployment/<name>`), diagnose after. If every replica is crash-looping right after a deploy, the deploy is almost certainly the cause, and restoring service takes priority over root-causing mid-incident â€” the previous working ReplicaSet is still there and rollback is fast and low-risk compared to debugging live while users are impacted.
**Follow-up trap:** *"What if the rollback itself doesn't fix it â€” replicas keep crash-looping on the old image too?"* â€” that reframes the whole hypothesis: it's not the deploy, it's likely an external dependency (a database migration that ran as part of the deploy and can't be un-run, a config/secret rotated at the same time, a downstream service that changed independently) â€” the fix at that point is finding what else changed at the same timestamp, not re-rolling-back an already-reverted image.

### Q14 â€” Why is `container_cpu_cfs_throttled_periods_total` relevant to a troubleshooting conversation about CrashLoopBackOff, even though throttling doesn't kill a container?
**Testing:** cross-module synthesis with the scaling module's CFS mechanics.
**Answer:** Severe, sustained CPU throttling can cause an application to fail its liveness probe simply because it's too starved of actual CPU time to respond within the probe's timeout â€” producing a `CrashLoopBackOff` whose root cause is CPU throttling, not any bug in the app itself. Reading `describe pod` shows "Liveness probe failed" and a clean exit code, which looks like a probe-tuning issue on the surface but traces back to CFS quota starvation if throttling metrics are checked.
**Follow-up trap:** *"How would you tell 'probe genuinely too aggressive' apart from 'CPU-starved so it can't respond in time,' from Events alone?"* â€” Events alone won't distinguish them; you need `container_cpu_cfs_throttled_periods_total` correlated against the probe failure timestamps â€” if throttling spikes align with probe failures, it's a CPU/resourcing problem masquerading as a probe-tuning problem, and raising the CPU limit (or removing it, per the scaling module) is the real fix, not just loosening probe timeouts.

### Q15 â€” What's the single biggest mistake candidates make when explaining how they'd debug a production Kubernetes incident?
**Testing:** meta-level judgment about the debugging process itself.
**Answer:** Jumping straight to `kubectl logs` (or worse, restarting things) without first running `kubectl describe pod` to establish which failure bucket (pull failure, crash, scheduling failure, eviction, resource pressure) they're actually in â€” logs are the right next step for maybe half of these states and actively useless or misleading for the other half (ImagePullBackOff, most Pending cases, and OOM-kills where the process never got to log anything).
**Follow-up trap:** *"Give a concrete example where 'just restart it' makes things worse."* â€” a fleet-wide OOMKilled/CrashLoopBackOff caused by a memory leak that manifests slowly: restarting resets the memory usage to zero and temporarily "fixes" the symptom, burning the incident-response window without addressing the leak, and the same pods will OOM-kill again on the same schedule â€” restarting without understanding `Last State`/exit code first can mask exactly the signal (a climbing memory graph over hours) that would have identified it as a leak rather than a one-off spike.

---

## Red flags that fail you

- Running `kubectl logs` before `kubectl describe pod` as a reflex, especially for ImagePullBackOff or Pending states where logs are structurally useless.
- Not knowing exit code 137 = SIGKILL (128+9), or claiming it always means OOMKilled without checking `Reason` in `Last State`.
- Treating "restart CoreDNS" as a fix for the conntrack-race 5-second DNS delay.
- Conflating `ndots:5` amplification (steady latency tax) with the conntrack race (intermittent full-timeout stall) as the same bug.
- Reflexively raising a memory limit in response to OOMKilled without checking whether usage history shows a leak versus a legitimate bounded spike.
- Not knowing the default hard eviction thresholds even approximately, or confusing Evicted (node-level, kubelet-driven) with OOMKilled (cgroup-level, kernel-driven).
- Assuming a `Pending` pod's problem is always "not enough nodes" without reading the actual predicate failure in Events (affinity, taints, PVC binding, quota).

---

## Cheat card

```
FUNNEL: kubectl get pods -o wide -> kubectl describe pod (Events, Last State) ->
        kubectl logs --previous (only useful once container has actually run)

CRASHLOOPBACKOFF: backoff 10/20/40/80/160s, cap 300s, resets after 10min stable uptime
  causes: app crash (logs --previous) | OOMKilled (describe, NOT logs) | failed liveness
  probe (Events: "Liveness probe failed" -> Killing) | missing config/secret ref

EXIT CODES: 137 = 128+9 = SIGKILL (often OOMKilled, check Reason explicitly)
            143 = 128+15 = SIGTERM (graceful shutdown request)
            0   = clean exit (probe-triggered kill still shows 0 if app handled SIGTERM)

IMAGEPULLBACKOFF: pre-start failure, ZERO logs available, diagnose from Events only
  causes: wrong tag | missing/wrong imagePullSecrets | registry rate limit (429) |
  node can't reach registry (generic timeout, not auth/not-found)

OOMKILLED: kernel cgroup OOM killer, immediate SIGKILL, no grace period, no log flush
  check container_memory_working_set_bytes HISTORY: leak (climbing) vs bounded spike
  JVM trap: -Xmx too close to container limit, no headroom for off-heap usage

PENDING: scheduler predicate failure, read exact reason in Events
  causes: insufficient cpu/mem | unsatisfiable affinity/taint | unbound PVC | quota exceeded

EVICTED: kubelet defends the NODE (not the cgroup) under pressure, QoS-ordered
  (BestEffort first, Burstable next, Guaranteed last)
  default hard thresholds: memory.available 100Mi | nodefs.available 10% |
    imagefs.available 15% | nodefs/imagefs.inodesFree 5%
  "innocent bystander" pattern: log-fills-disk evicts UNRELATED low-usage pods too

DNS: two DIFFERENT bugs, don't conflate them
  (1) conntrack UDP race: simultaneous A/AAAA query collision -> ~5s stall, INTERMITTENT,
      kernel-level, restarting CoreDNS does NOTHING
  (2) ndots:5 default: <5-dot names try search domains first -> up to 5 wasted queries per
      EXTERNAL call, STEADY latency tax, not intermittent -> fix: trailing-dot FQDN or
      lower ndots via dnsConfig.options on the specific pods

TOOLS: kubectl debug -it <pod> --image=busybox --target=<container> (ephemeral container,
  shares target's netns +, with --target, its PID ns; GA since 1.25, works on distroless)
  kubectl debug node/<name> -it --image=busybox -- chroot /host sh (node-level, real disk)
```

## Sources

- [Kubernetes Releases](https://kubernetes.io/releases/) â€” accessed 2026-08-03
- [Kubernetes v1.34](https://kubernetes.io/releases/1.34) â€” accessed 2026-08-03
- Kubernetes documentation â€” Pod Lifecycle, Debug Running Pods, Node-pressure Eviction, DNS for Services and Pods
- [Troubleshoot CrashLoopBackOff events â€” Google Cloud GKE docs](https://docs.cloud.google.com/kubernetes-engine/docs/troubleshooting/crashloopbackoff-events) â€” accessed 2026-08-03
- [Kubernetes DNS Troubleshooting: CoreDNS, ndots, and the 5-Second Timeout â€” Kubenatives](https://www.kubenatives.com/p/kubernetes-dns-troubleshooting-coredns) â€” accessed 2026-08-03
- Kubernetes GitHub issue #119985 â€” Default values of Kubelet's EvictionHard â€” accessed 2026-08-03
- Kubernetes documentation â€” Ephemeral Containers (`kubectl debug`, GA since 1.25)

## Changelog
- 2026-08-03 â€” created
