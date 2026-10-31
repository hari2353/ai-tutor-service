# Continuous & Online Learning: Concept Drift, Incremental Updates, and Feedback Loops

> **Track:** T03 Classical ML · **Time:** 2h · **Prereqs:** `T03-classical-ml`, `T09-model-monitoring` · **Updated:** 2026-10-31
> **Module id:** `T03-continuous-learning` · **Tags:** production, ml, advanced

## The 30-second version

Static models degrade. The world changes (concept drift), the data distribution shifts (data drift), and the model's predictions become stale. **Continuous learning** is the practice of updating models in production without full retraining. The techniques: (1) **online learning** — update model weights incrementally as new data arrives (SGD with learning rate decay). (2) **Incremental retraining** — periodically retrain on recent data (daily/weekly). (3) **Shadow deployment** — run the new model alongside the old, compare, then switch. (4) **Champion-challenger** — A/B test models in production. (5) **Feedback loops** — collect user feedback (thumbs up/down, corrections) and use it as training signal. The key insight: continuous learning is not about the algorithm (SGD is simple) — it's about the *infrastructure* (data pipelines, model versioning, rollback, monitoring, and the feedback collection mechanism). The 2026 reality: most production ML systems use scheduled retraining (daily/weekly) with shadow deployment, not true online learning, because online learning is unstable (catastrophic forgetting, learning rate sensitivity) and hard to debug.

## Why this gets asked

Because "model degradation in production" is the #1 operational problem in ML, and interviewers want to know if you have a strategy beyond "retrain monthly." They probe: "your model's accuracy dropped 5% last week — what do you do?" (wrong answer: "retrain"; right answer: "diagnose drift type (data vs concept), check if it's a distribution shift or a bug, then decide: retrain on recent data, update features, or rollback"). Also probed: "online learning vs batch retraining?" (answer: online learning updates incrementally (fast, unstable, hard to debug); batch retraining is periodic (stable, debuggable, but stale). Most production systems use batch retraining with shadow deployment). The principal-level probe: "design a continuous learning system for a recommendation model" (answer: feedback collection → data pipeline → scheduled retraining → shadow deployment → A/B test → gradual rollout → monitoring → rollback).

## Lineage: past → present → future

**What came before.** Static models (2010s): train once, deploy, hope. The pain: models degrade silently — accuracy drops, users complain, nobody knows why. The first fix: scheduled retraining (weekly/monthly). Better but still reactive. Online learning (SGD, 1950s origin) was the theoretical answer but was unstable in practice (catastrophic forgetting, learning rate sensitivity).

**Where it stands now.** The 2026 landscape: (1) **Scheduled retraining** is the default (daily/weekly/monthly, depending on data velocity). (2) **Shadow deployment** (run new model alongside old, compare, switch) is standard for high-risk models. (3) **Champion-challenger** (A/B test) is standard for user-facing models. (4) **Feedback loops** (thumbs up/down, corrections, implicit signals) feed the retraining pipeline. (5) **True online learning** is rare in production (instability, debugging difficulty) but used in ad-tech and recommendation systems where latency matters. (6) **Feature stores** (T18) enable incremental feature updates without full retraining.

**Where it's heading.** High confidence: scheduled retraining + shadow deployment remains the default. Medium confidence: feedback loops become more sophisticated (implicit signals, LLM-as-judge for quality). Speculative: true online learning becomes practical as catastrophic forgetting solutions (elastic weight consolidation, progressive neural networks) mature, but this is still research-stage.

## Mental model

```
CONTINUOUS LEARNING PIPELINE:

  Production traffic
       │
       ▼
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │ Model serves │────►│ Log preds +  │────►│ Feedback    │
  │ predictions  │     │ features     │     │ collection  │
  └─────────────┘     └──────────────┘     └──────┬──────┘
                                                    │
                                                    ▼
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │ Champion     │◄────│ Shadow       │◄────│ Retrain on  │
  │ (current)    │     │ (new model)  │     │ recent data │
  └──────┬──────┘     └──────────────┘     └─────────────┘
         │
         ▼
  ┌─────────────┐
  │ A/B test     │ → gradual rollout → monitor → rollback if degraded
  └─────────────┘

DRIFT TYPES:
  Data drift: P(X) changes (input distribution shifts)
  Concept drift: P(Y|X) changes (relationship between features and target changes)
  Label drift: P(Y) changes (target distribution shifts)
```

