"""Lab 02 — K8s objects without a cluster. Reference solution."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Union

SERVICE_TYPES = {"ClusterIP", "NodePort", "LoadBalancer", "ExternalName"}

_NUMERIC = re.compile(r"^[+-]?\d+$")


# ------------------------------------------------------------------ 1. manifest loader

def _scalar(value: str) -> Union[str, int]:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    if _NUMERIC.match(v):
        return int(v)
    return v


def _parse_document(lines: List[str]) -> Dict[str, Union[str, int, dict]]:
    doc: Dict[str, Union[str, int, dict]] = {}
    current_parent: Optional[str] = None
    for raw in lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            current_parent = None
            key, has_val, val = line.partition(":")
            if has_val and val.strip():
                doc[key.strip()] = _scalar(val)
            else:
                current_parent = key.strip()
                doc.setdefault(current_parent, {})
        elif indent >= 2 and current_parent is not None:
            key, has_val, val = line.partition(":")
            parent = doc[current_parent]
            if not isinstance(parent, dict):
                parent = {}
                doc[current_parent] = parent
            if has_val and val.strip():
                parent[key.strip()] = _scalar(val)
            else:
                parent.setdefault(key.strip(), {})
    return doc


def load_manifest(text: str) -> List[dict]:
    docs: List[dict] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.strip() == "---":
            if any(l.strip() for l in current):
                docs.append(_parse_document(current))
            current = []
        else:
            current.append(line)
    if any(l.strip() for l in current):
        docs.append(_parse_document(current))
    return docs


# ------------------------------------------------------------------ 2. validator

def _get(doc: dict, *path: str) -> object:
    node: object = doc
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def validate_object(doc: dict) -> List[str]:
    problems: List[str] = []
    kind = doc.get("kind")
    if "apiVersion" not in doc:
        problems.append("missing apiVersion")
    if "kind" not in doc:
        problems.append("missing kind")
    if not isinstance(_get(doc, "metadata", "name"), str):
        problems.append("missing metadata.name")
    if kind == "Deployment":
        replicas = _get(doc, "spec", "replicas")
        if not isinstance(replicas, int) or isinstance(replicas, bool):
            problems.append("spec.replicas must be an int")
        selector = _get(doc, "spec", "selector", "matchLabels")
        if not isinstance(selector, dict):
            problems.append("missing spec.selector.matchLabels")
        else:
            template_labels = _get(doc, "spec", "template", "metadata", "labels")
            if template_labels != selector:
                problems.append("selector matchLabels do not match template labels")
    elif kind == "Service":
        stype = _get(doc, "spec", "type")
        if stype not in SERVICE_TYPES:
            problems.append("spec.type must be one of ClusterIP, NodePort, "
                            "LoadBalancer, ExternalName")
    return problems


# ------------------------------------------------------------------ 3. recommend kind

def recommend_kind(requirements: Set[str]) -> str:
    reqs = set(requirements)
    if "cron" in reqs:
        return "CronJob"
    if "batch" in reqs:
        return "Job"
    if "singleton" in reqs or "stateful" in reqs:
        return "StatefulSet"
    if "node-agent" in reqs:
        return "DaemonSet"
    return "Deployment"


# ------------------------------------------------------------------ 4. reconcile

def reconcile(desired: Dict[str, object], observed: Dict[str, object]) -> List[str]:
    actions: List[str] = []
    if desired.get("replicas") != observed.get("replicas"):
        actions.append(f"scale to {desired.get('replicas')}")
    if desired.get("image") != observed.get("image"):
        actions.append(f"rolling update to {desired.get('image')}")
    return actions


# ------------------------------------------------------------------ 5. taints & tolerations

def schedulable(pod: Dict[str, list], taints: List[dict]) -> bool:
    tols = pod.get("tolerations", [])
    tol_keys = {(t.get("key"), t.get("effect")) for t in tols}
    return all((t.get("key"), t.get("effect")) in tol_keys for t in taints)
