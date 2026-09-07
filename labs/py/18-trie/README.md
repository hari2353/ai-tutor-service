# Lab 18: Trie (Prefix Tree)

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p18-trie`

**You will build:** a Trie from scratch with insert / exact search / prefix search, a wildcard (`.`) dictionary, bounded-k autocomplete, board word-search pruned by the trie itself, and longest-common-prefix via the trie's fan-out.

**You will be able to answer:** *"Typeahead: 500k queries/sec, prefix matching over 10M strings — why a trie and not a hash map, and where do real systems cheat?"*

## Setup

```bash
cd labs/py/18-trie
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Trie`** — `insert(word)` (idempotent — re-inserting is a no-op), `search(word)` exact membership, `starts_with(prefix)` — any inserted word with that prefix. All O(len).
2. **`WordDictionary`** — trie + `search` where `.` matches any single character. `search` on an empty dictionary returns False for any non-empty pattern; `""` search: True iff `""` was inserted.
3. **`autocomplete(trie, prefix, k)`** — up to k words sharing the prefix, **alphabetically first** (deterministic), built without full traversal sort; the trie yields words in alphabetical order during DFS, so collect until k.
4. **`find_words(board, words)`** — Boggle-style grid: return the words (any order, compare as sets) that appear on contiguous paths (4-directional, cells reusable **within** a word but each cell at most once per word). Prune with the trie: abort a path the moment the prefix is dead. No trie → exponential blow-up.
5. **`longest_common_prefix_via_trie(words)`** — walk children while exactly one branch and node is not terminal; stop at first fork or terminal. `""` for empty input; the single word itself if it's the whole list.
6. **Memory honesty** — plain dict-of-dicts nodes; no `__slots__` tricks needed, but nodes must not store parent pointers or per-node word copies (checked by behaviour: 10k words insert must be fast and lookups stay O(len)).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Compressed trie (radix tree)** — merge single-child chains; count the node savings on the English word list you insert.
2. **Top-k by frequency** — autocomplete ordered by popularity then alpha; store counts at terminals and keep a bounded heap per popular prefix (what real typeahead does).
3. **Fuzzy search** — Levenshtein-1 search with a budget on trie nodes; measure the pruning win vs brute force.
4. **Suffix trie → suffix automaton** — build a naive suffix trie and note when it explodes; read about Ukkonen's linear construction.
