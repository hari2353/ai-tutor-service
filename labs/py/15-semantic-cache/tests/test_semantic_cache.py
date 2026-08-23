"""Lab 15 tests. No sleeps, no wall-clock — everything runs on FakeClock."""
import pytest


# ------------------------------------------------------------------ helpers
def _counter_backend(calls, answers=None):
    """backend_fn with a call counter; optional scripted answer sequence."""

    def backend(prompt):
        calls["n"] += 1
        if answers is not None:
            return answers.pop(0)
        return f"ANSWER<{prompt}>"

    return backend


def _mkcache(R, **kw):
    kw.setdefault("clock", R.FakeClock())
    return R.SemanticCache(_counter_backend(kw.pop("calls", {"n": 0})), **kw)


# ------------------------------------------------------------------ text ops
def test_normalize_strips_punct_collapses_whitespace(R):
    assert R.normalize("  What   is the CAPITAL?? of France... ") == \
        "what is the capital of france"
    assert R.normalize("don't stop") == "dont stop"      # punct dropped, not spaced
    assert R.normalize("\t\n a \r b  ") == "a b"


def test_char_3grams_and_jaccard_basics(R):
    g = R.char_3grams("abcdef")
    assert g == frozenset({"abc", "bcd", "cde", "def"})
    assert R.char_3grams("") == frozenset()
    assert R.char_3grams("hi") == frozenset({"hi"})      # short-string fallback
    assert R.jaccard(g, g) == pytest.approx(1.0)
    assert R.jaccard(frozenset({"a"}), frozenset({"b"})) == 0.0
    assert R.jaccard(frozenset(), frozenset()) == 0.0    # no evidence, not 1.0


# ------------------------------------------------------------------ exact layer
def test_exact_hit_and_backend_called_once(R):
    c = R.FakeClock()
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=c,
                            prefix_min_chars=None, threshold=None)
    first = cache.ask("What is the capital of France?")
    assert first.layer == "backend"
    again = cache.ask("What is the capital of France?")
    assert again.layer == "exact"
    assert again.answer == first.answer
    assert calls["n"] == 1, "second identical ask must not reach the backend"


def test_exact_is_byte_strict_case_and_spaces(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=None, threshold=None)
    cache.ask("Hello World")
    assert cache.ask("hello world").layer == "backend"
    assert cache.ask("hello  world").layer == "backend"   # extra space
    assert calls["n"] == 3, "exact layer must NOT normalize case or whitespace"


def test_exact_key_param_order_insensitive_but_value_sensitive(R):
    c = R.FakeClock()
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=c,
                            prefix_min_chars=None, threshold=None)
    cache.ask("ping", params={"a": 1, "b": 2})
    assert cache.ask("ping", params={"b": 2, "a": 1}).layer == "exact"
    assert calls["n"] == 1

    calls2 = {"n": 0}
    cache2 = R.SemanticCache(_counter_backend(calls2), clock=c,
                             prefix_min_chars=None, threshold=None)
    cache2.ask("ping", params={"temperature": 0})
    assert cache2.ask("ping", params={"temperature": 1}).layer == "backend"
    assert calls2["n"] == 2, "different sampling params must be a different request"


def test_cross_model_isolation(R):
    calls = {"n": 0}
    prompt = "summarize the quarterly revenue outlook for the board meeting"
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=10, threshold=0.4)
    assert cache.ask(prompt, model="gpt-x").layer == "backend"
    second = cache.ask(prompt, model="claude-y")
    assert second.layer == "backend", "same prompt on another model must fully miss"
    assert calls["n"] == 2
    assert cache.ask(prompt, model="gpt-x").layer == "exact"
    assert cache.stats.misses == 2 and cache.stats.exact_hits == 1


# ------------------------------------------------------------------ prefix layer
def test_prefix_hit_returns_marker_and_prefix_chars(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=30, threshold=None)
    base_prompt = "you are a helpful assistant answering questions about paris"
    cached_answer = cache.ask(base_prompt).answer
    variant = "you are a helpful assistant answering questions about rome"
    res = cache.ask(variant)
    assert res.layer == "prefix"
    assert res.prefix_chars >= 30
    assert res.prefix_chars == R.common_prefix_len(
        R.normalize(variant), R.normalize(base_prompt))
    assert res.answer.startswith(cached_answer), "cached continuation served as-is"
    assert res.answer.endswith(R.PREFIX_CONTINUATION_MARKER)
    assert calls["n"] == 1


def test_prefix_miss_below_min_chars(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=30, threshold=None)
    cache.ask("you are a helpful assistant answering questions about paris")
    res = cache.ask("explain quicksort versus mergesort tradeoffs please")
    assert res.layer == "backend"
    assert calls["n"] == 2
    assert cache.stats.prefix_hits == 0
    assert cache.stats.misses == 2


