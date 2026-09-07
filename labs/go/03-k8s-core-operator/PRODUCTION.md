# Production notes — the reconcile loop

## What you'd actually use

| Layer | Real thing | What it gives you |
|---|---|---|
| Framework | `controller-runtime` (kubebuilder/operator-sdk) | `Reconciler` interface, manager, workqueue wiring |
| Watches | informers (`client-go`) | local caches of API objects; events → key enqueued |
| Queue | `workqueue.DelayingInterface` | dedup by key, rate limiting, delayed requeues |
| CRDs | code-gen + CRD YAML from Go types | typed clients, deep copies, OpenAPI validation |
| Leader election | manager option | one active reconciler per cluster (leases) |

**Do not write a controller against the raw client-go list/watch API if you can avoid it.** controller-runtime exists precisely because hand-rolled informer wiring is where subtle bugs live. Naming raw client-go as your default is a red flag; naming it as "what controller-runtime abstracts" is a strong answer.

## The real loop: watch → workqueue → Reconcile

```
API server ──watch──▶ informer cache ──(add/update/delete handlers)──▶ workqueue ──▶ Reconcile(ctx, key)
```

The handlers never touch the object. They enqueue the **namespace/name key** — nothing else. Everything the handler knew may be stale by the time `Reconcile` runs; that's fine, because `Reconcile` re-fetches from the cache and acts on **state, not events**. That's the level-triggered principle: "make it look like X" beats "do X, Y, Z in order." Edge-triggered controllers break the moment an event is lost, duplicated, or delivered while you're mid-write.

**Why idempotency is non-negotiable:** the queue dedups keys but delivers no exactly-once guarantee. The same key can be processed twice for one change, or once for three changes. If reconcile had side effects that compound, you'd corrupt state; because it converges to desired state, replays are free — the second pass writes nothing (that's your `WriteCount` test).

**Missing-CR-is-not-an-error:** when a key's object is gone, you return `ctrl.Result{}` with `nil` error. Returning an error makes controller-runtime retry with backoff forever — hot-looping on a deleted object is a classic incident. Deletion is handled by garbage collection via ownerReferences; you only need a **finalizer** when you must clean up something *outside* the cluster (a DNS record, a cloud load balancer), because GC only knows about objects inside the API.

**Backoff:** returning an error requeues with exponential backoff (5ms doubling, default cap 1000s in controller-runtime, per `rate.NewItemExponentialFailureRateLimiter`). Returning `Result{RequeueAfter: d}` requeues on a timer without error semantics — use it for things that converge slowly (waiting for pods to be ready). Requeue on success only when you're waiting on something the watch can't see; `RequeueAfter` for readiness polling is normal, unconditional `Requeue: true` on success is usually a bug (it's a busy loop).

## What the real controller-runtime adds over your toy

- **Informer caches** — reads hit a local cache, not the API server. Without this, a big cluster's controllers would melt etcd; watches are the only thing keeping the API server cheap. Your `ClusterState` maps *are* this cache, minus the watch plumbing.
- **Leader election** — via Lease objects, so only one replica of your controller manager reconciles at a time. Two active leaders = fighting writes and flapping status.
- **Resync period** — informers periodically re-list and re-emit every object as a synthetic event. This is the safety net against missed watches: even if every event is lost, full resync forces a reconcile and drift is caught. Your "manual drift injection" test simulates what resync catches in production.
- **Status subresource** — `/status` is a separate endpoint with separate RBAC; writes to status can't clobber spec and vice versa. It also enables optimistic concurrency via resourceVersion so two controllers can't interleave a spec write and a status write.
- **Conflict retries** — the cache is slightly stale; API writes can 409. controller-runtime's `client.Update` doesn't auto-retry (kube's `retry.RetryOnConflict` is opt-in, unlike `controllerutil.CreateOrUpdate` patterns). Thinking "read, compare, write, on 409 loop again" is the job interview.
- **Event bubbling** — watch the Deployment too (via `Owns()`), map it back to the owner Greeting, enqueue the Greeting's key. Your controller doesn't just react to the CR — it reacts to the things it owns, by translating them back into CR keys.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Controller CPU pinned, API server hammered | `Requeue: true` on every success | Requeue only on pending work, or `RequeueAfter` |
| Object deleted, reconciler 404s in a loop | Returning an error on "not found" | `errors.IsNotFound` → empty result, nil error |
| Two pods of the manager fight over the same CR | No leader election | Enable it — always, even "single replica" deployments |
| Drift persists for minutes after a manual edit | Watch only on the CR type | `Owns()` the Deployment so owned-object changes re-enqueue |
| Stale cache causes 409s at high write volume | Update-then-retry pattern | `retry.RetryOnConflict`, or Server-Side Apply (`Apply` with field managers) |
| Operator memory grows unbounded | Watch cluster-wide with no namespace scoping | Scope watches to namespaces/labels; use `cache.SelectorsByObject` |
| Slow reconcile starves other keys | Long work in one reconcile (network calls, waiting) | Return `RequeueAfter` instead of blocking the worker goroutine |

## Cost & latency

A reconcile is cheap — cache reads and maybe one or two API writes — the expensive part is watch fan-in: every object you watch costs the API server a watch slot and the controller memory for its cache. Scope your watches or your operator is the thing that needs an operator. At the far end, a single controller can comfortably reconcile thousands of CRs per minute; when it can't, the answer is sharding by key or splitting into multiple controllers, not a faster loop.

## The 3 questions an interviewer asks after you describe this

1. *"Why does the event handler enqueue only a key, not the object?"* — dedup, and because the object would be stale by processing time; reconcile re-fetches. The key is the *address* of desired state, not a snapshot of it.
2. *"Your reconcile creates a deployment, then the process crashes before the status update. What happens on restart?"* — nothing bad: the next reconcile sees the deployment already matches, writes status, done. That's idempotency as a crash-recovery mechanism — you get exactly-once *effects* from at-least-once *execution*.
3. *"A kubectl-scaling to 5 gets reverted to 3 by your controller. How does the HPA work with that?"* — HPAs and controllers both must write spec.replicas; conflict is real. The production answers: the HPA owns the field (your operator writes minReplicas and lets HPA manage current), or you use `controllerutil`'s "ignore replica drift" pattern (`ScaleReplicas: nil` skip), or Server-Side Apply with field managers so each writer owns distinct subfields. Knowing "you can't both own the same subfield" is the point.
