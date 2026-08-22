# cgroups + Namespaces: What Docker Actually Is

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 1.5h · **Prereqs:** T16-os-internals · **Updated:** 2026-08-03
> **Module id:** `T16-containers-low-level` · **Tags:** os

## The 30-second version

A container is not a lightweight VM — it's an ordinary Linux process that the kernel has been told to lie to about what it can see (namespaces) and constrain about what it can use (cgroups). Namespaces give visibility isolation: PID namespace makes a process think it's PID 1 in its own process tree, net namespace gives it a private network stack and interfaces, mnt namespace gives it a private filesystem view, and seven more types (uts, ipc, user, cgroup, time) each virtualize one more kernel resource — none of this limits *how much* anything the process can use, only *what it can see*. Cgroups (control groups) do the opposite: they enforce hard resource limits — CPU via `cpu.cfs_quota_us`/`cpu.cfs_period_us` (throttle, don't kill), memory via `memory.max` (kernel OOM-kills with SIGKILL the instant you cross it, no throttling possible because memory isn't compressible) — completely independent of what the process can see. Docker's actual architecture is a chain of processes: the `docker` CLI talks to `dockerd`, which delegates to `containerd` for lifecycle management, which spawns a `containerd-shim` per container (so containerd can restart without killing running containers), which calls `runc` — the low-level OCI runtime that actually calls the `clone()`/`unshare()` and cgroup-filesystem syscalls, then execs into the container process and exits. There's no hypervisor, no separate kernel — a container shares the host kernel entirely, which is precisely why container escapes (CVE-2024-21626, CVE-2025-31133) are a fundamentally different and generally more severe threat than a VM escape: breaking out of a container's namespace/cgroup jail lands you directly on the host kernel, not in a hypervisor layer with another boundary to cross.

## Why this gets asked

Because "what is a container, actually" separates people who've used Docker from people who've debugged what happens when the abstraction leaks — a process in a container getting OOMKilled at a limit that looked fine in `top` (because `top` inside the container often doesn't see the cgroup limit, only the host's total memory), a CPU-bound service getting mysteriously throttled well below 100% CPU usage because of `cfs_quota_us` math nobody looked at, or a `kubectl exec` into a container revealing PID 1 is your application with none of the usual init-process signal handling, causing zombie processes to accumulate. The interviewer wants to know you can explain resource limits and isolation as two genuinely separate kernel mechanisms rather than "Docker does the isolation thing," and that you've seen at least one incident where the container abstraction didn't behave the way `docker run --memory` intuitively suggested it would.

---

## Lineage: past → present → future

**What came before.** Before containers, the isolation options were either a full hypervisor-based VM (Xen 2003, KVM 2007) — genuinely separate kernels, strong isolation, but each VM pays the overhead of booting its own OS, its own memory footprint (typically hundreds of MB to GBs baseline), and slow startup (tens of seconds) — or `chroot()` (1979, from Unix V7), which changes a process's apparent filesystem root but provides no process, network, or resource isolation at all and is trivially escapable by anyone with sufficient privilege (a chrooted root process can often break out via file descriptor tricks or device nodes). FreeBSD jails (2000) and Solaris Zones (2004) were the first real attempts at OS-level virtualization with actual isolation guarantees, but they were platform-specific and never got Linux-kernel-wide adoption. The specific pain that drove Linux containers: VMs were too heavy for "I just want to isolate and resource-limit ten different application processes on one box" — the boot time, memory overhead, and management complexity of ten VMs for ten services was a real tax nobody wanted to keep paying as service-oriented architectures multiplied the number of deployable units.

