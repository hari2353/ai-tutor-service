"""Lab 12 — multi-agent topologies as composable orchestrators. Fill in every TODO.

Every "agent" is an injectable callable — no LLM, no I/O, no sleeps:
  * workers / proposers / stages:  fn(task) -> result
  * blackboard agents:             fn(state) -> state-update dict

A topology adds no intelligence, only routing, sequencing, and failure
containment at the seams. The tests define done.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Task = Any
Worker = Callable[[Task], Any]


# --------------------------------------------------------------------------- errors
class StageError(Exception):
    """A pipeline stage's controlled abort signal. Any other exception is a bug."""


class PipelineAborted(StageError):
    """Raised by Pipeline.run when a stage raises StageError.

    Carries the partial trace: .trace (outputs of completed stages, in order),
    .stage_index (the failing stage), .error (the original StageError).
    """

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
    """Per-worker crash report. Supervisor.broadcast returns these in place of results."""
    worker: str
    error: BaseException


# --------------------------------------------------------------------------- supervisor
class Supervisor:
    """Central router over named workers. Workers never talk to each other."""

    def __init__(self, workers: dict[str, Worker]) -> None:
        self.workers = dict(workers)

    def dispatch(self, task: Task, worker_name: str):
        """Route the task to one named worker and return its result.

        Unknown worker_name -> RoutingError.
        """
        # TODO(step 1)
        raise NotImplementedError

    def broadcast(self, task: Task) -> dict:
        """Run every worker on the task; return {name: result}.

        A worker that raises is caught and reported under its own name as
        Failure(worker, error); every other worker still runs.
        """
        # TODO(step 2)
        raise NotImplementedError


# --------------------------------------------------------------------------- pipeline
class Pipeline:
    """Sequential stages; each stage's output is the next stage's input."""

    def __init__(self, stages: list[Worker]) -> None:
        self.stages = list(stages)

    def run(self, task: Task):
        """Feed the task through every stage; return the final output.

        A stage raising StageError aborts the run: raise PipelineAborted
        carrying the partial trace (outputs of completed stages only; stages
        after the failure never run). Any other exception propagates raw —
        StageError is the protocol, the rest are bugs.
        """
        # TODO(step 3)
        raise NotImplementedError


# --------------------------------------------------------------------------- debate
class Debate:
    """N proposers answer independently; a judge picks a winner."""

    def __init__(self, proposers: list[Worker], judge: Callable) -> None:
        self.proposers = list(proposers)
        self.judge = judge

    def run(self, task: Task):
        """Every proposer sees the same task; judge(proposals, task) returns
        the winning index. Return (winner_index, proposals).
        """
        # TODO(step 4)
        raise NotImplementedError


# --------------------------------------------------------------------------- blackboard
class Blackboard:
    """Shared state dict; agents read it and return update dicts."""

    def __init__(self, agents: list[Callable[[dict], dict]],
                 max_rounds: int = 3) -> None:
        self.agents = list(agents)
        self.max_rounds = max_rounds

    def run(self, initial_state: dict | None = None):
        """Apply each agent's update dict sequentially, in registration order,
        until a full round produces no changes — or max_rounds is hit.

        An agent sees earlier agents' writes within the same round. An empty
        update dict means "no contribution". Return (final_state, rounds_used);
        the final changeless round counts.
        """
        # TODO(step 5)
        raise NotImplementedError


# --------------------------------------------------------------------------- router
class Router:
    """A classifier picks the worker; the router executes it."""

    def __init__(self, classifier: Callable[[Task], str],
                 workers: dict[str, Worker]) -> None:
        self.classifier = classifier
        self.workers = dict(workers)

    def route(self, task: Task):
        """classifier(task) -> worker name; run that worker, return its result.

        Unknown route -> RoutingError.
        """
        # TODO(step 6)
        raise NotImplementedError
