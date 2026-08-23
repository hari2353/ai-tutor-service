"""Lab 14 — durable graphs. Fill in every TODO. Tests define done.

Rules:
  * The runner checkpoints after EVERY completed node — pending writes first,
    then the full snapshot.
  * Resume skips nodes listed in state[META]["completed"].
  * SimulatedCrash must write NOTHING; HumanInterrupt saves status=waiting_human.
  * Everything the checkpointer returns is a deep copy.
"""
from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Callable

START = "__start__"
END = "__end__"

META = "_meta"  # reserved state key: {"completed": [...], "status": ..., "interrupt": ...}


# --------------------------------------------------------------------- errors
class SimulatedCrash(Exception):
    """Injected process death. Nothing is written; the last checkpoint stays intact."""


class HumanInterrupt(Exception):
    """ctx.interrupt() works by raising. The runner catches ONLY this type."""

    # TODO(step 0a): __init__(self, payload) — store .payload, call super().__init__
    def __init__(self, payload: Any) -> None:
        raise NotImplementedError


class NotWaitingError(Exception):
    """resume() on a thread that is not status='waiting_human' (double-resume included)."""


# ------------------------------------------------------------------ injection
class FlakyCrash:
    """Injectable crash_fn: raises SimulatedCrash n times, then passes forever."""

    def __init__(self, n: int) -> None:
        self.raised = 0
        # TODO(step 0b): track how many crashes are left (call it `remaining`)
        raise NotImplementedError

    def __call__(self) -> None:
        # TODO(step 0c): while any remain: decrement, count a raise,
        #                raise SimulatedCrash. Otherwise pass.
        raise NotImplementedError


# ----------------------------------------------------------------------- ctx
@dataclass
class Ctx:
    """Handed to every node invocation."""

    state: Mapping           # deep-copied read view of committed state
    config: dict             # {"configurable": {"thread_id": ...}}
    input: Any = None        # human_input when this node was interrupted

    def interrupt(self, payload: Any) -> None:
        """Pause the thread durably. Payload must be JSON-serialisable."""
        # TODO(step 1): raise HumanInterrupt(payload)
        raise NotImplementedError


# ------------------------------------------------------------------ snapshots
@dataclass
class Snapshot:
    values: dict                      # FULL state incl. META
    next: tuple                       # nodes to run next; () means done
    step: int
    checkpoint_id: str = ""
    parent_id: str | None = None
    status: str = "running"           # running | waiting_human | done
    completed: tuple = ()
    interrupt: dict | None = None     # {"node": ..., "payload": ...} when waiting


@dataclass
class CheckpointTuple:
    snapshot: Snapshot
    pending_writes: tuple             # ((task_id, writes_dict), ...) attached to this step


@dataclass
class RunResult:
    status: str                       # done | waiting_human | crashed
    state: dict                       # defensive copy of current values
    executed: list                    # nodes executed during THIS invoke/resume
    interrupt_payload: Any = None
    error: str | None = None


# ---------------------------------------------------------------- checkpointer
class MemoryCheckpointer:
    """Four-method saver keyed (thread_id, step). Deepcopy on write AND read."""

    def __init__(self) -> None:
        self._ckpts: dict[tuple[str, int], Snapshot] = {}
        self._writes: dict[tuple[str, int, str], dict] = {}

    def put(self, thread_id: str, step: int, snapshot: Snapshot) -> str:
        """Store one full snapshot. Returns its checkpoint_id."""
        # TODO(step 2a): mint a uuid4().hex id; link parent_id to the checkpoint
        #                at (thread_id, step-1); deepcopy BEFORE storing; stamp
        #                step + checkpoint_id on the stored copy; return the id.
        raise NotImplementedError

    def put_writes(self, thread_id: str, step: int, task_id: str, writes: dict) -> None:
        """Persist one finished task's writes against `step` before its snapshot."""
        # TODO(step 2b): store a deepcopy of dict(writes) under
        #                (thread_id, step, task_id).
        raise NotImplementedError

    def get_tuple(self, thread_id: str, at_step: int | None = None) -> CheckpointTuple | None:
        """Latest tuple, or exactly at_step. Returns deep copies or None."""
        # TODO(step 2c): resolve target step (latest if at_step is None);
        #                collect this step's pending writes sorted by task_id;
        #                return CheckpointTuple(deepcopied snapshot, writes tuple).
        raise NotImplementedError

    def list(self, thread_id: str) -> list[CheckpointTuple]:
        """All tuples for the thread, ascending by step."""
        # TODO(step 2d)
        raise NotImplementedError

    def steps(self, thread_id: str) -> list[int]:
        """Sorted step numbers that exist for the thread."""
        # TODO(step 2e)
        raise NotImplementedError


