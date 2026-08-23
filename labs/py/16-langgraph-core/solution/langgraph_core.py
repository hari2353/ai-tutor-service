"""Lab 16 — reference solution. A mini LangGraph core in ~200 lines."""
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
    """Fan-out directive returned from a conditional edge.

    Runs `node_name` once with its OWN sub-state copy seeded with `arg`
    (a dict overlaid onto a deep copy of the committed state). N Sends =
    N invocations of the same node on N different states; results merge
    through that node's updates with reducer semantics.
    """

    def __init__(self, node_name: str, arg: Any = None) -> None:
        self.node_name = node_name
        self.arg = arg

    def __repr__(self) -> str:
        return f"Send({self.node_name!r}, {self.arg!r})"


class StateGraph:
    """Builder. Declare nodes, reducers and edges; compile() validates + wires.

    State is a plain dict. One reducer per key via add_reducer(key, fn) with
    fn(current, update) -> new; absent reducer => OVERWRITE (last write wins),
    which is exactly the silent-clobber default the curriculum warns about.
    """

    def __init__(self, state_schema: Any = None) -> None:
        # Kept as declared metadata only: this engine treats state as a plain
        # dict regardless. Real LangGraph reads Annotated reducers off the
        # schema; here you register them explicitly with add_reducer().
        self.state_schema = state_schema
        self._nodes: dict[str, NodeFn] = {}
        self._reducers: dict[str, ReducerFn] = {}
        self._static: dict[str, list[str]] = {}   # source -> [targets]; START key = entry edge
        self._cond: dict[str, RouterFn] = {}      # source -> router(state)
        self._entry: str | None = None

    # ------------------------------------------------------------ declaration
    def add_reducer(self, key: str, fn: ReducerFn) -> "StateGraph":
        self._reducers[key] = fn
        return self

    def add_node(self, name: str, fn: NodeFn) -> "StateGraph":
        if name in (START, END):
            raise GraphError(f"'{name}' is reserved")
        if name in self._nodes:
            raise GraphError(f"node '{name}' registered twice")
        self._nodes[name] = fn
        return self

    def add_edge(self, a: str, b: str) -> "StateGraph":
        self._static.setdefault(a, []).append(b)
        return self

    def add_conditional_edges(self, name: str, router: RouterFn) -> "StateGraph":
        self._cond[name] = router
        return self

    def set_entry(self, name: str) -> "StateGraph":
        if self._entry is not None:
            raise GraphError("entry set twice")
        self._entry = name
        return self

    # ------------------------------------------------------------- validation
    def compile(self) -> "CompiledGraph":
        # 1. endpoints must exist (END is a legal static target)
        for src, tgts in self._static.items():
            if src != START and src not in self._nodes:
                raise GraphError(f"edge source '{src}' is not a registered node")
            for t in tgts:
                if t != END and t not in self._nodes:
                    raise GraphError(f"unknown edge target '{t}' (edge from '{src}')")
        for src in self._cond:
            if src not in self._nodes:
                raise GraphError(f"conditional edge source '{src}' is not a registered node")

        # 2. entry: set_entry() or add_edge(START, x), never both / several
        start_targets = self._static.get(START, [])
        if self._entry is not None and start_targets:
            raise GraphError("entry defined both by set_entry() and add_edge(START, ...)")
        if len(start_targets) > 1:
            raise GraphError("multiple START edges — one entry per graph")
        entry = self._entry or (start_targets[0] if start_targets else None)
        if entry is None:
            raise GraphError("no entry point: call set_entry(...) or add_edge(START, ...)")
        if entry not in self._nodes:
            raise GraphError(f"entry '{entry}' is not a registered node")

        # 3. one routing mechanism per node (Command-vs-static lesson)
        for name in self._cond:
            if self._static.get(name):
                raise GraphError(
                    f"node '{name}' mixes static edges and conditional routing "
                    f"— pick one mechanism per node")

        # 4. pure-STATIC cycles are errors; a loop must contain a conditional
        #    edge so it can terminate. Detect on the static subgraph only.
        self._assert_no_static_cycle()

        # 5. every node reachable from entry. Static BFS; if a reached node has
        #    conditional out-edges its destinations are dynamic, so treat all
        #    declared nodes as potentially reachable from there.
        seen = set()
        stack = [entry]
        dynamic_reached = False
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            for v in self._static.get(u, ()):
                if v != END:
                    stack.append(v)
            if u in self._cond:
                dynamic_reached = True
        if dynamic_reached:
            seen = set(self._nodes)
        unreachable = sorted(n for n in self._nodes if n not in seen)
        if unreachable:
            raise GraphError(f"nodes unreachable from entry '{entry}': {unreachable}")

        return CompiledGraph(entry, dict(self._nodes), dict(self._reducers),
                             {k: list(v) for k, v in self._static.items()},
                             dict(self._cond))

    def _assert_no_static_cycle(self) -> None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self._nodes}

        def dfs(u: str) -> None:
            color[u] = GRAY
            for v in self._static.get(u, ()):
                if v == END or v not in color:
                    continue
                if color[v] == GRAY:
                    raise GraphError(
                        f"static cycle through '{v}': every edge on it is unconditional, "
                        f"so it cannot terminate — put a conditional edge on the cycle")
                if color[v] == WHITE:
                    dfs(v)
            color[u] = BLACK

        for n in self._nodes:
            if color[n] == WHITE:
                dfs(n)


