"""A nanoGPT-class decoder-only transformer, small enough for CPU tests."""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        assert d_model % n_heads == 0
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_head = d_model // n_heads
        self.qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x):
        B, T, d = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        # [B, T, d] -> [B, heads, T, d_head]
        q = q.view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.d_head).transpose(1, 2)
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_head)
        mask = torch.triu(torch.ones(T, T, dtype=torch.bool, device=x.device), 1)
        scores = scores.masked_fill(mask, float("-inf"))
        attn = F.softmax(scores, dim=-1)
        out = (attn @ v).transpose(1, 2).contiguous().view(B, T, d)
        return self.proj(out)


class MLP(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.fc = nn.Linear(d_model, 4 * d_model)
        self.proj = nn.Linear(4 * d_model, d_model)

    def forward(self, x):
        return self.proj(F.gelu(self.fc(x)))


class Block(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = CausalSelfAttention(d_model, n_heads)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = MLP(d_model)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class NanoGPT(nn.Module):
    def __init__(self, vocab_size, d_model, n_layers, n_heads, block_size, seed=0):
        super().__init__()
        torch.manual_seed(seed)
        self.block_size = block_size
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(block_size, d_model)
        self.blocks = nn.ModuleList(
            [Block(d_model, n_heads) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, idx):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.tok_emb(idx) + self.pos_emb(pos)
        for blk in self.blocks:
            x = blk(x)
        return self.head(self.ln_f(x))

    def greedy_decode(self, idx, n):
        out = idx
        for _ in range(n):
            logits = self.forward(out[:, -self.block_size:])
            nxt = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            out = torch.cat([out, nxt], dim=1)
        return out


def param_count(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def train_steps(model, tokens, steps, lr=1e-3):
    bs = model.block_size
    losses = []
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    for _ in range(steps):
        i = torch.randint(0, max(len(tokens) - bs - 1, 1), (1,)).item()
        x = tokens[i:i + bs].unsqueeze(0)
        y = tokens[i + 1:i + bs + 1].unsqueeze(0)
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
    return losses
