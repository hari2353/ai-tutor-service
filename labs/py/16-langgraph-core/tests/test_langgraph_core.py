"""Lab 16 tests. No I/O, no threads — a deterministic mini-Pregel."""
import pytest


# ------------------------------------------------------------------ helpers
def append_reducer(cur, upd):
    return (cur or []) + [upd]


def concat_reducer(cur, upd):
    return (cur or []) + list(upd)


# ------------------------------------------------------- compile() validation
def test_no_entry_raises(R):
    g = R.StateGraph(dict)
    g.add_node("a", lambda s: None)
    with pytest.raises(R.GraphError, match="entry"):
        g.compile()


def test_unknown_edge_target_raises(R):
    g = R.StateGraph(dict)
    g.add_node("a", lambda s: None)
    g.set_entry("a")
    g.add_edge("a", "ghost")
    with pytest.raises(R.GraphError, match="unknown edge target 'ghost'"):
        g.compile()


def test_unreachable_node_raises(R):
    g = R.StateGraph(dict)
    for n in ("a", "b", "orphan"):
        g.add_node(n, lambda s: None)
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", R.END)
    with pytest.raises(R.GraphError, match="unreachable"):
        g.compile()


def test_static_cycle_raises(R):
    g = R.StateGraph(dict)
    for n in ("a", "b", "c"):
        g.add_node(n, lambda s: None)
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "b")            # pure-static back edge — cannot terminate
    with pytest.raises(R.GraphError, match="static cycle"):
        g.compile()


def test_loop_with_conditional_edge_is_allowed(R):
    """model -> tools static + model -?-> tools conditional = legal cycle."""
    g = R.StateGraph(dict)
    g.add_node("model", lambda s: {"count": s.get("count", 0) + 1})
    g.add_node("tools", lambda s: None)
    g.set_entry("model")
    g.add_conditional_edges(
        "model", lambda s: "tools" if s["count"] < 2 else R.END)
    g.add_edge("tools", "model")     # the only STATIC edge on the cycle
    compiled = g.compile()           # must NOT raise
    out = compiled.invoke({"count": 0})
    assert out["count"] == 2


def test_mixing_static_and_conditional_routing_raises(R):
    g = R.StateGraph(dict)
    for n in ("a", "b"):
        g.add_node(n, lambda s: None)
    g.set_entry("a")
    g.add_conditional_edges("a", lambda s: "b")
    g.add_edge("a", "b")             # both mechanisms from one node
    with pytest.raises(R.GraphError, match="mixes"):
        g.compile()


