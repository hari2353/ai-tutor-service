# Lab 05: K8s Storage & Config — PV/PVC, Mounts, RBAC

**Track:** T12 DevOps, Infra & Security · **Time:** 2h · **XP:** 50
**Module:** `T12-k8s-storage-config`

**You will build:** a PV/PVC binding simulator with reclaim policies, a volume-mount validator for pod specs, a ConfigMap/Secret exposure generator, and a namespaced-vs-cluster RBAC checker — pure stdlib, no cluster.

**You will be able to answer:** *"The PVC is Bound but the pod is Pending — walk me through why, and what do `reclaimPolicy` and `volumeBindingMode` have to do with it?"*

## Setup

```bash
cd labs/misc/05-k8s-storage-config
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **Objects** (dataclasses, given — the functions are the TODOs): `PersistentVolume(name, capacity, access_modes, storage_class="standard", reclaim_policy=None, claim_ref=None)` and `PersistentVolumeClaim(name, capacity, access_modes, storage_class="standard")`. `capacity` is an int in Gi; access modes are `ReadWriteOnce` / `ReadOnlyMany` / `ReadWriteMany` / `ReadWriteOncePod`; `claim_ref` is None until the PV is bound — PV↔PVC binding is 1:1.
2. **`bind(pvs, pvc)` → `(matched_pv_name, reason)`** — skip PVs whose `claim_ref` is already set (Bound, unavailable); candidates need `pv.capacity >= pvc.capacity`, at least one access mode in common, and the same storage class (default `"standard"` when unset). Among survivors pick the **smallest sufficient capacity** (tie → the one listed first), set its `claim_ref` to the claim's name, and return a reason starting with `"bound"`. No survivor → `(None, reason)` where reason names the first gate that eliminated every candidate:

   | Every candidate fails at | reason starts with |
   |---|---|
   | capacity | `capacity: …` |
   | access mode (among capacity-sufficient) | `accessmode: …` |
   | storage class | `class: …` |

3. **`pv_reclaim(policy, pv, claim_deleted)` → action string** — reclaim only fires once the claim is gone: `claim_deleted=False` → `"claim still bound - pv unchanged"`. Policy resolution: the explicit `policy` arg, else `pv.reclaim_policy`, else **`Delete` — the dynamic-provisioning default** (dynamically-provisioned StorageClasses default to Delete; Retain is the deliberate choice for data you can't regenerate):

   | policy | action |
   |---|---|
   | `Retain` | `"pv kept, Released status"` |
   | `Delete` | `"pv deleted"` |
   | `Recycle` | `"pv scrubbed"` (deprecated upstream — kept here for the interview) |

4. **`DeploymentMount().validate(pod_spec)` → list of problem strings** (empty = valid). `pod_spec` shape:

   ```python
   {"volumes": [{"name": "data",
                 "persistentVolumeClaim": {"claimName": "data"}   # or
                 "configMap": {"name": "cfg"}                     # or
                 "emptyDir": {}}],
    "containers": [{"volumeMounts": [{"name": "data", "mountPath": "/data"}]}]}
   ```

   | Fires when | problem string |
   |---|---|
   | a `volumeMounts[].name` with no matching declared volume | `dangling mount {name}` |
   | a declared volume no container mounts | `unused volume {name}` |
   | `mountPath` doesn't start with `/` | `mountPath must be absolute: {path}` |

   Missing keys count as empty lists. Tests assert by exact string membership, not order.
5. **`expose(kind, keys, as_env=True)`** — render a ConfigMap/Secret's keys the two ways a pod can consume them. `kind` is `"ConfigMap"` or `"Secret"` (case-insensitive; anything else raises `ValueError`).
   - **Env form** (`as_env=True`): one entry per key — `{"name": ENV, "valueFrom": {"configMapKeyRef" | "secretKeyRef": {"key": key}}}`. Env var name = **key uppercased with `-` and `.` replaced by `_`**: `"my-key"` → `MY_KEY`, `"db.url"` → `DB_URL`. (Real `envFrom` is stricter — keys that aren't valid env-var names get *skipped* with an `InvalidEnvironmentVariableNames` event; transformation is the pattern that keeps every key consumable.)
   - **Volume form** (`as_env=False`): one file path per key — `/etc/configmap/{key}` or `/etc/secret/{key}`, key unchanged.
6. **`RoleBindingSim(roles, bindings)` + `.can(subject, verb, resource, namespace=None)` → bool**:

   ```python
   roles = {"configmap-reader": {"verbs": ["get", "list"], "resources": ["configmaps"],
                                 "namespace": "prod"},    # namespace key -> namespaced Role
            "logs-viewer":     {"verbs": ["get"], "resources": ["pods"]}}  # no key -> ClusterRole
   bindings = {"worker-sa": "configmap-reader", "auditor-sa": "logs-viewer"}
   ```

   No binding for the subject → `False` (**default deny**); dangling role name → `False`; verb not in the role's verbs or resource not in its resources → `False`. A namespaced Role is `True` only when `namespace` equals the role's namespace; a ClusterRole is `True` in any namespace, including none passed.

## Run the tests

```bash
python -m pytest tests -q                 # against starter/ → FAILS. Make them pass.
python -m pytest tests -q --solution      # the reference — all green
```

## Stretch goals

1. **WaitForFirstConsumer** — add `zone` to PVs and a known consumer zone to the claim; `Immediate` binds before the zone is known (wrong-zone bind possible), `WaitForFirstConsumer` defers until the consumer's zone is set. *("Why does Immediate binding cause zone-mismatch with zonal disks?")*
2. **StorageClass defaults** — multiple classes with one flagged default; a PVC with no class resolves against the default; two defaults is an error. *("What breaks when a cluster ends up with two default StorageClasses?")*
3. **Immutable Secrets (1.21+)** — an expose() variant that emits the immutable flag, and a rotation path that creates a new object instead of updating. *("Why would you deliberately make a Secret unchangeable?")*
4. **RBAC union** — let a subject hold several roles; effective permissions are the union, and there is no deny rule. *("RBAC can't subtract — how do you un-grant a permission?")*
