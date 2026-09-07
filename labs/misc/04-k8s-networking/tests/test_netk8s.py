"""Lab 04 tests. No cluster, no network, no sleeps — pure state machines."""
import pytest


def _web_cluster(N):
    """Three pods, two namespaces, one web service — the shared fixture state."""
    net = N.ClusterNetwork()
    net.register_namespace("default")
    net.register_namespace("other", labels={"team": "data"})
    net.register_pod("10.0.0.1", "web-1", "default", {"app": "web"})
    net.register_pod("10.0.0.2", "web-2", "default", {"app": "web"})
    net.register_pod("10.0.0.3", "web-canary", "default", {"app": "web", "tier": "canary"})
    net.register_pod("10.0.1.7", "web-other-ns", "other", {"app": "web"})
    net.register_service("web", "10.96.0.10", {"app": "web"}, [80])
    return net


# ------------------------------------------------------------------ dns
def test_dns_name_default_namespace(N):
    assert N.ClusterNetwork.dns_name("web") == "web.default.svc.cluster.local"


def test_dns_name_explicit_namespace(N):
    assert N.ClusterNetwork.dns_name("db", "prod") == "db.prod.svc.cluster.local"


# ------------------------------------------------------------------ resolve
def test_resolve_returns_service_and_matching_pods(N):
    net = _web_cluster(N)
    svc, pods = net.resolve("web.default.svc.cluster.local")
    assert svc is net.services["web"]
    assert [p["name"] for p in pods] == ["web-1", "web-2", "web-canary"]


def test_resolve_default_ns_when_short_name(N):
    net = _web_cluster(N)
    svc, pods = net.resolve("web.svc.cluster.local")
    assert svc is net.services["web"]
    assert len(pods) == 3


def test_resolve_unknown_service_raises_lookuperror(N):
    net = _web_cluster(N)
    with pytest.raises(LookupError):
        net.resolve("nope.default.svc.cluster.local")


def test_resolve_empty_endpoints_when_no_pod_matches(N):
    net = _web_cluster(N)
    net.register_service("db", "10.96.0.20", {"app": "db"}, [5432])
    svc, pods = net.resolve("db.default.svc.cluster.local")
    assert svc is net.services["db"]
    assert pods == []


def test_resolve_cross_namespace_via_dns_string(N):
    net = _web_cluster(N)
    net.register_service("db", "10.96.0.20", {"app": "web"}, [5432])
    svc, pods = net.resolve("db.other.svc.cluster.local")
    assert svc is net.services["db"]
    assert [p["name"] for p in pods] == ["web-other-ns"]    # only the ns=other pod
    _, default_pods = net.resolve("db.default.svc.cluster.local")
    assert len(default_pods) == 3                          # default ns still matches 3


# ------------------------------------------------------------------ kube-proxy
def test_netrule_has_kube_svc_hash_prefix(N):
    net = _web_cluster(N)
    rule = net.kube_proxy_rule("web", net.services["web"])
    assert rule.startswith("KUBE-SVC-")
    digest = rule.split()[0][len("KUBE-SVC-"):]
    assert len(digest) == 10
    import hashlib
    assert digest == hashlib.sha256(b"web").hexdigest()[:10]


def test_netrule_contains_cluster_ip_and_endpoint_ips(N):
    net = _web_cluster(N)
    rule = net.kube_proxy_rule("web", net.services["web"])
    assert "10.96.0.10:80" in rule
    assert "10.0.0.1:80" in rule
    assert "10.0.0.2:80" in rule
    assert "10.0.0.3:80" in rule
    assert "10.0.1.7" not in rule          # other namespace's pod is not an endpoint


def test_netrule_empty_endpoints_when_no_backends(N):
    net = _web_cluster(N)
    net.register_service("db", "10.96.0.20", {"app": "db"}, [5432])
    rule = net.kube_proxy_rule("db", net.services["db"])
    assert rule.endswith("-> []")


# ------------------------------------------------------------------ NetworkPolicy
def _pods_for_policy(N):
    net = N.ClusterNetwork()
    net.register_namespace("default", labels={"name": "default"})
    net.register_namespace("payments", labels={"team": "payments", "env": "prod"})
    net.register_namespace("monitoring", labels={"team": "monitoring"})
    net.register_pod("10.0.0.1", "api", "default", {"app": "api"})
    net.register_pod("10.0.0.2", "pay", "payments", {"app": "pay"})
    net.register_pod("10.0.0.3", "metrics", "monitoring", {"app": "metrics"})
    net.register_pod("10.0.0.4", "api2", "default", {"app": "api2"})
    return net


def test_policy_no_policy_selecting_dst_allows(N):
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    assert enf.allowed("10.0.0.1", "10.0.0.4") is True


def test_policy_matching_dst_without_ingress_denies(N):
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    enf.policies.append({"podSelector": {"app": "pay"},
                         "ingressFrom": []})
    assert enf.allowed("10.0.0.1", "10.0.0.2") is False


def test_policy_matching_dst_missing_key_denies(N):
    """Default-deny also when the matching policy exists and src matches nothing."""
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    enf.policies.append({"podSelector": {"app": "pay"},
                         "ingressFrom": [{"podSelector": {"app": "nope"}}]})
    assert enf.allowed("10.0.0.1", "10.0.0.2") is False


def test_policy_pod_selector_ingress_allows(N):
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    enf.policies.append({"podSelector": {"app": "pay"},
                         "ingressFrom": [{"podSelector": {"app": "api"}}]})
    assert enf.allowed("10.0.0.1", "10.0.0.2") is True
    assert enf.allowed("10.0.0.3", "10.0.0.2") is False   # wrong-label src denied
    assert enf.allowed("10.0.0.4", "10.0.0.2") is False    # api2 does not match


def test_policy_namespace_selector_ingress_allows(N):
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    enf.policies.append({"podSelector": {"app": "pay"},
                         "ingressFrom": [{"namespaceSelector": {"team": "monitoring"}}]})
    assert enf.allowed("10.0.0.3", "10.0.0.2") is True    # monitoring ns may talk to pay
    assert enf.allowed("10.0.0.1", "10.0.0.2") is False   # default ns labels don't match


def test_policy_mixed_ingress_entries_or_semantics(N):
    net = _pods_for_policy(N)
    enf = N.NetworkPolicyEnforcer(net)
    enf.policies.append({"podSelector": {"app": "pay"},
                         "ingressFrom": [{"podSelector": {"app": "metrics"}},
                                         {"namespaceSelector": {"team": "payments"}}]})
    assert enf.allowed("10.0.0.1", "10.0.0.2") is False   # api matches neither entry
    assert enf.allowed("10.0.0.4", "10.0.0.2") is False
    # metrics pod: podSelector entry matches
    assert enf.allowed("10.0.0.3", "10.0.0.2") is True
    # a payments-ns pod would match the namespaceSelector entry (api in default ns does not)
