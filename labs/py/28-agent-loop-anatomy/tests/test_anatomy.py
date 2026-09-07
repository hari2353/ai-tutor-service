"""Lab 28 tests. Pure logic, no sleeps, no I/O — the model is scripted."""
import json

import pytest


# ------------------------------------------------------------- stage 1: resolve
def test_readonly_tools_always_allowed(A):
    tools = ["read", "grep", "glob", "search_files", "list_dir"]
    assert A.resolve_tools("anything", tools, permissions=[]) == tools


def test_write_tools_need_write_permission(A):
    tools = ["write", "edit", "delete"]
    assert A.resolve_tools("go", tools, permissions=[]) == []
    assert A.resolve_tools("go", tools, permissions=["write"]) == tools


def test_bash_and_execute_need_execute_permission(A):
    tools = ["bash", "execute"]
    assert A.resolve_tools("go", tools, permissions=[]) == []
    assert A.resolve_tools("go", tools, permissions=["write"]) == []
    assert A.resolve_tools("go", tools, permissions=["execute"]) == tools


def test_unknown_tools_excluded(A):
    tools = ["read", "launch_missiles", "bash"]
    got = A.resolve_tools("go", tools, permissions=[])
    assert "launch_missiles" not in got
    assert got == ["read"]


def test_unknown_tools_excluded_even_with_write(A):
    """A permission can never admit a tool the harness does not know."""
    tools = ["write", "time_travel"]
    assert A.resolve_tools("go", tools, permissions=["write"]) == ["write"]


def test_resolution_mixed_and_order_preserved(A):
    tools = ["edit", "read_file", "bash", "totally_unknown"]
    assert A.resolve_tools("go", tools, permissions=["write"]) == \
        ["edit", "read_file"]
    assert A.resolve_tools("go", tools,
                           permissions=["write", "execute"]) == \
        ["edit", "read_file", "bash"]


# ------------------------------------------------------------- stage 2: context
def test_context_ordering_system_history_user(A):
    history = ["h1", "h2", "h3"]
    ctx = A.build_context("hi", "SYS", history, max_history=10)
    assert ctx == ["SYS", "h1", "h2", "h3", "hi"]
    assert ctx[0] == "SYS"                     # system first
    assert ctx[-1] == "hi"                     # user last


def test_context_trims_to_last_max_history(A):
    history = ["h1", "h2", "h3", "h4", "h5"]
    ctx = A.build_context("hi", "SYS", history, max_history=2)
    assert ctx == ["SYS", "h4", "h5", "hi"]    # only the LAST 2 survive
    assert ctx[0] == "SYS" and ctx[-1] == "hi"


def test_context_trims_with_zero_max_history(A):
    ctx = A.build_context("hi", "SYS", ["h1", "h2"], max_history=0)
    assert ctx == ["SYS", "hi"]


# ------------------------------------------------------------- stage 3: parse
def test_parse_tool_use_valid(A):
    got = A.parse_model_output('TOOL: read {"path": "a.py"}')
    assert got == {"type": "tool_use", "tool": "read",
                   "args": {"path": "a.py"}}


def test_parse_plain_text(A):
    got = A.parse_model_output("The bug is in line 4.")
    assert got == {"type": "text", "text": "The bug is in line 4."}


def test_parse_invalid_json(A):
    got = A.parse_model_output("TOOL: read {path: a.py}")
    assert got == {"type": "invalid"}


def test_parse_empty_is_invalid(A):
    assert A.parse_model_output("") == {"type": "invalid"}
    assert A.parse_model_output("   ") == {"type": "invalid"}


# --------------------------------------------------- stage 4: execute & observe
def test_execute_returns_observation(A):
    fns = {"read": lambda path: f"content of {path}"}
    call = {"tool": "read", "args": {"path": "a.py"}}
    assert A.execute_and_observe(call, fns, {"max_output_chars": 100}) == \
        "content of a.py"


def test_execute_truncates_with_char_count(A):
    fns = {"read": lambda path: "x" * 250}
    call = {"tool": "read", "args": {"path": "big.log"}}
    obs = A.execute_and_observe(call, fns, {"max_output_chars": 100})
    assert obs.startswith("x" * 100)
    assert obs.endswith(" [truncated 150 chars]")   # 250-100 dropped
    assert len(obs) == 100 + len(" [truncated 150 chars]")


def test_execute_truncation_not_applied_at_exact_limit(A):
    fns = {"read": lambda path: "x" * 100}
    call = {"tool": "read", "args": {"path": "f"}}
    obs = A.execute_and_observe(call, fns, {"max_output_chars": 100})
    assert obs == "x" * 100                        # no marker when it fits


