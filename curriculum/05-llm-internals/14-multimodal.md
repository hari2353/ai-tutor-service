# ViT, CLIP, Whisper, VLM Architectures

> **Track:** T05 LLM Internals · **Time:** 3h · **Prereqs:** T05-03-attention, T05-04-positional, T05-09-inference-serving
> **Module id:** `T05-multimodal` · **Tags:** vision, multimodal, vlm, clip, whisper, vit

## The 30-second version

A Vision Transformer turns an image into a sequence by chopping it into fixed patches (16x16 or 14x14 pixels), linearly projecting each flattened patch to the model's embedding dimension, and running the resulting sequence through a standard transformer encoder with no convolutions at all — CLIP then pretrains a ViT and a text transformer jointly with a contrastive loss so that matching image-caption pairs land close together in a shared embedding space, at LAION-scale (400M+ pairs), giving you a vision encoder whose embeddings already understand language. Modern VLMs (LLaVA, Qwen-VL, GPT-4o, Gemini) get vision into an LLM's context window by taking that encoder's patch-grid output, running it through a projection layer (a 2-layer MLP in LLaVA, a resampler/merger in Qwen-VL), and concatenating the resulting vectors as extra "tokens" directly into the LLM's input sequence — the image never becomes discrete vocabulary tokens the way text does, it's continuous embeddings the LLM attends over exactly like any other token. This is expensive and non-obvious: a single 1024x1024 image costs GPT-4o roughly 765 tokens in high-detail mode, LLaVA-1.5 burns 576 tokens on one 336x336 image, and Qwen2.5-VL's dynamic-resolution encoder can emit anywhere from 4 to 16,384 tokens depending on image size — meaning a handful of screenshots in a conversation can consume more context budget than several pages of text, with real latency and cost consequences that most people building on top of these APIs don't do the arithmetic on. Whisper takes a different path entirely for audio: it converts 30-second audio chunks into log-mel spectrograms, encodes them with a transformer encoder, and decodes text autoregressively with cross-attention, no discretized "audio tokens" and no shared vocabulary with vision at all — the multimodal story is architecturally fragmented per-modality, and only the newest natively-multimodal models (Gemini's interleaved-modality training) are attempting to unify it end to end rather than bolting encoders onto a frozen LLM.

## Why this gets asked

Because "how does GPT-4o see an image" is a question almost every LLM-adjacent engineer gets asked in 2026 and most people answer with marketing-copy vagueness ("it converts the image to tokens somehow") instead of the actual patch-count math. The interviewer has usually personally hit the consequence in production: a RAG-over-documents pipeline that silently exploded its context budget the day someone added page-image inputs alongside OCR'd text, or a vision-enabled agent whose per-request latency and cost tripled once screenshots were added to every turn, and nobody had done the token-cost arithmetic up front. They want to know whether you can reason about vision-token cost the same way you'd reason about text-token cost — not just "attach an image and see what happens" — and whether you understand that a VLM's "vision tokens" are a fundamentally different kind of object than text tokens (continuous projected embeddings, not discrete vocabulary lookups), which has real implications for what you can and can't do with them (you can't easily constrain generation of a vision token, you can't run a vision "token" through a tokenizer's `decode()`, and prompt-injection-via-image is a qualitatively different attack surface than prompt-injection-via-text).

---

## Lineage: past → present → future

**What came before.** Pre-2020 vision and language were separate research fields with separate architectures: CNNs (AlexNet 2012, ResNet 2015, up through EfficientNet) dominated vision via convolutional inductive biases (translation equivariance, local receptive fields), while transformers (2017) took over language. Bridging them meant hand-built multimodal fusion — image captioning models bolted a CNN feature extractor onto an RNN or early transformer decoder (Show-and-Tell 2015, and later attention-based captioning), and visual question answering systems fused CNN features with text embeddings through ad hoc concatenation or bilinear pooling. These worked but didn't scale the way language models were about to: they needed task-specific architecture engineering per problem, had no shared pretraining objective across modalities, and inherited the CNN's local-receptive-field bias which capped how well global image context could be reasoned about. The Vision Transformer paper (Dosovitskiy et al., "An Image is Worth 16x16 Words," ICLR 2021) killed the convolution-is-necessary-for-vision assumption by showing a pure transformer, given enough pretraining data (JFT-300M), matched or beat CNNs on ImageNet — the specific pain it solved was that CNN inductive biases, useful at small data scale, became a ceiling at large data scale, exactly the bitter-lesson pattern that had already played out in NLP.

**Where it stands now.** ViT is the default vision backbone for essentially all large-scale multimodal systems as of 2026, and CLIP-style contrastive image-text pretraining (Radford et al., 2021, OpenAI) is the standard way to get vision embeddings that already share a semantic space with language before any LLM is ever attached — CLIP-ViT-L/14 (24 layers, ~307M params) and its OpenCLIP/LAION-trained descendants remain the dominant off-the-shelf vision encoder choice for open VLMs (LLaVA family, and many others), typically kept frozen or lightly fine-tuned rather than trained from scratch, because CLIP pretraining is itself expensive and the representations transfer well. The live disagreement is architectural: **adapter-based VLMs** (LLaVA-style: frozen or lightly-tuned CLIP ViT + a small trainable projection MLP + a frozen or fine-tuned LLM) are cheap to build and iterate on but inherit whatever blind spots the frozen vision encoder has, versus **natively multimodal models trained end-to-end from the start** (Gemini's family, and reportedly GPT-4o's unified architecture, neither of which has published vision-encoder specifics) where vision and text share representation learning from pretraining onward, at far higher training cost but without the adapter's translation-loss ceiling. Dynamic/variable-resolution vision tokenization (Qwen2-VL/2.5-VL's "Naive Dynamic Resolution," emitting a token count proportional to actual image size rather than a fixed 576 regardless of input) is now the more sophisticated approach that fixed-patch-count models like early LLaVA lack, trading implementation complexity for much better token efficiency on small or simple images. For audio, Whisper's encoder-decoder-with-cross-attention design (Radford et al., 2022) remains the dominant open architecture; newer end-to-end speech models (Voxtral, and multimodal LLMs with native audio input like GPT-4o's audio mode and Gemini's audio understanding) are increasingly folding audio into the same unified token stream as vision and text rather than keeping it as a separate ASR-then-text-injection pipeline, but this is genuinely less mature and less publicly documented than the vision story.

