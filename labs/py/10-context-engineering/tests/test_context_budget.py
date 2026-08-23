"""Lab 10 tests — pure arithmetic, deterministic, no sleeps."""
import pytest


# ------------------------------------------------------------------ helpers
def mk(kind, text, role="user", **kw):
    d = {"role": role, "text": text, "kind": kind}
    d.update(kw)
    return d


def turn(i, fill=280):
    return mk("turn", f"turn-{i}\n" + "x" * fill,
              role="user" if i % 2 else "assistant")


def big_tool_result(n_chars=2400, tag="RESULT"):
    return mk("tool_result", f"{tag} ok\n" + "R" * n_chars, role="tool")


# ------------------------------------------------------------------ token math
def test_est_tokens_ceil_math(C):
    assert C.est_tokens("") == 0
    assert C.est_tokens("ab") == 1            # ceil(0.5)
    assert C.est_tokens("abcd") == 1          # exact
    assert C.est_tokens("abcde") == 2         # ceil(1.25)
    assert C.est_tokens("x" * 9) == 3


def test_budget_total_and_boundary(C):
    items = [mk("task", "a" * 4), mk("turn", "b" * 8)]   # 1 + 2 tokens
    b = C.ContextBudget(limit=3)
    assert b.total(items) == 3
    assert b.fits(items) is True             # boundary: equal counts as fits
    assert C.ContextBudget(limit=2).fits(items) is False


def test_budget_empty_list_fits_any_nonnegative_limit(C):
    assert C.ContextBudget(limit=0).fits([]) is True


# ------------------------------------------------------------------ truncation
def test_truncate_touches_only_over_cap_tool_results(C):
    long_turn = turn(1, fill=2400)                       # way over cap
    small_tr = mk("tool_result", "ok")
    items = [long_turn, small_tr]
    out = C.truncate_tool_results(items, max_per=500)
    assert out[0] is long_turn, "turn kind must never be truncated"
    assert out[1] is small_tr
    assert out[0]["text"] == long_turn["text"]


def test_truncate_keeps_head_and_marks_exact_dropped_count(C):
    tr = big_tool_result(2400, tag="RESULT")             # 10 + 2400 = 2410 chars -> 603 tok
    out = C.truncate_tool_results([tr], max_per=500)
    got = out[0]
    assert got is not tr                                 # replaced with a stub dict
    assert got["text"].startswith(tr["text"][:1968])     # head kept verbatim
    assert "[truncated 111 tokens]" in got["text"]       # 603 - 492 dropped
    assert got["kind"] == "tool_result" and got["role"] == tr["role"]


def test_truncated_result_stays_within_cap(C):
    tr = big_tool_result(2400)
    got = C.truncate_tool_results([tr], max_per=500)[0]
    assert C.est_tokens(got["text"]) <= 500


def test_truncate_under_cap_result_untouched(C):
    tr = mk("tool_result", "y" * 100)                    # 25 tokens < 500
    out = C.truncate_tool_results([tr])
    assert out[0] is tr


def test_truncate_respects_protect_flag(C):
    tr = mk("tool_result", "Z" * 2400, protect=True)     # over cap but protected
    out = C.truncate_tool_results([tr], max_per=500)
    assert out[0] is tr
    assert "[truncated" not in out[0]["text"]


def test_truncate_is_idempotent_on_marked_results(C):
    tr = big_tool_result(2400)
    once = C.truncate_tool_results([tr], max_per=500)
    twice = C.truncate_tool_results(once, max_per=500)
    assert twice[0] is once[0]
    assert twice[0]["text"] == once[0]["text"]


# ------------------------------------------------------------------ compaction
def _six_turns():
    return [turn(i) for i in range(1, 7)]                # 72 tokens each


def test_compact_folds_old_into_single_recap_and_total_fits(C):
    task = mk("task", "TASK!")
    items = [task] + _six_turns()                        # 2 + 6*72 = 434
    before = C.ContextBudget(10 ** 6).total(items)
    out = C.compact(items, keep_recent=4)
    kinds = [it["kind"] for it in out]
    assert kinds.count("recap") == 1                     # exactly ONE recap
    assert out[0] is task
    after = C.ContextBudget(10 ** 6).total(out)
    assert after < before
    assert C.ContextBudget(after + 20).fits(out)


def test_compact_preserves_task_and_constraint_verbatim_interleaved(C):
    task = mk("task", "TASK: fix login")
    cons = mk("constraint", "NEVER email customers directly")
    items = [task, turn(1), cons, turn(2), turn(3), turn(4), turn(5), turn(6)]
    out = C.compact(items, keep_recent=4)
    assert out[0] is task and task["text"] == "TASK: fix login"
    assert cons in out and out.index(cons) < out.index(out[-1])
    assert cons["text"] == "NEVER email customers directly"


def test_compact_keeps_last_keep_recent_turns_verbatim(C):
    ts = _six_turns()
    out = C.compact(ts, keep_recent=2)
    survivors = [it for it in out if it["kind"] == "turn"]
    assert [it["text"] for it in survivors] == [ts[4]["text"], ts[5]["text"]]
    assert survivors[0] is ts[4] and survivors[1] is ts[5]


