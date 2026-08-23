"""Lab 02 tests. No clocks, no sleeps — the budget is steps and the model is fake."""
import json

import pytest


# ------------------------------------------------------------------ FakeLLM
def test_fake_llm_records_prompts_and_pops_script_in_order(R):
    llm = R.FakeLLM([{"final": "a"}, {"final": "b"}])
    assert llm.complete([{"role": "user", "content": "q1"}]) == {"final": "a"}
    assert llm.complete([{"role": "user", "content": "q2"}]) == {"final": "b"}
    assert llm.prompts[0][0]["content"] == "q1"
    assert llm.prompts[1][0]["content"] == "q2"


def test_fake_llm_survives_exhausted_script(R):
    llm = R.FakeLLM([])
    out = llm.complete([{"role": "user", "content": "anything"}])
    assert out == {"final": ""}
    assert llm.consumed() == 0
    assert llm.remaining() == 0


def test_fake_llm_hands_out_copies_not_its_script(R):
    scripted = [{"tool": "t", "args": {"k": [1, 2]}}]
    llm = R.FakeLLM(scripted)
    out = llm.complete([])
    out["args"]["k"].append(99)
    assert llm.script[0]["args"]["k"] == [1, 2]


# ------------------------------------------------------------------ happy path
def test_happy_path_uses_tool_then_finals(R):
    tools = {"echo": lambda args: {"you_said": args["msg"]}}
    llm = R.FakeLLM([
        {"tool": "echo", "args": {"msg": "hi"}},
        {"final": "done"},
    ])
    res = R.AgentLoop(llm, tools).run("say hi")
    assert (res.answer, res.reason, res.steps) == ("done", "final", 2)


def test_first_prompt_is_the_task_as_user_message(R):
    llm = R.FakeLLM([{"final": "ok"}])
    R.AgentLoop(llm, {}).run("what is 2+2")
    assert len(llm.prompts) == 1
    assert llm.prompts[0][0] == {"role": "user", "content": "what is 2+2"}


def test_observation_content_reaches_next_prompt(R):
    tools = {"double": lambda args: {"value": args["n"] * 2}}
    llm = R.FakeLLM([
        {"tool": "double", "args": {"n": 21}},
        {"final": "42 it is"},
    ])
    res = R.AgentLoop(llm, tools).run("double 21")
    assert res.reason == "final"
    observation_msgs = [m for m in llm.prompts[1]
                        if m["role"] == "user" and m["content"].startswith("Observation:")]
    assert observation_msgs, "observation must be fed back as its own message"
    assert '{"value":42}' in observation_msgs[-1]["content"].replace(" ", "")


def test_assistant_turn_records_the_raw_action(R):
    action = {"tool": "echo", "args": {"x": 1}}
    llm = R.FakeLLM([action, {"final": "ok"}])
    R.AgentLoop(llm, {"echo": lambda a: a}).run("go")
    roles = [m["role"] for m in llm.prompts[1]]
    contents = [m["content"] for m in llm.prompts[1]]
    assert roles == ["user", "assistant", "user"]
    assert json.loads(contents[1]) == action


# ------------------------------------------------------------------ recovery paths
def test_unknown_tool_becomes_error_observation_and_loop_continues(R):
    llm = R.FakeLLM([
        {"tool": "teleport", "args": {}},
        {"final": "recovered"},
    ])
    res = R.AgentLoop(llm, {}).run("try magic")
    assert res.answer == "recovered"
    assert res.reason == "final"
    obs = _observations(llm)[0]
    assert obs == "Observation: error: unknown tool teleport"


def test_tool_crash_becomes_error_observation_never_propagates(R):
    def bomb(args):
        raise ZeroDivisionError("division by zero")

    llm = R.FakeLLM([
        {"tool": "bomb", "args": {}},
        {"final": "survived"},
    ])
    res = R.AgentLoop(llm, {"bomb": bomb}).run("pull it")
    assert res.answer == "survived"
    assert _observations(llm)[0] == "Observation: error: division by zero"


