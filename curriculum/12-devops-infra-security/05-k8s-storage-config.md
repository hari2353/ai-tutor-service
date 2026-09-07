# PV/PVC/StorageClass, ConfigMaps, Secrets, ServiceAccounts, RBAC

> **Track:** T12 DevOps, Infra & Security Â· **Time:** 2h Â· **Prereqs:** T12-k8s-objects, T12-k8s-core Â· **Updated:** 2026-08-02
> **Module id:** `T12-k8s-storage-config` Â· **Tags:** k8s
> **Lab:** `labs/misc/05-k8s-storage-config/`

## The 30-second version

A PersistentVolumeClaim is a request for storage matching a size and access mode; a StorageClass with a CSI provisioner fulfills that request on-demand (dynamic provisioning) rather than requiring an admin to pre-create volumes, and `volumeBindingMode: WaitForFirstConsumer` (not the default `Immediate`) is what prevents a real, common bug: binding a zonal volume before the scheduler has picked a zone for the pod, producing a permanently unschedulable pod stuck in a zone mismatch. ConfigMaps and Secrets both inject config into pods, but they update completely differently â€” volume-mounted values sync live within roughly a minute, environment-variable-injected values are captured once at pod start and never update without a restart. Kubernetes Secrets are **base64-encoded, not encrypted**, by default â€” stored as plaintext-equivalent in etcd, fully readable by anyone with etcd access unless `EncryptionConfiguration` with a real KMS provider is explicitly configured, which most clusters don't have turned on. ServiceAccount tokens changed fundamentally in **1.24**: instead of an auto-generated, indefinitely-valid Secret-mounted JWT, pods now get a **bound token** via the TokenRequest API â€” time-limited (1 hour default, kubelet-refreshed), audience-scoped, and tied to that specific pod's lifetime, closing the "leaked token still works six months after the pod is gone" incident class. RBAC's most commonly flagged real-world finding, in nearly every pentest and CIS benchmark audit, is a wildcard grant (`resources: ["*"]`, `verbs: ["*"]`) introduced to "get something working" and never tightened.

## Why this gets asked

Because "base64 isn't encryption" is the single most cited-but-still-current Kubernetes security gap â€” teams that know it in the abstract still ship clusters without `EncryptionConfiguration` configured, and an interviewer who's done a security review has almost certainly found exactly that gap in a real audit. Storage binding-mode bugs (a PVC bound to the wrong availability zone before the pod is even scheduled) produce a specific, confusing failure â€” a pod that's healthy in every way except permanently `Pending` â€” that only makes sense once you understand *when* dynamic provisioning actually happens relative to scheduling. And RBAC wildcard grants are the top finding in essentially every Kubernetes security audit published in the last several years, which means "can you actually read and critique a Role" is a very live, very practical skill being tested here, not trivia.

---

## Lineage: past â†’ present â†’ future

**What came before.** Early container storage was host-path bind mounts â€” whatever directory happened to exist on whichever node a container landed on, with zero portability if that container rescheduled elsewhere, and no concept of "give me N gigabytes with these properties" as a request the platform fulfills. Kubernetes's PersistentVolume/PersistentVolumeClaim split (present from an early release, maturing through the 1.0-1.9 era) separated "what storage exists" (PV, an infrastructure/admin concern) from "what a workload needs" (PVC, an application concern) â€” but initially required **static provisioning**: a cluster admin manually pre-creating PV objects (and the underlying cloud volumes) ahead of every possible claim, real, tedious operational overhead that didn't scale to a platform serving many teams self-service. Storage drivers were originally **in-tree** â€” cloud-provider-specific volume code compiled directly into kubelet and the controller manager â€” meaning any new storage feature or bug fix had to ship as part of a full Kubernetes core release, coupling storage vendor velocity to the entire project's release cadence, a real bottleneck as the number of supported storage backends grew.

**Where it stands now.** StorageClass plus dynamic provisioning (matured mid-cycle, roughly 1.4-1.6) let a provisioner create the PV on-demand the moment a PVC references a class, eliminating the pre-provisioning bottleneck entirely. The Container Storage Interface (CSI, stabilizing around 1.13) externalized storage drivers into out-of-tree, independently-released plugins with their own versioning and release cadence â€” nearly all cloud and on-prem storage integrates via CSI today, and in-tree volume plugins have been progressively deprecated and removed in favor of it. Secrets' base64-only default remains, unresolved, exactly the gap it's always been â€” every CIS Kubernetes Benchmark and most security frameworks flag unencrypted Secrets as a baseline finding, and the fix (`EncryptionConfiguration` with a KMS provider) is opt-in, not default, which is precisely why it keeps showing up in real audits years after the fix has existed. ServiceAccount token security, by contrast, has genuinely moved: **1.22+** introduced bound tokens (time-limited, audience-bound, object-bound via the TokenRequest API), and **1.24** stopped auto-generating long-lived Secret-based tokens for every ServiceAccount by default â€” a direct, deliberate response to years of incidents where a token exfiltrated from a compromised pod kept working indefinitely, long after that pod was gone, with no built-in expiry to bound the damage. The live disagreement in this space isn't about these mechanics, it's about RBAC's expressiveness ceiling: RBAC's flat verb/resource/apiGroup model handles coarse "can this identity touch this resource type" access well, but has no native concept of conditional/attribute-based rules (time of day, request payload content, resource labels beyond `resourceNames`), which is why admission policy engines (OPA Gatekeeper, Kyverno) commonly sit alongside RBAC rather than being replaced by it â€” most practitioners land on "RBAC for coarse access, a policy engine for anything conditional," not a belief that RBAC alone should or could cover everything.

