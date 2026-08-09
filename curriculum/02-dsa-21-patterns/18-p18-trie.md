# Pattern: Trie (Prefix Tree)

> **Track:** T02 DSA: 21 Patterns · **Time:** 2.0h · **Prereqs:** trees, T02-p08-dfs, hashmaps
> **Module id:** `T02-p18-trie` · **Tags:** pattern, tree, strings
> **Practice:** the Problems tab in the app — this pattern has curated LeetCode problems rather than a lab

## The 30-second version

A trie is a tree where each edge represents one character and each root-to-node path represents a prefix, so any word sharing a prefix with another word shares that prefix's path through the tree — insert, search, and prefix-search all run in **O(L)** where L is the word/prefix length, completely independent of how many words are stored, which is what a hashmap of strings can never give you (a hashmap gives O(L) average lookup for an *exact* string but O(n·L) to find every string starting with a prefix, since it has no notion of "starting with"). The tell is any problem that needs prefix queries — autocomplete, "does any word start with this," spell-check, IP routing tables — layered on top of exact-match lookup. Each node holds a fixed-size array or map of children (26 for lowercase English) plus an `is_end_of_word` flag; that flag is the detail beginners forget, and its absence is what breaks "is 'car' a word" when only "cart" was inserted.

## Why this gets asked

It tests whether you reach for the data structure whose shape actually matches the query pattern (prefix membership) instead of forcing a hashmap or sorted-array workaround that degrades to linear scans. Interviewers who've built autocomplete/typeahead systems, DNS or IP routing tables (longest-prefix match is literally trie traversal), spell-checkers, or IDE symbol lookup have hit the real failure this models: a hashmap-based "does anything start with this" check that's fine at 100 words and falls over at 10 million, because every prefix query degenerates into scanning the whole dictionary. It also tests whether you understand the real memory cost of a trie — each node can be large relative to a single character, and that tradeoff needs to be stated honestly, not hand-waved.

---

## Lineage: past → present → future

**What came before.** Before tries, prefix search meant either a sorted array of strings with binary search to find the prefix's range (O(L log n) per query, but O(n) space overhead-free and cache-friendly) or a flat hashmap that could only do exact lookups, forcing prefix queries to fall back to a full linear scan filtering by `startswith`. The trie itself was introduced by René de la Briandais in 1959 and named (from "retrieval") by Edward Fredkin in 1960, specifically to make prefix-based retrieval structural rather than something you approximate with string comparisons — the pain it killed was exactly the O(n) or O(n log n) prefix-scan cost that plagued sorted-array and hashmap approaches at real dictionary sizes.

**Where it stands now.** Standard trie (array-of-26-children or hashmap-of-children per node) is settled and simple; the live engineering debate is entirely about **memory**, because a naive trie can use far more memory than the strings it stores — every node is a pointer-sized array or map even for a single branching character. Two well-established fixes address this: a **compressed trie / radix tree (Patricia trie)** merges chains of single-child nodes into one edge labeled with a substring instead of one character per edge, cutting node count dramatically for sparse tries; a **DAWG (Directed Acyclic Word Graph)** merges identical *suffixes* across different words (not just shared prefixes), giving the smallest possible structure for a fixed dictionary at the cost of losing the ability to cheaply insert new words afterward. Which one to reach for is a real, stated tradeoff, not a solved consensus — interviewers who work with search/autocomplete at scale often ask you to know all three exist and when each wins.

