# Advanced Strings: KMP, Z-Algorithm, Rabin-Karp Rolling Hash

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** T02-p02-sliding-window, arrays
> **Module id:** `T02-adv-strings` · **Tags:** advanced, string-matching, hashing
> **Lab:** `labs/py/24-adv-strings/`

## The 30-second version

All three solve some version of "find pattern P in text T" in better than the naive O(nm), but they get there by different mechanisms and have different failure profiles. KMP builds a failure function (longest proper prefix that's also a suffix, for every prefix of P) in O(m), then scans T once in O(n), guaranteeing exact matches with zero false positives — deterministic, no randomness, the right default when correctness must be airtight. The Z-algorithm builds a single array `Z[i]` = length of the longest substring starting at `i` that matches a prefix of the whole string, in O(n) over a concatenated `P + separator + T`; it's more general than KMP's failure function (same asymptotic cost, arguably easier to reason about once you see the box-management invariant) and is the natural tool when you need prefix-match lengths at every position, not just a yes/no match. Rabin-Karp uses a rolling polynomial hash to compare an O(1)-updated hash of each window against the pattern's hash, giving expected O(n+m) but with a real false-positive risk (hash collision) that must be resolved with an explicit character comparison, and a real worst-case of O(nm) if an adversary can construct collisions against your modulus. The decision rule: need a guaranteed-correct single-pattern match with no chance of collision, or an interviewer named "no hashing allowed" — KMP. Need prefix-match lengths at every position or multiple pattern occurrences in a structured way — Z-algorithm. Need multi-pattern matching, 2D pattern matching, or "does this substring equal that substring" comparisons across many candidates cheaply — rolling hash (accepting the collision risk and double-hashing or explicit-compare mitigation).

## Why this gets asked

It probes whether you understand *why* naive string matching is O(nm) (worst case, a pattern like "aaaa...ab" against a text of "aaaa...a" forces a full mismatch scan at every starting position) and whether you can derive a linear-time alternative instead of reaching for a language's built-in `str.find` and hand-waving the complexity. The production pain behind it is real: search engines, DNA sequence alignment (bioinformatics tooling is one of the biggest real-world consumers of KMP/Z/suffix structures), log-grep tooling, and plagiarism/duplicate detection all need substring or near-duplicate matching at scale where O(nm) genuinely doesn't finish in time. It also tests whether you know rolling hash is probabilistic — using it without acknowledging the collision risk, or without a double-check compare or double-hashing scheme, is a real correctness bug that has bitten production deduplication and caching systems (two different byte ranges hashing identically and getting deduplicated as if equal).

---

## Lineage: past → present → future

**What came before.** Naive substring search — slide the pattern across the text, comparing character by character, restarting from scratch on every mismatch — is the obvious first algorithm and is O(nm) worst case; it was the default in early text editors and is still what a `for` loop written under pressure looks like. The failure mode that killed it for serious use: adversarial or repetitive text (biological sequences with long runs of the same base, or crafted inputs) makes the naive approach's worst case actually materialize, not just a theoretical concern.

**Where it stands now.** Knuth-Morris-Pratt (Knuth, Morris, and Pratt, 1977) was the first algorithm to guarantee O(n+m) by never re-examining a text character after a mismatch, reusing the information already extracted about the pattern's own self-overlap; it remains the standard "no false positives, no hashing" answer. The Z-algorithm (formalized later, widely attributed through Gusfield's 1997 string-algorithms textbook, itself built on ideas going back to the 1970s) achieves the same O(n) bound with an arguably simpler invariant (a single sliding "Z-box" window) and generalizes more naturally to problems beyond exact pattern matching, like finding all border lengths or computing string periods. Rabin-Karp (Rabin and Karp, 1987) took a completely different approach, trading a deterministic guarantee for expected-case speed and enabling multi-pattern search cheaply (hash every pattern once, then scan the text's rolling hash against a set) — its main production use today is in duplicate-content detection, plagiarism checkers, and as the substring-matching primitive inside `rsync`-style delta-sync algorithms (rolling hash to find where two files diverge). Suffix automata, suffix arrays, and suffix trees (Ukkonen's O(n) suffix tree construction, 1995) are the modern generalization for "answer many pattern queries against one fixed text," used in bioinformatics genome indexing and full-text search engines, but they're a materially bigger structure than an interview typically expects you to implement from scratch.