**Where it's heading.** Secrets-store CSI driver integration (mounting secrets live from an external vault â€” AWS Secrets Manager, HashiCorp Vault, Azure Key Vault â€” directly into a pod via a CSI volume, without ever creating a native Kubernetes `Secret` object at all) is growing specifically to sidestep the base64-in-etcd problem structurally rather than just encrypting around it, and is increasingly the recommended pattern for genuinely sensitive material in security-conscious organizations. The clear direction on ServiceAccount tokens is continued tightening â€” shorter default lifetimes, narrower audience scoping â€” following directly from the 1.24 change, with no indication of reversing course.

---

## Mental model

```
STORAGE:
  PVC (app: "I need 20Gi, ReadWriteOnce, class=fast-ssd")
        â”‚
        â–¼
  StorageClass "fast-ssd"  { provisioner: ebs.csi.aws.com,
                              volumeBindingMode: WaitForFirstConsumer,
                              reclaimPolicy: Delete }
        â”‚
        â”‚  binding/provisioning TIMING depends on volumeBindingMode:
        â”‚
        â”œâ”€â”€ Immediate (default): PV created/bound the INSTANT the PVC
        â”‚     is created â€” BEFORE any pod exists, so the provisioner has
        â”‚     no idea which zone the pod will eventually be scheduled to
        â”‚
        â””â”€â”€ WaitForFirstConsumer: binding/provisioning DELAYED until a
              pod referencing this PVC is actually scheduled â€” provisioner
              creates the volume in the SAME zone the scheduler picked
        â”‚
        â–¼
  CSI driver creates the actual cloud volume, PV object created/bound to PVC

CONFIG PROPAGATION:
  ConfigMap/Secret --volume mount--> kubelet syncs periodically (~1 min delay) -> LIVE update
  ConfigMap/Secret --env var------->  captured ONCE at pod start -> NEVER updates without restart

SECRETS AT REST:
  Secret object -> API server -> etcd, stored as base64 (NOT encrypted) BY DEFAULT
  base64 is trivially reversible -> etcd access = full plaintext secret access
  ONLY real encryption if EncryptionConfiguration + KMS provider explicitly configured

SERVICEACCOUNT TOKENS (1.24+ default):
  Pod -> TokenRequest API -> bound token: time-limited (1h, kubelet-refreshed),
         audience-scoped (this API server only), object-bound (dies with the pod)
  delivered via a projected volume kubelet actively refreshes, NOT a static Secret

RBAC:
  Role (namespaced) / ClusterRole (cluster-scoped, but bindable per-namespace too)
       { apiGroups, resources, verbs, [resourceNames] }
  RoleBinding / ClusterRoleBinding -> grants Role/ClusterRole to a Subject
       (User | Group | ServiceAccount)
```

---

## How it actually works

### PV/PVC/StorageClass fields that matter

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: ebs.csi.aws.com          # CSI driver name
parameters:
  type: gp3
reclaimPolicy: Delete                  # default for dynamic provisioning â€” underlying
                                        # cloud volume is deleted when the PVC is deleted
volumeBindingMode: WaitForFirstConsumer  # NOT the default (Immediate is) â€” see below
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  storageClassName: fast-ssd
  accessModes: ["ReadWriteOnce"]       # RWO: one node at a time (most block storage)
                                        # RWX: many nodes concurrently (needs NFS/EFS-like
                                        #      backend â€” most block storage, e.g. EBS, is
                                        #      RWO only, not RWX)
                                        # ReadWriteOncePod (newer, stricter): single POD,
                                        #      not just single node â€” prevents two pods on
                                        #      the same node from both mounting it
  resources:
    requests:
      storage: 20Gi
