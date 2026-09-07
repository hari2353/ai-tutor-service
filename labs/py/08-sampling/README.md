# Lab 08: Decoding Strategies From Scratch

**Track:** T05 LLM Internals · **Time:** 2h · **XP:** 50
**Module:** `T05-sampling`

**You will build:** every decoding knob you'd set on a vLLM/HF `SamplingParams` object — temperature, top-k, top-p (nucleus), min-p, beam search, and the speculative-decoding accept/reject test — on fixed logit vectors.

**You will be able to answer:** *"top_p=0.9 removed half my distribution — what exactly does nucleus sampling keep? And what does min_p do that top_p doesn't?"*

## Setup

```bash
cd labs/py/08-sampling
pip install pytest
```

## The spec

1. **`softmax(logits, temperature=1.0)`** — numerically stable (subtract max), T divides logits.
2. **`top_k_mask(logits, k)`** — return a copy where all but the k largest are `-inf`.
3. **`top_p_mask(logits, p)`** — nucleus: sort descending, keep the smallest prefix whose cumulative probability ≥ p; a token that straddles the boundary is KEPT (the one that crosses the threshold is included).
4. **`min_p_mask(logits, p)`** — keep tokens with prob ≥ p × max_prob; everything else `-inf`.
5. **`sample(logits, temperature, rng)`** — sample from the final distribution; seeded rng.
6. **`beam_search(step_logits, k, length_penalty=0.0)`** — step_logits is a list of per-step logit vectors (same vocabulary each step); expand k beams, score = sum log-prob / (len ** length_penalty); return (best_sequence, score) sorted.
7. **`speculative_accept(target_probs, draft_probs, proposal, rng)`** — accept `proposal` with probability min(1, p_target/p_draft); returns (accepted: bool, residual_sample: int or None) — if rejected, sample from the residual (renormalized p_target − p_draft⁺); a boltzmann illustration of the Lepton/Chen algorithm.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **HF cross-check** — compare `top_p_mask` output against `transformers` logits processors if installed (skip if not).
2. **Repetition penalty** — implement frequency/presence penalties and show how they push off greedy loops.
3. **Beam vs sampling quality** — on a branching toy, show beam=1 (greedy) repeats while top_p escapes.
