"""Lab 12 tests. Every agent is a deterministic fake — no LLM, no I/O, no sleeps."""
import pytest


# ------------------------------------------------------------------ supervisor
def test_supervisor_dispatch_routes_to_named_worker(R):
    calls = []

    def sql_agent(task):
        calls.append(task)
        return f"rows for {task}"

    sup = R.Supervisor(workers={"sql": sql_agent, "docs": lambda t: "doc hit"})
    assert sup.dispatch("find revenue", "sql") == "rows for find revenue"
    assert calls == ["find revenue"]


def test_supervisor_dispatch_unknown_worker(R):
    sup = R.Supervisor(workers={"sql": lambda t: "rows"})
    with pytest.raises(R.RoutingError):
        sup.dispatch("anything", "web")


def test_supervisor_broadcast_survives_one_worker_crash(R):
    ran = []

    def ok(task):
        ran.append("ok")
        return "fine"

    def boom(task):
        ran.append("boom")
        raise RuntimeError("worker down")

    def also_ok(task):
        ran.append("also_ok")
        return "also fine"

    sup = R.Supervisor(workers={"first": ok, "crashy": boom, "last": also_ok})
    results = sup.broadcast("task")
    assert results["first"] == "fine"
    assert results["last"] == "also fine"
    failure = results["crashy"]
    assert isinstance(failure, R.Failure)
    assert failure.worker == "crashy"
    assert isinstance(failure.error, RuntimeError)
    assert str(failure.error) == "worker down"
    assert set(ran) == {"ok", "boom", "also_ok"}    # the crash contained itself


# ------------------------------------------------------------------ pipeline
def test_pipeline_threads_each_stage_output_to_the_next(R):
    seen = []

    def upper(t):
        seen.append(t)
        return t.upper()

    def excite(t):
        seen.append(t)
        return t + "!"

    pipe = R.Pipeline([upper, excite, lambda t: f"<{t}>"])
    assert pipe.run("go") == "<GO!>"
    assert seen == ["go", "GO"]          # stage 2 got stage 1's output, not the task


def test_pipeline_stage_error_aborts_with_partial_trace(R):
    events = []
    after = []

    def ok1(t):
        events.append("stage0")
        return t + "-1"

    def abort(t):
        events.append("stage1")
        raise R.StageError("context budget blown")

    def never(t):
        after.append("must not run")
        return t

    pipe = R.Pipeline([ok1, abort, never])
    with pytest.raises(R.PipelineAborted) as excinfo:
        pipe.run("spec")
    err = excinfo.value
    assert err.trace == ["spec-1"]      # completed stage outputs only
    assert err.stage_index == 1
    assert isinstance(err.error, R.StageError)
    assert str(err.error) == "context budget blown"
    assert after == []                  # stages after the failure never ran
    assert events == ["stage0", "stage1"]


def test_pipeline_bare_exception_is_a_bug_not_an_abort(R):
    def buggy(t):
        raise ValueError("off-by-one")

    pipe = R.Pipeline([buggy, lambda t: t + "!"])
    with pytest.raises(ValueError):     # raw — not wrapped in PipelineAborted
        pipe.run("x")


# ------------------------------------------------------------------ debate
def test_debate_judge_picks_longest_proposal(R):
    def longest_judge(proposals, task):
        return max(range(len(proposals)), key=lambda i: len(proposals[i]))

    debate = R.Debate(
        proposers=[lambda t: "short",
                   lambda t: "a bit longer",
                   lambda t: "the longest proposal by far"],
        judge=longest_judge,
    )
    winner, proposals = debate.run("explain CRDTs")
    assert winner == 2
    assert proposals == ["short", "a bit longer", "the longest proposal by far"]


def test_debate_judge_sees_all_proposals_and_the_task(R):
    seen = {}

    def spy_judge(proposals, task):
        seen["proposals"] = proposals
        seen["task"] = task
        return 0

    debate = R.Debate(proposers=[lambda t: f"{t}-a", lambda t: f"{t}-b"],
                      judge=spy_judge)
    winner, _ = debate.run("rank db options")
    assert seen["proposals"] == ["rank db options-a", "rank db options-b"]
    assert seen["task"] == "rank db options"
    assert winner == 0


# ------------------------------------------------------------------ blackboard
def _abc_agents():
    """agent1 adds "a" if missing; agent2 adds "b" once "a" exists;
    agent3 adds "c" only while "b" is absent."""
    def add_a(state):
        return {} if "a" in state else {"a": 1}

    def add_b_if_a(state):
        if "a" in state and "b" not in state:
            return {"b": 1}
        return {}

    def add_c_until_b(state):
        return {} if "b" in state else {"c": 1}

    return [add_a, add_b_if_a, add_c_until_b]


def test_blackboard_abc_converges_in_two_rounds(R):
    bb = R.Blackboard(_abc_agents())
    state, rounds = bb.run()
    assert state == {"a": 1, "b": 1}    # "c" never lands: "b" arrived first
    assert rounds == 2                  # round 1 changed, round 2 confirmed quiescence


def test_blackboard_agent_sees_earlier_same_round_writes(R):
    """If agent2 could not see agent1's write within round 1, convergence
    would take 3 rounds instead of 2 — the sequential semantics are the spec."""
    bb = R.Blackboard(_abc_agents())
    _, rounds = bb.run(initial_state={"seed": True})
    assert rounds == 2


def test_blackboard_respects_initial_state(R):
    bb = R.Blackboard(_abc_agents())
    state, _ = bb.run(initial_state={"a": 1})
    assert state == {"a": 1, "b": 1}


def test_blackboard_hits_max_rounds_when_never_converging(R):
    def churn(state):
        return {f"k{len(state)}": True}      # always something new

    bb = R.Blackboard([churn])               # default max_rounds=3
    state, rounds = bb.run()
    assert rounds == 3
    assert len(state) == 3

    bb5 = R.Blackboard([churn], max_rounds=5)
    _, rounds5 = bb5.run()
    assert rounds5 == 5


def test_blackboard_quiesces_in_one_round(R):
    bb = R.Blackboard([lambda s: {}, lambda s: {}])
    state, rounds = bb.run()
    assert state == {}
    assert rounds == 1                      # the single changeless round counts


# ------------------------------------------------------------------ router
def test_router_classifier_selects_the_worker(R):
    def classify(task):
        return "sql" if "query" in task else "docs"

    router = R.Router(classifier=classify,
                      workers={"sql": lambda t: "rows", "docs": lambda t: "doc hit"})
    assert router.route("write a query") == "rows"
    assert router.route("find the doc") == "doc hit"


def test_router_unknown_route_raises(R):
    router = R.Router(classifier=lambda t: "ghost",
                      workers={"sql": lambda t: "rows"})
    with pytest.raises(R.RoutingError):
        router.route("anything")
