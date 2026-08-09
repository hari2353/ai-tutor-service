# Pretraining: Data Curation, Dedup, Scaling Laws, Curriculum

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** T05-autoregression, T05-tokenization, T05-build-nanogpt · **Updated:** 2026-07-28
> **Module id:** `T05-pretraining` · **Tags:** training
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one (data pipeline extensions)

## The 30-second version

Pretraining quality is decided before a single gradient step: filter and deduplicate the corpus (MinHash near-dedup, quality classifiers, boilerplate removal), decide a mixture across domains (web, code, books, math), and only then does the model-size-vs-token-count question matter. Chinchilla (Hoffmann et al., 2022) established that for a fixed compute budget, loss is minimized near a ~20 tokens-per-parameter ratio — but almost nothing shipped after 2023 actually targets that ratio, because Chinchilla optimizes training-loss-per-FLOP, not total cost of ownership, and inference cost (which scales with parameters, not training tokens) dominates lifetime cost for any model served at real traffic. The practical replacement is data-constrained and inference-aware scaling: Muennighoff et al. (2023) showed repeating data up to ~4 epochs costs almost nothing and up to ~16 epochs still helps before returns collapse, which is why frontier labs train far past Chinchilla-optimal — Qwen3-0.6B trained on a 60,000:1 token-to-parameter ratio, and LLaMA-family and Qwen/LFM models routinely train 100-1000x past the "optimal" ratio because tokens are cheaper than the perpetual cost of a bigger model in production. Compute budgeting itself is simple arithmetic (`FLOPs ≈ 6ND`) once you have `N` and `D`; the actual engineering effort goes into the data pipeline — a duplicate-heavy or garbage-heavy corpus wastes the FLOPs regardless of how well the arithmetic works out.

## Why this gets asked

Because nearly every candidate who has fine-tuned a model has never had to think about what feeds a pretraining run, and interviewers who have shipped a foundation model (or evaluated vendor claims about one) have watched a training run burn a $2M compute budget on a corpus with 15% near-duplicate content, silently wasting a fifth of the spend on tokens the model had already memorized. They want to know whether you understand that data quality problems are invisible in the loss curve — a model trained on duplicated data still shows a smoothly decreasing loss, it just plateaus at a worse number than the FLOP budget should buy, which only becomes visible against a scaling-law prediction, not from the curve alone.

## Lineage: past → present → future

**What came before.** Before 2020, "bigger corpus" mostly meant "more Common Crawl," with light heuristic filtering (language ID, basic boilerplate removal) and essentially no principled answer to how model size and dataset size should trade off against each other — early scaling work (Kaplan et al., 2020, "Scaling Laws for Neural Language Models") suggested model size mattered more than data size for a fixed compute budget, which is part of why GPT-3 (175B params, 300B tokens — a ratio of ~1.7 tokens/param) was trained comparatively data-light by later standards. The pain this produced: GPT-3-scale models were significantly undertrained relative to what their parameter count could absorb, meaning a much smaller model trained on more data could have matched their loss at a fraction of the inference cost — a fact nobody could prove until someone redid the scaling analysis properly.

