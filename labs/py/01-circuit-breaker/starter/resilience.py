"""Lab 01 — resilience primitives. Fill in every TODO. Tests define done.

Rules:
  * Nothing here may call time.monotonic() or time.sleep() directly — go through Clock.
  * Every primitive records stats.
"""
from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, Optional, TypeVar

T = TypeVar("T")


# --------------------------------------------------------------------------- errors
class TimeoutExceeded(Exception): ...
class CircuitBreakerOpen(Exception): ...
class BulkheadFull(Exception): ...
class RetriesExhausted(Exception): ...


# --------------------------------------------------------------------------- clock
class Clock:
    def now(self) -> float: raise NotImplementedError
    def sleep(self, seconds: float) -> None: raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float: return time.monotonic()
    def sleep(self, seconds: float) -> None: time.sleep(seconds)


class FakeClock(Clock):
    """Deterministic clock. sleep() advances instead of blocking."""
    def __init__(self, t: float = 0.0) -> None:
        self.t = t
        self.slept: list[float] = []

    # TODO(step 1): implement now(), sleep(), advance()
    def now(self) -> float:
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        raise NotImplementedError

    def advance(self, dt: float) -> None:
        raise NotImplementedError


# --------------------------------------------------------------------------- deadline
@dataclass
class Deadline:
    """Absolute deadline. Propagate this, never a bare duration."""
    at: float
    clock: Clock

    @classmethod
    def after(cls, seconds: float, clock: Clock) -> "Deadline":
        # TODO(step 2a)
        raise NotImplementedError

    def remaining(self) -> float:
        # TODO(step 2b): seconds left, never negative
        raise NotImplementedError

    def expired(self) -> bool:
        # TODO(step 2c)
        raise NotImplementedError

    def budget_for(self, per_call_max: float) -> float:
        """min(remaining, per_call_max). Raise TimeoutExceeded if nothing left."""
        # TODO(step 2d)
        raise NotImplementedError


# --------------------------------------------------------------------------- backoff
def full_jitter(attempt: int, base: float = 0.1, cap: float = 10.0,
                rng: random.Random | None = None) -> float:
    """sleep = rand(0, min(cap, base * 2**attempt)).  attempt is 0-indexed."""
    # TODO(step 3a)
    raise NotImplementedError


def decorrelated_jitter(prev: float, base: float = 0.1, cap: float = 10.0,
                        rng: random.Random | None = None) -> float:
    """sleep = min(cap, rand(base, prev * 3))."""
    # TODO(step 3b)
    raise NotImplementedError


# --------------------------------------------------------------------------- retry
@dataclass
class RetryStats:
    calls: int = 0
    attempts: int = 0
    exhausted: int = 0


class Retry:
    def __init__(self, attempts: int = 3, base: float = 0.1, cap: float = 10.0,
                 retry_on: Iterable[type[BaseException]] = (TimeoutExceeded, ConnectionError),
                 clock: Clock | None = None, rng: random.Random | None = None) -> None:
        self.attempts = attempts
        self.base = base
        self.cap = cap
        self.retry_on = tuple(retry_on)
        self.clock = clock or SystemClock()
        self.rng = rng or random.Random()
        self.stats = RetryStats()

    def call(self, fn: Callable[..., T], *a, **kw) -> T:
        """Retry only on self.retry_on. Sleep full_jitter between attempts.
        Re-raise the LAST exception when attempts are exhausted.
        Non-retryable exceptions propagate immediately without sleeping."""
        # TODO(step 4)
        raise NotImplementedError


# --------------------------------------------------------------------------- breaker
class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class BreakerStats:
    calls: int = 0
    failures: int = 0
    rejections: int = 0
    transitions: list[tuple[str, str]] = field(default_factory=list)


class CircuitBreaker:
    def __init__(self, failure_rate_threshold: float = 0.5, sliding_window: int = 100,
                 min_calls: int = 20, open_duration: float = 30.0, half_open_probes: int = 5,
                 slow_call_rate_threshold: float | None = None,
                 slow_call_duration: float = 2.0,
                 record_on: Iterable[type[BaseException]] = (Exception,),
                 ignore: Iterable[type[BaseException]] = (),
                 clock: Clock | None = None, name: str = "cb") -> None:
        self.failure_rate_threshold = failure_rate_threshold
        self.sliding_window = sliding_window
        self.min_calls = min_calls
        self.open_duration = open_duration
        self.half_open_probes = half_open_probes
        self.slow_call_rate_threshold = slow_call_rate_threshold
        self.slow_call_duration = slow_call_duration
        self.record_on = tuple(record_on)
        self.ignore = tuple(ignore)
        self.clock = clock or SystemClock()
        self.name = name
        self.stats = BreakerStats()
        self._state = State.CLOSED
        self._results: deque[tuple[bool, bool]] = deque(maxlen=sliding_window)  # (failed, slow)
        self._opened_at = 0.0
        self._probes_left = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        return self._state

    # TODO(step 5a): _failure_rate() and _slow_rate() — return 0.0 below min_calls
    # TODO(step 5b): _allow() — OPEN→HALF_OPEN after open_duration; cap concurrent probes
    # TODO(step 5c): _record(failed, slow) — HALF_OPEN: any failure re-trips,
    #                enough successes close it. CLOSED: trip on failure OR slow rate.
    # TODO(step 5d): _trip() — set OPEN, stamp _opened_at, clear the window,
    #                append to stats.transitions

    def call(self, fn: Callable[..., T], *a, **kw) -> T:
        # TODO(step 5e): reject when not allowed (count a rejection),
        # time the call, classify via record_on/ignore, record, return or re-raise
        raise NotImplementedError


# --------------------------------------------------------------------------- bulkhead
@dataclass
class BulkheadStats:
    calls: int = 0
    rejections: int = 0
    max_concurrent: int = 0


class Bulkhead:
    """Semaphore bulkhead. Rejects immediately when saturated — does NOT queue."""

    def __init__(self, limit: int, name: str = "bh") -> None:
        self.limit = limit
        self.name = name
        self.stats = BulkheadStats()
        # TODO(step 6a): pick your primitive. threading.BoundedSemaphore(limit)
        #                with acquire(blocking=False) is the simplest correct choice.

    def call(self, fn: Callable[..., T], *a, **kw) -> T:
        # TODO(step 6b): acquire without blocking; on failure count a rejection and
        # raise BulkheadFull. Track max_concurrent. ALWAYS release in a finally.
        raise NotImplementedError


# --------------------------------------------------------------------------- compose
def resilient(fn: Callable[..., T],
              timeout: float | None = None,
              retry: Retry | None = None,
              breaker: CircuitBreaker | None = None,
              bulkhead: Bulkhead | None = None,
              fallback: Callable[[BaseException], T] | None = None,
              clock: Clock | None = None) -> Callable[..., T]:
    """Compose in the correct nesting order:

        bulkhead( breaker( retry( timeout( fn ) ) ) )

    with `fallback` catching whatever escapes. Timeout innermost because you retry a
    timed-out attempt; retry inside the breaker so one logical failure is one
    breaker outcome; bulkhead outermost so rejection costs no thread.
    """
    # TODO(step 7)
    raise NotImplementedError
