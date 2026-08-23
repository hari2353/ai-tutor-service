"""Lab 04 — tool engineering primitives. Fill in every TODO. Tests define done.

Rules:
  * Nothing here may call time.monotonic() or time.sleep() directly — go through
    Clock, or the sleep callable injected into retryable().
  * Errors that cross the tool boundary are typed dicts, never raised
    exceptions. Exceptions are for harness bugs and give-up conditions.
"""
from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")


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

    # TODO(step 1): implement now(), sleep() (record + advance), advance()
    def now(self) -> float:
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        raise NotImplementedError

    def advance(self, dt: float) -> None:
        raise NotImplementedError


# --------------------------------------------------------------------------- errors
class DuplicateToolError(Exception):
    """Registration-time conflict — a harness bug, so it RAISES."""


class RetriesExhausted(Exception):
    """Raised by retryable() when the attempt budget is spent.

    TODO(step 5a): implement __init__(attempts, last) storing both as
    attributes; the raise site chains `from last`.
    """


# --------------------------------------------------------------------------- schema
def _matches_type(value: Any, expected: str) -> bool:
    """json-schema-lite type check.

    NOTE the Python trap: bool subclasses int, so a boolean must NOT satisfy
    'integer' or 'number'.
    """
    # TODO(step 2a): honour string/integer/number/boolean/array/object/null.
    #                An unknown type name is not enforced (return True).
    raise NotImplementedError


@dataclass
class ToolSpec:
    """A tool contract.

    `parameters` is json-schema-lite:

        {"type": "object",
         "properties": {"<param>": {"type": "...", "enum": [...]}},
         "required": ["<param>", ...]}

    Only type / required / properties / enum are honoured. Validation is
    STRICT: any argument key absent from `properties` is an error.
    """
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]

    def validate(self, args: Any) -> list[str]:
        """Return every problem as a readable string; empty list == valid.
        Order: unexpected fields, missing required, then per-field type/enum.
        Never raises."""
        # TODO(step 2b)
        raise NotImplementedError


# --------------------------------------------------------------------------- registry
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()

    def register(self, spec: ToolSpec) -> None:
        # TODO(step 3a): a duplicate name raises DuplicateToolError
        raise NotImplementedError

    def names(self) -> list[str]:
        return sorted(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def dispatch(self, name: str, args: dict) -> dict:
        """Validate FIRST, then call. Never raises for caller mistakes:

          unknown name       -> {"error": "unknown_tool", "details": [...]}
          failed validation  -> {"error": "invalid_args", "details": [...]}
          success            -> {"ok": True, "result": <fn(**args)>}

        A malformed call must cost ZERO side effects: fn runs only after
        validation passes, and receives a COPY of args. Genuine crashes of a
        validated tool propagate — this boundary owns caller mistakes, not
        your bugs.
        """
        # TODO(step 3b)
        raise NotImplementedError


# --------------------------------------------------------------------------- idempotency
@dataclass
class Outcome:
    result: Any
    replayed: bool


class IdempotencyLedger:
    """key -> cached result, TTL'd on the injected clock.

    Same LIVE key : fn does NOT run again; cached result, replayed=True.
    Distinct keys : independent executions.
    Expired key   : entry evicted, fn runs fresh, replayed=False.
    Only successes are cached — a raising fn leaves no trace.
    """

    def __init__(self, ttl: float = 300.0, clock: Clock | None = None) -> None:
        self.ttl = ttl
        self.clock = clock or SystemClock()
        self._store: dict[str, tuple[Any, float]] = {}   # key -> (result, stored_at)
        self._lock = threading.Lock()
        self.hits = 0
        self.executes = 0

    def execute(self, key: str, fn: Callable[..., T], *a, **kw) -> Outcome:
        # TODO(step 4a): lazy-evict expired entries, serve live hits WITHOUT
        #                running fn, otherwise run fn (outside the lock!) and
        #                store (result, now).
        raise NotImplementedError

    def purge(self) -> int:
        """Drop every expired entry now. Returns how many were dropped."""
        # TODO(step 4b)
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self._store)


# --------------------------------------------------------------------------- retry
def retryable(fn: Callable[..., T],
              attempts: int = 3,
              retry_on: Iterable[type[BaseException]] = (ConnectionError,),
              sleep: Callable[[float], None] = time.sleep,
              base_delay: float = 0.05) -> Callable[..., T]:
    """Wrap fn with bounded retries.

    * Retry ONLY on exceptions matching `retry_on`.
    * Between attempts sleep base_delay * 2**attempt — through the INJECTED
      sleep callable, never time.sleep() directly (tests pass FakeClock.sleep).
    * Exhausted: raise RetriesExhausted(attempts_used, last), chained from last.
    * Non-retryable exceptions propagate immediately and unslept.
    * Wrapper records .attempts_used (attempts consumed by the last call).
    """
    # TODO(step 5b)
    raise NotImplementedError