**Where it stands now.** Linux namespaces (introduced piecemeal 2002-2013: mnt namespace first, PID/net/ipc/uts around 2006-2008, user namespace stabilizing around 2013, cgroup namespace in 2016, time namespace in 2020) plus cgroups (v1 introduced 2008, v2 redesigned and merged in kernel 4.5, 2016) are the two kernel primitives every Linux container runtime is built on — there is no "container" syscall or kernel object; `docker run` is syntactic sugar over `clone()` with namespace flags plus writing to cgroup control files. The Open Container Initiative (OCI, 2015) standardized the runtime interface so `runc` (the reference implementation, originally extracted from Docker itself) is now used underneath Docker, containerd, CRI-O, and Kubernetes uniformly — this is the live consensus, there isn't a competing incompatible standard at the runtime layer anymore. The genuinely live disagreement is cgroups v1 vs v2: v2 unifies what was a separate, sometimes inconsistent per-controller hierarchy in v1 into a single hierarchy with more consistent accounting (notably fixing buffered I/O accounting, which was notoriously unreliable under v1), and virtually every current distribution defaults to v2 now — but a meaningful amount of production infrastructure, older Kubernetes clusters, and some monitoring tooling still assumes v1's interface, so "does your cluster's cgroup driver match what your kubelet/runtime expects" is a real, still-current operational question, not settled history.

**Where it's heading.** Two directions are both real and both still niche relative to standard containers: gVisor (a userspace kernel intercepting syscalls, Google, 2018) and Kata Containers (a lightweight VM with a lighter-weight guest kernel, but still a real hypervisor boundary) both trade some of the "just a process" simplicity for a stronger isolation boundary specifically because container escapes keep happening against a shared-kernel model, and they're used today in genuinely multi-tenant, untrusted-code contexts (Google Cloud Run's original runtime, some serverless/FaaS platforms) rather than as a general container replacement. WebAssembly-based sandboxing (WASI, component model) is the more speculative direction — it offers a fundamentally different, much smaller trusted-computing-base isolation model, real in specific edge/serverless deployments today but not a general-purpose Docker replacement yet, and how far it displaces traditional containers over the next several years is genuinely unresolved rather than a confident prediction.

---

## Mental model

```
                     docker run nginx
                          |
                     dockerd (daemon)
                          |
                     containerd  <-- lifecycle mgmt: pull image, start/stop, snapshot
                          |
                containerd-shim  <-- 1 per container, survives containerd restarts,
                          |          holds stdio, reports exit status
                        runc      <-- OCI runtime, does the ACTUAL isolation work:
                          |
              +-----------+-----------+
              |                       |
        clone()/unshare()       cgroup fs writes
        (NAMESPACES)            (CGROUPS)
        "what can I see?"       "how much can I use?"
              |                       |
        PID: I'm PID 1          cpu.cfs_quota_us
        NET: my own eth0        memory.max
        MNT: my own /           io.max, pids.max
        UTS/IPC/USER/...
              |                       |
              +-----------+-----------+
                          |
                exec() the container's actual process
                (an ordinary process on the SAME host kernel)

runc exits after start. containerd-shim stays alive as the container's real parent.
```

The critical thing this diagram makes visible: namespaces and cgroups are applied to an **ordinary process** via **ordinary kernel primitives** (`clone()`, `unshare()`, `setns()`, and writes to `/sys/fs/cgroup/...`). There is no container-specific kernel object — `docker ps` shows you processes, and `ps aux` on the host shows the exact same PIDs (just not visible *from inside* the PID namespace).

---

## How it actually works

### Namespaces: the eight types, concretely

```c
// untested sketch — minimal namespace creation via clone()
#include <sched.h>
int child_fn(void *arg) {
    // inside here, getpid() returns 1 — this process is PID 1 in its OWN namespace
    execve("/bin/sh", ...);
}
char stack[1024*1024];
clone(child_fn, stack + sizeof(stack),
      CLONE_NEWPID | CLONE_NEWNET | CLONE_NEWNS | CLONE_NEWUTS |
      CLONE_NEWIPC | CLONE_NEWUSER | SIGCHLD, NULL);
```

| Namespace | Flag | Isolates | Real number/gotcha |
|---|---|---|---|
| PID | `CLONE_NEWPID` | Process ID space — first process becomes PID 1 in the new namespace | If your app is PID 1 and doesn't reap zombies (no init semantics), orphaned child processes accumulate as `<defunct>` — this is why `tini`/`dumb-init` exist as the actual PID-1 entrypoint in production images |
| Net | `CLONE_NEWNET` | Network interfaces, routing tables, ports | A fresh net namespace starts with only `lo`; connectivity requires a `veth` pair bridging to the host, which is what `docker0`/CNI plugins set up |
| Mnt | `CLONE_NEWNS` | Filesystem mount points | Combined with a `chroot`/`pivot_root` into an image layer stack (usually OverlayFS), this is what makes `/` inside a container look like a whole separate filesystem |
| UTS | `CLONE_NEWUTS` | Hostname, domain name | Lets each container have its own `hostname` independent of the host's |
| IPC | `CLONE_NEWIPC` | System V IPC objects, POSIX message queues | Prevents one container from reading another's shared memory segment via a guessed key |
| User | `CLONE_NEWUSER` | UID/GID mapping | Lets a process be UID 0 (root) *inside* the namespace while mapped to an unprivileged UID on the host — the single most important namespace for limiting the blast radius of a container escape, and per the runc security team's own guidance, not mapping host root into the container is what blocks the most severe class of escape |
| Cgroup | `CLONE_NEWCGROUP` | The view of the cgroup hierarchy itself | Prevents a container process from seeing (or being confused by) the host's full cgroup tree |
| Time | `CLONE_NEWTIME` | `CLOCK_MONOTONIC`/`CLOCK_BOOTTIME` values | Newest (kernel 5.6, 2020); lets checkpoint/restore (CRIU) migrate a container without its uptime-dependent code breaking |

### Cgroups: the actual limit mechanics

**CPU — compressible, throttled not killed.** cgroups v2 (and v1) express CPU limits as a quota over a period: `cpu.cfs_quota_us` (microseconds of CPU time allowed) over `cpu.cfs_period_us` (period length, default **100,000μs = 100ms**). A Kubernetes pod with `resources.limits.cpu: "0.5"` translates to a quota of 50,000μs per 100ms period — if the container's threads collectively burn through that in, say, the first 30ms of the period, the kernel's CFS bandwidth controller simply **stops scheduling** that cgroup's threads for the remaining 70ms, regardless of whether other cores are idle. This is the mechanical reason a service can show `container_cpu_cfs_throttled_seconds_total` climbing while host CPU utilization looks fine — the throttling is per-cgroup-period, invisible in aggregate host metrics. Production guidance treats a throttling ratio (`throttled_seconds/periods`) above roughly **25%** on a normal traffic day as a signal the limit is set too tight and is producing real latency spikes, not just theoretical inefficiency.

**Memory — incompressible, OOM-killed.** `memory.max` (v2) or `memory.limit_in_bytes` (v1) sets a hard ceiling; the instant a cgroup's charged memory crosses it, the kernel's OOM killer sends **SIGKILL** to a process in that cgroup — there is no throttling equivalent for memory because you cannot "pause" memory the way you can pause CPU scheduling; the process either fits or it's killed. This is exactly why a container shows exit code **137** (128 + SIGKILL's signal number 9) specifically, and it's a distinct signal from an application-level crash — seeing 137 repeatedly is the tell that you're looking at a resource-limit kill, not a bug in the application logic, and the fix is either raising the limit or finding the actual memory growth (leak, unbounded cache, large batch size) rather than restarting and hoping.

