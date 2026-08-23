# Lab 05: Backprop By Hand

**Track:** T04 Deep Learning · **Time:** 2.5h · **XP:** 50
**Module:** `T04-backprop-derivation`

**You will build:** a 2-layer network (`Linear -> tanh -> Linear -> MSE`) with the
forward and backward passes implemented manually -- no autograd -- and verified
against numerical finite-difference gradients, then a training loop that actually
reduces loss on a fixed seeded problem.

**You will be able to answer:** *"Derive the gradient for a hidden layer weight
matrix by hand, and tell me how you'd know if your `.backward()` implementation
were wrong."*

## Setup

```bash
cd labs/py/05-backprop-by-hand
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                          # only dependencies
```

## The spec

1. **`forward(X)`** -- `z1 = X@W1+b1`, `a1 = tanh(z1)`, `z2 = a1@W2+b2`,
   `y_hat = z2`. Cache `X`, `z1`, `a1` -- `backward()` must reuse them, not
   recompute the forward pass.
2. **`loss(y_hat, y)`** -- mean squared error over every element (not just the
   batch axis) -- `np.mean((y_hat - y) ** 2)`.
3. **`backward(y_hat, y)`** -- the full manual chain rule back to `W1`, `b1`,
   `W2`, `b2`. This is the graded part of the lab: **every** analytic gradient is
   checked element-by-element against a numerical (central-difference) gradient
   computed independently using only `forward()`/`loss()`, to a tight tolerance.
4. **`step(grads, lr)`** -- plain SGD parameter update.
5. **`train(net, X, y, epochs, lr)`** -- the loop: forward, loss, backward, step,
   repeat. Must measurably reduce loss on a fixed seeded regression problem.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Swap the activation** -- replace `tanh` with `ReLU` (and its non-differentiable
   point at 0), re-derive the backward pass, and confirm the gradient check still
   passes. *(Interview: "why does ReLU's gradient check need special handling at
   z=0?")*
2. **Add a third layer** -- extend to `Linear -> tanh -> Linear -> tanh -> Linear`,
   and notice how much of the second hidden layer's backward pass is *identical in
   shape* to the first -- that repetition is exactly what a real autograd engine
   automates.
3. **Softmax + cross-entropy** -- swap the MSE regression head for a classification
   head, re-derive `dL/dz2` (it simplifies beautifully: `softmax(z) - one_hot(y)`),
   and gradient-check it the same way.
4. **Vanishing gradients, empirically** -- stack 10 tanh layers, gradient-check
   still passes, but print the gradient norm at each layer during training and
   watch it shrink geometrically -- the exact mechanism `T04-backprop-derivation`
   describes.