**Where it's heading.** The clear direction of travel — high confidence — is toward **fewer wasted vision tokens per unit of actual visual information**: token-pruning and token-merging research (dropping or merging visually-redundant patch tokens before they hit the LLM) is one of the most active 2025-2026 VLM research areas specifically because vision tokens are the expensive part of the multimodal context budget, and dynamic-resolution tokenization (Qwen's NDR) is already production-proven as one answer. Native end-to-end multimodal training (no frozen adapter boundary) is very likely the eventual default for frontier labs given Gemini and GPT-4o's trajectory, though this is moderate confidence since exact architectures for closed models remain undisclosed and adapter-based open models remain extremely competitive and far cheaper to build. Speculative, lower confidence: a genuinely unified tokenizer across vision, audio, and text (a single discretized or shared-embedding vocabulary spanning all modalities, rather than per-modality encoders bolted together) — some research points this direction but no production frontier model has fully committed to it as of this writing, and the practical difficulty of getting continuous audio/vision signal and discrete text vocabulary into one representation space without losing information in either direction remains a real open problem, not a solved one.

---

## Mental model

```
TEXT TOKEN PATH (for comparison):
  "the cat sat" --tokenizer--> [791, 5089, 3332]  <- DISCRETE ids, vocab lookup
                                    |
                                    v
                          embedding table lookup  <- learned vector per discrete id

IMAGE TOKEN PATH (ViT/CLIP-style, what LLaVA/Qwen-VL/GPT-4o all do at core):

  [ 224x224x3 image ]
         |
         | split into fixed PxP patches (P=16 or P=14)
         v
  [ patch_1 ] [ patch_2 ] ... [ patch_196 ]     <- 224/16 = 14, 14*14 = 196 patches
         |          |                |
         | flatten each patch to a vector (16*16*3 = 768 values), then
         | LINEAR PROJECTION to embedding dim (e.g. 768 or 1024)
         v          v                v
  [ e_1 ]     [ e_2 ]      ...  [ e_196 ]        <- CONTINUOUS vectors, NOT vocab ids
         |
         + learned [CLS] token + learned positional embeddings (no tokenizer decode() exists)
         |
         v
   Transformer ENCODER (ViT, e.g. 24 layers for ViT-L/14)
         |
         v
   [ 196 output patch embeddings, still continuous ]
         |
         | PROJECTION LAYER (LLaVA: 2-layer MLP.  Qwen-VL: cross-attn resampler/"merger")
         | this is the bridge: maps vision-encoder dim -> LLM's embedding dim
         v
   [ 196 "vision tokens" now living in the LLM's embedding space ]
         |
         | CONCATENATED directly into the LLM's input sequence, interleaved
         | with real text tokens, e.g.: [BOS] [vision x196] "what is in" [vision-crop x...] "this image?"
         v
   LLM decoder attends over ALL of them identically (self-attention doesn't
   care whether a position came from a tokenizer or a projection layer)

KEY DISTINCTION: vision "tokens" are never discrete IDs from a fixed vocabulary.
They cannot be decode()'d back to a human-readable symbol, cannot be
constrained-decoded, and a "vision token" costs the same context-window
slot as a text token despite carrying continuous, non-vocabulary information.
```

---

## How it actually works

### ViT: the patch-embedding arithmetic, worked through

A 224x224 image with 16x16 patches produces (224/16)^2 = 14^2 = **196 patches**. Each patch is 16x16x3 = 768 raw pixel values, flattened into a single vector, then run through one shared learned linear projection (a single `nn.Linear(768, D)`) to reach the model's embedding dimension `D` (768 for ViT-B, 1024 for ViT-L). A learnable `[CLS]` token is prepended (for classification-style pooling; CLIP uses this or a projection of it as the image's global embedding), and learned (not sinusoidal, in the original ViT) position embeddings are added elementwise so the model knows patch order despite the transformer's permutation-invariant self-attention having no inherent sense of 2D spatial layout. Total sequence length into the encoder: 196 + 1 = 197 tokens for ViT-B/16 at 224x224 — mechanically identical in shape to a text sequence of length 197, which is exactly why a standard transformer encoder architecture works unchanged. Smaller patches (14x14 in ViT-L/14) at the same image resolution produce more patches (16^2 = 256 at 224x224) — smaller patches mean finer spatial granularity but quadratically more self-attention compute, since attention cost scales with sequence length squared.

### CLIP: contrastive pretraining, mechanically

