# Lex→Parse→IR→Optimize→Codegen, SSA, Inlining, Vectorization, LLVM

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.5h · **Prereqs:** T16-assembly · **Updated:** 2026-08-03
> **Module id:** `T16-compilers` · **Tags:** compilers

## The 30-second version

A compiler is a pipeline of representations, each one lower-level and more amenable to a specific class of transformation than the last: lexing turns source text into a token stream, parsing turns tokens into an AST (a tree encoding syntax), semantic analysis/lowering turns the AST into an intermediate representation (IR) that's easier to optimize than either source syntax or final machine code, optimization passes rewrite that IR to be equivalent-but-better, and codegen turns the final IR into real machine instructions for a specific ISA. The single most important IR design in modern compilers is SSA (Static Single Assignment) — every variable is assigned exactly once, with a `phi` node reconciling values that arrive from different control-flow predecessors — because it turns data-flow analysis (which optimizations from constant propagation to dead-code elimination all depend on) into a simpler, more local problem. Inlining (replacing a call with the callee's body) and vectorization (rewriting scalar loops to use SIMD instructions) are the two optimizations most responsible for the gap between naive and fast compiled code, and both depend on the compiler being able to *prove* things about aliasing, side effects, and loop-carried dependencies — which is exactly why `restrict`/aliasing hints, function attributes, and clean loop structure matter more to real-world performance than most developers assume. LLVM's dominance (Clang, Rust, Swift, Julia, and countless JIT projects all target LLVM IR) comes from decoupling frontends (language → LLVM IR) from backends (LLVM IR → machine code) through one stable, well-optimized middle layer, so a new language gets a competitive optimizer and every supported ISA's codegen for free.

## Why this gets asked

Because understanding the compiler pipeline is the connective tissue between "I wrote code" and "I know what actually runs," and it directly explains behavior every senior engineer eventually has to debug: why `-O2` changes timing-sensitive code, why a function marked `inline` isn't always inlined (and vice versa for functions never marked so), why auto-vectorization silently fails on a loop that looks vectorizable, and why two semantically identical pieces of source code can compile to meaningfully different machine code. It's also table stakes for anyone claiming JIT/runtime expertise (JVM's C1/C2, V8's TurboFan, PyPy) since every one of those systems is a compiler pipeline running at runtime instead of ahead-of-time, and the same IR/optimization vocabulary transfers directly.

---

## Lineage: past → present → future

**What came before.** Early compilers (1950s-60s, e.g. the original FORTRAN compiler) were largely monolithic, single-pass translations from source syntax nearly straight to machine code, because memory was scarce enough that building and holding a full intermediate tree or graph in memory was itself a luxury. The pain this caused was twofold: portability (a compiler tightly coupled to one target ISA had to be substantially rewritten for a new one) and optimization quality (transformations that need a global view of the program — constant propagation across basic blocks, dead code elimination, register allocation informed by whole-function liveness — are hard or impossible to do well in a single syntax-directed pass).

**Where it stands now.** The multi-phase pipeline (frontend → IR → optimizer → backend) with SSA-form IR as the optimization substrate is the industry-standard architecture, used by GCC (its own internal IR, GIMPLE, then RTL), LLVM (LLVM IR throughout), the JVM's JIT tiers (bytecode → HIR/MIR in C2, or a simpler representation in C1), and V8 (bytecode → an SSA-based IR in TurboFan). The live disagreement is less about the phase structure (settled) and more about how much optimization should happen ahead-of-time versus at runtime with profile feedback: PGO (Profile-Guided Optimization, feeding real execution profiles back into a subsequent ahead-of-time compile) and JIT compilation (compiling based on live, currently-observed runtime behavior) both chase the same goal — using actual program behavior rather than static heuristics to guide optimization — via different tradeoffs (PGO needs a representative training run and adds build-pipeline complexity; JIT pays warmup cost but adapts continuously and can deoptimize when behavior changes, as covered in the CPython, JVM, and Go/V8 runtime modules).

