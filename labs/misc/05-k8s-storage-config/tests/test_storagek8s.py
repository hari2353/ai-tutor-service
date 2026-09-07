"""Lab 05 tests. No sleeps, no cluster — objects and functions only."""
import pytest


# ------------------------------------------------------------------ fixtures
def _pv(name, capacity, modes, **kw):
    return lambda S: S.PersistentVolume(name=name, capacity=capacity,
                                        access_modes=modes, **kw)


def _pvc(name, capacity, modes, **kw):
    return lambda S: S.PersistentVolumeClaim(name=name, capacity=capacity,
                                             access_modes=modes, **kw)


# ------------------------------------------------------------------ bind
def test_bind_happy_all_gates(S):
    pv = S.PersistentVolume("data-pv", 20, {"ReadWriteOnce"})
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"})
    name, reason = S.bind([pv], pvc)
    assert name == "data-pv"
    assert reason.startswith("bound")
    assert pv.claim_ref == "data"                    # 1:1 binding recorded


def test_bind_prefers_smallest_sufficient(S):
    pvs = [S.PersistentVolume("huge", 500, {"ReadWriteOnce"}),
           S.PersistentVolume("tight", 10, {"ReadWriteOnce"}),
           S.PersistentVolume("ok", 40, {"ReadWriteOnce"})]
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"})
    name, _ = S.bind(pvs, pvc)
    assert name == "tight"


def test_bind_smallest_sufficient_not_smallest_overall(S):
    """A 5Gi PV exists but is too small — it must not win by being first."""
    pvs = [S.PersistentVolume("tiny", 5, {"ReadWriteOnce"}),
           S.PersistentVolume("fit", 15, {"ReadWriteOnce"}),
           S.PersistentVolume("fat", 100, {"ReadWriteOnce"})]
    pvc = S.PersistentVolumeClaim("data", 12, {"ReadWriteOnce"})
    name, reason = S.bind(pvs, pvc)
    assert name == "fit"
    assert reason.startswith("bound")


def test_bind_capacity_too_small(S):
    pvs = [S.PersistentVolume("small", 5, {"ReadWriteOnce"}),
           S.PersistentVolume("small2", 9, {"ReadWriteMany"})]
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"})
    name, reason = S.bind(pvs, pvc)
    assert name is None
    assert reason.startswith("capacity:")


def test_bind_accessmode_mismatch(S):
    pvs = [S.PersistentVolume("rox", 50, {"ReadOnlyMany"}),
           S.PersistentVolume("rwx", 50, {"ReadWriteMany"})]
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"})
    name, reason = S.bind(pvs, pvc)
    assert name is None
    assert reason.startswith("accessmode:")


def test_bind_class_mismatch(S):
    pvs = [S.PersistentVolume("fast", 50, {"ReadWriteOnce"},
                              storage_class="fast-ssd"),
           S.PersistentVolume("slow", 50, {"ReadWriteOnce"},
                              storage_class="hdd")]
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"},
                                   storage_class="standard")
    name, reason = S.bind(pvs, pvc)
    assert name is None
    assert reason.startswith("class:")


def test_bind_skips_already_bound_pv(S):
    taken = S.PersistentVolume("taken", 50, {"ReadWriteOnce"},
                               claim_ref="someone-else")
    free = S.PersistentVolume("free", 50, {"ReadWriteOnce"})
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteOnce"})
    name, _ = S.bind([taken, free], pvc)
    assert name == "free"
    assert taken.claim_ref == "someone-else"        # untouched


def test_bind_modes_overlap_not_equal(S):
    pv = S.PersistentVolume("both", 50, {"ReadWriteOnce", "ReadWriteMany"})
    pvc = S.PersistentVolumeClaim("data", 10, {"ReadWriteMany"})
    name, _ = S.bind([pv], pvc)
    assert name == "both"


# ------------------------------------------------------------------ reclaim
def test_reclaim_retain(S):
    pv = S.PersistentVolume("data-pv", 10, {"ReadWriteOnce"})
    out = S.pv_reclaim("Retain", pv, claim_deleted=True)
    assert out == "pv kept, Released status"


def test_reclaim_delete_and_recycle(S):
    pv = S.PersistentVolume("data-pv", 10, {"ReadWriteOnce"})
    assert S.pv_reclaim("Delete", pv, claim_deleted=True) == "pv deleted"
    assert S.pv_reclaim("Recycle", pv, claim_deleted=True) == "pv scrubbed"


def test_reclaim_default_is_delete(S):
    """No explicit policy, none on the PV -> Delete: the dynamic-provisioning
    default. Document it, then defend it in the interview."""
    pv = S.PersistentVolume("dyn-pv", 10, {"ReadWriteOnce"})   # reclaim_policy=None
    assert S.pv_reclaim(None, pv, claim_deleted=True) == "pv deleted"
    pv2 = S.PersistentVolume("admin-pv", 10, {"ReadWriteOnce"},
                              reclaim_policy="Retain")
    assert S.pv_reclaim(None, pv2, claim_deleted=True) == "pv kept, Released status"