**Where it's heading.** For interview purposes, nothing changes — this is 65-year-old, closed data-structure design. In production, large-scale autocomplete and search-as-you-type systems (Elasticsearch's completion suggester, most real typeahead backends) layer a trie or FST (finite-state transducer, a generalization that's essentially a DAWG with associated output values) underneath a ranking layer that scores completions by popularity/recency rather than returning raw lexicographic order — the trie handles "which strings match the prefix," a separate ranking model handles "which of those matches to show first." Treat the ranking layer as a different, composed concern, not something the trie itself should try to solve.

---

## Mental model

Each path from the root spells out a prefix; a node marked "end of word" means that exact path is also a complete word, not just a prefix of a longer one.

```
insert: "car", "cart", "care", "cd"

root
 └─ c
     ├─ a
     │   └─ r  [END]        <- "car" is a complete word here
     │       ├─ t  [END]    <- "cart"
     │       └─ e  [END]    <- "care"
     └─ d  [END]            <- "cd"

search("car")   -> walk c->a->r, found, and END flag set      -> True
search("ca")    -> walk c->a, found, but END flag NOT set     -> False (it's a prefix, not a word)
startsWith("ca")-> walk c->a, found (END flag irrelevant)     -> True
```

The entire pattern is: walking a path character by character costs O(L), and once you're at the node for a prefix, everything below it in the tree is every word that starts with that prefix — that subtree *is* the answer to "give me all completions," no scanning required.

---

## Recognition heuristics

- **"Autocomplete," "typeahead," "suggest completions for a prefix."** The direct tell.
- **"Does any word in the dictionary start with this prefix?"** — distinct from "is this exact word in the dictionary," which a hashmap already handles; the *prefix* framing is what demands a trie.
- **Repeated insert/search/startsWith operations on a fixed or growing set of strings**, especially when the interviewer explicitly asks for O(L) per operation regardless of dictionary size.
- **Word search on a grid combined with a dictionary of target words** (Word Search II) — building a trie of the dictionary lets a single DFS over the grid prune branches the moment the current path stops being any dictionary word's prefix, instead of running a separate search per word.
- **IP address / network routing framed as "longest prefix match."** Structurally identical to a string trie with a binary (0/1) alphabet instead of 26 letters.
- **"Replace words with their shortest root"** (Replace Words) — build a trie of the roots, then for each word in the sentence walk the trie until you hit an END flag; that's the shortest matching root.
- **XOR-maximization over a set of numbers** (Maximum XOR of Two Numbers) — a trie over each number's binary digits (MSB to LSB), which is trie-adjacent but for a different reason than string prefixes; see `T02-p12-bitwise-xor`, Q6.

If the problem only ever needs exact-match lookup with no prefix or "starts with" semantics, a plain hashmap is simpler, uses less memory, and is the right answer — building a trie there is over-engineering.

---

## How it actually works

**Node structure.** Each trie node holds:
- a fixed-size array of `26` (or however many symbols the alphabet has) child pointers, or a hashmap of children if the alphabet is large/sparse (e.g., Unicode);
- a boolean `is_end` flag marking whether the path from the root to this node spells a complete inserted word (not just a prefix of one).

**Insert("word").** Start at the root. For each character, check if a child exists for it; if not, create one. Move into that child. After processing the last character, mark the current node's `is_end = True`.

**Search("word") — exact match.** Walk the same way; if any character's child doesn't exist, the word isn't present, return False. If you reach the end of the string, return whether `is_end` is set at that final node — this is the detail that trips people up: reaching the node isn't enough, since that node might only be a valid *prefix*, not itself a complete word.

**StartsWith("prefix").** Identical walk, but ignore the `is_end` flag entirely — reaching the end of the prefix string with all characters found is success, regardless of whether that exact path is also a complete word.

**Deletion (less commonly asked, but a real follow-up).** Walk down to the node representing the word, unset its `is_end` flag, then walk back up removing any node that has no children and is not itself the end of another word — this requires either recursion with a return value signaling "safe to delete me" or an explicit parent-pointer/stack-based walk.

---

## Template code (Python, Java, Go)

```python
# Python — Trie: insert, search, startsWith
class TrieNode:
    __slots__ = ("children", "is_end")
    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.is_end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        node.is_end = True

    def _walk(self, prefix: str) -> TrieNode | None:
        node = self.root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def search(self, word: str) -> bool:
        node = self._walk(word)
        return node is not None and node.is_end

    def starts_with(self, prefix: str) -> bool:
        return self._walk(prefix) is not None


# Word Search II (LC 212) — trie-pruned DFS over a grid
def find_words(board: list[list[str]], words: list[str]) -> list[str]:
    trie = Trie()
    for w in words:
        trie.insert(w)

    rows, cols = len(board), len(board[0])
    found: set[str] = set()

    def dfs(r: int, c: int, node: TrieNode, path: str):
        ch = board[r][c]
        if ch not in node.children:
            return
        nxt = node.children[ch]
        path += ch
        if nxt.is_end:
            found.add(path)
        board[r][c] = "#"
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and board[nr][nc] != "#":
                dfs(nr, nc, nxt, path)
        board[r][c] = ch

    for r in range(rows):
        for c in range(cols):
            dfs(r, c, trie.root, "")
    return list(found)
```

```java
// Java — Trie: insert, search, startsWith
class TrieNode {
    TrieNode[] children = new TrieNode[26];
    boolean isEnd = false;
}

class Trie {
    private final TrieNode root = new TrieNode();

    public void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) node.children[idx] = new TrieNode();
            node = node.children[idx];
        }
        node.isEnd = true;
    }

    private TrieNode walk(String s) {
        TrieNode node = root;
        for (char c : s.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) return null;
            node = node.children[idx];
        }
        return node;
    }

    public boolean search(String word) {
        TrieNode node = walk(word);
        return node != null && node.isEnd;
    }

    public boolean startsWith(String prefix) {
        return walk(prefix) != null;
    }
}
```

```go
// Go — Trie: insert, search, startsWith
type TrieNode struct {
    children [26]*TrieNode
    isEnd    bool
}

type Trie struct {
    root *TrieNode
}

func NewTrie() *Trie {
    return &Trie{root: &TrieNode{}}
}

func (t *Trie) Insert(word string) {
    node := t.root
    for _, c := range word {
        idx := c - 'a'
        if node.children[idx] == nil {
            node.children[idx] = &TrieNode{}
        }
        node = node.children[idx]
    }
    node.isEnd = true
}

func (t *Trie) walk(s string) *TrieNode {
    node := t.root
    for _, c := range s {
        idx := c - 'a'
        if node.children[idx] == nil {
            return nil
        }
        node = node.children[idx]
    }
    return node
}

func (t *Trie) Search(word string) bool {
    node := t.walk(word)
    return node != nil && node.isEnd
}

func (t *Trie) StartsWith(prefix string) bool {
    return t.walk(prefix) != nil
}
```

## Complexity, derived

Every operation — insert, search, startsWith — walks exactly one path from the root, one node per character, doing O(1) work per node (an array index or hashmap lookup), so **all three run in O(L)** where L is the length of the word/prefix, independent of how many other words are stored. **Space is O(total characters across all inserted words)** in the worst case with no shared prefixes, but real dictionaries share prefixes heavily, so actual space is typically far below `sum(len(word))` — the exact savings depend entirely on prefix overlap in the data, which is precisely the property a hashmap can't exploit at all (a hashmap's per-string storage is always proportional to that string's own length, with zero sharing across entries). Contrast directly: a hashmap gives O(L) average exact-match lookup (same as a trie) but O(n·L) to answer "which of n words start with this prefix," since it has no structural way to jump straight to the matching subset.

---

## The 5 variants interviewers actually ask

1. **Implement Trie (LC 208) — the base insert/search/startsWith.** Direct template application; the interview usually wants you to also state the O(L) complexity and the array-vs-hashmap children tradeoff.
2. **Design Add and Search Words Data Structure (LC 211) — search supports a wildcard `.` matching any single character.** Requires DFS/backtracking at the trie-search step: at a `.`, branch into every existing child rather than following one path; this turns O(L) search into O(26^k · L) in the worst case where k is the number of wildcards, which is worth stating explicitly rather than glossing over.
3. **Word Search II (LC 212) — find all dictionary words present in a character grid.** Build a trie of the dictionary first, then run a single DFS over the grid pruned by trie membership at every step, instead of running a separate grid search per dictionary word (which would be O(words · grid) instead of one shared O(grid) pass).
4. **Replace Words (LC 648) — replace each word in a sentence with its shortest dictionary root, if one exists.** Build a trie of the roots; for each sentence word, walk the trie until either the word ends or an `is_end` node is hit first (that's the shortest valid root) — stopping at the *first* `is_end` encountered, not the longest possible match, is the detail that separates correct from incorrect implementations.
5. **Search Suggestions System (LC 1268) — after each keystroke, return the top 3 lexicographically smallest products matching the prefix typed so far.** Trie built from product names (or, more simply for small inputs, sort the array once and binary-search the prefix range per keystroke); tests whether you know when a simpler sorted-array + binary-search approach beats building a full trie for a small, static, one-time-loaded dataset.

---

## Common bugs

- **Forgetting the `is_end` flag entirely, or checking only "the path exists" for `search`.** This makes `search("ca")` incorrectly return True when only `"car"` was ever inserted, because the path to `"ca"` exists as a prefix even though `"ca"` itself was never inserted as a word.
- **Using `search`'s logic for `startsWith` (or vice versa).** `startsWith` must ignore the `is_end` flag entirely — reaching the end of the queried prefix string is success regardless of whether that node also happens to mark a complete word.
- **Sizing the children array wrong for the actual alphabet.** A fixed `[26]` array assumes lowercase English only; mixed-case or Unicode input needs a hashmap of children or a larger fixed table, and using the wrong one either crashes on out-of-range characters or silently drops valid input.
- **Not pruning aggressively enough in Word Search II**, leaving the DFS to explore board cells that can no longer match any dictionary word once the current trie node has no matching child — checking `ch not in node.children` before recursing (rather than after) is what actually gives the expected speedup.
- **Memory blind spot.** Presenting a trie as "efficient" without acknowledging that a naive implementation can use dramatically more memory than a hashmap for datasets with little prefix sharing — the interviewer wants to hear you name this tradeoff, not just recite O(L) time.
- **Wildcard search treated as O(L) instead of acknowledging the exponential branching factor** introduced by each `.` in Design Add and Search Words — silently ignoring this in the stated complexity is a real gap.
- **Naive trie in production using far more memory than the raw dictionary** because every node allocates a full array/map even for long unbranching chains — fix by compressing single-child chains into one edge holding a substring (radix tree / Patricia trie).
- **Two words with identical suffixes wasting duplicate nodes**, since a standard trie only shares prefixes, never suffixes — a DAWG (merging identical suffix subtrees) fixes this for a static dictionary, at the cost of expensive/impossible inserts afterward.
- **Autocomplete returning technically-correct but useless results** (rare words surfacing first) because the trie encodes structural membership only, with no notion of popularity — layer a ranking score (frequency, recency) on top of the trie/FST match set rather than trying to make the trie itself popularity-aware.

---

## Interview questions

### Q1 — Implement a Trie with insert, search, and startsWith (LC 208).
**Testing:** the base data structure and the search-vs-startsWith distinction.
**Answer:** Each node holds children (array or map) plus an `is_end` flag; insert walks/creates nodes character by character and sets `is_end` at the final node; search requires both path existence and `is_end`; startsWith requires only path existence. All three are O(L).
**Follow-up trap:** *"What if the alphabet isn't just lowercase English?"* — swap the fixed 26-array for a hashmap of children; complexity stays O(L) per operation but with a larger constant factor per node.

### Q2 — Why does a trie beat a hashmap for prefix queries when both give O(L) exact-match lookup?
**Testing:** the actual structural reason, not just "tries are for prefixes."
**Answer:** A hashmap has no relationship between a string and its prefixes — finding all words starting with a given prefix requires scanning every entry, O(n·L). A trie's structure makes every word sharing a prefix live in the same subtree, so reaching the prefix's node in O(L) gives you direct access to every matching word without scanning unrelated entries.
**Follow-up trap:** *"So is a trie strictly better than a hashmap?"* — no; for pure exact-match workloads with no prefix queries, a hashmap is simpler and typically more memory-efficient since it doesn't pay the per-character node overhead of an unshared-prefix trie.

### Q3 — Design Add and Search Words (LC 211): search must support `.` as a wildcard matching any character.
**Testing:** combining trie traversal with backtracking when the path isn't deterministic.
**Answer:** At a normal character, follow the single matching child as usual; at a `.`, recursively try every existing child at that node and return true if any branch succeeds. Complexity degrades to O(26^k · L) in the worst case with k wildcards.
**Follow-up trap:** *"What's the worst case, and when does it actually happen?"* — a query that's all wildcards (e.g. `"...."`) against a dense trie forces exploring every path of that length, which is exponential in the number of wildcards; state this rather than claiming the operation is still O(L).

### Q4 — Word Search II (LC 212): find every dictionary word present in a character grid, each word using adjacent cells without reuse.
**Testing:** combining a trie with grid DFS instead of running independent searches per word.
**Answer:** Build one trie from the dictionary, then run a single DFS from every grid cell, following the trie alongside the grid path and pruning the moment the current path isn't any word's prefix; mark found words at `is_end` nodes.
**Follow-up trap:** *"Why is this better than running Word Search I once per dictionary word?"* — per-word search repeats grid traversal work `|words|` times; the shared trie lets one DFS pass prune all non-matching paths for every word simultaneously, turning `O(words · grid)` into roughly `O(grid · L_max)`.

### Q5 — Replace Words (LC 648): replace each word in a sentence with its shortest root from a dictionary, if any root matches.
**Testing:** correct early-stopping logic in a trie walk.
**Answer:** Build a trie from the roots; for each sentence word, walk the trie character by character and stop at the *first* `is_end` node encountered (not the longest path) — that's the shortest valid root; if no `is_end` is hit before the trie path breaks or the word ends, leave the word unchanged.
**Follow-up trap:** *"What if a longer root and a shorter root both match the same word?"* — the shortest one always wins per the problem's definition, which is exactly why you stop at the first `is_end`, not the last.

### Q6 — What's the actual memory cost of a trie versus a hashmap of the same strings, and when does the trie lose?
**Testing:** honest tradeoff awareness, not blind enthusiasm for the pattern.
**Answer:** A trie's memory scales with the number of distinct characters across the *tree's edges*, which is at most `sum(len(word))` but can be far less if words share prefixes heavily; when words share almost no prefixes (e.g., random strings, hashes, UUIDs), a naive trie uses more memory than a flat hashmap because of the per-node overhead (array/map allocation) with no compensating prefix-sharing benefit.
**Follow-up trap:** *"How would you fix that memory blowup while keeping prefix-query support?"* — compress single-child chains into a radix tree (Patricia trie), storing substrings on edges instead of one node per character.

### Q7 — How would you delete a word from a trie without breaking other words that share its prefix?
**Testing:** whether you can reason about shared structure correctly, not just insertion.
**Answer:** Walk to the node representing the word and clear its `is_end` flag; then walk back up the path, deleting each node only if it has zero children remaining and its own `is_end` is false (meaning it's not itself the end of some other word and has nothing else depending on it).
**Follow-up trap:** *"What if the word to delete is itself a prefix of another stored word?"* — you must only clear the `is_end` flag and must NOT delete any nodes along that path, since the longer word still depends on that entire chain existing.

### Q8 — Maximum XOR of Two Numbers in an Array (LC 421): use a trie to solve this without sorting.
**Testing:** recognizing that "trie" generalizes beyond strings to fixed-width binary representations.
**Answer:** Insert every number's binary representation (MSB to LSB, fixed width e.g. 32 bits) into a bitwise trie; for each number, greedily walk the trie preferring the opposite bit at each level to maximize the running XOR. O(32n) time and trie nodes.
**Follow-up trap:** *"Why walk MSB to LSB and not the other way?"* — the most significant differing bit contributes the most to the XOR's magnitude, so greedily maximizing from the top down guarantees a globally maximum result; greedily maximizing from the LSB up gives no such guarantee since higher bits dominate the numeric value.

### Q9 — Search Suggestions System (LC 1268): after each keystroke, return the 3 lexicographically smallest matching products.
**Testing:** knowing when a trie is overkill versus when it earns its complexity.
**Answer:** For a small, static, one-time-loaded product list, sort the array once and binary-search the prefix range after each keystroke — simpler than building and maintaining a full trie and asymptotically comparable for this input size. A trie only pulls ahead when the dictionary is large, dynamic, or queried far more often than it changes.
**Follow-up trap:** *"At what scale would you actually switch to a trie/FST here?"* — once the product catalog is large enough (millions of entries) or updated frequently enough that repeated full sorts/binary searches on a changing array become the bottleneck, or once you need popularity-ranked suggestions rather than pure lexicographic order, which pushes you toward a trie/FST plus a ranking layer.

### Q10 — Design an autocomplete system that also ranks suggestions by historical query frequency, not just lexicographic order.
**Testing:** production system design layered on top of the raw trie pattern.
**Answer:** Store aggregate frequency counts at (or reachable from) each trie node representing a complete query; on a prefix query, either maintain a small top-k cache per node (updated incrementally) or do a bounded DFS from the prefix node collecting and ranking by frequency, trading some insert/update cost for fast top-k reads.
**Follow-up trap:** *"What breaks if you naively DFS the entire subtree under a popular short prefix on every keystroke?"* — for short, extremely common prefixes (e.g., a single letter), the subtree can contain a huge fraction of the whole dictionary, making per-keystroke DFS effectively O(n); real systems precompute/cache top-k suggestions per node instead of recomputing on every query.

### Q11 — Would you use a trie for IP routing table longest-prefix-match lookups, and how does it map?
**Testing:** transferring the pattern to a domain outside natural-language strings.
**Answer:** Yes — treat each IP address as a fixed-length binary string (32 bits for IPv4) and build a binary trie over it; longest-prefix match is exactly "walk as far down the trie as the routing table has an entry for, and take the deepest node marked as a valid route," structurally identical to trie prefix search.
**Follow-up trap:** *"Real routers don't use plain binary tries for this — why not?"* — a plain 32-level binary trie wastes enormous memory on address ranges with sparse routing entries; real hardware routers use compressed variants (e.g., multi-bit tries, level-compressed tries, or specialized hardware TCAMs) to get the lookup down to a handful of memory accesses, the same radix-tree-style compression argument as the memory-blowup fix for string tries.

---

## Red flags that fail you

- Implementing `search` without checking the `is_end` flag, or implementing `startsWith` while incorrectly requiring it.
- Claiming a trie is unconditionally more memory-efficient than a hashmap without acknowledging the low-prefix-sharing counterexample.
- Not pruning the DFS in Word Search II using trie-child checks, degrading it back to per-word independent search.
- Missing that Design Add and Search Words' wildcard support changes the complexity from O(L) to exponential in the number of wildcards.
- Treating "trie" as string-only and failing to recognize the bitwise-trie generalization for XOR-maximization or IP routing problems.
- Suggesting full-subtree DFS per keystroke for a production autocomplete system without acknowledging the cost on popular short prefixes.

---

## Cheat card

```
NODE           children (array[26] or map) + is_end boolean
INSERT         walk/create per character, set is_end at final node           O(L)
SEARCH         walk per character; must ALSO check is_end at final node       O(L)
STARTSWITH     walk per character; is_end irrelevant                          O(L)
SPACE          O(total chars, minus shared-prefix savings) — can be WORSE than hashmap if no sharing
VS HASHMAP     same O(L) exact match; hashmap needs O(n*L) for prefix queries, trie needs O(L)
WILDCARD SRCH  LC211: branch into every child at '.'; O(26^k * L), k = wildcard count
WORD SEARCH 2  LC212: build dict trie FIRST, one DFS over grid, prune on trie-child-miss
REPLACE WORDS  LC648: walk root-trie, stop at FIRST is_end (shortest root wins)
MAX XOR PAIR   LC421: bitwise trie MSB->LSB, greedy opposite-bit walk, O(32n)
MEMORY FIX     sparse/no-shared-prefix data -> radix tree (Patricia trie), merge single-child chains
STATIC DICT    DAWG merges shared SUFFIXES too -> smallest structure, but hard to update after build
PRODUCTION     trie/FST gives candidate SET; separate ranking layer (frequency/recency) orders results
```

## Sources

- [Implement Trie (Prefix Tree) — LeetCode](https://leetcode.com/problems/implement-trie-prefix-tree/) — accessed 2026-07-26
- [Design Add and Search Words Data Structure — LeetCode](https://leetcode.com/problems/design-add-and-search-words-data-structure/) — accessed 2026-07-26
- [Word Search II — LeetCode](https://leetcode.com/problems/word-search-ii/) — accessed 2026-07-26
- [Replace Words — LeetCode](https://leetcode.com/problems/replace-words/) — accessed 2026-07-26
- [Search Suggestions System — LeetCode](https://leetcode.com/problems/search-suggestions-system/) — accessed 2026-07-26
- [Maximum XOR of Two Numbers in an Array — LeetCode](https://leetcode.com/problems/maximum-xor-of-two-numbers-in-an-array/) — accessed 2026-07-26
- [Trie — Wikipedia](https://en.wikipedia.org/wiki/Trie) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
