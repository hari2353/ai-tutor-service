# CPython: Bytecode, Eval Loop, PyObject, Refcounts, Adaptive Interpreter

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.0h · **Prereqs:** T16-compilers · **Updated:** 2026-08-03
> **Module id:** `T16-cpython-runtime` · **Tags:** runtime

## The 30-second version

CPython compiles source to bytecode (a stack-based instruction set, e.g. `LOAD_FAST`, `BINARY_OP`), which the eval loop (`_PyEval_EvalFrameDefault`, historically a giant `switch`/computed-goto over opcodes) interprets one instruction at a time; every Python object, no matter how simple, is a heap-allocated `PyObject` with at minimum a reference count and a type pointer, and CPython uses reference counting (not tracing GC alone) as its primary memory management strategy, with a supplementary cyclic garbage collector only for reference cycles that pure refcounting can't reclaim. The GIL (Global Interpreter Lock) exists because refcounting is not thread-safe without either per-object locking (slow) or one big lock serializing all bytecode execution (simpler, and what CPython chose in 1992 and has lived with since) — every `PyObject` refcount increment/decrement is a potential race, and the GIL sidesteps that by ensuring only one thread runs Python bytecode at a time, full stop, which is exactly why CPU-bound multi-threaded Python doesn't get faster with more threads while I/O-bound multi-threaded Python does (the GIL is released around blocking I/O calls). Python 3.11's specializing adaptive interpreter rewrites hot bytecode instructions in-place with type-specialized, faster variants once it observes stable types at a call site (e.g. `BINARY_OP` becomes `BINARY_OP_ADD_INT` after seeing repeated int+int), and PEP 703's free-threaded build (officially supported starting 3.14, "phase II" as of today) removes the GIL entirely via per-object or biased locking schemes, trading a modest single-threaded slowdown (down to roughly 5-10% by 3.14 from ~40% in 3.13's experimental phase) for real multi-core parallelism on CPU-bound Python code for the first time in the language's history.

## Why this gets asked

Because "why is Python slow" and "why can't I just add threads" are two of the most common surface-level questions in any Python-heavy interview, and nearly every candidate can recite "the GIL" without being able to explain what it actually protects or why removing it took over two decades of false starts (the failed 1999 "Gilectomy"-precursor attempts, and Larry Hastings' actual Gilectomy project circa 2016 both failed for concrete, instructive reasons). An interviewer wants to know whether you understand this is a genuine engineering tradeoff with measurable costs on both sides, not a historical accident waiting to be casually fixed, and whether you know what 3.11+ actually changed (adaptive specialization) versus what's still an active, not-yet-default transition (free-threading).

---

## Lineage: past → present → future

**What came before.** CPython's reference-counting-plus-GIL design dates to Guido van Rossum's original 1991 implementation, at a time when multi-core consumer/server hardware was essentially nonexistent — a single global lock serializing bytecode execution was not a meaningful constraint when there was only one core to run on anyway, and refcounting gave simple, deterministic, immediate reclamation (an object's `__del__` runs the instant its refcount hits zero, unlike a tracing collector's unpredictable timing) which mattered for a language positioned as a simple scripting glue layer. The pain arrived gradually as multi-core hardware became universal (mid-2000s onward): CPU-bound multi-threaded Python code fundamentally cannot use more than one core's worth of Python-level computation, no matter how many threads you spawn, because the GIL serializes bytecode execution regardless of thread count — a limitation invisible in 1991 and increasingly costly for decades afterward.

**Where it stands now.** The dominant practical workaround has been process-based parallelism (`multiprocessing`, or process-pool-based frameworks) which sidesteps the GIL entirely by using separate interpreter processes (each with its own GIL) at the cost of IPC/serialization overhead and higher memory usage, plus C-extension-based parallelism (NumPy, PyTorch's underlying kernels) where the actual hot loop runs in C/C++/CUDA code that explicitly releases the GIL during long-running native computation. PEP 703 (accepted 2023, championed largely by Sam Gross's "nogil" fork work) proposed actually removing the GIL from CPython itself via biased reference counting and other synchronization techniques, and PEP 779 formalized the phased rollout plan; free-threaded builds became officially supported (not just experimental) starting with Python 3.14 (October 2025), installable alongside the standard GIL build via a distinct ABI tag (`t`). The live disagreement is about pace and cost: free-threaded builds still carry real overhead (single-threaded slowdown, cited around 5-10% by 3.14 versus roughly 40% during 3.13's initial experimental phase, plus 15-20% higher memory usage from per-object locking metadata and reduced allocator sharing), and a large fraction of the C-extension ecosystem (NumPy, and everything built on CPython's C API) needs explicit updates to be thread-safe without the GIL's implicit protection — this migration is real and ongoing, not complete.

**Where it's heading.** CPython's own roadmap (as communicated through PEP 703/779) is explicit and multi-release: after 2-3 more releases (roughly 2026-2027), the GIL becomes controllable via a runtime flag/environment variable rather than a purely build-time choice; after another 2-3 releases (roughly 2028-2030), free-threading becomes the *default*, with the GIL still available to re-enable at runtime for compatibility. This is a stated plan with real momentum (the specializing adaptive interpreter's PEP 659 work is explicitly enabled and improved within free-threaded mode specifically to close the single-threaded performance gap), but the exact timeline for the ecosystem (extension authors, especially long-tail packages) to catch up is the genuinely uncertain part — CPython core team commitment to the direction is confident; ecosystem-wide readiness on any specific calendar date is not.

---

## Mental model

Picture the eval loop as a stack machine reading one instruction at a time from a flat array of bytecode, manipulating a per-frame value stack, with every value on that stack being a *pointer* to a heap object carrying its own refcount:

```
source:  x = a + b

bytecode (simplified, 3.11+ style):
  LOAD_FAST   a        ; push ptr-to-a's PyObject onto value stack
  LOAD_FAST   b        ; push ptr-to-b's PyObject
  BINARY_OP   +        ; pop both, call type's __add__, push result ptr
  STORE_FAST  x        ; pop, store ptr into local slot x

each PyObject on the heap:
  +----------------+
  | ob_refcnt: N   |  <- incremented/decremented as pointers are pushed/popped/stored
  | ob_type: *PyLong_Type |
  | ob_digit[...]  |  <- actual value representation (variable-length for int)
  +----------------+
```

Every `LOAD_FAST`/`STORE_FAST` isn't just a pointer copy — it's a pointer copy *plus* a refcount adjustment, and that refcount adjustment is exactly the operation that isn't safe to do from multiple threads simultaneously without either a lock or the GIL.

---

## How it actually works

### Bytecode and the eval loop

`compile()` (invoked implicitly by `python foo.py` or explicitly via the `compile()` builtin) turns source through the same lex→parse→AST pipeline described in the compilers module into CPython bytecode — inspectable directly via `dis.dis()`. The bytecode is a stack-based ISA: most instructions pop operands off a per-frame value stack and push results back, rather than referencing named registers. The core interpreter loop, `_PyEval_EvalFrameDefault` in `Python/ceval.c`, is (in the 3.11+ implementation) a computed-goto-dispatched loop over opcodes on platforms that support it (falling back to a `switch` statement otherwise) — computed goto avoids the branch-misprediction cost of a single large `switch`'s indirect jump by giving each opcode's dispatch its own predictable branch target, a real, measured interpreter-loop optimization technique that predates and is orthogonal to the 3.11 specialization work.

```python
>>> import dis
>>> def add(a, b): return a + b
>>> dis.dis(add)
  1           0 RESUME                   0
              2 LOAD_FAST                0 (a)
              4 LOAD_FAST                1 (b)
              6 BINARY_OP                0 (+)
             10 RETURN_VALUE
```

### PyObject layout and reference counting

Every Python object, including small integers and `None`, is represented at the C level by a struct beginning with a common header — at minimum `ob_refcnt` (a reference count) and `ob_type` (a pointer to the object's type object, itself a `PyObject`). Container/variable-length types (`PyVarObject`, the base for `list`, `tuple`, `str`, `int`) additionally carry `ob_size`. This uniform header is what lets CPython's C API treat every Python value polymorphically through a single `PyObject*` pointer type regardless of what it actually points to.

Reference counting works by incrementing `ob_refcnt` (`Py_INCREF`) whenever a new reference to an object is created (assigned to a variable, appended to a list, passed as an argument) and decrementing it (`Py_DECREF`) whenever a reference goes out of scope or is explicitly deleted; when the count hits zero, the object's memory is immediately freed (and its `__del__`, if any, runs immediately, synchronously, at that exact point — a real, deterministic behavior tracing garbage collectors like the JVM's don't offer). The cost: **every** object touch, not just allocation, does refcount bookkeeping, and in the free-threaded build this bookkeeping must be atomic or otherwise synchronized (Python 3.13+'s free-threaded build uses **biased reference counting**, optimizing the common case where an object is only ever touched by the thread that "owns" it, falling back to a slower shared/atomic path for genuinely cross-thread references) — which is precisely the source of free-threaded Python's per-object memory overhead and the residual single-threaded slowdown, since even the biased fast path costs more than the GIL-protected non-atomic increment it replaces.

Reference counting alone cannot reclaim **reference cycles** (e.g. two objects referencing each other, or a self-referential container) since neither object's count ever reaches zero through ordinary dereferencing. CPython supplements refcounting with a **generational cyclic garbage collector** (`gc` module) that periodically scans candidate container objects for unreachable cycles and collects them — this is the "GC" most people mean when they say "Python has garbage collection," but it's a supplement to, not a replacement for, refcounting as the primary reclamation mechanism.

### Why the GIL exists

The GIL is a single lock that must be held to execute Python bytecode. Its purpose is narrower than "thread safety for Python code" broadly — it specifically protects CPython's internal data structures, above all the refcount field on every `PyObject`, from concurrent modification. Without it (or an equivalent fine-grained locking scheme), two threads simultaneously incrementing the same object's refcount could race (a classic lost-update bug: both threads read the same old value, both write back the same incremented value, one increment is silently lost), leading to premature frees and use-after-free memory corruption — a catastrophic, hard-to-reproduce class of bug in a language whose entire memory-safety story rests on refcounting being reliable. CPython's 1992-era choice was a single coarse lock rather than per-object fine-grained locking, because fine-grained locking (a lock per object, or per bucket of objects) is dramatically more complex to implement correctly and, historically, slower for single-threaded code due to lock acquisition overhead on every single object touch — the GIL was, and for decades remained, the simpler and faster choice for the overwhelmingly common case of single-threaded or I/O-bound multi-threaded Python.

The GIL is released around blocking I/O operations (file reads, network calls, `time.sleep`) specifically so that I/O-bound multi-threaded Python *does* get real concurrency benefit — one thread can block on a socket read while another runs Python bytecode — which is exactly why "Python threads are useless" is an overstatement: they're useless for CPU-bound parallelism, genuinely useful for I/O-bound concurrency, a distinction that trips up candidates who've heard "GIL" as an unqualified negative without understanding what it actually restricts.

### The 3.11+ specializing adaptive interpreter (PEP 659)

Starting in Python 3.11, the eval loop implements **quickening**: generic bytecode instructions that observe stable, predictable behavior at a given call site get rewritten in-place to type-specialized, faster variants after a warmup threshold. A generic `BINARY_OP` instruction handles every possible operand-type combination via a slow, general dispatch path; after observing several executions where both operands were `int`, the interpreter rewrites that specific bytecode slot to `BINARY_OP_ADD_INT`, a specialized variant that skips the general type-dispatch machinery and does a direct, guarded integer addition — guarded because the specialization includes an inline check that the operand types are still what was observed, and if that guard fails (the site becomes polymorphic — e.g. it later sees a `float`), the interpreter **de-specializes** back to the generic path rather than executing incorrect logic. This is architecturally the same "observe real behavior, specialize the hot path, guard and deoptimize on assumption violation" pattern used by tiered JIT compilers (covered in the JVM and Go/V8 modules) — the meaningful difference is that CPython's adaptive interpreter specializes *bytecode instructions in place within the interpreter*, rather than compiling to native machine code the way a true JIT does; it's an interpreter optimization, not JIT compilation, though CPython 3.13+ has also begun shipping an experimental JIT (a copy-and-patch based compiler building on this same specialization data) as a further, still-maturing step.

### Free-threading: what it actually removes and what it costs

PEP 703's free-threaded build removes the GIL and replaces its protections with a combination of: **biased reference counting** (fast-path refcounting for single-threaded/owning-thread access, slower atomic/shared path for genuine cross-thread references), **per-object or striped locks** for mutable container operations that need atomicity beyond simple refcounting, and a stop-the-world mechanism retained specifically for the cyclic garbage collector's scanning phase (which still needs a consistent view of the object graph). The tradeoffs are concrete and measured: single-threaded overhead that started around 40% in 3.13's experimental phase has been brought down to roughly 5-10% by 3.14 through continued optimization (including enabling the specializing adaptive interpreter within free-threaded builds, which wasn't initially compatible), the free-threaded build uses roughly 15-20% more memory (per-object lock/refcount metadata, reduced ability to share certain cached objects across threads), and — critically for real-world adoption — C extensions written against the assumption of GIL-protected single-threaded access to CPython internals (a large fraction of the scientific Python and native-extension ecosystem, historically) require explicit auditing and updates to be safe under free-threading, since the GIL was implicitly doing synchronization work many extension authors never had to think about.

---

## Build it from scratch

A minimal reference-counting toy allocator, in Python itself, demonstrates the refcount-vs-cycle distinction that motivates CPython's two-tier (refcount + cyclic GC) design:

```python
# untested sketch — toy refcounted object model illustrating why cycles need a separate collector
class RefCounted:
    def __init__(self, name):
        self.name = name
        self.refcount = 0
        self.refs = []          # objects this one points to

    def incref(self):
        self.refcount += 1

    def decref(self, heap):
        self.refcount -= 1
        print(f"decref {self.name} -> {self.refcount}")
        if self.refcount == 0:
            print(f"  freeing {self.name}")
            heap.discard(self)
            for r in self.refs:
                r.decref(heap)   # releasing this object drops its outgoing references too

    def add_ref(self, other):
        self.refs.append(other)
        other.incref()

heap = set()
a = RefCounted("a"); heap.add(a); a.incref()   # one external reference holds a alive
b = RefCounted("b"); heap.add(b); b.incref()

a.add_ref(b)   # a -> b
b.add_ref(a)   # b -> a  (a cycle!)

a.decref(heap)  # external ref to a dropped; a.refcount is now 1 (from b's ref), NOT 0
b.decref(heap)  # external ref to b dropped; b.refcount is now 1 (from a's ref), NOT 0
print("still on heap:", [o.name for o in heap])  # both a and b -- LEAKED despite no external refs
```

Running this shows both `a` and `b` remaining on the simulated heap even after every *external* reference is gone — exactly the cycle-leak scenario pure refcounting cannot solve on its own, which is precisely why CPython's real cyclic GC exists as a second, separate mechanism (periodically scanning for and breaking exactly this pattern) rather than something refcounting could ever be made to handle alone.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| CPU-bound Python code with more `threading.Thread` workers shows no throughput improvement (or gets worse) | The GIL serializes bytecode execution regardless of thread count; more Python-level threads add scheduling/context-switch overhead without adding parallelism for CPU-bound work | Use `multiprocessing` (or a process-pool framework) for CPU-bound parallelism, push the hot loop into a GIL-releasing C extension (NumPy, Cython `nogil` blocks), or evaluate a free-threaded (3.14+, `python3.14t`) build if the workload and its dependencies support it |
| Long-running Python process's memory grows steadily despite objects "going out of scope" | Reference cycles among objects with `__del__` methods or objects the cyclic GC's generational thresholds haven't yet swept, or genuine reference leaks (module-level caches, unbounded lists) that refcounting correctly reports as still-referenced | Profile with `gc.get_objects()`/`objgraph`/`tracemalloc` to find what's actually still referenced and why; don't assume "Python has GC" means leaks are impossible — cycles and unbounded caches are still real, common leak patterns |
| A hot function is faster the second time it's called with the same argument types, in a way that isn't simple caching | The specializing adaptive interpreter (3.11+) quickened the bytecode after observing stable types at that call site's operations | Expected behavior; visible via `dis.dis(..., adaptive=True)` showing the specialized opcode variants after warmup — not a bug, and not something to "fix," but worth knowing when explaining a microbenchmark's warmup-sensitive results |
| A C extension crashes intermittently only when built/run against a free-threaded (`3.14t`) interpreter, not the standard GIL build | The extension relies on the GIL's implicit serialization for safety (e.g. mutating shared C-level state without its own locking) and wasn't audited/updated for free-threading | Check the extension's free-threading support status explicitly (many major packages publish this); avoid free-threaded builds for dependencies that haven't been audited, or contribute/wait for upstream thread-safety fixes |
| Adding `__del__` to a class with potential reference cycles makes objects survive longer than expected | Historically (pre-3.4), objects with `__del__` in a reference cycle couldn't be collected by the cyclic GC at all because the collector couldn't safely determine finalization order; this was fixed in PEP 442 (Python 3.4+), but very old codebases or comments referencing this limitation persist as outdated folklore | Confirm the actual Python version in use — this specific limitation was resolved in 3.4, and citing it as a current constraint in 3.11+ code is dated advice |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `threading` expecting CPU-bound speedup.** This is the single most common Python-concurrency mistake; threads help I/O-bound concurrency (the GIL releases around blocking calls) and do essentially nothing for CPU-bound parallelism under the standard GIL build — know which category your workload falls into before choosing a concurrency primitive.
- **Don't assume free-threaded Python is a drop-in performance upgrade today.** As of 3.14 it's officially supported but still trades single-threaded overhead (5-10%) and memory overhead (15-20%) for multi-core parallelism, and a meaningful fraction of the extension ecosystem isn't yet audited for it — appropriate for genuinely CPU-bound, pure-Python-or-thread-safe-extension workloads that specifically need multi-core scaling today, premature for most general-purpose services until the ecosystem catches up further.
- **Don't rely on `__del__`/refcount-triggered cleanup for anything correctness-critical in cyclic structures without understanding cycle-collection timing.** Deterministic cleanup is a real refcounting benefit for the *non-cyclic* case, but any object graph with cycles depends on the generational cyclic collector's non-deterministic scheduling — using context managers (`with`) for resources that must be released promptly and predictably is more reliable than depending on `__del__` timing.
- **Don't treat the specializing adaptive interpreter as a substitute for algorithmic or vectorization-level fixes.** It meaningfully speeds up the interpreter loop itself, but a genuinely hot numeric inner loop still benefits far more from moving into NumPy/Cython/C than from any amount of bytecode-level specialization — the mechanisms described in this module close a real but bounded gap, not the ~50-100x gap to compiled code described in the assembly module.
- **This module's concurrency model is specific to CPython.** PyPy, GraalPy, and other implementations have different (or no) GIL and different memory management strategies entirely — assuming CPython's specific tradeoffs apply universally to "Python" is a mistake worth flagging explicitly in any answer that generalizes.

---

## Interview questions

### Q1 — What does the GIL actually protect, precisely?
**Testing:** whether the answer is "thread safety" (too vague) or the specific mechanism.
**Answer:** It protects CPython's internal data structures — most importantly, the reference count field on every `PyObject` — from concurrent, unsynchronized modification by multiple threads executing Python bytecode simultaneously. Without it, two threads incrementing the same object's refcount could race and lose an increment, leading to premature deallocation and use-after-free memory corruption.
**Follow-up trap:** *"Does the GIL protect against all Python-level race conditions, like two threads appending to the same list?"* — no; the GIL guarantees individual bytecode instructions execute atomically relative to other Python threads, but a multi-instruction sequence (like `x += 1` on a shared object, which is load-modify-store across multiple bytecode ops) can still be interrupted between instructions by a thread switch, so higher-level race conditions on shared mutable state are still entirely possible under the GIL — it protects CPython's internals, not your application's logic.

### Q2 — Why can't reference counting alone reclaim all garbage, and what does CPython do about it?
**Answer:** Reference cycles (object A references object B, which references A, directly or transitively) mean neither object's refcount ever reaches zero through ordinary dereferencing, even when nothing outside the cycle references either — pure refcounting leaks these permanently. CPython supplements refcounting with a generational cyclic garbage collector (the `gc` module) that periodically scans candidate container objects for unreachable cycles and breaks/collects them.
**Follow-up trap:** *"If I never create cyclic references, can I disable `gc` entirely, and would that be safe?"* — yes, it's possible (`gc.disable()`) and some latency-sensitive applications do this deliberately to avoid GC pause unpredictability, but it's only safe if you're certain no cycles are created anywhere in your dependency graph too (including third-party libraries), which is a strong and easy-to-violate assumption in practice — a safer middle ground is tuning `gc` thresholds rather than disabling outright, unless you've specifically audited for cycle-free guarantees.

### Q3 — Explain the specializing adaptive interpreter with a concrete example, and what happens when its assumption breaks.
**Answer:** A generic bytecode instruction like `BINARY_OP` initially dispatches through a slow, type-generic path. After the interpreter observes several executions at a specific bytecode site with stable operand types (e.g. both `int`), it rewrites that instruction in place to a specialized variant (`BINARY_OP_ADD_INT`) that skips the general dispatch and does a direct, guarded operation. If a later execution at that same site sees a different type (e.g. a `float` arrives), the inline guard fails and the interpreter de-specializes back to the generic path rather than executing incorrect specialized logic.
**Follow-up trap:** *"Is this the same thing as the JVM's JIT compiling hot methods to machine code?"* — architecturally similar in spirit (observe real behavior, specialize the hot path, guard and deopt on violation) but mechanically different: CPython's adaptive interpreter specializes bytecode instructions executed by the interpreter loop itself, it does not compile to native machine code — that's a true JIT's job, and CPython only began shipping an experimental JIT (built on this same specialization infrastructure) starting in 3.13, still maturing, distinct from and layered on top of the adaptive interpreter.

### Q4 — Why does I/O-bound multi-threaded Python get real concurrency benefit despite the GIL, while CPU-bound multi-threaded Python doesn't?
**Answer:** The GIL is explicitly released around blocking operations (file/socket I/O, `time.sleep`, and other calls that drop into native code awaiting an external event), so while one thread is blocked waiting on I/O, another thread can acquire the GIL and run Python bytecode — genuine concurrency for the I/O-bound case. CPU-bound Python code never blocks on anything external; it's continuously executing bytecode, so the GIL is continuously held by whichever thread is running, and other threads simply wait their turn — no parallelism, only time-sliced serialization.
**Follow-up trap:** *"Does calling a NumPy function count as 'I/O-bound' for this purpose?"* — no, but it gets similar benefit through a different mechanism: NumPy's C-level hot loops explicitly release the GIL during long-running native computation (since they're not touching Python objects/CPython internals during that time), allowing other Python threads to run concurrently — this is why NumPy-heavy multi-threaded code can show real parallelism even though it's CPU-bound, but only because the actual CPU-bound work happens outside the GIL's scope entirely, not because Python threading itself changed.

### Q5 — What's the concrete performance and memory cost of the free-threaded (no-GIL) build as of Python 3.14, and why does that overhead exist at all?
**Answer:** Roughly 5-10% single-threaded slowdown (down substantially from ~40% during 3.13's initial experimental phase) and roughly 15-20% higher memory usage. The overhead exists because removing the GIL means refcounting and other previously GIL-protected operations now need their own synchronization — biased reference counting optimizes the common single-owning-thread case but still costs more than the GIL-protected non-atomic increment it replaces, and per-object lock/metadata overhead increases memory footprint.
**Follow-up trap:** *"If free-threading has a real cost, why pursue it at all instead of leaving the GIL in place?"* — because the GIL's cost (zero multi-core scaling for CPU-bound pure-Python code, permanently) is unbounded and grows with core counts that keep increasing, while free-threading's cost (a bounded single-digit-to-low-teens percentage overhead) is fixed and shrinking as the implementation matures — for genuinely CPU-bound, multi-core-hungry Python workloads, a bounded fixed tax is a better tradeoff than an unbounded scaling ceiling, which is the core argument that ultimately won out in PEP 703's acceptance.

### Q6 — Why does the CPython team's PEP 703/779 rollout plan span multiple years and releases instead of switching immediately?
**Answer:** Because the C-extension ecosystem (NumPy and everything built on the CPython C API) has, for over three decades, been able to implicitly rely on the GIL for thread safety without extension authors needing to think about synchronization explicitly — flipping the default abruptly would silently introduce data races and crashes across a huge fraction of the ecosystem with no warning. The phased plan (optional build → runtime-flag-controllable → free-threading as default with GIL still available as an opt-in fallback) gives extension maintainers years of overlap to audit and update their code, rather than forcing an all-at-once ecosystem-wide migration.
**Follow-up trap:** *"How would you personally decide whether to adopt free-threaded Python for a specific production service today?"* — audit every C-extension dependency's explicit free-threading support status (increasingly published by major packages), benchmark the actual workload under both builds (the 5-10%/15-20% figures are averages, not guarantees for any specific workload), and weigh that against the actual multi-core CPU-bound speedup the workload would realize — for a service that's mostly I/O-bound or already uses `multiprocessing`/NumPy effectively, the case for switching today is weak; for a genuinely CPU-bound, pure-Python-heavy, multi-core-starved workload with fully audited dependencies, it's a real, evaluable option now rather than purely theoretical.

### Q7 — A long-running Python service's memory grows steadily even though "everything looks like it should be garbage collected." What's your diagnostic approach?
**Answer:** Don't assume "Python has GC" rules out leaks — check for reference cycles involving objects the generational cyclic collector's thresholds haven't yet swept (`gc.collect()` forced manually, or tuning `gc.set_threshold`), and separately check for genuine reference leaks that refcounting is *correctly* reporting as still-alive (module-level caches that grow unbounded, closures capturing large objects, event listener registries that never unregister). Use `gc.get_objects()`, `objgraph.show_growth()`, or `tracemalloc` snapshots taken over time to identify which object types are actually accumulating and trace their referrers.
**Follow-up trap:** *"Could this be the free-threaded build's memory overhead instead of a leak?"* — worth ruling out explicitly if running on `3.14t` — the 15-20% memory overhead is a flat, roughly constant increase from per-object locking metadata, not a growth pattern; a steadily *growing* memory footprint over the service's lifetime is a leak signature regardless of which build is in use, and conflating the two wastes debugging time chasing the wrong hypothesis.

### Q8 — How do subinterpreters (PEP 554/684) differ from both free-threading and `multiprocessing` as a concurrency answer, and when would you actually reach for them?
**Testing:** whether the candidate can place a third, less-discussed concurrency model correctly relative to the two everyone defaults to.
**Answer:** Each subinterpreter (as of PEP 684, CPython 3.12+) gets its own GIL, so multiple subinterpreters in the same process can run Python bytecode truly in parallel across cores — unlike classic threading, which shares one GIL. Unlike `multiprocessing`, they share the same OS process (no fork/spawn overhead, no pickling data across a process boundary to communicate), but unlike free-threading, they don't share Python objects directly by default either — communication between subinterpreters goes through explicit, restricted channels, which is closer in spirit to message-passing than to shared-memory threading. Reach for them when you want process-like isolation (no shared mutable Python state, no GIL contention between interpreters) without the process-creation and IPC-serialization cost `multiprocessing` pays.
**Follow-up trap:** *"Given free-threading is coming, do subinterpreters become pointless?"* — no, they solve a different problem: free-threading gives shared-memory parallelism (fast communication, but every C extension needs auditing for thread safety); subinterpreters give isolation-by-construction (safer by default, no extension-auditing burden for shared state since there isn't any) at the cost of explicit, more limited inter-interpreter communication — a workload that specifically wants isolation (multi-tenant plugin execution, for instance) still has a real reason to prefer subinterpreters over free-threading even once free-threading is stable.

### Q9 — CPython's memory usage sometimes stays high even after objects are clearly dereferenced and collected. Why doesn't the process return that memory to the OS?
**Testing:** pymalloc/arena allocator knowledge, a common source of "Python is leaking" false alarms.
**Answer:** CPython's small-object allocator (`pymalloc`) manages memory in 256KB arenas subdivided into pools and fixed-size blocks for objects under ~512 bytes, and it can only return an entire arena to the OS once every pool within it is completely empty — a single long-lived small object sitting in an otherwise-empty arena pins the whole arena resident, even though the vast majority of that arena's memory is genuinely free from CPython's own perspective. This is why `RSS` (resident set size) as seen by the OS frequently doesn't shrink proportionally to how much Python memory was actually freed — the memory is free *to CPython* for reuse by future small-object allocations, but not necessarily returned to the OS.
**Follow-up trap:** *"So is high RSS after a big batch job always this effect, never an actual leak?"* — no, and conflating them wastes debugging time — check whether RSS is stable-but-elevated (consistent with fragmented pymalloc arenas, generally benign) versus continuing to *grow* on subsequent batches (a real leak signature, per Q7's diagnostic approach); large objects over pymalloc's threshold go straight to the system allocator via `malloc`/`free` and don't have this arena-pinning behavior at all, so the effect is specifically a small-object phenomenon.

### Q10 — Since Python 3.6/3.7, dicts preserve insertion order as a language guarantee. What changed internally to make that both true and *more* memory-efficient than the old implementation, not less?
**Testing:** a specific, often-surprising implementation fact — that a stronger guarantee came with a memory *improvement*, counter to the naive expectation.
**Answer:** The old dict implementation stored hash/key/value triples directly in the sparse hash table itself, wasting space on empty slots sized for the worst-case load factor. The compact dict (PEP 468-adjacent implementation work, landing as a guarantee in 3.7) splits this into a sparse array of just indices (small integers) pointing into a dense, insertion-ordered array holding the actual hash/key/value triples — the dense array is naturally insertion-ordered as a side effect of being append-only, and because indices are far smaller than full triples, the sparse portion shrinks substantially, reducing overall dict memory by a real, measured margin industry-wide reported around 20-25% at the time of the change, while *adding* an ordering guarantee rather than costing one.
**Follow-up trap:** *"Does this mean dicts and OrderedDict are now interchangeable?"* — not entirely — `OrderedDict` still provides operations dicts don't guarantee efficiently or at all (`move_to_end`, and historically, order-sensitive equality comparison between two OrderedDicts, which plain dict equality ignores), and it's implemented as a doubly-linked list structure distinct from the compact-dict internals, so it's still the right choice when those specific operations are needed even though plain dicts adopted the ordering guarantee.

---

## Red flags that fail you

- Saying "the GIL makes Python threads useless" without the I/O-bound vs CPU-bound distinction.
- Claiming Python has no memory-safety mechanism for reference cycles, or conversely claiming refcounting alone handles cycles.
- Confusing the 3.11+ specializing adaptive interpreter with a full JIT compiler (they're related but architecturally distinct).
- Claiming free-threaded Python is already the default or ships with zero overhead as of 2026.
- Assuming CPython's GIL/refcounting model applies to all Python implementations (PyPy, GraalPy differ significantly).
- Citing the pre-3.4 "objects with `__del__` in cycles can't be collected" limitation as if it's still true (fixed by PEP 442).

---

## Cheat card

```
BYTECODE: stack-based ISA, inspect via dis.dis(). Eval loop: _PyEval_EvalFrameDefault,
  computed-goto dispatch (3.11+) over opcodes.
PyObject: every object has >=2-field header: ob_refcnt, ob_type. PyVarObject adds ob_size.
REFCOUNTING: Py_INCREF/Py_DECREF on every touch. refcount==0 -> immediate, deterministic
  free + __del__ runs synchronously right then (unlike tracing GC's unpredictable timing).
CYCLES: refcounting alone leaks reference cycles (A->B->A). Generational cyclic GC (gc
  module) supplements refcounting specifically for this -- periodic scan + collect.
GIL: protects PyObject refcount (and other CPython internals) from concurrent bytecode
  execution races. Released around blocking I/O -> I/O-bound threading gets real
  concurrency; CPU-bound threading gets NONE (bytecode execution fully serialized).
  NumPy/native-extension hot loops release GIL explicitly during native computation.
ADAPTIVE INTERPRETER (3.11+, PEP 659): "quickening" -- generic opcode observes stable
  types at a site -> rewritten in-place to specialized variant (e.g. BINARY_OP ->
  BINARY_OP_ADD_INT). Inline guard checks assumption; fails -> de-specialize to generic.
  NOT a JIT (no native codegen) -- interpreter-level specialization. Experimental JIT
  (copy-and-patch, built on this data) shipping since 3.13, still maturing.
FREE-THREADING (PEP 703/779): removes GIL via biased refcounting (fast path = owning
  thread, slow path = atomic/shared) + per-object/striped locks. Officially supported
  3.14+ (build tag "t"). Cost: ~5-10% single-thread slowdown (down from ~40% in 3.13
  experimental), ~15-20% more memory. C extensions need explicit thread-safety audits.
ROLLOUT PLAN: 3.14 official-but-optional -> ~2026-27 GIL runtime-flag-controllable
  -> ~2028-30 free-threading DEFAULT, GIL still available as opt-in fallback.
```

## Sources

- [Python support for free threading — Python 3.14 documentation](https://docs.python.org/3/howto/free-threading-python.html) — accessed 2026-08-03
- [Python 3.14 — Astral](https://astral.sh/blog/python-3.14) — accessed 2026-08-03
- PEP 703 — Making the Global Interpreter Lock Optional in CPython
- PEP 779 — Criteria for supported status for free-threaded Python
- PEP 659 — Specializing Adaptive Interpreter
- PEP 442 — Safe object finalization (resolving `__del__`-in-cycles limitation)
- [CPython internals: `Python/ceval.c`, `Include/object.h`](https://github.com/python/cpython) — accessed 2026-08-03, primary source for PyObject layout and eval loop structure

## Changelog
- 2026-08-03 — created
