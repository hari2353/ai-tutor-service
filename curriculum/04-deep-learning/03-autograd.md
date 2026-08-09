# Autograd From Scratch: micrograd's Value Engine, a Tensor Engine, and Reverse-Mode AD

> **Track:** T04 Deep Learning · **Time:** 3h · **Prereqs:** T04-backprop-derivation · **Updated:** 2026-08-03
> **Module id:** `T04-autograd` · **Tags:** fundamentals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

An autograd engine builds a directed acyclic graph (DAG) during the forward pass — every operation creates a node that remembers its inputs and a small closure implementing that operation's *local* backward rule (its vector-Jacobian product) — and `.backward()` is nothing but a topological sort of that graph followed by walking it in reverse, calling each node's local closure and *accumulating* (never overwriting) into every input's `.grad`, because a value used in multiple places in the graph receives a separate gradient contribution from each use, summed by the multivariable chain rule. This is exactly the layer-by-layer backprop from the previous module, generalized from a strict stack of layers to an arbitrary DAG that permits reused variables, branching, and control flow — Karpathy's micrograd implements this in about 100 lines with a scalar `Value` class; PyTorch's engine is the same algorithm operating on tensors instead of scalars, with two additional real complications: broadcasting (a smaller tensor's gradient must be summed over the dimensions it was broadcast along before it matches that tensor's original shape) and in-place mutation (overwriting a tensor the graph still needs for backward corrupts the recorded computation, caught via a per-tensor version counter). Reverse-mode AD dominates deep learning for a specific, quantifiable reason: with `P` parameters and one scalar loss, reverse mode computes *all* `P` parameter gradients in a single backward pass costing roughly 2x the forward pass, while forward-mode AD (propagating a tangent through the graph rather than an adjoint) would need one full pass *per parameter* — for a network with even a few million parameters, that's the difference between one backward pass and millions of forward passes to get the same gradient, which is exactly why every deep learning framework's default `.backward()`/`grad()` is reverse-mode, and forward-mode is reserved for the (rarer) case of few inputs and many outputs.

## Why this gets asked

Because "explain what `loss.backward()` actually does" is the single cleanest way to separate someone who has used PyTorch from someone who understands it, and because the specific bugs this topic produces — forgotten `zero_grad()`, an in-place operation silently corrupting a graph, a second `.backward()` call crashing because the graph was already freed, a custom `autograd.Function` with a wrong backward — are bugs every senior ML engineer has personally lost hours to, and interviewers ask this precisely to find out if you'd know how to debug them in twenty minutes or in two days. It's also the direct bridge to two topics interviewers care about at a systems level: how `torch.compile` traces this same dynamic graph into something a compiler can optimize (covered in `T04-compile-cuda`), and why gradient checkpointing (`T04-training-engineering`) trades recomputation for the memory this graph consumes by keeping every intermediate tensor alive until its backward runs.

---

## Lineage: past → present → future

**What came before.** Before automatic differentiation, computing a gradient meant either symbolic differentiation (apply calculus rules to an expression tree, exactly, using a computer algebra system) or numerical differentiation (finite differences: perturb each parameter slightly, measure the change in output, divide). Both were dead ends for anything at neural-network scale. Symbolic differentiation suffers "expression swell" — differentiating a composed expression tree via the product/chain rules repeatedly, without recognizing shared subexpressions, produces a symbolic gradient expression that can be exponentially larger than the original function, intractable to even write down for a network with millions of operations. Finite differences require one full forward-pass evaluation *per parameter* (`O(P)` forward passes to get the gradient of all `P` parameters) — for a network with a few thousand parameters this is merely slow; for millions or billions, it is not computationally feasible on any hardware that exists.

**Where it stands now.** Reverse-mode automatic differentiation — first described mathematically by Seppo Linnainmaa (1970, as "the reverse mode of automatic differentiation") and independently rediscovered and popularized for neural networks as "backpropagation" by Rumelhart, Hinton, and Williams (1986) — is the universal solution: build a computation graph during the forward pass, then compute *all* gradients in one reverse traversal at a cost proportional to the forward pass, not to the parameter count. Every major framework (PyTorch, JAX, TensorFlow) implements exactly this algorithm; where they genuinely differ is graph construction style. PyTorch (and originally, distinctively, Chainer before it) builds the graph dynamically, "define-by-run" — every single forward call constructs a fresh graph out of real executed operations, which is thrown away after backward unless explicitly retained, making arbitrary Python control flow (loops, conditionals depending on tensor values) trace naturally. JAX instead traces a function once into a static representation (a "jaxpr") that gets compiled (via XLA) ahead of execution — more rigid about control flow (`jax.lax.cond`/`scan` needed for data-dependent branching) but more amenable to aggressive whole-graph compiler optimization. This is a genuine, live design tradeoff with no single winner: dynamic graphs are more debuggable and more naturally Pythonic; static/traced graphs compile better. PyTorch's own `torch.compile` (via Dynamo/Inductor, covered in `T04-compile-cuda`) is explicitly PyTorch's attempt to get static-graph-style compilation benefits without giving up the dynamic-graph authoring experience.