# ---------------------------------------------------------------- linear flow
def test_linear_flow_order_and_merge(R):
    g = R.StateGraph({"topic": str})
    g.add_node("plan", lambda s: {"query": f"q:{s['topic']}"})
    g.add_node("search", lambda s: {"hits": [s["query"] + ":hit"]})
    g.add_node("answer", lambda s: {"out": s["hits"][0].upper()})
    g.set_entry("plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "answer")
    g.add_edge("answer", R.END)
    graph = g.compile()

    out = graph.invoke({"topic": "mvcc"})
    assert out == {"topic": "mvcc", "query": "q:mvcc",
                   "hits": ["q:mvcc:hit"], "out": "Q:MVCC:HIT"}
    assert graph.execution_log == ["plan", "search", "answer"]


def test_end_terminates_run(R):
    g = R.StateGraph(dict)
    g.add_node("only", lambda s: {"done": True})
    g.set_entry("only")
    g.add_conditional_edges("only", lambda s: R.END)
    graph = g.compile()
    out = graph.invoke({"start": True})
    assert out == {"start": True, "done": True}
    assert graph.execution_log == ["only"]           # END scheduled nothing


def test_dead_end_halts_without_error(R):
    g = R.StateGraph(dict)
    g.add_node("a", lambda s: {"x": 1})
    g.set_entry("a")                 # no outgoing edge at all
    graph = g.compile()
    assert graph.invoke({}) == {"x": 1}
    assert graph.execution_log == ["a"]


# ------------------------------------------------------------ conditional edges
def test_conditional_taken_path_only(R):
    g = R.StateGraph(dict)
    g.add_node("route", lambda s: None)
    g.add_node("high", lambda s: {"path": "high"})
    g.add_node("low", lambda s: {"path": "low"})
    g.set_entry("route")
    g.add_conditional_edges("route", lambda s: "high" if s["amount"] > 100 else "low")
    g.add_edge("high", R.END)
    g.add_edge("low", R.END)
    graph = g.compile()
    assert graph.invoke({"amount": 500})["path"] == "high"
    assert graph.execution_log == ["route", "high"]
    assert graph.invoke({"amount": 5})["path"] == "low"
    assert graph.execution_log == ["route", "low"]


def test_conditional_not_taken_branch_never_runs(R):
    ran = {"low": 0}

    def low(state):
        ran["low"] += 1
        return {}

    g = R.StateGraph(dict)
    g.add_node("route", lambda s: None)
    g.add_node("high", lambda s: {"p": 1})
    g.add_node("low", low)
    g.set_entry("route")
    g.add_conditional_edges("route", lambda s: "high")
    g.add_edge("high", R.END)
    g.add_edge("low", R.END)
    g.compile().invoke({"amount": 1})
    assert ran["low"] == 0           # not-taken branch never executes


def test_router_returning_list_runs_both_then_joins_once(R):
    seen_by = {}

    def z(state):
        seen_by.setdefault("n", 0)
        seen_by["n"] += 1
        return {"z": True}

    g = R.StateGraph(dict)
    g.add_node("r", lambda s: None)
    g.add_node("x", lambda s: {"who": "x"})
    g.add_node("y", lambda s: {"who": "y"})
    g.add_node("z", z)
    g.set_entry("r")
    g.add_conditional_edges("r", lambda s: ["x", "y"])   # different nodes, SAME state
    g.add_edge("x", "z")
    g.add_edge("y", "z")
    graph = g.compile()
    out = graph.invoke({})
    assert graph.execution_log == ["r", "x", "y", "z"]   # join deduped to one run
    assert seen_by["n"] == 1
    assert out["who"] in ("x", "y")                      # last write wins (no reducer)


# ------------------------------------------------------- reducers vs overwrite
def test_default_reducer_is_overwrite_sequential(R):
    """The silent bug: consecutive writes to an unreduced key, second wins,
    first is gone — and NOTHING complains."""
    g = R.StateGraph(dict)
    g.add_node("w1", lambda s: {"verdict": "first"})
    g.add_node("w2", lambda s: {"verdict": "second"})
    g.set_entry("w1")
    g.add_edge("w1", "w2")
    g.add_edge("w2", R.END)
    out = g.compile().invoke({})
    assert out["verdict"] == "second"


def test_declared_reducer_accumulates_sequential(R):
    g = R.StateGraph(dict)
    g.add_reducer("trail", append_reducer)
    g.add_node("a", lambda s: {"trail": "a"})
    g.add_node("b", lambda s: {"trail": "b"})
    g.add_node("c", lambda s: {"trail": "c"})
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", R.END)
    assert g.compile().invoke({})["trail"] == ["a", "b", "c"]


def test_fanout_overwrite_vs_reducer_distinction(R):
    """THE distinction. Same two writers, same tick: the reduced key folds BOTH
    writes; the unannotated key keeps exactly one (last write in list order)."""
    g = R.StateGraph(dict)
    g.add_reducer("appended", concat_reducer)

    g.add_node("router", lambda s: None)
    g.add_node("w1", lambda s: {"appended": ["one"], "overwritten": "from_w1"})
    g.add_node("w2", lambda s: {"appended": ["two"], "overwritten": "from_w2"})

    g.set_entry("router")
    g.add_conditional_edges("router", lambda s: ["w1", "w2"])
    g.add_edge("w1", R.END)
    g.add_edge("w2", R.END)

    out = g.compile().invoke({})
    assert sorted(out["appended"]) == ["one", "two"]     # reducer merged both
    assert out["overwritten"] == "from_w2"               # default LWW kept one


# ------------------------------------------------------------------ Send fan-out
def test_send_n_way_merge_completeness_and_join_once(R):
    joins_seen = []

    def join(state):
        joins_seen.append(list(state["findings"]))
        return {"joined": len(state["findings"])}

    def worker(state):
        return {"findings": [f"f:{state['subquery']}"]}

    g = R.StateGraph(dict)
    g.add_reducer("findings", concat_reducer)
    g.add_node("plan", lambda s: None)
    g.add_node("worker", worker)
    g.add_node("join", join)
    g.set_entry("plan")
    g.add_conditional_edges(
        "plan", lambda s: [R.Send("worker", {"subquery": q}) for q in s["subqueries"]])
    g.add_edge("worker", "join")
    g.add_edge("join", R.END)
    graph = g.compile()

    qs = ["alpha", "beta", "gamma", "delta"]
    out = graph.invoke({"subqueries": qs})
    assert out["findings"] == [f"f:{q}" for q in qs]     # ALL N landed, in order
    assert out["joined"] == 4
    assert len(joins_seen) == 1                          # join ran ONCE, after all
    assert joins_seen[0] == [f"f:{q}" for q in qs]       # and saw everything
    assert graph.execution_log == ["plan", "worker", "worker", "worker", "worker", "join"]


def test_send_log_order_deterministic_list_order(R):
    def worker(state):
        return {"order": [state["subquery"]]}

    g = R.StateGraph(dict)
    g.add_reducer("order", concat_reducer)
    g.add_node("plan", lambda s: None)
    g.add_node("worker", worker)
    g.set_entry("plan")
    sends = [R.Send("worker", {"subquery": q}) for q in ("q3", "q1", "q2")]
    g.add_conditional_edges("plan", lambda s: list(sends))
    g.add_edge("worker", R.END)
    graph = g.compile()

    out1 = graph.invoke({})
    log1 = list(graph.execution_log)
    out2 = graph.invoke({})
    log2 = list(graph.execution_log)
    expected = ["plan", "worker", "worker", "worker"]
    assert log1 == log2 == expected                  # router list order, every run
    assert out1["order"] == out2["order"] == ["q3", "q1", "q2"]


def test_send_branches_are_deep_copy_isolated(R):
    observed = []

    def worker(state):
        observed.append(list(state["scratch"]))      # snapshot BEFORE mutating
        state["scratch"].append(state["subquery"])   # in place, NEVER returned
        return {"seen": [state["subquery"]]}

    g = R.StateGraph(dict)
    g.add_reducer("seen", concat_reducer)
    g.add_node("plan", lambda s: None)
    g.add_node("worker", worker)
    g.set_entry("plan")
    g.add_conditional_edges(
        "plan", lambda s: [R.Send("worker", {"subquery": q}) for q in ("a", "b", "c")])
    g.add_edge("worker", R.END)
    graph = g.compile()

    out = graph.invoke({"scratch": ["base"]})
    # each branch saw only its own pristine copy — no cross-branch leakage
    assert observed == [["base"], ["base"], ["base"]]
    assert out["scratch"] == ["base"]                # mutation never leaked up
    assert out["seen"] == ["a", "b", "c"]            # only RETURNED updates merged


def test_send_arg_seeds_branch_state(R):
    got = {}

    def worker(state):
        got.update(state)                            # branch input snapshot
        return {}

    g = R.StateGraph(dict)
    g.add_node("plan", lambda s: None)
    g.add_node("worker", worker)
    g.set_entry("plan")
    g.add_conditional_edges("plan", lambda s: [R.Send("worker", {"subquery": "q1"})])
    g.add_edge("worker", R.END)
    g.compile().invoke({"topic": "graphs"})
    # arg overlaid AND parent keys still visible through the copy
    assert got["subquery"] == "q1"
    assert got["topic"] == "graphs"


def test_send_to_unknown_node_raises_at_runtime(R):
    g = R.StateGraph(dict)
    g.add_node("plan", lambda s: None)
    g.set_entry("plan")
    g.add_conditional_edges("plan", lambda s: [R.Send("ghost", {})])
    graph = g.compile()                              # dynamic dest: compiles fine
    with pytest.raises(R.GraphError, match="unknown node 'ghost'"):
        graph.invoke({})


# --------------------------------------------------------------- immutability
def test_nested_mutation_without_returning_does_not_leak(R):
    downstream_saw = {}

    def mutator(state):
        state["items"].append("MUTANT")              # nested in-place, no return
        state["flag"] = True                         # top-level too

    def observer(state):
        downstream_saw["items"] = list(state["items"])
        downstream_saw["flag"] = state.get("flag")

    g = R.StateGraph(dict)
    g.add_node("mutator", mutator)
    g.add_node("observer", observer)
    g.set_entry("mutator")
    g.add_edge("mutator", "observer")
    g.add_edge("observer", R.END)
    out = g.compile().invoke({"items": [1, 2]})
    assert downstream_saw == {"items": [1, 2], "flag": None}   # invisible downstream
    assert out["items"] == [1, 2] and "flag" not in out       # and in final state


def test_returned_updates_are_deep_copied_into_state(R):
    local = {"k": [1, 2]}

    g = R.StateGraph(dict)
    g.add_node("a", lambda s: {"items": local["k"]})   # returns an alias
    g.set_entry("a")
    graph = g.compile()

    out = graph.invoke({})
    local["k"].append(99)                            # mutate AFTER the fact
    assert out["items"] == [1, 2]                    # state holds its own copy


def test_invoke_input_untouched_and_result_detached(R):
    values = {"items": [1], "nested": {"deep": ["x"]}}

    g = R.StateGraph(dict)
    g.add_node("a", lambda s: {"items": s["items"] + [2]})
    g.set_entry("a")
    graph = g.compile()

    out = graph.invoke(values)
    assert values == {"items": [1], "nested": {"deep": ["x"]}}   # input intact
    out["items"].append(777)
    out["nested"]["deep"].append("y")
    assert graph.invoke(values)["items"] == [1, 2]               # engine unaffected


# ------------------------------------------------------------- loop + limits
def test_conditional_loop_iterates_to_budget(R):
    runs = {"tools": 0}

    def tools(state):
        runs["tools"] += 1
        return {"history": [state["count"]], "count": state["count"] + 1}

    g = R.StateGraph(dict)
    g.add_reducer("history", concat_reducer)
    g.add_node("model", lambda s: None)                          # routes only
    g.add_node("tools", tools)
    g.set_entry("model")
    g.add_conditional_edges(
        "model", lambda s: "tools" if s["count"] < 3 else R.END)
    g.add_edge("tools", "model")                                 # back edge
    graph = g.compile()

    out = graph.invoke({"count": 0, "history": []})
    assert runs["tools"] == 3                                    # budget honoured
    assert out["count"] == 3 and out["history"] == [0, 1, 2]
    assert graph.execution_log == ["model", "tools", "model", "tools",
                                   "model", "tools", "model"]


def test_recursion_limit_raises_when_router_never_ends(R):
    g = R.StateGraph(dict)
    g.add_node("spin", lambda s: None)
    g.set_entry("spin")
    g.add_conditional_edges("spin", lambda s: "spin")            # infinite loop
    graph = g.compile()
    with pytest.raises(R.GraphError, match="recursion limit"):
        graph.invoke({}, recursion_limit=10)


# ------------------------------------------------------------------- hygiene
def test_execution_log_resets_between_invokes(R):
    g = R.StateGraph(dict)
    g.add_node("a", lambda s: {"n": s.get("n", 0) + 1})
    g.add_node("b", lambda s: None)
    g.set_entry("a")
    g.add_edge("a", "b")
    g.add_edge("b", R.END)
    graph = g.compile()
    graph.invoke({"n": 0})
    assert graph.execution_log == ["a", "b"]
    graph.invoke({"n": 10})
    assert graph.execution_log == ["a", "b"]         # no accumulation across runs