class CompiledGraph:
    """Immutable wiring. invoke() runs Pregel-style super-steps until END."""

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
        """Run to END. Returns the final state as a detached deep copy.

        Each super-step: run every scheduled node (on its own deep-copied
        input), reduce ALL writes in execution order, then schedule the next
        frontier. The log records node names in exact execution order — Send
        fan-out appears in the deterministic order of the router's list.
        """
        state: dict = copy.deepcopy(dict(values)) if values else {}
        self.execution_log = []
        frontier: list[tuple[str, dict | None]] = [(self.entry, copy.deepcopy(state))]

        for _step in range(recursion_limit):
            if not frontier:
                return copy.deepcopy(state)

            writes: list[tuple[str, Any]] = []
            for name, own_input in frontier:
                self.execution_log.append(name)
                node_input = own_input if own_input is not None else copy.deepcopy(state)
                upd = self.nodes[name](node_input)
                if upd is None:
                    continue
                if not isinstance(upd, Mapping):
                    raise GraphError(
                        f"node '{name}' returned {type(upd).__name__}; "
                        f"nodes must return a partial-update dict (or None)")
                for k, v in upd.items():
                    writes.append((k, v))

            for k, v in writes:                      # reduce THIS super-step's writes
                red = self.reducers.get(k)
                state[k] = red(state.get(k), copy.deepcopy(v)) if red else copy.deepcopy(v)

            nxt: list[tuple[str, dict | None]] = []
            scheduled: set[str] = set()              # static targets run once per tick
            for name, _own in frontier:
                for d in self._destinations(name, state):
                    if isinstance(d, Send):
                        if d.node_name not in self.nodes:
                            raise GraphError(f"Send targets unknown node '{d.node_name}'")
                        branch = copy.deepcopy(state)
                        if d.arg is not None:
                            if not isinstance(d.arg, Mapping):
                                raise GraphError(
                                    f"Send('{d.node_name}', ...) arg must be a dict "
                                    f"seeding the branch state, got {type(d.arg).__name__}")
                            branch.update(copy.deepcopy(dict(d.arg)))
                        nxt.append((d.node_name, branch))   # never deduped: N Sends = N tasks
                    elif d != END:
                        if d not in self.nodes:
                            raise GraphError(f"routing to unknown node '{d}'")
                        if d not in scheduled:
                            scheduled.add(d)
                            nxt.append((d, None))
            frontier = nxt

        raise GraphError(
            f"recursion limit ({recursion_limit}) exceeded without reaching END")

    def _destinations(self, name: str, state: dict) -> list:
        """Conditional router wins when present; otherwise the static edges."""
        if name in self.cond:
            out = self.cond[name](state)
            if out is None:
                return []
            if isinstance(out, (str, Send)):
                return [out]
            return list(out)
        return list(self.static.get(name, ()))