```

`volumeBindingMode: Immediate` (the field's default when unset) provisions and binds the volume the instant the PVC is created â€” before the scheduler has assigned the pod using it to any node at all. For zonal block storage (an EBS volume, for instance, which physically exists in one specific availability zone and can only attach to nodes in that same zone), this is a real, common bug: the volume gets created in whatever zone the provisioner happens to pick, and if the scheduler later decides â€” based on completely independent criteria like resource availability or affinity rules â€” to place the pod in a *different* zone, the pod becomes permanently unschedulable, because it now needs a volume that physically cannot attach to any node in the zone it's stuck being placed in. `WaitForFirstConsumer` fixes this by deferring binding/provisioning until a pod referencing the PVC is actually scheduled, so the provisioner creates the volume in whatever zone the scheduler already committed to â€” the correct default for any zonal storage backend, even though it isn't the field's actual default value.

`reclaimPolicy: Delete` (the default for dynamically provisioned volumes) means deleting the PVC deletes the underlying cloud volume too â€” fine for ephemeral or easily-reproducible data, dangerous for anything genuinely irreplaceable, where `Retain` (leaving the PV and underlying volume intact, requiring manual cleanup/reattachment) is the safer choice despite the operational overhead of not having automatic cleanup.

### ConfigMap and Secret propagation â€” a real operational gotcha

Volume-mounted ConfigMaps and Secrets are kept in sync by the kubelet's periodic sync loop â€” a change to the source object propagates to every pod with it mounted as a volume within roughly the kubelet's sync period (commonly cited around **one minute**, plus any additional TTL-based caching layer in front of the API server), with **no pod restart required**. Environment-variable injection (`envFrom`/`valueFrom.configMapKeyRef`) behaves completely differently: the value is read and baked into the container's environment exactly once, at pod start â€” it **never** updates for the life of that pod, no matter how many times the source ConfigMap or Secret changes, and the only way to pick up a new value is to actually recreate the pod (commonly automated via a checksum annotation on the pod template that changes whenever the referenced ConfigMap's content changes, forcing a rollout). Teams that expect "hot config reload" from env-var-injected values and don't get it are hitting exactly this, not a bug.

### Secrets â€” base64 is not encryption, and neither is the default

```
# what's actually stored in etcd by default for a Secret with data "password: hunter2":
data:
  password: aHVudGVyMg==     # this is base64("hunter2"), NOT ciphertext.
                               # `echo aHVudGVyMg== | base64 -d` recovers it instantly.
```

Base64 is an *encoding*, chosen because Secret values need to safely represent arbitrary binary data in JSON/YAML text, not a security mechanism â€” it has no key, no confidentiality property, and is trivially reversible by anyone who can read the raw object, whether via `kubectl get secret -o yaml`, direct etcd access, or a leaked etcd snapshot/backup. Actual encryption at rest requires explicitly configuring `EncryptionConfiguration` on the API server:

```yaml
# untested sketch â€” API server --encryption-provider-config
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources: ["secrets"]
  providers:
  - kms:
      apiVersion: v2
      name: aws-kms
      endpoint: unix:///var/run/kmsplugin/socket.sock  # calls out to AWS KMS for every
                                                          # encrypt/decrypt operation
  - identity: {}   # fallback â€” MUST be last; new writes use the first provider listed,
                    # reads try providers in order for backward compatibility