**Where it's heading.** MLIR (Multi-Level IR, an LLVM subproject) is a real, actively growing direction: instead of one fixed IR level, MLIR supports a stack of custom "dialects" at different abstraction levels (from ML-graph-level operations down to LLVM IR itself) that can be progressively lowered, which is genuinely useful for domain-specific compilers (ML compilers like XLA/IREE, hardware-description compilers) that need higher-level structure preserved longer than LLVM IR alone allows — this is shipped and used in production ML compiler stacks today, not speculative. More speculative: how much of traditional ahead-of-time compiler optimization gets subsumed by increasingly aggressive JIT and profile-guided techniques industry-wide, versus AOT compilation remaining dominant for latency-sensitive cold-start-averse deployment (a live tension visible in, e.g., the JVM's continued AOT experiments like Project Leyden alongside its mature JIT), is a real direction of travel without a fully settled endpoint.

---

## Mental model

Picture the pipeline as a series of translations, each stripping away information the *next* stage doesn't need while adding structure the next stage *does* need:

```
source text
   |  lexer (regex-like tokenizer)
tokens:  IDENT("x") OP("=") NUM("3") OP("+") NUM("4") SEMI
   |  parser (grammar-driven, builds tree)
AST:      Assign(x, Add(3, 4))
   |  lowering / semantic analysis (type-check, resolve names)
IR (SSA):  %1 = add i32 3, 4
           store i32 %1, ptr %x
   |  optimization passes (constant fold, DCE, inline, vectorize...)
optimized IR:  store i32 7, ptr %x     ; folded at compile time
   |  codegen (instruction selection, register allocation)
machine code:  mov dword [x], 7
```

Each arrow is a *lowering* — later stages know less about the original source's structure (a parser knows about `if`/`while`; codegen only knows about basic blocks and jumps) but gain properties useful for mechanical transformation (SSA's "each variable assigned once" property is what makes data-flow analysis simple).

---

## How it actually works

### Lexing and parsing

The **lexer** (tokenizer) consumes raw source text and emits a stream of tokens, typically implemented as a hand-written or generator-produced (`flex`, or a hand-rolled DFA) finite-state scanner — this stage is intentionally "dumb," recognizing lexical categories (identifier, number, operator, keyword) with no understanding of grammar. The **parser** consumes that token stream and builds an AST according to the language's grammar, most commonly via recursive descent (hand-written, common in production compilers including Clang and modern Rust) or a generated LR/LALR parser (`yacc`/`bison`-family, more common in academic or older toolchains) — recursive descent has become the practical favorite in industrial compilers because it gives far better, more specific error messages than table-driven generated parsers, which matters enormously for developer experience even though it's slightly more code to write by hand.

### From AST to IR, and why IR exists at all

The AST directly mirrors source syntax (an `if` node, a `while` node, a `+` node with source-shaped children) which is exactly what makes it awkward to optimize: the same logical operation can appear in structurally different AST shapes depending on how it was written, so a pass written against the AST has to handle many syntactic variations of the same semantic pattern. **Lowering** to an IR normalizes this — control flow becomes a graph of basic blocks connected by explicit jumps/branches, and expressions become sequences of simple, uniform three-address-code-style instructions (`%3 = add %1, %2`), so a single pass written against the IR handles every syntactic form that lowers to the same IR pattern.

### SSA — the pivotal idea

