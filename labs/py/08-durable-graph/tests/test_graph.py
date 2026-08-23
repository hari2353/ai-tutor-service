"""Lab 08 tests. No LangGraph, no network, no sleeps. SQLite tests use a
plain tempfile path (the shim has no built-in tmp_path fixture)."""
import os
import tempfile

import pytest


# ------------------------------------------------------------------ step 1/3: linear graph execution
def test_linear_graph_runs_all_nodes_in_order(G):
    order = []

    def a(state):
        order.append("a")
        return {"a_done": True}

    def b(state):
        order.append("b")
        return {"b_done": True}

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("a", a)
    graph.add_node("b", b)
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", G.END)

    result = graph.run("t1", {})
    assert order == ["a", "b"]
    assert result.status == "done"
    assert result.state == {"a_done": True, "b_done": True}


def test_run_with_no_entry_point_raises(G):
    graph = G.StateGraph(G.InMemoryCheckpointer())
    with pytest.raises(ValueError):
        graph.run("t1", {})


def test_unknown_node_referenced_by_edge_raises(G):
    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("a", lambda state: {})
    graph.set_entry_point("a")
    graph.add_edge("a", "ghost")
    with pytest.raises(KeyError):
        graph.run("t1", {})


# ------------------------------------------------------------------ step 3: conditional edges
def test_conditional_edge_routes_to_path_a(G):
    hits = {"a": 0, "b": 0}

    def classify(state):
        return {}

    def path_a(state):
        hits["a"] += 1
        return {"path": "a"}

    def path_b(state):
        hits["b"] += 1
        return {"path": "b"}

    def router(state):
        return "path_a" if state.get("go") == "a" else "path_b"

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("classify", classify)
    graph.add_node("path_a", path_a)
    graph.add_node("path_b", path_b)
    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", router)
    graph.add_edge("path_a", G.END)
    graph.add_edge("path_b", G.END)

    result = graph.run("t1", {"go": "a"})
    assert result.state["path"] == "a"
    assert hits == {"a": 1, "b": 0}   # the untaken path never ran


def test_conditional_edge_routes_to_path_b(G):
    def router(state):
        return "path_b"

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("classify", lambda state: {})
    graph.add_node("path_a", lambda state: {"path": "a"})
    graph.add_node("path_b", lambda state: {"path": "b"})
    graph.set_entry_point("classify")
    graph.add_conditional_edges("classify", router)
    graph.add_edge("path_a", G.END)
    graph.add_edge("path_b", G.END)

    result = graph.run("t1", {})
    assert result.state["path"] == "b"


# ------------------------------------------------------------------ step 1/2: pluggable checkpointers
def _linear_graph(checkpointer, G):
    graph = G.StateGraph(checkpointer)
    graph.add_node("a", lambda state: {"a": 1})
    graph.add_node("b", lambda state: {"b": 2})
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", G.END)
    return graph


def test_in_memory_checkpointer_records_every_step(G):
    cp = G.InMemoryCheckpointer()
    graph = _linear_graph(cp, G)
    graph.run("t1", {})
    history = cp.list_checkpoints("t1")
    # step 0 (initial), after a, after b(done) == 3 checkpoints
    assert [c.step for c in history] == [0, 1, 2]
    assert history[-1].status == "done"


def test_sqlite_checkpointer_records_every_step(G):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        cp = G.SqliteCheckpointer(path)
        graph = _linear_graph(cp, G)
        graph.run("t1", {})
        history = cp.list_checkpoints("t1")
        assert [c.step for c in history] == [0, 1, 2]
        assert history[-1].state == {"a": 1, "b": 2}
    finally:
        os.remove(path)


def test_checkpointer_load_latest_returns_none_when_absent(G):
    assert G.InMemoryCheckpointer().load_latest("nope") is None
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        assert G.SqliteCheckpointer(path).load_latest("nope") is None
    finally:
        os.remove(path)


def test_thread_ids_are_isolated(G):
    cp = G.InMemoryCheckpointer()
    graph = _linear_graph(cp, G)
    graph.run("thread-1", {"seed": 1})
    graph.run("thread-2", {"seed": 2})
    r1 = cp.load_latest("thread-1")
    r2 = cp.load_latest("thread-2")
    assert r1.state["seed"] == 1
    assert r2.state["seed"] == 2


# ------------------------------------------------------------------ step 4: kill mid-execution, resume from checkpoint
def _flaky_chain(counter, G, checkpointer, fail_on_attempt=1):
    def node_a(state):
        counter["a"] = counter.get("a", 0) + 1
        return {"a": counter["a"]}

    def node_b(state):
        counter["b"] = counter.get("b", 0) + 1
        if counter["b"] == fail_on_attempt:
            raise RuntimeError("simulated crash in node b")
        return {"b": counter["b"]}

    def node_c(state):
        counter["c"] = counter.get("c", 0) + 1
        return {"c": counter["c"]}

    graph = G.StateGraph(checkpointer)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_node("c", node_c)
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", G.END)
    return graph


def test_crash_mid_run_propagates_and_leaves_last_good_checkpoint(G):
    counter = {}
    cp = G.InMemoryCheckpointer()
    graph = _flaky_chain(counter, G, cp)

    with pytest.raises(RuntimeError, match="simulated crash"):
        graph.run("t1", {})

    assert counter == {"a": 1, "b": 1}   # c never ran
    latest = cp.load_latest("t1")
    assert latest.next_node == "b"       # last checkpoint says "b" is still pending
    assert latest.status == "running"


