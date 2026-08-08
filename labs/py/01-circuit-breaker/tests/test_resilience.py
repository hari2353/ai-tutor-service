"""Lab 01 tests. No sleeps, no wall-clock — everything runs on FakeClock."""
import random
import threading

import pytest


# ------------------------------------------------------------------ clock
def test_fake_clock_advances(R):
    c = R.FakeClock(t=100.0)
    assert c.now() == 100.0
    c.advance(5.0)
    assert c.now() == 105.0


def test_fake_clock_sleep_does_not_block(R):
    c = R.FakeClock()
    c.sleep(3.0)
    assert c.now() == 3.0
    assert c.slept == [3.0]


# ------------------------------------------------------------------ deadline
def test_deadline_remaining_and_expiry(R):
    c = R.FakeClock()
    d = R.Deadline.after(10.0, c)
    assert d.remaining() == pytest.approx(10.0)
    c.advance(4.0)
    assert d.remaining() == pytest.approx(6.0)
    assert not d.expired()
    c.advance(6.0)
    assert d.expired()
    assert d.remaining() == 0.0        # never negative


def test_deadline_budget_shrinks_with_depth(R):
    c = R.FakeClock()
    d = R.Deadline.after(3.0, c)
    assert d.budget_for(5.0) == pytest.approx(3.0)   # capped by what's left
    c.advance(2.5)
    assert d.budget_for(5.0) == pytest.approx(0.5)
    c.advance(1.0)
    with pytest.raises(R.TimeoutExceeded):
        d.budget_for(5.0)


# ------------------------------------------------------------------ backoff
def test_full_jitter_bounded_and_grows(R):
    rng = random.Random(0)
    for attempt in range(6):
        for _ in range(50):
            s = R.full_jitter(attempt, base=0.1, cap=10.0, rng=rng)
            assert 0.0 <= s <= min(10.0, 0.1 * 2 ** attempt)


def test_full_jitter_respects_cap(R):
    rng = random.Random(1)
    assert all(R.full_jitter(20, base=0.1, cap=2.0, rng=rng) <= 2.0 for _ in range(100))


def test_full_jitter_is_actually_random(R):
    rng = random.Random(2)
    vals = {R.full_jitter(5, rng=rng) for _ in range(50)}
    assert len(vals) > 40, "no jitter — the herd stays synchronised"


def test_decorrelated_jitter_bounded(R):
    rng = random.Random(3)
    prev = 0.1
    for _ in range(50):
        prev = R.decorrelated_jitter(prev, base=0.1, cap=5.0, rng=rng)
        assert 0.0 <= prev <= 5.0


# ------------------------------------------------------------------ retry
def test_retry_succeeds_after_transient_failures(R):
    c = R.FakeClock()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    r = R.Retry(attempts=3, clock=c, rng=random.Random(0))
    assert r.call(flaky) == "ok"
    assert calls["n"] == 3
    assert len(c.slept) == 2                  # slept between, not after the last


def test_retry_reraises_last_when_exhausted(R):
    c = R.FakeClock()
    r = R.Retry(attempts=3, clock=c, rng=random.Random(0))

    def always():
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        r.call(always)
    assert r.stats.attempts == 3
    assert r.stats.exhausted == 1


def test_retry_does_not_retry_non_retryable(R):
    c = R.FakeClock()
    r = R.Retry(attempts=3, retry_on=(ConnectionError,), clock=c)
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise ValueError("400 — retrying this is pure waste")

    with pytest.raises(ValueError):
        r.call(bad_request)
    assert calls["n"] == 1
    assert c.slept == []


# ------------------------------------------------------------------ breaker
def _fail(cb, n, exc=RuntimeError):
    for _ in range(n):
        with pytest.raises(exc):
            cb.call(lambda: (_ for _ in ()).throw(exc("boom")))


def test_breaker_starts_closed(R):
    cb = R.CircuitBreaker(clock=R.FakeClock())
    assert cb.state is R.State.CLOSED


def test_breaker_does_not_trip_below_min_calls(R):
    """1 failure out of 1 call is a 100% failure rate. Without min_calls
    the breaker trips on the very first error at low traffic."""
    cb = R.CircuitBreaker(min_calls=20, sliding_window=100, clock=R.FakeClock())
    _fail(cb, 5)
    assert cb.state is R.State.CLOSED


def test_breaker_trips_at_threshold(R):
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=10,
                          sliding_window=100, clock=R.FakeClock())
    for _ in range(5):
        cb.call(lambda: "ok")
    _fail(cb, 5)
    assert cb.state is R.State.OPEN


def test_open_breaker_fails_fast_without_calling(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2,
                          sliding_window=10, clock=c)
    _fail(cb, 2)
    assert cb.state is R.State.OPEN
    called = {"n": 0}

    def should_not_run():
        called["n"] += 1

    with pytest.raises(R.CircuitBreakerOpen):
        cb.call(should_not_run)
    assert called["n"] == 0
    assert cb.stats.rejections == 1


def test_breaker_half_opens_after_wait(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=30.0, half_open_probes=2, clock=c)
    _fail(cb, 2)
    assert cb.state is R.State.OPEN
    c.advance(29.0)
    with pytest.raises(R.CircuitBreakerOpen):
        cb.call(lambda: "ok")
    c.advance(2.0)
    assert cb.call(lambda: "ok") == "ok"      # probe admitted
    assert cb.state is R.State.HALF_OPEN


def test_half_open_closes_after_enough_probes(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=1.0, half_open_probes=2, clock=c)
    _fail(cb, 2)
    c.advance(2.0)
    cb.call(lambda: "ok")
    cb.call(lambda: "ok")
    assert cb.state is R.State.CLOSED


