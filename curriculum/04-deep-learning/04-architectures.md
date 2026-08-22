# MLP → CNN → RNN → LSTM, Raw, Then PyTorch, Then Keras 3

> **Track:** T04 Deep Learning · **Time:** 3h · **Prereqs:** T04-autograd · **Updated:** 2026-08-03
> **Module id:** `T04-architectures` · **Tags:** fundamentals

## The 30-second version

Every architecture in this module is the same "affine transform, then nonlinearity" primitive from `T04-neural-net-math`, specialized by a different assumption about the input's structure: an MLP assumes none (every input dimension can interact with every other, via a full dense weight matrix); a CNN assumes local, translation-invariant structure (a small kernel slides across the input, sharing the same weights everywhere, so a `3×3` kernel over a `32×32×3` image with 64 output channels needs only `3*3*3*64+64=1792` parameters regardless of image size, versus a dense layer's parameter count scaling with the full flattened input); and an RNN/LSTM assumes sequential structure (the same weights are applied at every timestep, with a hidden state carried forward as memory). A vanilla RNN's hidden state update `h_t = tanh(W_h h_{t-1} + W_x x_t + b)` is mathematically identical, unrolled across `T` timesteps, to a `T`-layer deep network with tied weights — which means it suffers *exactly* the vanishing-gradient problem derived in `T04-backprop-derivation`, compounded across sequence length instead of network depth. The LSTM (Hochreiter & Schmidhuber, 1997) fixes this with a separate cell state `c_t` updated *additively* (`c_t = f_t ⊙ c_{t-1} + i_t ⊙ g_t`, where `f_t, i_t, g_t` are learned gates) rather than through a repeated matrix multiplication — the additive update means the gradient path through `c_t` across timesteps is (in the forget gate's absence of saturation) close to `1` rather than a product of many sub-1 factors, structurally mirroring exactly how a residual connection fixes vanishing gradients in a deep feedforward net. A worked single-unit LSTM step (`h_prev=0.1, c_prev=0.2, x=0.5`) gives forget gate `f=0.5987`, input gate `i=0.5474`, candidate `g=0.4053`, output gate `o=0.5890`, new cell state `c=0.3416`, new hidden state `h=0.1937` — every one of those six numbers is a sigmoid or tanh of a weighted sum, computed exactly like the previous modules' worked examples, just with four gates instead of one.

## Why this gets asked

Because architecture choice is one of the first real design decisions in any deep learning system, and interviewers want to know whether you pick an architecture because you understand what structural assumption it encodes about your data, or because it's what a tutorial used. "Why would a CNN beat an MLP on images" and "why do LSTMs handle long sequences better than vanilla RNNs" are two of the most reliably asked architecture questions specifically because both have precise, derivable, non-hand-wavy answers (parameter sharing plus translation invariance; additive versus multiplicative gradient paths across time), and both are frequently answered with vague pattern-matched phrases ("CNNs are good at images," "LSTMs have memory") that don't survive a single follow-up question. It's also a practical fluency check: can you translate the same architecture across the two dominant framework idioms (PyTorch's eager, object-oriented `nn.Module` style; Keras 3's multi-backend functional/sequential style), since real teams work in both depending on the project.

---

## Lineage: past → present → future