**pids.max and io.max** exist too and are less discussed but real: `pids.max` caps the number of processes/threads a cgroup can fork, which is the actual production defense against a fork-bomb inside one container taking down the whole host's PID table; `io.max` throttles block-device I/O bandwidth/IOPS per cgroup, the mechanism behind Kubernetes' (alpha/beta, evolving) I/O QoS features.

### The overlay filesystem — how the image layers become one `/`

Docker images are stacks of read-only layers; OverlayFS mounts them as a single merged view by stacking a `lowerdir` (the read-only image layers) under an `upperdir` (a writable layer unique to this container instance) with a `workdir` for internal bookkeeping — writes go to `upperdir`, reads fall through to the first layer (searching top-down) that has the file, and this copy-on-write behavior is why modifying a large file in a running container the first time can be visibly slower (the whole file is copied up to `upperdir` before the write proceeds) — a real, measurable "why did this one write take 200ms" surprise in databases or log files run inside unmodified base images without a volume mount.

### Docker isn't a hypervisor — the security consequence

Because every container process runs on the **same host kernel** (no separate kernel, no hypervisor-enforced hardware isolation boundary), a bug that lets a process escape its namespace/cgroup jail lands it directly in host kernel context. **CVE-2024-21626** (runc ≤1.1.11) is a concrete, recent example: an internal file descriptor leak could let a newly-spawned container process end up with its working directory in the *host's* filesystem namespace, giving a container full host filesystem access — a complete escape, not a partial information leak. **CVE-2025-31133** (disclosed November 2025) is a related class: replacing `/dev/null` with a symlink during container initialization to redirect a privileged operation. Both are patched, but they illustrate the structural point: a container escape is a kernel-level compromise, whereas a VM escape (rare, but when it happens) still has to cross a hypervisor boundary most attackers never reach. This is the concrete reason gVisor/Kata exist for genuinely untrusted multi-tenant workloads.

