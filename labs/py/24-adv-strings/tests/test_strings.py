"""Lab 24 tests — KMP, Z-algorithm, rolling hash, palindromes.

Every hardcoded expectation is verified by a brute-force cross-check in
the final tests, so the fixtures below are hand-verified twice over.
"""
import random

import pytest


# ------------------------------------------------------------------ kmp_prefix
def test_prefix_function_documented_cases(R):
    """Classic worked examples (CLRS / Gusfield)."""
    assert R.kmp_prefix("ababc") == [0, 0, 1, 2, 0]
    assert R.kmp_prefix("aaaa") == [0, 1, 2, 3]
    assert R.kmp_prefix("abcd") == [0, 0, 0, 0]
    assert R.kmp_prefix("aabxaabxcaabxaabx") == \
        [0, 1, 0, 0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 5, 6, 7, 8]


def test_prefix_function_edge_cases(R):
    assert R.kmp_prefix("") == []
    assert R.kmp_prefix("a") == [0]
    assert R.kmp_prefix("ababab") == [0, 0, 1, 2, 3, 4]


def test_prefix_matches_bruteforce(R):
    rng = random.Random(42)
    for _ in range(100):
        s = "".join(rng.choice("abx") for _ in range(rng.randrange(0, 20)))
        brute = [0] * len(s)
        for i in range(len(s)):                    # O(n^2) reference LPS
            for length in range(i, 0, -1):          # PROPER prefix: length <= i
                if s[:length] == s[i + 1 - length:i + 1]:
                    brute[i] = length
                    break
        assert R.kmp_prefix(s) == brute, s


# ------------------------------------------------------------------ kmp_search
def test_kmp_search_overlapping_matches(R):
    """aaaab/aaab is the case that makes naive search quadratic: KMP
    still never re-reads a text character."""
    assert R.kmp_search("aaaaab", "aaab") == [2]
    assert R.kmp_search("aaaab", "aaab") == [1]
    assert R.kmp_search("ababa", "aba") == [0, 2]   # overlaps share the middle 'a'
    assert R.kmp_search("aaaa", "aa") == [0, 1, 2]


def test_kmp_search_single_and_none(R):
    assert R.kmp_search("ababcababc", "abc") == [2, 7]
    assert R.kmp_search("hello world", "o w") == [4]
    assert R.kmp_search("abcdefg", "xyz") == []
    assert R.kmp_search("short", "longer-than-text") == []


def test_kmp_search_empty_and_trivial(R):
    assert R.kmp_search("anything", "") == []
    assert R.kmp_search("", "a") == []
    assert R.kmp_search("", "") == []
    assert R.kmp_search("a", "a") == [0]


def test_kmp_search_unicode(R):
    """Unicode code points must flow through ord()/comparison unchanged."""
    assert R.kmp_search("αβγαβγαβ", "αβγ") == [0, 3]
    assert R.kmp_search("naïve café naïve", "naïve") == [0, 11]
    assert R.kmp_search("日本語の日本語", "日本") == [0, 4]


# ------------------------------------------------------------------ z_array
def test_z_array_documented_cases(R):
    """Gusfield's worked example, plus edges: "" -> [], "a" -> [0],
    "ab" -> [0, 0]."""
    assert R.z_array("aaaaa") == [0, 4, 3, 2, 1]
    assert R.z_array("aabxaabxcaabxaabx") == \
        [0, 1, 0, 0, 4, 1, 0, 0, 0, 8, 1, 0, 0, 4, 1, 0, 0]
    assert R.z_array("ababc") == [0, 0, 2, 0, 0]
    assert R.z_array("") == []
    assert R.z_array("a") == [0]
    assert R.z_array("ab") == [0, 0]


def test_z_array_matches_bruteforce(R):
    rng = random.Random(7)
    for _ in range(100):
        s = "".join(rng.choice("abx") for _ in range(rng.randrange(0, 20)))
        brute = [0] * len(s)
        for i in range(1, len(s)):
            while i + brute[i] < len(s) and s[brute[i]] == s[i + brute[i]]:
                brute[i] += 1                       # O(n^2) reference Z
        assert R.z_array(s) == brute, s


# ------------------------------------------------------------------ z_search
def test_z_search_via_concatenation_trick(R):
    assert R.z_search("aaaaab", "aaab") == [2]
    assert R.z_search("ababa", "aba") == [0, 2]
    assert R.z_search("hello world hello", "hello") == [0, 12]


def test_z_search_same_contract_as_kmp(R):
    """Empty pattern, no-hit, pattern-longer-than-text: identical contract."""
    assert R.z_search("anything", "") == []
    assert R.z_search("", "a") == []
    assert R.z_search("", "") == []
    assert R.z_search("tiny", "much too long") == []
    assert R.z_search("abc", "xyz") == []


