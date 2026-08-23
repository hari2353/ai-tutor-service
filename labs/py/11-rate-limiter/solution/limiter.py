"""Lab 11 -- rate limiters from scratch: token bucket, sliding-window counter,
and a distributed-style limiter that shares one counter across "nodes".

Everything runs on an injectable Clock. Nothing here calls time.sleep() --
tests move time forward instantly via FakeClock.advance().
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- clock
class Clock:
    def now(self) -> float: raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float: return time.monotonic()


class FakeClock(Clock):
    """Deterministic clock. advance() moves time forward without blocking."""
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        if seconds:
            self.t += seconds


# --------------------------------------------------------------------------- token bucket
class TokenBucket:
    """Classic token bucket: starts with `initial_tokens` (defaults to full
    capacity -- a fresh bucket permits an immediate burst), refills
    continuously at `refill_rate` tokens/second, capped at `capacity`.
    After the initial burst is spent, sustained throughput is exactly
    `refill_rate` requests/second -- no more, no less."""

    def __init__(self, capacity: float, refill_rate: float, clock: Clock,
                 initial_tokens: float | None = None) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clock = clock
        self.tokens = capacity if initial_tokens is None else initial_tokens
        self._last_refill = clock.now()

    def _refill(self) -> None:
        now = self.clock.now()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self._last_refill = now

    def try_acquire(self, cost: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self.tokens


# --------------------------------------------------------------------------- fixed window (the buggy baseline)
class FixedWindowCounter:
    """The naive, classically-buggy rate limiter: count requests in a fixed
    calendar-aligned window, reset to 0 the instant the window rolls over.
    Included here ONLY as the baseline that demonstrates the bug --
    SlidingWindowCounter below is the fix. A client that saves up requests
    and fires `limit` of them at the very end of one window, then `limit`
    more at the very start of the next, gets 2x the limit through in a near-
    instant burst spanning the boundary, and this class allows exactly that.
    """

    def __init__(self, limit: int, window_seconds: float, clock: Clock) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._window_start: float | None = None
        self._count = 0

    def try_acquire(self) -> bool:
        now = self.clock.now()
        window_start = math.floor(now / self.window_seconds) * self.window_seconds
        if self._window_start != window_start:
            self._window_start = window_start
            self._count = 0
        if self._count < self.limit:
            self._count += 1
            return True
        return False


# --------------------------------------------------------------------------- sliding window (the fix)
class SlidingWindowCounter:
    """Sliding-window-counter approximation (the algorithm behind Cloudflare's
    and many API gateways' rate limiters): blend the previous fixed window's
    count into the current window's estimate, weighted by how much of the
    previous window is still "inside" the trailing look-back:

        estimated = current_count + previous_count * (time left in the
                                                        overlap / window_seconds)

    Right at a window boundary the previous window's weight is ~1.0, so a
    client that maxed out the previous window is immediately throttled again
    in the new window -- no 2x-at-the-edge burst.
    """

    def __init__(self, limit: int, window_seconds: float, clock: Clock) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._current_window_start: float | None = None
        self._current_count = 0
        self._previous_count = 0

    def _roll(self) -> None:
        now = self.clock.now()
        window_start = math.floor(now / self.window_seconds) * self.window_seconds
        if self._current_window_start is None:
            self._current_window_start = window_start
            return
        if window_start != self._current_window_start:
            windows_advanced = round((window_start - self._current_window_start) / self.window_seconds)
            self._previous_count = self._current_count if windows_advanced == 1 else 0
            self._current_count = 0
            self._current_window_start = window_start

    def try_acquire(self) -> bool:
        self._roll()
        now = self.clock.now()
        elapsed_in_current = now - self._current_window_start
        weight_prev = max(0.0, (self.window_seconds - elapsed_in_current) / self.window_seconds)
        estimated = self._current_count + self._previous_count * weight_prev
        if estimated < self.limit:
            self._current_count += 1
            return True
        return False


# --------------------------------------------------------------------------- distributed-style: shared counter
class Node:
    """One 'app server' hitting a shared limiter. The correct distributed
    pattern: every node reads and writes the SAME counter (in real systems,
    a Redis key with an atomic INCR+EXPIRE, or an atomic compare-and-swap
    store) -- so the aggregate limit is enforced across the whole fleet, not
    per node. Give each node its OWN bucket instead and you silently
    multiply your real limit by the number of nodes -- see
    `test_naive_per_node_buckets_over_admit_by_node_count` for the bug this
    class exists to avoid."""

    def __init__(self, node_id: str, shared_bucket: TokenBucket) -> None:
        self.node_id = node_id
        self.shared_bucket = shared_bucket

    def try_acquire(self, cost: float = 1.0) -> bool:
        return self.shared_bucket.try_acquire(cost)


# --------------------------------------------------------------------------- fair queueing under contention
@dataclass
class FairQueueLimiter:
    """Token bucket with round-robin fair allocation across clients. When a
    batch of pending requests from multiple clients is processed together
    and there isn't enough budget for everyone, grants are handed out one at
    a time, round-robin across DISTINCT clients that still have pending
    requests -- not first-come-first-served -- so one client submitting far
    more requests than everyone else cannot starve the others."""

    capacity: float
    refill_rate: float
    clock: Clock
    bucket: TokenBucket = field(init=False)

    def __post_init__(self) -> None:
        self.bucket = TokenBucket(self.capacity, self.refill_rate, self.clock)

    def process_batch(self, client_requests: dict[str, int]) -> dict[str, int]:
        """client_requests: client_id -> number of pending requests this
        round. Returns client_id -> number admitted. Stops the instant the
        bucket has no tokens left (further rounds can't succeed either,
        since no clock time passes during batch processing)."""
        remaining = dict(client_requests)
        admitted = {cid: 0 for cid in client_requests}
        order = list(client_requests.keys())

        made_progress = True
        while made_progress:
            made_progress = False
            for cid in order:
                if remaining.get(cid, 0) <= 0:
                    continue
                if not self.bucket.try_acquire(1.0):
                    return admitted
                admitted[cid] += 1
                remaining[cid] -= 1
                made_progress = True
        return admitted


def fcfs_process_batch(bucket: TokenBucket, ordered_client_ids: list[str]) -> dict[str, int]:
    """The anti-pattern for comparison: process requests strictly in
    submission order. If one client front-loads many requests before
    others get a chance, first-come-first-served lets it consume the
    entire budget."""
    admitted: dict[str, int] = {}
    for cid in ordered_client_ids:
        if bucket.try_acquire(1.0):
            admitted[cid] = admitted.get(cid, 0) + 1
    return admitted
