# Debugging Containers: exec, logs, inspect, nsenter, dive, OOMKilled, Exit Codes

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.0h · **Prereqs:** T27-docker-essentials, T27-docker-mastery
> **Module id:** `T27-docker-debug` · **Tags:** docker, critical

## The 30-second version

Container debugging is reading three sources of ground truth in order: the exit code (`docker inspect -f '{{.State.ExitCode}}'`) tells you the shape of the failure, `docker inspect -f '{{.State.OOMKilled}}'` tells you specifically whether the kernel's OOM killer fired, and `docker logs` tells you what the process said before it died — none of these are optional and none substitute for each other. Exit code 137 means SIGKILL landed (almost always OOM, sometimes a manual `docker kill`); exit code 143 means SIGTERM was handled by the default handler (a graceful-shutdown timeout that ran out); exit code 1 is an unhandled application exception; exit code 126/127 mean the entrypoint itself couldn't execute (permission or not-found). `CrashLoopBackOff` (the Kubernetes-level symptom) is just this same exit-code/OOM diagnosis repeated with exponential backoff between restarts. `nsenter` and `dive` exist for when `docker exec` isn't available at all — a distroless container with no shell, or a namespace you need to inspect from the host directly.

## Why this gets asked

Because reading `CrashLoopBackOff` or exit code 137 off a dashboard and immediately guessing ("bump the memory limit," "just restart it") is the single most common on-call anti-pattern interviewers have personally cleaned up after, and they want to see the actual diagnostic sequence: read the exit code, read the OOM flag, read the logs, only then form a hypothesis.

---

## Lineage: past → present → future

**What came before.** Debugging a crashed process on a bare-metal or VM host meant `dmesg`, core dumps, and application logs written to a known filesystem path you could tail directly — the process and the host shared the same view of "what happened," because there was no isolation layer between them. Early container debugging inherited this instinct (SSH to the host, look at the process) before tooling caught up to the fact that a container's process tree, filesystem, and resource accounting are all namespaced away from the host's default view — `ps aux` on the host shows container processes with different names/paths than what's visible from inside, and a container's own `top` shows only its cgroup's resource usage, not the host's.

**Where it stands now.** `docker inspect`, `docker logs`, and `docker exec` cover the majority of debugging needs for containers that still have a shell; the discipline that separates competent from cargo-cult debugging is checking `State.ExitCode` and `State.OOMKilled` as literal, structured fields before forming any hypothesis, rather than pattern-matching on symptoms alone. The harder and increasingly common case is debugging containers that don't have a shell at all — distroless final images by design ship no `sh`, no coreutils, no package manager, which means the entire `docker exec ... sh` workflow is unavailable, and the field has converged on ephemeral debug containers (`kubectl debug --target`, `docker run --pid=container:X --network=container:X <debug-image>`) or `nsenter` from a privileged host process as the correct alternative rather than "make the production image less minimal so it's easier to debug," which reintroduces the attack surface distroless was adopted to remove.

**Where it's heading.** eBPF-based tooling (bpftrace, Pixie) is increasingly answering "what syscalls/network calls did this specific container make" without needing a shell inside the container at all, which is a genuine structural improvement over exec-based debugging for exactly the shell-less-container case — this is real and shipping, not speculative, though it requires host-level privileges and tooling most teams don't yet have wired up by default. The more speculative direction is "you never need to attach at all because continuous profiling and structured tracing already captured what you'd have needed" (covered in the prod-debugging and observability-debug modules) — real for well-instrumented services, not yet true for the median production container.

---

## Mental model

```
FAILURE INVESTIGATION ORDER (don't skip steps, don't reorder)

1. docker inspect -f '{{.State.ExitCode}}' <c>       <- WHAT KIND of failure
2. docker inspect -f '{{.State.OOMKilled}}' <c>       <- was it specifically OOM
3. docker logs --tail 200 <c>                          <- what did the process SAY before dying
4. docker inspect <c>  (full JSON)                     <- mounts, env, restart count, health history
5. (still running / flapping) docker exec -it <c> sh   <- live shell, IF one exists
6. (no shell / need host view) nsenter --target <pid> --all
7. (need to see WHY the image is shaped this way) dive <image>

EXIT CODE DECODER
  0    clean exit                      -- but check if intended (see docker-essentials Q3)
  1    unhandled exception / generic app error
  126  command found but not executable (permission bit, wrong architecture)
  127  command not found (typo'd ENTRYPOINT, missing binary in a minimal base)
  137  128+9  = SIGKILL   -- OOM killer (check OOMKilled field!) or manual `docker kill`
  139  128+11 = SIGSEGV   -- segfault, often a native extension / bad memory access
  143  128+15 = SIGTERM   -- graceful shutdown signal, handled by default handler (process didn't catch it)

CrashLoopBackOff (Kubernetes) = same exit-code/OOM diagnosis, just repeated with the kubelet's
  exponential backoff (10s, 20s, 40s ... capped at 5min) between restart attempts --
  `kubectl describe pod` shows the same ExitCode/Reason fields `docker inspect` would.
```

