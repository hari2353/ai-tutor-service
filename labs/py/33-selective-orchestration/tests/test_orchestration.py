def candidates(R):
    return [
        R.Candidate("docs", frozenset({"search", "summarize"}), 0.001, 80),
        R.Candidate("code", frozenset({"code", "debug"}), 0.003, 180),
        R.Candidate("reasoning", frozenset({"reason", "math"}), 0.005, 300),
        R.Candidate("slow-fallback", frozenset({"search"}), 0.002, 240),
    ]


def test_rank_is_bounded_and_deterministic(R):
    router = R.SelectiveRouter(candidates(R), max_candidates=2)
    ranked = router.rank(["search", "summarize"])
    assert [candidate.name for candidate in ranked] == ["docs", "slow-fallback"]
    assert len(ranked) == 2


def test_ambiguous_route_abstains_before_call_and_spend(R):
    router = R.SelectiveRouter(candidates(R), max_candidates=2,
                               min_confidence=0.75)
    calls = []

    result = router.dispatch(["search"], 1000,
                             lambda candidate, skills: calls.append(candidate))

    assert result.abstained is True
    assert result.status == "abstained"
    assert result.selected is None
    assert result.attempts == ()
    assert result.cost == 0.0
    assert result.latency_ms == 0
    assert calls == []


def test_confident_route_accounts_for_cost_and_latency(R):
    router = R.SelectiveRouter(candidates(R), max_candidates=2,
                               min_confidence=0.5)
    result = router.dispatch(["code", "debug"], 1000,
                             lambda candidate, skills: "patched")

    assert result.status == "success"
    assert result.selected == "code"
    assert result.confidence == 1.0
    assert result.fallback_used is False
    assert result.attempts == ("code",)
    assert result.output == "patched"
    assert result.cost == 3.0
    assert result.latency_ms == 180


def test_unavailable_primary_uses_only_bounded_fallbacks(R):
    router = R.SelectiveRouter(candidates(R), max_candidates=2,
                               min_confidence=0.5)
    seen = []

    def call(candidate, skills):
        seen.append(candidate.name)
        if candidate.name == "docs":
            raise R.CandidateUnavailable("provider outage")
        return "fallback result"

    result = router.dispatch(["search", "summarize"], 500, call)

    assert result.status == "success"
    assert result.selected == "slow-fallback"
    assert result.fallback_used is True
    assert result.candidate_set == ("docs", "slow-fallback")
    assert result.attempts == ("docs", "slow-fallback")
    assert seen == ["docs", "slow-fallback"]
    assert result.cost == 1.5
    assert result.latency_ms == 320


def test_no_match_abstains_and_unexpected_errors_propagate(R):
    router = R.SelectiveRouter(candidates(R))
    result = router.dispatch(["translation"], 200, lambda *args: None)
    assert result.status == "abstained"
    assert result.candidate_set == ()

    def bug(candidate, skills):
        raise ValueError("bad worker contract")

    with __import__("pytest").raises(ValueError):
        router.dispatch(["code"], 200, bug)


def test_all_fallbacks_fail_and_all_attempts_are_charged(R):
    router = R.SelectiveRouter(candidates(R), max_candidates=2,
                               min_confidence=0.5)

    def unavailable(candidate, skills):
        raise R.CandidateUnavailable(candidate.name)

    result = router.dispatch(["search", "summarize"], 100, unavailable)
    assert result.status == "failed"
    assert result.selected is None
    assert result.fallback_used is True
    assert result.attempts == ("docs", "slow-fallback")
    assert result.cost == 0.3
    assert result.latency_ms == 320
