"""Lab 19 — reference solution. The starter is this file with every body
replaced by NotImplementedError."""
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
    fn: Callable[[str, GuardState], "str | None"]
    on_violation: Policy
    on_error: Policy
    cost_ms: int = 0


def redact(text: str, st: GuardState) -> str | None:
    for kind, pat in PII.items():
        def swap(m, kind=kind):
            tok = f"<{kind}:{len(st.pseudonyms)}>"
            st.pseudonyms[tok] = m.group(0)
            return tok
        text = pat.sub(swap, text)
    return text or None


def jailbreak_stub(text: str, st: GuardState) -> str | None:
    markers = ("ignore previous", "disregard all", "developer mode", "you are danyl")
    low = text.lower()
    return "looks like a jailbreak template" if any(m in low for m in markers) else None


def has_canary(text: str, st: GuardState, canary: str = "CANARY_7f3a91") -> str | None:
    return "system-prompt leak" if canary in text else None


def schema_ok(text: str, st: GuardState, required: tuple = ("action", "args")) -> str | None:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return f"not json: {e}"
    missing = [k for k in required if k not in obj]
    return f"missing keys: {missing}" if missing else None


def run_guards(text: str, guards: list[Guard], st: GuardState) -> str:
    for g in guards:
        try:
            reason = g.fn(text, st)
        except Exception as e:
            reason, pol = f"guard error: {e}", g.on_error
        else:
            pol = g.on_violation if reason else None
        if not reason:
            continue
        st.hits.append((g.name, pol, reason))
        if pol == "fix":
            text = g.fn(text, st) or text
        elif pol == "block":
            raise Blocked(g.name, reason)
        elif pol == "escalate":
            raise NeedsHuman(g.name, reason)
        # "log" -> continue; the alarm fires from st.hits downstream
    return text


def hydrate(text: str, st: GuardState) -> str:
    for tok, val in st.pseudonyms.items():
        text = text.replace(tok, val)
    return text


def handle(user_msg: str, agent: Callable[[str], str]) -> str:
    st = GuardState()
    inp = [Guard("pii_in", redact, "fix", "log", 5),
           Guard("jailbreak", jailbreak_stub, "block", "block", 2)]
    out = [Guard("schema", schema_ok, "block", "log", 1),
           Guard("leak", has_canary, "block", "escalate", 1)]
    user_msg = run_guards(user_msg, inp, st)     # model sees pseudonyms only
    raw = agent(user_msg)
    raw = run_guards(raw, out, st)
    return hydrate(raw, st)                       # reals restored for THIS user only
