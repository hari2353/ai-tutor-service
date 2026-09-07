"""Lab 18 — trie. Fill in every TODO. Tests define done.

Rules:
  * Nodes: dict children + a terminal marker. No parent pointers, no stored words.
  * insert is idempotent. search/starts_with are O(len(word)).
  * autocomplete: alphabetical order straight from the DFS (no full-sort).
  * find_words prunes dead prefixes with the trie — the whole point.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple


class Trie:
    """Prefix tree: insert, exact search, prefix query. O(len) each."""

    def __init__(self) -> None:
        raise NotImplementedError

    def insert(self, word: str) -> None:
        raise NotImplementedError

    def search(self, word: str) -> bool:
        raise NotImplementedError

    def starts_with(self, prefix: str) -> bool:
        raise NotImplementedError


class WordDictionary:
    """Trie + wildcard search: '.' matches any single character."""

    def __init__(self) -> None:
        raise NotImplementedError

    def add_word(self, word: str) -> None:
        raise NotImplementedError

    def search(self, word: str) -> bool:
        raise NotImplementedError


def autocomplete(trie: Trie, prefix: str, k: int) -> List[str]:
    """Up to k words with the prefix, alphabetically first (deterministic).

    Built by DFS in alphabetical order — collect until k, then stop.
    """
    raise NotImplementedError


def find_words(board: List[List[str]], words: List[str]) -> List[str]:
    """Words findable on contiguous 4-directional paths (a cell used at most
    once per word). Trie-pruned DFS. Return in any order; tests compare sets."""
    raise NotImplementedError


def longest_common_prefix_via_trie(words: List[str]) -> str:
    """Walk the trie while there is exactly one child and no terminal; stop
    at the first fork or terminal. Empty input -> ""; single word -> itself."""
    raise NotImplementedError
