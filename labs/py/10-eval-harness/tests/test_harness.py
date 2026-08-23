"""Lab 10 tests. Fully scripted, fully deterministic, no network, no sleeps."""
import os
import tempfile

import pytest


# ------------------------------------------------------------------ step 1: scorers
def test_exact_match_scorer_correct(H):
    case = H.GoldenCase(id="c1", input="2+2?", expected="4")
    assert H.exact_match_scorer("4", case) == 1.0


def test_exact_match_scorer_incorrect(H):
    case = H.GoldenCase(id="c1", input="2+2?", expected="4")
    assert H.exact_match_scorer("5", case) == 0.0


def test_exact_match_scorer_ignores_surrounding_whitespace(H):
    case = H.GoldenCase(id="c1", input="2+2?", expected="4")
    assert H.exact_match_scorer("  4\n", case) == 1.0


def test_contains_scorer_substring_match(H):
    case = H.GoldenCase(id="c1", input="capital of France?", expected="Paris")
    assert H.contains_scorer("The capital of France is Paris.", case) == 1.0


def test_contains_scorer_case_insensitive(H):
    case = H.GoldenCase(id="c1", input="capital of France?", expected="Paris")
    assert H.contains_scorer("i think it's paris", case) == 1.0


def test_contains_scorer_no_match(H):
    case = H.GoldenCase(id="c1", input="capital of France?", expected="Paris")
    assert H.contains_scorer("I don't know", case) == 0.0


# ------------------------------------------------------------------ step 2: scripted model
def test_scripted_model_returns_configured_response(H):
    model = H.ScriptedModel({"2+2?": "4"})
    assert model("2+2?") == "4"


def test_scripted_model_records_calls(H):
    model = H.ScriptedModel({"a": "1", "b": "2"})
    model("a")
    model("b")
    assert model.calls == ["a", "b"]


def test_scripted_model_raises_on_unscripted_input_with_no_default(H):
    model = H.ScriptedModel({"a": "1"})
    with pytest.raises(KeyError):
        model("never scripted")


def test_scripted_model_falls_back_to_default(H):
    model = H.ScriptedModel({"a": "1"}, default="idk")
    assert model("something else") == "idk"


# ------------------------------------------------------------------ step 3: eval runner
def _golden_set(H):
    return [
        H.GoldenCase(id="c1", input="2+2?", expected="4"),
        H.GoldenCase(id="c2", input="capital of France?", expected="Paris"),
        H.GoldenCase(id="c3", input="3+3?", expected="6"),
    ]


def test_eval_runner_scores_each_case(H):
    model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "7"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)
    report = runner.run(model, _golden_set(H))
    scores = {r.case_id: r.score for r in report.results}
    assert scores == {"c1": 1.0, "c2": 1.0, "c3": 0.0}


def test_eval_runner_case_results_carry_output(H):
    model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "7"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)
    report = runner.run(model, _golden_set(H))
    outputs = {r.case_id: r.output for r in report.results}
    assert outputs["c3"] == "7"


def test_eval_runner_computes_mean_score(H):
    model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "7"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)
    report = runner.run(model, _golden_set(H))
    assert report.metrics["mean_score"] == pytest.approx(2 / 3)


def test_eval_runner_computes_pass_rate_with_threshold(H):
    model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "7"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer, pass_threshold=1.0)
    report = runner.run(model, _golden_set(H))
    assert report.metrics["pass_rate"] == pytest.approx(2 / 3)


def test_eval_runner_all_correct_gives_perfect_metrics(H):
    model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "6"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)
    report = runner.run(model, _golden_set(H))
    assert report.metrics["mean_score"] == pytest.approx(1.0)
    assert report.metrics["pass_rate"] == pytest.approx(1.0)


def test_eval_runner_empty_golden_set_does_not_divide_by_zero(H):
    model = H.ScriptedModel({})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)
    report = runner.run(model, [])
    assert report.metrics == {"mean_score": 0.0, "pass_rate": 0.0}
    assert report.results == []


# ------------------------------------------------------------------ step 4: regression gate
def test_check_regression_passes_when_metrics_meet_baseline(H):
    result = H.check_regression({"mean_score": 0.9}, {"mean_score": 0.85})
    assert result.passed is True
    assert result.failures == []


def test_check_regression_fails_when_metric_drops_below_baseline(H):
    result = H.check_regression({"mean_score": 0.7}, {"mean_score": 0.85})
    assert result.passed is False
    assert any("mean_score" in f for f in result.failures)


def test_check_regression_respects_tolerance(H):
    # 0.83 is within 0.05 of the 0.85 baseline -- should pass with tolerance
    result = H.check_regression({"mean_score": 0.83}, {"mean_score": 0.85}, tolerance=0.05)
    assert result.passed is True

    # but not with a tighter tolerance
    result = H.check_regression({"mean_score": 0.83}, {"mean_score": 0.85}, tolerance=0.01)
    assert result.passed is False


def test_check_regression_fails_when_metric_missing_from_current(H):
    result = H.check_regression({}, {"mean_score": 0.85})
    assert result.passed is False
    assert any("missing" in f for f in result.failures)


