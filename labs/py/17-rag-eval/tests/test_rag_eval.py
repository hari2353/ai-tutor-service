"""Lab 17 tests. The stub judge is deterministic - every score is pinnable."""
import pytest


# ------------------------------------------------------------------ fixtures
QUESTION = "How do plants capture light energy?"

CTX_1 = "Photosynthesis lets plants capture light energy."
CTX_2 = "Chlorophyll inside leaves absorbs sunlight for photosynthesis."
CTX_BAD = "The Eiffel Tower stands in Paris."

GROUND_TRUTH = ("Plants capture light energy through photosynthesis. "
                "Chlorophyll inside leaves absorbs sunlight.")

GOOD_ANSWER = ("Plants capture light energy via photosynthesis. "
               "Chlorophyll inside leaves absorbs sunlight.")
HALLUCINATIONS = ["Mars has two moons, Phobos plus Deimos.",
                  "Jupiter has ninety five moons."]
FILLER_ANSWER = "Plants capture light energy. There are various aspects."


def perfect_case(R):
    return R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                      contexts=[CTX_1, CTX_2], ground_truth=GROUND_TRUTH)


def hallucinated_case(R):
    return R.EvalCase(question=QUESTION,
                      answer=GOOD_ANSWER + " " + " ".join(HALLUCINATIONS),
                      contexts=[CTX_1, CTX_2], ground_truth=GROUND_TRUTH)


def dragged_precision_case(R):
    """Irrelevant chunk ranked TOP; the covering chunks sit below it."""
    return R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                      contexts=[CTX_BAD, CTX_1, CTX_2], ground_truth=GROUND_TRUTH)


def uncovered_recall_case(R):
    gt = GROUND_TRUTH + " Water and carbon dioxide are required inputs."
    return R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                      contexts=[CTX_1, CTX_2], ground_truth=gt)


# ------------------------------------------------------------------ text ops
def test_split_sentences_keeps_punctuation(R):
    assert R.split_sentences("One fact here. Two facts now! Three?") == \
        ["One fact here.", "Two facts now!", "Three?"]
    assert R.split_sentences("   ") == []
    assert R.split_sentences("No terminal punctuation") == ["No terminal punctuation"]


def test_content_words_drop_stopwords_and_punctuation(R):
    assert R.content_words("The cat, sat on the mat!") == ["cat", "sat", "mat"]
    assert R.content_words(QUESTION) == ["plants", "capture", "light", "energy"]


# ------------------------------------------------------------------ perfect fixture
def test_perfect_rag_scores_one_on_every_metric(R):
    case = perfect_case(R)
    prec = R.context_precision(case, k=2)
    rec = R.context_recall(case)
    fai = R.faithfulness(case)
    rel = R.answer_relevancy(case)
    print(f"\nperfect fixture exact scores: "
          f"context_precision@2={prec!r} context_recall={rec!r} "
          f"faithfulness={fai!r} answer_relevancy={rel!r}")
    assert prec == 1.0
    assert rec == 1.0
    assert fai == 1.0
    assert rel == 1.0


def test_perfect_fixture_flags_nothing(R):
    detail_f = R.faithfulness_detail(perfect_case(R))
    detail_r = R.context_recall_detail(perfect_case(R))
    assert detail_f["unsupported_claims"] == []
    assert detail_r["uncovered_sentences"] == []


# ------------------------------------------------------------------ faithfulness
def test_hallucination_drives_faithfulness_down(R):
    good, bad = R.faithfulness(perfect_case(R)), R.faithfulness(hallucinated_case(R))
    print(f"\nfaithfulness: grounded={good!r} with_hallucination={bad!r}")
    assert good == 1.0
    assert bad == 0.5


def test_hallucinated_claims_are_listed_verbatim(R):
    detail = R.faithfulness_detail(hallucinated_case(R))
    assert detail["unsupported_claims"] == HALLUCINATIONS


def test_faithfulness_empty_contexts_guarded(R):
    case = R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                      contexts=[], ground_truth=GROUND_TRUTH)
    detail = R.faithfulness_detail(case)
    assert detail["score"] == 0.0
    assert detail["unsupported_claims"] == R.split_sentences(GOOD_ANSWER)


def test_blank_answer_scores_zero_not_crash(R):
    case = R.EvalCase(question=QUESTION, answer="", contexts=[CTX_1], ground_truth=GROUND_TRUTH)
    assert R.faithfulness(case) == 0.0
    assert R.answer_relevancy(case) == 0.0


# ------------------------------------------------------------------ precision vs recall
def test_irrelevant_top_context_drags_precision_at_k(R):
    case = dragged_precision_case(R)
    p_at_1 = R.context_precision(case, k=1)
    p_at_3 = R.context_precision(case, k=3)
    print(f"\nrank matters: precision@1={p_at_1!r} precision@3={p_at_3!r}")
    assert p_at_1 == 0.0                       # the noise IS the top result
    assert p_at_3 == pytest.approx(2 / 3)      # two of three chunks relevant


def test_irrelevant_top_context_spares_recall(R):
    """Recall ignores rank: the covering chunks are still SOMEWHERE in the list.
    Precision punishes noise; recall does not â€” that asymmetry is the point."""
    assert R.context_precision(dragged_precision_case(R), k=3) < 1.0
    assert R.context_recall(dragged_precision_case(R)) == 1.0
    assert R.context_recall(perfect_case(R)) == 1.0


def test_uncovered_sentence_flagged_with_text(R):
    detail = R.context_recall_detail(uncovered_recall_case(R))
    assert detail["score"] == pytest.approx(2 / 3)
    assert detail["uncovered_sentences"] == \
        ["Water and carbon dioxide are required inputs."]


