# K8s Objects: Pod â†’ Deployment â†’ StatefulSet â†’ DaemonSet â†’ Job, and YAML That Works

> **Track:** T12 DevOps, Infra & Security Â· **Time:** 2.5h Â· **Prereqs:** T12-docker Â· **Updated:** 2026-08-02
> **Module id:** `T12-k8s-objects` Â· **Tags:** k8s, critical
> **Lab:** `labs/misc/02-k8s-objects/`

## The 30-second version

A Pod is the smallest deployable unit â€” one or more containers sharing a network namespace and localhost â€” and you almost never create one directly in production because it has no self-healing or rollout mechanism of its own. Deployment wraps a ReplicaSet to give stateless workloads rolling updates, rollback history, and self-healing, and its `spec.selector` is immutable after creation, which trips people up the first time they try to relabel an existing Deployment. StatefulSet exists for workloads that need stable identity: pods get deterministic ordinal names (`db-0`, `db-1`, `db-2`) resolvable via a mandatory headless Service, each gets its own persistent volume from `volumeClaimTemplates` that follows it across rescheduling, and by default those PVCs survive both scale-down and StatefulSet deletion â€” a deliberate data-safety default that surprises people expecting automatic cleanup. DaemonSet runs exactly one pod per matching node with no `replicas` field at all, used for node-scoped agents like CNI plugins and log shippers, and needs explicit tolerations to land on tainted nodes. Job runs pods to completion with a `backoffLimit` (default 6) and requires `restartPolicy: OnFailure` or `Never` â€” `Always` is invalid and rejected by the API â€” and CronJob schedules Jobs with a `concurrencyPolicy` that most people leave at the dangerous default (`Allow`, meaning overlapping runs) when they actually wanted `Forbid`.

## Why this gets asked

Because the fields nobody reads carefully â€” `restartPolicy`, `persistentVolumeClaimRetentionPolicy`, `concurrencyPolicy`, `podManagementPolicy` â€” are exactly the ones that cause real incidents: a CronJob silently double-running against a database because `concurrencyPolicy` defaulted to `Allow`, a StatefulSet scale-down that the team assumed deleted its PVCs (it didn't, by design) leading to either a false sense of data loss or an unexpected storage bill, a DaemonSet that mysteriously doesn't run on the exact nodes that need it because nobody added the matching toleration. The interviewer isn't testing whether you can name the five controller types â€” everyone can â€” they're testing whether you've been burned by one of these defaults in production and know it from the incident, not the docs page.

---

## Lineage: past â†’ present â†’ future

**What came before.** Kubernetes 1.0 (2015) shipped with the ReplicationController (RC) as the only replica-management primitive: a flat pod template plus a desired count, with a mutable, equality-based selector and no built-in rolling update mechanism â€” updating an RC's pod template required either manual `kubectl rolling-update` scripting or replacing the RC entirely, and there was no rollback history if a bad rollout needed reverting. The pain that killed it was operational: teams needed atomic, revertible rollouts as deployment frequency increased, and RC's model of "just a replica count plus a template" had no concept of a rollout as a first-class, trackable event. StatefulSet's lineage is separate and later â€” it started as the experimental `PetSet` (Kubernetes 1.3-1.4, 2016), explicitly named to contrast "pets" (individually identified, cared-for instances like a database node) against the "cattle" model RC/Deployment assumed (interchangeable, disposable, no identity), because Kubernetes originally had no answer at all for workloads where pod identity and storage had to survive rescheduling.

**Where it stands now.** Deployment (GA in 1.9, 2018) wraps a ReplicaSet and owns the rollout: changing the pod template creates a new ReplicaSet, scales it up while scaling the old one down according to `strategy.rollingUpdate` bounds, and keeps prior ReplicaSets around (bounded by `revisionHistoryLimit`, default 10) so `kubectl rollout undo` has something to revert to. StatefulSet reached GA alongside Deployment in 1.9 and is now the settled answer for anything needing stable network identity and per-instance storage â€” Kafka via the Strimzi operator, Cassandra, self-hosted Postgres via an operator like CloudNativePG, Elasticsearch. DaemonSet's model hasn't fundamentally changed since early Kubernetes; it remains the correct pattern for node-scoped agents specifically because it bypasses the scheduler's normal bin-packing logic in favor of "exactly one per matching node," which is precisely the guarantee a CNI plugin or node-level log shipper needs. Job and CronJob matured meaningfully more recently: indexed completion mode (`completionMode: Indexed`, giving each pod in a parallel Job a `JOB_COMPLETION_INDEX` env var) and pod failure policies (distinguishing an infrastructure-caused pod failure that should retry from an application-caused failure that should fail the Job immediately, GA around 1.31) turned Kubernetes-native Jobs into a genuinely viable batch-processing primitive rather than something you'd reach for an external scheduler to avoid. The live disagreement is less about the object types themselves and more about *whether stateful workloads belong in Kubernetes at all* â€” plenty of senior engineers will argue a single-instance relational database is better run as a managed service (RDS, Cloud SQL) than as a hand-rolled StatefulSet, reserving StatefulSet for things that genuinely need Kubernetes-native scaling and co-location (Kafka, distributed caches), because the operational burden StatefulSet doesn't remove â€” backup scheduling, failover orchestration, patching â€” is exactly what a managed service is paid to absorb.

**Where it's heading.** Native sidecar containers (GA in 1.29) â€” `initContainers` entries with `restartPolicy: Always`, which start before the main containers, keep running alongside them, and are guaranteed to terminate after the main containers on pod shutdown rather than being killed arbitrarily â€” are replacing a decade of hacky patterns (service mesh proxy injection racing the app container's startup, log-shipping sidecars with no defined shutdown ordering) with a first-class primitive. Indexed Jobs with pod failure policies are pushing more batch workloads to run natively rather than via an external workflow engine layered on top, though for genuinely complex DAG-shaped batch pipelines (multi-stage ETL with dependencies), tools like Argo Workflows still sit above raw Jobs rather than being replaced by them. Expect the object model itself to stay largely stable going forward â€” this is one of the more settled parts of the Kubernetes API surface â€” with incremental additions (like the sidecar and pod-failure-policy work) refining edge cases rather than restructuring the core five controllers.

