"""Lab 05 — K8s storage & config without a cluster. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. No cluster, no network, no PyYAML.
  * No time.sleep() anywhere — nothing here is wall-clock dependent.
  * PV <-> PVC binding is 1:1: a PV whose claim_ref is set is Bound and
    unavailable to other claims.
  * RBAC is default-deny: no binding for the subject -> False. Always.
  * The dynamic-provisioning reclaim default is Delete (documented in the
    README — Retain is the deliberate choice for data you can't regenerate).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

ACCESS_MODES = {"ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany", "ReadWriteOncePod"}
DEFAULT_STORAGE_CLASS = "standard"
DEFAULT_RECLAIM_POLICY = "Delete"          # dynamic-provisioning default


# ------------------------------------------------------------------ objects
@dataclass
class PersistentVolume:
    """Cluster-scoped actual storage. claim_ref is None until bound (1:1)."""
    name: str
    capacity: int                                    # Gi
    access_modes: Set[str]
    storage_class: str = DEFAULT_STORAGE_CLASS
    reclaim_policy: Optional[str] = None
    claim_ref: Optional[str] = None                   # bound PVC's name, else None


@dataclass
class PersistentVolumeClaim:
    """Namespaced request for storage."""
    name: str
    capacity: int                                    # Gi
    access_modes: Set[str]
    storage_class: str = DEFAULT_STORAGE_CLASS


# ------------------------------------------------------------------ 1. bind
def bind(pvs: Sequence[PersistentVolume],
         pvc: PersistentVolumeClaim) -> Tuple[Optional[str], str]:
    """Match a claim to the best free PV. Returns (pv_name, reason).

    Gates, in order; each surviving candidate must pass all of:
      available  — claim_ref is None (Bound PVs are taken)
      capacity   — pv.capacity >= pvc.capacity
      accessmode — at least one mode in common
      class      — same storage_class (default "standard")
    Winner: smallest sufficient capacity; ties -> the PV listed first.
    On bind, set the winner's claim_ref to the claim's name and return a
    reason starting with "bound".
    No winner -> (None, reason): report the LAST gate that still had
    candidates at its start but eliminated them all — i.e. if the
    capacity pass empties the pool, blame "capacity:"; else if the mode
    pass empties it, blame "accessmode:"; else blame "class:".
    """
    # TODO(step 1): implement
    raise NotImplementedError


# ------------------------------------------------------------------ 2. reclaim
def pv_reclaim(policy: Optional[str], pv: PersistentVolume,
               claim_deleted: bool) -> str:
    """What happens to a bound PV once its claim goes away.

    Reclaim only fires when the claim is gone: claim still alive ->
    "claim still bound - pv unchanged".
    Policy resolution: explicit arg > pv.reclaim_policy > Delete
    (the dynamic-provisioning default).
      Retain  -> "pv kept, Released status"
      Delete  -> "pv deleted"
      Recycle -> "pv scrubbed"   (deprecated upstream, kept for the interview)
    """
    # TODO(step 2): implement
    raise NotImplementedError


# ------------------------------------------------------------------ 3. mounts
class DeploymentMount:
    """Validates volumes <-> volumeMounts in a pod spec.

    pod_spec = {"volumes": [...], "containers": [{"volumeMounts": [...]}]}
    Missing keys are empty lists.

      volumeMounts[].name  -> must match a declared volume, else
                              "dangling mount {name}"
      volumes[].name       -> must be mounted by some container, else
                              "unused volume {name}"
      mountPath           -> must start with "/", else
                              "mountPath must be absolute: {path}"
    """

    def validate(self, pod_spec: dict) -> List[str]:
        """Return problem strings; empty list means the spec mounts cleanly."""
        # TODO(step 3): implement
        raise NotImplementedError


# ------------------------------------------------------------------ 4. config exposure
_KIND_DIR = {"ConfigMap": "configmap", "Secret": "secret"}
_KIND_REF = {"ConfigMap": "configMapKeyRef", "Secret": "secretKeyRef"}


def _env_name(key: str) -> str:
    """Real rule: upper, then '.' and '-' -> '_'. "my-key" -> MY_KEY,
    "db.url" -> DB_URL. (envFrom is stricter upstream: invalid env-var
    names are skipped with an InvalidEnvironmentVariableNames event —
    transformation is the pattern that keeps every key consumable.)"""
    # TODO(step 4a): implement
    raise NotImplementedError


def expose(kind: str, keys: Sequence[str], as_env: bool = True) -> List[dict]:
    """Render a ConfigMap/Secret's keys the two ways a pod consumes them.

    kind: "ConfigMap" or "Secret", case-insensitive; anything else -> ValueError.
    Env form (as_env=True): per key
      {"name": _env_name(key), "valueFrom": {_KIND_REF[kind]: {"key": key}}}
    Volume form (as_env=False): per key, the file path the kubelet writes:
      "/etc/{configmap|secret}/{key}"   (key unchanged)
    """
    # TODO(step 4b): implement
    raise NotImplementedError


# ------------------------------------------------------------------ 5. RBAC
class RoleBindingSim:
    """Default-deny RBAC.

    roles    = {"role-name": {"verbs": [...], "resources": [...],
                              "namespace": "prod"}}   # namespace key -> namespaced
              # no namespace key -> ClusterRole (works in any namespace)
    bindings = {"subject": "role-name"}
    """

    def __init__(self, roles: Dict[str, dict],
                 bindings: Dict[str, str]) -> None:
        self.roles = roles
        self.bindings = bindings

    def can(self, subject: str, verb: str, resource: str,
            namespace: Optional[str] = None) -> bool:
        """True only if: subject has a binding, the binding resolves to a
        known role, the role grants (verb, resource), AND the scope fits —
        a namespaced Role matches only in its own namespace; a ClusterRole
        matches in any namespace, including None. Everything else: False.
        """
        # TODO(step 5): implement
        raise NotImplementedError
