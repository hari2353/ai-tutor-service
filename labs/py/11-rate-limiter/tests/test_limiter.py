"""Lab 11 tests. Fully deterministic, no network, no time.sleep() -- every
test drives time forward via FakeClock.advance(). Tests define done."""
import pytest


# ============================================================== step 1: fake clock
def test_fake_clock_advances_without_blocking(L):
    c = L.FakeClock(t=0.0)
    c.advance(3.0)
    assert c.now() == 3.0
    c.advance(2.0)
    assert c.now() == 5.0


# ============================================================== step 2: token bucket -- burst boundary
def test_token_bucket_permits_a_full_burst(L):
    clock = L.FakeClock(t=0.0)
    bucket = L.TokenBucket(capacity=5, refill_rate=1.0, clock=clock)
    # a fresh bucket starts full -- all 5 burst requests succeed immediately
    for _ in range(5):
        assert bucket.try_acquire() is True
    # the 6th, still at t=0, must be throttled -- burst is exhausted
    assert bucket.try_acquire() is False


def test_token_bucket_throttles_to_exact_refill_rate_after_burst(L):
    """After the initial burst, sustained throughput must be EXACTLY
    refill_rate requests/second -- not faster, not slower."""
    clock = L.FakeClock(t=0.0)
    bucket = L.TokenBucket(capacity=5, refill_rate=1.0, clock=clock)
    for _ in range(5):
        assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False  # burst spent

    clock.advance(1.0)  # exactly one refill_rate tick
    assert bucket.try_acquire() is True    # exactly one new token available
    assert bucket.try_acquire() is False   # and only one

    clock.advance(0.5)  # half a token -- not enough for cost=1.0
    assert bucket.try_acquire() is False

    clock.advance(0.5)  # now a full token has accumulated (0.5 + 0.5)
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_never_exceeds_capacity_even_after_long_idle(L):
    clock = L.FakeClock(t=0.0)
    bucket = L.TokenBucket(capacity=5, refill_rate=1.0, clock=clock, initial_tokens=0)
    clock.advance(1000.0)  # would refill to 1000 tokens if uncapped
    assert bucket.available_tokens == pytest.approx(5.0)
    # still only 5 acquires succeed, not 1000
    for _ in range(5):
        assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_respects_variable_cost(L):
    clock = L.FakeClock(t=0.0)
    bucket = L.TokenBucket(capacity=10, refill_rate=1.0, clock=clock)
    assert bucket.try_acquire(cost=7.0) is True
    assert bucket.try_acquire(cost=4.0) is False  # only 3 left
    assert bucket.try_acquire(cost=3.0) is True


# ============================================================== step 3: fixed-window bug (baseline)
def test_fixed_window_counter_allows_2x_burst_across_a_boundary(L):
    """The classic fixed-window bug, demonstrated directly: fill the limit
    at the very end of one window, then fill it again at the very start of
    the next -- a naive fixed-window counter lets 2x the limit through in a
    near-instant span around the boundary."""
    clock = L.FakeClock(t=9.99)
    counter = L.FixedWindowCounter(limit=10, window_seconds=10.0, clock=clock)
    admitted = sum(1 for _ in range(10) if counter.try_acquire())
    assert admitted == 10  # window [0,10) fully spent, right at the edge

    clock.advance(0.02)  # now t=10.01 -- into window [10,20)
    admitted_after = sum(1 for _ in range(10) if counter.try_acquire())
    assert admitted_after == 10  # THE BUG: window reset gives a fresh 10

    # 20 requests admitted within a 0.02-second span -- 2x the stated limit
    assert admitted + admitted_after == 20


# ============================================================== step 4: sliding window -- the fix
def test_sliding_window_counter_does_not_allow_2x_burst_across_a_boundary(L):
    """Same scenario as the fixed-window test above, same limit, same
    boundary -- but the sliding window counter must NOT let 2x through."""
    clock = L.FakeClock(t=9.99)
    counter = L.SlidingWindowCounter(limit=10, window_seconds=10.0, clock=clock)
    admitted = sum(1 for _ in range(10) if counter.try_acquire())
    assert admitted == 10  # first window fills normally

    clock.advance(0.02)  # t=10.01 -- just barely into the next window
    admitted_after = sum(1 for _ in range(10) if counter.try_acquire())

    total = admitted + admitted_after
    assert total < 20          # strictly less than the fixed-window bug's total
    assert total <= 12         # close to the true limit, not anywhere near double