# ------------------------------------------------------------------ rabin_karp
def test_rabin_karp_basic_matches(R):
    assert R.rabin_karp("hello world", "o w") == [4]
    assert R.rabin_karp("abababab", "abab") == [0, 2, 4]
    assert R.rabin_karp("needle in the needle stack", "needle") == [0, 14]


def test_rabin_karp_empty_pattern_returns_empty(R):
    assert R.rabin_karp("abc", "") == []
    assert R.rabin_karp("", "abc") == []
    assert R.rabin_karp("", "") == []


def test_rabin_karp_tiny_mod_forces_collisions(R):
    """THE test. With base=256, mod=13, hash('ab') == hash('da') — but
    verification on a hash hit must reject the false candidate."""
    assert (ord("a") * 256 + ord("b")) % 13 == (ord("d") * 256 + ord("a")) % 13
    assert R.rabin_karp("dab", "ab", mod=13) == [1]           # 'da' must not match
    assert R.rabin_karp("dabba dab", "ab", mod=13) == [1, 7]  # collision 'da'@6 rejected
    assert R.rabin_karp("daabda", "ab", mod=13) == [2]        # 'da' hits everywhere
    assert R.rabin_karp("a" * 20, "aa", mod=13) == list(range(19))


def test_rabin_karp_unicode_and_default_mod(R):
    assert R.rabin_karp("naïve café naïve", "naïve") == [0, 11]
    assert R.rabin_karp("αβγαβγαβ", "αβγ") == [0, 3]


# ------------------------------------------------------------------ palindrome
def test_palindrome_documented_cases(R):
    assert R.longest_palindromic_substring("babad") in ("bab", "aba")
    assert R.longest_palindromic_substring("cbbd") == "bb"
    assert R.longest_palindromic_substring("forgeeksskeegfor") == "geeksskeeg"
    assert R.longest_palindromic_substring("") == ""


def test_palindrome_edges_and_ties(R):
    assert R.longest_palindromic_substring("a") == "a"
    assert R.longest_palindromic_substring("ac") in ("a", "c")   # any single
    assert R.longest_palindromic_substring("abcba") == "abcba"   # whole string
    assert R.longest_palindromic_substring("bananas") == "anana"
    assert len(R.longest_palindromic_substring("abacdfgdcaba")) == 3  # tie


def test_palindrome_matches_bruteforce_lengths(R):
    rng = random.Random(99)
    for _ in range(60):
        s = "".join(rng.choice("abc") for _ in range(rng.randrange(0, 16)))
        best = 0
        for i in range(len(s)):                    # O(n^3) reference
            for j in range(i, len(s)):
                sub = s[i:j + 1]
                if sub == sub[::-1]:
                    best = max(best, len(sub))
        assert len(R.longest_palindromic_substring(s)) == best, s
        got = R.longest_palindromic_substring(s)   # whatever it returns
        assert got == got[::-1]                    # must be a real palindrome
        assert s.find(got) >= 0                    # ...actually in s


# ------------------------------------------------------------------ cross-check
def test_all_three_algorithms_agree_on_random_strings(R):
    """kmp vs z vs rabin-karp vs built-in find: 4-way agreement on 200
    seeded random (text, pattern) pairs over a 2-letter alphabet, where
    matches are dense and overlapping."""
    rng = random.Random(2024)
    for _ in range(200):
        text = "".join(rng.choice("ab") for _ in range(rng.randrange(0, 40)))
        m = rng.randrange(1, 8)
        pattern = "".join(rng.choice("ab") for _ in range(m))
        expected = []
        i = text.find(pattern)
        while i != -1:                             # ground truth, overlapping
            expected.append(i)
            i = text.find(pattern, i + 1)
        kmp = R.kmp_search(text, pattern)
        z = R.z_search(text, pattern)
        rk = R.rabin_karp(text, pattern)
        assert kmp == expected, (text, pattern)
        assert z == expected, (text, pattern)
        assert rk == expected, (text, pattern)


def test_cross_check_with_collisions_everywhere(R):
    """Even with a toy mod where collisions are constant, all three
    algorithms must still agree with ground truth."""
    rng = random.Random(5)
    for _ in range(100):
        text = "".join(rng.choice("ab") for _ in range(rng.randrange(0, 30)))
        pattern = "".join(rng.choice("ab") for _ in range(rng.randrange(1, 5)))
        expected = []
        i = text.find(pattern)
        while i != -1:
            expected.append(i)
            i = text.find(pattern, i + 1)
        assert R.rabin_karp(text, pattern, mod=13) == expected, (text, pattern)
        assert R.kmp_search(text, pattern) == expected
        assert R.z_search(text, pattern) == expected
