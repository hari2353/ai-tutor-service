"""Lab 02 -- the agent loop from scratch, against a scripted fake model.
Fill in every TODO. Tests define done.

Rules:
  * Nothing here may call time.sleep() or time.monotonic() directly -- go through Clock.
  * dispatch_tool() must NEVER raise -- every failure becomes a string observation.
  * FakeModel is a fixed script, not a real model -- it makes tests deterministic and free.
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

    # TODO(step 4a): implement now() and advance()
    def now(self) -> float:
        raise NotImplementedError

    def advance(self, seconds: float) -> None:
        raise NotImplementedError


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

    # TODO(step 1): return script[calls] and advance the call counter. Raise
    # IndexError with a clear message if the script has run out -- that means
    # the test's script is shorter than the loop actually ran.
    def next(self, messages: list[Message]) -> ModelResponse:
        raise NotImplementedError


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
    becomes a string observation the model can read and route around.

    TODO(step 2): in order --
      1. unknown tool name -> "ERROR: unknown tool '<name>'. Available: [...]"
      2. missing required args -> "ERROR: ... missing required args: [...]"
      3. unexpected args (not in params) -> "ERROR: ... unexpected args: [...]"
      4. wrong arg type (isinstance check against params[key]) -> "ERROR: ..."
      5. call spec.handler(**call.args); if it raises, catch it and return
         "ERROR: tool '<name>' raised <ExcType>: <msg>" -- do not let it propagate
      6. on success return f"OK: {result}"
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- no-progress
def hash_call(name: str, args: dict) -> int:
    """Stable hash of (tool_name, sorted args) -- order of kwargs must not
    matter: two calls with the same name and the same arguments (in any
    insertion order) must hash identically.

    TODO(step 3a)
    """
    raise NotImplementedError


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
        """The whole loop. Build it up in this order:

        TODO(step 1): bare loop with message passing.
          - seed `messages` with a system message (SYSTEM_PROMPT, obligation=True)
            and a user message (task, obligation=True)
          - call self.model.next(messages) each turn
          - on a "final" response, append an assistant Message with the answer
            and return AgentResult(StopReason.FINAL_ANSWER, ...)

        TODO(step 2): on a "tool_call" response, append an assistant message
          describing the call, then dispatch_tool(...) and append the
          observation as a "tool" role Message. Loop back to the top.

        TODO(step 3b): no-progress detection. hash_call() each tool call.
          Track how many times each hash has occurred (repeat_counts).
          - on the NO_PROGRESS_THRESHOLD'th (3rd) occurrence: do NOT dispatch
            the tool. Instead append a "tool" role Message (obligation=True)
            nudging the model to try something else, increment
            no_progress_warnings, and `continue` the loop (give it one more
            chance).
          - on any occurrence AFTER that (4th+ of the same hash): hard-stop
            with StopReason.NO_PROGRESS.

        TODO(step 4b): budgets, checked against self.budget and self.clock --
          - before calling the model: if step > max_steps -> StopReason.MAX_STEPS
            (steps_used = step - 1, nothing else executed this iteration)
          - before calling the model: if a deadline is set and
            self.clock.now() >= deadline -> StopReason.DEADLINE
          - after the model call: advance the clock by response.think_seconds,
            accumulate tokens_used/cost_used, and stop with MAX_TOKENS /
            MAX_COST if either budget is exceeded
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- compaction
def compact_context(messages: list[Message], keep_last: int = 4) -> list[Message]:
    """Shrink the context while PROVABLY preserving the original task and any
    open obligations: their exact text must be present, verbatim, in the
    output -- never summarised away.

    TODO(step 5):
      - if len(messages) <= keep_last + 2: return list(messages) unchanged
      - anchors: messages[0] plus the first message with role == "user"
        (the original task -- these might be the same message or different)
      - obligations: any message with .obligation == True that isn't already
        an anchor, from everything BEFORE the kept tail
      - tail: the last `keep_last` messages, kept verbatim
      - middle: everything else before the tail (not an anchor, not an
        obligation) -- replace it with a single summary Message
        (role="system", content mentioning how many messages were compacted
        and which roles they had)
      - return anchors + obligations + [summary if any middle] + tail
    """
    raise NotImplementedError
