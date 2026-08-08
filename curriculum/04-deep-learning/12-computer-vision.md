# Computer Vision: CNN → ResNet → ViT, Detection, Segmentation

> **Track:** T04 Deep Learning · **Time:** 2.5h · **Prereqs:** T03 · **Updated:** 2026-08-01
> **Module id:** `T04-computer-vision` · **Tags:** models,critical

## The 30-second version

CNNs beat MLPs on images because of two structural choices, not luck: weight sharing (one kernel reused across every spatial position) and translation equivariance (a shifted input produces a correspondingly shifted output), which cut parameter count by orders of magnitude and encode the prior that a cat is a cat wherever it appears in the frame. ResNet's skip connections solved a real, measured pain — the degradation problem, where adding depth made training error worse, not just validation error, meaning it wasn't overfitting, it was an optimization failure — by letting a block default to the identity function when extra depth wasn't helping. Vision Transformers (ViT) drop the convolutional inductive bias entirely and only win once you have on the order of 100M+ pretraining images; below that, a ResNet with far less data usually still wins, which is why most production vision pipelines pretrain on ImageNet and fine-tune rather than train ViT from scratch. Object detection evolved region-proposal-then-classify (R-CNN) into single-shot regression (YOLO) into set-prediction transformers (DETR); segmentation evolved from per-pixel encoder-decoder (U-Net) to instance-aware (Mask R-CNN) to promptable and zero-shot (SAM).

## Why this gets asked

Because computer vision interviews separate people who used `torchvision.models.resnet50(pretrained=True)` from people who understand why that call works at all. The interviewer has debugged a vision model that plateaued at a depth where adding layers made things worse, or has had to decide whether a ViT or a CNN backbone is the right call for a dataset with 50K labeled images, and wants to know if you'd reason about that or just reach for whatever's trending on a leaderboard.

---

## Lineage: past → present → future

**What came before.** Fully-connected networks applied to raw pixels don't scale: a 224×224×3 image flattened into an MLP's first layer with even a modest 1,000 hidden units needs `224×224×3×1000 ≈ 150M` weights in that single layer alone, with no notion that a pixel's neighbors matter more than a pixel on the other side of the image. LeNet-5 (LeCun et al., 1998) introduced the convolution + pooling pattern for digit recognition, but compute and data were too limited to scale it. The pain that actually broke the dam was ImageNet: a 1.2M-image, 1000-class benchmark that plain feature-engineering pipelines (SIFT + SVM, the pre-2012 state of the art) could not push past roughly 26% top-5 error. AlexNet (Krizhevsky, Sutskever, Hinton, 2012) dropped that to 15.3% using GPU-trained convolutions, ReLU, and dropout, and the field pivoted to deep CNNs almost overnight.

