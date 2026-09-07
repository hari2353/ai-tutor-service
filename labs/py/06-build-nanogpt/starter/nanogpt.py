"""A nanoGPT-class decoder-only transformer, small enough for CPU tests."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        """Manual MHA: per-head Q/K/V projections, scaled dot-product,
        causal mask on the upper triangle, output projection."""

    def forward(self, x):
        """x: [B, T, d] -> [B, T, d]. Attention over positions <= t."""


class MLP(nn.Module):
    def __init__(self, d_model):
        """Linear -> GELU -> Linear with 4x expansion."""

    def forward(self, x):
        raise NotImplementedError


class Block(nn.Module):
    def __init__(self, d_model, n_heads):
        """Pre-LN residual: x + attn(ln(x)); then x + mlp(ln(x))."""

    def forward(self, x):
        raise NotImplementedError


class NanoGPT(nn.Module):
    def __init__(self, vocab_size, d_model, n_layers, n_heads, block_size, seed=0):
        """Token + learned position embeddings, blocks, final LN, logits head."""

    def forward(self, idx):
        """idx: [B, T] int64 -> logits [B, T, vocab_size]."""

    def greedy_decode(self, idx, n):
        """Append the argmax token n times. Returns the full sequence [B, T+n]."""


def param_count(model):
    """Total number of trainable parameters (an int)."""


def train_steps(model, tokens, steps, lr=1e-3):
    """AdamW + next-token cross-entropy. tokens: 1-D LongTensor.
    Windows of length block_size -> next-token targets. Returns list of losses."""
