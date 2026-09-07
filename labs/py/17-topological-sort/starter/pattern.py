"""Lab 17 — topological sort. Fill in every TODO. Tests define done.

Rules:
  * Determinism: among available nodes, always emit the smallest id/name first.
  * Both algorithms must detect cycles and return None (or raise where the
    spec says so). Kahn's: leftover nodes after the pass. DFS: three colours.
  * No mutating caller data. No network. Pure stdlib.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple


def kahns_toposort(n: int, edges: Sequence[Tuple[int, int]]) -> Optional[List[int]]:
    """BFS toposort over nodes 0..n-1 with edges (a, b) meaning a before b.

    Among in-degree-0 candidates always take the smallest id.
    Return None on a cycle.
    """
    raise NotImplementedError


def dfs_toposort(n: int, edges: Sequence[Tuple[int, int]]) -> Optional[List[int]]:
    """DFS postorder reversed. Three-colour cycle detection (GRAY on stack).

    Among choices, visit smallest id first for determinism.
    Return None on a cycle.
    """
    raise NotImplementedError


def course_schedule(n: int, prerequisites: Sequence[Sequence[int]]) -> Optional[List[int]]:
    """prerequisites pairs are [course, prereq]: to take `course` you need
    `prereq` first. Return a valid order to take all n courses, or None."""
    raise NotImplementedError


def build_order(projects: Sequence[str],
                dependencies: Sequence[Tuple[str, str]]) -> Optional[List[str]]:
    """(before, after) dependencies. Return names in build order or None.
    Unknown project name in a dependency -> ValueError."""
    raise NotImplementedError


def alien_dictionary(words: Sequence[str]) -> str:
    """Infer character order from lexicographically sorted words.

    "" if the order is inconsistent/undecidable. Otherwise every character
    that appears in any word appears in the output, in a consistent order.
    """
    raise NotImplementedError


def min_semesters(n: int, relations: Sequence[Tuple[int, int]]) -> Optional[int]:
    """Courses 1..n. (prev, next) relations. Any number of unlocked courses
    may be taken in parallel in one semester. Cycle -> None."""
    raise NotImplementedError
