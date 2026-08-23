"""Lab 16 — a mini LangGraph core. Fill in every TODO. Tests define done.

Rules:
  * State is a plain dict. One reducer per key; the DEFAULT reducer is
    OVERWRITE (last write wins) — the silent-clobber default from the curriculum.
  * Nodes receive a DEEP COPY of committed state and return partial updates
    (or None). In-place mutation of the input must never leak unless returned.
  * One super-step: every scheduled node runs, ALL writes are reduced in
    execution order, THEN the next frontier is scheduled.
  * Send(node, arg) fans out from a conditional edge: each branch gets its own
    deep-copied sub-state seeded with arg (a dict overlaid on the state copy),
    results merge through that node's updates, and its static join target runs
    exactly once after all branches.
  * compile() validates: unknown edge targets, missing entry, unreachable
    nodes, mixed routing mechanisms, and PURE-STATIC cycles are GraphError.
    A cycle that includes a conditional edge is allowed (it can terminate).
"""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any, Callable

START = "__start__"
END = "__end__"

NodeFn = Callable[[dict], "dict | None"]
RouterFn = Callable[[dict], "str | Send | list"]
ReducerFn = Callable[[Any, Any], Any]


class GraphError(Exception):
    """Structural problem found at compile(), or a runtime wiring violation."""


class Send:
    """Fan-out directive returned from a conditional edge."""

    # TODO(step 1): __init__(self, node_name, arg=None) — store both attributes.
    def __init__(self, node_name: str, arg: Any = None) -> None:
        raise NotImplementedError


class StateGraph:
    """Builder. Declare nodes, reducers and edges; compile() validates + wires."""

    def __init__(self, state_schema: Any = None) -> None:
        self.state_schema = state_schema   # declared metadata only; state stays a plain dict
        # TODO(step 2): initialise empty registries —
        #   _nodes: {name: fn}, _reducers: {key: fn},
        #   _static: {source: [targets]} (START key = entry edge), _cond: {source: router},
        #   _entry: str | None = None
        raise NotImplementedError

    # ------------------------------------------------------------ declaration
    def add_reducer(self, key: str, fn: ReducerFn) -> "StateGraph":
        """fn(current, update) -> new. Absent reducer => overwrite."""
        # TODO(step 3)
        raise NotImplementedError

    def add_node(self, name: str, fn: NodeFn) -> "StateGraph":
        """fn(state_copy) -> partial-update dict or None. Reject reserved names,
        reject double registration."""
        # TODO(step 4)
        raise NotImplementedError

    def add_edge(self, a: str, b: str) -> "StateGraph":
        """Static edge. a may be START (that defines the entry)."""
        # TODO(step 5): record under _static; validation happens at compile()
        raise NotImplementedError

    def add_conditional_edges(self, name: str, router: RouterFn) -> "StateGraph":
        """router(state) -> node name | END | Send | list of those."""
        # TODO(step 6)
        raise NotImplementedError

    def set_entry(self, name: str) -> "StateGraph":
        """Declare the entry node. Exactly one entry per graph."""
        # TODO(step 7): reject a second entry
        raise NotImplementedError

    # ------------------------------------------------------------- validation
    def compile(self) -> "CompiledGraph":
        """Validate structure and return CompiledGraph. Raise GraphError on:
          (8a) unknown static-edge sources/targets (END is a legal target);
          (8b) no entry / entry set twice / several START edges / unknown entry;
          (8c) a node mixing static out-edges with conditional routing;
          (8d) pure-STATIC cycles (DFS over static edges only — GRAY hit =
               cycle; a loop must contain a conditional edge to terminate);
          (8e) nodes unreachable from entry: BFS static edges from entry;
               if a reached node has conditional out-edges, treat ALL declared
               nodes as reachable from there (dynamic destinations)."""
        # TODO(step 8a-8e)
        raise NotImplementedError


class CompiledGraph:
    """Immutable wiring. invoke() runs super-steps until END."""

    def __init__(self, entry: str, nodes: dict[str, NodeFn],
                 reducers: dict[str, ReducerFn], static: dict[str, list[str]],
                 cond: dict[str, RouterFn]) -> None:
        self.entry = entry
        self.nodes = nodes
        self.reducers = reducers
        self.static = static
        self.cond = cond
        self.execution_log: list[str] = []

    def invoke(self, values: dict | None = None,
               *, recursion_limit: int = 1000) -> dict:
        """Run to END; return final state as a DETACHED deep copy.

        Per super-step (TODO steps 9a-9f):
          9a. reset execution_log; seed frontier [(entry, deepcopy(values))];
              loop until the frontier empties; if it never empties within
              recursion_limit ticks -> GraphError.
          9b. run each scheduled node ON ITS OWN deep copy of committed state
              (Send branches carry their pre-built branch input instead);
              collect (key, value) writes in execution order; non-dict,
              non-None returns are a GraphError.
          9c. reduce all writes in order: registered reducer folds
              red(current, deepcopy(v)); default OVERWRITE stores deepcopy(v).
          9d. schedule the next frontier per executed node in order:
              router output when the node has one, else its static edges;
              END contributes nothing.
          9e. Send destinations become their own frontier items with input =
              deepcopy(state) overlaid with a deepcopy of the Send's dict arg
              (non-dict arg -> GraphError); Send targets unknown node ->
              GraphError; NEVER dedupe Send items.
          9f. static/string destinations run at most ONCE per tick (dedupe by
              name, keep first occurrence) — this is why N branches join once.
        """
        # TODO(step 9a-9f)
        raise NotImplementedError

    def _destinations(self, name: str, state: dict) -> list:
        """Conditional router wins when present; otherwise the static edges.
        Normalise the router result into a list (str/Send pass through)."""
        # TODO(step 10)
        raise NotImplementedError
