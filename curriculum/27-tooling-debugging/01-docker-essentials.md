# Docker Essentials: Images, Layers, Volumes, Networks — Every Command

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.5h · **Prereqs:** none
> **Module id:** `T27-docker-essentials` · **Tags:** docker, critical

## The 30-second version

An image is a read-only stack of layers plus metadata (entrypoint, env, exposed ports); a container is a writable layer on top of an image plus a set of namespaces and cgroups that make it look like an isolated machine. Layers are content-addressed and cached by instruction plus the state of everything above it, which is why instruction order in a Dockerfile is a performance decision, not a style one. A volume is storage that outlives the container and is managed by the Docker daemon (`/var/lib/docker/volumes/...`); a bind mount is a path from the host filesystem injected straight into the container, useful for local dev, wrong for anything you want portable. Networking defaults to a bridge per Compose project with automatic DNS between service names; `host` and `none` exist for the cases where you need to skip the abstraction entirely. Everything else — `exec`, `logs`, `inspect`, `cp`, `stats` — is instrumentation for that same small mental model.

## Why this gets asked

Because "I've used Docker for years" and "I understand what a container actually is" are different claims, and interviewers have watched engineers debug a container issue for an hour by guessing (`docker restart`, "just rebuild it") instead of reasoning from the layer/namespace model. They want to know if you'll reach for `docker inspect` and read the actual state, or cargo-cult a fix.

---

## Lineage: past → present → future

**What came before.** Before containers, isolation meant full virtual machines (Xen, VMware, KVM) — each with its own kernel, booting in tens of seconds to minutes and costing hundreds of MB to GB of RAM per instance just for the guest OS. The pain: "works on my machine" was endemic because a VM image was too heavy to rebuild on every commit, so most teams shipped code onto long-lived, hand-configured VMs that drifted from each other and from the developer's laptop. Solaris Zones (2004) and FreeBSD jails (2000) had already proven OS-level virtualization was viable, and Linux control groups (cgroups, merged into the kernel in 2007-2008 by Google engineers) plus namespaces gave Linux the primitives, but nobody had packaged them for application developers. LXC (2008) exposed those primitives directly but still required real systems knowledge to drive.

