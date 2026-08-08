# Caches, Lines, Associativity, False Sharing, TLB, NUMA, MESI

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.5h · **Prereqs:** T16-cpu-microarch · **Updated:** 2026-08-03
> **Module id:** `T16-memory-hierarchy` · **Tags:** hardware, critical
> **Lab:** `labs/c/02-false-sharing/`

## The 30-second version

The memory hierarchy exists because DRAM is roughly 100x slower than a register access and getting relatively slower every year (the "memory wall"), so hardware hides that latency with a chain of progressively larger, slower caches: L1 (~4-5 cycles, ~1ns, 32-48KB per core), L2 (~12-14 cycles, ~3-4ns, 256KB-2MB per core), L3 (~40-75 cycles, ~10-20ns, tens of MB shared), and DRAM (~200-300 cycles, ~70-100ns). Caches move data in fixed-size lines (almost universally 64 bytes on x86-64 and ARM64), and associativity (how many places a given address can live in a cache set) trades hardware complexity for fewer conflict misses. False sharing is the single most common "invisible" multi-core performance bug: two threads writing to *different* variables that happen to sit in the *same* 64-byte cache line force the coherence protocol to bounce that line between cores on every write, turning what looks like embarrassingly parallel code into something slower than single-threaded — and it's directly measurable and fixable by padding structures to cache-line boundaries. The TLB caches virtual-to-physical address translations (a TLB miss costs ~100+ cycles to walk the page table, comparable to or worse than an L2 miss), and NUMA means "local" memory (attached to the socket your thread is running on) is meaningfully faster (roughly 1.3-2x lower latency, higher bandwidth) than "remote" memory on another socket — both are silent tail-latency killers that don't show up in single-threaded benchmarks. MESI (Modified/Exclusive/Shared/Invalid) is the cache coherence protocol that keeps all of this consistent across cores by tracking, per cache line, whether it's uniquely owned, shared read-only, or stale, and every cross-core write that touches a shared line pays a coherence-traffic cost that is the real mechanism behind false sharing.

## Why this gets asked

Because memory hierarchy effects are the single biggest source of "the algorithm is O(n) but it's still slow" bugs, and false sharing specifically has burned enough production multi-threaded systems that any interviewer who's shipped concurrent code has a war story: a lock-free counter array, a per-thread stats struct, a hot ring buffer, all silently serialized by cache-line contention nobody wrote in application code. The interviewer wants to know you reach for `perf c2c` or a cache-line diagram before blaming the algorithm, and that you understand NUMA and TLB effects are real, measurable, and not exotic — they show up any time you pin threads, size a JVM heap, or provision a multi-socket instance.

---

## Lineage: past → present → future

**What came before.** Early computers had a flat memory model — the CPU accessed main memory directly, and that was fine because CPU cycle times and memory access times were close enough (both measured in similar orders of magnitude through the 1970s) that no intermediate cache was needed. The pain that killed this was divergent scaling: CPU clock speeds and later instruction-level parallelism improved far faster than DRAM latency did (DRAM latency has improved only modestly over decades while capacity and CPU speed grew orders of magnitude), a trend formalized as the "memory wall" (Wulf & McKee, 1995) — by the 1990s a cache miss to main memory could cost hundreds of CPU cycles, meaning a CPU with no cache would spend the overwhelming majority of its time simply waiting.

