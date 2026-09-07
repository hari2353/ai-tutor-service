# Lab 24: KMP, Z-Algorithm, Rolling Hash

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-adv-strings`

**You will build:** exact substring search three ways — KMP with its failure function, the Z-algorithm with the separator trick, and Rabin-Karp with a collision-verified rolling hash — plus expand-around-center longest palindromic substring, all from scratch in pure stdlib.

**You will be able to answer:** *"Walk me through a KMP implementation — why does the failure function mean you never re-read the text, and when would you reach for Rabin-Karp or the Z-algorithm instead?"*

## Setup

```bash
cd labs/py/24-adv-strings
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`kmp_prefix(s)`** — the failure function (LPS). `lps[i]` = length of the longest proper prefix of `s[:i+1]` that is also a suffix of it; `lps[0] = 0`. `"ababc"` → `[0, 0, 1, 2, 0]`; `"aaaa"` → `[0, 1, 2, 3]`. O(n) amortized — no re-scan loops that degrade to O(n²).
2. **`kmp_search(text, pattern)`** — ALL match positions, overlapping included, 0-based, ascending. Empty pattern → `[]`; pattern longer than text → `[]`. On mismatch the text index never moves backwards — that is the O(n+m) argument.
3. **`z_array(s)`** — `z[i]` = length of the longest substring starting at `i` that matches a prefix of `s`, for `i ≥ 1`; `z[0] = 0` by convention. `"aaaaa"` → `[0, 4, 3, 2, 1]`. Must reuse the current Z-box `[l, r)` instead of comparing from scratch at every index.
4. **`z_search(text, pattern)`** — the concatenation trick: compute `z_array(pattern + "\x00" + text)` and report every index `i` with `z[i] == len(pattern)` (the `\x00` separator must not occur in either input). Same all-positions / empty-pattern contract as `kmp_search`.
5. **`rabin_karp(text, pattern, base=256, mod=1_000_000_007)`** — polynomial rolling hash with an O(1) window update (subtract the leaving character's `base^(m-1)` term, shift, add the entering character). A hash hit is a *candidate*, not a match: verify it with a real comparison before reporting. Must return exact positions for **any** `mod` — a test runs `mod=13`, where `"ab"` and `"da"` hash identically, and still demands correct output.
6. **`longest_palindromic_substring(s)`** — expand around each of the `2n−1` centers (odd and even). O(n²) time, O(1) extra space. Empty string → `""`. On length ties any longest answer is accepted (the reference returns the earliest occurrence).

Rules: pure stdlib; no `str.find` / `in` / regex inside the search functions — you are building them (Rabin-Karp's on-hit window comparison is the mandated exception); no `time.sleep` anywhere.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Boyer-Moore bad-character heuristic** — precompute the last-occurrence table, skip by shift when the text char isn't in the pattern. *(Interview: "grep uses which algorithm, and why is sublinear average the real goal?")*
2. **Manacher's algorithm** — O(n) longest palindrome via the parity-transformed string. What does mirroring inside the rightmost palindrome boundary buy you? *(Interview: "can you beat expand-around-center asymptotically?")*
3. **Multi-pattern Rabin-Karp** — hash a set of same-length patterns into a dict, scan the text once, match them all. *(Interview: "how do plagiarism checkers scale to thousands of fingerprints?")*
4. **Double hashing** — two independent `(base, mod)` pairs, hit only when both agree; collision probability drops to ~`1/mod²`. *(Interview: "why is one hash not enough at scale, and what does an adversarial input do to your complexity?")*
