import pytest


def make_agent(P, replies, tools=None, **cfg):
    tools = tools if tools is not None else {
        "search": lambda q: f"results for {q}",
        "write": lambda path, data: "written",
    }
    config = dict(max_turns=10, token_budget=10 ** 9, cost_cap_usd=10.0,
                  cost_per_call=0.01)
    config.update(cfg)
    llm = P.FakeLLM(replies)
    return P.ProductionAgent(llm, tools, config, P.FakeClock())


def test_happy_path(P):
    replies = ['CALL: search {"q": "agents"}',
               'CALL: write {"path": "/tmp/a", "data": "x"}',
               "DONE: shipped it"]
    a = make_agent(P, replies)
    res = a.run("do the thing")
    assert res["stopped_by"] == "done"
    assert res["answer"] == "shipped it"
    assert res["turns"] == 3
    assert res["cost_usd"] == pytest.approx(0.03)
    kinds = [e["kind"] for e in res["events"]]
    assert kinds.count("tool_call") == 2
    assert kinds.count("observation") == 2


def test_unknown_tool_continues_as_error(P):
    replies = ['CALL: nope {}', 'DONE: fine']
    a = make_agent(P, replies)
    res = a.run("t")
    assert res["stopped_by"] == "done"
    assert res["answer"] == "fine"
    assert any(e["kind"] == "tool_error" and "unknown tool" in e["error"]
               for e in res["events"])


def test_tool_exception_continues_as_error(P):
    def boom(**kw):
        raise RuntimeError("disk full")

    a = make_agent(P, ['CALL: write {"path": "x", "data": "y"}', "DONE: ok"],
                   tools={"write": boom})
    res = a.run("t")
    assert res["stopped_by"] == "done"
    assert any(e["kind"] == "tool_error" and "disk full" in e["error"]
               for e in res["events"])


def test_three_consecutive_errors_abort(P):
    a = make_agent(P, ['CALL: nope {}'] * 10)
    res = a.run("t")
    assert res["stopped_by"] == "tool_errors"
    assert res["turns"] == 3


def test_success_resets_error_counter(P):
    replies = ['CALL: nope {}', 'CALL: nope {}', 'CALL: search {"q": "x"}',
               'CALL: nope {}', 'CALL: nope {}', "DONE: made it"]
    a = make_agent(P, replies)
    res = a.run("t")
    assert res["stopped_by"] == "done"
    assert res["turns"] == 6


def test_cost_cap_aborts_preserving_events(P):
    replies = ['CALL: search {"q": "a"}'] * 20
    a = make_agent(P, replies, cost_cap_usd=0.05, cost_per_call=0.01)
    res = a.run("t")
    assert res["stopped_by"] == "cost"
    assert res["cost_usd"] <= 0.05
    assert len(res["events"]) >= 4          # partial events preserved


def test_max_turns(P):
    a = make_agent(P, ['CALL: search {"q": "x"}'] * 50, max_turns=4)
    res = a.run("t")
    assert res["stopped_by"] == "max_turns"
    assert res["turns"] == 4


def test_checkpoint_resume_equals_uninterrupted(P):
    script = ['CALL: search {"q": "1"}', 'CALL: search {"q": "2"}',
              'CALL: search {"q": "3"}', "DONE: all done"]

    # uninterrupted run
    full = make_agent(P, list(script)).run("task")

    # interrupted run: 2 turns, checkpoint, resume
    a1 = make_agent(P, list(script))
    a1.config["max_turns"] = 2
    r1 = a1.run("task")
    assert r1["stopped_by"] == "max_turns"
    cp = a1.checkpoint()
    # build a fresh agent and resume
    a2 = make_agent(P, list(script))
    P.resume(a2, cp)
    a2.config["max_turns"] = 10
    r2 = a2.run("ignored-task")   # messages already restored; task not re-appended
    # The resumed agent inherits the restored turn count, so its final turns
    # equal the uninterrupted run's, and the answer matches exactly.
    assert r2["answer"] == full["answer"]
    assert r2["turns"] == full["turns"]
    assert r2["cost_usd"] == pytest.approx(full["cost_usd"])


def test_validate_healthy_run(P):
    a = make_agent(P, ['CALL: search {"q": "x"}', "DONE: ok"])
    res = a.run("t")
    assert P.validate(res["events"]) == []


def test_validate_flags_orphan_tool_call(P):
    events = [
        {"kind": "llm_call", "t": 0, "turn": 1, "cost_after": 0.01},
        {"kind": "tool_call", "t": 0, "turn": 1, "tool": "search", "args": {}},
        {"kind": "done", "t": 0, "turn": 1},
    ]
    v = P.validate(events)
    assert any("search" in s for s in v)


def test_validate_flags_cost_decrease(P):
    events = [
        {"kind": "llm_call", "t": 0, "cost_after": 0.03},
        {"kind": "llm_call", "t": 1, "cost_after": 0.01},
    ]
    v = P.validate(events)
    assert any("cost" in s for s in v)


def test_fake_llm_repeats_last(P):
    llm = P.FakeLLM(["a", "b"])
    assert llm([]) == "a"
    assert llm([]) == "b"
    assert llm([]) == "b"
    assert llm.i == 3


def test_fake_llm_resume_at(P):
    llm = P.FakeLLM(["a", "b"], resume_at=1)
    assert llm([]) == "b"