def test_resume_after_crash_does_not_reexecute_completed_nodes(G):
    """The centerpiece: kill the run mid-way, resume, and prove node 'a'
    (already checkpointed past) does NOT run again -- only 'b' (which never
    completed) and 'c' run."""
    counter = {}
    cp = G.InMemoryCheckpointer()
    graph = _flaky_chain(counter, G, cp)

    with pytest.raises(RuntimeError):
        graph.run("t1", {})

    result = graph.resume("t1")

    assert result.status == "done"
    assert counter["a"] == 1     # NOT re-executed
    assert counter["b"] == 2     # re-executed once (crashed attempt + successful retry)
    assert counter["c"] == 1
    assert result.state == {"a": 1, "b": 2, "c": 1}


def test_resume_with_sqlite_survives_a_simulated_process_restart(G):
    """Same scenario, but the checkpointer is backed by a SQLite file and
    'resume' happens through a brand-new StateGraph + a brand-new
    SqliteCheckpointer connection -- nothing but the on-disk file is
    shared, which is the actual claim durable checkpointing makes."""
    counter = {}
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        cp1 = G.SqliteCheckpointer(path)
        graph1 = _flaky_chain(counter, G, cp1)
        with pytest.raises(RuntimeError):
            graph1.run("t1", {})
        assert counter == {"a": 1, "b": 1}

        # simulate a fresh process: new checkpointer connection, new graph,
        # nodes re-registered from source (only state is persisted, not code)
        cp2 = G.SqliteCheckpointer(path)
        graph2 = _flaky_chain(counter, G, cp2)
        result = graph2.resume("t1")

        assert result.status == "done"
        assert counter["a"] == 1   # still never re-executed
        assert counter["b"] == 2
        assert counter["c"] == 1
    finally:
        os.remove(path)


def test_resume_on_a_done_thread_is_a_noop(G):
    cp = G.InMemoryCheckpointer()
    graph = _linear_graph(cp, G)
    graph.run("t1", {})
    result = graph.resume("t1")
    assert result.status == "done"
    assert result.state == {"a": 1, "b": 2}


def test_resume_with_no_checkpoint_raises(G):
    cp = G.InMemoryCheckpointer()
    graph = _linear_graph(cp, G)
    with pytest.raises(KeyError):
        graph.resume("never-started")


# ------------------------------------------------------------------ step 5: interrupt / approve cycle
def test_interrupt_pauses_the_run_and_returns_payload(G):
    def gate(state):
        raise G.Interrupt({"question": "approve refund of $50?"})

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("gate", gate)
    graph.set_entry_point("gate")
    graph.add_edge("gate", G.END)

    result = graph.run("t1", {"amount": 50})
    assert result.status == "interrupted"
    assert result.interrupt_payload == {"question": "approve refund of $50?"}
    assert result.state == {"amount": 50}   # pre-interrupt state preserved


def test_resume_with_value_completes_the_interrupted_node_and_round_trips_state(G):
    def gate(state):
        if G.RESUME_KEY not in state:
            raise G.Interrupt({"question": "approve?"})
        return {"approved": state[G.RESUME_KEY]}

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("gate", gate)
    graph.set_entry_point("gate")
    graph.add_edge("gate", G.END)

    first = graph.run("t1", {"amount": 50})
    assert first.status == "interrupted"

    second = graph.resume("t1", resume_value=True)
    assert second.status == "done"
    assert second.state == {"amount": 50, "approved": True}   # original state survived the round trip


def test_non_idempotent_node_executed_twice_on_resume_is_detectable(G):
    """The gotcha this lab exists to teach: resume reruns the interrupted
    node from its first line. A side effect placed before the interrupt
    fires again. That's not a framework bug -- it's why idempotency keys
    on mutating tool calls are a correctness requirement, not a nicety."""
    log = []

    def gate(state):
        log.append("gate_ran")   # non-idempotent: e.g. "charged the card"
        if G.RESUME_KEY not in state:
            raise G.Interrupt({"question": "approve?"})
        return {"approved": state[G.RESUME_KEY]}

    graph = G.StateGraph(G.InMemoryCheckpointer())
    graph.add_node("gate", gate)
    graph.set_entry_point("gate")
    graph.add_edge("gate", G.END)

    graph.run("t1", {})
    assert log == ["gate_ran"]

    graph.resume("t1", resume_value=True)
    assert log == ["gate_ran", "gate_ran"]   # ran twice -- detectable, and expected


def test_interrupt_then_resume_checkpoint_history_shows_both_statuses(G):
    def gate(state):
        if G.RESUME_KEY not in state:
            raise G.Interrupt({"q": "ok?"})
        return {"done": True}

    cp = G.InMemoryCheckpointer()
    graph = G.StateGraph(cp)
    graph.add_node("gate", gate)
    graph.set_entry_point("gate")
    graph.add_edge("gate", G.END)

    graph.run("t1", {})
    graph.resume("t1", resume_value=True)

    statuses = [c.status for c in cp.list_checkpoints("t1")]
    assert "interrupted" in statuses
    assert statuses[-1] == "done"
