"""Lab 24 — reference solution."""
from __future__ import annotations


def kmp_prefix(s: str) -> list[int]:
    """KMP failure function (LPS): lps[i] = longest proper prefix of
    s[:i+1] that is also its suffix. O(n) amortized — len and jk each
    advance by at most 1 per iteration."""
    n = len(s)
    lps = [0] * n
    k = 0                                  # length of current prefix-suffix
    for i in range(1, n):
        while k > 0 and s[i] != s[k]:
            k = lps[k - 1]                 # fall back to the next border
        if s[i] == s[k]:
            k += 1
        lps[i] = k
    return lps


def kmp_search(text: str, pattern: str) -> list[int]:
    """All match positions, overlapping included. The text index i never
    decreases — the O(n+m) guarantee."""
    if not pattern or len(pattern) > len(text):
        return []
    lps = kmp_prefix(pattern)
    out: list[int] = []
    k = 0                                  # chars of pattern matched so far
    for i, ch in enumerate(text):
        while k > 0 and ch != pattern[k]:
            k = lps[k - 1]                 # mismatch: shift the pattern
        if ch == pattern[k]:
            k += 1
        if k == len(pattern):
            out.append(i - k + 1)
            k = lps[k - 1]                 # keep going for overlapping hits
    return out


def z_array(s: str) -> list[int]:
    """Z-values via a single rightmost Z-box [l, r). For i in the box,
    seed from z[i - l] instead of comparing from scratch."""
    n = len(s)
    z = [0] * n
    l = r = 0                              # current Z-box [l, r)
    for i in range(1, n):
        if i < r:
            z[i] = min(r - i, z[i - l])    # reuse what is already known
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1                      # extend past the box
        if i + z[i] > r:
            l, r = i, i + z[i]             # new rightmost box
    return z


def z_search(text: str, pattern: str) -> list[int]:
    """All occurrences via the concatenation trick."""
    if not pattern or len(pattern) > len(text):
        return []
    sep = "\x00"                           # must not occur in either input
    z = z_array(pattern + sep + text)
    m = len(pattern)
    start = m + 1                          # where text begins in concat
    return [i - start for i in range(start, len(z)) if z[i] == m]


def rabin_karp(text: str, pattern: str, base: int = 256,
               mod: int = 1_000_000_007) -> list[int]:
    """Polynomial rolling hash, O(1) window update, explicit verification
    on every hash hit — correct for any mod, collision or not."""
    n, m = len(text), len(pattern)
    if m == 0 or m > n:
        return []
    out: list[int] = []
    shift = pow(base, m - 1, mod)          # weight of the leading char
    ph = 0
    for ch in pattern:                    # pattern hash
        ph = (ph * base + ord(ch)) % mod
    th = 0
    for ch in text[:m]:                   # first window hash
        th = (th * base + ord(ch)) % mod
    for i in range(n - m + 1):
        if th == ph and text[i:i + m] == pattern:
            out.append(i)                 # verify: hash hit != match
        if i + m < n:                     # roll the window one char
            th = ((th - ord(text[i]) * shift) * base + ord(text[i + m])) % mod
    return out


def longest_palindromic_substring(s: str) -> str:
    """Expand around each of the 2n-1 centers. O(n^2), O(1) extra space."""
    if not s:
        return ""
    start = end = 0                        # inclusive bounds of best window

    def expand(lo: int, hi: int) -> tuple[int, int]:
        while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
            lo -= 1
            hi += 1
        return lo + 1, hi - 1              # last valid palindrome

    for c in range(len(s)):
        for lo, hi in (expand(c, c), expand(c, c + 1)):   # odd + even centers
            if hi - lo > end - start:
                start, end = lo, hi
    return s[start:end + 1]