def test_agent_recovers_after_two_failures_in_a_row(R):
    calls = {"n": 0}

    def flaky(args):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ValueError(f"attempt {calls['n']} failed")
        return {"ok": True}

    llm = R.FakeLLM([
        {"tool": "flaky", "args": {}},
        {"tool": "flaky", "args": {}},
        {"tool": "flaky", "args": {}},
        {"final": "third time lucky"},
    ])
    res = R.AgentLoop(llm, {"flaky": flaky}).run("persist")
    assert res.answer == "third time lucky"
    assert res.steps == 4
    assert "error: attempt 1 failed" in _observations(llm)[0]
    assert "error: attempt 2 failed" in _observations(llm)[1]


# ------------------------------------------------------------------ budgets
def test_budget_stop_returns_reason_budget(R):
    llm = R.FakeLLM([{"tool": "tick", "args": {}} for _ in range(10)])
    res = R.AgentLoop(llm, {"tick": lambda a: {"tock": True}}, max_steps=3).run("loop forever")
    assert (res.answer, res.steps, res.reason) == (None, 3, "budget")
    assert len(llm.prompts) == 3                # exactly max_steps model calls


def test_max_steps_zero_is_immediate_budget(R):
    llm = R.FakeLLM([{"final": "never reached"}])
    res = R.AgentLoop(llm, {}, max_steps=0).run("no time")
    assert (res.answer, res.steps, res.reason) == (None, 0, "budget")
    assert llm.prompts == []


def test_default_max_steps_is_eight(R):
    llm = R.FakeLLM([{"tool": "tick", "args": {}} for _ in range(20)])
    res = R.AgentLoop(llm, {"tick": lambda a: {}}).run("loop")
    assert (res.steps, res.reason) == (8, "budget")


# ------------------------------------------------------------------ purity rules
def test_tools_dict_is_never_mutated(R):
    tools = {"echo": lambda args: args}
    snapshot = dict(tools)
    llm = R.FakeLLM([
        {"tool": "echo", "args": {"a": 1}},
        {"tool": "ghost", "args": {}},
        {"final": "ok"},
    ])
    R.AgentLoop(llm, tools).run("keep my dict tidy")
    assert tools == snapshot


def test_tool_receives_a_copy_of_scripted_args(R):
    def greedy(args):
        args["list"].append(999)
        args["new"] = True
        return {}

    llm = R.FakeLLM([{"tool": "greedy", "args": {"list": [1, 2]}}, {"final": "ok"}])
    R.AgentLoop(llm, {"greedy": greedy}).run("mutate away")
    assert llm.script[0]["args"] == {"list": [1, 2]}


def test_final_short_circuits_remaining_script(R):
    llm = R.FakeLLM([
        {"tool": "echo", "args": {}},
        {"final": "enough"},
        {"final": "never used"},
        {"final": "never used either"},
    ])
    res = R.AgentLoop(llm, {"echo": lambda a: {}}).run("stop early")
    assert res.answer == "enough"
    assert res.steps == 2
    assert llm.consumed() == 2
    assert llm.remaining() == 2


def test_non_string_tool_output_is_jsonified_into_observation(R):
    llm = R.FakeLLM([
        {"tool": "calc", "args": {"op": "sum"}},
        {"final": "read it back"},
    ])
    R.AgentLoop(llm, {"calc": lambda a: 41 + 1}).run("math")
    assert "42" in _observations(llm)[0]


# ------------------------------------------------------------------ helpers
def _observations(llm):
    """Every distinct observation string, in the order it first appeared."""
    out = []
    for prompt in llm.prompts:
        for msg in prompt:
            if msg["role"] == "user" and msg["content"].startswith("Observation:"):
                if msg["content"] not in out:
                    out.append(msg["content"])
    return out