CLIP trains two encoders jointly — a ViT (or ResNet, in the original paper's ablations, though ViT variants dominate now) for images and a causal transformer for text — with no classification head and no captioning objective. For a batch of N (image, caption) pairs, both encoders produce an embedding per input, projected to a shared dimension and L2-normalized; you compute the N x N cosine-similarity matrix between every image embedding and every text embedding in the batch, and the loss is symmetric cross-entropy pushing the diagonal (the true pairs) to be the highest similarity in both the row direction (image-to-text) and column direction (text-to-image), while every off-diagonal (mismatched pairs, which are free negatives from the rest of the batch) is pushed down. This is why CLIP batch size matters enormously for pretraining quality — a bigger batch gives more (and harder) in-batch negatives per gradient step, which is why the original CLIP paper used a batch size of 32,768. The resulting embedding space is the actual product: downstream, you can do zero-shot classification by comparing an image embedding's cosine similarity against text embeddings of candidate class names ("a photo of a dog" vs "a photo of a cat") with no task-specific fine-tuning at all, and this same joint embedding space is what makes CLIP's vision encoder a good starting point for VLMs — the visual features already correlate with linguistic concepts before any LLM is ever attached.

### How vision tokens actually enter an LLM's context: the projection layer

The mechanical bridge between "a ViT's output" and "something an LLM's self-attention can consume" is a **projection layer**, and its exact form is the biggest architectural fork between VLM families:

- **LLaVA (Liu et al., 2023, and LLaVA-1.5)**: a simple 2-layer MLP with GELU activation, one linear projection per patch-embedding vector, mapping the CLIP ViT-L/14's 1024-dim output directly to the LLM's (Vicuna's) embedding dimension — no cross-attention, no resampling, just a per-token linear map. Simple, cheap, but produces exactly as many output tokens as input patches: 336x336 image / 14x14 patch = 24x24 = **576 tokens**, always, regardless of how visually simple or complex the image is.
- **Qwen2-VL / Qwen2.5-VL**: "Naive Dynamic Resolution" — the vision encoder itself handles variable input resolutions natively (no forced resize to a fixed square), and a subsequent merger module (using 2D-RoPE-aware attention plus token merging) compresses adjacent patches, producing a variable vision-token count reported as ranging roughly **4 to 16,384 tokens per image** depending on native resolution — far more token-efficient for small or simple images, at the cost of a more complex encoder/merger implementation.
- **GPT-4o / GPT-4V (architecture undisclosed, but documented token-cost behavior)**: OpenAI's public API behavior (not the internal architecture) is a tiling scheme — an image is first scaled to fit within 2048x2048, then the shortest side is scaled to 768px, then divided into 512x512 tiles, each tile costing **170 tokens**, plus a flat **85-token base cost**. A 1024x1024 image in high-detail mode costs roughly **765 tokens**; a 2048x4096 image costs around **1,105 tokens**. Low-detail mode bypasses tiling entirely and is a flat **85 tokens** regardless of image size — a real, checkable cost lever most people don't know exists.
- **Claude (Anthropic)**: a documented area-based formula, `tokens = (width_px * height_px) / 750` — a 1000x1000 image (1 megapixel) costs about 1,334 tokens; a 200x200 image costs about 54 tokens; the long edge is capped (1,568px in earlier Claude models, raised to 2,576px in Opus 4.7), with anything larger downscaled before tokenization.

### The cost arithmetic that actually matters

A single high-detail GPT-4o image (~765-1,105 tokens) is comparable to **500-800 words of English text** in context-budget terms — meaning three or four screenshots in one conversation turn can silently consume as much context as several pages of a document, an easy trap in agentic coding/browsing tools that pass full-resolution screenshots on every step. This compounds with **latency**: vision tokens still have to pass through every transformer layer's self-attention and feed-forward blocks exactly like text tokens, so a 576-token LLaVA image addition to a prompt is roughly the same per-token decode/prefill cost as 576 tokens of text — the "it's just one image" mental model badly undercounts both the dollar cost (billed per token, same rate as text on most APIs) and the prefill-latency cost (attention is O(n^2) in total sequence length, so stacking several full-resolution images into one prompt has real quadratic consequences at the attention layer, not just a linear token-count increase in billing).

### Whisper: a genuinely separate architecture for audio

Whisper (Radford et al., OpenAI, 2022) is a standard encoder-decoder transformer, but its input is never tokenized the way text or images are. Audio is resampled to 16kHz, chunked into fixed **30-second windows**, converted to an 80-channel (Whisper large-v2 and earlier) or 128-channel (large-v3 onward) log-mel spectrogram computed with a 10ms hop, and zero-padded if shorter than 30 seconds. Two convolutional layers downsample the spectrogram before sinusoidal positional embeddings are added and the sequence is passed through a stack of standard transformer encoder blocks — this is the only convolution in the whole modern multimodal stack discussed in this module, existing purely as a downsampling front-end, not as the primary feature extractor the way pre-ViT CNN vision backbones used convolutions. The decoder is an ordinary autoregressive BPE-tokenized language model that cross-attends into the encoder's output states and generates one text token at a time, using special tokens to control task (transcribe vs translate-to-English), language identification, and timestamp granularity — meaning Whisper's *output* is completely normal discrete text tokens even though its *input* was never tokenized at all. There is no shared vocabulary or embedding space between Whisper's audio encoder and a separate LLM by default; bridging them into one system (as in a voice-agent pipeline) typically means running Whisper as a standalone ASR step and feeding its text output into the LLM as ordinary text tokens, not fusing the audio embeddings directly the way VLMs fuse vision embeddings — this is the actual architectural gap between "the model sees the image" (true fusion, in modern VLMs) and "the model sees a transcript of the audio" (cascaded pipeline, the still-dominant pattern for voice agents as of 2026, though native audio-input models like GPT-4o's audio mode are moving away from this).

---

## Build it from scratch

Minimal ViT patch embedding plus a from-scratch CLIP-style contrastive loss over a toy batch — the two pieces most worth being able to derive cold:

```python
# untested sketch — minimal ViT patch embedding
import torch
import torch.nn as nn

class PatchEmbed(nn.Module):
    def __init__(self, img_size=224, patch_size=16, in_chans=3, embed_dim=768):
        super().__init__()
        self.num_patches = (img_size // patch_size) ** 2   # 196 for 224/16
        # a single Conv2d with stride == kernel_size IS the "flatten + linear
        # project each patch" operation, just expressed as a convolution --
        # this is the standard implementation trick, not a different mechanism
        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size, stride=patch_size)

    def forward(self, x):  # x: (B, 3, 224, 224)
        x = self.proj(x)                    # (B, embed_dim, 14, 14)
        x = x.flatten(2).transpose(1, 2)    # (B, 196, embed_dim) -- now a sequence
        return x

class ViTEncoder(nn.Module):
    def __init__(self, img_size=224, patch_size=16, embed_dim=768, depth=12, n_heads=12):
        super().__init__()
        self.patch_embed = PatchEmbed(img_size, patch_size, embed_dim=embed_dim)
        n = self.patch_embed.num_patches
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, n + 1, embed_dim))  # learned, not sinusoidal
        layer = nn.TransformerEncoderLayer(embed_dim, n_heads, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, depth)

    def forward(self, x):
        B = x.shape[0]
        x = self.patch_embed(x)                             # (B, 196, D)
        cls = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls, x], dim=1) + self.pos_embed      # (B, 197, D)
        return self.encoder(x)                               # (B, 197, D)


# untested sketch — CLIP-style symmetric contrastive loss over a batch
def clip_loss(image_embeds, text_embeds, logit_scale):
    # image_embeds, text_embeds: (N, D), already L2-normalized
    logits = logit_scale * image_embeds @ text_embeds.T        # (N, N) similarity matrix
    labels = torch.arange(logits.shape[0], device=logits.device)  # diagonal = true pairs
    loss_i2t = nn.functional.cross_entropy(logits, labels)       # image-to-text direction
    loss_t2i = nn.functional.cross_entropy(logits.T, labels)     # text-to-image direction
    return (loss_i2t + loss_t2i) / 2
```

A fuller lab implementing the LLaVA-style bridge — take this `ViTEncoder`'s 197-token output, project it with a 2-layer MLP into a toy LLM's embedding space, and concatenate it with real text-token embeddings before a forward pass — belongs in `(lab pending)`, since walking through the actual concatenation and verifying attention runs over both token types identically is the exercise that makes the "vision tokens are just embeddings in the same sequence" claim concrete rather than asserted.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A vision-enabled agent's context budget fills up far faster than expected once screenshots are added | Each image costs hundreds to low-thousands of tokens (576 fixed for LLaVA-1.5 at 336px; ~765-1,105 for GPT-4o high-detail; up to 16,384 for large Qwen-VL inputs) — comparable to a full page of text, easy to undercount when mentally modeling "one image" as cheap | Compute actual token cost per image resolution before designing the pipeline; use low-detail/low-resolution modes where fine visual detail isn't needed; downscale or crop before sending |
| Per-request latency triples after adding image inputs to every agent step | Vision tokens pass through every transformer layer's self-attention and FFN exactly like text tokens, and attention cost is O(n^2) in total sequence length — stacking multiple full-res images compounds this quadratically, not linearly | Reduce image count/resolution per call; cache image embeddings across turns where the image doesn't change instead of re-sending it; use a smaller/dynamic-resolution vision encoder (Qwen-VL-style) where available |
| A VLM confidently describes fine print or small details in an image incorrectly | Fixed-patch-count encoders (LLaVA at 336x336, 576 tokens always) allocate the same patch grid to a huge image or a small icon — visual detail below one patch's spatial resolution is lost before the LLM ever sees it | Use models with dynamic/higher resolution support (Qwen2.5-VL's NDR, or tiling in GPT-4o) for tasks needing fine detail; crop/zoom the region of interest before sending rather than relying on the model to "zoom in" on a full-resolution encode it never received |
| Image-based prompt injection succeeds even though the text-only version of the same attack is blocked | Vision tokens are continuous projected embeddings, not discrete text run through the same input-sanitization/guardrail pipeline built for text tokens — text embedded as pixels in an image bypasses text-layer filters entirely | Run OCR + text-based guardrails on any user-supplied image before or alongside vision-model processing; do not assume text-input guardrails cover image-encoded text |
| A voice-agent pipeline mishears a proper noun or domain term consistently | Whisper is a cascaded ASR-then-text pipeline (not a fused audio-embedding architecture) — the LLM never sees raw audio, only Whisper's already-decided text transcript, so an ASR error is baked in before the LLM gets a chance to use broader context to correct it | Supply a domain vocabulary/prompt-bias hint to Whisper's decoding where supported, or move to a native-audio-input model (GPT-4o audio mode, Gemini audio) that lets the LLM reason jointly over acoustic and semantic signal instead of a frozen transcript |
| CLIP-based zero-shot classification performs poorly on a narrow domain (e.g. specific industrial defect types) | CLIP's contrastive pretraining data is broad web image-caption pairs; narrow domain concepts are underrepresented in that distribution, so the shared embedding space doesn't cluster them well | Fine-tune the vision encoder (or a lightweight adapter on top of frozen CLIP) on in-domain labeled pairs rather than relying on zero-shot; or fine-tune just the projection layer in a VLM setup |

