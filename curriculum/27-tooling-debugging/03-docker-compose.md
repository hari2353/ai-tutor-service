# Compose for Local Stacks: Depends-On, Healthchecks, Profiles, Overrides

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 1.5h · **Prereqs:** T27-docker-essentials
> **Module id:** `T27-docker-compose` · **Tags:** docker

## The 30-second version

Compose's job is reproducing a multi-service dev environment from one declarative file, and the three things people get wrong are: `depends_on` without a `condition` only waits for the dependency's container to *start*, not to be *ready*, so a Postgres container reporting "running" while still initializing its data directory races your app's first connection; `healthcheck` plus `depends_on: condition: service_healthy` fixes that by making Compose actually poll readiness before starting the dependent service; and `docker-compose.override.yml` (loaded automatically alongside `docker-compose.yml`) is how you keep a shared base file clean while layering local-only settings (bind mounts, debug ports, extra env) without ever touching the checked-in file the whole team uses. Profiles (`profiles:` on a service, activated with `--profile <name>` or `COMPOSE_PROFILES`) let one file describe "core stack" plus optional pieces (a debug UI, a seed-data job) that don't start by default. None of this replaces Kubernetes; Compose's job stops at "runs correctly on one machine."

## Why this gets asked

Because "my Compose file works" and "my Compose file starts services in the right order and actually waits for them to be usable" are different claims, and almost every new engineer's first flaky-local-dev bug report is exactly this: the app container started before the database was accepting connections, failed once, and either crash-looped or silently misbehaved. The interviewer wants to know you've internalized that container *running* and service *ready* are different events.

---

## Lineage: past → present → future

**What came before.** Before Compose (originally Fig, 2014, acquired and rebranded by Docker in 2015), running a multi-container local stack meant a shell script chaining `docker run` commands with manually managed networking (`--link`, later removed) and manual ordering via `sleep 5` between commands — fragile, undocumented, and different on every developer's machine because the script itself drifted. The pain: onboarding a new engineer meant "here's a README with twelve docker run commands, good luck," and any change to the stack's shape required updating prose documentation that was reliably out of date within weeks.

**Where it stands now.** Compose v2 (rewritten in Go, integrated into the Docker CLI as `docker compose` rather than the standalone Python `docker-compose`) is effectively unchallenged for single-host, declarative local dev and small-scale deployments — the file format (Compose Specification) is now an open standard used beyond Docker itself. `depends_on` with `condition: service_healthy` plus a proper `healthcheck:` block is the settled, correct way to sequence startup; `sleep`-based hacks and application-level retry loops as the *only* mitigation are recognized as fragile, though many teams still layer retry logic in the app anyway as defense in depth since healthchecks reduce but don't eliminate race windows (a healthcheck passing doesn't guarantee the service stays healthy through the exact millisecond the dependent's first request arrives). The live disagreement is Compose's role once teams have Kubernetes for production: some argue for `docker compose` purely as a local-dev convenience layered on the same images, others push for tools like `kind`/`minikube`/`Tilt` locally so dev environments match production orchestration semantics exactly, accepting the extra complexity to avoid "works in Compose, breaks in k8s" surprises around things Compose doesn't model (resource requests, readiness vs. liveness distinctions, rolling updates).

**Where it's heading.** Compose Watch (file-sync and rebuild-on-change without a full `docker compose up` restart) is real and shipping, narrowing the gap with hot-reload-native dev tools. The broader trend is Compose files becoming a genuine interchange format consumed by tools beyond Docker (some Kubernetes-adjacent tools can translate Compose to k8s manifests as a starting point), but that translation is inherently lossy — Compose has no native concept of resource requests/limits shaped like k8s's, no rolling-update strategy, no multi-node scheduling — so "write once, run in Compose and k8s identically" remains aspirational rather than achieved, and is likely to stay that way given how different the two systems' actual jobs are.

---

## Mental model

```
docker-compose.yml (checked in, shared by the team)
  + docker-compose.override.yml (auto-loaded if present, git-ignored, local-only tweaks)
  + docker-compose.prod.yml (explicit, via -f, for a genuinely different environment)
  ---------------------------------------------------------------------------
  = final merged config Compose actually runs

STARTUP ORDERING (the part people get wrong)
  depends_on: [db]                        <- waits for db's CONTAINER to start, nothing more
  depends_on: {db: {condition: service_started}}     <- same as above, explicit
  depends_on: {db: {condition: service_healthy}}     <- waits for db's HEALTHCHECK to pass
  depends_on: {db: {condition: service_completed_successfully}}  <- for one-shot init/migration jobs

  db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s     <- how often to check
      timeout: 3s      <- how long one check attempt gets before counting as failed
      retries: 5       <- consecutive failures before marking unhealthy
      start_period: 10s <- grace period where failures don't count (slow cold start)

PROFILES (optional pieces of one file)
  services:
    app:            {}                        <- always starts
    debug-ui:       {profiles: ["debug"]}      <- only with --profile debug or COMPOSE_PROFILES=debug
    seed-data:      {profiles: ["seed"]}       <- one-shot, only when explicitly requested
```

