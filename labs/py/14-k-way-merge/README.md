# Lab 14: K-Way Merge

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p14-k-way-merge`

**You will build:** the merge pattern behind every big-data pipeline — merging k sorted linked lists with your own binary heap, merging sorted arrays, the smallest-range-covering-k-lists sliding window, and an external-sort merge step that sorts a list too big to hold by sorting chunks and k-way-merging them.

**You will be able to answer:** *"External sort: 100GB of records, 1GB of RAM — walk me through exactly what happens, and why is the merge phase O(N log k) and not O(Nk)?"*

## Setup

```bash
cd labs/py/14-k-way-merge
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **Linked list representation** — lists come in as Python lists turned into chains: `build_list(values) -> head` where nodes are `(value, next)` tuples or a `ListNode` you define; `list_to_values(head)` converts back. Empty list → head is `None`.
2. **`merge_k_sorted_lists(lists)`** — k linked list heads → one merged chain, ascending, stable (ties: earlier list wins). Use a **binary heap of size k** keyed on (value, list-index) — implement sift-up/sift-down yourself, no `heapq`.
3. **`k_sorted_arrays_merge(arrays)`** — same merge over k sorted Python lists, returning one merged Python list. Same heap discipline, O(N log k).
4. **`smallest_range_covering_k_lists(lists)`** — the [min, max] range (inclusive, as a tuple) that includes at least one number from each of k sorted lists; ties → the one with the smaller start. Sliding window over k pointers; O(n log k).
5. **`external_sort(records, chunk_capacity)`** — simulate external sort: split records into chunks of ≤ chunk_capacity, **sort each chunk independently**, then k-way merge the chunks back into one ascending list. The original list must not be mutated. Chunk size must be honoured exactly (capacity 0 → `ValueError`).
6. **Complexity contract** — all merges O(N log k) in N total elements, k lists. Pairwise/binary-style merging is allowed but the heap path is the one tested for memory behaviour.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. ** loser's tree / tournament tree** — replace the heap with a tournament tree and articulate why it halves the comparisons.
2. ** Streaming merge** — implement `merge_sorted_streams(streams)` where each stream is an iterator that may only be read once; no materialization allowed.
3. ** Stable-multikey** — merge records that sort by (priority, timestamp) with stability; prove stability with a counter suffix.
4. ** Collation-aware** — merge lists of strings with locale-style collation (`é` sorting with `e`) using a fold-key; note where Unicode codepoint order breaks user expectation.