---

## Tradeoffs & when NOT to use it

- **Don't send full-resolution images when low-detail suffices.** GPT-4o's low-detail mode is a flat 85 tokens regardless of image size — if the task is "is there a cat in this image" rather than "read the small print on this receipt," high-detail tiling is wasted cost and latency for no accuracy gain.
- **Don't assume a fixed-patch-count VLM (LLaVA-style) scales gracefully to high-resolution-detail tasks.** 576 tokens at 336x336 is a hard ceiling on spatial granularity; if the task needs reading dense text or spotting small defects, either crop to the region of interest first or use a dynamic-resolution model (Qwen-VL family) instead of assuming "a bigger image" helps within a fixed-patch architecture.
- **Don't treat CLIP zero-shot performance as production-grade for narrow domains without validating it.** It's genuinely strong on broad, web-distribution-adjacent concepts and can quietly fail on specialized domains (medical imaging, industrial inspection) where the pretraining distribution has little coverage — validate against a labeled domain set before shipping, don't assume the general reputation transfers.
- **Don't use a cascaded ASR-then-LLM pipeline where native audio input is available and latency/nuance matters.** Whisper-then-text loses paralinguistic information (tone, emphasis, overlapping speech) that a natively multimodal audio model can use; the cascaded approach is simpler to build and debug, and still the right choice when you specifically want a clean, auditable text transcript as an artifact, but it's not free of information loss.
- **Don't reach for a VLM at all when OCR + text pipeline is sufficient and cheaper.** If the task is genuinely "extract the text from this document image," a dedicated OCR system feeding a text-only LLM is frequently cheaper, faster, and more accurate than routing the raw image through a general VLM's vision tokens — VLMs are the right tool when visual layout, non-text visual content, or genuinely joint visual-and-textual reasoning is required, not as a default replacement for OCR.

