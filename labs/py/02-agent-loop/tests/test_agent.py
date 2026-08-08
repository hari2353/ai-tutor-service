"""Lab 02 tests. Fully scripted, fully deterministic, no network, no sleeps."""
import pytest


# ------------------------------------------------------------------ step 1: bare loop
def test_bare_loop_returns_final_answer(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="42")])
    loop = A.AgentLoop(model=model, tools={}, clock=A.FakeClock())
    result = loop.run("what is the answer?")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER
    assert result.final_answer == "42"


def test_bare_loop_message_passing_records_task_and_answer(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="done")])
    loop = A.AgentLoop(model=model, tools={}, clock=A.FakeClock())
    result = loop.run("do the thing")
    contents = [m.content for m in result.messages]
    assert "do the thing" in contents
    assert "done" in contents
    assert result.messages[0].role == "system"
    assert result.messages[1].role == "user"


def test_bare_loop_steps_used_counts_model_calls(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="ok")])
    loop = A.AgentLoop(model=model, tools={}, clock=A.FakeClock())
    result = loop.run("task")
    assert result.steps_used == 1


# ------------------------------------------------------------------ step 2: tool dispatch
def _echo_tool(A, calls=None):
    def handler(text):
        if calls is not None:
            calls.append(text)
        return text.upper()
    return A.ToolSpec(name="echo", params={"text": str}, required={"text"}, handler=handler)


def test_dispatch_tool_success(A):
    tools = {"echo": _echo_tool(A)}
    obs = A.dispatch_tool(tools, A.ToolCall(name="echo", args={"text": "hi"}))
    assert obs == "OK: HI"


def test_dispatch_tool_unknown_tool_returns_error_not_raise(A):
    obs = A.dispatch_tool({}, A.ToolCall(name="ghost", args={}))
    assert obs.startswith("ERROR")
    assert "ghost" in obs


def test_dispatch_tool_missing_required_arg_returns_error_not_raise(A):
    tools = {"echo": _echo_tool(A)}
    obs = A.dispatch_tool(tools, A.ToolCall(name="echo", args={}))
    assert obs.startswith("ERROR")
    assert "text" in obs


def test_dispatch_tool_wrong_type_returns_error_not_raise(A):
    tools = {"echo": _echo_tool(A)}
    obs = A.dispatch_tool(tools, A.ToolCall(name="echo", args={"text": 5}))
    assert obs.startswith("ERROR")


def test_dispatch_tool_unexpected_arg_returns_error_not_raise(A):
    tools = {"echo": _echo_tool(A)}
    obs = A.dispatch_tool(tools, A.ToolCall(name="echo", args={"text": "hi", "loud": True}))
    assert obs.startswith("ERROR")


def test_dispatch_tool_handler_exception_becomes_observation_not_raise(A):
    def boom(text):
        raise ValueError("kaboom")
    tools = {"boom": A.ToolSpec(name="boom", params={"text": str}, required={"text"}, handler=boom)}
    obs = A.dispatch_tool(tools, A.ToolCall(name="boom", args={"text": "x"}))
    assert obs.startswith("ERROR")
    assert "kaboom" in obs


def test_loop_dispatches_tool_and_continues_to_final(A):
    calls = []
    tools = {"echo": _echo_tool(A, calls)}
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=A.ToolCall(name="echo", args={"text": "hi"})),
        A.ModelResponse(kind="final", content="I echoed hi"),
    ])
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("echo hi")
    assert calls == ["hi"]
    assert result.stop_reason is A.StopReason.FINAL_ANSWER
    assert any("OK: HI" in m.content for m in result.messages)


def test_loop_survives_failing_tool_and_reaches_final(A):
    """A tool that raises must not crash the loop -- it becomes an observation
    the model can read on its next turn."""
    def boom(text):
        raise RuntimeError("downstream is down")
    tools = {"boom": A.ToolSpec(name="boom", params={"text": str}, required={"text"}, handler=boom)}
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=A.ToolCall(name="boom", args={"text": "x"})),
        A.ModelResponse(kind="final", content="gave up gracefully"),
    ])
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("try the flaky tool")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER
    assert any("ERROR" in m.content and "downstream is down" in m.content for m in result.messages)


# ------------------------------------------------------------------ step 3: stop conditions
def test_stop_reason_max_steps(A):
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=A.ToolCall(name="noop", args={}))
        for _ in range(10)
    ])
    tools = {"noop": A.ToolSpec(name="noop", params={}, required=set(), handler=lambda: "ok")}
    loop = A.AgentLoop(model=model, tools=tools, budget=A.Budget(max_steps=2), clock=A.FakeClock())
    result = loop.run("loop forever")
    assert result.stop_reason is A.StopReason.MAX_STEPS
    assert result.steps_used == 2


