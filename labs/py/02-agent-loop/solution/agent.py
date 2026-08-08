"""Lab 02 -- the agent loop from scratch, against a scripted fake model.

No network, no API keys: FakeModel plays back a pre-written script of responses,
so the whole loop is deterministic and free to test. Nothing here calls
time.sleep() or time.monotonic() directly -- everything goes through Clock.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# --------------------------------------------------------------------------- clock
class Clock:
    def now(self) -> float: raise NotImplementedError
    def advance(self, seconds: float) -> None: raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> float: return time.monotonic()
    def advance(self, seconds: float) -> None: time.sleep(seconds)


class FakeClock(Clock):
    """Deterministic clock. advance() moves time forward without blocking."""
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        if seconds:
            self.t += seconds


# --------------------------------------------------------------------------- messages
@dataclass
class Message:
    role: str                       # "system" | "user" | "assistant" | "tool"
    content: str
    obligation: bool = False        # must survive context compaction verbatim


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ModelResponse:
    """One turn of the scripted fake model."""
    kind: str                          # "final" | "tool_call"
    content: Optional[str] = None      # final-answer text, when kind == "final"
    tool_call: Optional[ToolCall] = None
    tokens: int = 10
    cost: float = 0.01
    think_seconds: float = 0.0         # wall-clock time this turn consumes


class FakeModel:
    """Plays back a fixed script of ModelResponse objects, one per call to
    .next(). Deterministic and free -- the whole point of testing an agent
    loop without hitting a real LLM API."""
    def __init__(self, script: list[ModelResponse]) -> None:
        self.script = list(script)
        self.calls = 0

    def next(self, messages: list[Message]) -> ModelResponse:
        if self.calls >= len(self.script):
            raise IndexError(
                f"FakeModel script exhausted after {self.calls} calls -- "
                f"the test's script is shorter than the loop actually ran."
            )
        response = self.script[self.calls]
        self.calls += 1
        return response


SYSTEM_PROMPT = (
    "You are an agent. Use the available tools to accomplish the user's task, "
    "then give a final answer."
)


# --------------------------------------------------------------------------- tools
@dataclass
class ToolSpec:
    name: str
    params: dict[str, type]
    handler: Callable[..., str]
    required: set[str] = field(default_factory=set)


def dispatch_tool(tools: dict[str, ToolSpec], call: ToolCall) -> str:
    """Validate and execute a tool call. NEVER raises -- every failure mode
    becomes a string observation the model can read and route around."""
    spec = tools.get(call.name)
    if spec is None:
        return f"ERROR: unknown tool '{call.name}'. Available: {sorted(tools)}"

    missing = spec.required - call.args.keys()
    if missing:
        return f"ERROR: tool '{call.name}' missing required args: {sorted(missing)}"

    unexpected = set(call.args) - set(spec.params)
    if unexpected:
        return f"ERROR: tool '{call.name}' got unexpected args: {sorted(unexpected)}"

    for key, value in call.args.items():
        expected = spec.params[key]
        if not isinstance(value, expected):
            return (f"ERROR: tool '{call.name}' arg '{key}' expected "
                     f"{expected.__name__}, got {type(value).__name__}")

    try:
        result = spec.handler(**call.args)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: this is the boundary
        return f"ERROR: tool '{call.name}' raised {type(exc).__name__}: {exc}"
    return f"OK: {result}"


# --------------------------------------------------------------------------- no-progress
def hash_call(name: str, args: dict) -> int:
    """Stable hash of (tool_name, sorted args) -- order of kwargs must not
    matter, two calls with the same name and the same arguments (in any
    insertion order) must hash identically."""
    canonical = (name, tuple(sorted(args.items())))
    return hash(canonical)


# --------------------------------------------------------------------------- budgets / stop
class StopReason(Enum):
    FINAL_ANSWER = "final_answer"
    MAX_STEPS = "max_steps"
    MAX_TOKENS = "max_tokens"
    MAX_COST = "max_cost"
    DEADLINE = "deadline"
    NO_PROGRESS = "no_progress"


@dataclass
class Budget:
    max_steps: int = 50
    max_tokens: int = 100_000
    max_cost: float = 10.0
    deadline_seconds: Optional[float] = None


@dataclass
class AgentResult:
    stop_reason: StopReason
    final_answer: Optional[str]
    messages: list[Message]
    steps_used: int
    tokens_used: int
    cost_used: float
    no_progress_warnings: int


NO_PROGRESS_THRESHOLD = 3  # repeats of an identical call before intervention


class AgentLoop:
    def __init__(self, model: FakeModel, tools: dict[str, ToolSpec],
                 budget: Optional[Budget] = None, clock: Optional[Clock] = None) -> None:
        self.model = model
        self.tools = tools
        self.budget = budget or Budget()
        self.clock = clock or SystemClock()

    def run(self, task: str) -> AgentResult:
        messages: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT, obligation=True),
            Message(role="user", content=task, obligation=True),
        ]
        deadline = (None if self.budget.deadline_seconds is None
                    else self.clock.now() + self.budget.deadline_seconds)

        total_tokens = 0
        total_cost = 0.0
        step = 0
        no_progress_warnings = 0
        repeat_counts: dict[int, int] = {}

        while True:
            step += 1

            if step > self.budget.max_steps:
                return AgentResult(StopReason.MAX_STEPS, None, messages, step - 1,
                                    total_tokens, total_cost, no_progress_warnings)
            if deadline is not None and self.clock.now() >= deadline:
                return AgentResult(StopReason.DEADLINE, None, messages, step - 1,
                                    total_tokens, total_cost, no_progress_warnings)

            response = self.model.next(messages)
            self.clock.advance(response.think_seconds)
            total_tokens += response.tokens
            total_cost += response.cost

            if total_tokens > self.budget.max_tokens:
                return AgentResult(StopReason.MAX_TOKENS, None, messages, step,
                                    total_tokens, total_cost, no_progress_warnings)
            if total_cost > self.budget.max_cost:
                return AgentResult(StopReason.MAX_COST, None, messages, step,
                                    total_tokens, total_cost, no_progress_warnings)

            if response.kind == "final":
                messages.append(Message(role="assistant", content=response.content))
                return AgentResult(StopReason.FINAL_ANSWER, response.content, messages,
                                    step, total_tokens, total_cost, no_progress_warnings)

            call = response.tool_call
            key = hash_call(call.name, call.args)
            repeat_counts[key] = repeat_counts.get(key, 0) + 1
            count = repeat_counts[key]

            messages.append(Message(role="assistant",
                                     content=f"[tool_call] {call.name}({call.args})"))

            if count >= NO_PROGRESS_THRESHOLD:
                if count == NO_PROGRESS_THRESHOLD:
                    # Intervene: don't dispatch a 3rd identical call. Nudge the
                    # model instead and give it one more chance to recover.
                    no_progress_warnings += 1
                    messages.append(Message(
                        role="tool",
                        content=(f"OBSERVATION: you called '{call.name}' with the same "
                                 f"arguments {NO_PROGRESS_THRESHOLD} times with no new "
                                 f"information. Try a different tool or different arguments."),
                        obligation=True,
                    ))
                    continue
                # Repeated again after the intervention -- genuinely stuck.
                return AgentResult(StopReason.NO_PROGRESS, None, messages, step,
                                    total_tokens, total_cost, no_progress_warnings)

            observation = dispatch_tool(self.tools, call)
            messages.append(Message(role="tool", content=observation))


# --------------------------------------------------------------------------- compaction
def compact_context(messages: list[Message], keep_last: int = 4) -> list[Message]:
    """Shrink the context while PROVABLY preserving the original task and any
    open obligations: their exact text is guaranteed present, verbatim, in the
    output (checked by tests via substring containment), never summarised away.
    """
    if len(messages) <= keep_last + 2:
        return list(messages)

    anchor_indices = {0}
    for i, m in enumerate(messages):
        if m.role == "user":
            anchor_indices.add(i)
            break
    anchors = [messages[i] for i in sorted(anchor_indices)]
    anchor_ids = {id(m) for m in anchors}

    tail_start = len(messages) - keep_last
    tail = messages[tail_start:]
    tail_ids = {id(m) for m in tail}

    head = messages[:tail_start]
    obligations = [m for m in head if m.obligation and id(m) not in anchor_ids]
    middle = [m for m in head if id(m) not in anchor_ids and not m.obligation]

    out = list(anchors) + obligations
    if middle:
        roles = ", ".join(sorted({m.role for m in middle}))
        out.append(Message(role="system",
                            content=f"[compacted {len(middle)} earlier message(s): {roles}]"))
    out.extend(tail)
    return out