**Where it's heading.** The two styles are actively converging rather than one displacing the other: `torch.compile` traces PyTorch's dynamic execution into an intermediate representation compilable by Inductor, and `torch.func` (PyTorch's JAX-inspired functional transforms — `vmap`, `grad`, `jvp`, `vjp`, `jacrev`, `jacfwd`) brings composable function-transformation ergonomics into PyTorch without abandoning eager/dynamic execution as the default. Forward-mode AD, historically a footnote in deep learning because it's the wrong tool for many-parameters/one-output problems, is seeing renewed real use for specific workloads where it's actually the right tool: certain scientific-computing/PDE-solving contexts with few inputs and many outputs, and per-example or per-sample gradient computation combined with `vmap` for differential privacy and influence-function-style analyses. None of this changes the core algorithm this module derives — it changes which of forward-mode or reverse-mode gets reached for, and how aggressively the resulting graph gets compiled before execution.

---

## Mental model

```
FORWARD PASS builds a DAG, one node per operation:

   a=2.0   b=-3.0                      each node stores:
     \      /                            .data       (the actual value)
      \    /                             .grad       (accumulator, starts at 0)
     [ d = a*b ]  ---prev:[a,b]--->      ._prev      (which nodes fed this one)
        |                                ._backward  (closure: given self.grad,
        |    c=10.0                                   compute + ACCUMULATE the
        v   /                                         contribution into each
     [ e = d+c ]  ---prev:[d,c]--->                   parent's .grad)
        |
        v
     [ L = e*e ]  ---prev:[e,e]--->     <- e used TWICE: contributions ACCUMULATE

BACKWARD PASS = topological sort, then walk nodes in REVERSE order:

  L.grad = 1.0                          (seed: dL/dL = 1)
    |
    v   L._backward(): e.grad += 2*e.data * L.grad     (local vjp for x*x)
  e.grad = 8.0
    |
    v   e._backward(): d.grad += 1*e.grad; c.grad += 1*e.grad     (local vjp for +)
  d.grad = 8.0, c.grad = 8.0
    |
    v   d._backward(): a.grad += b.data*d.grad; b.grad += a.data*d.grad  (vjp for *)
  a.grad = -24.0, b.grad = 16.0

EVERY NODE'S BACKWARD DOES EXACTLY ONE THING: given the gradient flowing INTO it
from downstream, compute the LOCAL vector-Jacobian product for its own operation,
and += (accumulate, never overwrite) that into each of its inputs' .grad.
```

The one-line mental model: **an autograd engine is a graph of "remember what I did and how to locally undo one step of it, gradient-wise" nodes, and `.backward()` is just calling all those local undo-steps in the correct (reverse-topological) order while summing contributions from anything used more than once.**

---

## How it actually works

### The computation graph and what each node stores

Every value produced by an operation (not a raw input) is a graph node storing four things: its **data** (the actual number/tensor), its **grad** (a gradient accumulator, initialized to zero and only ever added to, never directly assigned to except at the root), its **parents** (the input nodes that produced it — this is what makes topological sorting possible), and its **local backward function** — a closure, created at the moment the operation runs, that knows exactly how to compute *that specific operation's* contribution to its parents' gradients given the gradient this node receives from downstream. Critically, this closure is created during the *forward* pass (it captures the actual input values via closure, e.g. `b.data` for multiplication's backward), which is why building the graph *is* the forward pass — there's no separate "graph construction phase," every operation you run builds one more node as a side effect.

### Why gradients accumulate (`+=`) instead of overwrite (`=`)

The multivariable chain rule for a variable used in multiple downstream computations is a **sum over every path** from that variable to the loss: if `x` feeds into both `p` and `q`, and both `p` and `q` feed into `L`, then `∂L/∂x = (∂L/∂p)(∂p/∂x) + (∂L/∂q)(∂q/∂x)` — a sum, not a single term. Concretely: `L2 = a*a + a` with `a=3.0` gives `L2=12.0`; treating this as `a` used twice (once in the multiplication, once in the addition), the gradient is `dL2/da = 2a + 1 = 7.0` — verified by central finite differences at `a=3.0±1e-6`, which gives `7.000000001866624`, matching to the precision finite differences allow. If the engine *overwrote* `a.grad` instead of accumulating, whichever path's backward ran last would silently clobber the other path's contribution, producing a wrong gradient — this is precisely why every production autograd engine's core accumulation step is `+=`, and precisely why forgetting to zero out `.grad` *between separate training steps* (a different, easily confused issue — see the production table below) causes gradients from unrelated batches to accumulate together.

### Full worked example, verified two ways

Graph: `a=2.0, b=-3.0, c=10.0`, `d = a*b`, `e = d + c`, `L = e*e`.
```
Forward:  d = 2.0 * -3.0 = -6.0
          e = -6.0 + 10.0 = 4.0
          L = 4.0 * 4.0 = 16.0

Backward (seed L.grad = 1.0):
  dL/de = 2*e*L.grad = 2*4.0*1.0 = 8.0                     (local vjp of x*x: 2x)
  dL/dd = dL/de * 1.0 = 8.0                                 (local vjp of +: pass through)
  dL/dc = dL/de * 1.0 = 8.0
  dL/da = dL/dd * b   = 8.0 * -3.0 = -24.0                   (local vjp of a*b w.r.t a: times b)
  dL/db = dL/dd * a   = 8.0 * 2.0  = 16.0                    (local vjp of a*b w.r.t b: times a)
```
Cross-checked against central finite differences (`h=1e-6`): `dL/da ≈ -23.99999999891378`, `dL/db ≈ 16.000000002236447`, `dL/dc ≈ 7.999999993124618` — all matching the hand-derived values to well within finite-difference precision. This two-way verification (derive by hand, confirm by finite difference) is the exact discipline to apply to any custom gradient before trusting it in real code.

### Topological sort: why order matters and how it's computed

A node's local backward function can only be safely called once *all* of its downstream consumers have already contributed their gradient to it — calling it too early would use an incomplete `.grad` (missing contributions that arrive later). A depth-first-search-based topological sort handles this correctly: recursively visit every parent of a node before adding the node itself to the order list, then reverse that list — this guarantees every node appears after all the nodes that depend on it, so walking the reversed list processes consumers strictly before their inputs. In the `micrograd`-style implementation below, this is exactly what `build_topo` does.

### Reverse-mode vs. forward-mode: the actual cost argument, not folklore

**Forward-mode AD** propagates a "tangent" (a directional derivative, formalized via dual numbers `x + x'ε` where `ε²=0`) alongside the ordinary value through the *forward* pass — one forward-mode pass computes a **Jacobian-vector product (JVP)**: the derivative of *every* output with respect to *one* chosen direction in input space. To get the full gradient of a scalar loss with respect to `P` separate parameters, you'd need `P` separate forward-mode passes (one per parameter, or per basis direction), each producing one column of the Jacobian. **Reverse-mode AD** propagates an "adjoint" (a gradient/cotangent) backward through the graph after a single forward pass — one reverse-mode pass computes a **vector-Jacobian product (VJP)**: the derivative of *one* chosen output (here, the scalar loss) with respect to *every* input, simultaneously, in one traversal. For deep learning's defining shape — millions to billions of parameters, one scalar loss — reverse mode computes the *entire* gradient in one backward pass costing roughly 2x the forward pass's cost; forward mode would need one pass per parameter, i.e. millions to billions of passes for the identical result. This asymmetry, not fashion or history, is the entire reason `.backward()` in every deep learning framework is reverse-mode by default, and it is also exactly why forward-mode remains genuinely useful in the opposite regime (few inputs, many outputs — e.g., computing how a handful of physical simulation parameters affect a large output field).

### A minimal, runnable scalar autograd engine (micrograd-style)

```python
import math

class Value:
    def __init__(self, data, _children=(), _op=""):
        self.data = data
        self.grad = 0.0
        self._backward = lambda: None   # local vjp, filled in by each op below
        self._prev = set(_children)
        self._op = _op

    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), "+")
        def _backward():
            self.grad += 1.0 * out.grad     # d(a+b)/da = 1, d(a+b)/db = 1
            other.grad += 1.0 * out.grad
        out._backward = _backward
        return out

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), "*")
        def _backward():
            self.grad += other.data * out.grad   # d(a*b)/da = b
            other.grad += self.data * out.grad   # d(a*b)/db = a
        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.data)
        out = Value(t, (self,), "tanh")
        def _backward():
            self.grad += (1 - t**2) * out.grad   # d(tanh(x))/dx = 1 - tanh(x)^2
        out._backward = _backward
        return out

    def backward(self):
        topo, visited = [], set()
        def build_topo(v):
            if v not in visited:
                visited.add(v)
                for parent in v._prev:
                    build_topo(parent)
                topo.append(v)
        build_topo(self)
        self.grad = 1.0                       # seed: dL/dL = 1
        for v in reversed(topo):
            v._backward()

    def __repr__(self):
        return f"Value(data={self.data}, grad={self.grad})"

# verify against the hand-derived example above
a, b, c = Value(2.0), Value(-3.0), Value(10.0)
d = a * b
e = d + c
L = e * e
L.backward()
print(a.grad, b.grad, c.grad)   # -24.0 16.0 8.0  -- matches the hand derivation exactly
```

`__radd__`/`__rmul__`, subtraction, division, and `pow` follow the same pattern (implement forward, capture a closure computing the local vjp, register it as `_backward`) and are the lab exercise in `labs/python/03-autograd/`, along with extending this exact class to `ReLU` and confirming its gradient is `1` when `data>0` and `0` otherwise (including the boundary case at exactly `0`, which frameworks conventionally treat as gradient `0`).

### From scalar `Value` to a tensor engine: what actually changes

A tensor autograd engine (what PyTorch, JAX, and every real framework implement) is the identical graph-and-reverse-traversal algorithm, with two real additional complications beyond swapping `float` for an array type:

**Broadcasting must be undone in the backward pass.** If `z = x + y` where `x` has shape `(3,1)` and `y` has shape `(1,4)`, the forward pass broadcasts both to shape `(3,4)` for the addition. The backward pass receives `dL/dz` with shape `(3,4)` but must produce `dL/dx` with shape `(3,1)` and `dL/dy` with shape `(1,4)` — each obtained by **summing** `dL/dz` over exactly the dimensions that were broadcast (axis 1 for `x`, axis 0 for `y`), because broadcasting a value along a dimension is equivalent to using that same value in multiple additions along that axis, and (per the accumulation rule above) multiple uses sum their gradient contributions. Forgetting this summation step — e.g., naively returning `dL/dz` unchanged as both `x`'s and `y`'s gradient — is a shape-mismatch bug that is the tensor-engine analogue of the scalar engine's accumulation rule.

**Every operation is a matched forward/backward pair, exactly what `torch.autograd.Function` formalizes.** PyTorch's built-in ops are implemented in C++ this way internally, and the same pattern is exposed to Python for custom ops:
```python
# untested sketch -- illustrates the forward/backward contract, not a complete op
class MyReLU(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        ctx.save_for_backward(x)          # cache what backward will need
        return x.clamp(min=0)

    @staticmethod
    def backward(ctx, grad_output):
        x, = ctx.saved_tensors
        grad_input = grad_output.clone()
        grad_input[x < 0] = 0             # local vjp: relu'(x) is 1 where x>0, else 0
        return grad_input
```
This is the exact same contract as the scalar `Value` class's `_backward` closures — `ctx.save_for_backward` is the tensor-engine equivalent of a closure capturing `self.data`/`other.data`, and `backward`'s job is identical: given the gradient flowing in from downstream (`grad_output`), compute this operation's local contribution to its input's gradient.

### In-place operations and the version counter

If a tensor needed for a backward computation (e.g., `x` in `MyReLU` above, cached via `save_for_backward`) is *mutated in place* after being cached but before backward runs, the cached reference now points to the *wrong* (post-mutation) data — the backward pass would silently compute the gradient of the wrong function. PyTorch prevents this with a **version counter**: every tensor tracks how many times it's been mutated in place, and if a cached tensor's version at backward time doesn't match its version at cache time, PyTorch raises `RuntimeError: one of the variables needed for gradient computation has been modified by an inplace operation` rather than silently computing a wrong gradient — a deliberate fail-loud design choice precisely because the silent-wrong-gradient failure mode is so much worse than a crash.

---

## Build it from scratch

The scalar `Value` engine above **is** the from-scratch implementation for this module; the lab (`labs/python/03-autograd/`) extends it three ways: (1) add `pow`, `__truediv__`, and `ReLU` following the identical closure pattern; (2) build a tiny 2-layer MLP purely out of `Value` objects (no tensors at all) and train it on a toy dataset with plain SGD, confirming every gradient matches `torch.autograd` on the same weights to `1e-6`; (3) extend the engine to operate on Python lists-of-lists as a minimal "tensor" (implementing broadcasting-aware `+` and matrix multiply backward) to directly experience the two additional complications described above, rather than taking them on faith.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Loss/gradients grow unexpectedly across training steps, or training behaves as if using a much larger effective batch | Forgot `optimizer.zero_grad()` (or `model.zero_grad()`) before `.backward()` — gradients from the previous step are still in `.grad` and the new step's gradients accumulate on top, by design of the `+=` accumulation rule | Call `zero_grad()` before every `.backward()` unless deliberately implementing gradient accumulation across multiple micro-batches (see `T04-training-engineering`), in which case the accumulation is intentional and `zero_grad()` is called once per *effective* batch, not per micro-batch |
| `RuntimeError: one of the variables needed for gradient computation has been modified by an inplace operation` | A tensor cached via `save_for_backward` (or needed by an autograd-tracked op) was mutated in place (e.g., `x += 1` or `x[0] = 5`) after being used in the forward pass but before backward ran | Avoid in-place ops on any tensor that requires gradient and feeds into more computation; use out-of-place equivalents (`x = x + 1` instead of `x += 1`) on the autograd-tracked path |
| `RuntimeError: Trying to backward through the graph a second time` | Calling `.backward()` twice on the same graph without `retain_graph=True` — by default, intermediate buffers needed for backward are freed immediately after the first backward call to save memory | Pass `retain_graph=True` if a genuine second backward through the same graph is needed (rare outside of specific multi-loss or meta-learning setups); more often this error indicates an accidental double-backward from a logic bug, not a real requirement |
| A model's parameters silently never update despite training running with no errors | A leaf tensor has `requires_grad=False` (default for freshly created tensors, or explicitly set), or the computation path to it was severed by `.detach()` or a `with torch.no_grad():` block somewhere upstream | Check `param.requires_grad` and confirm no `.detach()`/`no_grad()` sits between the parameter and the loss on the path that should be trainable |
| Second-order gradient (e.g. WGAN-GP style gradient penalty, or a Hessian-vector product) is `None` or raises an error | `create_graph=True` was not passed to the first `.backward()`/`torch.autograd.grad()` call — without it, the graph of the *backward pass itself* isn't tracked, so it can't be differentiated a second time | Pass `create_graph=True` to `torch.autograd.grad()` when the resulting gradient tensor itself needs to be part of a further-differentiable computation (double backward) |

---

## Tradeoffs & when NOT to use it

- **Don't hand-roll an autograd engine for production training code.** This module's `Value` class is a teaching tool — real training should always use a framework's engine (heavily optimized in C++/CUDA, extensively tested for numerical edge cases). Reserve hand-derivation and from-scratch engines for exactly the purpose this module and the previous one serve: building the intuition that makes debugging someone else's engine tractable.
- **Don't reach for forward-mode AD by default.** It's the wrong tool whenever you have many parameters and few (or one) output — which is the overwhelming majority of deep learning training — and using it there would cost one pass per parameter instead of one pass total. It genuinely is the right tool for the opposite shape: few inputs, many outputs (some scientific-computing and certain per-sample-gradient workloads via `vmap`+`jvp`).
- **Don't write a custom `autograd.Function` unless you actually need to.** Most operations compose fine from existing autograd-tracked ops, which already have correct, tested backward implementations; a custom `Function` is warranted when you need a fused/optimized forward pass (e.g., a custom CUDA kernel) whose backward can't be automatically derived from its constituent ops, or when the mathematically correct gradient isn't what naive differentiation of the forward code would produce (e.g., a straight-through estimator for a non-differentiable op).
- **Don't assume `retain_graph=True` is a free fix for "I need to backward twice."** It keeps every intermediate buffer alive across both backward calls, which is a real, sometimes large, memory cost — if you find yourself reaching for it repeatedly in a training loop rather than for a genuine second-order-gradient or multi-loss use case, that's usually a sign of an architectural issue (e.g., accidentally reusing a graph across steps) worth fixing rather than working around.

---

## Interview questions

### Q1 — What four things does a node in an autograd computation graph need to store, and why each one?
**Testing:** the foundational data structure, not just "it remembers the graph."
**Answer:** Its data (the actual computed value), its grad (an accumulator for the gradient flowing back to it, starting at zero), its parent nodes (the inputs that produced it, needed to build the graph structure and topologically sort it), and a local backward closure (created during the forward pass, capturing whatever values it needs to compute that specific operation's contribution to its parents' gradients).
**Follow-up trap:** *"Why must the backward closure be created during the forward pass, not afterward?"* — because it needs to capture the actual input *values* at the time the operation ran (e.g., multiplication's backward needs `other.data` to compute `self.grad += other.data * out.grad`) — those values may change or be unavailable later (especially under in-place mutation), so the closure must snapshot what it needs at creation time.

### Q2 — Why does an autograd engine accumulate (`+=`) into a node's gradient instead of overwriting it, and give a concrete example where overwriting would be wrong.
**Testing:** the accumulation rule as a direct consequence of the multivariable chain rule, not an arbitrary implementation choice.
**Answer:** A value used in multiple places contributes a gradient via each usage path, and the multivariable chain rule sums those contributions: `∂L/∂x = Σ_paths (∂L/∂path)(∂path/∂x)`. Example: `L = a*a + a` with `a=3.0` — `a` is used both in the multiplication and the addition; the correct gradient is `2a+1=7.0` (verified by finite differences at `≈7.0000000019`), and this is only correct because both paths' contributions are summed, not because the last one to run "wins."
**Follow-up trap:** *"If overwriting is wrong, why does forgetting `zero_grad()` between training steps also count as a bug, if accumulation is 'correct'?"* — accumulation across *paths within a single graph and a single `.backward()` call* is mathematically required; accumulation *across separate `.backward()` calls on unrelated graphs* (e.g., different training batches) is not what you want, since those aren't the same multivariable function — `zero_grad()` resets the accumulator between logically separate gradient computations, which is a different concern from within-graph accumulation.

### Q3 — Derive `dL/da` for the graph `d=a*b, e=d+c, L=e*e` with `a=2.0, b=-3.0, c=10.0`, showing every intermediate step.
**Testing:** actual chain-rule execution under pressure, matching the module's worked example.
**Answer:** Forward: `d=-6.0, e=4.0, L=16.0`. Backward: `dL/de = 2*e = 8.0`; `dL/dd = dL/de*1 = 8.0` (addition passes gradient through unchanged); `dL/da = dL/dd * b = 8.0 * -3.0 = -24.0` (multiplication's local vjp with respect to `a` is `b`).
**Follow-up trap:** *"How would you independently verify this is correct without re-deriving it symbolically?"* — central finite differences: `(f(a+h,b,c) - f(a-h,b,c)) / (2h)` for small `h` (e.g. `1e-6`), which gives `≈-23.99999999891378` here, matching the hand-derived `-24.0` to well within the precision finite differences allow — this cross-check habit is the single most useful debugging tool for any hand-derived or custom gradient.

### Q4 — Explain why reverse-mode AD is preferred over forward-mode AD for training a neural network, with the actual cost argument (not just "it's what frameworks do").
**Testing:** the cost-asymmetry argument, which is frequently known as a fact but not as a derivation.
**Answer:** Forward-mode AD computes a Jacobian-vector product per pass — the derivative of all outputs with respect to one chosen input direction — so getting the gradient of a scalar loss with respect to `P` parameters needs `P` separate forward-mode passes. Reverse-mode AD computes a vector-Jacobian product per pass — the derivative of one chosen output (the scalar loss) with respect to *all* inputs simultaneously — so it gets the complete gradient with respect to all `P` parameters in a single backward pass costing roughly 2x the forward pass. For deep learning (millions to billions of parameters, one scalar loss), that's the difference between one backward pass and millions of forward passes for the same result.
**Follow-up trap:** *"When would forward-mode actually be the better choice?"* — the opposite shape: few inputs, many outputs — e.g. computing how a handful of simulation parameters affect a large output field, or certain per-example/per-sample gradient computations paired with `vmap`, where reverse-mode's advantage (many-inputs-one-output) doesn't apply and forward-mode's per-input cost is actually smaller than reverse-mode's overhead for that shape.

### Q5 — What specifically does topological sorting guarantee for the backward pass, and why would skipping it (e.g., just calling backward in the order nodes were created) produce wrong gradients?
**Testing:** whether the ordering requirement is understood mechanically.
**Answer:** Topological sort guarantees every node appears in the order *before* all nodes that depend on it in the forward direction; reversing that order guarantees each node's backward runs only *after* every one of its downstream consumers has already contributed its gradient. Calling backward in naive creation order risks calling a node's backward before some consumer that was created later (but still depends on it through a different path) has contributed — producing an incomplete (too-small) gradient at that node, since not all contributions have arrived yet.
**Follow-up trap:** *"Give a concrete graph shape where creation order and reverse-topological order would actually differ."* — any graph where a node is reused after another operation branches off of it and finishes before the reuse — e.g., if `d` is used to compute both `e1` (created immediately) and, later, after several other unrelated operations, `e2` — creation order might process `d`'s backward before `e2` even exists yet if `d.backward()` were naively called right after `e1`'s creation, whereas topological order correctly waits until both `e1` and `e2` (and everything depending on them) have run.

### Q6 — What are the two additional complications a tensor autograd engine has beyond a scalar engine like micrograd's `Value`?
**Testing:** whether the scalar-to-tensor generalization is understood as a real technical jump, not "just use arrays."
**Answer:** First, broadcasting: when an operation broadcasts a smaller tensor's shape up to match a larger one, the backward pass must *sum* the incoming gradient over exactly the broadcast dimensions to shrink it back to the original tensor's shape before accumulating — omitting this produces a shape mismatch or silently wrong values. Second, in-place mutation: tensors cached for backward (via something like `save_for_backward`) can be corrupted if mutated in place before backward runs, which frameworks detect via a per-tensor version counter and fail loudly on, rather than silently computing a wrong gradient.
**Follow-up trap:** *"Walk through the broadcasting backward for `z = x + y` where `x` is shape `(3,1)` and `y` is shape `(1,4)`."* — forward broadcasts both to `(3,4)` for the add; `dL/dz` arrives with shape `(3,4)`; `dL/dx` is `dL/dz` summed over axis 1 (the dimension `x` was broadcast along) giving shape `(3,1)`; `dL/dy` is `dL/dz` summed over axis 0, giving shape `(1,4)` — each recovers the original tensor's shape by summing exactly the dimensions that were stretched to produce it.

### Q7 — A teammate's custom `torch.autograd.Function` produces a model that trains but converges to a worse loss than an equivalent built-in-ops implementation. How would you debug the custom `Function` specifically?
**Testing:** practical debugging methodology for exactly the failure mode this module warns about.
**Answer:** Isolate the custom `Function` and check its `backward` against a numerical gradient check (finite differences, or `torch.autograd.gradcheck`, on a small, controlled input) independent of the rest of the model — a systematically-wrong-but-not-catastrophic gradient (e.g., a sign error, a missing accumulation, an incorrect broadcast-sum) can produce a model that still trains and still decreases loss, just to a worse optimum, which is exactly the failure mode that "the loss curve looks fine" doesn't catch.
**Follow-up trap:** *"What's a concrete bug in a custom backward that would produce this exact symptom — trains, but converges worse — rather than crashing outright?"* — forgetting to multiply the local derivative by the incoming `grad_output` (e.g., returning `relu'(x)` directly instead of `grad_output * relu'(x)`, silently discarding all upstream gradient scaling information) — this still points gradients in a roughly plausible direction much of the time (since `relu'(x)` is nonnegative) but destroys the correct relative magnitude across the network, converging to a different, worse optimum without ever crashing or producing `nan`.

### Q8 — Why does PyTorch free the computation graph after the first `.backward()` call by default, and what's the actual cost of `retain_graph=True`?
**Testing:** connecting an autograd API detail to the underlying memory-cost reasoning from the previous module.
**Answer:** Every node's local backward closure and cached intermediate tensors (e.g., activations needed for weight gradients, per `T04-backprop-derivation`'s outer-product formula) are kept alive from forward until backward runs, purely to make that one backward pass possible — once backward has run, that memory is normally freed immediately since it's not needed again. `retain_graph=True` keeps all of it alive so a second backward through the *same* graph is possible, at the real cost of holding all those intermediate tensors in memory for as long as the graph is retained, which can be substantial for large models/activations.
**Follow-up trap:** *"Name a legitimate use case for `retain_graph=True` (not a bug workaround)."* — computing multiple losses that each need to backward through a shared upstream computation graph without recomputing the forward pass (e.g., a multi-task model where each task's loss backwards through a shared trunk before the trunk's own combined gradient is needed), or explicit second-order-gradient computations (with `create_graph=True` additionally, for genuine double backward, e.g. WGAN-GP's gradient penalty).

### Q9 — Why does PyTorch raise an error on in-place modification of an autograd-tracked tensor instead of just computing a slightly-off gradient?
**Testing:** the design-philosophy reasoning behind fail-loud vs fail-silent choices in a numerics-critical system.
**Answer:** A backward closure that cached a tensor for later use (e.g. `ctx.save_for_backward(x)`) is implicitly assuming that tensor's *value at cache time*; if it's mutated in place afterward, the cached reference now points to different data, and the "gradient" computed from it would be the gradient of a different function than the one that actually ran forward — silently wrong, with no symptom other than a model that mysteriously underperforms. PyTorch's version-counter check converts this into an immediate, loud, debuggable crash at the exact point of the violation, rather than a silent numerical error that could take days to trace back to its cause.
**Follow-up trap:** *"How would you fix code that triggers this error while still wanting an efficient in-place-style update?"* — replace the in-place operation with its out-of-place equivalent on the autograd-tracked path (`x = x + 1` instead of `x += 1`), reserving genuine in-place mutation for tensors explicitly outside the autograd graph (e.g., inside a `with torch.no_grad():` block, such as an optimizer's parameter update step itself, which legitimately mutates parameters in place because it is not itself part of the graph being differentiated).

### Q10 — Design question: you need the gradient of a model's output with respect to its input (not its parameters) — e.g. for an adversarial example or a saliency map. How do you get it, and what's different from a normal training step?
**Testing:** whether `torch.autograd.grad` vs `.backward()` and `requires_grad` on inputs (not just parameters) are understood as a deliberate, different use of the same engine.
**Answer:** Set `requires_grad=True` on the *input* tensor (normally only parameters have this set during training), run the forward pass, then call `torch.autograd.grad(outputs=loss_or_output, inputs=input_tensor)` (or `.backward()` and read `input_tensor.grad`) to get the gradient with respect to the input specifically — the engine doesn't care whether a leaf is a "parameter" or an "input," it only cares which leaves have `requires_grad=True` and are reachable from the differentiated output; everything else in the mechanics (graph construction, reverse traversal, accumulation) is identical to a normal training backward pass.
**Follow-up trap:** *"If you also want the model's parameter gradients at the same time (e.g. for a combined training + adversarial-example step), does this require two separate backward passes?"* — not necessarily; a single `.backward()` populates `.grad` for *every* leaf with `requires_grad=True` reachable from the loss, whether that leaf is a parameter or an input, in one traversal — the distinction between "getting input gradients" and "getting parameter gradients" is just which leaves you set `requires_grad=True` on and which `.grad` you read afterward, not a different backward mechanism.

### Q11 — What does `create_graph=True` do, and why is it required for computing something like a gradient penalty (WGAN-GP) or a Hessian-vector product?
**Testing:** second-order/higher-order gradient mechanics, a genuine staff-level nuance.
**Answer:** By default, the backward pass itself is computed with plain tensor operations that are *not* tracked by autograd (since normally nothing needs to differentiate through the backward pass itself) — `create_graph=True` makes the backward pass's own operations autograd-tracked, building a graph *of the gradient computation*, so that graph can itself be differentiated again (a second backward pass, computing a gradient of a gradient). A gradient penalty term (`‖∇ₓD(x)‖` in WGAN-GP) needs the *gradient itself* to be part of the loss being optimized, which requires differentiating through the gradient computation — impossible without `create_graph=True` on the first `.backward()`/`grad()` call that produced that gradient.
**Follow-up trap:** *"What's the memory/compute cost implication of `create_graph=True`?"* — since the backward pass's own operations are now tracked and their intermediate tensors kept alive (exactly like any other autograd-tracked forward computation), you pay a similar memory and compute overhead as running an additional forward-pass-worth of tracked computation, on top of the original graph — using it when you don't actually need a second-order gradient is a real, avoidable cost.

---

## Red flags that fail you

- Cannot explain why gradients accumulate (`+=`) rather than overwrite, or can't connect it to the multivariable chain rule's sum-over-paths.
- Believes forward-mode and reverse-mode AD are just "two implementations of the same thing" with no real cost difference.
- Cannot explain what a topological sort buys the backward pass, or why processing order matters at all.
- Thinks `.backward()` and gradient computation happen "during" the forward pass rather than the forward pass building a graph that backward later walks.
- Doesn't know why forgetting `zero_grad()` and encountering the in-place-modification error are two different bugs with two different causes.
- Cannot describe what a custom `autograd.Function`'s `forward`/`backward` pair actually needs to implement.

---

## Cheat card

```
NODE = {data, grad (accumulator, starts 0), parents (_prev), local backward closure}
  closure captures values at FORWARD time (e.g. mult: da += b*dout; db += a*dout)

BACKWARD = topo-sort (DFS: visit parents first, then append self) -> REVERSE it
  -> walk reversed list, call each node's local backward, ACCUMULATE into parents
  seed: root.grad = 1.0

WHY ACCUMULATE not overwrite: chain rule sums over EVERY path a var is used in
  dL/dx = sum_over_paths (dL/dpath)(dpath/dx)
  example: L=a*a+a, a=3.0 -> dL/da = 2a+1 = 7.0 (verified vs finite-diff 7.0000000019)

WORKED GRAPH: a=2.0,b=-3.0,c=10.0, d=a*b=-6.0, e=d+c=4.0, L=e*e=16.0
  dL/de=8.0  dL/dd=8.0  dL/dc=8.0  dL/da=-24.0 (=dL/dd*b)  dL/db=16.0 (=dL/dd*a)
  verify via central finite diff: (f(x+h)-f(x-h))/(2h), h=1e-6

REVERSE-MODE vs FORWARD-MODE (the actual cost argument):
  forward-mode: 1 pass = 1 Jacobian-VECTOR product (1 input direction, ALL outputs)
    -> need P passes for P parameters
  reverse-mode: 1 pass = 1 VECTOR-Jacobian product (1 output, ALL inputs)
    -> need 1 pass for P parameters, given 1 scalar loss
  DL training = millions of params, ONE scalar loss -> reverse-mode wins by millions-to-1
  forward-mode still right tool: few inputs, many outputs (some sci-compute, vmap+jvp)

TENSOR ENGINE = same graph, + 2 real complications:
  BROADCASTING: backward must SUM incoming grad over broadcast dims to restore shape
    z=x+y, x:(3,1) y:(1,4) -> dL/dx = sum(dL/dz, axis=1); dL/dy = sum(dL/dz, axis=0)
  IN-PLACE MUTATION: cached tensor (ctx.save_for_backward) mutated before backward
    -> version counter mismatch -> RuntimeError (fail LOUD, not silently wrong)

torch.autograd.Function: forward(ctx,x)+ctx.save_for_backward(x); backward(ctx,grad_out)
  returns grad_out * local_derivative  <- forgetting to multiply by grad_out = common bug

COMMON BUGS: forgot zero_grad() -> grads accumulate ACROSS steps (different issue
  from within-graph accumulation); double .backward() without retain_graph=True ->
  RuntimeError (graph freed after first backward); create_graph=True needed for
  second-order grads (WGAN-GP penalty, Hessian-vector products)
```

## Sources

- [micrograd — Andrej Karpathy, GitHub](https://github.com/karpathy/micrograd) — accessed 2026-08-03
- [The Fundamentals of Autograd — PyTorch tutorials](https://docs.pytorch.org/tutorials/beginner/introyt/autogradyt_tutorial.html) — accessed 2026-08-03
- [torch.autograd.functional.vjp / jvp — PyTorch 2.9 documentation](https://docs.pytorch.org/docs/2.9/generated/torch.autograd.functional.vjp.html) — accessed 2026-08-03
- [torch.autograd.Function — PyTorch documentation, Extending torch.autograd](https://docs.pytorch.org/docs/stable/notes/extending.html) — accessed 2026-08-03
- Linnainmaa, S. (1970). "The representation of the cumulative rounding error of an algorithm as a Taylor expansion of the local rounding errors" (originating description of reverse-mode automatic differentiation)

## Changelog
- 2026-08-03 — created