The fact that resolves the most confusion: exit code and OOMKilled are two separate, independently-set fields. A process can exit with code 137 for a reason that has nothing to do with memory (someone ran `docker kill` manually, which sends SIGKILL directly) — `OOMKilled: false` with `ExitCode: 137` means something else sent the kill, and jumping straight to "must be a memory leak" without checking that field first is a diagnosis built on an assumption, not evidence.

## How it actually works

**Exit codes are POSIX signal-plus-128 encoding.** When a process is terminated by signal N, the shell/container runtime reports its exit status as 128+N by convention. SIGKILL is signal 9, giving 137; SIGTERM is signal 15, giving 143; SIGSEGV is signal 11, giving 139. This is not Docker-specific — it's how POSIX shells have reported signal-terminated exit statuses for decades — which is exactly why "exit code 137" generalizes cleanly to bare processes, Kubernetes pods, and CI job runners without any container-specific magic.

**`OOMKilled`, mechanically.** Docker sets `State.OOMKilled: true` specifically when the *container's own cgroup* memory limit triggered the kernel OOM killer against a process in that cgroup — this is distinct from a host-wide OOM event (kernel killing something because the whole machine ran low on memory, which wouldn't necessarily set this per-container flag the same way, and is visible instead via `dmesg`/`journalctl -k` showing an OOM invocation with a PID that maps to a container you'd have to cross-reference manually). `dmesg | grep -i "killed process"` or `journalctl -k | grep -i oom` on the host shows the actual kernel OOM killer's log line, including the score-based victim selection (`oom_score_adj`), which is the ground truth beneath Docker's own reporting.

**`docker exec` runs a new process inside existing namespaces.** `docker exec -it <container> sh` doesn't attach to the container's existing PID 1 — it starts a brand-new process joined to that container's existing namespaces (pid, net, mnt, etc.), which is why a container with a broken/hung PID 1 can still be exec'd into (you get a fresh, working shell process sharing the same isolated view), but also why `docker exec` fails outright with "no such file or directory" if there's genuinely no shell binary anywhere in that mount namespace — distroless images have nothing for `exec` to launch, full stop.

**`nsenter`, mechanically.** `nsenter --target <pid> --mount --uts --ipc --net --pid <command>` runs `<command>` from the host, but inside the specified namespaces of the target process — this works even against a container with no shell of its own, because the command being executed (e.g., `busybox sh`, or a static binary you bring) originates from the host's filesystem, not the container's. It requires host-level access (root or `CAP_SYS_ADMIN`/`CAP_SYS_PTRACE`), which is exactly why it's a "break glass" host-admin tool, not a routine per-container debugging command.

**`dive`, mechanically.** `dive <image>` (or `dive build -t tag .` to build and inspect immediately) reads the image's layer tarballs directly and diffs each layer's filesystem against the one before it, categorizing every path as added/modified/removed and computing an "efficiency score" plus total wasted bytes — specifically bytes that were added in one layer and removed in a later one, which still physically exist in the earlier immutable layer and count against image size even though they're invisible in the final container's filesystem view. This is the tool for "why is this image 400MB" when `docker history` alone doesn't make the culprit obvious.

## Build it from scratch

