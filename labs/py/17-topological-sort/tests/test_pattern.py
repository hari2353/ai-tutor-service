"""Lab 17 tests — topological sort. Deterministic."""
import random

import pytest


def _is_valid_toposort(order, n, edges):
    if order is None or sorted(order) != list(range(n)):
        return False
    pos = {v: i for i, v in enumerate(order)}
    return all(pos[a] < pos[b] for a, b in edges)


# ------------------------------------------------------------------ kahns
def test_kahns_linear_chain(P):
    assert P.kahns_toposort(4, [(0, 1), (1, 2), (2, 3)]) == [0, 1, 2, 3]


def test_kahns_deterministic_smallest_first(P):
    assert P.kahns_toposort(3, []) == [0, 1, 2]
    assert P.kahns_toposort(3, [(2, 1)]) == [0, 2, 1]


def test_kahns_diamond(P):
    order = P.kahns_toposort(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    assert _is_valid_toposort(order, 4, [(0, 1), (0, 2), (1, 3), (2, 3)])
    assert order == [0, 1, 2, 3]


def test_kahns_cycle_returns_none(P):
    assert P.kahns_toposort(3, [(0, 1), (1, 2), (2, 0)]) is None


def test_kahns_two_cycle(P):
    assert P.kahns_toposort(2, [(0, 1), (1, 0)]) is None


def test_kahns_self_loop(P):
    assert P.kahns_toposort(2, [(1, 1)]) is None


def test_kahns_no_edges(P):
    assert P.kahns_toposort(2, []) == [0, 1]
    assert P.kahns_toposort(0, []) == []


# ------------------------------------------------------------------ dfs
def test_dfs_matches_validity_randomized(P):
    rng = random.Random(1)
    for _ in range(40):
        n = rng.randrange(1, 10)
        edges = [(rng.randrange(n), rng.randrange(n)) for _ in range(rng.randrange(0, 12))]
        order = P.dfs_toposort(n, edges)
        kahns = P.kahns_toposort(n, edges)
        if order is None:
            assert kahns is None
        else:
            assert _is_valid_toposort(order, n, edges)
            assert kahns is not None


def test_dfs_cycle_detection(P):
    assert P.dfs_toposort(4, [(0, 1), (1, 2), (2, 1), (2, 3)]) is None


def test_dfs_cycle_deep_in_stack(P):
    # cycle not involving the start node: 0->1->2->3->1
    assert P.dfs_toposort(4, [(0, 1), (1, 2), (2, 3), (3, 1)]) is None


def test_dfs_linear(P):
    assert P.dfs_toposort(3, [(2, 0), (0, 1)]) == [2, 0, 1]


def test_dfs_no_edges(P):
    # postorder reversed: valid toposort of independent nodes
    assert _is_valid_toposort(P.dfs_toposort(3, []), 3, [])


# ------------------------------------------------------------------ course schedule
def test_course_schedule_basic(P):
    order = P.course_schedule(2, [[1, 0]])
    assert order == [0, 1]


def test_course_schedule_prereq_direction(P):
    """[course, prereq] — the classic LeetCode 210 direction."""
    order = P.course_schedule(4, [[1, 0], [2, 0], [3, 1], [3, 2]])
    assert order == [0, 1, 2, 3]


def test_course_schedule_impossible(P):
    assert P.course_schedule(3, [[0, 1], [1, 2], [2, 0]]) is None


def test_course_schedule_no_prereqs(P):
    assert P.course_schedule(3, []) == [0, 1, 2]


def test_course_schedule_single(P):
    assert P.course_schedule(1, []) == [0]


# ------------------------------------------------------------------ build order
def test_build_order_classic(P):
    projects = ["a", "b", "c", "d", "e", "f"]
    deps = [("a", "d"), ("f", "b"), ("b", "d"), ("f", "a"), ("d", "c")]
    assert P.build_order(projects, deps) == ["e", "f", "a", "b", "d", "c"]


def test_build_order_cycle(P):
    projects = ["a", "b"]
    assert P.build_order(projects, [("a", "b"), ("b", "a")]) is None


def test_build_order_independent_only(P):
    assert P.build_order(["z", "x"], []) == ["x", "z"]


def test_build_order_unknown_project(P):
    with pytest.raises(ValueError):
        P.build_order(["a"], [("a", "ghost")])


def test_build_order_chain(P):
    projects = ["lib", "app", "test"]
    deps = [("lib", "app"), ("app", "test")]
    assert P.build_order(projects, deps) == ["lib", "app", "test"]


# ------------------------------------------------------------------ alien dictionary
def test_alien_dictionary_classic(P):
    words = ["wrt", "wrf", "er", "ett", "rftt"]
    assert P.alien_dictionary(words) == "wertf"


def test_alien_dictionary_simple(P):
    assert P.alien_dictionary(["z", "x", "z"]) == ""


def test_alien_dictionary_prefix_violation(P):
    assert P.alien_dictionary(["abc", "ab"]) == ""


def test_alien_dictionary_single_word(P):
    # single word: all its chars, in appearance... consistent == any valid order
    out = P.alien_dictionary(["abc"])
    assert sorted(out) == ["a", "b", "c"]


def test_alien_dictionary_two_letters(P):
    assert P.alien_dictionary(["a", "b", "a"]) == ""


def test_alien_dictionary_valid_multi(P):
    words = ["ba", "bc", "ac"]
    # b<a (ba<ac first chars), a<c (from nothing? ba<bc gives a<c)
    out = P.alien_dictionary(words)
    assert out == "bac"


def test_alien_dictionary_empty(P):
    assert P.alien_dictionary([]) == ""


def test_alien_dictionary_all_same(P):
    out = P.alien_dictionary(["a", "a"])
    assert out == "a"


# ------------------------------------------------------------------ min semesters
def test_min_semesters_linear(P):
    assert P.min_semesters(3, [(1, 2), (2, 3)]) == 3


def test_min_semesters_parallel(P):
    # 1 -> {2,3} -> 4: three levels
    assert P.min_semesters(4, [(1, 2), (1, 3), (2, 4), (3, 4)]) == 3


def test_min_semesters_no_relations(P):
    assert P.min_semesters(5, []) == 1


def test_min_semesters_cycle(P):
    assert P.min_semesters(3, [(1, 2), (2, 3), (3, 1)]) is None


def test_min_semesters_single_course(P):
    assert P.min_semesters(1, []) == 1


def test_min_semesters_wide(P):
    # 7 courses: take 1 in sem 1, 2 and 3 in sem 2, rest in sem 3
    n = 7
    rels = [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6), (3, 7)]
    assert P.min_semesters(n, rels) == 3


# ------------------------------------------------------------------ complexity witness
def test_kahns_linear_time_big_graph(P):
    """Kahn's must be O(V+E); a 100k-node chain plus 100k skips of width 100
    builds and sorts in well under 2 seconds."""
    import time
    n = 100_000
    edges = [(i, i + 1) for i in range(n - 1)]
    edges += [(i, i + 50_000) for i in range(50_000)]
    t0 = time.perf_counter()
    order = P.kahns_toposort(n, edges)
    dt = time.perf_counter() - t0
    assert order is not None
    assert len(order) == n
    assert dt < 2.0
