# Lab 11: Attention Internals — Softmax, √d_k, MHA, KV-Cache

**Track:** T05 LLM Internals · **Time:** 2h · **XP:** 50
**Module:** `T05-attention`

**You will build:** numerically stable softmax, scaled dot-product attention with additive causal/padding masks, single-matmul multi-head attention that must match a naive per-head loop, and an incremental KV-cache decode step whose output must equal the full-recompute row.

**You will be able to answer:** *"Why exactly √d_k — and why does a KV-cache step give bit-comparable output to full recompute?"*

## Setup

```bash
cd labs/py/11-attention
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest numpy                         # only dependencies
```

## The spec

Masks are **additive**: `0.0` where attention is allowed, `-inf` where blocked, added to scores *before* softmax. Everything is float64 numpy; all equivalence checks are seeded so the printed max-abs-diffs are reproducible.

1. **`softmax_lastdim(x)`** — softmax over the last axis. Must survive logits with huge spread (subtract the row max first); rows sum to 1.
2. **`attention(Q, K, V, mask=None)`** — `softmax(QKᵀ/√d_k + mask)·V`. Leading dims broadcast, so one implementation serves one head `(n, d)`, a head stack `(h, n, d)`, or a batch `(B, h, n, d)`. Shape mismatches (Q/K head dim, K/V token count, non-broadcastable mask) → `ValueError`. Returns weights too when `return_weights=True`.
3. **Masks** — `causal_mask(T)`: `(T, T)` with `0.0` on/below the diagonal, `-inf` above. `padding_mask(lengths, max_len)`: valid-length variant returning `(B, 1, 1, L)` — singleton axes broadcast over query positions and heads. Pad keys get ~0 weight; padded output must equal attention recomputed on the trimmed sequences.
4. **`multi_head(x, Wq, Wk, Wv, Wo, h)`** — ONE matmul per projection for all heads; split via `reshape(n, h, d_head).swapaxes(0,1)` (consecutive column blocks = the naive loop's slices), vectorised attention per head, concat in head order, then `Wo`. Must equal the naive looping reference within **1e-5**, unmasked and causal. Bad shapes / `d_model % h != 0` → `ValueError`.
5. **KV-cache step** — `attention_step(q_new, k_new, v_new, k_cache, v_cache)`: append the new key/value (each cache grows by exactly 1 row), attend the single new query over the grown cache. At several sequence lengths, every incremental output row must match full recompute within **1e-5** — causality is implicit because only past+current keys exist.
6. **Scaling sanity fixtures** — unscaled raw scores at large `d_k` saturate softmax toward one-hot (peak weight grows, entropy collapses); `1/√d_k` keeps the spread; dividing by `d_k` instead over-corrects toward uniform.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference (max-abs-diff numbers print with `-s`): `pytest tests/ -v -s --solution`

## Stretch goals

1. **Online softmax** — implement the FlashAttention-style running max/sum rescale from the curriculum sketch and show it matches your batched softmax to float tolerance on long rows.
2. **GQA heads** — generalise `multi_head` so `h_kv < h`: repeat each KV head across its query group; verify against a per-group loop and count the cache savings in bytes/token.
3. **Fused causal+padding** — build the combined `(B, 1, T, T)` additive mask and prove it equals masking in two separate passes.
4. **Float32 stress** — rerun every equivalence fixture in float32; find which assertion tolerance breaks first and explain why (hint: softmax normalisation vs matmul accumulation).
