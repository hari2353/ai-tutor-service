# Sampling: Temperature, Top-k/p, Min-p, Beam, Speculative Decoding

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** T05-autoregression, T05-attention · **Updated:** 2026-07-28
> **Module id:** `T05-sampling` · **Tags:** inference
> **Lab:** `labs/py/08-sampling/`

## The 30-second version

A trained model outputs a probability distribution over the whole vocabulary at every step; everything in this module is about which subset of that distribution you actually sample from, and it's the cheapest lever in the entire stack because it changes zero weights. Temperature reshapes the distribution's sharpness before any truncation; top-k and top-p truncate to a fixed-size or fixed-cumulative-probability set; min-p truncates relative to the top token's own confidence, which adapts automatically to how sure the model is at each step — a property neither top-k nor top-p has. Repetition penalties fight degenerate loops that greedy and beam search are especially prone to. Beam search is the wrong default for open-ended generation (it produces bland, repetitive text by maximizing joint sequence probability, which is not what makes text good) but is still correct for tasks with one right answer, like translation. Speculative decoding is a different axis entirely — it doesn't change *what* gets sampled, it changes how fast you get there, by having a cheap draft model propose several tokens that the real model verifies in one parallel pass, typically cutting latency 2-3x on accepted spans with EAGLE-3-class drafters reaching 0.80-0.88 token acceptance rates on coding and instruction-following tasks. Constrained/structured decoding is yet another axis — it masks invalid tokens to *guarantee* a grammar (JSON schema, regex) is satisfied, with modern grammar engines like XGrammar adding under 40 microseconds per token, negligible next to the model's own 10-50ms per-token cost.

## Why this gets asked

Because sampling parameters are the first knobs anyone touches and the last ones anyone understands. The interviewer has watched a production system either loop into repetitive garbage under greedy decoding, or hallucinate wildly under too-high temperature, or burn an unnecessary latency budget because nobody set up speculative decoding despite having spare capacity for a draft model. They want to know if you understand these are genuinely different axes — some trade quality for diversity (temperature, top-p), some trade guaranteed correctness for flexibility (constrained decoding), and some trade nothing at all and only buy speed (speculative decoding, when done right) — and conflating them is a real production mistake, not just an academic distinction.

## Lineage: past → present → future

**What came before.** Early neural sequence generation (RNN-based machine translation, pre-2015) used almost exclusively beam search, inherited directly from statistical machine translation, where maximizing joint sequence probability was a reasonable proxy for translation quality because the task has a comparatively narrow space of acceptable outputs. As generation moved into open-ended tasks (story generation, chat), Holtzman et al.'s "The Curious Case of Neural Text Degeneration" (2019) showed that beam search and greedy decoding on open-ended generation produce text that is *more* probable than human text at every step yet reads as bland and repetitive — the pain that killed pure likelihood-maximization as the default: **human text is not the mode of the model's distribution, it lives in the typical set**, and greedy/beam search hunt for the mode. That paper introduced nucleus (top-p) sampling as the fix.

