"""Autoregression from scratch: AR processes, n-gram LMs, teacher forcing, exposure bias."""
import numpy as np


class ARProcess:
    def __init__(self, k, phi, sigma=0.0, seed=0):
        """AR(k): x_t = sum(phi_i * x_{t-i}) + N(0, sigma)."""

    def generate(self, n, x0=None):
        """Return array of n values. x0: list-like of k initial values (padded with phi-weighted 1.0 if None)."""
        raise NotImplementedError


class CharNGram:
    def __init__(self, order=2, corpus=""):
        """Character n-gram LM. order = context length in chars (1=bigram over chars)."""

    def fit(self):
        """Count transitions from sliding windows over the corpus."""

    def next_token(self, prefix, temperature=0.0, rng=None, noise_scale=0.0):
        """Return the next char given a prefix of >= order chars.
        temperature 0 -> argmax; T>0 -> sample p^(1/T) over observed successors.
        noise_scale>0 -> multiply counts by exp(noise*std_normal) per successor, renormalize.
        Unknown prefix -> fall back to the last <order chars that are known, else most frequent char."""

    def generate(self, prefix, n, temperature=0.0, rng=None, noise_scale=0.0):
        """Free-running generation: feed own outputs back, return prefix + n more chars."""

    def dist(self, context):
        """Return dict {char: prob} for a context (empirical, unsmoothed)."""


def teacher_forced_nll(model, corpus):
    """Average negative log-likelihood of every position after the first `order` chars.
    Use model's empirical transition probability with eps=1e-10 floor. Natural log."""


def free_run_divergence(model, corpus, n, noise_scale=0.0, rng=None):
    """Free-run generate n chars from corpus[:order]; compare each position against
    the teacher-forced (true corpus) continuation corpus[order:order+n].
    Return the mismatch fraction over the n positions (fewer if corpus shorter)."""
