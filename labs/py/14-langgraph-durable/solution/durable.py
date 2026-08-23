"""Lab 14 — durable graphs: checkpointer, resume, interrupt()/HITL, time travel.

A mini node-runner (pure stdlib) that proves the curriculum claim: durability,
human-in-the-loop, crash recovery and time travel are all the same feature —
a full state snapshot written after every node, keyed by (thread_id, step).

Rules:
  * The runner checkpoints after EVERY completed node — pending writes first,
    then the full snapshot (the langgraph commit order).
  * Resume loads the last checkpoint and skips nodes in the state's meta
    completed log. Completed work is never re-executed.
  * SimulatedCrash writes NOTHING. HumanInterrupt pauses with status
    waiting_human. get_state(at_step=k) is a read-only time-travel view.
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
    """ctx.interrupt() works by raising. The runner catches ONLY this type —
    a bare `except Exception` in a node would swallow the pause."""

    def __init__(self, payload: Any) -> None:
        super().__init__(f"interrupt: {payload!r}")
        self.payload = payload


class NotWaitingError(Exception):
    """resume() on a thread that is not status='waiting_human' (double-resume included)."""


# ------------------------------------------------------------------ injection
class FlakyCrash:
    """Injectable crash_fn: raises SimulatedCrash n times, then passes forever.

    Hold onto the instance across invokes — it stands in for a flag that gets
    cleared between processes.
    """

    def __init__(self, n: int) -> None:
        self.remaining = int(n)
        self.raised = 0

    def __call__(self) -> None:
        if self.remaining > 0:
            self.remaining -= 1
            self.raised += 1
            raise SimulatedCrash(f"simulated crash ({self.remaining} retries left)")


# ----------------------------------------------------------------------- ctx
@dataclass
class Ctx:
    """Handed to every node invocation."""

    state: Mapping           # deep-copied read view of committed state
    config: dict             # {"configurable": {"thread_id": ...}}
    input: Any = None        # human_input when this node was interrupted

    def interrupt(self, payload: Any) -> None:
        """Pause the thread durably. Payload must be JSON-serialisable."""
        raise HumanInterrupt(payload)


# ------------------------------------------------------------------ snapshots
@dataclass
class Snapshot:
    values: dict                      # FULL state incl. META (completed log inside)
    next: tuple                       # nodes to run next; () means done
    step: int
    checkpoint_id: str = ""
    parent_id: str | None = None
    status: str = "running"           # running | waiting_human | done
    completed: tuple = ()             # node names already executed, in order
    interrupt: dict | None = None     # {"node": name, "payload": ...} when waiting


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
    """Four-method saver keyed (thread_id, step).

    Stores full snapshots plus per-task pending writes. Deepcopies on write
    AND on read, so no caller can corrupt the store through a returned object.
    """

    def __init__(self) -> None:
        self._ckpts: dict[tuple[str, int], Snapshot] = {}
        self._writes: dict[tuple[str, int, str], dict] = {}

    def put(self, thread_id: str, step: int, snapshot: Snapshot) -> str:
        """Store one full snapshot. Returns its checkpoint_id."""
        cid = uuid.uuid4().hex
        prev = self._ckpts.get((thread_id, step - 1))
        snap = copy.deepcopy(snapshot)
        snap.step = step
        snap.checkpoint_id = cid
        snap.parent_id = prev.checkpoint_id if prev else None
        self._ckpts[(thread_id, step)] = snap
        return cid

    def put_writes(self, thread_id: str, step: int, task_id: str, writes: dict) -> None:
        """Persist one finished task's writes against `step` BEFORE the snapshot
        that will contain them commits. This is what lets a sibling (here: an
        orphaned task whose snapshot never landed) recover without re-executing."""
        self._writes[(thread_id, step, task_id)] = copy.deepcopy(dict(writes))

    def get_tuple(self, thread_id: str, at_step: int | None = None) -> CheckpointTuple | None:
        if at_step is not None:
            steps = [at_step] if (thread_id, at_step) in self._ckpts else []
        else:
            steps = self.steps(thread_id)[-1:]
        if not steps:
            return None
        step = steps[0]
        snap = self._ckpts[(thread_id, step)]
        pw = tuple(
            (task_id, copy.deepcopy(w))
            for (tid, s, task_id), w in sorted(self._writes.items())
            if tid == thread_id and s == step
        )
        return CheckpointTuple(copy.deepcopy(snap), pw)

    def list(self, thread_id: str) -> list[CheckpointTuple]:
        return [
            self.get_tuple(thread_id, at_step=step)
            for step in self.steps(thread_id)
        ]

    def steps(self, thread_id: str) -> list[int]:
        return sorted(s for (t, s) in self._ckpts if t == thread_id)


# ---------------------------------------------------------------------- graph
class DurableGraph:
    """Linear mini-graph with durable resume.

    nodes: {name: fn(state_view, ctx) -> updates_dict | None}
    edges: {START: entry, name: successor | END, ...}   (one target per edge)
    """

    def __init__(self, nodes: dict[str, Callable], edges: dict,
                 checkpointer: MemoryCheckpointer, thread_id: str) -> None:
        self.nodes = dict(nodes)
        self.edges = {}
        for src, dst in dict(edges).items():
            self.edges[src] = [dst] if isinstance(dst, str) else list(dst or [])
        for src, targets in self.edges.items():
            if len(targets) > 1:
                raise ValueError(
                    f"edge from {src!r}: this lab runs ONE node per super-step; "
                    "fan-out is a stretch goal")
            for t in targets:
                if t != END and t not in self.nodes:
                    raise ValueError(f"{src!r} points at unknown node {t!r}")
        missing = sorted(n for n in self.nodes if n not in self.edges)
        if missing:
            raise ValueError(f"nodes without an outgoing edge: {missing}")
        if len(self.edges.get(START, [])) != 1:
            raise ValueError("edges must map START to exactly one entry node")
        self.checkpointer = checkpointer
        self.thread_id = thread_id

    # ------------------------------------------------------------- public API
    def invoke(self, values: dict | None = None) -> RunResult:
        """Run (fresh thread + values) or RESUME (existing thread). Resuming
        skips every node already in the checkpointed completed log."""
        tup = self.checkpointer.get_tuple(self.thread_id)
        if tup is None:
            if values is None:
                raise ValueError(
                    f"thread {self.thread_id!r} has no checkpoints: "
                    "pass initial values to invoke()")
            state = dict(values)
            state[META] = {"completed": [], "status": "running", "interrupt": None}
            nxt = self._entry()
            self._save(state, nxt)          # input checkpoint, step 0
            return self._advance(state, nxt, pending_input=None)
        if tup.snapshot.status == "waiting_human":
            payload = (tup.snapshot.interrupt or {}).get("payload")
            return RunResult("waiting_human", copy.deepcopy(tup.snapshot.values),
                             [], interrupt_payload=payload)
        state, nxt = self._apply_pending(tup)
        return self._advance(state, nxt, pending_input=None)

    def resume(self, thread_id: str, human_input: Any) -> RunResult:
        """Deliver human_input to the waiting node. The node re-runs FROM ITS
        TOP (curriculum Rule 2): everything before ctx.interrupt() happens again."""
        if thread_id != self.thread_id:
            raise NotWaitingError(f"graph is bound to thread {self.thread_id!r}")
        tup = self.checkpointer.get_tuple(thread_id)
        if tup is None or tup.snapshot.status != "waiting_human":
            raise NotWaitingError(f"thread {thread_id!r} is not waiting on a human")
        state = tup.snapshot.values
        nxt = tuple(tup.snapshot.next)
        state[META]["status"] = "running"
        state[META]["interrupt"] = None
        return self._advance(state, nxt, pending_input=human_input)

    def get_state(self, thread_id: str | None = None, *,
                  at_step: int | None = None) -> Snapshot:
        """Latest snapshot, or time travel to at_step=k. Read-only by copy:
        mutating what you get back cannot touch the store."""
        tid = thread_id if thread_id is not None else self.thread_id
        tup = self.checkpointer.get_tuple(tid, at_step=at_step)
        if tup is None:
            where = f" at step {at_step}" if at_step is not None else ""
            raise KeyError(f"no checkpoint for thread {tid!r}{where}")
        return tup.snapshot

    # ---------------------------------------------------------------- engine
    def _apply_pending(self, tup: CheckpointTuple) -> tuple[dict, tuple]:
        """Fold orphaned pending writes into state before continuing: a task
        whose writes landed but whose snapshot never did does NOT re-execute."""
        state = tup.snapshot.values
        nxt = tuple(tup.snapshot.next)
        meta = state[META]
        applied = False
        for task_id, writes in tup.pending_writes:
            if task_id in self.nodes and task_id not in meta["completed"]:
                meta["completed"].append(task_id)
                state.update(copy.deepcopy(writes))
                nxt = self._succ(task_id)
                applied = True
        if applied:
            meta["status"] = "running"
            self._save(state, nxt)
        return state, nxt

    def _advance(self, state: dict, nxt: tuple, pending_input: Any) -> RunResult:
        executed: list[str] = []
        completed = state[META]["completed"]
        hops, limit = 0, len(self.nodes) + 2
        while nxt:
            hops += 1
            if hops > limit:
                raise RuntimeError("cycle detected in edges")
            name = nxt[0]
            if name in completed:                    # durable skip
                nxt = self._succ(name)
                continue
            ctx = Ctx(state=copy.deepcopy(state), config=self._cfg(),
                      input=pending_input)
            pending_input = None
            try:
                updates = self.nodes[name](ctx.state, ctx) or {}
            except HumanInterrupt as hum:            # pause is a raise — catch narrowly
                state[META]["status"] = "waiting_human"
                state[META]["interrupt"] = {"node": name, "payload": hum.payload}
                self._save(state, (name,))
                return RunResult("waiting_human", copy.deepcopy(state), executed,
                                 interrupt_payload=hum.payload)
            except SimulatedCrash as why:            # write nothing; last ckpt intact
                return RunResult("crashed", copy.deepcopy(state), executed,
                                 error=str(why))
            state.update(updates)
            completed.append(name)
            state[META]["status"] = "running"
            nxt = self._succ(name)
            if not nxt:
                state[META]["status"] = "done"
            step = self._latest_step() + 1
            self.checkpointer.put_writes(self.thread_id, step - 1, name, updates)
            self._save(state, nxt, step=step)
            executed.append(name)
        return RunResult("done", copy.deepcopy(state), executed)

    # --------------------------------------------------------------- helpers
    def _save(self, state: dict, nxt: tuple, step: int | None = None) -> str:
        if step is None:
            step = self._latest_step() + 1
        snap = Snapshot(values=state, next=tuple(nxt), step=step,
                        status=state[META]["status"],
                        completed=tuple(state[META]["completed"]),
                        interrupt=state[META].get("interrupt"))
        return self.checkpointer.put(self.thread_id, step, snap)

    def _latest_step(self) -> int:
        steps = self.checkpointer.steps(self.thread_id)
        return steps[-1] if steps else -1

    def _succ(self, name: str) -> tuple:
        targets = self.edges[name]
        return () if targets in ([END], []) else tuple(targets)

    def _entry(self) -> tuple:
        return tuple(self.edges[START])

    def _cfg(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}
