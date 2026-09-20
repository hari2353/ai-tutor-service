def test_peek_is_bounded_and_versioned(R):
    store = R.ContextStore({"tickets": ("v3", "alpha billing issue beta")})
    item = store.peek("tickets", 6, 13)
    assert item.text == "billing"
    assert item.version == "v3"
    assert item.slice_id == "tickets:v3:6-13"


def test_grep_is_case_insensitive_and_deterministic(R):
    store = R.ContextStore({
        "b": ("v1", "Beta billing"),
        "a": ("v2", "alpha BILLING"),
    })
    assert [x.source_id for x in store.grep("billing")] == ["a", "b"]


def test_budget_stops_before_child_runs(R):
    store = R.ContextStore({"x": ("v1", "one two three")})
    slices = [store.peek("x")]
    budget = R.Budget(max_calls=0)
    calls = []

    def child(*args):
        calls.append(args)
        return None

    results = R.run_children("q", slices, child, budget)
    assert calls == []
    assert results[0].status == "budget_exceeded"


def test_child_timeout_is_partial_not_negative_evidence(R):
    store = R.ContextStore({"x": ("v1", "one")})

    def child(*args):
        raise TimeoutError

    result = R.run_children("q", [store.peek("x")], child, R.Budget())
    reduced = R.reduce_results(result)
    assert reduced["partial"] is True
    assert reduced["claims"] == ()
    assert result[0].status == "timeout"


def test_reducer_deduplicates_claims_and_keeps_evidence(R):
    results = [
        R.ChildResult("a", ("Billing is monthly",), ((1, 4),), "ok", 3, 2),
        R.ChildResult("b", ("billing is monthly", "Tax is separate"), ((8, 12),), "ok", 3, 3),
    ]
    reduced = R.reduce_results(results)
    assert reduced["claims"] == ("Billing is monthly", "Tax is separate")
    assert reduced["evidence"] == ((1, 4), (8, 12))
    assert reduced["partial"] is False


def test_depth_budget_is_enforced(R):
    store = R.ContextStore({"x": ("v1", "one")})
    result = R.run_children("q", [store.peek("x")], lambda *a: None,
                            R.Budget(max_depth=1), depth=2)
    assert result[0].status == "budget_exceeded"
