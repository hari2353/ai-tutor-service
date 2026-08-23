# Production notes -- backprop and autograd

## What you'd actually use

| Concern | This lab | Production |
|---|---|---|
| Gradients | Hand-derived, hand-coded | Autograd (PyTorch `autograd`, JAX `grad`, TF `GradientTape`) -- you never write `backward()` by hand |
| Numerical gradient checking | Manual, run once as a test | Occasionally used to debug a *custom* autograd op (a new CUDA kernel, a custom `Function`), never for standard layers |
| Update rule | Plain SGD | Adam/AdamW almost everywhere; plain SGD (with momentum) survives mainly in some CV/vision training recipes |
| Precision | float64 throughout | Mixed precision (fp16/bf16) with loss scaling, for memory and throughput |
| Scale | One dense matmul, one machine | Distributed data/tensor/pipeline parallelism across hundreds of GPUs |

## What the real ones add over yours

- **Automatic differentiation, not manual chain rule.** Every framework you'll
  actually use builds a computation graph at forward time and walks it backward
  automatically. What you did by hand in this lab -- propagate `dL/dz2` back to
  `dL/da1` back to `dL/dz1` -- is *exactly* what `loss.backward()` does, generically,
  for any graph, not just a 2-layer network. Understanding this lab is what makes
  `.backward()` stop being magic.
- **Numerical stability tricks you didn't need at this scale.** Softmax needs a
  max-subtraction trick to avoid overflow; layer norm needs a careful epsilon in
  the denominator; mixed precision needs loss scaling so small gradients don't
  underflow to zero in fp16. None of these show up in a 2-layer float64 tanh
  network, and all of them show up the moment you scale up.
- **Gradient checkpointing.** This lab's `forward()` caches `X`, `z1`, `a1` for
  every layer -- fine for 2 layers, a real memory problem for 96. Production
  training recompiles the forward pass for consumed activations during the
  backward pass instead of storing all of them, trading compute for memory.
- **Fused kernels.** `X @ W1 + b1` here is three separate numpy calls (matmul,
  broadcast add, tanh). Production kernels fuse linear+bias+activation into one
  GPU kernel launch, because kernel launch overhead dominates at small op sizes.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Gradient check fails only sometimes, at random seeds | `eps` too large (finite-difference truncation error) or too small (floating-point cancellation) | Use `eps` around `1e-5` in float64; compare with both relative and absolute tolerance, never absolute alone |
| Training loss is `NaN` after a few steps | Exploding gradients, or a learning rate too high for the loss landscape | Gradient clipping, a lower learning rate, or better initialization (this lab's `* 0.5` init is a coarse version of what Xavier/He init do carefully) |
| Loss decreases in this lab but not in a 50-layer version of the same architecture | Vanishing gradients through many `tanh` layers -- the exact mechanism `T04-backprop-derivation` derives (`0.25^L` shrinkage) | Residual connections, normalization layers, or a non-saturating activation (ReLU family) |
| `backward()` is correct per this lab's gradient check but training still doesn't converge | Gradient check verifies *correctness*, not *optimization dynamics* -- learning rate, initialization, and data scaling are separate problems | Don't stop debugging at "the gradients are right"; check the loss curve, the learning rate, and input normalization separately |
| Numerical gradient check takes forever on a real model | Finite differences are `O(params)` forward passes -- completely impractical past a few thousand parameters | This is precisely why autograd exists: `O(1)` backward passes regardless of parameter count, via the chain rule computed once per graph, not once per parameter |

## Cost & latency

Finite-difference gradient checking costs `2 × num_params` forward passes --
utterly fine for this lab's ~30 parameters, completely impossible for a model with
millions or billions. That asymmetry (`O(params)` for finite differences vs.
`O(1)` extra backward passes for autograd, regardless of parameter count) is the
entire reason automatic differentiation exists and why every real ML system uses
it instead of what you just implemented by hand.

## The 3 questions an interviewer asks after you describe this

1. *"Your gradient check compares to finite differences. Why can't you use finite
   differences to actually train a big model?"* -- it costs one full forward pass
   *per parameter, per direction* (`2 × num_params` forward passes for one
   gradient), while backprop computes the exact gradient for every parameter in a
   single backward pass -- the entire point of the chain rule as an algorithm, not
   a formula.
2. *"What's the difference between what you wrote and what `loss.backward()` does
   in PyTorch?"* -- yours is hand-derived for one fixed 2-layer architecture;
   PyTorch builds a dynamic computation graph at forward time recording every
   operation, then walks that graph backward generically -- the same chain rule,
   applied automatically to any graph shape.
3. *"Your gradient check passed. Training still doesn't converge on the real
   problem. What do you check next?"* -- gradient correctness and optimization
   dynamics are separate failure modes: check learning rate, weight
   initialization scale, input normalization, and the loss curve shape (does it
   diverge, plateau immediately, or oscillate) before suspecting the gradients
   again.