**Where it stands now.** Docker (2013) won not on isolation technology — it used the same namespaces/cgroups LXC did — but on developer experience: a Dockerfile, a registry, and a single `docker run` turned "here's a VM image, good luck" into "here's an image tag, it runs the same everywhere." The runtime itself has since been decomposed and standardized: `containerd` and `runc` (OCI-compliant) now sit underneath Docker, Kubernetes, and podman alike, so the image format is the actual portable artifact, not "Docker" as a monolith. Docker Engine reached v29 in 2026, with containerd's own image store now the default for new installs and the minimum supported API bumped to 1.44, reflecting the ecosystem's consolidation around containerd rather than Docker's original graphdriver storage. The live disagreement is daemon architecture: Docker's dockerd is a long-running root daemon, which is precisely what podman's daemonless, rootless-by-default model exists to avoid, and enterprises with strict security postures increasingly run podman or containerd directly in production while keeping Docker Desktop for local dev because the ergonomics still win there.
[Docker Engine v29 Release](https://www.docker.com/blog/docker-engine-version-29/) — accessed 2026-07-26

**Where it's heading.** WebAssembly (via runwasi/wasmtime shims on containerd) is a real, shipping alternative for a narrowing slice of workloads — sub-millisecond cold starts and no OS to boot at all — but it's additive, not a replacement, since most real services still need a filesystem, sockets, and syscalls Wasm's sandbox doesn't expose. gVisor and Kata Containers (VM-strength isolation with container ergonomics) are seeing real adoption in multi-tenant platforms (Cloud Run, Fargate under the hood) specifically because a shared-kernel container is not a hard security boundary against a kernel exploit — this is confidently true and already deployed, not speculative. What's more speculative is how far "no Dockerfile at all" tooling (buildpacks, ko for Go, Nixpacks) displaces hand-written Dockerfiles for application images; it's real for simple cases today, but Dockerfiles remain the fallback the moment you need anything non-standard, and that's likely to stay true for years.

---

## Mental model

```
IMAGE (read-only, content-addressed layers + config JSON)
  layer 4: COPY . .              <-- changes on every code edit
  layer 3: RUN pip install -r requirements.txt   <-- changes when deps change
  layer 2: COPY requirements.txt .
  layer 1: FROM python:3.12-slim  <-- rarely changes
  -----------------------------------------------------
CONTAINER = image + one thin writable layer + namespaces + cgroups
  writable layer: anything the process writes at runtime (deleted with the container
  unless it's a volume or bind mount)
  namespaces: pid, net, mnt, uts, ipc, user  -- "what this process can SEE"
  cgroups: cpu, memory, io                    -- "what this process can USE, and how much"

VOLUME  = named storage Docker manages, lives in /var/lib/docker/volumes/<name>/_data
          survives `docker rm`, portable via `docker volume` commands, backend-agnostic
BIND MOUNT = host path injected directly, e.g. -v /home/user/code:/app
          fastest for local dev (edit on host, see it live in container), but ties
          you to that exact host path -- not portable, not what you want in prod

NETWORK (bridge, the default for user-defined networks)
  each container gets a veth pair into a virtual bridge on the host; containers on the
  same user-defined bridge network resolve each other by container/service name via
  Docker's embedded DNS (127.0.0.11 inside the container) -- this is why "connection
  refused to db" in Compose is almost never a DNS problem and almost always "db isn't
  listening yet" or "wrong port."
```

The single fact that resolves most confusion: a layer is immutable once built. `RUN rm -rf /tmp/big-file` in a later layer does not shrink the image — the file still exists in the earlier layer and is just hidden by a whiteout marker in the layer above it. This is exactly what `dive` measures as "wasted space."

## How it actually works

**Layers and the build cache.** Each Dockerfile instruction produces one layer, keyed by a hash of the instruction plus its inputs. Docker walks the Dockerfile top to bottom; the first instruction whose cache key doesn't match invalidates every layer after it, forcing a rebuild from that point down, even if instruction 8 out of 10 was the only real change. This is why `COPY requirements.txt .` followed by `RUN pip install` before `COPY . .` matters: with dependencies copied and installed first, editing application code invalidates only the final `COPY . .` layer, and the (often 30-90 second) dependency install layer stays cached. Reverse the order and every code edit reinstalls every dependency.

**Content addressing.** Each layer is stored as a compressed tarball diff, addressed by a SHA-256 digest of its content. Two images built from different Dockerfiles that happen to produce byte-identical layers (e.g., the same base image layer) share storage on disk — this is why `docker images` showing "5 images, 4.2 GB total" doesn't mean 5x the base image size; `docker system df` shows actual reclaimable space, which is almost always dramatically less than the naive per-image sum.

**Namespaces, concretely.** `pid` namespace: the containerized process sees itself as PID 1, with no visibility into host or sibling-container processes — `ps aux` inside a container shows only that container's tree, which is also why the classic "container as PID 1 must handle SIGTERM directly, since there's no init to reap zombies or forward signals" gotcha exists (fixed by `--init` or `tini`). `net` namespace: a private interface set (usually just `eth0` and `lo`), connected to the host via a veth pair into a bridge — `docker network inspect bridge` shows the actual subnet and connected containers. `mnt` namespace: a private view of the filesystem, built from the image's layers plus an overlay writable layer — this is why deleting a file inside a container doesn't touch anything on the host unless you're using a bind mount.

**cgroups, concretely.** `docker run -m 512m --cpus 1.5 myapp` sets `memory.max` (or `memory.limit_in_bytes` on cgroup v1) to 512 MiB and `cpu.max` to 150% of one core, enforced by the kernel, not by Docker userspace — a process that tries to allocate past its memory cgroup limit gets killed by the kernel's OOM killer specifically for that cgroup, independent of host memory pressure. `docker stats` reads these cgroup counters directly (`CONTAINER_ID/memory.current`, `.../cpu.stat`), so a container showing `512MiB / 512MiB` in `docker stats` right before it disappears is the OOM kill, not a coincidence.

## Build it from scratch

The useful "from scratch" here is not reimplementing Docker but knowing the exact commands cold, since that's what gets tested:

```bash
# Images
docker build -t myapp:1.2 .                  # -t tag, . build context (sent to daemon!)
docker build --no-cache -t myapp:1.2 .        # bust the entire cache, rarely what you want
docker build --target builder -t myapp:dev . # build only up to a named stage
docker images                                 # list local images
docker image prune -a                         # remove all unused images, not just dangling
docker history myapp:1.2                      # per-layer size and the command that created it
docker tag myapp:1.2 registry.example.com/myapp:1.2
docker push registry.example.com/myapp:1.2

# Containers
docker run -d --name web -p 8080:80 -e ENV=prod --restart unless-stopped myapp:1.2
  # -d detach, -p host:container port publish, -e env var, --restart policy
docker run --rm -it myapp:1.2 /bin/sh         # --rm cleanup on exit, -it interactive tty
docker ps                                      # running containers
docker ps -a                                   # include stopped/exited
docker stop web                                # SIGTERM, then SIGKILL after grace period (default 10s)
docker stop -t 30 web                          # extend grace period to 30s
docker rm web                                  # remove a stopped container
docker rm -f web                               # SIGKILL immediately, then remove

# Inspecting a running/stopped container
docker logs -f --tail 200 web                  # follow, last 200 lines
docker exec -it web /bin/sh                    # shell into a RUNNING container
docker inspect web                              # full JSON: mounts, network, env, state, exit code
docker inspect -f '{{.State.OOMKilled}} {{.State.ExitCode}}' web   # targeted field
docker cp web:/app/output.log ./output.log      # copy a file OUT of a container
docker stats web                                # live CPU/mem/net/io, reads cgroup counters
docker top web                                  # processes inside the container, from the host

# Volumes and mounts
docker volume create mydata
docker run -v mydata:/data myapp                # named volume, Docker-managed
docker run -v /host/path:/data myapp            # bind mount, host path injected directly
docker run --mount type=bind,src=/host/path,dst=/data,readonly myapp  # explicit, preferred in scripts
docker volume ls / docker volume inspect mydata / docker volume prune

# Networks
docker network create mynet                    # user-defined bridge, gets embedded DNS
docker network ls
docker network inspect mynet                    # subnet, connected containers, their IPs
docker run --network mynet --name db postgres
docker run --network mynet myapp                # can resolve "db" by name, same network only
docker run --network host myapp                 # no network namespace isolation at all
docker run --network none myapp                 # no network access whatsoever

# Cleanup
docker system df                                 # actual disk usage/reclaimable, by category
docker system prune                              # stopped containers, unused networks, dangling images
docker system prune -a --volumes                 # also unused images and volumes -- destructive
```

## How it's done in production

In production the raw commands above are almost always wrapped by an orchestrator (Kubernetes, ECS, Nomad) that translates `docker run` flags into pod/task specs, but the underlying primitives — image, layer, namespace, cgroup — are identical; a Kubernetes memory `limit` is still a cgroup memory limit enforced the same way. The container runtime itself is frequently containerd or CRI-O directly, with Docker CLI absent from the node entirely — this is why "the pod got OOMKilled" and "the container got OOMKilled" are the same underlying event described at two different abstraction layers.

| Symptom | Cause | Fix |
|---|---|---|
| Container exits immediately after `docker run` with no error | Main process (often a shell script or interpreter) exits after finishing its work — there's no long-running foreground process for PID 1 | Check the actual entrypoint/CMD runs a foreground process (`exec` your server, don't background it), `docker logs` the exited container to see stdout before it exited |
| `docker exec` works but `docker logs` shows nothing | Application logs to a file inside the container instead of stdout/stderr | Redirect app logging to stdout/stderr — Docker's log driver only captures those two streams |
| Container works with `docker run` but not `docker-compose up` | Different network — Compose puts services on a project-specific bridge with DNS by service name, not `localhost` | Reference the dependency by service name (`db`, not `localhost` or `127.0.0.1`) inside the container |
| `docker build` succeeds locally, fails in CI with "no space left on device" | CI runner's `/var/lib/docker` filled up from prior unpruned images/layers | `docker system df` to confirm, `docker system prune -af` in a pre-build CI step, or move to a bigger disk |
| Bind-mounted code changes don't show up in the container | Editor writes via a new inode (common with some editors' atomic-save behavior) that breaks a mount setup, or you bind-mounted the wrong path | Confirm the exact host path with `docker inspect -f '{{.Mounts}}' <container>` |
| Container can't resolve another container's hostname | Containers are on different Docker networks (default bridge doesn't get embedded DNS the way user-defined networks do) | Put both on the same user-defined network; `docker network inspect` to confirm both are members |

## Tradeoffs & when NOT to use it

- **Don't containerize a stateful database you actually care about without volumes and a real backup story.** A container's writable layer disappearing with `docker rm` is the correct, intended behavior — treating a container's local filesystem as durable storage is the single most common way people lose data with Docker.
- **Don't use `--network host` by default "to avoid networking issues."** It removes network namespace isolation entirely (the container shares the host's network stack, including all its ports), which defeats one of the main security boundaries containers provide and makes port conflicts a host-wide problem instead of a per-container one. It's a legitimate escape hatch for specific performance-sensitive cases (some high-throughput networking workloads), not a default.
- **Don't reach for a container when a static binary or a venv would do.** For a Python/Go CLI tool you run locally, the image build/pull overhead and the layer of indirection cost more than they save; containers earn their keep when you need reproducible deployment across heterogeneous hosts or dependency isolation between services on the same box.
- **A shared kernel is not a hard multi-tenant security boundary.** If you're running untrusted code from different customers on the same host, plain containers (even non-root, even with seccomp/AppArmor profiles) are a weaker isolation guarantee than a VM; that's exactly why gVisor/Kata/Firecracker exist for genuinely multi-tenant platforms.

