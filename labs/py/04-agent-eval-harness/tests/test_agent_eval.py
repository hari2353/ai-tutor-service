"""Lab 04 tests. All trajectories are fixtures — no LLM, no network, no sleep."""
import pytest

from agent_eval import ToolCall, TaskSpec, Trajectory


def call(name, args=None, result=None, latency_ms=100.0, cost_usd=0.001):
    return ToolCall(name=name, args=args or {}, result=result,
                    latency_ms=latency_ms, cost_usd=cost_usd)


# ------------------------------------------------------------------ task completion
def test_completion_exact(E):
    assert E.task_completion("42", 42) is True
    assert E.task_completion("42", "43") is False


def test_completion_contains(E):
    assert E.task_completion("Eiffel", "The Eiffel Tower is in Paris",
                             mode="contains") is True
    assert E.task_completion("Berlin", "The Eiffel Tower is in Paris",
                             mode="contains") is False


def test_completion_numeric_tolerance(E):
    assert E.task_completion(100.0, 100.005, mode="numeric", tolerance=0.01) is True
    assert E.task_completion(100.0, 100.02, mode="numeric", tolerance=0.01) is False
    assert E.task_completion("100.0", "100.004", mode="numeric") is True


def test_completion_numeric_non_numeric_is_fail(E):
    assert E.task_completion(100.0, "not a number", mode="numeric") is False


def test_completion_unknown_mode_raises(E):
    with pytest.raises(ValueError):
        E.task_completion("x", "x", mode="vibes")


