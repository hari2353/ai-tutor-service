# x86-64 & ARM64: Registers, ABI, Stack Frames, Reading objdump

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.5h · **Prereqs:** T16-cpu-microarch · **Updated:** 2026-08-03
> **Module id:** `T16-assembly` · **Tags:** assembly
> **Lab:** `labs/c/03-reading-asm/`

## The 30-second version

x86-64 (System V ABI, used on Linux/macOS) passes the first six integer/pointer arguments in `rdi, rsi, rdx, rcx, r8, r9`, returns integer/pointer values in `rax`, and dedicates `rbp`/`rsp` to the stack frame; ARM64 (AAPCS64) passes the first eight arguments in `x0-x7`, returns in `x0`, and uses `x29`/`x30` as frame pointer/link register with a dedicated link register (`x30`) instead of x86's push-return-address-on-call convention. A stack frame is just a fixed-size scratch region for a function's locals and saved registers, built on entry (`push rbp; mov rbp, rsp; sub rsp, N`) and torn down on exit, and every "why is this function slow" question that isn't about algorithms eventually resolves to reading what the compiler actually emitted — via `objdump -d`, `gdb`, or Compiler Explorer (godbolt.org) — rather than guessing. A CPython `for` loop over a numeric range is roughly 50-100x slower than the equivalent C loop not because Python's arithmetic is slow per se, but because each iteration pays for bytecode dispatch, dynamic type checks, refcounting, and boxed-object allocation — costs that don't exist at all in compiled, statically-typed machine code, and that numeric libraries (NumPy, Cython, PyPy's JIT) exist specifically to route around by dropping into compiled code for the actual inner loop.

## Why this gets asked

Because "read the assembly" is the single fastest way to separate someone who can *use* a profiler from someone who actually understands what their code compiles to, and it's a skill that transfers directly to debugging optimized-away variables in a debugger, understanding why `-O2` changed program behavior (usually a UB bug the optimizer was allowed to exploit), or explaining exactly what a JIT-compiled hot path looks like. It's also the fastest way to test whether someone actually understands the Python-is-slow claim mechanically (bytecode dispatch + refcounting + boxing) versus reciting it as received wisdom.

---

## Lineage: past → present → future