**Static Single Assignment** requires every variable to be assigned exactly once in the IR text (not once at runtime — a loop can still assign a variable's SSA-name-equivalent many times at runtime, but each *textual* assignment site gets a fresh name). Where control flow merges (e.g. after an `if`/`else`, or at a loop header), a **phi node** (`%x3 = phi [%x1, block_then], [%x2, block_else]`) picks the correct incoming value based on which predecessor block control actually arrived from.

Why this matters mechanically: in non-SSA IR, reasoning about "what value does this variable hold at this point" requires tracing backward through all possible reassignments, which can require whole-function reachability analysis for every single query. In SSA, each variable name has exactly one definition site, so "what value does this hold" is answered by looking at exactly one place — the definition — which turns most classical optimizations (constant propagation, dead code elimination, common subexpression elimination, value numbering) from a whole-program fixpoint problem into a local, often single-pass computation. This is *the* reason essentially every modern optimizing compiler (LLVM, GCC's GIMPLE-SSA form, the JVM's C2, V8's TurboFan) uses SSA or an SSA-like form as its core optimization IR — it's not an implementation detail, it's the property that makes the rest of the optimizer tractable.

```llvm
; untested sketch — LLVM IR showing SSA + a phi node for: y = cond ? a+1 : a-1
define i32 @example(i32 %a, i1 %cond) {
entry:
  br i1 %cond, label %then, label %else
then:
  %t1 = add i32 %a, 1
  br label %merge
else:
  %t2 = sub i32 %a, 1
  br label %merge
merge:
  %y = phi i32 [ %t1, %then ], [ %t2, %else ]
  ret i32 %y
}
```

### Optimization passes: inlining and vectorization, concretely

**Inlining** replaces a call site with a copy of the callee's body (SSA-renamed to avoid collisions), eliminating call/return overhead and, critically, exposing the callee's internals to the *caller's* subsequent optimization passes — constant propagation, dead-code elimination, and register allocation can all now see across what used to be an opaque function boundary. This is why inlining is often called the single most impactful optimization: it doesn't just save a `call`/`ret` pair, it *unlocks* every other optimization to work across a boundary they previously couldn't cross. The cost is code size (excessive inlining bloats the binary and can hurt instruction-cache locality, a real countervailing effect), which is why compilers use cost models (estimated callee size, call-site hotness from profile data if available, whether the callee is recursive) to decide, and why `inline`/`__forceinline`/`[[gnu::always_inline]]` are *hints* the compiler is free to ignore (for `inline`) or a stronger directive it will generally honor (for the force variants) rather than guarantees in the general case.

**Auto-vectorization** rewrites a scalar loop to process multiple elements per iteration using SIMD instructions, and it depends on the compiler being able to *prove* the loop has no cross-iteration dependency that would make reordering/parallelizing iterations incorrect, and that the memory accessed by different iterations doesn't alias in a way that would break correctness. Two specific failure modes explain most "why didn't my loop vectorize" cases: **pointer aliasing** — given `void f(float *a, float *b, int n) { for (int i=0;i<n;i++) a[i] += b[i]; }`, the compiler cannot assume `a` and `b` don't overlap, and if they do overlap in a way that creates a loop-carried dependency, vectorizing would change behavior, so without a `restrict` qualifier (C99+) or equivalent proof, many compilers conservatively refuse to vectorize; and **loop-carried dependencies** — an accumulator pattern like `sum += a[i]` is vectorizable (the compiler can use multiple SIMD-lane partial sums, changing floating-point rounding, as discussed in the CPU microarchitecture module) but a pattern like `a[i] = a[i-1] * 2` genuinely cannot be vectorized because each iteration's result depends on the immediately preceding iteration's result by construction. Compilers can report this directly: `-fopt-info-vec-missed` (GCC) or `-Rpass-missed=loop-vectorize` (Clang) print the specific reason a given loop wasn't vectorized, which is the single most useful diagnostic for this class of problem — read it before assuming intrinsics are necessary.

### Codegen: instruction selection and register allocation

The final phase turns optimized IR into real machine code for a specific ISA, via two conceptually separate (though sometimes interleaved) problems: **instruction selection** (choosing which real machine instructions implement a given IR pattern — e.g. recognizing `a*2` should become a shift, not a multiply, or that a multiply-then-add pattern should become a single fused-multiply-add instruction if the target ISA has one) and **register allocation** (assigning the IR's unlimited virtual registers/SSA values onto the target's small, finite physical register set, inserting spill code to memory when there aren't enough physical registers to go around — spills are exactly the `[rbp-N]`-style stack loads/stores visible in disassembly for register-pressure-heavy functions). LLVM's backend does this via a target-independent framework (SelectionDAG or the newer GlobalISel) parameterized per-target by a machine description (`.td` TableGen files) that encodes each ISA's actual instruction set, register classes, and calling convention — which is exactly the architecture that lets one frontend (Clang) and one optimizer (LLVM's `opt` passes) support dozens of backend targets (x86, ARM, RISC-V, WebAssembly, GPUs via NVPTX, and more) without duplicating the optimizer per target.

### Why LLVM specifically

LLVM's core architectural bet — a stable, well-documented, SSA-based IR that both frontends and backends target independently — is what made it possible for Clang, Rust's `rustc`, Swift, Julia, and a long tail of JIT and specialized-language projects to get a competitive optimizer and broad hardware support essentially for free, rather than each language reimplementing its own optimization passes and per-target codegen. This is a genuinely different tradeoff from GCC's more monolithic, historically less-modular internal architecture (GCC has become more modular over time but LLVM was architected around this separation from the start), and it's the direct reason LLVM IR shows up as a compilation target far outside its original C/C++/Objective-C use case — including inside JIT compilers (Julia's JIT, Numba) and GPU compute stacks (CUDA's NVPTX backend goes through LLVM).

---

## Build it from scratch

A minimal expression compiler that goes lex → parse → naive-IR → constant-fold proves the pipeline shape without needing a full language:

```python
# untested sketch — a tiny arithmetic expression compiler: lex -> parse -> "IR" -> constant fold
import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"\s*(?:(\d+)|([+\-*/()]))")

def lex(s):
    pos, tokens = 0, []
    while pos < len(s):
        m = TOKEN_RE.match(s, pos)
        if not m or m.end() == pos:
            raise SyntaxError(f"bad token at {pos}")
        pos = m.end()
        if m.group(1): tokens.append(("NUM", int(m.group(1))))
        elif m.group(2): tokens.append(("OP", m.group(2)))
    return tokens

@dataclass
class Num: value: int
@dataclass
class BinOp: op: str; left: object; right: object

class Parser:  # recursive descent, handles + - * / with precedence
    def __init__(self, tokens): self.tokens, self.i = tokens, 0
    def peek(self): return self.tokens[self.i] if self.i < len(self.tokens) else None
    def eat(self): t = self.tokens[self.i]; self.i += 1; return t
    def parse_expr(self):
        node = self.parse_term()
        while self.peek() and self.peek()[1] in ("+", "-"):
            op = self.eat()[1]
            node = BinOp(op, node, self.parse_term())
        return node
    def parse_term(self):
        node = self.parse_factor()
        while self.peek() and self.peek()[1] in ("*", "/"):
            op = self.eat()[1]
            node = BinOp(op, node, self.parse_factor())
        return node
    def parse_factor(self):
        kind, val = self.eat()
        if kind == "NUM": return Num(val)
        raise SyntaxError("expected NUM")

def constant_fold(node):  # the "optimization pass"
    if isinstance(node, Num): return node
    left, right = constant_fold(node.left), constant_fold(node.right)
    if isinstance(left, Num) and isinstance(right, Num):
        ops = {"+": lambda a,b: a+b, "-": lambda a,b: a-b, "*": lambda a,b: a*b, "/": lambda a,b: a//b}
        return Num(ops[node.op](left.value, right.value))
    return BinOp(node.op, left, right)

ast = Parser(lex("3 + 4 * 2")).parse_expr()
folded = constant_fold(ast)
print(folded)  # Num(value=11) -- fully folded at "compile time," nothing left to codegen
```

This is small on purpose, mirroring the TCP and pipeline exercises in this track: the point isn't a production parser, it's proving that lex→parse→optimize is mechanically understood — precedence handling in the recursive-descent parser and the recursive constant-folding pass are exactly the kind of detail an interviewer probes when they ask you to trace "how does `2 + 3 * 4` become `14`, not `20`."

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A hot loop doesn't vectorize despite looking straightforward | Compiler can't prove pointer non-aliasing between two array arguments | Add `restrict` (C) / prove non-aliasing another way; check `-fopt-info-vec-missed` (GCC) or `-Rpass-missed=loop-vectorize` (Clang) for the exact reason before reaching for intrinsics |
| A function marked `inline` still shows a `call` in the disassembly | `inline` is a hint, not a guarantee; the compiler's cost model judged the callee too large, too hot-path-uncertain, or recursive | Use a stronger directive (`__attribute__((always_inline))`/`[[gnu::always_inline]]`) if truly required, or restructure the callee to be small enough to clear the default inlining threshold — but measure first, since forcing inlining can regress icache locality |
| Binary size balloons after enabling more aggressive optimization | Overly aggressive inlining and loop unrolling duplicating code at many call/iteration sites | Profile-guided optimization (PGO) lets the compiler inline aggressively only at genuinely hot call sites and stay conservative elsewhere, rather than uniformly aggressive static heuristics |
| Two builds of "the same" code produce measurably different performance with no source change | Non-determinism in build flags, LTO (Link-Time Optimization) inclusion/exclusion, or PGO profile staleness relative to current code/traffic patterns | Pin and audit build flags across environments; if using PGO, ensure the training workload still represents current production traffic, and re-profile periodically |
| A JIT-compiled hot path (JVM/V8) suddenly deoptimizes and falls back to the interpreter mid-run | A speculative optimization's assumption (a monomorphic call site, a type guard) was invalidated by runtime behavior the JIT hadn't seen during its initial compilation | Expected, self-correcting behavior in most cases (covered in depth in the JVM and Go/V8 modules); if deoptimization is frequent and sustained, it signals genuinely polymorphic/megamorphic call sites that need source-level restructuring, not a JIT bug |

---

## Tradeoffs & when NOT to use it

- **Don't force inlining broadly as a default performance lever.** The compiler's cost model exists because unconditional inlining trades runtime call overhead for code bloat and worse instruction-cache behavior — forcing it everywhere can *regress* performance on code with many moderately-hot call sites; reserve forced inlining for measured, genuinely hot, small functions.
- **Don't chase auto-vectorization for loops that aren't hot.** Restructuring loop bodies (splitting arrays, avoiding aliasing, adding `restrict`) to satisfy the vectorizer adds real code complexity and portability risk for a gain that only matters if the loop is a measured bottleneck.
- **Don't assume PGO or LTO are free wins to enable everywhere.** Both add real build-pipeline complexity and time (PGO requires a representative training run and a two-pass build; LTO can dramatically increase link time and memory usage for large codebases) — appropriate for release builds of genuinely performance-sensitive binaries, often not worth the CI-time cost for every internal tool or rapidly-iterating service.
- **Don't treat compiler warnings/vectorization-missed reports as noise to suppress.** They're frequently the fastest path to understanding why code isn't as fast as expected — silencing them loses a real diagnostic signal, not just cosmetic noise.
- **This entire module is the wrong lens for algorithmic or I/O-bound bottlenecks.** No amount of inlining or vectorization fixes an O(n²) algorithm that should be O(n log n), or a service whose latency is dominated by a downstream network call — profile to confirm you're actually compiler-optimization-bound before investing here.

---

## Interview questions

### Q1 — Walk through the compiler pipeline stage by stage, and name what each stage's output looks like.
**Testing:** whether the phases and their concrete artifacts (not just names) are understood.
**Answer:** Lexer: source text → token stream (categorized lexemes, e.g. `IDENT`, `NUM`, `OP`). Parser: tokens → AST (a tree mirroring source grammar). Lowering/semantic analysis: AST → IR (normalized, often SSA-form, with explicit control-flow graph of basic blocks). Optimization: IR → optimized IR (same semantics, better properties — fewer instructions, better locality, exposed parallelism). Codegen: optimized IR → machine code (via instruction selection and register allocation, target-specific).
**Follow-up trap:** *"Which of these stages is most language-specific, and which is most reusable across languages?"* — lexing and parsing are inherently language-specific (grammar differs per language); IR, optimization, and codegen are the reusable core that LLVM-style architectures share across many frontends — this is exactly why a new language targeting LLVM IR gets a competitive optimizer essentially for free.

### Q2 — What is SSA, and why does nearly every modern optimizing compiler use it as its core IR?
**Answer:** Static Single Assignment requires every variable to be assigned exactly once textually, with `phi` nodes reconciling values arriving from different control-flow predecessors at merge points. It matters because most classical optimizations (constant propagation, dead-code elimination, common subexpression elimination) reduce to answering "what value does this variable hold here," and in SSA that's answered by looking at exactly one definition site instead of tracing backward through all possible reassignments — turning a whole-program data-flow problem into a local one.
**Follow-up trap:** *"Does SSA mean a loop variable is only assigned once at runtime too?"* — no; SSA is about the *textual* IR having one definition site per name, not about runtime assignment count. A loop variable's SSA form uses a `phi` node at the loop header to merge the initial value (from outside the loop) and the updated value (from the loop's back-edge), and that single `phi` definition can correspond to many runtime assignments across loop iterations — conflating textual single-assignment with runtime single-assignment is a common and revealing mistake.

### Q3 — Why doesn't `restrict` (or its absence) matter for correctness in most code, but matters enormously for vectorization?
**Answer:** `restrict` is a promise to the compiler that a given pointer doesn't alias with certain other pointers in scope — it changes nothing about what the code *does* if the promise is true, but without it, the compiler must conservatively assume aliasing is possible and therefore cannot safely reorder or parallelize memory accesses across iterations, because if the arrays actually did overlap in the wrong way, vectorizing would silently change behavior. With `restrict` (and the promise being true), the compiler can prove the reordering is safe and vectorize.
**Follow-up trap:** *"What happens if you lie and mark two aliasing pointers as `restrict`?"* — undefined behavior; the compiler is now free to generate code that assumes no aliasing, and if the arrays actually do overlap in a way that would change vectorized versus scalar results, the program's behavior is unspecified and can silently produce wrong answers, differ across optimization levels, or vary by compiler — `restrict` is a contract the programmer must actually uphold, not a hint the compiler double-checks.

### Q4 — Why is inlining considered the single most impactful compiler optimization, beyond just removing call overhead?
**Answer:** Inlining exposes a callee's internal instructions directly to the caller's optimization context, which unlocks every other optimization pass to operate *across* what used to be an opaque function boundary — constant propagation can now flow a caller's known argument value into the callee's body, dead-code elimination can remove callee logic that's unreachable given the caller's specific call site, and register allocation can consider the combined function as one unit instead of two separately-allocated pieces. The `call`/`ret` overhead saved is real but usually secondary to this cascading unlock effect.
**Follow-up trap:** *"If inlining is so valuable, why isn't everything always inlined?"* — code size and instruction-cache locality; unconstrained inlining duplicates callee code at every call site, which can bloat the binary enough to hurt icache hit rate and actually regress overall performance despite each individual call site theoretically benefiting — compilers use cost models (callee size, estimated hotness, recursion) to balance this, and `inline` as a keyword is only ever a hint to that cost model, not a directive.

### Q5 — A loop that looks obviously vectorizable to you isn't being vectorized by the compiler. What's your diagnostic process?
**Answer:** Check the compiler's own missed-optimization report first — `-fopt-info-vec-missed` on GCC or `-Rpass-missed=loop-vectorize` on Clang — which states the specific reason (unproven pointer aliasing, a loop-carried dependency, a function call the compiler won't inline/analyze, insufficient trip-count information). Address that specific reason (add `restrict`, hoist the call, restructure the dependency) rather than guessing or jumping straight to hand-written intrinsics.
**Follow-up trap:** *"Give an example of a genuinely non-vectorizable loop-carried dependency, distinct from a reduction that IS vectorizable."* — `a[i] = a[i-1] * 2` is genuinely non-vectorizable because each iteration's result depends directly on the immediately preceding iteration's *result*, not just an associative accumulation; contrast with `sum += a[i]`, a reduction, which the vectorizer CAN parallelize using multiple partial-sum lanes because addition is (approximately, modulo floating-point rounding) associative and the accumulation order doesn't change what's fundamentally being computed, just how the partial results are combined.