def test_reclaim_ignores_live_claim(S):
    pv = S.PersistentVolume("data-pv", 10, {"ReadWriteOnce"})
    assert S.pv_reclaim("Delete", pv, claim_deleted=False) \
        == "claim still bound - pv unchanged"


# ------------------------------------------------------------------ mounts
def _spec(volumes, containers):
    return {"volumes": volumes, "containers": containers}


def test_mounts_clean_spec(S):
    spec = _spec([{"name": "data", "persistentVolumeClaim": {"claimName": "d"}}],
                 [{"volumeMounts": [{"name": "data", "mountPath": "/data"}]}])
    assert S.DeploymentMount().validate(spec) == []


def test_mounts_dangling_flagged(S):
    spec = _spec([{"name": "data", "persistentVolumeClaim": {"claimName": "d"}}],
                 [{"volumeMounts": [{"name": "typo", "mountPath": "/data"}]}])
    problems = S.DeploymentMount().validate(spec)
    assert "dangling mount typo" in problems


def test_mounts_unused_volume_warned(S):
    spec = _spec([{"name": "data", "persistentVolumeClaim": {"claimName": "d"}},
                  {"name": "scratch", "emptyDir": {}}],
                 [{"volumeMounts": [{"name": "data", "mountPath": "/data"}]}])
    problems = S.DeploymentMount().validate(spec)
    assert "unused volume scratch" in problems


def test_mounts_relative_mountpath_flagged(S):
    spec = _spec([{"name": "data", "persistentVolumeClaim": {"claimName": "d"}}],
                 [{"volumeMounts": [{"name": "data", "mountPath": "data"}]}])
    problems = S.DeploymentMount().validate(spec)
    assert "mountPath must be absolute: data" in problems


def test_mounts_multi_container_union(S):
    spec = _spec([{"name": "cfg", "configMap": {"name": "app-cfg"}}],
                 [{"volumeMounts": [{"name": "cfg", "mountPath": "/etc/cfg"}]},
                  {"volumeMounts": []}])
    assert S.DeploymentMount().validate(spec) == []


# ------------------------------------------------------------------ expose
def test_expose_env_name_transformation(S):
    out = S.expose("ConfigMap", ["my-key", "db.url", "plain"])
    names = [e["name"] for e in out]
    assert names == ["MY_KEY", "DB_URL", "PLAIN"]


def test_expose_env_refs_the_key(S):
    out = S.expose("Secret", ["password"])
    assert out == [{"name": "PASSWORD",
                    "valueFrom": {"secretKeyRef": {"key": "password"}}}]
    cm = S.expose("ConfigMap", ["x"])
    assert cm[0]["valueFrom"] == {"configMapKeyRef": {"key": "x"}}


def test_expose_volume_file_paths(S):
    out = S.expose("ConfigMap", ["redis.conf"], as_env=False)
    assert out == [{"path": "/etc/configmap/redis.conf"}]
    sec = S.expose("Secret", ["tls.crt"], as_env=False)
    assert sec == [{"path": "/etc/secret/tls.crt"}]


def test_expose_rejects_unknown_kind(S):
    with pytest.raises(ValueError):
        S.expose("Pod", ["x"])


# ------------------------------------------------------------------ RBAC
def _rbac(S):
    roles = {
        "configmap-reader": {"verbs": ["get", "list"],
                              "resources": ["configmaps"],
                              "namespace": "prod"},
        "logs-viewer": {"verbs": ["get"], "resources": ["pods"]},
    }
    bindings = {"worker-sa": "configmap-reader", "auditor-sa": "logs-viewer"}
    return S.RoleBindingSim(roles, bindings)


def test_rbac_allowed_in_own_namespace(S):
    assert _rbac(S).can("worker-sa", "get", "configmaps", namespace="prod") is True


def test_rbac_default_deny_unbound_subject(S):
    assert _rbac(S).can("nobody-sa", "get", "configmaps", namespace="prod") is False


def test_rbac_denies_wrong_verb_or_resource(S):
    rb = _rbac(S)
    assert rb.can("worker-sa", "delete", "configmaps", namespace="prod") is False
    assert rb.can("worker-sa", "get", "secrets", namespace="prod") is False


def test_rbac_namespaced_role_wrong_namespace_denied(S):
    assert _rbac(S).can("worker-sa", "get", "configmaps", namespace="dev") is False
    assert _rbac(S).can("worker-sa", "get", "configmaps") is False  # no ns given


def test_rbac_clusterrole_any_namespace(S):
    rb = _rbac(S)
    assert rb.can("auditor-sa", "get", "pods", namespace="dev") is True
    assert rb.can("auditor-sa", "get", "pods", namespace="prod") is True
    assert rb.can("auditor-sa", "get", "pods") is True
