"""Lab 02 — reference solution."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Callable


class FakeLLM:
    def __init__(self, script: list[dict]) -> None:
        self.script = copy.deepcopy(script)
        self.i = 0
        self.prompts: list[list[dict]] = []

    def complete(self, messages: list[dict]) -> dict:
        self.prompts.append([dict(m) for m in messages])
        if self.i >= len(self.script):
            return {"final": ""}
        out = copy.deepcopy(self.script[self.i])
        self.i += 1
        return out

    def consumed(self) -> int:
        return self.i

    def remaining(self) -> int:
        return len(self.script) - self.i


@dataclass
class Result:
    answer: str | None = None
    steps: int = 0
    reason: str = "budget"


def _stringify(out: Any) -> str:
    if isinstance(out, str):
        return out
    try:
        return json.dumps(out, sort_keys=True)
    except (TypeError, ValueError):
        return repr(out)


class AgentLoop:
    def __init__(self, model: FakeLLM,
                 tools: dict[str, Callable[[dict], Any]],
                 max_steps: int = 8) -> None:
        self.model = model
        self.max_steps = max_steps
        self._tools: dict[str, Callable[[dict], Any]] = dict(tools)

    def run(self, task: str) -> Result:
        messages: list[dict] = [{"role": "user", "content": task}]
        for step in range(self.max_steps):
            response = self.model.complete([dict(m) for m in messages])

            if "final" in response:
                return Result(answer=str(response["final"]),
                              steps=step + 1, reason="final")

            if "tool" in response:
                name = response["tool"]
                args = copy.deepcopy(response.get("args") or {})
                observation = self._dispatch(name, args)
            else:
                observation = ("error: malformed response "
                               + _stringify(response))

            messages.append({"role": "assistant",
                             "content": _stringify(response)})
            messages.append({"role": "user",
                             "content": f"Observation: {observation}"})

        return Result(answer=None, steps=self.max_steps, reason="budget")

    def _dispatch(self, name: str, args: dict) -> str:
        fn = self._tools.get(name)
        if fn is None:
            return f"error: unknown tool {name}"
        call_args = copy.deepcopy(args)
        try:
            out = fn(call_args)
        except Exception as exc:          # noqa: BLE001 — the harness owns failures
            return f"error: {exc}"
        return _stringify(out)
