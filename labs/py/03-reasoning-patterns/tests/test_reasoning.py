"""Lab 03 tests. No clocks, no sleeps, no randomness — the model is scripted."""
import json

import pytest


# ------------------------------------------------------------------ FakeLLM
def test_fake_llm_pops_scripted_responses_in_order_and_records_prompts(R):
    llm = R.FakeLLM([{"answer": "a"}, {"answer": "b"}])
    assert llm.complete([{"role": "user", "content": "q1"}]) == {"answer": "a"}
    assert llm.complete([{"role": "user", "content": "q2"}]) == {"answer": "b"}
    assert llm.prompts[0][0]["content"] == "q1"
    assert llm.prompts[1][0]["content"] == "q2"
    assert (llm.consumed(), llm.remaining()) == (2, 0)


def test_fake_llm_dry_script_returns_empty_final(R):
    llm = R.FakeLLM([])
    out = llm.complete([{"role": "user", "content": "anything"}])
    assert out == {"final": ""}
    assert (llm.consumed(), llm.remaining()) == (0, 0)


def test_fake_llm_hands_out_copies_not_its_script(R):
    llm = R.FakeLLM([{"tool": "t", "args": {"k": [1]}}])
    out = llm.complete([])
    out["args"]["k"].append(9)
    assert llm.script[0]["args"]["k"] == [1]


# ------------------------------------------------------------------ ReAct
def test_react_trace_is_exact_thought_action_observation_interleave(R):
    tools = {"lookup": lambda args: {"fact": "legless"}}
    llm = R.FakeLLM([
        {"thought": "find the fact", "tool": "lookup", "args": {"q": "snake"}},
        {"thought": "got it", "final": "snakes have no legs"},
    ])
    res = R.react_loop(llm, tools, max_steps=4, task="how many legs")
    assert res.reason == "final"
    assert res.answer == "snakes have no legs"
    assert res.steps == 2
    assert res.trace == [
        "Thought: find the fact",
        'Action: lookup({"q": "snake"})',
        'Observation: {"fact": "legless"}',
        "Thought: got it",
        "Final: snakes have no legs",
    ]


def test_react_every_action_has_a_thought_before_it_and_an_observation_after(R):
    llm = R.FakeLLM([
        {"thought": "one", "tool": "tick", "args": {}},
        {"thought": "two", "tool": "tick", "args": {}},
        {"thought": "three", "final": "enough"},
    ])
    res = R.react_loop(llm, {"tick": lambda a: "tock"}, max_steps=5, task="loop")
    trace = res.trace
    actions = [i for i, line in enumerate(trace) if line.startswith("Action:")]
    assert len(actions) == 2
    for i in actions:
        assert any(trace[j].startswith("Thought:") for j in range(i)), \
            "no thought precedes this action"
        assert trace[i + 1].startswith("Observation:"), \
            "observation must follow its action"
    # every thought comes before the first action or right after an observation
    thoughts = [i for i, line in enumerate(trace) if line.startswith("Thought:")]
    assert thoughts == sorted(thoughts)
    assert trace[0].startswith("Thought:")
    assert not any(line.startswith("Observation:") and i == 0
                   for i, line in enumerate(trace))


def test_react_budget_exhaustion_returns_budget_result(R):
    llm = R.FakeLLM([{"thought": "keep going", "tool": "tick", "args": {}}
                     for _ in range(6)])
    res = R.react_loop(llm, {"tick": lambda a: {}}, max_steps=3, task="forever")
    assert (res.answer, res.steps, res.reason) == (None, 3, "budget")
    assert len(llm.prompts) == 3                 # one model call per step
    assert not any(line.startswith("Final:") for line in res.trace)
    assert sum(1 for l in res.trace if l.startswith("Action:")) == 3


def test_react_unknown_tool_becomes_error_observation_and_loop_continues(R):
    llm = R.FakeLLM([
        {"thought": "try magic", "tool": "teleport", "args": {}},
        {"thought": "fine, answer anyway", "final": "recovered"},
    ])
    res = R.react_loop(llm, {}, max_steps=3, task="go")
    assert (res.answer, res.reason) == ("recovered", "final")
    assert "Observation: error: unknown tool teleport" in res.trace


def test_react_tool_crash_becomes_error_observation_never_propagates(R):
    def bomb(args):
        raise ZeroDivisionError("boom")

    llm = R.FakeLLM([
        {"thought": "pull it", "tool": "bomb", "args": {}},
        {"thought": "walk away", "final": "survived"},
    ])
    res = R.react_loop(llm, {"bomb": bomb}, max_steps=3, task="x")
    assert res.answer == "survived"
    assert "Observation: error: boom" in res.trace


