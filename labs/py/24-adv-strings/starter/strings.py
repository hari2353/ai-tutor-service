"""Lab 24 — advanced strings: KMP, Z-algorithm, rolling hash. Fill in every
TODO. Tests define done.

Rules:
  * Pure stdlib, no imports needed.
  * Do NOT reach for str.find / `in` / regex to implement the searching
    functions — you are building them. The one sanctioned comparison is
    rabin_karp's window-vs-pattern check on a hash hit: that verification
    is the point of the algorithm.
  * kmp_search and z_search return ALL match positions, overlapping
    included, 0-based, ascending. Empty pattern -> [].
  * rabin_karp must be correct for ANY mod: a hash hit is a candidate,
    not a match — verify it (tiny mods that force collisions are a test).
"""
from __future__ import annotations


def kmp_prefix(s: str) -> list[int]:
    """KMP failure function (LPS). lps[i] = length of the longest proper
    prefix of s[:i+1] that is also a suffix of it; lps[0] = 0.

    "ababc" -> [0, 0, 1, 2, 0]
    "aaaa"  -> [0, 1, 2, 3]
    "aabxaabxcaabxaabx" -> [0, 1, 0, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 5, 6, 7, 8]
    ""      -> []
    """
    raise NotImplementedError


def kmp_search(text: str, pattern: str) -> list[int]:
    """All start indices where pattern occurs in text (overlapping included,
    ascending). Empty pattern or pattern longer than text -> [].

    kmp_search("ababa", "aba")   -> [0, 2]
    kmp_search("aaaab", "aaab")  -> [1]      # naive compares m chars at
    kmp_search("aaaaab", "aaab") -> [2]      # every offset and is O(nm)
    """
    raise NotImplementedError


def z_array(s: str) -> list[int]:
    """Z-values: z[i] = length of the longest substring starting at i that
    matches a prefix of s (for i >= 1); z[0] = 0 by convention.

    "aaaaa" -> [0, 4, 3, 2, 1]
    "ababc" -> [0, 0, 2, 0, 0]
    "aabxaabxcaabxaabx" -> [0, 1, 0, 0, 4, 1, 0, 0, 0, 8, 1, 0, 0, 4, 1, 0, 0]
    ""      -> []
    """
    raise NotImplementedError


def z_search(text: str, pattern: str) -> list[int]:
    """All pattern occurrences via z_array(pattern + "\\x00" + text): every
    index i with z[i] == len(pattern) is a match. The separator must not
    occur in either input. Same contract as kmp_search.

    z_search("aaaab", "aaab")  -> [1]
    z_search("aaaaab", "aaab") -> [2]
    """
    raise NotImplementedError


def rabin_karp(text: str, pattern: str, base: int = 256,
               mod: int = 1_000_000_007) -> list[int]:
    """All occurrences via a polynomial rolling hash (base 256, mod a
    large prime). Roll the window in O(1): drop the leaving character's
    base^(m-1) term, shift, add the entering character. On a hash hit,
    compare the window to the pattern before reporting it — correctness
    must hold for ANY mod, including ones small enough to collide
    constantly.

    With base=256, mod=13: hash("ab") == hash("da") — yet
    rabin_karp("dab", "ab", mod=13) -> [1], not [0, 1].
    """
    raise NotImplementedError


def longest_palindromic_substring(s: str) -> str:
    """Longest palindromic substring via expand-around-center over all
    2n-1 centers (odd and even). O(n^2) time, O(1) extra space.
    "" -> "". On length ties the reference returns the earliest occurrence.

    "babad" -> "bab" or "aba"
    "forgeeksskeegfor" -> "geeksskeeg"
    """
    raise NotImplementedError