**What came before.** The MLP (multi-layer perceptron, viable for training once backprop existed, 1986 onward) treats every input as an unstructured flat vector — applied to an image, this means flattening a `32×32×3` image into a 3072-length vector and connecting it densely to the first hidden layer, discarding all spatial locality (a pixel and the pixel one row below it are just two unrelated vector entries as far as the network's weights are concerned) and requiring a separate weight for every pixel-to-hidden-unit pair. This was computationally and statistically painful at real image resolution: parameter count exploded, and the network had to re-learn "edge detector" from scratch at every possible image location independently, since nothing shared weights across positions. LeCun's convolutional network (LeNet, 1989/1998) fixed exactly this by imposing two structural priors motivated directly by images: locality (a feature depends on a small neighborhood, not the whole image) and translation invariance (an edge detector useful in one location is useful everywhere, so share its weights across all locations) — parameter sharing via the convolution operation, not a new kind of neuron. For sequences, plain feedforward and even CNN architectures don't naturally handle variable-length input with long-range temporal dependencies; the vanilla RNN (Elman/Jordan networks, late 1980s) introduced a recurrent hidden state specifically to carry information across time, but Hochreiter's own 1991 diploma thesis (predating even the more widely-cited 1994 Bengio et al. analysis) demonstrated the vanishing-gradient problem in RNNs specifically, which is what LSTM (Hochreiter & Schmidhuber, 1997) was built to solve.

**Where it stands now.** CNNs remain the default first choice for grid-structured data (images, and increasingly graphs of local structure) where parameter efficiency and inductive locality bias measurably help, especially in the small-to-medium data regime — ResNet-style CNN backbones are still extremely commonly deployed in production computer vision (covered in depth in `T04-computer-vision`), even as Vision Transformers have taken over research leaderboards at large data scale. For sequences, the picture has shifted dramatically: the Transformer (Vaswani et al., 2017 — full treatment in `T05-llm-internals`) has displaced RNN/LSTM as the default architecture for the highest-value sequence modeling tasks (language modeling above all), because self-attention gives direct, non-sequential access to any position in the sequence (no vanishing-gradient-across-time problem at all, since there's no recurrence to vanish through) and parallelizes across the sequence dimension during training, which RNNs fundamentally cannot (each timestep depends on the previous one's hidden state). LSTMs and GRUs are not extinct — they remain genuinely useful in latency-constrained streaming/online settings (constant per-step compute and memory regardless of sequence length so far, unlike attention's quadratic cost in sequence length) and in some time-series/control applications where sequence lengths are short and paired with limited data, where a Transformer's larger parameter count and lack of a sequential inductive bias can actually underperform. The live disagreement is precisely this tradeoff: attention's unbounded-context flexibility and parallel training throughput versus recurrence's constant-memory streaming inference and stronger inductive bias in low-data regimes.

**Where it's heading.** Sub-quadratic sequence architectures (state-space models like Mamba, and various linear-attention variants) are an active 2024-2026 research direction explicitly trying to recover RNN-like constant-per-step inference cost while keeping Transformer-like parallel-trainability and long-range modeling quality — this is a real, ongoing research program, not yet a settled replacement for attention in the highest-stakes production language models as of 2026, and how far it goes is genuinely uncertain. CNNs continue to be refined (efficient mobile/edge architectures, CNN-Transformer hybrids) rather than replaced outright for vision tasks where their inductive bias and parameter efficiency remain a real, measured advantage, particularly outside large-scale-data regimes. What's stable and won't change: the core lesson of this module — that architecture choice is an encoding of a structural prior about your data (locality for CNNs, sequential recurrence for RNN/LSTM, full pairwise interaction for attention) — remains the correct mental model regardless of which specific architecture wins a given task in a given year.

---

## Mental model

```
MLP:  every input connects to every hidden unit -- NO structural assumption
  x (flat vector) --[dense W, full matrix]--> h --[dense W2]--> ... --> out
  param count grows with FULL input size x hidden size -- no sharing at all

CNN: LOCAL + SHARED weights (a small kernel slides across the input)
  image (H x W x C_in)
    |
    v   [same K x K x C_in x C_out kernel, applied at EVERY spatial position]
  feature map (H' x W' x C_out)     <- H' = floor((H - K + 2P)/S) + 1
    |
    v   [pool: downsample, e.g. max over 2x2 windows]
  smaller feature map -- deeper layers see progressively larger RECEPTIVE FIELDS
  (each 3x3 stride-1 layer adds 2 to receptive field: RF(L layers) = 1 + 2L)

RNN: SAME weights applied at EVERY timestep, hidden state carried forward
  x1 --[Wx]--\                          UNROLLED across T steps, this is
              +--> h1 --[Wh]--\           mathematically a T-layer deep net
  x2 --[Wx]--/                 +--> h2 --[Wh]--> ... --> h_T
                               /
  SAME Wx, Wh reused every step  <- weight TYING across time = why vanishing
                                     gradients-across-time is EXACTLY the same
                                     phenomenon as vanishing-across-depth

LSTM: adds a CELL STATE with an ADDITIVE (not multiplicative-only) update
  c_{t-1} --*forget_gate--> + <--*input_gate*candidate-- --> c_t --> (tanh)*output_gate --> h_t
              (f_t in [0,1])   (i_t, g_t)
  c_t = f_t (elementwise*) c_{t-1}  +  i_t (elementwise*) g_t
  THE ADD, not a matrix multiply, is why gradient can flow across many
  timesteps close to unchanged when f_t stays near 1 -- this is the
  "constant error carousel" -- same fix idea as a residual connection.
```

The one-line mental model: **MLP assumes nothing about structure, CNN assumes locality and shares weights across space, RNN shares weights across time, and LSTM adds an additive memory highway through time to survive the exact vanishing-gradient mechanism derived in the previous module.**

---

## How it actually works

### CNN: the convolution operation, output size, and parameter sharing, with real numbers

A 2D convolution slides a `K×K×C_in` kernel across an input of shape `H×W×C_in`, computing a dot product at each position to produce one output value per position per output channel. The output spatial size follows `H' = ⌊(H - K + 2P)/S⌋ + 1` (`P`=padding, `S`=stride) — for `H=32, K=3, P=1, S=1` (the extremely common "3×3, same padding, stride 1" configuration): `H' = ⌊(32-3+2)/1⌋+1 = 32`, i.e. the spatial size is preserved. **Parameter count is independent of input spatial size** — a `Conv2d(in_channels=3, out_channels=64, kernel_size=3)` layer has `3*3*3*64 + 64 (bias) = 1792` parameters regardless of whether the input image is `32×32` or `1024×1024`, because the *same* `1792` numbers are reused (convolved) at every spatial position. Contrast this with a dense layer connecting a flattened `32×32×3=3072`-dimensional input to a 64-unit hidden layer: `3072*64+64 = 196,672` parameters — over 100x more, and that count would grow further with image resolution, while the CNN's would not. This parameter-sharing is precisely the mechanism, not a side effect, of translation invariance: a kernel that has learned to detect a vertical edge produces that same detection wherever the edge appears in the image, because it's the literal same set of weights evaluated at every location.

**Receptive field** — how much of the original input a given feature-map location's value actually depends on — grows with depth: each additional `3×3` stride-1 convolutional layer adds `2` to the receptive field (`RF(L layers) = 1 + 2L`), so `RF(1)=3, RF(3)=7, RF(5)=11, RF(10)=21` — this is *why* deep stacks of small kernels (VGG-style) can see large image regions despite each individual layer only looking at a `3×3` neighborhood, and it's the concrete number to reach for when asked "how deep does this network need to be to see the whole object."

**Pooling** (max or average, over a small window, typically `2×2` with stride 2) downsamples the feature map, reducing spatial resolution and computation for later layers while adding a small amount of local translation invariance (a feature detected anywhere within the pooling window produces the same pooled output) — modern architectures increasingly replace pooling with strided convolutions to let the network learn the downsampling operation rather than fixing it, a design choice covered further in `T04-computer-vision`.

### RNN: the recurrence equation and why it's a tied-weight deep network in disguise

A vanilla RNN updates its hidden state at each timestep with `h_t = tanh(W_h h_{t-1} + W_x x_t + b)`, and produces an output (if needed) via a separate readout `y_t = W_y h_t + b_y`. Unrolling this across `T` timesteps produces a computation graph that looks *exactly* like a `T`-layer deep feedforward network, with one crucial difference from an ordinary deep net: **the same `W_h` (and `W_x`) is reused at every layer/timestep** (weight tying), rather than each layer having independent weights. This is the entire reason "backpropagation through time" (BPTT) is not a separate algorithm from ordinary backprop — it's the identical reverse-mode chain rule from `T04-autograd`, applied to this specific unrolled, weight-tied graph, with gradients for the shared `W_h` accumulated (summed) across every timestep's contribution, following the exact same accumulation rule that any reused parameter gets in the autograd module. And because it's structurally a deep network with `tanh` activations (derivative ceiling `<1`, same as sigmoid's saturation problem from the backprop module) repeated `T` times, a long sequence (`T=100` or `T=1000`) produces the *identical* vanishing-gradient mathematics as a `100`- or `1000`-layer feedforward network — `0.25^100` is not a typo-scale number, it is functionally exactly zero in float32.

### LSTM: the four gates, worked with actual numbers

The LSTM (Hochreiter & Schmidhuber, 1997) introduces a separate **cell state** `c_t`, updated by three sigmoid "gates" (each producing a value in `[0,1]`, functioning as a *soft, learned, per-dimension switch*) and one `tanh` candidate:
```
f_t = sigmoid(W_f . [h_{t-1}, x_t] + b_f)      "forget gate": how much of c_{t-1} to keep
i_t = sigmoid(W_i . [h_{t-1}, x_t] + b_i)      "input gate": how much of the new candidate to add
g_t = tanh(W_g . [h_{t-1}, x_t] + b_g)         "candidate": new information proposed this step
o_t = sigmoid(W_o . [h_{t-1}, x_t] + b_o)      "output gate": how much of c_t to expose as h_t

c_t = f_t (elementwise*) c_{t-1}  +  i_t (elementwise*) g_t      <- THE ADDITIVE UPDATE
h_t = o_t (elementwise*) tanh(c_t)
```
**Worked single-unit example** (`h_prev=0.1, c_prev=0.2, x=0.5`, small illustrative weights):
```
zf = 0.5*h_prev + 0.5*x + 0.1 = 0.4         -> f = sigmoid(0.4) = 0.598688
zi = 0.4*h_prev + 0.3*x + 0.0 = 0.19        -> i = sigmoid(0.19) = 0.547358
zg = 0.3*h_prev + 0.6*x + 0.1 = 0.43        -> g = tanh(0.43)    = 0.405321
zo = 0.6*h_prev + 0.2*x + 0.2 = 0.36        -> o = sigmoid(0.36) = 0.589040

c_new = f*c_prev + i*g = 0.598688*0.2 + 0.547358*0.405321 = 0.119738 + 0.221856 = 0.341594
h_new = o*tanh(c_new) = 0.589040 * tanh(0.341594) = 0.589040 * 0.328829 = 0.193677
```
(minor rounding differences in the last digit versus a raw float computation are normal at this precision.) **Why the additive update matters mechanically**: backpropagating through `c_t = f_t⊙c_{t-1} + i_t⊙g_t` with respect to `c_{t-1}` gives `∂c_t/∂c_{t-1} = f_t` (elementwise) — a single multiplicative factor per timestep, not the product of an activation derivative *and* a weight matrix the way a vanilla RNN's hidden-state recurrence requires. If the forget gate `f_t` learns to stay close to `1` for information that needs to persist, the gradient flowing backward through the cell state across many timesteps is a product of many factors each close to `1`, not close to `0.25` — this is the "constant error carousel," Hochreiter & Schmidhuber's own term for exactly this mechanism, and it is structurally the same fix idea as a residual connection's `I + Jf` Jacobian from the previous module: an additive path that lets gradient bypass the lossy multiplicative path.

### Same architectures, in PyTorch

```python
import torch.nn as nn

mlp = nn.Sequential(nn.Linear(784, 256), nn.ReLU(), nn.Linear(256, 10))

cnn_block = nn.Sequential(
    nn.Conv2d(in_channels=3, out_channels=64, kernel_size=3, padding=1),  # 1792 params
    nn.ReLU(),
    nn.MaxPool2d(kernel_size=2, stride=2),
)

# nn.LSTM expects input shape (seq_len, batch, input_size) by default,
# or (batch, seq_len, input_size) with batch_first=True
lstm = nn.LSTM(input_size=32, hidden_size=128, num_layers=2, batch_first=True)
# output, (h_n, c_n) = lstm(x)   -- output: per-timestep hidden states; h_n/c_n: final states
```

### Same architectures, in Keras 3

Keras 3 (current release line as of 2026 is 3.x, e.g. 3.14) is a genuinely multi-backend framework — the identical model code runs unchanged on TensorFlow, JAX, PyTorch, or OpenVINO (inference-only) backends, selected via the `KERAS_BACKEND` environment variable or `~/.keras/keras.json`, which is the single biggest practical difference from pre-3.0 Keras (which was TensorFlow-only):
```python
import keras
from keras import layers

mlp = keras.Sequential([
    layers.Input(shape=(784,)),
    layers.Dense(256, activation="relu"),
    layers.Dense(10),
])

cnn_block = keras.Sequential([
    layers.Input(shape=(32, 32, 3)),
    layers.Conv2D(64, kernel_size=3, padding="same", activation="relu"),
    layers.MaxPooling2D(pool_size=2),
])

lstm_model = keras.Sequential([
    layers.Input(shape=(None, 32)),          # (timesteps, features), batch dim implicit
    layers.LSTM(128, return_sequences=False),
])
```
The functional/mechanical content is identical to the PyTorch version (same convolution math, same LSTM gate equations); the differences are almost entirely API ergonomics (`Sequential`/functional/subclassing model-building styles, `padding="same"` as a string versus PyTorch's explicit numeric padding, `.fit()`'s built-in training loop versus PyTorch's explicit training loop) rather than anything mathematically different.

---

## Build it from scratch

A from-scratch (`numpy`-only) 2D convolution — nested loops over output position and kernel offset, computing the dot product directly — and a from-scratch vanilla-RNN-cell forward/backward pass (reusing the `Value`-engine style from `T04-autograd`, or plain `numpy` with manually-derived gradients following `T04-backprop-derivation`'s pattern) are the lab exercises in `(lab pending)`; both are deliberately small enough (a `5×5` toy image, a 3-timestep toy sequence) to hand-verify against `torch`'s equivalent `nn.Conv2d`/`nn.RNNCell` outputs to `1e-6`, exactly the verification discipline established in the previous two modules. The from-scratch LSTM cell (four gates, the additive cell-state update) is the natural extension once the vanilla RNN cell works, and directly reproduces the worked numeric example above.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| CNN accuracy plateaus far below expectation on a dataset with clear local/translation-invariant structure | Network too shallow for the receptive field the task needs (small objects need less depth, whole-scene context needs more) | Compute the needed receptive field for the task's object scale, use `RF(L)=1+2L` (for 3x3 stride-1 stacks) to estimate required depth, or use dilated/atrous convolutions to grow receptive field faster without adding depth |
| Vanilla RNN's loss stalls on long sequences (T > ~20-30) but trains fine on short ones | Vanishing gradients through time — mathematically identical to the previous module's deep-network vanishing gradients, just across the time dimension instead of the layer dimension | Switch to LSTM/GRU (additive cell-state gradient path), or truncate BPTT to a manageable window if long-range dependencies aren't actually required for the task |
| LSTM training loss is `nan` within the first few steps despite the architecture being designed to resist vanishing gradients | LSTMs resist *vanishing* gradients via the additive cell-state path but do not automatically prevent *exploding* gradients (a large `W` in any of the four gate computations, or in the readout, can still explode) | Apply gradient clipping (near-universal for RNN/LSTM training in practice, more so than for standard feedforward/CNN training) |
| A Keras 3 model trains correctly on one backend but errors or behaves differently on another (e.g. TensorFlow vs JAX) | A backend-specific operation was used directly (e.g. `tf.` ops mixed into Keras 3 code) instead of the backend-agnostic `keras.ops` API | Use `keras.ops.*` for any custom operation inside a Keras 3 model instead of importing backend-specific tensor ops directly, to preserve multi-backend portability |
| A CNN's parameter count is dramatically higher than expected for a given layer | Using a fully-connected layer to flatten a large feature map directly into a dense classification head, rather than global average pooling first | Replace `Flatten() -> Dense(large)` with `GlobalAveragePooling2D() -> Dense(small)` where the task permits it, cutting parameters by orders of magnitude with often negligible accuracy cost (the standard modern CNN classifier head pattern) |

---

## Tradeoffs & when NOT to use it

- **Don't use an MLP on raw image or sequence data if you can avoid it.** Discarding the CNN's locality prior or the RNN/attention's sequential prior throws away real inductive bias, typically costing both parameter efficiency and accuracy for no benefit — reserve MLPs for genuinely unstructured/tabular input, or as the final classification head on top of a structure-aware backbone.
- **Don't default to an LSTM for new sequence-modeling work in 2026 without checking whether a Transformer is simply the better choice.** For most large-data, offline-trainable sequence tasks (especially language), attention-based architectures now dominate on quality and training throughput; LSTMs remain the right choice specifically when constant-memory streaming inference matters more than peak quality, or in genuinely low-data regimes where a smaller, more strongly-biased model generalizes better.
- **Don't stack convolutional layers indefinitely assuming "deeper is always better."** Beyond the receptive field the task actually needs, additional depth mostly adds vanishing-gradient risk (mitigated by residual connections, per the previous module) and inference cost without accuracy benefit — size depth to the problem's actual required receptive field and data budget, and validate empirically.
- **Don't assume Keras 3's backend-agnostic promise is absolute.** Some ops, custom layers, or lower-level backend-specific features may not have perfect parity across TensorFlow/JAX/PyTorch backends; test the specific model on the target backend before assuming portability, especially for anything beyond standard layers.

---

## Interview questions

### Q1 — Why does a CNN need dramatically fewer parameters than an MLP for the same image input, and what specific structural assumption buys that?
**Testing:** parameter sharing as the actual mechanism, not "CNNs are efficient" as a slogan.
**Answer:** A `Conv2d(3->64, kernel=3)` layer has `3*3*3*64+64=1792` parameters regardless of image size, because the *same* kernel is convolved (reused) at every spatial position — this is the parameter-sharing structural assumption (translation invariance: a useful feature detector at one location is useful everywhere). A dense layer connecting a flattened `32x32x3=3072` input to a 64-unit layer needs `3072*64+64=196,672` parameters — over 100x more — because it assumes no shared structure at all, learning an independent weight for every input-position/hidden-unit pair.
**Follow-up trap:** *"Does that parameter savings come with any cost?"* — yes: the locality/translation-invariance assumption is a real inductive bias, not free lunch — for tasks where features genuinely aren't local or translation-invariant (e.g. some tabular or graph-structured data with no spatial meaning), imposing this assumption can hurt rather than help, which is exactly why CNNs are chosen *because* the data has this structure, not universally.

### Q2 — Derive the output spatial size of a `32x32` input through a `3x3` kernel, stride 1, padding 1.
**Testing:** the actual formula, not a memorized "same padding" fact.
**Answer:** `H' = floor((H-K+2P)/S)+1 = floor((32-3+2)/1)+1 = floor(31)+1 = 32` — spatial size is preserved, which is exactly why this specific configuration (3x3, stride 1, padding 1) is called "same" padding.
**Follow-up trap:** *"What's the output size with the same kernel and padding but stride 2?"* — `floor((32-3+2)/2)+1 = floor(15.5)+1 = 15+1 = 16` — stride 2 roughly halves spatial resolution, which is the standard way modern architectures downsample without a separate pooling layer.

### Q3 — What is receptive field, and how much does one additional 3x3 stride-1 convolutional layer add to it?
**Testing:** a specific, checkable number, not a vague "sees more context" answer.
**Answer:** Receptive field is how much of the original input a given feature-map location's value actually depends on. Each additional 3x3 stride-1 layer adds 2 to the receptive field: `RF(L layers) = 1 + 2L`, so 5 layers give `RF=11`, 10 layers give `RF=21`.
**Follow-up trap:** *"If you need a receptive field of ~50 pixels but want to avoid adding 25 layers, what are your options?"* — dilated/atrous convolutions (spacing out kernel taps to grow receptive field faster per layer without adding depth or parameters), strided convolutions/pooling (downsampling trades spatial resolution for effectively larger receptive field per subsequent layer), or larger kernels — each is a real, used tradeoff, not just "add more layers."

### Q4 — Explain why "backpropagation through time" is not a separate algorithm from ordinary backpropagation.
**Testing:** connecting BPTT directly to the reverse-mode AD/accumulation mechanics from the previous two modules.
**Answer:** Unrolling an RNN across `T` timesteps produces an ordinary computation graph — the fact that it's "recurrent" just means the same weights (`W_h`, `W_x`) are reused (tied) at every timestep, which is exactly the "value used multiple times" case from the autograd module: the gradient for the shared weight accumulates (sums) contributions from every timestep, following the identical accumulation rule any reused parameter gets. BPTT is reverse-mode automatic differentiation applied to this specific weight-tied, unrolled graph — no new algorithm required.
**Follow-up trap:** *"Why does this mean a vanilla RNN suffers vanishing gradients across long sequences?"* — because the unrolled graph is structurally a `T`-layer deep network with `tanh` activations (derivative ceiling below 1) repeated at every layer/timestep — the exact same product-of-derivatives argument from `T04-backprop-derivation` applies, just with `T` (sequence length) playing the role of `L` (network depth); `0.25^100` is effectively zero, so a 100-timestep vanilla RNN has essentially no usable gradient signal reaching early timesteps.

### Q5 — Write out the four LSTM gate equations and explain what each gate does conceptually.
**Testing:** whether the gates are understood individually, not just "LSTM has gates."
**Answer:** `f_t = sigmoid(W_f.[h_{t-1},x_t]+b_f)` (forget gate: how much of the previous cell state to retain, in `[0,1]` per dimension); `i_t = sigmoid(W_i.[h_{t-1},x_t]+b_i)` (input gate: how much of the new candidate to write in); `g_t = tanh(W_g.[h_{t-1},x_t]+b_g)` (candidate: the new information proposed this step, in `[-1,1]`); `o_t = sigmoid(W_o.[h_{t-1},x_t]+b_o)` (output gate: how much of the updated cell state to expose as the hidden state this step).
**Follow-up trap:** *"Given h_prev=0.1, x=0.5, and forget-gate weights W_f=[0.5,0.5], b_f=0.1, compute f_t."* — `z_f = 0.5*0.1+0.5*0.5+0.1=0.4`, `f_t=sigmoid(0.4)=0.598688` — being able to actually execute this arithmetic, not just recite the formula, is the specific bar this module sets.

### Q6 — Why does the LSTM's additive cell-state update fix the vanishing-gradient problem that plagues vanilla RNNs?
**Testing:** the mechanical derivative argument, connecting directly to the residual-connection fix from the previous module.
**Answer:** `c_t = f_t⊙c_{t-1} + i_t⊙g_t` gives `∂c_t/∂c_{t-1} = f_t` (elementwise) — a single multiplicative factor per timestep that the network *learns* and can keep close to 1 for information that needs to persist, rather than a forced product of a weight-matrix Jacobian and a saturating activation derivative (the vanilla RNN's mechanism). If `f_t≈1` across many timesteps, the gradient flowing backward through the cell state stays close to unchanged — the "constant error carousel," structurally the same idea as a residual connection's identity-plus-learned-path Jacobian.
**Follow-up trap:** *"Does this mean LSTMs are completely immune to vanishing or exploding gradients?"* — no; the additive cell-state path specifically resists *vanishing* gradients when the forget gate learns to stay open, but the four gates' own weight matrices (in the hidden-state-dependent computations, and especially the readout layers) can still contribute to vanishing or exploding gradients through the ordinary multiplicative mechanism — LSTMs mitigate, they don't eliminate, and gradient clipping remains standard practice for RNN/LSTM training in production regardless.

### Q7 — In production, why might you still choose an LSTM over a Transformer in 2026, given Transformers dominate most leaderboards?
**Testing:** whether the candidate has real judgment about the tradeoff rather than reflexively choosing the "state of the art" architecture.
**Answer:** LSTM inference cost per new timestep is constant (fixed hidden-state size, regardless of how much history precedes it), while attention's cost to process a new token grows with total context length (quadratic in full attention over the full sequence, or at minimum requires managing a growing KV cache) — for genuinely latency- and memory-constrained streaming/online applications (e.g. certain real-time control or on-device applications with long, continuous input streams), that constant-cost property can matter more than raw quality. LSTMs can also generalize better than a much larger Transformer in genuinely low-data regimes, where the LSTM's stronger sequential inductive bias reduces the effective hypothesis space the optimizer needs to search.
**Follow-up trap:** *"What would you check empirically before committing to that choice, rather than reasoning about it purely theoretically?"* — actual measured latency/memory on the target deployment hardware at the required context length, and validation performance on held-out data for both architectures under a matched (small) data budget — theoretical inductive-bias arguments are directional, not a substitute for measuring on the actual task and constraints.

### Q8 — What's the practical difference between PyTorch's and Keras 3's approach to specifying a model, and what's the one thing to watch for with Keras 3's multi-backend promise?
**Testing:** framework fluency and an awareness of Keras 3's real limitation, not just API syntax differences.
**Answer:** PyTorch is eager/imperative by default — you write a `forward()` method as literal Python control flow, and the graph is built dynamically every call (per `T04-autograd`). Keras 3's `Sequential`/functional API declares a static architecture up front, with `.fit()` providing a built-in training loop (versus PyTorch's typically explicit loop), and — the genuinely new capability since Keras 3.0 — the identical model code can run on TensorFlow, JAX, or PyTorch backends by switching `KERAS_BACKEND`. The thing to watch for: using a backend-specific op (e.g. a raw `tf.` call) inside a Keras 3 model breaks that portability; the backend-agnostic `keras.ops.*` API must be used for custom logic to preserve it.
**Follow-up trap:** *"If you needed genuinely custom, non-standard control flow inside a layer (e.g. a data-dependent branch), which framework's default authoring style makes that easier, and why?"* — PyTorch's eager/imperative style generally makes arbitrary Python-level control flow (including data-dependent branching) more natural to write directly in `forward()`, since the graph is built fresh from whatever code actually executes each call; Keras 3's more declarative style (especially on non-eager backends like a compiled JAX/XLA backend) can require more careful use of backend-agnostic conditional ops (`keras.ops.cond`-style constructs) for genuinely data-dependent branching to remain portable across backends.

### Q9 — Why does replacing `Flatten() -> Dense(large)` with `GlobalAveragePooling2D() -> Dense(small)` in a CNN classifier head reduce parameters so dramatically, and what's the tradeoff?
**Testing:** a concrete, commonly-encountered production parameter-reduction pattern.
**Answer:** `Flatten()` turns a `(H,W,C)` feature map into a single `H*W*C`-length vector, so the following dense layer's parameter count scales with the full spatial extent of the feature map (potentially hundreds of thousands of connections). `GlobalAveragePooling2D()` instead averages each channel over its entire spatial extent, producing a single `C`-length vector regardless of `H, W` — the following dense layer's parameter count then scales only with the (much smaller) channel count, cutting parameters by orders of magnitude.
**Follow-up trap:** *"What information does global average pooling discard that Flatten preserves, and when would that matter?"* — it discards all spatial position information within the feature map (averaging destroys "where" a feature was detected, keeping only "how much" of it was present overall) — this matters for tasks that need spatial localization (e.g. detection, segmentation, covered in `T04-computer-vision`), where architectures deliberately avoid collapsing spatial information this early, but is a non-issue (and a clear win) for whole-image classification, where only "is this feature present somewhere" typically matters.

### Q10 — Design question: you're building a model to classify fixed-length audio clips (a few seconds each) into a small set of categories. Would you reach for a CNN, an RNN/LSTM, or something else, and why?
**Testing:** staff-level architecture-selection judgment applied to a concrete, moderately ambiguous scenario.
**Answer:** For fixed-length clips with a whole-clip classification target (not a per-timestep or streaming task), a 1D (or 2D, over a spectrogram) CNN is frequently the pragmatic first choice: it exploits local, translation-invariant structure in the time (or time-frequency) dimension efficiently, trains with better parallelism than a recurrent architecture (no sequential dependency across timesteps during training), and doesn't need to model unbounded-length dependencies since the clip length is fixed and short. An RNN/LSTM would be the better-justified choice specifically if the task were genuinely streaming (classify as audio arrives, before the clip ends) or needed to model long-range temporal dependencies a local CNN receptive field can't reach without significant depth.
**Follow-up trap:** *"What would change your answer if the clips were minutes long instead of seconds, with important information at arbitrary time offsets?"* — at that length, a plain CNN's receptive field would need substantial depth to span the full clip, and attention-based architectures (processing a spectrogram as a sequence of patches/frames with self-attention, e.g. audio-spectrogram-transformer-style models) become more competitive by giving direct access to any time offset without the receptive-field-growth cost of stacking more convolutional layers — the deciding factor is whether the *relevant* temporal range plausibly exceeds what a reasonably-deep CNN's receptive field can cover.

---

## Red flags that fail you

- Cannot derive the CNN output-size formula or compute a specific example's parameter count.
- Says "CNNs are good at images" or "LSTMs have memory" without a mechanical explanation underneath.
- Doesn't know that BPTT is ordinary backprop applied to an unrolled, weight-tied graph, not a separate algorithm.
- Cannot write the four LSTM gate equations, or doesn't know which gates are sigmoid vs. tanh and why.
- Doesn't know why the LSTM's additive cell-state update specifically fixes vanishing gradients (versus vaguely "gates help somehow").
- Reflexively picks a Transformer for every sequence task without considering streaming/latency/low-data tradeoffs.

---

## Cheat card

```
MLP: no structural assumption, dense W connects everything to everything
CNN: LOCAL + SHARED weights (parameter sharing = translation invariance)
  out size: H' = floor((H-K+2P)/S)+1;  3x3,P=1,S=1 -> preserves H ("same")
  Conv2d(3->64, k=3) params = 3*3*3*64+64 = 1792  (INDEPENDENT of image size)
  receptive field: RF(L layers of 3x3 s1) = 1+2L -> L=5:11, L=10:21
  Flatten->Dense(large) vs GlobalAvgPool->Dense(small): orders-of-magnitude fewer
    params, at the cost of discarding spatial position info

RNN: h_t = tanh(W_h h_{t-1} + W_x x_t + b)  -- SAME weights every timestep (tied)
  unrolled across T steps = a T-layer deep net w/ tied weights
  BPTT = ordinary reverse-mode AD on this graph, shared-weight grad ACCUMULATES
    across all T timesteps (same rule as any reused parameter)
  vanishing across TIME = identical math to vanishing across DEPTH (tanh deriv <1)

LSTM (Hochreiter & Schmidhuber 1997) -- adds cell state c_t, ADDITIVE update:
  f_t=sigmoid(Wf.[h,x]+bf)  forget gate
  i_t=sigmoid(Wi.[h,x]+bi)  input gate
  g_t=tanh(Wg.[h,x]+bg)     candidate
  o_t=sigmoid(Wo.[h,x]+bo)  output gate
  c_t = f_t*c_{t-1} + i_t*g_t   <- d(c_t)/d(c_{t-1}) = f_t, ONE factor, not a
                                    matrix-multiply-and-saturating-activation chain
  h_t = o_t * tanh(c_t)
  worked (h_prev=0.1,c_prev=0.2,x=0.5): f=0.5987 i=0.5474 g=0.4053 o=0.5890
    c_new=0.3416  h_new=0.1937
  "constant error carousel": f_t~1 -> gradient survives many timesteps, same
    idea as residual connection's I+Jf Jacobian

PYTORCH: nn.Conv2d(in,out,kernel_size,padding); nn.LSTM(input_size,hidden_size,
  num_layers, batch_first=True) -> output, (h_n,c_n)
KERAS 3 (multi-backend: TF/JAX/PyTorch/OpenVINO via KERAS_BACKEND):
  layers.Conv2D(filters,kernel_size,padding="same"); layers.LSTM(units)
  use keras.ops.* not backend-specific ops to keep portability

2026 status: Transformers dominate large-scale sequence modeling (parallel
  train, no recurrence to vanish through); LSTM/GRU still win for constant-
  memory streaming inference and small-data regimes with strong inductive bias
```

## Sources

- [Long Short-Term Memory — Hochreiter & Schmidhuber, Neural Computation (1997)](https://www.bioinf.jku.at/publications/older/2604.pdf) — accessed 2026-08-03
- [Gradient-Based Learning Applied to Document Recognition — LeCun et al. (1998, LeNet)](http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf) — accessed 2026-08-03
- [Keras 3 — About Keras 3 / multi-backend documentation](https://keras.io/getting_started/about/) — accessed 2026-08-03
- [torch.nn.LSTM — PyTorch documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html) — accessed 2026-08-03
- [torch.nn.Conv2d — PyTorch documentation](https://docs.pytorch.org/docs/stable/generated/torch.nn.Conv2d.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
