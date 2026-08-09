"""Lab 08 -- a minimal durable state graph, built from scratch (no
LangGraph dependency) so the mechanism underneath the framework is visible.
Fill in every TODO. Tests define done.

The whole trick is ONE idea: after every node finishes, persist a
checkpoint (state + "what runs next") before moving on. Resuming a thread
means loading the latest checkpoint and picking up at `next_node` -- nodes
that already have a checkpoint recorded past them never run again. A node
that was *in flight* when the process died has no such checkpoint, so it
reruns from its first line on resume. That's not a bug to work around --
it's the actual contract LangGraph gives you, which is why non-idempotent
side effects before an interrupt or a crash point are a correctness bug in
the node, not in the framework.

Rules:
  * Node functions receive `state` and return a dict of UPDATES -- they
    must not mutate `state` in place.
  * Only `Interrupt` pauses a run cleanly; any other exception from a node
    must propagate out of run()/resume() uncaught (that's the simulated
    crash) with NO new checkpoint written for the node that raised.
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
        # TODO(step 1a): append to self._store[checkpoint.thread_id]
        raise NotImplementedError

    def load_latest(self, thread_id: str) -> Optional[Checkpoint]:
        # TODO(step 1b): return the last checkpoint for thread_id, or None
        raise NotImplementedError

    def list_checkpoints(self, thread_id: str) -> list[Checkpoint]:
        # TODO(step 1c): return the full ordered list (empty list if none)
        raise NotImplementedError


class SqliteCheckpointer:
    """Persists checkpoints to a SQLite file via stdlib sqlite3. A fresh
    SqliteCheckpointer pointed at the same file (a new connection, no
    shared Python state) can resume a thread -- that's what makes it a
    legitimate stand-in for surviving an actual process restart."""

    def __init__(self, path: str) -> None:
        # TODO(step 2a): open a sqlite3 connection to `path` and create the
        # `checkpoints` table if it doesn't exist. Columns: thread_id TEXT,
        # step INTEGER, state TEXT (JSON), next_node TEXT, status TEXT,
        # interrupt_payload TEXT (JSON, nullable). PRIMARY KEY (thread_id, step).
        raise NotImplementedError

    def save(self, checkpoint: Checkpoint) -> None:
        # TODO(step 2b): INSERT OR REPLACE, json.dumps(state) and
        # json.dumps(interrupt_payload). Commit.
        raise NotImplementedError

    def load_latest(self, thread_id: str) -> Optional[Checkpoint]:
        # TODO(step 2c): SELECT ... ORDER BY step DESC LIMIT 1, json.loads
        # the state and interrupt_payload columns back into Python objects.
        raise NotImplementedError

    def list_checkpoints(self, thread_id: str) -> list[Checkpoint]:
        # TODO(step 2d): SELECT ... ORDER BY step ASC, same decoding as
        # load_latest for each row.
        raise NotImplementedError


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
        # TODO(step 3): if node_name has a conditional router registered,
        # call it with state and return its result. Otherwise look it up in
        # self.edges, defaulting to END if there's no edge at all.
        raise NotImplementedError

    def run(self, thread_id: str, initial_state: dict) -> RunResult:
        """TODO(step 4a):
          - if self.entry_point is None: raise ValueError
          - build the initial Checkpoint(thread_id, step=0,
            state=dict(initial_state), next_node=self.entry_point,
            status="running"), save it, then call self._execute(checkpoint)
        """
        raise NotImplementedError

    def resume(self, thread_id: str, resume_value: Any = None) -> RunResult:
        """TODO(step 4b):
          - load the latest checkpoint for thread_id; if None, raise KeyError
          - if its status is "done": return RunResult("done", state, None)
            immediately (resuming a finished thread is a no-op)
          - otherwise: copy its state; if resume_value is not None, stash it
            under state[RESUME_KEY]; build a fresh "running" Checkpoint with
            the SAME step and next_node as the loaded one, and call
            self._execute(fresh)
        """
        raise NotImplementedError

    def _execute(self, checkpoint: Checkpoint) -> RunResult:
        """TODO(step 5): the core loop. In order:
          - state = dict(checkpoint.state)  (defensive copy -- do not
            let a node's in-place mutation corrupt an already-saved
            checkpoint)
          - node_name = checkpoint.next_node; step = checkpoint.step
          - while node_name != END:
              * look up fn = self.nodes.get(node_name); raise KeyError if
                missing
              * call update = fn(state)
                - if it raises Interrupt: build a state snapshot with
                  RESUME_KEY stripped, save a Checkpoint with
                  status="interrupted", next_node=node_name (the SAME node
                  -- it hasn't completed), interrupt_payload=the exception's
                  payload, and return RunResult("interrupted", snapshot,
                  node_name, payload) -- do NOT let it propagate further
                - any OTHER exception must propagate out of this function
                  uncaught (that's the simulated crash) -- do not save a
                  checkpoint for it
              * on success: state = {**state, **update}; pop RESUME_KEY
                from state if present; step += 1; compute the next node via
                self._next_after(node_name, state); save a new Checkpoint
                (status "done" if the next node is END, else "running")
          - after the loop: return RunResult("done", state, None)
        """
        raise NotImplementedError
