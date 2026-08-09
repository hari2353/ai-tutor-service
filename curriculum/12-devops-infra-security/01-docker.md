# Docker: Layers, Multi-Stage, Distroless, BuildKit, Scanning

> **Track:** T12 DevOps, Infra & Security · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-02
> **Module id:** `T12-docker` · **Tags:** containers
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A Docker image is a stack of immutable, content-addressed layers produced one per build instruction, and the two things that actually move the needle on image quality are cache correctness (order instructions least-to-most-volatile so a `COPY package.json` doesn't get invalidated by every source change) and stage separation (build with a full toolchain, ship a runtime with none of it). BuildKit, the default builder since Docker 23.0, replaced the old sequential builder with a DAG executor that runs independent stages in parallel and adds `--mount=type=cache` for persistent build caches (npm/pip/go-mod directories that survive across builds without polluting the final image) and `--mount=type=secret` so credentials never land in a layer. Distroless or scratch final stages cut CVE surface by removing the shell, package manager, and everything else an attacker would use after landing a foothold, at the direct cost of losing `docker exec sh` as a debugging tool. None of this is optional anymore: unsigned, unscanned images with baked-in secrets are the default finding in every container security audit, and the fix is mechanical, not aspirational.

## Why this gets asked

Because nearly every production incident that touches "the image" traces back to one of three things: a cache-busted build that made CI unbearably slow, a 1.2GB image that shipped a full OS's worth of attack surface into a security review, or a secret that got baked into a layer and is now permanently in the image history even after being "removed" in a later layer. The interviewer has almost certainly sat through an incident retro where someone asked "why does this build take 18 minutes" or a pen test finding that said "base image contains 340 known CVEs, several critical," and they want to know if you can reason about *why* those things happen at the layer/cache mechanics level rather than just reciting "use multi-stage builds" as a slogan.

---

## Lineage: past → present → future

**What came before.** Before Docker (2013), isolation was VMs (full OS per workload, minutes to boot, gigabytes of overhead) or raw LXC/chroot/cgroups used directly, which worked but had no portable image format, no layer reuse, and no ecosystem — every team built its own bespoke deployment artifact. Docker's contribution wasn't containers (Linux namespaces and cgroups predate it by years), it was the *image format*: a union filesystem (originally AUFS, standardized later as OverlayFS/overlay2) that let you express "this image is that image plus these three changes" and share the unchanged layers across every image built from the same base. The pain that made this necessary was "works on my machine" — dependency drift between dev, CI, and prod that no amount of configuration management fully solved. The early cost nobody priced in: teams built images from `FROM ubuntu:latest`, `apt-get install` a build toolchain, compiled in place, and shipped the same 900MB-plus image with compilers, package managers, and shells into production, because there was no easy way to separate "what I needed to build this" from "what I need to run it."

**Where it stands now.** Multi-stage builds (Docker 17.05, 2017) solved the separation problem directly — `COPY --from=<stage>` lets a final stage pull only the compiled artifact out of a build stage and discard everything else, including the entire build toolchain, without needing two separate Dockerfiles or manual `docker export` gymnastics. Distroless images (Google, 2017 onward) took the final stage further by removing the shell and package manager entirely, not just trimming the OS — `gcr.io/distroless/*` images contain your runtime and its shared libraries and nothing an attacker can use post-compromise to explore, download tools, or pivot. BuildKit becoming the default builder (Docker 23.0, May 2023) changed the build execution model itself: from a strictly sequential instruction-by-instruction builder to a DAG scheduler that parallelizes independent stages and supports cache and secret mounts as first-class primitives instead of hacks (multi-stage "throwaway" stages just to leak a cached directory, or `--build-arg` smuggling of secrets that then sit in image history forever). The live disagreement in 2026 is less "should you multi-stage" (settled, yes) and more Alpine-vs-distroless-vs-scratch for the final stage: Alpine's musl libc is smaller but has real compatibility gaps with glibc-compiled artifacts (notably Python wheels with native extensions, which is why the official Python image ships glibc-based `slim` variants alongside Alpine ones), while distroless and scratch eliminate the shell entirely, which some teams still find operationally uncomfortable despite the security win, because it removes the "just exec in and poke around" reflex.

**Where it's heading.** Supply chain security is moving from "best practice for regulated industries" to table stakes, driven by concrete incidents — the xz-utils backdoor (discovered March 2024, a maintainer-social-engineering supply chain attack embedded in a widely used compression library that very nearly landed in major Linux distributions) is the reference incident cited in nearly every 2025-2026 SBOM and signing pitch, the same way SolarWinds anchored the CI/CD-compromise conversation in 2020-2021. SBOM generation (Syft, `docker buildx imagetools`) and image signing (Sigstore/cosign, keyless signing tied to OIDC identity rather than long-lived keys) are increasingly wired directly into build pipelines rather than bolted on afterward, and SLSA provenance attestations (verifiable claims about *how* an artifact was built, not just what's in it) are the direction admission-control policy is heading — expect "unsigned image" and "no SBOM attached" to become hard blocks in more organizations' deploy pipelines over the next few years, though this is not yet universal outside finance, healthcare, and government-adjacent shops.