def test_react_tools_receive_json_args_and_action_line_is_canonical_json(R):
    seen = {}

    def probe(args):
        seen["type"] = type(args).__name__
        seen["value"] = args
        seen["json_roundtrip"] = json.loads(json.dumps(args)) == args
        return {"echo": True}

    llm = R.FakeLLM([
        {"thought": "probe it", "tool": "probe", "args": {"b": 2, "a": [1, True]}},
        {"thought": "done", "final": "ok"},
    ])
    res = R.react_loop(llm, {"probe": probe}, max_steps=2, task="t")
    assert seen["type"] == "dict"
    assert seen["json_roundtrip"] is True
    assert seen["value"] == {"a": [1, True], "b": 2}
    action_line = next(l for l in res.trace if l.startswith("Action:"))
    assert action_line.startswith('Action: probe({"a": [1, true], "b": 2})')


def test_react_tool_mutation_cannot_corrupt_the_scripted_args(R):
    def greedy(args):
        args["list"].append(999)
        return {}

    llm = R.FakeLLM([
        {"thought": "g", "tool": "greedy", "args": {"list": [1]}},
        {"thought": "d", "final": "ok"},
    ])
    R.react_loop(llm, {"greedy": greedy}, max_steps=2, task="mutate away")
    assert llm.script[0]["args"] == {"list": [1]}


# ------------------------------------------------------------------ Plan-Execute
def test_plan_execute_plans_then_executes_each_step_in_order(R):
    calls = []

    def fetch(args):
        calls.append("fetch")
        return {"rows": 42}

    def clean(args):
        calls.append("clean")
        return "tidy"

    llm = R.FakeLLM([
        {"plan": ["get the rows", "clean them up"]},
        {"tool": "fetch", "args": {"src": "db"}},
        {"tool": "clean", "args": {}},
    ])
    res = R.plan_execute(llm, {"fetch": fetch, "clean": clean}, task="report")
    assert res.plan == ["get the rows", "clean them up"]
    assert res.outputs == ['{"rows": 42}', "tidy"]
    assert res.answer == "tidy"
    assert (res.replans, res.reason) == (0, "completed")
    assert calls == ["fetch", "clean"]           # plan order preserved
    assert len(llm.prompts) == 3                 # 1 planner + 2 executors


def test_plan_execute_executor_sees_prior_outputs(R):
    llm = R.FakeLLM([
        {"plan": ["step one", "step two"]},
        {"tool": "t1", "args": {}},
        {"tool": "t2", "args": {}},
    ])
    R.plan_execute(llm, {"t1": lambda a: {"n": 7}, "t2": lambda a: "end"}, task="p")
    second_executor_prompt = llm.prompts[2][0]["content"]
    assert "step two" in second_executor_prompt          # its own step text
    assert '{"n": 7}' in second_executor_prompt          # prior result visible
    assert "(none yet)" in llm.prompts[1][0]["content"]  # first step has nothing yet


def test_plan_execute_failure_triggers_exactly_one_replan(R):
    def bomb(args):
        raise RuntimeError("relation gone")

    llm = R.FakeLLM([
        {"plan": ["query old table", "never reached"]},
        {"tool": "bomb", "args": {}},                 # fails → replan edge
        {"plan": ["query new table"]},                # the single replan
        {"tool": "safe", "args": {"src": "v2"}},      # revised step succeeds
    ])
    res = R.plan_execute(llm, {"bomb": bomb, "safe": lambda a: {"rows": 1}},
                         task="etl")
    assert (res.replans, res.reason) == (1, "completed")
    assert res.plan == ["query new table"]
    assert res.outputs == ['{"rows": 1}']
    assert len(llm.prompts) == 4                      # planner+exec+replan+exec
    replan_prompt = llm.prompts[2][0]["content"]
    assert "relation gone" in replan_prompt           # failure fed to replanner
    assert len(res.plan) >= 1


def test_plan_execute_no_second_replan_after_repeated_failure(R):
    def bomb(args):
        raise RuntimeError("still broken")

    llm = R.FakeLLM([
        {"plan": ["first try"]},
        {"tool": "bomb", "args": {}},                 # first failure → replan
        {"plan": ["second try"]},
        {"tool": "bomb", "args": {}},                 # second failure → STOP
    ])
    res = R.plan_execute(llm, {"bomb": bomb}, task="doomed")
    assert (res.replans, res.reason) == (1, "failed")
    assert len(llm.prompts) == 4                      # no third planner call — not a loop
    assert all(o.startswith("error:") for o in res.outputs)
    assert res.answer is None


