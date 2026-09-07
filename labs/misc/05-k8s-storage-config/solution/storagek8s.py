"""Lab 05 — reference solution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

ACCESS_MODES = {"ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany", "ReadWriteOncePod"}
DEFAULT_STORAGE_CLASS = "standard"
DEFAULT_RECLAIM_POLICY = "Delete"          # dynamic-provisioning default


@dataclass
class PersistentVolume:
    name: str
    capacity: int                                    # Gi
    access_modes: Set[str]
    storage_class: str = DEFAULT_STORAGE_CLASS
    reclaim_policy: Optional[str] = None
    claim_ref: Optional[str] = None                   # bound PVC's name, else None


@dataclass
class PersistentVolumeClaim:
    name: str
    capacity: int                                    # Gi
    access_modes: Set[str]
    storage_class: str = DEFAULT_STORAGE_CLASS


def bind(pvs: Sequence[PersistentVolume],
         pvc: PersistentVolumeClaim) -> Tuple[Optional[str], str]:
    available = [pv for pv in pvs if pv.claim_ref is None]

    by_capacity = [pv for pv in available if pv.capacity >= pvc.capacity]
    if not by_capacity:
        small = min((pv.capacity for pv in available), default=pvc.capacity)
        return (None, f"capacity: smallest available PV is {small}Gi, "
                       f"claim wants {pvc.capacity}Gi")

    by_mode = [pv for pv in by_capacity
               if set(pv.access_modes) & set(pvc.access_modes)]
    if not by_mode:
        want = ",".join(sorted(pvc.access_modes))
        return (None, f"accessmode: no capacity-matching PV offers {want}")

    by_class = [pv for pv in by_mode if pv.storage_class == pvc.storage_class]
    if not by_class:
        classes = ",".join(sorted({pv.storage_class for pv in by_mode}))
        return (None, f"class: claim wants {pvc.storage_class}, "
                       f"matching PVs offer {classes}")

    best = min(by_class, key=lambda pv: pv.capacity)    # ties: min keeps first
    best.claim_ref = pvc.name
    return (best.name, f"bound: {best.name} ({best.capacity}Gi >= "
                       f"{pvc.capacity}Gi, class {pvc.storage_class})")


def pv_reclaim(policy: Optional[str], pv: PersistentVolume,
               claim_deleted: bool) -> str:
    if not claim_deleted:
        return "claim still bound - pv unchanged"
    effective = policy or pv.reclaim_policy or DEFAULT_RECLAIM_POLICY
    if effective == "Retain":
        return "pv kept, Released status"
    if effective == "Delete":
        return "pv deleted"
    if effective == "Recycle":
        return "pv scrubbed"
    raise ValueError(f"unknown reclaim policy: {effective}")


class DeploymentMount:
    def validate(self, pod_spec: dict) -> List[str]:
        volumes = pod_spec.get("volumes") or []
        declared = {v["name"] for v in volumes}
        mounts: List[dict] = []
        for c in pod_spec.get("containers") or []:
            mounts.extend(c.get("volumeMounts") or [])

        problems: List[str] = []
        mounted: Set[str] = set()
        for m in mounts:
            name = m["name"]
            if name not in declared:
                problems.append(f"dangling mount {name}")
            mounted.add(name)
            path = m.get("mountPath", "")
            if not path.startswith("/"):
                problems.append(f"mountPath must be absolute: {path}")
        for name in sorted(declared - mounted):
            problems.append(f"unused volume {name}")
        return problems


_KIND_DIR = {"ConfigMap": "configmap", "Secret": "secret"}
_KIND_REF = {"ConfigMap": "configMapKeyRef", "Secret": "secretKeyRef"}
_KIND_CANON = {k.lower(): k for k in _KIND_DIR}


def _env_name(key: str) -> str:
    return key.upper().replace(".", "_").replace("-", "_")


def expose(kind: str, keys: Sequence[str], as_env: bool = True) -> List[dict]:
    k = _KIND_CANON.get(kind.lower()) if isinstance(kind, str) else None
    if k is None:
        raise ValueError(f"kind must be ConfigMap or Secret, got {kind!r}")
    if as_env:
        ref = _KIND_REF[k]
        return [{"name": _env_name(key), "valueFrom": {ref: {"key": key}}}
                for key in keys]
    directory = _KIND_DIR[k]
    return [{"path": f"/etc/{directory}/{key}"} for key in keys]


class RoleBindingSim:
    def __init__(self, roles: Dict[str, dict],
                 bindings: Dict[str, str]) -> None:
        self.roles = roles
        self.bindings = bindings

    def can(self, subject: str, verb: str, resource: str,
            namespace: Optional[str] = None) -> bool:
        role_name = self.bindings.get(subject)
        if role_name is None:
            return False                            # default deny
        role = self.roles.get(role_name)
        if role is None:                            # dangling binding
            return False
        if verb not in role.get("verbs", []):
            return False
        if resource not in role.get("resources", []):
            return False
        if "namespace" in role:
            return role["namespace"] == namespace  # namespaced Role
        return True                                 # ClusterRole: any namespace
