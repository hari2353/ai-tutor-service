def test_equivalent_currency_values_answer(R):
    claims = [
        R.Claim("Rs 41,964", "policy", 3),
        R.Claim("41964", "runbook", 2),
    ]
    decision = R.resolve_claims(claims)
    assert decision.status == "answered"
    assert decision.value == "41964"
    assert decision.sources == ("policy", "runbook")


def test_low_tier_copies_do_not_outvote_policy(R):
    claims = [
        R.Claim("false", "forum-1", 0),
        R.Claim("false", "forum-2", 0),
        R.Claim("false", "forum-3", 0),
        R.Claim("true", "policy", 3),
    ]
    decision = R.resolve_claims(claims)
    assert decision.status == "answered"
    assert decision.value == "true"
    assert decision.sources == ("policy",)


def test_equal_authority_conflict_abstains(R):
    decision = R.resolve_claims([
        R.Claim("red", "policy-a", 3),
        R.Claim("blue", "policy-b", 3),
    ])
    assert decision.status == "abstained"
    assert decision.value is None
    assert decision.sources == ("policy-a", "policy-b")


def test_unapproved_claims_are_not_evidence(R):
    decision = R.resolve_claims([
        R.Claim("poison", "uploaded-doc", 3, approved=False),
        R.Claim("truth", "approved-policy", 2),
    ])
    assert decision.status == "answered"
    assert decision.value == "truth"


def test_low_authority_unique_winner_is_hedged(R):
    decision = R.resolve_claims([R.Claim("maybe", "forum", 0)])
    assert decision.status == "hedged"
    assert decision.value == "maybe"


def test_no_usable_claims_abstain(R):
    assert R.resolve_claims([]).status == "abstained"
    assert R.resolve_claims([R.Claim("", "empty", 3)]).status == "abstained"