---

## Build it from scratch

The mechanically honest version of "build a container" is composing `unshare`, `chroot`, and a cgroup directory by hand — this is small enough to actually run and prove the model, and a fuller shell-script version belongs in `(lab pending)`:

```bash
# untested sketch — a "container" in ~15 lines, Linux only, run as root
mkdir -p /tmp/mycontainer/{bin,lib,lib64,proc}
cp /bin/busybox /tmp/mycontainer/bin/          # a real minimal rootfs needs libs too

# cgroup v2: cap this process tree at 50MB memory, 50% of one core
mkdir /sys/fs/cgroup/mycontainer
echo 50000000 > /sys/fs/cgroup/mycontainer/memory.max
echo "50000 100000" > /sys/fs/cgroup/mycontainer/cpu.max   # quota period, both us
echo $$ > /sys/fs/cgroup/mycontainer/cgroup.procs            # put THIS shell in it

# namespaces: new PID, mount, UTS, IPC namespace; pivot root into the rootfs
unshare --pid --mount --uts --ipc --fork --mount-proc \
  chroot /tmp/mycontainer /bin/busybox sh
# inside: `ps` only sees this namespace's processes; `hostname somename` doesn't
# touch the host; and the cgroup limits from above still apply because cgroups
# were set on the process BEFORE unshare, and children inherit cgroup membership
```

This intentionally skips network namespacing (needs a `veth` pair + bridge setup, more moving parts) and a real multi-layer rootfs (needs OverlayFS mounts), but the core claim — "a container is `clone`/`unshare` plus cgroup writes plus a `chroot`" — is fully demonstrated and runnable.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Container repeatedly exits with code 137, no application error logged | `memory.max` exceeded, kernel OOM-killed the process with SIGKILL — memory is incompressible, there's no throttling equivalent | Find the actual memory growth (leak, unbounded cache, oversized batch/buffer) via `kubectl top`/heap profiling rather than just raising the limit; raise the limit only after confirming the workload's real requirement |
| Service p99 latency spikes even though `top`/host CPU usage looks fine | `cpu.cfs_quota_us` throttling — the container burns its quota early in a 100ms period and is stopped for the remainder, invisible in host-aggregate CPU metrics | Monitor `container_cpu_cfs_throttled_seconds_total / container_cpu_cfs_periods_total`; a ratio above ~25% on normal traffic means the CPU limit is too tight for real burstiness, raise it or remove the limit if requests dominate scheduling anyway |
| Zombie (`<defunct>`) processes accumulate inside a container over time | The container's PID 1 (often the application itself) doesn't implement init semantics (reaping orphaned children via `wait()`) | Use a minimal init process (`tini`, `dumb-init`) as the actual entrypoint, with the real application as its child |
| First write to a large file inside a running container is unexpectedly slow | OverlayFS copy-up: modifying a file that only exists in a read-only lower layer copies the entire file into the writable upper layer before the write proceeds | Mount a volume for write-heavy paths (databases, logs) instead of writing into the image's layered filesystem |
| A process escapes its container and reads/writes host files | A runc/kernel vulnerability (e.g. CVE-2024-21626 fd leak, CVE-2025-31133 symlink swap) bypassing the namespace boundary | Patch runc/containerd promptly; run containers with user namespaces enabled and host root NOT mapped into the container (blocks the most severe escape class); for genuinely untrusted workloads use a stronger isolation boundary (gVisor, Kata) instead of relying on namespaces alone |
| `top` inside a container shows the host's full memory/CPU count, confusing capacity planning | Many tools reading `/proc/meminfo`/`/proc/cpuinfo` are not cgroup-aware by default and report host-wide values regardless of the container's actual cgroup limit | Use cgroup-aware tooling, or explicitly configure JVM/runtime heap sizing (many modern JVMs/runtimes now detect cgroup limits automatically) rather than trusting `/proc` inside the container |