---

## Interview questions

### Q1 — Walk through the patch-embedding arithmetic for a 224x224 image with 16x16 patches. How many tokens does the ViT encoder actually process?
**Testing:** whether the mechanics are understood well enough to derive the number, not just recall "ViT uses patches."
**Answer:** (224/16)^2 = 14^2 = 196 patches, each 16x16x3 = 768 raw pixel values flattened and linearly projected (a single shared `Linear(768, D)`, implementable as a `Conv2d` with stride equal to kernel size) to the embedding dimension `D`. Prepend a learnable `[CLS]` token and add learned positional embeddings: 196 + 1 = 197 total sequence positions entering the transformer encoder, mechanically identical in shape to a 197-token text sequence.
**Follow-up trap:** *"What happens to that count if you switch to 14x14 patches at the same resolution?"* — (224/14)^2 = 16^2 = 256 patches, more spatial granularity but self-attention cost scales quadratically with sequence length, so smaller patches are a real compute/detail tradeoff, not a free upgrade — this is exactly the ViT-B/16 vs ViT-L/14 naming convention distinction.

### Q2 — Explain CLIP's contrastive training objective mechanically. Why does batch size matter so much for CLIP pretraining quality?
**Testing:** whether the in-batch-negatives mechanism is actually understood, versus "it learns to match images and text."
**Answer:** For a batch of N (image, caption) pairs, both encoders produce L2-normalized embeddings, and you build the N x N cosine-similarity matrix between every image and every text embedding. Symmetric cross-entropy loss pushes the diagonal (true pairs) highest in both the image-to-text row direction and text-to-image column direction, with every off-diagonal pair in the batch serving as a free negative. Every other item in the batch is a negative example for every anchor, so a larger batch gives more — and harder — negatives per gradient step, which is why the original CLIP paper trained with a batch size of 32,768.
**Follow-up trap:** *"Could you get the same effect with a smaller batch and more epochs?"* — not equivalently — the in-batch-negative mechanism specifically needs a large *simultaneous* pool of negatives per step to shape the embedding space's discriminative geometry; more epochs over small-batch negatives don't substitute for the harder, more numerous negatives a large batch provides at each individual step, which is why memory-bank and momentum-encoder tricks (MoCo-style) exist specifically to approximate large-batch negatives without the full batch-size memory cost.

### Q3 — A "vision token" enters an LLM's context window. Is it the same kind of object as a text token? What can't you do with it that you can do with a text token?
**Testing:** the core conceptual distinction this whole module is built around.
**Answer:** No — a text token is a discrete id from a fixed vocabulary, looked up in an embedding table. A vision token is a continuous vector produced by a vision encoder and then a projection layer, with no corresponding vocabulary entry and no `decode()` back to a human-readable symbol. Consequences: you cannot apply constrained decoding/grammar-based sampling to a vision token the way you can force a text token to come from a valid JSON grammar, and you cannot run standard text-input guardrails/content filters against it, since those operate on tokenizable text.
**Follow-up trap:** *"Does self-attention treat them differently once they're both in the sequence?"* — no, and that's the point — self-attention operates on whatever vectors occupy each sequence position identically regardless of how that position's vector was produced; the distinction (discrete-vocab vs continuous-projection) exists entirely at the input-construction stage, not inside the transformer's attention computation itself.