**What came before.** Early assembly programming targeted CISC ISAs with variable-length, densely-encoded instructions and comparatively few general-purpose registers (x86's 32-bit predecessor had 8 GPRs, several with fixed special roles), and calling conventions varied wildly across compilers and even across versions of the same compiler on the same OS, because there was no single mandated ABI — this "pain" (binary incompatibility between object files compiled by different tools, and the need to hand-tune register allocation because there were so few registers to work with) motivated the standardization pass that produced the modern ABIs.

**Where it stands now.** x86-64 standardized on the System V AMD64 ABI (Linux, macOS, BSD; Windows uses a materially different convention with different register assignments and a caller-allocated shadow space) and ARM64 standardized on AAPCS64 (used consistently across Linux, macOS/iOS, and Android with only minor platform-specific variations) — both give 64-bit general-purpose registers, doubled or more register counts versus 32-bit predecessors (x86-64 has 16 GPRs, ARM64 has 31), and mandate exactly which registers carry arguments, return values, and which the callee must preserve across a call. The live disagreement, to the extent one exists, is less about the ABIs themselves (settled, stable, rarely revised) and more about how much of this level should be visible to application programmers at all — WebAssembly and managed-runtime bytecodes (JVM bytecode, CPython bytecode) exist specifically to give a portable target that never has to think about a specific ISA's register file, at the cost of an interpretation or JIT-compilation layer between the portable representation and real silicon.

**Where it's heading.** ARM64's server-side share has grown substantially and durably (AWS Graviton, Azure Cobalt, Google Axion, Apple Silicon) to the point where "compile once, assume x86" is no longer a safe default for anything shipping to cloud infrastructure — multi-architecture container builds and CI matrices covering both x86-64 and ARM64 are now standard practice for serious production software, a real and largely completed shift rather than a speculative one. More speculative: RISC-V's role in general-purpose server/desktop computing is still early — real but currently concentrated in embedded, specialized accelerator, and some China-market contexts rather than mainstream cloud compute, and whether it becomes a true third mainstream server ISA on the timescale of the next several years is not yet a settled bet.

---

## Mental model

Think of a function call as handing off a clipboard: the caller fills in a fixed set of "slots" (registers, then stack if more than the register budget) with arguments, writes the return address on top of the stack (x86) or into a dedicated register (ARM64's `x30`), and jumps. The callee treats some registers as "yours to trash" (caller-saved) and others as "hand back exactly as you found them" (callee-saved) — this contract is the entire calling convention, and getting it wrong (writing hand-tuned assembly, or debugging a corrupted stack) means violating an agreement neither side can see enforced except by crashing.

```
x86-64 System V call:  main() calls add(3, 4)
  mov edi, 3      ; arg1 -> rdi
  mov esi, 4      ; arg2 -> rsi
  call add        ; pushes return address, jumps
add:
  mov eax, edi
  add eax, esi    ; result -> eax (low 32 bits of rax)
  ret             ; pops return address, jumps back
```

---

## How it actually works

### x86-64 registers and the System V ABI

16 general-purpose 64-bit registers: `rax, rbx, rcx, rdx, rsi, rdi, rbp, rsp, r8-r15`. The System V AMD64 ABI (the Linux/macOS/BSD convention) assigns roles:

- **Integer/pointer arguments 1-6:** `rdi, rsi, rdx, rcx, r8, r9`, in that order. A 7th+ argument spills to the stack.
- **Return value:** `rax` (and `rdx:rax` together for 128-bit values).
- **Floating-point arguments:** the first eight go in `xmm0-xmm7`, entirely separate from the integer argument registers — a function with mixed int/float arguments interleaves them independently across the two register files, not combined into one sequence.
- **Caller-saved (volatile) registers:** `rax, rcx, rdx, rsi, rdi, r8-r11` — the callee is free to clobber these, so the caller must save anything it needs across the call itself.
- **Callee-saved (non-volatile) registers:** `rbx, rbp, r12-r15, rsp` — the callee must restore these to their original values before returning, typically by pushing them on entry and popping before `ret`.

A quirk worth knowing cold: the **Windows x64 calling convention** is materially different — only four register arguments (`rcx, rdx, r8, r9`), a caller-allocated 32-byte "shadow space" on the stack even when arguments fit in registers, and a different caller/callee-saved register split — which is exactly why code compiled for Linux and code compiled for Windows are ABI-incompatible even on identical hardware, and why cross-platform C libraries need `extern "C"` linkage plus careful attention to which convention a given build targets.

### ARM64 registers and AAPCS64

31 general-purpose 64-bit registers `x0-x30` (each also addressable as a 32-bit `w0-w30`), plus a dedicated stack pointer `sp` (not one of the 31 general-purpose registers) and an implicit zero register `xzr`/`wzr` usable as a source operand. AAPCS64 (ARM's standard procedure call standard for AArch64) assigns:

- **Arguments 1-8:** `x0-x7`. A 9th+ argument spills to the stack.
- **Return value:** `x0` (and `x1` for a second word of a larger return value).
- **Link register:** `x30` (`lr`) holds the return address, set automatically by the `bl` (branch-and-link) instruction — this is the single biggest structural difference from x86, which pushes the return address onto the stack on `call` instead of using a dedicated register.
- **Frame pointer:** `x29` (`fp`), by convention.
- **Callee-saved:** `x19-x28`, plus `x29`/`x30` if the function itself calls other functions (a "leaf" function that calls nothing can skip saving `lr` entirely, a real and common compiler optimization visible in disassembly as the absence of a stack frame).

Because `lr` holds the return address in a register rather than the stack, a leaf function on ARM64 often needs zero stack frame setup at all — call this function, do arithmetic in registers, `ret` straight back using `lr` — which is a visibly different, leaner disassembly pattern than the equivalent x86-64 function, which still needs at minimum a `ret` popping a stack-resident return address even if it skips setting up `rbp`.

### Stack frames

A stack frame is the region of the stack a function uses for local variables, saved registers, and spilled arguments, built and torn down around the function body:

```asm
; x86-64, typical -O0 (unoptimized) prologue/epilogue
push   rbp            ; save caller's frame pointer
mov    rbp, rsp        ; establish new frame pointer
sub    rsp, 0x20        ; allocate 32 bytes of locals
; ... function body, referencing locals as [rbp-8], [rbp-16], etc ...
leave                  ; equivalent to: mov rsp, rbp; pop rbp
ret                     ; pop return address, jump back
```

At `-O0`, compilers preserve this textbook frame-pointer-based layout because it makes debugging trivial (a debugger can walk `rbp` chains to reconstruct a call stack even without debug symbols). At `-O2`/`-O3`, compilers commonly **omit the frame pointer** entirely (`-fomit-frame-pointer`, default at higher optimization levels on many toolchains) and address locals directly off `rsp` with statically-computed offsets, freeing `rbp` for general use as one more allocatable register — this is exactly why stack unwinding/backtraces in optimized release builds sometimes need `.eh_frame`/DWARF CFI metadata instead of a simple `rbp` walk, and why a release-mode crash's backtrace can be less reliable than a debug build's without that metadata present.

### Reading objdump / Compiler Explorer output

`objdump -d --no-show-raw-insn binary` (or, far more pleasantly for exploration, godbolt.org / Compiler Explorer, which shows source-to-assembly mapping live and color-codes corresponding lines) disassembles machine code back to readable mnemonics. The reading workflow that matters in an interview or in real debugging:

1. **Find the function's entry** — look for the label matching the function name (mangled for C++, plain for C, whatever the source language's export convention produces).
2. **Read the prologue** to understand the stack frame size and what's being saved — this tells you how many locals/spilled registers the compiler decided it needed.
3. **Match register usage to the ABI** — `rdi`/`x0` at function entry is argument 1, so seeing `mov eax, edi` at the top of a function immediately tells you "this returns (a transformation of) its first argument" without needing the source.
4. **Look for what's missing** as much as what's present — a function with no `call` instructions at all besides `ret` was fully inlined/optimized down; a loop with no branch back to its own top was fully unrolled; a comparison with no corresponding conditional jump might have been turned into a branchless `cmov`.
5. **Compiler Explorer specifically** is worth using for A/B comparisons — same source, different `-O` levels or different compilers (GCC vs Clang vs MSVC), side by side, to build the intuition for what a given optimization actually does to real code rather than trusting a textbook description of it.

### Why a Python loop is ~100x slower than C, mechanically

```c
// C: compiles to a handful of instructions per iteration, no allocation, no dispatch
long sum = 0;
for (long i = 0; i < 100000000; i++) sum += i;
```

```python
# Python: same logical loop, wildly different execution
total = 0
for i in range(100_000_000):
    total += i
```

The C loop, at `-O2`, is typically just a register increment and compare per iteration (or gets vectorized/unrolled entirely, potentially summing many elements per instruction) — a handful of cycles per iteration, no memory allocation, no indirection.

The CPython loop pays, per iteration: (1) **bytecode dispatch** — the eval loop fetches a `BINARY_ADD`-class opcode (specialized further in 3.11+'s adaptive interpreter, see the CPython runtime module) and dispatches through a switch/computed-goto, itself several instructions of overhead before any real work happens; (2) **boxed integer objects** — `total` and `i` are `PyObject*` heap allocations (a Python `int` is a variable-length struct with a refcount, type pointer, and digit array, not a machine word), so `total += i` means allocating a *new* boxed int object for the result (CPython ints are immutable) unless the small-int cache (-5 to 256) applies; (3) **reference counting** — every object touch increments/decrements a refcount field, each of which is itself a memory read-modify-write with, in the free-threaded build, actual atomic-operation cost; (4) **dynamic type dispatch** — even though both operands are ints, the interpreter must (absent specialization caching the result) look up `__add__` via the type's method resolution before doing the arithmetic. Stacked together, these costs routinely put a naive CPython loop 50-100x slower than the equivalent compiled C loop for pure arithmetic, which is precisely why NumPy (vectorized C loops under a Python API), Cython (compiles Python-like syntax to C), and PyPy's JIT (traces and compiles hot loops to machine code, bypassing the bytecode dispatch and much of the boxing entirely) exist — none of them make Python's *semantics* faster, they route the hot inner loop around the interpreter loop that's actually the bottleneck.

---

## Build it from scratch

The from-scratch exercise here is reading, not writing: compile a small function at multiple optimization levels and explain the diff.

```c
// untested sketch — save as sum.c
long sum_range(long n) {
    long total = 0;
    for (long i = 0; i < n; i++) total += i;
    return total;
}
```

```bash
gcc -O0 -S -o sum_O0.s sum.c
gcc -O2 -S -o sum_O2.s sum.c
diff sum_O0.s sum_O2.s
```

At `-O0`, expect a literal translation of the loop with a real branch back to the top each iteration and `total`/`i` living in stack slots (`[rbp-8]`, `[rbp-16]`), reloaded and stored every iteration. At `-O2`, expect the compiler to either recognize the closed form (`n*(n-1)/2`) and eliminate the loop entirely, or vectorize it with SIMD instructions summing multiple values per iteration — either way, a dramatically different instruction sequence for logically identical source, which is exactly the "derive rather than assert" exercise this section of the house format calls for: don't just claim `-O2` is faster, read the actual diff and explain *why* each changed instruction exists. Full walkthrough with expected output and an ARM64 (`gcc -target aarch64` or a Compiler Explorer link) comparison lives in `labs/c/03-reading-asm/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A debugger backtrace in a release build is truncated or wrong past a few frames | Frame pointer omission (`-fomit-frame-pointer`, default at `-O2`+) removed the simple `rbp`-chain a naive unwinder relies on | Build with `-fno-omit-frame-pointer` for debuggable release builds (a real, small, quantifiable perf cost, commonly cited low single-digit percent), or ensure the toolchain/profiler uses DWARF CFI-based unwinding instead of frame-pointer walking |
| A function behaves differently (or crashes) only at `-O2`/`-O3`, not `-O0` | Undefined behavior in the source (signed integer overflow, use of an uninitialized value, strict-aliasing violation) that the optimizer is legally permitted to exploit, producing different codegen | Build with `-fsanitize=undefined,address` during development to catch UB before it becomes an optimization-dependent bug; don't treat `-O0` behavior as the source of truth for correctness |
| A hot numeric Python function is unacceptably slow despite a correct O(n) algorithm | The cost is bytecode dispatch + boxed-object allocation + refcounting per element, not the algorithm | Vectorize with NumPy (push the loop into compiled C), or compile the hot path with Cython/Numba, rather than attempting to "optimize" pure-Python arithmetic further |
| ARM64 build of a library that works fine on x86-64 crashes or misbehaves only on Graviton/Apple Silicon CI | An assumption baked into hand-written assembly or intrinsics (or, less commonly, memory-ordering assumptions valid on x86's stronger memory model but not on ARM64's weaker one) that doesn't hold cross-architecture | Rebuild the assumption-sensitive code from portable C with proper memory-order-aware atomics (`std::atomic` with explicit ordering) instead of relying on x86's comparatively strong default ordering |
| Calling a C library from a language runtime crashes intermittently only on Windows, not Linux/macOS | Calling convention mismatch — code assumed System V register assignments (`rdi, rsi, ...`) or didn't account for Windows x64's caller-allocated shadow space | Ensure the FFI layer / `extern "C"` binding explicitly targets the correct platform ABI; don't assume System V register assignments are portable to Windows |

---

## Tradeoffs & when NOT to use it

- **Don't read assembly to "optimize" code that isn't hot.** This entire skill is a diagnostic tool for the small fraction of code where microarchitecture-level behavior actually matters (profiled hot paths); applying it broadly produces unreadable, unmaintainable code for no measured benefit — the same principle as the previous two modules.
- **Don't hand-write assembly as a default performance lever.** Modern optimizing compilers (GCC, Clang/LLVM, MSVC) routinely produce code as good as or better than hand-written assembly for anything beyond a tiny number of genuinely special cases (specific SIMD kernels, certain cryptographic primitives requiring constant-time guarantees the compiler can't promise); hand-written assembly is also immediately non-portable across ISAs and a maintenance liability.
- **Don't assume `-fomit-frame-pointer`'s debuggability cost is always worth paying.** For latency-critical services where production profiling/debugging matters more than the last percent of throughput, `-fno-omit-frame-pointer` (increasingly the norm at large companies specifically to keep `perf`-based production profiling usable, e.g. widely discussed in the context of continuous profiling infrastructure) is a defensible default; for genuinely throughput-bound batch compute with good pre-production profiling coverage, the default omission is fine.
- **Don't treat "Python is 100x slower than C" as true for all Python code.** It's specifically true for tight, allocation-heavy, dynamically-dispatched pure-Python numeric loops; Python code that spends its time in C extensions (NumPy, most of the standard library's hot paths, database drivers) pays none of this per-element overhead — the 100x number is about the interpreter loop, not about "Python" as a monolith.
- **This module is the wrong lens for algorithmic complexity problems.** Reading assembly to shave constant-factor overhead on an O(n²) algorithm that should be O(n log n) is solving the wrong problem entirely; get the complexity class right first.

---

## Interview questions

### Q1 — Name the first four integer argument registers in the System V x86-64 ABI and AAPCS64, in order.
**Testing:** baseline ABI knowledge, checked for precision (order matters, integer vs float registers are separate).
**Answer:** System V x86-64: `rdi, rsi, rdx, rcx` (continuing `r8, r9` for args 5-6). AAPCS64: `x0, x1, x2, x3` (continuing through `x7` for args 5-8, giving ARM64 two more register-passed arguments than x86-64 before spilling to the stack).
**Follow-up trap:** *"Where do floating-point arguments go, and does that change the integer register assignment for a mixed-type function?"* — floating-point args go in a separate register file (`xmm0-xmm7` on x86-64, `v0-v7` on ARM64) with independent numbering from the integer arguments, so `func(int a, double b, int c)` puts `a` in `rdi`/`x0`, `b` in `xmm0`/`v0`, and `c` in `rsi`/`x1` — the two register files are numbered independently, not interleaved into one combined sequence.

### Q2 — What's the difference between caller-saved and callee-saved registers, and why does this distinction exist at all?
**Answer:** Caller-saved (volatile) registers may be freely clobbered by any function call, so the caller must save any value it needs across the call itself; callee-saved (non-volatile) registers must be restored to their original value by the callee before returning. The distinction exists to avoid every function having to save *every* register on every call — by convention, a function only needs to protect the registers it actually cares about surviving a call, and only needs to preserve the registers a caller might be relying on, splitting the bookkeeping burden efficiently between both sides.
**Follow-up trap:** *"Give the x86-64 System V caller-saved and callee-saved lists."* — Caller-saved: `rax, rcx, rdx, rsi, rdi, r8-r11`. Callee-saved: `rbx, rbp, r12-r15` (and implicitly `rsp`, which every function must restore by definition of a balanced stack).

### Q3 — Explain why a leaf function on ARM64 can skip stack frame setup entirely, while an x86-64 function always needs at least a `ret`.
**Answer:** ARM64's `bl` instruction stores the return address in a dedicated register, `x30`/`lr`, rather than pushing it to the stack — a leaf function (one that calls nothing else) can do all its work in registers and `ret` directly using `lr` with zero stack interaction. x86-64's `call` instruction always pushes the return address onto the stack, so even the leanest possible x86-64 function must execute `ret` to pop that address back off the stack and jump — there's no register-only equivalent, because the ABI's call mechanism is stack-based, not register-based, from the instruction set itself.
**Follow-up trap:** *"Does this mean ARM64 is always faster for function calls?"* — not universally; it means ARM64 leaf calls specifically avoid a stack write/read that x86-64 cannot avoid, which matters for call-heavy code with many small leaf functions, but non-leaf functions on both architectures still need to save/restore whatever registers cross their own nested calls, and overall call overhead depends heavily on calling convention register-argument counts, inlining decisions, and the specific microarchitecture's call/return prediction hardware — a blanket "ARM64 is faster at calls" claim oversimplifies a workload-dependent comparison.

### Q4 — You're debugging a release-mode crash and the backtrace stops after two frames. What's your first hypothesis?
**Answer:** Frame pointer omission — at `-O2`/`-O3`, `rbp` is commonly repurposed as a general register (`-fomit-frame-pointer`, often the default at higher optimization levels), so a naive frame-pointer-walking unwinder (or a profiler/debugger relying on that method) loses the chain after the last frame that still has one. The fix is either rebuilding with `-fno-omit-frame-pointer` or ensuring the tool uses DWARF CFI (`.eh_frame`)-based unwinding, which encodes stack-layout metadata independent of whether `rbp` is used as a frame pointer.
**Follow-up trap:** *"What's the actual performance cost of keeping the frame pointer, and is it worth it in production?"* — commonly cited as a small, low-single-digit percent throughput cost depending on workload (frame pointer omission frees one more general-purpose register); many large-scale production environments now default to `-fno-omit-frame-pointer` specifically because always-on production profiling (continuous `perf`-based profiling infrastructure) depends on reliable stack unwinding, judging that tradeoff worth paying — a legitimate, increasingly common choice rather than a purely academic one.

### Q5 — A function behaves correctly at `-O0` but crashes or misbehaves at `-O2`. What's your first hypothesis, and how do you confirm it?
**Answer:** Undefined behavior in the source — signed integer overflow, dereferencing an uninitialized pointer, violating strict aliasing, or reading past an array bound — that happens to produce "accidentally correct" results at `-O0` (which does minimal transformation) but gives the optimizer license to transform the code in ways that expose the UB once `-O2`'s more aggressive analysis and transformation passes are applied. Confirm by rebuilding with `-fsanitize=undefined,address` (UBSan/ASan), which instruments exactly these classes of UB and reports them at runtime regardless of optimization level.
**Follow-up trap:** *"Isn't it more likely the optimizer has a bug?"* — compiler bugs exist but are rare relative to UB in application code; the correct debugging discipline is to rule out UB first (sanitizers), because "blame the compiler" without that step is both usually wrong and a red flag that the candidate doesn't reach for the standard tool that actually answers the question.

### Q6 — Mechanically, why is a naive CPython arithmetic loop roughly 50-100x slower than the equivalent C loop?
**Answer:** Four stacked costs per iteration that don't exist in compiled C: bytecode dispatch overhead (fetching and dispatching an opcode through the eval loop before any real work happens), boxed integer allocation (Python ints are heap-allocated `PyObject` structs, and arithmetic on them allocates a new immutable result object unless the small-int cache applies), reference counting (every object touch does an atomic-adjacent refcount read-modify-write), and dynamic type dispatch (looking up `__add__` via the type rather than emitting a single machine `add` instruction). None of these exist in a compiled C loop, which is typically just a register increment/compare, possibly vectorized.
**Follow-up trap:** *"Does this mean all Python is 50-100x slower than C?"* — no, specifically the *interpreter loop's* per-element overhead is; Python code whose hot path executes inside a C extension (NumPy's vectorized operations, most standard-library internals) pays essentially none of this per-element cost, which is exactly why "vectorize with NumPy" rather than "rewrite the loop more cleverly in pure Python" is the standard fix.

### Q7 — What does it mean for the Windows x64 calling convention to be "materially different" from System V, concretely?
**Answer:** Windows x64 passes only the first four integer/pointer arguments in registers (`rcx, rdx, r8, r9`, versus System V's six), requires the caller to reserve a 32-byte "shadow space" on the stack even when all arguments fit in registers (so the callee has a place to spill them if needed), and has a different caller/callee-saved register split. This means object code compiled for Linux/macOS under System V and object code compiled for Windows under its convention are ABI-incompatible even on identical x86-64 hardware — you cannot link them together without an explicit calling-convention-aware shim.
**Follow-up trap:** *"How does this affect writing portable C that calls into platform-specific assembly or intrinsics?"* — any hand-written assembly or raw calling-convention-sensitive FFI code must be written twice (or conditionally compiled) per platform; this is exactly why cross-platform libraries lean heavily on `extern "C"` and compiler-generated code (which handles the convention correctly per target) rather than hand-written platform-specific assembly wherever avoidable.

### Q8 — Explain what "the compiler fully inlined and optimized away a function call" looks like in objdump output, concretely.
**Answer:** The calling function's disassembly shows no `call` instruction to the target function's label at all — the target's logic (its instructions, operating on the caller's already-loaded registers) appears directly inline within the caller's own instruction stream, and if the target's return value was used in a way the compiler can fully resolve statically (e.g. a compile-time-constant input), the entire computation might collapse to a single `mov` of a precomputed constant, with no trace of the original function's logic surviving at all.
**Follow-up trap:** *"How would you confirm a specific function was inlined versus simply not present in the binary for an unrelated reason (e.g. dead code elimination)?"* — check whether the *effects* of the function's logic are still present inline at the call site (the arithmetic/behavior is visibly happening, just without a `call`) versus genuinely absent (the call site and its surrounding logic vanished entirely because the result was provably unused) — Compiler Explorer's source-to-assembly highlighting makes this distinction easy to see directly; `objdump` alone requires more careful manual correlation with the source.

### Q9 — Why does `sub_range(n)` summing `0..n-1` in a naive loop sometimes compile, at `-O2`, to code with no loop at all?
**Answer:** The compiler's optimizer can recognize the loop computes a closed-form arithmetic series (`n*(n-1)/2`) through strength reduction and induction-variable analysis, and replace the entire loop with a single multiply-and-shift computing the closed form directly — a transformation only possible because the loop body has no side effects and a provably fixed trip count relationship to the result, which the compiler's data-flow analysis can establish.
**Follow-up trap:** *"Would the same optimization happen if the loop body called an external function each iteration?"* — no; a call to a function the compiler cannot fully analyze (not inlined, potentially has side effects, e.g. writes to a global or performs I/O) breaks the analysis the closed-form transformation depends on, because the compiler can no longer prove the loop is a pure, side-effect-free computation reducible to a formula — it must preserve the actual iteration.

### Q10 — Staff-level: your team wants to enable `-fno-omit-frame-pointer` fleet-wide to support continuous production profiling. What's the actual cost-benefit case you'd make?
**Answer:** The cost is a measurable but typically small (low single-digit percent, workload-dependent) throughput regression from dedicating `rbp` to frame-pointer bookkeeping instead of general use, paid on every function call across the fleet. The benefit is that `perf`-based (or equivalent) production profiling, which relies on stack unwinding to attribute CPU time to call stacks, becomes dramatically more reliable — without it, sampling profilers either miss frames past the first few (frame-pointer-based unwinding fails past omitted frames) or require DWARF CFI-based unwinding, which is slower to compute per sample and sometimes unavailable/unreliable for JIT-generated or stripped code. For a fleet where diagnosing production incidents by profiling live traffic is a core operational capability, the tradeoff favors keeping frame pointers; for narrowly-scoped, extensively pre-production-profiled batch workloads where that capability matters less, the throughput win from omission may be worth keeping.
**Follow-up trap:** *"Is there a way to get both the throughput win and reliable unwinding?"* — DWARF CFI-based unwinding (`.eh_frame`) gives reliable unwinding without keeping the frame pointer, but at higher per-sample computational cost for the profiler itself, and it doesn't help for hand-written/JIT-generated code lacking CFI metadata — so "both" isn't free either, it's a different point on the same tradeoff curve (unwinder cost/complexity instead of runtime register cost), not an escape from having one.

---

## Red flags that fail you

- Mixing up which registers carry arguments on x86-64 vs ARM64, or claiming they're the same convention.
- Claiming Python is "always 100x slower than C" without naming the actual mechanism (bytecode dispatch, boxing, refcounting, dynamic dispatch), or without the caveat that C-extension-backed Python code doesn't pay this cost.
- Not knowing that `-O2`+ commonly omits the frame pointer, or blaming a truncated backtrace purely on "an optimizer bug."
- Treating hand-written assembly as a default performance technique rather than a rare, targeted tool for cases the compiler genuinely can't handle as well.
- Assuming Windows and Linux x86-64 calling conventions are identical.
- Diagnosing a crash that only appears at `-O2` as a compiler bug before ruling out undefined behavior with sanitizers.

---

## Cheat card

```
x86-64 SysV: int args -> rdi,rsi,rdx,rcx,r8,r9 (7th+ on stack). FP args -> xmm0-7 (separate).
  Return: rax (rdx:rax for 128-bit). Caller-saved: rax,rcx,rdx,rsi,rdi,r8-r11.
  Callee-saved: rbx,rbp,r12-r15. call pushes return addr to stack; ret pops it.
ARM64 AAPCS64: args -> x0-x7 (9th+ on stack). Return: x0 (x1 for 2nd word).
  Link register x30(lr) holds return addr (bl sets it) -- leaf fns need NO stack frame.
  Frame pointer: x29(fp). Callee-saved: x19-x28 (+x29/x30 if non-leaf).
WINDOWS x64: only 4 reg args (rcx,rdx,r8,r9) + 32-byte caller-allocated shadow space.
  ABI-incompatible with System V on identical hardware.
STACK FRAME (-O0): push rbp; mov rbp,rsp; sub rsp,N ... leave; ret
  -O2+ commonly OMITS frame pointer (-fomit-frame-pointer) -> breaks naive rbp-walk
  backtraces; use -fno-omit-frame-pointer or DWARF CFI (.eh_frame) unwinding instead.
READING OBJDUMP: find entry label -> read prologue (frame size) -> map regs to ABI
  (rdi/x0 at entry = arg1) -> note what's MISSING (no call = inlined, no loop = unrolled,
  no jcc = branchless cmov).
PYTHON ~50-100x SLOWER THAN C (pure arithmetic loop): bytecode dispatch overhead +
  boxed PyObject allocation per result + refcounting on every touch + dynamic __add__
  dispatch. Fix = route hot loop into compiled code (NumPy/Cython/Numba), not micro-tune
  pure Python.
UB AT -O2 ONLY: signed overflow / uninit read / strict-aliasing violation the optimizer
  is legally allowed to exploit. Diagnose with -fsanitize=undefined,address, not by
  blaming the compiler.
```

## Sources

- System V Application Binary Interface, AMD64 Architecture Processor Supplement (the authoritative x86-64 Linux/macOS/BSD ABI spec)
- ARM, "Procedure Call Standard for the Arm 64-bit Architecture (AAPCS64)" — official ARM64 calling convention spec
- Microsoft, "x64 calling convention" (learn.microsoft.com) — Windows x64 ABI specifics
- [Compiler Explorer (godbolt.org)](https://godbolt.org) — accessed 2026-08-03, primary tool referenced throughout this module
- [Python support for free threading — Python 3.14 documentation](https://docs.python.org/3/howto/free-threading-python.html) — accessed 2026-08-03, referenced for refcounting cost context
- Agner Fog, "Calling conventions for different C++ compilers and operating systems" — cross-platform ABI reference

## Changelog
- 2026-08-03 — created
