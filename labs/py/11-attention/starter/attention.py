"""Lab 11 — attention internals. Fill in every TODO. Tests define done.

Rules:
  * Pure numpy, float64. No torch, no scipy.
  * Masks are ADDITIVE: 0.0 where attention is allowed, -inf where blocked.
  * softmax_lastdim must be numerically stable — subtract the row max first.
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------- validation
def _as_float(x, what: str) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64)
    if arr.size == 0:
        raise ValueError(f"{what} must not be empty")
    return arr


# ---------------------------------------------------------------- softmax
def softmax_lastdim(x) -> np.ndarray:
    """Numerically stable softmax over the LAST axis.

    TODO(step 1): subtract max(axis=-1, keepdims=True), exponentiate,
    normalise by the sum. Why the shift? exp overflow otherwise.
    """
    # TODO(step 1)
    raise NotImplementedError


# ---------------------------------------------------------------- masks
def causal_mask(T: int) -> np.ndarray:
    """Additive (T, T) mask: 0.0 on/below the diagonal, -inf strictly above.

    TODO(step 2): np.triu_indices(T, k=1) marks everything a query at i
    must NOT see (keys j > i).
    """
    # TODO(step 2)
    raise NotImplementedError


def padding_mask(lengths, max_len: int) -> np.ndarray:
    """Valid-length padding mask that broadcasts across heads.

    lengths: int or per-sequence array of valid prefix lengths;
    returns a (B, 1, 1, L) additive mask — 0.0 for key positions
    j < lengths[b], -inf for pad positions j >= lengths[b].

    TODO(step 3): singleton axes broadcast over query positions and heads.
    Validate 0 <= lengths[b] <= max_len -> ValueError otherwise.
    """
    # TODO(step 3)
    raise NotImplementedError


# ---------------------------------------------------------------- core attention
def attention(Q, K, V, mask=None, return_weights: bool = False):
    """Scaled dot-product attention: softmax(QK^T / sqrt(d_k) + mask) @ V.

    Q: (..., n_q, d_k), K: (..., n_k, d_k), V: (..., n_k, d_v); leading dims
    broadcast so one implementation serves single head / head stack / batch.

    TODO(step 4a): validate shapes (Q/K head dim equal, K/V token count equal,
    >= 2-D each) and raise ValueError otherwise.
    TODO(step 4b): scores = Q @ swapaxes(K, -1, -2) / sqrt(d_k); add the
    additive mask (accept bool masks as 0.0 / -inf; non-broadcastable ->
    ValueError). Softmax the last axis with step 1.
    TODO(step 4c): out = weights @ V; return (out, weights) if return_weights
    else out.
    """
    # TODO(step 4)
    raise NotImplementedError


# ---------------------------------------------------------------- multi-head
def multi_head(x, Wq, Wk, Wv, Wo, h: int, mask=None,
               return_weights: bool = False):
    """Multi-head self-attention with fused single-matmul projections.

    x: (n, d_model); Wq/Wk/Wv/Wo: (d_model, d_model); h divides d_model;
    mask: optional additive mask broadcastable to (h, n, n), e.g. causal.

    TODO(step 5a): validate x is 2-D, h positive, d_model % h == 0, every
    weight exactly (d_model, d_model) — ValueError otherwise.
    TODO(step 5b): ONE matmul per projection for all heads:
        Q = x @ Wq  (n, d_model), same for K, V.
    TODO(step 5c): split into h heads WITHOUT slicing columns one at a time:
        reshape(n, h, d_head).swapaxes(0, 1) -> (h, n, d_head).
        Row-major reshape = consecutive column blocks, which matches the naive
        loop's slice [i*d_head:(i+1)*d_head] exactly.
    TODO(step 5d): run step-4 attention across the head axis (passing the
        mask through), concat heads back with swapaxes + reshape(n, d_model)
        IN HEAD ORDER, then @ Wo.
    """
    # TODO(step 5)
    raise NotImplementedError


# ---------------------------------------------------------------- kv-cache step
def attention_step(q_new, k_new, v_new, k_cache=None, v_cache=None):
    """Incremental decode step for ONE new token (the KV-cache payoff).

    q_new/k_new/v_new: 1-D vectors; caches (t, ·) or BOTH None to start.

    TODO(step 6a): validate caches given together, 2-D, same t — else
    ValueError.
    TODO(step 6b): append new k/v so each cache grows by EXACTLY one row.
    TODO(step 6c): attend the single new query over the full grown cache with
    step-4 attention (no mask needed — causality is implicit: only past+current
    keys exist). Return (out_row, new_k_cache, new_v_cache).
    """
    # TODO(step 6)
    raise NotImplementedError