**Where it stands now.** Top-p and top-k, often combined with temperature, are the settled default for open-ended and chat-style generation across essentially every production API. Min-p (Nguyen et al., ICLR 2025) is the newest widely-adopted addition, dynamically scaling the inclusion threshold by the top token's own probability rather than using a fixed cumulative mass or fixed count — this genuinely fixes a known top-p failure mode (top-p keeps too many tokens when the model is very confident, since even far-lower-probability tokens can still be within the cumulative-p mass) and is now supported as a first-class parameter in vLLM, SGLang, and most open-source serving stacks, with practical settings around `min_p=0.05-0.1` combined with `temperature=0.7-1.0` reported to outperform top-p on creative-writing benchmarks at ICLR 2025. It is not without controversy: a 2025 critique (Schaeffer et al.) argues evaluation artifacts inflate min-p's reported advantage, and the live disagreement in the field is genuinely unresolved as of mid-2026 — a candidate who states min-p as unambiguously superior to top-p is overclaiming a debated result. On the speed axis, speculative decoding has moved from research curiosity (Leviathan et al., 2023) to standard production infrastructure: EAGLE-3-class draft heads (trained on the target model's internal features rather than token embeddings) and DeepSeek's own multi-token-prediction (MTP) heads are both deployed at scale, cutting latency roughly 2.8x and inference cost by close to half in reported 2026 production benchmarks. Constrained decoding for structured output has similarly moved from a niche feature to a default: XGrammar became the default structured-generation backend across vLLM, SGLang, and TensorRT-LLM in 2026, with per-token grammar-checking overhead now small enough (tens of microseconds) to be a rounding error against model inference latency.

**Where it's heading.** With reasonable confidence: speculative decoding keeps improving as draft-head training techniques mature (EAGLE-3's approach of fusing multiple internal layers into the draft head, rather than only the final layer, is the direction newer methods are extending) and as target models increasingly ship their own lightweight draft/MTP heads at pretraining time rather than requiring a separately-trained external draft model. The min-p vs top-p debate is likely to be resolved by more rigorous, artifact-controlled benchmarks over the next year or two rather than by consensus forming around either camp's current claims — treat the "which is better" question as genuinely open. More speculatively, adaptive/entropy-aware decoding (dynamically adjusting the sampling strategy per-step based on the model's own uncertainty, of which min-p is an early example and "Top-H" entropy-bounded decoding is a 2025 successor) is a plausible direction for further convergence between the "creative" and "coherent" ends of the sampling tradeoff, but no single adaptive method has yet become a clear default the way top-p did.

---

## Mental model

```
raw logits (vocab_size,)
        │  ÷ temperature   (T<1 sharpens, T>1 flattens, T=0 = argmax/greedy)
        ▼
   scaled logits
        │  softmax
        ▼
   probability distribution over vocab
        │
        ├─ top-k:    keep only the k highest-probability tokens, renormalize
        ├─ top-p:    keep the smallest set whose cumulative probability ≥ p, renormalize
        ├─ min-p:    keep tokens with prob ≥ (min_p × top-1 token's prob), renormalize
        │              (this threshold SHRINKS or GROWS automatically with model confidence)
        └─ repetition penalty: applied to LOGITS before the above, downweighting seen tokens
        ▼
   truncated distribution
        │  sample (or argmax if greedy, or expand K branches if beam search)
        ▼
   next token
```

The key distinction to hold in your head: **temperature reshapes the whole distribution's sharpness; top-k/top-p/min-p decide which part of the (reshaped) distribution is even eligible; repetition penalties bias against specific tokens based on generation history; beam search changes the search strategy entirely (tracking multiple candidate sequences, not just the next token); speculative decoding changes nothing about which token gets chosen, only how many forward passes it costs to get there; constrained decoding masks out tokens that would break a grammar, independent of all of the above.**

---

## How it actually works

### Temperature, derived

Given logits `z`, softmax with temperature `T` computes `p_i = exp(z_i/T) / Σ_j exp(z_j/T)`. As `T → 0`, the largest logit dominates the exponential ratio increasingly strongly, and the distribution collapses toward a one-hot vector on the argmax (greedy decoding is the `T=0` limit). As `T → ∞`, all logits get divided toward zero, `exp(z_i/T) → 1` for every token, and the distribution flattens toward uniform over the vocabulary. `T=1` recovers the model's raw trained distribution unmodified. Values above 1 flatten (more diversity, more risk of incoherence); values below 1 sharpen (more determinism, more risk of repetition/blandness). There is no universally correct value — it's a direct dial on the diversity/coherence tradeoff, and the right setting is task-dependent (near-0 for code/extraction, 0.7-1.0 for open-ended chat, higher for creative writing).

### Top-k and top-p, and top-p's real failure mode

**Top-k** keeps exactly the `k` highest-probability tokens regardless of how the probability mass is actually distributed among them. Failure: at a very confident step (e.g., "The capital of France is ___" with 99.9% mass on "Paris"), a fixed `k=50` still admits 49 essentially-irrelevant low-probability tokens into the sample pool — small probability, but not zero, and over enough generated tokens this produces occasional bizarre completions at exactly the moments the model was *most* sure of itself.