**Where it's heading.** No foundational change is expected in the core three algorithms; they're closed 20th-century results with stable, well-understood proofs. The applied direction is approximate/fuzzy matching at scale — locality-sensitive hashing (LSH) for near-duplicate detection (SimHash, MinHash) used in large-scale document dedup and plagiarism systems, which trades exactness for sublinear similarity search over massive corpora, and embedding-based semantic "fuzzy substring" matching in retrieval systems, which is a genuinely different tool (nearest-neighbor search over vector embeddings) rather than an evolution of exact string matching. Treat LSH/embeddings as adjacent, not a replacement — exact substring matching (KMP/Z/Rabin-Karp) is still what you reach for when the match must be exact.

---

## Mental model

KMP's failure function tells you, on a mismatch, exactly how far back in the pattern you can safely resume without ever re-reading a text character you've already consumed — because the prefix of the pattern that matched so far has a known self-overlap you can exploit instead of restarting from scratch.

```
Pattern: A B A B C
Failure function (longest proper prefix == suffix, per prefix length):
index:    0 1 2 3 4
char:     A B A B C
lps:      0 0 1 2 0

Matching "ABABABC" against pattern "ABABC":
text:    A B A B A B C
pattern: A B A B C
mismatch at pattern[4]='C' vs text[4]='A', but pattern[0..3]="ABAB" has
lps[3]=2, meaning "AB" is both a prefix and suffix of "ABAB" -- so instead
of restarting the pattern at index 0, resume comparing at pattern index 2,
reusing the already-matched "AB" overlap instead of re-scanning the text.
```

The Z-array is a single sliding window ("Z-box") that remembers the rightmost prefix-match found so far, so that computing `Z[i]` for later positions can reuse work already done instead of comparing from scratch.

```
String: a a b a a b a a a  (index 0..8)
Z:      0 1 0 3 1 0 2 1 0
Z[3]=3 means "aab" starting at index 3 matches the first 3 characters "aab".
Z-box mechanism: while computing Z[i] for i inside a known matching box
[L,R], initialize Z[i] from Z[i-L] instead of comparing character by
character from scratch, then extend past R only if needed.
```

Rabin-Karp treats a string window as a number in some base (like reading digits), and updates that number in O(1) as the window slides by subtracting the leaving digit's contribution and adding the entering digit's, avoiding recomputing the whole hash from scratch.

```
window "abc" -> hash = a*B^2 + b*B^1 + c*B^0  (mod M)
slide to "bcd":
new_hash = (hash - a*B^2) * B + d   (mod M)
           remove leaving char's weighted contribution, shift, add new char
```

---

## Recognition heuristics

- **"Find all occurrences of pattern P in text T"**, guaranteed exact, no hashing — KMP or Z-algorithm; both are O(n+m) and either is acceptable, but KMP is the traditionally expected answer.
- **"Compute the failure function / longest proper prefix-suffix for every prefix"**, or **"find the shortest repeating unit (period) of a string"** — KMP's `lps` array directly answers this: if `n - lps[n-1]` divides `n`, that's the period length.
- **"For every position, how long is the matching prefix starting there"** — Z-array, directly.
- **"Multiple patterns, one text"** or **"does any of these k patterns appear"** — Rabin-Karp with a hash set of pattern hashes, or Aho-Corasick (a further generalization, out of scope here but worth naming) if k is large.
- **"Check if string A is a rotation of string B"** — concatenate `B+B`, then KMP/Z/substring-search for `A` inside it in O(n).
- **"Longest common substring between two strings, hashed comparison allowed"** — binary search on length + rolling hash set comparison, O(n log n) instead of the O(nm) DP.
- **"Detect near-duplicate documents at scale"** — this is explicitly *not* exact substring matching; it's the tell that the expected answer is MinHash/SimHash/LSH, not KMP/Z/Rabin-Karp.
- **A qualifier like "using only O(1) extra space per comparison, no extra data structure"** attached to a hashing-flavored problem — signals rolling hash is expected specifically because it avoids building an auxiliary structure like a suffix array.