def test_prefix_min_chars_boundary_flips_hit(R):
    a = "recommend me a movie for tonight please"
    b = "recommend her a book for tonight please"
    lcp = R.common_prefix_len(R.normalize(a), R.normalize(b))
    assert lcp > 0

    hit_cache = R.SemanticCache(
        lambda p: f"A:{p}", clock=R.FakeClock(),
        prefix_min_chars=lcp, threshold=None)
    hit_cache.ask(a)
    assert hit_cache.ask(b).layer == "prefix"

    miss_cache = R.SemanticCache(
        lambda p: f"A:{p}", clock=R.FakeClock(),
        prefix_min_chars=lcp + 1, threshold=None)
    miss_cache.ask(a)
    assert miss_cache.ask(b).layer == "backend"


def test_prefix_picks_longest_shared_candidate(R):
    answers = {}
    # cached pair must NOT share >= min_chars with each other, or the second
    # fill would prefix-hit instead of populating
    prompts = {
        "one": "please summarize chapter one of the book tonight",
        "two": "please recap chapter ten of the book tonight",
    }

    def backend(prompt):
        answers[prompt] = f"A[{prompt}]"
        return answers[prompt]

    cache = R.SemanticCache(backend, clock=R.FakeClock(),
                            prefix_min_chars=20, threshold=None)
    assert R.common_prefix_len(R.normalize(prompts["one"]),
                               R.normalize(prompts["two"])) < 20
    cache.ask(prompts["one"])
    cache.ask(prompts["two"])
    query = "please recap chapter twelve of the book tonight"
    res = cache.ask(query)
    assert res.layer == "prefix"
    expected_target = max(
        prompts.values(),
        key=lambda p: R.common_prefix_len(R.normalize(query), R.normalize(p)),
    )
    assert expected_target == prompts["two"]     # sanity: a real longest match exists
    assert res.answer.startswith(answers[expected_target])


# ------------------------------------------------------------------ semantic layer
def test_semantic_hit_records_similarity(R):
    calls = {"n": 0}
    # reorder pair: near-identical trigram sets, ~zero shared prefix
    base = "the cat sat on the mat because it was tired"
    query = "because it was tired, the cat sat on the mat!"
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=20, threshold=0.5)
    cached = cache.ask(base)
    res = cache.ask(query)
    assert res.layer == "semantic"
    expected_sim = R.jaccard(R.char_3grams(query), R.char_3grams(base))
    assert expected_sim > 0.5                       # sanity: pair clears threshold
    assert res.similarity == pytest.approx(expected_sim)
    assert res.answer == cached.answer
    assert calls["n"] == 1


def test_semantic_miss_below_threshold_calls_backend(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=None, threshold=0.9)
    cache.ask("the cat sat on the mat because it was tired")
    res = cache.ask("recommend a good python debugger for windows")
    assert res.layer == "backend"
    assert calls["n"] == 2
    assert cache.stats.semantic_hits == 0


def test_threshold_tuning_flips_semantic_hit_miss(R):
    # differ in exactly the token that changes the answer (curriculum's false-hit
    # shape) — similarity sits mid-range so ±0.01 flips the decision
    annual = "annual plan refund window explained"
    monthly = "monthly plan refund window explained"
    sim = R.jaccard(R.char_3grams(annual), R.char_3grams(monthly))
    assert 0.0 < sim < 1.0

    loose = R.SemanticCache(lambda p: "A", clock=R.FakeClock(),
                            prefix_min_chars=None, threshold=sim - 0.01)
    loose.ask(annual)
    assert loose.ask(monthly).layer == "semantic"

    strict = R.SemanticCache(lambda p: "A", clock=R.FakeClock(),
                             prefix_min_chars=None, threshold=sim + 0.01)
    strict.ask(annual)
    res = strict.ask(monthly)
    assert res.layer == "backend"
    assert strict.stats.semantic_hits == 0


def test_semantic_layer_can_be_disabled(R):
    calls = {"n": 0}
    base = "the cat sat on the mat because it was tired"
    query = "because it was tired, the cat sat on the mat!"
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=None, threshold=None)
    cache.ask(base)
    assert cache.ask(query).layer == "backend"
    assert calls["n"] == 2


# ------------------------------------------------------------------ layer order
def test_layers_checked_in_order_exact_prefix_semantic(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=20, threshold=0.5)
    prompt = "please explain the refund policy for annual plans in detail"
    cache.ask(prompt)

    exact_res = cache.ask(prompt)
    assert exact_res.layer == "exact"

    prefix_res = cache.ask("please explain the refund policy for annual plans in depth")
    assert prefix_res.layer == "prefix", "long shared prefix must win before semantic"

    reordered = "in detail, please explain the refund policy for annual plans"
    sem_res = cache.ask(reordered)
    assert sem_res.layer == "semantic", "no shared prefix → falls through to semantic"
    assert calls["n"] == 1


