"""Evaluating the harness itself: injection resistance, timeouts, over-tooling, cost guard."""
import json
import re

_DIRECTIVE_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?(previous|the above)",
    r"(please )?call \w+ now",
    r"you must (now )?\w+",
    r"^(system|assistant):",
    r"new instructions:",
]


def sanitize_tool_result(result):
    out = result
    for pat in _DIRECTIVE_PATTERNS:
        out = re.sub(pat, lambda m: f"[data: {m.group(0)}]", out,
                     flags=re.IGNORECASE)
    return out


def injection_resistant_harness(llm, router, max_turns=10):
    events = []
    messages = []
    stopped_by = None
    for turn in range(max_turns):
        reply = llm(messages)
        messages.append(f"assistant: {reply}")
        if reply.strip() == "STOP":
            stopped_by = "stop"
            break
        if reply.startswith("CALL:"):
            try:
                body = reply[5:].strip()
                name, argstr = body.split(" ", 1)
                args = json.loads(argstr)
                result = router.call(name, args)
                safe = sanitize_tool_result(str(result))
                messages.append(f"tool-result: {safe}")
                events.append({"turn": turn, "tool": name, "result": safe})
            except Exception as e:
                messages.append(f"tool-error: {e}")
                events.append({"turn": turn, "error": str(e)})
        else:
            stopped_by = "done"
            break
    if stopped_by is None:
        stopped_by = "max_turns"
    return {"events": events, "stopped_by": stopped_by, "messages": messages}


class _DeadlineExceeded(Exception):
    pass


def with_deadline(fn, deadline_s, clock):
    """fn receives the clock; a cooperative hanging fn advances the clock past
    the deadline and raises _DeadlineExceeded itself (that's the contract the
    sandboxed fn has). We translate that into a timeout count."""
    start = clock.now()
    try:
        result = fn(clock)
    except _DeadlineExceeded:
        return ("timeout", None)
    elapsed = clock.now() - start
    if elapsed > deadline_s:
        return ("timeout", None)
    return ("ok", result)


def detect_over_tooling(tool_history, per_task_budget):
    return {tid for tid, calls in tool_history.items() if len(calls) > per_task_budget}


class CostGuard:
    def __init__(self, cap_usd, cost_per_tool_usd=None):
        self.cap = cap_usd
        self.costs = dict(cost_per_tool_usd or {})
        self._default = self.costs.get("default", 0.01)
        self.total = 0.0

    def charge(self, tool):
        self.total += self.costs.get(tool, self._default)
        return max(self.cap - self.total, 0.0)

    def exceeded(self):
        return self.total > self.cap