---

## How it actually works — deriving KMP's failure function and why Rabin-Karp needs a real compare on hash match

The KMP failure function `lps[i]` (for pattern index `i`, 0-indexed) is defined as the length of the longest proper prefix of `pattern[0..i]` that's also a proper suffix of it. It's built with a two-pointer method inside the pattern itself: maintain `len` (length of the current matching prefix-suffix), and for each new character, if it matches `pattern[len]`, extend `len` and record it; if it doesn't match and `len > 0`, fall back to `lps[len-1]` (reusing the already-known overlap of a shorter prefix) instead of resetting to 0 outright, exactly the same trick applied recursively. This construction is itself O(m) because `len` only increases by at most 1 per outer iteration and only decreases via the fallback, and the total decrease across the whole loop is bounded by the total increase — the classic amortized-analysis argument. During the main scan, on a text/pattern mismatch at pattern index `j`, instead of restarting the pattern pointer at 0, jump to `lps[j-1]` — this is valid precisely because `pattern[0..lps[j-1]-1]` is guaranteed to already match the text at the current position (it's a suffix of what just matched), so no text character needs to be re-read. That "never move the text pointer backward" property is what makes KMP O(n+m) instead of O(nm).

Rabin-Karp's rolling hash update is O(1) via the polynomial-hash-in-a-modulus trick shown above, giving expected O(n+m) total. The catch: two different strings can hash to the same value modulo `M` (a collision), and if you skip the character-by-character verification on a hash match, you get a false positive — the algorithm reports a match that isn't real. The standard fix is to always verify a hash match with an explicit O(m) character comparison (the *expected* total cost stays O(n+m) because true collisions are rare with a good modulus and base, but the *worst case* is still O(nm) if an adversary can force many collisions against your specific modulus, which is possible if the modulus is small, fixed, and known — a real, documented attack surface for hash-based deduplication systems that select a single fixed 32-bit modulus). Using a large random prime modulus, or double-hashing with two independent bases/moduli and requiring both to match before even the verification step, is how production systems reduce this risk to negligible without paying the O(m) compare on every window.

---

## Template code (Python, Java, Go)

```python
# KMP — failure function (lps) + search
def kmp_failure(pattern: str) -> list[int]:
    m = len(pattern)
    lps = [0] * m
    length = 0
    i = 1
    while i < m:
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        elif length > 0:
            length = lps[length - 1]  # reuse known overlap, don't reset to 0
        else:
            lps[i] = 0
            i += 1
    return lps

def kmp_search(text: str, pattern: str) -> list[int]:
    if not pattern:
        return []
    lps = kmp_failure(pattern)
    matches = []
    i = j = 0  # i: text pointer, j: pattern pointer
    while i < len(text):
        if text[i] == pattern[j]:
            i += 1
            j += 1
            if j == len(pattern):
                matches.append(i - j)
                j = lps[j - 1]
        elif j > 0:
            j = lps[j - 1]
        else:
            i += 1
    return matches


# Z-algorithm
def z_array(s: str) -> list[int]:
    n = len(s)
    z = [0] * n
    z[0] = n
    l, r = 0, 0
    for i in range(1, n):
        if i < r:
            z[i] = min(r - i, z[i - l])
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1
        if i + z[i] > r:
            l, r = i, i + z[i]
    return z

def z_search(text: str, pattern: str) -> list[int]:
    combined = pattern + "\x00" + text  # separator not present in either string
    z = z_array(combined)
    m = len(pattern)
    return [i - m - 1 for i in range(m + 1, len(combined)) if z[i] >= m]


# Rabin-Karp rolling hash
def rabin_karp(text: str, pattern: str, base: int = 256, mod: int = 1_000_000_007) -> list[int]:
    n, m = len(text), len(pattern)
    if m == 0 or m > n:
        return []
    high_pow = pow(base, m - 1, mod)
    pattern_hash = 0
    window_hash = 0
    for i in range(m):
        pattern_hash = (pattern_hash * base + ord(pattern[i])) % mod
        window_hash = (window_hash * base + ord(text[i])) % mod

    matches = []
    for i in range(n - m + 1):
        if window_hash == pattern_hash and text[i:i + m] == pattern:  # verify on hash hit
            matches.append(i)
        if i + m < n:
            window_hash = ((window_hash - ord(text[i]) * high_pow) * base + ord(text[i + m])) % mod
            window_hash %= mod
    return matches
```