def test_stop_reason_max_tokens(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="x", tokens=999)])
    loop = A.AgentLoop(model=model, tools={}, budget=A.Budget(max_tokens=100), clock=A.FakeClock())
    result = loop.run("task")
    assert result.stop_reason is A.StopReason.MAX_TOKENS


def test_stop_reason_max_cost(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="x", cost=50.0)])
    loop = A.AgentLoop(model=model, tools={}, budget=A.Budget(max_cost=1.0), clock=A.FakeClock())
    result = loop.run("task")
    assert result.stop_reason is A.StopReason.MAX_COST


def test_stop_reason_deadline_on_fake_clock(A):
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=A.ToolCall(name="noop", args={}), think_seconds=10.0),
        A.ModelResponse(kind="final", content="too late"),
    ])
    tools = {"noop": A.ToolSpec(name="noop", params={}, required=set(), handler=lambda: "ok")}
    loop = A.AgentLoop(model=model, tools=tools, budget=A.Budget(deadline_seconds=5.0), clock=A.FakeClock())
    result = loop.run("task")
    assert result.stop_reason is A.StopReason.DEADLINE
    assert result.steps_used == 1


def test_no_deadline_means_no_deadline_stop(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="ok", think_seconds=1e9)])
    loop = A.AgentLoop(model=model, tools={}, budget=A.Budget(deadline_seconds=None), clock=A.FakeClock())
    result = loop.run("task")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER


def test_stop_reason_no_progress_hard_stop(A):
    call = A.ToolCall(name="search", args={"q": "cats", "limit": 5})
    model = A.FakeModel([A.ModelResponse(kind="tool_call", tool_call=call) for _ in range(4)])
    tools = {"search": A.ToolSpec(name="search", params={"q": str, "limit": int},
                                   required={"q"}, handler=lambda q, limit=10: "no results")}
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("find cats")
    assert result.stop_reason is A.StopReason.NO_PROGRESS
    assert result.no_progress_warnings == 1


def test_no_progress_argument_order_does_not_matter(A):
    """hash_call must treat {'a':1,'b':2} the same as {'b':2,'a':1}."""
    calls = [
        A.ToolCall(name="search", args={"q": "cats", "limit": 5}),
        A.ToolCall(name="search", args={"limit": 5, "q": "cats"}),
        A.ToolCall(name="search", args={"q": "cats", "limit": 5}),
        A.ToolCall(name="search", args={"q": "cats", "limit": 5}),
    ]
    model = A.FakeModel([A.ModelResponse(kind="tool_call", tool_call=c) for c in calls])
    tools = {"search": A.ToolSpec(name="search", params={"q": str, "limit": int},
                                   required={"q"}, handler=lambda q, limit=10: "no results")}
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("find cats")
    assert result.stop_reason is A.StopReason.NO_PROGRESS


def test_no_progress_intervention_lets_model_recover(A):
    """After 3 identical calls the loop intervenes (does not dispatch a 4th
    identical call, injects a nudge) but keeps going -- if the model then
    does something different, the run completes normally."""
    same = A.ToolCall(name="search", args={"q": "cats"})
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=same),
        A.ModelResponse(kind="tool_call", tool_call=same),
        A.ModelResponse(kind="tool_call", tool_call=same),
        A.ModelResponse(kind="final", content="giving up on cats, here is a fallback answer"),
    ])
    tools = {"search": A.ToolSpec(name="search", params={"q": str}, required={"q"},
                                   handler=lambda q: "no results")}
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("find cats")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER
    assert result.no_progress_warnings == 1
    assert any("repeated identical call" in m.content.lower()
               or "same arguments" in m.content.lower() for m in result.messages)
    # the 3rd identical call must NOT have been dispatched to the tool
    assert sum(1 for m in result.messages if m.content == "OK: no results") == 2


def test_no_progress_different_args_do_not_count_as_repeats(A):
    calls = [A.ToolCall(name="search", args={"q": f"query-{i}"}) for i in range(4)]
    model = A.FakeModel([A.ModelResponse(kind="tool_call", tool_call=c) for c in calls]
                         + [A.ModelResponse(kind="final", content="found it")])
    tools = {"search": A.ToolSpec(name="search", params={"q": str}, required={"q"},
                                   handler=lambda q: "ok")}
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("find things")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER
    assert result.no_progress_warnings == 0