### Q6 — What's the practical difference between what PGO and a JIT compiler are both trying to achieve, and where do their tradeoffs diverge?
**Answer:** Both use real, observed program behavior (rather than static heuristics) to guide optimization decisions — which branches are hot, which call sites are monomorphic, which loops actually execute many iterations. PGO does this ahead-of-time: run an instrumented or sampled build against representative traffic, feed the resulting profile into a subsequent compile, and ship a statically-optimized binary. A JIT does this continuously at runtime: start with unoptimized (interpreted or lightly-compiled) code, observe actual live execution, and compile hot paths based on what's *currently* true. PGO's tradeoff is needing a representative training run and paying zero runtime warmup cost; a JIT's tradeoff is paying warmup cost (interpreting or running less-optimized code before the JIT kicks in) but adapting continuously, including deoptimizing if runtime behavior later diverges from what an earlier compilation assumed.
**Follow-up trap:** *"Could you combine both in one system?"* — yes, and modern JVMs and V8 essentially do internally (tiered compilation collects runtime profile data that informs later, more aggressive JIT tiers), and some systems apply PGO to the JIT's own AOT-compiled interpreter/baseline-compiler binary as a separate, additional layer — the two techniques are not mutually exclusive, they operate at different points in the same broader "use real behavior to guide codegen" idea.

