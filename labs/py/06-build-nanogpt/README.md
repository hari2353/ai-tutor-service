# Lab 06: Build a nanoGPT-Class Transformer From Scratch

**Track:** T05 LLM Internals · **Time:** 4h · **XP:** 50
**Module:** `T05-build-nanogpt`

**You will build:** a decoder-only transformer — embeddings, manual causal multi-head attention, GELU MLP, pre-LN residual blocks, logits head — small enough to train on CPU in seconds.

**You will be able to answer:** *"Walk me through the attention computation — where does √d_k come from, what does causal masking do mechanically, and why is the parameter count ≈ 12·d²·L?"*

## Setup

```bash
cd labs/py/06-build-nanogpt
pip install torch pytest
```

CPU only. d_model=32, 2 layers, vocab 16 runs the whole suite in seconds.

## The spec

1. **`CausalSelfAttention(d_model, n_heads)`** — manual scaled dot-product attention: Q=W_q·x etc. per head; scores = QKᵀ/√(d_head); causal mask sets upper triangle to −inf; softmax; out = attn·V through W_o. NO `nn.MultiheadAttention`.
2. **`MLP(d_model)`** — Linear→GELU→Linear with 4× expansion.
3. **`Block(d_model, n_heads)`** — pre-LN: `x + attn(ln(x))`, `x + mlp(ln(x))`.
4. **`NanoGPT(vocab_size, d_model, n_layers, n_heads, block_size, seed)`** — token + learned position embeddings, blocks, final LN, logits head. `forward(idx)` → logits `[B, T, V]`.
5. **`param_count(model)`** — total parameters.
6. **`greedy_decode(model, idx, n)`** — append argmax token n times.
7. **`train_steps(model, tokens, steps, lr)`** — AdamW, cross-entropy over next-token prediction; returns loss list.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Weight tying** — tie the unembedding to the token embedding; how much does param_count drop?
2. **KV cache** — cache K/V per step in greedy_decode and measure the speedup.
3. **Scale up** — d=64, L=4, train 200 steps on a longer repeating corpus; watch loss curve shape.