---

## Interview questions

### Q1 — What's the difference between an image and a container, precisely?
**Testing:** whether the mental model is actually load-bearing or just vocabulary.
**Answer:** An image is a read-only, layered filesystem plus config metadata (entrypoint, env, exposed ports) stored content-addressed on disk. A container is that image plus one thin writable layer for runtime changes, plus a set of Linux namespaces (pid, net, mnt, uts, ipc, user) and cgroups that give the process its own view of the system and enforce resource limits. One image can back many simultaneously running containers, each with its own writable layer and namespaces.
**Follow-up trap:** *"If I delete a file inside a running container, does the image change?"* — no; the delete only happens in the container's writable layer as a whiteout marker over the image's read-only layers, which are immutable once built. Committing that container to a new image (`docker commit`) would produce a new image reflecting the delete, but the original image is untouched.

### Q2 — Why does instruction order in a Dockerfile affect build speed, and how do you order it correctly?
**Answer:** Docker caches each layer keyed on the instruction plus everything above it; the first changed instruction invalidates every layer below it in the build. Put things that change rarely (base image, OS packages, dependency manifests + install) before things that change often (application source), so a code-only edit only invalidates the final `COPY . .` layer instead of re-running a multi-minute dependency install.
**Follow-up trap:** *"You copy `requirements.txt` and run `pip install` before `COPY . .`, but builds are still slow on every commit. Why?"* — check whether the build context itself is large and slow to hash/send (a missing `.dockerignore` sending `.git`, `node_modules`, or a virtualenv into the build context on every invocation) or whether something upstream of the dependency install (like the base image tag) is actually changing.

