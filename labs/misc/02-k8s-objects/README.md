# Lab 02: K8s Objects — The Object Model, Reconciled

**Track:** T12 DevOps, Infra & Security · **Time:** 2.5h · **XP:** 50
**Module:** `T12-k8s-objects`

**You will build:** a hand-rolled manifest loader, an object validator, a workload-kind recommender, a level-triggered reconcile function, and a taints/tolerations schedulability check — pure stdlib, no cluster, no PyYAML.

**You will be able to answer:** *"Kubernetes has four workload controllers — why four, and what actually happens between `kubectl apply` and a running Pod?"*

## Setup

```bash
cd labs/misc/02-k8s-objects
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`load_manifest(text)`** → list of dicts, one per document. A deliberately minimal YAML subset — no PyYAML:
   - a line containing only `---` starts a new document; empty documents are dropped;
   - `key: value` at indent 0 → top-level; `  key: value` (indent 2) → nested under the last indent-0 key;
   - `key:` with no inline value opens a nested block (`metadata:`, `spec:`);
   - scalars: one pair of matching quotes is stripped; numeric values become `int`, everything else stays `str`.
2. **`validate_object(doc)`** → list of problem strings; empty means valid.

   | Fires when | Problem string |
   |---|---|
   | `apiVersion` missing | `missing apiVersion` |
   | `kind` missing | `missing kind` |
   | `metadata.name` missing | `missing metadata.name` |
   | Deployment: `spec.replicas` missing or not an `int` | `spec.replicas must be an int` |
   | Deployment: `spec.selector.matchLabels` missing | `missing spec.selector.matchLabels` |
   | Deployment: selector labels ≠ `spec.template.metadata.labels` | `selector matchLabels do not match template labels` |
   | Service: `spec.type` not one of ClusterIP/NodePort/LoadBalancer/ExternalName | `spec.type must be one of ClusterIP, NodePort, LoadBalancer, ExternalName` |

   The first three run on every kind; the rest are kind-specific. One defect → exactly one problem.
3. **`recommend_kind(requirements)`** → kind string, by priority: `cron` → `CronJob`; `batch` → `Job`; `singleton` or `stateful` → `StatefulSet` (a singleton is a StatefulSet with `replicas: 1`); `node-agent` → `DaemonSet`; everything else — `stateless-web`, unknown tags, empty — defaults to `Deployment`.
4. **`reconcile(desired, observed)`** → list of action strings. Both sides are `{"replicas": n, "image": str}`. `replicas` differ → `scale to <n>`; `image` differs → `rolling update to <image>` — both values from **desired**, scale listed before image. Identical specs → `[]`. It must be a pure function of (desired, observed): same inputs → same actions, every call. That property is the whole point — it is called *level-triggered*.
5. **`schedulable(pod, taints)`** → bool. `pod["tolerations"]` and `taints` are lists of `{"key", "effect"}`. True iff **every** taint has a toleration with the same key **and** effect. No taints → True.

## Run the tests

```bash
python -m pytest tests -q                 # against starter/ → FAILS. Make them pass.
python -m pytest tests -q --solution      # the reference — all green
```

## Stretch goals

1. **Depth-3 YAML** — extend the parser to indent 4+ (a stack, not the last-key hack) so `spec.template.spec` parses. *("Why does no production controller hand-parse manifests?")*
2. **Rolling update planner** — `reconcile` that takes `maxSurge`/`maxUnavailable` and emits an ordered action list. *("What does `maxUnavailable: 0` guarantee, and what does it cost?")*
3. **StatefulSet ordering** — a reconcile variant that will not start `web-1` until `web-0` is Ready. *("Why does a StatefulSet boot one replica at a time?")*
4. **Admission webhook** — a mutate step that injects missing labels, so a selector-mismatched Deployment never reaches etcd. *("Dry-run vs admission — where does each one catch the bug?")*