## Recognition heuristics

- **"Model accuracy dropped 5% last week"** → diagnose drift type (data vs concept), check if distribution shift or bug, then: retrain on recent data, update features, or rollback.
- **"Online learning vs batch retraining?"** → Online: incremental, fast, unstable, hard to debug. Batch: periodic, stable, debuggable, but stale. Most production uses batch + shadow deployment.
- **"How do you collect training signal from production?"** → Explicit feedback (thumbs up/down, corrections) + implicit feedback (clicks, dwell time, conversions) + LLM-as-judge for quality scoring.
- **"How do you deploy a new model safely?"** → Shadow deployment (run alongside, compare) → A/B test (champion-challenger) → gradual rollout (1% → 10% → 50% → 100%) → monitor → rollback.

## Common bugs and how these get shipped wrong

- **Retraining on stale data.** The model was trained on 6-month-old data; retraining on the same data gives the same model. Fix: use recent data (last 30 days) with exponential decay weighting.
- **No shadow deployment.** Switching directly to a new model without comparing can cause regressions. Fix: always shadow-deploy first, compare metrics, then switch.
- **No rollback plan.** When the new model is worse, you need to revert instantly. Fix: keep the previous model version warm, use feature flags for model selection.
- **Catastrophic forgetting in online learning.** The model forgets old patterns when learning new ones. Fix: replay buffer (mix old + new data), elastic weight consolidation, or just use batch retraining.
- **Feedback loop contamination.** The model's predictions influence the training data (e.g., a recommendation model shows items, users click them, clicks become training labels). Fix: use exploration (show diverse items), log counterfactuals, use inverse propensity scoring.

## Interview questions

1. **"Your model's accuracy dropped 5% last week — what do you do?"** Answer: (1) Check monitoring dashboards (data drift, concept drift, latency, error rate). (2) Determine if it's a distribution shift (new user segment, seasonal change) or a bug (data pipeline, feature engineering). (3) If drift: retrain on recent data with shadow deployment. If bug: fix the pipeline, retrain. (4) If unclear: rollback to previous model version.
2. **"Design a continuous learning system for a recommendation model."** Answer: feedback collection (clicks, dwell time, conversions) → data pipeline (daily aggregation, feature engineering) → scheduled retraining (weekly, on recent 30 days) → shadow deployment (compare new vs old) → A/B test (champion-challenger, 10% traffic) → gradual rollout → monitoring (accuracy, latency, business metrics) → rollback if degraded.
3. **"Online learning vs batch retraining — when do you use each?"** Answer: Online learning (incremental SGD) for ad-tech (click prediction, where latency matters and data is high-volume). Batch retraining (scheduled, full retrain) for most ML systems (stable, debuggable, reproducible). Most production systems use batch retraining + shadow deployment.

## Red flags that fail you

- "Just retrain the model" without diagnosing the drift type.
- No shadow deployment or rollback plan.
- "Online learning is always better" — it's unstable and hard to debug.
- Not collecting feedback (no training signal for retraining).
- Not monitoring for drift (silent degradation).

## Cheat card

- Drift types: data drift (P(X) changes), concept drift (P(Y|X) changes), label drift (P(Y) changes).
- Online learning: incremental SGD, fast but unstable. Batch retraining: periodic, stable, debuggable.
- Shadow deployment: run new model alongside old, compare, then switch.
- Champion-challenger: A/B test models in production.
- Gradual rollout: 1% → 10% → 50% → 100% with monitoring.
- Feedback loops: explicit (thumbs up/down) + implicit (clicks, dwell time) + LLM-as-judge.
- Rollback: keep previous model warm, use feature flags for model selection.

## Sources

- [Machine Learning Engineering (Andriy Burkov)](https://www.mlebook.com/wiki/doku.php) — accessed 2026-10-31
- [Google — Hidden Technical Debt in Machine Learning Systems](https://papers.nips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html) — accessed 2026-10-31
- [Evidently AI — ML Monitoring and Observability](https://www.evidentlyai.com/) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Continuous/Online Learning identified as a gap (no dedicated module).