```

A local AES-CBC/AES-GCM provider (a static key in a file on the control plane) is strictly better than nothing but doesn't protect against a full control-plane compromise, since the key material lives right there alongside what it protects. A **KMS provider** (AWS KMS, Azure Key Vault, GCP KMS) is the production-grade answer: the actual data-encryption-key material is never persisted locally at all, every encrypt/decrypt operation calls out to the external, hardware-backed KMS, and this gets you automatic rotation, audit logging, and a genuine separation between "who can read etcd" and "who can decrypt what's in it." Critically: **enabling `EncryptionConfiguration` does not retroactively encrypt existing Secrets** â€” only newly written or updated objects get encrypted under the new configuration; existing Secrets remain in their old (base64-only, or whatever the previous provider was) form until they're rewritten, which is why the standard rollout procedure explicitly includes a follow-up step to force-rewrite every existing Secret (`kubectl get secrets --all-namespaces -o json | kubectl replace -f -`, or an equivalent bulk touch) after turning encryption on. And even with KMS-backed encryption at rest fully configured, that only protects Secrets *in etcd* â€” anything mounted into a running pod is fully readable by anyone with `exec`/shell access to that pod or sufficient RBAC to read the Secret object directly via the API, so etcd encryption alone does not solve secret sprawl or over-broad access inside the cluster.

### ServiceAccount tokens â€” what actually changed and why

Before **1.24**, creating a ServiceAccount auto-generated a companion Secret containing a long-lived JWT with no built-in expiry, automatically mounted into every pod using that ServiceAccount by default. This was a real, standing liability: if any pod was compromised, the exfiltrated token worked indefinitely â€” not scoped to that pod's lifetime, not time-limited, and usable from anywhere an attacker could reach the API server, long after the original pod was gone. **1.24+ stopped this auto-generation by default.** Instead, pods get tokens via the **TokenRequest API** (the `serviceaccounts/token` subresource): **bound tokens** that are time-limited (**1 hour default lifetime**, though the kubelet proactively refreshes the token before it expires, so a long-running pod's mounted token stays continuously valid without ever going stale), **audience-bound** (scoped to a specific intended recipient, typically the API server itself, rather than a generic bearer token usable against anything that trusts a JWT signed by the cluster), and **object-bound** (tied to the specific pod's lifetime â€” the token becomes invalid the moment that exact pod is deleted, regardless of its nominal 1-hour expiry). These are delivered via a **projected volume** the kubelet actively keeps current, not a static mounted Secret file that sits unchanged for the container's entire life. This closes exactly the incident class described above: a leaked bound token has a narrow, bounded blast radius by construction, not by operational diligence someone has to remember to apply.

### RBAC â€” Role/ClusterRole and the wildcard trap

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: payments
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]        # NOT ["*"] â€” least privilege, explicit verbs
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: payments
  name: read-pods
subjects:
- kind: ServiceAccount
  name: monitoring-agent
  namespace: payments
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

`Role` is always namespace-scoped; `ClusterRole` is cluster-scoped by nature but can *also* be bound within a single namespace via an ordinary `RoleBinding` referencing it â€” a common, deliberate pattern for defining a reusable permission set once (e.g. "read pods and logs") and granting it per-namespace without duplicating the `Role` object in every namespace that needs it. The single most commonly flagged real-world finding across Kubernetes pentests and CIS benchmark audits is a wildcard grant â€” `resources: ["*"]`, `verbs: ["*"]`, or both combined with `apiGroups: ["*"]` â€” typically introduced early "to get something working" during initial setup and never revisited, effectively granting cluster-admin-equivalent access far beyond what was intended. A second, less obvious but equally real risk: RBAC access to the `serviceaccounts/token` subresource itself. Anyone with `create` permission on `serviceaccounts/token` can mint a fresh bound token impersonating that ServiceAccount at will â€” meaning granting that specific permission is functionally equivalent to granting everything that ServiceAccount itself can do, and it needs exactly that level of scrutiny, not the lighter treatment "just a token" implies.

---

## Build it from scratch

The combination worth being able to write from memory, since each piece independently fixes a real, common misconfiguration:

```yaml
# untested sketch â€” zonal-storage-safe StorageClass + PVC
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: zonal-fast
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer   # <- prevents the zone-mismatch Pending bug
reclaimPolicy: Retain                      # <- deliberate: don't auto-delete real data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata: { name: orders-data }
spec:
  storageClassName: zonal-fast
  accessModes: ["ReadWriteOnce"]
  resources: { requests: { storage: 50Gi } }
---
# least-privilege ServiceAccount + Role, no wildcards, no auto-mounted token
# for a pod that doesn't need broad API access
apiVersion: v1
kind: ServiceAccount
metadata: { name: orders-api }
automountServiceAccountToken: false   # <- explicit: this workload never calls the API
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: { namespace: payments, name: orders-configmap-reader }
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["orders-config"]     # <- object-level restriction, not "any configmap"
  verbs: ["get", "watch"]              # <- not "list", not "*" â€” exactly what's needed
