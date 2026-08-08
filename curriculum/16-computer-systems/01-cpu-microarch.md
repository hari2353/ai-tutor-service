# Gates → ALU → Pipelining, Hazards, Branch Prediction, OoO, SIMD

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.5h · **Prereqs:** none (track entry point) · **Updated:** 2026-08-03
> **Module id:** `T16-cpu-microarch` · **Tags:** hardware

## The 30-second version

A CPU is a pipeline of latches around a combinational logic core: gates build an ALU, the ALU plus a register file and control logic become a datapath, and pipelining overlaps the fetch/decode/execute/memory/writeback stages of successive instructions so throughput approaches one instruction per cycle even though any single instruction still takes 5-19+ cycles latency. Hazards (structural, data, control) are the tax on that overlap, and every technique after the classic 5-stage RISC pipeline exists to hide one of them: forwarding/bypassing hides data hazards, branch prediction plus speculative execution hides control hazards, and out-of-order (OoO) execution with a reorder buffer hides both data hazards and the load-use latency wall by letting independent instructions run ahead of a stalled one. Modern cores are superscalar (decode/issue 4-8 instructions per cycle) and OoO with reorder buffers of 320-512+ entries (Zen4 ~320, Golden Cove ~512), branch predictors that hit 95-99% on real workloads with a ~15-20 cycle misprediction penalty when they miss, and SIMD units (AVX-512, up to 512 bits = 16 fp32 lanes per instruction) that trade flexibility for throughput on data-parallel loops. The entire discipline of writing "fast" low-level code is really about not fighting this machine: keep branches predictable, keep dependency chains short, keep memory access patterns vectorizable, and let the hardware's speculation do the rest.

## Why this gets asked

Interviewers ask this to find out whether you understand *why* certain code is fast independent of algorithmic complexity, because Big-O is blind to cache misses, branch mispredictions, and pipeline stalls, and a surprising fraction of real production perf work (JIT-compiled hot loops, SIMD-friendly numeric kernels, lock-free data structures) lives entirely in this territory. Someone who has actually profiled a hot loop with `perf stat` and seen IPC (instructions per cycle) sitting at 0.6 instead of 3+ knows the answer usually isn't "algorithm is wrong," it's "branch misprediction rate is 8%" or "this loop has a serial dependency chain that OoO can't parallelize." The Spectre/Meltdown disclosures (2018) also turned speculative execution from an academic curiosity into something every senior engineer is expected to at least understand the shape of, because it revealed the *security* cost of the exact performance trick this module explains.

---

## Lineage: past → present → future

**What came before.** Early CPUs (single-cycle designs like the original 6502 or a naive multi-cycle datapath) executed one instruction fully before starting the next — correct, simple to reason about, and a hard ceiling of roughly 1 instruction per multi-cycle period regardless of clock speed. The pain was throughput: as transistor budgets grew (Dennard scaling let clock speeds climb through the 1980s-2000s), a single-cycle design couldn't exploit that budget for anything except a longer critical path, so it left most of the die idle most of the time. The classic 5-stage RISC pipeline (MIPS, early ARM, the model every CS architecture course still teaches: IF-ID-EX-MEM-WB) fixed this by overlapping instructions, but it exposed hazards as a first-class problem — a load followed immediately by a use of that value now genuinely stalls the pipeline because the data isn't ready yet, and a branch's target isn't known until partway through the pipeline, so naive designs either stalled on every branch or guessed and sometimes guessed wrong.

**Where it stands now.** Every mainstream general-purpose core (Intel Golden Cove/Redwood Cove, AMD Zen4/Zen5, Apple M-series, ARM Cortex-X) is deeply pipelined (14-20+ stages), superscalar (4-8 wide), and out-of-order, using a reorder buffer (ROB) to retire instructions in program order while executing them internally in whatever order their operands become ready. Branch prediction is now a multi-level, TAGE-style or perceptron-based predictor trained continuously on runtime behavior, hitting 95-99%+ on typical code. The live disagreement isn't "should we speculate" — everyone does — it's how far to push it given Spectre-class attacks: speculative execution that reads memory it shouldn't (past a branch that will be found mispredicted) can leave measurable microarchitectural side effects (cache state) even though the wrong-path instructions are architecturally squashed, and mitigations (retpolines, IBRS, page-table isolation) that close this cost real, measured throughput — commonly cited at 5-30% depending on workload and mitigation level. In-order, simpler cores haven't disappeared: they're the deliberate choice for power-constrained or real-time-predictable designs (many microcontrollers, some ARM little cores in big.LITTLE) precisely because a predictable in-order pipeline trades peak throughput for area, power, and worst-case-timing determinism that OoO cannot offer.

