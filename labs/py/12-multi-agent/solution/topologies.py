"""Lab 12 — reference solution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Task = Any
Worker = Callable[[Task], Any]


class StageError(Exception):
    """A pipeline stage's controlled abort signal."""


class PipelineAborted(StageError):
    def __init__(self, message: str, *, trace: list, stage_index: int,
                 error: BaseException) -> None:
        super().__init__(message)
        self.trace = list(trace)
        self.stage_index = stage_index
        self.error = error


class RoutingError(Exception):
    """No worker matches the requested route."""


@dataclass
class Failure:
    """Per-worker crash report."""
    worker: str
    error: BaseException


class Supervisor:
    def __init__(self, workers: dict[str, Worker]) -> None:
        self.workers = dict(workers)

    def dispatch(self, task: Task, worker_name: str):
        if worker_name not in self.workers:
            raise RoutingError(f"no worker named {worker_name!r}")
        return self.workers[worker_name](task)

    def broadcast(self, task: Task) -> dict:
        results: dict = {}
        for name, worker in self.workers.items():
            try:
                results[name] = worker(task)
            except Exception as exc:
                results[name] = Failure(worker=name, error=exc)
        return results


class Pipeline:
    def __init__(self, stages: list[Worker]) -> None:
        self.stages = list(stages)

    def run(self, task: Task):
        trace: list = []
        value = task
        for stage_index, stage in enumerate(self.stages):
            try:
                value = stage(value)
            except StageError as exc:
                raise PipelineAborted(
                    f"pipeline aborted at stage {stage_index}",
                    trace=trace, stage_index=stage_index, error=exc,
                ) from exc
            trace.append(value)
        return value


class Debate:
    def __init__(self, proposers: list[Worker], judge: Callable) -> None:
        self.proposers = list(proposers)
        self.judge = judge

    def run(self, task: Task):
        proposals = [propose(task) for propose in self.proposers]
        winner_index = self.judge(proposals, task)
        return winner_index, proposals


class Blackboard:
    def __init__(self, agents: list[Callable[[dict], dict]],
                 max_rounds: int = 3) -> None:
        self.agents = list(agents)
        self.max_rounds = max_rounds

    def run(self, initial_state: dict | None = None):
        state = dict(initial_state) if initial_state is not None else {}
        rounds_used = 0
        for _ in range(self.max_rounds):
            rounds_used += 1
            changed = False
            for agent in self.agents:
                update = agent(state) or {}
                if self._differs(state, update):
                    state.update(update)
                    changed = True
            if not changed:
                break
        return state, rounds_used

    @staticmethod
    def _differs(state: dict, update: dict) -> bool:
        return any(key not in state or state[key] != value
                   for key, value in update.items())


class Router:
    def __init__(self, classifier: Callable[[Task], str],
                 workers: dict[str, Worker]) -> None:
        self.classifier = classifier
        self.workers = dict(workers)

    def route(self, task: Task):
        worker_name = self.classifier(task)
        if worker_name not in self.workers:
            raise RoutingError(
                f"classifier routed {task!r} to unknown worker {worker_name!r}")
        return self.workers[worker_name](task)