```

`automountServiceAccountToken: false` is worth calling out explicitly: any pod that never actually calls the Kubernetes API shouldn't have a token mounted into it at all â€” this reduces blast radius directly (nothing to exfiltrate) rather than relying on RBAC alone to make an unused, present token harmless.

---

## How it's done in production

Genuinely sensitive material (payment credentials, third-party API keys with broad scope) increasingly bypasses native Kubernetes `Secret` objects entirely via the **Secrets Store CSI Driver** or an operator like **External Secrets Operator**, pulling live from Vault/AWS Secrets Manager/Azure Key Vault directly into a mounted volume â€” sidestepping the base64-in-etcd exposure structurally rather than layering encryption around it. GitOps workflows that need to commit *something* representing a secret to version control commonly use **Sealed Secrets** (client-side encrypted before commit, only the in-cluster controller holding the private key can decrypt) rather than committing plaintext or base64 (which, again, is not encryption) directly. `cert-manager` automates TLS certificate issuance and rotation as Secret objects, itself a good example of "secrets that rotate on a schedule with no human in the loop." Policy engines (OPA Gatekeeper, Kyverno) commonly enforce organization-wide guardrails RBAC alone can't express cleanly â€” "no wildcard verbs/resources in any Role," "`automountServiceAccountToken` must be explicitly set," "no Secret without an owning NetworkPolicy-equivalent access boundary."

| Symptom | Cause | Fix |
|---|---|---|
| Pod permanently `Pending`, its PVC shows `Bound` | `volumeBindingMode: Immediate` bound the volume to a zone before the scheduler placed the pod, and the pod later got scheduled (or could only be scheduled) to a different zone the volume can't attach to | Use `WaitForFirstConsumer` for any zonal storage backend; for an already-broken PVC, delete and recreate it so provisioning happens after scheduling this time |
| Secret value recovered from an etcd snapshot or backup by someone who shouldn't have access | No `EncryptionConfiguration` configured â€” Secrets are base64 only | Configure `EncryptionConfiguration` with a KMS provider, then force-rewrite all existing Secrets (enabling the config doesn't retroactively re-encrypt what's already stored) |
| ConfigMap updated, application still serving stale config | Value is env-var-injected (captured once at pod start) rather than volume-mounted, or a volume-mounted change hasn't propagated within the kubelet sync window yet | For env vars, force a pod rollout (commonly via a checksum annotation on the pod template tied to the ConfigMap's content); for volume mounts, confirm the app is actually watching the mounted file for changes rather than only reading it once at its own startup |
| A leaked token from months ago still authenticates successfully against the API server | ServiceAccount predates 1.24 semantics, or someone manually created a long-lived Secret-based token instead of using TokenRequest-based bound tokens | Migrate to bound tokens (the 1.24+ default path via `kubectl create token` / projected volumes); explicitly delete any lingering long-lived Secret tokens and audit for other ServiceAccounts with the same legacy pattern |
| Pentest/audit finds a namespace-scoped ServiceAccount can effectively do cluster-admin-level things | A wildcard RBAC grant (`resources: ["*"]`/`verbs: ["*"]`), or unrestricted `create` on `serviceaccounts/token` letting it mint tokens for a more-privileged ServiceAccount | Audit with `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<name>`; replace wildcards with explicit resource/verb lists; treat `serviceaccounts/token` create access with the same scrutiny as the target ServiceAccount's full permission set |
| A RWX (`ReadWriteMany`) PVC request fails to provision on a common cloud CSI driver | The default/expected block storage CSI driver (e.g. `ebs.csi.aws.com`) only supports `ReadWriteOnce`, not `ReadWriteMany` | Use a storage backend that genuinely supports concurrent multi-node mounts (EFS, Azure Files, NFS-backed storage classes) rather than assuming any StorageClass can satisfy any access mode |

---

## Tradeoffs & when NOT to use it

- **Don't store large or highly dynamic blobs in ConfigMaps or Secrets.** Both live in etcd, and etcd is tuned for small objects at moderate write volume (the same constraint discussed for the control plane's quota/compaction behavior) â€” large or frequently-changing config belongs in object storage referenced by a small pointer, not stuffed into a ConfigMap that balloons toward etcd's practical size limits.
- **Don't treat native Kubernetes Secrets, even with KMS-backed `EncryptionConfiguration`, as equivalent to a dedicated secrets manager for genuinely high-sensitivity material.** It solves etcd-at-rest exposure specifically, but doesn't provide the fine-grained access audit trail, seamless application-transparent rotation, or HSM-backed guarantees a dedicated system (Vault, AWS Secrets Manager) is purpose-built for â€” reach for those when the compliance or threat-model bar actually requires it, not by default for every Secret.
- **Don't grant a wildcard RBAC rule "temporarily to unblock a deploy" without a hard, tracked follow-up to tighten it.** This is exactly how wildcard grants become permanent â€” treat it as a P1 remediation item the moment it's introduced, not a footnote for "later."
- **Don't assume `ReadWriteMany` is available by default.** Most common block-storage CSI drivers (EBS, most cloud block volumes) are `ReadWriteOnce` only; reaching for RWX means a deliberate choice of a different storage backend (NFS/EFS-class) with real performance and consistency tradeoffs versus block storage, not a default assumption.
- **Don't blanket-disable `automountServiceAccountToken` cluster-wide without auditing which workloads genuinely call the API.** It's a real hardening win for workloads that never touch the Kubernetes API, but disabling it for something that does need API access just breaks that workload outright â€” this needs a deliberate per-workload audit, not a global toggle applied without verification.

---

## Interview questions

### Q1 â€” Why does a pod sometimes get permanently stuck `Pending` even though its PVC shows `Bound`?
**Testing:** the `volumeBindingMode` timing bug specifically, a real and confusing production symptom.
**Answer:** With the default `volumeBindingMode: Immediate`, the PV gets provisioned and bound the instant the PVC is created â€” before the scheduler has assigned the pod to any node. For zonal storage (an EBS volume, physically bound to one availability zone), if the scheduler later places the pod in a different zone based on independent criteria, the pod becomes permanently unschedulable: it needs a volume that can't physically attach to any node in the zone it's stuck being placed in. `WaitForFirstConsumer` fixes this by deferring binding/provisioning until after the pod is actually scheduled, so the volume gets created in the same zone the scheduler already chose.
**Follow-up trap:** *"If you find a cluster already hit this bug, what's the fix â€” can you just change the StorageClass's volumeBindingMode after the fact?"* â€” no, changing the StorageClass doesn't retroactively fix an already-bound PVC/PV pair; the broken PVC needs to be deleted and recreated (against a StorageClass now correctly set to `WaitForFirstConsumer`) so provisioning happens fresh, after scheduling, this time.

### Q2 â€” Are Kubernetes Secrets encrypted by default? Walk through exactly what's stored in etcd.
**Testing:** the base64-is-not-encryption fact, precisely, not just as a slogan.
**Answer:** No. By default, a Secret's values are base64-encoded, not encrypted, when written to etcd â€” base64 is an encoding chosen so arbitrary binary data can be safely represented in JSON/YAML text, with no key and no confidentiality property, trivially reversible by anyone who can read the raw object (`kubectl get secret -o yaml`, direct etcd access, a leaked etcd snapshot). Real encryption at rest requires explicitly configuring `EncryptionConfiguration` on the API server with an actual encryption provider.
**Follow-up trap:** *"If you enable EncryptionConfiguration with a KMS provider today, are all your existing Secrets now protected?"* â€” no â€” enabling the configuration only affects newly written or updated objects; existing Secrets remain in whatever form they were previously stored in until they're explicitly rewritten (a bulk `get`/`replace` pass is the standard follow-up step), which is a commonly missed part of the rollout that leaves old Secrets unprotected indefinitely if skipped.

### Q3 â€” What's the practical difference between a local AES key provider and a KMS provider for Secret encryption at rest?
**Testing:** whether "just enable encryption" is understood at the level of what threat it actually defends against.
**Answer:** A local provider (AES-CBC/AES-GCM with a key stored in a file on the control plane) is strictly better than base64-only, but the key material sits right there alongside the control plane it's protecting, so it doesn't meaningfully defend against a full control-plane compromise. A KMS provider (AWS KMS, Azure Key Vault, GCP KMS) never persists the data-encryption-key material locally at all â€” every encrypt/decrypt operation calls out to the external, typically hardware-backed key service â€” giving genuine separation between "who can read etcd" and "who can actually decrypt what's in it," plus centralized rotation and audit logging the local-key approach doesn't provide.
**Follow-up trap:** *"Does KMS-backed encryption at rest mean a compromised pod can't read its own mounted Secret?"* â€” no, unrelated concern: encryption at rest protects the etcd storage layer specifically; a pod that legitimately mounts a Secret (or has RBAC access to read it via the API) still sees the plaintext value exactly as before â€” etcd encryption doesn't restrict in-cluster access at all, it only protects against exposure via etcd itself.

### Q4 â€” What changed about ServiceAccount tokens in Kubernetes 1.24, and what specific incident class does it close?
**Testing:** currency and the actual security reasoning, not just "tokens got better somehow."
**Answer:** Before 1.24, creating a ServiceAccount auto-generated a companion long-lived Secret containing a JWT with no built-in expiry, auto-mounted into every pod using that ServiceAccount. 1.24+ stopped this by default; pods instead get bound tokens via the TokenRequest API â€” time-limited (1 hour default, kubelet-refreshed so a long-running pod's token stays valid continuously), audience-bound (scoped to the API server specifically), and object-bound (invalidated the moment that specific pod is deleted). This closes the incident class where a token exfiltrated from a compromised pod kept working indefinitely, with unbounded blast radius, long after the pod itself was gone.
**Follow-up trap:** *"If the token is refreshed automatically before it expires, doesn't that mean a compromised pod's token is effectively still long-lived for as long as the pod runs?"* â€” yes, correctly noted: the security improvement isn't "shorter-lived while the pod is alive," it's "bounded to the pod's actual lifetime and to the intended audience" â€” a token that leaks from a long-running pod is still valid for that pod's lifetime, but it stops working the instant the pod is deleted and can't be replayed against an unintended recipient, both real, meaningful reductions versus the pre-1.24 default even though it doesn't eliminate risk from a currently-running compromised pod.

### Q5 â€” Explain the difference in how ConfigMap changes propagate via volume mount versus environment variable injection.
**Testing:** a very practical, commonly-hit operational gotcha.
**Answer:** Volume-mounted ConfigMaps/Secrets sync via the kubelet's periodic sync loop, propagating a source change to every pod with it mounted within roughly a minute, with no pod restart needed. Environment-variable injection is captured once, at pod start, and never updates for that pod's lifetime regardless of how many times the source object changes â€” the only way to pick up a new value is recreating the pod, commonly automated via a checksum annotation on the pod template tied to the ConfigMap's content, forcing a rollout whenever it changes.
**Follow-up trap:** *"If an app reads an env var once at startup versus continuously re-reading a mounted file, which pattern is actually 'correct'?"* â€” neither is universally correct, it's a deliberate tradeoff: env vars are simpler and match "config is fixed for this process's life" semantics cleanly, but require an explicit rollout mechanism for changes; volume-mounted files support live reload but require the application to actually watch the file (most runtimes don't do this by default, so unless the app is specifically written to notice file changes, a "live-updating" mount is just as stale in practice as an env var until the app restarts anyway).

### Q6 â€” What's the single most commonly flagged RBAC finding in Kubernetes security audits, and why does it keep happening?
**Testing:** practical security-review experience, not textbook RBAC syntax.
**Answer:** Wildcard grants â€” `resources: ["*"]`, `verbs: ["*"]`, sometimes combined with `apiGroups: ["*"]` â€” effectively granting cluster-admin-equivalent access far beyond what was intended. It keeps recurring because it's typically introduced during initial setup specifically to "get something working" quickly under time pressure, and the follow-up to scope it down to least privilege gets deprioritized or forgotten once the immediate blocker is resolved, especially in fast-moving teams without a recurring audit process catching it.
**Follow-up trap:** *"How would you actually audit an existing cluster for this at scale, rather than reading every Role by hand?"* â€” `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<name>` for spot-checking specific identities, but at scale this needs tooling that programmatically scans every Role/ClusterRole for wildcard verbs/resources across the whole cluster (several open-source RBAC auditing tools exist for exactly this), since manually reading every Role in a cluster with hundreds of namespaces and teams is not a realistic ongoing process.

### Q7 â€” Why does RBAC access to the `serviceaccounts/token` subresource specifically need the same scrutiny as granting direct access to that ServiceAccount's full permissions?
**Testing:** an easy-to-miss but genuinely important escalation path.
**Answer:** Anyone with `create` permission on `serviceaccounts/token` can invoke the TokenRequest API to mint a fresh bound token impersonating that ServiceAccount at will â€” meaning that specific permission is functionally equivalent to being granted everything that target ServiceAccount can do, not merely "the ability to read a token." A Role that looks narrowly scoped ("can only create tokens, nothing else") is misleadingly named if the ServiceAccount it can mint tokens for is itself highly privileged.
**Follow-up trap:** *"If you restrict serviceaccounts/token access tightly, is that sufficient, or is there a related privilege-escalation path worth checking too?"* â€” also check for unrestricted access to create/modify RoleBindings and ClusterRoleBindings themselves â€” an identity that can bind an existing (even unused) highly-privileged ClusterRole to itself or to a ServiceAccount it controls has an equivalent escalation path that doesn't touch `serviceaccounts/token` at all; Kubernetes RBAC's `escalate` and `bind` verbs exist specifically to let cluster admins restrict this class of self-escalation separately.

### Q8 â€” Why did Kubernetes move storage drivers from in-tree to CSI (Container Storage Interface)?
**Testing:** the actual architectural motivation, not just "CSI is the standard now."
**Answer:** In-tree volume plugins were compiled directly into kubelet and the controller manager, coupling every storage vendor's feature velocity and bug-fix cadence to Kubernetes core's own release cycle â€” a new storage feature or urgent fix had to wait for (and ship as part of) a full Kubernetes release. CSI externalized storage drivers into independently versioned, out-of-tree plugins that any vendor can develop, release, and patch on their own schedule, decoupling storage driver evolution entirely from core Kubernetes releases.
**Follow-up trap:** *"Does this mean every storage backend automatically works the same way regardless of CSI driver?"* â€” no, CSI standardizes the *interface* Kubernetes uses to talk to a driver, not the capabilities every driver provides â€” access modes (RWO vs RWX), volume expansion support, snapshotting, and topology-awareness all vary meaningfully by driver, so "it's CSI-compliant" doesn't guarantee feature parity across different storage backends, and checking the specific driver's documented capabilities remains necessary.

### Q9 â€” When would you deliberately choose `reclaimPolicy: Retain` over the default `Delete`, and what operational cost does that choice carry?
**Testing:** the senior judgment call on a real, easy-to-overlook default.
**Answer:** `Retain` for any workload where the underlying data is genuinely irreplaceable or expensive to reconstruct â€” a database's storage, for instance â€” where the risk of a PVC deletion (accidental or as a side effect of some automated cleanup) silently destroying real data outweighs the convenience of automatic volume cleanup. The operational cost: retained PVs and their underlying cloud volumes don't get cleaned up automatically, so an operational process (manual or scripted) is needed to identify and actually delete truly-orphaned retained volumes, or storage cost accumulates indefinitely from volumes nobody remembers to remove.
**Follow-up trap:** *"Isn't Retain strictly safer, so why not make it the default for everything?"* â€” because for genuinely ephemeral or trivially-reproducible data (a cache, a scratch/temp volume, a CI build's throwaway workspace), `Delete`'s automatic cleanup is the correct behavior and `Retain` would just accumulate orphaned volumes and unnecessary storage cost with no corresponding safety benefit â€” the right default depends on whether the specific data is actually worth protecting against accidental deletion, which is a per-workload judgment, not a universal rule.

### Q10 â€” A team disables `automountServiceAccountToken` cluster-wide as a security hardening measure. What breaks, and how should this actually be rolled out?
**Testing:** whether a good security instinct is applied with the necessary care rather than as a blunt global toggle.
**Answer:** Any workload that genuinely needs to call the Kubernetes API (operators, controllers, any pod using a client-go/kubernetes client library to read or write cluster objects) breaks outright with no mounted token to authenticate with. The correct rollout is a per-workload audit â€” identify which ServiceAccounts are actually used for API access versus which are attached to pods that never touch the API at all â€” and set `automountServiceAccountToken: false` only on the ServiceAccounts/pods confirmed not to need it, not as a single global default applied without verification.
**Follow-up trap:** *"How would you verify, for an existing cluster with many workloads, which ones actually use their mounted token?"* â€” audit logs on the API server (or a service mesh's access logs, if present) showing which ServiceAccount identities are actually making API requests is the reliable signal; assuming a workload doesn't need API access just because its primary function doesn't obviously involve it (a web frontend that turns out to call the API for feature-flag or config lookups, for instance) is a common way this kind of hardening breaks something unexpectedly if done by inspection alone rather than by observed behavior.

---

## Red flags that fail you

- Describing Kubernetes Secrets as "encrypted" without qualifying that this requires explicit `EncryptionConfiguration` â€” base64 is the unqualified default.
- Not knowing that `volumeBindingMode` defaults to `Immediate`, or not knowing why `WaitForFirstConsumer` matters for zonal storage.
- Claiming enabling `EncryptionConfiguration` retroactively encrypts already-stored Secrets.
- Recommending wildcard RBAC grants (`resources: ["*"]`, `verbs: ["*"]`) as acceptable "for now," or not flagging one as a serious finding when asked to review a Role.
- Not knowing what changed about ServiceAccount tokens in 1.24, or claiming all clusters still auto-mount long-lived tokens by default.
- Confusing env-var config injection with volume-mount injection's live-update behavior.
- Treating `serviceaccounts/token` create access as a minor, low-risk permission rather than equivalent to the target ServiceAccount's full privilege set.

---

## Cheat card

```
PV/PVC/STORAGECLASS: PVC = request, StorageClass+CSI provisioner = dynamic fulfillment
  volumeBindingMode: Immediate (DEFAULT, binds before pod scheduled -> zone-mismatch bug
    for zonal storage) | WaitForFirstConsumer (correct for zonal, binds AFTER scheduling)
  reclaimPolicy: Delete (default, auto-deletes underlying volume) | Retain (manual cleanup)
  accessModes: RWO (most block storage, one node) | RWX (needs NFS/EFS-class backend)
    | ReadWriteOncePod (newer, single POD not just single node)