---

## Mental model

```
Deployment  â”€â”€ownsâ”€â”€>  ReplicaSet  â”€â”€ownsâ”€â”€>  Pod, Pod, Pod   (interchangeable, no identity)
   (template change creates a NEW ReplicaSet, old one scaled to 0, kept for rollback)

StatefulSet â”€â”€ownsâ”€â”€>  Pod-0, Pod-1, Pod-2   (each has a stable name + own PVC, in order)
   requires:  Headless Service (clusterIP: None)
              -> DNS: <pod-name>.<service-name>.<namespace>.svc.cluster.local
   scale-down: Pod-2 removed first (reverse ordinal), its PVC usually SURVIVES (retention
               policy default), same PVC reattaches if scaled back up

DaemonSet   â”€â”€ownsâ”€â”€>  one Pod PER matching node, no `replicas` field at all
   node A: [daemon-pod]   node B: [daemon-pod]   node C (tainted, no toleration): (nothing)

Job         â”€â”€ownsâ”€â”€>  Pod(s) run to COMPLETION, not forever
   restartPolicy must be OnFailure or Never (Always is rejected by API validation)
   completions=N, parallelism=M -> up to M pods running concurrently until N succeed

CronJob     â”€â”€createsâ”€â”€>  Job (on schedule)  â”€â”€ownsâ”€â”€>  Pod(s)
   concurrencyPolicy: Allow (default, can overlap) | Forbid | Replace
```