**Where it's heading.** The single-core frequency and IPC curve has been flat-ish for years (the end of easy Dennard scaling, ~2005-06), so the industry's direction of travel is width and heterogeneity rather than deeper speculation: wider decode/issue (Apple's M-series decodes 8-9 instructions/cycle, among the widest shipping), more execution ports, chiplet designs with heterogeneous core types (performance + efficiency cores, now standard from Intel 12th-gen onward and Apple's P/E cores), and increasingly specialized units (matrix/tensor extensions like Intel AMX, ARM SME) sitting next to the general-purpose pipeline specifically because general-purpose OoO speculation stops paying off for dense linear algebra — that's confidently true and already shipping. More speculative (lower confidence): whether new ISAs or capability architectures (CHERI) meaningfully change the speculative-execution security tradeoff industry-wide is still an open research question, not a shipped consensus.

---

## Mental model

Think of the pipeline as a 5-station assembly line where each station holds one instruction's work-in-progress, and hazards are the specific ways one instruction's station can block another's:

```
cycle:        1    2    3    4    5    6    7    8
instr 1:      IF   ID   EX   MEM  WB
instr 2:           IF   ID   EX   MEM  WB
instr 3:                IF   ID   EX   MEM  WB
instr 4 (branch dependent on instr 3's result):
                              IF?  <- don't know target until EX/MEM of instr 3
```

IF = fetch, ID = decode + register read, EX = ALU, MEM = memory access, WB = write back to register file. A data hazard is instr 2 needing a register instr 1 hasn't written back yet (fixed by *forwarding* the ALU result straight from instr 1's EX stage into instr 2's EX stage, skipping the register file). A control hazard is instr 4 not knowing whether to fetch the branch target or the fall-through until the branch resolves — fixed by *predicting* and speculatively continuing, then squashing everything fetched on a misprediction. OoO execution generalizes this: instead of one linear pipeline, picture a pool of instructions waiting in "reservation stations" for their operands to become ready, firing into whichever of several execution ports is free, while a reorder buffer keeps the illusion of in-order completion for anything that can observe it (interrupts, memory writes, and eventually the retired register file).

---

## How it actually works

### From gates to an ALU

A 1-bit full adder is built from XOR/AND/OR gates (sum = A⊕B⊕Cin, carry-out = majority(A,B,Cin)); chain 64 of them with the carry wired in series and you have a 64-bit ripple-carry adder — correct but slow, because the carry has to propagate through 64 gate-delays. Real ALUs use carry-lookahead or carry-select adders that compute carries for multiple bit-groups in parallel, trading transistor count for a shorter critical path, which is a direct preview of the space/time tradeoff that shows up at every level above this one too. The ALU itself is a mux-selected bank of these functional units (adder, shifter, logic unit) controlled by the opcode's function-select bits.

### Pipelining and hazards, with numbers

The classic 5-stage pipeline's whole value proposition is throughput: ideally one instruction retires per cycle once the pipeline is full, versus one instruction per 5 cycles unpipelined — a 5x throughput improvement in principle, eroded in practice by hazards and pipeline flushes. Real cores today are 14-20+ stages deep (Intel Skylake-class is roughly 14-19 stages depending on how you count the frontend, AMD Zen designs are in a similar range) specifically to allow higher clock frequencies — each pipeline stage does less work, so the clock period (which must accommodate the slowest stage) shrinks.

**Data hazards** are handled by forwarding/bypassing networks that route a just-computed ALU result directly to a dependent instruction's input, avoiding a stall. The one hazard forwarding cannot fully hide is load-use latency: a load's data isn't available until it returns from the memory hierarchy (L1 hit latency is commonly 4-5 cycles on modern x86 cores), so an instruction immediately consuming a load's result stalls for that latency regardless of forwarding — this is exactly why compilers and JITs try to schedule independent work between a load and its first use.

