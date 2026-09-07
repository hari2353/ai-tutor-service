import pytest


# ---------------- LoopBudget ----------------

def test_budget_none_is_unlimited(L):
    b = L.LoopBudget()
    b.consume_turn(10 ** 9)
    b.consume_tokens_in(10 ** 9)
    b.consume_tokens_out(10 ** 9)
    b.consume_wallclock(10 ** 9)
    assert b.exhausted() is None


def test_budget_first_tripped_wins_in_order(L):
    b = L.LoopBudget(turns=5, tokens_in=3)
    b.consume_turn(5)
    b.consume_tokens_in(3)
    assert b.exhausted() == "turns"   # turns checked first


def test_budget_tokens_out(L):
    b = L.LoopBudget(tokens_out=10)
    b.consume_tokens_out(9)
    assert b.exhausted() is None
    b.consume_tokens_out(1)
    assert b.exhausted() == "tokens_out"


# ---------------- compaction strategies ----------------

def tok(s):
    return len(s)  # 1 token per char for tests


MSGS = [{"text": "sys", "pinned": True},
        {"text": "a" * 10},
        {"text": "b" * 10},
        {"text": "c" * 10},
        {"text": "d" * 10}]


def test_truncate_oldest_keeps_pinned_and_head(L):
    out = L.truncate_oldest(tok, MSGS, target_tokens=25, keep_head=1)
    texts = [m["text"] for m in out]
    assert texts[0] == "sys"
    assert "d" * 10 in texts          # newest survives
    assert "a" * 10 not in texts      # oldest dropped
    assert sum(len(t) for t in texts) <= 25


def test_truncate_never_drops_pinned(L):
    msgs = [{"text": "p" * 30, "pinned": True}] + [{"text": "x" * 10}]
    out = L.truncate_oldest(tok, msgs, target_tokens=35, keep_head=1)
    assert out[0]["text"] == "p" * 30


def test_sliding_window_keeps_head_and_tail(L):
    msgs = [{"text": f"m{i}" + "z" * 10} for i in range(8)]
    out = L.sliding_window(tok, msgs, target_tokens=40, n_head=1, n_tail=2)
    assert out[0]["text"].startswith("m0")
    assert out[-1]["text"].startswith("m7")
    assert out[-2]["text"].startswith("m6")
    assert sum(len(m["text"]) for m in out) <= 40


def test_summarize_inserts_summary_message(L):
    out = L.summarize(tok, MSGS, target_tokens=25,
                      summarizer=lambda dropped: f"[SUMMARY of {len(dropped)}]")
    texts = [m["text"] for m in out]
    assert any(t.startswith("[SUMMARY") for t in texts)
    assert texts[0] == "sys"
    assert sum(len(t) for t in texts) <= 25 + len("[SUMMARY of 99]")


def test_compaction_engine_trigger_threshold(L):
    eng = L.CompactionEngine(
        lambda tk, ms, t: L.truncate_oldest(tk, ms, t), tokenizer=tok,
        threshold=0.8)
    msgs = [{"text": "z" * 50}]        # 50 tokens, cap 60 -> 50 > 48 -> compact
    out, compacted = eng.maybe_compact(msgs, cap=60)
    assert compacted is True
    msgs2 = [{"text": "z" * 40}]       # 40 <= 48 -> no compaction
    out2, c2 = eng.maybe_compact(msgs2, cap=60)
    assert c2 is False
    assert out2 == msgs2


def test_compaction_engine_no_op_below_threshold(L):
    eng = L.CompactionEngine(
        lambda tk, ms, t: L.truncate_oldest(tk, ms, t), tokenizer=tok)
    msgs = [{"text": "small", "pinned": False}]
    out, compacted = eng.maybe_compact(msgs, cap=1000)
    assert compacted is False and out == msgs


# ---------------- StopConditions ----------------