def test_execute_tool_raising_returns_error_observation(A):
    def boom(**kwargs):
        raise ValueError("disk on fire")
    call = {"tool": "bash", "args": {"cmd": "oops"}}
    obs = A.execute_and_observe(call, {"bash": boom},
                                {"max_output_chars": 1000})
    assert obs.startswith("error:")
    assert "ValueError" in obs and "disk on fire" in obs


def test_execute_unknown_tool(A):
    call = {"tool": "time_travel", "args": {}}
    obs = A.execute_and_observe(call, {}, {"max_output_chars": 100})
    assert obs == "error: unknown tool"


# ------------------------------------------------------------- stage 5: the turn
def _scripted_model(outputs):
    """A fake model that plays back `outputs` in order and records contexts."""
    seen = []
    state = {"i": 0}

    def model(context):
        seen.append(list(context))
        out = outputs[state["i"]]
        state["i"] += 1
        return out
    model.contexts = seen
    return model


def test_turn_two_tools_then_text(A):
    outputs = [
        'TOOL: read {"path": "a.py"}',
        'TOOL: grep {"pattern": "def"}',
        "Done — the answer is 42.",
    ]
    calls = []

    def read(**kwargs):
        calls.append(("read", kwargs))
        return "FILE CONTENTS"

    def grep(**kwargs):
        calls.append(("grep", kwargs))
        return "no matches"

    model = _scripted_model(outputs)
    result = A.turn_loop(
        "find the bug", model,
        {"read": read, "grep": grep},
        {"system_prompt": "SYS", "history": [], "max_history": 10,
         "max_iterations": 10, "limits": {"max_output_chars": 1000}},
    )
    assert result["final_text"] == "Done — the answer is 42."
    assert result["iterations"] == 3
    assert calls == [("read", {"path": "a.py"}),
                     ("grep", {"pattern": "def"})]
    # history: user msg, both observations, final text
    assert result["history"][0] == "find the bug"
    assert "FILE CONTENTS" in result["history"]
    assert "no matches" in result["history"]
    assert result["history"][-1] == "Done — the answer is 42."
    assert len(result["history"]) == 4


def test_turn_immediate_text(A):
    model = _scripted_model(["hello!"])
    result = A.turn_loop("hi", model, {},
                         {"system_prompt": "SYS", "history": [],
                          "max_history": 5, "max_iterations": 5})
    assert result == {"final_text": "hello!", "iterations": 1,
                      "history": ["hi", "hello!"]}


def test_turn_max_iterations_caps(A):
    outputs = ['TOOL: read {"n": %d}' % i for i in range(50)]
    model = _scripted_model(outputs)
    result = A.turn_loop(
        "loop forever", model, {"read": lambda **kw: "ok"},
        {"system_prompt": "SYS", "history": [], "max_history": 10,
         "max_iterations": 4, "limits": {"max_output_chars": 100}},
    )
    assert result["iterations"] == 4
    assert result["final_text"] == ""          # never reached a text answer
    assert len(model.contexts) == 4             # model called exactly 4x


def test_turn_error_observation_does_not_crash(A):
    def boom(**kwargs):
        raise RuntimeError("tool exploded")
    outputs = ['TOOL: bash {"cmd": "ls"}', "recovered."]
    model = _scripted_model(outputs)
    result = A.turn_loop(
        "run it", model, {"bash": boom},
        {"system_prompt": "SYS", "history": [], "max_history": 5,
         "max_iterations": 5, "limits": {"max_output_chars": 500}},
    )
    assert result["final_text"] == "recovered."    # loop continued past error
    assert any(h.startswith("error:") for h in result["history"])


def test_turn_model_sees_growing_history(A):
    """Each iteration's context must contain the observations so far —
    that is the whole point of an agent loop."""
    outputs = ['TOOL: read {"path": "a"}', 'TOOL: read {"path": "b"}',
               "done"]
    model = _scripted_model(outputs)
    A.turn_loop("go", model, {"read": lambda **kw: "OBS"},
                {"system_prompt": "SYS", "history": [], "max_history": 10,
                 "max_iterations": 10, "limits": {"max_output_chars": 100}})
    ctx2 = model.contexts[1]
    ctx3 = model.contexts[2]
    # ordering inside iteration 2: SYS, the first observation, user msg last
    assert ctx2 == ["SYS", "OBS", "go"]
    # by iteration 3 both observations are in context, user msg still last
    assert ctx3 == ["SYS", "OBS", "OBS", "go"]


def test_turn_invalid_output_survives_then_finishes(A):
    outputs = ["TOOL: read {broken json", "all good."]
    model = _scripted_model(outputs)
    result = A.turn_loop("go", model, {"read": lambda **kw: "ok"},
                         {"system_prompt": "SYS", "history": [],
                          "max_history": 5, "max_iterations": 5})
    assert result["final_text"] == "all good."
    assert result["iterations"] == 2