**Control hazards** are the reason branch prediction exists at all: a mispredicted branch on a 19-stage pipeline means everything fetched down the wrong path (potentially 15-20+ instructions' worth of pipeline state) has to be squashed and refetched from the correct target, which is the concrete meaning of "misprediction penalty ≈ 15-20 cycles" quoted for modern cores. At a 1% misprediction rate on a branch-heavy workload (roughly one branch per 5-6 instructions in typical code), that's a real, measurable throughput tax; at 5-10% (a genuinely unpredictable branch, e.g. `if (rand() % 2)` in a loop, or a data-dependent branch over unsorted input) it can cut IPC by half or more. Branch predictors are TAGE-family (Tagged Geometric history length) or perceptron-based in modern high-end cores, using multiple tables of different history lengths to capture both short-range and long-range correlation in branch behavior, and they achieve 95-99%+ accuracy on real integer/control-flow-heavy code — the famous "sorted array is faster to branch over" demo (branchmisprediction.com-style benchmarks) typically shows a 2-6x slowdown on unsorted data purely from misprediction, no cache effects involved.

**Structural hazards** (two instructions wanting the same functional unit or port in the same cycle) are handled by duplicating scarce resources — modern cores have multiple ALU ports (commonly 4+ integer ALU ports plus separate load/store ports on high-end designs) specifically to reduce how often this stalls issue.

### Speculative execution and out-of-order, concretely

OoO execution decouples *program order* from *execution order* using three structures worth naming precisely: **reservation stations** (or a unified scheduler) hold decoded instructions until their operands are ready; a **reorder buffer (ROB)** tracks every in-flight instruction in original program order so results can be committed (retired) in order even though they executed out of order — ROB sizes on recent high-end cores are large (Intel Golden Cove ~512 entries, AMD Zen4 ~320 entries, both up sharply from ~100-200 a decade earlier, which directly reflects how much "instruction window" the core searches for independent work); and **register renaming** maps architectural registers onto a larger physical register file so that false dependencies (write-after-write, write-after-read on the same architectural register from unrelated instructions) don't block parallelism.

Speculative execution rides on top of this: the core predicts a branch, keeps fetching and *executing* down the predicted path using OoO machinery, and only commits those results at retirement once the branch actually resolves as correctly predicted. If it mispredicts, every speculatively executed instruction past that branch is flushed from the ROB and its architectural effects are discarded — but its *microarchitectural* effects (what it pulled into cache, what it trained a predictor with) are not automatically undone, which is precisely the side channel Spectre (2018) exploited: a mistrained branch predictor could be coerced into speculatively executing a memory read using attacker-influenced data, and even though the read's result was architecturally discarded, its cache-timing footprint was measurable and leaked the data.

### Superscalar width and SIMD

Superscalar cores fetch/decode/issue multiple instructions per cycle — modern high-end designs are commonly 4-6 wide (Zen4/Zen5, Golden Cove class) with Apple's M-series pushing to 8-9 wide decode, which matters because decode width caps the best-case IPC regardless of how deep the OoO window is. SIMD (Single Instruction, Multiple Data) is an orthogonal lever: instead of parallelizing across different instructions, one instruction operates on a vector register holding multiple data elements — SSE (128-bit, 4x fp32), AVX2 (256-bit, 8x fp32), AVX-512 (512-bit, 16x fp32) — so a vectorized loop can process 8-16x the data per instruction versus scalar code, provided the data is contiguous, aligned, and the loop has no cross-iteration dependency the vectorizer can't break. This is why a hand-vectorized or auto-vectorized numeric kernel can be an order of magnitude faster than the "equivalent" scalar C loop even at identical clock speed and even before considering cache effects — it's pure instruction-level data parallelism.

---

## Build it from scratch

A full pipeline simulator is out of scope for one sitting, but a minimal in-order 5-stage pipeline simulator with hazard detection proves the model is understood rather than memorized as a diagram:

```python
# untested sketch — models forwarding + a single load-use stall, not full OoO
from dataclasses import dataclass, field

@dataclass
class Instr:
    op: str; dst: str = None; src1: str = None; src2: str = None; is_load: bool = False

class Pipeline:
    STAGES = ["IF", "ID", "EX", "MEM", "WB"]

    def __init__(self, instrs):
        self.instrs = instrs
        self.cycle = 0
        self.stalls = 0

    def run(self):
        # in_flight[i] = which stage instruction i is in this cycle, or None
        n = len(self.instrs)
        stage_of = [-1] * n  # -1 = not yet issued
        i = 0
        history = []
        while i < n or any(0 <= s < 5 for s in stage_of):
            self.cycle += 1
            # advance everyone already in flight
            for j in range(n):
                if 0 <= stage_of[j] < 4:
                    stage_of[j] += 1
                elif stage_of[j] == 4:
                    stage_of[j] = 5  # retired
            # try to issue next instruction into IF, unless a load-use hazard blocks it
            if i < n:
                cur = self.instrs[i]
                blocked = False
                if i > 0:
                    prev = self.instrs[i - 1]
                    # load-use hazard: prev is a load, cur reads prev's dst, and
                    # prev hasn't reached MEM yet (data not ready without a stall)
                    if prev.is_load and prev.dst in (cur.src1, cur.src2) and stage_of[i - 1] < 3:
                        blocked = True
                        self.stalls += 1
                if not blocked:
                    stage_of[i] = 0
                    i += 1
            history.append(list(stage_of))
        return history, self.cycle, self.stalls

instrs = [
    Instr("LD", dst="r1", is_load=True),
    Instr("ADD", dst="r2", src1="r1", src2="r3"),   # load-use hazard on r1
    Instr("SUB", dst="r4", src1="r5", src2="r6"),
]
p = Pipeline(instrs)
_, cycles, stalls = p.run()
print(f"cycles={cycles} stalls={stalls}")  # stalls>0 shows the load-use bubble
```

The point of writing this out is the same as the TCP state machine exercise: the assertions about *when* a hazard exists (same register, producer not yet far enough along) are exactly what an interviewer probes when they ask "why can't forwarding fix a load-use hazard the same way it fixes an ALU-to-ALU dependency."

---

## How it's done in production

You don't hand-schedule pipelines; you write code that cooperates with what the hardware already does, and you diagnose problems with `perf stat`/`perf record` (Linux) or Instruments (macOS) reading hardware performance counters.

| Symptom | Cause | Fix |
|---|---|---|
| `perf stat` shows IPC ~0.5-0.8 despite low cache-miss rate | Long serial dependency chain (each instruction waits on the previous one's result) that OoO can't parallelize regardless of window size | Break the chain: use multiple accumulators in a reduction loop instead of one running sum, so independent partial sums can execute on different ports simultaneously |
| `perf stat` shows high `branch-misses` (e.g. >5%) on a hot loop | Data-dependent branch over unpredictable input (unsorted data, random control flow) | Replace the branch with branchless code (conditional move, bitmask select) or sort/partition data so the branch becomes predictable |
| Auto-vectorization report (`-fopt-info-vec-missed` in GCC/Clang) shows a hot loop wasn't vectorized | A loop-carried dependency, unclear aliasing (compiler can't prove pointers don't overlap), or a function call inside the loop the vectorizer won't inline | Add `restrict`/`__restrict` to disambiguate pointers, hoist function calls out, or manually vectorize with intrinsics as a last resort |
| Throughput regresses after a kernel/OS security update with no code change | Spectre/Meltdown mitigations (retpolines, IBRS/IBPB, page-table isolation) disable or throttle speculative execution paths | Usually not worth "fixing" by disabling mitigations; measure the actual regression (commonly single-digit to ~30% depending on workload) and treat it as a cost of doing business, or isolate genuinely trusted workloads onto unmitigated, physically isolated hardware if the threat model allows it |
| A tight loop is fast in isolation but slow inside a larger binary | Instruction-cache pressure or a decode-width bottleneck from surrounding code polluting the frontend, not the loop's own logic | Profile with `perf record -e instructions,branch-misses` around the call site, not just the microbenchmark; consider `__attribute__((hot))`/PGO to help the compiler lay out code for icache locality |

---

## Tradeoffs & when NOT to use it

- **Don't assume more speculation/OoO window is free.** ROB and reservation-station area, and the power cost of executing instructions that get squashed, are real; this is precisely why efficiency cores (Intel E-cores, Apple E-cores, many mobile SoCs) deliberately ship narrower, shallower, more in-order-leaning designs — they trade peak single-thread IPC for area and power efficiency on background/parallel work, and that's the *correct* choice for that workload class, not a lesser one.
- **Don't hand-vectorize before you've confirmed the compiler didn't already do it.** Modern compilers auto-vectorize well-structured loops; reaching for intrinsics first is premature and produces code that's harder to maintain and port across ISAs (x86 AVX vs ARM NEON/SVE) for a gain the compiler may already have captured. Check the vectorization report before writing intrinsics.
- **Don't chase branch-prediction micro-optimizations in code that isn't actually hot.** Branchless tricks (bit masking instead of `if`) often *reduce* readability and can even be slower if the branch in question is already highly predictable (>99%) — the CPU's own predictor is good enough that "avoid branches" is not a universal rule, it's a targeted fix for measured, unpredictable branches only.
- **Don't reach for wider SIMD than your data actually supports.** AVX-512 downclocks some Intel cores under sustained heavy use (a real, measured effect on certain server parts), and small or non-contiguous data doesn't amortize the gather/scatter or alignment overhead — for genuinely small, branchy, pointer-chasing workloads, scalar or narrower SIMD can win.
- **This whole module is the wrong lens for I/O-bound or allocation-bound code.** If a service's bottleneck is network round-trips or GC pauses, micro-tuning branch predictability or vectorization is solving the wrong problem; profile first (see the memory-hierarchy and OS-internals modules) before assuming you're in microarchitecture-bound territory at all.

---

## Interview questions

### Q1 — What's the difference between pipelining and out-of-order execution?
**Testing:** whether these two independent concepts are conflated, a common gap.
**Answer:** Pipelining overlaps the *stages* of different instructions (fetch of instr N+1 while instr N decodes) but still executes instructions in program order through those stages. Out-of-order execution additionally lets independent instructions execute in a different order than the program specifies, as long as results are retired in original order via a reorder buffer — pipelining is about overlap, OoO is about reordering.
**Follow-up trap:** *"Can you have OoO without pipelining, or pipelining without OoO?"* — pipelining without OoO is exactly the classic 5-stage in-order RISC pipeline (very common, still used in simple/embedded cores); OoO without pipelining is essentially never built in practice because OoO's whole benefit compounds with pipelining's overlap, but conceptually they're separable.

### Q2 — Why can't forwarding fully eliminate a load-use hazard the way it eliminates an ALU-to-ALU dependency?
**Testing:** understanding that forwarding routes *already-computed* values, it doesn't manufacture data early.
**Answer:** Forwarding shortcuts a result from one pipeline stage's output directly to another instruction's input, skipping the register file — but it can only forward a value once it exists. An ALU result exists at the end of the EX stage, early enough to forward to the next instruction's EX stage with no bubble. A load's result doesn't exist until the MEM stage completes (after the L1 access latency), so an instruction immediately consuming that load's result in the very next cycle has nothing to forward yet — the pipeline must stall (bubble) for however many cycles the load's latency requires, commonly modeled as one stall cycle in the classic 5-stage pipeline, or several cycles of effective L1 latency (4-5 cycles) on real cores.
**Follow-up trap:** *"How does OoO execution mitigate this instead?"* — rather than stalling the whole pipeline, an OoO core lets independent, unrelated instructions execute from the reservation stations while the load-dependent instruction waits, so the load latency is *hidden* by useful work instead of *eliminated* — it's scheduling around the hazard, not shortening it.

### Q3 — Explain what a 2% branch misprediction rate actually costs on a 19-stage pipeline, with a rough number.
**Testing:** ability to connect predictor accuracy to a concrete throughput cost, not just recite "prediction reduces stalls."
**Answer:** Each misprediction flushes everything speculatively fetched down the wrong path — on a deep pipeline this penalty is commonly cited around 15-20 cycles. At roughly one branch per 5-6 instructions (typical for control-flow-heavy code) and a 2% misprediction rate, that's roughly 1 misprediction per 250-300 instructions, each costing ~15-20 cycles versus the ~1 cycle those instructions would otherwise take — a back-of-envelope estimate puts the overhead in the single-digit percent range of total cycles, which is measurable and exactly what shows up as reduced IPC in `perf stat`.
**Follow-up trap:** *"Would you expect a 2% or a 10% misprediction rate on a `switch` over a small enumerated set of common cases vs a hash-based dispatch?"* — a small, hot, well-trained `switch`/branch table on a stable value distribution often predicts far better than 2%, because the predictor learns the pattern; a hash-based dispatch with effectively random target addresses defeats prediction much more, closer to double-digit percent, because there's no learnable pattern to exploit — the predictor is pattern-matching runtime *history*, not analyzing code structure.

### Q4 — What is a reorder buffer, and why does its size matter for performance?
**Testing:** understanding the ROB as the mechanism that both enables OoO and bounds how much parallelism the core can discover.
**Answer:** The ROB tracks every instruction currently in flight in original program order, holding their results until they can be retired (committed to architectural state) in that same order, even though they may have executed out of order. Its size directly bounds the "instruction window" the core can search for independent work — a larger ROB (e.g. ~512 entries on Golden Cove vs ~320 on Zen4) lets the core look further ahead past a stalled instruction (like a cache-missing load) to find unrelated work to execute, which is exactly why ROB sizes have grown substantially over the past decade as memory latency (relative to core speed) has become the dominant bottleneck for many workloads.
**Follow-up trap:** *"Why not just make the ROB arbitrarily large?"* — ROB entries, plus the associated reservation stations, physical register file, and load/store queue entries all needed to support a larger window, cost real die area and power, and there are diminishing returns once the window exceeds what typical workloads' independent-work distance actually needs — it's a tuned tradeoff, not a knob you'd crank to infinity even with unlimited transistor budget.

### Q5 — Explain Spectre in one paragraph, mechanically, not just "it's a side-channel attack."
**Testing:** whether the candidate understands the actual mechanism (mistrained predictor + speculative memory access + cache timing), not just the buzzword.
**Answer:** An attacker mistrains a victim's branch predictor (or manipulates a bounds check) so that, when the victim's code hits a branch whose *correct* outcome would prevent an out-of-bounds or unauthorized read, the predictor instead guesses the wrong (attacker-favorable) outcome and the core speculatively executes down that path — including a memory read using attacker-influenced data as an index, and a subsequent access that depends on the read's value (e.g. indexing into a large array based on the leaked byte). Even though the branch is eventually resolved as mispredicted and the architectural results are discarded, the *cache state* left behind by the speculative access (which array line got pulled into cache) is not undone, and the attacker measures cache access timing afterward to infer which line was touched — reconstructing the leaked value one bit/byte at a time despite never architecturally "reading" it.
**Follow-up trap:** *"Why doesn't squashing the mispredicted instructions also undo this?"* — squashing discards *architectural* state (registers, memory writes) but has no obligation to undo *microarchitectural* state (cache lines pulled in, branch predictor tables updated, TLB entries touched) because that state was never part of the ISA's defined behavior — it's an implementation side effect, and that gap between "architecturally invisible" and "microarchitecturally invisible" is exactly the class of vulnerability Spectre/Meltdown opened up.

### Q6 — What's the difference between structural, data, and control hazards? Give one fix for each.
**Testing:** baseline vocabulary, checked for precision.
**Answer:** Structural hazard: two instructions need the same hardware resource in the same cycle (e.g. one memory port for both an instruction fetch and a data access) — fixed by duplicating resources (separate instruction/data caches, multiple ALU ports). Data hazard: an instruction needs a value another in-flight instruction hasn't produced yet — fixed by forwarding/bypassing for close dependencies, or by OoO scheduling/stalling for longer-latency producers like loads. Control hazard: the next instruction to fetch is unknown until a branch resolves — fixed by branch prediction plus speculative execution, with squash-and-refetch on misprediction.
**Follow-up trap:** *"Which of these three does increasing pipeline depth make worse, and why?"* — control hazards, specifically the misprediction penalty, scale directly with pipeline depth because a deeper pipeline means more speculatively-fetched instructions must be squashed on a misprediction — this is exactly why very deep pipelines (Intel's old NetBurst/Pentium 4, ~20-31 stages) put enormous pressure on branch prediction accuracy and were ultimately judged a bad tradeoff, contributing to the industry's return to shorter, wider designs post-2006.

### Q7 — A numeric loop summing a large float array is memory-bound, not compute-bound, on your hardware. How would you confirm that with `perf`, and does SIMD still help?
**Testing:** whether the candidate reaches for measurement instead of assuming, and understands SIMD's limits.
**Answer:** Run `perf stat -e cycles,instructions,cache-misses,cache-references` (or use `perf mem`/`toplev` methodology) — if cache-miss rate is high and IPC is low despite a simple loop, the bottleneck is memory bandwidth/latency, not ALU throughput. SIMD still helps up to the point where memory bandwidth saturates, because vectorized loads still have to move the same total bytes from memory, just processed in wider chunks per instruction — once the loop is bandwidth-bound, further widening SIMD (e.g. AVX2 to AVX-512) yields diminishing or zero returns because the ALUs are already waiting on data, not the reverse.
**Follow-up trap:** *"If AVX-512 gives no speedup here, is it a wasted feature?"* — no; it means *this specific loop* is memory-bound at this data size. The same instruction set would show a real speedup on a compute-bound kernel (e.g. one with more arithmetic per byte loaded, like a polynomial evaluation or FMA-heavy inner loop) — the right conclusion is "profile before concluding an ISA feature doesn't help," not "wide SIMD doesn't matter."

### Q8 — Why does branch-heavy code over sorted data run faster than the same code over unsorted data, holding the algorithm's complexity constant?
**Testing:** the canonical microarchitecture demo question; tests whether the answer stays mechanical rather than hand-wavy.
**Answer:** Sorting the data makes the branch's outcome sequence highly patterned (e.g. long runs of "taken" followed by long runs of "not taken" as values cross the comparison threshold) which a branch predictor learns and predicts near-perfectly; unsorted data makes the branch outcome effectively random relative to iteration, which no predictor can learn, driving misprediction rate up and paying the full pipeline-flush penalty repeatedly. This is a classic demonstration (often 2-6x observed slowdown) that has nothing to do with cache behavior if the data already fits in cache — it isolates branch prediction as the sole variable.
**Follow-up trap:** *"How would you fix the unsorted case without sorting the actual data (if order must be preserved)?"* — replace the branch with branchless logic (e.g. a conditional move, `x * (cond) + y * (1-cond)`, or bitmask-select), which trades a mispredictable branch for a small constant amount of always-executed arithmetic — worse than a well-predicted branch, but far better than a poorly-predicted one, because it removes the control hazard entirely rather than trying to predict it.

### Q9 — What is register renaming, and what specific hazard does it eliminate that forwarding cannot?
**Testing:** distinguishing renaming (false dependencies) from forwarding (true dependencies).
**Answer:** Register renaming maps the small set of architectural registers (e.g. x86-64's 16 general-purpose registers) onto a much larger physical register file, giving each *write* to an architectural register a fresh physical register. This eliminates write-after-write (WAW) and write-after-read (WAR) hazards — false dependencies that exist only because two unrelated instructions happen to reuse the same architectural register name, not because one instruction actually needs the other's data. Forwarding addresses true (read-after-write) dependencies where data genuinely must flow from producer to consumer; renaming addresses the *naming* collisions that would otherwise force serialization for no data-flow reason at all.
**Follow-up trap:** *"How large is the physical register file relative to the architectural one, roughly?"* — several times larger; modern high-end cores carry physical register files in the range of 200-300+ entries per file (integer and floating-point/vector typically separate) against only 16-32 architectural registers, and this ratio has grown alongside ROB size for the same reason — bigger instruction windows need more in-flight renamed destinations to track.

### Q10 — Design question: you have a hot reduction loop (`sum += arr[i]`) that shows IPC around 1.0 despite the core supporting 4+ ops/cycle and all data being L1-resident. What's wrong and how do you fix it?
**Testing:** staff-level ability to diagnose a dependency-chain bottleneck rather than assuming a cache or width problem.
**Answer:** A single running accumulator creates a strict serial dependency chain — each addition must wait for the previous addition's result, so no matter how wide the core is, only one addition can be in flight at a time, capping throughput at roughly the ALU's add latency (commonly ~1 cycle, but the *dependency*, not the width, is the bound). The fix is to break the chain into multiple independent partial sums (e.g. 4-8 accumulators, or let the compiler's auto-vectorizer do this via SIMD lanes acting as independent accumulators), summing them together only at the end — this lets the OoO scheduler and multiple ALU ports actually run additions in parallel, and lets the vectorizer treat it as a reducible pattern instead of a serial one.
**Follow-up trap:** *"Does using more accumulators change the numerical result for floating-point sums?"* — yes, potentially: floating-point addition isn't associative, so reordering into multiple partial sums can produce a slightly different rounding result than strict left-to-right summation. This is usually acceptable for a reduction over many similarly-scaled values, but it's a real, quotable caveat — not a purely free optimization — and matters more when values have wildly different magnitudes (see the numerics module on catastrophic cancellation).

### Q11 — What's the practical performance cost of Spectre/Meltdown mitigations, and when would you consider it acceptable to disable them?
**Testing:** staff/principal judgment on a real production tradeoff, not just knowing the mitigations exist.
**Answer:** Reported costs vary widely by workload and mitigation combination — commonly single digits for typical application code, up to 20-30%+ for syscall-heavy or virtualization-heavy workloads (page-table isolation specifically taxes syscall/context-switch-heavy code since it changes TLB behavior on privilege transitions). Disabling mitigations is only defensible when the threat model genuinely excludes the attack surface they close — e.g. a single-tenant, physically isolated batch-compute node running fully trusted code with no untrusted co-tenants and no untrusted code execution capability at all — and even then it should be a deliberate, documented, reviewed decision, not a default performance tweak, because the blast radius of getting the threat model wrong (leaking secrets across a security boundary) is categorically worse than the performance cost of leaving mitigations on.
**Follow-up trap:** *"Does disabling mitigations on a Kubernetes node with multiple tenants' pods ever make sense?"* — essentially no; multi-tenant scheduling is exactly the scenario these mitigations exist for (isolating one tenant's speculative execution side effects from another's secrets), and recommending disabling them there is a red flag, structurally identical to recommending `tcp_tw_recycle` for TIME_WAIT — a plausible-sounding "fix" that ignores why the safety mechanism exists.

---

## Red flags that fail you

- Saying "pipelining" and "out-of-order execution" interchangeably, or claiming OoO requires more pipeline stages (it doesn't; they're independent axes).
- Explaining Spectre as "a cache attack" without the mistrained-predictor-plus-speculative-read mechanism, or claiming squashing a misprediction undoes all its effects.
- Claiming forwarding eliminates all data hazards, including load-use — it cannot, because the value doesn't exist yet at forward-time.
- Reaching for hand-written SIMD intrinsics as a first move without checking whether the compiler already auto-vectorized the loop.
- Treating "add more branches" or "add more speculation" as free — ignoring the real area/power/security cost of larger ROBs, wider issue, and deeper speculation.
- Recommending disabling Spectre/Meltdown mitigations on shared/multi-tenant infrastructure as a default performance fix.

---

## Cheat card

```
PIPELINE: overlap stages (IF ID EX MEM WB), not reordering. 14-20+ stages on modern cores.
HAZARDS: structural (dup resource) | data (forward for ALU->ALU; load-use still stalls,
  L1 hit ~4-5 cycles) | control (branch outcome unknown -> predict + speculate)
OoO: reservation stations (wait for operands) + ROB (in-order retire) + register renaming
  (kills WAW/WAR false deps). ROB size: Golden Cove ~512, Zen4 ~320 entries.
BRANCH PREDICTION: TAGE/perceptron-class, 95-99%+ accuracy on real code.
  Misprediction penalty ~15-20 cycles on deep pipelines (flush + refetch).
SUPERSCALAR: 4-6 wide issue typical x86 (Golden Cove/Zen4), Apple M-series ~8-9 wide decode.
SIMD: SSE 128b(4xfp32) / AVX2 256b(8xfp32) / AVX-512 512b(16xfp32).
  Vectorization needs: contiguous data, no unresolved cross-iter dependency, no aliasing.
SPECTRE (2018): mistrained predictor -> speculative OOB/gated read -> cache-timing leak.
  Architectural squash != microarchitectural undo (cache state persists).
MITIGATION COST: retpolines/IBRS/KPTI ~single digits to 20-30%+ depending on workload,
  worst on syscall-heavy code. Never disable on multi-tenant infra.
DEPENDENCY CHAINS: serial accumulator caps IPC near 1 regardless of core width.
  Fix: multiple independent accumulators (changes FP rounding, not free numerically).
```

## Sources

- [Python support for free threading — Python 3.14 documentation](https://docs.python.org/3/howto/free-threading-python.html) — accessed 2026-08-03 (context on where speculative/parallel execution tradeoffs recur at the runtime level, referenced across this track)
- Hennessy & Patterson, *Computer Architecture: A Quantitative Approach* — canonical primary source for pipelining, hazards, and OoO fundamentals
- [The JVM Garbage Collector Decision in 2026 — Java Code Geeks](https://www.javacodegeeks.com/2026/04/the-jvm-garbage-collector-decision-in-2026-g1-vs-zgc-vs-shenandoah-for-real-workloads.html) — accessed 2026-08-03 (cross-referenced for current hardware-generation context)
- Kocher et al., "Spectre Attacks: Exploiting Speculative Execution," IEEE S&P 2019 (original Spectre paper)
- Intel 64 and IA-32 Architectures Optimization Reference Manual — microarchitecture and port/latency details for recent Intel cores
- AMD Software Optimization Guide for the Zen4 Microarchitecture — ROB/issue-width specifics for AMD cores

## Changelog
- 2026-08-03 — created
