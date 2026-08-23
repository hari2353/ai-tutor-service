"""Lab 02 — an agent loop from scratch. Fill in every TODO. Tests define done.

Rules:
  * Deterministic only — no time, no randomness. The budget is steps.
  * Tool errors and unknown tools become observations; nothing propagates.
  * Never mutate the caller's tools dict or the scripted args.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable


# --------------------------------------------------------------------------- fake model
class FakeLLM:
    """Deterministic model: pops queued JSON responses, records every prompt.

    Each scripted response is either {"tool": name, "args": {...}} or
    {"final": "answer"}. When the script is exhausted it answers {"final": ""}.
    """

    def __init__(self, script: list[dict]) -> None:
        self.script = copy.deepcopy(script)
        self.i = 0
        self.prompts: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> dict:
        """Show the transcript to the 'model' and return the next queued response.

        Records `messages` in self.prompts (verbatim) before answering.
        """
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


# --------------------------------------------------------------------------- result
@dataclass
class Result:
    answer: str | None = None
    steps: int = 0
    reason: str = "budget"          # "final" | "budget"


# --------------------------------------------------------------------------- the loop
class AgentLoop:
    def __init__(self, model: FakeLLM,
                 tools: dict[str, Callable[[dict], Any]],
                 max_steps: int = 8) -> None:
        self.model = model
        self.max_steps = max_steps
        # TODO(step 4): store the tools WITHOUT aliasing the caller's dict.

    def run(self, task: str) -> Result:
        """prompt → model → parse → dispatch tool or finish.

        One model call == one step. Unknown tool → observation
        "error: unknown tool <name>"; a raising tool → observation
        "error: <exception message>". Budget exhausted →
        Result(None, max_steps, "budget").
        """
        # TODO(step 5): build the first user message from `task`, then loop.
        raise NotImplementedError

    def _dispatch(self, name: str, args: dict) -> str:
        """Resolve the tool, call it with a COPY of args, stringify the output.

        Returns the observation string in every case (never raises).
        """
        # TODO(step 6)
        raise NotImplementedError