The fact that resolves the most confusion: `depends_on` without a `condition` (or with `service_started`, which is the same thing) is a *start-order* hint, not a *readiness* guarantee — Compose considers its job done the instant the dependency's container process exists, regardless of whether the application inside it has finished booting, opened its listening socket, or run migrations.

## How it actually works

**Why plain `depends_on` isn't enough, mechanically.** `docker compose up` calls the container runtime to start each container in dependency order, and "started" for Compose's purposes means the process was launched — it does not poll anything about what that process does afterward. Postgres, for instance, does real work after its main process starts (initializing `PGDATA` on first run, replaying WAL on restart, etc.) during which it is not yet accepting connections on its listening socket; a dependent service that starts its first connection attempt immediately after `depends_on` is satisfied races this window and typically loses on a cold `docker compose up` on a slow machine, though it may reliably "work" on a fast machine where the race window happens to not matter — which is exactly why this class of bug is often first reported as "works on my machine, flaky in CI."

**`healthcheck` semantics, precisely.** Compose (and Docker generally) runs the `test:` command inside the container on the configured `interval`. A single failure doesn't flip status immediately — it takes `retries` consecutive failures to transition from `starting`/`healthy` to `unhealthy`, and `start_period` explicitly exempts the first N seconds from counting failures toward that threshold at all, which matters for services with a genuinely slow cold start (a JVM app with a multi-second classloading/warmup phase would otherwise flap to `unhealthy` before it's had a fair chance). `docker inspect --format='{{.State.Health.Status}}' <container>` shows the current status directly; `docker inspect --format='{{json .State.Health}}' <container>` shows the full log of recent check attempts, which is the actual debugging tool when a healthcheck is flapping and you need to see the last few real outputs, not just the current binary status.

**Override file merge semantics.** Compose merges `docker-compose.yml` and any auto-loaded `docker-compose.override.yml` (or explicit `-f base.yml -f override.yml` files, applied left to right) key by key: scalar values in a later file replace the earlier one, list values for most keys (like `ports`, `volumes`) are *appended*, not replaced, and `environment` entries merge by key with later files winning per-variable. This is why an override file adding one extra bind mount doesn't require repeating the base service's other volumes — but it also means a common mistake is expecting an override's `ports:` entry to *replace* the base file's port mapping when it actually adds an additional one.

## Build it from scratch

```yaml
# docker-compose.yml (checked in, shared)
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: devpass
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s
    volumes:
      - dbdata:/var/lib/postgresql/data

  migrate:
    image: myapp:latest
    command: ["python", "manage.py", "migrate"]
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    environment:
      DATABASE_URL: postgres://postgres:devpass@db:5432/postgres

  debug-ui:
    image: dpage/pgadmin4
    profiles: ["debug"]
    ports:
      - "5050:80"

volumes:
  dbdata:
```

```yaml
# docker-compose.override.yml (git-ignored, local-only, auto-loaded)
services:
  app:
    build:
      target: dev              # different Dockerfile stage locally
    volumes:
      - .:/app                 # live-reload bind mount, not wanted in the base/shared file
    ports:
      - "5678:5678"             # local debugger port, not part of the checked-in contract
```

