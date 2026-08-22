# Rust Performance: Zero-Cost Abstractions (Verified, Not Believed), SIMD, Criterion, Profiling

> **Track:** T20 Rust · **Time:** 2h · **Prereqs:** `T20-rust-ownership`, `T20-rust-memory` · **Updated:** 2026-08-05
> **Module id:** `T20-rust-perf` · **Tags:** performance, systems, benchmarking, critical

## The 30-second version

"Zero-cost abstraction" means the abstraction costs nothing *that a hand-written version wouldn't also cost*, and it is a claim you verify by reading the generated assembly, not a property you assume. Most of the time it holds spectacularly: a `fold` over a `&[Add1]` slice compiled to two instructions (`lea`, `ret`) on rustc 1.97.1 because LLVM proved the whole loop was `x + len`, and an iterator sum and an index loop over `&[u64]` produced 34 and 35 instructions of identical vectorized `paddq` code. It fails predictably in four places: behind `dyn Trait` (no monomorphisation, so no inlining, so a `call *0x18(%rcx)` per element), across a crate boundary for large functions without LTO, on floating-point reductions where IEEE non-associativity blocks autovectorisation (my `dot_f32` stayed scalar even with `-C target-cpu=native` on an AVX2 machine, and manually splitting it into 8 accumulators was 6.67x faster), and on indirect indexing where the bounds check genuinely survives. The costs you *do* pay are compile time and binary size from monomorphisation (200 generic instantiations: 536 ms vs 169 ms and 494 KB vs 387 KB against the `dyn` equivalent), and in production the bottleneck is almost never the abstraction at all: it is allocation, cache misses, and false sharing, which cost me 57x, 3.06x and 3.68x respectively in the measurements below. Benchmark with Criterion 0.8.2 and `std::hint::black_box`, but know that `black_box` on the input is not enough to stop the optimiser deleting your work: my 10-million-iteration sum benchmarked at 955 picoseconds because LLVM found the closed form.

## Why this gets asked

Because "Rust is fast" is a slogan and the interviewer wants to know whether you have ever actually *checked*. Almost every senior Rust engineer has personally shipped a change that was supposed to be faster and wasn't, then spent a day discovering the reason: an iterator over `Box<dyn Fn>` that couldn't inline, a `.collect::<Vec<_>>()` in a hot loop allocating 200k times per request, a `HashMap<String, _>` keyed by strings that were cloned on every lookup, or a microbenchmark that showed a 40x improvement because the optimiser had deleted the entire body. That last one is the specific war story that makes this question a filter: someone on the team reported a "50x speedup", it did not materialise in production, and the postmortem found the benchmark was measuring an empty loop.

The second thing they are probing is whether you profile or guess. A candidate who says "I'd use `#[inline(always)]` and switch to SIMD" before showing a flamegraph is telling the interviewer that they optimise by folklore. A candidate who says "first I'd check whether we're allocation-bound with `dhat` or `perf stat`, because in my experience the abstraction is rarely the problem" is telling them something else. For someone who has already driven an 89% ETL latency reduction and diagnosed a ClickHouse OOM, the transferable skill is obvious; what they are testing is whether you know the *Rust-specific* layer: which optimisations rustc and LLVM actually perform, which ones they silently decline, and how to tell the difference in under five minutes.

---

## Lineage: past → present → future