**Where it stands now.** The 2012-2015 depth race (AlexNet → VGG → GoogLeNet) hit a wall: past a certain depth, plain stacked convolutional networks got *worse* at training, not just validation, error — the degradation problem — because gradient and signal propagation broke down, not because of overfitting. ResNet (He et al., 2015) fixed this with skip connections (`y = F(x) + x`), making 152-layer networks trainable and winning ILSVRC 2015; ResNet-50/101 remain a default production backbone a decade later precisely because they're cheap, well-understood, and "good enough" for most transfer-learning use cases.
[Deep Residual Learning for Image Recognition — arXiv](https://arxiv.org/abs/1512.03385) — accessed 2026-08-01

Vision Transformers (Dosovitskiy et al., 2020) then challenged the assumption that convolution's inductive bias was necessary at all, treating an image as a sequence of patches fed to a standard transformer encoder. The live, well-documented finding from that paper: ViT underperforms ResNets of comparable size when trained from scratch on ImageNet-1k alone (~1.3M images), and only starts to match or beat CNN baselines once pretrained on tens-to-hundreds of millions of images (ImageNet-21k, ~14M, is borderline; JFT-300M, ~300M, is where ViT clearly wins). The current consensus split: at production data scales below roughly 100M images, a CNN (often a ResNet or ConvNeXt) is still typically the better choice or at least the safer default; at web-scale pretraining data, ViT-based backbones (and ViT-derived architectures inside CLIP, DINOv2, and most current vision-language models) dominate.
[Vision Transformer — ICLR 2021 discussion](https://medium.com/aiguys/vit-an-image-is-worth-16x16-words-transformers-for-image-recognition-at-scale-iclr21-dd5c1d071045) — accessed 2026-08-01

Detection and segmentation followed a similar arc: R-CNN's slow region-proposal-then-classify pipeline (2014) gave way to Faster R-CNN's learned region proposals (2015), then to YOLO's single-shot regression (2016) trading a little accuracy for real-time speed, then to DETR (Carion et al., 2020) reframing detection as set prediction via a transformer, eliminating hand-tuned anchors and non-max suppression at the cost of slow convergence and weaker small-object performance. Segmentation moved from U-Net's fully-convolutional encoder-decoder (2015, medical imaging) to Mask R-CNN's instance-aware masks (2017) to Meta's Segment Anything Model (Kirillov et al., 2023), which reframed segmentation itself as a promptable, zero-shot task trained on 1.1 billion masks across 11 million images.
[End-to-End Object Detection with Transformers — Springer](https://link.springer.com/chapter/10.1007/978-3-030-58452-8_13) — accessed 2026-08-01
[Segment Anything — Semantic Scholar](https://www.semanticscholar.org/paper/Segment-Anything-Kirillov-Mintun/7470a1702c8c86e6f28d32cfa315381150102f5b) — accessed 2026-08-01

**Where it's heading.** NMS-free, end-to-end detectors are now shipping in production tooling — Ultralytics' YOLO26 (released January 2026) removes Distribution Focal Loss and does native NMS-free inference, following DETR's set-prediction idea back into the fast single-shot family. That's real and deployed, not speculative.
[Ultralytics YOLO Evolution: YOLO26, YOLO11 — arXiv](https://arxiv.org/abs/2510.09653) — accessed 2026-08-01
Promptable, foundation-model-style segmentation (SAM and its successors) is displacing task-specific segmentation heads for many annotation and interactive-editing workflows, though task-specific fine-tuned models still win on narrow, high-volume production tasks where SAM's zero-shot generality isn't needed. More speculatively: convolution and attention are converging rather than competing — hybrid architectures (ConvNeXt borrowing transformer training recipes, and transformer variants borrowing convolutional locality biases) suggest the CNN-vs-ViT framing itself may be a temporary one, but which hybrid wins outright is not settled.

---

## Mental model

```
Convolution: one small kernel slides over the whole image, sharing weights

  Input (5x5)          3x3 kernel            Output (3x3), stride 1, no pad
  . . . . .            [k00 k01 k02]         each output cell = dot product
  . . . . .            [k10 k11 k12]         of kernel with the 3x3 patch
  . . X . .     *       [k20 k21 k22]   =    under it, SAME 9 kernel weights
  . . . . .                                  used at every position
  . . . . .

  Same kernel at position (0,0) and position (2,2): if the cat moves from
  top-left to bottom-right, the SAME kernel produces the SAME feature
  response, just at a shifted output location. That's translation
  equivariance. An MLP has to re-learn "cat" separately at every pixel
  position because its weights aren't shared spatially at all.

ResNet block: y = F(x) + x
  x ──────────────┬─────────────────────▶ (+) ──▶ y
                  │                        ▲
                  └──▶ [conv-bn-relu-conv-bn] ──┘
  If F(x) has nothing useful to add, gradient flows through the identity
  path untouched — the block can default to "do nothing" instead of
  actively hurting training, which is what happens without the skip.
```

**Parameter count, with real numbers.** A single 3×3 convolution with 64 input and 64 output channels has `3×3×64×64 = 36,864` weights, reused at every one of the (say) 224×224 spatial positions it's applied to. A fully-connected layer mapping a 224×224×64 feature map (≈3.2M values) to another 224×224×64 output would need on the order of `3.2M × 3.2M ≈ 10 trillion` weights — the convolution gets a comparable receptive-field-limited transformation for roughly 6 orders of magnitude fewer parameters, because it assumes locality (only a 3×3 neighborhood matters) and reuses the same weights everywhere (translation equivariance).

---

## How it actually works

### Convolution mechanics

- **Kernel/filter** — a small learned weight matrix (commonly 3×3 or 1×1) convolved across the input.
- **Stride** — how many pixels the kernel moves per step. Stride 1 preserves spatial resolution (before padding); stride 2 halves it, which is how CNNs downsample without a separate pooling layer.
- **Padding** — zeros added around the border so the kernel can be centered on edge pixels. "Same" padding keeps output size equal to input size; "valid" padding (no padding) shrinks it.
- **Output size formula:** `out = floor((in + 2·pad - kernel) / stride) + 1`. Example: `in=224, kernel=7, stride=2, pad=3` (ResNet's first conv layer) gives `floor((224+6-7)/2)+1 = 112`.
- **Receptive field** — how much of the original input a given output unit "sees," which grows with depth. Stacking two 3×3 convolutions gives a receptive field of 5×5 with fewer parameters (`2×9=18` weight positions) than one 5×5 convolution (`25` weight positions) at the same effective receptive field — this is the argument VGG made for using stacks of small kernels instead of large ones.

### Pooling

Max pooling (take the max in each window, typically 2×2 stride 2) or average pooling reduce spatial resolution and add a small amount of translation invariance (not just equivariance — a small shift in the input often leaves the max-pooled output unchanged). Cost: some spatial precision is thrown away, which matters more for segmentation/detection than classification. Many modern architectures (ResNet included) replace some pooling with strided convolutions, letting the network learn the downsampling instead of using a fixed rule.

### Why CNNs beat MLPs on images

Two properties, both required:

1. **Weight sharing** — one kernel's parameters are reused at every spatial location, so the parameter count depends on kernel size and channel depth, not on image resolution at all. A 3×3×64×64 kernel costs 36,864 parameters whether the input is 32×32 or 4096×4096.
2. **Translation equivariance** — shifting the input shifts the feature map output correspondingly (exactly, ignoring boundary/pooling effects). This directly encodes the prior that an object's identity doesn't depend on its position in the frame, which an MLP has to learn from data (and generally can't learn perfectly, requiring far more examples to generalize across positions).

Together these took ImageNet's parameter-hungry problem from "150M+ weights in the first layer alone for an MLP" to "tens of thousands per layer" for AlexNet-scale convolutions, which is why CNNs could be trained on datasets that would make an equivalent MLP hopelessly overfit or simply too large to fit in memory.

### LeNet → AlexNet → VGG → ResNet: the pain each one fixed

| Architecture | Year | Depth | Specific pain it solved |
|---|---|---|---|
| **LeNet-5** | 1998 | 5 layers | First conv+pool+FC pattern for digit recognition; too small a model and dataset (MNIST-scale) to prove the approach at scale |
| **AlexNet** | 2012 | 8 layers | Proved deep CNNs beat hand-engineered features (SIFT+SVM) at scale, using ReLU (no vanishing-gradient ceiling like the tanh nets before it), dropout (overfitting on 1.2M images with 60M parameters), and GPU training (feasible wall-clock time) |
| **VGG** | 2014 | 16-19 layers | Showed stacking small 3×3 kernels gives a larger effective receptive field with fewer parameters than fewer large kernels, and that depth alone (with a simple, uniform block design) improves accuracy — up to a point |
| **ResNet** | 2015 | up to 152 layers | Fixed the **degradation problem**: past ~20 layers, plain stacked CNNs got *worse training error*, not just worse validation error, meaning the extra depth was an optimization failure, not overfitting. Skip connections (`y=F(x)+x`) let a block default to identity, so adding depth can only help or do nothing, never actively hurt training |

**The degradation problem, precisely:** it is not vanishing gradients in the sigmoid sense (these networks used ReLU, which doesn't saturate on the positive side) — it's that a deeper *plain* stack of convolutions has strictly more representational capacity than a shallower one, yet in practice trained *worse* on the training set itself. He et al.'s framing: if extra layers only need to learn identity to match the shallower network's performance, plain networks apparently still struggle to learn that identity mapping through many stacked nonlinear layers, whereas explicitly providing the identity as a shortcut removes that burden entirely.
[Deep Residual Learning for Image Recognition — arXiv](https://arxiv.org/abs/1512.03385) — accessed 2026-08-01

### Batch normalization

Normalizes each channel's activations to zero mean, unit variance across the batch (then applies a learned scale/shift), computed per mini-batch during training and using running statistics at inference. It stabilizes and speeds up training by keeping activation distributions from drifting as earlier layers' weights change (originally framed as reducing "internal covariate shift," though later work argues its main benefit is smoothing the loss landscape rather than that specific mechanism). ResNet interleaves batch norm after every convolution, before the activation.

**Failure mode:** batch norm's statistics are computed per-batch, so very small batch sizes (common when fine-tuning large models on limited GPU memory) give noisy mean/variance estimates and can hurt more than help — the standard fix is GroupNorm or LayerNorm, which don't depend on batch size.

### Vision Transformers (ViT) and patch embedding

ViT (Dosovitskiy et al., 2020) splits an image into fixed-size patches (typically 16×16), flattens and linearly projects each patch into a token embedding, prepends a learnable `[CLS]` token, adds positional embeddings (since attention itself has no notion of spatial order), and feeds the sequence through a standard transformer encoder. A 224×224 image with 16×16 patches produces `(224/16)² = 196` patch tokens plus the CLS token.

There is no convolutional inductive bias here at all — no locality assumption, no weight sharing across space beyond what the patch-embedding linear layer does uniformly. That's the tradeoff: without the CNN's built-in priors, ViT has to *learn* locality and translation structure from data, which requires much more of it. The paper's own results: trained on ImageNet-1k alone (~1.3M images), ViT underperforms ResNets of similar size; trained on ImageNet-21k (~14M images) results are mixed; only at JFT-300M scale (~300M images) does ViT clearly overtake ResNet baselines. The practical rule of thumb the field converged on: **below roughly 100M pretraining images, bet on a CNN (or a pretrained/distilled ViT); above that, ViT-family backbones tend to win.**
[Vision Transformer — ICLR 2021 discussion](https://medium.com/aiguys/vit-an-image-is-worth-16x16-words-transformers-for-image-recognition-at-scale-iclr21-dd5c1d071045) — accessed 2026-08-01

### Detection: R-CNN → Faster R-CNN → YOLO → DETR

| Model | Year | Approach | Cost/limitation |
|---|---|---|---|
| **R-CNN** | 2014 | Selective search proposes ~2000 region candidates per image, each cropped and run through a CNN separately | Extremely slow (each region is a separate forward pass); proposals aren't learned |
| **Faster R-CNN** | 2015 | Region Proposal Network (RPN) shares the backbone's features and learns proposals jointly with the classifier | Much faster, still two-stage (propose, then classify/refine), typically not real-time |
| **YOLO** | 2016+ | Single forward pass directly regresses bounding boxes and class probabilities on a grid | Real-time speed; historically weaker on small/overlapping objects than two-stage detectors, though later YOLO versions closed much of this gap |
| **DETR** | 2020 | Frames detection as set prediction: a fixed number of learned "object queries" attend over CNN features via a transformer, matched to ground truth via bipartite matching (Hungarian algorithm), eliminating anchors and NMS entirely | Conceptually simpler, no hand-tuned anchor boxes; original DETR has slow convergence (many more training epochs than Faster R-CNN) and weaker small-object detection due to global attention diluting fine spatial detail |

Current production direction: Ultralytics' YOLO26 (Jan 2026) adopts NMS-free, end-to-end inference, folding DETR's key simplification (no post-hoc box suppression step) back into the fast single-shot family, plus a small-object-aware label assignment scheme addressing YOLO's historical weak point.
[Ultralytics YOLO Evolution: YOLO26, YOLO11 — arXiv](https://arxiv.org/abs/2510.09653) — accessed 2026-08-01

### Segmentation: U-Net → Mask R-CNN → SAM

- **U-Net** (Ronneberger et al., 2015) — symmetric encoder-decoder with skip connections between corresponding encoder/decoder resolutions, so fine spatial detail lost during downsampling is recovered during upsampling. Originally for biomedical images with very few labeled examples; the architecture (not just the domain) became a segmentation default well beyond medical imaging.
- **Mask R-CNN** (He et al., 2017) — extends Faster R-CNN with a per-instance mask-prediction branch running in parallel with the box/class heads, giving instance segmentation (distinguishing individual object instances, not just semantic classes).
- **SAM** (Kirillov et al., 2023) — reframes segmentation as a promptable task: given a point, box, or (in later variants) text prompt, produce a valid mask, with no task-specific fine-tuning needed. Trained on SA-1B: 11M images, 1.1 billion masks, the largest segmentation dataset at release. Architecture: an image encoder (ViT-based) computing embeddings once per image, a lightweight prompt encoder, and a fast mask decoder that can run interactively per-prompt without re-running the expensive image encoder.
[Segment Anything — Semantic Scholar](https://www.semanticscholar.org/paper/Segment-Anything-Kirillov-Mintun/7470a1702c8c86e6f28d32cfa315381150102f5b) — accessed 2026-08-01

### Transfer learning: what people actually do

The default production pattern, still true a decade after AlexNet: take a backbone pretrained on ImageNet (or a larger corpus), replace the final classification head, and either (a) freeze the backbone and train only the new head (fast, needs less data, works when the target domain is visually similar to ImageNet), or (b) fine-tune the whole network at a low learning rate (needs more data and compute, but adapts low-level features too, useful when the target domain is visually distant from natural photos — medical, satellite, industrial inspection). Training a CNN from random initialization on a few thousand labeled images is rarely competitive with fine-tuning a pretrained backbone on the same data.

---

## Build it from scratch

Minimal 2D convolution forward pass, no framework, to make the mechanics concrete:

```python
# untested sketch
import numpy as np

def conv2d(x, kernel, stride=1, padding=0):
    """x: (H, W) single-channel input. kernel: (kh, kw). Returns (out_h, out_w)."""
    if padding > 0:
        x = np.pad(x, padding)
    H, W = x.shape
    kh, kw = kernel.shape
    out_h = (H - kh) // stride + 1
    out_w = (W - kw) // stride + 1
    out = np.zeros((out_h, out_w))
    for i in range(out_h):
        for j in range(out_w):
            r, c = i * stride, j * stride
            patch = x[r:r+kh, c:c+kw]
            out[i, j] = np.sum(patch * kernel)   # elementwise multiply + sum = dot product
    return out

def max_pool2d(x, size=2, stride=2):
    H, W = x.shape
    out_h = (H - size) // stride + 1
    out_w = (W - size) // stride + 1
    out = np.zeros((out_h, out_w))
    for i in range(out_h):
        for j in range(out_w):
            r, c = i * stride, j * stride
            out[i, j] = x[r:r+size, c:c+size].max()
    return out
```

A minimal residual block in PyTorch, runnable:

```python
import torch, torch.nn as nn

class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + identity          # the skip connection
        return self.relu(out)

# sanity check
block = ResidualBlock(16)
x = torch.randn(2, 16, 32, 32)
y = block(x)
assert y.shape == x.shape
```

Full CNN-from-scratch (forward + backward, no autograd) and a from-zero training loop live alongside `T04-architectures`; this module focuses on the vision-specific mechanics (convolution, pooling, ResNet block, ViT patch embedding) rather than re-deriving generic backprop, which is covered in `T04-neural-net-math` and `T04-backprop-derivation`.

---

## How it's done in production

| Task | Typical production choice | What it adds over a from-scratch implementation |
|---|---|---|
| Classification backbone | `torchvision.models.resnet50(weights="IMAGENET1K_V2")` or a ConvNeXt/ViT variant from `timm` | Pretrained weights, tested numerics, exportable to ONNX/TensorRT |
| Detection | Ultralytics YOLO family (YOLO11/YOLO26), or Detectron2/MMDetection for Faster R-CNN/DETR variants | Data augmentation pipelines, anchor/NMS tuning (or NMS-free heads), export tooling, tracked benchmarks |
| Segmentation | `segment-anything` (Meta) for promptable/zero-shot, MMSegmentation or a fine-tuned U-Net/Mask R-CNN for task-specific pixel-perfect masks | SAM: zero-shot generality, interactive prompting. Task-specific: higher accuracy on a narrow, high-volume production task |
| Transfer learning | Freeze backbone + new head, or full fine-tune at low LR (`1e-4` to `1e-5` typical vs `1e-3` from-scratch) | Established recipes (warmup, discriminative LR per layer group) that avoid catastrophic forgetting of pretrained features |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Training error increases when you add more layers to a plain (non-residual) CNN | The degradation problem — optimization difficulty, not overfitting | Add residual/skip connections; verify by checking that training error (not just validation) is the one going up |
| Batch norm layers produce wildly different train vs eval behavior, especially after fine-tuning with a small batch size | BatchNorm statistics estimated from a tiny batch are noisy, and running stats haven't stabilized | Increase batch size, use gradient accumulation, or switch to GroupNorm/LayerNorm |
| ViT trained from scratch on a 50K-image dataset underperforms a pretrained ResNet by a wide margin | ViT has no convolutional inductive bias and needs far more data to learn locality/translation structure from scratch | Use a CNN, or use a ViT pretrained on a large corpus (ImageNet-21k+) and fine-tune, don't train ViT from random init on small data |
| Detector's mAP is fine on large objects, poor on small ones | Downsampling (pooling/strided convs, or DETR's global attention) loses fine spatial detail small objects need | Feature pyramid networks (multi-scale features), higher input resolution, or an architecture with explicit small-object handling (later YOLO/DETR variants add this) |
| Segmentation masks are blocky/low-resolution around object boundaries | Skip connections missing or too coarse in the decoder (i.e., not enough U-Net-style fusion of early high-resolution features) | Add or strengthen encoder-decoder skip connections at multiple resolutions |
| Fine-tuned model's accuracy drops below the pretrained baseline right after unfreezing all layers | Catastrophic forgetting: LR too high for the pretrained layers, wiping out useful pretrained features in a few steps | Use a much lower LR for fine-tuning (often 10-100x lower than from-scratch), or discriminative LR per layer group, with warmup |
| DETR-based detector needs far more epochs than a Faster R-CNN baseline to reach comparable mAP | Original DETR's slow convergence, a known, documented limitation of the bipartite-matching + global-attention training dynamics | Use a DETR variant with deformable/sparse attention (e.g. Deformable DETR) if convergence speed matters, or budget for more training epochs |

---

## Tradeoffs & when NOT to use it

- **Don't train a ViT from scratch on a dataset under roughly 100M images.** The paper's own numbers show it loses to CNNs at ImageNet-1k scale (~1.3M) and is mixed at ImageNet-21k scale (~14M); only web-scale pretraining changes this. If you have a 50K-image production dataset, a pretrained CNN or a pretrained-then-fine-tuned ViT beats a from-scratch ViT, full stop.
- **Don't reach for DETR when convergence time or small-object accuracy is the constraint** without budgeting for it or using a deformable-attention variant — vanilla DETR needs substantially more training epochs than Faster R-CNN and struggles more on small objects due to global attention.
- **Don't use SAM as a drop-in replacement for a task-specific fine-tuned segmentation model in a high-volume, narrow production pipeline.** SAM's value is zero-shot generality and interactivity; a fine-tuned U-Net/Mask R-CNN on your specific domain (e.g. a fixed set of product categories) will typically be faster and more accurate for that one task.
- **Don't skip transfer learning to "prove you can train from scratch."** Outside of research settings or genuinely novel domains with no relevant pretrained backbone (some medical/satellite imagery), training from random initialization on a limited dataset is strictly worse in accuracy-per-compute than fine-tuning, and it's the wrong default to reach for in an interview design answer.
- **YOLO-family single-shot detectors are the wrong choice when you need the last few points of mAP on small or heavily occluded objects** and can afford the latency of a two-stage detector — the speed/accuracy tradeoff is real, not just historical.
- **Batch norm is the wrong normalization choice for very small batch sizes** (e.g. per-GPU batch size of 1-2 in memory-constrained fine-tuning) — use GroupNorm or LayerNorm instead.

---

## Interview questions

### Q1 — Why do CNNs beat MLPs on image tasks? Give me numbers, not just "fewer parameters."
**Testing:** whether the parameter-efficiency claim is understood quantitatively.
**Answer:** Weight sharing plus translation equivariance. A 3×3 kernel over 64 input/output channels has `3×3×64×64=36,864` parameters, reused at every spatial position regardless of image size. An MLP layer connecting a 224×224×64 feature map to another of the same size would need on the order of `10^13` weights for a comparable transformation. The CNN also encodes the prior that object identity doesn't depend on position, which an MLP has to learn purely from data and generally can't learn as sample-efficiently.
**Follow-up trap:** *"So why not always use the smallest possible kernel?"* — smaller kernels need more layers stacked to reach the same receptive field, which is exactly VGG's argument (two 3×3 convs = a 5×5 receptive field with 18 weight-positions vs 25 for one 5×5 conv), but there's a floor: 1×1 kernels have no spatial receptive field at all and are used for channel mixing/dimensionality reduction, not spatial feature extraction.

### Q2 — What is the degradation problem and how does ResNet fix it?
**Answer:** Past a certain depth, plain stacked CNNs (no skip connections) got *worse training error*, not just worse validation error — a genuine optimization failure, not overfitting, since more capacity should be able to at least match a shallower network's training performance if it could learn the identity mapping. ResNet's `y=F(x)+x` skip connection lets a block default to identity when the extra transformation isn't helping, removing the burden of learning identity through stacked nonlinear layers.
**Follow-up trap:** *"Is this the same thing as vanishing gradients?"* — no. ResNet used ReLU, which doesn't saturate on the positive side, so this isn't the sigmoid-style vanishing-gradient failure; it's specifically that deep plain networks struggled to learn an identity mapping through many nonlinear layers, which the residual formulation sidesteps directly rather than fixing gradient flow per se (though skip connections do also improve gradient flow as a side effect).

### Q3 — When would you choose a CNN over a ViT, and vice versa, for a real project?
**Answer:** Below roughly 100M pretraining images (which covers nearly every production dataset that isn't web-scale), a CNN or a pretrained-then-fine-tuned ViT wins; a from-scratch ViT on a 50K or even 1M-image dataset underperforms because it lacks convolution's built-in locality/translation priors and has to learn them from data it doesn't have enough of. Above that scale, or when using an already-pretrained ViT-family backbone (CLIP, DINOv2), ViT-based approaches are typically state of the art.
**Follow-up trap:** *"What if I only have 50K images but access to a ViT pretrained on LAION or similar?"* — then fine-tuning that pretrained ViT is reasonable and often competitive, because the data-hungriness argument applies to training from random initialization, not to fine-tuning an already-pretrained transformer; the pretraining already supplied what the small dataset can't.

### Q4 — Walk me through the ViT patch embedding pipeline for a 224x224 image with 16x16 patches.
**Answer:** Split the image into non-overlapping 16×16 patches, giving `(224/16)² = 196` patches. Flatten each patch (16×16×3 = 768 values for RGB) and linearly project it to the model's embedding dimension. Prepend a learnable `[CLS]` token used for the final classification. Add learned or fixed positional embeddings to every token, since self-attention has no inherent notion of spatial order — without them the model can't distinguish "patch at top-left" from "patch at bottom-right." Feed the resulting 197-token sequence through a standard transformer encoder.
**Follow-up trap:** *"Why not just use the convolutional feature map directly, without treating it as a sequence?"* — that's a legitimate hybrid (convolutional stem + transformer, used by some ViT variants), but pure ViT's point was showing that transformers work on raw patches with no convolutional prior at all, given enough data; the hybrid approach reintroduces some convolutional bias to help at smaller data scales.

### Q5 — Explain the R-CNN to Faster R-CNN to YOLO progression and what changed at each step.
**Answer:** R-CNN (2014) runs ~2000 separately-cropped region proposals through a CNN each, extremely slow. Faster R-CNN (2015) shares backbone features across proposals and learns the proposals themselves via a Region Proposal Network, much faster but still two-stage. YOLO (2016) collapses this into a single forward pass that directly regresses boxes and classes on a grid, trading some accuracy (historically, on small/overlapping objects) for real-time speed.
**Follow-up trap:** *"Is two-stage always more accurate than one-stage?"* — historically yes on small/dense objects, but the gap has narrowed substantially with newer single-shot architectures (feature pyramids, better label assignment, and now NMS-free end-to-end training in YOLO26). Say the gap narrowed rather than claiming it's closed for every case, since two-stage detectors still lead on some fine-grained benchmarks.

### Q6 — What problem does DETR solve that YOLO/Faster R-CNN don't, and what does it cost?
**Answer:** DETR eliminates anchor boxes and non-max suppression entirely by framing detection as set prediction: a fixed number of learned object queries attend over image features, matched to ground-truth boxes via bipartite (Hungarian) matching during training, so the model directly outputs a final, non-overlapping set of detections. Cost: original DETR needs substantially more training epochs to converge than Faster R-CNN, and its global attention dilutes the fine spatial detail small objects need, giving it weaker small-object performance.
**Follow-up trap:** *"How would you fix the slow convergence without abandoning the set-prediction idea?"* — Deformable DETR and similar variants restrict attention to a small set of learned sampling points near each query's reference location instead of full global attention, which speeds convergence substantially and improves small-object handling while keeping the anchor-free, NMS-free framing.

### Q7 — What is SAM and how is its architecture designed for interactive use?
**Answer:** SAM (Kirillov et al., 2023) is a promptable segmentation model: given a point, box, or mask prompt, it outputs a valid segmentation mask, trained on 1.1 billion masks across 11 million images (SA-1B) for zero-shot generalization. Its architecture splits work deliberately for interactivity: a heavier ViT-based image encoder runs once per image to compute embeddings, while a lightweight prompt encoder and mask decoder run per-prompt in milliseconds, so a user can click multiple points/boxes on the same image and get near-instant mask updates without re-running the expensive encoder each time.
**Follow-up trap:** *"Would you use SAM for a fixed-category production segmentation pipeline processing millions of images a day?"* — usually not as the primary model; a task-specific fine-tuned model (U-Net/Mask R-CNN, or a SAM-distilled lightweight variant) is typically faster and more accurate for a narrow, high-volume, fixed-category task. SAM's value is zero-shot generality and interactive annotation tooling, not narrow high-throughput inference.

### Q8 — Derive the output size of a convolution: 224 input, 7x7 kernel, stride 2, padding 3.
**Answer:** `out = floor((in + 2·pad - kernel)/stride) + 1 = floor((224 + 6 - 7)/2) + 1 = floor(223/2) + 1 = 111 + 1 = 112`. This is exactly ResNet's stem layer, halving 224 to 112 in the first convolution.
**Follow-up trap:** *"What if padding were 0 instead of 3?"* — `floor((224-7)/2)+1 = floor(217/2)+1 = 108+1=109`, a different (and non-round) output size — padding is chosen deliberately to hit clean power-of-two-friendly dimensions through the network, not just to preserve size.

### Q9 — Why does batch norm sometimes hurt rather than help during fine-tuning?
**Answer:** Batch norm estimates per-channel mean/variance from the current mini-batch during training; with a small batch size (common when fine-tuning a large model under GPU memory constraints), these estimates are noisy, and the running statistics used at inference may not have stabilized, producing a train/eval mismatch that shows up as validation accuracy that doesn't match training behavior.
**Follow-up trap:** *"What's your fix if you can't increase batch size?"* — switch to GroupNorm or LayerNorm, which normalize over channels/features rather than across the batch dimension, making them batch-size-independent; or freeze the BatchNorm running statistics (common practice when fine-tuning with a very small batch) so at least inference behavior is stable.

### Q10 — Design a transfer-learning strategy for classifying a new, visually distinct domain (e.g. satellite imagery) with 20K labeled images.
**Testing:** whether the candidate can reason about when to freeze vs fine-tune, not just recite "use transfer learning."
**Answer:** Start with a backbone pretrained on ImageNet, replace the head, and fine-tune the whole network at a low learning rate rather than only training the head, because satellite imagery's low-level statistics (color distributions, textures, scale) differ substantially from natural photos, so the pretrained low-level features need adaptation too, not just the high-level classifier. Use a lower LR for earlier layers and a higher LR for the new head (discriminative learning rates), with warmup, to avoid catastrophic forgetting of useful pretrained features early in fine-tuning.
**Follow-up trap:** *"What if you only had 500 labeled images instead of 20K?"* — at that scale, full fine-tuning risks overfitting or catastrophic forgetting faster than the model can adapt usefully; freezing most of the backbone and training only the head (or the last block plus the head) is the safer default, possibly combined with heavy data augmentation.

### Q11 — Your detector's mAP is strong on the validation set but degrades sharply on small objects specifically. Diagnose and fix.
**Answer:** Likely cause: repeated downsampling (pooling/strided convolutions, or a transformer detector's global attention) has diluted the fine spatial detail small objects depend on by the time features reach the detection head. Fix: add or strengthen a feature pyramid network to detect at multiple resolutions, increase input resolution, or (for a transformer detector) switch to a deformable/sparse-attention variant that samples locally rather than diluting signal globally.
**Follow-up trap:** *"Would simply increasing input resolution always fix this?"* — it helps but isn't free: higher resolution increases compute roughly quadratically and can push you outside your latency budget; a feature pyramid is often the more compute-efficient fix because it recovers multi-scale detail without scaling the whole network's input size.

### Q12 — What's the actual number that made AlexNet a turning point rather than an incremental improvement?
**Answer:** AlexNet dropped ImageNet top-5 error from roughly 26% (best pre-deep-learning approaches, largely SIFT+SVM-style pipelines) to 15.3% in 2012 — a roughly 40% relative error reduction in a single submission, achieved via GPU-trained deep convolutions, ReLU activations, and dropout regularization, which together made training a network of that depth and parameter count (~60M parameters) computationally and statistically feasible for the first time.
**Follow-up trap:** *"Was the architecture itself novel, or was it mostly an engineering achievement?"* — mostly engineering and scale: the conv+pool+FC pattern already existed in LeNet from 1998. What was new was making it work at GPU-trainable scale with ReLU (avoiding the saturating-activation ceiling) and dropout (controlling overfitting on a dataset still small relative to the model's capacity) — a fair answer credits both the architectural choices and the systems/scale achievement, not one or the other alone.

---

## Red flags that fail you

- Saying "ResNet fixes vanishing gradients" as the sole explanation without mentioning the degradation problem (a distinct, measured training-error phenomenon).
- Claiming ViT is unconditionally better than CNNs, with no mention of the data-scale threshold where that flips.
- Describing YOLO and Faster R-CNN as differing only in speed, with no mention of the one-stage vs two-stage architectural distinction that causes it.
- Not knowing that batch norm behaves differently at train vs eval time (running stats vs batch stats).
- Recommending SAM as a default production segmentation model for a narrow, fixed-category, high-volume task without weighing a fine-tuned task-specific model.
- Treating "add more layers" as free — not knowing that plain (non-residual) stacks degrade past a certain depth.
- Not being able to compute a convolution's output size from kernel/stride/padding when asked directly.

---

## Cheat card

```
CONV OUTPUT SIZE   out = floor((in + 2*pad - kernel)/stride) + 1
                   e.g. in=224,k=7,s=2,p=3 -> 112 (ResNet stem)
PARAMS PER CONV    kernel_h * kernel_w * in_ch * out_ch (independent of image size)
                   3x3x64x64 = 36,864 vs MLP equivalent ~10^13
WHY CNN > MLP      weight sharing (same kernel everywhere) + translation
                   equivariance (shift input -> shift output correspondingly)
LENET->ALEXNET->VGG->RESNET
   LeNet(1998,5L): proved conv+pool pattern, too small to scale
   AlexNet(2012,8L): ImageNet top-5 26%->15.3%, ReLU+dropout+GPU
   VGG(2014,16-19L): stacked 3x3 > one big kernel, same receptive field, fewer params
   ResNet(2015,152L): FIXED DEGRADATION PROBLEM (deeper plain net = worse TRAINING
     error, not overfitting) via y=F(x)+x skip connections
BATCHNORM          normalize per-channel across batch, train=batch stats,
                   eval=running stats. Small batch -> noisy -> use GroupNorm/LayerNorm
VIT                patches (16x16) -> flatten -> linear proj -> +[CLS] +pos_embed
                   -> transformer encoder. 224/16=14 -> 196 patches +1 CLS =197 tokens
                   NO conv inductive bias. Loses to CNN <~100M pretrain images
                   (ImageNet-1k ~1.3M: loses. JFT-300M ~300M: wins.)
DETECTION          R-CNN(2014,slow,2000 crops/img) -> Faster R-CNN(2015,RPN,2-stage)
                   -> YOLO(2016,1-stage,real-time,weaker small-obj historically)
                   -> DETR(2020,set prediction,bipartite match,no anchors/NMS,
                      slow convergence + weak small-obj due to global attn)
                   -> YOLO26(2026): NMS-free end-to-end, small-obj-aware assignment
SEGMENTATION       U-Net(2015,enc-dec+skip conns,medical) -> Mask R-CNN(2017,
                   +instance mask branch on Faster R-CNN) -> SAM(2023,promptable,
                   zero-shot, SA-1B: 11M images/1.1B masks, ViT encoder once + fast
                   per-prompt decoder)
TRANSFER LEARNING  pretrain ImageNet -> replace head -> freeze+train head (small data,
                   similar domain) OR full fine-tune at low LR ~1e-4/1e-5 (more data,
                   distant domain). From-scratch on small data is rarely competitive.
```

## Sources

- [Deep Residual Learning for Image Recognition — arXiv](https://arxiv.org/abs/1512.03385) — accessed 2026-08-01
- [Vision Transformer — ICLR 2021 discussion](https://medium.com/aiguys/vit-an-image-is-worth-16x16-words-transformers-for-image-recognition-at-scale-iclr21-dd5c1d071045) — accessed 2026-08-01
- [End-to-End Object Detection with Transformers — Springer](https://link.springer.com/chapter/10.1007/978-3-030-58452-8_13) — accessed 2026-08-01
- [Segment Anything — Semantic Scholar](https://www.semanticscholar.org/paper/Segment-Anything-Kirillov-Mintun/7470a1702c8c86e6f28d32cfa315381150102f5b) — accessed 2026-08-01
- [Ultralytics YOLO Evolution: An Overview of YOLO26, YOLO11, YOLOv8, YOLOv5 — arXiv](https://arxiv.org/abs/2510.09653) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