**Where it stands now.** Multi-level cache hierarchies (L1/L2/L3, sometimes L4 as eDRAM or off-chip) are universal on general-purpose CPUs, cache-coherence protocols (MESI and its variants MESIF/MOESI) keep multi-core caches consistent transparently to software, and NUMA is the default topology for anything beyond a single socket — software either respects it (NUMA-aware allocators, thread pinning) or pays a real, measured penalty. The live disagreement isn't whether caching matters, it's how much of this complexity should be exposed to software: languages and runtimes increasingly try to hide false sharing and NUMA effects from application developers (Java's `@Contended` annotation, Go's padding conventions, jemalloc/tcmalloc's NUMA-aware arenas), while performance-critical C/C++/Rust code still requires explicit reasoning about cache-line layout, and there's genuine debate about how much of that burden a "modern" language should absorb versus expose.

**Where it's heading.** The gap between compute throughput and memory bandwidth keeps widening (compute has scaled with transistor density far faster than DRAM bandwidth or, especially, DRAM latency), which is the direct cause of the industry's push toward HBM (High Bandwidth Memory, stacked directly on-package, used in GPUs and some server CPUs) and CXL (Compute Express Link, a standard for pooling and disaggregating memory across a rack while keeping cache-coherence-like semantics) — CXL memory pooling is real and shipping in some hyperscaler deployments today, though it's not yet the default for typical workloads. More speculative: whether CXL-attached memory becomes common enough in mainstream cloud instances that "NUMA-style" latency tiers become a 3+ level concern (local DRAM, CXL-attached DRAM, remote-socket DRAM) rather than today's 2-level local/remote split is a direction of travel, not yet a settled consensus on timeline.

---

## Mental model

Picture the hierarchy as concentric circles of a desk: registers are papers in your hand (instant), L1 is the drawer you can reach without standing up, L2 is a filing cabinet across the room, L3 is a shared archive room down the hall that your whole team uses, and DRAM is off-site storage requiring a courier trip:

```
Register        ~0.3 ns    (part of the CPU itself)
L1 cache        ~1 ns      32-48 KB, per-core, ~4-5 cycle latency
L2 cache        ~3-4 ns    256KB-2MB, per-core (or per-cluster), ~12-14 cycles
L3 cache        ~10-20 ns  several-100 MB, SHARED across cores on the die
DRAM            ~70-100 ns  GBs, off-chip, ~200-300 cycles
NUMA remote DRAM  ~100-180 ns  same as above but across a socket interconnect
SSD (NVMe)      ~10-100 us  another 100-1000x beyond DRAM
```

Each step is roughly an order of magnitude slower, which is why hit rate at the *outermost* level you can stay within dominates performance far more than raw clock speed for anything touching more data than fits in L1/L2.

---

## How it actually works

### Cache lines, sets, and associativity

Caches don't move individual bytes; they move fixed-size **cache lines**, almost universally **64 bytes** on both x86-64 and ARM64. Touching one byte of an array pulls its entire 64-byte line into every cache level, which is why sequential access patterns (an array scan) are dramatically faster than random access at the same total byte count — sequential access amortizes each line fetch across 64 bytes of useful work, random access wastes most of each fetched line.

A cache is organized into **sets**, and **associativity** (N-way set-associative) is how many distinct lines can simultaneously occupy one set. A direct-mapped cache (1-way) is simplest but suffers **conflict misses** — two frequently-used addresses that happen to map to the same set will repeatedly evict each other even if the rest of the cache is empty. Real caches trade this off: L1 is commonly 8-way set-associative (e.g. many recent Intel/AMD designs), L2 similarly 8-16 way, and L3 often 12-16+ way given its larger size and shared nature — more ways reduce conflict misses at the cost of more comparators and power to check every way in a set on each access.

### Latency numbers worth having cold

These are representative modern x86-64 server-class figures, not architecture-specific to any one vendor, and are the numbers that should come out instantly in an interview:

| Level | Typical latency | Typical size (per core unless noted) |
|---|---|---|
| L1 | ~4-5 cycles (~1 ns) | 32-48 KB |
| L2 | ~12-14 cycles (~3-4 ns) | 256 KB - 2 MB |
| L3 | ~40-75 cycles (~10-20 ns) | tens of MB, shared per socket |
| Local DRAM | ~200-300 cycles (~70-100 ns) | GBs |
| Remote NUMA DRAM | +50-100% over local | GBs |

The ratio that matters most in interviews: an L1 hit versus a DRAM access is roughly **100x** in raw cycles — which is the entire justification for every cache-conscious data structure and access pattern technique that exists.

### False sharing — the measurable demo

False sharing occurs when two independent variables, owned by different threads, happen to be placed in the **same 64-byte cache line** by the compiler/allocator's default layout. Even though the threads never touch each other's variable, every write by thread A invalidates the *entire line* in thread B's cache (per MESI, detailed below), forcing B to refetch it from a shared cache level or another core's cache before its own next write — turning independent, parallel-looking work into serialized cache-coherence traffic.

```c
// untested sketch — classic false-sharing demo, two threads incrementing "independent" counters
struct Counters {
    long a;   // written only by thread 1
    long b;   // written only by thread 2 -- but shares a's cache line!
};

// vs. the fix:
struct CountersPadded {
    alignas(64) long a;   // pads a onto its own 64-byte cache line
    alignas(64) long b;   // b gets its own line too
};
```

Running the naive `Counters` version with two threads hammering `a` and `b` independently for, say, 100M increments each typically runs **several times slower** (commonly cited 2-10x depending on core count and topology) than the padded version, purely from coherence traffic — no shared data is ever actually contended, only the cache line. This is directly observable with `perf c2c record`/`perf c2c report` on Linux, which specifically flags "HITM" (hit-modified) events — cache lines that were found modified in another core's cache — as the smoking gun for false sharing. Java exposes `sun.misc.Contended`/`jdk.internal.vm.annotation.Contended` for exactly this padding purpose; Go convention is manual struct padding; C++ has `alignas(std::hardware_destructive_interference_size)` (C++17) for portable line-size-aware padding.

### TLB — the hierarchy's hidden extra level

Every memory access goes through address translation: virtual address → physical address via page tables. The **TLB (Translation Lookaside Buffer)** caches recent translations so this doesn't require a multi-level page-table walk on every access. A TLB hit is essentially free (folded into the cache access); a **TLB miss** requires walking the page table (typically 4 levels on x86-64 for 4KB pages), costing on the order of **100+ cycles** — comparable to or worse than an L2 miss, and it happens *in addition to* whatever the actual memory access costs. Standard page size is 4KB, meaning a single TLB entry (with a typical L1 DTLB of 64 entries, L2 STLB of 1024-2048 entries on modern x86 cores) covers only 4KB of address space — a process touching gigabytes of memory with a working set that doesn't fit the TLB's reach pays constant TLB-miss overhead. **Huge pages** (2MB or 1GB on x86-64, configured via `transparent_hugepage` or explicit `hugetlbfs` on Linux) directly attack this: a single 2MB huge page covers what would otherwise be 512 separate 4KB TLB entries, so a large, mostly-sequential working set (common in databases, JVMs with large heaps, ML training) can see a measurable throughput improvement (commonly cited single-digit to low double-digit percent, workload-dependent) purely from reduced TLB miss rate.

### NUMA — memory has a zip code

On multi-socket servers, DRAM is physically attached per-socket, and a core accessing memory attached to *its own* socket ("local") is faster than accessing memory attached to a *different* socket ("remote"), because the remote access must traverse the inter-socket interconnect (Intel UPI, AMD Infinity Fabric). Typical remote-vs-local latency penalties are commonly in the **1.3-2x range**, with bandwidth similarly reduced for remote access, and this is entirely invisible to code that doesn't check `numactl --hardware`/`lscpu` topology or pin threads and allocations deliberately. The classic production symptom: a service runs fine in single-socket benchmarks but shows inconsistent, bimodal latency in a dual-socket production deployment because the OS scheduler migrated a thread to the other socket from its allocated memory, or because a large heap/buffer was allocated before threads were pinned and ended up entirely on one socket while threads run split across both. `numactl --cpunodebind=0 --membind=0` (or the equivalent language-runtime NUMA-aware pinning) forces both CPU and memory locality; leaving it to OS defaults is a common, avoidable source of tail-latency variance.

### MESI — how coherence actually works

MESI names four states a cache line can be in, per core, per line:
- **Modified (M):** this core has the only copy, and it's dirty (differs from memory) — any other core wanting it must get it from this core, not memory.
- **Exclusive (E):** this core has the only copy, and it's clean (matches memory) — can be silently upgraded to Modified on a local write with no bus traffic, since no other core has it.
- **Shared (S):** multiple cores may have this line, all clean and identical — any core wanting to *write* must first invalidate all other copies (a bus/interconnect broadcast).
- **Invalid (I):** this core's copy (if any) is stale and unusable, must be refetched.

The transitions are what create false sharing's cost: a line in Shared state that one core writes to must broadcast an invalidation to every other core holding it (S→M for the writer, S→I for everyone else), and if another core then reads or writes that same line, it must fetch the now-Modified copy from the writer's cache (a cache-to-cache transfer, not a memory access, but still far slower than a private L1 hit) — this exact I→S/M cross-core traffic is what `perf c2c`'s HITM counter is measuring, and it's identical machinery whether the contention is "real" (two threads genuinely sharing a variable) or "false" (two threads sharing only a cache line, not any actual data).

---

## Build it from scratch

The most convincing from-scratch artifact for this module is a runnable false-sharing benchmark, since the point is to *measure* the effect, not just describe it:

```c
// untested sketch — compile with: gcc -O2 -pthread false_sharing.c -o fs
#include <pthread.h>
#include <stdio.h>
#include <stdint.h>
#include <time.h>

#define ITERS 100000000

struct Unpadded { volatile long a; volatile long b; };
struct Padded   { volatile long a; char pad[56]; volatile long b; };  // a and b now 64B apart

void *bump_a(void *arg) { volatile long *p = arg; for (long i = 0; i < ITERS; i++) (*p)++; return NULL; }
void *bump_b(void *arg) { volatile long *p = arg; for (long i = 0; i < ITERS; i++) (*p)++; return NULL; }

double run_unpadded(void) {
    struct Unpadded s = {0, 0};
    pthread_t t1, t2;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pthread_create(&t1, NULL, bump_a, (void *)&s.a);
    pthread_create(&t2, NULL, bump_b, (void *)&s.b);
    pthread_join(t1, NULL); pthread_join(t2, NULL);
    clock_gettime(CLOCK_MONOTONIC, &end);
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

double run_padded(void) {
    struct Padded s = {0, {0}, 0};
    pthread_t t1, t2;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    pthread_create(&t1, NULL, bump_a, (void *)&s.a);
    pthread_create(&t2, NULL, bump_b, (void *)&s.b);
    pthread_join(t1, NULL); pthread_join(t2, NULL);
    clock_gettime(CLOCK_MONOTONIC, &end);
    return (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
}

int main(void) {
    printf("unpadded (false sharing): %.3fs\n", run_unpadded());
    printf("padded   (no contention): %.3fs\n", run_padded());
    return 0;
}
```

Full instructions and a `perf c2c` capture walkthrough live in `labs/c/02-false-sharing/`. The expected result — unpadded meaningfully slower than padded despite doing identical arithmetic — is the whole point: this is a bug class invisible in code review and only visible under measurement.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Multi-threaded code scales sub-linearly or even *worsens* with more threads despite no logical shared state | False sharing — independent per-thread counters/state packed into the same cache line by default struct layout | Pad hot per-thread fields to 64-byte boundaries (`alignas(64)`, `@Contended`, manual padding); confirm with `perf c2c report` (look for high HITM counts) |
| Same service shows bimodal p99 latency across a dual-socket host but not on single-socket test hardware | NUMA — threads and the memory they access ended up on different sockets, either from OS scheduler migration or allocation-before-pinning | Pin threads and memory with `numactl`/`taskset` and NUMA-aware allocators; verify with `numastat` showing cross-node access counts |
| Large-heap JVM/DB workload shows unexplained CPU time in kernel page-fault handling under `perf top` | High TLB miss rate from a large working set spread across many 4KB pages | Enable transparent huge pages or explicit `hugetlbfs` for the large allocation; measure via `perf stat -e dTLB-load-misses` before/after |
| A "read-mostly" shared cache/config object causes unexpected write-side stalls under concurrent readers | Even read-only access requires the line in Shared state; any writer (including infrequent config reloads) triggers invalidation broadcast to all readers, momentarily stalling their next access | For genuinely hot read paths, consider RCU-style or copy-on-write patterns that avoid in-place mutation of a widely-shared line, or reduce write frequency |
| Sequential array scan is fast; the "same" data accessed via a linked list or hash-scattered structure is 5-10x slower | Cache-line utilization — sequential access amortizes each 64-byte line fetch across many useful bytes; pointer-chasing wastes most of each fetched line and adds latency-bound (non-prefetchable) misses | Prefer arrays/flat structures for hot paths (data-oriented design); if a linked structure is required, consider intrusive/pooled allocation to improve locality |

---

## Tradeoffs & when NOT to use it

- **Don't pad every struct defensively.** Padding trades memory footprint (and worse cache *capacity* utilization elsewhere) for reduced false-sharing risk — apply it deliberately to genuinely hot, genuinely multi-threaded-contended fields identified by measurement (`perf c2c`), not as a blanket style rule; over-padding a large struct array can itself hurt performance by blowing past cache capacity.
- **Don't NUMA-pin everything by default.** Rigid CPU/memory pinning helps steady-state latency-sensitive workloads but can hurt load-balancing and utilization for bursty, unpredictable workloads where the OS scheduler's flexibility to move work across sockets is actually beneficial — measure before pinning broadly.
- **Don't reach for huge pages unconditionally.** Transparent huge pages have a real, documented failure mode: khugepaged's background compaction/promotion can itself cause latency spikes and unpredictable memory fragmentation behavior on some workloads (this has been a known operational gotcha for Redis and some JVM deployments) — explicit `hugetlbfs` for a known, large, stable allocation is often safer than blanket transparent huge pages for latency-sensitive services.
- **Don't over-index on cache-line-level micro-tuning for code that isn't hot.** This is the same principle as CPU-microarchitecture tuning: profile first (`perf stat`, `perf c2c`) and confirm the bottleneck is genuinely coherence traffic or TLB pressure before restructuring data layout — premature cache-line engineering makes code harder to read for no measured benefit.
- **This entire hierarchy is the wrong mental model for workloads dominated by network or disk I/O latency** (microseconds to milliseconds) — squeezing cache-line contention out of a service whose p99 is dominated by a downstream HTTP call is solving the wrong layer; profile end-to-end before assuming memory hierarchy is the bottleneck.

---

## Interview questions

### Q1 — Walk through the full memory hierarchy with real latency numbers.
**Testing:** whether the numbers are memorized or approximated wildly.
**Answer:** Register (~0.3ns, part of the core) → L1 (~4-5 cycles, ~1ns, 32-48KB) → L2 (~12-14 cycles, ~3-4ns, 256KB-2MB) → L3 (~40-75 cycles, ~10-20ns, tens of MB shared) → local DRAM (~200-300 cycles, ~70-100ns) → remote NUMA DRAM (50-100% higher than local) → SSD (tens to hundreds of microseconds). Each step is roughly an order of magnitude slower than the one before.
**Follow-up trap:** *"Which single ratio matters most to remember?"* — L1 hit vs DRAM access is roughly 100x in cycles; that ratio alone justifies essentially every cache-conscious data structure technique.

### Q2 — What is false sharing, and how would you detect it in a running production service?
**Testing:** knowing both the mechanism and the actual diagnostic tool, not just the concept.
**Answer:** Two threads write to logically independent variables that happen to share a 64-byte cache line, so each write invalidates the whole line in the other thread's cache, forcing repeated cross-core cache-to-cache transfers even though no real data is contended. Detect with `perf c2c record`/`perf c2c report` on Linux, specifically looking for high HITM (hit-modified) counts on the suspect addresses — that's the direct signature of cache-to-cache coherence traffic from false (or true) sharing.
**Follow-up trap:** *"How do you tell false sharing apart from genuine contention on the same variable in that report?"* — `perf c2c` shows the actual addresses/offsets involved; if the two threads' hot addresses fall within the same 64-byte-aligned line but are logically different fields (different offsets, different purposes in your struct), it's false sharing — the fix is padding, not a lock or atomic, because there's no real race to resolve.

### Q3 — Explain associativity and why an interviewer might ask about "conflict misses" specifically.
**Answer:** Associativity is how many distinct cache lines can occupy one set simultaneously. A direct-mapped (1-way) cache forces any two addresses that hash to the same set to repeatedly evict each other (a conflict miss) even if most of the cache is empty elsewhere — a classic pathological case is striding through a large array with a stride that's a power-of-two multiple of the cache size, causing every access to land in the same set. N-way set-associative caches (commonly 8-16 way on modern L1/L2/L3) reduce this by giving each set multiple slots.
**Follow-up trap:** *"Give a concrete code pattern that triggers pathological conflict misses."* — iterating a 2D array's columns instead of rows when the row stride happens to be a multiple of the cache's set-mapping period (common with power-of-two-sized matrices) can turn what should be a cache-friendly scan into a near-100%-miss pattern; the general fix is padding array dimensions to break the power-of-two alignment, or simply iterating in row-major order to match memory layout.

### Q4 — What's a TLB miss, and why can it cost more than an L2 cache miss?
**Answer:** The TLB caches virtual-to-physical address translations; a miss requires walking the (typically 4-level on x86-64) page table, an operation that itself involves multiple memory accesses, commonly costing 100+ cycles total — comparable to or exceeding an L2 miss cost, and it's paid *in addition to* whatever the actual data access then costs, since a TLB miss must resolve before the data access can even begin.
**Follow-up trap:** *"How do huge pages help, and is there a downside?"* — a 2MB huge page covers what would be 512 separate 4KB TLB entries, dramatically reducing TLB miss rate for large, mostly-sequential working sets (databases, large JVM heaps, ML training buffers). Downside: Linux's transparent huge pages use background compaction (khugepaged) that has caused documented latency spikes in latency-sensitive services (notably Redis); explicit `hugetlbfs` for a known large allocation avoids that background-compaction risk.

### Q5 — Explain the four MESI states and what happens, state-by-state, when one core writes to a line currently Shared across three cores.
**Answer:** Modified (sole dirty owner), Exclusive (sole clean owner, can silently upgrade to Modified), Shared (multiple clean readers), Invalid (stale, must refetch). When one of three cores holding a Shared line writes to it, it must broadcast an invalidation over the coherence interconnect; the other two cores' copies transition Shared→Invalid, and the writer's transitions Shared→Modified. If either of the other cores then accesses that address again, it's a miss requiring a cache-to-cache transfer (or memory fetch) to get the current Modified copy.
**Follow-up trap:** *"Is this exact mechanism what makes false sharing expensive, or is false sharing something different?"* — it's the identical mechanism; false sharing's cost *is* MESI invalidation/transfer traffic, triggered by cache-line proximity rather than genuine logical data sharing. There's no separate "false sharing protocol" — it's ordinary coherence traffic paying for accidental line co-location.

### Q6 — Your dual-socket production host shows bimodal p99 latency that doesn't reproduce on single-socket test hardware. What's your hypothesis and how do you confirm it?
**Answer:** NUMA — threads and the memory they're accessing likely ended up on different sockets, either because the OS scheduler migrated a thread post-allocation or because a large buffer was allocated before thread affinity was set, leaving it entirely on one node while threads run split across both. Confirm with `numastat` (cross-node access counts) and `numactl --hardware` for topology; fix by pinning both CPU and memory locality (`numactl --cpunodebind`/`--membind`, or the runtime's NUMA-aware equivalent).
**Follow-up trap:** *"Would you recommend NUMA-pinning every service by default as a preventive measure?"* — no; rigid pinning helps steady-state, latency-sensitive workloads but can hurt bursty or unpredictable workloads by removing the scheduler's flexibility to balance load across sockets — this should be a measured, workload-specific decision, not a blanket default.