The one thing that unifies all five: every controller is a reconcile loop comparing *desired* state (the spec you wrote) against *observed* state (what the API server's watch stream reports), and issuing the minimal diff of create/update/delete calls to close the gap â€” nothing here is imperative "do this now," it's declarative "make it look like this, continuously."

---

## How it actually works

### Pod-level fields people get wrong

`restartPolicy` (Pod-level, default `Always`) governs what happens when a container exits. `Always` is required for Deployment/StatefulSet/DaemonSet-managed pods (a crashed container should restart to maintain the desired replica count) but is **invalid for a Job** â€” the API server rejects a Job pod template with `restartPolicy: Always` outright, because a Job's entire purpose is running to completion, and "always restart" is incompatible with the concept of "completion" ever being reached. Job pods must use `OnFailure` (failed container restarts in place, counted against `backoffLimit`) or `Never` (failed container is not restarted; a new pod is created instead, also counted against `backoffLimit`).

`terminationGracePeriodSeconds` (default **30 seconds**) governs shutdown: on pod deletion, the kubelet sends `SIGTERM` to each container, runs any `preStop` hook concurrently, waits up to the grace period, then sends `SIGKILL` to anything still alive. The common mistake is an application that doesn't handle `SIGTERM` at all (many runtimes need an explicit signal handler to drain in-flight requests) getting hard-killed after 30 seconds every single deploy, silently dropping in-flight work â€” the fix is either handling `SIGTERM` gracefully in the app or using a `preStop` hook (commonly `sleep 5-15` to let load balancer deregistration propagate before the app stops accepting new connections) alongside an explicit grace period long enough to drain, not just the default.

Init containers run sequentially, each must exit 0 before the next starts, and all must complete before any app container starts â€” this is the correct place for one-time setup (schema migration wait, config templating) but a slow or hanging init container silently delays the whole pod with no separate visibility unless you specifically check `kubectl describe pod` for init container status. Native sidecar containers (1.29+, an `initContainers` entry with `restartPolicy: Always`) are different: they start before app containers like a normal init container but keep running alongside them and are the last to terminate on shutdown, which is the correct primitive for a service mesh proxy or log shipper that needs to outlive the app container during graceful shutdown.

### Deployment â€” the fields that bite

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api          # IMMUTABLE after creation â€” cannot be changed with kubectl apply
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%        # default â€” extra pods allowed above `replicas` during rollout
      maxUnavailable: 25%  # default â€” pods allowed below `replicas` during rollout
  revisionHistoryLimit: 10  # default â€” how many old ReplicaSets are kept for rollback
  progressDeadlineSeconds: 600  # default â€” rollout marked Failed if no progress in 10min
  template:
    metadata:
      labels:
        app: api          # MUST match selector.matchLabels exactly, or the API rejects it
    spec:
      restartPolicy: Always
      containers:
      - name: api
        image: myrepo/api:v3
```

`selector.matchLabels` being immutable is the single most common "why won't my apply work" moment â€” you cannot relabel an existing Deployment's selector; you have to delete and recreate it (losing rollout history) or, more commonly, get the selector right from the start and never touch it. `maxSurge`/`maxUnavailable` at their **25%/25%** defaults mean a 3-replica Deployment can transiently run 4 pods (surge) while transiently having as few as 2 Ready (unavailable) during a rollout â€” for a workload with tight capacity margins, both of those defaults are worth tuning explicitly rather than trusting them blindly.

### StatefulSet â€” identity and storage

```yaml
apiVersion: v1
kind: Service
metadata:
  name: db
spec:
  clusterIP: None       # headless â€” REQUIRED for StatefulSet pod DNS identity
  selector:
    app: db
  ports:
  - port: 5432
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: db
spec:
  serviceName: db        # must match the headless Service above
  replicas: 3
  podManagementPolicy: OrderedReady  # default: db-0 must be Ready before db-1 starts
  updateStrategy:
    type: RollingUpdate   # default: updates in REVERSE ordinal order, N-1 down to 0
  selector:
    matchLabels:
      app: db
  template:
    metadata:
      labels:
        app: db
    spec:
      containers:
      - name: db
        image: postgres:16
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
  persistentVolumeClaimRetentionPolicy:
    whenScaled: Retain    # default â€” PVC survives scale-down (data-safety default)
    whenDeleted: Retain    # default â€” PVC survives StatefulSet deletion too
```

Each replica gets a deterministic hostname (`db-0`, `db-1`, `db-2`) and its own PVC named `data-db-0`, `data-db-1`, `data-db-2` from the `volumeClaimTemplates`. DNS resolves per-pod via the headless Service: `db-0.db.<namespace>.svc.cluster.local` â€” this is what lets a Postgres replica always find "the primary at ordinal 0" deterministically across restarts. `podManagementPolicy: OrderedReady` (the default) starts pods strictly sequentially, each waiting for the previous to be Ready â€” correct for workloads with real startup ordering dependencies, but a real cost in rollout latency for clusters with many replicas; `Parallel` starts all pods simultaneously and is the right choice when ordering doesn't actually matter (many Cassandra deployments use `Parallel` specifically to cut multi-minute sequential startup down). `persistentVolumeClaimRetentionPolicy` (beta since roughly 1.23, GA by 1.27) defaults both `whenScaled` and `whenDeleted` to `Retain` â€” this is the thing that surprises people who scale a StatefulSet from 5 to 2 replicas expecting the freed PVCs to vanish; they don't, on purpose, because losing a database's storage silently on a routine scale-down is a much worse failure mode than an operator having to explicitly clean up orphaned PVCs later.

### DaemonSet â€” node-scoped, no replica count

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
spec:
  selector:
    matchLabels:
      app: node-exporter
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1   # default â€” nodes updated one at a time
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        effect: NoSchedule    # WITHOUT this, node-exporter never runs on control-plane nodes
      containers:
      - name: node-exporter
        image: prom/node-exporter:v1.8.2
```

No `replicas` field exists on a DaemonSet spec at all â€” the count is implicitly "one per node matching the pod's node selector/affinity and tolerating its taints," fully determined by the cluster's node set, not a number you set. The single most common DaemonSet bug is exactly what's shown above: forgetting a toleration for an existing taint (control-plane nodes, GPU nodes, spot-instance taints) means the DaemonSet silently doesn't run there, which is often precisely the set of nodes an observability or security agent most needs to be on.

### Job and CronJob

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: nightly-report
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 6            # default â€” retries before marking the Job Failed
  activeDeadlineSeconds: 3600  # optional hard wall-clock cap, no default
  ttlSecondsAfterFinished: 86400  # optional auto-cleanup, no default (jobs pile up forever otherwise)
  template:
    spec:
      restartPolicy: OnFailure   # REQUIRED to be OnFailure or Never â€” Always is rejected
      containers:
      - name: report
        image: myrepo/report:v2
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly-report-cron
spec:
  schedule: "0 2 * * *"
  timeZone: "America/New_York"   # GA'd ~1.27 â€” before this, schedules were UTC only
  concurrencyPolicy: Forbid       # default is ALLOW â€” most teams actually want Forbid
  startingDeadlineSeconds: 300    # how late a missed run can start before being skipped
  successfulJobsHistoryLimit: 3   # default
  failedJobsHistoryLimit: 1       # default
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: report
            image: myrepo/report:v2
```

`concurrencyPolicy` defaults to `Allow`, meaning if a run takes longer than the schedule interval, a second overlapping Job starts â€” for anything touching a shared resource (writing to the same DB table, acquiring the same external lock) this is the exact bug that produces duplicate writes or a race, and `Forbid` (skip a new run if the previous is still active) or `Replace` (kill the previous, start the new one) are what most production CronJobs actually want. The CronJob controller also has an internal safety valve: if it detects **100 or more missed schedule times** since it last checked (commonly from the controller itself being down, or the cluster being unreachable for an extended period), it stops scheduling that CronJob entirely and logs an error, rather than trying to catch up by firing a hundred overlapping Jobs at once â€” a real, non-obvious behavior worth knowing when a CronJob mysteriously "just stopped running" after a control-plane outage.

---

## Build it from scratch

A minimal, deliberately annotated set proving the fields above are understood, not memorized:

```yaml
# untested sketch â€” annotated minimal StatefulSet + headless Service, the two
# most commonly misconfigured objects in this list
apiVersion: v1
kind: Service
metadata:
  name: cache
spec:
  clusterIP: None              # <- omit this and StatefulSet pods get NO stable DNS identity
  selector: { app: cache }
  ports: [{ port: 6379 }]
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: cache
spec:
  serviceName: cache           # <- must equal the Service name above, not enforced by API
                                #    validation â€” a typo here silently breaks pod DNS
  replicas: 3
  selector: { matchLabels: { app: cache } }
  template:
    metadata: { labels: { app: cache } }
    spec:
      terminationGracePeriodSeconds: 60   # <- default 30s is often too short for a DB flush
      containers:
      - name: cache
        image: redis:7.4
        readinessProbe:
          exec: { command: ["redis-cli", "ping"] }
          initialDelaySeconds: 5
  volumeClaimTemplates:
  - metadata: { name: data }
    spec:
      accessModes: ["ReadWriteOnce"]
      resources: { requests: { storage: 5Gi } }
```

Applying this, then running `kubectl scale statefulset cache --replicas=1`, then `kubectl get pvc` proves the point mechanically: two PVCs remain even though only one pod exists, because `persistentVolumeClaimRetentionPolicy` defaulted to `Retain` â€” exactly the behavior that surprises people who expected scale-down to clean up storage automatically.

---

## How it's done in production

Nobody hand-writes raw YAML like the above at scale â€” Helm charts or Kustomize overlays template these objects, and GitOps controllers (ArgoCD, Flux) continuously reconcile the cluster's actual state against what's committed to a Git repository, which is itself just another layer of the same declarative-reconciliation model these controllers use internally. Stateful workloads in production are overwhelmingly run behind purpose-built operators (Strimzi for Kafka, CloudNativePG or the Postgres Operator for Postgres, the Elastic Cloud on Kubernetes operator for Elasticsearch) rather than a hand-rolled StatefulSet, because the operator encodes operational knowledge (failover orchestration, backup scheduling, safe rolling upgrade ordering) that a bare StatefulSet spec has no concept of.

| Symptom | Cause | Fix |
|---|---|---|
| StatefulSet pods stuck `Pending`, never reach `Running` | No headless Service matching `serviceName`, or the StorageClass can't dynamically provision a PVC per ordinal | Create/fix the headless Service; check `kubectl describe pvc` for provisioning errors and confirm the StorageClass exists and supports dynamic provisioning |
| `kubectl apply` fails with "field is immutable" on a Deployment | Tried to change `spec.selector.matchLabels` after creation | Delete and recreate the Deployment (loses rollout history), or plan the selector correctly before first apply |
| DaemonSet pods missing on specific nodes (often the ones that matter most: control-plane, GPU) | No toleration for the taint on those nodes | Add the matching `tolerations` entry; confirm with `kubectl get nodes -o json \| jq '.items[].spec.taints'` |
| CronJob silently stopped running after a control-plane outage | Controller detected â‰¥100 missed schedule times since last check and disabled further scheduling for that CronJob as a safety valve | Check controller-manager logs for the "too many missed start times" message; manually trigger a Job if needed and investigate why the controller was down that long |
| Job pods restart forever, `backoffLimit` never seems to stop them | `restartPolicy: Always` mistakenly set (should be rejected, but check API version/admission if it wasn't) or `backoffLimit` set unreasonably high, masking a genuine app crash-loop | Set `restartPolicy: OnFailure`/`Never`, lower `backoffLimit` to a sane value, and check application logs for the actual crash cause rather than treating retries as the fix |
| PVCs accumulating and driving up storage cost after routine StatefulSet scale-downs | `persistentVolumeClaimRetentionPolicy` defaults to `Retain` on both `whenScaled` and `whenDeleted` | If the workload genuinely doesn't need data to survive a scale-down (e.g. a stateless-ish cache), explicitly set `whenScaled: Delete`; otherwise this is by design, clean up deliberately with a documented process |
| Rolling update stuck at "1 of 3 updated," never completes | New ReplicaSet's pods failing readiness probe; `progressDeadlineSeconds` (default 600s) hasn't elapsed yet to mark the rollout Failed | `kubectl rollout status` / `kubectl describe pod` on the new pods to find the actual readiness failure; fix the probe or the app startup issue, don't just wait it out |

---

## Tradeoffs & when NOT to use it

- **Don't use StatefulSet for workloads with no real identity requirement**, even if the stable naming looks convenient â€” `OrderedReady` sequential startup adds real, avoidable rollout latency for something that would deploy just as correctly, and faster, as a Deployment.
- **Don't self-host a single-instance relational database as a StatefulSet by default.** A managed service (RDS, Cloud SQL, Aurora) absorbs failover orchestration, automated backups, and patching that a bare StatefulSet spec does nothing to provide â€” reach for a StatefulSet-backed operator only when there's a genuine reason (data residency, cost at very large scale, needing tight co-location with compute) that outweighs the operational burden you're taking back on.
- **Don't create bare Pods in any manifest meant to run continuously.** A Pod with no owning controller has no self-healing â€” if the node dies or the process crashes, nothing recreates it, and this is a startlingly common beginner mistake that looks fine until the first node failure.
- **Don't use DaemonSet for workloads that aren't fundamentally node-scoped.** It deliberately bypasses the scheduler's normal bin-packing and resource-based placement decisions in favor of "one per matching node," which is the wrong tradeoff for anything that should be scaled based on load rather than node count.
- **Don't use CronJob for sub-minute-granularity scheduling.** Cron syntax bottoms out at one-minute resolution; anything needing tighter cadence belongs in a long-running Deployment consuming from a queue or running its own internal scheduler loop, not a CronJob firing every 60 seconds with the overhead of a fresh pod each time.

---

## Interview questions

### Q1 â€” Why can't you just change a Deployment's selector and re-apply?
**Testing:** whether they've hit this in practice versus only reading about Deployments.
**Answer:** `spec.selector.matchLabels` is immutable after creation by API validation â€” any `kubectl apply` attempting to change it is rejected outright. The workaround is deleting and recreating the Deployment (which discards rollout/revision history) or, in practice, getting the selector correct before the first apply and treating it as permanent.
**Follow-up trap:** *"Why is it immutable in the first place, rather than the API just handling a selector change gracefully?"* â€” because changing the selector changes which existing pods the Deployment's ReplicaSet considers "mine," which could cause it to silently adopt or orphan pods it didn't create, an ambiguity the API sidesteps by simply disallowing the change rather than trying to define correct adoption semantics for every case.

### Q2 â€” Walk through what happens, mechanically, when you scale a StatefulSet from 5 replicas to 2.
**Testing:** ordering and the PVC-retention surprise.
**Answer:** Pods are removed in reverse ordinal order â€” pod-4, then pod-3, then pod-2 â€” each fully terminated before the next is removed (under the default `OrderedReady` policy). The PVCs backing those removed pods (`data-db-4`, `data-db-3`, `data-db-2`) are **not** deleted by default â€” `persistentVolumeClaimRetentionPolicy.whenScaled` defaults to `Retain` â€” so scaling back up to 5 later reattaches the same volumes with whatever data was on them.
**Follow-up trap:** *"Is that a bug or intentional?"* â€” intentional, and stated as a deliberate data-safety default: silently losing a database's storage on a routine scale-down would be a far worse failure mode than requiring an operator to explicitly opt into `whenScaled: Delete` for workloads that genuinely don't need the data to persist.

### Q3 â€” A CronJob is supposed to run every 5 minutes, but you're seeing two overlapping runs writing conflicting data. What's wrong?
**Testing:** the `concurrencyPolicy` default trap.
**Answer:** `concurrencyPolicy` defaults to `Allow`, meaning if a run takes longer than the 5-minute interval, the next scheduled run starts anyway, overlapping with the still-running previous one. For anything touching shared state, `concurrencyPolicy: Forbid` (skip the new run if the previous is still active) or `Replace` (kill the old, start the new) is almost always what was actually wanted.
**Follow-up trap:** *"What if the job legitimately needs to run to completion even if it occasionally takes longer than 5 minutes, and skipping a run is unacceptable?"* â€” that's a sign the workload doesn't belong in a fixed-interval CronJob at all; either widen the interval to a safe worst-case duration, or move to a queue-consumer pattern (a long-running Deployment pulling work items) that isn't coupled to a wall-clock schedule in the first place.

### Q4 â€” Why does `restartPolicy: Always` get rejected on a Job, and what should it be instead?
**Testing:** mechanical understanding of Job semantics, not just "I know it's wrong."
**Answer:** A Job's entire purpose is running pods to completion â€” success is a terminal state that must be reachable. `restartPolicy: Always` means "restart the container no matter what happens," which is fundamentally incompatible with ever reaching a terminal completed state, so the API server rejects it at validation time. Valid values are `OnFailure` (failed container restarts in the same pod, counted against `backoffLimit`) or `Never` (a new pod is created instead of restarting the container, also counted against `backoffLimit`).
**Follow-up trap:** *"What's the actual behavioral difference between OnFailure and Never in terms of what you'd see in `kubectl get pods`?"* â€” with `OnFailure`, you see the same pod name with an increasing container restart count; with `Never`, you see multiple distinct pod objects (one per attempt) all owned by the same Job, which matters for anyone trying to `kubectl logs` a specific failed attempt after the fact.

### Q5 â€” DaemonSet pods aren't running on your GPU nodes. What do you check first?
**Testing:** the toleration/taint mechanic specifically, since this is the most common real DaemonSet bug.
**Answer:** Check the node's taints (`kubectl describe node <gpu-node> | grep Taints`) and compare against the DaemonSet's pod template `tolerations`. GPU node pools are commonly tainted (e.g. `nvidia.com/gpu=present:NoSchedule`) specifically to keep non-GPU workloads off them, and a DaemonSet with no matching toleration is excluded from those nodes exactly like any other pod would be â€” DaemonSet doesn't bypass taints, it just otherwise runs on every node that would accept a normal pod.
**Follow-up trap:** *"Does adding the toleration guarantee the DaemonSet pod actually gets scheduled there, or just that it's allowed to be?"* â€” tolerations only permit scheduling onto a tainted node, they don't force it; if the DaemonSet's pod template also has node affinity/selector requirements that don't match, or the node lacks required resources, it still won't land â€” toleration is a necessary but not sufficient condition.

### Q6 â€” What's the actual difference between `podManagementPolicy: OrderedReady` and `Parallel` on a StatefulSet, and when would you choose `Parallel`?
**Testing:** whether they know this is a real, tunable tradeoff rather than an obscure field nobody touches.
**Answer:** `OrderedReady` (default) starts pod-0, waits for it to be Ready, then starts pod-1, and so on â€” correct when replicas genuinely have startup ordering dependencies (a primary must be up before replicas attempt to join it). `Parallel` starts and stops all pods simultaneously with no ordering guarantee, which is the right choice when replicas are independent at startup and the sequential wait is pure added latency â€” many Cassandra StatefulSets use `Parallel` because Cassandra nodes don't have a leader-follower startup dependency the way, say, a primary-replica Postgres setup would.
**Follow-up trap:** *"If you switch an existing production StatefulSet from OrderedReady to Parallel, what could break?"* â€” anything implicitly relying on ordering that wasn't actually enforced by StatefulSet semantics but happened to work because of it â€” e.g., an app that assumes pod-0 is always fully initialized before pod-1's init container runs some check against it. `Parallel` removes that guarantee entirely, so any hidden ordering dependency in application logic needs to be found and made explicit first.

### Q7 â€” Explain why a headless Service is required for StatefulSet and what breaks without it.
**Testing:** the DNS mechanism specifically, not just "it's required."
**Answer:** A headless Service (`clusterIP: None`) doesn't load-balance; instead, DNS queries against it return the individual pod IPs directly, and combined with `serviceName` on the StatefulSet, each pod also gets its own resolvable per-pod DNS name (`<pod-name>.<service-name>.<namespace>.svc.cluster.local`). Without it, StatefulSet pods still get stable *names* and stable *storage*, but nothing provides stable, individually addressable *network identity* â€” any client trying to reach "the primary at ordinal 0 specifically" (not just any pod behind a load-balanced VIP) has no way to do so.
**Follow-up trap:** *"If you forget the headless Service, does the StatefulSet fail to create, or does it silently work in a degraded way?"* â€” it doesn't fail outright; pods can still start and get stable names/storage, so the failure is silent and only surfaces when something tries to resolve per-pod DNS and gets nothing, which is exactly why this bug is common and annoying to diagnose after the fact rather than caught immediately at apply time.

### Q8 â€” Your CronJob "just stopped running" sometime after a multi-hour control-plane outage. What's the mechanism, and how do you confirm it?
**Testing:** knowledge of the 100-missed-schedules safety valve, a genuinely non-obvious behavior.
**Answer:** The CronJob controller, on catching up after being down, checks how many scheduled run times were missed since it last observed the CronJob; if that count is 100 or more, it treats catching up (firing a hundred-plus overlapping Jobs at once) as more dangerous than simply giving up, logs an error, and stops scheduling further runs for that CronJob until manually addressed. Confirm via `kubectl-controller-manager` logs for a "too many missed start times" style message, or via CronJob's own `status` conditions.
**Follow-up trap:** *"What's the fix â€” bump startingDeadlineSeconds?"* â€” no, `startingDeadlineSeconds` controls how late a *single* missed run can still start before being skipped, a different knob; the 100-missed-schedules valve isn't configurable, and the actual fix is investigating and resolving whatever kept the controller down that long, then manually triggering a Job if the missed run's work still needs to happen.

### Q9 â€” When would you deliberately choose `updateStrategy: OnDelete` over `RollingUpdate` for a StatefulSet?
**Testing:** whether they understand this as a real operational lever, not a vestigial option.
**Answer:** `OnDelete` means the StatefulSet controller does nothing automatically on a template change â€” pods only get the new template when manually deleted (and recreated by the controller). This is the right choice for workloads where an automated rolling update's ordering or timing can't be trusted to be safe for that specific stateful system â€” e.g., a database cluster where the operator (not raw StatefulSet mechanics) needs to drive exactly when each replica is safe to bounce, based on replication lag or leader status the StatefulSet controller has no visibility into.
**Follow-up trap:** *"Isn't that basically giving up the automation StatefulSet provides?"* â€” yes, deliberately: it's an acknowledgment that RollingUpdate's ordering guarantee (reverse-ordinal, wait-for-Ready) isn't sufficient for every stateful system's actual safety requirements, and this is precisely why most serious stateful workloads run behind an operator that manages the rollout itself using domain-specific health checks, rather than trusting either RollingUpdate or manual OnDelete alone.

### Q10 â€” What's the difference between an `initContainer` and a native sidecar container (1.29+), and why does the distinction matter for graceful shutdown?
**Testing:** awareness of a genuinely recent, high-value addition to the object model.
**Answer:** A normal `initContainer` runs to completion before any app container starts and then exits â€” it has no ongoing role during the pod's life. A native sidecar (an `initContainers` entry with `restartPolicy: Always`) also starts before app containers but keeps running alongside them for the pod's full lifetime, and critically, on pod termination it's guaranteed to be shut down *after* the app containers, not arbitrarily or concurrently â€” which is exactly the ordering a service mesh proxy needs (keep routing traffic until the app container has fully drained) that a plain sidecar pattern using a regular container in the `containers` list never reliably guaranteed.
**Follow-up trap:** *"Before 1.29, how did people work around the lack of this ordering guarantee?"* â€” commonly with `preStop` hooks and manual sleep-based delays trying to approximate "shut down after the app container," or accepting the race and occasionally losing the tail end of in-flight requests during a proxy's premature termination â€” a real, previously-unsolved gap that native sidecars close properly.

### Q11 â€” A Job with `completions: 10, parallelism: 3` â€” walk through what actually happens.
**Testing:** the completions/parallelism mechanic for non-indexed Jobs.
**Answer:** The Job controller keeps up to 3 pods running concurrently at any time, and as each pod succeeds, starts a new one, until 10 total pods have succeeded â€” so it's a moving window of at most 3 concurrent pods working through 10 total units of work, not 3 fixed pods each doing roughly 3.3 units. Failed pods (up to `backoffLimit`) don't count toward the 10 successes and trigger a replacement pod.
**Follow-up trap:** *"How would each pod know which chunk of work to do, if they're all running the same image with no differentiation?"* â€” that's exactly what non-indexed Jobs don't provide out of the box; either the application pulls work items from an external queue itself (each pod is interchangeable, grabs the next item), or you use `completionMode: Indexed`, which injects a `JOB_COMPLETION_INDEX` environment variable (0 through completions-1) into each pod so it can statically determine its own slice of work without needing an external queue.

### Q12 â€” Why does a slow-starting application commonly cause a rolling Deployment update to "hang" rather than fail outright, and what actually resolves it?
**Testing:** the interaction between readiness probes and `progressDeadlineSeconds`, a very common real incident pattern.
**Answer:** During a rolling update, the new ReplicaSet's pods must pass their readiness probe before the old ReplicaSet is scaled down further (bounded by `maxUnavailable`) and before the rollout is considered progressing. If the new pods are slow to become Ready (misconfigured `initialDelaySeconds`, a genuinely slow app startup, or a probe hitting an endpoint that isn't actually up yet), the rollout appears stuck at partial completion. It doesn't fail immediately â€” `progressDeadlineSeconds` (default **600 seconds**) has to elapse with no progress before the rollout is marked `Failed` â€” so for the first 10 minutes it just looks stuck, not broken.
**Follow-up trap:** *"Does `kubectl rollout status` block until the deadline, or does it tell you anything useful before then?"* â€” it blocks and reports live progress, but the earlier and more useful signal is `kubectl describe pod` on the new pods showing readiness probe failures directly, which tells you the actual cause well before the 10-minute deadline would otherwise expire and mark the rollout failed automatically.

### Q13 â€” Is it ever correct to run a production database directly as a StatefulSet with no operator?
**Testing:** the senior "when NOT to" judgment call.
**Answer:** Rarely, and it should be a deliberate, justified choice rather than a default â€” a bare StatefulSet gives you stable identity and per-pod storage, and nothing else: no automated failover, no backup scheduling, no safe rolling-upgrade ordering aware of replication state. For anything beyond a throwaway/dev environment, either use a managed database service or a purpose-built operator (CloudNativePG, the Postgres Operator, Strimzi for Kafka) that encodes the operational logic a raw StatefulSet spec has no concept of.
**Follow-up trap:** *"What's a legitimate reason to still do it bare, then?"* â€” a genuinely simple, low-stakes internal tool's database where the team explicitly accepts manual failover/backup responsibility in exchange for avoiding operator complexity, or a specific compliance/data-residency requirement that rules out managed cloud services entirely and where the team has the operational maturity to run it safely by hand â€” a narrow, named exception, not a general pattern.

---

## Red flags that fail you

- Creating bare Pods for anything meant to run continuously, with no owning controller.
- Not knowing that `restartPolicy: Always` is rejected on a Job, or confusing what `OnFailure` vs `Never` actually do to the pod count.
- Assuming StatefulSet scale-down automatically deletes PVCs â€” the default is `Retain` on both `whenScaled` and `whenDeleted`.
- Not knowing CronJob's `concurrencyPolicy` defaults to `Allow`, or recommending it without checking whether overlapping runs are safe for that workload.
- Forgetting that DaemonSet pods still respect taints/tolerations like any other pod and don't automatically run everywhere.
- Claiming a Deployment's selector can be changed via `kubectl apply` without acknowledging the immutability error.
- Treating `terminationGracePeriodSeconds`'s 30-second default as universally sufficient without considering the application's actual drain time.

---

## Cheat card

```
Pod: smallest unit, never bare in prod. restartPolicy: Always (default; required for
     Deployment/StatefulSet/DaemonSet), OnFailure/Never REQUIRED for Job (Always rejected)

DEPLOYMENT: selector.matchLabels IMMUTABLE after creation
  maxSurge 25% / maxUnavailable 25% (defaults, RollingUpdate)
  revisionHistoryLimit 10 (default), progressDeadlineSeconds 600s (default)

STATEFULSET: needs headless Service (clusterIP: None), serviceName must match
  DNS: <pod>.<svc>.<ns>.svc.cluster.local ; ordinals 0..N-1
  volumeClaimTemplates -> 1 PVC per replica, name <template>-<sts>-<ordinal>
  persistentVolumeClaimRetentionPolicy: whenScaled/whenDeleted default RETAIN (not deleted!)
  podManagementPolicy: OrderedReady (default, sequential) | Parallel
  updateStrategy: RollingUpdate (reverse ordinal order) | OnDelete (manual)

DAEMONSET: no `replicas` field â€” one pod per matching node automatically
  needs explicit tolerations for tainted nodes (control-plane, GPU, spot)
  updateStrategy.rollingUpdate.maxUnavailable default 1

JOB: completions / parallelism, backoffLimit default 6
  restartPolicy: OnFailure | Never ONLY (Always = API validation error)
  completionMode: NonIndexed (default) | Indexed (JOB_COMPLETION_INDEX env var)
  ttlSecondsAfterFinished: NOT set by default -> finished Jobs pile up forever, set it

CRONJOB: concurrencyPolicy default ALLOW (overlapping runs!) â€” most prod wants Forbid/Replace
  successfulJobsHistoryLimit 3 / failedJobsHistoryLimit 1 (defaults)
  >=100 missed schedules since controller downtime -> controller STOPS scheduling, manual fix

terminationGracePeriodSeconds default 30s: SIGTERM -> preStop hook -> wait -> SIGKILL
native sidecars (1.29+): initContainers entry w/ restartPolicy: Always, terminates LAST
```

## Sources

- [Kubernetes documentation â€” StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/) â€” accessed 2026-08-02
- [Kubernetes documentation â€” Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/) â€” accessed 2026-08-02
- [Kubernetes documentation â€” CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/) â€” accessed 2026-08-02
- [Kubernetes documentation â€” Sidecar Containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/) â€” accessed 2026-08-02
- [Kubernetes Interview Questions and Answers 2026 â€” DataCamp](https://www.datacamp.com/blog/kubernetes-interview-questions) â€” accessed 2026-08-02
- [33 Kubernetes Interview Questions and Answers for 2026 â€” Spacelift](https://spacelift.io/blog/kubernetes-interview-questions) â€” accessed 2026-08-02
- Kubernetes release notes 1.27-1.31 (CronJob timeZone GA, PVC retention policy, indexed Job pod failure policy)

## Changelog
- 2026-08-02 â€” created
