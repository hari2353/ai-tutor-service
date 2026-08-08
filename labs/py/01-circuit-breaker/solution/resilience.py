"""Lab 01 — reference solution."""
from __future__ import annotations

import inspect
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


class TimeoutExceeded(Exception): ...
class CircuitBreakerOpen(Exception): ...
class BulkheadFull(Exception): ...
class RetriesExhausted(Exception): ...


class Clock:
    def now(self) -> float: raise NotImplementedError
    def sleep(self, seconds: float) -> None: raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float: return time.monotonic()
    def sleep(self, seconds: float) -> None: time.sleep(seconds)


class FakeClock(Clock):
    def __init__(self, t: float = 0.0) -> None:
        self.t = t
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds

    def advance(self, dt: float) -> None:
        self.t += dt


@dataclass
class Deadline:
    at: float
    clock: Clock

    @classmethod
    def after(cls, seconds: float, clock: Clock) -> "Deadline":
        return cls(at=clock.now() + seconds, clock=clock)

    def remaining(self) -> float:
        return max(0.0, self.at - self.clock.now())

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def budget_for(self, per_call_max: float) -> float:
        rem = self.remaining()
        if rem <= 0.0:
            raise TimeoutExceeded("deadline exceeded before call")
        return min(rem, per_call_max)


def full_jitter(attempt: int, base: float = 0.1, cap: float = 10.0,
                rng: random.Random | None = None) -> float:
    r = rng or random
    return r.uniform(0.0, min(cap, base * (2 ** attempt)))


def decorrelated_jitter(prev: float, base: float = 0.1, cap: float = 10.0,
                        rng: random.Random | None = None) -> float:
    r = rng or random
    return min(cap, r.uniform(base, max(base, prev * 3)))


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
        self.stats.calls += 1
        last: BaseException | None = None
        for attempt in range(self.attempts):
            self.stats.attempts += 1
            try:
                return fn(*a, **kw)
            except self.retry_on as exc:
                last = exc
                if attempt < self.attempts - 1:
                    self.clock.sleep(full_jitter(attempt, self.base, self.cap, self.rng))
        self.stats.exhausted += 1
        assert last is not None
        raise last


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
        self._results: deque[tuple[bool, bool]] = deque(maxlen=sliding_window)
        self._opened_at = 0.0
        self._probes_left = 0
        self._probe_successes = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        return self._state

    def _rate(self, idx: int) -> float:
        if len(self._results) < self.min_calls:
            return 0.0
        return sum(1 for r in self._results if r[idx]) / len(self._results)

    def _failure_rate(self) -> float:
        return self._rate(0)

    def _slow_rate(self) -> float:
        return self._rate(1)

    def _to(self, new: State) -> None:
        self.stats.transitions.append((self._state.value, new.value))
        self._state = new

    def _trip(self) -> None:
        self._to(State.OPEN)
        self._opened_at = self.clock.now()
        self._results.clear()

    def _allow(self) -> bool:
        with self._lock:
            if self._state is State.OPEN:
                if self.clock.now() - self._opened_at >= self.open_duration:
                    self._to(State.HALF_OPEN)
                    self._probes_left = self.half_open_probes
                    self._probe_successes = 0
                else:
                    return False
            if self._state is State.HALF_OPEN:
                if self._probes_left <= 0:
                    return False
                self._probes_left -= 1
            return True

    def _record(self, failed: bool, slow: bool) -> None:
        with self._lock:
            if self._state is State.HALF_OPEN:
                if failed:
                    self._trip()
                else:
                    self._probe_successes += 1
                    if self._probe_successes >= self.half_open_probes:
                        self._to(State.CLOSED)
                        self._results.clear()
                return
            self._results.append((failed, slow))
            if self._failure_rate() >= self.failure_rate_threshold:
                self._trip()
            elif (self.slow_call_rate_threshold is not None
                  and self._slow_rate() >= self.slow_call_rate_threshold):
                self._trip()

    def call(self, fn: Callable[..., T], *a, **kw) -> T:
        if not self._allow():
            self.stats.rejections += 1
            raise CircuitBreakerOpen(f"circuit '{self.name}' is open")
        self.stats.calls += 1
        started = self.clock.now()
        try:
            out = fn(*a, **kw)
        except self.ignore:
            raise
        except self.record_on:
            self.stats.failures += 1
            self._record(True, False)
            raise
        elapsed = self.clock.now() - started
        self._record(False, elapsed >= self.slow_call_duration)
        return out


@dataclass
class BulkheadStats:
    calls: int = 0
    rejections: int = 0
    max_concurrent: int = 0


class Bulkhead:
    def __init__(self, limit: int, name: str = "bh") -> None:
        self.limit = limit
        self.name = name
        self.stats = BulkheadStats()
        self._sem = threading.BoundedSemaphore(limit)
        self._in_flight = 0
        self._lock = threading.Lock()

    def call(self, fn: Callable[..., T], *a, **kw) -> T:
        if not self._sem.acquire(blocking=False):
            self.stats.rejections += 1
            raise BulkheadFull(f"bulkhead '{self.name}' at capacity ({self.limit})")
        try:
            with self._lock:
                self._in_flight += 1
                self.stats.calls += 1
                self.stats.max_concurrent = max(self.stats.max_concurrent, self._in_flight)
            return fn(*a, **kw)
        finally:
            with self._lock:
                self._in_flight -= 1
            self._sem.release()


def _with_timeout(fn: Callable[..., T], budget: float, clock: Clock) -> Callable[..., T]:
    """Pass the budget down if the callable accepts `timeout=`, and treat an
    over-budget return as a failure. This mirrors how real clients work: you hand
    the deadline to the transport, you do not kill a thread."""
    accepts = False
    try:
        accepts = "timeout" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        pass

    def wrapper(*a, **kw):
        started = clock.now()
        if accepts and "timeout" not in kw:
            kw["timeout"] = budget
        out = fn(*a, **kw)
        if clock.now() - started > budget:
            raise TimeoutExceeded(f"call exceeded {budget}s budget")
        return out

    return wrapper


def resilient(fn: Callable[..., T],
              timeout: float | None = None,
              retry: Retry | None = None,
              breaker: CircuitBreaker | None = None,
              bulkhead: Bulkhead | None = None,
              fallback: Callable[[BaseException], T] | None = None,
              clock: Clock | None = None) -> Callable[..., T]:
    clk = clock or SystemClock()

    def invoke(*a, **kw) -> T:
        target = fn
        if timeout is not None:
            target = _with_timeout(target, timeout, clk)
        inner = target

        def with_retry(*aa, **kk):
            return retry.call(inner, *aa, **kk) if retry else inner(*aa, **kk)

        def with_breaker(*aa, **kk):
            return breaker.call(with_retry, *aa, **kk) if breaker else with_retry(*aa, **kk)

        if bulkhead:
            return bulkhead.call(with_breaker, *a, **kw)
        return with_breaker(*a, **kw)

    def wrapped(*a, **kw) -> T:
        try:
            return invoke(*a, **kw)
        except Exception as exc:
            if fallback is not None:
                return fallback(exc)
            raise

    return wrapped
