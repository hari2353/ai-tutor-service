# TensorFlow, Keras 3, and PyTorch Parity: Graph Tracing, XLA, and TF Serving

> **Track:** T04 Deep Learning · **Time:** 2h · **Prereqs:** T04-architectures, T04-compile-cuda · **Updated:** 2026-08-03
> **Module id:** `T04-tensorflow` · **Tags:** frameworks

## The 30-second version

TensorFlow and PyTorch converged on the same eager-first ergonomics years ago (TF2's 2019 default switch to eager execution, matching what PyTorch had offered since its 2017 release), and Keras 3 (2023) closed the remaining gap by becoming genuinely multi-backend — the identical model code runs unchanged on TensorFlow, JAX, PyTorch, or OpenVINO (inference-only), selected via `KERAS_BACKEND`, current release line 3.x (e.g. 3.14) as of 2026 — so "TensorFlow vs. PyTorch" is now less a mathematical-capability question than a tooling/ecosystem/deployment-infrastructure question. The one genuinely load-bearing mechanical parallel to internalize: TensorFlow's `tf.function` decorator traces a Python function into a static graph the first time it's called with a given input signature (shapes/dtypes), caching that graph for reuse and **retracing** (recompiling) whenever an incompatible signature appears — this is *exactly* the same shape-guard-triggers-recompilation mechanism `torch.compile`'s Dynamo implements (`T04-compile-cuda`), just introduced years earlier (TF's `tf.function`/AutoGraph, 2019, predates Dynamo's 2023 debut) and with the identical "recompilation storm" failure mode when input shapes vary uncontrollably. XLA (TensorFlow and JAX's compiler backend) plays the same role Inductor plays for `torch.compile` — lowering a traced graph into fused, hardware-specific compiled code — and Keras 3 models on the TensorFlow backend can opt into XLA compilation via `model.compile(jit_compile=True)`, while the JAX backend gets XLA compilation natively as its default execution mode. For production serving specifically, **TF Serving** remains a mature, purpose-built, non-Python-runtime-dependent serving system for TensorFlow `SavedModel` artifacts, with request batching configured via a `batching_params.pbtxt` file (`max_batch_size`, `batch_timeout_micros`, and related knobs) that groups incoming requests into one `Session::Run()` call for throughput — a request-level batching model closer to the "static batching" `T16-gpu-arch` describes than to vLLM-style continuous/iteration-level batching, which matters directly for anyone comparing TF Serving against a modern LLM-specific serving stack.

## Why this gets asked

Because plenty of production ML organizations (especially ones with mature pre-2023 TensorFlow investments, or teams using Google Cloud/TPU infrastructure where TensorFlow and JAX have historically had first-class support) run real systems on TensorFlow or Keras, and interviewers want to know whether a PyTorch-fluent candidate can actually reason about and work in that ecosystem too — not out of framework tribalism, but because "can you pick up an unfamiliar but related framework's actual mechanics quickly" is a genuine, transferable engineering skill this question tests directly. It's also a good test of whether a candidate understands the *underlying* concepts (graph tracing, compilation, batched serving) well enough to recognize the same idea wearing a different framework's name, rather than having memorized PyTorch-specific API calls without the concept underneath them.

---

## Lineage: past → present → future

**What came before.** TensorFlow 1.x (2015-2019) required explicit, upfront static graph construction: you built a computation graph using placeholder tensors with no attached values, then executed it by running data through a `tf.Session` — a fundamentally different, less immediately-debuggable programming model than eager execution (no `print(tensor)` mid-computation showing an actual value, since nothing had a value until the session actually ran), which was directly responsible for TensorFlow's reputation (deserved, at the time) for having a steep learning curve relative to more research-friendly alternatives. PyTorch's 2017 debut with eager-by-default execution (build and run the graph as one and the same step, with real tensor values visible immediately) was a direct, explicit reaction to this pain, and its rapid adoption in research settings through the late 2010s was substantially driven by this ergonomic difference — this is exactly the historical pain TF2's 2019 default switch to eager execution (with `tf.function` as an opt-in decorator to recover graph-mode performance when needed) was built to close.

**Where it stands now.** The eager-vs-graph ergonomics gap that used to clearly separate the two frameworks is now closed on both sides: PyTorch is eager by default with `torch.compile` as an increasingly seamless opt-in path to graph-level optimization (`T04-compile-cuda`), and TensorFlow is eager by default with `tf.function`/XLA as its equivalent opt-in path — the frameworks have converged on the same underlying idea (trace what actually runs, guard/retrace on incompatible signatures, compile the traced graph) via largely parallel, independently-developed mechanisms. Keras 3's multi-backend capability (2023) is the more consequential recent differentiator: it decouples the *modeling API* from the *execution backend* entirely, meaning a team's choice of TensorFlow, JAX, or PyTorch as an execution backend no longer needs to be a permanent, model-code-level commitment when Keras 3's API is used — a genuinely new capability neither framework offered independently before. TF Serving remains a mature, widely-deployed, production-hardened serving system specifically for TensorFlow `SavedModel` artifacts, valued for exactly the kind of stability and operational maturity (versioned model rollout, non-Python C++ runtime, mature monitoring/batching configuration) that newer, more research-velocity-oriented serving stacks sometimes trade away for faster iteration on cutting-edge techniques (e.g. LLM-specific continuous batching in vLLM/TensorRT-LLM, which TF Serving's request-level batching model doesn't natively implement).

**Where it's heading.** JAX's role continues to grow specifically in large-scale research and TPU-centric training (Google's own large model training increasingly leans on JAX/XLA), while Keras 3's multi-backend abstraction is the more accessible on-ramp for teams who want *some* backend flexibility without committing to JAX's more functional, less object-oriented programming style directly. TF Serving's relatively static, request-level batching model is a genuine, real limitation for teams whose primary serving workload has shifted toward LLM-style autoregressive generation, where continuous/iteration-level batching (`T16-gpu-arch`) delivers order-of-magnitude throughput gains TF Serving's architecture wasn't designed around — this is a real, current reason many LLM-serving-focused teams reach for vLLM/TensorRT-LLM/TGI instead of TF Serving even when their model was originally trained in TensorFlow, exporting to ONNX or another interchange format as the bridge. What's stable: the underlying mathematical content (forward propagation, backprop, the architectures and optimizers from earlier modules in this track) is identical regardless of which framework executes it — this module is entirely about ecosystem and tooling fluency, not a different set of mathematics.

---

## Mental model

```
HISTORICAL ERGONOMICS GAP (now CLOSED on both sides):

  TF 1.x (2015-2019): build STATIC GRAPH (placeholders, no values) -> tf.Session.run()
    <- painful to debug (no real values until session runs)
  PyTorch (2017+): EAGER by default -- build+run as one step, real values always visible
  TF 2.x (2019+): EAGER by default too, matching PyTorch's ergonomics
    tf.function: opt-in decorator -> TRACE into a static graph for performance
  torch.compile (2023+): opt-in DYNAMO tracing -> graph for performance (T04-compile-cuda)

  SAME UNDERLYING IDEA, PARALLEL IMPLEMENTATIONS, YEARS APART:
    tf.function's input SIGNATURE (shape/dtype) mismatch -> RETRACE
      <-- IDENTICAL mechanism to Dynamo's GUARD failure -> RECOMPILE
    XLA (TF/JAX compiler backend) <-- IDENTICAL role to Inductor (torch.compile backend)

KERAS 3 (2023+): decouples the MODELING API from the EXECUTION BACKEND
  same model code -> KERAS_BACKEND=tensorflow | jax | torch | openvino(inference)
  TF backend: model.compile(jit_compile=True) -> opts into XLA
  JAX backend: XLA compilation is the NATIVE default execution mode
  PyTorch backend: can layer torch.compile on top

PRODUCTION SERVING:
  TF Serving: mature, SavedModel-specific, C++ runtime, VERSIONED model rollout
    batching_params.pbtxt: max_batch_size, batch_timeout_micros
    -> REQUEST-LEVEL (static) batching, closer to T16-gpu-arch's "static batching"
       than vLLM's iteration-level CONTINUOUS batching for LLMs
```

The one-line mental model: **TensorFlow and PyTorch solved the same eager-vs-compiled-performance problem independently and arrived at the same shape (trace, guard/retrace, compile via XLA/Inductor); Keras 3 additionally decouples which backend actually executes that traced graph, and TF Serving is a mature, batteries-included serving system built around a batching model that predates and differs from modern LLM-specific continuous batching.**

---

## How it actually works

### `tf.function`, tracing, and retracing: the direct parallel to Dynamo's guards

Decorating a Python function with `@tf.function` doesn't execute it eagerly on each call — the first time it's called with a given **input signature** (the shapes and dtypes of its arguments), TensorFlow traces the function's execution (via **AutoGraph**, which converts Python control flow like `if`/`for` into equivalent graph operations) into a static computation graph, caches that graph, and reuses it on subsequent calls with a *matching* signature. If a later call arrives with a genuinely different signature (a different input shape, for instance), TensorFlow **retraces** — builds and caches an entirely new graph for that signature — exactly analogous to a Dynamo guard failure triggering recompilation in `torch.compile`. This produces the identical failure mode `T04-compile-cuda` describes for PyTorch: a function called repeatedly with highly variable input shapes retraces on nearly every call, paying tracing cost repeatedly instead of amortizing one trace over many calls — mitigated the same way, by specifying an explicit, relaxed `input_signature` (accepting a range of shapes, e.g. marking a dimension as `None`/dynamic) rather than letting TensorFlow specialize a fresh graph per exact shape.

### XLA: the same role as Inductor, for a different set of frameworks

XLA (Accelerated Linear Algebra) is TensorFlow's (and JAX's) compiler backend — it takes a traced computation graph and lowers it into fused, hardware-specific compiled code, performing the same category of optimization (operator fusion, reducing kernel-launch overhead and redundant HBM round-trips, per `T16-gpu-arch`'s argument) that Inductor performs for `torch.compile`. On the TensorFlow backend, Keras 3 models opt into XLA compilation via `model.compile(jit_compile=True)`; on the JAX backend, XLA compilation is the default, native execution mode (JAX's `jax.jit` is effectively always in the picture, not an opt-in the way `tf.function`/`torch.compile` are), reflecting JAX's design as a functional, trace-and-compile-first framework from the start rather than eager-first with compilation as an add-on.

### Keras 3: one model, multiple backends, and what that actually decouples

Before Keras 3, "Keras" specifically meant a TensorFlow-only high-level API — switching your execution framework meant rewriting your model. Keras 3 (2023) restructured this so the modeling API (`keras.Model`, `keras.layers.*`, `keras.optimizers.*`) is genuinely backend-agnostic: the same `keras.Sequential`/functional model definition runs, unmodified, against a TensorFlow, JAX, PyTorch, or (inference-only) OpenVINO backend, selected via the `KERAS_BACKEND` environment variable (or `~/.keras/keras.json`). The practical constraint this creates (covered in `T04-architectures`): any custom operation inside a Keras 3 model must use the backend-agnostic `keras.ops.*` API rather than importing a specific backend's tensor operations directly (e.g. `tf.*` calls), or that portability is broken for that model. This decoupling is genuinely new — neither TensorFlow nor PyTorch independently offered "write once, choose your execution backend later" before Keras 3 existed.

### TF Serving: what it actually provides beyond "run the model"

TF Serving is a dedicated, production-hardened C++ serving runtime specifically for TensorFlow `SavedModel` artifacts (a self-contained, versioned export format including the model's graph and trained weights) — it is deliberately *not* a Python process running your training-time code, which removes Python's runtime overhead and dependency-management burden from the serving path entirely. Its two most operationally significant features: **versioned model rollout** (TF Serving can hold multiple versions of a model simultaneously and route traffic according to a configurable policy, supporting canary/rollback deployment patterns without a separate infrastructure layer), and **request batching**, configured via a `batching_params.pbtxt` file specifying parameters like `max_batch_size` (the largest number of individual requests grouped into one batched `Session::Run()` call) and `batch_timeout_micros` (how long to wait accumulating requests into a batch before running it anyway, even if `max_batch_size` hasn't been reached) — this batching happens at the *request* level, grouping whole, complete inference requests together before running them as one batch, which is architecturally the "static batching" pattern `T16-gpu-arch` contrasts against vLLM-style **continuous/iteration-level** batching (which operates at the granularity of individual autoregressive decode steps, swapping requests in and out mid-generation). This is not a defect in TF Serving — request-level batching is entirely appropriate and effective for the fixed-length-inference workloads (classification, embedding, single-forward-pass regression) TF Serving was originally designed around — but it is a real, architectural reason TF Serving is not the tool of choice for serving autoregressive LLM generation at competitive throughput, where the continuous-batching techniques `T16-gpu-arch` covers dominate specifically because request lengths vary so widely mid-generation.

### Distribution strategies: TensorFlow's DDP/FSDP equivalents

`tf.distribute.MirroredStrategy` (single-machine, multi-GPU) and its multi-machine equivalents implement the same data-parallel replicate-and-all-reduce pattern `T04-distributed-training` derives for PyTorch's DDP — full model replicated per device, gradients averaged via all-reduce across devices, identical update applied to every replica. `TPUStrategy` extends the same conceptual pattern to Google's TPU hardware specifically, which has its own distinct interconnect and memory characteristics from GPU clusters but follows the same underlying data-parallel replication-and-synchronization logic this track's distributed training module derives in general terms — the mechanics (what's replicated, what's communicated, why communication cost behaves as it does) transfer directly even though the specific API and hardware differ.

---

## Build it from scratch

```python
import tensorflow as tf

@tf.function
def train_step(x, y, model, optimizer, loss_fn):
    with tf.GradientTape() as tape:           # TF's analogue of building the autograd
        pred = model(x, training=True)         # graph during the forward pass (T04-autograd)
        loss = loss_fn(y, pred)
    grads = tape.gradient(loss, model.trainable_variables)
    optimizer.apply_gradients(zip(grads, model.trainable_variables))
    return loss

# calling train_step with a NEW input shape (different from any prior call)
# triggers a RETRACE -- the direct TF analogue of a Dynamo guard failure.
# specifying input_signature avoids this for genuinely variable shapes:
@tf.function(input_signature=[
    tf.TensorSpec(shape=[None, 784], dtype=tf.float32),   # None = any batch size
    tf.TensorSpec(shape=[None], dtype=tf.int32),
])
def train_step_fixed_signature(x, y):
    ...
```
`tf.GradientTape` is TensorFlow's explicit-scope equivalent of PyTorch's implicit, always-on autograd tape (`T04-autograd`) — operations inside the `with tf.GradientTape() as tape:` block are recorded for differentiation, and `tape.gradient(loss, variables)` performs the reverse-mode traversal, conceptually identical to calling `.backward()` and reading `.grad` in PyTorch, just requiring an explicit context manager rather than tracking every operation by default. The lab exercise in `(lab pending)`: implement the exact 2-layer sigmoid network and worked forward/backward numbers from `T04-neural-net-math`/`T04-backprop-derivation` using `tf.GradientTape` directly, confirming the gradients match the hand-derived values from those modules to `1e-6`, exactly the same cross-framework verification discipline applied throughout this track.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A `tf.function`-decorated training step recompiles on nearly every call, with compilation time dominating total runtime | Input shapes vary across calls without an explicit relaxed `input_signature`, triggering a retrace per distinct signature — the TF analogue of a `torch.compile` recompilation storm | Specify an explicit `input_signature` with `None` for genuinely variable dimensions, so TensorFlow traces once for a range of shapes rather than once per exact shape |
| A Keras 3 model works correctly on the TensorFlow backend but errors when switched to the JAX or PyTorch backend | A backend-specific operation (e.g. a raw `tf.*` call) was used inside a custom layer/loss instead of the backend-agnostic `keras.ops.*` API | Replace backend-specific tensor operations with `keras.ops.*` equivalents to restore cross-backend portability |
| TF Serving throughput on an LLM-style autoregressive generation workload falls far short of a vLLM/TensorRT-LLM deployment of the same model | TF Serving's request-level (static) batching groups whole, complete requests together, unlike continuous/iteration-level batching's per-decode-step scheduling — an architectural mismatch for autoregressive generation's highly variable per-request length | Use an LLM-specific serving stack (vLLM, TensorRT-LLM, TGI) for autoregressive generation workloads; reserve TF Serving for fixed-length-inference workloads (classification, embedding, single-pass regression) it was designed around |
| A model trained and exported as a TensorFlow `SavedModel` needs to run in a non-TensorFlow inference environment | `SavedModel` is TensorFlow-specific; the target runtime has no TensorFlow dependency available | Export via ONNX (`T04-export-optimize`) as the framework-agnostic interchange format, then use the target environment's ONNX-compatible runtime |
| `tf.distribute.MirroredStrategy` training shows poor multi-GPU scaling | The same communication-cost considerations `T04-distributed-training` derives for DDP apply directly — e.g. batch size too small to amortize per-step communication overhead, or a topology mismatch (slow interconnect between devices) | Apply the identical diagnostic approach from `T04-distributed-training`: check effective batch size and per-step communication overhead relative to compute time, and confirm device interconnect matches the workload's communication pattern |

---

## Tradeoffs & when NOT to use it

- **Don't choose a framework based on "which is mathematically more powerful."** Since Keras 3, TF2's eager-by-default execution, and PyTorch's own maturity, the frameworks are functionally at parity for the vast majority of modeling tasks — the real decision drivers are ecosystem fit (existing team expertise, deployment infrastructure, cloud provider's first-class support, e.g. TPU access historically favoring TensorFlow/JAX), not raw modeling capability.
- **Don't use TF Serving for LLM-style autoregressive generation workloads expecting vLLM-competitive throughput.** Its request-level batching architecture is a real, structural mismatch for that specific workload shape — this isn't a configuration problem to tune around, it's an architectural difference requiring a different serving stack.
- **Don't reach for Keras 3's multi-backend flexibility if your team has deep, exclusive expertise and tooling investment in one specific backend already.** The portability is valuable specifically when backend flexibility is actually needed (uncertain future hardware/platform requirements, wanting to benchmark the same model across backends) — for a team fully committed to one ecosystem with no near-term reason to switch, it adds a constraint (backend-agnostic-only custom ops) for a benefit that may never be exercised.
- **Don't assume `tf.function`/XLA and `torch.compile`/Inductor are interchangeable in every performance characteristic just because they solve the same conceptual problem.** They're independently engineered systems with their own specific strengths, maturity levels for particular operation types, and debugging tooling — validate actual measured performance for your specific model and hardware target rather than assuming parity from the shared conceptual lineage.

---

## Interview questions

### Q1 — What is the direct mechanical parallel between `tf.function`'s retracing and `torch.compile`'s recompilation, and why do both exist?
**Testing:** recognizing the same underlying idea across two independently-developed frameworks, not memorized API trivia.
**Answer:** `tf.function` traces a Python function into a static graph the first time it's called with a given input signature (shapes/dtypes), caching that graph for reuse; a call with an incompatible signature triggers a **retrace** — building and caching a new graph. This is mechanically identical to Dynamo's **guards**: cheap runtime checks on shape/dtype/value assumptions that, if violated, trigger a **recompilation**. Both exist because tracing a graph once and reusing it repeatedly is only valid as long as the assumptions the trace was built under still hold — a genuinely new shape/signature makes the old trace invalid, requiring a fresh one.
**Follow-up trap:** *"Does this mean tf.function and torch.compile would suffer the identical 'recompilation storm' failure mode from highly variable input shapes?"* — yes, precisely the same failure mode: a function called with a new, distinct shape on nearly every call retraces/recompiles nearly every call in both systems, with compilation cost dominating instead of amortizing — the mitigation is also parallel: an explicit relaxed input signature (TF) or marking dimensions dynamic (PyTorch), compiling once for a range of shapes rather than once per exact shape.

### Q2 — What role does XLA play relative to TensorFlow/JAX, and what's its direct equivalent in the `torch.compile` pipeline?
**Testing:** connecting XLA to Inductor as the same conceptual compiler-backend role.
**Answer:** XLA takes a traced computation graph and lowers it into fused, hardware-specific compiled code — the same category of work (operator fusion, reducing kernel-launch overhead and HBM round-trips) Inductor performs as `torch.compile`'s backend. On TensorFlow, XLA compilation is opt-in (`jit_compile=True`); on JAX, it's the default, always-on execution mode via `jax.jit`, reflecting JAX's functional, trace-and-compile-first design versus TensorFlow's eager-first-with-opt-in-compilation design.
**Follow-up trap:** *"Why is XLA the default on JAX but opt-in on TensorFlow, given both are Google-developed?"* — JAX was designed from the start as a functional, trace-and-compile-oriented framework (its core execution model assumes tracing/compilation as the normal path, not an add-on), whereas TensorFlow 2.x deliberately made eager execution the default specifically to match PyTorch's more immediately-debuggable ergonomics, with `tf.function`/XLA compilation available as an explicit performance opt-in rather than forced on every function — a direct historical consequence of the eager-ergonomics pain TF2 was built to fix.

### Q3 — What does Keras 3 genuinely decouple that neither TensorFlow nor PyTorch independently offered before it existed?
**Testing:** understanding Keras 3's actual novel contribution, not just "it's a high-level API."
**Answer:** It decouples the *modeling API* (how you define layers, models, optimizers) from the *execution backend* (which framework — TensorFlow, JAX, or PyTorch — actually runs the computation), letting the identical model code run against any of them via `KERAS_BACKEND`. Before Keras 3, "Keras" meant a TensorFlow-only API; switching execution frameworks meant rewriting the model entirely. Neither TensorFlow nor PyTorch independently offered "write once, choose your execution backend later" — that specific capability is Keras 3's.
**Follow-up trap:** *"What breaks this portability, and why?"* — using a backend-specific operation (e.g. a raw `tf.*` call) inside a custom layer or loss instead of the backend-agnostic `keras.ops.*` API — any code that directly imports and calls a specific backend's tensor operations ties that model to that one backend, defeating the portability Keras 3's `keras.ops.*` API exists specifically to preserve.

### Q4 — Why is TF Serving's request batching described as "static" or "request-level," and why does that make it a poor fit for LLM autoregressive generation specifically?
**Testing:** connecting TF Serving's batching architecture directly to the continuous-batching argument from the GPU architecture module.
**Answer:** TF Serving's batching (`batching_params.pbtxt`: `max_batch_size`, `batch_timeout_micros`) groups complete, whole inference requests together into one batched `Session::Run()` call — appropriate for fixed-length, single-forward-pass workloads (classification, embedding) where every request in the batch takes the same, bounded amount of compute. Autoregressive LLM generation produces wildly variable-length outputs per request, and grouping *whole* requests together (per `T16-gpu-arch`'s static-batching argument) wastes GPU cycles once shorter requests finish and their batch slots sit idle waiting for the longest request — exactly the problem continuous/iteration-level batching (vLLM, TensorRT-LLM, TGI) solves by swapping requests in/out at every decode step instead of at the whole-request level.
**Follow-up trap:** *"Is this a fixable configuration issue in TF Serving, or a fundamental architectural limitation?"* — architectural, not a tuning problem — TF Serving's batching operates at the request/session-run granularity by design; achieving true iteration-level batching would require a fundamentally different serving architecture operating at the decode-step granularity, which is exactly why LLM-serving-focused teams reach for purpose-built alternatives (vLLM, TensorRT-LLM, TGI) rather than tuning TF Serving's batching parameters further.

### Q5 — What is `tf.GradientTape`, and how does it compare mechanically to PyTorch's autograd?
**Testing:** the explicit-scope-versus-always-on distinction between the two frameworks' autodiff mechanisms.
**Answer:** `tf.GradientTape` requires an explicit `with tf.GradientTape() as tape:` context — only operations executed inside that block are recorded for differentiation, and `tape.gradient(loss, variables)` performs the reverse-mode traversal to compute gradients, conceptually identical to PyTorch's `.backward()` + reading `.grad`. The mechanical difference is that PyTorch's autograd tracks every operation on tensors with `requires_grad=True` by default, always building a graph (per `T04-autograd`), whereas TensorFlow requires explicitly opting into tracking via the `GradientTape` context for each computation you want to differentiate.
**Follow-up trap:** *"What's a practical consequence of this difference for memory usage or code structure?"* — TensorFlow's explicit scoping means you can precisely control exactly which computation gets tracked for gradients (no tracking overhead outside the `with` block at all), which can be a deliberate memory/performance advantage for code that mixes differentiable and non-differentiable computation frequently — PyTorch achieves the equivalent selectivity via `torch.no_grad()` blocks or `.detach()` calls (per `T04-autograd`), an opt-out-by-exception model rather than TensorFlow's opt-in-by-scope model, both achieving the same underlying control with different default assumptions.

### Q6 — A team trained a model in TensorFlow and needs to serve it from an environment with no TensorFlow runtime available. What's the standard path, and why?
**Testing:** connecting this module directly to the export/interchange content from the previous module.
**Answer:** Export the TensorFlow `SavedModel` to ONNX (the framework-agnostic interchange format from `T04-export-optimize`), then run it in the target environment's ONNX-compatible runtime (ONNX Runtime, or a further-compiled TensorRT engine if targeting NVIDIA GPU inference specifically) — `SavedModel` itself is a TensorFlow-specific format with no meaning to a non-TensorFlow runtime, so a genuinely framework-agnostic interchange step is required to bridge the gap.
**Follow-up trap:** *"Would this same path work for a Keras 3 model trained on the JAX backend, or does the export path differ?"* — Keras 3's own model-saving format is backend-agnostic at the Keras API level, but ultimately still needs to go through some framework-specific export path (or ONNX, if the target environment needs full framework independence) depending on which concrete backend actually executed training — Keras 3's multi-backend capability affects which framework you *write* and *train* with, not automatically the deployment/interchange format story, which still depends on the specific backend's own export tooling or a subsequent ONNX conversion step.

### Q7 — How does `tf.distribute.MirroredStrategy` relate to PyTorch's DDP, mechanically?
**Testing:** recognizing the identical data-parallel pattern under a different framework's API name.
**Answer:** Both implement the same core pattern from `T04-distributed-training`: the full model is replicated on every device, each device computes forward/backward on its own data shard, and gradients are synchronized (all-reduced/averaged) across devices before every replica applies an identical update — `MirroredStrategy` is TensorFlow's API name and implementation for exactly the DDP pattern, with `TPUStrategy` extending the same conceptual approach to TPU hardware specifically.
**Follow-up trap:** *"Does the ring all-reduce communication-cost arithmetic from the distributed training module apply identically to MirroredStrategy?"* — the same underlying principle (communication cost scaling with the amount of data synchronized, largely independent of device count for a well-implemented reduction algorithm) applies, though the specific implementation and interconnect characteristics (TPU pod interconnect topology differs from typical GPU cluster interconnects) mean the exact constants and practical scaling behavior can differ from a GPU-based ring all-reduce — the conceptual arithmetic transfers, the specific hardware numbers don't automatically.

### Q8 — Why might a team choose Keras 3 with a JAX backend specifically over a PyTorch-based training stack, given the mathematical content is identical?
**Testing:** ecosystem-fit reasoning rather than assuming one framework is universally "better."
**Answer:** JAX has historically had first-class, deeply-optimized support for TPU hardware specifically (Google's own large-scale training infrastructure leans heavily on JAX/XLA), and JAX's functional, always-compiled execution model can offer performance and scaling advantages for certain large-scale training regimes — a team with access to TPU infrastructure, or wanting JAX's specific functional-transform ecosystem (`vmap`, `pmap` for data/model parallelism expressed functionally) might reasonably choose Keras 3 on a JAX backend, while still getting Keras 3's familiar, more object-oriented modeling API rather than needing to write directly against JAX's more functional-programming-style API.
**Follow-up trap:** *"If that same team later needs to deploy on GPU-only inference infrastructure with no TPU access, does their JAX-backend training choice create a problem?"* — not necessarily a hard blocker, since Keras 3's portability was specifically designed to let a model trained on one backend potentially be used/exported differently for deployment, but it does mean validating that whatever deployment path is chosen (TF Serving, ONNX export, or another route) is actually compatible with a JAX-backend-trained Keras 3 model's specific export/serialization format — a real, concrete thing to verify rather than assume works seamlessly, precisely because backend choice does have downstream export/deployment implications even with Keras 3's API-level portability.

### Q9 — What's the practical, checkable difference between "TensorFlow/PyTorch have converged on ergonomics" and "TensorFlow/PyTorch are now identical for all purposes"?
**Testing:** whether the candidate over-generalizes convergence into false equivalence, a staff-level nuance.
**Answer:** The *ergonomic* convergence (eager-by-default, opt-in graph compilation, guard/retrace mechanics) is real and mechanically near-identical, and Keras 3 further closes the API gap — but the frameworks remain independently-engineered systems with different maturity levels for specific operations, different debugging tooling, different first-class hardware support (historically TPU-JAX/TF versus broader general GPU-PyTorch), and different production-serving ecosystems (TF Serving's specific maturity versus PyTorch-ecosystem-native serving approaches) — "conceptually converged" does not mean "operationally interchangeable for every specific workload," and a real engineering decision should validate the actual, current state of whichever specific capability matters most for the task at hand rather than assuming parity from the shared conceptual lineage.
**Follow-up trap:** *"Give one concrete example where this distinction would actually change a real production decision."* — choosing a serving stack for LLM autoregressive generation: despite TensorFlow and PyTorch's ergonomic convergence at the modeling/training level, TF Serving's request-level batching architecture is a genuine, current limitation for that specific workload relative to PyTorch-ecosystem-native options like vLLM/TensorRT-LLM — a team assuming "the frameworks are basically equivalent now" might default to TF Serving for an LLM deployment and get meaningfully worse throughput than the ecosystem-appropriate choice, a concrete cost of over-generalizing convergence.

### Q10 — Design question: your team has an existing TensorFlow-trained recommendation model currently served via TF Serving with request-level batching, achieving acceptable throughput. A new initiative wants to add an LLM-based re-ranking step to the same serving pipeline. Would you extend TF Serving to handle both, or architect them separately, and why?
**Testing:** staff-level judgment applying this module's batching-architecture distinction to a concrete mixed-workload scenario.
**Answer:** Architect them separately: the existing recommendation model's fixed-length, single-forward-pass workload is exactly what TF Serving's request-level batching handles well, and there's no reason to disturb a working, acceptable-throughput deployment — but the new LLM re-ranking step's autoregressive generation is exactly the workload shape TF Serving's batching architecture handles poorly (per this module's Q4), so it should go through an LLM-appropriate serving stack (vLLM/TensorRT-LLM/TGI) with continuous batching, with the two systems composed at the application/orchestration layer (recommendation candidates from TF Serving feeding into the LLM re-ranker's separate serving endpoint) rather than trying to force one serving architecture to handle both fundamentally different workload shapes well.
**Follow-up trap:** *"What would change your answer if the team specifically wanted to minimize operational complexity (fewer serving systems to maintain) over maximizing throughput for the LLM component?"* — if the LLM re-ranking step's actual throughput/latency requirements are modest (e.g., re-ranking a small candidate set, not high-volume open-ended generation) and operational simplicity is a genuinely higher priority than squeezing maximum LLM throughput, it might be defensible to serve the LLM component through the same infrastructure (even suboptimally) rather than adding a second serving stack — this is a real tradeoff between operational complexity and workload-optimal architecture, and the "right" answer depends on the LLM component's actual measured request volume/latency requirements, not a universal rule that every LLM workload requires a dedicated continuous-batching serving stack regardless of scale.

---

## Red flags that fail you

- Believes TensorFlow and PyTorch differ mathematically or in modeling capability, rather than recognizing the convergence is ergonomic/ecosystem, not mathematical.
- Cannot connect `tf.function`'s retracing to `torch.compile`'s guard-triggered recompilation as the same underlying mechanism.
- Doesn't know what Keras 3's multi-backend capability actually decouples, or thinks "Keras" still means TensorFlow-only.
- Describes TF Serving's batching as equivalent to vLLM-style continuous batching, missing the request-level versus iteration-level distinction.
- Cannot explain the difference between `tf.GradientTape`'s explicit scoping and PyTorch's always-on autograd tracking.
- Recommends switching frameworks or serving stacks without connecting the recommendation to an actual, workload-specific technical reason.

---

## Cheat card

```
HISTORY: TF1.x static graph (tf.Session, no eager values) -> painful debugging
  PyTorch (2017): eager by default -- direct reaction to that pain
  TF2 (2019): eager by default too, tf.function = opt-in graph-mode perf
  torch.compile (2023): opt-in Dynamo tracing -- SAME idea, years later

DIRECT PARALLELS (independently engineered, mechanically identical):
  tf.function TRACE on first call w/ a given input SIGNATURE (shape/dtype)
    incompatible signature -> RETRACE       <-> Dynamo GUARD fails -> RECOMPILE
    variable shapes -> retrace storm        <-> recompilation storm
    fix: explicit input_signature (None=dynamic dim) <-> mark dims dynamic
  XLA (TF/JAX compiler backend)             <-> Inductor (torch.compile backend)
    TF: opt-in via model.compile(jit_compile=True)
    JAX: XLA compile is the DEFAULT (jax.jit) -- functional, compile-first design

KERAS 3 (2023): decouples MODELING API from EXECUTION BACKEND
  KERAS_BACKEND = tensorflow | jax | torch | openvino(inference-only)
  custom ops MUST use keras.ops.* (not tf.*/torch.* directly) to stay portable

tf.GradientTape: EXPLICIT scope (with tf.GradientTape() as tape:) records ops
  tape.gradient(loss, vars) <-> PyTorch .backward()+.grad (always-on by default,
  opt-out via no_grad()/detach() instead of TF's opt-in-by-scope)

tf.distribute.MirroredStrategy <-> PyTorch DDP (same replicate+all-reduce pattern)
  TPUStrategy: same pattern, TPU-specific interconnect/hardware

TF SERVING: mature, SavedModel-specific, C++ runtime (no Python serving overhead)
  versioned model rollout (canary/rollback built in)
  batching_params.pbtxt: max_batch_size, batch_timeout_micros
    -> REQUEST-LEVEL (static) batching -- groups WHOLE requests
    -> poor fit for LLM autoregressive generation (architectural, not tunable)
       vs vLLM/TensorRT-LLM/TGI's CONTINUOUS (iteration-level) batching
  needs non-TF runtime? export SavedModel -> ONNX (T04-export-optimize) as bridge
```

## Sources

- [Keras 3 — About Keras 3 / multi-backend documentation](https://keras.io/getting_started/about/) — accessed 2026-08-03
- [tf.function — TensorFlow API documentation](https://www.tensorflow.org/api_docs/python/tf/function) — accessed 2026-08-03
- [Better performance with tf.function — TensorFlow guide](https://www.tensorflow.org/guide/function) — accessed 2026-08-03
- [TensorFlow Serving Configuration — TFX documentation](https://www.tensorflow.org/tfx/serving/serving_config) — accessed 2026-08-03
- [TensorFlow Serving batching README — GitHub](https://github.com/tensorflow/serving/blob/master/tensorflow_serving/batching/README.md) — accessed 2026-08-03
- [Serving TensorFlow models with TFServing — Keras documentation](https://keras.io/examples/keras_recipes/tf_serving/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
