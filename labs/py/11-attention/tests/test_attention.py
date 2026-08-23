"""Lab 11 tests. Everything is seeded and deterministic — no flakes.

Max-abs-diff numbers are printed so both pytest modes show measured evidence
for every equivalence claim (naive-loop MHA, prefix recompute, trimmed
recompute, KV-cache vs full recompute).
"""
import sys

import numpy as np
import pytest


def _A():
    return sys.modules["attention"]             # registered by conftest


def _maxdiff(a, b) -> float:
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


# ------------------------------------------------------------------ softmax
def test_softmax_rows_sum_to_one(A):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(7, 33))
    w = A.softmax_lastdim(x)
    assert w.shape == x.shape
    assert np.all(w >= 0.0)
    assert np.allclose(w.sum(axis=-1), 1.0, atol=1e-12)


def test_softmax_shift_invariance(A):
    """softmax(x + c*1) == softmax(x): subtracting the max must not change
    the result, only the overflow safety."""
    rng = np.random.default_rng(1)
    x = rng.normal(size=(4, 9))
    assert _maxdiff(A.softmax_lastdim(x), A.softmax_lastdim(x + 123.45)) < 1e-12


def test_softmax_extreme_logits_stable(A):
    """Logits with a 20_000 spread: naive exp overflows to inf/NaN."""
    x = np.array([[10_000.0, -10_000.0, 0.0]])
    w = A.softmax_lastdim(x)
    assert np.all(np.isfinite(w))                        # naive exp would give inf/nan
    assert w.sum() == pytest.approx(1.0, abs=1e-12)
    assert w.argmax() == 0
    assert float(w[0, 0]) > 0.9999

    # moderate spread: every entry survives, order preserved
    w2 = A.softmax_lastdim(np.array([[30.0, 20.0, 0.0]]))
    assert np.all(w2 > 0.0)
    assert list(np.argsort(-w2[0])) == [0, 1, 2]


# ------------------------------------------------------------------ attention core
def test_attention_matches_manual_formula(A):
    Q = np.array([[1.0, 2.0], [0.5, -1.0]])
    K = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    V = np.array([[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]])
    scores = Q @ K.T / np.sqrt(2)
    e = np.exp(scores - scores.max(axis=-1, keepdims=True))
    expected = (e / e.sum(axis=-1, keepdims=True)) @ V
    out = A.attention(Q, K, V)
    assert out.shape == (2, 2)
    assert _maxdiff(out, expected) < 1e-12


def test_attention_weights_sum_to_one_per_row(A):
    rng = np.random.default_rng(2)
    Q, K, V = (rng.normal(size=(6, 8)) for _ in range(3))
    out, w = A.attention(Q, K, V, return_weights=True)
    assert w.shape == (6, 6)
    assert np.allclose(w.sum(axis=-1), 1.0, atol=1e-12)
    assert _maxdiff(out, w @ V) == 0.0                   # out IS weights @ V


def test_attention_shape_errors(A):
    Q = np.zeros((4, 8))
    with pytest.raises(ValueError):                      # d_q != d_k
        A.attention(Q, np.zeros((3, 16)), np.zeros((3, 8)))
    with pytest.raises(ValueError):                      # n_k != n_v
        A.attention(Q, np.zeros((5, 8)), np.zeros((6, 8)))
    with pytest.raises(ValueError):                      # mask not broadcastable
        A.attention(Q, np.zeros((5, 8)), np.zeros((5, 8)),
                    mask=np.zeros((3, 3)))


# ------------------------------------------------------------------ causal
def test_causal_mask_structure(A):
    m = A.causal_mask(4)
    assert m.shape == (4, 4)
    upper = np.triu_indices(4, k=1)
    lower = np.tril_indices(4)
    assert np.all(m[upper] == -np.inf)
    assert np.all(m[lower] == 0.0)


def test_causal_weights_upper_triangle_zero(A):
    rng = np.random.default_rng(3)
    Q, K, V = (rng.normal(size=(7, 8)) for _ in range(3))
    _, w = A.attention(Q, K, V, mask=A.causal_mask(7), return_weights=True)
    upper = np.triu_indices(7, k=1)
    assert float(np.max(np.abs(w[upper]))) == 0.0        # exp(-inf) is exactly 0


