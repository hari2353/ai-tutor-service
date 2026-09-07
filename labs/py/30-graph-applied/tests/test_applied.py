"""Lab 30 tests — behaviour only, hand-verified fixtures, no sleeps."""
import pytest


# ------------------------------------------------------------------ resolver
def test_resolver_picks_highest_satisfying_version(A):
    assert A.resolve_packages(
        [("webserver", ">=1.0")],
        {"webserver": ["1.0", "1.5", "2.0"], "leftpad": ["1.0", "2.0", "9.9"]},
    ) == {"webserver": "2.0"}


def test_resolver_respects_exact_pin(A):
    assert A.resolve_packages(
        [("webserver", "1.5")],
        {"webserver": ["1.0", "1.5", "2.0"]},
    ) == {"webserver": "1.5"}


def test_resolver_multiple_min_specs_pick_lowest_common(A):
    plan = A.resolve_packages(
        [("webserver", ">=1.0"), ("cache", ">=1.4")],
        {"webserver": ["1.0", "1.5", "2.0"], "cache": ["1.2", "1.4", "2.0"]},
        {("cache", "2.0"): [("webserver", ">=1.5")]},
    )
    assert plan == {"webserver": "2.0", "cache": "2.0"}


def test_resolver_follows_deps_of_chosen_version(A):
    plan = A.resolve_packages(
        [("app", ">=1.0")],
        {"app": ["1.0", "2.0"], "webserver": ["1.0", "1.5", "2.0"]},
        {("app", "2.0"): [("webserver", ">=1.5")]},
    )
    assert plan == {"app": "2.0", "webserver": "2.0"}


def test_resolver_requested_constraint_conflicts(A):
    assert A.resolve_packages(
        [("webserver", ">=3.0")],
        {"webserver": ["1.0", "1.5", "2.0"]},
    ) is None


def test_resolver_two_requests_on_same_name_must_intersect(A):
    assert A.resolve_packages(
        [("webserver", ">=1.0"), ("webserver", ">=3.0")],
        {"webserver": ["1.0", "1.2", "2.0"]},
    ) is None


def test_resolver_unknown_package_requested(A):
    assert A.resolve_packages([("leftpad", ">=1.0")],
                              {"webserver": ["1.0"]}) is None


def test_resolver_unknown_dep_is_conflict(A):
    assert A.resolve_packages(
        [("app", ">=1.0")],
        {"app": ["1.0"]},
        {("app", "1.0"): [("ghost", ">=1.0")]},
    ) is None


def test_resolver_version_compare_is_numeric_not_lexicographic(A):
    """'9.9' vs '10.0' — string comparison would sort '9.9' higher."""
    assert A.resolve_packages(
        [("pkg", ">=1.0")],
        {"pkg": ["9.9", "10.0"]},
    ) == {"pkg": "10.0"}


def test_resolver_dep_of_chosen_version_only(A):
    """Deps of the *unchosen* 2.0 (which wants >=9.0) must not constrain."""
    plan = A.resolve_packages(
        [("app", "1.0")],
        {"app": ["1.0", "2.0"], "webserver": ["1.0", "1.5"]},
        {("app", "2.0"): [("webserver", ">=9.0")]},
    )
    assert plan == {"app": "1.0"}


def test_resolver_shared_dep_conflict_yields_none(A):
    """a wants shared>=2.0, b pins shared=1.0 — no plan exists."""
    assert A.resolve_packages(
        [("a", ">=1.0"), ("b", ">=1.0")],
        {"a": ["1.0"], "b": ["1.0"], "shared": ["1.0", "2.0"]},
        {("a", "1.0"): [("shared", ">=2.0")],
         ("b", "1.0"): [("shared", "1.0")]},
    ) is None


def test_resolver_shared_dep_floor_common(A):
    """a wants shared>=2.0, b wants shared>=1.0 -> the floor 2.0 wins."""
    assert A.resolve_packages(
        [("a", ">=1.0"), ("b", ">=1.0")],
        {"a": ["1.0"], "b": ["1.0"], "shared": ["1.0", "2.0"]},
        {("a", "1.0"): [("shared", ">=2.0")],
         ("b", "1.0"): [("shared", ">=1.0")]},
    ) == {"a": "1.0", "b": "1.0", "shared": "2.0"}


def test_resolver_unsupported_spec_operator_raises(A):
    with pytest.raises(ValueError):
        A.resolve_packages([("pkg", "<2.0")], {"pkg": ["1.0", "2.0"]})


# ----------------------------------------------------------------- graphrag
@pytest.fixture
def KG():
    """Hand-built knowledge graph — the 'no single chunk mentions both' fixture."""
    return {
        "python":    [("guido", "created_by"), ("cpython", "implemented_in")],
        "guido":     [("microsoft", "works_at"), ("python", "creator_of")],
        "cpython":   [("guido", "maintained_by"), ("c", "written_in")],
        "microsoft": [("azure", "develops"), ("openai", "invests_in")],
        "azure":     [("microsoft", "owned_by")],
    }


def test_graphrag_known_chain_found(A, KG):
    assert A.graph_rag_answer(
        KG, ["python", "guido", "microsoft"]) == ["created_by", "works_at"]


def test_graphrag_single_hop(A, KG):
    assert A.graph_rag_answer(KG, ["python", "guido"]) == ["created_by"]


def test_graphrag_three_hops(A, KG):
    assert A.graph_rag_answer(
        KG, ["python", "cpython", "guido", "microsoft"]) == \
        ["implemented_in", "maintained_by", "works_at"]


