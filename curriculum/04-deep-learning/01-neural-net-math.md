# The Neuron, Forward Propagation, Loss Functions, and a Fully Worked Numerical Forward Pass

> **Track:** T04 Deep Learning · **Time:** 3h · **Prereqs:** T03 (gradient descent, logistic regression, MLE-as-loss) · **Updated:** 2026-08-03
> **Module id:** `T04-neural-net-math` · **Tags:** fundamentals, critical
> **Lab:** `labs/python/01-neural-net-math/`

## The 30-second version

A neural network is a stack of affine transformations `z = Wx + b` separated by nonlinear activation functions `a = f(z)`; without the nonlinearity, any depth of stacked linear layers collapses algebraically into one linear layer, so the nonlinearity is not decoration, it's the entire source of representational power (this is why the universal approximation theorem requires a nonlinear squashing function, not just "more weights"). Forward propagation is just repeated application of that pair, layer by layer, until you reach an output — a scalar for regression, a probability vector via softmax for classification — and a loss function converts that output plus the true label into a single number to minimize: MSE for regression, cross-entropy for classification, because cross-entropy is the negative log-likelihood under a categorical distribution and its gradient with respect to the pre-softmax logits collapses to the beautifully simple `predicted_probs - one_hot_target`. Concretely, for a 2-input, 2-hidden-neuron, 2-output-neuron sigmoid network with weights `w1=0.15, w2=0.20, w3=0.25, w4=0.30` (input→hidden), `w5=0.40, w6=0.45, w7=0.50, w8=0.55` (hidden→output), biases `b1=0.35, b2=0.60`, and inputs `x1=0.05, x2=0.10`, the hidden pre-activations are `net_h1=0.3775, net_h2=0.3925`, giving `out_h1=0.59327, out_h2=0.59688` after sigmoid; propagating those forward gives output pre-activations `net_o1=1.10591, net_o2=1.22492` and final outputs `out_o1=0.75137, out_o2=0.77293`, which against targets `0.01` and `0.99` produce a total squared error of `0.29837`. Every number in that chain is just a dot product, an addition, and a sigmoid evaluation, applied twice — there is no magic step, which is exactly the point: if you can't reproduce this arithmetic by hand you don't yet understand what a forward pass *is*, you've only memorized that `model(x)` returns a tensor.

## Why this gets asked

