import numpy as np
import pytest


def test_ar1_deterministic_halving(A):
    ar = A.ARProcess(1, [0.5], sigma=0.0)
    x = ar.generate(4, x0=[1.0])
    assert np.allclose(x, [0.5, 0.25, 0.125, 0.0625])


def test_ar2_deterministic(A):
    # x_t = 0.5*x_{t-1} + 0.25*x_{t-2}; x0 = 1, x1 = 2
    ar = A.ARProcess(2, [0.5, 0.25], sigma=0.0)
    x = ar.generate(3, x0=[1.0, 2.0])
    # x2 = 0.5*2 + 0.25*1 = 1.25; x3 = 0.5*1.25 + 0.25*2 = 1.125; x4 = 0.5*1.125+0.25*1.25
    assert np.allclose(x, [1.25, 1.125, 0.5625 + 0.3125])


def test_ar_noise_seeded_deterministic(A):
    a1 = A.ARProcess(1, [0.3], sigma=0.1, seed=42).generate(10, x0=[1.0])
    a2 = A.ARProcess(1, [0.3], sigma=0.1, seed=42).generate(10, x0=[1.0])
    assert np.allclose(a1, a2)


def test_ar_noise_changes_output(A):
    a1 = A.ARProcess(1, [0.3], sigma=0.5, seed=1).generate(10, x0=[1.0])
    a2 = A.ARProcess(1, [0.3], sigma=0.5, seed=2).generate(10, x0=[1.0])
    assert not np.allclose(a1, a2)


CORPUS = "abab abac abad abab abac"


def test_bigram_counts_exact(A):
    m = A.CharNGram(1, corpus="abab")
    m.fit()
    # order=1 => context is 1 char. transitions: a->b, b->a, a->b
    assert m.dist("a") == {"b": 1.0}
    assert m.dist("b") == {"a": 1.0}


def test_temperature_zero_is_argmax(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    assert m.next_token("ab", temperature=0.0) == "a"


def test_temperature_sampling_seeded_deterministic(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    r1 = np.random.default_rng(7)
    r2 = np.random.default_rng(7)
    s1 = m.generate("ab", 12, temperature=1.0, rng=r1)
    s2 = m.generate("ab", 12, temperature=1.0, rng=r2)
    assert s1 == s2
    assert len(s1) == 2 + 12


def test_nll_hand_computed(A):
    m = A.CharNGram(1, corpus="ab")
    m.fit()
    # corpus "ab": one transition a->b with prob 1. avg NLL = -ln(1) = 0
    val = A.teacher_forced_nll(m, "ab")
    assert val == pytest.approx(0.0, abs=1e-9)


def test_nll_smoothing_on_unseen(A):
    m = A.CharNGram(1, corpus="ab")
    m.fit()
    # corpus "ac": context a never followed by c in training => prob floor eps
    val = A.teacher_forced_nll(m, "ac")
    assert val == pytest.approx(-np.log(1e-10), abs=1e-6)


def test_nll_prefers_own_corpus(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    own = A.teacher_forced_nll(m, CORPUS)
    other = A.teacher_forced_nll(m, "zzzz zzzz zzzz")
    assert own < other


def test_exposure_bias_divergence_grows_with_noise(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    d0 = A.free_run_divergence(m, CORPUS, 30, noise_scale=0.0,
                               rng=np.random.default_rng(3))
    d3 = A.free_run_divergence(m, CORPUS, 30, noise_scale=3.0,
                                rng=np.random.default_rng(3))
    assert d3 > d0


def test_free_run_deterministic_given_seed(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    d1 = A.free_run_divergence(m, CORPUS, 20, noise_scale=1.0,
                               rng=np.random.default_rng(11))
    d2 = A.free_run_divergence(m, CORPUS, 20, noise_scale=1.0,
                                rng=np.random.default_rng(11))
    assert d1 == d2


def test_generate_length(A):
    m = A.CharNGram(2, corpus=CORPUS)
    m.fit()
    out = m.generate("ab", 5, temperature=0.0)
    assert len(out) == 7
    assert out.startswith("ab")
