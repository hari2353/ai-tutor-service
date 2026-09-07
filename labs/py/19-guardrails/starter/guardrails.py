"""Lab 19 — Layered guardrails. Fill in every TODO.

The sketch lives in curriculum/07-agentic-ai/19-guardrails.md; this lab
makes it real and testable. Policies: block > fix > escalate > log.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Literal

Policy = Literal["block", "fix", "log", "escalate"]  # fail-closed -> fail-open order

PII = {"ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
       "card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
       "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")}


class Blocked(Exception):
    """fail-closed: the request dies here."""

    def __init__(self, guard: str, reason: str):
        self.guard, self.reason = guard, reason
        super().__init__(f"[{guard}] {reason}")


class NeedsHuman(Exception):
    """escalate: a human must decide before this ships."""

    def __init__(self, guard: str, reason: str):
        self.guard, self.reason = guard, reason
        super().__init__(f"[{guard}] {reason}")


@dataclass
class GuardState:
    pseudonyms: dict = field(default_factory=dict)   # token -> real value; NOT logged
    hits: list = field(default_factory=list)         # audit trail (no raw PII)


@dataclass
class Guard:
    name: str
    fn: Callable[[str, GuardState], "str | None"]    # None = pass
    on_violation: Policy
    on_error: Policy                                 # THE per-risk decision
    cost_ms: int = 0                                 # for budget accounting


def redact(text: str, st: GuardState) -> str | None:
    """Replace each PII match with a deterministic token; record the swap."""
    # TODO(step 1)
    raise NotImplementedError


def jailbreak_stub(text: str, st: GuardState) -> str | None:
    """Marker-based jailbreak detector. Returns a reason string or None."""
    # TODO(step 2)
    raise NotImplementedError


def has_canary(text: str, st: GuardState, canary: str = "CANARY_7f3a91") -> str | None:
    """System-prompt leak detector: the canary must never reach the user."""
    # TODO(step 3)
    raise NotImplementedError


def schema_ok(text: str, st: GuardState, required: tuple = ("action", "args")) -> str | None:
    """Structured-output validator: parseable JSON with all required keys."""
    # TODO(step 4)
    raise NotImplementedError


def run_guards(text: str, guards: list[Guard], st: GuardState) -> str:
    """Run each guard in order. A violation applies the guard's policy:
    fix -> rerun the guard on the text and keep its output,
    block -> raise Blocked, escalate -> raise NeedsHuman, log -> continue.
    A guard that THROWS applies on_error, not on_violation."""
    # TODO(step 5)
    raise NotImplementedError


def hydrate(text: str, st: GuardState) -> str:
    """Re-hydration: restore real values for tokens, exactly once, at render."""
    # TODO(step 6)
    raise NotImplementedError


def handle(user_msg: str, agent: Callable[[str], str]) -> str:
    """Input guards -> agent -> output guards (on pseudonymised text!) ->
    hydrate. The model only ever sees pseudonyms; the user gets reals back."""
    # TODO(step 7)
    raise NotImplementedError
