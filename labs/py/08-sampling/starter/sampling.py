"""Decoding strategies: temperature, top-k, top-p, min-p, beam search, speculative accept."""
import math


def softmax(logits, temperature=1.0):
    """Numerically stable softmax; temperature divides logits before exp."""


def top_k_mask(logits, k):
    """Return a copy where all but the k largest entries are -inf (ties: keep first k in order)."""


def top_p_mask(logits, p):
    """Nucleus: keep the smallest set of highest-prob tokens whose cumsum >= p.
    The token that crosses the threshold is INCLUDED."""


def min_p_mask(logits, p):
    """Keep tokens with probability >= p * max_probability. Others -> -inf."""


def sample(logits, temperature=1.0, rng=None):
    """Sample an index from softmax(logits, T). Seeded rng required for determinism."""


def beam_search(step_logits, k=3, length_penalty=0.0):
    """step_logits: list of per-step logit vectors (same vocab each step).
    Expand k beams. Score = sum(logprob) / (length ** length_penalty).
    Returns (best_sequence, best_score) where sequence is token indices."""


def speculative_accept(target_probs, draft_probs, proposal, rng=None):
    """Speculative decoding accept/reject for ONE token.
    Accept proposal with prob min(1, p_target[proposal] / p_draft[proposal]).
    If rejected, sample from the residual (target - min(target,draft)), renormalized.
    Returns (accepted: bool, residual_index or None)."""