### Q7 — Why is a sequential array scan so much faster than pointer-chasing through a linked list of the same total data size?
**Answer:** Sequential access amortizes each 64-byte cache line fetch across many useful bytes (touching one element pulls in ~15 more int32s "for free"), and the hardware prefetcher can predict the stride and fetch ahead of demand. Pointer-chasing wastes most of each fetched line (each node might be much smaller than 64 bytes and scattered across memory), gets no benefit from stride-based prefetching since the next address is data-dependent and unknowable until the current node is read, and each traversal step is effectively a full latency-bound miss if the working set exceeds cache capacity.
**Follow-up trap:** *"Does this mean linked lists are always the wrong choice?"* — no, but it does mean linked structures should be treated as a locality liability on genuinely hot paths; when a linked/tree structure is required, intrusive containers, memory pools, or arena allocation that keep related nodes physically close can recover much of the lost locality without abandoning the logical structure.

### Q8 — Explain why `struct { long a; long b; }` accessed by two different threads can be a serious production bug even though `a` and `b` are never logically shared.
**Testing:** whether the candidate can articulate the false-sharing mechanism unprompted, without the term being given in the question.
**Answer:** If `a` and `b` land within the same 64-byte cache line (highly likely for two adjacent `long`s in a default layout), every write to `a` by one thread invalidates the whole line in the other thread's cache per MESI, forcing the other thread to refetch before its next write to `b` even though it never touches `a`. Under sustained concurrent writes this can make two-thread "parallel" code slower than single-threaded, purely from coherence traffic — a correctness-clean, logically-parallel program with a severe hidden performance bug.
**Follow-up trap:** *"How would you have caught this in code review, before it ever ran?"* — largely you wouldn't, reliably — this is precisely why the answer isn't "read more carefully," it's "measure hot multi-threaded structures with `perf c2c` as a standard practice," especially for any struct with fields written by different threads at high frequency.

