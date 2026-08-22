# Pattern: Bitwise XOR

> **Track:** T02 DSA: 21 Patterns · **Time:** 1h · **Prereqs:** arrays, binary representation, T02-p11-binary-search
> **Module id:** `T02-p12-bitwise-xor` · **Tags:** pattern, bit-manipulation

## The 30-second version

XOR is the pattern for "find the odd one out" problems under a hard constant-space constraint: `a ^ a = 0`, `a ^ 0 = a`, and XOR is commutative and associative, so every value that appears an even number of times cancels itself out regardless of order, leaving only the value(s) that don't pair up. That single identity solves Single Number, Missing Number, and a dozen variants in O(n) time and O(1) extra space, where the naive hashmap answer costs O(n) space. The tell is a problem statement that says "every element appears twice/three times except one" or "find the missing/duplicate number in range [0, n]" and then adds "can you do it in O(1) space" — that qualifier is the signal that XOR, not a hash set, is the expected answer.

## Why this gets asked

It's a cheap, fast way to check two things at once: can you reach for a non-obvious identity instead of defaulting to a hashmap, and do you actually understand what a hash set costs versus what three lines of XOR cost. Interviewers who have shipped embedded systems, network protocols (XOR is how RAID parity and checksums work), or memory-constrained services have lived through the version of this where "just use a HashSet" isn't acceptable because you're processing a stream that can't fit in memory, or the language doesn't give you a convenient hash set at all. It also quietly tests whether you understand two's-complement and fixed-width integer behavior, which bites people the moment negative numbers or 32-bit overflow enter the picture.

---

## Lineage: past → present → future