def test_hash_call_is_order_independent_and_stable(A):
    h1 = A.hash_call("search", {"q": "cats", "limit": 5})
    h2 = A.hash_call("search", {"limit": 5, "q": "cats"})
    h3 = A.hash_call("search", {"q": "dogs", "limit": 5})
    assert h1 == h2
    assert h1 != h3


# ------------------------------------------------------------------ step 4: budgets on fake clock
def test_fake_clock_advances_without_blocking(A):
    c = A.FakeClock(t=0.0)
    c.advance(3.0)
    assert c.now() == 3.0
    c.advance(2.0)
    assert c.now() == 5.0


def test_budget_defaults_are_generous_enough_for_normal_runs(A):
    model = A.FakeModel([A.ModelResponse(kind="final", content="ok")])
    loop = A.AgentLoop(model=model, tools={}, clock=A.FakeClock())
    result = loop.run("simple task")
    assert result.stop_reason is A.StopReason.FINAL_ANSWER


def test_tokens_and_cost_accumulate_across_steps(A):
    model = A.FakeModel([
        A.ModelResponse(kind="tool_call", tool_call=A.ToolCall(name="noop", args={}),
                         tokens=10, cost=0.1),
        A.ModelResponse(kind="final", content="ok", tokens=5, cost=0.05),
    ])
    tools = {"noop": A.ToolSpec(name="noop", params={}, required=set(), handler=lambda: "ok")}
    loop = A.AgentLoop(model=model, tools=tools, clock=A.FakeClock())
    result = loop.run("task")
    assert result.tokens_used == 15
    assert result.cost_used == pytest.approx(0.15)


# ------------------------------------------------------------------ step 5: context compaction
def _msg(A, role, content, obligation=False):
    return A.Message(role=role, content=content, obligation=obligation)


def test_compact_is_noop_when_short(A):
    messages = [
        _msg(A, "system", "sys"), _msg(A, "user", "task"),
        _msg(A, "assistant", "a1"), _msg(A, "tool", "t1"),
    ]
    out = A.compact_context(messages, keep_last=4)
    assert [m.content for m in out] == [m.content for m in messages]


def test_compact_preserves_original_task_verbatim(A):
    messages = [_msg(A, "system", "sys prompt"), _msg(A, "user", "book me a flight to Denver")]
    messages += [_msg(A, "assistant", f"step {i}") for i in range(20)]
    messages += [_msg(A, "tool", f"obs {i}") for i in range(20)]
    out = A.compact_context(messages, keep_last=4)
    assert any(m.content == "book me a flight to Denver" for m in out)


def test_compact_preserves_open_obligations_verbatim(A):
    messages = [_msg(A, "system", "sys"), _msg(A, "user", "task")]
    messages.append(_msg(A, "tool", "MUST confirm the refund amount before closing the ticket",
                          obligation=True))
    messages += [_msg(A, "assistant", f"noise {i}") for i in range(30)]
    out = A.compact_context(messages, keep_last=4)
    assert any(m.content == "MUST confirm the refund amount before closing the ticket" for m in out)


def test_compact_actually_shrinks_long_histories(A):
    messages = [_msg(A, "system", "sys"), _msg(A, "user", "task")]
    messages += [_msg(A, "assistant", f"noise {i}") for i in range(50)]
    out = A.compact_context(messages, keep_last=4)
    assert len(out) < len(messages)


def test_compact_keeps_last_n_messages_verbatim(A):
    messages = [_msg(A, "system", "sys"), _msg(A, "user", "task")]
    messages += [_msg(A, "assistant", f"noise {i}") for i in range(20)]
    tail = [_msg(A, "assistant", "recent-1"), _msg(A, "tool", "recent-2")]
    messages += tail
    out = A.compact_context(messages, keep_last=2)
    assert [m.content for m in out[-2:]] == ["recent-1", "recent-2"]


def test_compact_multiple_obligations_all_survive(A):
    messages = [_msg(A, "system", "sys"), _msg(A, "user", "task")]
    messages.append(_msg(A, "tool", "OBLIGATION: confirm address", obligation=True))
    messages += [_msg(A, "assistant", f"noise {i}") for i in range(10)]
    messages.append(_msg(A, "tool", "OBLIGATION: confirm payment method", obligation=True))
    messages += [_msg(A, "assistant", f"more noise {i}") for i in range(10)]
    out = A.compact_context(messages, keep_last=3)
    contents = [m.content for m in out]
    assert "OBLIGATION: confirm address" in contents
    assert "OBLIGATION: confirm payment method" in contents