def test_compact_noop_when_nothing_evictable(C):
    items = [mk("task", "TASK!")] + _six_turns()[:3]     # 3 evictables <= keep_recent
    out = C.compact(items, keep_recent=4)
    assert out == items
    assert all(a is b for a, b in zip(out, items))
    assert not any(it["kind"] == "recap" for it in out)


def test_default_summarizer_first_line_per_item(C):
    t1 = mk("turn", "alpha line\nmore detail here")
    t2 = mk("turn", "gamma line\nother detail")
    tail = _six_turns()[2:]
    out = C.compact([mk("task", "TASK!"), t1, t2] + tail, keep_recent=4)
    recap = next(it for it in out if it["kind"] == "recap")
    assert recap["text"] == "alpha line\ngamma line"


def test_summarizer_receives_exactly_the_evicted_texts_once(C):
    ts = _six_turns()
    seen = []

    def summ(joined):
        seen.append(joined)
        return "S"

    out = C.compact(ts, keep_recent=4, summarizer=summ)
    assert len(seen) == 1
    assert seen[0] == ts[0]["text"] + "\n" + ts[1]["text"]
    assert any(it["kind"] == "recap" and it["text"] == "S" for it in out)


def test_protect_flag_survives_multiple_compactions(C):
    p = mk("turn", "CORRECTION: use staging account ACCT-88, not prod", protect=True)
    task = mk("task", "TASK!")
    v1 = C.compact([task, p] + _six_turns(), keep_recent=4)
    v2 = C.compact(v1 + [turn(7), turn(8)], keep_recent=4)
    v3 = C.compact(v2 + [turn(9), turn(10)], keep_recent=4)
    for v in (v1, v2, v3):
        assert p in v and p["text"] == v[v.index(p)]["text"]
        assert "ACCT-88" in next(it["text"] for it in v if it is p)


# ------------------------------------------------------------------ enforce
def test_enforce_already_fitting_returns_input_identity_and_order(C):
    items = [mk("task", "TASK!"), turn(1), turn(2)]
    out = C.enforce(items, limit=10 ** 6)
    assert out is items
    assert [id(x) for x in out] == [id(x) for x in items]


def test_enforce_pipeline_truncates_then_compacts_until_fits(C):
    task = mk("task", "TASK: fix login bug")
    cons = mk("constraint", "NEVER email customers")
    items = ([task, cons]
             + [turn(1), turn(2), big_tool_result(tag="RESULT-1"), turn(3), turn(4),
                big_tool_result(tag="RESULT-2"), turn(5), turn(6),
                big_tool_result(tag="RESULT-3"), turn(7), turn(8)])
    out = C.enforce(items, limit=800)
    budget = C.ContextBudget(800)
    assert budget.fits(out)
    recaps = [it for it in out if it["kind"] == "recap"]
    assert len(recaps) == 1
    trs = [it for it in out if it["kind"] == "tool_result"]
    assert len(trs) == 1 and "[truncated" in trs[0]["text"]
    assert task in out and cons in out                   # verbatim survivors
    assert task["text"] == "TASK: fix login bug"
    assert cons["text"] == "NEVER email customers"
    tail_texts = {it["text"] for it in out if it["kind"] == "turn"}
    for i in (6, 7, 8):                                  # recent window intact
        assert turn(i)["text"] in tail_texts
    assert all("turn-1\n" not in t for t in tail_texts)  # old turns folded away


def test_enforce_does_not_mutate_input(C):
    r1 = big_tool_result()
    items = [mk("task", "TASK!")] + [turn(1), turn(2), r1] + [turn(i) for i in range(3, 9)]
    snapshot = [dict(d) for d in items]
    C.enforce(items, limit=400)
    assert len(items) == len(snapshot)
    assert items == snapshot


def test_enforce_raises_unfittable_when_protected_alone_exceed_limit(C):
    huge_task = mk("task", "T" * 2000)                   # 500 tokens
    with pytest.raises(C.Unfittable):
        C.enforce([huge_task, turn(1)], limit=400)


def test_enforce_raises_unfittable_when_tail_alone_cannot_shrink(C):
    items = [mk("task", "TASK!")] + [turn(i) for i in range(1, 5)]  # 2 + 4*72
    with pytest.raises(C.Unfittable):
        C.enforce(items, limit=150)                      # nothing evictable, no tool_results


def test_enforce_repeated_run_is_stable(C):
    items = ([mk("task", "TASK: fix login bug")]
             + [turn(1), turn(2), big_tool_result()] + [turn(i) for i in range(3, 9)])
    once = C.enforce(items, limit=800)
    assert C.ContextBudget(800).fits(once)
    twice = C.enforce(once, limit=800)
    assert twice is once or twice == once
    assert C.ContextBudget(800).total(twice) == C.ContextBudget(800).total(once)
    assert [it["kind"] for it in twice] == [it["kind"] for it in once]
