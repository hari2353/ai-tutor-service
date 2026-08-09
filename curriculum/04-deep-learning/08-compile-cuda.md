# torch.compile Internals: Dynamo, Inductor, the CUDA Mental Model, and a First Triton Kernel

> **Track:** T04 Deep Learning · **Time:** 2.5h · **Prereqs:** T04-distributed-training, T16-gpu-arch · **Updated:** 2026-08-03
> **Module id:** `T04-compile-cuda` · **Tags:** performance
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

`torch.compile` is a four-stage pipeline that turns ordinary eager PyTorch code into fused, hardware-specific kernels without you rewriting anything: **Dynamo** hooks into CPython's frame evaluation API to trace your Python function as it actually executes, capturing an FX graph of the underlying ATen tensor operations while attaching **guards** (runtime checks on tensor shape/dtype/device and certain Python values) that must hold true for the captured graph to be safely reused on a later call — a guard failure triggers a recompilation, and Python constructs Dynamo can't trace at all (data-dependent control flow, calls into un-traceable libraries) trigger a **graph break**, falling back to eager execution for that portion before resuming tracing afterward, which doesn't crash but does shrink how much can be fused and optimized around the break. **AOTAutograd** then traces the forward and backward passes together ahead of time (running both once to record their joint computation graph, letting the backward pass be optimized with the same knowledge of the forward as the forward pass itself). **Inductor**, the default backend, lowers that joint graph into actual code — generating fused Triton kernels for GPU targets (or C++/OpenMP for CPU) — performing the exact kernel-fusion optimization that `T16-gpu-arch` motivates (combining multiple small operations into fewer, larger kernel launches to amortize the ~3-10μs fixed launch overhead and avoid redundant intermediate round-trips through HBM). Triton itself is a Python-embedded language and compiler that lets you write a GPU kernel by describing computation over "blocks" of data rather than manually managing individual CUDA threads, shared memory, and warp-level synchronization — the compiler handles that mapping; a minimal, complete, correct Triton vector-add kernel is about a dozen lines: compute a `program_id`-based block offset, build a mask for the tail of the array that doesn't fill a whole block, `tl.load` both inputs with that mask, add them, and `tl.store` the result — for `n_elements=10000` and `BLOCK_SIZE=1024`, the launch grid is `ceil(10000/1024)=10` blocks, with the 10th block's mask filtering out the `240` out-of-bounds lanes (`10*1024=10240 - 10000 = 240`) so it doesn't read or write past the array's end.

## Why this gets asked

