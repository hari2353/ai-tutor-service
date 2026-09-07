"""Lab 28 tests. Pure stdlib on the implementation side — `re` only."""
import pytest


# shared skills: one per lab concern, all with boundary-honest patterns
DEPLOY = dict(name="deploy", description="Ship the current branch to staging or prod",
              patterns=[r"\bdeploy\b", r"\bship\b", r"\brelease to (?:staging|prod)\b"])
REVIEW = dict(name="review", description="Review a diff or pull request",
              patterns=[r"\breview\b", r"\bcode review\b"])
TEST = dict(name="test", description="Run the test suite",
            patterns=[r"\btests?\b"])
# the control: NO \b — this is the bug you are writing patterns to avoid
LOOSE = dict(name="loose", description="Demonstrates an unguarded pattern",
             patterns=["test"])


def _index(S, *skills):
    idx = S.SkillIndex()
    for s in skills:
        idx.register(S.Skill(**s))
    return idx


# ------------------------------------------------------------------ register
def test_register_and_count(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    assert len(idx.skills) == 3
    assert {s.name for s in idx.skills} == {"deploy", "review", "test"}


def test_match_single_pattern(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    assert idx.match("please review the auth diff") == ("review", (1, 6))


# ------------------------------------------------------------------ scoring
def test_two_pattern_matches_beats_one(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    # "review" skill matches 2 patterns (\breview\b + \bcode review\b);
    # "deploy" only 1 via \bship\b — count wins over span length
    assert idx.match("run a code review, then ship it") == ("review", (2, 11))


def test_tiebreak_by_longest_match(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    # deploy: \bship\b (4) ; review: \breview\b (6) — both 1 pattern
    assert idx.match("review the diff and ship the branch") == ("review", (1, 6))


def test_tiebreak_prefers_longer_match_over_more_recent_skill(S):
    # two skills, same single-pattern count; later skill's match is shorter
    skill_a = dict(name="short_match", description="a",
                   patterns=[r"\brefactor\b"])
    skill_b = dict(name="long_match", description="b",
                   patterns=[r"\bcode review\b"])
    idx = _index(S, skill_a, skill_b)
    assert idx.match("please run a code review after the refactor") == ("long_match", (1, 11))


def test_full_tie_goes_to_earliest_registered(S):
    first = dict(name="first", description="", patterns=[r"\bship\b"])
    second = dict(name="second", description="", patterns=[r"\bship\b"])
    idx = _index(S, first, second)
    assert idx.match("ship it") == ("first", (1, 4))


def test_ambiguity_detected_on_equal_scores(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    # true tie: deploy \bdeploy\b (6) vs review \breview\b (6), one pattern each
    assert sorted(idx.ambiguous("review the plan and deploy it")) == ["deploy", "review"]


def test_ambiguity_clear_when_scores_differ(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    assert idx.ambiguous("review the diff, then ship it") == []


# ------------------------------------------------------------------ no match
def test_no_match_returns_none(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    assert idx.match("what's for lunch?") is None


def test_match_on_empty_index(S):
    assert S.SkillIndex().match("anything") is None


# ------------------------------------------------------------------ boundaries
def test_word_boundary_prevents_test_matching_testing(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    # "testing" must NOT trigger \btests?\b; nobody else matches -> None
    assert idx.match("improve our testing strategy") is None


def test_unguarded_pattern_is_the_failure_mode(S):
    idx = _index(S, DEPLOY, REVIEW, TEST, LOOSE)
    # control: with the loose "test" pattern registered, "testing" triggers —
    # this is exactly the over-trigger an honest golden set must catch
    assert idx.match("improve our testing strategy") == ("loose", (1, 4))


def test_word_boundary_allows_real_word_forms(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    assert idx.match("run the tests") == ("test", (1, 5))


# ------------------------------------------------------------------ versions
def test_bump_increments_version_and_preserves_skill(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    old = idx.get("deploy")
    new = S.bump(old)
    assert new.version == old.version + 1 == 2
    assert new.name == old.name and new.patterns == old.patterns


def test_register_same_version_raises(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    twin = S.Skill(name="deploy", description="different words", patterns=[r"\bdeploy\b"])
    with pytest.raises(S.RegisteringError):
        idx.register(twin)                     # same version 1 — rejected


def test_register_lower_version_raises(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    v3 = S.bump(S.bump(idx.get("deploy")))     # version 3
    idx.register(v3)
    stale = idx.get("deploy")
    old = S.Skill(name="deploy", description="stale replica", patterns=[r"\bdeploy\b"])
    with pytest.raises(S.RegisteringError):
        idx.register(old)                      # version 1 < current 3 — rejected


def test_register_higher_version_replaces(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    next_ = S.bump(idx.get("review"))
    idx.register(next_)
    assert idx.get("review").version == 2
    # and the replacement is live for matching
    assert idx.match("run a code review, then ship it") == ("review", (2, 11))


def test_new_name_registers_at_any_version(S):
    idx = _index(S, DEPLOY, REVIEW, TEST)
    idx.register(S.Skill(name="fresh", description="new", patterns=[r"\bfresh\b"], version=4))
    assert idx.get("fresh").version == 4


# ------------------------------------------------------------------ eval harness
def _golden(S, with_loose=False):
    if with_loose:
        idx = _index(S, DEPLOY, REVIEW, TEST, LOOSE)
    else:
        idx = _index(S, DEPLOY, REVIEW, TEST)
    cases = [
        ("review this pr before merging", "review"),
        ("run the tests and report failures", "test"),
        ("deploy to staging after CI is green", "deploy"),
        ("write more tests for the parser", "test"),          # under-trigger guard
        ("refactor the parser module", None),                  # over-trigger guard
    ]
    return idx, cases


def test_evaluate_perfect_on_honest_golden_set(S):
    idx, cases = _golden(S)
    report = S.evaluate(idx, cases)
    assert report.accuracy == 1.0
    assert report.misses == []
    assert len(report.results) == 5
    assert all(r.passed for r in report.results)


def test_evaluate_flags_misses_individually(S):
    idx, cases = _golden(S)
    cases[4] = ("improve our testing strategy", "review")     # a lie: should be None
    report = S.evaluate(idx, cases)
    assert report.accuracy == pytest.approx(4 / 5)
    assert len(report.misses) == 1
    miss = report.misses[0]
    assert miss.query == "improve our testing strategy"
    assert miss.expected == "review" and miss.actual is None


def test_evaluate_scores_overtrigger_as_a_miss(S):
    idx, cases = _golden(S, with_loose=True)
    cases = cases[:5]                                         # expects None; loose fires
    cases.append(("improve our testing strategy", None))
    report = S.evaluate(idx, cases)
    assert report.accuracy == pytest.approx(5 / 6)
    assert report.misses[0].query == "improve our testing strategy"
    assert report.misses[0].actual == "loose"