```java
import java.util.*;

public class StringMatching {

    // KMP
    static int[] kmpFailure(String pattern) {
        int m = pattern.length();
        int[] lps = new int[m];
        int length = 0, i = 1;
        while (i < m) {
            if (pattern.charAt(i) == pattern.charAt(length)) {
                lps[i++] = ++length;
            } else if (length > 0) {
                length = lps[length - 1];
            } else {
                lps[i++] = 0;
            }
        }
        return lps;
    }

    static List<Integer> kmpSearch(String text, String pattern) {
        List<Integer> matches = new ArrayList<>();
        if (pattern.isEmpty()) return matches;
        int[] lps = kmpFailure(pattern);
        int i = 0, j = 0;
        while (i < text.length()) {
            if (text.charAt(i) == pattern.charAt(j)) {
                i++; j++;
                if (j == pattern.length()) {
                    matches.add(i - j);
                    j = lps[j - 1];
                }
            } else if (j > 0) {
                j = lps[j - 1];
            } else {
                i++;
            }
        }
        return matches;
    }

    // Z-algorithm
    static int[] zArray(String s) {
        int n = s.length();
        int[] z = new int[n];
        z[0] = n;
        int l = 0, r = 0;
        for (int i = 1; i < n; i++) {
            if (i < r) z[i] = Math.min(r - i, z[i - l]);
            while (i + z[i] < n && s.charAt(z[i]) == s.charAt(i + z[i])) z[i]++;
            if (i + z[i] > r) { l = i; r = i + z[i]; }
        }
        return z;
    }

    // Rabin-Karp
    static List<Integer> rabinKarp(String text, String pattern, long base, long mod) {
        List<Integer> matches = new ArrayList<>();
        int n = text.length(), m = pattern.length();
        if (m == 0 || m > n) return matches;
        long highPow = 1;
        for (int i = 0; i < m - 1; i++) highPow = (highPow * base) % mod;
        long patternHash = 0, windowHash = 0;
        for (int i = 0; i < m; i++) {
            patternHash = (patternHash * base + pattern.charAt(i)) % mod;
            windowHash = (windowHash * base + text.charAt(i)) % mod;
        }
        for (int i = 0; i <= n - m; i++) {
            if (windowHash == patternHash && text.substring(i, i + m).equals(pattern)) {
                matches.add(i);
            }
            if (i + m < n) {
                windowHash = ((windowHash - text.charAt(i) * highPow % mod + mod) * base
                        + text.charAt(i + m)) % mod;
            }
        }
        return matches;
    }
}
```