---

## Mental model

Think of an image as a git history where every commit is a filesystem diff, and the union filesystem is what lets the runtime present all those diffs as one merged view without physically copying anything:

```
IMAGE = ordered list of read-only layers, each content-addressed by sha256(layer contents)

  layer 4 (sha256:abcd...)  COPY app.py /app/          <- most volatile, changes every build
  layer 3 (sha256:9f2e...)  RUN pip install -r req.txt <- changes when deps change
  layer 2 (sha256:71ac...)  COPY requirements.txt /app/
  layer 1 (sha256:0e33...)  FROM python:3.13-slim      <- base, almost never changes

overlay2 union mount at container runtime:
  /var/lib/docker/overlay2/<id>/diff/       <- layer 1 (lowerdir, read-only)
  /var/lib/docker/overlay2/<id>/diff/       <- layer 2 (lowerdir, read-only)
  ...
  /var/lib/docker/overlay2/<id>/diff/       <- layer 4 (lowerdir, read-only)
  /var/lib/docker/overlay2/<container>/upper/  <- container's own writable layer
                                                   (upperdir — anything the running
                                                    process writes lands ONLY here)
  merged/  <- what the container process actually sees: all lowerdirs + upperdir
             flattened into one filesystem view, copy-on-write
```

The insight that matters: a `RUN` or `COPY` instruction's cache key is a hash of *the instruction plus its inputs* (the build context files it touches, for `COPY`; the instruction string itself, for `RUN`), not a hash of "did anything change." Reorder instructions so the ones that change most often are last, and every layer above a cache hit gets reused verbatim without re-executing.

---

## How it actually works

### Cache invalidation, precisely

BuildKit checks each instruction's cache key against what's already been built. For `RUN`, the key is derived from the exact instruction text and the state of the layer below it — change one character in a `RUN` command and every layer from that point forward rebuilds, even if the actual effect would've been identical. For `COPY`/`ADD`, the key additionally depends on the content hash of the files being copied, so `COPY . /app` invalidates on *any* file change anywhere in the build context, which is why copying `requirements.txt` or `package.json` alone, running the install step, and only then copying the rest of the source is the standard pattern:

```dockerfile
# BAD: any source change invalidates the pip install layer, forcing a full reinstall
COPY . /app
RUN pip install -r /app/requirements.txt

# GOOD: pip install only reruns when requirements.txt itself changes
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt
COPY . /app
```

`COPY --link` (BuildKit-specific) goes further: it copies files as an independent layer that doesn't depend on the layer below it, so reordering or inserting instructions earlier in the Dockerfile doesn't invalidate that copy's cache the way a normal `COPY` would, because the link-copy layer is composed at the image-assembly step rather than chained to its predecessor's state.

### Multi-stage builds, with real numbers

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.23 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/root/go/pkg/mod \
    go mod download
COPY . .
RUN --mount=type=cache,target=/root/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -o /out/app .

FROM gcr.io/distroless/static-debian12:nonroot AS final
COPY --from=build /out/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

The `build` stage (golang:1.23, ~800MB with the full toolchain) never ships. The `final` stage starts from `distroless/static` (roughly **2MB** base — no libc even, for a fully static binary) and adds only the compiled binary. The two `--mount=type=cache` lines are BuildKit cache mounts: they persist `/root/go/pkg/mod` (downloaded modules) and the Go build cache *across builds on the same builder*, without those directories ever becoming part of any image layer — a repeat build with unchanged dependencies goes from a multi-minute `go mod download` to a cache hit measured in low seconds, because the cache directory already has the modules on disk and BuildKit just mounts it in for the duration of that `RUN`.

For a typical Node.js service, the same pattern with `--mount=type=cache,target=/root/.npm` turns `npm install` from **minutes on a cold cache to sub-second on a warm one**, and the reported end-to-end effect on CI in practice is builds dropping from roughly **20 minutes to under 5** once both dependency caching and multi-stage separation are in place — the two changes compound because a smaller final stage also means less to push/pull to and from the registry.

### Distroless vs Alpine vs scratch — the actual tradeoff

| Base | Approx. size | Shell? | Package manager? | Right for |
|---|---|---|---|---|
| `scratch` | 0MB | No | No | Fully static binaries (Go with `CGO_ENABLED=0`, Rust with musl target) — nothing else works, no libc at all |
| `distroless/static` | ~2MB | No | No | Static binaries that don't need libc but want CA certs, timezone data, `/etc/passwd` present |
| `distroless/base` | ~20MB | No | No | Dynamically linked binaries needing glibc but no interpreter |
| `distroless/python3` / `distroless/java` | tens of MB | No | No | Interpreted/JVM languages, still no shell for debugging |
| `alpine` | ~5MB | Yes (`ash`) | Yes (`apk`) | When you need a shell for entrypoint scripting or genuinely need `apk` at runtime; watch for musl-vs-glibc native extension breakage |
| `debian-slim` | ~80MB | Yes | Yes (`apt`) | Widest compatibility, still meaningfully smaller than full `debian`/`ubuntu` |

