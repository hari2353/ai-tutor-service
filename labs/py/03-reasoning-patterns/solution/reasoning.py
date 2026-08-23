"""Lab 03 — reference solution."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Callable


# --------------------------------------------------------------------------- fake model
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


# --------------------------------------------------------------------------- helpers
def _stringify(out: Any) -> str:
    if isinstance(out, str):
        return out
    try:
        return json.dumps(out, sort_keys=True)
    except (TypeError, ValueError):
        return repr(out)


def _dispatch(tools: dict[str, Callable[[dict], Any]], name: Any, args: dict) -> str:
    fn = tools.get(name)
    if fn is None:
        return f"error: unknown tool {name}"
    try:
        return _stringify(fn(copy.deepcopy(args)))
    except Exception as exc:          # noqa: BLE001 — the harness owns failures
        return f"error: {exc}"


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
    tools = dict(tools)
    messages: list[dict] = [{"role": "user", "content": task}]
    trace: list[str] = []
    for step in range(max_steps):
        response = model.complete([dict(m) for m in messages])
        thought = str(response.get("thought", "")).strip()
        trace.append(f"Thought: {thought}")

        if "final" in response:
            answer = str(response["final"])
            trace.append(f"Final: {answer}")
            return ReactResult(answer=answer, trace=trace,
                               steps=step + 1, reason="final")

        name = response.get("tool")
        args = copy.deepcopy(response.get("args") or {})
        trace.append(f"Action: {name}({_stringify(args)})")
        observation = _dispatch(tools, name, args)
        trace.append(f"Observation: {observation}")

        messages.append({"role": "assistant",
                         "content": f"Thought: {thought}\nAction: {name}({_stringify(args)})"})
        messages.append({"role": "user",
                         "content": f"Observation: {observation}"})

    return ReactResult(answer=None, trace=trace,
                       steps=max_steps, reason="budget")


# --------------------------------------------------------------------------- plan-execute
@dataclass
class PlanExecuteResult:
    plan: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    answer: str | None = None
    replans: int = 0
    reason: str = "completed"


def _parse_plan(response: dict) -> list[str]:
    plan = response.get("plan")
    if not isinstance(plan, list):
        return []
    return [str(s) for s in plan]


def plan_execute(model: FakeLLM,
                 tools: dict[str, Callable[[dict], Any]],
                 task: str = "") -> PlanExecuteResult:
    tools = dict(tools)
    replans = 0

    planner_prompt = [{"role": "user",
                       "content": f"Task: {task}\nList the ordered steps to solve it."}]
    plan = _parse_plan(model.complete(planner_prompt))
    if not plan:
        return PlanExecuteResult(plan=[], outputs=[], answer=None,
                                 replans=0, reason="failed")

    while True:
        outputs: list[str] = []
        failure: tuple[str, str] | None = None
        for step in plan:
            results_block = "\n".join(f"- {o}" for o in outputs) if outputs else "(none yet)"
            executor_prompt = [{"role": "user", "content":
                                (f"Task: {task}\n\nStep: {step}\n"
                                 f"Results so far:\n{results_block}\n\n"
                                 "Call one tool with JSON args.")}]
            response = model.complete(executor_prompt)
            if "tool" in response:
                observation = _dispatch(tools, response["tool"],
                                        copy.deepcopy(response.get("args") or {}))
            else:
                observation = "error: malformed response " + _stringify(response)
            outputs.append(observation)
            if observation.startswith("error:"):
                failure = (step, observation)
                break

        if failure is None:
            return PlanExecuteResult(plan=list(plan), outputs=outputs,
                                     answer=outputs[-1] if outputs else None,
                                     replans=replans, reason="completed")

        step, obs = failure
        if replans >= 1:
            return PlanExecuteResult(plan=list(plan), outputs=outputs,
                                     answer=None, replans=replans, reason="failed")

        progress_block = "\n".join(f"- {o}" for o in outputs) or "(none)"
        replan_prompt = [{"role": "user", "content":
                          (f"Task: {task}\n\nThe plan failed.\n"
                           f"Failing step: {step}\nFailure: {obs}\n"
                           f"Progress so far:\n{progress_block}\n\n"
                           "Issue a revised plan.")}]
        plan = _parse_plan(model.complete(replan_prompt))
        replans += 1
        if not plan:
            return PlanExecuteResult(plan=[], outputs=[], answer=None,
                                     replans=replans, reason="failed")


# --------------------------------------------------------------------------- reflexion
@dataclass
class ReflexionResult:
    success: bool = False
    answer: Any = None
    trials: int = 0
    reflections: list[str] = field(default_factory=list)
    reason: str = "exhausted"


def reflexion(model: FakeLLM,
              task_fn: Callable[[Any], bool],
              max_trials: int = 3,
              task: str = "") -> ReflexionResult:
    reflections: list[str] = []
    answer: Any = None
    for trial in range(1, max_trials + 1):
        content = task or "Solve the task."
        if reflections:
            feedback = "\n".join(f"- {r}" for r in reflections)
            content += f"\n\nFeedback from previous attempts:\n{feedback}"

        response = model.complete([{"role": "user", "content": content}])
        answer = response.get("answer", response.get("final"))
        if task_fn(answer):
            return ReflexionResult(success=True, answer=answer, trials=trial,
                                   reflections=list(reflections), reason="pass")

        if trial < max_trials:
            reflect_prompt = [{"role": "user", "content":
                               (f"Candidate answer: {_stringify(answer)}\n"
                                "The attempt above did not pass. "
                                "State what went wrong and what to try next.")}]
            rresponse = model.complete(reflect_prompt)
            refl = rresponse.get("reflection")
            if isinstance(refl, str) and refl.strip():
                reflections.append(refl.strip())

    return ReflexionResult(success=False, answer=answer, trials=max_trials,
                           reflections=list(reflections), reason="exhausted")
