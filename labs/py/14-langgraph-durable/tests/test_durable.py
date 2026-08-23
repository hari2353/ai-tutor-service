"""Lab 14 tests. No sleeps, no wall-clock — durability is pure state mechanics."""
from collections import Counter

import pytest


# ------------------------------------------------------------------ helpers
def chain_edges(R, names):
    """START -> n1 -> ... -> nk -> END."""
    e = {R.START: names[0]}
    for a, b in zip(names, names[1:]):
        e[a] = b
    e[names[-1]] = R.END
    return e


def counter_nodes(spec):
    """{name: (fn, updates)} -> nodes dict + per-node call counters."""
    counts = Counter()

    def make(name, fn):
        def node(state, ctx):
            counts[name] += 1
            return fn(state, ctx)
        return node

    nodes = {name: make(name, fn) for name, (fn, _) in spec.items()}
    return nodes, counts


def noop(_state, _ctx):
    return None


# ------------------------------------------------------------- checkpointing
def test_one_checkpoint_per_completed_node(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (noop, {}), "b": (noop, {}), "c": (noop, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b", "c"]), ck, "t1")
    out = g.invoke({"amount": 500})
    assert out.status == "done"
    # input checkpoint + one per completed node — the interview trap answer is 4
    assert [t.snapshot.step for t in ck.list("t1")] == [0, 1, 2, 3]
    assert [t.snapshot.next for t in ck.list("t1")] == [("a",), ("b",), ("c",), ()]


def test_initial_checkpoint_records_input_and_next(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a"]), ck, "t1")
    g.invoke({"amount": 500})
    first = ck.get_tuple("t1", at_step=0).snapshot
    assert first.values["amount"] == 500
    assert first.next == ("a",)
    assert first.status == "running"
    assert first.completed == ()
    assert R.META in first.values


def test_final_checkpoint_is_done(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {}),
                              "b": (lambda s, c: {"y": 2}, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b"]), ck, "t1")
    out = g.invoke({})
    assert out.state["x"] == 1 and out.state["y"] == 2
    last = ck.get_tuple("t1").snapshot
    assert last.next == ()
    assert last.status == "done"
    assert last.completed == ("a", "b")
    assert out.state[R.META]["completed"] == ["a", "b"]   # completed log lives in state meta


def test_checkpoint_chain_parent_ids_unique_and_strict(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({n: (noop, {}) for n in "abc"})
    g = R.DurableGraph(nodes, chain_edges(R, list("abc")), ck, "t1")
    g.invoke({})
    tuples = ck.list("t1")
    ids = [t.snapshot.checkpoint_id for t in tuples]
    assert len(set(ids)) == len(ids)
    steps = [t.snapshot.step for t in tuples]
    assert steps == sorted(steps) and len(set(steps)) == len(steps)
    assert tuples[0].snapshot.parent_id is None
    for prev, cur in zip(tuples, tuples[1:]):
        assert cur.snapshot.parent_id == prev.snapshot.checkpoint_id


# ------------------------------------------------------------------- crashes
def test_resume_skips_completed_nodes_execution_order(R):
    ck = R.MemoryCheckpointer()
    crash = R.FlakyCrash(1)

    def a(s, c): return {"x": 1}
    def b(s, c): return {"y": 2}
    def c(s, c):
        crash()          # dies before any write, twice-free on the retry
        return {"z": 3}
    def d(s, c): return {"w": 4}

    nodes, counts = counter_nodes({"a": (a, {}), "b": (b, {}),
                                   "c": (c, {}), "d": (d, {})})
    order = []
    for name, fn in nodes.items():
        def wrapper(s, ctx, _fn=fn, _name=name):
            order.append(_name)
            return _fn(s, ctx)
        nodes[name] = wrapper

    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b", "c", "d"]), ck, "t1")
    r1 = g.invoke({"i": 0})
    assert r1.status == "crashed"
    assert r1.executed == ["a", "b"]

    r2 = g.invoke()                      # same thread: resume from last checkpoint
    assert r2.status == "done"
    assert r2.executed == ["c", "d"]     # only what was left
    # c appears twice because IT crashed (Case B: the failed node restarts);
    # a, b and d — every COMPLETED node — never re-ran.
    assert counts == Counter({"a": 1, "b": 1, "c": 2, "d": 1})
    assert order == ["a", "b", "c", "c", "d"]


def test_crash_leaves_last_checkpoint_intact(R):
    ck = R.MemoryCheckpointer()
    crash = R.FlakyCrash(2)

    def b(s, c):
        crash()
        return {"y": 2}

    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {}), "b": (b, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b"]), ck, "t1")
    assert g.invoke({"i": 0}).status == "crashed"
    before = ck.get_tuple("t1")                       # a's snapshot, step 1
    assert g.invoke().status == "crashed"             # crash again — still no write
    after = ck.get_tuple("t1")
    assert after.snapshot.checkpoint_id == before.snapshot.checkpoint_id
    assert after.snapshot.step == before.snapshot.step == 1
    assert after.snapshot.values["x"] == 1
    assert after.snapshot.next == ("b",)
    assert after.snapshot.completed == ("a",)
    assert crash.raised == 2


def test_flaky_crash_n_times_converges_without_duplicate_effects(R):
    ck = R.MemoryCheckpointer()
    crash = R.FlakyCrash(3)
    effects = Counter()

    def enrich(s, c):
        crash()                    # effect sits AFTER the crash point: safe spot
        effects["enrich"] += 1
        return {"tier": "gold"}

    def score(s, c):
        effects["score"] += 1
        return {"score": 99}

    nodes, _ = counter_nodes({"enrich": (enrich, {}), "score": (score, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["enrich", "score"]), ck, "t1")

    attempts = 0
    while True:
        out = g.invoke({"q": 1}) if attempts == 0 else g.invoke()
        attempts += 1
        if out.status != "crashed":
            break
        assert attempts <= 10

    assert out.status == "done"
    assert crash.remaining == 0
    assert attempts == 4                        # 3 crashes + 1 clean pass
    assert effects == Counter({"enrich": 1, "score": 1})


def test_pre_failure_side_effect_repeats_on_resume(R):
    # The curriculum lesson: a side effect BEFORE the failure point happens again.
    ck = R.MemoryCheckpointer()
    charges = []
    crash = R.FlakyCrash(1)

    def charge_then_die(s, c):
        charges.append(("charge", s["amount"]))
        crash()                                # process dies AFTER charging
        return {"charged": True}

    def settle(s, c):
        return {"settled": True}

    nodes, _ = counter_nodes({"charge": (charge_then_die, {}), "settle": (settle, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["charge", "settle"]), ck, "acct-7")

    assert g.invoke({"amount": 99}).status == "crashed"
    done = g.invoke()
    assert done.status == "done"
    # at-least-once: resume restarts the node from line one → charged twice
    assert charges == [("charge", 99), ("charge", 99)]
    assert done.state[R.META]["completed"] == ["charge", "settle"]


# ---------------------------------------------------------------- interrupts
def build_hitl(R, tid, seen=None):
    ck = R.MemoryCheckpointer()

    def triage(s, c):
        return {"tier": "manual"}

    def approve(s, c):
        if seen is not None:
            seen.append("pre-interrupt body ran")
        if c.input is None:
            c.interrupt({"prompt": "Approve refund?", "amount": s["amount"],
                         "customer": s["cid"]})
        return {"status": "approved" if c.input["approved"] else "rejected",
                "decision_by": c.input.get("who", "system")}

    def settle(s, c):
        return {"final": "settled"}

    nodes, counts = counter_nodes({"triage": (triage, {}),
                                   "approve": (approve, {}),
                                   "settle": (settle, {})})
    edges = chain_edges(R, ["triage", "approve", "settle"])
    return R.DurableGraph(nodes, edges, ck, tid), ck, counts


def test_interrupt_saves_waiting_human_state(R):
    g, ck, _ = build_hitl(R, "refund-8812")
    r1 = g.invoke({"amount": 45000, "cid": "c-771"})
    assert r1.status == "waiting_human"
    assert r1.executed == ["triage"]              # approve never completed
    snap = g.get_state()
    assert snap.status == "waiting_human"
    assert snap.next == ("approve",)
    assert "approve" not in snap.completed
    assert snap.interrupt == {"node": "approve",
                              "payload": {"prompt": "Approve refund?",
                                          "amount": 45000, "customer": "c-771"}}
    waiting_tuple = ck.get_tuple("refund-8812")
    assert waiting_tuple.snapshot.step == 2       # triage's step + 1


def test_interrupt_payload_surfaces(R):
    g, _, _ = build_hitl(R, "refund-8812")
    r1 = g.invoke({"amount": 100, "cid": "c-1"})
    payload = r1.interrupt_payload
    assert isinstance(payload, dict)
    assert payload["prompt"] == "Approve refund?"
    assert payload["customer"] == "c-1"
    # also readable later from the durable snapshot
    assert g.get_state().interrupt["payload"]["amount"] == 100


def test_resume_delivers_human_input_into_waiting_node(R):
    g, _, counts = build_hitl(R, "refund-8812")
    g.invoke({"amount": 45000, "cid": "c-771"})
    r2 = g.resume("refund-8812", {"approved": True, "who": "alice"})
    assert r2.status == "done"
    assert r2.state["status"] == "approved"
    assert r2.state["decision_by"] == "alice"     # human_input reached the node
    assert r2.state["final"] == "settled"         # downstream ran with the decision
    assert r2.executed == ["approve", "settle"]
    assert counts["settle"] == 1


def test_waiting_node_restarts_from_top_on_resume(R):
    seen = []
    g, _, _ = build_hitl(R, "refund-8812", seen=seen)
    g.invoke({"amount": 5, "cid": "c-2"})
    g.resume("refund-8812", {"approved": False})
    # curriculum Rule 2: resume means re-run the NODE, not resume the line
    assert seen.count("pre-interrupt body ran") == 2


def test_double_resume_is_guarded(R):
    g, _, _ = build_hitl(R, "refund-8812")
    g.invoke({"amount": 5, "cid": "c-3"})
    assert g.resume("refund-8812", {"approved": True}).status == "done"
    with pytest.raises(R.NotWaitingError):
        g.resume("refund-8812", {"approved": False})


def test_resume_requires_waiting_thread(R):
    # a thread that finished without ever interrupting
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {})})
    g2 = R.DurableGraph(nodes, chain_edges(R, ["a"]), ck, "t-done")
    assert g2.invoke({}).status == "done"
    with pytest.raises(R.NotWaitingError):
        g2.resume("t-done", {"approved": True})
    with pytest.raises(R.NotWaitingError):
        g2.resume("never-started", {"approved": True})


# ------------------------------------------------------------------- threads
def test_fresh_thread_starts_clean_on_shared_checkpointer(R):
    ck = R.MemoryCheckpointer()

    def mk(tid):
        nodes, counts = counter_nodes({"a": (lambda s, c: {"x": 1}, {}),
                                       "b": (lambda s, c: {"y": 2}, {})})
        return R.DurableGraph(nodes, chain_edges(R, ["a", "b"]), ck, tid), counts

    g1, counts1 = mk("A")
    g1.invoke({"src": "A"})
    g2, counts2 = mk("B")
    out = g2.invoke({"src": "B"})
    assert out.status == "done"
    assert counts1 == Counter({"a": 1, "b": 1})   # B did not piggyback on A's log
    assert counts2 == Counter({"a": 1, "b": 1})   # B started from scratch
    assert out.state["src"] == "B"
    assert ck.steps("A") == [0, 1, 2]             # A untouched by B's run
    assert ck.get_tuple("A").snapshot.values["src"] == "A"


# --------------------------------------------------------------- immutability
def test_snapshots_are_defensive_copies(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"nested": {"k": [1, 2]}}, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a"]), ck, "t1")
    res = g.invoke({})

    s = g.get_state()
    s.values["nested"]["k"].append(99)
    s.values[R.META]["status"] = "hacked"
    s.completed = ()
    assert g.get_state().values["nested"]["k"] == [1, 2]
    assert g.get_state().values[R.META]["status"] == "done"

    res.state["nested"]["k"].append(5)
    assert g.get_state().values["nested"]["k"] == [1, 2]

    tup = ck.get_tuple("t1")
    tup.snapshot.values["nested"]["k"].clear()
    assert ck.get_tuple("t1").snapshot.values["nested"]["k"] == [1, 2]


def test_time_travel_get_state_at_step(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {}),
                              "b": (lambda s, c: {"y": 2}, {}),
                              "c": (lambda s, c: {"z": 3}, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b", "c"]), ck, "t1")
    g.invoke({})

    mid = g.get_state(at_step=1)
    assert mid.values["x"] == 1
    assert "y" not in mid.values
    assert mid.completed == ("a",)
    assert mid.next == ("b",)

    early = g.get_state(at_step=0)
    assert early.completed == () and early.next == ("a",)

    latest = g.get_state()                        # present unaffected
    assert latest.status == "done" and latest.values["z"] == 3
    mid.values["x"] = 999                         # read-only view: store untouched
    assert g.get_state(at_step=1).values["x"] == 1
    with pytest.raises(KeyError):
        g.get_state(at_step=42)


# -------------------------------------------------------------- pending writes
def test_pending_writes_stored_per_step(R):
    ck = R.MemoryCheckpointer()
    nodes, _ = counter_nodes({"a": (lambda s, c: {"x": 1}, {}),
                              "b": (lambda s, c: {"y": 2}, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b"]), ck, "t1")
    g.invoke({})
    tuples = {t.snapshot.step: t for t in ck.list("t1")}
    # writes attach to the step they EXTEND (the checkpoint the task advanced
    # from) — which is why an orphaned write is found on the latest tuple
    assert tuples[0].pending_writes == (("a", {"x": 1}),)
    assert tuples[1].pending_writes == (("b", {"y": 2}),)
    assert tuples[2].pending_writes == ()


def test_orphan_pending_writes_applied_without_rerun(R):
    # Task finished, its writes landed, the snapshot commit was lost to a crash.
    ck = R.MemoryCheckpointer()
    crash = R.FlakyCrash(1)

    def d(s, c):
        crash()
        return {"w": 4}

    nodes, counts = counter_nodes({"a": (lambda s, c: {"x": 1}, {}),
                                   "b": (lambda s, c: {"y": 2}, {}),
                                   "c": (lambda s, c: {"z": 3}, {}),
                                   "d": (d, {})})
    g = R.DurableGraph(nodes, chain_edges(R, ["a", "b", "c", "d"]), ck, "t1")
    assert g.invoke({"i": 0}).status == "crashed"
    assert ck.get_tuple("t1").snapshot.step == 3

    ck.put_writes("t1", 3, "d", {"w": 4})         # simulate the lost window
    r = g.invoke()
    assert r.status == "done"
    assert r.executed == []                       # d recovered, not re-executed
    assert counts["d"] == 1                       # its one entry was the crashed attempt
    assert r.state["w"] == 4
    assert r.state[R.META]["completed"] == ["a", "b", "c", "d"]
    assert ck.get_tuple("t1").snapshot.step == 4  # application itself checkpointed


# ---------------------------------------------------------------- validation
def test_constructor_validation_and_fresh_invoke_guard(R):
    ck = R.MemoryCheckpointer()
    nodes = {"a": lambda s, c: None}
    with pytest.raises(ValueError):
        R.DurableGraph(nodes, {R.START: "a", "a": "ghost"}, ck, "t")   # unknown target
    with pytest.raises(ValueError):
        R.DurableGraph(nodes, {R.START: "a"}, ck, "t")                 # a has no edge
    with pytest.raises(ValueError):
        R.DurableGraph(nodes, {R.START: ["a", "a"], "a": R.END}, ck, "t")  # fan-out
    g = R.DurableGraph(nodes, {R.START: "a", "a": R.END}, ck, "t")
    with pytest.raises(ValueError):
        g.invoke()                                     # fresh thread needs values