Because a shocking fraction of engineers who use PyTorch daily have never once multiplied a weight matrix by an input vector with a pencil, and interviewers at the senior+ level know that fluency with `nn.Linear` is not the same skill as understanding what it computes. The question is a filter: can you explain what happens between `model(x)` and `loss.item()` without gesturing at a framework? It also probes whether you understand *why* activations are nonlinear (a shockingly common gap — people can name ReLU and sigmoid but can't explain why linear layers alone are useless), and whether you know which loss function is the mathematically correct choice for which output distribution rather than just copying whichever `nn.XLoss` the tutorial used. Interviewers who have shipped models that silently trained wrong (MSE on a classification head, or forgetting that softmax + cross-entropy needs raw logits, not post-softmax probabilities, to avoid double-applying softmax) ask this because they've personally debugged exactly that bug at 2am.

---

## Lineage: past → present → future

**What came before.** The perceptron (Rosenblatt, 1958) was a single linear threshold unit: it could only separate linearly separable data, and Minsky & Papert's *Perceptrons* (1969) proved it couldn't even compute XOR — a two-input, two-class problem with no single straight line that separates the classes. That result is widely credited with freezing neural network research funding for over a decade (the first "AI winter"), and the pain that killed the single-layer perceptron was precisely this: no amount of clever weight-setting fixes a representational limit, you need to stack layers with a nonlinearity between them to bend the decision boundary at all. The 1986 Rumelhart/Hinton/Williams backpropagation paper (covered in depth in the next module) made training *multi-layer* networks tractable, which is what actually solved the XOR-class problem — a multi-layer perceptron with a hidden layer and a nonlinear activation can represent XOR trivially, but only once you have an efficient algorithm to fit its weights.

**Where it stands now.** The forward-pass mechanics in this module — affine transform, nonlinearity, repeat — have not changed since the 1980s multi-layer perceptron; what has changed relentlessly is which nonlinearity and which loss are default choices, and how the same math is expressed at scale. Sigmoid/tanh hidden activations, standard through the 1990s-2000s, are now essentially extinct in hidden layers of modern deep nets (ReLU-family activations dominate; see the activations module) because sigmoid/tanh saturate and starve gradients in deep stacks — but sigmoid and softmax remain exactly correct and near-universal at the *output* layer, because they are the correct link functions for Bernoulli and categorical likelihoods respectively, which is a live source of confusion: people sometimes think sigmoid is "outdated" and try to remove it from a binary classifier's output layer, which is simply wrong. There is no live disagreement about the forward-propagation math itself — this is settled, textbook material — the live disagreement in the field is entirely about *architecture* (which layers, in what arrangement) and *loss function design* (auxiliary losses, label smoothing, contrastive objectives), which build on top of this chapter rather than replacing it.
​
**Where it's heading.** The core forward-pass arithmetic in this module is permanent — every architecture from a two-neuron toy network to a trillion-parameter mixture-of-experts transformer reduces to affine transforms and nonlinearities at the tensor level, so nothing here is going to become obsolete the way a specific optimizer or framework API might. What continues to evolve is what sits *around* it: attention mechanisms compute more complex functions of multiple positions (covered in T05), losses increasingly combine multiple terms (auxiliary losses, KL regularization terms in RLHF-style training, contrastive losses), and numerics precision (fp8, and experimentally sub-8-bit formats) changes how these same additions and multiplications are actually represented in hardware — but "what is a neuron, what is forward propagation, how does a loss connect them to a scalar" is as stable a piece of knowledge as anything in this curriculum.

---

## Mental model

```
ONE NEURON:
  x = [x1, x2, ..., xn]        input vector
  z = w . x + b                 weighted sum ("pre-activation" / "logit")
  a = f(z)                      nonlinear activation ("post-activation")

  x1 --w1--\
  x2 --w2---+--> [ Σ + b ] --z--> [ f ] --a-->
  x3 --w3--/

ONE LAYER (vectorized, this is all nn.Linear does):
  z = W x + b          W is (out_features x in_features)
  a = f(z)             f applied elementwise

STACKING LAYERS (why nonlinearity is load-bearing, not decorative):
  Two linear layers with NO activation between them:
    z2 = W2(W1 x + b1) + b2 = (W2 W1) x + (W2 b1 + b2) = W' x + b'
  That is STILL one linear function -- depth added ZERO representational power.
  Insert f between them and W2 f(W1 x + b1) + b2 cannot be collapsed into
  one affine map -- THIS is the entire reason deep networks can represent
  more than logistic regression.

FORWARD PASS THROUGH THE WHOLE NETWORK = apply this twice, then a loss:
  x --[W1,b1]--> z1 --f--> a1 --[W2,b2]--> z2 --g--> a2 --[loss vs target y]--> L
     (layer 1: hidden)                  (layer 2: output)
```

The one-line mental model: **a forward pass is nothing but "multiply, add, squash" repeated once per layer, and the loss is the one extra step that turns the network's output and the true label into the single number everything else in deep learning exists to make smaller.**

---

## How it actually works

### The neuron: an affine map plus a nonlinearity

A single artificial neuron computes `z = w · x + b = Σᵢ wᵢxᵢ + b`, then `a = f(z)` for some nonlinear `f`. The weight vector `w` defines a hyperplane in input space; `b` shifts that hyperplane away from the origin (without `b`, every neuron's decision boundary would be forced to pass through the origin, which is an unnecessary and usually false restriction on the data). `f` is what makes the neuron more than "linear regression with a rebrand" — the choice of `f` (sigmoid, tanh, ReLU, GELU, ...) is covered exhaustively in `T04-activations`; this module treats `f` as a black box you plug in, because the forward-propagation mechanics are identical regardless of which one you choose.

### Layers as matrix operations

A layer of `m` neurons applied to an `n`-dimensional input is exactly `m` neurons computed in parallel: stack the `m` weight vectors as rows of a matrix `W` (shape `m × n`), stack the `m` biases into a vector `b` (shape `m`), and the entire layer collapses to `z = Wx + b`, `a = f(z)` with `f` applied elementwise. This is precisely what `torch.nn.Linear(n, m)` stores and computes — its `.weight` is that `W`, its `.bias` is that `b`, and calling the module executes exactly this line. For a batch of `B` inputs stacked as rows of a matrix `X` (shape `B × n`), the same computation becomes `Z = XWᵀ + b` (shape `B × m`, with `b` broadcast across the batch dimension) — this is the only shape gymnastics forward propagation ever requires, and getting `W` vs `Wᵀ` backwards is the single most common shape-mismatch bug when re-deriving this from scratch.

### Why nonlinearity is not optional (the algebra, not just an assertion)

Composing two affine maps `z2 = W2(W1x + b1) + b2` distributes to `z2 = (W2W1)x + (W2b1 + b2)`, which is itself just one affine map (call the effective weight `W' = W2W1` and effective bias `b' = W2b1+b2`). Stack as many linear layers as you like — the composition of any number of affine maps is always exactly one affine map. This means a "deep" network built from linear layers alone has *exactly* the representational capacity of a single linear layer, regardless of depth: it can only ever draw a straight decision boundary (in classification) or fit a hyperplane (in regression). Insert a nonlinear `f` between layers — `z2 = W2 f(W1x+b1) + b2` — and this algebraic collapse is no longer possible; `f` breaks the associativity that let the two matrices multiply together into one. This is the precise, checkable reason (not a hand-wave) that the XOR problem is unsolvable by a single-layer perceptron but trivial for a 2-layer network with a nonlinear hidden activation.

### A fully worked numerical forward pass, by hand

Network: 2 inputs → hidden layer (2 sigmoid neurons) → output layer (2 sigmoid neurons). This is a deliberately small, hand-traceable network — the same arithmetic scales to any width/depth, only the bookkeeping grows.

**Given:**
```
x1 = 0.05,  x2 = 0.10                          (inputs)
w1 = 0.15, w2 = 0.20, w3 = 0.25, w4 = 0.30     (input -> hidden weights)
b1 = 0.35                                       (hidden bias, shared by both hidden neurons)
w5 = 0.40, w6 = 0.45, w7 = 0.50, w8 = 0.55     (hidden -> output weights)
b2 = 0.60                                       (output bias, shared by both output neurons)
target_o1 = 0.01, target_o2 = 0.99              (true labels)
```

**Step 1 — hidden layer pre-activations** (`net_hᵢ = Σ wx + b1`):
```
net_h1 = w1*x1 + w2*x2 + b1 = 0.15*0.05 + 0.20*0.10 + 0.35 = 0.0075 + 0.02 + 0.35 = 0.3775
net_h2 = w3*x1 + w4*x2 + b1 = 0.25*0.05 + 0.30*0.10 + 0.35 = 0.0125 + 0.03 + 0.35 = 0.3925
```

**Step 2 — hidden layer activations** (sigmoid, `σ(z) = 1/(1+e⁻ᶻ)`):
```
out_h1 = σ(0.3775) = 1 / (1 + e^-0.3775) = 0.593269992
out_h2 = σ(0.3925) = 1 / (1 + e^-0.3925) = 0.596884378
```

**Step 3 — output layer pre-activations** (`net_oᵢ = Σ w·out_h + b2`):
```
net_o1 = w5*out_h1 + w6*out_h2 + b2 = 0.40*0.593269992 + 0.45*0.596884378 + 0.60
       = 0.237307997 + 0.268597970 + 0.60 = 1.105905967
net_o2 = w7*out_h1 + w8*out_h2 + b2 = 0.50*0.593269992 + 0.55*0.596884378 + 0.60
       = 0.296634996 + 0.328286408 + 0.60 = 1.224921404
```

**Step 4 — output layer activations:**
```
out_o1 = σ(1.105905967) = 0.751365070
out_o2 = σ(1.224921404) = 0.772928465
```

**Step 5 — loss (sum-of-squared-error, the classic pedagogical choice, `E = ½(target - out)²` per output, summed):**
```
E_o1 = 0.5 * (0.01 - 0.751365070)^2 = 0.5 * (-0.741365070)^2 = 0.274811083
E_o2 = 0.5 * (0.99 - 0.772928465)^2 = 0.5 * (0.217071535)^2 = 0.023560026
E_total = E_o1 + E_o2 = 0.298371109
```

This exact worked example (weights, inputs, and every intermediate number) is the widely-used pedagogical network popularized by Matt Mazur's step-by-step backpropagation writeup — reusing it here is deliberate: the backward pass through this identical network, with these identical numbers, is the worked example in `T04-backprop-derivation`, so you can trace one continuous, self-consistent numerical thread from forward pass through loss through gradient through weight update.

### Loss functions: the mathematically correct choice per output type

A loss function is not a free style choice — it is determined by what probability distribution you are assuming generates your labels, and the "correct" loss is the negative log-likelihood (NLL) under that distribution (this is why "loss function" and "likelihood" are two names for closely related things once you attach a minus sign and take a log).

- **Regression, Gaussian-noise assumption → Mean Squared Error.** `MSE = (1/N) Σ (yᵢ - ŷᵢ)²`. This is exactly the NLL of a Gaussian with fixed variance around the prediction; minimizing MSE is equivalent to maximum-likelihood estimation under that assumption. Sensitive to outliers (squared term), which is precisely why Huber loss (quadratic near zero, linear in the tails) exists as a robust alternative — pick MSE by default, switch to Huber when your label noise has heavy tails (e.g. GPS coordinates, sensor readings with occasional large spikes).
- **Binary classification → Binary Cross-Entropy (BCE).** `BCE = -(1/N) Σ [yᵢ log(p̂ᵢ) + (1-yᵢ) log(1-p̂ᵢ)]`, the NLL of a Bernoulli distribution, applied to a sigmoid output `p̂ = σ(z)`.
- **Multi-class classification → Categorical Cross-Entropy.** `CE = -(1/N) Σᵢ log(p̂ᵢ,ᵧᵢ)` where `p̂ = softmax(z)` and `yᵢ` is the true class index — the NLL of a categorical distribution.

**Worked softmax + cross-entropy numeric example.** Logits `z = [2.0, 1.0, 0.1]`, true class = 0.
```
softmax: exp(z) = [7.389056, 2.718282, 1.105171]  (numerically, subtract max(z)=2.0 first for stability:
                   exp([0, -1, -1.9]) = [1.0, 0.367879, 0.149569])
sum = 1.0 + 0.367879 + 0.149569 = 1.517448
probs = [1.0/1.517448, 0.367879/1.517448, 0.149569/1.517448]
       = [0.659001, 0.242433, 0.098566]
CE loss = -log(probs[0]) = -log(0.659001) = 0.417030
```
The single most useful gradient fact in all of deep learning, worth memorizing outright: **when softmax feeds directly into cross-entropy, the gradient of the loss with respect to the pre-softmax logits is exactly `p̂ - y_onehot`.** For this example, `y_onehot = [1, 0, 0]`, so `∂CE/∂z = [0.659001-1, 0.242433-0, 0.098566-0] = [-0.340999, 0.242433, 0.098566]`. This is not a coincidence of this example — it is a general algebraic identity (the softmax Jacobian and the cross-entropy gradient cancel almost entirely), and it is *why* frameworks provide a fused `softmax + cross-entropy` op (`nn.CrossEntropyLoss` in PyTorch expects raw logits, not post-softmax probabilities, precisely so it can compute this simplified gradient directly and more numerically stably than computing softmax and log separately).

### The classic bug this section exists to prevent

`nn.CrossEntropyLoss` in PyTorch applies `log_softmax` internally and expects **raw logits** as input. Passing it post-softmax probabilities computes `-log(softmax(softmax(z)))` — softmax applied twice — which trains, produces a lower-than-expected but nonzero loss, and silently degrades accuracy without crashing, making it one of the nastiest bugs in this whole space precisely because nothing errors. The single check that catches it: if your model's last layer is `nn.Softmax` or you manually call `.softmax(dim=-1)` before the loss, and the loss is `nn.CrossEntropyLoss`, that is a bug.

---

## Build it from scratch

```python
# verified against the manual arithmetic above -- reproduces the exact numbers
import math

def sigmoid(z):
    return 1 / (1 + math.exp(-z))

def forward(x1, x2, w1, w2, w3, w4, w5, w6, w7, w8, b1, b2):
    net_h1 = w1 * x1 + w2 * x2 + b1
    net_h2 = w3 * x1 + w4 * x2 + b1
    out_h1, out_h2 = sigmoid(net_h1), sigmoid(net_h2)

    net_o1 = w5 * out_h1 + w6 * out_h2 + b2
    net_o2 = w7 * out_h1 + w8 * out_h2 + b2
    out_o1, out_o2 = sigmoid(net_o1), sigmoid(net_o2)

    return (net_h1, net_h2, out_h1, out_h2, net_o1, net_o2, out_o1, out_o2)

result = forward(
    x1=0.05, x2=0.10,
    w1=0.15, w2=0.20, w3=0.25, w4=0.30,
    w5=0.40, w6=0.45, w7=0.50, w8=0.55,
    b1=0.35, b2=0.60,
)
net_h1, net_h2, out_h1, out_h2, net_o1, net_o2, out_o1, out_o2 = result
print(f"out_h1={out_h1:.9f} out_h2={out_h2:.9f}")   # 0.593269992 0.596884378
print(f"out_o1={out_o1:.9f} out_o2={out_o2:.9f}")   # 0.751365070 0.772928465

target_o1, target_o2 = 0.01, 0.99
E_total = 0.5 * (target_o1 - out_o1) ** 2 + 0.5 * (target_o2 - out_o2) ** 2
print(f"E_total={E_total:.9f}")                     # 0.298371109
```

Running this prints exactly the numbers derived by hand above — that agreement is the whole point of the exercise: the framework isn't doing anything you can't do with `math.exp` and five lines of arithmetic. The equivalent 3-line PyTorch version (`nn.Linear(2,2)`, `torch.sigmoid`, `nn.MSELoss()`) computes the identical numbers once you load these exact weights into it; building it both ways and diffing the outputs to `1e-6` is the lab exercise in `labs/python/01-neural-net-math/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Loss decreases but validation accuracy is much worse than expected, no errors thrown | `nn.CrossEntropyLoss` fed post-softmax probabilities instead of raw logits — softmax applied twice, gradient direction still roughly correct but magnitude distorted | Remove any `Softmax`/`.softmax()` before a `CrossEntropyLoss`; only apply softmax explicitly at inference for human-readable probabilities |
| Loss is `nan` within the first few steps | Logits far from zero fed directly into `exp()` without the max-subtraction stabilization, causing overflow | Use framework's fused, numerically-stable softmax/log-softmax (never hand-roll `exp(z)/sum(exp(z))` without subtracting `max(z)` first) |
| Model trains to a mediocre plateau on a clearly nonlinear problem (e.g. XOR-like decision boundary) | Accidentally linear network — missing activation function between layers, or activation applied only after the final layer | Confirm a nonlinearity sits between every pair of weight layers, verify by checking that composing two consecutive layers' weight matrices does NOT reproduce the network's behavior |
| Regression model's loss is dominated by a handful of examples | MSE's squared term overweights outliers/heavy-tailed label noise | Switch to Huber loss (quadratic near zero, linear beyond a threshold `δ`) or clip/winsorize labels if the outliers are known data errors |
| Multi-class model over-confident on wrong predictions (predicted probability near 1.0 on the wrong class) | Hard one-hot targets with plain cross-entropy push logits to extremes with no ceiling | Label smoothing (blend the one-hot target with a small uniform probability mass, e.g. `0.9` true class + `0.1/K` spread across the rest) |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a deep network when the true decision boundary is linear.** If logistic regression already achieves near-ceiling accuracy on your validation set, adding hidden layers adds optimization difficulty and inference cost for no representational gain — always fit the linear baseline first and only add depth if it measurably beats it.
- **Don't use MSE for classification "because it's simpler."** MSE on a softmax output has vanishing gradients when predictions are confidently wrong (the sigmoid/softmax derivative is near zero at the saturated ends), which is exactly where you need the largest gradient signal; cross-entropy's gradient (`p̂ - y`) stays large precisely when the prediction is most wrong. This is a real, frequently-made mistake, not a pedantic style preference.
- **Don't assume more hidden units always help.** A wildly over-parameterized shallow network for a genuinely simple mapping mostly buys slower training and a higher variance solution for no bias improvement — width is a hyperparameter to tune against validation loss, not to maximize.
- **Don't skip the bias term "to keep it simple."** Removing `b` forces every neuron's decision boundary through the origin; this is a real representational restriction, not a negligible simplification, and shows up as an unexplained accuracy ceiling that's maddening to debug if you don't know to check for it.

---

## Interview questions

### Q1 — Write out, in one line, what a single artificial neuron computes.
**Testing:** whether the absolute fundamentals are automatic, not looked up.
**Answer:** `a = f(w · x + b)` — a weighted sum of inputs plus a bias (`z`, the "pre-activation" or "logit"), passed through a nonlinear activation function `f` to produce the output `a`.
**Follow-up trap:** *"What happens if you remove `f` entirely?"* — the neuron becomes pure linear regression; stacking any number of such neurons in layers still computes only an affine function of the input, because composing affine maps yields another affine map.

### Q2 — Prove, don't just assert, that a 10-layer network with no activation functions is no more expressive than a single linear layer.
**Testing:** whether "nonlinearity matters" is understood algebraically or just recited.
**Answer:** Each linear layer computes `zᵢ = Wᵢx + bᵢ`. Composing two: `z2 = W2(W1x+b1)+b2 = (W2W1)x + (W2b1+b2)`, which is itself `W'x + b'` — one affine map. This holds inductively for any number of layers: the product of any number of matrices is still one matrix, so the composition of arbitrarily many linear layers reduces algebraically to exactly one linear layer, regardless of depth.
**Follow-up trap:** *"Does that mean depth is useless without nonlinearity — even for something like PCA-style dimensionality reduction stacks?"* — depth without nonlinearity can still be useful for controlling the *rank* or parameterization of the effective linear map (e.g. a bottleneck of two linear layers `n→k→n` with `k<n` constrains the effective map to rank ≤k, which is genuinely useful, as in linear autoencoders/PCA) — but it adds zero *nonlinear* representational power; that distinction (rank-constrained linear map vs strictly more expressive function class) is the senior-level nuance.

### Q3 — Derive why `net_h1 = 0.3775` for `x1=0.05, x2=0.10, w1=0.15, w2=0.20, b1=0.35`.
**Testing:** can you actually do the arithmetic, not just recognize the formula.
**Answer:** `net_h1 = w1*x1 + w2*x2 + b1 = 0.15*0.05 + 0.20*0.10 + 0.35 = 0.0075 + 0.02 + 0.35 = 0.3775`.
**Follow-up trap:** *"Now give me `out_h1` after a sigmoid."* — `σ(0.3775) = 1/(1+e^-0.3775) ≈ 0.593269992`; failing to know `σ(0) = 0.5` and that positive `z` pushes the output above `0.5` (a fast sanity check without a calculator) is a tell that the candidate has never actually reasoned about the sigmoid's shape.

### Q4 — Why is cross-entropy the "correct" loss for classification instead of MSE, in a precise sense, not just "it works better"?
**Testing:** likelihood-based reasoning, not folklore.
**Answer:** Cross-entropy is exactly the negative log-likelihood of the labels under the categorical (or Bernoulli, for binary) distribution parameterized by the model's softmax (or sigmoid) output — minimizing it is maximum likelihood estimation. MSE assumes Gaussian-distributed continuous targets; applying it to a probability output is not the NLL of any distribution matching the classification setup, and its gradient vanishes when predictions saturate near 0 or 1 exactly where the model is most confidently wrong, unlike cross-entropy's gradient (`p̂-y`), which stays proportional to the error.
**Follow-up trap:** *"What distribution assumption does Huber loss correspond to, and when would you actually prefer it over MSE?"* — Huber loss corresponds to a NLL under a distribution that behaves like a Gaussian near zero error but like a Laplace (heavier-tailed) distribution beyond a threshold `δ` — prefer it when label noise has occasional large outliers you don't want to dominate the gradient (e.g., sensor glitches), and MSE otherwise, since MSE is more efficient (lower variance estimator) under genuinely Gaussian noise.

### Q5 — What is the gradient of cross-entropy loss with respect to the pre-softmax logits, and why is that fact operationally important?
**Testing:** the single most load-bearing gradient identity in the whole curriculum.
**Answer:** `∂CE/∂z = p̂ - y_onehot` — the softmax output minus the one-hot true label, elementwise. It's operationally important because it's why `nn.CrossEntropyLoss` (and equivalents) take raw logits as input rather than post-softmax probabilities: computing softmax and cross-entropy as one fused operation lets the framework use this simplified, numerically stable gradient directly instead of backpropagating through a separate softmax Jacobian and log, which is both slower and less numerically stable.
**Follow-up trap:** *"What actually breaks if someone applies softmax manually before calling `CrossEntropyLoss`?"* — softmax gets applied twice (once manually, once inside the loss), which doesn't crash, still trains (the true class still gets the highest probability under repeated softmax, so gradient direction is roughly preserved), but distorts the gradient magnitude and typically caps achievable accuracy noticeably below the same model trained correctly — a bug that's invisible in the loss curve and only shows up as unexplained underperformance.

### Q6 — Walk through the softmax computation for logits `[2.0, 1.0, 0.1]` and explain the max-subtraction trick.
**Testing:** numerical stability awareness, not just the formula.
**Answer:** `softmax(z)ᵢ = exp(zᵢ)/Σⱼexp(zⱼ)`. Subtracting `max(z)=2.0` from every logit first — giving `[0, -1, -1.9]` — doesn't change the mathematical result (it's an algebraic identity: `exp(zᵢ-c)/Σexp(zⱼ-c) = exp(zᵢ)/Σexp(zⱼ)` for any constant `c`), but keeps every exponent ≤ 0, preventing `exp()` overflow for large logits. Computing: `exp([0,-1,-1.9]) = [1.0, 0.367879, 0.149569]`, sum `= 1.517448`, giving `probs = [0.659001, 0.242433, 0.098566]`.
**Follow-up trap:** *"What happens numerically if you skip the max-subtraction on a logit of, say, 1000?"* — `exp(1000)` overflows to `inf` in float32/float64, and `inf/inf` (in the normalization) produces `nan`, silently poisoning the entire forward pass; every production softmax implementation performs this subtraction internally for exactly this reason, which is why hand-rolled softmax without it is a real, recurring bug in from-scratch implementations.

### Q7 — What role does the bias term play geometrically, and what happens if you omit it?
**Testing:** whether bias is understood as a real degree of freedom, not boilerplate.
**Answer:** `w · x` alone defines a hyperplane through the origin (`w · x = 0` when `x=0`); `b` shifts that hyperplane away from the origin, giving the decision boundary (or regression fit line) freedom to not pass through `(0,...,0)`. Without `b`, every neuron is restricted to hyperplanes through the origin, which is a real, often data-violating constraint — most real datasets aren't centered such that the correct boundary passes exactly through the origin.
**Follow-up trap:** *"If you forgot to add bias, would training still converge?"* — often yes, to a worse solution — gradient descent will still reduce the loss, but the model hits an accuracy ceiling it can't cross no matter how long you train, because the *representable* solution set no longer contains the true decision boundary; this is a capacity bug, not an optimization bug, and more training epochs will not fix it.

### Q8 — What's the difference between `net` (pre-activation) and `out` (post-activation), and why does the distinction matter for backprop?
**Testing:** whether the two intermediate values are kept distinct, since collapsing them is a common source of chain-rule errors later.
**Answer:** `net = Wx+b` is the raw linear combination; `out = f(net)` is what gets passed to the next layer. They matter as separate quantities because the chain rule for backprop needs `∂out/∂net = f'(net)` as one distinct factor, separate from `∂net/∂W = x` (the previous layer's `out`) as another factor — conflating them (e.g., differentiating `f(Wx+b)` as one blob instead of two composed functions) is exactly the kind of shortcut that produces a wrong gradient in a from-scratch implementation.
**Follow-up trap:** *"In the worked example, what is `∂out_h1/∂net_h1` numerically?"* — `σ'(net_h1) = out_h1(1-out_h1) = 0.593269992 * (1 - 0.593269992) = 0.241300709`; knowing that sigmoid's own derivative is expressible in terms of its own output (no need to re-evaluate `σ` at a different point) is the specific fact the next module's derivation leans on.

### Q9 — Compare BCE and categorical cross-entropy: when is each the right choice, and what's the trap of using BCE for a multi-class problem?
**Testing:** whether output-layer architecture and loss choice are correctly paired.
**Answer:** BCE pairs with a sigmoid output and assumes each output is an *independent* binary decision (Bernoulli) — correct for binary classification, or for multi-label classification where multiple classes can be simultaneously true. Categorical cross-entropy pairs with a softmax output and assumes exactly one class is true out of K mutually exclusive options (categorical distribution) — correct for standard single-label multi-class classification.
**Follow-up trap:** *"What breaks if you use BCE (with a sigmoid per class, independently) for a mutually-exclusive multi-class problem?"* — the model can (and often will) predict high probability for more than one class simultaneously since each sigmoid is optimized independently with no constraint that they sum to 1, whereas softmax explicitly couples the classes so raising one class's probability necessarily lowers the others' — using BCE there produces a technically-trainable but conceptually wrong model that doesn't respect the mutual-exclusivity structure of the labels.

### Q10 — In the worked example, why is `E_o2` (0.0236) so much smaller than `E_o1` (0.2748) even though both outputs started from a similar sigmoid computation?
**Testing:** whether the candidate connects the loss value back to how close the prediction is to the target, not just recomputes numbers mechanically.
**Answer:** `out_o1 = 0.751365` vs `target_o1 = 0.01` — a large gap (`0.741365`), squared and halved gives `0.274811`. `out_o2 = 0.772928` vs `target_o2 = 0.99` — a much smaller gap (`0.217072`), squared and halved gives `0.023560`. The loss per output is driven entirely by how far the prediction is from that specific target, not by any property of the computation path that produced it — `out_o1` and `out_o2` are similar in value (both around 0.75-0.77) but their targets are wildly different (0.01 vs 0.99), which is exactly why one output contributes over 10x more to the total loss.
**Follow-up trap:** *"Which weight would receiving the larger gradient update make sense for, intuitively, before even computing it?"* — the weights feeding `net_o1` (i.e., `w5, w6`) should receive a larger update than those feeding `net_o2` (`w7, w8`), since `o1`'s error is much larger — this intuition is confirmed exactly in the backprop module's worked numbers (`delta_o1 ≈ 0.1385` vs `delta_o2 ≈ -0.0381`, an order of magnitude apart).

### Q11 — What's the practical difference between computing a forward pass for one example versus a batch, in terms of the actual matrix shapes involved?
**Testing:** the shape-level understanding needed to not introduce bugs when moving from toy to production code.
**Answer:** For a single example, `x` is a vector (shape `n`), `W` is `(m × n)`, and `z = Wx+b` is a vector (shape `m`). For a batch of `B` examples stacked as rows of matrix `X` (shape `B × n`), the same layer computes `Z = XWᵀ + b` (shape `B × m`), with `b` (shape `m`) broadcast across all `B` rows. The actual arithmetic per example is identical; only the bookkeeping (which dimension is "batch") changes.
**Follow-up trap:** *"What error would you get if you mixed up `XW` vs `XWᵀ`?"* — a shape mismatch exception in most cases (inner dimensions won't align unless the layer happens to be square), which is the "lucky" version of this bug — the unlucky version is when `W` happens to be square and the matmul silently succeeds with transposed semantics, quietly computing the wrong function while producing a plausible-looking (wrong) output with no error at all.

### Q12 — A colleague claims "adding more hidden layers can only help, since it can't hurt representational power." Is that true in practice?
**Testing:** staff-level judgment distinguishing representational capacity from optimization/generalization reality.
**Answer:** Representational capacity, yes — a deeper network with nonlinearities can represent everything a shallower one can (in principle, given the right weights) plus more. In practice, no — deeper networks are harder to optimize (vanishing/exploding gradients, covered next module), need more data to avoid overfitting the extra capacity, and cost more at inference; "can represent more" is not the same claim as "will learn a better solution given your actual data, optimizer, and training budget."
**Follow-up trap:** *"How would you actually settle this argument for a specific dataset?"* — empirically: hold out a validation set, train both configurations with matched compute/tuning budgets, and compare validation loss — theoretical representational capacity arguments don't substitute for measuring what the optimizer actually finds on your data.

---

## Red flags that fail you

- Cannot compute a sigmoid or softmax by hand on small numbers without a calculator or code — this is the entire point of the module and should be automatic.
- Says "cross-entropy is just what everyone uses" instead of connecting it to negative log-likelihood.
- Doesn't know that `nn.CrossEntropyLoss` expects raw logits, not post-softmax probabilities.
- Can't explain, algebraically, why stacked linear layers with no activation collapse to one linear layer.
- Confuses `net` (pre-activation) and `out` (post-activation) as the same quantity.
- Thinks removing the bias term is a harmless simplification.

---

## Cheat card

```
NEURON: a = f(w.x + b)         z=w.x+b is "pre-activation"/"logit", a=f(z) is output
LAYER (vectorized): z = Wx + b (W is out_features x in_features); a = f(z) elementwise
BATCH: Z = X W^T + b  (X is B x n, W is m x n, Z is B x m)

WHY NONLINEARITY MATTERS: composing linear layers stays linear
  W2(W1 x + b1) + b2 = (W2 W1)x + (W2 b1 + b2)  -- still ONE affine map, any depth
  insert f between layers -> breaks this collapse -- THE reason depth adds power

WORKED FORWARD PASS (2-2-2 sigmoid net, x=[0.05,0.10]):
  net_h1=0.3775 net_h2=0.3925 -> out_h1=0.593270 out_h2=0.596884
  net_o1=1.105906 net_o2=1.224921 -> out_o1=0.751365 out_o2=0.772928
  targets [0.01, 0.99] -> E_total (SSE, half-squared) = 0.298371

LOSS = NLL under an assumed distribution:
  regression, Gaussian noise         -> MSE = mean((y-yhat)^2)
  binary classification, Bernoulli   -> BCE = -mean[y log p + (1-y) log(1-p)]
  multi-class, categorical           -> CE  = -mean log(p_true_class)
  heavy-tailed regression noise      -> Huber (quadratic near 0, linear in tails)

KEY IDENTITY: softmax + cross-entropy -> d(CE)/d(logits) = p_hat - y_onehot
  (why frameworks require RAW LOGITS into CrossEntropyLoss, never post-softmax)

softmax([2.0,1.0,0.1]) = [0.659, 0.242, 0.099]; CE vs class0 = -log(0.659) = 0.417
ALWAYS subtract max(z) before exp() in softmax -- prevents overflow -> nan

sigma(z) = 1/(1+e^-z); sigma(0)=0.5; sigma'(z) = sigma(z)(1-sigma(z)), max 0.25 at z=0
BIAS geometric role: shifts hyperplane off the origin -- omit it, boundary forced through 0
```

## Sources

- [A Step by Step Backpropagation Example — Matt Mazur](https://mattmazur.com/2015/03/17/a-step-by-step-backpropagation-example/) — accessed 2026-08-03 (source of the worked-example weights/inputs reused in this module and the next)
- [Deep Learning, Chapter 6: Deep Feedforward Networks — Goodfellow, Bengio, Courville](https://www.deeplearningbook.org/contents/mlp.html) — accessed 2026-08-03
- [torch.nn.CrossEntropyLoss — PyTorch documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