### Q3 — A container exits immediately with no visible error. Walk through your diagnosis.
**Answer:** `docker logs <container>` first — captures stdout/stderr up to the exit, which is the highest-signal, lowest-effort check. Then `docker inspect -f '{{.State.ExitCode}}' <container>` to read the actual exit code (0 = clean exit of the main process, non-zero = error, 137 = SIGKILL/OOM, 143 = SIGTERM). If logs are empty and exit code is 0, the main process legitimately finished and returned — common when a script wasn't meant to be the long-running foreground process.
**Follow-up trap:** *"Exit code is 0, but you expected the server to run forever."* — check the actual `ENTRYPOINT`/`CMD` — a common bug is a shell script that starts the server in the background (`server &`) and then exits itself, taking PID 1 (and the whole container) down with it even though the backgrounded process was still "running" from the shell's perspective.

### Q4 — Explain what happens, mechanically, when you set `docker run -m 512m`.
**Answer:** Docker sets the container's cgroup memory limit (`memory.max` under cgroup v2, `memory.limit_in_bytes` under v1) to 512 MiB. This is enforced by the kernel, not Docker — if the cgroup's total resident memory tries to exceed that limit, the kernel's OOM killer targets a process in that specific cgroup, independent of how much memory the host has free overall. `docker stats` reads the same cgroup counters live.
**Follow-up trap:** *"Container shows healthy `docker stats` memory usage right up until it dies with exit code 137. What are you missing?"* — page cache and buffer memory used by the process for file I/O also counts against the cgroup limit in many configurations, and short-lived spikes (a burst allocation, a GC pause building up garbage before collecting) can exceed the limit for long enough to trigger a kill between `docker stats` polling intervals — the fix is checking `dmesg`/kernel OOM logs for the exact kill event, not trusting the last `docker stats` sample as ground truth.