**What came before.** C++ coined "zero-overhead abstraction" (Bjarne Stroustrup's formulation: "what you don't use, you don't pay for; what you do use, you couldn't hand-code better"), and templates delivered on it for `std::sort` versus C's `qsort`, which paid an indirect call per comparison. The pain that killed the pure-C++ answer was not performance, it was that the guarantee was unverifiable and unenforced: `std::vector::operator[]` had no bounds check and `at()` had one that never got elided reliably, iterator invalidation was undefined behaviour rather than a compile error, and template instantiation blowup produced binaries and compile times nobody could predict (the canonical horror stories from Boost-heavy codebases in the 2000s involved 20-minute single-translation-unit builds). Meanwhile the managed-language world took the opposite trade: Java's JIT (HotSpot C2, 1999 onward) could inline *through* virtual calls using runtime class-hierarchy analysis and speculative devirtualisation, which is a genuinely stronger optimisation than anything an ahead-of-time compiler can do, but paid for it with warmup time, deoptimisation cliffs, a GC that made p99 latency a tuning exercise, and object headers plus pointer-chasing layouts that destroyed cache locality. The specific pain: teams doing low-latency work in Java ended up writing `long[]` arrays of manually packed fields to escape object layout, which is C with extra steps.

**Where it stands now.** Rust's position is that the abstraction is zero-cost *and* the safety is compile-time-enforced, with the escape hatch being that you can read the assembly and confirm it. That is now genuinely deployed at scale: Cloudflare's Pingora, AWS Firecracker and the S3 ShardStore, Discord's read-states service (the famous 2020 migration away from Go specifically to escape GC latency spikes), and the Linux kernel's Rust support. The live disagreement is about what "zero-cost" is allowed to mean. One camp (broadly, the language team's framing) holds that it means "no worse than the hand-written equivalent, given the same semantics", and that bounds checks are part of the semantics, not overhead. The other camp, largely people writing numerical and cryptographic kernels, points out that the abstraction is only zero-cost when LLVM cooperates, that FP reductions and indirect indexing are cases where it reliably does not, and that the monomorphisation tax (compile time, binary size, instruction-cache pressure) is a real cost that the slogan hides. Both are right; the useful answer in an interview is that the claim is falsifiable and you know how to falsify it. Separately, the tooling has consolidated: Criterion moved to the `criterion-rs` GitHub organisation with v0.8.2 (released 2026-02-04, MSRV Rust 1.88) after a maintenance gap under the original `bheisler` repo, Divan arrived in 2023 as a faster, simpler alternative that a meaningful slice of the ecosystem now prefers, and `samply` has largely displaced the raw `perf` + FlameGraph Perl-script pipeline for interactive work.

**Where it's heading.** Three things, at descending confidence. High confidence: portable SIMD stays nightly-only for a while yet. As of rustc 1.97.1 (2026-07-14) `std::simd` is still gated behind `#![feature(portable_simd)]`, tracking issue rust-lang/rust#86656, with `Simd<T, N>` for lane counts 1 through 64 and, notably, `f16xN` types now present; stable code that wants portable vectors still reaches for the `wide` crate or hand-writes `std::arch` intrinsics with `is_x86_feature_detected!` dispatch. Medium confidence: the benchmarking ecosystem keeps fragmenting rather than converging, with Criterion holding the "statistical rigour and regression detection" niche and Divan taking the "I want a number in two seconds" niche; codspeed-style CI-integrated instrumented benchmarking (which uses simulated-CPU counts rather than wall time to get variance low enough for CI gating) is the interesting third path. Speculative, flag it as such: there is ongoing work on making rustc emit better aliasing metadata (`noalias` on `&mut`, which was famously disabled and re-enabled multiple times between 2015 and 2021 due to LLVM miscompilation bugs) and on autodiff/GPU offload in the compiler; if the aliasing story keeps improving, some of the FP-reduction and pointer-disambiguation failures documented below will quietly stop being failures, which is exactly why you should re-run the assembly check on a new toolchain rather than trusting a blog post from 2022.

---

## Mental model

```
THE CLAIM:  high-level Rust  ==compiles to==>  what you'd hand-write in C
THE METHOD: don't believe it. diff the assembly.

  iterator chain            index loop
  v.iter().sum()            for i in 0..n { t += v[i] }
        |                          |
        +---------- LLVM ----------+
                     |
              [ SAME machine code ]   <- verify with cargo-show-asm

WHERE THE ABSTRACTION SURVIVES (measured, rustc 1.97.1, x86-64):
  generics / impl Trait  -> monomorphised -> inlined -> vectorised
  closures (FnMut)       -> a struct with a call method -> inlined
  Iterator adaptors      -> internal iteration -> loop fusion, NO bounds checks
  newtype wrappers       -> #[repr(transparent)] -> literally the same bits

WHERE IT DIES (also measured):
  dyn Trait      -> vtable -> `call *0x18(%rcx)` -> inlining barrier
  crate boundary -> big fn, no #[inline], no LTO -> real call
  f32/f64 sum    -> IEEE non-associativity -> LLVM refuses to reorder -> scalar
  a[idx[i]]      -> index unknown at compile time -> bounds check survives

THE COST YOU DO PAY (never zero):
                 monomorphised          dyn
  compile time   536 ms                 169 ms      (3.17x)
  .rlib size     494,904 B              387,256 B   (1.28x)
  LLVM IR        10,847 lines           5,690 lines (1.91x)
       (200 instantiations of one 8-line generic fn)

THE THING THAT IS ACTUALLY SLOW IN YOUR SERVICE:
      allocation  >  cache misses  >  false sharing  >>  the abstraction
        57x           3.06x            3.68x              ~0x
   (String vs &str)  (AoS vs SoA)   (packed vs padded)
```

The memory-hierarchy half of the model, which is what most "why is my Rust slow" questions actually reduce to:

```
                 latency        my measured cost per touch
  register        0 cyc         -
  L1d  48 KB      ~4-5 cyc      0.36 ns  (stride 1B, 64 sequential touches/line)
  L2   1.25 MB    ~14 cyc       -
  L3   12 MB      ~40-50 cyc    -
  DRAM            ~200-300 cyc  3.22 ns  (stride 64B = 1 touch per cache line)
                                6.63 ns  (stride 256B, prefetcher losing)

  CACHE LINE = 64 BYTES. This single number explains:
    - AoS vs SoA (you pay for the 28 bytes you didn't want)
    - false sharing (4 AtomicU64 = 32 B, all on ONE line, 4 cores fighting)
    - #[repr(align(64))] padding (the fix for the above)
    - why linked lists lose to Vec even at equal asymptotic complexity
```

---

## How it actually works

Everything in this section was compiled and run on rustc 1.97.1 (8bab26f4f, 2026-07-14), stable, `x86_64-unknown-linux-gnu`, `opt-level=3`, on a 12th Gen Intel Core i5-12450H (Alder Lake, 4 P-cores + 4 E-cores, AVX2 and FMA present, no AVX-512). Assembly was extracted with `objdump -d`. Numbers are minimum-of-N wall time unless stated, which is the right statistic for "how fast can this go" and the wrong one for "what will my p99 be"; Criterion's are medians with confidence intervals.

### The verification loop: how to actually check a zero-cost claim

Three tools, in increasing order of ceremony:

1. **Compiler Explorer** (godbolt.org) for a self-contained snippet. Set the compiler to a specific rustc version and pass `-C opt-level=3`. Mark the function `#[no_mangle] pub extern "C"` or `pub` in a `--crate-type=lib` so it survives dead-code elimination.
2. **`cargo-show-asm`** (`cargo install cargo-show-asm`, then `cargo asm --lib 'mycrate::myfunc' --rust`) for code inside a real crate with real dependencies. The `--rust` flag interleaves source lines with assembly, which is what makes it readable. It also emits `--llvm` (LLVM IR) and `--mir`, and the MIR view is the right one when you want to know what rustc did *before* handing off to LLVM.
3. **`objdump -d target/release/libfoo.rlib`** when you want the ground truth including linker-visible symbols. This is what I used below because it is the least likely to be lying to me.

The single most common mistake is checking a debug build. `cargo build` defaults to `opt-level=0`, where nothing is inlined, every bounds check is present, and iterator chains genuinely are slower than loops. Every measurement and every assembly listing in this module is `--release`.

**Test 1. Does an iterator chain compile to the same code as the index loop?**

```rust
#[no_mangle]
pub fn sum_loop(v: &[u64]) -> u64 {
    let mut t = 0u64;
    for i in 0..v.len() { t = t.wrapping_add(v[i]); }
    t
}
#[no_mangle]
pub fn sum_iter(v: &[u64]) -> u64 {
    v.iter().copied().fold(0u64, |a, b| a.wrapping_add(b))
}
```

Result: `sum_loop` is 34 instructions, `sum_iter` is 35. The bodies are semantically identical and both contain the same vectorised core:

```asm
40:  movdqu (%rdi,%rdx,1),%xmm2
45:  paddq  %xmm2,%xmm1
49:  movdqu 0x10(%rdi,%rdx,1),%xmm2
4f:  paddq  %xmm2,%xmm0        ; two independent xmm accumulators
53:  add    $0x20,%rdx          ; 32 bytes = 4 u64 per iteration
57:  cmp    %rdx,%rax
5a:  jne    40
5c:  paddq  %xmm1,%xmm0         ; horizontal reduce at the end
60:  pshufd $0xee,%xmm0,%xmm1
65:  paddq  %xmm0,%xmm1
```

`diff` of the two listings shows the only differences are label names and the *order* of two `xor` register-zeroing instructions. That is register-allocation noise, not a cost. Both got SSE2 `paddq` with a 2x unroll (4 `u64` per iteration), and neither has a bounds check inside the loop: `v[i]` where `i` comes from `0..v.len()` is a range LLVM can prove. This is the claim holding, and it is the version of the answer you give: not "they're the same", but "34 versus 35 instructions, identical vector core, difference is register-zeroing order".

**Test 2. The case that looks the same and is not.** Here is the same reduction over `f32`:

```rust
#[no_mangle] pub fn sum_f32(v: &[f32]) -> f32 { v.iter().sum() }
#[no_mangle] pub fn dot_f32(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}
```

`sum_f32` compiles to 39 instructions containing **zero** packed-vector operations. What LLVM emitted is an 8x-unrolled chain of *scalar* `addss`:

```asm
40:  addss  (%rdi,%rcx,4),%xmm0
45:  addss  0x4(%rdi,%rcx,4),%xmm0
4b:  addss  0x8(%rdi,%rcx,4),%xmm0
51:  addss  0xc(%rdi,%rcx,4),%xmm0     ; ... 8 of these, all into %xmm0
```

Eight loads, eight adds, one accumulator, and therefore one serial dependency chain at roughly 4 cycles of `addss` latency per element. The unroll bought nothing because every add depends on the previous one. LLVM did this because IEEE-754 addition is **not associative**: `(a+b)+c != a+(b+c)` for some inputs, so reordering the sum into 4 or 8 lanes changes the answer, and LLVM will not silently change your numerics. Rebuilding with `-C target-cpu=native` on a machine that reports `avx2 fma sse4_2` changed nothing: `dot_f32` went from 48 to 60 instructions, with 0 `ymm` registers used and 0 `vfmadd` instructions. The instruction mix was 5 `vaddss`, 5 `vmulss`, 8 `vmovss`. All scalar. Compare `sum_i32` in the same build, which used 8 `ymm` registers and vectorised cleanly, because integer wrapping addition *is* associative.

The fix is to break the dependency chain yourself, which is a semantic change you are choosing to make:

```rust
pub fn dot_unroll8(a: &[f32], b: &[f32]) -> f32 {
    let n = a.len().min(b.len());
    let chunks = n / 8;
    let mut acc = [0f32; 8];
    for c in 0..chunks {
        let (x, y) = (&a[c*8..c*8+8], &b[c*8..c*8+8]);
        for l in 0..8 { acc[l] += x[l] * y[l]; }   // 8 independent chains
    }
    let mut s = acc.iter().sum::<f32>();
    for i in chunks*8..n { s += a[i] * b[i]; }
    s
}
```

Criterion result on 4096-element `f32` slices: `scalar_sum` 1.9323 µs, `unroll8` 289.69 ns. **6.67x.** Per element that is 471.7 ps versus 70.7 ps. Note what you gave up: the two functions can produce different last-bit results, and if you are computing a financial aggregate or something that must be bit-reproducible across machines, that is a correctness regression, not an optimisation. Say that out loud in an interview.

**Test 3. Where the abstraction is not just equal but better.** A `fold` over a slice of a concrete zero-sized-ish type:

```rust
pub trait Op { fn apply(&self, x: u64) -> u64; }
pub struct Add1;
impl Op for Add1 { fn apply(&self, x: u64) -> u64 { x + 1 } }

#[no_mangle] pub fn run_static(ops: &[Add1], x: u64) -> u64 {
    ops.iter().fold(x, |a, o| o.apply(a))
}
```

Compiles to, in full:

```asm
0000000000000000 <run_static>:
   0:  lea    (%rsi,%rdx,1),%rax
   4:  ret
```

Two instructions. LLVM monomorphised the fold, inlined `apply`, recognised the loop as `x + 1` repeated `len` times, and replaced the entire thing with an addition. No hand-written C loop beats that. Now the `dyn` version:

```rust
#[no_mangle] pub fn run_dyn(ops: &[Box<dyn Op>], x: u64) -> u64 {
    ops.iter().fold(x, |a, o| o.apply(a))
}
```

24 instructions, with a real loop and this at its heart:

```asm
20:  mov    (%r14,%r15,1),%rdi     ; data pointer
24:  mov    0x8(%r14,%r15,1),%rcx  ; vtable pointer (fat pointer = 16 bytes)
29:  mov    %rax,%rsi
2c:  call   *0x18(%rcx)            ; indirect call through vtable slot 3
2f:  add    $0x10,%r15             ; stride 16 = size of Box<dyn Op>
```

`call *0x18(%rcx)` is the whole story: offset `0x18` is 24 bytes into the vtable, which is slots 0/1/2 (drop-in-place, size, align) followed by the first method. The compiler cannot see through it, so it cannot inline, so it cannot constant-fold, so it cannot vectorise. That is 2 instructions versus a loop with an indirect call per element. This is the answer to "what does `dyn` actually cost": not the ~2-5 cycles of the indirect call itself (branch predictors handle monomorphic call sites well), but the *optimisation barrier* it erects around everything downstream.

**Test 4. The bounds check that survives, and the one that doesn't.** People repeat "bounds checks are eliminated" and "bounds checks cost 5%" with equal confidence and neither is a rule. Here is what actually happened.

```rust
#[no_mangle] pub fn sum_idx_bad(v: &[u64], n: usize) -> u64 {
    let mut t = 0u64;
    for i in 0..n { t = t.wrapping_add(v[i]); }   // n is unrelated to v.len()
    t
}
```

You would predict a per-iteration check. What LLVM actually did was **hoist** it: one `cmp %rax,%rsi; jbe <panic>` before the loop testing `n-1 < v.len()`, then a fully vectorised `paddq` loop identical to the safe version. That is loop-invariant bounds-check hoisting, and it is why the naive "add `assert!(n <= v.len())` at the top" trick often measures as zero improvement: LLVM already did it. Adding the idiomatic hint (`let v = &v[..n];`) produced 43 instructions versus 41, i.e. very slightly *worse*, because the explicit slice reborrow added its own check that LLVM then could not merge.

Now the case where it genuinely survives, indirect indexing:

```rust
#[no_mangle] pub fn gather_bad(src: &[f32], idx: &[usize], out: &mut [f32]) {
    for i in 0..idx.len() { out[i] = src[idx[i]]; }
}
```

26 instructions, and the loop body contains **two** live bounds checks per iteration:

```asm
10:  mov    (%rdx,%r10,8),%rax     ; load idx[i]
14:  cmp    %rsi,%rax
17:  jae    46 <panic_bounds_check> ; check 1: idx[i] < src.len()
19:  cmp    %r10,%r9
1c:  je     33 <panic_bounds_check> ; check 2: i < out.len()
1e:  movss  (%rdi,%rax,4),%xmm0
23:  movss  %xmm0,(%r8,%r10,4)
```

No vectorisation at all, because a data-dependent gather with a possible panic in the middle is not something LLVM will speculate through. The cost, measured over 1M elements: random indirect `src[idx[i]]` 1.896 ms, sequential indirect `src[seq[i]]` 0.714 ms, and the iterator form `for (o, s) in out.iter_mut().zip(&src)` 0.179 ms. The iterator is **10.6x** faster than random indirect and **4.0x** faster than sequential indirect. Note that most of the random-versus-sequential gap (1.896 vs 0.714) is cache misses, not the check; the check's contribution is visible in the sequential-versus-iterator gap.

**How to help LLVM prove it, in order of preference:**
- Use iterators. `zip`, `chunks_exact`, `windows`, `iter().enumerate()`. Internal iteration means the length is a loop-carried invariant the compiler owns. In my zip test, the hand-written `for i in 0..a.len() { out[i] = a[i] + b[i] }` produced 63 instructions with 2 panic-call sites, while `out.iter_mut().zip(a).zip(b)` produced 37 instructions with 0. The iterator was smaller *and* had no panic paths.
- Slice first, then index: `let (a, b) = (&a[..n], &b[..n]);` collapses three independent length facts into one.
- `chunks_exact(8)` gives LLVM a compile-time-known inner length of 8, which is the single most effective vectorisation hint in safe Rust.
- `assert!(i < v.len())` before a loop, as a last resort. It is a real technique (it gives LLVM a fact it can propagate) but as shown above it frequently does nothing because the hoist already happened.
- `get_unchecked`, which is `unsafe`, requires you to have actually proven the invariant, and should come with a `// SAFETY:` comment explaining the proof. Reach for this only after measuring that the check is on the profile, which in my experience is roughly one time in twenty.

### Monomorphisation: the cost that is genuinely not zero

Every distinct type argument to a generic function produces a distinct copy of that function's machine code. That is what makes `run_static` two instructions. It is also what makes your build slow. I measured this directly: one 8-line generic function with a `Shape` bound, instantiated over 200 distinct concrete types, versus the identical function taking `&[&dyn Shape]` and instantiated once.

| Metric | 200 monomorphised instantiations | Single `dyn` instantiation | Ratio |
|---|---|---|---|
| Clean rebuild, `--release` | 536 ms | 169 ms | 3.17x |
| `.rlib` size | 494,904 B | 387,256 B | 1.28x (+107,648 B) |
| LLVM IR lines emitted | 10,847 | 5,690 | 1.91x |

Scale that mentally. This is *one small function*. A real service pulling in `serde`, `tokio`, `reqwest` and a few `#[derive]`-heavy crates instantiates thousands of these, and the reason a 50-KLOC Rust service takes 4 minutes to build while an equivalent Go service takes 8 seconds is overwhelmingly monomorphisation plus LLVM optimisation of the resulting IR, not the borrow checker (which is typically single-digit percent of build time; check yours with `cargo build --timings` and `-Z self-profile` on nightly).

Diagnosing it is mechanical: `cargo install cargo-llvm-lines`, then `cargo llvm-lines --release | head -30` ranks functions by lines of LLVM IR generated, which correlates almost perfectly with compile time and binary size contribution. The usual offenders are generic functions with a large body called with many type parameters, and the standard fix is the **thin generic wrapper**: keep the type-parameterised surface tiny and push the bulk into a non-generic inner function.

```rust
// BAD: the whole 200-line body is duplicated per P.
pub fn load<P: AsRef<Path>>(p: P) -> io::Result<Config> { /* 200 lines */ }

// GOOD: one line duplicated per P; the 200 lines exist exactly once.
pub fn load<P: AsRef<Path>>(p: P) -> io::Result<Config> { load_inner(p.as_ref()) }
fn load_inner(p: &Path) -> io::Result<Config> { /* 200 lines */ }
```

Other levers, with their real costs: `codegen-units = 1` (default is 16 for release) improves optimisation quality and shrinks binaries but serialises the backend, so builds get slower; `lto = "thin"` is the good default and `lto = "fat"` costs the most build time; `panic = "abort"` removes all landing-pad and unwind-table code, typically 5-10% of a binary, at the cost of losing `catch_unwind` and per-thread panic recovery; `opt-level = "z"` optimises for size over speed and will disable loop unrolling and vectorisation, so never use it on a compute-bound service; and `strip = "symbols"` cuts a large fraction of the file size but destroys your ability to read a flamegraph, so use `strip = "debuginfo"` or keep a separate symbol file instead.

### Inlining: `#[inline]`, `#[inline(always)]`, and the LTO story that is now half-obsolete

Within a crate, rustc and LLVM inline based on a cost model and `#[inline]` is a *hint* you rarely need. The classic rule is that across a crate boundary, a non-generic function without `#[inline]` cannot be inlined because its MIR is not exported, and you need either `#[inline]` (which forces MIR export) or LTO. **That rule is now partly outdated and it is a great thing to know in an interview.** rustc's MIR inliner has been enabled on stable for several years and does cross-crate inlining of small-to-medium functions regardless of `#[inline]`. I tested it: a two-crate workspace with `pub fn scale(x: f64, k: f64) -> f64 { x * k + 1.0 }` in the dependency and no `#[inline]` attribute, built with `lto = false`, produced **zero** `call` instructions to `scale` in the consumer binary. Then I made the function genuinely bulky (an 8-iteration loop with `mul_add`, `sqrt`, `ln`, and branches) and it *still* inlined with LTO off.

What LTO actually bought in that test:

| Build | Binary size | Build time | `call bulky` sites | Runtime |
|---|---|---|---|---|
| `lto = false`, default CGUs | 4,426,416 B | 0.14 s | 0 | 928.9 ms |
| `lto = "fat"`, `codegen-units = 1` | 2,221,304 B | 2.48 s | 0 | 895.3 ms |

A **49.8% binary size reduction** and a 17.7x build-time increase, for a 3.6% runtime difference that is close to noise on a loop that is FP-latency-bound anyway. That is the honest summary of LTO in 2026: it is primarily a *size* and cross-crate-devirtualisation tool, and the runtime win depends entirely on whether your hot path actually crosses crate boundaries at a call site the MIR inliner declined. Measure before you pay 17x on CI.

The attribute rules, precisely:
- `#[inline]` is a hint plus a guarantee that the function's MIR is available to downstream crates. Put it on small, hot, cross-crate functions (accessors, `new`, operator impls). Cost: every downstream crate that inlines it emits its own copy, growing their binaries.
- `#[inline(always)]` overrides LLVM's cost model. This is almost always wrong. The two legitimate uses are a wrapper that must vanish for correctness of an intrinsic sequence (common in `std::arch` shims, where `#[inline(always)]` plus `#[target_feature]` is how you get the intrinsic into the caller's `target_feature` context), and a function whose body is smaller than its call sequence. Applying it to a large function inflates code size, blows the instruction cache, and can measure *slower*.
- `#[inline(never)]` is a profiling tool. Add it temporarily so a function shows up as its own frame in a flamegraph instead of being smeared into its callers. This is the single most useful profiling trick in Rust and almost nobody mentions it.
- Generic functions are implicitly inlinable cross-crate because their MIR must be exported to be monomorphised at all. This is why generic-heavy crates like `serde` inline well without LTO.

### Allocation: the actual culprit, and where the folklore is wrong

If you profile a Rust service that someone believes is "slow because of abstractions", the flamegraph will show `malloc`, `free`, `memcpy` and `realloc`. Allocation is the real cost. But the specific folklore around it is more nuanced than the advice you will read, and I measured the nuance.

`Vec::with_capacity` is supposed to beat repeated `push`. Here is what actually happened over 1,000,000 elements:

| Workload | No capacity hint | `with_capacity` | Ratio |
|---|---|---|---|
| `Vec<u64>`, 1M pushes | 0.677 ms | 0.674 ms | 1.00x |
| `Vec<[u64; 8]>` (64-byte elems), 1M pushes | 19.902 ms | 18.235 ms | 1.09x |
| `Vec<String>`, 200k pushes | 10.491 ms | 6.619 ms | **1.58x** |
| `(0..1M).collect::<Vec<u64>>()` | 0.203 ms | (n/a) | **3.33x vs push loop** |

Read that carefully, because it is a better answer than the folklore. For `Vec<u64>` the pre-allocation won **nothing**. Growth is amortised doubling, so 1M pushes cost about 20 reallocations total, and for large blocks glibc's `realloc` frequently extends the mapping in place rather than copying. Where `with_capacity` earned its 1.58x was `Vec<String>`, because every realloc there has to `memcpy` 24-byte `String` headers *and* the allocator is already under pressure from 200k separate string allocations, so it cannot extend in place. And the biggest single win, 3.33x over the push loop, came from `collect()`, which uses `Iterator::size_hint` to allocate exactly once and then writes through a raw pointer with no per-push capacity check.

The rule that falls out: **`with_capacity` matters in proportion to how expensive the element move is and how fragmented the heap already is.** For `Copy` scalars into a fresh heap it is nearly free either way; for anything owning a heap allocation it is real. And `collect()` from a `TrustedLen`/exact-size iterator beats both.

The genuinely enormous number is `String` versus `&str`:

| Workload over 200k words | Time |
|---|---|
| `w.clone() + "!"` (allocates a fresh `String` per item) | 3.899 ms |
| `w.len() + 1` (no allocation) | 0.068 ms |

**57x.** That is the single most common real Rust performance bug I would expect in an AI/backend service: a request handler that takes `&str`, immediately `.to_string()`s it into a struct, clones that struct into a `HashMap` key, and does it 500 times per request. Nobody notices until the p99 moves.

The toolkit, in order of how often it is the right answer:
- **Take `&str` / `&[T]` in function signatures, own only at storage boundaries.** Free, and it is an API design decision, not an optimisation.
- **`Cow<'a, str>`** when a function usually borrows but occasionally must modify. `Cow::Borrowed` is zero-cost; `Cow::Owned` allocates only on the path that needs it. This is the right shape for normalisation and escaping functions where 95% of inputs are already clean.
- **`Vec::with_capacity` / `String::with_capacity` / `HashMap::with_capacity`.** For `HashMap` the win is larger than for `Vec` because growth means rehashing every key, not just a `memcpy`.
- **`SmallVec<[T; N]>`** (from the `smallvec` crate) stores up to N elements inline in the struct and spills to the heap beyond that. The right N is the p95 of your actual length distribution, not a round number. The cost is real: `SmallVec<[T; 16]>` where `T` is 8 bytes makes the struct at least 128 bytes plus discriminant, so passing it by value gets expensive and putting it in a `Vec` wastes memory for the common short case. Measure `size_of` before adopting. `ArrayVec` is the fixed-capacity, never-spills variant, and `SmallString`/`compact_str` do the same for strings (`compact_str` inlines up to 24 bytes on 64-bit, which covers a large fraction of real identifiers).
- **Arena / bump allocation** (`bumpalo`, or a hand-rolled `Vec<T>` plus `u32` indices) when you have a phase structure: allocate many objects, use them, drop them all at once. A bump allocator's `alloc` is a pointer increment and a bounds compare, roughly 2-3 instructions versus ~100+ for `malloc`, and `free` is resetting one pointer. This is also the standard idiomatic answer to graph and tree structures in Rust (see `T20-rust-ownership`) and it happens to be the fastest one, because indices are 4 bytes instead of 8 and the nodes are contiguous.
- **Swap the global allocator.** `mimalloc` or `jemallocator` as `#[global_allocator]` routinely wins 10-30% on allocation-heavy multithreaded workloads versus glibc `malloc`, purely from better per-thread caching and less lock contention. It is a three-line change and it is the highest-leverage thing you can do to an allocation-bound service before you refactor anything. The cost is a larger binary and a dependency with `unsafe` in it.
- **Reuse buffers across iterations.** `buf.clear(); read_into(&mut buf);` in a loop keeps the capacity and does zero allocations after the first. This is the pattern behind every fast parser and serialiser in the ecosystem.

### Cache behaviour and data layout

The cache line is 64 bytes on every x86-64 and every ARM64 you will deploy on (Apple M-series has 128-byte lines on some levels, which is why `crossbeam-utils`'s `CachePadded` pads to 128 on aarch64). Here is the stride experiment over a 64 MB buffer, touching one byte every K bytes:

| Stride | Touches | ns per touch |
|---|---|---|
| 1 B | 67,108,864 | 0.36 |
| 4 B | 16,777,216 | 0.53 |
| 16 B | 4,194,304 | 1.22 |
| 32 B | 2,097,152 | 2.06 |
| **64 B** | 1,048,576 | **3.22** |
| 128 B | 524,288 | 5.52 |
| 256 B | 262,144 | 6.63 |

The cost per touch climbs 8.9x from stride 1 to stride 64, then only 2.06x more from 64 all the way to 256. That knee is the cache line making itself visible: below 64 bytes you are amortising one memory fetch over multiple touches, at and above 64 bytes every touch is its own line. The 128-and-256 numbers are still cheaper than a full cold miss because the hardware prefetcher is still tracking a constant stride; make the stride random and you fall off that cliff too.

**Array-of-structs versus struct-of-arrays.** This is the layout decision that matters. Given 1,000,000 particles:

```rust
#[derive(Clone, Copy)]
struct Particle { x: f32, y: f32, z: f32, vx: f32, vy: f32, vz: f32, mass: f32, charge: f32 }
// size_of::<Particle>() == 32 bytes  (8 x f32, no padding)
```

Summing just `p.x` across all of them:

| Layout | Bytes the CPU must pull | Time |
|---|---|---|
| AoS: `Vec<Particle>`, read `p.x` | 32,000,000 | 1.394 ms |
| SoA: `Vec<f32>` of just `x` | 4,000,000 | 0.456 ms |

**3.06x**, from an 8x reduction in bytes touched. Note it is not 8x: at 32 MB you are DRAM-bandwidth-bound and the prefetcher does well on both, so the speedup is sublinear in the traffic reduction. The decision rule: if your hot loops touch a *subset* of fields across *many* objects, go SoA; if they touch *all* fields of *one* object at a time, AoS is right and SoA will be slower because you now have 8 independent streams competing for prefetcher slots and TLB entries. Most real code is somewhere in between, and the pragmatic middle ground is "hot/cold splitting": put the 3 fields the hot loop reads in one struct and box the other 20 fields behind a pointer.

Related layout facts worth having cold:
- Rust's default `repr(Rust)` gives the compiler freedom to **reorder fields**, and it does, sorting by alignment to minimise padding. `struct S { a: u8, b: u64, c: u8 }` is 16 bytes in Rust and 24 bytes in C. This is a real win you get for free and lose the moment you add `#[repr(C)]`.
- `#[repr(C)]` exists for FFI and for any struct whose byte layout is part of a wire format or a mmap'd file. Adding it "for predictability" without needing it costs you padding. `#[repr(packed)]` additionally removes padding, and creates unaligned fields, and taking a reference to an unaligned field is undefined behaviour, so it should be confined to parsing code that reads fields by value.
- `#[repr(transparent)]` on a newtype guarantees identical layout and ABI to the inner type. This is what makes `struct UserId(u64)` genuinely zero-cost including across FFI.
- Enum layout: `Option<&T>`, `Option<Box<T>>`, and `Option<NonZeroU32>` are the same size as the payload because of niche optimisation (the null pointer or the zero value encodes `None`). `Option<u64>` is 16 bytes because there is no spare bit pattern. This matters when you are putting millions of them in a `Vec`.
- `size_of::<Vec<T>>() == 24` on 64-bit (ptr, len, cap). `size_of::<String>() == 24`. `size_of::<&[T]>() == 16` (fat pointer). `size_of::<&dyn Trait>() == 16` (data ptr + vtable ptr). A `Vec<Box<dyn Trait>>` therefore costs 16 bytes per element *plus* a separate heap allocation per element, with no locality between them.

**False sharing** is the multithreaded version of the same 64-byte fact, and it is the one that produces the most baffling production symptom: adding threads makes throughput go *down*, with high `cpu` and near-zero useful work. Four threads, each doing 50,000,000 relaxed `fetch_add` on its own counter:

| Layout | Time |
|---|---|
| `Vec<AtomicU64>` (8 bytes each, 4 fit in one 64-byte line) | 1768.298 ms |
| `#[repr(align(64))] struct Padded(AtomicU64)` (64 bytes each) | 481.023 ms |

**3.68x penalty** purely from cache-line ping-pong. Each core's write invalidates the line in the other three cores' L1, so every increment becomes a coherence transaction on the interconnect instead of a local L1 hit. Nothing in the source code hints at this; the counters are logically independent. The fix is one attribute, or `crossbeam_utils::CachePadded<T>`, which handles the aarch64-128-byte case for you. The diagnostic is `perf c2c` on Linux, which directly reports HITM (hit-modified) events and tells you which cache line and which two instructions are fighting. Failing that, `perf stat -e cache-misses,LLC-load-misses` showing an enormous miss count with a tiny working set is the tell.

### SIMD: autovectorisation, when LLVM gives up, and explicit vectors

Autovectorisation is the default and it works more often than people expect. `sum_i32` above vectorised to AVX2 with 8 `ymm` registers under `-C target-cpu=native`. What makes LLVM give up, in rough order of how often you will hit it:

1. **Floating-point reductions.** Demonstrated above: `sum_f32` stayed scalar even with AVX2 and FMA available, because reassociation changes results. There is no stable Rust equivalent of `-ffast-math`; the nightly `core::intrinsics::fadd_fast` family and the `fast_float` style crates exist, and the stable answer is manual accumulator splitting as shown, which is explicit about the numerics change.
2. **Possible aliasing.** If two `&mut [f32]` could overlap, LLVM must either not vectorise or emit a runtime overlap check plus two code paths. Rust's `&mut` is `noalias` at the LLVM level, which is a genuine advantage over C here, but it does not extend through raw pointers or through indices into a shared buffer.
3. **A possible panic inside the loop.** A bounds check, an integer overflow check in debug, or a `.unwrap()` creates a side exit LLVM will not speculate past. This is the mechanism behind the `gather_bad` result: two panic edges, zero vectorisation.
4. **Non-contiguous or data-dependent access.** Gathers and scatters. AVX2 has `vgatherdps` but it is slow enough (roughly 12-20 cycles) that LLVM's cost model usually declines.
5. **Loop-carried dependencies** that are not reductions, e.g. `a[i] = a[i-1] * 2 + b[i]`. Genuinely unvectorisable.
6. **Unknown or tiny trip counts.** LLVM emits a scalar prologue plus a vector body plus a scalar epilogue, and if it cannot prove the trip count is large enough to amortise that, it skips the vector body. `chunks_exact(8)` fixes this by construction.

When autovectorisation is not enough, the three explicit paths as of rustc 1.97.1:

- **`std::simd`** (portable SIMD) is **still nightly-only**, gated behind `#![feature(portable_simd)]`, tracking issue rust-lang/rust#86656. It provides `Simd<T, N>` for lane counts 1, 2, 4, 8, 16, 32 and 64, `Mask<T, N>`, `simd_swizzle!`, and as of the current docs includes `f16xN` types. The API is stable-looking and pleasant (`a + b` on `f32x8` is elementwise), operations lower to the best available instruction for the target, and on targets without SIMD it degrades to scalar code rather than failing to compile. It has been "nearly ready" for several years; do not tell an interviewer it is stable.
- **`std::arch` intrinsics** (`_mm256_add_ps` and friends) are stable and are what you actually ship today for x86-64 and aarch64. They are `unsafe`, architecture-specific, and require the right `target_feature` to be enabled at the call site.
- **The `wide` crate** is the pragmatic stable-Rust portable option (`f32x8`, `i32x8` types with operator overloading), and `pulp` and `multiversion` sit on top of the dispatch problem.

**`target-feature` and runtime dispatch** is the part candidates get wrong. `-C target-cpu=native` compiles for the machine doing the build, which is fine for a benchmark and a disaster for a container image that will run on a mixed fleet: the binary will `SIGILL` on any host missing an instruction it used. The three deployable options:

```rust
// untested sketch
// 1. Baseline: compile the whole binary for a floor everyone has.
//    RUSTFLAGS="-C target-cpu=x86-64-v2"   (SSE4.2, POPCNT)  ~ everything since 2009
//    RUSTFLAGS="-C target-cpu=x86-64-v3"   (AVX2, FMA, BMI)  ~ Haswell 2013+ / Zen 1+
//    v3 is the usual sweet spot for cloud fleets; verify your instance families first.

// 2. Per-function opt-in, with a runtime check. The standard shape:
#[target_feature(enable = "avx2")]
unsafe fn dot_avx2(a: &[f32], b: &[f32]) -> f32 { /* std::arch intrinsics */ 0.0 }

fn dot(a: &[f32], b: &[f32]) -> f32 {
    if is_x86_feature_detected!("avx2") {
        // SAFETY: guarded by the runtime feature check above.
        unsafe { dot_avx2(a, b) }
    } else {
        dot_scalar(a, b)
    }
}
// is_x86_feature_detected! reads CPUID and caches the result, so the check is
// a load and a test after the first call. Hoist it OUT of your hot loop anyway:
// resolve once into a fn pointer stored in a OnceLock and call through that.

// 3. The `multiversion` crate generates the above for a list of targets:
//    #[multiversion(targets("x86_64+avx2", "x86_64+sse4.2"))]
//    with "direct" dispatch (direct calls) or "indirect" (fn pointer).
```

Two traps here. First, calling a `#[target_feature(enable = "avx2")]` function from a non-AVX2 context prevents inlining across that boundary, so a thin wrapper marked `#[inline(always)] #[target_feature(enable = "avx2")]` is the idiom for getting the intrinsics into one big AVX2 region rather than paying a call per operation. Second, the win is often smaller than expected because you are memory-bandwidth-bound, not ALU-bound: vectorising a loop that reads 32 MB from DRAM changes nothing, because the bottleneck was never the arithmetic. Check arithmetic intensity (FLOPs per byte loaded) before investing a week in intrinsics.

### Benchmarking with Criterion, and the benchmark that measured nothing

`#[bench]` from libtest is gone: it was nightly-only for a decade and is now a hard error on stable. Criterion is the default replacement. Current state as of 2026-08-05: Criterion lives at `github.com/criterion-rs/criterion.rs` (the original `bheisler/criterion.rs` repo is unmaintained; the new org has 1,589 commits and 34 releases), latest release **0.8.2 on 2026-02-04**, MSRV policy is the last three stable minors, currently **Rust 1.88 or later** (1.86 believed to still work but unsupported). Maintainers are `@lemmih` and `@berkus`. `black_box` is now in `std::hint::black_box`, stable since Rust 1.66; do not import Criterion's re-export in new code.

What Criterion actually does that a `for` loop with `Instant::now()` does not: 3 seconds of warmup (to let the CPU reach a steady clock and the branch predictors and caches settle), then ~5 seconds collecting **100 samples** at increasing iteration counts, then bootstrap resampling to produce a median with a 95% confidence interval, outlier classification (mild/severe, high/low, by Tukey fences), and automatic comparison against the previous run stored in `target/criterion/` with a change estimate and a p-value. That last part is the actual reason to use it: it turns "is this 3% faster or is my laptop thermally throttling" into a statistical statement.

Minimal setup:

```toml
[dev-dependencies]
criterion = { version = "0.8", features = ["html_reports"] }

[[bench]]
name = "my_benchmark"
harness = false        # <- the most-forgotten line. Without it, libtest
                       #    eats the CLI args and Criterion never runs.
```

Now the important part. Here is a benchmark I actually ran, and its output:

```rust
pub fn sum_to(n: u64) -> u64 { (0..n).fold(0u64, |a, b| a.wrapping_add(b)) }

c.bench_function("sum_to_10M_NO_blackbox",     |b| b.iter(|| sum_to(10_000_000)));
c.bench_function("sum_to_10M_blackbox",        |b| b.iter(|| sum_to(black_box(10_000_000))));
c.bench_function("sum_to_10M_result_dropped",  |b| b.iter(|| { sum_to(black_box(10_000_000)); }));
```

```
sum_to_10M_NO_blackbox      time: [965.77 ps 975.34 ps  987.12 ps]
sum_to_10M_blackbox         time: [953.48 ps 958.84 ps  964.72 ps]
sum_to_10M_result_dropped   time: [950.03 ps 955.54 ps  961.64 ps]
```

**All three ran in under one nanosecond for a ten-million-iteration loop.** At ~3 GHz that is about 3 clock cycles. Criterion reported "Collecting 100 samples in estimated 5.0000 s (5.2B iterations)", and 5.2 billion iterations in 5 seconds is itself the smoking gun. And notice that `black_box` on the input **did not save it**. That is the deeper lesson most write-ups miss: `black_box` on the argument stops constant-folding of the argument, but LLVM recognised `(0..n).fold(+)` as a triangular sum and replaced the entire loop with the closed form `n*(n-1)/2`, which is a handful of instructions regardless of what `n` is.

**How to spot a benchmark that is measuring nothing**, in order of how fast the check is:
- **Sanity-check the number against physics.** A loop over N elements cannot run faster than roughly N/8 cycles even fully vectorised. If N is 10M and the reported time is 1 ns, the work is gone. Criterion's own "estimated 5.0000 s (5.2B iterations)" line tells you the iteration count for free.
- **Scale the input and check the time scales.** Run at N and 2N. If the time does not roughly double for an O(n) function, the optimiser folded it. This is the single most reliable test and it takes 30 seconds.
- **Look at the assembly** with `cargo asm --bench`. An empty loop is unmistakable.
- **Check the noise floor.** Criterion reporting a confidence interval narrower than 1% on a sub-nanosecond measurement means it is measuring its own harness overhead, which on modern hardware is roughly 1-2 ns per iteration.

**Using `black_box` correctly** means blocking the optimiser on *both* ends:

```rust
use std::hint::black_box;
// input: stop constant propagation INTO the function
// output: stop dead-code elimination of the RESULT
b.iter(|| black_box(my_fn(black_box(&input))));
```

And if the function is still foldable (as `sum_to` was), no amount of `black_box` at the call site helps; you have to make the *body* opaque or benchmark something the compiler cannot solve in closed form. `black_box` is documented as a best-effort hint with no formal guarantee, which is worth stating precisely because interviewers like the honesty.

Two more Criterion facts worth having: `b.iter_batched(setup, routine, BatchSize::SmallInput)` runs `setup` outside the timed region, which is how you benchmark a function that mutates its input without timing the clone; and `Throughput::Bytes(n)` on a `BenchmarkGroup` makes Criterion report GiB/s alongside time, which is the only unit that lets you compare against DRAM bandwidth and know whether you are anywhere near the machine's limit.

**Alternatives, honestly.** Divan (`nvzqz/divan`, first released 2023) has a nicer API (`#[divan::bench]` attribute, generic and const-generic benchmarks, `#[divan::bench(args = [...])]`), much faster startup, and built-in allocation counting via a wrapping allocator, which is genuinely something Criterion does not do. It has less statistical machinery and weaker regression comparison. Tango uses paired interleaved sampling to cancel out drift, which is the right technique for detecting sub-1% changes but is a niche tool. If you are gating CI on performance, the honest current answer is that wall-clock benchmarks on shared CI runners have variance well above the effect sizes you care about, and the fix is either instrumented counting (cachegrind-style, which is what CodSpeed does) or running benchmarks on dedicated hardware. Saying "we tried to gate CI on Criterion and the false-positive rate made us turn it off" is a credible, senior-sounding answer.

### Profiling: what to reach for and how to read it

The ordering that matters: **profile before you optimise, and profile the thing that is actually slow**, which for a service is usually not the function someone suspects.

**Step 1. Build with symbols.** A release binary with no debug info produces a flamegraph of hex addresses. Put this in `Cargo.toml`:

```toml
[profile.release]
debug = 1              # line tables; ~free at runtime, bigger binary
# or a dedicated profile so prod binaries stay stripped:
[profile.profiling]
inherits = "release"
debug = true
strip = false
```
Do **not** profile a debug build. It is a different program: no inlining, no vectorisation, every bounds check live. Its profile will send you to the wrong place.

**Step 2. Pick the tool for the question.**

| Question | Tool | Command |
|---|---|---|
| Where is wall time going? | `samply` | `samply record ./target/profiling/app` |
| Same, in a shareable SVG | `cargo-flamegraph` | `cargo flamegraph --bin app` |
| Raw counters: IPC, miss rates, branch misses | `perf stat` | `perf stat -e cycles,instructions,cache-misses,branch-misses ./app` |
| Which cache line are two cores fighting over? | `perf c2c` | `perf c2c record ./app && perf c2c report` |
| Exact instruction counts, deterministic, no noise | `cachegrind` | `valgrind --tool=cachegrind ./app` |
| Who is allocating, and how much? | `dhat` / `heaptrack` | `valgrind --tool=dhat ./app` |
| Where is time going inside `rustc` (build slowness) | `cargo build --timings` | opens an HTML timeline |
| Which generics are bloating the build? | `cargo-llvm-lines` | `cargo llvm-lines --release \| head -30` |

`samply` is the current default recommendation for interactive work: `cargo install --locked samply`, then `samply record ./target/profiling/app`, and it opens the Firefox Profiler UI in a browser with a flamegraph, a call tree, a stack chart over time, and per-thread timelines. It works on Linux and macOS without the `perf` permissions dance, and the time-axis view is the thing raw flamegraphs lack: a flamegraph aggregates the whole run, so a 200 ms stall in one phase is invisible if the run is 20 seconds long.

**Step 3. Read it correctly.** Since you already read flamegraphs, the Rust-specific gotchas are the whole value here:

- **Inlining destroys frames.** A function that was inlined does not appear; its samples are attributed to the caller. If the profile shows a fat `main` or a fat `poll`, that is what happened. The fix is `#[inline(never)]` on the specific functions you want to see, rebuilt just for the profiling run. This is the number one reason people say "Rust flamegraphs are useless".
- **Look for `__rust_alloc`, `__rust_dealloc`, `malloc`, `free`, `memcpy`, `realloc`.** Aggregate them mentally. If they total more than ~15% you are allocation-bound and every other optimisation is premature.
- **`core::ptr::drop_in_place` frames** are destructor time. A wide one usually means you are dropping a large nested structure (a `Vec<HashMap<String, Vec<String>>>` and friends) at a point that shows up on the critical path. The fix is often moving the drop off the hot path (send it to a cleanup thread) rather than making it faster.
- **`panic_bounds_check` / `core::panicking::panic_bounds_check`** appearing at all in a hot path is the direct signal that a bounds check survived and is being executed, not just present.
- **Async runtimes smear everything.** In a Tokio program, samples land under `tokio::runtime::...::poll` and the logical call chain is lost across `.await` points because each poll is a separate stack. `tokio-console` for task-level views and `tracing` spans with `tracing-flame` give you the logical picture that a stack sampler cannot. Say this if asked about profiling an async service; it is the thing that separates people who have done it from people who have read about it.
- **`perf stat` first, always.** IPC below ~1.0 with a large `cache-misses` count means memory-bound, and no amount of instruction-level optimisation will help. IPC above 2.5 with high `branch-misses` means you are branch-bound and want branchless or sorted data. This 10-second check tells you which half of this module to read.
- **Cachegrind gives you deterministic numbers.** It simulates the cache, so it is roughly 50-100x slower than native but has zero run-to-run variance, which makes it the right tool for detecting a 2% regression that wall-clock benchmarking cannot resolve. `cg_annotate` maps the counts back to source lines.

---

## Build it from scratch

The lab in `(lab pending)` should be one crate you can run end to end in about 20 minutes. Everything below was actually compiled and run to produce the numbers in this module, so it is not a sketch unless marked.

```rust
// (lab pending)src/lib.rs
// Step A: two functions that SHOULD compile identically. Verify, don't assume.
#[no_mangle] pub fn sum_loop(v: &[u64]) -> u64 {
    let mut t = 0u64; for i in 0..v.len() { t = t.wrapping_add(v[i]); } t
}
#[no_mangle] pub fn sum_iter(v: &[u64]) -> u64 {
    v.iter().copied().fold(0u64, |a, b| a.wrapping_add(b))
}
// Step B: the same shape in f32. This one does NOT vectorise. Find out why.
#[no_mangle] pub fn sum_f32(v: &[f32]) -> f32 { v.iter().sum() }
// Step C: static vs dynamic dispatch. One of these is two instructions.
pub trait Op { fn apply(&self, x: u64) -> u64; }
pub struct Add1;
impl Op for Add1 { fn apply(&self, x: u64) -> u64 { x + 1 } }
#[no_mangle] pub fn run_static(ops: &[Add1], x: u64) -> u64 {
    ops.iter().fold(x, |a, o| o.apply(a))
}
#[no_mangle] pub fn run_dyn(ops: &[Box<dyn Op>], x: u64) -> u64 {
    ops.iter().fold(x, |a, o| o.apply(a))
}
// Step D: a bounds check that genuinely survives.
#[no_mangle] pub fn gather(src: &[f32], idx: &[usize], out: &mut [f32]) {
    for i in 0..idx.len() { out[i] = src[idx[i]]; }
}
```

The workflow to run against it, in order:

```bash
cargo build --release
# 1. Confirm sum_loop == sum_iter modulo register naming.
objdump -d --no-show-raw-insn target/release/libperflab.rlib \
  | sed -n '/<sum_loop>:/,/^$/p'   > /tmp/a.txt
objdump -d --no-show-raw-insn target/release/libperflab.rlib \
  | sed -n '/<sum_iter>:/,/^$/p'   > /tmp/b.txt
diff /tmp/a.txt /tmp/b.txt        # expect: label names + xor ordering only

# 2. Count vector instructions per function. sum_f32 should be ZERO.
for f in sum_loop sum_iter sum_f32 run_static run_dyn gather; do
  echo "$f: $(objdump -d target/release/libperflab.rlib \
    | sed -n "/<$f>:/,/^\$/p" | grep -cE 'paddq|addps|mulps')"
done

# 3. Prove the SIMD refusal is about FP associativity, not about f32.
RUSTFLAGS="-C target-cpu=native" cargo build --release   # still scalar. still.

# 4. Find the panic edges that block vectorisation.
objdump -d target/release/libperflab.rlib \
  | sed -n '/<gather>:/,/^$/p' | grep -E 'jae|je .*panic|call'

# 5. Measure the monomorphisation tax on your own crate.
cargo llvm-lines --release | head -20
cargo build --timings          # then open target/cargo-timings/*.html
```

The exercise that actually builds the instinct: write `dot_scalar` and `dot_unroll8` (both shown above), benchmark them with Criterion, get the 6.67x, then go read the assembly of both and confirm that the fast one has `mulps`/`addps` and the slow one has `mulss`/`addss`. Then write `dot_unroll4` and `dot_unroll16` and find where the curve turns over, because it will: past the register file width you start spilling accumulators to the stack and the speedup reverses. That single experiment teaches more about LLVM's cost model than any amount of reading.

A second, shorter exercise: take the false-sharing benchmark, run it with 2, 4 and 8 threads, and plot throughput. The packed version's throughput should go *down* as you add threads past 2 while the padded version scales close to linearly until you run out of physical cores. Being able to say "I have watched throughput decrease as I added threads and known immediately to look for false sharing" is a strong interview answer.

---

## How it's done in production

The production version of this is a **performance CI pipeline plus a release profile**, not a person reading assembly. What the tooling adds over the manual workflow is regression detection, which is the only part that scales.

A realistic release profile for a compute-bound service, with the reasoning for each line:

```toml
[profile.release]
opt-level = 3          # 3 is the default; "z"/"s" disable unrolling+vectorisation
lto = "thin"           # good default: most of fat LTO's benefit, ~1/3 the cost
codegen-units = 1      # better optimisation, serialises the backend, slower builds
panic = "abort"        # removes unwind tables, typically 5-10% smaller binary
debug = 1              # line tables so flamegraphs are readable in prod
strip = "debuginfo"    # ship without full DWARF, keep symbol names
incremental = false    # incremental + release is a known deoptimisation

[profile.profiling]
inherits = "release"
debug = true
strip = false
```

`panic = "abort"` deserves a caveat: it makes `catch_unwind` a no-op, so any library relying on it (some test harnesses, some FFI boundaries, Tokio's task-panic isolation) changes behaviour. On a service where a panicking request handler should not kill the process, `panic = "unwind"` is correct and the binary-size saving is not worth it.

For the fleet, set a target-CPU floor in `.cargo/config.toml` rather than `native`:

```toml
[build]
rustflags = ["-C", "target-cpu=x86-64-v3"]   # AVX2/FMA/BMI2; Haswell 2013+, Zen 1+
```

Verify against your actual instance families first. On AWS, `x86-64-v3` covers everything from c5/m5 onward but excludes some older burstable families, and Graviton is a different target entirely (`-C target-cpu=neoverse-n1` or `neoverse-v1`). A `SIGILL` at startup on 3% of your fleet is the failure mode, and it is silent until it isn't.

The CI shape that actually works: run Criterion benchmarks on a **dedicated, pinned, non-shared** runner with turbo/boost disabled and the CPU governor set to `performance`, store `target/criterion/` as an artifact, and alert on regressions above a threshold you derived from measured run-to-run variance (usually 5-10% on real hardware, which means you cannot catch a 2% regression this way). If you need 2% resolution, switch to instrumented counting: cachegrind instruction counts, or CodSpeed, which does exactly this and has zero variance at the cost of not measuring cache effects faithfully.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Benchmark reports sub-nanosecond time for an O(n) function with n in the millions; Criterion says "5.2B iterations" | Optimiser deleted the work. `black_box` on the argument does not stop LLVM finding a closed form for the whole body | Scale the input and confirm the time scales; make the body genuinely opaque; `black_box` the *result* as well as the input; read the assembly of the bench binary |
| Rewrote a `for` loop as an iterator chain, expected a speedup, got none | The claim was correct: they already compiled to the same code (34 vs 35 instructions in my test). You optimised something that was not the bottleneck | `perf stat` for IPC and cache-miss rate before touching code; the bottleneck is elsewhere |
| Hot loop over `Vec<Box<dyn Trait>>` will not vectorise and shows `call *0x18(%rcx)` in `perf annotate` | `dyn` dispatch is an inlining barrier; nothing downstream can be constant-folded or vectorised | Enum dispatch (`enum Op { A(A), B(B) }` + `match`) if the set is closed; generics + monomorphisation if it is open at compile time; batch by concrete type so each inner loop is monomorphic |
| `f32`/`f64` reduction stays scalar even with `-C target-cpu=native` on an AVX2 machine; assembly shows 8x-unrolled `addss` into one register | IEEE-754 addition is non-associative; LLVM will not reorder and change your results | Split into 4/8/16 independent accumulators manually (measured 6.67x). Accept and document that last-bit results change. Do not reach for nightly fast-math intrinsics in production code |
| `panic_bounds_check` visible in the flamegraph inside a hot loop | Index is data-dependent (`src[idx[i]]`) or lengths are independent facts LLVM cannot relate | Restructure to iterators/`zip`/`chunks_exact`; slice once up front to unify the lengths; only then consider `get_unchecked` with a `// SAFETY:` proof |
| Adding threads *decreases* throughput; `perf stat` shows huge `cache-misses` on a tiny working set | False sharing: independent counters or per-thread state sharing a 64-byte cache line (measured 3.68x penalty) | `#[repr(align(64))]` or `crossbeam_utils::CachePadded`; confirm with `perf c2c` HITM events. Pad to 128 bytes on aarch64/Apple silicon |
| Flamegraph is a single enormous `main` or `poll` frame with no detail | Everything got inlined, so frames were attributed to the caller; or you profiled a stripped binary | `debug = 1` in the release profile; add `#[inline(never)]` temporarily to the functions you want to see; for async use `tokio-console` and `tracing-flame` instead of a stack sampler |
| p99 latency has a periodic spike with no GC in the language | Bulk `drop_in_place` of a large nested structure on the request path, or an allocator returning memory to the OS (`madvise`) | Look for wide `drop_in_place` frames; move the drop off the critical path; try `mimalloc`/`jemallocator` as the global allocator |
| Build takes 4 minutes for 50 KLOC; `cargo build --timings` shows one crate dominating | Monomorphisation blowup: a large generic body instantiated over many types (measured 3.17x compile time, 1.28x binary for 200 instantiations of one small fn) | `cargo llvm-lines --release \| head -30` to rank offenders; refactor to a thin generic wrapper over a non-generic inner fn taking `&dyn`/`&Path`/`&[u8]` |
| Binary is 40 MB and the container image is slow to pull | No LTO, 16 codegen units, full debug info, unwind tables, monomorphised duplicates | `lto = "fat"` + `codegen-units = 1` cut a test binary 49.8% (4,426,416 to 2,221,304 B) at 17.7x build time; add `strip = "debuginfo"` and `panic = "abort"` if acceptable |
| `SIGILL` / "illegal instruction" on some fleet hosts, works locally | Built with `-C target-cpu=native` on a newer CPU than some deployment targets | Pin a floor (`x86-64-v2` or `v3`) and use `is_x86_feature_detected!` runtime dispatch for anything above it |
| CPU is at 100% and `perf stat` shows IPC of 0.4 | Memory-bound. Vectorising and micro-optimising will do nothing | Fix data layout (AoS to SoA gave 3.06x here), shrink your working set, improve locality, reduce pointer chasing |
| Service allocates 200k times per request; `__rust_alloc` is 30% of the flamegraph | `String`/`Vec` created per item where a borrow would do (measured 57x for `String` clone vs `&str` len) | Take `&str`/`&[T]` in signatures, `Cow<'_, str>` for the sometimes-modify case, reuse buffers with `clear()`, `with_capacity` at the boundaries |
| Criterion says "performance has regressed" on 30% of CI runs with no code change | Shared CI runner: noisy neighbours, frequency scaling, thermal throttling. Wall-clock variance exceeds the effect size | Dedicated pinned runner with boost disabled and `performance` governor, or switch to instrumented instruction counting (cachegrind/CodSpeed) for CI gating |

---

## Tradeoffs & when NOT to use it

- **Do not optimise before you have a profile and a target number.** The most common expensive mistake in this whole area is spending a week on SIMD for a service whose flamegraph is 40% `serde_json` and 25% allocator. Every technique in this module has a precondition, and "I measured and it was X% of the profile" is the precondition. The corollary: if you cannot state what fraction of latency the code you are about to optimise represents, you are not ready to optimise it.

- **`#[inline(always)]` is almost always the wrong tool.** It overrides a cost model that has been tuned against enormous corpora. Applied to a non-trivial function it inflates code size, evicts other code from the ~32 KB L1 instruction cache, and can measure slower than the call it removed. The legitimate uses are narrow: `#[target_feature]` wrappers, and functions genuinely smaller than their call sequence. If you are adding it speculatively, you are guessing.

- **Do not reach for `unsafe` `get_unchecked` to remove bounds checks without measuring the check first.** In my tests LLVM hoisted or eliminated the check in every case *except* data-dependent indexing, and the iterator form beat the manual-index form anyway (37 vs 63 instructions, 0 vs 2 panic edges). You are trading a memory-safety guarantee for a benefit that frequently rounds to zero. When it genuinely is the bottleneck, `get_unchecked` is correct and you should use it, with a `// SAFETY:` comment that states the invariant and why it holds.

- **SoA is not universally better than AoS.** It won 3.06x here because the loop touched 1 field out of 8. Flip the access pattern to "process one particle completely" and SoA loses: you now have 8 independent memory streams, 8 TLB entries in flight, and worse locality than the single 32-byte struct that fit inside half a cache line. SoA also makes the code substantially harder to read and makes "add a field" a refactor. Hot/cold splitting is usually the better cost/benefit point.

- **`SmallVec` is a pessimisation at the wrong N.** `SmallVec<[T; 32]>` where `T` is 16 bytes makes the type 512+ bytes, so every move is a 512-byte `memcpy`, passing it by value is expensive, and storing a million of them wastes hundreds of megabytes when the median length is 2. Pick N from the measured p95 of your length distribution, check `size_of`, and be willing to conclude that a plain `Vec` was fine.

- **Do not enable `lto = "fat"` and `codegen-units = 1` on a crate your team iterates on daily.** In my test that combination took the build from 0.14 s to 2.48 s (17.7x) for a 3.6% runtime difference that was within noise. It is a release-build setting, and if CI build time is on your critical path, `lto = "thin"` gets most of the size benefit for a fraction of the cost. Developer iteration speed is a real, measurable cost that performance work routinely externalises.

- **Do not gate CI on wall-clock microbenchmarks on shared runners.** The false-positive rate will exceed the true-positive rate and the team will start ignoring the alert, which is worse than not having it. Either buy dedicated hardware or move to instrumented counting.

- **Do not reach for `std::simd` in production code today.** It is nightly-only as of rustc 1.97.1 (tracking issue #86656) and pinning your whole service to nightly to get it is a large, ongoing tax on every dependency upgrade for a benefit you can usually get from restructuring the loop so autovectorisation fires. If you genuinely need explicit vectors on stable, `wide` or `std::arch` with runtime dispatch is the deployable answer.

- **`-C target-cpu=native` should never appear in a build that ships.** It is correct for a benchmark on the machine you are benchmarking and it is a latent `SIGILL` in a container image. Related: benchmark numbers taken with `native` are not the numbers your production binary will hit, which is a common and embarrassing gap between a "measured 4x speedup" claim and a deployment that changes nothing.

- **When the language is not the bottleneck, none of this matters.** If your service is 90% waiting on a vector database, an LLM inference endpoint, or S3, then the Rust-level constant factor is rounding error and the right work is batching, caching, concurrency and connection pooling. The senior failure mode here is applying systems-programming instincts to an I/O-bound problem because that is the skill you enjoy using.

---

## Interview questions

### Q1 — What does "zero-cost abstraction" actually mean, and how would you verify the claim for a specific piece of code?
**Testing:** whether you treat it as a falsifiable engineering claim or a marketing slogan.
**Answer:** It means the abstraction costs nothing beyond what the hand-written equivalent with the same semantics would cost, and that you do not pay for abstractions you do not use. It is verified by reading the generated assembly, not assumed. Concretely: compile with `--release` (not debug, where nothing is inlined), then `cargo asm --lib 'crate::func' --rust`, Compiler Explorer for a snippet, or `objdump -d` on the rlib, and diff the abstraction against the manual version. I did this for `v.iter().copied().fold(0, wrapping_add)` versus `for i in 0..v.len() { t += v[i] }` on rustc 1.97.1 and got 34 versus 35 instructions with the identical SSE2 `paddq` core, 2x unrolled at 4 `u64` per iteration; the only diff was label names and the order of two register-zeroing `xor`s. The mechanism is monomorphisation plus inlining: `fold` with a concrete closure type becomes a struct with a call method, gets inlined, and the loop that remains is the same loop.
**Follow-up trap:** *"So iterator chains are always as fast as loops?"* No, and the reverse is also false. My `zip` test had the iterator version at 37 instructions with zero panic edges versus 63 instructions with two panic call sites for the hand-written index loop, so the iterator was strictly *better*. And in the other direction, an iterator over `Box<dyn Fn>` cannot be inlined at all. The honest statement is "the abstraction is not inherently costly, and which one wins depends on whether the compiler can prove the same facts in both versions; check, don't assume in either direction."

### Q2 — Show me a case where the zero-cost claim breaks down.
**Testing:** whether you have actually looked, or are reciting the happy path.
**Answer:** Four, in the order I would check them. First, `dyn Trait`: `ops.iter().fold(x, |a, o| o.apply(a))` over `&[Add1]` compiled to two instructions total (`lea (%rsi,%rdx,1),%rax; ret`) because LLVM proved the loop was `x + len`, while the identical code over `&[Box<dyn Op>]` was a 24-instruction loop with `call *0x18(%rcx)` per element. The cost is not the indirect call, it is the optimisation barrier. Second, floating-point reductions: `v.iter().sum::<f32>()` compiled to an 8x-unrolled chain of scalar `addss` into a single accumulator with zero packed instructions, even with `-C target-cpu=native` on an AVX2+FMA machine, because IEEE addition is non-associative. Third, data-dependent indexing: `out[i] = src[idx[i]]` kept two live bounds checks per iteration and did not vectorise. Fourth, cross-crate calls to large functions, though this is now weaker than the folklore because rustc's MIR inliner handles a lot of it without `#[inline]` or LTO.
**Follow-up trap:** *"Which of those would you actually fix, and how?"* The `dyn` one, by enum dispatch if the type set is closed or by batching work per concrete type so each inner loop is monomorphic. The FP one, by manually splitting into 8 accumulators, which I measured at 6.67x (1.9323 µs to 289.69 ns on 4096 elements), while being explicit that it changes last-bit results and is therefore not acceptable if the output must be bit-reproducible. The others usually are not worth fixing, and saying so is the point.

### Q3 — Rust has bounds checks on every slice index. What does that actually cost?
**Testing:** whether you know that "eliminated" and "5% overhead" are both wrong as blanket claims.
**Answer:** It depends entirely on whether LLVM can prove the index is in range, and the outcome is bimodal rather than a uniform tax. Indexing with `i` from `0..v.len()` costs zero, the check is not emitted. Indexing with an unrelated `n` got the check *hoisted* out of the loop by LLVM: one `cmp; jbe` before the loop testing `n-1 < len`, then a fully vectorised body, which is why the common "add `assert!(n <= v.len())`" trick often measures as no change. Where it genuinely survives is data-dependent indexing: `out[i] = src[idx[i]]` kept two checks in the loop body and blocked vectorisation entirely, and the iterator equivalent ran 4.0x faster on sequential data (0.179 ms vs 0.714 ms over 1M elements) and 10.6x faster than the random-index version.
**Follow-up trap:** *"So should you use `get_unchecked` in hot loops?"* Only after the profile shows `panic_bounds_check` executing there, which in my experience is rare. The first three fixes are all safe: use iterators (`zip`, `chunks_exact`, `windows`), slice once up front so the lengths become one fact instead of three, and use `chunks_exact(8)` to give LLVM a compile-time-known inner trip count. If you do use `get_unchecked`, it needs a `// SAFETY:` comment stating the invariant and why it holds, and a debug assertion is cheap insurance.

### Q4 — Walk me through the cost of monomorphisation.
**Testing:** whether you know generics are not free, with numbers.
**Answer:** Every distinct type argument produces a distinct copy of the function's machine code. That is exactly what enables the inlining and constant folding that makes generics fast, and it is paid for in compile time, binary size and instruction-cache pressure. I measured it: one small generic function instantiated over 200 concrete types versus the same function taking `&[&dyn Shape]` once. Clean release rebuild 536 ms versus 169 ms (3.17x), rlib 494,904 versus 387,256 bytes (+107,648 B, 1.28x), LLVM IR 10,847 versus 5,690 lines (1.91x). Scale that to a real service pulling in `serde`, `tokio` and derive-heavy crates and it is the dominant reason Rust builds are slow, not the borrow checker, which is typically single-digit percent (check with `cargo build --timings`).
**Follow-up trap:** *"How would you find and fix the worst offender in a real codebase?"* `cargo llvm-lines --release | head -30` ranks functions by LLVM IR lines generated, which correlates almost exactly with compile-time and binary-size contribution. The fix is the thin generic wrapper: keep the type-parameterised surface one line long and push the body into a non-generic inner function taking `&Path`, `&[u8]` or `&dyn Trait`. `fn load<P: AsRef<Path>>(p: P) { load_inner(p.as_ref()) }` duplicates one line per `P` instead of two hundred.

### Q5 — When does `#[inline]` actually matter, and what does LTO add on top?
**Testing:** whether you know the current behaviour or the 2018 folklore.
**Answer:** Within a crate, `#[inline]` is a hint you rarely need; LLVM's cost model is good. Its real function is to export the MIR so downstream crates *can* inline it. The classic rule was that a non-generic cross-crate function without `#[inline]` cannot be inlined without LTO, and that rule is now only partly true: rustc's MIR inliner does cross-crate inlining of small-to-medium functions on stable regardless. I tested it with a two-crate workspace, no `#[inline]`, `lto = false`, and got zero `call` instructions to the dependency's function in the consumer binary, and it still inlined when I made the function genuinely bulky. What LTO reliably bought in that test was **size**: 4,426,416 down to 2,221,304 bytes, a 49.8% reduction, at 0.14 s to 2.48 s build time (17.7x), with a 3.6% runtime difference that was within noise.
**Follow-up trap:** *"Then when would you turn LTO on?"* When binary size or container pull time matters, when you have genuinely large hot functions crossing crate boundaries that the MIR inliner declined, or when you need cross-crate devirtualisation. Not by default on a crate the team iterates on daily, because a 17.7x build-time increase is a real productivity cost. `lto = "thin"` is the reasonable middle. And note `#[inline(always)]` is a different question and almost always wrong: it overrides the cost model, inflates code size, and evicts other code from the ~32 KB L1 instruction cache.

### Q6 — I wrote a Criterion benchmark and it says my function takes 900 picoseconds. What do you think?
**Testing:** the single highest-signal question in this area. Does the candidate immediately smell a dead benchmark?
**Answer:** I think the optimiser deleted the work. 900 ps is under three clock cycles at 3 GHz, which cannot be a function doing meaningful work. I hit this exact case: `(0..n).fold(0u64, wrapping_add)` with `n = 10_000_000` benchmarked at 975.34 ps, and critically it was still 958.84 ps *with* `black_box` on the input, because LLVM recognised the triangular sum and replaced the loop with the closed form. Criterion's own output gives it away: "Collecting 100 samples in estimated 5.0000 s (5.2B iterations)". Five billion iterations in five seconds is not a real workload.
**Follow-up trap:** *"How do you prove it, and how do you fix it?"* Prove it by scaling: run at N and 2N and check the time roughly doubles for an O(n) function. That is a 30-second test and it is more reliable than reading assembly. If it does not scale, look at the bench binary's assembly with `cargo asm --bench`. Fix it by `black_box`-ing both the input and the *result* (`black_box(f(black_box(&input)))`), and if the body is still analytically foldable, by benchmarking something the compiler cannot solve in closed form. Also worth stating: `black_box` is documented as best-effort with no formal guarantee, so it is a tool, not a proof.

### Q7 — Why does `v.iter().sum::<f32>()` not vectorise when `v.iter().sum::<i32>()` does?
**Testing:** whether the candidate understands the numerics, not just "SIMD sometimes doesn't happen".
**Answer:** IEEE-754 floating-point addition is not associative: `(a+b)+c` and `a+(b+c)` can differ in the last bits when magnitudes differ. Vectorising a reduction means splitting one serial sum into 4 or 8 partial sums and combining them at the end, which is exactly a reassociation, so LLVM refuses because it would change your program's output. Integer wrapping addition *is* associative, so the same reduction over `i32` vectorised cleanly with 8 `ymm` registers under `-C target-cpu=native`. I confirmed both on the same build: `sum_f32` was 39 instructions of 8x-unrolled scalar `addss` all accumulating into `%xmm0`, so the unroll bought nothing because every add depended on the previous one at roughly 4 cycles of latency.
**Follow-up trap:** *"So how do you get the speedup anyway?"* Split the accumulator yourself: 8 independent partial sums in a `[f32; 8]`, combined at the end. That is you choosing to reassociate, explicitly and visibly, and I measured 6.67x for it. C would let you do the same with `-ffast-math`, and Rust deliberately has no stable equivalent because a global flag that silently changes numerics across an entire binary is a footgun. The thing to say out loud is that this is a *correctness* change: if the result feeds a financial aggregate or must be bit-reproducible across machines or across different lane counts, you cannot do it.

### Q8 — A service's CPU is pinned at 100%. Walk me through your first 15 minutes.
**Testing:** profiling discipline and ordering. Rust-specific knowledge is secondary here to not guessing.
**Answer:** First `perf stat -e cycles,instructions,cache-misses,branch-misses` for 30 seconds on the live process. IPC below ~1.0 with high cache misses means memory-bound, and I stop thinking about instruction-level optimisation entirely. IPC above ~2.5 with high branch misses means branch-bound. That one number decides the next hour. Then a sampling profile: `samply record -p <pid>`, which gives me a flamegraph plus a time axis, the latter mattering because an aggregate flamegraph hides a 200 ms stall in a 20 second run. Reading it, I aggregate `__rust_alloc`/`__rust_dealloc`/`malloc`/`free`/`memcpy` first, because if that totals more than ~15% the answer is allocation and everything else is premature. I look for wide `drop_in_place` frames (bulk destruction on the request path) and for `panic_bounds_check` appearing at all.
**Follow-up trap:** *"The flamegraph is one giant `main` frame with no detail. Now what?"* That is inlining, or a stripped binary. Two fixes: set `debug = 1` in the release profile so line tables exist (nearly free at runtime), and temporarily add `#[inline(never)]` to the handful of functions I want as distinct frames and rebuild just for the profiling run. If it is an async service, a stack sampler is the wrong tool at all: everything lands under `tokio::runtime::...::poll` and the logical call chain is lost across `.await` points, so I want `tokio-console` for task-level state and `tracing` spans with `tracing-flame` for the logical picture.

### Q9 — Throughput went DOWN when we added threads. The threads share nothing. What is happening?
**Testing:** whether false sharing is in the candidate's vocabulary as a first hypothesis, not a trivia answer.
**Answer:** Almost certainly false sharing. Cache coherence operates on 64-byte lines, not on variables, so four `AtomicU64` counters that are logically independent but physically adjacent all live on one line, and every core's write invalidates that line in the other three cores' L1 caches. Each increment becomes a coherence transaction instead of an L1 hit. I measured it directly: four threads doing 50,000,000 relaxed `fetch_add` each on packed `AtomicU64`s took 1768.298 ms; the same code with `#[repr(align(64))]` around each counter took 481.023 ms. **3.68x**, from one attribute. Nothing in the source suggests a dependency. `perf c2c record` and `perf c2c report` confirm it directly by reporting HITM events and naming the cache line and the two instructions contending.
**Follow-up trap:** *"Is 64 bytes always the right padding?"* No. aarch64 and Apple silicon have 128-byte lines at some cache levels, and Intel's adjacent-line prefetcher can effectively make the contended unit 128 bytes on x86 too. That is why `crossbeam_utils::CachePadded` pads to 128 on those targets rather than 64, and why hand-rolling `#[repr(align(64))]` is the portable-looking answer that is subtly wrong on ARM. Also worth noting the cost: padding four counters to 64 bytes each turns 32 bytes of state into 256 bytes, so this is a bad idea for anything you have millions of.

### Q10 — Explain array-of-structs versus struct-of-arrays with a number, and tell me when SoA is the wrong choice.
**Testing:** data layout as a first-class optimisation, plus the discipline to name the counter-case.
**Answer:** Given a 32-byte `Particle` with 8 `f32` fields and 1,000,000 of them, summing just `p.x`: AoS forces the CPU to pull all 32,000,000 bytes because it fetches whole 64-byte lines and you use 4 bytes of every 32; SoA over a `Vec<f32>` of just `x` touches 4,000,000 bytes. Measured: 1.394 ms versus 0.456 ms, **3.06x**. It is not the full 8x because at 32 MB you are DRAM-bandwidth-bound and the hardware prefetcher does well on both, so the speedup is sublinear in the traffic reduction. SoA also unlocks vectorisation that AoS blocks, because the `x` values are now contiguous rather than strided.
**Follow-up trap:** *"When is AoS better?"* When the hot loop touches all or most fields of one object at a time, which is most business logic. SoA then means 8 independent memory streams competing for prefetcher slots and TLB entries, and worse locality than a 32-byte struct that fits inside half a cache line. It also makes the code harder to read and turns "add a field" into a refactor. The pragmatic middle is hot/cold splitting: the 3 fields the hot loop reads in one struct, the other 20 behind a `Box`. And I would add that Rust's default `repr(Rust)` already reorders fields by alignment to minimise padding, so `struct S { a: u8, b: u64, c: u8 }` is 16 bytes in Rust and 24 in C, and you lose that the moment you add `#[repr(C)]`.

### Q11 — Is `Vec::with_capacity` always worth it?
**Testing:** whether the candidate parrots advice or has measured it.
**Answer:** No, and the shape of the answer is more useful than the yes/no. Over 1,000,000 `u64` pushes, `Vec::new()` and `Vec::with_capacity(1_000_000)` were 0.677 ms and 0.674 ms, indistinguishable, because growth is amortised doubling (about 20 reallocations total) and glibc's `realloc` often extends large mappings in place rather than copying. Over 200,000 `String` pushes it was 10.491 ms versus 6.619 ms, a real **1.58x**, because each realloc must move 24-byte `String` headers and the heap is already fragmented by 200k separate string allocations so in-place extension fails. The rule is that pre-allocation matters in proportion to how expensive the element move is and how fragmented the heap already is.
**Follow-up trap:** *"What beats both?"* `collect()`. `(0..1_000_000).collect::<Vec<u64>>()` took 0.203 ms, **3.33x faster than either push loop**, because it uses `Iterator::size_hint` to allocate exactly once and then writes through a raw pointer with no per-push capacity check. So the actual advice is "prefer `collect` from an exact-size iterator, use `with_capacity` when you must push in a loop and the element is non-trivial, and don't bother for scalars into a fresh `Vec`". For `HashMap` the calculus is different and `with_capacity` matters more, because growth means rehashing every key rather than a `memcpy`.

### Q12 — What is the status of `std::simd`, and what would you ship on stable today?
**Testing:** version discipline. This is a question people confidently get wrong from memory.
**Answer:** As of rustc 1.97.1 (2026-07-14), `std::simd` is **still nightly-only**, gated behind `#![feature(portable_simd)]`, tracking issue rust-lang/rust#86656. It provides `Simd<T, N>` for lane counts 1 through 64, `Mask<T, N>`, `simd_swizzle!`, and now includes `f16xN` types; operations lower to the best instruction available on the target and degrade to scalar code where there is no SIMD, rather than failing to compile. It has been close to stabilisation for several years, which is exactly why I would not claim it is stable. On stable today I would first try to make autovectorisation fire (`chunks_exact(8)`, iterators, splitting FP accumulators), then reach for the `wide` crate for portable vector types, and only then hand-write `std::arch` intrinsics.
**Follow-up trap:** *"How do you ship AVX2 code to a fleet where some hosts don't have AVX2?"* Not with `-C target-cpu=native`, which produces a binary that `SIGILL`s on any host missing an instruction it used. Set a floor in `.cargo/config.toml` (`x86-64-v2` for SSE4.2, `x86-64-v3` for AVX2/FMA/BMI2, which covers Haswell 2013+ and Zen 1+, but verify against your actual instance families), then use `#[target_feature(enable = "avx2")] unsafe fn` guarded by `is_x86_feature_detected!("avx2")` for anything above the floor. Resolve the dispatch once into a function pointer in a `OnceLock` rather than checking inside the hot loop, and remember that calling into a `#[target_feature]` function from a non-AVX2 context blocks inlining across that boundary, so the idiom is one big `#[inline(always)] #[target_feature]` region rather than per-operation calls.

### Q13 — Criterion or Divan? And would you gate CI on benchmark results?
**Testing:** current ecosystem awareness plus judgement about what actually works in CI.
**Answer:** Criterion is the default and what I would reach for. Current state: it moved to the `criterion-rs` GitHub org because the original `bheisler` repo went unmaintained, latest release 0.8.2 on 2026-02-04, MSRV is the last three stable minors which is currently Rust 1.88. It gives 3 s warmup, 100 samples over ~5 s, bootstrap confidence intervals, Tukey outlier classification, and automatic comparison against the stored previous run in `target/criterion/`. Divan is genuinely nicer to use (attribute macros, generic and const-generic benchmarks, much faster startup) and has built-in allocation counting, which Criterion does not; it has weaker statistics and regression comparison. `#[bench]` from libtest is gone, so those are the two real options. And `harness = false` in `[[bench]]` is the line everyone forgets, without which libtest eats the CLI args and Criterion never runs.
**Follow-up trap:** *"Would you fail a PR on a 3% Criterion regression?"* Not on a shared CI runner. Noisy neighbours, frequency scaling and thermal throttling produce wall-clock variance of 5-10% on typical cloud CI, which is larger than the effect size, so the false-positive rate exceeds the true-positive rate and the team learns to ignore the alert, which is worse than no alert. Either run on dedicated pinned hardware with boost disabled and the `performance` governor, or switch to instrumented counting: cachegrind instruction counts are deterministic with zero run-to-run variance (at 50-100x slowdown), which is the technique CodSpeed productised. The honest sentence to say is "we tried wall-clock gating, the false-positive rate made us turn it off, and we moved to instruction counting for the CI signal and wall-clock for the release check."

### Q14 — You have a hot loop dispatching over a trait. The set of implementations is known at compile time but the elements are heterogeneous. What do you do?
**Testing:** staff-level judgement about the static/dynamic dispatch tradeoff with a concrete third option.
**Answer:** Three options, and I would pick based on the shape. Generics plus monomorphisation give the best code (my `run_static` collapsed a whole fold to two instructions) but require a single concrete type per call site, which heterogeneous elements do not satisfy. `Box<dyn Trait>` handles heterogeneity but erects an inlining barrier: 24 instructions with `call *0x18(%rcx)` per element, no constant folding, no vectorisation, plus 16 bytes per element for the fat pointer *and* a separate heap allocation per element with no locality between them. The third option, and usually the right one here, is **enum dispatch**: `enum Op { A(A), B(B), C(C) }` with a `match` in the method. That is a jump table or a few compares instead of an indirect call, the payloads are stored inline so a `Vec<Op>` is contiguous with no per-element allocation, and LLVM can inline into each match arm. The `enum_dispatch` crate generates this from a trait automatically.
**Follow-up trap:** *"What's the cost of enum dispatch?"* Two real ones. Every `Op` is as large as the largest variant plus a discriminant, so one 200-byte variant among five 8-byte variants wastes 192 bytes on every element, and the fix is boxing just the fat variant. And the enum is closed: downstream crates cannot add implementations, which is exactly the extensibility that `dyn Trait` exists to provide. If you are writing a plugin interface, `dyn` is correct and the dispatch cost is the price of the design. The other structural fix worth naming is **batching by concrete type**: sort or partition the work so each inner loop is monomorphic, which recovers full inlining and vectorisation and is usually a bigger win than the dispatch mechanism itself.

### Q15 — A colleague says "we should rewrite this Python service in Rust, it'll be 100x faster." How do you respond?
**Testing:** whether the candidate can apply all of the above to a business decision instead of a microbenchmark.
**Answer:** I would ask what fraction of latency is actually CPU in Python. If the service is 90% waiting on a vector store, an LLM endpoint or S3, the language constant factor is rounding error and the right work is batching, caching and connection pooling, which is far cheaper than a rewrite. If it *is* CPU-bound, I would want to know whether the CPU is in Python bytecode or already in C extensions, because NumPy and PyArrow paths are already vectorised C and Rust will win maybe 1-2x there, not 100x. Where the 10-100x claims are real is Python-level loops over Python objects, per-object allocation and refcounting, and GIL-serialised multithreading. The pragmatic middle is a PyO3 extension for the hot kernel rather than a full rewrite: you keep the Python surface and the team's velocity, and you get the constant factor where it matters.
**Follow-up trap:** *"Say we do it and it's only 3x. What went wrong?"* Most likely one of: the workload was I/O-bound and we measured the wrong thing; the Rust version allocates as much as the Python one did because someone wrote it with `String` and `.clone()` everywhere (I measured 57x between `String` clone and `&str` borrow on the same workload); the hot loop is behind `dyn Trait` and never inlined; we shipped with `opt-level` defaults and no LTO; or we are memory-bandwidth-bound and no language changes that. The diagnostic order is the same as always: `perf stat` for IPC, then a flamegraph, then check the allocator fraction. If IPC is 0.4 the answer was never the language.

---

## Red flags that fail you

- Saying "zero-cost abstraction" without being able to describe how you would verify it for a specific function, or claiming iterators are "always" as fast as loops in either direction.
- Benchmarking a debug build, or not knowing that `--release` is a materially different program (no inlining, no vectorisation, every bounds check live).
- Reporting a sub-nanosecond benchmark result for a loop over millions of elements without noticing that it is physically impossible.
- Believing `black_box` on the input is sufficient. It stops constant propagation into the function; it does not stop LLVM finding a closed form for the body, which is exactly what happened in my 955-picosecond measurement.
- Reaching for `#[inline(always)]` or `unsafe { get_unchecked }` before showing a profile that says those are the bottleneck.
- Claiming bounds checks cost a fixed percentage. The outcome is bimodal: usually eliminated or hoisted entirely, occasionally fully present and blocking vectorisation.
- Not knowing why `f32` reductions do not autovectorise, or proposing "just enable fast-math" as if stable Rust had it.
- Asserting `std::simd` is stable. It is nightly-only as of rustc 1.97.1, tracking issue #86656.
- Shipping `-C target-cpu=native` to a fleet, or quoting benchmark numbers taken with `native` as if they predict production.
- Being unable to name false sharing when told throughput dropped as threads were added.
- Optimising the abstraction when the flamegraph shows 30% in the allocator, or optimising anything at all in a service that is 90% blocked on I/O.
- Not knowing the cache line is 64 bytes, or not connecting that one number to AoS/SoA, false sharing, and padding.

## Cheat card

```
VERIFY, DON'T BELIEVE: cargo asm --lib 'crate::f' --rust | godbolt | objdump -d.
  ALWAYS --release. Debug build = no inlining, no vectorisation, all checks live.

MEASURED (rustc 1.97.1, x86-64, i5-12450H, opt-level=3):
  sum_loop 34 instrs vs sum_iter 35 -> identical paddq core, 4 u64/iter
  fold over &[Add1]  -> 2 instrs: `lea (%rsi,%rdx,1),%rax; ret`
  fold over &[Box<dyn Op>] -> 24 instrs, `call *0x18(%rcx)` per element
  iterator zip 37 instrs / 0 panic edges  vs  index loop 63 / 2 panic edges

ZERO-COST DIES AT: dyn Trait (inlining barrier) | FP reductions (IEEE
  non-associative) | data-dependent index a[idx[i]] (2 live bounds checks,
  no vectorisation) | large cross-crate fn w/o #[inline] and w/o LTO.

MONOMORPHISATION TAX (200 instantiations of 1 small generic fn vs dyn):
  compile 536 ms vs 169 ms (3.17x) | rlib 494,904 vs 387,256 B (1.28x)
  LLVM IR 10,847 vs 5,690 lines (1.91x).  Find it: cargo llvm-lines --release
  Fix: thin generic wrapper -> non-generic inner fn taking &Path/&[u8]/&dyn.

INLINE: #[inline] = hint + exports MIR cross-crate. #[inline(always)] almost
  always wrong (blows ~32KB L1i). #[inline(never)] = PROFILING TOOL, makes a
  frame visible in a flamegraph. Generics inline cross-crate for free.
  MIR inliner now does cross-crate inlining WITHOUT #[inline] or LTO.
  LTO fat + cgu=1: binary 4,426,416 -> 2,221,304 B (-49.8%), build 0.14 -> 2.48 s
  (17.7x), runtime delta 3.6% = noise. LTO is a SIZE tool first.

ALLOCATION (the real culprit):
  String clone vs &str len, 200k items: 3.899 ms vs 0.068 ms  = 57x
  Vec<u64> 1M push vs with_capacity: 0.677 vs 0.674 ms = NO WIN
  Vec<String> 200k  push vs with_capacity: 10.491 vs 6.619 ms = 1.58x
  collect() (size_hint, 1 alloc): 0.203 ms = 3.33x vs push loop
  Toolkit: &str/&[T] in signatures > Cow > with_capacity > SmallVec<[T;N]>
  (N = measured p95, check size_of!) > arena/bumpalo > mimalloc global alloc.

CACHE LINE = 64 B (128 on aarch64/Apple). Everything follows from this.
  stride 1B 0.36 ns/touch -> 64B 3.22 ns -> 256B 6.63 ns (knee AT 64)
  AoS vs SoA, 1M x 32-B Particle, sum 1 field: 1.394 vs 0.456 ms = 3.06x
    (32 MB vs 4 MB touched; sublinear because DRAM-bandwidth-bound)
    SoA WRONG when the loop touches all fields of one object.
  FALSE SHARING 4 threads x 50M fetch_add: packed 1768 ms vs
    #[repr(align(64))] 481 ms = 3.68x.  Diagnose: perf c2c (HITM).
  size_of: Vec/String 24 B | &[T] 16 | &dyn 16 | Option<&T> 8 (niche)
  repr(Rust) reorders fields by alignment; repr(C) gives that up.

SIMD: std::simd STILL NIGHTLY (rustc 1.97.1, #86656, Simd<T,N> N=1..64, f16xN).
  Stable: autovectorise first, then `wide`, then std::arch intrinsics.
  LLVM gives up on: FP reductions, possible aliasing, panic edges in the loop,
  gathers, loop-carried deps, unknown/tiny trip counts.
  f32 dot 4096: scalar 1.9323 us -> 8 manual accumulators 289.69 ns = 6.67x
    (this CHANGES last-bit results; not OK if bit-reproducible is required)
  Ship: -C target-cpu=x86-64-v3 floor + is_x86_feature_detected! dispatch,
  resolved ONCE into a OnceLock<fn>. NEVER target-cpu=native in a shipped build.

CRITERION 0.8.2 (2026-02-04, org = criterion-rs, MSRV 1.88). harness = false!
  3 s warmup, 100 samples over ~5 s, bootstrap CI, Tukey outliers, auto-compare.
  black_box is std::hint::black_box (stable since 1.66).
  DEAD BENCHMARK TELL: 10M-iter loop measured 975 ps EVEN WITH black_box on
  the input (LLVM found the closed form). Test: run at N and 2N, time must
  roughly double. Alternatives: divan (faster, allocation counting, weaker
  stats), tango (paired sampling). Don't CI-gate wall clock on shared runners.

PROFILE ORDER: perf stat (IPC <1.0 = memory-bound, STOP micro-optimising;
  >2.5 + branch-misses = branch-bound) -> samply record (flamegraph + TIME AXIS)
  -> aggregate __rust_alloc/malloc/free/memcpy (>15% = allocation-bound)
  -> wide drop_in_place = bulk destruction on the hot path
  -> panic_bounds_check present = a check survived.
  Needs debug=1 in [profile.release]. Async: tokio-console + tracing-flame,
  NOT a stack sampler (everything smears into ::poll).
  Deterministic counts for CI: cachegrind (50-100x slow, zero variance).
```

## Sources

- [The Rust Performance Book (Nicholas Nethercote) — Profiling](https://nnethercote.github.io/perf-book/profiling.html) — accessed 2026-08-05
- [The Rust Performance Book — Bounds Checks](https://nnethercote.github.io/perf-book/bounds-checks.html) — accessed 2026-08-05
- [The Rust Performance Book — Build Configuration](https://nnethercote.github.io/perf-book/build-configuration.html) — accessed 2026-08-05
- [criterion-rs/criterion.rs README (v0.8.2, released 2026-02-04; MSRV Rust 1.88)](https://github.com/criterion-rs/criterion.rs) — accessed 2026-08-05
- [Criterion.rs User Guide](https://criterion-rs.github.io/book/index.html) — accessed 2026-08-05
- [`std::simd` module docs, rustc 1.97.1 — nightly-only, `portable_simd` feature](https://doc.rust-lang.org/std/simd/index.html) — accessed 2026-08-05
- [Tracking issue for portable SIMD (rust-lang/rust#86656)](https://github.com/rust-lang/rust/issues/86656) — accessed 2026-08-05
- [`std::hint::black_box` documentation](https://doc.rust-lang.org/std/hint/fn.black_box.html) — accessed 2026-08-05
- [`is_x86_feature_detected!` documentation](https://doc.rust-lang.org/std/macro.is_x86_feature_detected.html) — accessed 2026-08-05
- [cargo-show-asm (pacak/cargo-show-asm)](https://github.com/pacak/cargo-show-asm) — accessed 2026-08-05
- [samply — sampling profiler with Firefox Profiler UI](https://github.com/mstange/samply) — accessed 2026-08-05
- [flamegraph-rs/flamegraph (cargo-flamegraph)](https://github.com/flamegraph-rs/flamegraph) — accessed 2026-08-05
- [Divan: Fast and Simple Benchmarking for Rust (Nikolai Vazquez)](https://nikolaivazquez.com/blog/divan/) — accessed 2026-08-05
- [nvzqz/divan](https://github.com/nvzqz/divan) — accessed 2026-08-05
- [multiversion crate — runtime target-feature dispatch](https://docs.rs/multiversion/latest/multiversion/attr.multiversion.html) — accessed 2026-08-05
- [The Cargo Book — Profiles (`lto`, `codegen-units`, `panic`, `strip`, `debug`)](https://doc.rust-lang.org/cargo/reference/profiles.html) — accessed 2026-08-05
- [The Rustonomicon — Alternative representations (`repr(C)`, `repr(packed)`, `repr(transparent)`)](https://doc.rust-lang.org/nomicon/other-reprs.html) — accessed 2026-08-05
- [LLVM Language Reference — `fast-math` flags and reassociation](https://llvm.org/docs/LangRef.html#fast-math-flags) — accessed 2026-08-05
- [LLVM Auto-Vectorization documentation](https://llvm.org/docs/Vectorizers.html) — accessed 2026-08-05
- [The state of SIMD in Rust (Sergey Davidoff)](https://shnatsel.medium.com/the-state-of-simd-in-rust-in-2025-32c263e5f53d) — accessed 2026-08-05

*Measurement provenance: every number attributed to "I measured" in this module was produced in a Linux sandbox on rustc 1.97.1 (8bab26f4f, 2026-07-14) stable, `x86_64-unknown-linux-gnu`, `opt-level=3`, on a 12th Gen Intel Core i5-12450H (Alder Lake, AVX2 + FMA, no AVX-512), using `objdump -d` for assembly and Criterion 0.8.2 or minimum-of-N `Instant` timing for wall clock. They are single-machine results on a virtualised host and should be treated as illustrative of direction and rough magnitude, not as portable constants. The cache and memory latency figures in the mental model (L1 ~4-5 cycles, L2 ~14, L3 ~40-50, DRAM ~200-300) are standard published Alder Lake/x86-64 figures, not measured here.*

## Changelog
- 2026-08-05 — created
