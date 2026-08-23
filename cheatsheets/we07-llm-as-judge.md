# LLM-as-Judge and Its Failure Modes; Judge Calibration

> Sprint weekend 7 · source: `curriculum/08-eval-observability/02-llm-as-judge.md`

```
MODES        pointwise (absolute score, drifts across sessions) · pairwise (A vs B,
              most reliable for ranking) · reference-based (vs gold answer, best
              when gold exists, misses valid paraphrases)

BIASES        position:      10-15pt win-rate swing on order swap (Zheng 2023)
              verbosity:     15-30pt preference for longer answers (Wang 2023)
              self-pref:     +10-25% for judge's own model family (arXiv:2410.21819)
              format:        prefers bullets/headers over equal-quality prose
              sycophancy:    shifts toward the framing embedded in the prompt

CALIBRATE     1) 100-300 real traces  2) 2-3 humans label, same rubric
              3) inter-annotator: Cohen's kappa (2 raters) / Krippendorff's alpha (3+)
              4) judge scores same traces  5) judge-vs-human kappa
              THRESHOLDS: <0.4 rubric ambiguous · 0.4-0.6 weak · >0.6 ship · >0.8 strong
              re-calibrate on ANY rubric change or judge model version bump

CHEAP vs      cheap (small/fine-tuned/mini): CI gates, 100% traffic, checklist-style
FRONTIER      frontier (GPT-5/Opus-class): calibration set, hard cases, nuanced judgment

MITIGATIONS   position -> run both orderings, flip = tie
              verbosity -> explicit rubric line + length-bucketed analysis
              self-pref -> judge from a DIFFERENT model family than any candidate
              shared blind spot -> ground judge in external source/gold answer

G-EVAL        CoT-generate-steps -> form-fill -> probability-weighted score
              beats naive "output a number" on correlation w/ human judgment

RED FLAG      judge-vs-human kappa suspiciously high (>0.9) -> audit for collusion
              on a superficial correlate before trusting it
```