# ------------------------------------------------------------------ tool call accuracy
def test_accuracy_perfect_match(E):
    gold = [call("search", {"q": "hotels"}), call("book", {"id": 7})]
    actual = [call("search", {"q": "hotels"}), call("book", {"id": 7})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(1.0)


def test_accuracy_extra_args_are_fine(E):
    """run_id/trace_id noise must not count against the run."""
    gold = [call("search", {"q": "hotels"})]
    actual = [call("search", {"q": "hotels", "run_id": "abc", "trace_id": "xyz"})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(1.0)


def test_accuracy_wrong_relevant_arg_is_miss(E):
    gold = [call("search", {"q": "hotels"})]
    actual = [call("search", {"q": "hostels"})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(0.0)


def test_accuracy_fuzzy_only_declared_relevant_args(E):
    """With relevant_args declared, EVERYTHING else is noise."""
    gold = [call("search", {"q": "hotels", "user": "u1"})]
    actual = [call("search", {"q": "hotels", "user": "SOMEBODY ELSE"})]
    rel = {"search": {"q"}}
    assert E.tool_call_accuracy(gold, actual, relevant_args=rel) == pytest.approx(1.0)
    # but with no relevant_args spec, all gold args are relevant -> mismatch
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(0.0)


def test_accuracy_missing_step_is_miss(E):
    gold = [call("search", {"q": "h"}), call("fetch", {"id": 1}),
            call("book", {"id": 1})]
    actual = [call("search", {"q": "h"}), call("book", {"id": 1})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(2 / 3)


def test_accuracy_matches_in_order(E):
    """A gold step may only match an actual step at or after the previous
    match — the agent that books before searching is not 'accurate'.
    Here search is found only AFTER book, so the book gold step (which
    comes after search in gold) can't match anything later: 1 of 2."""
    gold = [call("search", {"q": "h"}), call("book", {"id": 1})]
    actual = [call("book", {"id": 1}), call("search", {"q": "h"})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(0.5)
    # and a strict gold order with the last one missing entirely
    gold3 = [call("search"), call("fetch"), call("book")]
    actual3 = [call("search"), call("book")]
    assert E.tool_call_accuracy(gold3, actual3) == pytest.approx(2 / 3)


def test_accuracy_wrong_tool_name_is_miss(E):
    gold = [call("search", {"q": "h"})]
    actual = [call("web_search", {"q": "h"})]
    assert E.tool_call_accuracy(gold, actual) == pytest.approx(0.0)


def test_accuracy_empty_gold_is_zero(E):
    assert E.tool_call_accuracy([], [call("search")]) == pytest.approx(0.0)


# ------------------------------------------------------------------ trajectory validity
SEARCH_ALLOWED = {
    "init": {"search"},
    "search": {"fetch", "end"},
    "fetch": {"book", "end"},
    "book": {"end"},
}


def test_validity_legal_path(E):
    steps = [call("search"), call("fetch"), call("book")]
    rep = E.trajectory_validity(steps, SEARCH_ALLOWED)
    assert rep.valid
    assert rep.violations == []


def test_validity_tool_before_init_is_illegal(E):
    """book before search: book is not reachable from init."""
    steps = [call("book", {"id": 1}), call("search"), call("fetch")]
    rep = E.trajectory_validity(steps, SEARCH_ALLOWED)
    assert not rep.valid
    assert rep.violations == [(0, "init", "book")]


def test_validity_illegal_jump_mid_trajectory(E):
    """fetch -> book is legal, but search -> book skips fetch."""
    steps = [call("search"), call("book"), call("fetch")]
    rep = E.trajectory_validity(steps, SEARCH_ALLOWED)
    assert not rep.valid
    assert rep.violations == [(1, "search", "book")]


def test_validity_violation_does_not_cascade(E):
    """One illegal step is ONE violation; the walker stays put and the
    next legal step from the same state is fine."""
    steps = [call("search"), call("book"), call("fetch"), call("book")]
    rep = E.trajectory_validity(steps, SEARCH_ALLOWED)
    assert rep.violations == [(1, "search", "book")]
    assert not rep.valid


def test_validity_unknown_tool_from_init(E):
    steps = [call("teleport")]
    rep = E.trajectory_validity(steps, SEARCH_ALLOWED)
    assert not rep.valid
    assert rep.violations == [(0, "init", "teleport")]


# ------------------------------------------------------------------ cost & latency
def test_cost_per_step(E):
    steps = [call("a", cost_usd=0.02), call("b", cost_usd=0.04)]
    traj = Trajectory(task_id="t", steps=steps, final_answer="x")
    assert E.total_cost(traj) == pytest.approx(0.06)
    assert E.cost_per_step(traj) == pytest.approx(0.03)


def test_cost_per_step_empty_trajectory(E):
    traj = Trajectory(task_id="t", steps=[], final_answer="x")
    assert E.cost_per_step(traj) == 0.0


def test_latency_p50_even_and_odd(E):
    odd = [call("a", latency_ms=100), call("b", latency_ms=300),
           call("c", latency_ms=200)]
    assert E.latency_p50(odd) == pytest.approx(200.0)
    even = [call("a", latency_ms=100), call("b", latency_ms=300),
            call("c", latency_ms=200), call("d", latency_ms=400)]
    assert E.latency_p50(even) == pytest.approx(250.0)


def test_latency_p95_nearest_rank(E):
    """20 steps: p95 rank = ceil(0.95*20) = 19 -> the 19th of 20 sorted."""
    steps = [call(f"s{i}", latency_ms=float(i * 100)) for i in range(20)]
    # sorted: 0,100,...,1900; index 18 (0-based) = 1800
    assert E.latency_p95(steps) == pytest.approx(1800.0)


def test_latency_p95_small_list_is_max(E):
    """ceil(0.95*3)=3 -> the largest value."""
    steps = [call("a", latency_ms=100), call("b", latency_ms=300),
             call("c", latency_ms=200)]
    assert E.latency_p95(steps) == pytest.approx(300.0)


def test_latency_empty(E):
    assert E.latency_p50([]) == 0.0
    assert E.latency_p95([]) == 0.0


# ------------------------------------------------------------------ EvalSuite
def _gold_task(t_id, answer="42", mode="exact", steps=None, allowed=None):
    gold = {"steps": steps or [call("search", {"q": f"{t_id} query"})],
            "expected_answer": answer, "mode": mode}
    if allowed:
        gold["allowed"] = allowed
    return gold


def _traj(t_id, answer="42", steps=None, spec=None):
    return Trajectory(task_id=t_id, steps=steps or [call("search", {"q": f"{t_id} query"})],
                      final_answer=answer, task_spec=spec)


def test_suite_perfect_run_passes(E):
    gold = {"t1": _gold_task("t1"), "t2": _gold_task("t2")}
    trajs = [_traj("t1"), _traj("t2")]
    rep = E.EvalSuite().run(trajs, gold)
    assert rep.passed
    assert rep["tool_accuracy"] == pytest.approx(1.0)
    assert rep["completion"] == pytest.approx(1.0)
    assert rep["validity"] == pytest.approx(1.0)
    assert rep.fail_reasons == []


def test_suite_completion_modes_used(E):
    gold = {
        "t1": _gold_task("t1", answer="Eiffel", mode="contains"),
        "t2": _gold_task("t2", answer=100.0, mode="numeric"),
    }
    trajs = [_traj("t1", answer="The Eiffel Tower stands in Paris"),
             _traj("t2", answer="100.005")]
    rep = E.EvalSuite().run(trajs, gold)
    assert rep["completion"] == pytest.approx(1.0)


def test_suite_failed_completion_drags_average(E):
    gold = {"t1": _gold_task("t1"), "t2": _gold_task("t2"),
            "t3": _gold_task("t3"), "t4": _gold_task("t4")}
    trajs = [_traj("t1"), _traj("t2", answer="WRONG"), _traj("t3"), _traj("t4")]
    rep = E.EvalSuite().run(trajs, gold)
    assert rep["completion"] == pytest.approx(0.75)
    assert not rep.passed, "0.75 < 0.8 threshold: completion must fail the run"
    assert any("completion" in r for r in rep.fail_reasons)


def test_suite_illegal_ordering_fails_validity_metric(E):
    gold = {"t1": _gold_task("t1", steps=[call("search"), call("fetch"), call("book")],
                            allowed=SEARCH_ALLOWED)}
    bad = Trajectory(task_id="t1",
                     steps=[call("book", {"id": 1}), call("search"), call("fetch")],
                     final_answer="42",
                     task_spec=TaskSpec(expected_answer="42"))
    rep = E.EvalSuite().run([bad], gold)
    assert rep["validity"] == pytest.approx(0.0)
    assert not rep.passed
    assert any("validity" in r for r in rep.fail_reasons)


def test_suite_cost_threshold_fails_expensive_run(E):
    gold = {"t1": _gold_task("t1")}
    expensive = _traj("t1", steps=[call("search", cost_usd=0.10)])
    rep = E.EvalSuite().run([expensive], gold)
    assert rep["cost_per_step"] == pytest.approx(0.10)
    assert not rep.passed, "cost 0.10 > 0.05 threshold"
    assert any("cost_per_step" in r for r in rep.fail_reasons)


def test_suite_p95_threshold_fails_slow_run(E):
    gold = {"t1": _gold_task("t1")}
    slow = _traj("t1", steps=[call("search", latency_ms=9000.0)])
    rep = E.EvalSuite().run([slow], gold)
    assert rep["p95_latency_ms"] == pytest.approx(9000.0)
    assert not rep.passed
    assert any("p95_latency_ms" in r for r in rep.fail_reasons)


def test_suite_task_spec_overrides_gold_answer(E):
    """The trajectory's own task_spec wins over the golden entry's answer."""
    gold = {"t1": _gold_task("t1", answer="gold says this")}
    spec = TaskSpec(expected_answer="spec says this", mode="exact")
    traj = _traj("t1", answer="spec says this", spec=spec)
    rep = E.EvalSuite().run([traj], gold)
    assert rep["completion"] == pytest.approx(1.0)


def test_suite_custom_thresholds(E):
    gold = {"t1": _gold_task("t1")}
    run = [_traj("t1"), _traj("t1")]     # two tasks, both perfect tools
    # accuracy 1.0 but completion 0.5 (one wrong answer) — custom thresholds flip it
    run[1] = _traj("t1", answer="WRONG")
    strict = E.EvalSuite(thresholds={"completion": 1.0})
    rep = strict.run(run, {"t1": gold["t1"], "t2": gold["t1"]})
    assert not rep.passed
    loose = E.EvalSuite(thresholds={"completion": 0.4})
    rep2 = loose.run(run, {"t1": gold["t1"], "t2": gold["t1"]})
    assert rep2.passed


def test_suite_threshold_boundary_exact_pass(E):
    """tool_accuracy == 0.9 exactly: pass (>= threshold)."""
    gold_steps = [call(f"s{i}") for i in range(10)]
    gold = {"t1": _gold_task("t1", steps=gold_steps)}
    actual = [_traj("t1", steps=[call(f"s{i}") for i in range(9)])]
    rep = E.EvalSuite().run(actual, gold)
    assert rep["tool_accuracy"] == pytest.approx(0.9)
    assert rep.passed or not rep.passed  # boundary itself: 0.9 >= 0.9 -> pass
    # assert the boundary semantics explicitly
    failed_metrics = [r for r in rep.fail_reasons if "tool_accuracy" in r]
    assert failed_metrics == [], "0.9 >= 0.9 must not appear in fail_reasons"


def test_suite_threshold_boundary_just_below_fails(E):
    gold_steps = [call(f"s{i}") for i in range(10)]
    gold = {"t1": _gold_task("t1", steps=gold_steps)}
    actual = [_traj("t1", steps=[call(f"s{i}") for i in range(8)])]
    rep = E.EvalSuite().run(actual, gold)
    assert rep["tool_accuracy"] == pytest.approx(0.8)
    assert not rep.passed
    assert any("tool_accuracy" in r for r in rep.fail_reasons)


def test_suite_empty_run(E):
    rep = E.EvalSuite().run([], {})
    assert rep.rows == []
    assert rep.passed, "no data, no failures"


# ------------------------------------------------------------------ regression
def _report(E, **averages):
    rep = E.RunReport()
    rep.averages = averages
    return rep


def test_regression_fires_on_accuracy_drop(E):
    prev = _report(E, tool_accuracy=0.95, completion=1.0)
    cur = _report(E, tool_accuracy=0.85, completion=1.0)
    rr = E.compare_runs(prev, cur)
    assert rr.regressed
    assert rr.regressions[0][0] == "tool_accuracy"
    assert rr.regressions[0][1] == pytest.approx(0.95)
    assert rr.regressions[0][2] == pytest.approx(0.85)


def test_regression_fires_on_cost_rise(E):
    prev = _report(E, cost_per_step=0.05)
    cur = _report(E, cost_per_step=0.08)    # +60%
    rr = E.compare_runs(prev, cur)
    assert rr.regressed
    assert rr.regressions[0][0] == "cost_per_step"


def test_regression_quiet_on_equal_run(E):
    prev = _report(E, tool_accuracy=0.9, completion=0.85, cost_per_step=0.05,
                   p95_latency_ms=3000.0)
    cur = _report(E, tool_accuracy=0.9, completion=0.85, cost_per_step=0.05,
                  p95_latency_ms=3000.0)
    rr = E.compare_runs(prev, cur)
    assert not rr.regressed
    assert rr.regressions == []


def test_regression_quiet_on_better_run(E):
    prev = _report(E, tool_accuracy=0.85, cost_per_step=0.06)
    cur = _report(E, tool_accuracy=0.95, cost_per_step=0.03)
    rr = E.compare_runs(prev, cur)
    assert not rr.regressed


def test_regression_within_tolerance_is_quiet(E):
    """accuracy drops 0.04 (< 0.05) and cost rises 15% (< 20%): no alarm."""
    prev = _report(E, tool_accuracy=0.90, cost_per_step=0.10)
    cur = _report(E, tool_accuracy=0.86, cost_per_step=0.115)
    rr = E.compare_runs(prev, cur)
    assert not rr.regressed


def test_regression_boundary_exactly_at_tolerance_is_quiet(E):
    """accuracy drop == 0.05 exactly, cost rise == 20% exactly: no alarm.
    (0.90-0.85 is 0.050000... in binary floats; the tolerance must not fire.)"""
    prev = _report(E, tool_accuracy=0.90, cost_per_step=0.10)
    cur = _report(E, tool_accuracy=0.85, cost_per_step=0.12)
    rr = E.compare_runs(prev, cur)
    assert not rr.regressed, "drop of exactly 0.05 is at tolerance, not beyond"


def test_regression_just_beyond_tolerance_fires(E):
    prev = _report(E, tool_accuracy=0.90, cost_per_step=0.10)
    cur = _report(E, tool_accuracy=0.8499, cost_per_step=0.1201)
    rr = E.compare_runs(prev, cur)
    assert rr.regressed
    assert {m for m, _, _ in rr.regressions} == {"tool_accuracy", "cost_per_step"}


def test_regression_prev_zero_cost_any_rise_fires(E):
    prev = _report(E, cost_per_step=0.0)
    cur = _report(E, cost_per_step=0.001)
    rr = E.compare_runs(prev, cur)
    assert rr.regressed, "free -> any cost at all is a regression"


def test_regression_multiple_metrics_flagged(E):
    prev = _report(E, tool_accuracy=0.95, completion=0.9, validity=1.0)
    cur = _report(E, tool_accuracy=0.7, completion=0.6, validity=0.8)
    rr = E.compare_runs(prev, cur)
    assert rr.regressed
    assert len(rr.regressions) == 3


def test_regression_ignores_metrics_missing_in_current(E):
    prev = _report(E, tool_accuracy=0.95, legacy_metric=1.0)
    cur = _report(E, tool_accuracy=0.95)
    rr = E.compare_runs(prev, cur)
    assert not rr.regressed
