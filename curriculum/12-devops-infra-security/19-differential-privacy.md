# Differential Privacy: Epsilon, Mechanisms, and the Privacy-Utility Tradeoff

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** `T03-classical-ml` · **Updated:** 2026-10-31
> **Module id:** `T12-differential-privacy` · **Tags:** security, privacy, critical

## The 30-second version

Differential privacy (DP) is a mathematical framework for quantifying and limiting the privacy loss when releasing information about a dataset. The core idea: adding carefully calibrated noise to a computation so that the output is (almost) the same whether or not any single individual's data is included. The privacy budget is epsilon (ε): smaller ε = more privacy = more noise = worse utility. The two fundamental mechanisms: **Laplace mechanism** (add Laplace noise to numeric queries) and **Gaussian mechanism** (add Gaussian noise, for (ε,δ)-DP). DP is used in production: Apple (telemetry, emoji suggestions), Google (Chrome usage stats), US Census (2020 census). The key insight for interviews: DP is not "anonymization" — it's a mathematical guarantee about the worst-case privacy loss, and the tradeoff between privacy (ε) and utility (accuracy) is quantifiable and unavoidable.

## Why this gets asked

Because privacy regulations (GDPR, CCPA, HIPAA) make data handling a legal requirement, and DP is the only mathematically rigorous privacy framework. Interviewers probe: "how do you share aggregate statistics without leaking individual data?" (answer: differential privacy with calibrated noise). Also probed: "what's the difference between anonymization and differential privacy?" (anonymization = remove identifiers, fails under re-identification attacks; DP = mathematical guarantee regardless of auxiliary information). The principal-level probe: "your healthcare app needs to share patient outcome statistics with researchers — design the privacy mechanism" (answer: DP with per-query epsilon budget, Laplace/Gaussian mechanism, composition for multiple queries, privacy accountant for budget tracking).

## Lineage: past → present → future

**What came before.** Anonymization (2000s): remove names, SSNs, etc. The pain: re-identification attacks (Sweeney 2000: 87% of Americans uniquely identifiable by ZIP+DOB+gender; Netflix Prize 2008: de-anonymized by matching with IMDB ratings). k-anonymity and l-diversity were attempts to fix this but failed against sophisticated adversaries. The need for a mathematical privacy guarantee, not just "remove identifiers," drove DP's development (Dwork et al., 2006).

**Where it stands now.** DP is the gold standard: Apple (telemetry, emoji frequency), Google (Chrome usage stats, RAPPOR), US Census (2020 census, ε=1-10 per table), Microsoft (SmartNoise library). The 2026 landscape: DP is standard for aggregate statistics but still emerging for ML training (DP-SGD, used by Apple and Google for on-device models). The live disagreement: the privacy-utility tradeoff — at ε=1, the noise is large enough to significantly degrade model accuracy for small datasets; at ε=10, privacy is weak but utility is good. The "right" ε depends on the threat model and regulatory requirements.

**Where it's heading.** High confidence: DP becomes standard for aggregate statistics in regulated industries. Medium confidence: DP-SGD becomes practical for on-device ML (Apple, Google already use it). Speculative: DP becomes a regulatory requirement (EU AI Act may mandate DP for high-risk AI systems), but the enforcement is still unclear.

## Mental model

```
DIFFERENTIAL PRIVACY (the core guarantee):

For any two datasets D and D' that differ in one individual's data,
and for any output S:
  P[M(D) ∈ S] ≤ e^ε · P[M(D') ∈ S] + δ

ε = privacy budget (smaller = more privacy)
δ = failure probability (usually 1/n² or smaller)

MECHANISMS:

Laplace (for (ε,0)-DP):
  noise ~ Laplace(0, sensitivity/ε)
  sensitivity = max change in query output when one person's data changes

Gaussian (for (ε,δ)-DP):
  noise ~ N(0, σ²) where σ = sensitivity · sqrt(2 ln(1.25/δ)) / ε

COMPOSITION (privacy budget across multiple queries):
  Basic: ε_total = ε₁ + ε₂ + ... + εₖ (linear)
  Advanced (Rényi DP): ε_total ≈ sqrt(k) · ε (much better for many queries)

DP-SGD (for ML training):
  1. Clip gradients to bound sensitivity
  2. Add Gaussian noise to clipped gradients
  3. Track privacy budget with accountant (RDP or GDP)
```