---

## Tradeoffs & when NOT to use it

- **Don't treat containers as a security boundary for genuinely untrusted, multi-tenant code.** Shared-kernel isolation means a kernel bug in namespaces/cgroups is a full host compromise, not a contained failure — CVE-2024-21626 and CVE-2025-31133 are recent, real examples, not hypothetical. For running arbitrary customer-submitted code (serverless platforms, CI runners executing untrusted pipelines), a stronger boundary (gVisor, Kata Containers, or a real VM) is the defensible choice.
- **Don't set memory limits without first understanding the workload's actual peak usage.** A limit set from a guess, not measurement, produces either silent OOM-kills under normal load spikes (limit too tight) or no protection at all (limit too loose) — profile first.
- **Don't rely on CPU limits (`cfs_quota_us`) for latency-sensitive services without watching the throttling ratio.** A "correctly sized" limit based on average usage can still throttle hard during legitimate bursts, producing exactly the tail-latency spikes the limit was meant to prevent elsewhere; sometimes CPU *requests* (scheduling priority) without a hard *limit* is the better choice for bursty, latency-sensitive workloads.
- **Don't run your application as PID 1 without an init process if it forks children** — the zombie-reaping problem is real and slow-building, not an immediate failure, which makes it easy to ship and only notice under sustained load.
- **Don't assume cgroup v1 and v2 are interchangeable in tooling/config** — the hierarchy model and some controller interfaces genuinely differ (v1's separate per-controller hierarchies vs v2's unified hierarchy), and older monitoring/orchestration assumptions can silently misreport or misapply limits on a v2 host if not updated.

---

## Interview questions

### Q1 — What is a container, mechanically? No product names.
**Testing:** whether the candidate can strip away Docker/Kubernetes branding and describe the actual kernel primitives.
**Answer:** An ordinary Linux process created with `clone()`/`unshare()` using namespace flags (PID, net, mnt, uts, ipc, user, cgroup, time) that change what the process can *see*, combined with cgroup control-file writes that limit what it can *use* (CPU, memory, I/O, process count). There is no container-specific kernel object — it's process isolation plus resource limiting, both built from pre-existing, independently usable kernel mechanisms.
**Follow-up trap:** *"Is a container a lightweight VM?"* — no, and saying so is a red flag; a VM has its own kernel and a hypervisor-enforced hardware boundary, a container shares the host kernel entirely, which is the direct reason container escapes are more severe than VM escapes.

### Q2 — Namespaces vs cgroups — what's the actual division of responsibility?
**Testing:** the most common point of confusion, tested directly.
**Answer:** Namespaces provide visibility isolation — what a process can see (its own PID tree, its own network stack, its own mount table). Cgroups provide resource isolation — hard limits on what a process can consume (CPU quota, memory ceiling, process count, I/O bandwidth). They're independent kernel subsystems; a process can have namespace isolation with no cgroup limits at all, or vice versa.
**Follow-up trap:** *"If I only apply namespaces and no cgroups, can one 'container' still take down the host?"* — yes, trivially — an unlimited fork bomb or a runaway memory allocation inside a namespaced-only process has zero resource ceiling and can exhaust the host's actual physical resources, since namespaces never limit *quantity*, only *visibility*.

