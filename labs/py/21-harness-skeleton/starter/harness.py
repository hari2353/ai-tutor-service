"""Harness skeleton: context window + compaction, risk-gated tool router, budgeted loop, kill switch."""
import time


class SystemClock:
    def now(self):
        return time.monotonic()


class FakeClock:
    def __init__(self, t=0):
        self._t = t

    def now(self):
        return self._t

    def advance(self, dt):
        self._t += dt


class ContextWindow:
    def __init__(self, cap, tokenizer=None, summarizer=None):
        """cap: max tokens. tokenizer: fn(str)->int (default len(s)//4).
        summarizer: fn(list_of_dropped)->str, injected as a summary message."""

    def add(self, msg, pinned=False):
        """Add a message. If over cap, compact: drop oldest non-pinned, then
        inject the summarizer output as one message. Pinned messages never drop."""

    def tokens(self):
        """Current total token estimate."""

    def messages(self):
        """List of (text, pinned) in order. Summary messages are normal unpinned."""


class ToolError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class PermissionDenied(Exception):
    pass


class ToolRouter:
    def __init__(self):
        """Registry of tools: name -> (fn, schema, risk)."""

    def register(self, name, fn, schema, risk):
        """risk in {read_only, side_effect, destructive}."""

    def call(self, name, args, approver=None):
        """Validate schema (required keys present, else ToolError non-retryable),
        gate destructive on approver(name, args) -> True,
        wrap tool exceptions as ToolError(retryable from the exception's flag)."""


class LoopEngine:
    def __init__(self, llm, router, context, cfg, clock):
        """cfg: dict(max_turns, token_budget, wallclock_budget, max_tool_errors).
        llm: fn(list_of_message_texts) -> reply string. A reply starting with
        'CALL: name {json}' is a tool call; 'STOP' ends the loop; else a plain
        assistant message (also ends the loop)."""

    def run(self):
        """Run turns until a stop condition fires. Between turns, check:
        kill_switch flag, budgets (tokens via context, wallclock via clock),
        consecutive tool errors >= max_tool_errors. Log every decision point.
        Returns {"stopped_by": str, "turns": int}."""

    @property
    def kill_switch(self):
        """Setting this to True stops the loop before the next turn begins."""


class EventLog:
    def __init__(self):
        """Append-only event store."""

    def append(self, t, kind, payload):
        raise NotImplementedError

    def events(self, kind=None):
        """Events in order, optionally filtered by kind."""