# ---------------------------------------------------------------------- graph
class DurableGraph:
    """Linear mini-graph with durable resume.

    nodes: {name: fn(state_view, ctx) -> updates_dict | None}
    edges: {START: entry, name: successor | END, ...}   (one target per edge)
    """

    def __init__(self, nodes: dict[str, Callable], edges: dict,
                 checkpointer: MemoryCheckpointer, thread_id: str) -> None:
        # TODO(step 3a): normalise edges (str -> [str]); reject fan-out (>1 target),
        #                unknown targets and nodes without an outgoing edge;
        #                require exactly one START entry. Store checkpointer + thread_id.
        raise NotImplementedError

    # ------------------------------------------------------------- public API
    def invoke(self, values: dict | None = None) -> RunResult:
        """Run (fresh thread + values) or RESUME (existing thread)."""
        # TODO(step 4a): no checkpoints yet? require values, seed META
        #                ({"completed": [], "status": "running", "interrupt": None}),
        #                save the INPUT checkpoint at step 0, advance.
        # TODO(step 4b): existing thread waiting_human? return it unchanged
        #                (status waiting_human, interrupt payload surfaced, [] executed).
        # TODO(step 4c): existing running/done thread: apply orphaned pending
        #                writes, then advance from the last checkpoint.
        raise NotImplementedError

    def resume(self, thread_id: str, human_input: Any) -> RunResult:
        """Deliver human_input to the waiting node; it re-runs FROM ITS TOP."""
        # TODO(step 5): guard wrong thread / not-waiting with NotWaitingError;
        #               clear interrupt, reset status to running, advance with
        #               human_input delivered as ctx.input of the first node.
        raise NotImplementedError

    def get_state(self, thread_id: str | None = None, *,
                  at_step: int | None = None) -> Snapshot:
        """Latest snapshot, or time travel to at_step=k. KeyError if absent."""
        # TODO(step 6)
        raise NotImplementedError

    # ---------------------------------------------------------------- engine
    def _apply_pending(self, tup: CheckpointTuple) -> tuple[dict, tuple]:
        """Fold orphaned pending writes into state before continuing."""
        # TODO(step 7a): for each pending write whose task_id is a real node NOT
        #                in completed: merge writes, mark completed, retarget nxt
        #                to that node's successors; if anything applied, save a
        #                new checkpoint recording it.
        raise NotImplementedError

    def _advance(self, state: dict, nxt: tuple, pending_input: Any) -> RunResult:
        """The loop: skip completed, run node, checkpoint, repeat."""
        # TODO(step 7b): per node —
        #   * skip names already in completed (durable skip);
        #   * build Ctx with a DEEPCOPY of state and pending_input (once);
        #   * HumanInterrupt  -> META status waiting_human + interrupt record,
        #                        save checkpoint with next=(node,), return result;
        #   * SimulatedCrash  -> write NOTHING, return status 'crashed';
        #   * success         -> merge updates, append completed, set status done
        #                        when nxt empties, put_writes against the PARENT
        #                        step, then _save the full snapshot.
        raise NotImplementedError

    # --------------------------------------------------------------- helpers
    def _save(self, state: dict, nxt: tuple, step: int | None = None) -> str:
        # TODO(step 7c): default step = latest+1; build Snapshot carrying values,
        #                next, status, completed tuple, interrupt; checkpointer.put it.
        raise NotImplementedError

    def _latest_step(self) -> int:
        # TODO(step 7d): last known step for this thread, else -1
        raise NotImplementedError

    def _succ(self, name: str) -> tuple:
        # TODO(step 7e): () for END/empty edges, else the successor tuple
        raise NotImplementedError

    def _entry(self) -> tuple:
        # TODO(step 7f): the START edge's targets as a tuple
        raise NotImplementedError

    def _cfg(self) -> dict:
        # TODO(step 7g): {"configurable": {"thread_id": self.thread_id}}
        raise NotImplementedError
