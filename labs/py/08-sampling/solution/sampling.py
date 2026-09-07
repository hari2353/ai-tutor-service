"""Decoding strategies: temperature, top-k, top-p, min-p, beam search, speculative accept."""
import math

NEG_INF = float("-inf")


def softmax(logits, temperature=1.0):
    t = max(temperature, 1e-12)
    scaled = [l / t for l in logits]
    m = max(scaled)
    exps = [math.exp(x - m) for x in scaled]
    s = sum(exps)
    return [e / s for e in exps]


def _mask_from_indices(logits, keep_idx):
    keep = set(keep_idx)
    return [l if i in keep else NEG_INF for i, l in enumerate(logits)]


def top_k_mask(logits, k):
    order = sorted(range(len(logits)), key=lambda i: -logits[i])
    keep = order[:max(0, int(k))]
    return _mask_from_indices(logits, keep)


def top_p_mask(logits, p):
    probs = softmax(logits)
    order = sorted(range(len(probs)), key=lambda i: -probs[i])
    keep, cum = [], 0.0
    for i in order:
        keep.append(i)
        cum += probs[i]
        if cum >= p:
            break
    return _mask_from_indices(logits, keep)


def min_p_mask(logits, p):
    probs = softmax(logits)
    pmax = max(probs)
    keep = [i for i, pr in enumerate(probs) if pr >= p * pmax]
    return _mask_from_indices(logits, keep)


def sample(logits, temperature=1.0, rng=None):
    probs = softmax(logits, temperature)
    x = rng.random() if rng is not None else 0.5
    cum = 0.0
    for i, pr in enumerate(probs):
        cum += pr
        if x < cum:
            return i
    return len(probs) - 1


def beam_search(step_logits, k=3, length_penalty=0.0):
    beams = [([], 0.0)]          # (sequence, sum_logprob)
    for logits in step_logits:
        probs = softmax(logits)
        # rank tokens once; each beam extends with top-k tokens
        order = sorted(range(len(probs)), key=lambda i: -probs[i])[:k]
        new = []
        for seq, score in beams:
            for t in order:
                lp = math.log(max(probs[t], 1e-12))
                new.append((seq + [t], score + lp))
        if not new:
            break
        new.sort(key=lambda b: -(b[1] / max(len(b[0]), 1) ** length_penalty))
        beams = new[:k]
    best = max(beams, key=lambda b: b[1] / max(len(b[0]), 1) ** length_penalty)
    return best[0], best[1] / max(len(best[0]), 1) ** length_penalty


def speculative_accept(target_probs, draft_probs, proposal, rng=None):
    pt = target_probs[proposal]
    pd = max(draft_probs[proposal], 1e-12)
    accept_prob = min(1.0, pt / pd)
    x = rng.random() if rng is not None else 0.5
    if x < accept_prob:
        return True, None
    # residual: p_target - min(p_target, p_draft), elementwise, floor at 0
    residual = [max(t - min(t, d), 0.0) for t, d in zip(target_probs, draft_probs)]
    s = sum(residual)
    if s <= 0:
        return False, 0
    residual = [r / s for r in residual]
    y = rng.random() if rng is not None else 0.5
    cum = 0.0
    for i, r in enumerate(residual):
        cum += r
        if y < cum:
            return False, i
    return False, len(residual) - 1