**Where it stands now.** Hoffmann et al.'s Chinchilla paper (2022) fixed the Kaplan-era math (fitting IsoFLOP curves properly) and found the compute-optimal ratio is close to 20 tokens per parameter, then trained a 70B model on 1.4T tokens that beat the 280B-parameter Gopher trained on far fewer tokens at the *same* training compute — a genuinely important correction. But by 2023-2024 the field had already moved past treating Chinchilla-optimal as the target: Meta's LLaMA (2023) explicitly trained smaller models (7B, 13B) on far more tokens than Chinchilla-optimal (1T tokens for 7B, a ~143:1 ratio) specifically because a model that's cheaper to run at inference beats a "loss-optimal" one once you account for serving cost at scale — this is the "Beyond Chinchilla-optimal" argument formalized by several 2024 papers on inference-aware scaling laws. On the data side, deduplication has become as load-bearing as the scaling math: FineWeb's pipeline uses MinHash over 5-grams (112 hash functions, 14 buckets of 8) at a 75% similarity threshold, deduplicated *per crawl snapshot* rather than globally, because global dedup was found to systematically discard older but still-valuable content in favor of whatever happened to be crawled last ([FineWeb](https://arxiv.org/html/2406.17557v1), accessed 2026-07-28). The live disagreement is less about whether to dedupe (settled — yes) and more about domain mixture: static mixture weights fit on small proxy models (DoReMi, DoGE, RegMix) are the common current practice, but they don't adapt as training progresses, and dynamic/online reweighting approaches are actively being researched without a clear production-proven winner as of mid-2026.

**Where it's heading.** With reasonable confidence: token-to-parameter ratios keep climbing — Qwen3-0.6B (April 2025) hit 60,000:1, and Liquid AI's LFM2.5-350M (April 2026) reportedly reached 80,000:1 by combining heavy data reuse with large-scale RL, suggesting "compute-optimal-for-loss" is now almost irrelevant to how real labs allocate budget compared to "optimal for the actual deployed cost function." Multi-stage curricula (bulk web data first, a later high-quality "mid-training" or "annealing" phase with curated/synthetic data, adopted by OLMo 2, Phi-4, and others) are becoming close to standard practice rather than a research curiosity. More speculatively: synthetic data mixed with natural text at controlled ratios (roughly 1:3 synthetic:natural in some reported setups) is being used to accelerate training, but pure-synthetic corpora risk model collapse (a self-reinforcing quality degradation across generations of synthetic data), and where the safe mixing ratio actually sits is still being empirically discovered rather than established — treat specific ratios as provisional, not settled science.

---

## Mental model

```
raw web crawl (petabytes)
        │  language ID, boilerplate/nav strip, basic quality heuristics
        ▼
   filtered corpus
        │  near-dedup (MinHash/LSH) — collapse clusters of similar docs to ONE representative
        ▼
   deduplicated corpus
        │  quality classifier (trained on "looks like Wikipedia/books" vs "looks like spam")
        ▼
   curated corpus  ──┐
                      │  mix domains by weight: web 60%, code 15%, books 10%, math/reasoning 10%, other 5% (illustrative)
                      ▼
              training token stream
                      │  Stage 1: broad web-dominated mixture (bulk of tokens)
                      │  Stage 2 ("mid-training"/annealing): shift toward high-quality/curated/synthetic data
                      ▼
                 trained model
```

Every stage upstream of "training token stream" is where the actual differentiation between labs happens — the transformer architecture and training loop are close to commoditized; the data pipeline is not.

---

## How it actually works

### Deduplication: exact vs fuzzy, and why fuzzy is the hard part

**Exact deduplication** is cheap: hash each document, drop exact repeats. It catches almost none of the real duplication in a web crawl, because near-duplicates (a news article mirrored across ten sites with different headers/footers, a forum thread quoted in full inside another thread) vastly outnumber byte-identical repeats.

**Fuzzy (near) deduplication** via MinHash + LSH is the real workhorse:

1. Break each document into overlapping n-grams (FineWeb uses 5-grams of words).
2. Hash each n-gram with `k` independent hash functions; the document's MinHash signature is the minimum hash value achieved for each function across all its n-grams — a compact, fixed-size sketch (FineWeb: 112 hash values) that approximates Jaccard similarity between documents.
3. Split the signature into `b` bands of `r` hash values each (FineWeb: 14 bands × 8 values); documents that match exactly within *any* band are placed in the same candidate-duplicate bucket (Locality-Sensitive Hashing) — this avoids the `O(n²)` cost of comparing every document pair directly.
4. Within each bucket, keep one representative document (typically the longest or highest-quality-scored), drop the rest.

**Threshold tuning.** A similarity threshold around 75% Jaccard is a common working point — high enough to avoid discarding genuinely distinct documents that happen to share common phrasing, low enough to actually catch near-duplicates. **Per-snapshot vs global dedup is a real, measured tradeoff**: FineWeb explicitly deduplicates *within* each crawl snapshot rather than globally across all snapshots, because global dedup was found to disproportionately keep whichever snapshot was processed first (or last, depending on implementation) and discard genuinely higher-quality older content purely due to processing order — a subtle bug-shaped quality regression that only shows up in downstream eval, not in the dedup step's own logs.

### Quality filtering

Beyond dedup, corpora are filtered by:
- **Heuristic rules**: minimum/maximum document length, ratio of alphabetic characters, absence of excessive boilerplate ("click here," repeated navigation text), line-length distribution (catches list-heavy or malformed pages).
- **Classifier-based filtering**: train a lightweight classifier (fastText or a small BERT-style model) to distinguish "high-quality" reference text (Wikipedia, curated books, well-formed articles) from typical web crawl, then keep documents scoring above a threshold. This is the single highest-leverage step in most published pipelines — FineWeb and its contemporaries report that classifier-based quality filtering produces the largest single jump in downstream benchmark performance per token, more than any individual dedup refinement.

### Scaling laws, derived from the numbers you'd actually use

**Chinchilla's core result**: for a fixed compute budget `C`, model parameters `N` and training tokens `D` trade off, and the loss-minimizing point satisfies `N ∝ C^0.5` and `D ∝ C^0.5` — both scale with the *square root* of compute, which is the mathematical content behind "roughly 20 tokens per parameter" being close to optimal across a wide range of budgets Hoffmann et al. tested.

**Compute budgeting arithmetic**: `FLOPs ≈ 6ND`. For a 7B-parameter model at the Chinchilla ratio (~140B tokens): `6 × 7×10^9 × 1.4×10^11 ≈ 5.9×10^21` FLOPs. At ~1.5×10^15 achievable FLOP/s on an 8-A100 node (bf16, good kernels, not theoretical peak), that's `5.9×10^21 / 1.5×10^15 ≈ 3.9×10^6` seconds ≈ **45 days on one 8-GPU node** — which is exactly why real training runs use hundreds to thousands of GPUs: to bring 45 node-days down to a few days of wall-clock time via data/tensor/pipeline parallelism.

**Why "Chinchilla-optimal" stopped being the target.** Chinchilla-optimal minimizes *training* loss per FLOP spent on *training*. It says nothing about inference cost, which scales with `N` (parameters) and is paid on every single request, indefinitely, at production traffic. A model trained past the Chinchilla ratio (more tokens, same or smaller `N`) accepts a training-time FLOP inefficiency (you're on the flatter part of the loss-vs-tokens curve for that model size) in exchange for a permanently cheaper model to serve. LLaMA-7B's ratio of ~143 tokens/param (1T tokens ÷ 7B params) is roughly 7x past the Chinchilla ratio for its size — a deliberate choice, not an oversight.

**Data-constrained scaling (Muennighoff et al., 2023)**: when you don't have enough *unique* high-quality tokens to hit your target ratio, repeating data is not free but is also not catastrophic. Their empirical finding, across ~400 runs from 10M to 9B parameters and up to 900B tokens: repeating data for **up to ~4 epochs causes negligible degradation** versus the same token count from unique data; meaningful (if diminishing) gains continue out to roughly **16 epochs**; benefit effectively disappears by around **40 epochs**, and each repetition's marginal value decays roughly like `(1-δ)^(k-1)` for the k-th pass ([Scaling Data-Constrained Language Models](https://arxiv.org/pdf/2305.16264), accessed 2026-07-28). The practical implication: if you're data-constrained, the right move is often a *smaller* model trained for more epochs on your available unique data, not shrinking the token budget to preserve a strict Chinchilla ratio.

### Curriculum: not just "easy examples first"

In LLM pretraining, "curriculum" mostly does not mean literally ordering examples from easy to hard (as in classic curriculum learning); it means **staged domain mixture**. The now-common two-stage pattern, adopted by OLMo 2, Phi-4, and others: Stage 1 trains on a broad, web-dominated mixture for the bulk of total tokens (maximizes raw scale and diversity cheaply); Stage 2 ("mid-training" or "annealing") shifts the mixture toward a smaller volume of high-quality, curated, and sometimes synthetic data (books, filtered web, instruction-adjacent text, math/code) for the final fraction of training, using a lower or specially-scheduled learning rate. This exploits the fact that late-training examples have outsized influence on final model behavior (the model is fine-tuning its already-mostly-formed representations), so spending the "expensive" curated data late is more efficient than diluting it across the entire run. A relevant recent finding: curriculum-based (staged) training needs a *different*, more moderate learning-rate decay schedule than uniform-mixture training — using the LR schedule tuned for a uniform-data run on a staged-mixture run measurably wastes the value of the late high-quality stage ([Predicting Training Re-evaluation Curves](https://arxiv.org/pdf/2509.25380), accessed 2026-07-28).

---

## Build it from scratch

A minimal MinHash near-dedup pipeline, illustrating the actual mechanism (not production-scale, but the same math):

```python
# untested sketch -- illustrates MinHash/LSH mechanics on a small corpus
import re, hashlib
from collections import defaultdict

def shingles(text: str, k: int = 5) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i+k]) for i in range(len(words) - k + 1)}

def minhash_signature(shingle_set: set[str], num_hashes: int = 32) -> tuple[int, ...]:
    sig = []
    for seed in range(num_hashes):
        min_h = min(
            int(hashlib.md5(f"{seed}:{s}".encode()).hexdigest(), 16)
            for s in shingle_set
        ) if shingle_set else 0
        sig.append(min_h)
    return tuple(sig)

def lsh_buckets(signatures: dict[str, tuple], bands: int = 8, rows: int = 4):
    buckets = defaultdict(list)
    for doc_id, sig in signatures.items():
        for b in range(bands):
            band = sig[b*rows:(b+1)*rows]
            buckets[(b, band)].append(doc_id)
    return {k: v for k, v in buckets.items() if len(v) > 1}  # candidate duplicate clusters

docs = {"a": "the quick brown fox jumps over the lazy dog",
        "b": "the quick brown fox jumps over a lazy dog",   # near-dup of a
        "c": "completely different content about databases"}
sigs = {k: minhash_signature(shingles(v)) for k, v in docs.items()}
dupes = lsh_buckets(sigs)
```

This is deliberately small-scale (MD5 per shingle per hash seed is far too slow for billions of documents — production pipelines use vectorized hashing and distributed bucketing, e.g., `datatrove`'s implementation). It is enough to show *why* LSH avoids the O(n²) pairwise comparison problem: documents only get compared directly if they land in the same band-bucket, and choosing `bands × rows` controls the precision/recall tradeoff between catching true near-duplicates and false-positive collisions.

Full deduplication + quality-classifier + domain-mixture pipeline on a real corpus subset (FineWeb sample): **`labs/py/06-build-nanogpt/data/`**.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Crawling & extraction | Common Crawl WARC/WET, trafilatura-style boilerplate stripping | Raw text extraction from HTML at web scale |
| Dedup & filtering | `datatrove` (HuggingFace), NeMo Curator | Distributed MinHash/LSH, quality classifiers, PII scrubbing, at billions-of-documents scale |
| Mixture design | DoReMi, DoGE, RegMix, or manual heuristic weights | Estimating per-domain weights via small proxy-model experiments before committing the full run |
| Scaling-law fitting | IsoFLOP sweeps at small scale (10M-1B params), extrapolated | Predicting the loss-optimal `N`/`D` split for the actual target compute budget before spending it |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Loss curve looks smooth and reasonable, but eval scores are well below what the compute budget should produce | Undetected near-duplicates inflating apparent training progress (model re-sees the same content) | Run MinHash dedup with a validated threshold; spot-check retained clusters manually |
| Model over-indexes on one domain's style/vocabulary in outputs | Domain mixture weights wrong, or one domain oversampled during data-constrained repetition | Recompute weights via a proxy-model sweep (DoReMi-style); cap max epochs per domain independently |
| Training run's actual loss trajectory diverges from the scaling-law prediction fit at small scale | Small-scale proxy runs used a different data mixture or tokenizer than the full run | Fit scaling laws on the *exact* pipeline (same filtering, same tokenizer) you'll use at full scale, not a convenience subset |
| Late-training ("mid-training") stage doesn't improve eval scores as expected | LR schedule tuned for uniform-mixture training used unchanged on a staged curriculum | Use a more moderate LR decay for the curriculum stage; the optimal schedule differs from the uniform-data case |
| Synthetic-data-heavy runs show early gains then plateau or regress on diversity-sensitive evals | Model collapse from too high a synthetic:natural ratio, or synthetic data itself generated from a narrow-distribution model | Keep synthetic data as a minority of the mixture (illustrative reported ratios sit near 1:3 synthetic:natural) and audit synthetic data diversity directly, not just downstream loss |

---

## Tradeoffs & when NOT to use it

- **Don't target strict Chinchilla-optimal if you're going to serve the model at real traffic.** It minimizes training FLOPs, not total cost of ownership; a smaller, more-overtrained model is very often the right call once inference volume is nontrivial.
- **Don't skip dedup to save pipeline engineering time.** The FLOP cost of training on duplicated data is not recovered by "just training longer" — duplicated tokens contribute far less marginal information than unique ones, so the wasted compute is real and roughly proportional to the duplication rate.
- **Don't over-repeat data past ~16 epochs expecting linear returns.** Muennighoff et al.'s results show returns collapse well before 40 epochs; past that point, additional repetition is close to pure waste and can start to hurt via memorization-driven overfitting on a narrow corpus.
- **Don't blindly copy a mixture ratio from a paper.** Published domain weights (web/code/books percentages) were tuned for that lab's specific corpus, tokenizer, and target capability profile; a proxy-model sweep on your own data is cheap relative to a full run and catches mismatches a borrowed ratio won't.
- **Global deduplication across all data sources/snapshots is not automatically better than per-snapshot dedup** — it can systematically bias which era or source of content survives; treat "more aggressive dedup" as a hypothesis to validate against downstream eval, not an unconditional improvement.

---

## Interview questions

### Q1 — State the Chinchilla scaling result and the compute-budget arithmetic behind it.
**Testing:** baseline fluency with real numbers.
**Answer:** For fixed compute `C`, both optimal parameters `N` and optimal tokens `D` scale as `C^0.5`, giving a compute-optimal ratio near 20 tokens per parameter across the range Hoffmann et al. tested. `FLOPs ≈ 6ND` connects the two: given a compute budget, solving `6ND = C` with `D ≈ 20N` gives `N ≈ √(C/120)`.
**Follow-up trap:** *"Is 20 tokens/param still the number people target in 2026?"* — no, and saying otherwise is a real red flag; production models routinely train at 100-1000x that ratio because Chinchilla optimizes training-loss-per-FLOP, not inference cost, which dominates total cost of ownership at scale.

### Q2 — Why did LLaMA deliberately train "past" the Chinchilla-optimal ratio?
**Answer:** LLaMA-7B trained on 1T tokens (~143 tokens/param, ~7x the Chinchilla ratio for that size) because a smaller model that's cheaper to run at inference — for the rest of its deployed life, across every request — beats a larger "training-FLOP-optimal" model once you account for the fact that inference cost scales with parameters and is paid indefinitely, while training cost is paid once.
**Follow-up trap:** *"Does that mean bigger training-token budgets are free wins?"* — no, returns diminish; the loss-vs-tokens curve for a fixed model size flattens, so there's a real point past which more tokens buy very little, distinct from the point where duplicated tokens buy nothing (data-constrained scaling) or where quality tokens run out entirely.

### Q3 — Explain MinHash + LSH deduplication mechanically, including why it avoids O(n²) comparison.
**Answer:** Represent each document as a set of n-gram shingles; compute a MinHash signature (the minimum hash value per hash function across all its shingles, using k independent hash functions) which approximates Jaccard similarity between documents. Split the signature into bands of rows; documents that match exactly within any band are grouped into a candidate bucket — only documents sharing a bucket are ever directly compared, avoiding all-pairs comparison. FineWeb uses 112 hash functions in 14 bands of 8.
**Follow-up trap:** *"What happens if you choose too few bands, or too many rows per band?"* — fewer bands (with more rows each) makes matching within a band harder, increasing false negatives (missed true duplicates); more bands (fewer rows each) increases false positives (unrelated documents colliding), raising review/compute cost downstream. The band/row split directly controls the precision/recall tradeoff of the LSH step.

### Q4 — Why does FineWeb deduplicate per-snapshot instead of globally?
**Answer:** Global deduplication across all crawl snapshots was found to systematically favor whichever snapshot was processed first (or last, depending on tie-breaking), discarding genuinely valuable content purely due to processing order rather than quality — a quality regression that doesn't show up in the dedup step's own metrics, only in downstream benchmark performance.
**Follow-up trap:** *"So is less aggressive dedup always safer?"* — no, this is specifically about global-vs-per-snapshot granularity, not about dedup aggressiveness generally; missing near-duplicates entirely (too little dedup) still wastes compute and can bias the model toward whatever content happened to be over-represented in the crawl.

### Q5 — What did Muennighoff et al.'s data-constrained scaling laws find about repeating data?
**Answer:** Across ~400 experiments (10M-9B params, up to 900B tokens, up to 1500 epochs), repeating data for up to ~4 epochs causes negligible degradation versus unique tokens; meaningful gains continue to roughly 16 epochs with diminishing returns; benefit is essentially gone by ~40 epochs. Each repetition's marginal value decays roughly geometrically.
**Follow-up trap:** *"If I only have 200B unique tokens but want to train a Chinchilla-ratio-sized model needing 1T, what do you do?"* — either shrink the model to match the effective (repetition-discounted) data budget, or accept training at up to ~4-16 epochs of repetition with a smaller-than-"ideal" model rather than a larger model repeating the same 200B tokens dozens of times past the point of diminishing returns; the paper's finding directly favors the smaller/more-epochs choice under data constraints.

### Q6 — Derive the compute-time estimate for training a 7B model at the Chinchilla ratio on an 8-GPU node.
**Answer:** `D ≈ 20 × 7×10^9 = 1.4×10^11` tokens. `FLOPs = 6ND ≈ 6 × 7×10^9 × 1.4×10^11 ≈ 5.9×10^21`. At ~1.5×10^15 achievable FLOP/s on 8 A100s (bf16, good kernels), time ≈ `5.9×10^21 / 1.5×10^15 ≈ 3.9×10^6 s ≈ 45 days`.
**Follow-up trap:** *"Your CFO asks why you need 500 GPUs instead of 8 if the total FLOPs are fixed."* — because FLOPs are fixed but wall-clock time is what the business cares about; parallelizing across ~60x more GPUs (with realistic scaling efficiency, not perfectly linear) brings 45 node-days down to under a day of wall-clock, at the cost of needing tensor/pipeline/data-parallel orchestration and dealing with communication overhead, which is why this is a systems engineering problem, not just an arithmetic one.

### Q7 — What's the difference between heuristic filtering and classifier-based quality filtering, and which matters more?
**Answer:** Heuristic filtering applies fixed rules (length bounds, alphabetic ratio, boilerplate detection) — cheap, catches obviously bad documents, but blunt. Classifier-based filtering trains a lightweight model (fastText, small BERT) to score documents against a "looks like high-quality reference text" target and filters by score threshold — more expensive to build, but reported as the single largest per-token quality lever in most published pipelines, larger than incremental dedup refinements.
**Follow-up trap:** *"What's the risk of over-relying on a quality classifier trained on Wikipedia-like reference text?"* — it can systematically down-weight legitimate but stylistically different content (technical forums, non-Western-formatted prose, code-adjacent text), narrowing the model's effective training distribution in ways that only surface as blind spots much later, in specific downstream domains the classifier implicitly penalized.

### Q8 — What is "curriculum" in modern LLM pretraining, and how is it different from classic ML curriculum learning?
**Answer:** It almost always means staged *domain mixture*, not per-example difficulty ordering: a broad web-dominated mixture for the bulk of tokens, followed by a shorter high-quality/curated/synthetic "mid-training" or annealing stage near the end, adopted by OLMo 2, Phi-4, and others. This differs from classic curriculum learning's easy-to-hard example ordering; it's closer to "spend your most expensive, highest-signal data where it has outsized influence on the final model," which is late in training.
**Follow-up trap:** *"Why does late data have outsized influence?"* — the model's representations are already mostly formed by late training, so the final stage functions similarly to a targeted fine-tune on top of a well-trained base, meaning a small amount of high-quality late data shifts final behavior more per-token than the same data mixed uniformly throughout, where its signal is diluted by orders of magnitude more tokens.

### Q9 — A staged (curriculum) training run underperforms a uniform-mixture baseline at the same token budget. What's your first hypothesis?
**Answer:** The learning-rate schedule. Curriculum-based training needs a more moderate LR decay than what's optimal for uniform-mixture training; reusing the uniform-training schedule on a staged run can waste the value of the late high-quality stage because the LR may already be too low (or decaying on the wrong schedule) by the time the high-value data arrives.
**Follow-up trap:** *"You retune the LR schedule and it's still underperforming. What next?"* — check whether the domain-mixture weights for stage 1 were tuned via a small-model proxy sweep on the *same* filtered/deduplicated pipeline as the full run; a mismatch between the proxy experiment's data and the production pipeline's data is a common, easy-to-miss source of a scaling-law or mixture-weight prediction failing to transfer.

### Q10 — Design the data pipeline and scaling-law approach for a team with a $2M training compute budget and access to 500B unique tokens of reasonably good text.
**Testing:** synthesis under a real constraint.
**Answer:** First, run MinHash dedup and classifier-based quality filtering on the full 500B-token pool to get an honest count of *usable, deduplicated* tokens — this number, not the raw 500B, is what feeds the scaling-law fit. Fit IsoFLOP scaling curves at small scale (10M-1B params) using the *actual* filtered/tokenized pipeline, not a convenience subset, to predict the loss-optimal `N`/`D` split for the target compute. Given the likely gap between available unique tokens and a Chinchilla-ratio ideal, decide deliberately whether to (a) size the model to match available data at low repetition, or (b) accept up to ~4-16 epochs of repetition on a somewhat larger model, using Muennighoff's discount curve to estimate effective data size either way. Then decide the ratio against inference-cost expectations: if this model will serve high production traffic, bias toward a smaller model with a much higher token/parameter ratio than Chinchilla suggests, since serving cost will dominate the $2M training spend within months of launch at any real traffic volume.
**Follow-up trap:** *"Your finance team asks for a single 'optimal' model size number before any of this analysis is done."* — the honest answer is that you can't give a defensible number without first knowing the deduplicated/filtered unique token count and the expected inference traffic profile; giving a number anchored purely on raw corpus size or a borrowed Chinchilla ratio is exactly the mistake that produces an expensively wrong model.

---

## Red flags that fail you

- Citing 20 tokens/parameter as "the" target ratio without qualifying that production models routinely train far past it for inference-cost reasons.
- Not knowing that MinHash/LSH exists specifically to avoid O(n²) pairwise document comparison.
- Treating a smooth loss curve as proof the data pipeline is healthy — duplication and poor mixture don't show up as curve instability, only as a worse-than-predicted asymptote.
- Confusing "curriculum" in LLM pretraining with classic easy-to-hard example ordering.
- Assuming more epochs on the same data always helps, with no mention of the diminishing-returns/collapse point.
- Applying a published domain mixture ratio unchanged to a different corpus without re-validating.

---

## Cheat card

```
CHINCHILLA      N,D both ~ C^0.5 for fixed compute C; optimal ratio ~20 tokens/param (Hoffmann 2022)
6ND             FLOPs ~= 6 * N_params * D_tokens (compute budgeting arithmetic)
WORKED EX       7B @ Chinchilla ratio (140B tok): 6ND ~= 5.9e21 FLOPs ~= 45 node-days on 8xA100
BEYOND CHIN.    LLaMA-7B trained ~143 tok/param (~7x Chinchilla) -- inference cost >> training FLOP-per-loss
2026 EXTREMES   Qwen3-0.6B: 60,000:1 tok/param; LFM2.5-350M: 80,000:1 (w/ large-scale RL)
DEDUP           MinHash + LSH: 5-gram shingles, k hash fns -> signature, split into bands -> bucket matches
FINEWEB CONFIG  112 hash fns, 14 bands x 8, ~75% Jaccard threshold, dedup PER SNAPSHOT not globally
DATA-CONSTRAINED (Muennighoff 2023): repeat up to ~4 epochs ~free; gains to ~16 epochs; ~gone by ~40 epochs
                value of k-th repetition decays ~ (1-delta)^(k-1)
QUALITY FILTER  classifier-based (fastText/small BERT vs reference text) > heuristic rules alone, biggest per-token lever
CURRICULUM      = staged domain MIXTURE (web-heavy -> curated/synthetic "mid-training"), not example difficulty order
                needs a more moderate LR decay than uniform-mixture training
MIXTURE WEIGHTS DoReMi/DoGE/RegMix: fit weights on small proxy models before committing full run
SYNTHETIC DATA  minority ratio (illustrative ~1:3 synthetic:natural) -- pure-synthetic risks model collapse
```

## Sources

- [The FineWeb Datasets: Decanting the Web for the Finest Text Data at Scale (arXiv:2406.17557)](https://arxiv.org/html/2406.17557v1) — accessed 2026-07-28
- [FineWeb2: One Pipeline to Scale Them All (arXiv:2506.20920)](https://arxiv.org/pdf/2506.20920) — accessed 2026-07-28
- [Scaling Data-Constrained Language Models (arXiv:2305.16264)](https://arxiv.org/pdf/2305.16264) — accessed 2026-07-28
- [Chinchilla data-optimal scaling laws: In plain English](https://lifearchitect.ai/chinchilla/) — accessed 2026-07-28
- [Prescriptive Scaling Laws for Data Constrained Training (arXiv:2605.01640)](https://arxiv.org/html/2605.01640) — accessed 2026-07-28
- [Predicting Training Re-evaluation Curves Enables Effective Data Curriculums for LLMs (arXiv:2509.25380)](https://arxiv.org/pdf/2509.25380) — accessed 2026-07-28
- [AI Pretraining Data Curation on GPU Cloud: NeMo Curator, Datatrove, and FineWeb-Style Pipelines (2026 Guide)](https://www.spheron.network/blog/ai-pretraining-data-curation-nemo-curator-datatrove-fineweb-gpu-cloud/) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