### Q7 — Explain register allocation's core problem and why "spilling" happens.
**Answer:** IR represents values using an effectively unlimited number of virtual registers/SSA names; the target ISA has a small, fixed number of physical registers (16 GPRs on x86-64, 31 on ARM64). Register allocation assigns virtual registers to physical ones, and when more values are simultaneously "live" (still needed) than there are physical registers available, some values must be **spilled** — stored to a stack slot and reloaded when needed again, trading a register access for a memory access. Spills are directly visible in disassembly as `[rbp-N]`/stack-relative loads and stores in code that would otherwise be pure register-to-register operations.
**Follow-up trap:** *"Why does high register pressure often correlate with heavy inlining?"* — inlining combines a callee's live values into the caller's already-live set at the call site, increasing the total number of simultaneously-live values the register allocator must fit into the same fixed physical register budget — this is one concrete mechanism behind inlining's code-bloat/register-pressure tradeoff, distinct from the pure instruction-count code-size cost.

### Q8 — Why does LLVM's architecture make it easier to add a new backend target than GCC's historically more monolithic design?
**Answer:** LLVM was architected from the start around a stable, well-specified SSA-form IR that frontends and backends both target independently — a new backend needs to implement instruction selection and register allocation against that one stable IR, described via a target machine description (TableGen `.td` files), without needing to understand or modify the frontend or the shared optimizer at all. This separation is what let LLVM accumulate dozens of backend targets (x86, ARM, RISC-V, WebAssembly, NVPTX for GPUs) and multiple independent frontends (Clang, Rust, Swift, Julia) sharing one optimizer, versus needing per-target, per-frontend-specific optimization work.
**Follow-up trap:** *"Does this mean LLVM IR is a universal, stable ABI-like contract across LLVM versions?"* — no, and this is a genuine practical gotcha: LLVM IR is *not* guaranteed stable across LLVM versions in the way a wire protocol or file format would be — frontends and backends generally need to be built against matching or compatible LLVM versions, which is a real maintenance burden for projects (like Rust, which vendors/tracks specific LLVM versions carefully) that depend on it as their core codegen infrastructure.