```bash
docker compose up                          # base + override, automatically merged
docker compose --profile debug up          # also starts debug-ui
docker compose -f docker-compose.yml -f docker-compose.prod.yml up   # explicit prod overlay, no auto-override
docker compose config                      # print the fully merged, resolved config -- the real debugging tool
docker compose up --wait                   # blocks until all healthchecks report healthy, then returns
```

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| App container crashes on first start with a DB connection error, works fine on retry/restart | `depends_on` without `condition: service_healthy` — db container "started" but wasn't accepting connections yet | Add a `healthcheck` to the db service and `condition: service_healthy` on the dependent |
| Healthcheck flaps between healthy/unhealthy right after startup | `start_period` too short for a genuinely slow cold-start service (JVM warmup, large migration) | Increase `start_period`; confirm actual startup time first rather than guessing a number |
| Override file's `ports:` entry doesn't seem to replace the base file's port mapping | List-valued keys like `ports`/`volumes` are appended across merged files, not replaced | Don't rely on override to change a port mapping; remove/adjust it in the base file, or use `!reset`/`!override` merge directives (Compose Spec) if genuine replacement is needed |
| A service defined with `profiles:` never starts even with `docker compose up` | Profiles are opt-in; a service with any `profiles:` entry only starts when one of its listed profiles is explicitly activated | `docker compose --profile <name> up` or set `COMPOSE_PROFILES=<name>` |
| `docker compose up` on CI is flaky but identical config works locally | CI runners are frequently slower/more resource-constrained, widening the exact race window a missing/misconfigured healthcheck was masking locally | Fix the healthcheck/condition properly rather than adding a blanket `sleep`; use `docker compose up --wait` to fail fast if health never reached |
| `environment:` value from override isn't taking effect | Merge is per-key, but a `.env` file or shell-exported variable can also feed interpolation (`${VAR}`) inside the compose file itself, and precedence between those and an override's `environment:` block is a frequent source of "which value actually won" confusion | `docker compose config` to see the final resolved environment for each service, rather than guessing from the source files |

## Tradeoffs & when NOT to use it

- **Don't treat Compose as a production orchestrator.** It has no rolling updates, no multi-node scheduling, no native autoscaling, and its restart policies are far simpler than what Kubernetes offers — it's explicitly a single-host tool, and "just run Compose in prod" is a reasonable choice only for genuinely small, single-machine deployments where you've accepted that tradeoff explicitly, not a default.
- **Don't rely purely on `depends_on`/healthchecks and skip application-level connection retry logic.** A healthcheck passing at second T doesn't guarantee the dependency stays healthy through second T+1 when your app's first real request arrives (network blip, a dependency's own transient restart) — healthchecks reduce the race window, they don't eliminate the need for retry-with-backoff in the client.
- **Don't add `profiles:` to every optional service reflexively if your team is small and always wants the full stack running.** Profiles add a layer of "did you remember the right flag" friction that's worth it for genuinely optional heavyweight pieces (a debug UI, a data-seeding job) but not for services everyone always needs.
- **A `sleep N` between service starts is not a substitute for a real healthcheck**, even as a quick fix — it either underestimates real startup time under load (still flaky) or overestimates it (wastes real time on every single `up`), and it doesn't communicate anything to Compose's own dependency graph the way `condition: service_healthy` does.

---

## Interview questions

### Q1 — What does `depends_on` guarantee, and what does it not guarantee?
**Testing:** the single most common Compose misconception.
**Answer:** Plain `depends_on` (or `condition: service_started`, the default) guarantees only that Compose starts the dependency's container before the dependent's — it says nothing about whether the application inside that container has finished initializing or is accepting connections/requests yet.
**Follow-up trap:** *"Your app connects to Postgres immediately on startup and depends_on lists db. It works locally every time but fails intermittently in CI. Why?"* — CI machines are frequently slower/more loaded, widening the window between Postgres's container starting and it actually accepting connections (data directory init, WAL replay); the fix is a proper `healthcheck` on db plus `condition: service_healthy` on the dependent, not blaming CI flakiness generically.

### Q2 — Walk through the exact healthcheck fields and what each does.
**Answer:** `test` is the command run inside the container to determine health; `interval` is the time between checks; `timeout` is how long a single check attempt gets before it's counted as a failure; `retries` is how many consecutive failures are required before the status flips to `unhealthy`; `start_period` is a grace window at the start where failures don't count toward that threshold at all, protecting services with a genuinely slow cold start from being marked unhealthy prematurely.
**Follow-up trap:** *"Your service's healthcheck flaps between healthy and unhealthy specifically during its first 15 seconds after a cold start, but is rock solid afterward. What's the single most likely fix?"* — increase `start_period` to comfortably exceed the measured real cold-start time, rather than adjusting `retries`/`interval`, which would affect steady-state flapping detection too and mask a genuine post-startup problem if one appears later.

### Q3 — You add a `ports:` entry in `docker-compose.override.yml` expecting it to replace the base file's port mapping, but the container ends up with both ports mapped. Why?
**Answer:** Compose merges list-valued keys like `ports` and `volumes` by concatenation across merged files, not replacement — the override's entry is additive, not a substitution. Scalar keys (like `image` or `restart`) do get replaced by a later file's value; list keys generally don't, without an explicit reset directive.
**Follow-up trap:** *"How would you actually force a genuine replacement rather than an addition, if the Compose Specification supports it?"* — the Compose Specification's merge directives (`!reset`/`!override` in newer spec versions) allow explicitly replacing rather than merging a specific key; absent that, the practical fix is not duplicating the value in the base file at all and only ever setting it in whichever file should own it.