def test_single_fill_populates_all_layers(R):
    """ONE backend call, then every layer serves from that single fill."""
    calls = {"n": 0}

    def const_backend(prompt):
        calls["n"] += 1
        return "BACKEND_ANSWER"

    cache = R.SemanticCache(const_backend, clock=R.FakeClock(),
                            prefix_min_chars=20, threshold=0.5)
    base = "the cat sat on the mat because it was tired"

    assert cache.ask(base).layer == "backend"
    assert cache.ask(base).layer == "exact"                    # raw bytes repeat
    variant = "THE CAT  SAT on the MAT?! because IT was tired..."
    assert cache.ask(variant).layer == "prefix"                # normalized repeat
    reorder = "because it was tired, the cat sat on the mat"
    assert cache.ask(reorder).layer == "semantic"              # paraphrase
    assert calls["n"] == 1, "three layers served from one fill — zero extra calls"
    assert cache.stats.as_dict() == {
        "exact_hits": 1, "prefix_hits": 1, "semantic_hits": 1,
        "misses": 1, "evictions": 0,
    }


# ------------------------------------------------------------------ TTL
def test_ttl_expiry_only_affects_expired_entry(R):
    c = R.FakeClock()
    calls = {"n": 0}
    answers = ["old-A", "B", "new-A"]
    cache = R.SemanticCache(_counter_backend(calls, answers), clock=c,
                            ttl=10.0, prefix_min_chars=None, threshold=None)

    cache.ask("prompt A")                 # t=0, ts=0
    c.advance(5.0)
    cache.ask("prompt B")                 # t=5, ts=5
    assert cache.ask("prompt A").layer == "exact"   # age 5 < ttl 10
    assert cache.ask("prompt B").layer == "exact"
    assert calls["n"] == 2

    c.advance(6.0)                        # t=11: A aged out (11-0>=10), B alive
    assert cache.ask("prompt B").layer == "exact", "only the expired entry expires"
    res = cache.ask("prompt A")
    assert res.layer == "backend" and res.answer == "new-A"
    assert cache.ask("prompt A").layer == "exact"   # refilled fresh
    assert cache.stats.evictions == 0, "TTL expiry is lazy cleanup, not eviction"


def test_expired_entry_refills_with_fresh_answer(R):
    c = R.FakeClock(t=100.0)
    seq = iter(["stale", "fresh"])
    cache = R.SemanticCache(lambda p: next(seq), clock=c,
                            ttl=5.0, prefix_min_chars=None, threshold=None)
    stale = cache.ask("q")
    c.advance(6.0)
    res = cache.ask("q")
    assert res.layer == "backend"
    assert res.answer == "fresh" and stale.answer == "stale"


# ------------------------------------------------------------------ stats
def test_stats_counters_and_hit_rate_math(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=20, threshold=0.5)
    base = "the cat sat on the mat because it was tired"
    cache.ask(base)                                        # miss
    cache.ask(base)                                        # exact
    cache.ask("THE CAT  SAT on the MAT?! because IT was tired...")   # prefix
    cache.ask("because it was tired, the cat sat on the mat")        # semantic
    cache.ask("totally unrelated request about kubernetes ingress")  # miss
    s = cache.stats.as_dict()
    assert s == {"exact_hits": 1, "prefix_hits": 1, "semantic_hits": 1,
                 "misses": 2, "evictions": 0}
    assert cache.hit_rate() == pytest.approx(3 / 5), "denominator is hits+misses"


def test_hit_rate_zero_before_any_ask(R):
    cache = _mkcache(R, calls={"n": 0}, prefix_min_chars=None, threshold=None)
    assert cache.hit_rate() == 0.0
    assert cache.stats.lookups == 0


# ------------------------------------------------------------------ eviction
def test_eviction_capacity_cap_lru_by_insertion(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            capacity=2, prefix_min_chars=None, threshold=None)
    cache.ask("prompt alpha")     # [alpha]
    cache.ask("prompt bravo")     # [alpha, bravo]
    cache.ask("prompt charlie")   # evicts alpha → [bravo, charlie]
    assert cache.stats.evictions == 1
    assert cache.stats.misses == 3

    res = cache.ask("prompt alpha")
    assert res.layer == "backend", "oldest-inserted entry must be gone"
    assert cache.stats.evictions == 2          # refill evicted bravo → [charlie, alpha]
    assert cache.ask("prompt charlie").layer == "exact"
    assert cache.stats.evictions == 2
    assert cache.stats.misses == 4


def test_no_eviction_below_capacity(R):
    calls = {"n": 0}
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            capacity=5, prefix_min_chars=None, threshold=None)
    for p in ("a", "b", "c"):
        cache.ask(p)
    assert cache.stats.evictions == 0
    assert len(cache) == 3


# ------------------------------------------------------------------ invalidate
def test_invalidate_clears_only_target_model(R):
    calls = {"n": 0}
    prompt = "explain how the retry budget interacts with the circuit breaker state"
    cache = R.SemanticCache(_counter_backend(calls), clock=R.FakeClock(),
                            prefix_min_chars=10, threshold=0.4)
    cache.ask(prompt, model="m1")
    cache.ask(prompt, model="m2")
    assert cache.invalidate("m1") == 1
    assert cache.invalidate("does-not-exist") == 0

    assert cache.ask(prompt, model="m1").layer == "backend"
    assert cache.ask(prompt, model="m2").layer == "exact", "other model untouched"

    assert cache.invalidate("m2") == 1
    assert len(cache) == 1                     # only m1's fresh entry remains