### Q4 — Compute the approximate token cost of sending three 1024x1024 images to GPT-4o in high-detail mode in a single request. Is this cheap relative to a page of text?
**Testing:** whether the candidate has internalized real numbers rather than treating vision cost as an afterthought.
**Answer:** GPT-4o's tiling scheme charges roughly 765 tokens per 1024x1024 image in high-detail mode (base 85 tokens plus 170 tokens per 512x512 tile after scaling), so three images cost roughly 2,295 tokens — comparable to 1,500-2,000+ words of English text, i.e. several full pages, in a single request before any text prompt is even added.
**Follow-up trap:** *"How would you cut that cost without dropping the images entirely?"* — switch to low-detail mode (a flat 85 tokens per image regardless of size) if fine visual detail isn't needed for the task, downscale/crop to only the relevant region before sending, or cache/reuse an image's embedding across multiple turns instead of re-sending the raw image on every request if the API/architecture supports it.

### Q5 — What's the actual difference between LLaVA's fixed 576-token image encoding and Qwen2.5-VL's dynamic resolution approach? Why would you choose one over the other?
**Testing:** whether the tradeoff between simplicity and token efficiency is understood as a real architectural fork, not trivia.
**Answer:** LLaVA-1.5 always resizes to 336x336 and always produces 576 vision tokens (24x24 patches at 14px), regardless of the source image's actual size or visual complexity — simple to implement, but wasteful on small/simple images and detail-limited on large/complex ones. Qwen2.5-VL's Naive Dynamic Resolution lets the vision encoder process images at their native aspect ratio and resolution, with a merger module producing a variable token count (reported range roughly 4 to 16,384 tokens) proportional to actual visual content — far more token-efficient on average, at the cost of a materially more complex encoder and merger implementation.
**Follow-up trap:** *"If you're fine-tuning a VLM on your own data and engineering time is the scarce resource, which would you pick?"* — LLaVA's fixed-count architecture is genuinely simpler to fine-tune, debug, and reason about (every image is exactly 576 tokens, no dynamic-shape handling), which is a legitimate reason to choose it even knowing it's less token-efficient — the "better" architecture on paper isn't automatically the right choice under an engineering-time constraint.