# ------------------------------------------------------------------ Reflexion
def test_reflexion_pass_on_first_trial_skips_reflection(R):
    llm = R.FakeLLM([{"answer": "42"}, {"reflection": "never asked"}])
    res = R.reflexion(llm, lambda a: a == "42", max_trials=3,
                      task="the ultimate question")
    assert (res.success, res.trials, res.reason) == (True, 1, "pass")
    assert res.answer == "42"
    assert res.reflections == []
    assert llm.consumed() == 1                        # no reflection call on success
    assert llm.remaining() == 1
    assert "the ultimate question" in llm.prompts[0][0]["content"]


def test_reflexion_second_trial_prompt_embeds_the_previous_reflection(R):
    reflection_text = "I guessed; look up the disambiguation page first."
    llm = R.FakeLLM([
        {"answer": "v1"},
        {"reflection": reflection_text},
        {"answer": "v2"},
    ])
    verdicts = []

    def task_fn(answer):
        verdicts.append(answer)
        return answer == "v2"

    res = R.reflexion(llm, task_fn, max_trials=3, task="who directed X")
    assert (res.success, res.trials) == (True, 2)
    assert verdicts == ["v1", "v2"]
    assert res.reflections == [reflection_text]
    # trial 1 failed → exactly one reflection request in between
    assert "did not pass" in llm.prompts[1][0]["content"]
    # trial 2's prompt carries the reflection as feedback
    trial2_prompt = llm.prompts[2][0]["content"]
    assert "Feedback from previous attempts" in trial2_prompt
    assert reflection_text in trial2_prompt


def test_reflexion_trial_exhaustion_returns_last_answer_as_best_effort(R):
    llm = R.FakeLLM([
        {"answer": "a1"}, {"reflection": "r1"},
        {"answer": "a2"}, {"reflection": "r2"},
        {"answer": "a3"},
    ])
    res = R.reflexion(llm, lambda a: False, max_trials=3, task="hard task")
    assert res.success is False
    assert (res.answer, res.trials, res.reason) == ("a3", 3, "exhausted")
    assert res.reflections == ["r1", "r2"]
    assert len(llm.prompts) == 5                      # 3 answers + 2 reflections
    final_prompt = llm.prompts[4][0]["content"]
    assert "- r1" in final_prompt and "- r2" in final_prompt


def test_reflexion_success_stops_consuming_the_script(R):
    llm = R.FakeLLM([
        {"answer": "no"},
        {"reflection": "wrong units"},
        {"answer": "yes"},
        {"reflection": "unused"},
        {"answer": "unused"},
    ])
    res = R.reflexion(llm, lambda a: a == "yes", max_trials=5, task="t")
    assert (res.success, res.trials, res.reason) == (True, 2, "pass")
    assert llm.consumed() == 3
    assert llm.remaining() == 2


# ------------------------------------------------------------------ determinism & purity
def test_react_is_deterministic_across_identical_scripts(R):
    def build():
        llm = R.FakeLLM([
            {"thought": "add them", "tool": "add", "args": {"x": 1, "y": 2}},
            {"thought": "sum known", "final": "3"},
        ])
        res = R.react_loop(llm, {"add": lambda a: {"sum": a["x"] + a["y"]}},
                           max_steps=4, task="add")
        return llm.prompts, res

    p1, r1 = build()
    p2, r2 = build()
    assert p1 == p2
    assert r1.trace == r2.trace
    assert (r1.answer, r1.steps, r1.reason) == (r2.answer, r2.steps, r2.reason)


def test_plan_execute_is_deterministic_across_identical_scripts(R):
    def build():
        llm = R.FakeLLM([
            {"plan": ["a", "b"]},
            {"tool": "t1", "args": {"x": 1}},
            {"tool": "t2", "args": {}},
        ])
        res = R.plan_execute(llm, {"t1": lambda a: {"got": a["x"]},
                                   "t2": lambda a: "done"}, task="p")
        return llm.prompts, res

    p1, r1 = build()
    p2, r2 = build()
    assert p1 == p2
    assert (r1.plan, r1.outputs, r1.replans, r1.reason) == \
           (r2.plan, r2.outputs, r2.replans, r2.reason)


def test_caller_tools_dict_survives_all_three_patterns(R):
    tools = {"echo": lambda a: a}
    snapshot = dict(tools)
    R.react_loop(
        R.FakeLLM([{"thought": "t", "tool": "echo", "args": {}},
                   {"thought": "f", "final": "x"}]),
        tools, max_steps=2, task="r")
    R.plan_execute(
        R.FakeLLM([{"plan": ["s"]}, {"tool": "echo", "args": {}}]),
        tools, task="p")
    R.reflexion(R.FakeLLM([{"answer": "a"}]), lambda a: True,
                max_trials=1, task="f")
    assert tools == snapshot