def test_causal_rows_softmax_over_prefix(A):
    """Row i is a distribution over positions 0..i only — and it sums to 1
    WITHOUT renormalisation help, because softmax of the masked row already
    drops the -inf entries."""
    rng = np.random.default_rng(4)
    Q, K, V = (rng.normal(size=(6, 8)) for _ in range(3))
    _, w = A.attention(Q, K, V, mask=A.causal_mask(6), return_weights=True)
    for i in range(6):
        assert w[i, : i + 1].sum() == pytest.approx(1.0, abs=1e-12)
    assert w[0, 0] == pytest.approx(1.0)                 # token 0 can only see itself


def test_causal_output_equals_prefix_recompute(A):
    """The masked-matrix shortcut must equal honestly recomputing attention
    over each row's visible prefix."""
    rng = np.random.default_rng(5)
    T, d = 8, 8
    Q, K, V = (rng.normal(size=(T, d)) for _ in range(3))
    out = A.attention(Q, K, V, mask=A.causal_mask(T))
    diff = max(_maxdiff(out[i],
                        A.attention(Q[: i + 1], K[: i + 1], V[: i + 1])[-1])
               for i in range(T))
    print(f"[prefix recompute] causal vs per-row full attention "
          f"max-abs-diff = {diff:.3e}")
    assert diff <= 1e-10


# ------------------------------------------------------------------ padding
def test_padding_mask_values_and_broadcast(A):
    m = A.padding_mask([6, 3, 1], max_len=6)
    assert m.shape == (3, 1, 1, 6)
    assert np.all(m[0] == 0.0)                           # fully valid sequence
    assert np.all(m[1, ..., :3] == 0.0)
    assert np.all(m[1, ..., 3:] == -np.inf)
    assert np.all(m[2, ..., 0] == 0.0)
    assert np.all(m[2, ..., 1:] == -np.inf)

    # singleton head/query axes broadcast onto batched stacked-head scores
    scores = np.zeros((3, 4, 6, 6))
    masked = scores + m                                  # no ValueError
    assert masked.shape == (3, 4, 6, 6)
    assert np.all(masked[1, :, :, 3:] == -np.inf)

    single = A.padding_mask(2, max_len=4)                # scalar length form
    assert single.shape == (1, 1, 1, 4)
    assert np.all(single[..., 2:] == -np.inf)


def test_padding_mask_rejects_bad_lengths(A):
    with pytest.raises(ValueError):
        A.padding_mask([-1], max_len=4)
    with pytest.raises(ValueError):
        A.padding_mask([5], max_len=4)


def test_padding_weights_zero_at_pad_positions(A):
    rng = np.random.default_rng(6)
    B, h, T, dh = 3, 4, 6, 8
    lengths = [6, 3, 1]
    Q, K, V = (rng.normal(size=(B, h, T, dh)) for _ in range(3))
    _, w = A.attention(Q, K, V, mask=A.padding_mask(lengths, T),
                       return_weights=True)
    for b, L in enumerate(lengths):
        if L < T:                                        # skip fully-valid seq (empty pad slice)
            pad_w = w[b, :, :, L:]
            assert float(np.max(np.abs(pad_w))) <= 1e-30, \
                f"seq {b}: mass leaked onto pad keys"
        assert np.allclose(w[b].sum(axis=-1), 1.0, atol=1e-12)


def test_padding_output_equals_trimmed_recompute(A):
    """Masking pad keys must be EXACTLY equivalent to never having padded:
    compare against attention over the trimmed K/V per sequence."""
    rng = np.random.default_rng(7)
    B, h, T, dh = 3, 2, 6, 8
    lengths = [6, 4, 2]
    Q, K, V = (rng.normal(size=(B, h, T, dh)) for _ in range(3))
    out = A.attention(Q, K, V, mask=A.padding_mask(lengths, T))
    diff = max(_maxdiff(out[b], A.attention(Q[b], K[b, :, :L], V[b, :, :L]))
               for b, L in enumerate(lengths))
    print(f"[trimmed recompute] padded+mask vs unpadded max-abs-diff "
          f"= {diff:.3e}")
    assert diff <= 1e-10


# ------------------------------------------------------------------ multi-head
def _naive_mha(A, x, Wq, Wk, Wv, Wo, h, mask=None):
    """Curriculum reference: slice contiguous column blocks per head, loop."""
    n, d_model = x.shape
    d_head = d_model // h
    Q, K, V = x @ Wq, x @ Wk, x @ Wv
    out = np.zeros((n, d_model))
    for i in range(h):
        sl = slice(i * d_head, (i + 1) * d_head)
        out[:, sl] = A.attention(Q[:, sl], K[:, sl], V[:, sl], mask=mask)
    return out @ Wo


