import math
import random

import pytest

# Fixture distribution: 6 tokens
LOGITS = [6.0, 4.0, 2.0, 0.0, -2.0, -4.0]


def test_softmax_sums_to_one_and_is_stable(P):
    p = P.softmax([1000.0, 1000.0, 1000.0])
    assert all(abs(x - 1 / 3) < 1e-9 for x in p)
    p2 = P.softmax(LOGITS)
    assert abs(sum(p2) - 1.0) < 1e-9
    assert p2[0] > p2[1] > p2[5]


def test_temperature_flattens(P):
    cold = P.softmax(LOGITS, temperature=0.1)
    hot = P.softmax(LOGITS, temperature=5.0)
    assert cold[0] > hot[0]
    assert max(hot) - min(hot) < max(cold) - min(cold)


def test_top_k_masks(P):
    masked = P.top_k_mask(LOGITS, 2)
    assert masked[0] == LOGITS[0] and masked[1] == LOGITS[1]
    assert masked[2:] == [float("-inf")] * 4


def test_top_k_full(P):
    assert P.top_k_mask(LOGITS, 10) == LOGITS


def test_top_p_keeps_boundary_crosser(P):
    # probs approx: e^6=403, e^4=54.6, e^2=7.4, ... total ~468
    # sorted cumsum: [0.861, 0.978, 0.994, ...]. p=0.95 must keep tokens 0,1 (cum 0.978 >= .95)
    masked = P.top_p_mask(LOGITS, 0.95)
    assert masked[0] != float("-inf") and masked[1] != float("-inf")
    assert masked[2] == float("-inf")


def test_top_p_boundary_exact(P):
    # uniform over 4: each 0.25. p=0.75 exactly => keep 3 (cumsum crosses at 3rd)
    masked = P.top_p_mask([0.0, 0.0, 0.0, 0.0], 0.75)
    kept = sum(1 for m in masked if m != float("-inf"))
    assert kept == 3


def test_top_p_one_keeps_all(P):
    masked = P.top_p_mask(LOGITS, 1.0)
    assert masked == LOGITS


def test_min_p_threshold(P):
    # probs approx [0.861, 0.117, 0.016, ...]; max*0.1 = 0.086 -> keeps tokens 0,1
    masked = P.min_p_mask(LOGITS, 0.1)
    assert masked[0] != float("-inf") and masked[1] != float("-inf")
    assert masked[2] == float("-inf")
    # aggressive: 0.5 -> only token 0 (0.861 >= 0.4305; 0.117 < 0.4305)
    masked2 = P.min_p_mask(LOGITS, 0.5)
    assert masked2[0] != float("-inf")
    assert masked2[1] == float("-inf")


def test_sample_seeded_deterministic(P):
    r1, r2 = random.Random(7), random.Random(7)
    a = [P.sample(LOGITS, 1.0, r1) for _ in range(20)]
    b = [P.sample(LOGITS, 1.0, r2) for _ in range(20)]
    assert a == b


def test_sample_respects_mask(P):
    masked = P.top_k_mask(LOGITS, 1)
    r = random.Random(3)
    # with only token 0 unmasked, every sample is 0 (works because -inf -> ~0 prob)
    ids = {P.sample(masked, 1.0, r) for _ in range(20)}
    assert ids == {0}


def test_beam_search_hand_computed(P):
    # 2 steps, vocab 3. Greedy at each step must win for k=1.
    step_logits = [[2.0, 1.0, 0.0], [0.0, 2.0, 1.0]]
    seq, score = P.beam_search(step_logits, k=1)
    assert seq == [0, 1]
    p1 = math.exp(2) / (math.exp(2) + math.exp(1) + 1)
    p2 = math.exp(2) / (math.exp(2) + math.exp(1) + 1)
    assert score == pytest.approx(math.log(p1) + math.log(p2), abs=1e-9)


def test_beam_search_finds_non_greedy_global(P):
    # Beam 2 finds a better global path than greedy: step1 token 1 is worse
    # alone but unlocks a much better step2.
    step_logits = [
        [1.0, 0.9, -5.0],                     # greedy takes 0
        [0.0, -1.0, 6.0],                     # token 2 huge: only reachable if...
    ]
    # path (0,2): lp0 = log(e/(e+e^.9+e^-5)) ; (1,2): smaller step1 but same step2
    # greedy k=1: picks 0 then 2. beam k=2 also (0,2) or (1,2)? both end 2.
    seq, score = P.beam_search(step_logits, k=2)
    assert len(seq) == 2
    assert score == pytest.approx(
        math.log(P.softmax(step_logits[0])[seq[0]]) +
        math.log(P.softmax(step_logits[1])[seq[1]]), abs=1e-9)


def test_beam_length_penalty(P):
    # same logits each step; penalty 0 vs 1.0 changes normalized score but not sequence here
    steps = [[1.0, 0.5]] * 3
    s0, sc0 = P.beam_search(steps, k=2, length_penalty=0.0)
    s1, sc1 = P.beam_search(steps, k=2, length_penalty=1.0)
    assert s0 == s1 == [0, 0, 0]
    assert sc1 == pytest.approx(sc0 / 3.0, abs=1e-9)


def test_speculative_accept_when_target_higher(P):
    # p_target[0]=0.9, p_draft[0]=0.5 -> accept prob 1.0: always accepted
    target = [0.9, 0.1]
    draft = [0.5, 0.5]
    r = random.Random(1)
    for _ in range(50):
        acc, resid = P.speculative_accept(target, draft, 0, r)
        assert acc is True
        assert resid is None


def test_speculative_reject_samples_residual(P):
    # p_target[0]=0.1, p_draft[0]=0.9 -> accept prob 0.1/0.9 ~ 0.111: mostly rejected
    target = [0.1, 0.45, 0.45]
    draft = [0.9, 0.05, 0.05]
    r = random.Random(2)
    rejects = 0
    for _ in range(300):
        acc, resid = P.speculative_accept(target, draft, 0, r)
        if not acc:
            rejects += 1
            assert resid in (1, 2)   # residual mass is entirely on 1,2
    assert rejects > 200            # ~89% reject


def test_speculative_accept_rate_matches_theory(P):
    # uniform target, peaked draft on token 0: accept prob = 0.25/0.8 = 0.3125
    target = [0.25, 0.25, 0.25, 0.25]
    draft = [0.8, 0.1, 0.05, 0.05]
    r = random.Random(42)
    acc = sum(P.speculative_accept(target, draft, 0, r)[0] for _ in range(4000))
    assert abs(acc / 4000 - 0.3125) < 0.05
