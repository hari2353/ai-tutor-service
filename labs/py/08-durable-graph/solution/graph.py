"""Lab 08 -- a minimal durable state graph, built from scratch (no
LangGraph dependency) so the mechanism underneath the framework is visible.

The whole trick is ONE idea: after every node finishes, persist a
checkpoint (state + "what runs next") before moving on. Resuming a thread
means loading the latest checkpoint and picking up at `next_node` -- nodes
that already have a checkpoint recorded past them never run again. A node
that was *in flight* when the process died has no such checkpoint, so it
reruns from its first line on resume. That's not a bug to work around --
it's the actual contract LangGraph gives you, which is why non-idempotent
side effects before an interrupt or a crash point are a correctness bug in
the node, not in the framework.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

END = "__end__"
RESUME_KEY = "__resume_value__"


# --------------------------------------------------------------------------- checkpoint model
@dataclass
class Checkpoint:
    thread_id: str
    step: int
    state: dict
    next_node: str                 # node to run next, or END
    status: str = "running"        # "running" | "interrupted" | "done"
    interrupt_payload: Any = None


class Checkpointer(Protocol):
    def save(self, checkpoint: Checkpoint) -> None: ...
    def load_latest(self, thread_id: str) -> Optional[Checkpoint]: ...
    def list_checkpoints(self, thread_id: str) -> list[Checkpoint]: ...


class InMemoryCheckpointer:
    """A dict in a process. Gone on restart -- included so a test can prove
    that's exactly the property that makes SqliteCheckpointer different."""

    def __init__(self) -> None:
        self._store: dict[str, list[Checkpoint]] = {}

    def save(self, checkpoint: Checkpoint) -> None:
        self._store.setdefault(checkpoint.thread_id, []).append(checkpoint)

    def load_latest(self, thread_id: str) -> Optional[Checkpoint]:
        items = self._store.get(thread_id)
        return items[-1] if items else None

    def list_checkpoints(self, thread_id: str) -> list[Checkpoint]:
        return list(self._store.get(thread_id, []))