### Q5 — What's the difference between a named volume and a bind mount, and when do you use each?
**Answer:** A named volume is storage Docker itself manages under `/var/lib/docker/volumes/<name>/_data`, addressed by name, portable across containers, and the correct choice for anything you want to persist independent of a specific host path — databases, caches. A bind mount is a literal host filesystem path injected into the container; it's the right tool for local development (live-editing source on the host, seeing it instantly inside the container) but ties the setup to that exact host path and isn't portable to a different machine or orchestrator.
**Follow-up trap:** *"You bind-mount your entire project directory including `node_modules` built for your host OS into a Linux container. What breaks?"* — native binary dependencies (compiled node modules, some Python C extensions) built for the host OS/arch get shadowed into the container and won't run there if the container's OS/arch differs — the classic fix is excluding `node_modules`/`venv` from the bind mount and installing them fresh inside the container via a named volume or the image build itself.

### Q6 — Two containers on the default `bridge` network can't resolve each other by name, but the same two containers work fine under `docker-compose up`. Why?
**Answer:** Docker's embedded DNS (`127.0.0.11` inside each container) only functions on user-defined bridge networks, not the default `bridge` network created automatically by the daemon — Compose always creates a user-defined bridge per project, which is why service-name resolution "just works" there but not with plain `docker run` on the default network.
**Follow-up trap:** *"How would you get name resolution working with plain `docker run`, without Compose?"* — `docker network create mynet` and run both containers with `--network mynet`; they'll then resolve each other by container name through the same embedded DNS mechanism Compose relies on.

### Q7 — What does `docker system df` show that summing image sizes with `docker images` doesn't?
**Answer:** `docker images` sizes are per-image and count shared, content-addressed layers redundantly across every image that references them; `docker system df` reports actual disk usage and the specifically reclaimable portion (unused, non-dangling-only images, stopped containers, unused volumes), reflecting shared-layer deduplication.
**Follow-up trap:** *"`docker system df` shows 40 GB reclaimable in images, but `docker image prune -a` only frees 5 GB. Explain the gap."* — `prune -a` without force still respects images referenced by any container (running or stopped) or tagged with something other than `<none>`; check for stopped containers holding references (`docker ps -a`) or images tagged and still "in use" by that definition even if nothing's actively running.

### Q8 — Explain why PID 1 inside a container needs special handling for signals.
**Answer:** The kernel gives PID 1 in a namespace the same special treatment it gives PID 1 on a full host: default signal handlers are not installed automatically, so a process that doesn't explicitly handle `SIGTERM` will simply ignore it, forcing Docker to wait out the full stop grace period (default 10s) and then send `SIGKILL`. Additionally, PID 1 is responsible for reaping zombie child processes; a shell or interpreter that spawns children without reaping them can accumulate zombies.
**Follow-up trap:** *"Your entrypoint is `CMD ["python", "app.py"]` and `docker stop` always takes the full 10 seconds even though your app has a signal handler. What's wrong?"* — check whether `CMD` is being run through a shell wrapper (`sh -c "python app.py"`), which makes the shell PID 1 and the actual Python process a child that never sees the signal directly; use exec form (`CMD ["python", "app.py"]`, no shell) or `exec python app.py` inside a shell script so the real process becomes PID 1 or directly receives the forwarded signal.