def test_precision_empty_contexts_guarded(R):
    case = R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                      contexts=[], ground_truth=GROUND_TRUTH)
    assert R.context_precision(case, k=3) == 0.0


def test_recall_empty_contexts_flags_every_sentence(R):
    detail = R.context_recall_detail(
        R.EvalCase(question=QUESTION, answer="x", contexts=[], ground_truth=GROUND_TRUTH))
    assert detail["score"] == 0.0
    assert detail["uncovered_sentences"] == [
        "Plants capture light energy through photosynthesis.",
        "Chlorophyll inside leaves absorbs sunlight.",
    ]


def test_precision_k_larger_than_context_list(R):
    """min(k, len(contexts)) denominator: a short list isn't punished for
    retrieval slots it never filled."""
    assert R.context_precision(perfect_case(R), k=5) == 1.0


# ------------------------------------------------------------------ answer relevancy
def test_answer_relevancy_overlap_penalty_offtopic(R):
    perfect = R.EvalCase(question=QUESTION, answer=GOOD_ANSWER,
                         contexts=[CTX_1, CTX_2], ground_truth=GROUND_TRUTH)
    filler = R.EvalCase(question=QUESTION, answer=FILLER_ANSWER,
                        contexts=[CTX_1, CTX_2], ground_truth=GROUND_TRUTH)
    offtopic = R.EvalCase(question=QUESTION,
                          answer="The Eiffel Tower stands tall in Paris.",
                          contexts=[CTX_1, CTX_2], ground_truth=GROUND_TRUTH)
    a, b, c = R.answer_relevancy(perfect), R.answer_relevancy(filler), R.answer_relevancy(offtopic)
    print(f"\nanswer_relevancy: on_topic={a!r} filler_heavy={b!r} off_topic={c!r}")
    assert a == 1.0                            # touches every question term, no filler
    assert b == 0.8125                         # 4/4 overlap x (1 - 0.5 * 3/8 fillers)
    assert c == 0.0                            # zero term overlap with the question


def test_empty_question_relevancy_guarded(R):
    case = R.EvalCase(question="", answer=GOOD_ANSWER, contexts=[CTX_1],
                      ground_truth=GROUND_TRUTH)
    assert R.answer_relevancy(case) == 0.0


# ------------------------------------------------------------------ judge injection
def test_judge_weights_are_configurable(R):
    default = R.JudgeStub()                              # q=1.0, gt=2.0
    no_gt = R.JudgeStub(ground_truth_weight=0.0)         # question terms only
    base = default.context_relevance(QUESTION, GROUND_TRUTH, CTX_2)
    stripped = no_gt.context_relevance(QUESTION, GROUND_TRUTH, CTX_2)
    print(f"\nrelevance(CTX_2): weighted={base!r} question_only={stripped!r}")
    assert base > stripped               # CTX_2 supports the GT but not the question
    assert stripped == 0.0
    assert R.context_precision(perfect_case(R), no_gt, k=2) == 0.5   # CTX_2 now irrelevant


def test_relevance_threshold_knob_flips_a_context(R):
    strict = R.JudgeStub(relevance_threshold=0.45)       # CTX_2 scores 0.4 -> cut
    loose = R.JudgeStub(relevance_threshold=0.30)
    assert R.context_precision(perfect_case(R), strict, k=2) == 0.5
    assert R.context_precision(perfect_case(R), loose, k=2) == 1.0


def test_custom_injected_judge_overrides_verdicts(R):
    class AlwaysSupport(R.JudgeStub):
        def is_claim_supported(self, claim, contexts):
            return True

    assert R.faithfulness(hallucinated_case(R)) == 0.5
    assert R.faithfulness(hallucinated_case(R), AlwaysSupport()) == 1.0


# ------------------------------------------------------------------ eval_suite
def test_suite_aggregate_means_exact(R):
    report = R.eval_suite([perfect_case(R), hallucinated_case(R)], k=2)
    agg = report["aggregate"]
    print(f"\naggregate: {agg}")
    assert report["n_cases"] == 2
    assert agg["n_cases"] == 2
    assert agg["context_precision"] == 1.0        # (1.0 + 1.0) / 2
    assert agg["context_recall"] == 1.0           # (1.0 + 1.0) / 2
    assert agg["faithfulness"] == 0.75            # (1.0 + 0.5) / 2
    assert agg["answer_relevancy"] == 1.0         # both answers filler-free


def test_worst_cases_sorted_ascending_by_faithfulness(R):
    report = R.eval_suite([perfect_case(R), hallucinated_case(R),
                           uncovered_recall_case(R)], k=2)
    worst = report["worst_cases"]
    faiths = [c["faithfulness"] for c in worst]
    assert faiths == sorted(faiths) == [0.5, 1.0, 1.0]
    assert worst[0]["index"] == 1                 # the hallucinator ranks first
    assert [c["index"] for c in worst] == [1, 0, 2]   # stable sort keeps P before U


def test_suite_per_case_fields_present(R):
    report = R.eval_suite([hallucinated_case(R)], k=2)
    row = report["cases"][0]
    for key in ("index", "question", "context_precision", "context_recall",
                "faithfulness", "answer_relevancy", "unsupported_claims",
                "uncovered_sentences"):
        assert key in row
    assert row["unsupported_claims"] == HALLUCINATIONS
    assert row["uncovered_sentences"] == []


def test_suite_deterministic_across_runs(R):
    cases = [perfect_case(R), hallucinated_case(R),
             dragged_precision_case(R), uncovered_recall_case(R)]
    first = R.eval_suite(cases, k=3)
    second = R.eval_suite(cases, k=3)
    third = R.eval_suite([perfect_case(R), hallucinated_case(R),
                          dragged_precision_case(R), uncovered_recall_case(R)], k=3)
    assert first == second
    assert first == third
