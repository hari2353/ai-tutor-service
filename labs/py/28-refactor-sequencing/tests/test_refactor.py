"""Lab 28 tests. Pure stdlib, no I/O, no sleeps."""
import pytest


# --------------------------------------------------------------- fixtures
@pytest.fixture
def diamond(R):
    """a -> {b, c} -> d, plus isolated e."""
    files = ["a", "b", "c", "d", "e"]
    imports = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"], "e": []}
    return files, imports


@pytest.fixture
def graph(R, diamond):
    files, imports = diamond
    return R.build_change_graph(files, imports)


# --------------------------------------------------------------- graph
def test_cycle_raises(R):
    with pytest.raises(R.RefactorCycleError):
        R.build_change_graph(["x", "y"], {"x": ["y"], "y": ["x"]})


def test_graph_drops_unknown_imports(R):
    graph = R.build_change_graph(
        ["a", "b"], {"a": ["os", "b"], "b": []})
    assert graph == {"a": ["b"], "b": []}


# --------------------------------------------------------------- safe_order
def test_order_respects_diamond(R, graph):
    order = R.safe_order(graph)
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_isolated_file_lands_anywhere(R, graph):
    order = R.safe_order(graph)
    assert sorted(order) == ["a", "b", "c", "d", "e"]


def test_order_is_deterministic(R, graph):
    assert R.safe_order(graph) == R.safe_order(graph)


def test_empty_graph_sorted(R):
    assert R.safe_order({}) == []
    graph = R.build_change_graph(["b", "a", "c"], {})
    assert R.safe_order(graph) == ["a", "b", "c"]


# --------------------------------------------------------------- batch
def test_batch_deps_in_earlier_batches(R, graph):
    order = R.safe_order(graph)
    batches = R.batch(order, graph, 2)
    placement = {f: i for i, b in enumerate(batches) for f in b}
    for f, deps in graph.items():
        for dep in deps:
            assert placement[dep] < placement[f], f"{dep} must precede {f}"


def test_batch_respects_size(R, graph):
    order = R.safe_order(graph)
    batches = R.batch(order, graph, 2)
    assert all(len(b) <= 2 for b in batches)
    assert sorted(f for b in batches for f in b) == ["a", "b", "c", "d", "e"]


def test_chain_of_five_size_two_is_three_batches(R):
    """A plain sequence (no interdependencies) with max size 2 -> ceil(5/2)=3.
    Interleaved chain edges f1->f3->f5 keep the same count (2 apart never share)."""
    files = ["f1", "f2", "f3", "f4", "f5"]
    imports = {"f1": [], "f2": [], "f3": ["f1"],
               "f4": [], "f5": ["f3"]}
    graph = R.build_change_graph(files, imports)
    batches = R.batch(R.safe_order(graph), graph, 2)
    assert len(batches) == 3
    assert [len(b) for b in batches] == [2, 2, 1]
    placement = {f: i for i, b in enumerate(batches) for f in b}
    for f, deps in graph.items():
        for dep in deps:
            assert placement[dep] < placement[f]


# --------------------------------------------------------------- strangler
def test_parallel_run_first_lists_all_new_files(R):
    old_files = R.build_change_graph(["a", "b", "d"], {"a": [], "b": ["a"], "d": ["b"]})
    plan = R.StranglerPlan(old_files, {"a": "na", "b": "nb", "d": "nd"})
    phases = plan.phases()
    assert phases[0] == {"phase": "parallel_run", "files": ["na", "nb", "nd"]}


def test_cutover_dependencies_before_dependents(R):
    old_files = R.build_change_graph(["a", "b", "d"], {"a": [], "b": ["a"], "d": ["b"]})
    plan = R.StranglerPlan(old_files, {"a": "na", "b": "nb", "d": "nd"})
    cutovers = [p["files"][0] for p in plan.phases() if p["phase"] == "cutover"]
    assert cutovers == ["na", "nb", "nd"]


def test_cleanup_last_lists_old_files(R):
    old_files = R.build_change_graph(["a", "b", "d"], {"a": [], "b": ["a"], "d": ["b"]})
    plan = R.StranglerPlan(old_files, {"a": "na", "b": "nb", "d": "nd"})
    phases = plan.phases()
    assert phases[-1] == {"phase": "cleanup", "files": ["a", "b", "d"]}
    assert [p["phase"] for p in phases] == \
        ["parallel_run"] + ["cutover"] * 3 + ["cleanup"]


# --------------------------------------------------------------- checkpoints
def test_checkpoint_can_rollback_and_rollback(R):
    batches = [["a", "b"], ["c", "d"], ["e"]]
    cp = R.checkpoint({"batches": 3, "notes": "mid-flight"}, 1)
    assert R.can_rollback(cp, 1) is True
    assert R.can_rollback(cp, 2) is False
    assert R.rollback(cp, batches) == ["e"]


def test_rollback_returns_every_later_batch_flattened(R):
    batches = [["a"], ["b"], ["c", "d"], ["e"]]
    cp = R.checkpoint({}, 0)
    assert R.rollback(cp, batches) == ["b", "c", "d", "e"]
    cp_last = R.checkpoint({}, 3)
    assert R.rollback(cp_last, batches) == []


def test_can_rollback_false_once_past_checkpoint(R):
    cp = R.checkpoint({}, 2)
    assert R.can_rollback(cp, 0) is True
    assert R.can_rollback(cp, 2) is True
    assert R.can_rollback(cp, 3) is False
