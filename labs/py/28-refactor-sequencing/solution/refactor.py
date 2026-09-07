"""Lab 28 — reference solution."""
from __future__ import annotations


class RefactorCycleError(Exception):
    """The change graph has a cycle — there is no safe order."""


def build_change_graph(files, imports):
    """files: list[str]; imports: {file: [imported filenames]}.

    Return {file: [its imports]}, keeping only imports present in `files`.
    Raise RefactorCycleError if the graph has a cycle (detect via DFS).
    """
    in_set = set(files)
    graph = {f: [dep for dep in imports.get(f, []) if dep in in_set]
             for f in files}

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {f: WHITE for f in files}

    def dfs(node):
        colour[node] = GREY
        for dep in graph[node]:
            if colour[dep] == GREY:
                raise RefactorCycleError(f"cycle through {dep!r} and {node!r}")
            if colour[dep] == WHITE:
                dfs(dep)
        colour[node] = BLACK

    for f in files:
        if colour[f] == WHITE:
            dfs(f)
    return graph


def safe_order(graph):
    """Topological order (Kahn): dependencies before dependents.
    Deterministic: at each step take the ready nodes in name order.
    """
    deps = {f: list(deps_) for f, deps_ in graph.items()}
    dependents = {f: [] for f in graph}
    for f, ds in deps.items():
        for dep in ds:
            dependents[dep].append(f)

    order = []
    ready = sorted(f for f, ds in deps.items() if not ds)
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in dependents[node]:
            deps[dependent].remove(node)
            if not deps[dependent]:
                ready.append(dependent)
        ready.sort()
    if len(order) != len(graph):
        raise RefactorCycleError("cycle in change graph")
    return order


def batch(order, graph, max_batch_size):
    """Split `order` into batches of <= max_batch_size where each file
    appears in a batch strictly after all its imports' batches.
    """
    if max_batch_size < 1:
        raise ValueError("max_batch_size must be >= 1")

    batches = []
    placement = {}          # file -> batch index
    for file in order:
        deps = [d for d in graph.get(file, []) if d in graph]
        earliest = 0
        for dep in deps:
            earliest = max(earliest, placement[dep] + 1)

        batch_index = None
        for i in range(earliest, len(batches)):
            if len(batches[i]) < max_batch_size:
                batch_index = i
                break
        if batch_index is None:
            batches.append([])
            batch_index = len(batches) - 1
        batches[batch_index].append(file)
        placement[file] = batch_index
    return batches


class StranglerPlan:
    """mapping: {old_file: new_file}."""

    def __init__(self, old_files, mapping):
        self.mapping = dict(mapping)
        self.order = safe_order(old_files)

    def phases(self):
        """[parallel_run (all new files)] + [cutover per old file, dependencies
        first, dependents last] + [cleanup (all old files)]."""
        phases = [{
            "phase": "parallel_run",
            "files": sorted(new for new in self.mapping.values()),
        }]
        for old in self.order:
            phases.append({"phase": "cutover",
                           "files": [self.mapping[old]]})
        phases.append({"phase": "cleanup",
                       "files": sorted(self.mapping.keys())})
        return phases


def checkpoint(plan_state, batch_index):
    """Snapshot dict taken before applying batch `batch_index` (0-based)."""
    return {
        "batch_index": batch_index,
        "plan_state": dict(plan_state),
        "applied_batches": batch_index,
    }


def can_rollback(cp, current_batch):
    """True iff nothing later than the checkpoint has started
    (current_batch <= the checkpoint's batch).
    """
    return current_batch <= cp["batch_index"]


def rollback(cp, batches):
    """The files changed after the checkpoint: flatten every batch
    past the checkpoint's index.
    """
    return [file
            for i in range(cp["batch_index"] + 1, len(batches))
            for file in batches[i]]