def _naive_mha_weights(A, x, Wq, Wk, h, mask=None):
    """Same per-head loop, collecting the (n, n) weight matrices."""
    n, d_model = x.shape
    d_head = d_model // h
    Q, K = x @ Wq, x @ Wk
    ws = []
    for i in range(h):
        sl = slice(i * d_head, (i + 1) * d_head)
        _, w = A.attention(Q[:, sl], K[:, sl], np.zeros((n, 1)),
                           mask=mask, return_weights=True)
        ws.append(w)
    return np.stack(ws)


@pytest.fixture(scope="module")
def mha_fixture():
    rng = np.random.default_rng(42)
    n, d_model, h = 11, 24, 4
    x = rng.normal(size=(n, d_model))
    Wq, Wk, Wv, Wo = (rng.normal(scale=0.3, size=(d_model, d_model))
                      for _ in range(4))
    return x, Wq, Wk, Wv, Wo, h


def test_multi_head_matches_naive_loop(A, mha_fixture):
    x, Wq, Wk, Wv, Wo, h = mha_fixture
    got = A.multi_head(x, Wq, Wk, Wv, Wo, h)
    expect = _naive_mha(A, x, Wq, Wk, Wv, Wo, h)
    diff = _maxdiff(got, expect)
    print(f"[MHA fused-vs-loop] max-abs-diff = {diff:.3e}")
    assert got.shape == x.shape
    assert diff <= 1e-5


def test_multi_head_with_causal_matches_naive_loop(A, mha_fixture):
    """The fused path must also agree with the naive loop when masked — and
    its returned per-head weights must match the per-head-loop weights."""
    x, Wq, Wk, Wv, Wo, h = mha_fixture
    n = x.shape[0]
    mask = A.causal_mask(n)

    out_fused, w_fused = A.multi_head(x, Wq, Wk, Wv, Wo, h, mask=mask,
                                      return_weights=True)
    out_loop = _naive_mha(A, x, Wq, Wk, Wv, Wo, h, mask=mask)
    w_loop = _naive_mha_weights(A, x, Wq, Wk, h, mask=mask)
    assert w_fused.shape == (h, n, n)

    d_out = _maxdiff(out_fused, out_loop)
    d_w = _maxdiff(w_fused, w_loop)
    print(f"[MHA causal] out max-abs-diff = {d_out:.3e}, "
          f"weights max-abs-diff = {d_w:.3e}")
    assert d_out <= 1e-5
    assert d_w <= 1e-5

    upper = np.triu_indices(n, k=1)
    assert float(np.max(np.abs(w_fused[:, upper[0], upper[1]]))) == 0.0


def test_multi_head_shape_errors(A):
    rng = np.random.default_rng(8)
    x = rng.normal(size=(5, 32))
    W = rng.normal(size=(32, 32))
    with pytest.raises(ValueError):                      # 32 % 5 != 0
        A.multi_head(x, W, W, W, W, h=5)
    with pytest.raises(ValueError):                      # wrong weight shape
        A.multi_head(x, rng.normal(size=(31, 31)), W, W, W, h=4)
    with pytest.raises(ValueError):                      # Wo wrong too
        A.multi_head(x, W, W, W, rng.normal(size=(16, 16)), h=4)
    with pytest.raises(ValueError):                      # h < 1
        A.multi_head(x, W, W, W, W, h=0)
    with pytest.raises(ValueError):                      # x not 2-D
        A.multi_head(rng.normal(size=(2, 3, 32)), W, W, W, W, h=4)