### Q6 — Why does Whisper use a fixed 30-second chunk size rather than processing arbitrary-length audio directly?
**Testing:** whether the practical constraint (not just the number) is understood.
**Answer:** Whisper's encoder was trained on fixed 30-second log-mel spectrogram windows (16kHz sample rate, 10ms hop), so at inference the model processes audio in 30-second chunks, zero-padding shorter clips; audio longer than 30 seconds requires chunking with a sliding window and stitching, which is where boundary artifacts (a word split across a chunk boundary) can appear if the chunking/overlap strategy is naive.
**Follow-up trap:** *"How would you handle a boundary word split across two chunks in production?"* — overlap consecutive chunks by a few seconds and use timestamp-aware merging (many production Whisper deployments use overlapping windows plus a de-duplication pass on the overlapping region, or rely on Whisper's own timestamp tokens to align and stitch segments) rather than naive non-overlapping chunking, which risks silently dropping or duplicating words at each boundary.

### Q7 — Is Whisper a "multimodal model" in the same sense as LLaVA or GPT-4o? Justify the answer architecturally.
**Testing:** whether the candidate distinguishes fused multimodal architectures from cascaded pipelines, a real production-relevant distinction.
**Answer:** Not in the same sense. Whisper's audio encoder output and a downstream LLM don't share an embedding space by default — Whisper is a standalone encoder-decoder that converts audio directly to text tokens, and integrating it with an LLM typically means running ASR as a separate step and feeding the resulting text transcript into the LLM as ordinary text tokens (a cascaded pipeline). LLaVA/GPT-4o-style VLMs, by contrast, project the vision encoder's continuous embeddings directly into the LLM's own embedding space and concatenate them into one sequence the LLM attends over jointly — true fusion, not a cascade.
**Follow-up trap:** *"What's lost by treating audio as a cascaded pipeline instead of fusing it the way vision is fused?"* — paralinguistic signal (tone, emphasis, pauses, overlapping speech, uncertainty in the ASR itself) that never reaches the LLM once collapsed to a flat text transcript — this is exactly the gap native-audio-input models (GPT-4o's audio mode, Gemini's audio understanding) are trying to close by letting the LLM reason over acoustic signal jointly with semantic content, rather than only ever seeing what a frozen ASR system decided the words were.

### Q8 — A production RAG pipeline was extended to include full-page document images alongside OCR'd text, and cost/latency roughly tripled. Diagnose why, and propose two concrete fixes.
**Testing:** the real cost arithmetic applied to an actual production scenario, and whether a candidate can reason from principles to fixes rather than reciting numbers.
**Answer:** Each full-page image likely costs several hundred to over a thousand vision tokens per page (depending on the model and detail setting) on top of the existing OCR'd text tokens, roughly doubling or tripling per-request token count, and vision tokens incur the same O(n^2) attention cost as text tokens, so prefill latency scales worse than linearly with the added length. Two fixes: (1) if the OCR text is already being extracted and is accurate, drop the raw image entirely for pages where text-only reasoning suffices, reserving image input only for pages with genuinely important non-text visual content (tables, diagrams, signatures); (2) use low-detail/downscaled image modes for pages where only coarse layout signal is needed, reserving high-detail encoding for the specific pages/regions that actually require fine visual detail.
**Follow-up trap:** *"What if the OCR text alone is measurably less accurate than image+text for this document type?"* — that's a legitimate reason to keep the image, but the fix then shifts to cost-control rather than removal: crop to only the regions OCR struggled with (dense tables, handwriting, non-Latin scripts) rather than sending the full page image at full resolution for every request, and measure whether low-detail mode recovers enough accuracy at a fraction of the token cost before defaulting to high-detail.

### Q9 — Explain why a Vision Transformer needs an explicit positional embedding when a CNN doesn't.
**Testing:** whether the inductive-bias tradeoff between architectures is actually understood, a frequent staff-level probe.
**Answer:** A CNN's convolution operation is inherently local and translation-equivariant — a filter's response depends on the spatial arrangement of nearby pixels by construction, so spatial structure is baked into the architecture itself. A transformer's self-attention is permutation-invariant by construction — it has no inherent notion of which patch came from where in the image unless that information is explicitly added, which is exactly what the learned positional embedding (added elementwise to each patch embedding before the encoder) supplies.
**Follow-up trap:** *"What would happen to a ViT's accuracy if positional embeddings were removed entirely?"* — the model would still function (permutation-invariant attention over an unordered bag of patches) but would lose the ability to distinguish "a cat's face patch in the top-left" from "the same patch content in the bottom-right," destroying spatial reasoning tasks (localization, layout understanding) while leaving coarse global classification tasks (is there a cat somewhere in this image) relatively less affected — a real, testable ablation result from the ViT literature, not a hypothetical.

### Q10 — What does "tokenizer-free" mean in the context of vision input to an LLM, and is it fully accurate to say vision input has no tokenization step at all?
**Testing:** precision under a slightly loaded/imprecise term, a common staff-level trap.
**Answer:** "Tokenizer-free" for vision means there's no discrete-vocabulary lookup step the way BPE/SentencePiece works for text — no fixed vocabulary of visual "words" being matched against. It's not fully accurate to say there's *no* discretization step at all: patchification (chopping the image into a fixed grid) is itself a discretization of continuous pixel space into a fixed number of discrete spatial units (patches), it's just that each resulting patch's *content* is represented continuously (a projected vector) rather than being mapped to a discrete id from a closed vocabulary. The precise claim is "no discrete vocabulary," not "no discretization whatsoever."
**Follow-up trap:** *"Are there vision architectures that DO use a discrete visual vocabulary, closer to text tokenization?"* — yes — VQ-VAE-style discrete visual tokenizers (used in some image-generation architectures, and in some multimodal-generation research systems that need to *generate* images token-by-token, not just understand them) quantize continuous patch/latent representations into a fixed discrete codebook, genuinely analogous to text BPE vocabulary — but this is architecturally distinct from and less common than the continuous-projection approach used by the mainstream understanding-focused VLMs (LLaVA, Qwen-VL, GPT-4o-style) covered in this module.

### Q11 — Design the vision-token budget for an agentic browsing tool that takes a screenshot on every step of a multi-step task. What breaks if you don't think about this up front, and how would you bound it?
**Testing:** applying the token-cost material to a system-design-adjacent, staff-level scenario.
**Answer:** If every step's full-resolution screenshot (potentially 700-1,000+ vision tokens each in a GPT-4o-style API) is appended to a growing conversation history rather than only the current step's screenshot being sent, context usage grows roughly linearly with step count purely from images, independent of any text growth — a 20-step task could burn 15,000-20,000 tokens on screenshots alone before counting any reasoning text, risking hitting the context window ceiling mid-task or paying dramatically more than expected. Bound it by only including the most recent 1-2 screenshots in context (dropping older ones once the agent has acted on them and they're no longer needed for the current decision), using low-detail mode for screenshots where fine text reading isn't the immediate need, and summarizing older screenshot content into text once it's no longer the active focus.
**Follow-up trap:** *"What if the agent genuinely needs to compare the current screenshot against one from several steps ago (e.g. did this UI element change)?"* — that's a legitimate case for keeping a specific older screenshot in context rather than dropping it universally — the fix isn't a blanket "always drop old images" rule, it's an explicit, deliberate policy about which screenshots are load-bearing for the current decision versus which are stale, decided by the agent's control logic rather than left to unbounded accumulation.

### Q12 — CLIP is described as producing embeddings where "images and their captions land close together in a shared space." What does "close together" mean mechanically, and what's the failure mode when this breaks down (e.g. adversarial or out-of-distribution inputs)?
**Testing:** staff-level precision about what the training objective actually guarantees versus what people assume it guarantees.
**Answer:** "Close together" means high cosine similarity between the L2-normalized image embedding and text embedding, which is exactly and only what the contrastive training objective directly optimizes — it does not guarantee any particular semantic property beyond "this specific objective was pushed toward this specific geometric relationship on the training distribution." The known failure mode: CLIP is documented to be vulnerable to "typographic attacks" — an image with text pasted onto it (e.g. the word "iPod" written on an image of an apple) can shift the embedding toward the written word's semantic neighborhood strongly enough to flip zero-shot classification, because the contrastive training never explicitly taught the model to distinguish "described content" from "depicted text," both of which correlate with caption text in the training distribution.
**Follow-up trap:** *"Is this a CLIP-specific flaw, or does it generalize to VLMs built on top of CLIP?"* — it's inherited — a VLM whose vision encoder is a frozen or lightly fine-tuned CLIP carries this vulnerability forward unless the downstream LLM's own training (on top of the vision embeddings) has independently learned to discount text-in-image versus depicted content, which isn't guaranteed and is a real, checkable prompt-injection-via-image attack vector worth naming explicitly if asked about VLM security.

---

## Red flags that fail you

- Saying an image is "converted to tokens" without being able to state roughly how many, for any concrete model and resolution.
- Claiming vision tokens are discrete ids from a vocabulary the same way text tokens are, rather than continuous projected embeddings.
- Not knowing that vision-token cost is comparable to hundreds to low-thousands of text-token-equivalents per image, and treating "just add the image" as cost-free in a system design answer.
- Confusing CLIP's contrastive dual-encoder pretraining with a VLM's LLM-attached architecture — they're related but distinct: CLIP produces a vision encoder, a VLM is what you get after bridging that encoder into an LLM with a projection layer.
- Describing Whisper as producing tokens fused into an LLM's context the way vision tokens are — it doesn't, by default; it's a cascaded ASR pipeline.
- Being unable to explain why ViT needs positional embeddings when CNNs don't.
- Treating all VLMs as architecturally identical ("they all just use CLIP and an LLM") without knowing the real forks: fixed-patch-count (LLaVA) versus dynamic-resolution (Qwen-VL) versus tiling-based (GPT-4o) versus natively multimodal end-to-end (Gemini, reportedly GPT-4o's core architecture).

---

## Cheat card

```
ViT PATCH MATH: 224x224 img, 16x16 patch -> (224/16)^2 = 196 patches + 1
  [CLS] = 197 tokens. Each patch flattened (16*16*3=768 vals) + linear
  projection to embed dim D. Learned (not sinusoidal) positional embeds
  ADDED -- needed because self-attention is permutation-invariant, unlike
  a CNN's inherent spatial locality.

CLIP: dual encoder (ViT + text transformer), contrastive loss, symmetric
  cross-entropy over NxN cosine-sim matrix per batch, diagonal = true
  pairs. Bigger batch = more/harder in-batch negatives (orig paper: 32,768).
  Known failure: typographic attacks (text pasted on image shifts embed).

VISION TOKENS != TEXT TOKENS: continuous projected vectors, NOT discrete
  vocab ids. No decode(), no constrained decoding, bypass text-only
  guardrails/content filters (image-encoded text attack surface).

REAL TOKEN COSTS (memorize the ORDER OF MAGNITUDE, not exact digits):
  LLaVA-1.5 @ 336x336: FIXED 576 tokens, always.
  GPT-4o high-detail: 85 base + 170/512x512 tile. 1024x1024 ~= 765 tokens.
    low-detail: flat 85 tokens regardless of size.
  Claude: tokens = (w_px * h_px) / 750. 1000x1000 ~= 1,334 tokens.
  Qwen2.5-VL (dynamic resolution): ~4 to ~16,384 tokens, size-dependent.
  ORDER OF MAGNITUDE: one image ~= 500-1500+ text-token-equivalents.

PROJECTION LAYER = the bridge: vision encoder output -> LLM embed space.
  LLaVA: simple 2-layer MLP, per-patch, no cross-attn.
  Qwen-VL: merger module w/ 2D-RoPE-aware attention, dynamic token count.

ATTENTION COST: vision tokens go through every layer like text tokens.
  O(n^2) in TOTAL sequence length -- stacking images compounds
  quadratically, not linearly. Latency cost is real, not just $ cost.

WHISPER: encoder-decoder, NOT fused w/ LLM by default. 30-sec chunks,
  16kHz, log-mel spectrogram (80-bin thru large-v2, 128-bin large-v3+),
  10ms hop. 2 conv layers downsample -> sinusoidal pos embed -> transformer
  encoder. Decoder: autoregressive BPE text, cross-attends encoder states.
  Default integration = CASCADED (ASR then text into LLM), loses
  paralinguistic signal. Native-audio models (GPT-4o audio, Gemini) fuse.

ARCHITECTURE FORKS TO NAME: fixed-patch-count (LLaVA) vs dynamic-res
  (Qwen-VL, ~4-16384 tok) vs tiling (GPT-4o) vs natively multimodal
  end-to-end (Gemini, no disclosed frozen-encoder boundary).
```

## Sources

- [An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale — arXiv](https://arxiv.org/abs/2010.11929) — accessed 2026-08-03
- [Learning Transferable Visual Models From Natural Language Supervision (CLIP) — arXiv](https://arxiv.org/abs/2103.00020) — accessed 2026-08-03
- [Introducing Whisper — OpenAI](https://openai.com/index/whisper/) — accessed 2026-08-03
- [Understanding Whisper's Encoder-Decoder Transformer Architecture — Medium](https://medium.com/@mayankbambal/understanding-whispers-encoder-decoder-transformer-architecture-6d1beea51569) — accessed 2026-08-03
- [GPT-4o Vision Guide: Building with OpenAI's Image API — GetStream](https://getstream.io/blog/gpt-4o-vision-guide/) — accessed 2026-08-03
- [What does it cost to process an image with a vision model? — Roboflow](https://blog.roboflow.com/image-token-cost-vlm/) — accessed 2026-08-03
- [Vision — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/vision) — accessed 2026-08-03
- [Qwen/Qwen2-VL-7B-Instruct — How many tokens is one image? — Hugging Face](https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct/discussions/47) — accessed 2026-08-03
- [Qwen2-VL: A Vision Language Model That Runs Locally — Medium](https://medium.com/axinc-ai/qwen2-vl-a-vision-language-model-that-runs-locally-4b97ccab1bf6) — accessed 2026-08-03
- [Gemini 1.5: Unlocking multimodal understanding across millions of tokens — arXiv](https://arxiv.org/abs/2403.05530) — accessed 2026-08-03
- [Building Vision AI with Gemini 3: The Complete Guide — GetStream](https://getstream.io/blog/gemini-vision-ai-capabilities/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