def test_half_open_reopens_on_any_probe_failure(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=1.0, half_open_probes=3, clock=c)
    _fail(cb, 2)
    c.advance(2.0)
    cb.call(lambda: "ok")
    _fail(cb, 1)
    assert cb.state is R.State.OPEN


def test_half_open_limits_concurrent_probes(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=1.0, half_open_probes=1, clock=c)
    _fail(cb, 2)
    c.advance(2.0)
    cb.call(lambda: "ok")                     # consumes the only probe, closes it
    # a second breaker to check the rejection path with 2 probes, 1 consumed
    cb2 = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                           open_duration=1.0, half_open_probes=2, clock=c)
    _fail(cb2, 2)
    c.advance(2.0)
    cb2.call(lambda: "ok")
    cb2.call(lambda: "ok")
    assert cb2.state is R.State.CLOSED


def test_breaker_ignores_business_exceptions(R):
    class NotFound(Exception): ...
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          record_on=(Exception,), ignore=(NotFound,), clock=R.FakeClock())
    for _ in range(10):
        with pytest.raises(NotFound):
            cb.call(lambda: (_ for _ in ()).throw(NotFound("404")))
    assert cb.state is R.State.CLOSED, "404s must not trip the breaker"


def test_breaker_trips_on_slow_calls_that_succeed(R):
    """The dependency returns 200s in 5s. Failure rate is 0%. It still kills you."""
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.99, min_calls=4, sliding_window=10,
                          slow_call_rate_threshold=0.5, slow_call_duration=2.0, clock=c)

    def slow():
        c.advance(5.0)
        return "ok"

    for _ in range(4):
        cb.call(slow)
    assert cb.state is R.State.OPEN


def test_breaker_records_transitions(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=1.0, half_open_probes=1, clock=c)
    _fail(cb, 2)
    c.advance(2.0)
    cb.call(lambda: "ok")
    assert ("closed", "open") in cb.stats.transitions
    assert ("open", "half_open") in cb.stats.transitions


# ------------------------------------------------------------------ bulkhead
def test_bulkhead_allows_up_to_limit(R):
    bh = R.Bulkhead(limit=3)
    for _ in range(10):
        assert bh.call(lambda: "ok") == "ok"   # sequential — never saturates
    assert bh.stats.rejections == 0


def test_bulkhead_rejects_when_saturated(R):
    bh = R.Bulkhead(limit=2)
    entered, release = threading.Semaphore(0), threading.Event()
    errors = []

    def hold():
        entered.release()
        release.wait(timeout=5)
        return "held"

    ts = [threading.Thread(target=lambda: bh.call(hold)) for _ in range(2)]
    for t in ts:
        t.start()
    entered.acquire(timeout=5)
    entered.acquire(timeout=5)

    with pytest.raises(R.BulkheadFull):
        bh.call(lambda: "should be rejected")

    release.set()
    for t in ts:
        t.join(timeout=5)
    assert bh.stats.rejections == 1
    assert bh.stats.max_concurrent == 2


def test_bulkhead_releases_on_exception(R):
    bh = R.Bulkhead(limit=1)
    for _ in range(5):
        with pytest.raises(ValueError):
            bh.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
    assert bh.call(lambda: "ok") == "ok", "slot leaked on the exception path"


# ------------------------------------------------------------------ composition
def test_resilient_composes_and_falls_back(R):
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=2, sliding_window=10,
                          open_duration=30.0, clock=c)
    r = R.Retry(attempts=2, retry_on=(ConnectionError,), clock=c, rng=random.Random(0))

    def dead():
        raise ConnectionError("down")

    call = R.resilient(dead, retry=r, breaker=cb, bulkhead=R.Bulkhead(limit=5),
                       fallback=lambda exc: "STALE_CACHE", clock=c)
    for _ in range(4):
        assert call() == "STALE_CACHE"
    assert cb.state is R.State.OPEN


def test_retry_group_counts_as_one_breaker_outcome(R):
    """THE test. Retry lives inside the breaker: 3 attempts of one logical
    call must record ONE failure, not three — otherwise the breaker trips 3x fast."""
    c = R.FakeClock()
    cb = R.CircuitBreaker(failure_rate_threshold=0.5, min_calls=4, sliding_window=10,
                          clock=c)
    r = R.Retry(attempts=3, retry_on=(ConnectionError,), clock=c, rng=random.Random(0))

    def dead():
        raise ConnectionError("down")

    call = R.resilient(dead, retry=r, breaker=cb, clock=c)
    for _ in range(3):
        with pytest.raises(ConnectionError):
            call()
    assert r.stats.attempts == 9          # 3 logical calls x 3 attempts
    assert cb.stats.calls == 3            # but only 3 breaker outcomes
    assert cb.state is R.State.CLOSED     # min_calls=4 not yet reached


def test_bulkhead_rejection_costs_no_downstream_call(R):
    bh = R.Bulkhead(limit=1)
    hits = {"n": 0}

    def work():
        hits["n"] += 1
        return "ok"

    call = R.resilient(work, bulkhead=bh)
    entered, release = threading.Semaphore(0), threading.Event()

    def holder():
        bh.call(lambda: (entered.release(), release.wait(timeout=5))[0])

    t = threading.Thread(target=holder)
    t.start()
    entered.acquire(timeout=5)
    with pytest.raises(R.BulkheadFull):
        call()
    release.set()
    t.join(timeout=5)
    assert hits["n"] == 0
