"""Lab 04 tests. No sleeps, no wall-clock — everything runs on FakeClock."""
import pytest


# ------------------------------------------------------------------ helpers
def make_spec(R, name="search_contacts", fn=None, properties=None, required=None):
    params = {"type": "object"}
    if properties:
        params["properties"] = properties
    if required:
        params["required"] = required
    return R.ToolSpec(name=name, description="test double",
                      parameters=params, fn=fn or (lambda **kw: kw))


def ledger_spy():
    calls = {"n": 0}

    def charge():
        calls["n"] += 1
        return {"charge": calls["n"]}

    return charge, calls


# ------------------------------------------------------------------ ToolSpec schema
def test_validate_accepts_valid_args(R):
    s = make_spec(R, properties={"query": {"type": "string"},
                                 "max_results": {"type": "integer"}},
                  required=["query"])
    assert s.validate({"query": "jane"}) == []
    assert s.validate({"query": "jane", "max_results": 5}) == []


def test_validate_flags_wrong_type(R):
    s = make_spec(R, properties={"max_results": {"type": "integer"},
                                 "ratio": {"type": "number"}})
    problems = s.validate({"max_results": "five"})
    assert any("max_results" in p for p in problems)
    assert any("integer" in p for p in problems)
    assert s.validate({"ratio": 7}) == [], "int is a valid JSON number"


def test_validate_bool_is_not_integer(R):
    """bool subclasses int in Python; the lite schema must not be fooled."""
    s = make_spec(R, properties={"depth": {"type": "integer"}})
    assert s.validate({"depth": True}) != []
    assert s.validate({"depth": 3}) == []


def test_validate_flags_missing_required(R):
    s = make_spec(R, properties={"query": {"type": "string"},
                                 "service": {"type": "string"}},
                  required=["query", "service"])
    problems = s.validate({"query": "timeout"})
    assert any("service" in p and "required" in p for p in problems)
    assert s.validate({"query": "t", "service": "checkout-api"}) == []


def test_validate_flags_enum_violation(R):
    s = make_spec(R, properties={"status": {"type": "string",
                                            "enum": ["pending", "shipped"]}})
    problems = s.validate({"status": "cancelled"})
    assert any("'cancelled'" in p for p in problems)
    assert s.validate({"status": "shipped"}) == []


def test_validate_rejects_extra_fields_strictly(R):
    s = make_spec(R, properties={"query": {"type": "string"}})
    problems = s.validate({"query": "x", "drop_tables": True})
    assert any("drop_tables" in p for p in problems)
    assert s.validate({}) == [], "fields are optional unless required"


def test_validate_requires_an_object(R):
    s = make_spec(R, properties={"query": {"type": "string"}})
    assert s.validate(["query=x"]) != []
    assert s.validate("query=x") != []


# ------------------------------------------------------------------ registry
def test_dispatch_success_envelope(R):
    def search(query, max_results=10):
        return ["hit1", "hit2"]

    reg = R.ToolRegistry()
    reg.register(make_spec(R, fn=search,
                           properties={"query": {"type": "string"},
                                       "max_results": {"type": "integer"}},
                           required=["query"]))
    out = reg.dispatch("search_contacts", {"query": "jane"})
    assert out == {"ok": True, "result": ["hit1", "hit2"]}


def test_duplicate_registration_raises(R):
    reg = R.ToolRegistry()
    reg.register(make_spec(R))
    with pytest.raises(R.DuplicateToolError):
        reg.register(make_spec(R))
    assert len(reg) == 1, "the original registration must survive"


def test_dispatch_unknown_tool_is_a_typed_observation(R):
    reg = R.ToolRegistry()
    reg.register(make_spec(R))
    out = reg.dispatch("search_contactz", {"query": "jane"})
    assert out["error"] == "unknown_tool"
    assert isinstance(out["details"], list) and out["details"]


def test_invalid_args_typed_error_before_any_side_effect(R):
    seen = {"n": 0}

    def create_ticket(title, priority):
        seen["n"] += 1
        return {"id": 42}

    reg = R.ToolRegistry()
    reg.register(make_spec(R, name="create_ticket", fn=create_ticket,
                           properties={"title": {"type": "string"},
                                       "priority": {"type": "string",
                                                    "enum": ["low", "high"]}},
                           required=["title", "priority"]))
    out = reg.dispatch("create_ticket", {"priority": "URGENT"})   # bad enum + missing title
    assert out["error"] == "invalid_args"
    assert isinstance(out["details"], list) and len(out["details"]) == 2
    assert seen["n"] == 0, "validation MUST happen before the tool runs"

    ok = reg.dispatch("create_ticket", {"title": "printer on fire", "priority": "high"})
    assert ok == {"ok": True, "result": {"id": 42}}
    assert seen["n"] == 1