Distroless removing the shell and package manager isn't a size optimization primarily, it's an attack-surface one: **Google reports distroless images cut CVE surface by roughly 90%** relative to a full-distro base, because the vast majority of CVEs scanners flag in a typical image are in OS packages the application never touches (coreutils, package manager internals, shells) rather than in the application's actual runtime dependencies. The direct cost: `docker exec -it <container> sh` stops working, because there's no `sh`. The fix in production is an **ephemeral debug container** (`kubectl debug -it <pod> --image=busybox --target=<container>` shares the target's process namespace without modifying the running pod) rather than baking debug tooling into the production image, or using the distroless `:debug` tag variants that include a busybox shell for local troubleshooting only.

### Secrets: the ARG/ENV trap and the BuildKit fix

```dockerfile
# WRONG — this secret is now permanently embedded in the image's layer history,
# recoverable with `docker history` or by pulling the image and inspecting layers,
# even if a later instruction "deletes" the file — the layer that added it still exists
ARG NPM_TOKEN
RUN echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > .npmrc && npm install && rm .npmrc

# RIGHT — BuildKit secret mount: available only for the duration of this RUN,
# never written to any layer, never appears in `docker history`
RUN --mount=type=secret,id=npmtoken \
    NPM_TOKEN=$(cat /run/secrets/npmtoken) npm install
```

Build with `docker build --secret id=npmtoken,src=$HOME/.npmtoken .`. The secret file is mounted at `/run/secrets/<id>` only inside that specific `RUN` step's filesystem and is never committed to a layer, which is the entire point — `rm`ing a file in a later layer does not remove it from the layer where it was written, because layers are immutable and additive; the file is still recoverable from the earlier layer's diff.

### Numbers worth having ready

- Unoptimized image with a full OS + build toolchain baked in: commonly **800MB-1.2GB**.
- Same app, multi-stage + distroless final stage: typically **under 50MB**, often **2-20MB** for statically linked binaries.
- Distroless CVE surface reduction versus full-distro base: **~90%** (Google's own figure, widely corroborated by scanner output comparisons).
- Warm-cache `npm install`/`go mod download` with BuildKit cache mounts: **sub-second**, versus multi-minute cold.
- Reported CI build time improvement from cache mounts + multi-stage together: **~20 minutes down to under 5**.
- BuildKit became Docker's default builder in **Docker 23.0 (May 2023)** — anything before that on the legacy builder doesn't get parallel stage execution or `--mount` support without explicitly opting in via `DOCKER_BUILDKIT=1`.

---

## Build it from scratch

The mechanical piece worth internalizing isn't reimplementing overlay2, it's proving you understand content-addressed layer caching by simulating it:

```python
# untested sketch — models layer cache-key derivation, not a real builder
import hashlib
import json

class Layer:
    def __init__(self, instruction: str, input_hash: str, content_hash: str = ""):
        self.instruction = instruction
        # cache key = hash of (instruction text + upstream layer's hash + any copied content)
        key_material = f"{instruction}|{input_hash}|{content_hash}"
        self.cache_key = hashlib.sha256(key_material.encode()).hexdigest()[:12]

class BuildCache:
    def __init__(self):
        self.built = {}  # cache_key -> "layer contents"

    def build_layer(self, instruction: str, parent: "Layer | None", content_hash: str = ""):
        input_hash = parent.cache_key if parent else "scratch"
        layer = Layer(instruction, input_hash, content_hash)
        if layer.cache_key in self.built:
            print(f"CACHED  {instruction!r:45} -> {layer.cache_key}")
        else:
            print(f"RUN     {instruction!r:45} -> {layer.cache_key}")
            self.built[layer.cache_key] = f"result of: {instruction}"
        return layer

cache = BuildCache()
base = cache.build_layer("FROM python:3.13-slim", None)
reqs = cache.build_layer("COPY requirements.txt", base, content_hash="req-v1")
deps = cache.build_layer("RUN pip install -r requirements.txt", reqs)
app  = cache.build_layer("COPY . /app", deps, content_hash="src-v1")

# rebuild with unchanged requirements.txt but changed source: only the COPY . layer reruns
base2 = cache.build_layer("FROM python:3.13-slim", None)               # CACHED
reqs2 = cache.build_layer("COPY requirements.txt", base2, "req-v1")    # CACHED
deps2 = cache.build_layer("RUN pip install -r requirements.txt", reqs2)  # CACHED
app2  = cache.build_layer("COPY . /app", deps2, content_hash="src-v2")   # RUN (content changed)
```

The point of writing this out is that the assertion "reorder least-to-most-volatile" stops being folklore once you can show *why* the hash changes — the cache key is a function of everything upstream plus this instruction's own content, so any change anywhere upstream cascades forward, and that's the mechanical reason instruction order is the single highest-leverage lever on build time.

---

## How it's done in production

`docker buildx` (BuildKit's CLI frontend, bundled by default since Docker 23) adds multi-platform builds (`--platform linux/amd64,linux/arm64` building both in one invocation via QEMU emulation or native multi-arch builders) and remote cache backends — `--cache-to type=registry,ref=myrepo/app:buildcache --cache-from type=registry,ref=myrepo/app:buildcache` persists the build cache in a registry so ephemeral CI runners (which have no local disk cache between runs) still get cache hits, and GitHub Actions' native cache backend (`type=gha`) does the same against Actions' cache storage.

Image scanning happens at (at least) three points, each catching different things: **build-time** (Trivy/Grype/Snyk scanning the image right after `docker build`, blocking the pipeline on criticals — catches known CVEs in what you just built, but only as of that moment); **registry-time** (periodic re-scan of everything already pushed, because CVEs get disclosed after an image ships — an image that was clean on Monday can have a critical finding by Friday with zero code changes); and **admission-time** (Kyverno/OPA Gatekeeper policies in the cluster rejecting deploys of unsigned images or images missing an attached SBOM, the last line of defense against a scan being skipped or bypassed upstream). SBOM generation (Syft, or `docker buildx imagetools` / `docker sbom`) produces a manifest of every package and version in the image, which is what a scanner actually diffs against a CVE database, and image signing (cosign, Sigstore's keyless flow tied to an OIDC identity like a CI job's GitHub Actions token rather than a long-lived private key you have to rotate and protect) proves provenance — *who* built this image and that it hasn't been tampered with since — which is a distinct guarantee from "this image has no known CVEs."

| Symptom | Cause | Fix |
|---|---|---|
| Image size barely shrinks despite multi-stage | Final stage `COPY --from=build` copies more than the binary (e.g. `COPY --from=build /src /app` grabs the whole build tree), or no `.dockerignore` so build context itself is huge | Copy only the specific artifact path; add a `.dockerignore` excluding `.git`, `node_modules`, test fixtures, docs |
| CI cache always misses despite unchanged deps | Runners are ephemeral with no persisted local disk between jobs | Use `--cache-to`/`--cache-from` with a registry or `type=gha` remote cache backend instead of relying on local BuildKit cache |
| `RUN apt-get update` reruns on every build even with unchanged Dockerfile | A `COPY . .` earlier in the file invalidates everything below it whenever *any* source file changes | Reorder: dependency-manifest `COPY` + install *before* the broad `COPY . .` |
| "exec format error" running the built image on a different arch | Image built for one platform (e.g. amd64 on an Apple Silicon dev machine building without `--platform`) deployed to another (arm64 Graviton nodes) | `docker buildx build --platform linux/amd64,linux/arm64` and push a multi-arch manifest, or explicitly match builder platform to target |
| Secret found in `docker history` during a security review | `ARG`/`ENV` used to pass a credential into a `RUN` step; even "deleted" in a later layer, it's recoverable from the layer that added it | `--mount=type=secret` for anything that must never persist in a layer; rotate the leaked credential regardless, deleting the image doesn't retroactively secure it if it was ever pushed |
| Distroless container "works locally, breaks in prod," no way to `exec` in | No shell in the image by design | Debug via ephemeral debug container (`kubectl debug --target=`) rather than `exec`; keep a `:debug` tag with busybox for local-only troubleshooting |
| Scan blocks deploy on a CVE in a component the app never actually invokes | Scanner flags anything present in the image regardless of whether it's reachable code | Document and suppress with a scoped, expiring exception (`.trivyignore` with a reason and review date), don't disable scanning wholesale |

---

## Tradeoffs & when NOT to use it

- **Don't reach for distroless/scratch on your local dev-loop image.** The fast iterate-rebuild-inspect cycle benefits from a shell and a package manager being present; ship a heavier debug-friendly image locally and reserve the minimal final stage for what actually deploys.
- **`scratch` is the wrong base for anything not fully statically linked.** A dynamically linked binary in a `scratch` image will fail immediately with a missing-loader error; this is a common first-attempt mistake, and the fix isn't "add more to scratch," it's using `distroless/base` (which has glibc) or accepting you need `CGO_ENABLED=0` and a static build in the first place.
- **Multi-stage complexity isn't worth it for a throwaway internal tool** where image size and attack surface genuinely don't matter and the team values a simple, single-stage Dockerfile they can read in ten seconds over a marginal size win.
- **BuildKit cache mounts are a build-machine optimization, not a portability guarantee.** The cached directory content is explicitly excluded from the final image and from any reproducibility/provenance story — don't rely on cache mount contents surviving a builder migration, and don't assume the cache makes the build itself reproducible (it doesn't; it just makes it faster on a warm builder).
- **Signing and SBOM pipelines have a real setup and maintenance cost** (key/identity management, verifying policy enforcement in admission control, keeping the SBOM tooling current) — worth it early for regulated environments, genuinely optional overhead for a pre-PMF startup that isn't shipping to environments requiring the guarantee yet; don't cargo-cult it onto a two-person team's internal tools.

---

## Interview questions

### Q1 — Walk through exactly what invalidates a Docker layer's build cache.
**Testing:** whether the candidate knows this is content-hash-based, not timestamp-based, and can reason about instruction ordering.
**Answer:** Each layer's cache key is derived from the exact instruction text plus, for `COPY`/`ADD`, a content hash of the files being copied, chained to the cache key of the layer beneath it. Any change to an upstream layer's key invalidates every layer built on top of it, even if the downstream instruction itself is unchanged. That's why ordering matters: put the least-frequently-changing instructions (base image, dependency manifest copy, dependency install) first, and the most-frequently-changing (source code copy) last.
**Follow-up trap:** *"If I change one comment in my Dockerfile with no functional effect, does the cache still get busted?"* — depends on where: a comment change doesn't itself become part of any instruction's cache key since comments aren't executed, but reordering or inserting instructions absolutely does shift what's "upstream" of everything below it, busting cache even with zero functional change to the build's output.

### Q2 — Explain multi-stage builds and why the intermediate stage's contents don't end up in the final image.
**Testing:** mechanical understanding of `COPY --from`, not just "it makes images smaller."
**Answer:** Each `FROM` starts a new, independent build stage with its own layer chain. A later stage can `COPY --from=<earlier-stage-name-or-index>` specific files out of an earlier stage's filesystem, but the final image's layer list only includes the layers actually declared in the final stage — nothing from the discarded intermediate stage's layers is part of the shipped image's manifest, so the build toolchain, cached dependency downloads, and intermediate object files never leave the builder.
**Follow-up trap:** *"Does Docker build every stage in the Dockerfile even if the final target doesn't reference some of them?"* — with BuildKit, no: it only builds stages that are actual dependencies of the target stage (default: the last one, or whatever `--target` specifies), skipping unreferenced stages entirely, which is a real behavioral difference from the legacy sequential builder in some edge cases.

### Q3 — Distroless, Alpine, or scratch for a Python service — which, and why?
**Testing:** whether they know the musl/glibc trap, not just "smaller is better."
**Answer:** Neither `scratch` (Python needs a runtime and dynamic libraries, it isn't a static binary) nor a naive assumption that Alpine is strictly best. Alpine uses musl libc, and Python wheels with native C extensions (numpy, cryptography, many ML libraries) are frequently built against glibc; installing them on Alpine either fails outright or falls back to a much slower source compile at install time. `distroless/python3` or a `debian-slim`-based image sidesteps this because both are glibc-based, at the cost of Alpine's smaller base size.
**Follow-up trap:** *"You benchmarked and Alpine is 5MB smaller — worth the risk?"* — no, not usually: the actual pip install failure or silent slow-path recompilation is a worse production risk than a few MB of image size, and the fix (glibc-based slim/distroless) costs tens of MB at most, which is noise next to build-toolchain removal via multi-staging in the first place.

### Q4 — What does `--mount=type=cache` actually do, and why doesn't its content show up in the final image?
**Testing:** whether they understand cache mounts are a build-time-only filesystem overlay, distinct from image layers.
**Answer:** It mounts a persistent directory (keyed by an id, shared across builds on the same builder) into the container for the duration of a single `RUN` step, so tools like `pip`, `npm`, or `go build` can read and write their cache directories without that cache becoming part of any committed layer. It's explicitly excluded from the layer diff BuildKit records — the mount exists only during execution and is unmounted (but persisted on the builder host/volume) after the `RUN` finishes.
**Follow-up trap:** *"Does this make the build reproducible — same inputs, byte-identical output?"* — no, the opposite concern: reproducibility usually wants to eliminate hidden state affecting the build, and a cache mount is exactly that kind of hidden, builder-local state (a `pip install` might resolve a slightly different package version depending on what's already cached versus a truly clean environment). Cache mounts optimize speed, not determinism; those are separate goals that can even be in tension.

### Q5 — Your distroless production container is misbehaving. How do you debug it without a shell?
**Testing:** knowledge of ephemeral debug containers as the actual production-safe pattern, not "add a shell to prod."
**Answer:** `kubectl debug -it <pod> --image=busybox --target=<container-name>` attaches a new ephemeral container into the target pod's process namespace, giving shell access and tooling without modifying the running container or its image. For local, pre-deploy debugging, distroless images ship parallel `:debug` tags with a minimal busybox shell baked in specifically for that purpose, never intended for production use.
**Follow-up trap:** *"Isn't it simpler to just keep a shell in the production image?"* — that reintroduces the exact attack surface distroless removes; the entire threat model it's defending against is "attacker with code execution now has a shell and package manager to explore, exfiltrate, or escalate with," and losing the `exec` convenience is the accepted, deliberate cost, not an oversight.

### Q6 — What's the actual difference between build-time scanning, registry scanning, and admission-time scanning?
**Testing:** whether the candidate sees scanning as a pipeline with distinct failure modes at each stage rather than a single checkbox.
**Answer:** Build-time scanning (Trivy/Grype/Snyk right after `docker build`) catches known CVEs as of that moment and can block the pipeline before push. Registry scanning re-checks already-pushed images periodically, catching newly disclosed CVEs in dependencies that haven't changed — an image clean on Monday can have a critical finding by Friday with no rebuild. Admission-time scanning/policy (Kyverno, OPA Gatekeeper) is the last gate, rejecting a deploy of an image missing a signature, SBOM, or passing scan result, which matters specifically because it catches the case where build-time scanning was skipped, bypassed, or the image was pushed by some other path entirely.
**Follow-up trap:** *"If build-time scanning already passed, is registry scanning redundant?"* — no: CVE databases update continuously and independently of your build cadence, so an unchanged image can transition from clean to vulnerable purely because a new CVE was published against a package version already baked in; only periodic re-scanning catches that.

### Q7 — Explain the xz-utils backdoor at a level that shows you understand why supply chain security tooling exists.
**Testing:** whether the "SBOM and signing" advice is grounded in a real incident or recited as buzzwords.
**Answer:** In March 2024, a maintainer identity that had spent roughly two years building trust in the xz-utils compression library project (used transitively by OpenSSH on many distributions via liblzma) inserted an obfuscated backdoor into the build scripts, engineered to activate specifically in distribution release-build environments rather than from-source builds, giving an attacker with the corresponding key remote code execution via sshd. It was caught before wide distribution, by a developer noticing unrelated performance regressions, not by any automated scanning — which is precisely the case for SBOMs and signing: an SBOM would have shown the dependency and version present, and signing/provenance attestation would have made "was this artifact built the way the public source claims" independently verifiable, neither of which existed as standard practice at the time for a project this deep in the dependency tree.
**Follow-up trap:** *"Would an SBOM alone have prevented this?"* — no, an SBOM tells you *what's in* the artifact, not whether the build process itself was compromised; that's what provenance attestation (SLSA-style, "built by this exact CI job from this exact commit") is for, and the two are complementary, not substitutes for each other.

### Q8 — Why is `docker exec ... rm /app/secret.txt` in a later layer not actually a fix for a secret baked into an earlier layer?
**Testing:** whether the candidate understands layer immutability at the content-addressing level, not just as a rule of thumb.
**Answer:** Layers are immutable and additive; a later layer's `rm` only affects the merged view a running container sees (via a whiteout file in overlay2 marking the path deleted in the upper layers), it doesn't remove or modify the earlier layer that actually wrote the secret to disk. That earlier layer is still a distinct, retrievable object in the image's layer list — `docker history`, or simply pulling the image and extracting/inspecting each layer tarball, recovers it in full.
**Follow-up trap:** *"So what's the actual remediation once this has happened and the image was pushed?"* — rebuild the image from scratch without the secret ever touching a layer (via `--mount=type=secret`), and rotate the leaked credential immediately — deleting or overwriting the tag in the registry does not retroactively secure anything that already had the vulnerable image pulled, cached, or scanned by a third party.

### Q9 — Your CI build takes 18 minutes. Diagnose the likely causes and fix them, using real numbers.
**Testing:** synthesis of cache correctness, cache persistence, and multi-stage separation as the three levers.
**Answer:** First check instruction ordering — if dependency install reruns on every build because a broad `COPY . .` precedes it, that's the single biggest lever; reordering alone can take a `pip install`/`npm install` from minutes to cache-hit speed. Second, check whether the CI runner is ephemeral with no persisted BuildKit cache — if so, local `--mount=type=cache` never gets a warm hit across separate jobs, and you need a remote cache backend (`--cache-to type=registry` or `type=gha`). Third, check whether the final image is still built from a single non-multi-stage Dockerfile carrying a full build toolchain into what gets pushed, which inflates push/pull time on top of build time. Combined, these commonly take a build from the ~20-minute range down to under 5.
**Follow-up trap:** *"You've fixed all three and it's still slow — what's left?"* — check whether the build context itself is huge (no `.dockerignore`, so `.git`, `node_modules`, or test fixtures get uploaded to the builder on every invocation even before any instruction runs) and whether platform emulation (QEMU cross-arch builds) is silently multiplying build time for architectures you don't actually need in that pipeline stage.

### Q10 — What's the practical difference between image signing and image scanning, and why do you need both?
**Testing:** whether they conflate "secure" with "vulnerability-free."
**Answer:** Scanning answers "does this image contain known-vulnerable software," a statement about content. Signing (cosign/Sigstore) answers "was this image built by the process I trust and has it been tampered with since," a statement about provenance and integrity, independent of content. An image can be perfectly clean of CVEs and still be an attacker's forged or tampered artifact if there's no way to verify who actually built it; conversely a signed, verifiably-authentic image can still ship a critical CVE if scanning wasn't run or was skipped.
**Follow-up trap:** *"If I only have budget to implement one, which first?"* — scanning, because vulnerable-dependency exposure is the far more common real-world incident source than supply-chain build tampering for most teams; signing becomes the priority once you're operating in a regulated environment or have specific evidence of targeted supply-chain risk (e.g., you're a high-value target, or a compliance framework mandates provenance attestation).

### Q11 — Why does `distroless/static` need almost no size at all, but `distroless/base` is meaningfully bigger?
**Testing:** understanding of static vs dynamic linking's effect on what the runtime environment must provide.
**Answer:** A statically linked binary (e.g., Go with `CGO_ENABLED=0`) has every library it needs compiled directly into the executable — the only runtime environment requirement is basic OS primitives like CA certificates and `/etc/passwd` entries for non-root execution, which is what `distroless/static` (~2MB) provides and nothing more. `distroless/base` additionally ships glibc and a handful of shared libraries for dynamically linked binaries that expect to `dlopen`/link against them at runtime, which is unavoidable overhead if the binary wasn't built statically.
**Follow-up trap:** *"Why not always build statically then, and always use `distroless/static`?"* — not every language/toolchain supports clean static linking (CGO-dependent Go code, most C/C++, and many interpreted-language native extensions genuinely need dynamic linking against system libraries), and forcing static linking where it's awkward can trade a build-complexity and correctness cost for a size win that's already small relative to the base image tiers above it.

### Q12 — Dockershim was removed from Kubernetes in 1.24 (2022) — what does that actually mean, and does it mean Kubernetes stopped supporting Docker-built images?
**Testing:** whether the candidate confuses the Docker *daemon/CLI* with the OCI *image format*, a common and telling confusion.
**Answer:** No — images are still images, built to the OCI image spec regardless of whether `docker build` or `buildx` or any other OCI-compliant builder produced them, and Kubernetes nodes run them fine. What changed is the *runtime* Kubernetes talks to on each node: dockershim was a compatibility shim letting kubelet drive the Docker daemon via CRI (Container Runtime Interface); its removal means nodes now run a CRI-native runtime directly (containerd or CRI-O), cutting out the Docker daemon as an unnecessary extra layer. Docker itself uses containerd under the hood already, so this was largely an architectural simplification, not a compatibility break for image consumers.
**Follow-up trap:** *"So does a developer running `docker build` locally need to change anything?"* — no, the build-side workflow is entirely unaffected; this is purely a node-runtime-internals change on the Kubernetes side, and it's a common interview trap because "Docker" colloquially refers to both the image format and the specific daemon/CLI, and conflating them is exactly the mistake this question is designed to surface.

### Q13 — How would you build one image that runs on both amd64 and arm64 nodes, and why would you need to?
**Testing:** practical multi-arch knowledge, relevant given Graviton/ARM cost savings pushing arm64 adoption.
**Answer:** `docker buildx build --platform linux/amd64,linux/arm64 -t myrepo/app:tag --push .` builds both architecture variants (via cross-compilation where the toolchain supports it, or QEMU emulation where it doesn't) and pushes a single multi-arch manifest list that the registry and container runtime resolve to the correct architecture-specific image automatically based on the pulling node's platform. The need is typically cost: ARM instances (AWS Graviton, for instance) are commonly 20-40% cheaper for equivalent throughput on well-suited workloads, and running a fleet on ARM requires images actually built for that architecture, not just "hoping x86 emulation is fast enough" in production.
**Follow-up trap:** *"What breaks if you skip `--platform` and just build normally on an Apple Silicon (arm64) laptop, then deploy to amd64 nodes?"* — the image is built for arm64 by default on an arm64 build host, and running it on amd64 nodes produces an immediate "exec format error" — the kernel can't execute a binary compiled for a different instruction set, and this is a very common first-encounter bug for anyone who started developing on Apple Silicon and deploys to x86 cloud infrastructure without ever specifying platform explicitly.

### Q14 — A security review flags 340 CVEs in your production image, several critical. Walk through your triage.
**Testing:** whether the candidate has an actual process versus panicking or dismissing the finding.
**Answer:** First, check the SBOM (or generate one if missing) to see exactly what package and version each finding is against, and whether it's an OS-level package inherited from the base image versus an application dependency you control directly. Second, check reachability — is the vulnerable code path actually invoked by this application, or is it dead weight from a full-distro base that a distroless/multi-stage rebuild would eliminate entirely without touching application code. Third, for anything that is a genuine risk, patch/upgrade the specific dependency; for anything confirmed unreachable, document a scoped, time-boxed exception rather than either ignoring it silently or blocking the pipeline indefinitely. In most cases, switching from a full-distro base to a minimal multi-stage + distroless final image resolves the overwhelming majority of these findings in one move, because most of the 340 are in OS packages the app never calls.
**Follow-up trap:** *"Is it acceptable to just suppress all 340 to unblock the release?"* — no, blanket suppression defeats the purpose of scanning entirely and is exactly the kind of finding that turns into a real incident later; a scoped exception with a documented reason and expiry for genuinely unreachable/false-positive findings is defensible, wholesale suppression to hit a deadline is a red flag an interviewer is specifically listening for.

### Q15 — What's the actual runtime cost difference between running many small containers versus fewer large ones, purely from an image/layer perspective?
**Testing:** understanding of layer deduplication and its effect on node-level pull/storage cost, a staff-level framing of "small images" beyond just "faster pulls."
**Answer:** Layers are content-addressed and shared across images and containers on the same node — if fifty services all build `FROM python:3.13-slim`, that base layer is stored and cached exactly once on a given node regardless of how many images reference it, so the marginal storage and pull cost of the 51st image sharing that base is just its own unique layers, not the whole image size. This is why standardizing on a small number of shared base images across a fleet (rather than every team picking its own base) compounds the multi-stage/distroless size win at the cluster level: new node bootstrap and pod scheduling both benefit from a warm, shared local layer cache.
**Follow-up trap:** *"Does this mean base image choice doesn't matter much once you're at scale, since it's shared anyway?"* — it still matters a great deal for the *first* pull on any given node (cold-start latency, e.g. during a scale-up event or node replacement) and for registry egress costs before local caching kicks in; layer sharing reduces steady-state marginal cost, it doesn't eliminate the cost of an oversized base entirely, especially in autoscaling environments cycling nodes frequently.

---

## Red flags that fail you

- Saying "use multi-stage builds" and "use distroless" without being able to explain what specifically each one removes and why that removal matters.
- Not knowing that a secret baked into an early layer is still present in the image even after a later layer "deletes" it.
- Recommending disabling or wholesale-suppressing a vulnerability scan to unblock a release, rather than triaging reachability and applying a scoped exception.
- Confusing the Docker daemon/CLI with the OCI image format, or claiming Kubernetes "doesn't support Docker images" post-dockershim-removal.
- Not knowing the difference between build-time, registry, and admission-time scanning, or treating scanning as a single one-time gate.
- Claiming Alpine is strictly better than distroless/slim without mentioning the musl/glibc compatibility risk for native-extension-heavy languages.
- Believing `--mount=type=cache` content ends up in the final image, or that cache mounts make a build reproducible.

---

## Cheat card

```
LAYER CACHE KEY = hash(instruction text + upstream layer key [+ content hash for COPY/ADD])
  -> order least-volatile to most-volatile: base, deps manifest, deps install, source last

BUILDKIT: default builder since Docker 23.0 (May 2023), DAG-parallel, was sequential before
  --mount=type=cache,target=<dir>   persistent build cache, NEVER in final image
  --mount=type=secret,id=<id>       secret only during that RUN, NEVER in a layer
  COPY --link                       decouples copy from upstream layer's cache state

MULTI-STAGE: FROM ... AS build ; FROM final-base ; COPY --from=build <artifact> <dest>
  only layers in the TARGET stage ship; unreferenced stages skipped by BuildKit

SIZE TIERS: scratch 0MB (static only) < distroless/static ~2MB < distroless/base ~20MB
            < alpine ~5MB (but musl != glibc) < debian-slim ~80MB
  distroless cuts CVE surface ~90% (no shell, no pkg manager)
  unoptimized full-OS image: 800MB-1.2GB -> multi-stage+distroless: <50MB typical

NO SHELL IN PROD -> debug via `kubectl debug -it <pod> --target=<container>` (ephemeral
                     debug container), NOT baking a shell back into the prod image

SCANNING: build-time (Trivy/Grype/Snyk) + registry re-scan (catches new CVEs, unchanged
          image) + admission-time policy (Kyverno/Gatekeeper block unsigned/unscanned)
SIGNING (cosign/Sigstore) proves WHO built it & no tampering; scanning proves WHAT's in it
  — need both, neither substitutes for the other. Ref incident: xz-utils backdoor, Mar 2024

CI TIME: reorder + remote cache (--cache-to/--cache-from type=registry|gha) + multi-stage
         => commonly ~20min builds down to <5min
```

## Sources

- [NFTables mode for kube-proxy](https://kubernetes.io/blog/2025/02/28/nftables-kube-proxy/) — accessed 2026-08-02 (kube-proxy context referenced across this track)
- [Slashing Image Size and CI Time: Multi-Stage Docker Build with Distroless and BuildKit — DevopsRoles](https://www.devopsroles.com/multi-stage-docker-build-slashing-image-size) — accessed 2026-08-02
- [30 Docker Interview Questions and Answers (2026) — Dataquest](https://www.dataquest.io/blog/docker-interview-questions-and-answers/) — accessed 2026-08-02
- [Docker Interview Questions 2026 — KodeKloud](https://kodekloud.com/blog/docker-interview-questions/) — accessed 2026-08-02
- Docker BuildKit official docs, `docs.docker.com/build/buildkit/` — cache and secret mount reference
- Google `distroless` project, `github.com/GoogleContainerTools/distroless` — image tiers and CVE-surface rationale
- xz-utils backdoor (CVE-2024-3094) public incident writeups, March 2024

## Changelog
- 2026-08-02 — created
