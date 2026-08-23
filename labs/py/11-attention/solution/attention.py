"""Lab 11 — attention internals: stable softmax, scaled dot-product attention,
masks, single-matmul multi-head attention, and an incremental KV-cache decode step.

Everything is plain numpy, float64, seeded-and-deterministic in the tests.
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

    Stability trick: subtract the row max before exponentiating. exp(z - m)
    has the same softmax as exp(z) but can never overflow, because every
    exponent is <= 0.
    """
    x = _as_float(x, "logits")
    shifted = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(shifted)
    return e / e.sum(axis=-1, keepdims=True)


# ---------------------------------------------------------------- masks
def causal_mask(T: int) -> np.ndarray:
    """Additive (T, T) mask: 0.0 on/below the diagonal, -inf strictly above.

    Added to the score matrix BEFORE softmax, so position i cannot attend to
    any position j > i (exp(-inf) == 0 weight). Shape broadcasts cleanly onto
    (..., T, T) score tensors, including stacked-head batches (h, T, T).
    """
    if int(T) != T or T < 1:
        raise ValueError(f"T must be a positive integer, got {T!r}")
    T = int(T)
    m = np.zeros((T, T), dtype=np.float64)
    m[np.triu_indices(T, k=1)] = -np.inf
    return m


def padding_mask(lengths, max_len: int) -> np.ndarray:
    """Valid-length padding mask that broadcasts across heads.

    Parameters
    ----------
    lengths : int or array-like of ints
        Valid (non-pad) prefix length per sequence.
    max_len : int
        Padded key dimension L.

    Returns
    -------
    (B, 1, 1, L) additive mask: 0.0 for key positions j < lengths[b],
    -inf for pad positions j >= lengths[b]. The singleton axes broadcast over
    query positions and heads, so it adds cleanly onto scores of shape
    (B, h, Tq, L) -- or any (..., L) tail, including a single (T, L) pair.

    Combine with the causal mask additively:
        mask = causal_mask(T) + padding_mask(lengths, T)[b]   # per sequence
    """
    if int(max_len) != max_len or max_len < 1:
        raise ValueError(f"max_len must be a positive integer, got {max_len!r}")
    max_len = int(max_len)
    lens = np.atleast_1d(np.asarray(lengths, dtype=np.int64))
    if np.any(lens < 0) or np.any(lens > max_len):
        raise ValueError(f"lengths must be in [0, {max_len}], got {lengths!r}")
    valid = np.arange(max_len)[None, :] < lens[:, None]          # (B, L) bool
    mask = np.where(valid, 0.0, -np.inf)
    return mask.reshape(len(lens), 1, 1, max_len)


# ---------------------------------------------------------------- core attention
def attention(Q, K, V, mask=None, return_weights: bool = False):
    """Scaled dot-product attention: softmax(QK^T / sqrt(d_k) + mask) @ V.

    Q: (..., n_q, d_k), K: (..., n_k, d_k), V: (..., n_k, d_v). Leading dims
    broadcast, so the same function serves a single head (n, d), a stack of
    heads (h, n, d), or a batch of them (B, h, n, d).

    mask: additive, broadcastable onto the score matrix (None = attend to all).
    Booleans are accepted and mapped to 0.0 (keep) / -inf (drop).

    Returns (out, weights) when return_weights else out, where
    out: (..., n_q, d_v) and weights: (..., n_q, n_k), rows summing to 1.
    """
    Q = _as_float(Q, "Q")
    K = _as_float(K, "K")
    V = _as_float(V, "V")
    if Q.ndim < 2 or K.ndim < 2 or V.ndim < 2:
        raise ValueError("Q, K, V must be at least 2-D (..., tokens, features)")
    d_k = Q.shape[-1]
    if K.shape[-1] != d_k:
        raise ValueError(
            f"Q and K must share the head dim, got d_q={d_k} vs d_k={K.shape[-1]}"
        )
    if V.shape[-2] != K.shape[-2]:
        raise ValueError(
            f"K and V must share the token count, got n_k={K.shape[-2]} "
            f"vs n_v={V.shape[-2]}"
        )

    scores = (Q @ np.swapaxes(K, -1, -2)) / np.sqrt(d_k)         # (..., n_q, n_k)
    if mask is not None:
        m = np.asarray(mask)
        if m.dtype == bool:
            m = np.where(m, 0.0, -np.inf)
        try:
            scores = scores + m.astype(np.float64)
        except ValueError as exc:
            raise ValueError(
                f"mask shape {m.shape} is not broadcastable to "
                f"score shape {scores.shape}"
            ) from exc

    weights = softmax_lastdim(scores)                            # (..., n_q, n_k)
    out = weights @ V                                            # (..., n_q, d_v)
    return (out, weights) if return_weights else out


