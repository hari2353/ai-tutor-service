# Production notes — trust calibration

## Where the confidence number comes from

| Signal | How you get it | Notes |
|---|---|---|
| Logprob of the top token / answer | `logprobs` in the API response | The native signal, but chat APIs often hide it (OpenAI exposes top logprobs, Anthropic does not) |
| Verbalized confidence | Ask the model: *"How confident are you (0–100%)?"* | Tian et al. 2023 — First-Person, Multiple-Step, and Closed-Form prompting; better than token probs for hidden-logprob chat models |
| Self-consistency | Sample k answers; agreement fraction | Cheaper to reason about, expensive to run; a strong proxy when the model is a good sampler |

The punchline of the 2023–2024 line (Tian et al.; Xiong et al., *Can LLMs Express Their Uncertainty?*): **verbalized confidence is systematically overconfident**, often worse-calibrated than token probabilities, but it survives when logprobs are hidden — which is why you calibrate after the fact.

## Calibration methods (what you'd actually use)

- **Temperature scaling (Guo et al. 2017, "On Calibration of Modern Neural Networks")** — the workhorse. One parameter T fit on a held-out validation set by minimizing NLL; `p = softmax(z/T)`. Fixes confidence without touching accuracy. Post-hoc, cheap, single-knob — this is the one to name in an interview.
- **Platt scaling / isotonic regression** — for binary or binned outputs; isotonic when the miscalibration shape is non-monotonic.
- **Temperature scaling does NOT fix selective prediction** — it rescales confidences monotonically, so the ranking (and your risk–coverage curve) barely moves. It fixes the confidence *number*; it cannot make the model know what it doesn't know. Miscalibration of the *ordering* needs the model itself to change (or self-consistency / retrieval-grounded verification).
- **ECE is a diagnostic, not a loss** — its binning is non-differentiable. Differentiable surrogates exist (MMCE, soft-binned versions); mention them only if asked.

## Selective prediction in production — when an agent abstains

1. **Define an explicit ABSTAIN / "I don't know" action** in the harness. If the model cannot refuse, it will hallucinate a refusal inside a confident answer — worse, because it looks the same downstream.
2. **Threshold on calibrated confidence, tuned to a risk target** — exactly `tune_threshold(data, target_accuracy)` from this lab: pick the largest threshold whose answered-set accuracy meets the product's error budget. Retune on fresh domain data when the distribution shifts.
3. **Escalate instead of just dropping** — abstention should trigger a fallback path: retrieve more context, ask a clarifying question, route to a human, or degrade to a less confident phrasing. An agent that silently returns nothing is an incident.
4. **The risk–coverage curve is the product trade** — "we answer 92% of questions at 1% error" is a business decision, not a model metric. Plot it in every eval review.
5. **Verbalized ≠ true, but log it** — when the model says "I'm 30% sure", route on it after calibration. Auditing real (confidence, correct) pairs from production traces — which is what `tune_threshold` consumes — is the only calibration signal that survives deployment drift.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Great eval ECE, terrible prod calibration | Calibrated on eval distribution, deployed on another | Recalibrate on production-trace (conf, correct) pairs |
| Agent abstains on everything | Threshold tuned on the wrong slice | Tune per task; check coverage, not just risk |
| Overconfident refusals ("I'm sure I can't answer") | Verbalized confidence overconfident in BOTH directions | Calibrate the abstention head separately |
| Risk–coverage curve flat at high risk | Confidence carries no ordering signal | Self-consistency voting; retrieval-grounded verification |