def test_stop_goal_met_first(L):
    sc = L.StopConditions(goal_detector=lambda msgs: any("DONE" in m["text"] for m in msgs),
                          budget=L.LoopBudget(turns=0))
    state = {"messages": [{"text": "DONE it"}], "tool_history": [],
             "budget_exhausted": True}
    assert sc.evaluate(state) == "goal_met"


def test_stop_budget_before_stuck(L):
    sc = L.StopConditions(goal_detector=None, budget=L.LoopBudget(turns=0))
    state = {"messages": [], "tool_history": [{"t": "x"}] * 5}
    assert sc.evaluate(state) == "budget_exhausted"


def test_stop_stuck_loop_on_k_repeats(L):
    sc = L.StopConditions(stuck_tool_repeat=3)
    state = {"messages": [],
             "tool_history": [("ls", {}), ("ls", {}), ("ls", {})]}
    assert sc.evaluate(state) == "stuck_loop"


def test_stop_not_stuck_when_args_differ(L):
    sc = L.StopConditions(stuck_tool_repeat=3)
    state = {"messages": [],
             "tool_history": [("ls", {"q": 1}), ("ls", {"q": 2}), ("ls", {"q": 3})]}
    assert sc.evaluate(state) is None


def test_stop_short_history_never_trips(L):
    sc = L.StopConditions(stuck_tool_repeat=3)
    state = {"messages": [], "tool_history": [("ls", {}), ("ls", {})]}
    assert sc.evaluate(state) is None


# ---------------- snapshot / restore ----------------

def test_snapshot_restore_roundtrip(L):
    state = {"messages": [{"text": "hi", "pinned": False}],
             "tool_history": [("ls", {"a": 1})],
             "counters": {"turns": 3}}
    blob = L.snapshot(state)
    state["messages"].append({"text": "mutated-after-snapshot"})
    restored = L.restore(blob)
    assert len(restored["messages"]) == 1
    assert restored["tool_history"] == [("ls", {"a": 1})]
    assert restored["counters"] == {"turns": 3}
    # mutating restored must not touch the blob
    restored["counters"]["turns"] = 99
    assert L.restore(blob)["counters"] == {"turns": 3}


def test_resume_produces_same_trace(L):
    # a scripted two-phase run: uninterrupted vs snapshot-resumed mid-way
    script = ["step one", "step two", "DONE"]

    def run(resume_from=None):
        msgs = []
        counters = {"i": 0}

        class LL:
            def __call__(self, ms, _c=counters, _r=resume_from):
                if _r is not None and _c["i"] == 0:
                    _c["i"] = _r
                r = script[_c["i"]] if _c["i"] < len(script) else "DONE"
                _c["i"] += 1
                return r

        ll = LL()
        msgs.append({"text": ll(msgs)})
        msgs.append({"text": ll(msgs)})
        mid = L.snapshot({"messages": msgs})
        msgs.append({"text": ll(msgs)})
        return msgs, mid

    full, mid = run()
    # resume from mid snapshot with a fresh engine using the same script
    resumed = L.restore(mid)
    counters = {"i": len(resumed["messages"])}
    ll = lambda ms: (script[counters["i"]] if counters["i"] < len(script) else "DONE",
                     counters.__setitem__("i", counters["i"] + 1))[0]
    msgs = list(resumed["messages"])
    msgs.append({"text": ll(msgs)})
    assert [m["text"] for m in msgs] == [m["text"] for m in full]


# ---------------- Metrics ----------------

def test_metrics_report(L):
    m = L.MetricsRecorder()
    m.record_turn(tokens_in=100, tokens_out=50, tool="search")
    m.record_turn(tokens_in=120, tokens_out=30, tool="search")
    m.record_turn(tokens_in=10, tokens_out=5, tool="write")
    r = m.report()
    assert r["turns"] == 3
    assert r["tokens_in"] == 230
    assert r["tokens_out"] == 85
    assert r["tool_histogram"] == {"search": 2, "write": 1}
