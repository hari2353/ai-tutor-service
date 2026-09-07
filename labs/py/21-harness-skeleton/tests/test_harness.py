import pytest


# ---------------- ContextWindow ----------------

def test_context_compaction_preserves_pinned(H):
    ctx = H.ContextWindow(cap=20)  # ~5 short messages
    ctx.add("SYSTEM: you are an agent", pinned=True)
    for i in range(10):
        ctx.add(f"user message number {i} " + "x" * 10)
    texts = [t for t, _ in ctx.messages()]
    assert any(t.startswith("SYSTEM") for t in texts)
    assert ctx.tokens() <= 20 + 12  # cap + one summary message headroom


def test_context_compaction_injects_summary(H):
    ctx = H.ContextWindow(cap=24,
                          summarizer=lambda dropped: f"[SUMMARY({len(dropped)})]")
    ctx.add("SYS", pinned=True)
    for i in range(12):
        ctx.add(f"m{i} " + "y" * 8)
    texts = [t for t, _ in ctx.messages()]
    assert any("[SUMMARY(" in t for t in texts)


def test_context_under_cap_never_compacts(H):
    ctx = H.ContextWindow(cap=1000)
    for i in range(5):
        ctx.add(f"msg {i}")
    assert len(ctx.messages()) == 5
    assert "[SUMMARY" not in " ".join(t for t, _ in ctx.messages())


# ---------------- ToolRouter ----------------

def test_router_unknown_tool(H):
    r = H.ToolRouter()
    with pytest.raises(H.ToolError) as ei:
        r.call("nope", {})
    assert ei.value.retryable is False


def test_router_schema_validation(H):
    r = H.ToolRouter()
    r.register("get", lambda q: q.upper(), {"required": ["q"]}, "read_only")
    with pytest.raises(H.ToolError):
        r.call("get", {})
    assert r.call("get", {"q": "hi"}) == "HI"


def test_router_destructive_requires_approval(H):
    r = H.ToolRouter()
    r.register("rm", lambda path: "deleted", {"required": ["path"]}, "destructive")
    with pytest.raises(H.PermissionDenied):
        r.call("rm", {"path": "/tmp/x"})
    assert r.call("rm", {"path": "/tmp/x"}, approver=lambda n, a: True) == "deleted"


def test_router_wraps_exceptions_with_retryable_flag(H):
    class Transient(Exception):
        retryable = True

    def flaky(**kw):
        raise Transient("boom")

    r = H.ToolRouter()
    r.register("flaky", flaky, {"required": []}, "read_only")
    with pytest.raises(H.ToolError) as ei:
        r.call("flaky", {})
    assert ei.value.retryable is True


def test_router_read_only_needs_no_approval(H):
    r = H.ToolRouter()
    r.register("ls", lambda: "files", {"required": []}, "read_only")
    assert r.call("ls", {}) == "files"


# ---------------- LoopEngine ----------------

def make_env(H, script, cfg=None, cap=10_000):
    """script: list of replies the fake LLM gives in order."""
    calls = {"i": 0}

    def llm(msgs):
        i = calls["i"]
        calls["i"] += 1
        return script[min(i, len(script) - 1)]

    router = H.ToolRouter()
    router.register("ls", lambda: "ok", {"required": []}, "read_only")
    ctx = H.ContextWindow(cap=cap)
    base = dict(max_turns=6, token_budget=10 ** 9, wallclock_budget=10 ** 9,
                max_tool_errors=3)
    base.update(cfg or {})
    cfg = base
    clock = H.FakeClock(0)
    eng = H.LoopEngine(llm, router, ctx, cfg, clock)
    return eng, clock, calls


def test_loop_tool_call_roundtrip(H):
    eng, clock, _ = make_env(H, ['CALL: ls {}', "STOP"])
    res = eng.run()
    assert res["stopped_by"] == "explicit_stop"
    assert res["turns"] == 2
    texts = " ".join(t for t, _ in eng.ctx.messages())
    assert "tool-result: ok" in texts


def test_loop_max_turns(H):
    eng, clock, _ = make_env(H, ['CALL: ls {}'] * 100)
    res = eng.run()
    assert res["stopped_by"] == "max_turns"
    assert res["turns"] == 6


def test_loop_wallclock_budget(H):
    router = H.ToolRouter()
    ctx = H.ContextWindow(cap=10_000)
    clock = H.FakeClock(0)

    # advance the clock 100 units per LLM call; keep calling tools so loop continues
    class LLM:
        def __call__(self, msgs, _c=clock):
            _c.advance(100)
            return "CALL: ls {}"

    eng = H.LoopEngine(LLM(), router, ctx,
                       dict(max_turns=99, token_budget=10 ** 9,
                            wallclock_budget=250, max_tool_errors=99), clock)
    res = eng.run()
    assert res["stopped_by"] == "wallclock_budget"


def test_loop_consecutive_tool_errors_trip(H):
    eng, clock, _ = make_env(H, ['CALL: nope {}'] * 50,
                             cfg=dict(max_tool_errors=3, max_turns=99))
    res = eng.run()
    assert res["stopped_by"] == "max_tool_errors"


def test_loop_kill_switch_between_turns(H):
    class LLM:
        def __init__(self, eng_holder):
            self.n = 0

        def __call__(self, msgs):
            self.n += 1
            if self.n == 2:
                eng.kill_switch = True
            return "CALL: ls {}"

    router = H.ToolRouter()
    router.register("ls", lambda: "ok", {"required": []}, "read_only")
    ctx = H.ContextWindow(cap=10_000)
    eng = H.LoopEngine(None, router, ctx,
                       dict(max_turns=99, token_budget=10 ** 9,
                            wallclock_budget=10 ** 9, max_tool_errors=99),
                       H.FakeClock(0))
    # bind after engine exists
    llm = LLM.__new__(LLM)
    llm.n = 0
    llm.__call__ = lambda msgs: (setattr(llm, 'n', llm.n + 1),
                                  eng.__setattr__('kill_switch', llm.n >= 2),
                                  "CALL: ls {}")[2]
    eng.llm = llm
    res = eng.run()
    assert res["stopped_by"] == "kill_switch"
    assert res["turns"] <= 3  # stopped between turns shortly after flip


def test_loop_plain_reply_ends(H):
    eng, clock, _ = make_env(H, ["the answer is 42"])
    res = eng.run()
    assert res["stopped_by"] == "done"
    assert res["turns"] == 1


def test_event_log_records_decisions(H):
    eng, clock, _ = make_env(H, ['CALL: ls {}', "STOP"])
    eng.run()
    kinds = {k for _, k, _ in eng.log.events()}
    assert "reply" in kinds
    assert "tool" in kinds
    assert "stop" in kinds
    stops = eng.log.events("stop")
    assert stops[-1][2]["reason"] == "explicit_stop"