### Q4 — What's the actual difference between `docker-compose.override.yml` and an explicitly named file passed via `-f`?
**Answer:** `docker-compose.override.yml` is auto-loaded by Compose alongside the base `docker-compose.yml` whenever it's present in the same directory, with zero explicit flags needed — it's designed for git-ignored, developer-local tweaks. A file like `docker-compose.prod.yml` requires an explicit `-f docker-compose.yml -f docker-compose.prod.yml` invocation; it's the mechanism for intentional, named environment overlays (staging, prod) that you don't want silently applied by accident.
**Follow-up trap:** *"A teammate accidentally commits their docker-compose.override.yml with local debug ports, and now everyone running plain `docker compose up` gets those debug ports exposed. What's the actual process fix, not just 'don't commit it'?"* — add `docker-compose.override.yml` to `.gitignore` from the start of the project and provide a checked-in `docker-compose.override.yml.example` template for developers to copy locally, so the mechanism designed for local-only config can't silently leak into the shared file by accident.

### Q5 — Explain `profiles:` and give a real reason to use them instead of just always running every service.
**Answer:** `services.<name>.profiles: [<names>]` marks a service as opt-in — it only starts when `docker compose up --profile <name>` or `COMPOSE_PROFILES=<name>` explicitly activates one of its listed profiles; without that, `docker compose up` skips it entirely. Real use: a heavyweight debug UI (pgAdmin, a metrics dashboard) or a one-shot data-seeding job that most developers don't need running by default but some do, without maintaining two separate Compose files.
**Follow-up trap:** *"A service with `profiles: [debug]` also has another service `depends_on` it unconditionally. What happens?"* — Compose will still attempt to start the dependency, effectively activating it implicitly even without its profile being requested, because `depends_on` on a running service forces its dependencies up regardless of profile gating — a genuinely confusing edge case worth testing explicitly rather than assuming profile isolation is airtight.

### Q6 — How do you debug "which config is Compose actually using" when base + override + `-f` files and `.env` interpolation are all in play?
**Answer:** `docker compose config` prints the fully merged, resolved configuration exactly as Compose will use it — all files merged, all `${VAR}` interpolation resolved — which is the authoritative source of truth over reading the individual YAML files and mentally merging them.
**Follow-up trap:** *"`docker compose config` shows the environment variable you expect, but the running container's actual `printenv` shows something different. What else could be overriding it?"* — the image's own `ENV` instructions baked in at build time, or an `env_file:`/`environment:` entry the application itself further overrides at process startup (e.g., a `.env` file loaded by the app's own config library inside the container) — `docker compose config` shows what Compose *passes in*, not necessarily what the process inside ultimately uses if the app has its own environment-loading logic.

### Q7 — Why might a `sleep 5` between starting the db and the app "work" for months and then suddenly start failing?
**Answer:** A fixed sleep is a bet on the dependency's cold-start time staying under that threshold; anything that slows startup (a larger dataset needing longer WAL replay, a busier host, a slightly heavier image pull, a resource-constrained CI runner) can push actual readiness past the hardcoded sleep window without any code change at all, which is exactly why it "worked" for months and then didn't — the underlying race was always there, just usually not triggered.
**Follow-up trap:** *"How would you prove that's actually what happened, after the fact, from logs?"* — correlate the app's connection-failure timestamp against the db container's own startup/ready log line timestamp; if the app's first connection attempt timestamp is earlier than the db's actual "ready to accept connections" log line, that's direct proof of the race, independent of theorizing about what changed.

### Q8 — What does `docker compose up --wait` do, and why is it useful in CI specifically?
**Answer:** It blocks the `up` command itself until every service with a healthcheck reports healthy (or times out), returning a non-zero exit code if any service never becomes healthy, instead of returning immediately once containers are merely started. In CI, this converts a race condition that would otherwise manifest as an intermittently failing subsequent test step into a clear, immediate, correctly-attributed failure of the `up` step itself.
**Follow-up trap:** *"A service has no healthcheck defined at all. What does `--wait` do for it?"* — a service without a `healthcheck` is considered "healthy" the instant it starts (Compose has nothing to poll), so `--wait` provides zero additional readiness guarantee for that service specifically — the fix is adding a real healthcheck, not assuming `--wait` alone solves the readiness problem for every service in the file.