CONFIG PROPAGATION: volume mount = LIVE sync (~1min kubelet delay), env var = ONCE at
  pod start, NEVER updates without restart (use a checksum annotation to force rollout)

SECRETS: base64 encoded in etcd BY DEFAULT â€” NOT encryption, trivially reversible
  Real encryption = explicit EncryptionConfiguration + provider (local AES < KMS provider)
  KMS provider: key never persisted locally, every op calls external KMS, real audit+rotation
  Enabling encryption config does NOT retroactively re-encrypt existing Secrets â€” must
    force-rewrite all existing Secret objects after enabling
  etcd encryption != in-cluster access control â€” pod w/ mount or RBAC read still sees plaintext

SERVICEACCOUNT TOKENS: pre-1.24 = auto long-lived Secret token, indefinite validity, BAD
  1.24+ default = TokenRequest API bound tokens: 1h lifetime (kubelet-refreshed),
    audience-bound (API server only), OBJECT-bound (dies when pod deleted)
    delivered via projected volume, not a static Secret

RBAC: Role (namespaced) / ClusterRole (cluster-scoped, bindable per-ns too) + verbs/
  resources/apiGroups/[resourceNames]. RoleBinding/ClusterRoleBinding -> grants to Subject
  #1 pentest finding: wildcard resources/verbs ["*"] = cluster-admin-equivalent, unaudited
  serviceaccounts/token create access = equivalent to full target SA privileges (mint-at-will)
  also check: bind/escalate verbs on RoleBindings/ClusterRoleBindings = self-escalation path
  automountServiceAccountToken: false for any pod that never calls the K8s API