### Q3 — A container keeps exiting with code 137. Diagnose it.
**Testing:** recognizing the OOM-kill signature and reasoning about the fix.
**Answer:** 137 = 128 + 9 (SIGKILL), which is the kernel OOM killer's signature when a cgroup's `memory.max` is exceeded — memory is incompressible so there's no throttling equivalent, the process is killed outright the instant it crosses the ceiling. Diagnosis: check actual memory usage trend (heap profiling, `kubectl top`) against the configured limit rather than assuming the application crashed on its own.
**Follow-up trap:** *"Would raising the memory limit be the right first fix?"* — only after confirming the workload's genuine requirement; raising the limit without investigating can mask a real leak or an unbounded cache/batch size that will eventually exceed any limit you set.

### Q4 — Explain why CPU limits throttle but memory limits kill.
**Testing:** the compressible-vs-incompressible resource distinction, a frequently underexplained mechanical fact.
**Answer:** CPU time is compressible — the kernel can simply stop scheduling a cgroup's threads for the remainder of a period (`cpu.cfs_quota_us` over `cpu.cfs_period_us`, default period 100ms) and resume them next period with no data loss, just delay. Memory is incompressible — there's no way to "pause" a process's already-allocated memory without either swapping (which cgroups' memory controller doesn't do as a throttle mechanism) or killing it, so crossing `memory.max` triggers the OOM killer's SIGKILL immediately.
**Follow-up trap:** *"Why does a service look fine on host-level CPU dashboards but show p99 latency spikes?"* — CPU throttling happens per-cgroup-period and is invisible in host-aggregate CPU utilization graphs; you have to look at `container_cpu_cfs_throttled_seconds_total` specifically, and a throttled-ratio above roughly 25% on normal traffic is the practical threshold indicating the limit is actively hurting latency.

### Q5 — Walk through the actual process chain from `docker run` to a running container.
**Testing:** whether the multi-daemon architecture is understood, not just "Docker starts it."
**Answer:** `docker` CLI talks to `dockerd`, which delegates lifecycle management (pull image, start/stop, snapshotting) to `containerd`, which spawns a `containerd-shim` process per container — the shim holds the container's stdio and survives even if `containerd` itself restarts, which is why `containerd` restarting doesn't kill running containers. The shim invokes `runc`, the OCI runtime, which does the actual `clone()`/`unshare()` namespace creation and cgroup filesystem writes, execs into the container's process, and then exits — the shim remains as the real parent process reporting exit status back up.
**Follow-up trap:** *"Why does runc exit instead of staying resident as the container's parent?"* — so that upgrading or restarting a long-running daemon (containerd, dockerd) doesn't require killing every running container; the shim's whole purpose is decoupling container lifetime from any single long-lived daemon process.

### Q6 — What's the security significance of the user namespace specifically?
**Testing:** whether the candidate can name the single namespace most relevant to escape severity.
**Answer:** The user namespace maps UIDs/GIDs between the namespace and the host, letting a process be UID 0 (root) *inside* the container while being mapped to an unprivileged, non-zero UID on the host. This means that even if a process somehow escapes its other namespace boundaries, it doesn't automatically have host root privileges — per runc's own security guidance, not mapping host root into the container's namespace blocks the most severe class of container escape.
**Follow-up trap:** *"So is `docker run` safe from escapes by default with user namespaces?"* — user namespaces significantly reduce blast radius but many production Docker/Kubernetes setups historically ran containers *without* user namespace remapping enabled by default (for compatibility reasons), so it's an available, recommended mitigation, not something you can assume is on without checking your runtime's configuration.

### Q7 — Explain OverlayFS's layer model and name a real performance surprise it causes.
**Testing:** filesystem-layer mechanics beyond "images have layers."
**Answer:** OverlayFS stacks read-only image layers (`lowerdir`) under a per-container writable layer (`upperdir`), with a `workdir` for internal bookkeeping; reads search top-down through the stack for the first layer containing the file, writes go to `upperdir`. The surprise: modifying a file that currently only exists in a lower (read-only) layer triggers a full copy-up of that entire file into `upperdir` before the write proceeds — so the first write to a large file inside an unmodified base image can be measurably slower than subsequent writes to the same file.
**Follow-up trap:** *"How would you avoid that copy-up cost for a write-heavy path like a database data directory?"* — mount an explicit volume for that path instead of letting it live in the image's layered filesystem; a volume bypasses OverlayFS entirely for that mount point.

