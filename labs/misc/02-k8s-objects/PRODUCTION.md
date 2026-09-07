# Production notes — the real reconcile loop

## The real thing is level-triggered, not edge-triggered

Your `reconcile()` is a pure function: same (desired, observed) → same actions, every call. That property is called **level-triggered** — the controller looks at the current *level* (state of the world), not the *edges* (events that happened). It is the single most important design decision in the Kubernetes control plane, and the one interviewers probe:

- **Idempotence is the point.** `kubectl apply` the same manifest twice → the second apply is a no-op. Your controller crashed halfway through a rolling update? Restart it, it re-reads levels, and continues. An edge-triggered system that missed an event is *wrong forever*; a level-triggered one is merely *behind* until the next reconcile.
- **The loop, in reality.** Every controller is: *watch* desired objects and observed children (informer caches, not per-request API calls) → *diff* → *act* → *requeue*. Watch events are just triggers to run the diff again, never inputs to it. A missed watch event is recovered by a periodic resync.
- **Why your reconcile ignores everything else.** Real controllers also own finalizers, owner references (for garbage collection), status subresources, and generation/observedGeneration bookkeeping. The diff stays dumb; the machinery around it is what grew.

## Controllers per kind — the lookup you memorise

| Kind | Controller (kube-controller-manager) | Owns |
|---|---|---|
| Deployment | deployment-controller (+ ReplicaSet) | rollouts, rollback |
| StatefulSet | statefulset-controller | ordered start/stop, ordinal identity, PVC binding |
| DaemonSet | daemonset-controller | one pod per eligible node |
| Job | job-controller | completions, parallelism, backoffLimit |
| CronJob | cronjob-controller | schedule → Job factories |

Each kind gets its own controller binary loop because each encodes a different answer to "which pods, where, and what identity?" — there is no generic one-size controller, which is *why* adding a kind means writing a controller (or an Operator).

## StatefulSet ordering — why web-1 waits for web-0

The statefulset-controller starts pods **one at a time, in ordinal order**, and will not create `web-1` until `web-0` is Running AND Ready (and terminates them in reverse). It exists for clustered software (databases, brokers) where the first bootstraps the cluster and the rest join it — concurrency there corrupts data. Production pressure point: if pod 0 is wedged and not Ready, the *entire set* stops scaling. Interview variant: "Your StatefulSet is stuck at 1/3 replicas — where do you look?" (`kubectl describe` the *pod*, not the StatefulSet; the controller is waiting on its readiness).

## DaemonSet — scheduling, not scaling

A DaemonSet doesn't scale — it *places*. One pod per node matching `spec.nodeSelector`/`affinity`, tolerated taints permitting. The classic production failure: a new node pool ships with a taint (e.g. `dedicated=observability:NoSchedule`) your agent doesn't tolerate → the DaemonSet silently runs on 29 of 30 nodes and nobody notices until an incident on the untolerated node. Your `schedulable()` check is the model of that: taint without a matching (key, effect) toleration → pod stays Pending. (Real tolerations add `operator: Exists` wildcarding and the default `node.kubernetes.io/not-ready:NoExecute` pair every pod carries.)

## CRDs + Operators — the production add

Everything in this lab is a *built-in* kind. The production pattern beyond it: define a Custom Resource Definition (`apiVersion: apiextensions.k8s.io/v1`) for your own domain object (e.g. `PostgresCluster`), and run an Operator — a reconcile loop over *your* CRD, usually written with Kubebuilder (Go) or Operator Framework/ Kopf (Python). The API server does the storage, validation, and RBAC; your controller does the diff-and-act. This is how StatefulSets-for-databases become *manageable* — the Operator adds leader election, failover, and backup logic that the core controller deliberately doesn't do.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Rollout "stuck", no errors | `selector.matchLabels` doesn't match template labels — the ReplicaSet adopts nothing | They're immutable: delete + recreate the Deployment |
| Apply rejected: field immutable | editing `spec.selector` on an existing Deployment | Same — immutability is deliberate (ownership ambiguity) |
| Pending pods on a node subset | taints without tolerations (new node pools are the usual source) | add explicit tolerations; monitor DaemonSet coverage per node |
| Service "works" but unreachable | wrong `spec.type` (e.g. forgot ClusterIP default vs NodePort), or selector matching zero pods | `kubectl get endpoints` — empty endpoints = label mismatch |
| Controller restarted mid-rollout, now what | nothing — it re-reads levels and resumes | this is level-triggered working, not a bug |
| `replicas: "3"` from a templating layer | YAML string vs int — kubectl catches it, CI templating often doesn't | `kubectl apply --dry-run=server`, and schema validation in CI |

## The 3 questions an interviewer asks after you describe this

1. *"Why four workload kinds instead of one with flags?"* — Each encodes a different identity/replication contract (interchangeable / ordinal-stable / node-permanent / run-to-completion). Flags would make the invalid combinations expressible; separate kinds make them unrepresentable. That's an API design answer, not a Kubernetes answer.
2. *"Controller restarts mid-rolling-update — does the rollout break?"* — No. On boot it diffs current Deployment/ReplicaSet levels vs the Pod reality and continues. Level-triggered means there's no event stream to lose.
3. *"When do you write a CRD + Operator instead of using a Deployment?"* — When the reconcile logic encodes domain knowledge beyond 'keep N pods alive' — leader election, failover, provisioning external resources. If your operator only ever creates a Deployment, you've built an indirection layer with nothing to reconcile.
