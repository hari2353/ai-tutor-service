# Lab 12: Bitwise XOR Patterns

**Track:** T02 DSA: 21 Patterns · **Time:** 2h · **XP:** 50
**Module:** `T02-p12-bitwise-xor`

**You will build:** the XOR family of interview problems — single number, two uniques, missing number, an XOR linked list simulated as pure functions over a dict-of-nodes, and bit count/parity — all from scratch, no `bin()` shortcuts.

**You will be able to answer:** *"Why does XOR find the unpaired element in O(n) time and O(1) space — and where does that trick actually ship in production?"*

## Setup

```bash
cd labs/py/12-bitwise-xor
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`single_number(nums)`** — every element appears exactly twice except one; return the unpaired one. O(n) time, O(1) extra space. Empty input returns 0 (XOR identity).
2. **`single_number_iii(nums)`** — exactly **two** elements appear once, everything else twice. Return them as a sorted tuple, still O(n) / O(1): XOR everything, split on the lowest differing bit.
3. **`missing_number(nums)`** — `nums` is a permutation of `0..n` with one value missing; return the missing one by XOR-ing `0..n` against the array. Empty input → 0.
4. **XOR linked list, simulated** — `build_xor_list(values) -> (head, memory)` where `memory` maps `node_id -> (value, both)` and `both = prev_id ^ next_id` (id 0 is NULL; ids start at 1). Then `xor_list_to_list(head, memory)` traverses with `next = prev ^ both`, and `xor_get_nth(head, memory, i)` returns the i-th value (0-indexed). No `next` pointers exist anywhere — the both-field and a running `prev` are the only navigation.
5. **`count_bits(n)`** — popcount via Kernighan's trick (`n &= n-1`), no `bin()`/`str` conversion. **`parity(n)`** — 1 if the popcount is odd else 0.
6. **Determinism** — everything is pure; identical input gives identical output. No sorting inside `single_number`, no sets, no `Counter`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **`single_number_ii`** — every element appears three times except one; find it with bit counts per position, O(32n) and O(1) space. *(Interview: "why does the XOR trick break here?")*
2. **Range XOR** — `xor_range(lo, hi)` in O(1) using the `f(n) = n ^ (n>>1 ...)` prefix pattern; then answer 10⁶ range queries instantly.
3. **XOR linked list with delete** — add `xor_remove(head, memory, i)` that rebuilds the both-fields of the two neighbours. *(This is why real C code stores the head AND the iterator's previous node.)*
4. **Swap without a temp** — implement `xor_swap` and articulate why compilers reject it in real code (it's slower and breaks when aliased).
