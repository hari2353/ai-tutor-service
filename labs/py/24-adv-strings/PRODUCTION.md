# Production notes — string algorithms

## Where you'd actually meet them

| Tool | Algorithm under the hood |
|---|---|
| `grep` (GNU) | Boyer-Moore / Aho-Corasick variants (Commentz-Walter) — sublinear average scans |
| `rsync` | Adler-32 rolling checksum (Rabin-Karp fingerprinting) to find fixed-size blocks that differ between files, then delta-encode only those |
| Bioinformatics (BLAST, short-read aligners) | k-mer indexes, seed-and-extend — KMP/Z-style exact seeds before expensive alignment |
| Plagiarism / document dedup | Rabin-Karp n-gram fingerprints at scale; SimHash/MinHash for near-dup |
| `git` / diff tools | Myers diff — but suffix-automaton-based prefiltering in some implementations |
| Compilers (lexer) | Aho-Corasick for keyword sets; suffix automata for token matching |

## What production adds over yours

- **Precomputed shift tables.** GNU grep uses a bad-character skip table allowing it to skip large chunks of the input, often scanning fewer bytes than the file contains — sublinear average. Yours reads every char.
- **Multiple patterns.** Aho-Corasick builds a trie of all patterns with failure links (KMP generalized to a trie) — O(text + patterns + matches). grep is a single automaton for the entire keyword list, not N separate scans.
- **Rolling checksums tuned for hardware.** rsync's Adler-32 is designed for cheap modulo (65521, near 2^16) — integer add/shift only, no 64-bit multiply, computable incrementally and recoverable when a block is found at a non-aligned offset. Cyclic polynomial (Buzhash) hashes avoid adversarial collisions by randomizing the byte→value table per run.
- **Double hashing / keyed hashes.** Plagiarism detection at scale fingerprints n-grams with two independent hashes (or a per-run random seed — see `rsync`'s `--rsh` checksum seed), dropping collision probability from ~`1/mod` to ~`1/mod²` and blocking adversarial inputs that could otherwise force O(nm) behavior.
- **Vectorized scan prefilter.** Real-world `memmem` implementations (glibc) use SIMD to find first-byte candidates, then confirm with `memcmp` — a constant-factor win that dominates wall-clock time in practice, more than the asymptotic difference between KMP and Boyer-Moore.
- **Suffix arrays / FM-index.** When the text is fixed and queried repeatedly (bioinformatics genome indexes — BWT/FM-index), a suffix array or full-text index answers each query in O(m) without rescanning the text at all. That's the scaling path when your bottleneck is repeated scans, not single searches.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Hash-based dedup merges distinct files | Rabin-Karp fingerprints colliding across huge corpora | Verify on hit (you did), or double-hash; never trust a single hash as equality |
| Worst-case O(nm) in hashing search | Adversarial input crafted against known (base, mod) | Randomize the seed per run; use a cryptographic hash where adversarial input is possible |
| Search slows as pattern count grows | Running one scan per pattern | Aho-Corasick: all patterns in one automaton |
| Same file re-scanned on every query | No index, rescanning text each time | Suffix array / FM-index / inverted k-mer index |
| Rolling hash overflow / precision bugs | Modular arithmetic errors on long strings | Use mod-safe integer ops (`pow(base, m-1, mod)`), never float pow, precompute the shift term once |

## Cost & latency

All three algorithms scan the text in O(n) with small constants — the practical differences show up only in specialized settings: multi-pattern (Aho-Corasick wins), delta-sync/dedup (rolling hash wins, since it enables block-level comparison without aligning blocks), or guaranteed-correctness single search (KMP/Z). For a single short pattern in memory, the SIMD-prefiltered `memmem` in your libc usually beats all of them.

## The 3 questions an interviewer asks after you describe this

1. *"Why does the failure function guarantee you never re-read a text character?"* — On mismatch, `lps` tells you how much of the already-matched prefix is reusable, so the text pointer only moves forward; the pattern's self-overlap substitutes for re-scanning the text.
2. *"Your hash hit just fired — is that a match?"* — No, it's a candidate; compare the window before claiming a match, otherwise a single collision silently corrupts results (this exact bug has hit real dedup and caching systems).
3. *"How does rsync use this?"* — Rolling checksum over fixed-size blocks on both ends; matching fingerprints let it skip re-transmitting unchanged blocks and delta-encode only the divergent ones — Rabin-Karp fingerprinting is what makes the window comparison O(1) per offset instead of O(block).