### Q9 — A `docker build` fails in CI with "no space left on device" but succeeds locally. Diagnose and fix.
**Answer:** `docker system df` on the CI runner almost always shows unpruned images/layers from prior builds filling `/var/lib/docker`; CI runners frequently reuse the same disk across many builds without the periodic manual cleanup a developer's laptop gets implicitly. Fix: add a `docker system prune -af` (or a dedicated cache-cleanup step) before or after builds, or move to a runner image/cache strategy that doesn't accumulate unbounded local layers.
**Follow-up trap:** *"Pruning fixes it today but it recurs every few weeks. What's the actual root cause, and what's the better fix than a recurring manual prune?"* — the CI system is treating the Docker layer cache as unbounded local disk instead of a bounded, evicting cache; the better fix is CI-native layer caching (BuildKit's `--cache-from`/`--cache-to` against a registry, or a CI provider's dedicated Docker layer cache feature) with an explicit size/TTL policy, not a human remembering to prune.

### Q10 — Why is `docker stop` followed by a grace period before `docker kill`, and what's the default?
**Answer:** `docker stop` sends `SIGTERM` first, giving the process a chance to shut down gracefully (flush buffers, close connections, finish in-flight requests), then waits a grace period (10 seconds by default) before escalating to `SIGKILL` if the process hasn't exited. This exists because an ungraceful kill mid-write can corrupt state or drop in-flight work.
**Follow-up trap:** *"Your app takes 25 seconds to drain in-flight requests on shutdown, but you're seeing connections cut off abruptly in production. What's the fix, and what's the actual failure signature you'd look for?"* — the default 10s grace period is shorter than the app's actual drain time, so it's being SIGKILLed mid-drain; fix with `docker stop -t 30` (or the orchestrator's equivalent, e.g. Kubernetes `terminationGracePeriodSeconds`); the signature is exit code 137 or the equivalent forced-termination event correlated with requests that show a truncated/reset connection right at the deploy/restart timestamp.

---

## Red flags that fail you

- Calling `docker run` and `docker-compose up` "basically the same thing" without knowing Compose creates a user-defined network with embedded DNS that plain `docker run` on the default bridge doesn't have.
- Treating a container's writable layer as durable storage for anything you'd be upset to lose.
- Not knowing the difference between a named volume and a bind mount when asked directly.
- Saying "just add more memory" to fix an OOMKilled container without first confirming with `docker inspect`/kernel OOM logs that it's actually a memory limit issue and not a leak.
- Not knowing `docker logs` only captures stdout/stderr, not arbitrary log files inside the container.

## Cheat card

```
IMAGE = read-only layers (content-addressed, hash of instruction + inputs) + config JSON
CONTAINER = image + 1 writable layer + namespaces (pid/net/mnt/uts/ipc/user) + cgroups
Layer cache invalidates FORWARD from first changed instruction -- order rare->frequent changes

docker build -t x:tag .          docker run -d --name n -p 8080:80 -e K=v --restart unless-stopped x
docker logs -f --tail 200 n      docker exec -it n sh
docker inspect -f '{{.State.OOMKilled}} {{.State.ExitCode}}' n
docker stats n                   docker top n
docker stop [-t 30] n  (SIGTERM, wait, then SIGKILL; default grace 10s)

Volume (Docker-managed, /var/lib/docker/volumes/..) vs Bind mount (host path, not portable)
docker network create net   -- user-defined bridge gets embedded DNS (127.0.0.11); default bridge does NOT
--network host = no net namespace isolation; --network none = no network at all

docker system df   -- real reclaimable space (dedup by shared layer)
docker system prune -af --volumes  -- destructive, confirm first

PID 1 in container: no default signal handlers, must reap zombies -- use exec form CMD, not `sh -c`
Exit 137 = SIGKILL (often OOM); Exit 143 = SIGTERM handled by default handler; Exit 0 = clean but check if intended
```

## Sources

- [Docker Engine v29 Release](https://www.docker.com/blog/docker-engine-version-29/) — accessed 2026-07-26
- [Docker Engine | endoflife.date](https://endoflife.date/docker-engine) — accessed 2026-07-26
- [Docker Interview Questions 2026: Crack It Like a Pro — KodeKloud](https://kodekloud.com/blog/docker-interview-questions/) — accessed 2026-07-26
- [Fix Docker Exit Code 137 (OOMKilled) — DEV Community](https://dev.to/jjoyneriv/fix-docker-exit-code-137-oomkilled-why-it-happens-and-how-to-stop-it-4ipf) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
