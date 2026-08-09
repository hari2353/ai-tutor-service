# Kubernetes: Control Plane, etcd, Scheduler, Reconcile Loop, Writing an Operator

> **Track:** T12 DevOps, Infra & Security · **Time:** 3h · **Prereqs:** T12-k8s-objects · **Updated:** 2026-08-02
> **Module id:** `T12-k8s-core` · **Tags:** k8s, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

The control plane is four cooperating processes: the API server (the only component that writes to etcd, stateless and horizontally scalable, enforcing an admission-control chain before anything is persisted), etcd (a Raft-consensus key-value store requiring a quorum majority to accept writes, which is why production clusters run 3 or 5 nodes — never an even number, since 4 tolerates exactly as many failures as 3 but costs more), the scheduler (a two-phase Filter-then-Score pipeline across roughly ten extension points that picks a node for each unscheduled pod), and the controller manager (a bundle of independent reconcile loops, one per built-in resource type). Every controller — built-in or a custom operator watching a CRD — follows the same pattern: an informer watches the API server via a long-lived list-and-watch connection, pushes changed object *keys* (not full objects) onto a workqueue, and worker goroutines pop keys off and call a `Reconcile(ctx, req)` function that re-fetches current state and drives it toward desired state. This is level-triggered, not edge-triggered — the function must be idempotent and safe to call repeatedly with no new information, because events get coalesced, dropped, and replayed, and the entire system's correctness depends on every reconciler tolerating that. Writing an operator means defining a CRD (a schema extension registered with the API server) and a controller that encodes domain-specific operational knowledge the built-in controllers don't have — which is the actual justification for building one at all, not "we wanted a nicer YAML API."

## Why this gets asked

Because "how does Kubernetes actually work" separates people who've read the architecture diagram from people who've debugged an etcd quorum loss at 3am, watched a misbehaving controller hammer the API server with a self-triggering reconcile loop, or had to explain why a pod sat `Pending` for ten minutes with a scheduling error that made no sense until they read the per-plugin `FailedScheduling` event breakdown. The interviewer wants to know whether "the reconcile loop" is a phrase you can define precisely — informer, workqueue, idempotency, level-triggered — or a term you've heard used in three different blog posts and can gesture at vaguely. This is also the module that separates "uses Kubernetes" from "could operate the control plane itself or build a real operator," which is exactly the line staff/principal infra interviews are drawn on.

---

## Lineage: past → present → future

**What came before.** Kubernetes's design (announced 2014, drawing directly on Google's internal Borg and its successor Omega, both predating the public project by years) was a deliberate reaction to the failure mode of imperative infrastructure automation — Puppet/Chef-style config management and hand-rolled deployment scripts that encoded *steps* ("run this command, then that one") rather than *desired state*. The pain that killed the imperative model at Google's scale was partial failure: a multi-step imperative script that dies halfway through leaves the system in an undefined intermediate state, and recovering requires knowing exactly which step it died on — brittle, and worse under concurrent operators or flapping infrastructure. Borg's engineers learned this the hard way over years of production incidents, and Kubernetes's core architectural bet — every controller declares "make reality look like this spec" and re-derives the necessary actions from scratch on every invocation, never remembering "what step I'm on" — is a direct, named response to that failure mode.

**Where it stands now.** etcd plus Raft consensus is the near-universal substrate for cluster state, though it's not the only option in practice — K3s and other lightweight distributions use "kine," a shim that lets the API server talk to Postgres, MySQL, or even SQLite instead of etcd, specifically for edge and resource-constrained deployments where running a dedicated etcd cluster is disproportionate overhead. The scheduler's extension model settled on the Scheduling Framework (KEP-624), which replaced the older, clunkier "scheduler extender" webhook mechanism (pre-1.15) with in-process plugins at roughly ten defined extension points (QueueSort, PreFilter, Filter, PostFilter, PreScore, Score, Reserve, Permit, PreBind, Bind, PostBind) — a typical kube-scheduler installation ships around fourteen in-tree Filter plugins and nine in-tree Score plugins covering the common cases (resource fit, affinity, topology spread, taints), with custom logic added as additional framework plugins compiled into a custom scheduler binary rather than external webhook calls, which is dramatically faster since it avoids a network round-trip per scheduling decision. The live disagreement in the ecosystem isn't about these mechanics — they're settled — it's about operator sprawl: plenty of platform teams have watched CRD-and-controller pairs proliferate for things that didn't need the operational complexity of "a controller that must itself be run, monitored, and kept correct," when a ConfigMap and a Deployment would have done the job with far less to maintain.