def test_graphrag_wrong_path_returns_none(A, KG):
    # python -> guido exists, guido -> python exists, python -> microsoft: no edge
    assert A.graph_rag_answer(
        KG, ["guido", "python", "microsoft"]) is None


def test_graphrag_unknown_entity_returns_none(A, KG):
    assert A.graph_rag_answer(KG, ["python", "guido", "openai"]) is None


def test_graphrag_reverse_direction_is_not_an_edge(A, KG):
    """Edges are directed: microsoft -> guido does not exist."""
    assert A.graph_rag_answer(KG, ["microsoft", "guido", "python"]) is None


def test_graphrag_too_short_path_returns_none(A, KG):
    assert A.graph_rag_answer(KG, ["python"]) is None
    assert A.graph_rag_answer(KG, []) is None


# ----------------------------------------------------------------- pagerank
def test_pagerank_two_node_cycle_symmetric(A):
    s = A.pagerank({"a": ["b"], "b": ["a"]})
    assert s["a"] == pytest.approx(s["b"])
    assert s["a"] == pytest.approx(0.5, abs=1e-6)


def test_pagerank_hub_scores_highest(A):
    star = {f"s{i}": ["hub"] for i in range(4)}   # 4 spokes -> hub (dangling)
    s = A.pagerank(star)
    assert s["hub"] > max(s[f"s{i}"] for i in range(4))
    # hand-derived: hub = 11/21, spoke = 5/42
    assert s["hub"] == pytest.approx(11 / 21, abs=5e-3)
    assert s["s0"] == pytest.approx(5 / 42, abs=5e-3)


def test_pagerank_scores_sum_to_one(A):
    g = {e: [t for t, _ in edges] for e, edges in {
        "python": [("guido", "created_by"), ("cpython", "implemented_in")],
        "guido": [("microsoft", "works_at"), ("python", "creator_of")],
        "cpython": [("guido", "maintained_by"), ("c", "written_in")],
        "microsoft": [("azure", "develops"), ("openai", "invests_in")],
        "azure": [("microsoft", "owned_by")],
    }.items()}
    s = A.pagerank(g)
    assert sum(s.values()) == pytest.approx(1.0, abs=1e-3)
    assert set(s) == {"python", "guido", "cpython",
                     "microsoft", "azure", "c", "openai"}


def test_pagerank_dangling_node_wins_over_linker(A):
    """a -> b, b dangles: all of a's endorsement flows into b and stays."""
    s = A.pagerank({"a": ["b"]})
    assert set(s) == {"a", "b"}
    # hand-derived: a = 20/57, b = 37/57 — b's score is larger
    assert s["b"] > s["a"]
    assert s["a"] == pytest.approx(20 / 57, abs=5e-3)
    assert s["b"] == pytest.approx(37 / 57, abs=5e-3)


def test_pagerank_zero_damping_is_uniform(A):
    s = A.pagerank({"a": ["b"], "b": ["c"], "c": []}, damping=0.0)
    assert all(v == pytest.approx(1.0 / 3) for v in s.values())


def test_pagerank_empty_graph(A):
    assert A.pagerank({}) == {}


# ------------------------------------------------------------ critical path
def test_critical_path_linear_chain(A):
    path, length = A.critical_path_dag(
        ["compile", "test", "package"],
        {"compile": 2, "test": 3, "package": 4},
        [("compile", "test"), ("test", "package")],
    )
    assert path == ["compile", "test", "package"]
    assert length == 9


def test_critical_path_diamond_picks_longest_branch(A):
    path, length = A.critical_path_dag(
        ["a", "b", "c", "d"],
        {"a": 1, "b": 5, "c": 2, "d": 1},
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )
    assert path == ["a", "b", "d"]
    assert length == 7


def test_critical_path_disconnected_node_excluded(A):
    path, length = A.critical_path_dag(
        ["a", "b", "c", "island"],
        {"a": 2, "b": 3, "c": 4, "island": 1},
        [("a", "b"), ("b", "c")],
    )
    assert path == ["a", "b", "c"]
    assert length == 9
    assert "island" not in path


def test_critical_path_disconnected_node_wins_when_longest(A):
    path, length = A.critical_path_dag(
        ["a", "b", "island"],
        {"a": 1, "b": 1, "island": 10},
        [("a", "b")],
    )
    assert path == ["island"]
    assert length == 10


def test_critical_path_single_node(A):
    assert A.critical_path_dag(["x"], {"x": 5}, []) == (["x"], 5)


def test_critical_path_longer_by_node_count_not_length(A):
    """Tie on total length -> must still return SOME valid critical path."""
    path, length = A.critical_path_dag(
        ["a", "b", "c", "d"],
        {"a": 1, "b": 1, "c": 1, "d": 2},
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )
    assert length == 4
    assert path[0] == "a" and path[-1] == "d" and len(path) == 3


def test_critical_path_cycle_raises(A):
    with pytest.raises(ValueError):
        A.critical_path_dag(
            ["a", "b", "c"],
            {"a": 1, "b": 1, "c": 1},
            [("a", "b"), ("b", "c"), ("c", "a")],
        )


def test_critical_path_integer_overflow_irrelevant_but_floats_ok(A):
    path, length = A.critical_path_dag(
        ["a", "b"], {"a": 0.5, "b": 0.25}, [("a", "b")]
    )
    assert path == ["a", "b"]
    assert length == pytest.approx(0.75)