def test_sliding_window_counter_relaxes_as_time_passes_into_new_window(L):
    """As more of the new window elapses, the previous window's weight
    decays and more requests should be admitted -- the throttling is smooth,
    not a hard wall for the rest of the window."""
    clock = L.FakeClock(t=9.99)
    counter = L.SlidingWindowCounter(limit=10, window_seconds=10.0, clock=clock)
    for _ in range(10):
        counter.try_acquire()

    clock.advance(0.02)  # t=10.01, previous window's weight ~0.999
    right_after_boundary = sum(1 for _ in range(5) if counter.try_acquire())

    clock.advance(4.99)  # t=15.0, previous window's weight = 0.5
    mid_window = sum(1 for _ in range(10) if counter.try_acquire())

    assert mid_window > right_after_boundary


def test_sliding_window_counter_allows_full_limit_in_a_fresh_window(L):
    clock = L.FakeClock(t=0.0)
    counter = L.SlidingWindowCounter(limit=5, window_seconds=10.0, clock=clock)
    admitted = sum(1 for _ in range(5) if counter.try_acquire())
    assert admitted == 5
    assert counter.try_acquire() is False


# ============================================================== step 5: distributed -- shared counter
def test_shared_bucket_caps_total_admissions_across_nodes(L):
    """The correct distributed pattern: multiple nodes share ONE bucket
    (one counter). Interleaved requests from 3 nodes must never admit more
    than the shared capacity in total."""
    clock = L.FakeClock(t=0.0)
    shared_bucket = L.TokenBucket(capacity=5, refill_rate=0.0, clock=clock)
    nodes = [L.Node(f"node-{i}", shared_bucket) for i in range(3)]

    admitted_total = 0
    # interleave: each node tries 5 times, round-robin, simulating 3 app
    # servers all handling concurrent traffic against the same shared limit
    for _round in range(5):
        for node in nodes:
            if node.try_acquire():
                admitted_total += 1

    assert admitted_total == 5  # exactly the shared capacity -- not 15


def test_naive_per_node_buckets_over_admit_by_node_count(L):
    """The bug this lab's Node class exists to avoid: give each node its OWN
    independent bucket (forgetting to share state) and the effective limit
    silently becomes capacity * number_of_nodes."""
    clock = L.FakeClock(t=0.0)
    per_node_buckets = [L.TokenBucket(capacity=5, refill_rate=0.0, clock=clock) for _ in range(3)]

    admitted_total = 0
    for _round in range(5):
        for bucket in per_node_buckets:
            if bucket.try_acquire():
                admitted_total += 1

    assert admitted_total == 15  # 3x the intended capacity -- the bug, made concrete


# ============================================================== step 6: fair queueing under contention
def test_fair_queue_limiter_splits_capacity_evenly_despite_lopsided_demand(L):
    """One client (A) submits far more requests than the others (B, C).
    Round-robin fair queueing must not let A's volume translate into a
    bigger share of a scarce, shared budget."""
    clock = L.FakeClock(t=0.0)
    limiter = L.FairQueueLimiter(capacity=6, refill_rate=0.0, clock=clock)
    admitted = limiter.process_batch({"A": 10, "B": 2, "C": 2})

    assert admitted == {"A": 2, "B": 2, "C": 2}
    assert sum(admitted.values()) == 6


def test_fair_queue_limiter_does_not_starve_low_volume_clients(L):
    clock = L.FakeClock(t=0.0)
    limiter = L.FairQueueLimiter(capacity=3, refill_rate=0.0, clock=clock)
    admitted = limiter.process_batch({"noisy": 100, "quiet": 1})
    assert admitted["quiet"] == 1  # quiet client is never starved out


def test_fcfs_baseline_lets_first_client_starve_the_rest(L):
    """Contrast: naive first-come-first-served processing, with the noisy
    client's requests submitted first, lets it consume the entire budget
    and starves everyone queued behind it -- the failure mode fair
    queueing exists to prevent."""
    clock = L.FakeClock(t=0.0)
    bucket = L.TokenBucket(capacity=6, refill_rate=0.0, clock=clock)
    order = ["A"] * 10 + ["B"] * 2 + ["C"] * 2
    admitted = L.fcfs_process_batch(bucket, order)

    assert admitted.get("A") == 6
    assert admitted.get("B") is None or admitted.get("B") == 0
    assert admitted.get("C") is None or admitted.get("C") == 0


def test_fair_queue_limiter_grants_exactly_capacity_when_demand_exceeds_it(L):
    clock = L.FakeClock(t=0.0)
    limiter = L.FairQueueLimiter(capacity=4, refill_rate=0.0, clock=clock)
    admitted = limiter.process_batch({"A": 3, "B": 3, "C": 3})
    assert sum(admitted.values()) == 4
    # fair round-robin over 3 clients for 4 slots: everyone gets at least 1
    assert all(count >= 1 for count in admitted.values())
