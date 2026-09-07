# Production notes — Docker semantics

## What you'd actually use

| Need | Tool |
|---|---|
| Build | Docker Engine 23+ (BuildKit is the default builder), or `docker buildx` |
| Layer inspection | `docker history --no-trunc`, `dive` (per-layer diff), `docker save | tar -t` |
| Image scanning | `trivy image`, `grype` — in CI, blocking on HIGH/CRITICAL |
| SBOM + signing | `docker buildx build --sbom=true`, cosign / Sigstore, Kyverno admission checks |
| Linting | `hadolint` (the real rules your W001–W005 are approximations of) |
| Registries | Docker Hub, ECR/GCR/ACR, GHCR — all speak the OCI distribution spec |

## BuildKit cache mounts vs the layer cache (the thing your simulator models)

Your `LayerCache` models the *layer cache*: a build step is keyed on its inputs, and one invalidated step invalidates every step after it. BuildKit adds a second mechanism that breaks the cascade — the **cache mount**:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

The pip cache directory persists *between builds as build state*, not as an image layer. When `requirements.txt` changes, the layer is invalidated (miss in your simulator), but the next build starts warm: the wheels are already downloaded, so a "cold" pip install that took 90s takes 9s. Same for `apt` (`/var/cache/apt`), `npm` (`/root/.npm`), `go` (`/root/.cache/go-build`), `cargo` (`/usr/local/cargo/registry`). Rule of thumb: **layer cache for "nothing changed" fast paths, cache mounts for "something changed but the internet is slow" paths.** The pair — cache mounts plus secret mounts (`--mount=type=secret`) — is what made `ENV AWS_SECRET_ACCESS_KEY` in a Dockerfile inexcusable.

## Multi-stage: the copy your simulator doesn't do

```dockerfile
FROM golang:1.23 AS build
WORKDIR /src
COPY . .
RUN go build -o /out/server ./cmd/server

FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/server /server
USER nonroot:nonroot
ENTRYPOINT ["/server"]
```

The 900MB Go toolchain exists only in the `build` stage. `COPY --from=build` pulls *only the named artifact* out of it; the final image ships the ~2MB distroless base plus your binary. The layers of intermediate stages never ship, never get pushed, never get scanned by whoever pulls your image. The move that unlocks the "why is prod 20MB when CI needs a gigabyte" interview question.

## Why 137 means OOMKill

A container exit code ≥ 128 means "killed by signal N" (`128 + N`). 137 = 128 + 9 = SIGKILL, and inside a container the two things that send SIGKILL are `docker kill` and the **kernel OOM killer**, because a container that exceeds its cgroup memory limit gets OOM-killed by the kernel — the process never gets a chance to clean up. 143 = 128 + 15 = SIGTERM, the *polite* request (`docker stop`, 10s grace, then SIGKILL). The on-call move: container restarts with code 137, check `docker inspect` for `OOMKilled: true` before touching the app. The interview follow-up: cgroup limits (or the k8s pod limit) cap RSS including page cache; "it works on my machine" VMs don't have that ceiling.

## What production adds over your simulation

- **Content-addressed storage for real** — your digests hash the *instruction*; real layers hash the *resulting filesystem diff* (a tar of the changed files). Two different instructions that produce the same filesystem (e.g. `RUN true` vs `RUN :`) deduplicate; yours can't.
- **Cross-build, cross-machine, cross-registry cache** — BuildKit's cache is a content-addressed graph that can be exported to and pulled from a registry (`--cache-to/--cache-from type=registry`), so a CI cold start can warm from last night's build. Yours lives in one Python object.
- **Parallel stage execution** — independent stages build concurrently; a missing `COPY . .`-style ordering dependency is resolved by BuildKit's dependency graph, not by your for-loop.
- **Secrets still leak in real layers** — your W005 catches `ENV`; real leaks come from `COPY . .` dragging a `.env` file in, or a `RUN curl -H "Authorization: ..."` where the token lands in shell history *inside the layer*. `docker history --no-trunc` on a published image is the post-mortem move; `--mount=type=secret` is the prevention.
- **The manifest list** — real images are manifest lists per architecture; a digest pins the *whole* list, so the same `FROM x@sha256:...` gets the same image on ARM CI and AMD64 prod. Your simulator has no architecture axis.

## The 3 questions an interviewer asks after you describe this

1. *"Your 30-second build just took 8 minutes. Walk me through the diagnosis."* — something early invalidated the prefix: usually a `COPY . .` above the dependency install. Order the Dockerfile least-likely-to-change → most-likely-to-change; fix with reordering, and if the download itself is the cost, a cache mount.
2. *"Where does a secret deleted in a later RUN actually live?"* — in the layer it was written to, forever: layers are immutable, later `rm` adds a whiteout, it never rewrites layer history. `docker history --no-trunc` or `docker save` proves it. Secret mounts prevent it.
3. *"What actually runs when you `docker run` distroless and `docker exec sh` fails?"* — no shell in the image; use `docker cp` + a debugger sidecar, or `kubectl debug` with an ephemeral container. Knowing *why* `exec sh` fails (no `/bin/sh` in the image) is the point of distroless.
