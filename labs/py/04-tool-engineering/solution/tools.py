"""Lab 04 — reference solution."""
from __future__ import annotations

import difflib
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


# --------------------------------------------------------------------------- errors
class DuplicateToolError(Exception):
    """Registration-time conflict — a harness bug, so it RAISES."""


class RetriesExhausted(Exception):
    def __init__(self, attempts: int, last: BaseException | None) -> None:
        super().__init__(f"gave up after {attempts} attempt(s): {last!r}")
        self.attempts = attempts
        self.last = last


# --------------------------------------------------------------------------- schema
def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return True   # unknown annotation: not enforced by the lite schema


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]

    def _properties(self) -> dict:
        props = self.parameters.get("properties")
        return props if isinstance(props, dict) else {}

    def _required(self) -> list[str]:
        req = self.parameters.get("required")
        return list(req) if req else []

    def validate(self, args: Any) -> list[str]:
        if not isinstance(args, dict):
            return [f"args must be a JSON object, got {type(args).__name__}"]
        props = self._properties()
        required = self._required()
        problems: list[str] = []
        for key in sorted(set(args) - set(props)):            # STRICT extras
            problems.append(f"{key}: unexpected argument (not in schema)")
        for key in required:
            if key not in args:
                problems.append(f"{key}: required argument missing")
        for key in sorted(set(props) & set(args)):
            pspec = props.get(key)
            if not isinstance(pspec, dict):
                continue
            want = pspec.get("type")
            if want and not _matches_type(args[key], want):
                got = "null" if args[key] is None else type(args[key]).__name__
                problems.append(f"{key}: expected type '{want}', got {got}")
                continue
            enum = pspec.get("enum")
            if enum and args[key] not in enum:
                problems.append(
                    f"{key}: expected one of {list(enum)}, got {args[key]!r}")
        return problems


# --------------------------------------------------------------------------- registry
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()

    def register(self, spec: ToolSpec) -> None:
        with self._lock:
            if spec.name in self._tools:
                raise DuplicateToolError(
                    f"tool '{spec.name}' is already registered")
            self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def dispatch(self, name: str, args: dict) -> dict:
        spec = self._tools.get(name)
        if spec is None:
            avail = ", ".join(self.names())
            close = difflib.get_close_matches(name, self._tools.keys(), n=3)
            detail = (f"no tool named '{name}'."
                      + (f" Did you mean: {', '.join(close)}?" if close else "")
                      + f" Available: {avail}")
            return {"error": "unknown_tool", "details": [detail]}

        problems = spec.validate(args)          # BEFORE any side effect
        if problems:
            return {"error": "invalid_args", "details": problems}

        result = spec.fn(**dict(args))          # copy: tools must not corrupt callers
        return {"ok": True, "result": result}


# --------------------------------------------------------------------------- idempotency
@dataclass
class Outcome:
    result: Any
    replayed: bool


class IdempotencyLedger:
    def __init__(self, ttl: float = 300.0, clock: Clock | None = None) -> None:
        self.ttl = ttl
        self.clock = clock or SystemClock()
        self._store: dict[str, tuple[Any, float]] = {}   # key -> (result, stored_at)
        self._lock = threading.Lock()
        self.hits = 0
        self.executes = 0

    def _evict_expired(self, now: float) -> int:
        dead = [k for k, (_, stored_at) in self._store.items()
                if now - stored_at >= self.ttl]
        for k in dead:
            del self._store[k]
        return len(dead)

    def execute(self, key: str, fn: Callable[..., T], *a, **kw) -> Outcome:
        with self._lock:
            self._evict_expired(self.clock.now())
            hit = self._store.get(key)
            if hit is not None:
                self.hits += 1
                return Outcome(result=hit[0], replayed=True)
        # never hold the lock across a side effect
        result = fn(*a, **kw)
        with self._lock:
            self.executes += 1
            self._store[key] = (result, self.clock.now())
        return Outcome(result=result, replayed=False)

    def purge(self) -> int:
        with self._lock:
            return self._evict_expired(self.clock.now())

    def __len__(self) -> int:
        return len(self._store)


# --------------------------------------------------------------------------- retry
def retryable(fn: Callable[..., T],
              attempts: int = 3,
              retry_on: Iterable[type[BaseException]] = (ConnectionError,),
              sleep: Callable[[float], None] = time.sleep,
              base_delay: float = 0.05) -> Callable[..., T]:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    retryable_exc = tuple(retry_on)

    @functools.wraps(fn)
    def wrapper(*a, **kw) -> T:
        last: BaseException | None = None
        used = 0
        for attempt in range(attempts):
            used += 1
            try:
                out = fn(*a, **kw)
            except retryable_exc as exc:
                last = exc
                if attempt < attempts - 1:
                    sleep(base_delay * (2 ** attempt))
                continue
            wrapper.attempts_used = used
            return out
        wrapper.attempts_used = used
        raise RetriesExhausted(used, last) from last

    wrapper.attempts_used = 0
    return wrapper
