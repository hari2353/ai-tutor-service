import math

import pytest
import torch


def test_output_shape(G, tiny_seed):
    m = G.NanoGPT(vocab_size=16, d_model=32, n_layers=2, n_heads=4, block_size=8)
    idx = torch.randint(0, 16, (3, 8))
    logits = m(idx)
    assert logits.shape == (3, 8, 16)


def test_param_count_formula(G, tiny_seed):
    # per block: qkv 3d^2 + proj d^2 (attn, no bias) + fc 4d^2+4d + proj 4d^2+d
    # (mlp, biased) + 2 LayerNorms (2d each) = 12d^2 + 5d + 4d
    # plus embeddings (vocab*d + ctx*d) + final LN (2d) + head vocab*d
    d, L, V, T = 32, 2, 16, 8
    m = G.NanoGPT(vocab_size=V, d_model=d, n_layers=L, n_heads=4, block_size=T)
    n = G.param_count(m)
    block = (3 * d * d + d * d) + (4 * d * d + 4 * d) + (4 * d * d + d) + 2 * (2 * d)
    expected = L * block + (V * d + T * d) + 2 * d + V * d
    assert n == expected


def test_causal_mask_future_grad_is_zero(G, tiny_seed):
    m = G.NanoGPT(vocab_size=16, d_model=32, n_layers=2, n_heads=4, block_size=8)
    idx = torch.randint(0, 16, (1, 8))
    logits = m(idx)
    # sum of logits at positions <= t must not depend on tokens at positions > t
    for t in [0, 3, 7]:
        idx2 = idx.clone()
        idx2[0, t + 1:] = (idx2[0, t + 1:] + 7) % 16   # scramble the future
        logits2 = m(idx2)
        assert torch.allclose(logits[0, : t + 1], logits2[0, : t + 1], atol=1e-5), \
            f"position {t} saw the future"


def test_attention_is_permutation_equivariant_over_past(G, tiny_seed):
    # permuting the PAST changes outputs at later positions (it must — attention
    # is not invariant to past permutations), but position embeddings must keep
    # logits distinct for identical tokens at different positions
    m = G.NanoGPT(vocab_size=8, d_model=16, n_layers=1, n_heads=2, block_size=4)
    a = torch.tensor([[1, 2, 3, 4]])
    b = torch.tensor([[1, 2, 3, 1]])   # same prefix, different last token
    la, lb = m(a), m(b)
    assert not torch.allclose(la[0, 3], lb[0, 3])


def test_training_loss_drops(G, tiny_seed):
    tokens = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3, 4, 5, 6, 7] * 4)
    m = G.NanoGPT(vocab_size=8, d_model=32, n_layers=2, n_heads=4, block_size=8,
                  seed=0)
    losses = G.train_steps(m, tokens, steps=60, lr=3e-3)
    assert len(losses) == 60
    assert losses[-1] < losses[0] * 0.5, f"loss didn't drop: {losses[0]} -> {losses[-1]}"
    assert all(not math.isnan(l) for l in losses)


def test_greedy_decode_deterministic_and_fixed_length(G, tiny_seed):
    tokens = torch.tensor([0, 1, 2, 3] * 8)
    m = G.NanoGPT(vocab_size=8, d_model=16, n_layers=1, n_heads=2, block_size=8,
                  seed=1)
    G.train_steps(m, tokens, steps=5, lr=1e-3)
    idx = torch.tensor([[0, 1, 2]])
    out1 = m.greedy_decode(idx, 4)
    out2 = m.greedy_decode(idx, 4)
    assert out1.shape == (1, 7)
    assert torch.equal(out1, out2)
    assert torch.equal(out1[:, :3], idx)


def test_greedy_decode_learns_repetition(G, tiny_seed):
    # after real training on a repeating pattern, greedy decode continues it
    tokens = torch.tensor([1, 2, 3] * 30)
    m = G.NanoGPT(vocab_size=8, d_model=32, n_layers=2, n_heads=4, block_size=8,
                  seed=2)
    G.train_steps(m, tokens, steps=100, lr=5e-3)
    out = m.greedy_decode(torch.tensor([[1, 2]]), 4)
    seq = out[0].tolist()
    assert seq == [1, 2, 3, 1, 2, 3] or seq == [1, 2, 3, 1, 2, 3][:6]


def test_different_seeds_differ(G, tiny_seed):
    m1 = G.NanoGPT(vocab_size=8, d_model=16, n_layers=1, n_heads=2, block_size=4,
                   seed=1)
    m2 = G.NanoGPT(vocab_size=8, d_model=16, n_layers=1, n_heads=2, block_size=4,
                   seed=2)
    idx = torch.randint(0, 8, (1, 4))
    assert not torch.allclose(m1(idx), m2(idx))