**What came before.** XOR-for-parity isn't an interview invention — it's how error-detecting parity bits and RAID-5 recovery have worked since the 1970s (recover a lost disk's data by XORing the survivors), and it's the basis of the classic XOR linked list trick (store `prev XOR next` in one pointer field to halve memory) from an era when every byte of node overhead mattered. The interview version of the pattern is a direct lift of the parity idea onto arrays: hashmap counting was the obvious first tool, and it dies the moment the constraint is O(1) space or a true streaming input where you can't retain all elements.

**Where it stands now.** The pattern is settled and small: know the identities, know the "counting bits per position mod k" generalization for the appears-3-times case, and know the bitwise-trie extension for maximum-XOR-pair problems. There's no live methodological disagreement here — this is closed 60-year-old math, not an evolving research area. The only real debate in interviews is stylistic: whether reaching immediately for bit tricks over-indexes on cleverness when a hashmap is O(n) time and space and perfectly fine unless the interviewer states the space constraint.

**Where it's heading.** Nowhere new for interviews — this bag of tricks hasn't changed since it was formalized in Bentley's *Programming Pearls* (1986) and it won't. The one place it's expanding is applied: XOR-based secure aggregation in federated learning (mask model updates with pairwise XOR/additive shares so a server never sees a raw update) and homomorphic-adjacent techniques use exactly this "even occurrences cancel" idea at a systems level. Treat that as trivia, not something you'll be asked to derive.

---

## Mental model

Think of an integer as 32 (or 64) independent lanes, one per bit. XOR never lets a lane talk to its neighbor — bit 5 of the result depends only on bit 5 of every input.

```
values:     5 = 0 1 0 1
            3 = 0 0 1 1
            5 = 0 1 0 1
            ---------- XOR column by column, independently
XOR:            0 0 1 1   = 3   (the two 5s cancelled, lane by lane)
```

Because each lane is independent and XOR on a lane is just "flip if 1", pairing up two identical values flips a lane twice — back to where it started. That's the entire mechanism. Order doesn't matter (commutative + associative), so you can XOR a million values in any order you receive them, one pass, and whatever didn't pair up survives.

---

## Recognition heuristics

Reach for XOR when the problem statement has any of these fingerprints:

- **"Every element appears twice except one"** (or "every element appears *k* times except one/two") — the canonical Single Number family.
- **"Find the missing number"** in a range `[0, n]` or `[1, n]` combined with **"O(1) extra space"** — sum-based math also works, but XOR avoids overflow entirely.
- **A qualifier "can you do it without extra memory / in linear time and constant space"** attached to a problem that looks like it wants a hash set. That qualifier is the whole signal.
- **"Swap without a temp variable"** or **"toggle a state / flag"** — direct application of `a ^= b; b ^= a; a ^= b;` or flipping a bit as a visited marker.
- **Subarray / range XOR queries** — build a prefix-XOR array (`pre[i] = pre[i-1] ^ a[i-1]`) exactly the way you'd build a prefix-sum array, then `xor(l, r) = pre[r+1] ^ pre[l]`.
- **"Maximum XOR of two elements in an array"** — this is a different sub-pattern (bitwise trie, greedy from the most significant bit), not plain cancellation; recognize it as XOR-adjacent but requiring a trie (see `T02-p18-trie`).
- **Anything phrased around parity** — "does flipping bit i change the outcome", checksum/error-detection framing.

If the problem instead needs the *actual counts* of duplicates (not just parity), XOR alone won't recover that information — you need bit-counting per position (Single Number II) or a hashmap.

---

## How it actually works — derivation of the counting generalization

The base identity set: `a ^ a = 0`, `a ^ 0 = a`, commutative, associative. For "every element appears twice except one," XOR-reduce the whole array; every paired value contributes `x ^ x = 0` regardless of when it's paired, leaving only the unpaired value.

For **"every element appears three times except one"** (Single Number II), plain XOR breaks: `x ^ x ^ x = x`, so the tripled values don't cancel — they survive as themselves, corrupting the result. The fix is to look at *each bit position independently* and count how many numbers have a 1 there: if every number appeared exactly 3 times, that count is a multiple of 3; the lone survivor contributes exactly 1 extra to whichever bits it has set. So for each bit `b`, `(count of numbers with bit b set) mod 3` reconstructs the answer bit by bit. That's the derivation — no magic, just "XOR is a mod-2 counter per bit; generalize to mod-k counting per bit for appears-k-times problems."

For **two elements that each appear once, rest appear twice** (Single Number III), a single XOR-reduce gives you `x ^ y` where `x` and `y` are the two singles — not either value alone. The recovery trick: `x ^ y != 0`, so some bit differs between them; take the lowest set bit of `x ^ y` as a partition key, split the whole array into "bit set" and "bit not set" buckets, and XOR-reduce each bucket separately. Every paired duplicate value has identical bits so it lands in the same bucket as its twin and cancels; `x` and `y` differ on the partition bit by construction, so they land in different buckets and each XOR-reduce recovers one of them cleanly.

---

## Template code (Python, Java, Go)

```python
# Python — Single Number (appears once, rest twice)
def single_number(nums: list[int]) -> int:
    result = 0
    for n in nums:
        result ^= n
    return result

# Single Number II (appears once, rest three times) — bit counting mod 3
def single_number_ii(nums: list[int]) -> int:
    ans = 0
    for bit in range(32):
        cnt = sum((n >> bit) & 1 for n in nums)
        if cnt % 3:
            ans |= (1 << bit)
    # Python ints are arbitrary precision — reinterpret as signed 32-bit
    if ans >= 2 ** 31:
        ans -= 2 ** 32
    return ans

# Single Number III (two elements appear once, rest twice)
def single_number_iii(nums: list[int]) -> list[int]:
    xor_all = 0
    for n in nums:
        xor_all ^= n
    lowest_set_bit = xor_all & (-xor_all)     # isolate rightmost 1 bit
    a = b = 0
    for n in nums:
        if n & lowest_set_bit:
            a ^= n
        else:
            b ^= n
    return [a, b]

# Missing Number in [0, n]
def missing_number(nums: list[int]) -> int:
    result = len(nums)
    for i, n in enumerate(nums):
        result ^= i ^ n
    return result
```

```java
// Java — Single Number
public int singleNumber(int[] nums) {
    int result = 0;
    for (int n : nums) result ^= n;
    return result;
}

// Single Number II — bit counting mod 3 (32-bit signed int, no reinterpret needed)
public int singleNumberII(int[] nums) {
    int ans = 0;
    for (int bit = 0; bit < 32; bit++) {
        int cnt = 0;
        for (int n : nums) cnt += (n >> bit) & 1;
        if (cnt % 3 != 0) ans |= (1 << bit);
    }
    return ans;
}

// Single Number III
public int[] singleNumberIII(int[] nums) {
    int xorAll = 0;
    for (int n : nums) xorAll ^= n;
    int lowestSetBit = xorAll & (-xorAll);
    int a = 0, b = 0;
    for (int n : nums) {
        if ((n & lowestSetBit) != 0) a ^= n; else b ^= n;
    }
    return new int[]{a, b};
}

// Missing Number
public int missingNumber(int[] nums) {
    int result = nums.length;
    for (int i = 0; i < nums.length; i++) result ^= i ^ nums[i];
    return result;
}
```

```go
// Go — Single Number
func singleNumber(nums []int) int {
    result := 0
    for _, n := range nums {
        result ^= n
    }
    return result
}

// Single Number II — bit counting mod 3
func singleNumberII(nums []int) int {
    ans := 0
    for bit := 0; bit < 32; bit++ {
        cnt := 0
        for _, n := range nums {
            cnt += (n >> bit) & 1
        }
        if cnt%3 != 0 {
            ans |= 1 << bit
        }
    }
    return ans
}

// Single Number III
func singleNumberIII(nums []int) [2]int {
    xorAll := 0
    for _, n := range nums {
        xorAll ^= n
    }
    lowestSetBit := xorAll & (-xorAll)
    a, b := 0, 0
    for _, n := range nums {
        if n&lowestSetBit != 0 {
            a ^= n
        } else {
            b ^= n
        }
    }
    return [2]int{a, b}
}

// Missing Number
func missingNumber(nums []int) int {
    result := len(nums)
    for i, n := range nums {
        result ^= i ^ n
    }
    return result
}
```

## Complexity — derived, not asserted

Every variant above is one or two linear passes over `n` elements with O(1) work per element (a handful of bit ops), so **time is O(n)** (Single Number II is O(32n), i.e. still O(n) since 32 is a constant bound on int width). **Space is O(1)**: no auxiliary structure grows with input size — contrast with the hashmap-counting alternative, which is O(n) time *and* O(n) space to hold the frequency table. The whole value proposition of this pattern is trading a small constant-factor slowdown (bit counting instead of hashmap lookup) for dropping the O(n) space term entirely.

---

## The 5 variants interviewers actually ask

1. **Appears once vs. appears twice (Single Number, LC 136).** Template: single XOR-reduce, no modification needed.
2. **Appears once vs. appears three times (Single Number II, LC 137).** Template modification: replace the single XOR-reduce with per-bit counting mod 3, as derived above.
3. **Two elements appear once, rest appear twice (Single Number III, LC 260).** Template modification: XOR-reduce once to get `x^y`, isolate the lowest set bit as a partition key, XOR-reduce each partition separately.
4. **Missing number in `[0, n]` (LC 268) / Missing + duplicate pair.** Template modification: XOR every array value with every index `0..n`; the duplicate pattern (find both the number that's missing *and* the one that's duplicated, LC 645-style) needs the sum-of-squares or the XOR-plus-sum combined trick — XOR alone can't separate two unknowns from one equation, so combine `xor_all` (gives `missing ^ duplicate`) with `sum(1..n) - sum(nums)` (gives `missing - duplicate`) to solve the 2x2 system.
5. **Maximum XOR of two numbers in an array (LC 421).** Not a cancellation problem — build a bitwise trie of all numbers from MSB to LSB, then for each number greedily walk the trie preferring the opposite bit at every level to maximize the XOR. O(32n) time, O(32n) trie nodes. This is the variant most likely to be presented as "just another XOR question" when it's actually a trie problem wearing an XOR costume — say so explicitly if asked.

---

## Common bugs and how this pattern gets written wrong under pressure

- **Using XOR for the "appears three times" case without modification.** `x^x^x = x`, not `0` — the triples don't cancel, so a naive XOR-reduce silently returns garbage. This is the single most common mistake; if the problem says "except one" but the multiplicity isn't 2, stop and re-derive.
- **Forgetting the sign-bit reinterpretation in Python.** Python integers are unbounded, so bit-counting code that assumes a 32-bit width (as in Single Number II) needs an explicit "reinterpret as signed 32-bit" step (`if ans >= 2**31: ans -= 2**32`), or it silently returns a large positive number instead of the correct negative one. Java and Go don't have this problem because their `int` is fixed-width already.
- **Off-by-one in the missing-number XOR.** The trick XORs indices `0..n` against values, but the array itself has `n` elements holding values in `[0, n]`; forgetting to include the extra index (`n`) or starting the loop at the wrong bound is a classic under-pressure slip.
- **Trying to recover two unknowns from one XOR equation.** `xor_all` for the missing+duplicate variant only gives `missing ^ duplicate`; people try to bit-split this the same way as Single Number III and get stuck, because that trick needs both values to appear an odd number of times overall, which isn't true here — you need a second independent equation (sum difference) to solve for both.
- **Treating `lowest_set_bit = x & -x` as needing two's-complement clarification and getting it backwards.** `-x` in two's complement is `~x + 1`; `x & -x` isolates the lowest set bit because all bits below it become 0 in `-x` and the rest are flipped, so `x & (~x+1)` collapses to exactly that one bit. If you can't derive this on request, you don't understand it well enough to trust it under pressure.
- **Reaching for XOR reflexively when a hashmap is simpler and no space constraint was stated.** Over-indexing on cleverness when the interviewer didn't ask for O(1) space is itself a minor red flag — state the hashmap solution first, then offer the XOR optimization as the space-constrained upgrade.

---

## Interview questions

### Q1 — Single Number: every element appears twice except one, find it in O(1) space.
**Testing:** the base identity.
**Answer:** XOR-reduce the whole array; paired values cancel, the singleton survives. O(n) time, O(1) space.
**Follow-up trap:** *"What if it appears three times instead of two?"* — plain XOR breaks (`x^x^x=x`); you need per-bit counting mod 3.

### Q2 — Single Number II: every element appears three times except one.
**Testing:** whether you can generalize past the base identity instead of forcing XOR to work.
**Answer:** For each of the 32 bit positions, count how many numbers have that bit set; a count not divisible by 3 means the singleton has that bit set. Reassemble bit by bit.
**Follow-up trap:** *"Can you avoid the O(32n) inner loop?"* — yes, with a 2-bit state machine (`ones`, `twos` registers) that tracks counts mod 3 per bit in a single pass without the explicit 32-iteration loop; it's the same math compressed into bitwise updates, and deriving it live is a strong signal.

### Q3 — Single Number III: two elements appear once, rest twice.
**Testing:** whether you can recover two unknowns from one XOR result.
**Answer:** XOR-reduce to get `x^y`; isolate the lowest set bit (`v & -v`) as a partition key since `x` and `y` must differ there; XOR-reduce each partition independently to recover each value.
**Follow-up trap:** *"Why the lowest set bit and not any set bit?"* — any set bit works for correctness; lowest is just the cheapest to compute (`v & -v`) and avoids scanning.

### Q4 — Missing Number in `[0, n]`.
**Testing:** baseline application, and whether you know the overflow-free alternative to the sum formula.
**Answer:** XOR every index `0..n` with every array value; every present number cancels with its index, leaving the missing one.
**Follow-up trap:** *"Why not just use `n(n+1)/2 - sum(nums)`?"* — that works too and is arguably simpler, but it can overflow for large `n` in fixed-width languages, where XOR cannot overflow. Know both and state the overflow tradeoff.

### Q5 — Find both the missing number and the duplicate number in `[1, n]`.
**Testing:** whether you notice one XOR equation isn't enough for two unknowns.
**Answer:** `xor_all` (array XOR indices) gives `missing ^ duplicate`. Combine with `sum(1..n) - sum(nums)` = `missing - duplicate` to solve the 2-variable system algebraically, or bit-partition using the lowest set bit of `missing ^ duplicate` and then determine which partition holds which by comparing against the array (the duplicate physically exists in the array; the missing one doesn't).
**Follow-up trap:** *"Can you do it without extra space, in one pass?"* — yes: compute `xor_all` in one pass, then a second pass to bit-partition; still O(1) extra space, two passes, no auxiliary array.

### Q6 — Maximum XOR of two numbers in an array (LC 421).
**Testing:** recognizing this isn't a cancellation problem.
**Answer:** Build a bitwise trie (MSB to LSB, typically 32 levels) of every number; for each number, greedily walk the trie choosing the child representing the opposite bit whenever it exists, to maximize the XOR bit by bit from the top. O(32n) time and trie nodes.
**Follow-up trap:** *"Can you do it without a trie?"* — yes, with a bitmask-prefix hash-set approach: build the answer bit by bit from MSB, at each step tentatively set that bit and check (via a hash set of number-prefixes) whether some pair achieves it; O(32n) time, no trie needed, more fiddly to get right live.

### Q7 — XOR Queries of Subarray (LC 1310): answer many `xor(l, r)` queries.
**Testing:** prefix-XOR construction, the XOR analogue of prefix sums.
**Answer:** Build `pre[0] = 0`, `pre[i+1] = pre[i] ^ a[i]`; each query answers as `pre[r+1] ^ pre[l]` in O(1) after O(n) preprocessing.
**Follow-up trap:** *"Why does XORing two prefixes give the range, the same way subtracting two prefix sums gives a range sum?"* — because `pre[r+1] = a[0]^...^a[r]` and `pre[l] = a[0]^...^a[l-1]`; XORing them cancels the common prefix `a[0]^...^a[l-1]` exactly the way subtraction cancels a common additive prefix, since XOR is its own inverse.

### Q8 — Total Hamming Distance (LC 477): sum of Hamming distances between all pairs in an array.
**Testing:** per-bit independent counting, the same idea underlying Single Number II.
**Answer:** For each bit position, if `c` numbers have that bit set and `n-c` don't, every set/unset pair contributes 1 to Hamming distance at that bit, so the total contribution is `c * (n-c)`. Sum over all 32 bit positions. O(32n) time.
**Follow-up trap:** *"Why is per-pair Hamming distance O(n²) naive but this is O(n)?"* — because Hamming distance decomposes additively across bit positions, and each bit position only needs a single count, not a pairwise comparison; the decomposition is the entire trick.

### Q9 — Decode an XORed array (LC 1720): given `encoded[i] = arr[i] ^ arr[i+1]` and `arr[0]`, recover `arr`.
**Testing:** whether you can invert an XOR relation forward.
**Answer:** `arr[i+1] = encoded[i] ^ arr[i]`, walk forward from the known `arr[0]`. O(n) time, O(1) extra space if writing in place.
**Follow-up trap:** *"What if you're given the XOR of the whole array instead of `arr[0]`?"* — a variant (LC 1734, "Decode XORed Permutation") on a permutation of `1..n`: XOR-reduce all indices' encoded values at odd positions plus the known total XOR of `1..n` to recover `arr[0]`, then decode forward the same way. Recognizing when you have enough independent XOR equations to solve for the unknown is the actual skill being tested across this whole family.

### Q10 — Swap two variables without a temporary variable.
**Testing:** whether you know the mechanical trick and its real-world worthlessness.
**Answer:** `a ^= b; b ^= a; a ^= b;` — works because each step is invertible and no information is lost.
**Follow-up trap:** *"Would you ship this in production code?"* — no. It's a curiosity: it fails silently if `a` and `b` are the same memory location (XORing a variable with itself zeroes it, and the "swap" leaves both as 0), it doesn't work for floats, and it's slower and less readable than a temp variable on any modern CPU where a register spill is free. Saying "cute trick, wrong in production" is the correct senior answer.

### Q11 — Given a stream too large to fit in memory, find the one value that appears an odd number of times.
**Testing:** whether you can apply the pattern beyond arrays, to a true streaming context.
**Answer:** Maintain a single running XOR accumulator, no state beyond one integer; process the stream once. This is the case where O(1) space isn't a nice-to-have optimization, it's the only thing that fits.
**Follow-up trap:** *"What if two values could each appear an odd number of times?"* — same limitation as Q3/Q5: one XOR accumulator can't distinguish two unknowns without a second pass, and a true single-pass streaming context may not allow a second pass at all — flag that as a real constraint, not something the pattern silently solves.

---

## Red flags that fail you

- Applying plain XOR-reduce to an "appears three times" problem without noticing it breaks.
- Not knowing why `x & -x` isolates the lowest set bit (can't explain two's complement on request).
- Reaching for a bitwise trie and calling it "just XOR" without distinguishing cancellation-based problems from greedy-bit-construction problems.
- Suggesting the swap-without-temp trick as production-worthy code.
- Not noticing when a problem needs two independent equations (missing+duplicate) versus one (single missing).
- Ignoring fixed-width integer / sign-bit behavior differences between Python and Java/Go.

---

## Cheat card

```
IDENTITIES     a^a=0 · a^0=a · commutative · associative
BASE PATTERN   XOR-reduce array → cancels every value with even multiplicity
APPEARS 2x     plain XOR-reduce                                (LC 136)
APPEARS 3x     per-bit count mod 3, or 2-register (ones,twos) state machine (LC 137)
TWO SINGLES    xor_all → isolate lowest set bit (v & -v) → partition → XOR each half (LC 260)
MISSING NUM    XOR indices 0..n with values 0..n-1              (LC 268)
MISSING+DUP    xor_all = missing^dup; sum diff = missing-dup; solve 2x2 system
PREFIX XOR     pre[i+1] = pre[i]^a[i]; range xor = pre[r+1]^pre[l]     (LC 1310)
MAX XOR PAIR   bitwise trie MSB→LSB, greedy opposite-bit walk    (LC 421, O(32n))
HAMMING SUM    per bit: c*(n-c) pairs differ; sum over 32 bits  (LC 477)
COMPLEXITY     O(n) or O(32n) time ≡ O(n) · O(1) space vs hashmap's O(n) space
WATCH          Python ints unbounded → must reinterpret signed 32-bit manually
```

## Sources

- [Single Number — LeetCode](https://leetcode.com/problems/single-number/) — accessed 2026-07-26
- [Single Number II — LeetCode](https://leetcode.com/problems/single-number-ii/) — accessed 2026-07-26
- [Single Number III — LeetCode](https://leetcode.com/problems/single-number-iii/) — accessed 2026-07-26
- [Maximum XOR of Two Numbers in an Array — LeetCode](https://leetcode.com/problems/maximum-xor-of-two-numbers-in-an-array/) — accessed 2026-07-26
- [XOR Queries of a Subarray — LeetCode](https://leetcode.com/problems/xor-queries-of-a-subarray/) — accessed 2026-07-26
- [Total Hamming Distance — LeetCode](https://leetcode.com/problems/total-hamming-distance/) — accessed 2026-07-26
- [Decode XORed Array — LeetCode](https://leetcode.com/problems/decode-xored-array/) — accessed 2026-07-26
- [All Types of Patterns for Bits Manipulations — LeetCode Discuss](https://leetcode.com/discuss/interview-question/3695233/all-types-of-patterns-for-bits-manipulations-and-how-to-use-it/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