```go
package main

// KMP
func kmpFailure(pattern string) []int {
    m := len(pattern)
    lps := make([]int, m)
    length, i := 0, 1
    for i < m {
        if pattern[i] == pattern[length] {
            length++
            lps[i] = length
            i++
        } else if length > 0 {
            length = lps[length-1]
        } else {
            lps[i] = 0
            i++
        }
    }
    return lps
}

func kmpSearch(text, pattern string) []int {
    var matches []int
    if len(pattern) == 0 {
        return matches
    }
    lps := kmpFailure(pattern)
    i, j := 0, 0
    for i < len(text) {
        if text[i] == pattern[j] {
            i++
            j++
            if j == len(pattern) {
                matches = append(matches, i-j)
                j = lps[j-1]
            }
        } else if j > 0 {
            j = lps[j-1]
        } else {
            i++
        }
    }
    return matches
}

// Z-algorithm
func zArray(s string) []int {
    n := len(s)
    z := make([]int, n)
    z[0] = n
    l, r := 0, 0
    for i := 1; i < n; i++ {
        if i < r {
            if r-i < z[i-l] {
                z[i] = r - i
            } else {
                z[i] = z[i-l]
            }
        }
        for i+z[i] < n && s[z[i]] == s[i+z[i]] {
            z[i]++
        }
        if i+z[i] > r {
            l, r = i, i+z[i]
        }
    }
    return z
}

// Rabin-Karp
func rabinKarp(text, pattern string, base, mod int64) []int {
    var matches []int
    n, m := len(text), len(pattern)
    if m == 0 || m > n {
        return matches
    }
    highPow := int64(1)
    for i := 0; i < m-1; i++ {
        highPow = (highPow * base) % mod
    }
    var patternHash, windowHash int64
    for i := 0; i < m; i++ {
        patternHash = (patternHash*base + int64(pattern[i])) % mod
        windowHash = (windowHash*base + int64(text[i])) % mod
    }
    for i := 0; i <= n-m; i++ {
        if windowHash == patternHash && text[i:i+m] == pattern {
            matches = append(matches, i)
        }
        if i+m < n {
            windowHash = ((windowHash-int64(text[i])*highPow%mod+mod)*base + int64(text[i+m])) % mod
        }
    }
    return matches
}
```

## Complexity — derived, not asserted

**KMP:** building `lps` is O(m) by the amortized argument (the fallback pointer `length` can decrease at most as many times total as it increased, and it increases at most once per outer loop iteration). The main search is O(n) because the text pointer `i` never moves backward — every character of the text is examined a bounded number of times (in fact, each character is compared at most twice in total across the whole algorithm, once per possible mismatch chain). Total: O(n+m), with zero risk of false positives since it's a direct character comparison, not a hash.

**Z-algorithm:** the same O(n) bound, via the box-reuse argument — each position's Z-value computation either reuses a previous result in O(1) (when inside the current box) or extends the box's right boundary `r`, and `r` only ever increases, bounding the total extension work across the whole array to O(n).

**Rabin-Karp:** hash computation for pattern and first window is O(m); each subsequent window update is O(1); total scanning is O(n). Expected total with verification is O(n+m) assuming few collisions. Worst case, if every window collides with the pattern's hash (adversarially constructible against a small or predictable modulus), every window pays its O(m) verification, degrading to O(nm) — the same worst case as naive search, which is exactly why Rabin-Karp is a probabilistic-in-practice algorithm, not a deterministic guarantee like KMP.

---

## The 5 variants interviewers actually ask

1. **Implement strStr() / find first occurrence of a pattern in a text (LC 28).** The baseline KMP or Z-algorithm implementation check.
2. **Repeated Substring Pattern (LC 459): can a string be built by repeating a substring?** KMP's `lps` array answers this directly: let `n` be the string length; if `n % (n - lps[n-1]) == 0`, the string is periodic with period `n - lps[n-1]`.
3. **Shortest Palindrome (LC 214): find the shortest palindrome by adding characters to the front.** Build `s + separator + reverse(s)`, run KMP's failure function on it; `lps[-1]` gives the longest palindromic prefix of `s`, and the remaining suffix (reversed) is what needs to be prepended.
4. **Longest Happy Prefix (LC 1392): longest proper prefix that's also a proper suffix of the whole string.** This is literally `lps[n-1]` from KMP's failure function on the string itself — no search needed, just the failure-function construction.
5. **Find all anagram-substring start indices, or find duplicate substrings of a fixed length (Repeated DNA Sequences, LC 187).** Rolling hash over fixed-length windows, storing seen hashes in a set (with real collision-safety via double hashing or verification), is the standard approach when the window length is fixed and you're checking membership across many windows rather than matching one specific pattern.

