# Lab 02: LLM-as-Judge Calibration Harness

**Track:** T08 Eval & Observability · **Time:** 2h · **XP:** 50
**Module:** `T08-llm-as-judge`

**You will build:** a judge-calibration harness — a `Judge` protocol with fully configurable fake judges (position-biased, verbosity-biased, self-preference, gold-label), agreement metrics (per-class accuracy, confusion matrix, Cohen's kappa), a position-bias detector that grades every pair both ways, and a `CalibrationReport` that accepts a judge only if kappa ≥ 0.6 and flip rate ≤ 0.10. No LLM, no network — every judge is a deterministic fake.

**You will be able to answer:** *"You replaced human graders with an LLM judge. How do you know it isn't biased — and what metrics would you show me?"*

## Setup

```bash
cd labs/py/02-judge-calibration
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`Judge` protocol** — `grade(question, candidate_answer, rubric) -> int` in 1–5. A `LabeledExample` is `(question, candidate_answer, gold_score)`.
2. **`GoldenJudge`** — reads `dataset[i].gold_score` for the example at index `i`; constructed `GoldenJudge(dataset)`. This is *your human labels* — the reference an honest judge must agree with.
3. **`PositionBiasedJudge(inner, bonus=1)`** — in pairwise mode (`grade_pair(question, a, b, rubric)`), the answer presented first wins; otherwise delegates to `inner`. This fake models the real position bias: the judge favours whichever answer it reads first.
4. **`VerbosityBiasedJudge(baseline_words=10, bump_per_20_words=1, cap=5)`** — score = `2 + round(min(cap, 2 + wc / 20))`-style: score correlates with word count. Deterministic: same word count, same score.
5. **`SelfPreferenceJudge(style_markers, inner=None)`** — if `candidate_answer` contains any marker phrase from `style_markers` (case-insensitive substring), score = 5; otherwise delegate to `inner` (or 3 if none).
6. **`calibrate(judge, dataset) -> CalibrationReport`** — grades every example once, then:
   - `per_class_accuracy`: for each gold score 1–5 present in the dataset, fraction where the judge gave exactly that gold score (denominator = examples with that gold score).
   - `confusion_matrix`: 5×5 list of lists; rows = gold (1–5), cols = judge (1–5); `matrix[gold-1][judge-1]` counts.
   - `kappa`: Cohen's kappa over (gold, judged) pairs: `1 - (1 - po) / (1 - pe)`; po = observed agreement, pe = Σ gold_marginal × judge_marginal per class. Kappa = 1.0 when pe == po == 1.0 (perfect agreement, degenerate marginals).
7. **`position_bias(judge, pair_questions, rubric) -> PositionBiasReport`** — for each question with its pair `(a, b)`: grade `(a, b)` then `(b, a)`. A *flip* = the two orders disagree on which answer scored higher (a strict `s_first > s_second` vs `s_first < s_second` reversal across the two orderings). `flip_rate = flips / pairs`. `PositionBiasReport` exposes `.flips`, `.total`, `.flip_rate`, `.per_question` (list of `(question, flipped)`) and `.passed` (flip_rate ≤ 0.10).
8. **`CalibrationReport`** — dataclass: `judge_name`, `n`, `per_class_accuracy`, `confusion_matrix`, `kappa`, `bias_report`, plus `.passed` (kappa ≥ 0.6 AND flip_rate ≤ 0.10 when a bias report is attached; kappa alone when it is `None`) and `.fail_reasons` (strings naming exactly what failed).

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Weighted kappa** — score errors 1-off vs 3-off shouldn't count the same; implement quadratic-weighted kappa (the metric medical-imaging evals use).
2. **Per-class calibration curve** — plot judged vs gold means per gold class; a slope < 1 means the judge regresses to the middle (the real "sycophancy" failure mode).
3. **Swap-detection with margin** — a flip only counts if the score *gap* reverses by more than δ; measure how flip rate depends on δ. Real MT-Bench does this by hand.
4. **Self-consistency judge** — grade each example k times with a noisy judge; does averaging improve kappa? (This is why production judges run n=3 and take the median.)