```bash
# The full diagnostic sequence for a container that just died
CID=myapp_1

# 1. exit code
docker inspect -f '{{.State.ExitCode}}' $CID

# 2. was it OOM
docker inspect -f '{{.State.OOMKilled}}' $CID

# 3. what did it say
docker logs --tail 200 --timestamps $CID

# 4. full state -- mounts, restart count, health history, network
docker inspect $CID | jq '.[0].State, .[0].RestartCount, .[0].Mounts'

# 5. host-level kernel OOM confirmation, independent of Docker's own report
dmesg -T | grep -i "killed process"
journalctl -k --since "10 min ago" | grep -i oom

# 6. shell exists? try it. If not, this fails cleanly and tells you so.
docker exec -it $CID sh || echo "no shell -- container is likely distroless/scratch-based"

# 7. no shell: nsenter from the host (needs root)
PID=$(docker inspect -f '{{.State.Pid}}' $CID)
sudo nsenter --target $PID --mount --uts --ipc --net --pid -- /bin/sh
# or bring your own static busybox if the mount namespace itself has nothing:
sudo nsenter --target $PID --net --pid -- busybox sh

# 8. why is the image this size / what's in this layer
dive myapp:latest
dive build -t myapp:latest .   # build + inspect in one step, CI mode: dive build -t x . --ci
```

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Exit code 137, `OOMKilled: true` | Process exceeded the container's cgroup memory limit | Profile actual memory usage (heap dump/`py-spy`/language-specific profiler — see prod-debugging module) before blindly raising the limit; a raised limit without understanding the growth pattern just delays the same crash |
| Exit code 137, `OOMKilled: false` | Something sent SIGKILL directly — manual `docker kill`, an orchestrator's liveness probe giving up and force-killing, or a host-wide OOM (not this cgroup specifically) | Check orchestrator events/liveness probe logs and host-wide `dmesg`/`journalctl -k` for a host OOM event separate from this container's own cgroup |
| Exit code 143 repeatedly on every deploy | Graceful shutdown handler exists but takes longer than the stop grace period, so SIGTERM's default handler (immediate termination) fires because the app never actually caught and acted on the signal in time, or never installed a handler at all | Confirm the app installs a `SIGTERM` handler and completes shutdown within the grace period; extend `docker stop -t`/orchestrator's grace period if genuine in-flight work needs more time |
| `CrashLoopBackOff` with increasing backoff intervals | Same exit-code/OOM diagnosis as a plain Docker container, repeated by the kubelet with exponential backoff (10s→20s→40s...capped ~5min) | `kubectl logs --previous` to see the last crashed instance's output (current logs may be from a fresh, still-starting restart); `kubectl describe pod` for the same ExitCode/Reason Docker would show |
| `docker exec -it <c> sh` returns "OCI runtime exec failed: exec: sh: no such file or directory" | Distroless/scratch-based image, no shell exists by design | `nsenter` from the host, or an ephemeral debug sidecar sharing the target's namespaces |
| `dive` reports a large "wasted space" percentage | Files added in one layer and deleted in a later layer — the delete only masks them, doesn't reclaim the earlier layer's space | Restructure the Dockerfile so temporary/build-only files never enter a layer that ships (use a multi-stage builder stage instead of "add then remove" in the same final stage) |
| Container flaps `unhealthy`→`healthy` repeatedly under load, but never actually crashes | Healthcheck timeout too aggressive for the app under real load (the app is fine, just briefly slower than the healthcheck's `timeout`), not the same failure as an actual crash | Distinguish this from a real crash by checking exit code (none — the container never actually restarted) versus health status; loosen `timeout`/`retries` if the app's real latency under load legitimately exceeds them, rather than treating it as a crash to "fix" the app for |

## Tradeoffs & when NOT to use it

- **Don't jump to `nsenter` before trying `docker exec`.** It requires host-level privileges most engineers shouldn't have routinely and is meaningfully more invasive; it's the right tool specifically when there's no shell to exec into, not a default first move.
- **Don't raise a memory limit as the first response to an OOMKilled container.** Without first checking whether it's a genuine leak (unbounded growth that would eventually exceed any limit) versus a legitimate but underestimated peak (a batch job's one-time working set), a higher limit either masks a real bug until it's bigger, or is the correct fix — you can't tell which without actually looking at a memory profile over time.
- **Don't treat `dive`'s wasted-space score as the only size lever.** A image can have a 0% waste score and still be huge simply because its actual dependencies are large (a full ML stack); `dive` finds *avoidable* waste from layer construction mistakes, not an inherent ceiling on how small an image with genuinely heavy dependencies can get.
- **`docker logs` only ever shows stdout/stderr captured by Docker's logging driver** — an application that logs to a file inside the container instead will show nothing here regardless of how thoroughly it's actually logging; this isn't a Docker limitation to fix, it's a signal the application's logging configuration is wrong for a containerized environment.

---

## Interview questions

### Q1 — A container exits with code 137. What's your exact next command, and why that one specifically?
**Testing:** whether the candidate reaches for evidence or a guess.
**Answer:** `docker inspect -f '{{.State.OOMKilled}}' <container>` — 137 means SIGKILL landed, but SIGKILL has more than one possible sender (OOM killer, manual `docker kill`, an orchestrator force-kill), and this field is the one piece of evidence that directly discriminates the most common cause (OOM) from the others without guessing.
**Follow-up trap:** *"`OOMKilled` reports `false`. What are your next two hypotheses, and how do you distinguish them?"* — a manual/orchestrator-issued `docker kill`/force-termination (check orchestrator events, deployment logs, whether a human ran a stop command around that timestamp) versus a host-wide OOM event that killed this process without necessarily tripping this container's own cgroup-specific flag (check `dmesg`/`journalctl -k` on the host for an OOM invocation around the same timestamp, independent of what Docker itself reports).

### Q2 — Explain exit codes 137, 143, and 139 from first principles, not memorization.
**Answer:** POSIX convention reports a signal-terminated process's exit status as 128 + signal number. SIGKILL is signal 9 → 137; SIGTERM is signal 15 → 143; SIGSEGV is signal 11 → 139. This isn't Docker-specific encoding — it's the same convention bash, Kubernetes, and CI runners all report, which is why the same three numbers show up identically across every layer of the stack.
**Follow-up trap:** *"You see exit code 143 on every single deploy, consistently. Is that necessarily a bug?"* — not automatically; 143 means the process received SIGTERM and its handling resulted in termination, which is the *expected* outcome of a graceful shutdown if the app's SIGTERM handler completes its cleanup and then exits — the actual question is whether it exited within the grace period and actually completed graceful shutdown work, not whether 143 appeared at all.

### Q3 — Why does `docker exec -it container sh` still work even if the container's main process (PID 1) is completely hung?
**Answer:** `docker exec` doesn't attach to or depend on the existing PID 1 process at all — it starts a brand-new process joined to the container's existing namespaces (pid, net, mnt, etc.), so a hung or unresponsive main process doesn't block a fresh exec'd shell from starting and running normally within the same isolated environment.
**Follow-up trap:** *"Given that, why does `docker exec` fail with 'no such file or directory' on some containers even though the container is clearly running fine?"* — the exec'd command (`sh` by default) genuinely doesn't exist anywhere in that container's mount namespace — distroless/scratch-based images ship no shell binary at all, so there's nothing for exec to launch regardless of how healthy the main process is.

### Q4 — You need to debug a running distroless container with no shell. Walk through two different valid approaches.
**Answer:** (1) `nsenter --target <pid> --mount --net --pid -- <command>` from the host (requires root/`CAP_SYS_PTRACE`), running a command that originates from the host's own filesystem — a static busybox, for instance — inside the target's namespaces. (2) An ephemeral debug container sharing the target's namespaces via the orchestrator or Docker directly: `docker run --pid=container:<target> --network=container:<target> busybox sh`, or `kubectl debug -it <pod> --image=busybox --target=<container>` in Kubernetes, which is the more common production-grade approach since it doesn't require direct host shell access.
**Follow-up trap:** *"Your `nsenter --pid --net` session can see the target's processes and network but can't read its open files. What's missing, and what's the fix?"* — the mount namespace wasn't included; add `--mount` to `nsenter`'s namespace list (or share it in the sidecar approach) to see the target's actual filesystem view including files under `/proc/<pid>/fd` or the target's own root filesystem, since PID/net namespace sharing alone doesn't grant filesystem visibility.

### Q5 — What does `dive` actually measure, and what real Dockerfile mistake does a high "wasted space" score usually indicate?
**Answer:** `dive` reads each layer's filesystem diff directly and flags files added in one layer and later deleted or modified in a subsequent layer — because layers are immutable and additive, the deleted/original version still physically exists in the earlier layer and counts toward total image size even though it's invisible in the final merged view. A high wasted-space score usually means a single-stage Dockerfile did "install build tools, compile, then `rm -rf` the build tools" all within the same stage, rather than isolating the build tools in a separate `builder` stage that's discarded entirely.
**Follow-up trap:** *"After fixing the Dockerfile to properly multi-stage, `dive`'s waste score drops to near zero but the image is still 500MB. What does that tell you, and what do you check next?"* — the remaining size isn't avoidable layering waste; it's the actual footprint of what's shipped (real dependencies, real application code) — the next check is `docker history` sorted by layer size to identify which specific dependency or asset dominates, not further layer restructuring, since `dive`'s waste metric has already confirmed there's nothing structurally wasteful left to fix.

### Q6 — A Kubernetes pod shows `CrashLoopBackOff`. Relate this precisely to what you'd see with plain Docker.
**Answer:** It's the identical underlying diagnosis — a container repeatedly exiting, characterized by the same exit code and OOM-or-not distinction Docker exposes — except the kubelet is the one restarting it, applying exponential backoff between attempts (starting around 10s, doubling up to a cap around 5 minutes) rather than restarting immediately, specifically to avoid hammering a genuinely broken workload in a tight loop.
**Follow-up trap:** *"`kubectl logs <pod>` shows nothing useful — just started, no errors yet. What command actually shows you the crash you care about?"* — `kubectl logs <pod> --previous`, which shows the logs from the last terminated instance rather than the current, freshly-restarted (and possibly not-yet-failed-again) one; plain `kubectl logs` without `--previous` is reading the wrong instance's output entirely if the pod just restarted moments ago.

### Q7 — A container's health status flaps between `healthy` and `unhealthy` under load, but `docker inspect` shows it was never actually restarted. Is this the same class of problem as an OOM kill?
**Answer:** No — a health status flap without an actual container restart means the healthcheck command itself is timing out or failing intermittently (often because the app is genuinely just slower under real load than the healthcheck's `timeout` allows), not that the process crashed or was killed. It's purely a healthcheck configuration/tuning problem, distinguishable from a real crash by the fact that `RestartCount` and `ExitCode` show no actual termination event at all.
**Follow-up trap:** *"Your orchestrator uses this health status to decide whether to route traffic to the container. What's the actual production consequence of ignoring this distinction?"* — if the orchestrator treats `unhealthy` (from a flapping healthcheck) the same as a real crash and stops routing traffic or restarts the container anyway, you can induce a self-inflicted outage on a container that was actually fine — the fix is loosening the healthcheck's `timeout`/`retries` to match real observed latency under load, not restarting a healthy process because its healthcheck was miscalibrated.

### Q8 — Why is `docker logs` sometimes completely empty even for a container you're certain is actively producing output?
**Answer:** `docker logs` only captures what the container's main process writes to stdout/stderr, as collected by Docker's configured logging driver — an application configured to log to a file inside the container (a common default for frameworks with their own file-based logging) produces output invisible to `docker logs` regardless of volume or frequency, because Docker was never watching that file descriptor.
**Follow-up trap:** *"You confirm the app does log to a file inside the container, not stdout. What are your two options to actually see those logs with standard Docker tooling, without changing the app's logging config?"* — `docker exec` in (if a shell exists) and `tail -f` the file directly inside the container, or `docker cp` the log file out to inspect it after the fact; neither requires modifying the application, though the durable fix for anything running long-term is still reconfiguring the app to log to stdout/stderr so `docker logs` and any downstream log aggregation actually captures it.

### Q9 — Exit code 126 versus 127 — what's the practical difference, and what's your first check for each?
**Answer:** 126 means the command was found but could not be executed — most commonly a missing execute permission bit on the binary/script, or an architecture mismatch (an `amd64` binary in an `arm64` container). 127 means the command wasn't found at all in the container's `PATH`/filesystem — a typo'd `ENTRYPOINT`/`CMD`, or a binary genuinely absent from a minimal base image that the Dockerfile assumed would be present. First check for 126: `docker run --entrypoint sh <image> -c 'ls -la /path/to/binary; file /path/to/binary'` to confirm permissions and architecture. First check for 127: confirm the exact `ENTRYPOINT`/`CMD` string against what actually exists in the image via `docker run --entrypoint sh <image> -c 'which <command>'` or an equivalent path check.
**Follow-up trap:** *"You switch a working image's base from Debian to Alpine and immediately get exit code 127 on a command that definitely worked before. Why?"* — Alpine's minimal base often lacks binaries or shell built-ins (like `bash` itself — Alpine ships `ash`/`sh` via BusyBox, not `bash`, by default) that a Debian-based image had installed or available implicitly; the entrypoint script likely assumed `bash`-specific syntax or a binary that simply isn't part of Alpine's default package set.

### Q10 — Walk through diagnosing "the image is 600MB and I don't know why" using the tools in this module.
**Answer:** `docker history <image>` first for a quick per-instruction size breakdown — often enough to spot an obviously oversized `RUN apt-get install` or `COPY` layer immediately. If the culprit isn't obvious (e.g., size is spread across many layers, or hidden by files added-then-removed across layers), `dive <image>` for the layer-by-layer filesystem diff and wasted-space analysis, which specifically catches the "added in one layer, deleted in a later one" pattern `docker history`'s size-per-layer view can't reveal on its own.
**Follow-up trap:** *"`dive` shows 0% wasted space but the image is still 600MB. The team wants it smaller. What's the actual remaining lever, and what's NOT the lever?"* — the remaining size is genuine dependency/application footprint (not layering waste), so the lever is reducing actual dependencies (pruning unused packages, choosing a lighter alternative library, moving to distroless if not already there) or accepting the size as a real reflection of what the application needs — restructuring the Dockerfile further is not the lever once `dive` confirms there's no structural waste left.

---

## Red flags that fail you

- Proposing "just restart it" or "bump the memory limit" as a first response without checking exit code and `OOMKilled` first.
- Not knowing exit codes are POSIX signal+128 encoding, and treating 137/143/139 as arbitrary Docker-specific magic numbers to memorize instead of derive.
- Believing `docker exec` requires the container's main process to be healthy or responsive.
- Not knowing distroless/scratch images have no shell, and proposing `docker exec ... sh` as a debugging step for one anyway.
- Confusing a flapping healthcheck (no actual restart) with a real crash/OOM event.
- Assuming `docker logs` shows everything the application logs, regardless of where the app is actually writing.

## Cheat card

```
ORDER: ExitCode -> OOMKilled -> logs --tail 200 -> full inspect -> exec (if shell) -> nsenter (if not) -> dive

EXIT CODES (128 + signal number, POSIX convention, not Docker-specific)
  0    clean exit (verify intended)         126  found, not executable (perms/arch)
  1    unhandled app error                  127  not found (typo, missing binary, wrong base)
  137  =128+9  SIGKILL  -- check OOMKilled! (OOM killer OR manual kill OR orchestrator force-kill)
  139  =128+11 SIGSEGV -- native crash/bad memory access
  143  =128+15 SIGTERM -- graceful shutdown signal; check it finished WITHIN the grace period

docker inspect -f '{{.State.ExitCode}}' <c>
docker inspect -f '{{.State.OOMKilled}}' <c>
docker logs --tail 200 --timestamps <c>
dmesg -T | grep -i "killed process"        journalctl -k --since "10 min ago" | grep -i oom

docker exec -it <c> sh                      -- NEW process joined to existing namespaces, PID1 needn't be alive
  fails "no such file" -> no shell exists (distroless/scratch) -> use nsenter or a debug sidecar instead

nsenter --target <pid> --mount --net --pid --uts --ipc -- sh   (needs root/CAP_SYS_PTRACE)
docker run --pid=container:X --network=container:X busybox sh  (sidecar approach, no host root needed)
kubectl debug -it <pod> --image=busybox --target=<container>   (k8s equivalent)

dive <image>  /  dive build -t x . --ci     -- wasted space = added-then-deleted-across-layers,
  layers are immutable, deletion just hides it, doesn't reclaim it

CrashLoopBackOff = same exit-code/OOM diagnosis, kubelet backoff 10s->20s->40s...capped ~5min
  kubectl logs --previous   -- last CRASHED instance, not the fresh restart's still-empty logs
```

## Sources

- [Fix Docker Exit Code 137 (OOMKilled): Why It Happens and How to Stop It — DEV Community](https://dev.to/jjoyneriv/fix-docker-exit-code-137-oomkilled-why-it-happens-and-how-to-stop-it-4ipf) — accessed 2026-07-26
- [How to Fix OOMKilled Kubernetes Error (Exit Code 137) — Komodor](https://komodor.com/learn/how-to-fix-oomkilled-exit-code-137/) — accessed 2026-07-26
- [Docker exiting with code 137 but OOMkilled is false — Docker Community Forums](https://forums.docker.com/t/docker-exiting-with-code-137-but-oomkilled-is-false/137273) — accessed 2026-07-26
- [dive — A tool for exploring each layer in a docker image (GitHub)](https://github.com/wagoodman/dive) — accessed 2026-07-26
- [How to Use Dive to Explore Docker Image Layers — OneUptime](https://oneuptime.com/blog/post/2026-02-08-how-to-use-dive-to-explore-docker-image-layers/view) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
