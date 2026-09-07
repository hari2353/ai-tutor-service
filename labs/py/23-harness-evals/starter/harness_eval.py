"""Evaluating the harness itself: injection resistance, timeouts, over-tooling, cost guard."""

import re

_DIRECTIVE_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?(previous|the above)",
    r"call \w+ now",
    r"you must (now )?\w+",
    r"system:",
    r"assistant:",
]


def sanitize_tool_result(result):
    """Instruction-shaped substrings in tool RESULTS get wrapped as data:
    'ignore previous instructions' -> '[data: ignore previous instructions]'.
    Returns the sanitized string."""


def injection_resistant_harness(llm, router, max_turns=10):
    """Mini loop: llm(messages) -> 'CALL: name {json}' | 'STOP' | plain text.
    Tool results pass through sanitize_tool_result before being appended.
    Returns {"events": [...], "stopped_by": str}."""


def with_deadline(fn, deadline_s, clock):
    """Run fn(a) — fn is given the clock; a hanging fn advances the clock past
    deadline inside itself and loops. Detect via clock sampling: call fn in
    chunks? NO — simulate: fn cooperatively raises after deadline by checking
    clock (test fns do this). If deadline exceeded when fn returns, count it
    as a timeout and return ('timeout', None). Else ('ok', result).
    A test's hanging fn raises _DeadlineExceeded after advancing the clock —
    catch that as the timeout signal."""


class _DeadlineExceeded(Exception):
    pass


def detect_over_tooling(tool_history, per_task_budget):
    """tool_history: {task_id: [tool names]}. Return the set of task_ids that
    used more than per_task_budget tool calls."""


class CostGuard:
    def __init__(self, cap_usd, cost_per_tool_usd=None):
        """cost_per_tool_usd: dict tool->usd (missing key = default 0.01)."""

    def charge(self, tool):
        """Add the tool's cost. Returns remaining budget."""

    def exceeded(self):
        """True when total charged > cap."""