# ---------------------------------------------------------------- multi-head
def multi_head(x, Wq, Wk, Wv, Wo, h: int, mask=None,
               return_weights: bool = False):
    """Multi-head self-attention with fused single-matmul projections.

    x: (n, d_model); Wq/Wk/Wv/Wo: (d_model, d_model); h divides d_model.
    mask: optional additive mask broadcastable to (h, n, n), e.g. causal_mask(n).

    One matmul per projection produces ALL heads' Q/K/V at once ((n, d_model));
    the heads are split with a reshape+swapaxes -- reshape(n, h, d_head) takes
    CONSECUTIVE column blocks per head, matching the naive per-head slice
    [i*d_head:(i+1)*d_head] exactly. Attention runs vectorised across heads,
    heads are concatenated back in order, and Wo mixes them.
    """
    x = _as_float(x, "x")
    if x.ndim != 2:
        raise ValueError(f"x must be 2-D (n, d_model), got {x.ndim}-D")
    n, d_model = x.shape
    if int(h) != h or h < 1:
        raise ValueError(f"h must be a positive integer, got {h!r}")
    h = int(h)
    if d_model % h != 0:
        raise ValueError(f"d_model={d_model} must be divisible by h={h}")
    d_head = d_model // h
    for name, W in (("Wq", Wq), ("Wk", Wk), ("Wv", Wv), ("Wo", Wo)):
        W = _as_float(W, name)
        if W.shape != (d_model, d_model):
            raise ValueError(
                f"{name} must have shape ({d_model}, {d_model}), got {W.shape}"
            )
    Wq, Wk, Wv, Wo = (np.asarray(w, dtype=np.float64) for w in (Wq, Wk, Wv, Wo))

    Q = x @ Wq                                                   # single matmul
    K = x @ Wk                                                   # for ALL heads
    V = x @ Wv
    Qh = Q.reshape(n, h, d_head).swapaxes(0, 1)                  # (h, n, d_head)
    Kh = K.reshape(n, h, d_head).swapaxes(0, 1)
    Vh = V.reshape(n, h, d_head).swapaxes(0, 1)

    out, weights = attention(Qh, Kh, Vh, mask=mask, return_weights=True)
    concat = out.swapaxes(0, 1).reshape(n, d_model)              # heads in order
    y = concat @ Wo
    return (y, weights) if return_weights else y


# ---------------------------------------------------------------- kv-cache step
def attention_step(q_new, k_new, v_new, k_cache=None, v_cache=None):
    """Incremental decode step for ONE new token (the KV-cache payoff).

    q_new, k_new, v_new: 1-D feature vectors for the incoming token.
    k_cache, v_cache: (t, ·) past key/value matrices, or BOTH None to start.

    Appends the new key/value to the caches (growing each by exactly 1 row),
    attends the new query over ALL cached keys plus itself -- causality comes
    for free because only past-and-current keys exist -- and returns

        (out_row (d_v,), new_k_cache (t+1, d_k), new_v_cache (t+1, d_v))

    Identical math to recomputing full attention and reading the last row,
    without ever redoing work for earlier tokens.
    """
    q = np.asarray(q_new, dtype=np.float64).reshape(1, -1)
    kn = np.asarray(k_new, dtype=np.float64).reshape(1, -1)
    vn = np.asarray(v_new, dtype=np.float64).reshape(1, -1)
    if (k_cache is None) != (v_cache is None):
        raise ValueError("k_cache and v_cache must be given together")
    if k_cache is None:
        k_full, v_full = kn.copy(), vn.copy()
    else:
        kc = np.asarray(k_cache, dtype=np.float64)
        vc = np.asarray(v_cache, dtype=np.float64)
        if kc.ndim != 2 or vc.ndim != 2:
            raise ValueError("caches must be 2-D (t, features)")
        if kc.shape[0] != vc.shape[0]:
            raise ValueError(
                f"k/v caches out of sync: t_k={kc.shape[0]} vs t_v={vc.shape[0]}"
            )
        k_full = np.vstack([kc, kn])
        v_full = np.vstack([vc, vn])
    out = attention(q, k_full, v_full)
    return out[0], k_full, v_full