**Where it's heading.** The operator pattern is expanding beyond application lifecycle management into infrastructure provisioning itself — tools like Crossplane treat cloud resources (an RDS instance, an S3 bucket) as CRDs reconciled by a controller calling cloud provider APIs, extending "desired state reconciliation" to infrastructure that used to live exclusively in Terraform's plan/apply model. Scheduler extensions for AI/ML workloads (gang scheduling — all-or-nothing placement for a distributed training job, topology-aware GPU placement) are an active area of development because the default scheduler's per-pod, independent-decision model doesn't natively express "these 8 pods must land together or not at all," a real and growing gap as GPU-heavy workloads become common (this connects directly to the scaling module's GPU scheduling section). Multi-cluster control planes (Cluster API, Karmada) treating "a cluster" itself as a reconciled custom resource are maturing but still meaningfully less standardized than single-cluster operations — confidence here is moderate, this is a genuinely less settled area than the rest of this module.

---

## Mental model

```
                         ┌─────────────────────────────┐
  kubectl apply  ──────> │         API SERVER            │ <──── only component
                         │  (stateless, admission chain) │      that writes to etcd
                         └───────────┬────────────────────┘
                                     │  writes (via optimistic concurrency,
                                     │  resourceVersion check)
                                     ▼
                         ┌─────────────────────────────┐
                         │   ETCD (Raft consensus KV)    │
                         │   quorum = floor(n/2)+1        │
                         │   3 nodes tolerate 1 failure   │
                         │   5 nodes tolerate 2 failures  │
                         └─────────────────────────────┘

        list+watch                              list+watch
             │                                        │
             ▼                                        ▼
   ┌───────────────────┐                  ┌──────────────────────┐
   │   SCHEDULER          │                  │  CONTROLLER MANAGER     │
   │  watches unscheduled  │                  │  (Deployment, RS, Job,  │
   │  pods, runs Filter →   │                  │   Node, etc. controllers│
   │  Score → Bind          │                  │   — each an independent │
   └───────────────────┘                  │   reconcile loop)        │
                                            └──────────────────────┘
             │                                        │
             ▼                                        ▼
   node gets pod assignment              desired state driven toward reality
   (kubelet on that node picks           (create/update/delete calls back
    it up via its own watch)              through the API server)
```

The insight that matters: **nothing in this diagram talks to etcd except the API server**, and nothing talks to each other directly — the scheduler doesn't call the controller manager, controllers don't call kubelet. Every component only watches the API server and writes back through it. This single-writer, watch-everything-else model is what makes the whole system's consistency story tractable.

---

## How it actually works

### The API server — the only door to etcd

Every write to cluster state goes through the API server's admission chain: authentication, authorization (RBAC), mutating admission webhooks (can modify the object — e.g. injecting a sidecar), schema validation, then validating admission webhooks (can only accept/reject, not modify), and finally the write to etcd. Reads and writes use **optimistic concurrency** via `resourceVersion`: every object carries a version stamp from etcd's MVCC revision counter, and an update must include the version it was read at — if another writer updated the object in between, the API server returns **HTTP 409 Conflict**, and the client is expected to re-fetch and retry rather than blindly overwrite. This is why every well-behaved controller's update loop is "get, modify, update-with-conflict-retry," not "blindly PUT."

### etcd — Raft, quorum, and why odd numbers

etcd achieves consistency via the Raft consensus algorithm: one node is elected leader, all writes go through it, and a write is only acknowledged once a **majority (quorum) of nodes** have persisted it to their write-ahead log. Quorum size is `floor(n/2) + 1`. A 3-node cluster needs 2 nodes to agree and tolerates **1** node failure before losing quorum (and thus losing the ability to accept writes at all — reads may still work in a degraded mode depending on configuration, but writes stop). A 5-node cluster needs 3 and tolerates **2** failures. A 4-node cluster needs 3 to agree — the exact same fault tolerance as a 3-node cluster (still only 1 failure survivable) but with more nodes to pay for and more replication overhead, which is precisely why production topologies are always odd-sized, standard practice being 3 for most clusters and 5 for clusters where surviving 2 simultaneous node failures (e.g., a full availability-zone outage plus one more) is a real requirement.

etcd's performance is dominated by disk fsync latency, not CPU or memory — every write must be durably fsynced to the WAL before it can be acknowledged as part of a Raft-committed entry, so etcd on spinning disks or noisy-neighbor network storage degrades badly under load. `etcd_disk_wal_fsync_duration_seconds` climbing past roughly **10ms** is the standard early-warning threshold operators watch for — well before it manifests as visible API server latency, because API server request latency for any write is directly downstream of etcd's commit latency. etcd also enforces a backend size quota (`--quota-backend-bytes`, defaulting to **2GB**) — exceeding it puts etcd into an alarm state that **rejects all further writes** with `mvcc: database space exceeded` until the database is compacted (removing old MVCC revisions) and defragmented (reclaiming the freed space at the storage-engine level, since compaction alone doesn't shrink the on-disk file); production guidance for larger clusters commonly raises the quota but still recommends keeping the working set well under roughly 8GB even with the override, since etcd fundamentally isn't designed to be a general-purpose large-object store.

### The scheduler — Filter, then Score, then Bind

For each unscheduled pod, the scheduler runs every eligible node through two sequential phases:

1. **Filter** (formerly called "predicates" in pre-framework Kubernetes): each Filter plugin either passes or rejects a node outright — `NodeResourcesFit` (does the node have enough allocatable CPU/memory left), `NodeAffinity`/`NodeSelector`, taints/tolerations, `PodTopologySpread` constraints. A node failing *any* Filter plugin is dropped entirely and never reaches Score. A typical installation ships around **14 in-tree Filter plugins**.
2. **Score**: every node that survived Filter gets scored 0-100 by each Score plugin — `NodeResourcesBalancedAllocation` (prefers nodes that keep CPU/memory usage ratios balanced), `ImageLocality` (prefers nodes that already have the pod's image cached, since that avoids a pull), `InterPodAffinity` — roughly **9 in-tree Score plugins**, each with a configurable weight, summed into a final per-node score, and the highest-scoring node wins (ties broken pseudo-randomly to spread load).

If **no** node survives Filter, `PostFilter` runs — this is where **preemption** happens: the scheduler looks for lower-`priorityClassValue` pods on some node whose eviction would free up enough room for the pending higher-priority pod, and if it finds a viable victim set, evicts them and retries scheduling. `Bind` is itself an API call (creating a `Binding` subresource that sets `pod.spec.nodeName`), which is why a slow or overloaded API server directly slows down scheduling even after a node decision has already been made in memory.

### The reconcile loop — informers, workqueues, idempotency

```go
// untested sketch — the shape of every controller-runtime Reconcile function
func (r *WidgetReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. Fetch CURRENT state fresh — req only carries namespace/name, never the object itself,
    //    because the object may have changed again since the event that enqueued this key.
    var widget myv1.Widget
    if err := r.Get(ctx, req.NamespacedName, &widget); err != nil {
        if apierrors.IsNotFound(err) {
            return ctrl.Result{}, nil // object deleted, nothing to reconcile
        }
        return ctrl.Result{}, err // will be requeued with backoff
    }

    // 2. Handle deletion via a finalizer, BEFORE the object is actually gone
    if !widget.DeletionTimestamp.IsZero() {
        return r.cleanupExternalResources(ctx, &widget)
    }

    // 3. Compute desired state and diff against observed state — idempotent by construction:
    //    calling this twice with unchanged input produces the same calls, or no calls at all.
    desired := buildDesiredDeployment(&widget)
    var current appsv1.Deployment
    err := r.Get(ctx, client.ObjectKeyFromObject(desired), &current)
    if apierrors.IsNotFound(err) {
        return ctrl.Result{}, r.Create(ctx, desired)
    }
    if !equality.Semantic.DeepEqual(current.Spec, desired.Spec) {
        current.Spec = desired.Spec
        return ctrl.Result{}, r.Update(ctx, &current)
    }

    // 4. Update status ONLY if it actually changed — updating unconditionally
    //    triggers a new watch event on the object, which re-enqueues it, which
    //    calls Reconcile again, which updates status again — an infinite self-triggered loop.
    newStatus := computeStatus(&current)
    if !equality.Semantic.DeepEqual(widget.Status, newStatus) {
        widget.Status = newStatus
        return ctrl.Result{}, r.Status().Update(ctx, &widget)
    }
    return ctrl.Result{}, nil
}
```

Mechanically: an **informer** opens a long-lived `list` (get everything now) followed by a `watch` (stream of subsequent changes, identified by resourceVersion) against the API server, populates a local in-memory cache (so reads inside Reconcile can be served from cache rather than hitting the API server every time), and on any add/update/delete event, enqueues the object's namespace/name into a **workqueue**. Worker goroutines dequeue keys (not objects — deliberately, so a rapid burst of updates to the same object collapses into a single dequeued key rather than processing every intermediate state) and call `Reconcile`. This is **level-triggered**: the function is handed "something about this object changed, go figure out what's true now," not "here is what changed." That's the reason idempotency is non-negotiable — the same key can be dequeued multiple times for the same underlying change (at-least-once delivery), after a controller restart with no memory of prior state, or speculatively on a resync interval even with no real change at all.

`.spec` describes desired state and should never be interpreted as an imperative instruction ("scale up by 2") — it must be re-readable at any point and mean the same thing. `.status` must be **computed from observation**, never trusted as remembered intent, because the controller process can restart and lose any in-memory state at any time, and on restart it has nothing but the current cluster state to reconstruct from.

### CRDs and operators, precisely

A **Custom Resource Definition** registers a new API type with the API server — schema (OpenAPI v3 validation), versioning, subresources (`status`, `scale`) — with zero behavior attached; the API server will happily store and serve `MyWidget` objects with no controller running at all, they just sit there inert. An **operator** is the pairing of a CRD with a controller that actually reconciles it, encoding domain-specific operational knowledge — a Postgres operator's controller knows how to safely promote a replica during a primary failure, which a bare StatefulSet spec fundamentally cannot express. "Controller" is the general term (built-in controllers reconcile built-in types); "operator" specifically means a controller for a *custom* resource type, usually one deep enough to encode real operational logic rather than trivial CRUD.

---

## Build it from scratch

The minimal operator scaffold that proves the reconcile-loop concepts above are understood in code, using kubebuilder's standard project shape:

```yaml
# untested sketch — CRD registering the custom type
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: widgets.example.com
spec:
  group: example.com
  names: { kind: Widget, plural: widgets }
  scope: Namespaced
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              replicas: { type: integer, minimum: 1 }
          status:
            type: object
            properties:
              readyReplicas: { type: integer }
    subresources:
      status: {}   # separate status subresource — spec updates and status updates
                    # go through different API calls, preventing a status write from
                    # accidentally clobbering a concurrent spec change
```

```go
// untested sketch — SetupWithManager wiring, showing what actually drives the workqueue
func (r *WidgetReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&myv1.Widget{}).           // primary watch: any Widget change enqueues its key
        Owns(&appsv1.Deployment{}).    // secondary watch: a change to a Deployment THIS
                                         // controller created also re-enqueues the owning Widget
        Complete(r)
}
```

`Owns()` is the mechanism that makes a controller react to changes in resources *it manages*, not just the primary CRD — if someone manually edits the Deployment a Widget created, that edit's watch event resolves back to the owning Widget's key via owner references, and `Reconcile` runs again, sees the drift, and corrects it. This is the concrete mechanism behind "Kubernetes self-heals": every controller continuously re-asserts its desired state against any observed drift, including drift caused by a human with `kubectl edit`. (Python teams commonly reach for Kopf instead of Go/kubebuilder for lighter-weight operators — same reconcile-loop concepts, a decorator-based API instead of a generated scaffold — but Go plus controller-runtime/kubebuilder remains the ecosystem standard for anything intended for wide production use, in large part because most CRD ecosystems and reference implementations are written against it.)

---

## How it's done in production

Kubebuilder and Operator SDK scaffold the boilerplate (CRD generation from Go type annotations, RBAC manifest generation, webhook wiring) so hand-written reconcile logic is the actual differentiated code. Any controller with more than one replica for HA **must** use leader election (`controller-runtime` provides this as a flag) — without it, every replica's informer fires independently and multiple replicas reconcile the same object concurrently, producing conflicting writes and wasted API server load; with it, only the elected leader (tracked via a Lease object, itself just another API resource with a renewal deadline) actively reconciles, and the others sit idle ready to take over on leader failure. **Finalizers** (a string in `metadata.finalizers`) are how a controller ensures cleanup happens *before* an object is actually removed from etcd — deleting an object with a finalizer present doesn't delete it, it sets `deletionTimestamp` and leaves the object visible until every finalizer is removed by its owning controller, which is what lets an operator, say, deprovision an external cloud resource before letting Kubernetes finish deleting the CRD instance that represented it.

| Symptom | Cause | Fix |
|---|---|---|
| API server returns `mvcc: database space exceeded`, writes rejected cluster-wide | etcd hit its backend size quota (default 2GB) and entered an alarm state | Compact old MVCC revisions and defragment the etcd data files; raise `--quota-backend-bytes` deliberately if the working set genuinely needs it, but investigate what's bloating the DB first (often unbounded Events or excessive CRD instance churn) |
| API server request latency spikes cluster-wide, timeouts on writes | etcd disk fsync latency degraded (slow/contended storage) | Check `etcd_disk_wal_fsync_duration_seconds`; move etcd to dedicated fast (SSD/NVMe) storage, isolate it from noisy-neighbor I/O contention |
| Pods stuck `Pending` with a confusing `FailedScheduling` message | One or more Filter plugins rejecting every node (insufficient resources, affinity/anti-affinity, taints without tolerations, topology spread unsatisfiable) | `kubectl describe pod` for the per-plugin filter failure breakdown in the event message, not just the summary line; check node resource headroom and affinity rules directly |
| A custom controller is hammering the API server, high CPU/write load with no obvious cause | `Reconcile` updates `.status` (or any field) unconditionally every call, which itself generates a watch event that re-enqueues the object — a self-triggering infinite loop | Compare current vs desired/computed state with a semantic deep-equal before calling `Update`/`Status().Update()`; only write when something actually changed |
| Two replicas of the same operator making conflicting changes to the same object | No leader election configured, both replicas' informers and reconcile loops are active simultaneously | Enable leader election (`--leader-elect` / the controller-runtime manager option); confirm only one replica holds the Lease at a time |
| A CRD instance can't be deleted, `kubectl delete` hangs indefinitely | A finalizer is present and its owning controller either isn't running or is erroring out of the cleanup path, so the finalizer never gets removed | Check controller logs for the reconcile error blocking cleanup; as a last resort (accepting orphaned external resources) manually `kubectl patch` the finalizers list to empty, but treat this as a real bug to fix, not routine practice |
| Scheduler makes a placement decision but the pod sits `Pending` for several extra seconds regardless | `Bind` is itself an API server write; a slow or overloaded API server delays the bind call even after the in-memory scheduling decision is already made | This is a real (if usually minor) cost of the single-writer model; investigate API server load/latency separately from scheduler logic if bind latency specifically is the bottleneck |

---

## Tradeoffs & when NOT to use it

- **Don't build a CRD-and-controller pair for something a ConfigMap and a Deployment already handle.** A custom controller is a new distributed system you now have to run, monitor, and keep correct forever — "operator sprawl" (dozens of thin, barely-differentiated operators across a platform team) is a real, named anti-pattern, and the honest bar is "does this encode operational knowledge a built-in resource genuinely can't express," not "would a custom YAML schema be nicer to look at."
- **Don't treat etcd as a general-purpose datastore for application data.** It's tuned for a specific workload shape — small objects, moderate write volume, strong consistency for cluster state — and pushing high-churn or large-payload data through it (unbounded Events, huge ConfigMaps used as ad hoc blob storage) degrades the entire control plane's latency, not just that one workload's.
- **Don't write reconcile logic with non-idempotent side effects** (calling a billing API, sending a notification) directly inside `Reconcile` without idempotency keys or a separate outbox pattern — the loop *will* call your function multiple times for what a human would consider "the same change," including after crashes and restarts, and any side effect without its own idempotency guarantee will double-fire.
- **Don't reach for a custom scheduler plugin or extender before checking whether existing primitives cover it.** Node affinity, taints/tolerations, topology spread constraints, and priority/preemption cover the overwhelming majority of real placement requirements; custom scheduling logic is a genuine maintenance burden best reserved for specialized cases like GPU-aware gang scheduling that the framework doesn't natively express.
- **Don't run a 2-node or 4-node etcd cluster expecting extra fault tolerance from the extra node.** The quorum math is unforgiving: 4 nodes need 3 for quorum, tolerating exactly the same single-node failure as a 3-node cluster while paying more in replication and storage cost — always size etcd odd.

---

## Interview questions

### Q1 — Why does etcd run with 3 or 5 nodes and never an even number?
**Testing:** whether the Raft quorum math is actually understood, not just memorized as "odd is better."
**Answer:** Quorum for a write to commit is `floor(n/2) + 1`. A 3-node cluster needs 2 to agree and survives 1 node failure before losing write availability. A 5-node cluster needs 3 and survives 2 failures. A 4-node cluster also needs 3 to agree — identical fault tolerance to 3 nodes (still only 1 failure survivable) — while paying for an extra replica's storage, network, and disk-fsync overhead with zero additional resilience gained.
**Follow-up trap:** *"So why would anyone ever run 5 instead of 3?"* — specifically to survive 2 simultaneous failures, e.g. a full availability-zone outage plus one additional unrelated node failure during that window; it's a genuine, deliberate tradeoff of more replication overhead for more fault tolerance, not a default upgrade everyone should make.

### Q2 — Why is the API server the only component allowed to write to etcd?
**Testing:** understanding of the single-writer architecture as a deliberate consistency mechanism, not an arbitrary rule.
**Answer:** Centralizing all writes through one component lets Kubernetes enforce a consistent admission chain (authn, authz/RBAC, mutating webhooks, schema validation, validating webhooks) and consistent optimistic-concurrency semantics (every write checked against the object's `resourceVersion`) uniformly, regardless of which client is writing. If schedulers, kubelets, and controllers all wrote to etcd directly, every one of them would need to reimplement that entire chain correctly and consistently, and any inconsistency between implementations becomes a real correctness bug.
**Follow-up trap:** *"What actually happens if two clients try to update the same object at nearly the same time?"* — the second writer's request carries the `resourceVersion` it read at; if the first writer already updated the object (bumping the version in etcd), the second write is rejected with HTTP 409 Conflict, and the client is expected to re-GET the current object and retry its logic against the fresh state, not blindly resubmit the same patch.

### Q3 — Walk through the scheduler's decision process for a single pod, start to finish.
**Testing:** the two-phase Filter/Score model plus binding, with real plugin names showing familiarity beyond the diagram level.
**Answer:** Every node is run through Filter plugins (roughly 14 in-tree ones — `NodeResourcesFit`, `NodeAffinity`, taint/toleration checks, `PodTopologySpread`) and any node failing even one is dropped entirely, never reaching scoring. Surviving nodes are scored 0-100 by each Score plugin (roughly 9 in-tree — `NodeResourcesBalancedAllocation`, `ImageLocality`, `InterPodAffinity`), each weighted and summed, and the highest-scoring node wins (ties broken pseudo-randomly). `Bind` is then an actual API server write assigning `pod.spec.nodeName`, which the target node's kubelet picks up via its own watch.
**Follow-up trap:** *"What happens if no node passes Filter for a high-priority pod?"* — `PostFilter` runs, attempting preemption: it looks for a set of lower-`priorityClassValue` pods whose eviction would free enough capacity for the pending pod, and if a viable victim set exists, evicts them and retries scheduling; if no viable set exists, the pod stays `Pending` and the scheduler retries on the next relevant cluster change.

### Q4 — What does "level-triggered, not edge-triggered" actually mean for a Kubernetes controller, and why does it matter?
**Testing:** the core reconcile-loop concept, stated precisely.
**Answer:** An edge-triggered system reacts to *the specific event* ("field X changed from A to B, do the corresponding delta action"). A level-triggered system reacts to *the fact that something changed* by re-deriving the full picture from current state ("something about this object changed, go figure out what's currently true and correct any drift from desired"). Kubernetes controllers are level-triggered: `Reconcile` receives just a namespace/name key, not a diff, and must re-fetch current state itself. This matters because event delivery isn't guaranteed exactly-once or in-order at the application level — events get coalesced (a rapid burst of changes to one object collapses to one workqueue entry), and controllers restart and lose any in-memory event history — so correctness can only be guaranteed by always re-deriving from current observed state, never from remembered event history.
**Follow-up trap:** *"Does that mean Reconcile is called on a timer even with zero actual changes?"* — yes, deliberately: controller-runtime periodically resyncs (re-enqueues every watched object on an interval, commonly around 10 hours by default, configurable) specifically to correct any drift that might have been missed by the watch mechanism itself (a dropped watch connection, an informer cache desync) — this is a second, independent safety net on top of the primary watch-driven trigger.

### Q5 — Why must `Reconcile` be idempotent, and what's a concrete failure if it isn't?
**Testing:** whether they can connect the abstract principle to a real bug pattern.
**Answer:** The same object key can be dequeued and reconciled multiple times for what a human would consider "one logical change" — at-least-once delivery, resyncs, and restarts all cause repeat calls with no new information. A concrete failure: a `Reconcile` that unconditionally calls `Status().Update()` on every invocation, rather than checking whether the computed status actually differs from the stored one, generates a new watch event on every write (since a status update is itself an object change), which re-enqueues the same object, which calls `Reconcile` again, which updates status again — an unbounded self-triggering loop hammering the API server with writes that accomplish nothing, a very real and commonly seen operator bug.
**Follow-up trap:** *"Wouldn't a semantic deep-equal check before every write fully solve this?"* — it solves the specific self-triggering-loop pattern, but idempotency has to hold for *every* side effect the reconciler performs, not just object writes — if `Reconcile` also calls an external API (provisioning a cloud resource, sending a webhook) as part of its logic, that call needs its own idempotency guarantee (an idempotency key, a check-before-create) independent of whether the Kubernetes object write itself is guarded correctly.

### Q6 — What's the actual difference between a "controller" and an "operator," precisely?
**Testing:** whether the terms are used correctly or interchangeably out of habit.
**Answer:** A controller is the general term for any reconcile loop watching a resource type and driving it toward desired state — the Deployment controller reconciling ReplicaSets is a controller, and it's built into `kube-controller-manager`. An operator specifically refers to a controller paired with a Custom Resource Definition, encoding domain-specific operational knowledge that no built-in controller has — the term implies the controller is doing something meaningfully beyond generic CRUD reconciliation, like a database operator understanding safe failover ordering.
**Follow-up trap:** *"Is a CRD with no controller running against it 'an operator'?"* — no, it's just a schema — the API server will store and serve those objects, but with no controller reconciling them, nothing actually happens as a result of creating one; "operator" specifically names the pairing of the schema and the behavior, not the schema alone.

### Q7 — Why is leader election mandatory for a multi-replica custom controller, and what actually breaks without it?
**Testing:** the concrete failure mode, not just "you need HA."
**Answer:** Without leader election, every replica runs its own independent informer and reconcile loop against the same watched objects, so multiple replicas can call `Reconcile` on the same object concurrently — best case, wasted duplicate work and API server load; worst case, conflicting writes racing against each other (both replicas GET the same `resourceVersion`, both compute slightly different desired state due to a timing difference, one write wins via optimistic concurrency and the other gets a 409 and retries against now-stale assumptions, potentially producing flapping or incorrect final state). Leader election uses a Lease object with a renewal deadline; only the current leader actively reconciles, and on leader failure (missed lease renewal), another replica acquires it and takes over.
**Follow-up trap:** *"If only the leader reconciles, what are the other replicas doing — are they wasted resources?"* — they're on standby, typically still running their informers and populating local caches so failover is fast (no cold-start cache rebuild delay), but not actively calling `Reconcile`; it's a deliberate active-standby tradeoff, not wasted capacity in the sense of doing nothing useful, since fast failover is the actual point of running more than one replica.

### Q8 — Explain finalizers and why "just delete the object" isn't always immediate.
**Testing:** understanding of the deletion lifecycle and its interaction with external cleanup.
**Answer:** A finalizer is a string entry in `metadata.finalizers`. Deleting an object that has one or more finalizers present doesn't remove it from etcd — it sets `metadata.deletionTimestamp` and the object remains visible (in a "terminating" state) until every finalizer is removed. This gives an owning controller a guaranteed window to perform cleanup (deprovisioning an external cloud resource the CRD instance represented, for instance) before the object actually disappears; the controller's `Reconcile` sees the non-zero `deletionTimestamp`, does the cleanup, and only then removes its finalizer entry, at which point (once no finalizers remain) the API server actually deletes the object.
**Follow-up trap:** *"A `kubectl delete` on a CRD instance is hanging forever. What's your diagnosis path, and what's the risky last resort?"* — check whether the owning controller is even running and whether its `Reconcile` is erroring out on the cleanup path (controller logs), since either would leave the finalizer stuck forever. The risky last resort is manually patching the finalizers list to empty to force deletion — this should be treated as accepting orphaned external resources (whatever the finalizer's cleanup was supposed to handle never happens) and is a workaround for a bug, not a routine operational step.

### Q9 — What's `mvcc: database space exceeded`, and how do you actually fix it, not just work around it?
**Testing:** whether the candidate understands compaction vs defragmentation as distinct steps, a common point of confusion.
**Answer:** etcd's backend size quota (`--quota-backend-bytes`, default 2GB) was exceeded, and etcd enters an alarm state rejecting all further writes cluster-wide until resolved. The fix has two distinct steps: **compaction** removes old MVCC revisions (historical versions of keys kept for watch/consistency purposes) up to a target revision, which frees *logical* space; **defragmentation** then reclaims that freed space at the underlying storage-engine (bbolt) level, since compaction alone doesn't shrink the on-disk file — skipping defrag after compacting leaves the alarm condition unresolved even though the data was logically compacted.
**Follow-up trap:** *"Should the fix always be raising the quota?"* — no, that treats the symptom; the actual first step is investigating *why* the database grew that large — commonly unbounded Event objects, excessive CRD instance churn, or a controller writing large objects at high frequency — because raising the quota without addressing the root cause just delays hitting the same alarm again at a higher threshold, with a now-larger etcd database that's slower to snapshot and restore.

### Q10 — A pod is `Pending` and `kubectl describe pod` shows `0/12 nodes are available`. How do you actually diagnose which constraint is the blocker?
**Testing:** practical debugging skill beyond "check the events."
**Answer:** The event message on a `FailedScheduling` reason includes a per-reason breakdown of how many nodes were rejected by which Filter check (e.g. "3 Insufficient cpu, 5 node(s) didn't match Pod's node affinity/selector, 4 node(s) had taint {...} that the pod didn't tolerate") — read that breakdown line by line rather than treating "0/12 nodes available" as an undifferentiated failure; it tells you exactly which Filter plugin is eliminating which nodes, and the fix path differs entirely depending on whether it's a resource-capacity problem versus an affinity/taint misconfiguration.
**Follow-up trap:** *"The breakdown shows plenty of nodes have capacity, but every one is rejected on affinity. What's your next step?"* — inspect the pod's actual `nodeAffinity`/`nodeSelector`/`podAntiAffinity` rules against the labels genuinely present on those nodes (`kubectl get nodes --show-labels`) — a very common real cause is a typo'd label key or value, or a topology label (like a zone label) that changed after the affinity rule was written and nobody updated the rule.

### Q11 — Why does `.status` need to be recomputed from observation rather than just tracked as whatever the controller last set it to?
**Testing:** understanding of controller statelessness and restart safety.
**Answer:** The controller process itself has no durability guarantee — it can crash and restart at any time, and on restart it has no memory of anything it did before, only whatever's currently visible in the cluster (the object's `.spec`, and the actual state of whatever real-world resources it manages). If `.status` were treated as "whatever I last wrote and am now just carrying forward," a restart would either need to somehow recover that in-memory intent (impossible in general) or `.status` would go stale and silently lie about current reality. Recomputing `.status` from live observation on every `Reconcile` call means a restart is invisible to correctness — the very next reconcile just recomputes the true current state from scratch.
**Follow-up trap:** *"Does that mean `.status` should never contain anything the controller can't directly observe right now?"* — essentially yes, and this is exactly why `.status` conventionally holds observed facts (`readyReplicas`, `conditions` with observed timestamps) rather than remembered plans or intentions — anything that can't be freshly derived from currently observable state doesn't belong there, because it can't survive a restart honestly.

### Q12 — Your custom operator's replica count is 3 for HA, but you're seeing intermittent conflicting writes to the objects it manages. What's the first thing you check?
**Testing:** direct application of the leader election concept to a live symptom.
**Answer:** Whether leader election is actually enabled and functioning — check for a Lease object in the controller's namespace and confirm only one replica currently holds it. If leader election was never configured (or is misconfigured, e.g. all replicas pointed at different Lease names by accident), every replica reconciles independently and concurrently, which produces exactly this symptom: races where two replicas compute slightly different desired state from a marginally different read and both attempt to write.
**Follow-up trap:** *"You confirm leader election is correctly configured and only one replica holds the lease, but you're still seeing occasional conflicting writes. What else could cause this?"* — a completely separate actor also writing to the same objects — a human running `kubectl edit`/`kubectl patch` directly, a second unrelated controller with overlapping ownership of the same resources, or a CI/CD pipeline applying manifests that collide with what the operator manages; leader election only prevents *the operator's own replicas* from racing each other, it does nothing about external writers.

### Q13 — When would you deliberately choose not to build an operator, even though "a CRD would model this nicely"?
**Testing:** the senior "when NOT to" judgment, specifically against the temptation of a clean abstraction.
**Answer:** When the actual operational logic doesn't go meaningfully beyond what a ConfigMap-plus-Deployment, a Helm chart, or a simple templating layer already provides — a CRD looking nicer as an API surface isn't sufficient justification for taking on a new, permanently-running distributed system (the controller itself) that now needs its own monitoring, its own failure-mode handling, its own on-call burden. The honest test is whether the controller encodes real operational knowledge (failover logic, safe upgrade ordering, external resource lifecycle management) that a human or a simpler tool would otherwise have to apply manually and repeatedly.
**Follow-up trap:** *"Isn't 'nicer API surface' worth something on its own, especially for a platform team serving many internal consumers?"* — sometimes, genuinely — a thin CRD as a stable, validated, self-service interface for internal teams can be worth the overhead even without deep reconciliation logic, provided the team is honest that they're paying for API ergonomics, not operational automation, and is willing to actually staff the ongoing maintenance of the controller that comes with it; the failure mode to avoid is building it without acknowledging that tradeoff explicitly.

---

## Red flags that fail you

- Claiming any component other than the API server writes to etcd directly.
- Not knowing why etcd clusters are sized odd (3 or 5), or claiming 4 nodes has more fault tolerance than 3.
- Describing the scheduler as a single-phase process, or not knowing Filter and Score are distinct, sequential phases.
- Writing (or describing) reconcile logic that updates `.status` unconditionally without checking if it actually changed.
- Confusing "controller" and "operator" as synonyms with no distinction, or claiming a CRD alone (with no controller) "does something."
- Not knowing what a finalizer is, or claiming `kubectl delete` always removes an object from etcd immediately.
- Recommending a custom operator as the default solution before checking whether existing primitives (ConfigMap, existing controllers, Helm templating) already cover the need.

---

## Cheat card

```
CONTROL PLANE: API server (only etcd writer, admission chain, stateless) + etcd (Raft KV)
               + scheduler (Filter->Score->Bind) + controller-manager (reconcile loops)

ETCD/RAFT: quorum = floor(n/2)+1. 3 nodes tolerate 1 failure, 5 tolerate 2, 4 = same as 3
  (never even-size). fsync latency dominates perf; >~10ms wal_fsync = red flag
  quota-backend-bytes default 2GB -> exceeded = "mvcc: database space exceeded", ALL
  writes rejected -> fix = compact (logical) THEN defrag (reclaim disk), not just raise quota

API SERVER WRITES: optimistic concurrency via resourceVersion -> stale write = HTTP 409
  admission chain order: authn -> authz(RBAC) -> mutating webhooks -> schema validation
  -> validating webhooks -> persist

SCHEDULER: Filter (~14 in-tree plugins, ANY fail = node dropped, e.g. NodeResourcesFit,
  taints/tolerations, PodTopologySpread) -> Score (~9 in-tree, 0-100 each, weighted sum,
  e.g. ImageLocality, NodeResourcesBalancedAllocation) -> Bind (actual API write)
  no node passes Filter -> PostFilter tries PREEMPTION (evict lower priorityClass pods)

RECONCILE LOOP: informer (list+watch, local cache) -> workqueue (KEYS not objects,
  coalesces bursts) -> worker calls Reconcile(ctx, namespacedName) -> MUST re-fetch fresh
  state, MUST be idempotent, LEVEL-triggered not edge-triggered (re-derive, don't remember)
  periodic resync (~10h default) as a second safety net independent of watch

CRD = schema only, no behavior. OPERATOR = CRD + controller w/ real domain logic.
  Owns() in SetupWithManager -> secondary watch, re-enqueues owner on owned-resource drift
  finalizers: block actual deletion until controller's cleanup runs & removes them
  LEADER ELECTION mandatory for >1 replica custom controllers (Lease object) or you get
  concurrent conflicting writes from independently-reconciling replicas

STATUS BUG: unconditional Status().Update() every Reconcile call -> generates a watch
  event -> re-enqueues self -> infinite self-triggering loop. Always deep-equal check first.
```

## Sources

- [Kubernetes Scheduling Framework (KEP-624)](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/624-scheduling-framework/README.md) — accessed 2026-08-02
- [Kubernetes documentation — Scheduling Framework](https://kubernetes.io/docs/concepts/scheduling-eviction/scheduling-framework/) — accessed 2026-08-02
- [Kubernetes Scheduler: How Filter, Score, Bind Actually Works — ScaleOps](https://scaleops.com/blog/kubernetes-scheduler/) — accessed 2026-08-02
- [Kubernetes Reconcile Loop Explained: Workqueue, Reconcile() & Code (2026) — GoLinuxCloud](https://www.golinuxcloud.com/kubernetes-reconcile-loop-explained/) — accessed 2026-08-02
- [The Kubebuilder Book — Good Practices](https://book.kubebuilder.io/reference/good-practices) — accessed 2026-08-02
- [etcd in Kubernetes: a deep dive — ITNEXT](https://itnext.io/etcd-in-kubernetes-a-deep-dive-55cb2b6ef72e) — accessed 2026-08-02
- etcd official documentation — `quota-backend-bytes`, compaction/defragmentation operations guide
- Raft consensus paper (Ongaro & Ousterhout, "In Search of an Understandable Consensus Algorithm," 2014) — quorum/leader election fundamentals

## Changelog
- 2026-08-02 — created
