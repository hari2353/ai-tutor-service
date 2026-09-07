# Production notes — bitwise XOR

## Where XOR actually ships

- **RAID-5 parity** — the parity disk stores `d1 ^ d2 ^ ... ^ dn`. Lose any one disk and the missing value is the XOR of the survivors. That is literally `single_number` with every block appearing "twice" (data + parity) except the lost one.
- **Hashing & checksums** — XOR is the mixing step in FNV, murmur and xxHash; it's associative and order-independent, which is why it also powers set-hash and Merkle tree diffs. Git's tree hashes XOR-free, but rsync's rolling checksum leans on the same algebra.
- **XOR linked lists (C)** — doubly-linked with one pointer field: `both = prev ^ next`. Used in memory-constrained allocators and LRU caches (the Linux kernel's older list debugging documented the pattern). You pay: can't dereference without *two* node addresses, and no O(1) arbitrary deletion — which is why no mainstream runtime ships them.
- **Bitmap indexes & bloom filters** — parity/count semantics underpin SIMD popcount instructions (`POPCNT`, `VPPOPCNT`); search engines use popcount to score set intersections.
- **Error detection** — parity bits (UARTs, RAID, ECC DIMMs) are exactly your `parity(n)` function in hardware.

## Complexity table

| Operation | XOR trick | Naive | Space |
|---|---|---|---|
| `single_number` | O(n) | O(n²) count-scan / O(n log n) sort | O(1) |
| `single_number_iii` | O(n) two passes | O(n) with a hash map | O(1) vs O(n) |
| `missing_number` | O(n) | O(n) with set | O(1) vs O(n) |
| `count_bits` (Kernighan) | O(k) set bits | O(b) all bits, O(1) per op | O(1) |
| XOR linked list traversal | O(n) | same | O(1) per node — the point |
| XOR linked list random delete | O(n) find | O(1) with real prev ptr | the tradeoff |

## The 3 questions an interviewer asks

1. *"Why does XOR work here but not when elements appear three times?"* — XOR forms a group where every element is its own inverse (order 2); triples need per-bit counts mod 3 (or `ones/twos` state machine).
2. *"Is XOR commutativity ever a bug?"* — yes: order-independent aggregation means you can't detect *sequence* — that's why rolling checksums (rsync, Adler-32) add position-dependent terms on top.
3. *"Would you ship an XOR linked list?"* — only in C, only when memory is the binding constraint; the loss of O(1) deletion and debuggability usually costs more than the saved pointer.