```

## Sources

- [Kubernetes documentation â€” StorageClass](https://kubernetes.io/docs/concepts/storage/storage-classes/) â€” accessed 2026-08-02
- [Kubernetes documentation â€” Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/) â€” accessed 2026-08-02
- [Kubernetes documentation â€” RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/) â€” accessed 2026-08-02
- [Attacker persistence in Kubernetes using the TokenRequest API â€” Datadog Security Labs](https://securitylabs.datadoghq.com/articles/kubernetes-tokenrequest-api/) â€” accessed 2026-08-02
- [Kubernetes Secrets Management in 2026: Best Practices â€” CloudOptimo](https://www.cloudoptimo.com/blog/kubernetes-secrets-management-in-2026-best-practices/) â€” accessed 2026-08-02
- [How to Use Kubernetes StorageClass for Dynamic Volume Provisioning â€” OneUptime](https://oneuptime.com/blog/post/2026-02-20-kubernetes-storageclass-dynamic-provisioning/view) â€” accessed 2026-08-02
- Kubernetes documentation â€” Encrypting Confidential Data at Rest (`EncryptionConfiguration`, KMS provider v2)
- CIS Kubernetes Benchmark â€” RBAC and Secrets encryption baseline checks

## Changelog
- 2026-08-02 â€” created