**Top-p (nucleus sampling)** keeps the smallest set of tokens whose cumulative probability is at least `p` (commonly 0.9-0.95). This adapts to the shape of the distribution better than top-k, but has its own failure mode in the *opposite* direction: when the model is extremely confident, the top few tokens might individually carry 90%+ of the mass but the remaining long tail can still require admitting a surprisingly large number of very-low-probability tokens to cross the cumulative threshold `p`, because a threshold on *cumulative* mass doesn't check whether any individual included token is meaningfully likely.

**Min-p (Nguyen et al., ICLR 2025)** fixes this directly: set the inclusion threshold as `min_p × P(top-1 token)`, not a fixed value. When the model is very confident (top token near 1.0), the effective threshold rises accordingly and the eligible set shrinks to just the genuinely plausible tokens. When the model is uncertain (top token has, say, only 15% probability), the threshold falls proportionally and a wider set of tokens becomes eligible — the exact adaptive behavior top-k and top-p both lack. Reported practical defaults: `min_p = 0.05-0.1` combined with `temperature = 0.7-1.0` ([Min-p Sampling, arXiv:2407.01082](https://arxiv.org/pdf/2407.01082), accessed 2026-07-28). Caveat, stated plainly: a 2025 critique (Schaeffer et al., "Min-p, Max Exaggeration") argues the ICLR 2025 benchmark comparisons contain evaluation artifacts that inflate min-p's reported win rate over top-p — this is a live, unresolved disagreement, not settled fact, and claiming otherwise in an interview is overclaiming.

### Repetition, frequency, and presence penalties

All three modify **logits before sampling**, not probabilities after:
- **Repetition penalty** (multiplicative, from CTRL/Keskar et al.): divides the logit of any already-generated token by a factor (`>1`) if positive, or multiplies if negative — pushes previously-seen tokens' logits toward zero, reducing their post-softmax probability.
- **Frequency penalty** (additive, OpenAI-style): subtracts a value proportional to *how many times* the token has already appeared — repeated repeats get progressively more suppressed.
- **Presence penalty** (additive, OpenAI-style): subtracts a flat value for *any* prior occurrence, regardless of count — discourages reusing a token at all, without further punishing reuse count.

**Why beam search needs these more than sampling does.** Beam search tracks the `k` highest joint-probability sequences at every step; once a repeated phrase becomes part of a high-probability partial sequence, continuing that repetition is *often* the locally-optimal continuation (repeating "the the the" can have higher joint probability than breaking the pattern, especially as the model's own attention starts strongly attending to the repeated tokens) — this is a well-documented degenerate feedback loop. Even moderate penalties are reported to be effective specifically because they flatten the early growth of the repetition probability before the loop has a chance to establish itself, rather than needing to fight an already-entrenched pattern.

### Beam search: when maximizing joint probability is (and isn't) the goal

Beam search maintains `k` candidate partial sequences ("beams") at each step, expanding each by its top continuations and keeping only the `k` highest cumulative-log-probability survivors. For **translation** (and other tasks with a comparatively narrow set of "correct" outputs, where fluency and adequacy dominate the objective), maximizing joint sequence probability is a reasonable proxy for quality, and beam search remains standard. For **open-ended generation** (chat, story writing), Holtzman et al. (2019) showed decisively that beam search text is degenerate — repetitive, bland — precisely *because* it successfully maximizes joint probability, and human-written text does not live at the probability-maximizing point of the distribution; it lives in the "typical set," a region of moderately-high but not maximal probability that sampling-based methods (top-p, min-p) target much more naturally than beam search does.

### Speculative decoding: same output distribution, fewer sequential forward passes

The core trick: run a small, cheap **draft model** to propose `γ` tokens autoregressively (fast, because it's small), then run the large **target model** once, in parallel, over all `γ` proposed tokens plus the true prefix, to get the target model's actual next-token distribution at every one of those positions simultaneously. Accept each proposed token with probability `min(1, p_target(token) / p_draft(token))` — a rejection-sampling correction that makes the *overall output distribution mathematically identical* to sampling from the target model alone, token for token. The first rejected token is resampled from a corrected distribution, and everything after it is discarded and redone. This is why speculative decoding is described as **exact**, not a quality-degrading approximation — same distribution, just fewer expensive sequential passes through the big model when acceptance is good.

**Acceptance rate is everything.** If the draft model matches the target well, most proposed tokens are accepted, and you get close to `γ`x fewer *sequential* target-model passes per token generated (though each pass now costs slightly more, since it processes `γ` positions at once). EAGLE-3 (2024), which trains a lightweight draft head directly on the target model's own internal feature representations (fused across multiple layers, not just the final one) rather than on raw token embeddings, reaches **0.80-0.88 acceptance rates** on coding and instruction-following tasks — high enough that production deployments report **~2.8x latency reduction and ~47% inference cost reduction** ([Speculative Decoding 2026 guides](https://callsphere.ai/blog/speculative-decoding-2026-eagle-3-medusa-v2-self-speculation), accessed 2026-07-28). Medusa (bolting `N` extra prediction heads directly onto the target model, each predicting position `+1, +2, ...`) is a competing, simpler architecture that avoids needing a separate draft model at all, but its acceptance rate degrades faster at longer speculation lengths and on varied (non-narrow-domain) prompts than EAGLE-3's approach.

### Constrained / structured decoding: guaranteeing validity, not just biasing toward it

Unlike everything above (which shapes a probability distribution the model is still free to sample any token from), constrained decoding **masks tokens outright**: given a JSON Schema or grammar, compile it into a finite-state (or pushdown) automaton; at every generation step, compute which vocabulary tokens are valid transitions from the automaton's current state, and set every other token's logit to `-∞` before softmax. This makes invalid output *impossible*, not merely unlikely — a categorically different guarantee than "well-prompted JSON" which can still occasionally emit invalid syntax. XGrammar, now the default backend in vLLM, SGLang, and TensorRT-LLM (as of March 2026), reports **under 40 microseconds per token** of grammar-checking overhead, negligible against the model's own 10-50ms per-token generation cost, largely because the grammar-state computation is precompiled and incremental rather than recomputed from scratch each step.

---

## Build it from scratch

```python
import numpy as np

def softmax(x):
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()

def temperature_scale(logits, T):
    if T == 0:
        out = np.full_like(logits, -np.inf)
        out[np.argmax(logits)] = 0.0
        return out
    return logits / T

def top_k_filter(probs, k):
    if k >= len(probs):
        return probs
    idx = np.argpartition(probs, -k)[-k:]
    out = np.zeros_like(probs)
    out[idx] = probs[idx]
    return out / out.sum()

def top_p_filter(probs, p):
    order = np.argsort(probs)[::-1]
    sorted_probs = probs[order]
    cum = np.cumsum(sorted_probs)
    cutoff = np.searchsorted(cum, p) + 1
    keep_idx = order[:cutoff]
    out = np.zeros_like(probs)
    out[keep_idx] = probs[keep_idx]
    return out / out.sum()

def min_p_filter(probs, min_p):
    threshold = min_p * probs.max()          # scales with the TOP token's own probability
    out = np.where(probs >= threshold, probs, 0.0)
    return out / out.sum()

def sample_next_token(logits, T=1.0, top_k=None, top_p=None, min_p=None, rng=None):
    rng = rng or np.random.default_rng()
    scaled = temperature_scale(logits, T)
    probs = softmax(scaled)
    if top_k is not None:
        probs = top_k_filter(probs, top_k)
    if top_p is not None:
        probs = top_p_filter(probs, top_p)
    if min_p is not None:
        probs = min_p_filter(probs, min_p)
    return rng.choice(len(probs), p=probs)
```

A minimal speculative-decoding sketch (rejection-sampling correction, the part that's easy to get subtly wrong):

```python
# untested sketch -- illustrates the exactness-preserving accept/reject step
def speculative_step(draft_probs, target_probs, draft_token, rng):
    """Returns (accept: bool, token_to_use)."""
    p_target = target_probs[draft_token]
    p_draft = draft_probs[draft_token]
    accept_prob = min(1.0, p_target / p_draft)
    if rng.random() < accept_prob:
        return True, draft_token
    # rejected: resample from the RESIDUAL distribution, not from target_probs directly
    residual = np.maximum(target_probs - draft_probs, 0.0)
    residual = residual / residual.sum()
    return False, rng.choice(len(residual), p=residual)
```

The residual-distribution resampling step is the detail most naive implementations get wrong — resampling directly from `target_probs` on rejection would bias the overall distribution; the correction must subtract out the draft's already-considered mass first, which is exactly what makes the algorithm exact rather than approximate.

Full implementation including top-k/top-p/min-p side-by-side distribution plots, a batched speculative-decoding harness, and an XGrammar-style FSM constrained-decoding toy example: **`labs/py/08-sampling/`**.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Basic sampling | vLLM/SGLang/TGI expose `temperature`, `top_k`, `top_p`, `min_p`, `repetition_penalty` as request params | Standard, cheap, no extra infra |
| Speculative decoding | EAGLE-3 draft heads, Medusa heads, or a small same-family draft model | 2-3x latency reduction on accepted spans; needs draft-model training or a compatible smaller sibling model |
| Structured output | XGrammar (default in vLLM/SGLang/TensorRT-LLM), Outlines, Guidance | Hard guarantee of schema validity, <40µs/token overhead |
| Model-native multi-token prediction | DeepSeek MTP heads, trained jointly with the base model | Removes the need for a *separate* draft model entirely |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Output loops on a repeated phrase or token | Greedy or beam search with no repetition penalty; repeated tokens become locally probability-maximizing | Add a repetition/frequency penalty, or switch off pure greedy/beam for open-ended tasks |
| Output is fluent but generic/bland | Beam search (or very low temperature) on open-ended generation | Switch to top-p/min-p sampling with temperature ~0.7-1.0 |
| Occasional bizarre, wildly off-topic token in an otherwise coherent response | Top-k with k too large, or top-p with p too high, admitting long-tail tokens at a confident step | Add or tighten min-p; it caps the tail specifically when the model is confident |
| Speculative decoding shows no speedup, or is slower than the base model | Draft model's acceptance rate is too low for this workload (draft/target distribution mismatch) | Retrain or pick a draft model whose distribution better matches the target on your actual traffic; measure acceptance rate directly, don't assume |
| Structured-output request occasionally returns invalid JSON despite a schema-following prompt | No hard constraint applied — relying on prompting alone instead of grammar-masked decoding | Switch to a constrained-decoding backend (XGrammar/Outlines); prompting alone cannot *guarantee* validity |
| Constrained decoding silently degrades output quality/relevance | The valid token at a given automaton state sometimes has very low model-assigned probability, forcing an unnatural completion (the "constraint tax") | Loosen the grammar where possible, or accept the quality tax as the cost of guaranteed validity for that field |

---

## Tradeoffs & when NOT to use it

- **Don't use beam search for open-ended generation.** It's the wrong objective (joint probability maximization) for a task where the target isn't a single "most likely" continuation; it reliably produces bland, repetitive text. Use it for translation and other narrow, largely-single-correct-answer tasks.
- **Don't stack top-k, top-p, and min-p all aggressively at once without understanding what each is doing** — they compose, but debugging "why did the model just say that" gets much harder with three interacting truncation mechanisms instead of one deliberate choice.
- **Don't treat min-p as settled science over top-p.** The comparative benchmark claims are contested (Schaeffer et al., 2025); pick based on your own task's measured behavior, not a blog post's recommendation.
- **Speculative decoding isn't free — it costs a draft model** (extra parameters, extra memory, extra maintenance if custom-trained) and only pays off if acceptance rate is genuinely high on your traffic; measure it, don't assume a published acceptance rate transfers to your workload.
- **Constrained decoding guarantees syntactic validity, not semantic correctness.** A JSON-schema-constrained model can still confidently emit a syntactically perfect but factually wrong or logically inconsistent structure; don't conflate "guaranteed to parse" with "guaranteed to be right."
- **Very low temperature (near-greedy) is the wrong default for anything requiring diversity across repeated calls** (e.g., generating N candidate solutions to rerank) — it collapses most calls to near-identical output, defeating the purpose of sampling multiple candidates at all.

---

## Interview questions

### Q1 — Walk through what temperature does mathematically, including both limits.
**Testing:** baseline fluency with the actual math, not just "temperature controls randomness."
**Answer:** `p_i = exp(z_i/T) / Σ exp(z_j/T)`. As `T→0`, the largest logit's exponential dominates increasingly, so the distribution collapses to one-hot on the argmax — greedy decoding is exactly the `T=0` limit. As `T→∞`, every `z_i/T→0`, so `exp(z_i/T)→1` for all tokens and the distribution flattens toward uniform. `T=1` is the model's raw trained distribution.
**Follow-up trap:** *"Does higher temperature always mean better diversity?"* — no, past a certain point it starts sampling tokens the model assigns genuinely low probability to, producing incoherence rather than useful diversity; temperature widens the *tail* that a truncation method (top-p/top-k/min-p) then has to crop back down, so temperature and truncation are usually tuned together, not independently.

### Q2 — Explain top-p's specific failure mode that motivated min-p.
**Answer:** Top-p keeps the smallest set of tokens whose *cumulative* probability crosses threshold `p`. When the model is very confident (top token near 1.0), the remaining probability mass is thin but can still be spread across a long tail of tokens, and reaching a high cumulative threshold like 0.9 can require admitting a surprisingly large number of individually near-irrelevant tokens purely to hit the cumulative target.
**Follow-up trap:** *"So min-p is strictly better?"* — that claim is contested; a 2025 critique (Schaeffer et al.) argues the benchmarks showing min-p's advantage contain evaluation artifacts. State the debate exists rather than picking a side unconditionally.

### Q3 — Derive the min-p threshold and explain why it adapts to model confidence automatically.
**Answer:** `threshold = min_p × P(top-1 token)`. When the model is confident (top-1 probability near 1.0), the threshold rises proportionally, shrinking the eligible set to only genuinely plausible tokens. When the model is uncertain (top-1 probability low, e.g., 0.15), the threshold falls proportionally, and a wider set of tokens becomes eligible — the threshold moves *with* the model's own confidence rather than being fixed, which is exactly what top-k and top-p lack.
**Follow-up trap:** *"What's a reported practical default, and does it transfer across tasks?"* — `min_p ≈ 0.05-0.1` combined with `temperature 0.7-1.0` is reported to work well for creative tasks specifically; there's no universal default, and the value should be tuned per task the same way temperature is.

### Q4 — Why is beam search the wrong default for chat/open-ended generation, given it maximizes sequence probability?
**Answer:** Holtzman et al. (2019) showed human-written text does not sit at the probability-maximizing point of a language model's distribution — it lives in the "typical set," a region of moderately high but non-maximal probability. Beam search successfully finds high-joint-probability sequences, and that success is exactly why the output reads as bland and repetitive: maximizing likelihood is not the same objective as "sounds like something a person would write."
**Follow-up trap:** *"When would beam search actually be the right choice?"* — narrow, largely single-correct-answer tasks like machine translation, where fluency and adequacy genuinely correlate well with sequence probability and the space of "acceptable" outputs is much smaller than in open-ended generation.

### Q5 — Explain why repetition/frequency/presence penalties matter more for beam search than for top-p sampling.
**Answer:** Beam search tracks the highest joint-probability partial sequences; once a repeated phrase becomes part of a high-probability beam, continuing that repetition can be the locally probability-maximizing choice — the model's own attention increasingly attends to the repeated pattern, entrenching it further. Penalties, applied as a logit adjustment before sampling, are reported to be most effective at flattening the *early* growth of this feedback loop, before it establishes itself, rather than fighting an already-dominant repeated pattern.
**Follow-up trap:** *"What's the risk of setting the penalty too high?"* — over-penalizing forces the model into awkward synonyms or unnatural phrasing to avoid reusing legitimate, contextually-correct repeated terms (e.g., forcing variation in technical terminology in a paper where consistent terminology is actually correct) — the right penalty strength is genuinely task-dependent.

### Q6 — Explain speculative decoding's correctness guarantee: why is it "exact" and not an approximation?
**Answer:** A draft model proposes tokens; the target model verifies them in one parallel forward pass. Each proposed token is accepted with probability `min(1, p_target/p_draft)` — a rejection-sampling correction. If rejected, the next token is resampled from the *residual* distribution `max(p_target - p_draft, 0)`, normalized — not from `p_target` directly. This accept/reject/residual-resample scheme is mathematically constructed so the marginal distribution of the final output token is provably identical to sampling directly from the target model, token for token, regardless of what the draft model looks like.
**Follow-up trap:** *"What happens if someone resamples from `p_target` directly on rejection instead of the residual?"* — it silently biases the output distribution away from the target model's true distribution, because it double-counts probability mass the draft model already had a chance to place, and the "exact" guarantee no longer holds — this is a genuinely easy bug to introduce and a real interview trap.

### Q7 — What acceptance rate does EAGLE-3 achieve and what architectural choice gets it there?
**Answer:** 0.80-0.88 on coding and instruction-following tasks. EAGLE-3 trains its lightweight draft head directly on the *target model's own internal feature representations*, fused across multiple transformer layers rather than only the final layer, instead of training on raw token embeddings — this gives the draft head access to richer intermediate signal about what the target model is likely to predict next, which is why it beats EAGLE-2 by 20-40% and outperforms Medusa, especially as speculation length grows.
**Follow-up trap:** *"Does a high acceptance rate always translate directly into proportional latency savings?"* — no; each verification pass costs more per forward call (processing `γ` positions instead of 1), and communication/memory-bandwidth overhead doesn't disappear, so real speedup is sublinear in acceptance rate and needs to be measured on your actual serving hardware and traffic mix, not assumed from a benchmark number.

### Q8 — How does constrained decoding guarantee valid JSON, and what does it not guarantee?
**Answer:** A JSON Schema is compiled into a finite-state (or pushdown) automaton; at each generation step, the automaton's current state determines the valid set of next tokens, and every other token's logit is set to `-∞` before softmax, making invalid syntax literally unreachable. It guarantees *syntactic* validity — the output will always parse — but says nothing about semantic correctness: the model can still confidently produce a syntactically perfect JSON object with a wrong field value or an internally inconsistent structure.
**Follow-up trap:** *"XGrammar reports under 40 microseconds per token overhead — is this always negligible?"* — yes relative to typical model inference latency (10-50ms/token), but the real cost is the "constraint tax": at some grammar states, the only valid tokens may have very low model-assigned probability, forcing an unnatural continuation the model wouldn't otherwise choose — a quality cost, not a latency cost, and it's the more important number to watch in practice.

### Q9 — A colleague sets `temperature=0` for a customer support bot to "make it more reliable." Evaluate this.
**Answer:** `temperature=0` is greedy decoding, which is deterministic but not necessarily more *correct* — it's the most likely single continuation, which for genuinely ambiguous queries can still be a confidently-wrong answer, and greedy decoding is specifically the mode most vulnerable to repetition loops on longer generations since there's no mechanism to escape a locally-dominant repeated pattern once one starts.
**Follow-up trap:** *"So what would you set instead?"* — a low but nonzero temperature (e.g., 0.2-0.4) combined with a mild repetition penalty typically balances determinism (important for a support bot's consistency) against escaping repetition loops, and if strict output format matters (e.g., a structured ticket classification), constrained decoding addresses that more directly than temperature ever could.

### Q10 — Design the decoding stack for a coding assistant that needs both low latency and valid, parseable code blocks.
**Testing:** synthesis connecting multiple axes of this module.
**Answer:** Speculative decoding with an EAGLE-3-style draft head trained on this specific target model, since coding tasks are reported to have some of the highest achievable acceptance rates (0.80-0.88), directly cutting latency. Layer constrained decoding for any strictly-structured output the assistant must produce (e.g., a function-call schema, a diff format), using a grammar engine like XGrammar so output validity is guaranteed rather than merely likely. For the natural-language explanation portions, moderate temperature (0.3-0.6) with top-p or min-p, since code explanations benefit from some fluency variation but not open-ended creative diversity. Keep beam search out of the stack entirely — it's the wrong objective for both the free text and, redundantly, for the already-constrained code portions.
**Follow-up trap:** *"Do the speculative decoding and constrained decoding layers interact?"* — yes, and this is a genuine engineering detail: the draft model's proposed tokens must also be checked against the same grammar constraint before verification, or you can end up either wasting draft proposals that were always going to be rejected by the grammar, or in a worse case, verifying against the target model's constrained distribution while the draft model proposed from its *unconstrained* distribution, silently lowering the effective acceptance rate; production stacks that support both together apply the grammar mask to both models' logits consistently.

---

## Red flags that fail you

- Saying beam search is "the standard" way to generate open-ended text.
- Confusing top-p (cumulative probability threshold) with top-k (fixed count).
- Claiming speculative decoding is a quality/accuracy tradeoff rather than an exact, distribution-preserving speedup technique.
- Not knowing that resampling from the raw target distribution on speculative-decoding rejection (instead of the residual) breaks exactness.
- Describing constrained decoding as guaranteeing "correct" output rather than "valid" (parseable) output.
- Presenting min-p as unambiguously superior to top-p with no mention of the ongoing benchmark dispute.
- Not distinguishing frequency penalty (scales with repeat count) from presence penalty (flat, one-time).

---

## Cheat card

```
TEMPERATURE     p_i = exp(z_i/T)/sum(exp(z_j/T));  T->0 = greedy/argmax;  T->inf = uniform;  T=1 = raw dist
TOP-K           keep k highest-prob tokens, fixed count -- ignores actual mass distribution
TOP-P (nucleus) keep smallest set with cumulative prob >= p -- can admit long tail at confident steps
MIN-P           threshold = min_p * P(top-1 token) -- adapts to model confidence; ~0.05-0.1 w/ T=0.7-1.0
                debated vs top-p (Schaeffer et al. 2025 critique) -- NOT settled
PENALTIES       repetition (mult., logit/factor), frequency (additive, scales w/ count), presence (additive, flat)
                applied to LOGITS before sampling; beam search needs them most (repetition = locally optimal)
BEAM SEARCH     tracks k highest joint-prob sequences -- right for translation, WRONG for open-ended (bland/repetitive)
                Holtzman 2019: human text lives in the "typical set," not the probability-maximizing mode
SPEC. DECODING  draft proposes gamma tokens, target verifies in 1 parallel pass
                accept w/ prob min(1, p_target/p_draft); reject -> resample from RESIDUAL (p_target - p_draft)
                EXACT: output distribution identical to sampling target model alone
EAGLE-3         draft head trained on target's fused internal features, not token embeddings
                0.80-0.88 acceptance (code/instruction-following); ~2.8x latency, ~47% cost cut (2026 reports)
MEDUSA          N extra heads bolted on target model, no separate draft model; degrades faster at longer speculation
CONSTRAINED DEC grammar/schema -> FSM/PDA; mask invalid tokens to logit=-inf every step
                guarantees SYNTACTIC validity only, not semantic correctness ("constraint tax")
XGRAMMAR        default in vLLM/SGLang/TensorRT-LLM (2026) -- <40us/token overhead, negligible vs 10-50ms/token infer
```

## Sources

- [Min-p Sampling for Creative and Coherent LLM Outputs (arXiv:2407.01082)](https://arxiv.org/pdf/2407.01082) — accessed 2026-07-28
- [Min-p, Max Exaggeration: A Critical Analysis of Min-p Sampling (arXiv:2506.13681)](https://arxiv.org/pdf/2506.13681) — accessed 2026-07-28
- [Speculative Decoding in 2026: EAGLE-3, Medusa-V2, and Self-Speculation](https://callsphere.ai/blog/speculative-decoding-2026-eagle-3-medusa-v2-self-speculation) — accessed 2026-07-28
- [Amazon SageMaker AI now supports EAGLE speculative decoding](https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-sagemaker-eagle-decoding) — accessed 2026-07-28
- [Constrained decoding: forcing LLM output to a grammar](https://zeroentropy.dev/concepts/constrained-decoding/) — accessed 2026-07-28
- [JSONSchemaBench: A Rigorous Benchmark of Structured Outputs for Language Models (arXiv:2501.10868)](https://arxiv.org/pdf/2501.10868) — accessed 2026-07-28
- [Solving LLM Repetition Problem in Production (arXiv:2512.04419)](https://arxiv.org/pdf/2512.04419) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