class SqliteCheckpointer:
    """Persists checkpoints to a SQLite file via stdlib sqlite3. A fresh
    SqliteCheckpointer pointed at the same file (a new connection, no
    shared Python state) can resume a thread -- that's what makes it a
    legitimate stand-in for surviving an actual process restart."""

    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints ("
            " thread_id TEXT NOT NULL,"
            " step INTEGER NOT NULL,"
            " state TEXT NOT NULL,"
            " next_node TEXT NOT NULL,"
            " status TEXT NOT NULL,"
            " interrupt_payload TEXT,"
            " PRIMARY KEY (thread_id, step)"
            ")"
        )
        self.conn.commit()

    def save(self, checkpoint: Checkpoint) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO checkpoints "
            "(thread_id, step, state, next_node, status, interrupt_payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (checkpoint.thread_id, checkpoint.step, json.dumps(checkpoint.state),
             checkpoint.next_node, checkpoint.status,
             json.dumps(checkpoint.interrupt_payload)),
        )
        self.conn.commit()

    def load_latest(self, thread_id: str) -> Optional[Checkpoint]:
        row = self.conn.execute(
            "SELECT thread_id, step, state, next_node, status, interrupt_payload "
            "FROM checkpoints WHERE thread_id = ? ORDER BY step DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    def list_checkpoints(self, thread_id: str) -> list[Checkpoint]:
        rows = self.conn.execute(
            "SELECT thread_id, step, state, next_node, status, interrupt_payload "
            "FROM checkpoints WHERE thread_id = ? ORDER BY step ASC",
            (thread_id,),
        ).fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    @staticmethod
    def _row_to_checkpoint(row) -> Checkpoint:
        thread_id, step, state_json, next_node, status, payload_json = row
        return Checkpoint(
            thread_id=thread_id, step=step, state=json.loads(state_json),
            next_node=next_node, status=status,
            interrupt_payload=json.loads(payload_json) if payload_json is not None else None,
        )


# --------------------------------------------------------------------------- interrupt / results
class Interrupt(Exception):
    """A node raises this to pause the run without it being treated as a
    crash. The graph saves a checkpoint recording the interrupted node and
    returns control to the caller instead of propagating."""

    def __init__(self, payload: Any) -> None:
        super().__init__(str(payload))
        self.payload = payload


@dataclass
class RunResult:
    status: str                      # "done" | "interrupted"
    state: dict
    next_node: Optional[str]
    interrupt_payload: Any = None


# --------------------------------------------------------------------------- graph
class StateGraph:
    def __init__(self, checkpointer: Checkpointer) -> None:
        self.nodes: dict[str, Callable[[dict], dict]] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, Callable[[dict], str]] = {}
        self.entry_point: Optional[str] = None
        self.checkpointer = checkpointer

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> None:
        self.nodes[name] = fn

    def set_entry_point(self, name: str) -> None:
        self.entry_point = name

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges[from_node] = to_node

    def add_conditional_edges(self, from_node: str, router: Callable[[dict], str]) -> None:
        """`router(state)` returns the name of the next node to run (or
        END). Overrides any fixed edge registered for the same source."""
        self.conditional_edges[from_node] = router

    def _next_after(self, node_name: str, state: dict) -> str:
        if node_name in self.conditional_edges:
            return self.conditional_edges[node_name](state)
        return self.edges.get(node_name, END)

    def run(self, thread_id: str, initial_state: dict) -> RunResult:
        if self.entry_point is None:
            raise ValueError("StateGraph has no entry point -- call set_entry_point()")
        checkpoint = Checkpoint(thread_id=thread_id, step=0, state=dict(initial_state),
                                 next_node=self.entry_point, status="running")
        self.checkpointer.save(checkpoint)
        return self._execute(checkpoint)

    def resume(self, thread_id: str, resume_value: Any = None) -> RunResult:
        checkpoint = self.checkpointer.load_latest(thread_id)
        if checkpoint is None:
            raise KeyError(f"no checkpoint for thread '{thread_id}' -- nothing to resume")
        if checkpoint.status == "done":
            return RunResult(status="done", state=checkpoint.state, next_node=None)

        state = dict(checkpoint.state)
        if resume_value is not None:
            state[RESUME_KEY] = resume_value
        fresh = Checkpoint(thread_id=thread_id, step=checkpoint.step, state=state,
                            next_node=checkpoint.next_node, status="running")
        return self._execute(fresh)

    def _execute(self, checkpoint: Checkpoint) -> RunResult:
        # Defensive copy: node functions receive `state` and must return a
        # dict of updates rather than mutating in place, but we don't trust
        # that -- a mutation must never corrupt an already-saved checkpoint
        # (InMemoryCheckpointer stores the object reference, not a copy).
        state = dict(checkpoint.state)
        node_name = checkpoint.next_node
        step = checkpoint.step

        while node_name != END:
            fn = self.nodes.get(node_name)
            if fn is None:
                raise KeyError(f"unknown node '{node_name}'")

            try:
                update = fn(state)
            except Interrupt as intr:
                snapshot = {k: v for k, v in state.items() if k != RESUME_KEY}
                cp = Checkpoint(thread_id=checkpoint.thread_id, step=step, state=snapshot,
                                 next_node=node_name, status="interrupted",
                                 interrupt_payload=intr.payload)
                self.checkpointer.save(cp)
                return RunResult(status="interrupted", state=snapshot, next_node=node_name,
                                  interrupt_payload=intr.payload)

            state = {**state, **update}
            state.pop(RESUME_KEY, None)
            step += 1
            node_name = self._next_after(node_name, state)

            cp = Checkpoint(thread_id=checkpoint.thread_id, step=step, state=state,
                             next_node=node_name, status="running" if node_name != END else "done")
            self.checkpointer.save(cp)

        return RunResult(status="done", state=state, next_node=None)
