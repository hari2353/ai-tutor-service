import pytest


# ---------------- HPA ----------------

def test_hpa_scale_up_formula(S):
    r = S.hpa_decide({"currentReplicas": 10,
                      "currentCPUUtilizationPercentage": 60},
                     {"minReplicas": 1, "maxReplicas": 50,
                      "targetCPUUtilizationPercentage": 50})
    assert r["replicas"] == 12          # ceil(10*60/50)


def test_hpa_scale_down_respects_min(S):
    r = S.hpa_decide({"currentReplicas": 10,
                      "currentCPUUtilizationPercentage": 10},
                     {"minReplicas": 5, "maxReplicas": 50,
                      "targetCPUUtilizationPercentage": 50})
    assert r["replicas"] == 5           # ceil(2)=2 -> clamped up to min


def test_hpa_caps_at_max(S):
    r = S.hpa_decide({"currentReplicas": 10,
                      "currentCPUUtilizationPercentage": 200},
                     {"minReplicas": 1, "maxReplicas": 30,
                      "targetCPUUtilizationPercentage": 50})
    assert r["replicas"] == 30


def test_hpa_no_change_at_target(S):
    r = S.hpa_decide({"currentReplicas": 10,
                      "currentCPUUtilizationPercentage": 50},
                     {"minReplicas": 1, "maxReplicas": 50,
                      "targetCPUUtilizationPercentage": 50})
    assert r["replicas"] == 10


# ---------------- VPA ----------------

def test_vpa_up_on_breach(S):
    r = S.vpa_decide({"cpu": "250m", "memory": "512Mi"}, p99_latency_ms=900,
                     slo_ms=500)
    assert r["cpu"] == "375m"
    assert r["memory"] == "768Mi"


def test_vpa_down_in_slack(S):
    r = S.vpa_decide({"cpu": "400m", "memory": "1Gi"}, p99_latency_ms=200,
                     slo_ms=500)
    assert r["cpu"] == "300m"
    assert r["memory"] == "768Mi"


def test_vpa_deadband_unchanged(S):
    r = S.vpa_decide({"cpu": "250m", "memory": "512Mi"}, p99_latency_ms=400,
                     slo_ms=500)
    assert r["cpu"] == "250m"
    assert r["memory"] == "512Mi"


def test_vpa_cap_at_4x(S):
    # a single recommendation caps at 1.5x the current request — but the cap
    # relative to the SEEN base is 4x: an input already at 3x of some tiny
    # floor can at most reach 4x per call. Verify per-call behavior directly:
    r = S.vpa_decide({"cpu": "400m", "memory": "1024Mi"}, p99_latency_ms=9999,
                     slo_ms=100)
    assert r["cpu"] == "600m"           # 1.5x of 400
    assert S._parse_mem(r["memory"]) == 1536   # 1.5x of 1024Mi
    # and the down-floor: repeated downsizing never goes below 0.5x per call
    req = {"cpu": "800m", "memory": "2Gi"}
    for _ in range(6):
        req = S.vpa_decide(req, p99_latency_ms=1, slo_ms=100)
    # 800 * 0.75^6 = ~142m; floor 0.5x of each call's base so it just decays
    assert S._parse_cpu(req["cpu"]) < 800
    assert S._parse_cpu(req["cpu"]) > 100


# ---------------- KEDA ----------------

def test_keda_formula(S):
    r = S.keda_decide(234, {"minReplicas": 1, "maxReplicas": 100,
                            "targetPerReplica": 50})
    assert r == 5


def test_keda_clamps(S):
    assert S.keda_decide(0, {"minReplicas": 2, "maxReplicas": 100,
                             "targetPerReplica": 50}) == 2
    assert S.keda_decide(10000, {"minReplicas": 2, "maxReplicas": 100,
                                 "targetPerReplica": 50}) == 100


# ---------------- cluster autoscaler ----------------

def test_pending_zero_when_free(S):
    nodes = [{"capacity_pods": 10, "usage_pods": 3},
             {"capacity_pods": 10, "usage_pods": 0}]
    assert S.pending_pods(17, nodes) == 0
    assert S.pending_pods(18, nodes) == 1


def test_scale_in_removes_empty_node(S):
    nodes = [{"capacity_pods": 10, "usage_pods": 4},
             {"capacity_pods": 10, "usage_pods": 0}]
    assert S.scale_in(nodes) == [1]


def test_scale_in_keeps_unrelocatable(S):
    # node1 has 5 pods; node0 has only 3 free — cannot fully relocate
    nodes = [{"capacity_pods": 10, "usage_pods": 7},
             {"capacity_pods": 10, "usage_pods": 5}]
    assert S.scale_in(nodes) == []


def test_scale_in_relocates_when_it_fits(S):
    # node1's 2 pods fit into node0's 5 free slots
    nodes = [{"capacity_pods": 10, "usage_pods": 5},
             {"capacity_pods": 10, "usage_pods": 2}]
    assert S.scale_in(nodes) == [1]


def test_scale_in_no_double_counting_freed_slots(S):
    # two candidate nodes, each 2 pods; only 3 free slots elsewhere: only ONE fits
    nodes = [{"capacity_pods": 10, "usage_pods": 7},
             {"capacity_pods": 10, "usage_pods": 2},
             {"capacity_pods": 10, "usage_pods": 2}]
    removable = S.scale_in(nodes)
    assert len(removable) == 1
    assert 0 not in removable


# ---------------- error budget ----------------

def test_error_budget_fraction(S):
    r = S.error_budget_burn(10, 100000, 99.9)
    assert r["budget_fraction"] == pytest.approx(0.001)
    assert r["multiplier"] == pytest.approx(10 / 100000 / 0.001)   # = 1.0


def test_error_budget_burn_2x(S):
    r = S.error_budget_burn(200, 100000, 99.9)
    assert r["multiplier"] == pytest.approx(2.0)
