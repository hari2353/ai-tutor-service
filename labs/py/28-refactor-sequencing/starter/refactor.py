"""Lab 28 — refactor sequencer. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib only. No I/O, no sleeps.
  * Everything deterministic: ties are always broken by name.
"""


class RefactorCycleError(Exception):
    """The change graph has a cycle — there is no safe order."""


def build_change_graph(files, imports):
    """files: list[str]; imports: {file: [imported filenames]}.

    Return {file: [its imports]}, keeping only imports present in `files`.
    Raise RefactorCycleError if the graph has a cycle (detect via DFS).
    """
    raise NotImplementedError


def safe_order(graph):
    """Topological order (Kahn): dependencies before dependents.
    Deterministic: at each step take the ready nodes in name order.
    """
    raise NotImplementedError


def batch(order, graph, max_batch_size):
    """Split `order` into batches of <= max_batch_size where each file
    appears in a batch strictly after all its imports' batches.
    """
    raise NotImplementedError


class StranglerPlan:
    """mapping: {old_file: new_file}."""

    def __init__(self, old_files, mapping):
        """old_files: change graph over the old files; mapping: old -> new."""
        raise NotImplementedError

    def phases(self):
        """[parallel_run (all new files)] + [cutover per old file, dependencies
        first, dependents last] + [cleanup (all old files)]."""
        raise NotImplementedError


def checkpoint(plan_state, batch_index):
    """Snapshot dict taken before applying batch `batch_index` (0-based)."""
    raise NotImplementedError


def can_rollback(cp, current_batch):
    """True iff nothing later than the checkpoint has started
    (current_batch <= the checkpoint's batch).
    """
    raise NotImplementedError


def rollback(cp, batches):
    """The files changed after the checkpoint: flatten every batch
    past the checkpoint's index.
    """
    raise NotImplementedError