### Q9 — A one-shot database migration service needs to run to completion before the app starts, but `condition: service_healthy` doesn't apply to a job that just exits. What do you use?
**Answer:** `condition: service_completed_successfully`, which waits for the dependency container to exit with status code 0 rather than polling a healthcheck — the correct mechanism specifically for init/migration/seed jobs that are expected to run once and terminate, as opposed to long-running services that stay up.
**Follow-up trap:** *"The migration container exits with code 0 but the migration actually failed silently (a caught exception that didn't propagate as a non-zero exit). What does Compose do, and how do you prevent this class of bug?"* — Compose considers the dependency satisfied since exit code 0 is all it checks; it has no way to know the job's internal logic actually failed. Prevention is at the application level: ensure migration scripts propagate real failures as non-zero exit codes rather than swallowing exceptions, since Compose's dependency mechanism can only ever be as accurate as the exit code it's given.

### Q10 — Compare Compose's `restart` policies and explain a case where the default is wrong.
**Answer:** Compose supports `no` (default, never restart), `always` (always restart regardless of exit reason, including manual stops), `on-failure[:max-retries]` (restart only on non-zero exit, optionally capped), and `unless-stopped` (restart on failure or daemon restart, but not after an explicit manual stop). The default (`no`) is wrong for any long-running service you actually want resilient to crashes in local dev — a database container that crashes once and then simply stays down silently is a worse debugging experience than one that restarts and re-surfaces the same error in logs on a loop, which is itself useful signal.
**Follow-up trap:** *"You set `restart: always` on a service that's crash-looping due to a genuine misconfiguration. What does that do to your ability to diagnose it, and what would you use instead?"* — `restart: always` can create a rapid crash-restart loop that floods `docker compose logs` and makes it hard to isolate a single failure's actual error output; `on-failure:3` (or a similarly bounded retry count) or manually stopping the restart loop (`docker compose stop <service>`) to read one clean failure's logs is the more practical debugging approach than an unbounded restart policy during active diagnosis.

---

## Red flags that fail you

- Believing `depends_on` alone guarantees the dependency is ready to serve requests.
- Not knowing `healthcheck`'s `retries`/`start_period` distinction, or proposing to "just add a sleep" as the real fix.
- Assuming an override file's list-valued keys (`ports`, `volumes`) replace rather than append to the base file's values.
- Not knowing `profiles:` exists and proposing two entirely separate Compose files to solve "optional services" instead.
- Treating Compose as production-ready orchestration without naming what it's missing (rolling updates, multi-node scheduling, autoscaling).

## Cheat card

```
depends_on: [db]                       -- waits for CONTAINER START only, NOT readiness
depends_on: {db: {condition: service_healthy}}              -- waits for healthcheck to pass
depends_on: {db: {condition: service_completed_successfully}} -- waits for exit 0 (migration/seed jobs)

healthcheck:
  test: [...]        the check command
  interval: 5s        time between checks
  timeout: 3s         time one check attempt gets before counting as failed
  retries: 5          consecutive failures before -> unhealthy
  start_period: 10s   grace window, failures don't count here (slow cold start)

docker-compose.yml (checked in) + docker-compose.override.yml (auto-loaded, git-ignore this)
  -f a.yml -f b.yml -- explicit named overlays, applied left to right
  MERGE: scalars replace, LISTS (ports/volumes) APPEND across files -- common gotcha

profiles: [debug]  on a service -> only starts w/ --profile debug or COMPOSE_PROFILES=debug
  gotcha: an unconditional depends_on can still force-start a profiled service

docker compose config      -- print fully merged/resolved config, the real debugging tool
docker compose up --wait   -- blocks until healthy, fails fast; no-op for services w/o healthcheck

restart: no (default) | always | on-failure[:N] | unless-stopped
  restart: always during active debugging = crash-loop flooding logs, hard to isolate one failure
```

## Sources

- [How to Use Docker Compose depends_on with Health Checks — OneUptime](https://oneuptime.com/blog/post/2026-01-16-docker-compose-depends-on-healthcheck/view) — accessed 2026-07-26
- [Docker Compose Healthcheck: Setup, Examples & Best Practices — Last9](https://last9.io/blog/docker-compose-health-checks/) — accessed 2026-07-26
- [Advanced Docker Compose: Using Profiles, extends, and depends_on — Medium](https://medium.com/@akaashhazarika/advanced-docker-compose-using-profiles-extends-and-depends-on-6f336f56f2de) — accessed 2026-07-26
- [Docker Compose v2 Tutorial 2026 — tutorials.technology](https://tutorials.technology/tutorials/docker-compose-v2-tutorial-2026.html) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
