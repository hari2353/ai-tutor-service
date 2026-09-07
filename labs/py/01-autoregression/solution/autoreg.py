"""Autoregression from scratch: AR processes, n-gram LMs, teacher forcing, exposure bias."""
import numpy as np


class ARProcess:
    def __init__(self, k, phi, sigma=0.0, seed=0):
        self.k = k
        self.phi = np.asarray(phi, dtype=float)
        assert len(self.phi) == k
        self.sigma = sigma
        self.rng = np.random.default_rng(seed)

    def generate(self, n, x0=None):
        if x0 is None:
            x0 = [1.0] * self.k
        x = list(x0[-self.k:])
        if self.sigma == 0.0:
            noise = np.zeros(n)
        else:
            noise = self.rng.normal(0.0, self.sigma, size=n)
        for t in range(n):
            window = x[-self.k:]
            xt = float(sum(self.phi[i] * window[-(i + 1)] for i in range(self.k))) + noise[t]
            x.append(xt)
        return np.array(x[self.k:])


class CharNGram:
    def __init__(self, order=2, corpus=""):
        self.order = order
        self.corpus = corpus
        self.counts = {}
        self._fitted = False

    def fit(self):
        self.counts = {}
        for i in range(len(self.corpus) - self.order):
            ctx = self.corpus[i:i + self.order]
            nxt = self.corpus[i + self.order]
            d = self.counts.setdefault(ctx, {})
            d[nxt] = d.get(nxt, 0) + 1
        self._fitted = True
        return self

    def _context_for(self, prefix):
        ctx = prefix[-self.order:]
        while len(ctx) > 0 and ctx not in self.counts:
            ctx = ctx[1:]
        if ctx == "":
            # global unigram fallback
            d = {}
            for c in self.corpus:
                d[c] = d.get(c, 0) + 1
            return None, d
        return ctx, self.counts[ctx]

    def dist(self, context):
        ctx, d = self._context_for(context)
        total = sum(d.values())
        return {c: v / total for c, v in d.items()}

    def next_token(self, prefix, temperature=0.0, rng=None, noise_scale=0.0):
        ctx, d = self._context_for(prefix)
        items = list(d.items())
        if noise_scale > 0.0 and rng is not None:
            items = [(c, v * float(np.exp(noise_scale * rng.standard_normal())))
                     for c, v in items]
        if temperature == 0.0:
            return max(items, key=lambda kv: kv[1])[0]
        # temperature sampling over observed successors
        p = np.array([v ** (1.0 / temperature) for _, v in items], dtype=float)
        p /= p.sum()
        if rng is None:
            rng = np.random.default_rng(0)
        return items[int(rng.choice(len(items), p=p))][0]

    def generate(self, prefix, n, temperature=0.0, rng=None, noise_scale=0.0):
        out = prefix
        for _ in range(n):
            out += self.next_token(out, temperature, rng, noise_scale)
        return out


def teacher_forced_nll(model, corpus):
    eps = 1e-10
    nll = 0.0
    count = 0
    for i in range(len(corpus) - model.order):
        ctx = corpus[i:i + model.order]
        nxt = corpus[i + model.order]
        d = model.counts.get(ctx)
        total = sum(d.values()) if d else 0
        p = (d.get(nxt, 0) / total) if total else eps
        nll += -np.log(max(p, eps))
        count += 1
    return nll / max(count, 1)


def free_run_divergence(model, corpus, n, noise_scale=0.0, rng=None):
    prefix = corpus[:model.order]
    truth = corpus[model.order:model.order + n]
    free = model.generate(prefix, len(truth), temperature=1.0, rng=rng,
                          noise_scale=noise_scale)[model.order:]
    if len(truth) == 0:
        return 0.0
    mism = sum(1 for a, b in zip(free, truth) if a != b)
    return mism / len(truth)