### Q9 — Compare the cost of a TLB miss, an L3 miss, and a NUMA-remote DRAM access. Which dominates and when?
**Answer:** A TLB miss (~100+ cycles for the page-table walk) happens *before* the data access; if it also misses L3 and hits remote NUMA DRAM, the costs stack — page-table walk cost, then the actual data fetch at remote-DRAM latency (200-300+ cycles local, 50-100% higher remote). For random-access workloads over large working sets on multi-socket hardware, the combination (TLB miss + NUMA-remote fetch) can be the dominant cost, easily exceeding 500 cycles for a single logical memory access — which is why database and JVM tuning guides treat huge pages and NUMA pinning as paired levers, not independent ones.
**Follow-up trap:** *"Does an L3 hit change this calculation much?"* — yes, substantially — if the translation and data are both cached (TLB hit, L3 hit), the same logical access costs on the order of tens of cycles instead of hundreds; this is exactly why working-set-fits-in-cache is such a dominant performance lever, and why "just add more RAM" doesn't fix a latency problem caused by cache/TLB misses, only a capacity problem.

### Q10 — Staff-level: you're asked to design a per-CPU counter array (like a metrics/stats system) for a highly concurrent service. What layout do you choose and why?
**Answer:** Allocate one counter (or small struct of counters) per logical CPU/thread, padded to a full 64-byte cache line (or the platform's `hardware_destructive_interference_size`) so no two CPUs' counters ever share a coherence unit — each CPU updates its own line with zero cross-core invalidation traffic, and reads (e.g. for a periodic aggregate) sum across all per-CPU slots, accepting eventually-consistent aggregation rather than a single globally-synchronized counter. This trades memory (N cache lines instead of one word) for eliminating coherence traffic entirely on the hot write path — the same pattern used by Linux kernel per-CPU variables and most production metrics libraries (e.g. per-core counters in high-throughput proxies).
**Follow-up trap:** *"What if you need an exact, immediately-consistent total, not eventual?"* — that requirement fundamentally conflicts with the lock-free per-CPU design; you'd need either a single contended atomic (accepting the coherence cost as the price of exact consistency) or a coarser synchronization point (periodic snapshot with a brief lock), and the honest answer is naming that tradeoff explicitly rather than claiming you can have both zero contention and exact real-time consistency for free.

---

## Red flags that fail you

- Confusing false sharing with a data race — false sharing has no logical data contention at all, only accidental cache-line co-location; calling it "a race condition" signals the mechanism isn't understood.
- Not knowing the L1/L2/L3/DRAM latency numbers even approximately, or being off by more than an order of magnitude.
- Claiming huge pages are a free win with no operational downside — ignoring documented transparent-huge-page latency-spike issues.
- Recommending NUMA pinning as a universal default rather than a measured, workload-specific decision.
- Describing MESI states incorrectly (e.g. claiming Exclusive requires bus traffic to write, when the entire point of Exclusive is a silent local upgrade to Modified).
- Proposing to "fix" false sharing with a mutex or atomic instead of padding — that adds real synchronization overhead to solve a problem that has no actual contention to synchronize.

---

## Cheat card

```
HIERARCHY (typical x86-64 server): L1 ~4-5cyc/~1ns (32-48KB) -> L2 ~12-14cyc/~3-4ns
  (256KB-2MB) -> L3 ~40-75cyc/~10-20ns (tens of MB shared) -> DRAM ~200-300cyc/~70-100ns
  Remote NUMA DRAM: +50-100% over local. L1-vs-DRAM ratio: ~100x.
CACHE LINE: 64 bytes (x86-64 and ARM64). Sequential access amortizes fetch; random wastes it.
ASSOCIATIVITY: N-way set-assoc trades HW cost for fewer conflict misses.
  L1 often 8-way, L3 often 12-16+ way.
FALSE SHARING: independent vars sharing one 64B line -> every write invalidates whole line
  for other core (MESI). 2-10x observed slowdown vs padded. Detect: perf c2c (HITM counter).
  Fix: alignas(64) / @Contended / manual padding -- NOT a lock, there's no real race.
TLB: caches VA->PA translation. Miss = page-table walk, ~100+ cycles, on TOP of the access.
  4KB pages default. Huge pages (2MB/1GB) cut TLB pressure for large working sets.
  Transparent hugepages: real risk of khugepaged-induced latency spikes (seen in Redis).
NUMA: memory attached per-socket. Remote access ~1.3-2x local latency, lower bandwidth.
  numactl --cpunodebind / --membind to pin; numastat to diagnose cross-node access.
MESI: M(odified, dirty, sole owner) E(xclusive, clean, sole owner, silent upgrade to M)
  S(hared, clean, multi-reader, write requires invalidate-broadcast) I(nvalid, stale)
```

## Sources

- Wulf & McKee, "Hitting the Memory Wall: Implications of the Obvious," ACM SIGARCH 1995 — original memory-wall framing
- Papamarcos & Patel, "A Low-Overhead Coherence Solution for Multiprocessors with Private Cache Memories," ISCA 1984 — foundational MESI-family coherence protocol
- Intel 64 and IA-32 Architectures Optimization Reference Manual — cache latency/associativity tables for recent Intel microarchitectures
- [Brendan Gregg — perf c2c false sharing detection](https://www.brendangregg.com/blog/2016-05-19/perf-c2c-false-sharing.html) — accessed 2026-08-03
- AMD Software Optimization Guide for Zen4/Zen5 — cache hierarchy specifics for AMD server parts
- C++17 `std::hardware_destructive_interference_size` (cppreference) — portable cache-line-aware padding
- Linux kernel documentation, `Documentation/admin-guide/mm/transparent_hugepage.rst` — khugepaged behavior and known latency caveats

## Changelog
- 2026-08-03 — created