# ------------------------------------------------------------------ idempotency
def test_first_execution_runs_fresh(R):
    c = R.FakeClock()
    led = R.IdempotencyLedger(ttl=30.0, clock=c)
    charge, calls = ledger_spy()

    o = led.execute("k1", charge)
    assert o.result == {"charge": 1}
    assert o.replayed is False
    assert calls["n"] == 1


def test_same_key_replays_cache_without_rerunning(R):
    c = R.FakeClock()
    led = R.IdempotencyLedger(ttl=30.0, clock=c)
    charge, calls = ledger_spy()

    first = led.execute("k1", charge)
    again = led.execute("k1", charge)
    assert again.result == first.result == {"charge": 1}
    assert again.replayed is True
    assert calls["n"] == 1, "the side effect must run exactly once"


def test_distinct_keys_execute_independently(R):
    c = R.FakeClock()
    led = R.IdempotencyLedger(ttl=30.0, clock=c)
    charge, calls = ledger_spy()

    a = led.execute("k1", charge)
    b = led.execute("k2", charge)
    assert (a.replayed, b.replayed) == (False, False)
    assert calls["n"] == 2
    assert a.result != b.result


def test_ttl_expiry_reexecutes_on_fake_clock(R):
    c = R.FakeClock()
    led = R.IdempotencyLedger(ttl=30.0, clock=c)
    charge, calls = ledger_spy()

    led.execute("k1", charge)
    c.advance(29.0)
    hit = led.execute("k1", charge)
    assert hit.replayed is True and calls["n"] == 1

    c.advance(2.0)                       # t=31 > ttl=30 — entry evicted
    fresh = led.execute("k1", charge)
    assert fresh.replayed is False and calls["n"] == 2
    assert fresh.result == {"charge": 2}


def test_purge_drops_only_expired_entries(R):
    c = R.FakeClock()
    led = R.IdempotencyLedger(ttl=10.0, clock=c)
    led.execute("old", lambda: "o")
    c.advance(6.0)
    led.execute("new", lambda: "n")
    c.advance(6.0)                       # old is 12s old (>ttl), new is 6s (<ttl)

    assert led.purge() == 1

    probe, calls = ledger_spy()
    assert led.execute("new", probe).replayed is True
    assert calls["n"] == 0, "'new' must have survived the purge"


# ------------------------------------------------------------------ retry
def test_retry_succeeds_after_transient_failures(R):
    c = R.FakeClock()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    w = R.retryable(flaky, attempts=3, retry_on=(ConnectionError,),
                    sleep=c.sleep, base_delay=0.1)
    assert w() == "ok"
    assert calls["n"] == 3
    assert w.attempts_used == 3
    assert len(c.slept) == 2             # slept between attempts, not after the last


def test_retry_exhaustion_raises_typed_give_up(R):
    c = R.FakeClock()
    calls = {"n": 0}

    def down():
        calls["n"] += 1
        raise ConnectionError("still down")

    w = R.retryable(down, attempts=3, retry_on=(ConnectionError,),
                    sleep=c.sleep, base_delay=0.1)
    with pytest.raises(R.RetriesExhausted) as ei:
        w()
    assert calls["n"] == 3
    assert w.attempts_used == 3
    assert ei.value.attempts == 3
    assert isinstance(ei.value.last, ConnectionError)


def test_retry_backoff_delays_go_through_injected_clock(R):
    c = R.FakeClock()

    def down():
        raise ConnectionError("down")

    w = R.retryable(down, attempts=4, retry_on=(ConnectionError,),
                    sleep=c.sleep, base_delay=0.1)
    with pytest.raises(R.RetriesExhausted):
        w()
    assert c.slept == pytest.approx([0.1, 0.2, 0.4])   # base_delay * 2**attempt
    assert c.now() == pytest.approx(0.7)


def test_non_retryable_propagates_immediately(R):
    c = R.FakeClock()
    calls = {"n": 0}

    def bug():
        calls["n"] += 1
        raise ValueError("400 — retrying this is pure waste")

    w = R.retryable(bug, attempts=5, retry_on=(ConnectionError,),
                    sleep=c.sleep, base_delay=0.1)
    with pytest.raises(ValueError) as ei:
        w()
    assert not isinstance(ei.value, R.RetriesExhausted)
    assert calls["n"] == 1
    assert c.slept == [], "a non-retryable error must not cost a single sleep"
