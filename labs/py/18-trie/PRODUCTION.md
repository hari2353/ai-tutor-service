# Production notes — tries

## Where tries ship

- **Typeahead** — search-box autocomplete is a trie walk: the prefix descends one node per keystroke, then a bounded-k DFS collects candidates. Real systems add per-node popularity heaps (your stretch goal) and cache hot prefixes.
- **IP routing — longest-prefix match** — routers forward on the most specific route: a *binary* trie (bit-level, path-compressed — a "Patricia/radix tree") over CIDR prefixes. This is the single most performance-critical trie in the world: done per-packet in ASICs.
- **Compilers & interpreters** — symbol tables and keyword recognizers are tries (perfect hashing for keywords is the trie's cousin).
- **Spellcheck / predictive text** — SymSpell and BK-trees dominate now, but the classic spellchecker dictionary walk is a trie with edit-distance budget (your fuzzy stretch goal).
- **String interning & DB indexes** — Elasticsearch `index-prefixes`, Postgres `pg_trgm` cousins; Td-idf inverted indexes use term dictionaries stored as FSTs (finite-state tries — Lucene) which compress to a few bytes per term.

## Complexity table

| Operation | Trie | Hash map | Sorted list |
|---|---|---|---|
| insert / exact search | O(L) | O(L) avg | O(log n) compares |
| prefix query / autocomplete | **O(L + k·L̃)** | impossible | O(log n + k) |
| wildcard `.` search | O(nodes^d) worst | n/a | n/a |
| longest common prefix | O(total chars) | n/a | O(n·L) sort |
| memory | O(total chars) worst, ~26× branching | O(total chars) once | O(total chars) |

L = word length, k = results, L̃ = average suffix length, d = number of dots.

The memory line is the honest cost: naive tries are space-hungry (26-way fan-out); that's why production uses radix-compressed tries, FSTs, or double-array tries.

## The 3 questions an interviewer asks

1. *"Why a trie over a hash set for autocomplete?"* — hash maps answer exact matches only; prefix queries need structure. A trie answers "all words starting with 'sta'" in O(L + output).
2. *"26-way fan-out wastes memory — what's the fix?"* — radix compression (merge single-child chains), FSTs (Lucene: shares suffixes too, ~10 bytes/term), or double-array representation for cache density.
3. *"How does a router do longest-prefix match at line rate?"* — bit-trie with path compression, implemented in ternary CAM / ASIC pipelines; software routers use DPDK-optimized multi-bit tries. The algorithm is the same tree you built, the constants differ by 10⁶.