## Recognition heuristics

- **"Share aggregate statistics without leaking individual data"** → differential privacy (Laplace for counts/sums, Gaussian for complex queries).
- **"How much noise to add?"** → sensitivity / ε. Sensitivity = max change in output when one person's data is added/removed. For counting queries, sensitivity = 1.
- **"Multiple queries on the same data"** → composition: ε_total = sum of individual ε's (basic) or sqrt(k)·ε (advanced). Track with a privacy accountant.
- **"Train a model with privacy guarantees"** → DP-SGD: clip gradients, add noise, track budget. Used by Apple, Google for on-device models.

## Common bugs and how these get shipped wrong

- **Treating anonymization as privacy.** Removing names/SSNs doesn't prevent re-identification. DP provides a mathematical guarantee regardless of auxiliary information.
- **Not tracking the privacy budget.** Each query spends ε; running 100 queries at ε=1 gives ε_total=100 (no privacy). Use a privacy accountant to track cumulative spend.
- **Setting ε too high.** ε=10 provides weak privacy (roughly 22,000x more likely to include/exclude an individual). ε=1 is moderate. ε=0.1 is strong but utility suffers.
- **Ignoring sensitivity.** The noise scale depends on sensitivity (max change per individual). For counting queries, sensitivity=1. For averages, sensitivity=1/n. For complex queries, sensitivity can be large.
- **DP-SGD without gradient clipping.** Without clipping, a single outlier can dominate the gradient, making the noise ineffective. Clip gradients to a fixed norm before adding noise.

## Interview questions

1. **"How do you share aggregate statistics without leaking individual data?"** Answer: differential privacy. Add Laplace noise (for counts/sums) or Gaussian noise (for (ε,δ)-DP) calibrated to sensitivity/ε. Track the privacy budget across queries with a privacy accountant.
2. **"What's the difference between anonymization and differential privacy?"** Answer: anonymization removes identifiers (fails under re-identification). DP provides a mathematical guarantee: the output is (almost) the same whether or not any individual's data is included, regardless of auxiliary information.
3. **"How does DP-SGD work?"** Answer: (1) Clip gradients to bound sensitivity. (2) Add Gaussian noise to clipped gradients. (3) Track privacy budget with an accountant (RDP or GDP). Used by Apple and Google for on-device models. Tradeoff: more noise = more privacy but worse model accuracy.

## Red flags that fail you

- "Anonymization = privacy" — re-identification attacks prove otherwise.
- Not knowing the privacy budget (ε) and its tradeoff with utility.
- Not tracking composition (cumulative ε across multiple queries).
- "DP-SGD is just adding noise to gradients" — without clipping, the noise is ineffective.
- Not knowing the difference between (ε,0)-DP (Laplace) and (ε,δ)-DP (Gaussian).

## Cheat card

- DP guarantee: P[M(D)∈S] ≤ e^ε · P[M(D')∈S] + δ. ε = privacy budget.
- Laplace mechanism: noise ~ Laplace(0, sensitivity/ε). For (ε,0)-DP.
- Gaussian mechanism: noise ~ N(0, σ²). For (ε,δ)-DP.
- Composition: ε_total = sum (basic) or sqrt(k)·ε (advanced/Rényi).
- DP-SGD: clip gradients → add Gaussian noise → track budget.
- Epsilon guide: ε=0.1 (strong), ε=1 (moderate), ε=10 (weak but useful).
- Sensitivity: counting queries = 1. Averages = 1/n. Complex queries = larger.

## Sources

- [Differential Privacy (Dwork & Roth, 2014)](https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf) — accessed 2026-10-31
- [Apple Differential Privacy (Technical Overview)](https://www.apple.com/privacy/docs/Differential_Privacy_Overview.pdf) — accessed 2026-10-31
- [Google RAPPOR (Randomized Aggregatable Privacy-Preserving Ordinal Response)](https://github.com/google/rappor) — accessed 2026-10-31
- [Opacus: PyTorch library for differential privacy](https://github.com/pytorch/opacus) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Differential Privacy identified as a gap (only 2 incidental mentions).