### Q9 — What's the mechanical reason a floating-point reduction loop's result can change slightly when vectorized, and is this a bug?
**Answer:** Floating-point addition is not associative (rounding at each step depends on operand order), so summing via multiple SIMD-lane partial accumulators and combining them at the end computes the sum in a genuinely different order than strict sequential left-to-right accumulation, which can produce a different (though typically extremely close) final rounded result. It's not a bug in the ordinary sense — both orderings are valid interpretations of "sum these numbers" under IEEE-754 semantics, and the compiler is only permitted to make this transformation under relaxed floating-point contract flags (`-ffast-math` or specific looser flags, not default strict IEEE compliance) precisely because it's aware this changes results.
**Follow-up trap:** *"Would strict `-fno-fast-math` builds still vectorize this loop?"* — often not the same way, or not at all for the reduction specifically — under strict IEEE-754 ordering requirements, the compiler generally can't reorder floating-point operations that would change rounding behavior, so it either vectorizes only the non-order-sensitive parts of a loop or declines to vectorize a strict sequential reduction, which is a real, quotable example of a correctness/performance tradeoff exposed directly through a compiler flag.

### Q10 — Staff-level: your team is deciding whether to invest in enabling both LTO and PGO for a latency-sensitive service's release pipeline. What's the actual case for and against?
**Answer:** Case for: LTO (Link-Time Optimization) lets the optimizer see across translation-unit boundaries that are otherwise opaque at compile time (e.g. inlining a function defined in one `.c` file into a call site in another), and PGO focuses aggressive optimization (inlining, code layout, branch prediction hints) on genuinely hot paths identified from real traffic rather than static heuristics — together they're commonly cited as producing meaningful throughput/latency improvements (often single-digit to low double-digit percent, workload-dependent) for exactly the kind of service where that matters. Case against: both add real build-pipeline cost and complexity — LTO can substantially increase link time and peak memory usage for large codebases, and PGO requires maintaining a training/profiling step and periodically re-profiling as the codebase and traffic patterns evolve, with a stale profile potentially guiding optimization toward code paths that are no longer actually hot. The right call depends on whether the service's performance is genuinely on the critical path for cost or user experience at a scale where the build-pipeline investment pays for itself, versus a service where iteration speed and pipeline simplicity matter more than the last few percent of runtime performance.
**Follow-up trap:** *"How would you detect that a PGO profile has gone stale and is actively hurting rather than helping?"* — compare current production behavior (via live profiling/observability, e.g. continuous `perf`-based profiling or APM traces) against what the PGO-guided binary assumed was hot; a mismatch (the binary optimized for call patterns or branch outcomes that no longer reflect current traffic) is the concrete, measurable signal, and the fix is re-running the training/profiling step against current representative traffic, not abandoning PGO outright.