---

## Common bugs and how this gets written wrong under pressure

- **Resetting the pattern pointer to 0 on every KMP mismatch instead of falling back to `lps[j-1]`.** This silently degrades KMP into the naive O(nm) algorithm while still "looking like" KMP code — the bug doesn't crash, it just loses the entire point of the algorithm.
- **Off-by-one in the `lps` array's meaning.** `lps[i]` describes the prefix ending at index `i` inclusive; using it as if it described the prefix of length `i` (exclusive) shifts every fallback by one and produces subtly wrong match positions, often only visible on patterns with non-trivial internal repetition.
- **Skipping the explicit character-by-character verification after a Rabin-Karp hash match.** This turns a probabilistic-but-safe algorithm into one with real false positives; it's the single most common way Rabin-Karp gets "implemented" incorrectly in an interview, because it looks like an optimization ("if the hash matches, why check again?") when it's actually removing the algorithm's correctness guarantee.
- **Recomputing the modular exponent `base^(m-1)` inside the sliding loop instead of once upfront.** This silently degrades the O(1)-per-step rolling update to O(m) per step, losing the entire asymptotic benefit over naive search while still "working."
- **Choosing a small, fixed, well-known modulus for Rabin-Karp** (like a small prime under 10^5) in a system exposed to adversarial input (user-uploaded content, deduplication services) — an attacker can construct many strings that collide under that specific modulus, degrading the expected-case guarantee into the O(nm) worst case deliberately, which is a documented algorithmic-complexity-attack pattern, not a hypothetical.
- **Forgetting the separator character between pattern and text in the Z-algorithm's concatenation trick**, or choosing a separator that can actually appear in either string — this corrupts the Z-values at the boundary and produces false matches or missed matches right at the seam.

---

## Interview questions

### Q1 — Implement strStr(): find the first occurrence of a pattern in a text (LC 28).
**Testing:** can you write correct KMP (or Z-algorithm) from scratch, not just call a library function.
**Answer:** Build the failure function in O(m), then scan the text once in O(n), falling back via `lps` on mismatch instead of restarting.
**Follow-up trap:** *"What's wrong with just using the language's built-in substring search here?"* — nothing in production, but the interviewer wants to see you can derive the O(n+m) algorithm yourself; naming the built-in as the practical answer *and* being able to implement KMP on request is the correct posture.

### Q2 — Repeated Substring Pattern (LC 459): can the string be constructed by repeating a substring?
**Testing:** recognizing the failure function encodes periodicity directly.
**Answer:** Compute `lps` on the string; if `n % (n - lps[n-1]) == 0`, the string has period `n - lps[n-1]` and is fully repeated.
**Follow-up trap:** *"Prove why this works."* — if a string has period `p` (i.e., `s[i] == s[i+p]` for all valid `i`), then the prefix of length `n-p` is both a prefix and a suffix of the whole string by construction, so `lps[n-1] >= n-p`; conversely a maximal `lps[n-1]` value forces the tightest possible period, and the divisibility check confirms it tiles evenly.

### Q3 — Why does Rabin-Karp need an explicit character comparison even after a hash match?
**Testing:** understanding that hashing is probabilistic, not a proof of equality.
**Answer:** Two different strings can hash to the same value mod M (a collision); without verifying, a hash match is reported as a real match even when the underlying strings differ.
**Follow-up trap:** *"How do you reduce this risk without paying O(m) on every window?"* — double hashing (two independent base/modulus pairs, require both to match before verifying) makes accidental collisions astronomically unlikely while keeping verification rare in the expected case; it doesn't eliminate the *need* for verification in a fully rigorous implementation, but it makes skipping verification defensible in practice for many non-adversarial systems.

### Q4 — An adversary controls the input to your Rabin-Karp-based deduplication service. What can go wrong?
**Testing:** awareness of algorithmic-complexity attacks against hash-based matching.
**Answer:** If the modulus is small, fixed, and known (or guessable), an attacker can construct many strings that collide under that modulus, forcing the O(m) verification path on every window and degrading the service to O(nm) — a denial-of-service vector, not just a correctness edge case.
**Follow-up trap:** *"How would you harden it?"* — use a large random-seeded modulus chosen at process start (not compile-time constant), or double hashing with independently random parameters, so an attacker can't precompute collisions offline against a known modulus.

