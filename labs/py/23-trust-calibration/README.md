# Lab 23: Trust Calibration — Confidence, Abstention, ECE

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-trust-calibration`

**You will build:** the trust layer of an answer pipeline — expected calibration error (ECE), a tunable abstention policy, and the selective-prediction risk–coverage curve, in one pure-Python file.

**You will be able to answer:** *"Your agent is wrong 8% of the time. Which 8% — and how do you make it refuse exactly those?"*

## Setup

```bash
cd labs/py/23-trust-calibration
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`ece(pairs, n_bins=10)`** — expected calibration error. `pairs` is a list of `(confidence, correct)`. Bin confidences into `n_bins` equal-width bins over [0, 1] (`conf == 1.0` belongs to the last bin). ECE = Σ (bin_size / N) × |mean bin confidence − bin accuracy|. Empty bins contribute nothing.
2. **`AbstentionPolicy(threshold)`** — answer only when confident enough.
   - `should_answer(conf)` → `conf >= threshold`. The boundary is inclusive: 0.5 answers at threshold 0.5.
   - `tune_threshold(data, target_accuracy)` → the **largest** threshold such that accuracy on the answered items (`conf >= threshold`) is `>= target_accuracy`. Candidates are the distinct confidences in `data`; an empty answered set never qualifies. Returns `None` if nothing qualifies. *(A confidence number is only useful if you can turn it into a decision — this is how.)*
3. **`selective_metrics(data, threshold)`** → `{"coverage": fraction answered, "risk": error rate on answered items}`. Risk is `0.0` when nothing is answered. **`risk_coverage_points(data)`** → one `(coverage, risk)` point per distinct confidence threshold, strictest first — the risk–coverage curve.
4. **`classify_with_abstention(classifier, x, policy)`** — `classifier` exposes `.confidence(x)` and `.predict(x)`. Return the prediction when `policy.should_answer(confidence)`, else the sentinel `ABSTAIN` (the string `"ABSTAIN"`).

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **MCE** — maximum calibration error (the worst bin, not the weighted mean). Find a dataset where ECE looks fine but one bin is wildly off. *(Interview: "when does ECE lie?")*
2. **Reliability diagram** — print the per-bin table (mean conf, accuracy, size) as ASCII; eyeball where the overconfidence lives.
3. **Risk–coverage AUC** — integrate the curve (trapezoid) and use it to compare two classifiers with identical accuracy. *(Interview: "same accuracy, different AUC — which one ships?")*
4. **Verbalized vs logprob** — skim Tian et al. 2023 and Xiong et al. 2024, then argue: for a chat model that hides logprobs, how do you get a usable confidence signal?