---

## Red flags that fail you

- Confusing an AST with an IR, or claiming they serve the same purpose in a compiler.
- Claiming SSA means a variable is only assigned once at *runtime* rather than once per textual definition site (missing the role of `phi` nodes in loops).
- Treating `inline` as a guarantee rather than a hint the compiler's cost model can override.
- Claiming a loop "should obviously vectorize" without checking the compiler's own missed-optimization diagnostics for the actual blocking reason.
- Not knowing that vectorized floating-point reductions can change numerical results due to non-associativity, or claiming floating-point reordering is always safe.
- Treating PGO/LTO as unconditionally worth enabling everywhere with no build-pipeline cost tradeoff.

---

## Cheat card

```
PIPELINE: source -> [lex] -> tokens -> [parse] -> AST -> [lower] -> IR (often SSA)
  -> [optimize] -> optimized IR -> [codegen: instr select + reg alloc] -> machine code
SSA: every variable assigned once TEXTUALLY (not once at runtime). phi node merges
  values at control-flow join points. Turns data-flow analysis local, not whole-program.
  -> why nearly every modern optimizer (LLVM, GCC GIMPLE-SSA, JVM C2, V8 TurboFan) uses it.
INLINING: replaces call with callee body -> UNLOCKS other passes across the old call
  boundary (const-prop, DCE, better reg alloc), not just removes call/ret overhead.
  inline keyword = HINT only. Cost: code bloat, worse icache, higher register pressure.
VECTORIZATION: needs proof of no cross-iteration dependency + no harmful aliasing.
  restrict (C99+) tells compiler pointers don't alias -> unlocks reordering.
  Diagnose failures: -fopt-info-vec-missed (GCC) / -Rpass-missed=loop-vectorize (Clang).
  Non-vectorizable: a[i]=a[i-1]*2 (true loop-carried dep). Vectorizable: sum+=a[i]
  (reduction, but changes FP rounding order -- needs relaxed FP flags to enable).
CODEGEN: instruction selection (pick real ops, e.g. fuse multiply-add) + register
  allocation (map unlimited virtual regs -> ~16-31 physical, SPILL to stack if not enough).
LLVM: stable SSA IR decouples frontends (Clang/Rust/Swift/Julia) from backends
  (x86/ARM/RISC-V/WASM/NVPTX) -> new language gets competitive optimizer + broad
  hardware support for free. LLVM IR NOT guaranteed stable across LLVM versions.
PGO vs JIT: both use REAL runtime behavior to guide optimization. PGO = ahead-of-time,
  needs representative training run, zero runtime warmup. JIT = continuous, adapts live,
  pays warmup + can deoptimize when assumptions break.
```

## Sources

- Aho, Lam, Sethi, Ullman, *Compilers: Principles, Techniques, and Tools* ("the Dragon Book") — canonical primary source for the full pipeline
- Cytron, Ferrante, Rosen, Wegman, Zadeck, "Efficiently Computing Static Single Assignment Form and the Control Dependence Graph," ACM TOPLAS 1991 — the original SSA construction paper
- [LLVM Language Reference Manual](https://llvm.org/docs/LangRef.html) — accessed 2026-08-03
- [LLVM auto-vectorization documentation](https://llvm.org/docs/Vectorizers.html) — accessed 2026-08-03
- [GCC vectorization diagnostics — `-fopt-info`](https://gcc.gnu.org/onlinedocs/gcc/Developer-Options.html) — accessed 2026-08-03
- [MLIR: A Compiler Infrastructure for the End of Moore's Law](https://arxiv.org/abs/2002.11054) — original MLIR paper, referenced for the "where it's heading" section

## Changelog
- 2026-08-03 — created