def test_save_and_load_baseline_round_trip(H):
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        H.save_baseline(path, {"mean_score": 0.9, "pass_rate": 0.8})
        loaded = H.load_baseline(path)
        assert loaded == {"mean_score": 0.9, "pass_rate": 0.8}
    finally:
        os.remove(path)


def test_regression_gate_end_to_end_fails_the_build_on_a_real_drop(H):
    """A worse model version regresses mean_score; the gate must catch it."""
    baseline_model = H.ScriptedModel({"2+2?": "4", "capital of France?": "Paris", "3+3?": "6"})
    regressed_model = H.ScriptedModel({"2+2?": "4", "capital of France?": "wrong", "3+3?": "wrong"})
    runner = H.EvalRunner(scorer=H.exact_match_scorer)

    baseline_report = runner.run(baseline_model, _golden_set(H))
    current_report = runner.run(regressed_model, _golden_set(H))

    gate = H.check_regression(current_report.metrics, baseline_report.metrics)
    assert gate.passed is False


# ------------------------------------------------------------------ step 5: biased judge -- position bias
def test_position_bias_flips_winner_when_order_swapped(H):
    """Same two answers, order swapped -- the winner changes, even though
    nothing about their actual content changed."""
    answer_1 = "The mitochondria is the powerhouse of the cell."
    answer_2 = "Mitochondria produce ATP through cellular respiration."
    # pad to equal length so the ONLY variable across the two calls is position
    pad = abs(len(answer_1) - len(answer_2))
    if len(answer_1) < len(answer_2):
        answer_1 += " " * pad
    else:
        answer_2 += " " * pad
    assert len(answer_1) == len(answer_2)

    result_forward = H.biased_judge("what does the mitochondria do?", answer_1, answer_2)
    result_swapped = H.biased_judge("what does the mitochondria do?", answer_2, answer_1)

    assert result_forward["winner"] == "A"
    assert result_swapped["winner"] == "A"
    # "A" means a different ANSWER won each time purely because of slot order
    winner_content_forward = answer_1
    winner_content_swapped = answer_2
    assert winner_content_forward != winner_content_swapped


def test_position_bias_measured_margin_equals_configured_bonus(H):
    """At equal quality and equal length, the score gap between slot A and
    slot B is exactly POSITION_BONUS -- a measured number, not a vibe."""
    same_length_answer_a = "x" * 50
    same_length_answer_b = "y" * 50
    result = H.biased_judge("q", same_length_answer_a, same_length_answer_b)
    assert result["score_a"] - result["score_b"] == pytest.approx(H.POSITION_BONUS)


def test_measured_position_bias_win_rate_across_many_equal_pairs(H):
    """Across a batch of equal-quality, equal-length pairs, an unbiased
    judge should land near a 0.5 first-slot win rate. This judge doesn't."""
    pairs = [(f"answer {i} " + "z" * 20, f"answer {i + 1} " + "z" * 19) for i in range(10)]
    # normalize each pair to equal length so position is the only variable
    normalized = []
    for a, b in pairs:
        n = max(len(a), len(b))
        normalized.append((a.ljust(n), b.ljust(n)))

    metrics = H.measure_position_bias(H.biased_judge, "q", normalized)
    assert metrics["first_slot_win_rate"] == pytest.approx(1.0)
    assert metrics["n"] == 20


# ------------------------------------------------------------------ step 6: biased judge -- verbosity bias
def test_verbosity_bias_prefers_longer_answer_at_equal_quality(H):
    short_answer = "Paris."
    long_answer = ("Paris is the capital of France. It has been the capital for "
                    "centuries and is known for the Eiffel Tower and the Louvre museum.")
    metrics = H.measure_verbosity_bias(H.biased_judge, "capital of France?", short_answer, long_answer)
    assert metrics["long_answer_win_rate"] == pytest.approx(1.0)


def test_verbosity_bias_measured_score_delta_matches_weight_times_length_diff(H):
    short_answer = "x" * 10
    long_answer = "x" * 200
    # hold position constant (both in slot B) to isolate the length effect
    baseline = "z" * 10
    result_short = H.biased_judge("q", baseline, short_answer)
    result_long = H.biased_judge("q", baseline, long_answer)
    delta = result_long["score_b"] - result_short["score_b"]
    expected_delta = H.VERBOSITY_WEIGHT * (len(long_answer) - len(short_answer))
    assert delta == pytest.approx(expected_delta)


def test_verbosity_bias_can_overpower_position_bias(H):
    """A long-enough answer wins even from the WORSE (non-first) slot,
    purely on length -- demonstrating verbosity bias is not just a tie
    breaker, it can dominate position bias entirely."""
    short_answer = "x" * 10
    long_answer = "x" * 500  # length gap far exceeds POSITION_BONUS / VERBOSITY_WEIGHT
    result = H.biased_judge("q", short_answer, long_answer)  # short gets the position bonus
    assert result["winner"] == "B"  # long wins anyway