Because `torch.compile` (introduced as PyTorch 2.0's flagship feature and standard practice for performance-sensitive training and inference by 2026) is the single highest-leverage "make it faster with one line of code" tool available to most ML engineers, and interviewers want to know whether you understand what it's actually doing well enough to debug it when the speedup doesn't materialize — a silent, frequent graph break, an expensive recompilation storm from dynamic shapes, or a custom op Inductor can't fuse are all real, common production issues that "just add `torch.compile()` and hope" doesn't help you diagnose. It's also a natural bridge to systems-level engineering credibility: understanding that a GPU kernel is fundamentally "load data, compute, store data" and that Triton exposes that at the block level rather than the individual-thread level is what separates someone who can write a first custom kernel from someone who treats all GPU code as an unopenable black box.

---

## Lineage: past → present → future

**What came before.** Before `torch.compile` (PyTorch 2.0, 2023), getting meaningful speedups beyond eager execution meant either hand-writing custom CUDA kernels (powerful but requiring genuine CUDA C++ expertise, a steep and narrow skill largely inaccessible to most ML engineers) or using `torch.jit.script`/`torch.jit.trace` (TorchScript, PyTorch's earlier compilation attempt), which required rewriting code into a restricted, traceable subset of Python and frequently broke on the exact dynamic control flow that made eager PyTorch pleasant to write in the first place — a real, frustrating tradeoff between "fast but hard to write/debug" and "easy but leaves real performance on the table." The pain this created: most PyTorch code shipped to production simply ran in slow, unfused eager mode, paying the per-operation kernel-launch overhead (`T16-gpu-arch`'s ~3-10μs per launch) and redundant HBM round-trips for every individual operation, because the alternative (TorchScript, or hand-written CUDA) cost too much engineering effort for most teams to adopt broadly.

**Where it stands now.** `torch.compile`'s Dynamo+AOTAutograd+Inductor pipeline solves the core adoption problem TorchScript couldn't: it traces *actual, unmodified* eager Python code (via CPython's frame evaluation API, not a restricted subset), falling back gracefully (a graph break, not a hard failure) whenever it hits something it can't trace, which makes partial adoption cheap and low-risk — you can `torch.compile()` a model with zero source changes and get real speedup on the parts that trace cleanly. As of PyTorch 2.9 (2026), the ONNX exporter defaults to the Dynamo-based export pipeline as well, and continued Dynamo/Inductor improvements (finer-grained graph-break control via `torch._dynamo.error_on_graph_break()`, expanding hardware wheel-variant support to AMD ROCm and Intel XPU alongside NVIDIA CUDA) reflect `torch.compile` becoming the default performance path across the ecosystem, not a specialized opt-in. Triton, meanwhile, has become the de facto standard way to write custom GPU kernels in Python for exactly the workloads that motivate custom kernels in modern deep learning (fused attention variants, custom quantized matrix multiplies) — it's also literally the backend Inductor itself generates code in, so understanding Triton directly demystifies what `torch.compile` produces under the hood, rather than being a separate, unrelated skill.

**Where it's heading.** PyTorch 2.10 (2026) extends `torch.compile` support further (Python 3.14 support, combo-kernel fusion, `LocalTensor` for distributed debugging), continuing the trajectory of making more of the ecosystem — including distributed training primitives — compilable rather than only single-GPU eager-style code. The live disagreement/frontier is less about whether to compile (that's settled — compile by default, fall back only where genuinely necessary) and more about *how much* of a complex, dynamic-control-flow-heavy model (e.g., a full LLM serving stack with speculative decoding, dynamic batching, and KV-cache management) can be brought under a single compiled graph without excessive graph breaks, and how gracefully the tooling reports *why* a given piece of code didn't compile as expected — better graph-break diagnostics and wider operator coverage remain active, ongoing engineering investment rather than a finished feature.

---

## Mental model

```
EAGER PYTHON CODE
     |
     v   Dynamo: hooks CPython's frame evaluation API, traces AS THE CODE RUNS
  FX GRAPH (of ATen ops) + GUARDS (shape/dtype/device/value assumptions)
     |         \
     |          \-- if code Dynamo CAN'T trace (data-dependent control flow,
     |               untraceable library call) --> GRAPH BREAK: fall back to
     |               EAGER for that piece, resume tracing after it
     v
  AOTAutograd: traces FORWARD + BACKWARD together, ahead of time, once
     |
     v
  INDUCTOR (backend compiler): lowers the joint graph to actual generated code
     |         \
     |          \--> GPU target: generates FUSED TRITON KERNELS
     |          \--> CPU target: generates C++/OpenMP code
     v
  COMPILED, FUSED KERNELS RUN  <-- fewer kernel launches, fewer HBM round-trips
                                    (exactly the T16-gpu-arch fusion argument)

  GUARD FAILS on a later call (e.g. different input shape)
     -> RECOMPILE (cached per distinct guard combination -- too many distinct
        shapes = "recompilation storm", mitigated by marking dims DYNAMIC)

TRITON KERNEL = describe computation over a BLOCK of data, not individual threads
  (block_start, offsets = block_start + arange(BLOCK_SIZE), MASK for the tail)
  tl.load(ptr + offsets, mask) -> compute -> tl.store(ptr + offsets, mask)
  compiler handles mapping this block-level description to actual GPU threads/warps
```

The one-line mental model: **`torch.compile` is "trace what your eager code actually does, verify with cheap runtime guards that it's still safe to reuse that trace, and hand the resulting graph to a compiler that fuses and codegens it into real (usually Triton) kernels" — and Triton itself is exactly that same "describe a block, let the compiler map it to hardware" idea, applied directly to writing a GPU kernel by hand.**

---

## How it actually works

### Dynamo: tracing real Python, not a restricted subset

Dynamo hooks into CPython's frame evaluation API — a genuine interpreter-level hook that lets it observe and intercept Python bytecode execution — which is what lets it trace *actual*, unmodified eager code (including much of the dynamic control flow that made TorchScript's more restricted tracing/scripting approach brittle), rather than requiring code to be rewritten into a specially-supported subset. As your function runs under Dynamo, it records the sequence of underlying ATen tensor operations into an FX graph, and — critically — attaches **guards**: cheap runtime checks (tensor shape, dtype, device, and certain Python-level values the traced code branched on) that must all still hold true for that captured graph to be safely reused unchanged on a subsequent call. If a guard fails (e.g., an input tensor's shape changed from what was traced), Dynamo triggers a **recompilation** for the new shape/condition, caching graphs per distinct guard combination — a workload whose input shapes vary on nearly every call (e.g., genuinely variable-length sequences with no padding/bucketing) can trigger a "recompilation storm," paying compilation cost repeatedly instead of amortizing it, which is exactly why marking specific dimensions as dynamic ahead of time (compiling once for a *range* of shapes rather than one exact shape) is the standard mitigation.

### Graph breaks: not a crash, but a real, measurable cost

When Dynamo encounters Python code it genuinely cannot trace into the graph — data-dependent control flow whose branch depends on an actual tensor *value* (not just its shape/dtype), a call into a library with no tracing support, or certain unsupported operations — it inserts a **graph break**: the untraceable portion runs in ordinary eager mode, and Dynamo resumes tracing a fresh graph immediately after it. This is a deliberate, graceful-degradation design choice (the whole point is that adopting `torch.compile` shouldn't require rewriting code to avoid ever triggering one), but it has a real cost: each graph break is a boundary Inductor cannot fuse or optimize across, so a model with frequent graph breaks gets meaningfully less benefit from compilation than one that traces as a single large graph — `torch._dynamo.error_on_graph_break()` (a context manager/decorator, distinct from the stricter `fullgraph=True` which cannot be toggled back off once set) lets you explicitly mark regions where a graph break should raise an error instead of silently falling back, specifically to catch performance-costing breaks during development rather than discovering them only via a disappointing benchmark.

### AOTAutograd: tracing forward and backward together, ahead of time

Rather than compiling only the forward pass and leaving the backward pass to ordinary eager autograd (per `T04-autograd`'s dynamic graph construction), AOTAutograd runs the forward pass once (under tracing) specifically to *also* derive the backward pass's computation graph ahead of time, producing a joint forward+backward representation before any actual training step runs. This matters because it lets Inductor apply the same fusion/optimization reasoning to the backward pass that it applies to the forward pass — an activation needed for a backward-pass gradient computation (per the outer-product weight-gradient formula from `T04-backprop-derivation`) can be scheduled and potentially fused with awareness of exactly how and when the backward pass will consume it, rather than treating the backward pass as an opaque, separately-executed black box the way plain eager-mode autograd does.

### Inductor: the actual code generator, and why it targets Triton for GPU

Inductor takes the joint FX graph AOTAutograd produced and lowers it into real, executable code — for GPU targets, this means generating **Triton** kernels directly; for CPU targets, C++ with OpenMP parallelization. The single most valuable optimization Inductor applies is **operator fusion**: combining a chain of elementwise or otherwise fusable operations (e.g., a matrix multiply followed by a bias add followed by a GELU activation) into *one* generated kernel, rather than the three-or-more separate kernel launches eager execution would perform — this is precisely the kernel-fusion argument from `T16-gpu-arch`: fewer kernel launches means less fixed per-launch overhead paid, and fusing operations means intermediate results stay in registers/shared memory rather than making redundant round trips out to and back from HBM between each separately-launched kernel. Inductor targeting Triton specifically (rather than emitting raw CUDA C++ directly) means the same generated-kernel approach can retarget other accelerators with Triton backends, and — usefully for anyone debugging performance — the Triton kernels Inductor generates are themselves inspectable Python-embedded code, not an opaque binary.

### The CUDA/GPU execution model, at the level a Triton kernel actually needs

A full treatment of SMs, warps, and occupancy is `T16-gpu-arch`'s job; the specific piece needed to write a first Triton kernel is this: a GPU kernel launch consists of a **grid** of **blocks** (in Triton's vocabulary, "programs"), each executing the *same* kernel code but over a different slice of the data, and each block executes across many GPU threads in parallel following the warp/SIMT execution model `T16-gpu-arch` derives in full. Triton's key ergonomic idea is that you write the kernel body describing what happens to **one block's worth of data** — a contiguous chunk, addressed via an offset computed from that block's `program_id` — and never manually address individual threads, manage shared memory placement, or handle warp-level synchronization; the Triton compiler handles mapping that block-level description down to actual threads and hardware. This is a genuinely different abstraction level from raw CUDA C++ (which requires exactly that manual thread/shared-memory management) while still producing kernels competitive with hand-optimized CUDA for many real workloads, which is exactly why Triton (not raw CUDA) is the practical entry point for most ML engineers writing a custom kernel today.

### A minimal, complete, correct Triton kernel: vector addition

```python
import torch
import triton
import triton.language as tl

@triton.jit
def add_kernel(x_ptr, y_ptr, output_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)                       # which block am I?
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)   # this block's slice of the array
    mask = offsets < n_elements                        # guard against reading past the end
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)
    output = x + y
    tl.store(output_ptr + offsets, output, mask=mask)

def add(x: torch.Tensor, y: torch.Tensor):
    output = torch.empty_like(x)
    n_elements = output.numel()
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n_elements, BLOCK_SIZE),)       # ceil(n_elements / BLOCK_SIZE) blocks
    add_kernel[grid](x, y, output, n_elements, BLOCK_SIZE=BLOCK_SIZE)
    return output
```
**Worked launch-configuration example**: for `n_elements=10000` and `BLOCK_SIZE=1024`, the grid size is `triton.cdiv(10000, 1024) = 10` blocks (since `9*1024=9216 < 10000 ≤ 10*1024=10240`). The 10th block (`pid=9`) computes `block_start=9216`, `offsets=[9216..10239]` — but only indices `9216..9999` are valid (`784` valid elements in that last block), so `mask = offsets < 10000` is `False` for the trailing `10240-10000=240` out-of-bounds offsets, and `tl.load`/`tl.store` skip those lanes entirely rather than reading or writing past the array's actual allocated length. This mask pattern — compute a block's offsets, mask off whatever exceeds the true data size — is the standard, load-bearing idiom in essentially every Triton kernel handling data whose size isn't a clean multiple of `BLOCK_SIZE`.

---

## Build it from scratch

The vector-add kernel above **is** the from-scratch exercise for this module's Triton component; the lab (`labs/python/08-compile-cuda/`) extends it two ways: (1) benchmark it against `torch.add` (eager) and `torch.compile(torch.add)` across several tensor sizes, confirming correctness (`torch.allclose`) and comparing throughput; (2) write a slightly more involved fused kernel (e.g., a fused multiply-add, or a simple fused elementwise activation) and inspect the Triton/generated code `torch.compile` itself produces for an equivalent small PyTorch function (via `TORCH_LOGS="output_code"` or the equivalent current debugging environment variable) to directly compare a hand-written kernel against what Inductor generates automatically for the same computation.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| `torch.compile` applied to a model produces little to no measured speedup | Frequent graph breaks fragmenting the model into many small, separately-executed (uncompiled or separately-compiled) pieces, preventing Inductor from fusing across them | Use `torch._dynamo.error_on_graph_break()` (or `fullgraph=True` for a stricter check) during development to surface exactly where and why breaks occur, then restructure the offending code (often data-dependent control flow) to avoid them where feasible |
| A model with variable-length inputs recompiles constantly, with compilation time dominating total runtime | Each distinct input shape triggers a new guard failure and a fresh recompilation ("recompilation storm") | Mark the varying dimension(s) as dynamic (compiling once for a range of shapes) rather than letting Dynamo specialize a fresh graph per exact shape, or bucket/pad inputs to a small fixed set of shapes |
| A custom `torch.autograd.Function` or third-party op causes compilation to silently fall back to eager for a large portion of the model | The custom op has no registered tracing/decomposition support Dynamo/AOTAutograd can trace through | Register appropriate tracing support for the custom op if performance there matters, or accept the graph break if that portion is not performance-critical |
| A hand-written Triton kernel produces incorrect output only for input sizes not evenly divisible by `BLOCK_SIZE` | Missing or incorrect masking — reading/writing past the true data length for the final, partially-filled block | Always compute a mask (`offsets < n_elements` or equivalent) and pass it to every `tl.load`/`tl.store` call operating on that block's offsets |
| GPU kernel profiling shows many small, separate kernel launches for a chain of simple elementwise operations even after adding `torch.compile` | Graph break(s) between those operations preventing Inductor from fusing the whole chain into one kernel, or the operations were never actually routed through the compiled path | Profile (Nsight Systems or equivalent, per `T16-gpu-arch`) to confirm the operations are inside the compiled region at all, and check for graph breaks specifically around that chain |

---

## Tradeoffs & when NOT to use it

- **Don't assume `torch.compile()` is a free, zero-risk speedup for every model.** Compilation itself has real fixed cost (the first call to a compiled function pays tracing and codegen time), which matters for very short-lived processes or workloads where the model runs only a handful of times; for a model that will run for many iterations (training, or a long-lived inference server), that fixed cost amortizes away, but it's a real, non-zero consideration for short-lived jobs.
- **Don't fight graph breaks reflexively if the broken-out portion isn't performance-critical.** Not every graph break is worth restructuring code to avoid — a graph break around a small, rarely-executed piece of logic (e.g., an occasional logging/debugging branch) costs little; reserve the effort of eliminating graph breaks for the hot path where fusion actually matters.
- **Don't hand-write Triton kernels for operations Inductor already fuses well automatically.** Writing a custom kernel is worthwhile specifically when you need something Inductor's automatic fusion doesn't produce (a specific novel fusion pattern, a specialized memory access pattern, an operation with no existing efficient implementation) — for standard elementwise chains and common patterns, `torch.compile` alone frequently matches or beats a quickly hand-written kernel with far less engineering effort.
- **Don't mark every dimension dynamic by default to avoid recompilation.** Dynamic shape support has its own real cost (less shape-specific optimization opportunity for Inductor, since it must generate code correct across a range rather than optimal for one exact shape) — mark dimensions dynamic specifically where genuine shape variability is expected and recompilation storms are a real, measured problem, not preemptively for every model.

---

## Interview questions

### Q1 — What does Dynamo actually do, mechanically, and how is that different from what TorchScript's `torch.jit.script` did?
**Testing:** the specific tracing mechanism, not "Dynamo compiles PyTorch code."
**Answer:** Dynamo hooks into CPython's frame evaluation API to observe and trace bytecode as ordinary, unmodified eager Python code actually executes, recording the underlying ATen operations into an FX graph and attaching runtime guards on the assumptions (shapes, dtypes, certain Python values) that must hold for that trace to be safely reused. `torch.jit.script` instead required rewriting code into a restricted, statically-analyzable subset of Python ahead of time, which frequently broke on genuinely dynamic control flow that Dynamo's runtime, execution-based tracing handles by falling back gracefully (a graph break) instead of failing outright.
**Follow-up trap:** *"If Dynamo traces real, unmodified Python, why does it still need guards at all?"* — because a single trace captured for one specific call's shapes/dtypes/branch outcomes isn't necessarily valid for a different call with different shapes or a different data-dependent branch outcome — guards are exactly the runtime check that a previously-traced graph is still safe to reuse for the current call, triggering a recompilation when they fail rather than silently reusing an invalid trace.

### Q2 — What is a graph break, and why is it a "cost" rather than a "failure"?
**Testing:** the graceful-degradation design and its real performance implication.
**Answer:** A graph break happens when Dynamo encounters Python code it cannot trace into the graph (data-dependent control flow on an actual tensor value, an untraceable library call) — it runs that portion in ordinary eager mode and resumes tracing a fresh graph immediately after. It's not a failure (the program still runs correctly), but it is a real cost: Inductor cannot fuse or optimize across a graph break boundary, so a heavily-broken-up model gets meaningfully less benefit from compilation than one traced as a single large graph.
**Follow-up trap:** *"How would you find out where and why graph breaks are happening in a specific model, rather than just observing disappointing overall speedup?"* — use `torch._dynamo.error_on_graph_break()` (or the stricter `fullgraph=True`) during development to make a graph break raise an explicit error at the exact point it would otherwise silently occur, surfacing the specific code and reason rather than inferring it indirectly from benchmark numbers alone.

### Q3 — Why does a workload with highly variable input shapes sometimes get *worse* performance with `torch.compile` than without it?
**Testing:** the recompilation-storm failure mode, a genuine and common production gotcha.
**Answer:** Each distinct combination of guarded values (notably input shape) that Dynamo hasn't seen before triggers a fresh recompilation, and compilation itself has real, nontrivial cost — if input shapes vary on nearly every call with no shape reuse, the model recompiles repeatedly instead of amortizing one compilation's cost over many calls, and total time can end up dominated by compilation rather than the (now-compiled) execution itself.
**Follow-up trap:** *"What's the standard mitigation, and does it have its own cost?"* — mark the varying dimension(s) as dynamic, so Dynamo compiles once for a *range* of shapes rather than specializing a fresh graph per exact shape — the cost is that Inductor must generate code correct across that whole range rather than maximally optimized for one exact shape, typically leaving some shape-specific optimization opportunity on the table relative to a fully-specialized (but constantly-recompiling) approach.

### Q4 — What does AOTAutograd add on top of what Dynamo alone provides?
**Testing:** distinguishing graph capture (Dynamo) from ahead-of-time joint forward/backward tracing (AOTAutograd), a commonly conflated distinction.
**Answer:** Dynamo captures a graph of the forward computation as it's traced; AOTAutograd additionally runs the forward pass once specifically to derive the *backward* pass's computation graph ahead of time as well, producing a joint forward+backward representation before any real training step executes — this lets Inductor apply its fusion/scheduling optimizations to the backward pass with the same graph-level knowledge it has of the forward pass, rather than treating backward as an opaque, separately-executed eager computation the way plain autograd (`T04-autograd`) would.
**Follow-up trap:** *"Why does having the backward graph available ahead of time specifically help fusion, connecting to the outer-product weight-gradient formula from the backprop module?"* — because Inductor can see which activations the backward pass's weight-gradient computation (`dL/dW = (dL/dz)xᵀ`) will actually need, and schedule/fuse the forward pass's computation with that future need in mind (e.g., choosing what to keep resident versus recompute), rather than the forward pass being compiled in total ignorance of what the (separately, eagerly-executed) backward pass will later require.

### Q5 — Explain what "operator fusion" means concretely, and connect it directly to the kernel-launch-overhead argument from the GPU architecture module.
**Testing:** whether the fusion benefit is understood mechanically, not just as a buzzword.
**Answer:** Operator fusion combines a chain of operations (e.g., matmul, then bias-add, then GELU) that would otherwise each launch as a separate GPU kernel into a *single* generated kernel that performs all three in sequence without writing intermediate results back to HBM between them. This directly addresses `T16-gpu-arch`'s two costs: the fixed per-kernel-launch overhead (roughly 3-10μs, paid once per launch regardless of how little work that kernel does) is now paid once instead of three times, and the intermediate results (the matmul's raw output, the biased-but-not-yet-activated output) stay in registers/shared memory instead of making two redundant round trips out to and back from HBM.
**Follow-up trap:** *"Would fusing an already very large, already compute-bound kernel with a tiny subsequent operation still help much?"* — much less so — the benefit of fusion is largest precisely when the operations being fused are individually small relative to fixed launch overhead and HBM round-trip cost (the memory-bandwidth-bound regime `T16-gpu-arch` describes); fusing a huge, already compute-bound matmul with one small following op saves one launch and one round-trip, a much smaller fraction of that kernel's already-large total cost.

### Q6 — Write and explain a minimal Triton vector-add kernel, including the role of the mask.
**Testing:** actual working knowledge of Triton's core idiom, not just familiarity with the name.
**Answer:** `pid = tl.program_id(axis=0)` identifies which block this kernel instance handles; `offsets = pid*BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)` computes that block's slice of indices into the arrays; `mask = offsets < n_elements` marks which of those offsets are actually within the array's bounds (needed because `n_elements` usually isn't an exact multiple of `BLOCK_SIZE`); `tl.load`/`tl.store` take that mask so out-of-bounds lanes are skipped rather than reading/writing past the allocated array.
**Follow-up trap:** *"For n_elements=10000 and BLOCK_SIZE=1024, how many blocks does the grid need, and how many lanes in the final block are masked off?"* — `ceil(10000/1024)=10` blocks; the 10th block covers offsets `9216..10239`, of which only `9216..9999` (784 elements) are valid, so `10240-10000=240` trailing lanes are masked off in that final block.

### Q7 — Why does Inductor generate Triton kernels rather than raw CUDA C++ directly?
**Testing:** connecting the choice of backend to Triton's own value proposition, not treating it as an arbitrary implementation detail.
**Answer:** Triton is itself a compiler that lets code be expressed at the "operate over a block of data" level rather than requiring manual thread/shared-memory/warp management, which is exactly the right abstraction level for a *compiler* (Inductor) to target when auto-generating kernels from a traced graph — it's a smaller, more tractable code-generation target than emitting hand-tuned CUDA C++ directly, while still producing kernels that perform competitively with hand-written CUDA for a very large fraction of real workloads, and the Triton output remains inspectable Python-embedded code rather than opaque compiled binary.
**Follow-up trap:** *"Does this mean torch.compile-generated kernels are always as fast as a CUDA expert's hand-tuned kernel for the same operation?"* — not always; for highly specialized, performance-critical operations (certain fused attention variants, specific quantized kernels) a CUDA or hand-tuned Triton expert can still out-optimize what automatic fusion/codegen produces — Inductor's generated kernels are very good defaults across a broad range of workloads, not a guaranteed ceiling on achievable performance for every specific operation.

### Q8 — A teammate benchmarks `torch.compile` on their model and finds it's actually *slower* in their measured end-to-end time. What's the first thing you'd check?
**Testing:** the specific, common measurement mistake around compilation's fixed cost.
**Answer:** Whether their benchmark includes the first (compiling) call's cost — the very first invocation of a compiled function pays tracing and codegen time on top of execution, which can be substantial, and if the benchmark only runs the model a handful of times (or measures wall-clock including that first call), the fixed compilation cost can dominate and make the compiled version look slower overall even though steady-state execution is genuinely faster.
**Follow-up trap:** *"If they exclude the first call and it's still slower in steady state, what's the next most likely cause?"* — recompilation happening repeatedly during what should be steady-state execution (a recompilation storm from varying input shapes not marked dynamic, or guards failing for some other reason on nearly every call) — check whether the model is actually reaching a stable, reused compiled graph at all, versus recompiling on most or every call.

### Q9 — Why is masking in a Triton kernel load-bearing for correctness, not just an optimization?
**Testing:** whether masking is understood as a correctness requirement, not a performance nicety.
**Answer:** Without a mask, `tl.load`/`tl.store` for the final, partially-filled block would read or write memory addresses past the actual allocated array's end (since `BLOCK_SIZE` blocks are launched uniformly regardless of whether `n_elements` divides evenly by `BLOCK_SIZE`) — this is out-of-bounds memory access, which can silently produce incorrect results (reading garbage/adjacent memory), a crash, or in a store's case, corrupt memory outside the intended array entirely; masking isn't tuning for speed, it's the mechanism that keeps every kernel invocation memory-safe when array sizes don't align exactly to the chosen block size.
**Follow-up trap:** *"Would choosing a BLOCK_SIZE that always evenly divides n_elements let you skip masking safely?"* — only if `n_elements` is *always* guaranteed to be an exact multiple of the chosen `BLOCK_SIZE` for every call site that will ever use the kernel, which is a fragile assumption to rely on in general-purpose code — masking costs very little (one comparison and a masked load/store, both natively supported operations) and removes an entire class of hard-to-debug, input-size-dependent correctness bugs, so it's standard practice even when a particular use case happens to align evenly today.

### Q10 — Design question: you're optimizing a training loop and profiling shows the GPU spending significant time on many small kernel launches for a custom loss function with several elementwise operations chained together. Walk through your diagnosis and fix, from cheapest to most involved.
**Testing:** staff-level triage ordering, matching effort to expected payoff.
**Answer:** First, the cheapest check: confirm the loss function is actually inside a `torch.compile`-wrapped region at all, and if it already is, check for graph breaks specifically around it (`torch._dynamo.error_on_graph_break()`) — if Inductor is simply not fusing these ops due to an avoidable graph break, fixing that (often restructuring a small piece of data-dependent logic) is the highest-leverage, lowest-effort fix. If the ops are already compiling into one graph but Inductor's automatic fusion genuinely isn't producing an efficient fused kernel for this specific pattern (rare, but possible for less-common operation combinations), the next step is inspecting Inductor's generated Triton code directly to understand what it's actually producing before deciding whether a hand-written custom Triton kernel is warranted — reserving hand-written kernels (the most engineering-expensive option) for confirmed cases where automatic compilation genuinely falls short, not as a first response.
**Follow-up trap:** *"What would make you decide hand-writing the Triton kernel yourself is NOT worth it, even if it would technically be faster?"* — if the loss function isn't actually a measured bottleneck in the overall training step's wall-clock time (e.g., it's a small fraction of total time dominated by the forward/backward pass through a much larger model), the engineering and maintenance cost of a hand-written, framework-bypassing custom kernel likely isn't justified by its marginal speedup — always weigh a targeted optimization's cost against its share of the actual measured bottleneck, not its theoretical improvability in isolation.

---

## Red flags that fail you

- Cannot explain what a graph break is, or thinks it means compilation failed/crashed rather than a graceful eager fallback.
- Doesn't know why guards exist or what triggers a recompilation.
- Confuses Dynamo (graph capture) with Inductor (code generation) or can't describe what each stage of the pipeline actually does.
- Cannot write or explain a masked Triton `tl.load`/`tl.store`, or doesn't understand why the mask is a correctness requirement.
- Believes `torch.compile` always makes any workload faster with no exceptions or tradeoffs.
- Cannot connect operator fusion back to the kernel-launch-overhead/HBM-round-trip argument from `T16-gpu-arch`.

---

## Cheat card

```
torch.compile PIPELINE:
  Dynamo: hooks CPython frame eval API, traces REAL eager code as it runs
    -> FX graph of ATen ops + GUARDS (shape/dtype/device/value assumptions)
    -> guard fails -> RECOMPILE; untraceable code -> GRAPH BREAK (fall back to
       eager for that piece, NOT a crash, but Inductor can't fuse across it)
  AOTAutograd: traces FORWARD + BACKWARD together, ahead of time (once)
  Inductor: lowers joint graph -> generates code
    GPU -> FUSED TRITON kernels;  CPU -> C++/OpenMP
    fusion = fewer kernel launches (saves ~3-10us/launch, T16-gpu-arch) +
             fewer HBM round-trips for intermediates

RECOMPILATION STORM: highly variable input shapes -> new guard fails every call
  -> recompile every call -> FIX: mark dims dynamic (compile once for a RANGE)
  cost: less shape-specific optimization vs a fully specialized graph

torch._dynamo.error_on_graph_break() / fullgraph=True: force an ERROR at a
  graph break instead of silent eager fallback -- use to FIND perf-costing breaks

TRITON KERNEL = describe ONE BLOCK of data, compiler maps to threads/warps
  (no manual thread indices / shared memory / warp sync -- unlike raw CUDA)

VECTOR ADD KERNEL (canonical minimal example):
  pid = tl.program_id(0)
  offsets = pid*BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
  mask = offsets < n_elements                      <- CORRECTNESS requirement,
  x = tl.load(x_ptr+offsets, mask=mask)                not just perf: skips
  y = tl.load(y_ptr+offsets, mask=mask)                out-of-bounds reads/writes
  tl.store(out_ptr+offsets, x+y, mask=mask)
  grid = ceil(n_elements/BLOCK_SIZE)
  n_elements=10000, BLOCK_SIZE=1024 -> grid=10 blocks; last block masks off
    10*1024-10000=240 trailing out-of-bounds lanes

WHEN NOT TO: compile has real fixed cost (bad for very short-lived processes);
  don't fight every graph break (only hot-path ones matter); don't hand-write
  Triton for patterns Inductor already fuses well; don't mark everything
  dynamic by default (loses shape-specific optimization)
```

## Sources

- [PyTorch 2.9 Release Blog](https://pytorch.org/blog/pytorch-2-9/) — accessed 2026-08-03
- [Dynamo Overview — PyTorch 2.9 documentation](https://docs.pytorch.org/docs/stable/torch.compiler_dynamo_overview.html) — accessed 2026-08-03
- [torch.compiler — PyTorch documentation](https://docs.pytorch.org/docs/main/user_guide/torch_compiler/torch.compiler.html) — accessed 2026-08-03
- [Triton Language Tutorials — Vector Addition (OpenAI Triton / PyTorch)](https://pytorch.org/blog/triton-kernel-compilation-stages/) — accessed 2026-08-03
- [Triton Kernel Development on GPU Cloud — Spheron Blog (2026)](https://www.spheron.network/blog/openai-triton-kernel-gpu-cloud-2026/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