### Q8 — Why is a container escape considered more severe than a typical VM escape?
**Testing:** the shared-kernel security model, with a concrete recent CVE.
**Answer:** A container shares the host kernel with no hypervisor boundary in between, so a namespace/cgroup escape lands the attacker directly in host kernel context with no further boundary to cross. CVE-2024-21626 (runc ≤1.1.11) is a concrete example: an internal file descriptor leak let a newly-spawned container process end up with its working directory in the host filesystem namespace, giving full host filesystem access. A VM escape, by contrast, still has to defeat the hypervisor's hardware-enforced isolation, which is a structurally harder and rarer class of bug.
**Follow-up trap:** *"Does that mean containers should never run untrusted code?"* — for genuinely untrusted, multi-tenant workloads (arbitrary customer code, CI pipelines), the honest answer is to add a stronger isolation layer on top (gVisor's syscall-interception userspace kernel, or Kata's lightweight-VM boundary) rather than relying on namespaces/cgroups alone as the security boundary.

### Q9 — What does `pids.max` protect against, and why is it easy to forget?
**Testing:** knowledge of a less-discussed but production-real cgroup controller.
**Answer:** `pids.max` caps the number of processes/threads a cgroup can fork — it's the direct defense against a fork bomb (accidental, e.g. a buggy retry loop that spawns subprocesses, or malicious) inside one container exhausting the host's entire PID table, which without this limit would affect every other container and process on the host, not just the offending one. It's easy to forget because CPU and memory limits get most of the attention in resource-limit configuration, while process-count exhaustion is a less common but equally host-wide failure mode.
**Follow-up trap:** *"What does hitting the PID table exhaustion look like on the host if pids.max isn't set?"* — `fork()`/`clone()` calls across the *entire host*, not just the offending container, start failing with `EAGAIN`/`ENOMEM` (PID space exhausted, default Linux PID max is commonly 32768 or configured higher via `kernel.pid_max`), a host-wide outage caused by one misbehaving container.

