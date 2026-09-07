"""Lab 02 tests. Pure stdlib, no cluster, no PyYAML — the object model simulated."""
import pytest


# ------------------------------------------------------------------ manifest loader
MANIFEST = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 3
  image: myregistry/api:1.4.0
"""


def test_parse_single_document(K):
    docs = K.load_manifest(MANIFEST)
    assert len(docs) == 1
    d = docs[0]
    assert d["apiVersion"] == "apps/v1"
    assert d["kind"] == "Deployment"
    assert d["metadata"]["name"] == "api"
    assert d["spec"]["replicas"] == 3                # int, not "3"
    assert d["spec"]["image"] == "myregistry/api:1.4.0"


def test_parse_multi_document_split(K):
    text = (MANIFEST + "---\n"
            + "apiVersion: v1\nkind: Service\nmetadata:\n  name: api-svc\n")
    docs = K.load_manifest(text)
    assert len(docs) == 2
    assert [d["kind"] for d in docs] == ["Deployment", "Service"]
    assert docs[1]["metadata"]["name"] == "api-svc"


def test_parse_quotes_and_ints(K):
    docs = K.load_manifest('key: "3"\nplain: 7\nname: \'api\'\n')
    assert docs[0]["key"] == "3"                     # quoted -> string
    assert docs[0]["plain"] == 7
    assert docs[0]["name"] == "api"


# ------------------------------------------------------------------ validator
# The API-server shape of a Deployment nests 3 deep (spec.selector.matchLabels),
# beyond the one-level YAML subset the loader supports — validation tests build
# the objects directly, exactly as real controllers receive them from the API.


def _deploy(name="api", replicas=3, match=None, labels=None):
    """Deployment dict as the API server hands it to the validator (the
    one-level YAML parser is exercised above; validation runs on real
    object shapes, which nest 3 deep)."""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": match if match is not None else {"app": name}},
            "template": {"metadata": {"labels":
                        labels if labels is not None else {"app": name}}},
        },
    }


def test_clean_deployment_passes(K):
    assert K.validate_object(_deploy()) == []


def test_clean_service_passes(K):
    doc = {"apiVersion": "v1", "kind": "Service",
           "metadata": {"name": "api-svc"}, "spec": {"type": "ClusterIP"}}
    assert K.validate_object(doc) == []


@pytest.mark.parametrize("doc,problem", [
    (_deploy(), "missing apiVersion"),                # handled below: del the key
    (_deploy(), "missing kind"),                      # handled below
    ({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {},
      "spec": {"replicas": 3, "selector": {"matchLabels": {"app": "api"}},
               "template": {"metadata": {"labels": {"app": "api"}}}}},
     "missing metadata.name"),
    (_deploy(replicas=None), "spec.replicas must be an int"),
    ({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api"},
      "spec": {"replicas": 3, "template": {"metadata": {"labels": {"app": "api"}}}}},
     "missing spec.selector.matchLabels"),
    (_deploy(match={"app": "api"}, labels={"app": "other"}),
     "selector matchLabels do not match template labels"),
    ({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api-svc"},
      "spec": {"type": "Magic"}},
     "spec.type must be one of ClusterIP, NodePort, LoadBalancer, ExternalName"),
])
def test_each_validation_rule_fires(K, doc, problem):
    if problem == "missing apiVersion":
        del doc["apiVersion"]
    elif problem == "missing kind":
        del doc["kind"]
    problems = K.validate_object(doc)
    assert problem in problems
    assert len(problems) == 1                          # one defect, one problem


# ------------------------------------------------------------------ recommend kind
def test_recommend_kind_mappings(K):
    assert K.recommend_kind({"stateful"}) == "StatefulSet"
    assert K.recommend_kind({"stateless-web"}) == "Deployment"
    assert K.recommend_kind({"node-agent"}) == "DaemonSet"
    assert K.recommend_kind({"batch"}) == "Job"
    assert K.recommend_kind({"cron"}) == "CronJob"
    assert K.recommend_kind({"singleton"}) == "StatefulSet"   # replicas: 1


def test_recommend_kind_defaults_to_deployment(K):
    assert K.recommend_kind(set()) == "Deployment"
    assert K.recommend_kind({"weird", "unknown-tag"}) == "Deployment"


# ------------------------------------------------------------------ reconcile
def test_reconcile_scale_up(K):
    assert K.reconcile({"replicas": 5, "image": "a:1"}, {"replicas": 3, "image": "a:1"}) \
        == ["scale to 5"]


def test_reconcile_scale_down(K):
    assert K.reconcile({"replicas": 1, "image": "a:1"}, {"replicas": 4, "image": "a:1"}) \
        == ["scale to 1"]


def test_reconcile_image_rolling_update(K):
    assert K.reconcile({"replicas": 3, "image": "a:2"}, {"replicas": 3, "image": "a:1"}) \
        == ["rolling update to a:2"]


def test_reconcile_noop(K):
    assert K.reconcile({"replicas": 3, "image": "a:1"}, {"replicas": 3, "image": "a:1"}) == []


def test_reconcile_is_level_triggered(K):
    """THE test. A level-triggered controller is a pure function: the same
    (desired, observed) pair must produce the same actions on every call —
    no event was consumed, no internal state may matter."""
    desired = {"replicas": 5, "image": "a:2"}
    observed = {"replicas": 3, "image": "a:1"}
    first = K.reconcile(desired, observed)
    assert first == ["scale to 5", "rolling update to a:2"]   # scale before image
    for _ in range(3):
        assert K.reconcile(desired, observed) == first


# ------------------------------------------------------------------ taints & tolerations
def test_schedulable_matching_toleration(K):
    pod = {"tolerations": [{"key": "gpu", "effect": "NoSchedule"}]}
    taints = [{"key": "gpu", "effect": "NoSchedule"}]
    assert K.schedulable(pod, taints) is True


def test_schedulable_missing_toleration(K):
    pod = {"tolerations": []}
    taints = [{"key": "gpu", "effect": "NoSchedule"}]
    assert K.schedulable(pod, taints) is False


def test_schedulable_wrong_effect(K):
    pod = {"tolerations": [{"key": "gpu", "effect": "NoExecute"}]}
    taints = [{"key": "gpu", "effect": "NoSchedule"}]
    assert K.schedulable(pod, taints) is False


def test_schedulable_no_taints(K):
    assert K.schedulable({"tolerations": []}, []) is True