# ------------------------------------------------------------------ kv cache
@pytest.mark.parametrize("T", [1, 2, 5, 16])
def test_kv_cache_matches_full_recompute(A, T):
    """Decode token-by-token with a growing KV cache; every incremental output
    row must equal the corresponding full-recompute row."""
    rng = np.random.default_rng(100 + T)
    d_k, d_v = 16, 12
    Q = rng.normal(size=(T, d_k))
    K = rng.normal(size=(T, d_k))
    V = rng.normal(size=(T, d_v))

    kc = vc = None                                       # empty cache at t=0
    diffs = []
    for t in range(T):
        out_t, kc, vc = A.attention_step(Q[t], K[t], V[t], kc, vc)
        full_t = A.attention(Q[: t + 1], K[: t + 1], V[: t + 1])
        diffs.append(_maxdiff(out_t, full_t[-1]))        # the NEW token's row
    diff = max(diffs)
    print(f"[kv-cache T={T}] step-vs-full-recompute max-abs-diff = {diff:.3e}")
    assert kc.shape == (T, d_k) and vc.shape == (T, d_v)
    assert diff <= 1e-5


def test_kv_cache_grows_by_one_per_step(A):
    rng = np.random.default_rng(200)
    qkv = [rng.normal(size=8) for _ in range(6)]
    kc = vc = None
    for t in range(len(qkv)):
        _, kc, vc = A.attention_step(qkv[t], qkv[t], qkv[t] + 1.0, kc, vc)
        assert kc.shape == (t + 1, 8)                    # grew by exactly one
        assert vc.shape == (t + 1, 8)
    assert np.array_equal(kc[:-1], np.stack([qkv[t] for t in range(5)]))
    assert np.array_equal(kc[-1], qkv[5])

    with pytest.raises(ValueError):                      # caches given together
        A.attention_step(qkv[0], qkv[0], qkv[0], k_cache=kc)
    with pytest.raises(ValueError):                      # out-of-sync caches
        A.attention_step(qkv[0], qkv[0], qkv[0], kc, vc[:-1])


# ------------------------------------------------------------------ scaling
def test_scaling_prevents_saturation_at_large_dk(A):
    """THE √d_k fixture. Without scaling, raw dot-product variance grows with
    d_k, so softmax saturates toward one-hot (entropy collapses). With 1/√d_k,
    variance stays ~1 and the distribution stays comparably spread."""
    rng = np.random.default_rng(11)
    stats = {}
    for d_k in (8, 256):
        q = rng.normal(size=(1, d_k))
        k = rng.normal(size=(64, d_k))
        s = q @ k.T                                      # raw scores
        w_raw = A.softmax_lastdim(s)
        w_scaled = A.softmax_lastdim(s / np.sqrt(d_k))
        stats[d_k] = (float(w_raw.max()), float(w_scaled.max()))
    peak_raw_small, peak_scaled_small = stats[8]
    peak_raw_big, peak_scaled_big = stats[256]

    print(f"[scaling] unscaled peak weight: d_k=8 -> {peak_raw_small:.4f}, "
          f"d_k=256 -> {peak_raw_big:.4f}")
    print(f"[scaling] scaled peak weight:   d_k=8 -> {peak_scaled_small:.4f}, "
          f"d_k=256 -> {peak_scaled_big:.4f}")
    assert peak_raw_big > peak_raw_small                 # unscaled saturates as d_k grows
    assert peak_scaled_big < peak_raw_big                # √d_k keeps it from peaking

    # entropy version: scaled keeps more spread than unscaled at large d_k
    def entropy(p):
        p = np.clip(p, 1e-300, 1.0)
        return float(-(p * np.log(p)).sum())

    q = rng.normal(size=(1, 256))
    k = rng.normal(size=(64, 256))
    s = q @ k.T
    assert entropy(A.softmax_lastdim(s / np.sqrt(256))) > \
        entropy(A.softmax_lastdim(s))


def test_dividing_by_dk_overshrinks_toward_uniform(A):
    """The curriculum's follow-up trap: dividing by d_k OVER-corrects (variance
    1/d_k), pushing softmax toward uniform and killing sharp preference."""
    rng = np.random.default_rng(12)
    d_k, nk = 128, 128
    q = rng.normal(size=(1, d_k))
    k = rng.normal(size=(nk, d_k))
    s = q @ k.T
    uniform = np.full(nk, 1.0 / nk)

    def l1_from_uniform(w):
        return float(np.abs(w - uniform).sum())

    d_sqrt = l1_from_uniform(A.softmax_lastdim(s / np.sqrt(d_k)))
    d_dk = l1_from_uniform(A.softmax_lastdim(s / d_k))
    print(f"[overcorrection] L1 distance from uniform: /sqrt(d_k)={d_sqrt:.4f}, "
          f"/d_k={d_dk:.4f}")
    assert d_dk < d_sqrt                                 # /d_k is closer to uniform
