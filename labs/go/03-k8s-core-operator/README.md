# Lab 03: Writing a K8s Operator — the Reconcile Loop

**Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **XP:** 50
**Module:** `T12-k8s-core`

**You will build:** a reconciler for a fictional `Greeting` CRD in pure Go — no `k8s.io` imports, no network. The cluster is an in-memory, mutex-guarded `ClusterState`; the loop is the real one: fetch CR → validate → compare → create-or-update → update status → return.

**You will be able to answer:** *"Walk me through a Kubernetes reconcile loop. Why is it level-triggered rather than edge-triggered, and what breaks if it isn't idempotent?"*

## Setup

```bash
cd labs/go/03-k8s-core-operator
go test ./...                     # starter → FAILS on assertions. Make them pass.
go test -tags solution ./...      # reference → PASSES
go test -race ./...               # concurrency teeth (needs cgo: CGO_ENABLED=1 + gcc)
```

## The spec

1. **`Greeting` CRD** — `GreetingSpec{MessageTemplate, Replicas}` (desired) and `GreetingStatus{ReadyReplicas, Conditions}` (observed). `Replicas: 0` is valid (scale-to-zero); negative is invalid.
2. **`ClusterState`** — the simulated API server: maps of `Greeting`s and `Deployment`s, `sync.Mutex`-guarded, with `Get/Set/CreateOrUpdate` semantics and a `WriteCount()` that counts every write (your idempotency oracle).
3. **`Reconcile(ctx, name, cluster)`** — the loop, in order:
   1. Fetch the Greeting CR. **Not found → return `(Result{}, nil)`** — no error, no requeue. Deletion is handled by garbage collection via ownerReferences, not by the loop.
   2. Validate the spec. Negative `Replicas` → set condition `"Invalid"`, **do not create a deployment**, do not requeue (requeueing on invalid input hot-loops).
   3. Fetch the deployment. Missing, or drifted (`Replicas` or `Template` differ from spec) → create-or-update it.
   4. Update status: `ReadyReplicas = Replicas` (the simulation's deployments are instantly ready), append condition `"Synced"`.
   5. Return `Result{}` — empty result, no requeue; the watch will wake you when something changes.
4. **Idempotency** — the contract: a second `Reconcile` with unchanged state must perform **zero writes** (`WriteCount()` unchanged). This is what "level-triggered" buys you: events may be lost or duplicated, state cannot lie.
5. **Level-triggered semantics** — you never react to "someone changed the deployment"; you compare current state to desired state and close the gap. Drift (manual scale, template edit) is corrected on the next pass, whoever caused it.

## Run the tests

```bash
go test ./... -v                # against starter/ → FAILS. Make them pass.
```

To check the reference: `go test -tags solution ./... -v`

The switch is build tags on the test side: `starter_test.go` (`//go:build !solution`) and `solution_test.go` (`//go:build solution`) each set `newReconciler` to the starter's or the solution's constructor. The types (`ClusterState`, `Greeting`, `Reconciler`) live in the root package; the two implementations live in `starter/` and `solution/` (both also named `k8soperator`, mirroring real operators where the controller imports its API types package). Exactly one selector is compiled in per build.

## Stretch goals

1. **Exponential backoff requeue** — make a `FailingCluster` whose writes error transiently; return `Result{RequeueAfter: base * 2^attempt}` capped at a max, and reset on success. *(Interview: "what lives on the workqueue, and when does the rate limiter kick in?")*
2. **Finalizers** — add a `DeletionTimestamp` to `Greeting`; while set, run cleanup (delete the owned deployment) and only then remove the finalizer. *(Why can't garbage collection alone handle external resources like a DNS record?)*
3. **Status subresource rules** — forbid `SetGreeting` from changing `Spec` and `SetGreetingStatus` from touching `Spec`; split the methods like the real API server does. What RBAC does the controller need for each?
4. **Multiple owned objects** — the `Greeting` also owns a `Service`; reconcile both and keep two independent write counts. What ordering bugs appear when one create succeeds and the second fails mid-loop?
