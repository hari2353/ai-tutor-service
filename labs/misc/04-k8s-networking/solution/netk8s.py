"""Lab 04 — K8s networking without a cluster. Reference solution."""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple


def _superset_match(labels: Dict[str, str], selector: Dict[str, str]) -> bool:
    """True iff every key:value in selector appears in labels."""
    return all(labels.get(k) == v for k, v in selector.items())


class ClusterNetwork:
    """The cluster's networking state: pods, services, namespaces."""

    def __init__(self) -> None:
        self.pods: Dict[str, dict] = {}            # ip -> {"name", "namespace", "labels"}
        self.services: Dict[str, dict] = {}         # name -> {"cluster_ip", "selector", "ports", "type"}
        self.namespaces: Dict[str, dict] = {}      # ns_name -> {"labels"}

    # ------------------------------------------------------------- registry
    def register_namespace(self, name: str, labels: Dict[str, str] = None) -> None:
        self.namespaces[name] = {"labels": dict(labels or {})}

    def register_pod(self, ip: str, name: str, namespace: str = "default",
                     labels: Dict[str, str] = None) -> None:
        self.pods[ip] = {"name": name, "namespace": namespace,
                         "labels": dict(labels or {})}

    def register_service(self, name: str, cluster_ip: str,
                         selector: Dict[str, str], ports: List[int] = None,
                         type: str = "ClusterIP") -> None:
        self.services[name] = {"cluster_ip": cluster_ip,
                               "selector": dict(selector or {}),
                               "ports": list(ports or []),
                               "type": type}

    # ------------------------------------------------------------- DNS
    @staticmethod
    def dns_name(service: str, namespace: str = "default") -> str:
        return f"{service}.{namespace}.svc.cluster.local"

    def resolve(self, dns_name_string: str) -> Tuple[dict, List[dict]]:
        labels = dns_name_string.split(".")
        service_name = labels[0]
        namespace = labels[1] if len(labels) > 1 and labels[1] != "svc" else "default"
        if service_name not in self.services:
            raise LookupError(f"service not found: {dns_name_string!r}")
        service = self.services[service_name]
        endpoint_pods = [pod for pod in self.pods.values()
                         if pod["namespace"] == namespace
                         and _superset_match(pod["labels"], service["selector"])]
        return service, endpoint_pods

    # ------------------------------------------------------------- kube-proxy
    def kube_proxy_rule(self, service_name: str, service: dict) -> str:
        digest = hashlib.sha256(service_name.encode()).hexdigest()[:10]
        port = service["ports"][0] if service["ports"] else 80
        eps = [f"{ip}:{port}" for ip in self.endpoints(service_name, "default")]
        return f"KUBE-SVC-{digest} {service['cluster_ip']}:{port} -> {eps}"

    # ------------------------------------------------------------- policy
    def endpoints(self, service_name: str, namespace: str) -> List[str]:
        service = self.services[service_name]
        return [ip for ip, pod in self.pods.items()
                if pod["namespace"] == namespace
                and _superset_match(pod["labels"], service["selector"])]


class NetworkPolicyEnforcer:
    """Default-allow NetworkPolicy evaluation over a ClusterNetwork."""

    def __init__(self, network: ClusterNetwork) -> None:
        self.network = network
        self.policies: List[dict] = []
        # each policy: {"podSelector": {...}, "ingressFrom": [ {...} or {...} ]}

    def allowed(self, src_ip: str, dst_ip: str) -> bool:
        net = self.network
        if src_ip not in net.pods or dst_ip not in net.pods:
            return False
        dst = net.pods[dst_ip]
        src = net.pods[src_ip]
        matching = [p for p in self.policies
                    if _superset_match(dst["labels"], p.get("podSelector") or {})]
        if not matching:
            return True                      # no policy selects dst -> default allow
        for policy in matching:
            for entry in policy.get("ingressFrom") or []:
                if "podSelector" in entry and _superset_match(
                        src["labels"], entry["podSelector"]):
                    return True
                if "namespaceSelector" in entry:
                    ns_labels = (net.namespaces.get(src["namespace"])
                                 or {}).get("labels", {})
                    if _superset_match(ns_labels, entry["namespaceSelector"]):
                        return True
        return False                         # selected but no ingress matches -> deny
