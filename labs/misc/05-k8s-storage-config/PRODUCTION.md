# Production notes — storage, config, and who's allowed to touch them

## CSI — the real storage layer

Your `bind()` matched claims against pre-existing PVs: **static provisioning**. Production is **dynamic** — the PVC names a `StorageClass`, and a **CSI driver** (Container Storage Interface) provisions the volume on demand. CSI is the plugin boundary that moved storage *out* of the Kubernetes core: pre-CSI, every vendor's driver was compiled in-tree, so a vendor bugfix needed a Kubernetes release. Post-CSI (GA 1.13, 2019), drivers ship as their own deployments (`ebs-csi-controller`, `gce-pd-csi-driver`, `azure-disk-csi`), and the in-tree plugins are frozen or removed. Your cloud's disk types are CSI parameters (`type: gp3`, `iopsPerGB: …`), not Kubernetes fields — the interview version: *"How does EBS actually get plugged into Kubernetes?"* → a CSI driver, two components (controller-side provisioning/attaching, node-side mount/unmount), CRDs for its own machinery (`VolumeAttachments`).

## WaitForFirstConsumer — why Immediate binding causes zone-mismatch

The single highest-impact StorageClass setting for zonal (per-AZ) disks:

- **`Immediate`**: the moment the PVC is created, the provisioner makes the volume — before any pod exists, so it has *no idea* which zone the consuming pod will land in. It picks (often round-robin) — say `us-east-1a`. Later the scheduler places the pod in `us-east-1b` (resource pressure, node affinity) — but the pod now *must* follow its bound PV's zone. Result: PVC says `Bound`, pod says `Pending` forever. This is the classic incident your `bind()` deliberately cannot reproduce, and the reason the failure is so confusing: every object looks healthy.
- **`WaitForFirstConsumer`**: provisioning is deferred until a pod referencing the PVC is *scheduled*; the provisioner then creates the volume in the zone the scheduler already chose. It's the correct default for essentially all zonal block storage.

Follow-up trap: *"The pod is already stuck this way — does switching the StorageClass fix it?"* No. `volumeBindingMode` only affects future provisioning; an already-bound wrong-zone PV means delete and recreate the PVC — with real data-loss risk if `reclaimPolicy: Delete`, which is exactly why getting it right at class-creation time matters.

## StorageClass defaults and reclaim in production

- A cluster can mark **one** default StorageClass (an `storageclass.kubernetes.io/is-default-class` annotation). A PVC with no `storageClassName` binds against it. Two defaults = undefined behavior and a support ticket; changing the default does not rebind existing PVCs.
- **`reclaimPolicy: Delete`** is the common dynamic default — PVC deleted → disk deleted. Fast, convenient, and the wrong default for anything with state you can't regenerate. **`Retain`** orphans the disk (PV moves to `Released`, needs manual admin action to reuse) precisely so a fat-fingered `kubectl delete` doesn't destroy production data. Your lab default is Delete; the production *decision* is "Retain for anything whose data has real value."
- **`Recycle`** (`rm -rf` the volume) is deprecated — don't mention it as a current option without saying so.

## Secrets: base64 is encoding, not encryption — and immutability

- Secret values are base64-*encoded* in etcd: trivially reversible by anyone with etcd read access. Real encryption at rest needs `EncryptionConfiguration` on the API server with a **KMS v2** provider (v1 deprecated 1.28, off by default 1.29), key material in a cloud KMS.
- Since **1.21**, Secrets can be `immutable: true` — kubelet and API server stop watching them, which cuts watch traffic dramatically for huge Secrets (the kubelet's periodic resync of large config objects is real load at scale), and prevents accidental updates. Rotation path: create a *new* Secret and update the reference — which is how you'd rotate safely anyway.
- Mount-vs-env update semantics (the shared gotcha): volume-mounted ConfigMap/Secret files sync automatically within ~a minute (kubelet); env-var injection is resolved once at pod start and needs a rollout restart. Mixing both for the same config is how "I updated the config and nothing changed" incidents happen.

## RBAC — what your `RoleBindingSim` leaves out, and escalation risks

- The real authorizer unions every Role/ClusterRole bound to the identity — RBAC has **no deny rule**; effective permissions only grow. That's why the audit finding is always a ServiceAccount with `cluster-admin` "temporarily" granted months ago: nothing ever subtracts.
- **Escalation risks an interviewer expects you to name:** `escalate`/`bind`/`impersonate` verbs (with these you can grant yourself more — `kubectl auth can-i --list` first); `create` on `pods/exec` or `pods/portforward` = code execution in any pod you can name, bypassing what `get pods` suggests; `create` on `secrets`/`serviceaccounts/token` = mint credentials; a `ClusterRoleBinding` to a workload that only needed a namespaced `Role`; and `ClusterRole` via `RoleBinding` — legal and common (reusable permission set granted per-namespace), the *reverse* (namespaced Role via ClusterRoleBinding) is not.
- Real Role rules are per `apiGroup` with `resourceNames` scoping — `"get", "pods", resourceNames: ["my-pod"]` is the shape of least privilege. Auditing: `kubectl auth can-i --list --as=system:serviceaccount:ns:sa` against actual audit-log usage, then cut over measured, not blind-revoke.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Pod Pending, PVC Bound | Immediate binding on a zonal class | WaitForFirstConsumer; recreate the PVC (mind the reclaim policy) |
| Disk still billed after PVC deleted | Retain leaves orphaned Released PVs | Reconcile Released PVs; Retain only where data value justifies it |
| Two StorageClasses both "default" | annotations added twice | Exactly one default; change with care — existing PVCs keep their class |
| Secret rotation breaks pods | env-var injection is frozen at start | Mount as volume, or rollout restart on change; immutable Secrets → new object + reference update |
| Watch traffic saturates API server | huge frequently-synced ConfigMaps/Secrets | `immutable: true`, split config, or external store |
| SA can do far more than it uses | accumulated bindings, wildcards | audit actual verbs, scope to exactly that set |

## The 3 questions an interviewer asks after you describe this

1. *"PVC is Bound but the pod is Pending — first thing you check?"* — the PV's zone vs the pod's node: `Immediate` binding mode on zonal storage. `WaitForFirstConsumer` is the fix; an already-bound PV means recreating the PVC.
2. *"Delete the PVC — what happens to the data?"* — whatever `reclaimPolicy` says: Delete destroys the disk, Retain orphans it (Released, manual cleanup). Name your default for reproducible data vs irreplaceable data.
3. *"Why can't I just deny one permission the SA has?"* — RBAC is purely additive; the fix is removing/narrowing the binding or splitting the identity, not adding a deny rule.