### Q5 — Longest Happy Prefix (LC 1392): longest string that's both a proper prefix and proper suffix.
**Testing:** recognizing `lps[n-1]` directly answers this without any additional search.
**Answer:** Run KMP's failure-function construction on the string itself; the answer is the prefix of length `lps[n-1]`.
**Follow-up trap:** *"What if you needed the second-longest such prefix-suffix, not just the longest?"* — follow the failure-function chain: `lps[lps[n-1]-1]` gives the next-longest border, and you can keep following the chain to enumerate all borders in decreasing length, each in O(1) amortized.

### Q6 — Shortest Palindrome (LC 214): minimum characters to prepend to make the whole string a palindrome.
**Testing:** combining KMP with a string-transformation trick.
**Answer:** Build `s + '#' + reverse(s)` (separator must not appear in `s`), run the failure function; `lps[-1]` is the length of the longest palindromic prefix of `s`, and the remaining suffix of `s` (reversed) is exactly what must be prepended.
**Follow-up trap:** *"Why not just check every prefix for being a palindrome directly?"* — that's O(n^2) in the worst case (checking each of n prefixes takes O(n)); the KMP construction gets the same answer in O(n).

### Q7 — Compute, for every position in a string, the length of the longest substring starting there that matches the string's own prefix.
**Testing:** direct Z-algorithm application, no disguise.
**Answer:** The Z-array, computed in O(n) using the box-reuse invariant.
**Follow-up trap:** *"How would you use the Z-array to find all occurrences of pattern P in text T?"* — concatenate `P + separator + T`, compute Z on the combined string, and every position `i` in the T portion with `Z[i] >= len(P)` marks a match start.

### Q8 — Repeated DNA Sequences (LC 187): find all 10-letter substrings that occur more than once.
**Testing:** recognizing fixed-length-window deduplication as a rolling-hash problem, not a KMP problem.
**Answer:** Rolling hash every 10-character window in O(1) per slide, track seen hashes in a set, and report any hash seen more than once (with verification or double hashing to avoid false positives).
**Follow-up trap:** *"Could you solve this with a plain hash set of substrings instead?"* — yes, and for DNA-length windows (short, fixed length) it's often simpler and just as fast in practice; the rolling hash mainly pays off when window length is large or the number of windows is huge enough that recomputing substring hashes from scratch (or slicing strings) becomes the bottleneck.

### Q9 — Given two strings, find their longest common substring using hashing instead of the O(nm) DP.
**Testing:** binary-search-on-answer combined with rolling hash, a staff-level combination.
**Answer:** Binary search on candidate length `L`; for each `L`, compute rolling hashes of all length-`L` substrings of both strings and check for any common hash (with verification), giving O(n log n) instead of the classic O(nm) DP.
**Follow-up trap:** *"Why does binary search on length work here?"* — because "does a common substring of length L exist" is monotonic: if a common substring of length L exists, one of length L-1 (a substring of it) also exists, so the existence predicate is monotonic in L, which is exactly the precondition for binary search on the answer.

### Q10 — Explain the amortized O(m) bound for building KMP's failure function.
**Testing:** whether you can actually prove the complexity, not just state it.
**Answer:** The pointer `length` increases by at most 1 per outer-loop iteration (at most m total increases across the whole construction) and only decreases via the fallback `length = lps[length-1]`; since it can't go below 0 and its total increase is bounded by m, its total decrease across the entire construction is also bounded by m, making the whole construction O(m) amortized rather than O(m^2) in the naive worst case.
**Follow-up trap:** *"Is this the same argument as the Z-algorithm's box-reuse bound?"* — structurally yes: both rely on a monotonically-bounded pointer/boundary that can only move forward a total of O(n) times across the whole algorithm, with any apparent "backward" step being O(1) amortized against prior forward progress.

