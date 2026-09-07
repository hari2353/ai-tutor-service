# Production notes — LLM-as-judge calibration

## What you'd actually use

| Concern | Real thing | What it adds over yours |
|---|---|---|
| Judge metrics | RAGAS `LLM-as-judge` metrics, DeepEval (`GEval`), promptfoo | prompt templates, structured 1–5 outputs enforced via structured outputs, reference-guided rubrics, statistical CIs on agreement |
| Position-bias / swap test | MT-Bench & Chatbot Arena swap protocol, RAGAS `Contextuality`, promptfoo `judge` assertion | pairwise battles with order-swap built into the leaderboard; tie/margin handling; Elo not raw win-rate |
| Agreement with humans | `ragas` adaptability, DeepEval `GEval` + human ground-truth CSV, cohen_kappa from scikit-learn | sklearn's `cohen_kappa_score(weights='quadratic')`, bootstrap CIs, per-rater analysis (humans disagree too) |
| Regression suite over generations | promptfoo CI matrix, LangSmith evaluation, Langfuse evals, Phoenix experiments | dataset versioning + leaderboards, run-comparison dashboards, alerts, rule-assertions + model-based assertions, webhooks into CI |
| Bias detection beyond position | "Great Chatbot Debaters" lineage, "Benchmarking LLMs as Judges" (Zheng et al. 2023), "Judging LLM-as-a-Judge" | verbosity, self-enhancement, format, and tone biases documented with measured rates on real models |

## What the real ones add over yours

- **Self-preference is real.** Zheng et al. (2023) found models rate answers *they generated* higher; Arena's blind + swap protocol exists precisely because presentation alone shifts ~5-20% of decisions. Your `SelfPreferenceJudge` fake reproduces it without the API bill.
- **You don't need a hard 0.6 kappa threshold.** LLM-judge/human agreement varies by domain and task; realistic values hover ~0.6-0.9 for narrow rubrics, far below on open-ended tasks. Use a distributional cutoff (bootstrap CI), not a point cutoff, before gating anything.
- **Median-of-k grading.** Production judges run the same grade n times and aggregate to reduce noise; `retries: 3, temperature: 0`, and structured outputs enforce the 1-5 int.
- **Human-in-the-loop sampling.** Langfuse and LangSmith both integrate with human-labeled subsets; DeepEval explicitly loads "golden" CSVs. The gold labels come from a *sample*, not a census — your `GoldenJudge` reads ground truth that doesn't exist for the full production stream.
- **Regression ≠ judgment.** promptfoo/LangSmith regression-testing compares *scores over time* (this run vs last run) — the model-vs-judge agreement question (this lab) is separate from the prompt-change question (Lab 04 covers that). Teams that conflate them ship silent quality regressions.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Judge flips identical pairs >10% | presentation order bias | order-swap protocol + position-bias detector (this lab) |
| "Judge looks great on the calibration set, then drifts" | calibration set was one domain / one model family | stratify calibration by domain, model family, length, recency; re-calibrate each time the judged model changes |
| Self-agreement between two LLM judges high but human agreement poor | shared training bias | always keep a human-labeled per-task sample, never judge-judge agreement alone |
| Verbosity bias misread as "model improved" | length tracked quality in the calibration set by luck | deconfound length and gold labels (your length-confounded dataset test) |
| Judge noise between re-runs | nonzero temperature, prompt churn | temperature 0, snapshot judge prompt + model version, median-of-3 |
| Kappa sky-high but useless | degenerate class marginals (all same score) | report class distributions + per-class accuracy alongside kappa; use weighted kappa |
| No idea judge went bad last deploy | no regression CI on judge metrics | freeze a golden calibration set, run judge-calibration in CI, alert on delta (Lab 04 harness) |

## The 3 questions an interviewer asks after you describe this

1. *"You replaced human graders with an LLM judge. How do you know it agrees?"* — sample ~100-300 examples, dual-label human + judge, report Cohen's (weighted) kappa and per-class accuracy, set a gate at e.g. kappa ≥ 0.6 before trusting the judge. Retain a rolling human-labeled set — labels drift as the judged distribution shifts.
2. *"What biases do LLM judges have?" — name the big four | position/order, verbosity/length, self-enhancement/preference-for-own-outputs, and format/tone. Describe the order-swap test for position bias; a deconfounded calibration set for length; a held-out sibling model or blind markers for self-preference.
3. *"When is an LLM judge the wrong choice?"* — when the rubric is high-stakes/subjective or the class distribution is degenerate; when graded outputs are short factual answers where an exact-match or programmatic grader (deterministic, free, monotone) exists; when the judged model family could share biases with the judge.