### Q10 — cgroups v1 vs v2 — what actually changed, and is it settled?
**Testing:** whether the candidate knows this is a live operational concern, not ancient history.
**Answer:** v1 had separate, independently-mountable hierarchies per controller (CPU, memory, etc. could each have a different process-grouping tree), which allowed inconsistent groupings and was notoriously unreliable for buffered I/O accounting specifically. v2 (merged kernel 4.5, 2016) unifies everything into a single hierarchy with more consistent accounting across controllers. Most current distributions default to v2 now, but a meaningful amount of production infrastructure (older Kubernetes clusters, some monitoring tooling assuming v1's file layout) still runs or assumes v1, making "which cgroup version and driver does this cluster actually use" a real, still-current question rather than settled history.
**Follow-up trap:** *"Would you expect the same `docker stats` output on a v1 vs v2 host?"* — not necessarily identical in every accounted metric, particularly I/O — v2's more consistent buffered-I/O accounting can report differently than v1's, which has caused real confusion when comparing metrics across a fleet mid-migration from v1 to v2.

### Q11 — Design question: you're building a CI system that runs arbitrary, untrusted pipeline code from external contributors. Would you use plain Docker containers?
**Testing:** staff-level judgment applying the whole isolation-model discussion to a concrete untrusted-code scenario.
**Answer:** Plain namespace/cgroup-based containers share the host kernel, so a kernel-level container-escape bug (a real, recurring CVE class) would compromise the CI host directly, potentially exposing every other tenant's pipeline running on the same fleet. For genuinely untrusted, externally-submitted code, the defensible design adds a stronger boundary — gVisor (intercepts syscalls in userspace, smaller attack surface exposed to the real kernel) or Kata Containers (each job gets its own lightweight VM with its own guest kernel) — accepting the extra overhead (higher startup latency, more memory per job) as the cost of a meaningfully stronger isolation guarantee for this specific threat model.
**Follow-up trap:** *"What if latency/cost makes gVisor or Kata too expensive at your CI volume?"* — a defensible middle ground is aggressive least-privilege hardening of plain containers (seccomp profiles restricting syscalls, no host root mapping via user namespaces, read-only root filesystems, dropped Linux capabilities) plus fast patching discipline on the runtime — a real risk-acceptance tradeoff to name explicitly rather than pretending it's equivalent to a VM boundary.

---

## Red flags that fail you

- Calling a container "a lightweight VM."
- Conflating namespaces and cgroups, or being unable to say which one does what.
- Not knowing why memory limits kill (137/SIGKILL) while CPU limits throttle.
- Claiming Docker itself does the isolation, with no mention of `runc`/OCI or the underlying kernel primitives.
- Treating container isolation as an adequate security boundary for arbitrary untrusted code with no caveat about shared-kernel risk.
- Not knowing that `runc` exits after container startup and that a shim process is the real parent.

---

## Cheat card

```
CONTAINER = ordinary Linux process + namespaces (visibility) + cgroups (limits)
  no separate kernel, no hypervisor -- SAME host kernel as everything else

8 NAMESPACES: pid, net, mnt, uts, ipc, user, cgroup, time (newest, kernel 5.6/2020)
  PID: 1st process = PID 1 in its own tree -> must reap zombies (tini/dumb-init)
  USER: UID0-in-ns != UID0-on-host -- biggest single escape-blast-radius reducer

CGROUPS: v1 (2008, per-controller hierarchies) vs v2 (2016, kernel 4.5, unified
  hierarchy, better I/O accounting) -- migration still ongoing in prod, check which
CPU: cpu.cfs_quota_us / cpu.cfs_period_us (period default 100ms=100000us)
  compressible -> THROTTLED not killed. throttled/periods ratio >25% = limit too tight
MEMORY: memory.max, incompressible -> OOM KILLED (SIGKILL) instantly on breach
  exit code 137 = 128+9(SIGKILL) -- the OOM-kill signature, not an app crash
PIDS: pids.max -- caps forks, defends against fork bomb exhausting host PID table

DOCKER CHAIN: docker CLI -> dockerd -> containerd (lifecycle) -> containerd-shim
  (1/container, survives containerd restart, holds stdio) -> runc (OCI runtime,
  does clone()/unshare()+cgroup writes, execs, EXITS) -> kernel

OVERLAYFS: lowerdir(RO image layers) + upperdir(RW, per-container) + workdir
  write to file only in lowerdir -> full COPY-UP first (real perf surprise)

ESCAPES ARE KERNEL COMPROMISES (shared kernel, no hypervisor boundary):
  CVE-2024-21626 (runc <=1.1.11, fd leak -> host fs access)
  CVE-2025-31133 (Nov 2025, /dev/null symlink swap during init)
  untrusted multi-tenant code -> gVisor / Kata Containers, not plain containers
```

## Sources

- [namespaces(7) — Linux manual page](https://man7.org/linux/man-pages/man7/namespaces.7.html) — accessed 2026-08-03
- [Why Kubernetes Kills Pods for Memory Overuse But Not CPU — Pablo Jusue](https://medium.com/@pablojusue/why-kubernetes-kills-pods-for-memory-overuse-but-not-cpu-a-deep-dive-into-cgroups-and-resource-09d2adab225d) — accessed 2026-08-03
- [Kubernetes CPU Throttling Explained: CFS Quota, Limits, and Latency Spikes — DevOpsBeast](https://devopsbeast.com/blog/kubernetes-cpu-throttling-explained) — accessed 2026-08-03
- [CVE-2024-21626: Runc Container Escape Vulnerability — SentinelOne](https://www.sentinelone.com/vulnerability-database/cve-2024-21626/) — accessed 2026-08-03
- [Critical runC Vulnerabilities Allow Container Escape in Docker, Kubernetes — Gopher Security](https://www.gopher.security/news/critical-runc-vulnerabilities-allow-container-escape-in-docker-kubernetes) — accessed 2026-08-03
- [How to Understand Docker runc and Container Runtimes — OneUptime](https://oneuptime.com/blog/post/2026-02-08-how-to-understand-docker-runc-and-container-runtimes/view) — accessed 2026-08-03
- [Resource Management for Pods and Containers — Kubernetes docs](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
