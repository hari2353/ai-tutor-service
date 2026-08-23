"""Lab 03 — reasoning patterns. Fill in every TODO. Tests define done.

Rules:
  * Deterministic only — no time, no randomness. Identical scripts, identical runs.
  * Tool errors become "error: ..." observation strings; nothing propagates.
  * Never mutate the caller's tools dict, the model's script, or scripted args.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Callable


# --------------------------------------------------------------------------- fake model
class FakeLLM:
    """Deterministic model: pops queued JSON responses, records every prompt.

    Responses are plain dicts ({"thought": ..., "tool": ..., "args": ...},
    {"plan": [...]}, {"answer": ...}, {"reflection": ...}, ...). When the
    script is exhausted it answers {"final": ""}.
    """

    def __init__(self, script: list[dict]) -> None:
        self.script = copy.deepcopy(script)
        self.i = 0
        self.prompts: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> dict:
        """Record `messages` verbatim in self.prompts, then pop the next
        scripted response. Hand out COPIES — a caller mutating what it got
        back must not corrupt the script. Dry script → {"final": ""}."""
        # TODO(step 1)
        raise NotImplementedError

    def consumed(self) -> int:
        """How many scripted responses have been used so far."""
        # TODO(step 2)
        raise NotImplementedError

    def remaining(self) -> int:
        """How many scripted responses are left."""
        # TODO(step 3)
        raise NotImplementedError


# --------------------------------------------------------------------------- helpers
def _stringify(out: Any) -> str:
    """Strings pass through unchanged; JSON-able values become canonical JSON
    (json.dumps with sort_keys=True); anything else falls back to repr()."""
    # TODO(step 4)
    raise NotImplementedError


def _dispatch(tools: dict[str, Callable[[dict], Any]], name: Any, args: dict) -> str:
    """Resolve the tool, call it with a COPY of args, stringify the output.

    Unknown tool → "error: unknown tool <name>". A raising tool →
    "error: <exception message>". Never raises.
    """
    # TODO(step 5)
    raise NotImplementedError


# --------------------------------------------------------------------------- react
@dataclass
class ReactResult:
    answer: str | None = None
    trace: list[str] = field(default_factory=list)
    steps: int = 0
    reason: str = "budget"          # "final" | "budget"


def react_loop(model: FakeLLM,
               tools: dict[str, Callable[[dict], Any]],
               max_steps: int = 6,
               task: str = "") -> ReactResult:
    """ReAct: Thought → Action → Observation per step, recorded in `trace`.

    Trace lines (exact format):
        "Thought: <text>"
        "Action: <name>(<canonical json args>)"
        "Observation: <stringified tool output or error>"
        "Final: <answer>"

    The scripted model answers either {"thought", "tool", "args"} (one action)
    or {"thought", "final"} (finish). One model call == one step. Every action
    is preceded by its thought in the trace; every observation follows its
    action. Tool errors come back as observations and the loop continues.
    Budget exhausted → ReactResult(None, trace, max_steps, "budget").
    """
    # TODO(step 6): first prompt is [{"role": "user", "content": task}],
    # then loop: complete → thought line → final? → action + observation lines,
    # feeding the assistant turn ("Thought: ...\nAction: ...") and the user
    # turn ("Observation: ...") back into messages.
    raise NotImplementedError


# --------------------------------------------------------------------------- plan-execute
@dataclass
class PlanExecuteResult:
    plan: list[str] = field(default_factory=list)   # the plan that was executed
    outputs: list[str] = field(default_factory=list)
    answer: str | None = None                       # last output, if any
    replans: int = 0                                # 0 or 1 — never more
    reason: str = "completed"       # "completed" | "failed"


def plan_execute(model: FakeLLM,
                 tools: dict[str, Callable[[dict], Any]],
                 task: str = "") -> PlanExecuteResult:
    """Plan-and-Execute with a replan-on-failure edge that fires at most ONCE.

    Flow:
      1. planner call — prompt starts "Task: <task>", model returns {"plan": [...]}.
      2. one executor call per step — prompt carries the step text plus ALL
         results so far; model returns {"tool", "args"}; output appended.
      3. an output starting "error:" is a failure:
           - first failure  → exactly one replan call ("Task:", the failure,
             the progress so far), new plan replaces the old one, outputs reset;
           - any later failure → stop. reason "failed". NO second replan.
      4. all steps succeed → reason "completed", answer = last output.
    """
    # TODO(step 7)
    raise NotImplementedError


# --------------------------------------------------------------------------- reflexion
@dataclass
class ReflexionResult:
    success: bool = False
    answer: Any = None                              # best effort = last candidate
    trials: int = 0
    reflections: list[str] = field(default_factory=list)
    reason: str = "exhausted"       # "pass" | "exhausted"


def reflexion(model: FakeLLM,
              task_fn: Callable[[Any], bool],
              max_trials: int = 3,
              task: str = "") -> ReflexionResult:
    """Reflexion outer loop. `task_fn` is the external verdict (returns bool).

    Per trial:
      1. answer call — user prompt with the task; when reflections exist they
         are embedded under "Feedback from previous attempts:" as "- <r>" lines.
         Model returns {"answer": ...}.
      2. task_fn(answer) passes → ReflexionResult(True, answer, trial,
         reflections, "pass"). No reflection call on success.
      3. otherwise one reflection call (prompt contains "did not pass") —
         skipped after the FINAL failed trial, since no next attempt exists
         to consume it; the model returns {"reflection": "..."} and non-empty
         ones accumulate in .reflections, shaping the NEXT trial's prompt.

    Trials exhausted without passing → best-effort result: the LAST candidate
    answer, success=False, trials=max_trials, reason="exhausted".
    """
    # TODO(step 8)
    raise NotImplementedError