### Q11 — Multi-pattern search: given k patterns and one text, find all occurrences of any pattern.
**Testing:** knowing when Rabin-Karp's per-pattern hashing generalizes and when it doesn't scale.
**Answer:** Hash all k patterns of the same length into a set, then roll a single hash across the text checking set membership at each window — O(n + k) if all patterns share a length; for variable-length patterns, this doesn't directly work and Aho-Corasick (a trie of patterns with failure links, generalizing KMP to many patterns simultaneously) is the correct O(n + sum(pattern lengths) + matches) tool.
**Follow-up trap:** *"Why can't you just run KMP k times?"* — you can, but that costs O(k*n + sum(pattern lengths)), which is worse than Aho-Corasick's single O(n) text scan when k and n are both large; naming Aho-Corasick as the right escalation, even without implementing it, is the senior signal here.

---

## Red flags that fail you

- Resetting the KMP pattern pointer to 0 on mismatch instead of using the failure function's fallback — silently degrading to naive O(nm) while claiming it's KMP.
- Skipping the verification step after a Rabin-Karp hash match and calling it correct.
- Not knowing Rabin-Karp's worst case is O(nm), same as naive search, under adversarial collisions.
- Confusing the Z-array's definition (match against the *whole string's prefix*) with the KMP failure function's definition (match against *the current prefix's own suffix*) — they answer related but distinct questions.
- Reaching for rolling hash / near-duplicate techniques (MinHash/SimHash) when the problem actually needs exact matching, or vice versa.
- Not being able to derive why KMP's total runtime is O(n+m) — reciting the algorithm without the amortized-pointer argument.

---

## Cheat card

```
KMP            O(n+m), deterministic exact match, zero false positives
               lps[i] = longest proper prefix==suffix of pattern[0..i]
               mismatch -> j = lps[j-1], NEVER reset text pointer i
               lps[n-1] on the string itself = periodicity / longest border
Z-ALGORITHM    O(n), Z[i] = longest match with the string's own prefix
               starting at i; box [L,R] reuse: Z[i] init from Z[i-L] if i<R
               pattern search: Z(P + sep + T), match where Z[i] >= len(P)
RABIN-KARP     expected O(n+m), worst case O(nm) under hash collisions
               rolling hash: O(1) update per window slide
               ALWAYS verify a hash match with explicit compare
               small/fixed modulus = exploitable collision attack surface
DECISION       exact + no hashing allowed -> KMP
               need prefix-match length at every position -> Z
               multi-pattern / fixed-window dedup -> rolling hash (+ verify)
               near-duplicate at scale -> MinHash/SimHash/LSH (different tool)
WATCH          off-by-one in lps semantics; recomputing base^(m-1) inside
               the loop; separator collision in Z-algorithm concatenation
```

## Sources

- Knuth, D., Morris, J., Pratt, V. (1977). "Fast Pattern Matching in Strings." SIAM Journal on Computing, 6(2), 323-350.
- Rabin, M., Karp, R. (1987). "Efficient Randomized Pattern-Matching Algorithms." IBM Journal of Research and Development, 31(2), 249-260.
- Gusfield, D. (1997). *Algorithms on Strings, Trees, and Sequences*, Cambridge University Press (standard reference for the Z-algorithm formalization).
- [Z-function — CP-Algorithms](https://cp-algorithms.com/string/z-function.html) — accessed 2026-07-26
- [Prefix function (KMP) — CP-Algorithms](https://cp-algorithms.com/string/prefix-function.html) — accessed 2026-07-26
- [Implement strStr() — LeetCode](https://leetcode.com/problems/find-the-index-of-the-first-occurrence-in-a-string/) — accessed 2026-07-26
- [Repeated Substring Pattern — LeetCode](https://leetcode.com/problems/repeated-substring-pattern/) — accessed 2026-07-26
- [Repeated DNA Sequences — LeetCode](https://leetcode.com/problems/repeated-dna-sequences/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
