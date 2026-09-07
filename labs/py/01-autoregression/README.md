# Lab 01: Autoregression — Next-Token Prediction, Teacher Forcing, Exposure Bias

**Track:** T05 LLM Internals · **Time:** 2h · **XP:** 50
**Module:** `T05-autoregression`

**You will build:** an AR(k) process generator and a character n-gram "LM" that exposes the three ideas LLM training inherited from autoregression: next-token prediction, teacher forcing, and exposure bias.

**You will be able to answer:** *"LLM training uses teacher forcing, inference is autoregressive — why does that gap matter, and when does it bite?"*

## Setup

```bash
cd labs/py/01-autoregression
pip install numpy pytest
```

## The spec

1. **`ARProcess(k, phi, sigma=0.0, seed=0)`** — `generate(n, x0)` returns a numpy array with `x_t = Σ phi_i·x_{t-i} + noise`, noise `N(0, sigma)` from a seeded generator. `sigma=0` → pure deterministic.
2. **`CharNGram(order=2, corpus=...)`** — `fit()` builds character transition counts over sliding windows; `next_token(prefix, temperature, rng)` — temperature 0 = argmax; T>0 = sample from `p^(1/T)` renormalized over observed successors only; `generate(prefix, n, temperature, rng)` — free-running: feeds its own outputs back.
3. **`teacher_forced_nll(model, corpus)`** — average negative log-likelihood of every corpus position under the model's empirical transition probabilities with `eps=1e-10` smoothing.
4. **`free_run_divergence(model, corpus, n, noise_scale, rng)`** — free-run generate `n` chars from the corpus's own start; at each step multiply the count-derived distribution by `noise_scale`-scaled multiplicative noise (`counts * exp(noise * standard_normal)` then renormalize); return the fraction of positions where the free-run char differs from the teacher-forced (true corpus) char.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Scheduled sampling** — interpolate between teacher-forced and free-running targets by probability p; when does it help? *(Bengio et al. 2015.)*
2. **Order sweep** — plot NLL of bigram vs trigram on the same corpus: when does higher order overfit?
3. **Beam "decoding"** — keep the top-k prefixes by accumulated log-prob; compare argmax vs beam output on a branching corpus.
