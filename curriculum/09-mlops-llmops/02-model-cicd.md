# CI/CD for Models & Prompts, Shadow/Canary, Rollback

> **Track:** T09 MLOps / LLMOps · **Time:** 2.5h · **Prereqs:** T09-tracking-registry
> **Module id:** `T09-model-cicd` · **Tags:** mlops,deployment,shadow,canary,rollback,critical

## The 30-second version

"CI/CD for a model" tests different things than CI/CD for a service — code correctness is table stakes, but the pipeline also has to validate data schema/quality, re-run evaluation against a held-out set, and gate promotion on a metric threshold, not just "the build passed." Shadow deployment runs the new model on 100% of real production traffic in parallel, but its output never reaches the user — only logged for comparison — which gives you paired observations against the same requests the current model sees, canceling out request-level noise and making differences detectable with far less traffic than an unpaired A/B test needs; the cost is doubled inference infrastructure for the shadow window and the fact that a shadow model literally never proves anything about downstream business outcomes since its output never actually influences a user or a decision. Canary deployment routes a genuinely small slice (typically 1-5%, ramping through 20%/50%/100%) of real traffic to the new model and its output does reach users, so it validates actual outcome metrics shadow can't, at the cost of real exposure and needing enough volume at that small percentage to reach statistical significance before ramping further — the two are complementary stages, not competing choices, and a mature pipeline runs shadow first to catch gross regressions cheaply, then canary to validate real-world impact. Rollback for a model is not a code revert: it has to also revert (or version-tag) any downstream cache keyed on model output, ensure the feature computation the rolled-back version expects still matches what the serving pipeline is producing, and confirm every component in the path (serving, cache, preprocessing, batch scoring jobs) actually reverted together — the well-documented failure mode is a "rollback" that reverts the serving container while a stale cache or a still-forward-deployed feature pipeline keeps serving mixed-version behavior with no error, no alert, and no clean signal beyond confused users and diverging metrics.

## Why this gets asked

The interviewer has watched (or caused) a "rollback" that didn't actually roll back — the dashboard says the previous model version is live, the deploy log looks clean, and user complaints keep arriving anyway, because a response cache still held entries computed by the bad version, or a feature pipeline had already moved forward to a schema the rolled-back model wasn't trained to expect. They've also likely shipped a canary that looked fine at 1% traffic, ramped to 50%, and then broke, because 1% of traffic wasn't enough volume to detect a real but rare regression, or the sample at 1% happened to skew toward a request type that didn't expose the bug. They want to hear you treat "did the rollback actually work" and "is the canary result actually significant" as engineering questions with numeric answers, not procedural checkboxes — and to hear you name the specific downstream state (cache, features, batch jobs) that a naive rollback misses.

---

## Lineage: past → present → future

**What came before.** Classic software CI/CD (Jenkins-era, then GitHub Actions/CircleCI, mainstream by the mid-2010s) tests and deploys code: unit tests, integration tests, a build artifact, a deploy. Applied naively to ML, this checks that the training script runs and produces *a* model, but says nothing about whether that model is any good, whether the data it trained on passed a schema/quality check, or whether its evaluation metrics cleared a bar — a model that "builds successfully" in the CI sense can still be a materially worse model than what's currently live, and classic CI/CD has no concept of that failure at all. Early production ML deployment (through the mid-2010s) commonly meant a full-traffic-switch deploy with no staged rollout — the new model either served 100% of traffic immediately or didn't, with no paired-comparison or gradual-exposure mechanism, which meant regressions were discovered only after they'd already affected all users.

**Where it stands now.** "CI/CD for ML" now names a genuinely broader pipeline: continuous integration validates code AND data (schema checks, missing-value/drift detection on incoming training data) AND the model (re-running evaluation against a held-out set, comparing against the current champion's metrics, not just checking the training job exited zero) [CI/CD for Machine Learning — DVC](https://dvc.org/doc/use-cases/ci-cd-for-machine-learning) — accessed 2026-08-03. Tools like CML (Continuous Machine Learning, from Iterative/DVC) make a generic CI runner ML-aware — posting metric comparisons and plots directly as pull-request comments so a model-quality regression is visible in code review the same way a failing unit test would be, and can provision cloud GPU runners on demand for the training step itself. Shadow and canary deployment are both mature, widely-used patterns now, and the live disagreement isn't whether to use staged rollout (broadly settled: yes) but how to sequence and combine shadow and canary, and how much statistical rigor a given team actually applies before trusting a canary result — many teams still ramp canary traffic on gut feel ("looks fine, bump it to 20%") rather than a pre-registered significance threshold, which is a real, common gap between what's "best practice" and what's actually deployed. Rollback has matured from "redeploy the previous container" to an explicit checklist covering every stateful component in the request path — serving, response/feature caches, preprocessing, batch/offline scoring jobs — precisely because enough teams have been burned by a rollback that looked complete on the deploy dashboard while a stale cache or an already-forward-migrated feature pipeline kept serving inconsistent behavior.

**Where it's heading.** High confidence: data and model validation gates keep getting stricter and more automated as teams get burned by "the build passed but the model regressed" incidents — expect schema/drift checks and automated metric-threshold gating to become as unremarkable a CI step as a linter is for code today. Medium confidence: LLM-specific CI/CD (evaluating prompts and fine-tunes against an eval suite, not just classical metrics) is converging toward the same shadow/canary/rollback discipline as classical model deployment, treating a prompt or fine-tune change exactly like a model version change (see `T09-tracking-registry`'s prompt registry section) rather than as a lower-stakes text edit — this convergence is actively happening but not yet universal practice. Speculative: fully automated canary-ramp decisions (a controller that advances traffic percentage based on a live statistical test crossing a pre-registered significance threshold, halting or rolling back automatically on a negative signal) replacing today's mostly-manual "someone watches a dashboard and decides to bump the percentage" — a few platforms are building toward this, but manual judgment in the ramp decision remains the norm as of 2026.

---

## Mental model

```
SHADOW vs CANARY: what traffic sees, and why the statistics differ

  SHADOW:  100% of real requests --> [CURRENT MODEL] --> response to user
                                  \-> [NEW MODEL]     --> logged only, NEVER served

           Same request hits both models -> PAIRED observations.
           Shared request-level noise cancels out in the paired difference.
           Detects prediction-distribution differences with LESS traffic
           needed than an unpaired comparison -- but proves NOTHING about
           actual business/outcome impact, because the new model's output
           never influenced a real decision.

  CANARY:  100% of real requests --> ROUTER
                                       |-- 95-99% --> [CURRENT MODEL] --> user
                                       \-- 1-5%   --> [NEW MODEL]     --> user (REAL)

           New model's output DOES reach users at the canary percentage.
           Validates real outcome metrics shadow cannot (conversion, revenue,
           actual user-facing error rate) -- at the cost of real exposure
           and needing enough volume AT THAT SMALL PERCENTAGE to reach
           significance before ramping to 20% / 50% / 100%.

MATURE PIPELINE: run BOTH, in sequence, not either/or
  shadow (catch gross regressions cheap, zero user exposure)
    --> canary at 1-5% (validate real outcome impact, small blast radius)
      --> ramp 20% -> 50% -> 100% (each step gated on a significance check,
                                     not gut feel)

ROLLBACK: reverting the SERVING CONTAINER is necessary but NOT SUFFICIENT

  [Serving: model v7 -> v6]   <- the part everyone remembers to revert
  [Response/feature cache: still holds entries computed by v7's outputs]  <- FORGOTTEN
  [Feature pipeline: already forward-migrated to a schema v6 wasn't trained on]  <- FORGOTTEN
  [Batch/offline scoring jobs: still running against v7]  <- FORGOTTEN

  Result: dashboard says "v6 is live," deploy log is clean, user complaints
  keep arriving -- VERSION DRIFT, different requests served by an
  inconsistent mix of what the rollback intended and what's actually running.
```

---

## How it actually works

### What "CI" actually validates for a model, beyond the build

A CI pipeline for a model needs three validation layers classic software CI doesn't have, and skipping any one of them is where "the build passed" and "the model is fine" diverge:

1. **Data validation** — schema checks (are the expected columns present, right types), missing-value and null-rate checks, and drift/anomaly detection on the incoming training data, run *before* training starts. A schema check catching a silently-added or -renamed column is the difference between a clear CI failure and a model silently training on garbage or crashing at serving time months later.
2. **Model validation** — re-run evaluation against a fixed, versioned held-out set (not the training set) and compare the resulting metrics against the current champion's metrics on the same set, not just against an absolute threshold — a model that "passes" an absolute AUC bar of 0.85 but is worse than the currently-deployed 0.90 is a regression a threshold-only check would miss entirely.
3. **Input/output contract validation** — the new model's expected input schema and output shape/range still match what the serving code and downstream consumers expect; a model retrained with an extra feature or a changed output scale can pass every accuracy metric while silently breaking the serving contract.

```yaml
# untested sketch — CI stage gating model promotion on evaluation metrics, not just build success
model-validation:
  stage: validate
  script:
    - python validate_data_schema.py --data $TRAIN_DATA_PATH --schema schemas/v3.json
    - python train.py --data $TRAIN_DATA_PATH --output model.pkl
    - python evaluate.py --model model.pkl --eval-set data/eval_fixed_v3.parquet --output metrics.json
    - python compare_to_champion.py --new-metrics metrics.json --registry-alias champion --min-delta 0.0
    # compare_to_champion exits non-zero (failing the pipeline) if the new
    # model's metric is not >= the current champion's metric on the SAME
    # fixed eval set -- this is the actual gate, not "did training finish"
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
```

CML posts the metric comparison and any generated plots directly as a pull-request comment, making a model-quality regression visible in code review the same way a failing unit test is — a genuine improvement over "the metrics are in a dashboard nobody checks before merging" [CML (DVC) — Arize AX Docs](https://arize.com/docs/ax/machine-learning/machine-learning/integrations-ml/integrations/ci-cd-cml) — accessed 2026-08-03.

### Shadow deployment: the paired-observation statistical advantage, and its real limit

The mechanical setup: every real production request is sent to both the current model and the new model, but only the current model's response is returned to the user — the new model's prediction is logged for offline comparison. Because both models see the *exact same request*, the comparison is **paired**: any noise from request-to-request variation (different users, different times of day, different input distributions within the sample) is shared between both models' observations on that request and cancels out when you compute the paired difference, rather than adding variance the way an unpaired comparison (two different groups of requests, as in a canary or classic A/B test) would. This is the concrete reason shadow deployment can detect a meaningful prediction-distribution difference with substantially less total traffic than an equivalent unpaired test needs to reach the same statistical power [Shadow Deployment for ML Models — Atlan](https://atlan.com/know/shadow-deployment-for-ml-models/) — accessed 2026-08-03.

**What shadow cannot do, no matter how much traffic you run through it:** validate whether a prediction difference actually translates into a better business outcome. A shadow model's output never reaches a user, never influences a decision, never gets acted on — so you can conclusively show "the new model's predictions differ from the current model's on 8% of requests, in this direction," but you cannot conclude "and that difference improves conversion/revenue/user satisfaction," because nothing about the shadow run ever tested that causal path. This is the specific reason shadow is a *precursor* to canary, not a replacement for it — shadow answers "is the new model different, and is that difference gross-regression-shaped," canary answers "does routing real users to it actually help or hurt."

**Real costs**, not token caveats: shadow deployment doubles inference infrastructure for the entire shadow window (both models processing 100% of traffic), adds real architectural complexity in the request-mirroring/logging path, and carries a specific risk that shadow conditions don't fully replicate production — a shadow model evaluated against logged features computed at request time can diverge from what the model would actually see if truly serving traffic, if there's any timing-dependent feature computation the shadow harness doesn't faithfully reproduce [Shadow deployment vs. canary release of ML models — Qwak/JFrog ML](https://www.qwak.com/post/shadow-deployment-vs-canary-release-of-machine-learning-models) — accessed 2026-08-03.

### Canary deployment: real exposure, and the statistical rigor most teams skip

Canary routes a genuinely small, real slice of production traffic — commonly starting at 1%, ramping through 5%, 20%, 50%, to 100% — to the new model, and that traffic's users actually receive the new model's output. This is what lets canary validate outcome metrics shadow structurally cannot: actual conversion, actual user-facing error rate, actual downstream business impact, because the new model's predictions genuinely influenced real decisions for that slice of users.

The statistical rigor gap that separates a mature canary process from a naive one: **at 1% traffic, how much volume do you actually need before the difference you're seeing is signal rather than noise?** A team watching a dashboard and deciding "looks fine, bump to 20%" after an hour, with no pre-registered minimum sample size or significance threshold, is running an unpaired comparison on a small, possibly-unrepresentative slice and calling it validated. The honest process: define the metric you're gating on (a specific outcome metric, not "vibes"), a minimum detectable effect size you actually care about, and the sample size needed at the canary percentage to detect that effect with acceptable statistical power *before* starting the canary — then don't ramp until that sample size is actually reached and the test crosses the pre-registered significance threshold, not before. Skipping this and ramping on gut feel is the single most common gap between textbook canary process and what teams actually do in practice.

```python
# untested sketch — a canary gate that actually checks significance before ramping,
# instead of a human eyeballing a dashboard
from scipy import stats

def canary_ramp_decision(control_outcomes, canary_outcomes, min_sample_size=5000, alpha=0.05):
    if len(canary_outcomes) < min_sample_size:
        return "hold", f"only {len(canary_outcomes)}/{min_sample_size} samples collected"

    stat, p_value = stats.ttest_ind(control_outcomes, canary_outcomes)
    if p_value > alpha:
        return "hold", f"difference not significant (p={p_value:.3f}), need more samples or effect is truly null"

    if canary_outcomes.mean() < control_outcomes.mean():
        return "rollback", f"canary significantly WORSE (p={p_value:.3f})"

    return "ramp", f"canary significantly better (p={p_value:.3f}), safe to increase traffic %"
```

### Rollback: reverting the model is necessary, not sufficient

The specific, well-documented failure mode: "some of the nastiest ML incidents happen not during the bad release, but during the false sense of safety that follows it, where the dashboard says the previous model is live and the deploy log looks clean, yet user complaints keep coming in" — because a rollback that only reverts the serving container leaves other stateful components in the request path still reflecting the bad version [11 production lessons from a model rollback that didn't rollback — Medium](https://medium.com/@komalbaparmar007/11-production-lessons-from-a-model-rollback-that-didnt-rollback-669629360815) — accessed 2026-08-03. The components a complete rollback checklist needs to cover, beyond the serving container itself:

- **Response/prediction caches** — if a cache is keyed on request features and stores the model's output, a rollback that reverts the model but leaves cached entries computed by the bad version means users hitting a cache hit still get bad-version behavior indefinitely, or until those specific cache keys naturally expire. The fix pattern: version-tag every cache entry with the model version that produced it, and either invalidate on version change or make the cache key itself include the version, so a rollback naturally stops serving stale-version entries without needing an explicit flush (though an explicit flush is the safer, more deterministic option when speed matters more than cache-warm efficiency).
- **Feature pipelines** — if the bad model's replacement (the rolled-back-to version) was trained expecting a specific feature schema, and the feature computation pipeline has since moved forward (a new feature added, a transformation changed) to support the *bad* version, rolling back the model without also rolling back or version-gating the feature pipeline means the "old" model now receives features it was never trained on — a **training-serving skew** introduced by the rollback itself (see `T09-feature-stores`).
- **Batch/offline scoring jobs** — any scheduled batch job (nightly re-scoring, a recommendation refresh) that was already using the bad model needs its own explicit rollback; it's a common miss because batch jobs aren't in the same deploy pipeline as the live serving path and a "rollback" that only touches the real-time endpoint silently leaves batch jobs on the bad version.
- **Version-aware monitoring** — logging which model version actually served each individual request (not just "which version is nominally deployed") is what makes **version drift** (different requests served by an inconsistent mix of versions across serving/cache/batch) detectable at all; without per-request version logging, drift is invisible until predictions diverge visibly enough for someone to notice by hand.

---

## Build it from scratch

A minimal shadow-and-canary harness demonstrating the paired-comparison logging and a significance-gated ramp decision together:

```python
# untested sketch — shadow logging + canary gate, the shape worth writing cold
import random
import logging

def handle_request(request, current_model, new_model, canary_pct=0.0, shadow=True):
    current_output = current_model.predict(request)

    if shadow:
        # paired observation: SAME request, both models, only current is served
        new_output = new_model.predict(request)
        logging.info({
            "request_id": request.id,
            "current_output": current_output,
            "shadow_output": new_output,
            "diverged": current_output != new_output,
        })
        return current_output   # user ALWAYS gets current model's output in shadow mode

    if random.random() < canary_pct:
        output = new_model.predict(request)
        logging.info({"request_id": request.id, "served_by": "canary", "output": output,
                       "model_version": new_model.version})
        return output   # user genuinely receives the new model's output

    output = current_model.predict(request)
    logging.info({"request_id": request.id, "served_by": "control", "output": output,
                   "model_version": current_model.version})
    return output

def rollback(target_version, cache, feature_pipeline, batch_scheduler):
    # a real rollback touches every stateful component in the path, not just
    # the serving container -- this is the checklist, made explicit as code
    serving.set_active_version(target_version)          # 1. serving
    cache.invalidate_entries_not_matching_version(target_version)  # 2. cache
    feature_pipeline.pin_schema_for_version(target_version)        # 3. features
    batch_scheduler.set_model_version(target_version)              # 4. batch jobs
    logging.warning(f"rollback to {target_version} completed across serving, cache, features, batch")
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Canary "looked fine" at 1% for an hour, then broke at 20% | Ramped on gut feel, not a pre-registered significance threshold and minimum sample size — 1% traffic for an hour didn't have the volume to detect a real but rare regression | Define the outcome metric, minimum detectable effect, and required sample size *before* starting canary; gate every ramp step on an actual significance test, not a dashboard glance |
| Dashboard shows the rolled-back model version live, but user complaints continue | A response/feature cache still holds entries computed by the bad version, or a batch scoring job wasn't included in the rollback | Version-tag cache entries and invalidate on version mismatch; include every batch/offline job explicitly in the rollback checklist, not just the live serving endpoint |
| A rolled-back model behaves worse than it did before the bad release, even though it's the "same" version | The feature pipeline moved forward to support the bad version's schema and wasn't rolled back with the model — training-serving skew introduced by the rollback itself | Version-gate the feature pipeline alongside the model, or maintain schema compatibility windows so an older model version still receives features in the shape it was trained on |
| "The build passed" but the deployed model is measurably worse than the previous one | CI validated that training completed and code ran, but never compared the new model's metrics against the current champion's metrics on a fixed eval set | Add an explicit metric-comparison gate (new model's held-out metric >= current champion's, same fixed eval set) as a required CI stage, not just a training-completion check |
| Shadow deployment shows the new model diverges from the current one on 8% of requests, and the team ships it anyway based on that alone | Conflating "shadow proved a difference exists" with "shadow proved the difference is good" — shadow cannot validate outcome impact, only that a difference exists | Treat shadow as a precursor gate (catch gross regressions cheaply) and require canary with real outcome metrics before any full rollout decision |
| Different requests get inconsistent predictions with no clear pattern, hard to reproduce | Version drift — serving, cache, and batch jobs are running an inconsistent mix of model versions with no per-request version logging to detect it | Log which exact model version served each individual request; treat version-aware monitoring as a required observability signal, not optional |
| A prompt/fine-tune "hotfix" shipped straight to production with none of this rigor | Treated as a low-stakes text edit rather than a model version change subject to the same shadow/canary/rollback discipline | Route prompt and fine-tune changes through the same registry-gated, evaluated promotion pipeline as any other model version (`T09-tracking-registry`) |

---

## Tradeoffs & when NOT to use it

- **Don't run shadow deployment as your only validation step before a full rollout.** It structurally cannot validate business-outcome impact — a prediction-distribution difference is not proof of a better or worse real-world result. Always follow shadow with a real canary before rolling out fully.
- **Don't run canary at a fixed 1% for an arbitrary time window and call it validated.** Define the required sample size for your minimum detectable effect up front; ramping before that sample size is reached is validating on noise, not signal.
- **Don't treat "revert the serving container" as a complete rollback for any system with output-dependent caching or a feature pipeline that could have drifted.** Build and rehearse a rollback checklist covering serving, cache, features, and batch jobs explicitly — an incomplete rollback that looks clean on a dashboard is worse than a visibly-failed one, because it hides the actual problem.
- **Don't apply full CI/CD rigor (shadow, canary, staged rollout) to every model change indiscriminately if the blast radius genuinely doesn't warrant it** — an internal-only, low-stakes batch scoring job with no user-facing exposure doesn't need the same staged-rollout ceremony as a customer-facing real-time model; match the process to the actual risk, not a one-size-fits-all checklist applied reflexively.
- **Don't skip data/model validation gates in CI because "the training script hasn't changed."** A silently-changed upstream data schema or drift in the training data distribution can still produce a materially worse model even with unchanged code — the gate needs to catch that regardless of what triggered the pipeline run.
- **Don't treat prompt or fine-tune changes as exempt from this discipline because they "feel" lower stakes than a full model retrain.** The blast radius of a wording or fine-tune change is frequently just as large as a model swap; route it through the same gated pipeline.

---

## Interview questions

### Q1 — Explain the statistical advantage of shadow deployment over an unpaired A/B test, mechanically.
**Testing:** whether the candidate understands *why* shadow needs less traffic, not just that it does.
**Answer:** Shadow sends the exact same request to both the current and new model, producing paired observations — any noise from request-to-request variation is shared between both models' outputs on that request and cancels out in the paired difference. An unpaired comparison (two separate groups of requests, as in a canary) has to contend with between-group variance on top of the actual model difference, requiring more total samples to reach the same statistical power.
**Follow-up trap:** *"So should you always prefer shadow over canary for validation?"* — no; shadow's statistical efficiency only validates that a prediction difference exists, never whether it improves a real outcome, since the new model's output never reaches a user or influences a decision — canary is required to validate actual business impact, and the two are complementary stages, not substitutes.

### Q2 — What's the concrete cost of running a shadow deployment, beyond "it's more complex"?
**Testing:** specific, not hand-wavy, cost awareness.
**Answer:** Doubled inference infrastructure for the entire shadow window, since both models process 100% of production traffic; real architectural complexity in the request-mirroring and logging path; and a genuine risk that the shadow harness doesn't fully replicate production conditions (timing-dependent feature computation, for example), which can make shadow results diverge from what the model would actually see serving real traffic.
**Follow-up trap:** *"How would you decide the shadow window's duration?"* — long enough to accumulate sufficient paired samples to detect the smallest prediction-distribution difference you actually care about, and to cover any known cyclical traffic patterns (day-of-week, seasonal) that could otherwise bias the comparison toward an unrepresentative slice of traffic.

### Q3 — A canary at 1% traffic "looks fine" after an hour. What do you check before approving a ramp to 20%?
**Testing:** whether statistical rigor is a reflex, not an afterthought.
**Answer:** Whether the accumulated sample size at 1% actually reaches the pre-registered minimum needed to detect the smallest effect size you care about, and whether the outcome metric's difference between canary and control crosses a defined significance threshold — not whether a dashboard "looks fine" to a human glancing at it. If the sample size requirement wasn't defined before starting the canary, that's itself a process gap to flag before approving any ramp.
**Follow-up trap:** *"The sample size is sufficient and the result isn't statistically significant. Do you ramp?"* — a non-significant result with adequate sample size is meaningfully different from an inconclusive one due to insufficient data — it suggests the true effect (if any) is smaller than your minimum-detectable-effect threshold, which is itself useful information; whether to ramp depends on whether "no meaningful difference" is an acceptable outcome for this specific change (a refactor with no expected behavior change) versus a red flag (a change explicitly intended to improve the metric that shows no improvement).

### Q4 — Design a rollback checklist for a real-time recommendation model with a response cache and a nightly batch re-scoring job. What does a naive rollback miss?
**Testing:** whether "rollback" is understood as a multi-component operation.
**Answer:** A naive rollback reverts only the serving container to the previous model version. The full checklist needs: (1) serving container reverted, (2) the response cache invalidated or version-tagged so stale entries computed by the bad version stop being served, (3) the feature pipeline confirmed to still produce features in the schema the rolled-back version expects (or explicitly rolled back too, if it had moved forward), and (4) the nightly batch re-scoring job's model version explicitly updated, since it's on a separate schedule from the live serving path and won't pick up a serving-only rollback automatically.
**Follow-up trap:** *"The dashboard shows the correct version live in all four places, but complaints continue. What's left to check?"* — per-request version logging to detect actual version drift (a load balancer routing some requests to an instance that hasn't yet picked up the rollback, or a CDN/edge cache still serving stale responses) — "the dashboard says X" and "every actual request was served by X" are different claims, and only per-request version logging distinguishes them.

### Q5 — Why can't shadow deployment validate whether a new model improves business outcomes, no matter how much traffic you run through it?
**Testing:** the conceptual limit of shadow, stated precisely.
**Answer:** The shadow model's predictions are logged but never returned to a user or acted upon — nothing about the shadow run tests the causal path from "the model outputs X" to "a real decision or user action changes as a result." You can conclusively measure that predictions differ and characterize the direction/magnitude of that difference, but you cannot observe whether acting on the new model's predictions actually changes a downstream outcome, because it never gets the chance to.
**Follow-up trap:** *"Could you approximate outcome impact from shadow data using an offline simulation?"* — sometimes, if you have a reliable offline model of how a prediction change maps to outcome (a well-validated uplift/counterfactual model), but that's a separate, nontrivial modeling exercise with its own validation burden — it's not something shadow deployment gives you for free, and treating a plausible-looking offline simulation as equivalent to real canary evidence is a common overreach.

### Q6 — What does CI validate for a model beyond "the training script completed successfully," and why does that distinction matter?
**Testing:** whether the candidate treats "the build passed" and "the model is fine" as the same claim.
**Answer:** Data validation (schema, missing values, drift on the incoming training data) before training even starts; model validation (evaluation against a fixed held-out set, compared against the current champion's metrics on that same set, not an absolute threshold alone); and input/output contract validation (the new model's expected inputs and output shape still match what serving code and downstream consumers assume). A training script exiting successfully proves the code ran, not that the resulting model is as good as or better than what's currently deployed, or that it won't break serving-time assumptions.
**Follow-up trap:** *"Your CI gate compares the new model's metric against an absolute threshold of 0.85 AUC, and it passes. Is that sufficient?"* — no, if the currently-deployed champion is at 0.90 AUC, a 0.85 model that "passes" the absolute bar is still a real regression relative to what's live; the gate needs to compare against the current champion's metric on the same fixed eval set, not just an absolute floor.

### Q7 — Explain training-serving skew introduced by a rollback itself. How does this happen?
**Testing:** a specific, non-obvious failure mode connecting rollback to feature consistency.
**Answer:** If the feature computation pipeline was updated to support a newer model version (say, adding a feature the new model uses), and the model is later rolled back to the older version without also reverting or version-gating the feature pipeline, the "old" model now receives feature vectors in a shape or distribution it was never trained on — the rollback itself introduces a training-serving mismatch that didn't exist before the rollback, even though the model artifact reverted correctly.
**Follow-up trap:** *"How would you design the feature pipeline to avoid this dependency in the first place?"* — version-gate feature schemas explicitly (the pipeline knows which feature schema each model version expects and serves accordingly), or maintain backward-compatible feature additions (new features are additive, old models simply ignore columns they weren't trained on, rather than the pipeline changing existing feature semantics in place) — see `T09-feature-stores` for the broader training-serving consistency problem this is one instance of.

### Q8 — When would shadow deployment specifically be the wrong choice, even though it's lower-risk than canary?
**Testing:** genuine "when NOT to use it" reasoning, not reflexive praise of the safer-sounding option.
**Answer:** When the doubled inference cost for the shadow window is genuinely prohibitive relative to the risk being mitigated (a low-stakes internal tool, or a change with a well-understood, small blast radius), or when the model's behavior is inherently dependent on its output actually being acted upon in a way shadow can't replicate (a bandit or reinforcement-learning-style system whose future inputs depend on its own past actions — shadow can't observe the counterfactual world where its actions actually happened) — in that case, shadow's comparison is measuring something structurally different from what deploying the model would actually produce.
**Follow-up trap:** *"Give a concrete example of the bandit case."* — a contextual bandit for content ranking that adapts based on which items it actually showed and how users responded — a shadow-mode bandit's logged predictions reflect what it *would have* shown, but the real bandit's future decisions depend on the actual exploration/exploitation history from what was truly served, which shadow mode never generates; this is directly relevant to a PySpark/EMR contextual-bandit pipeline where the model's own deployment changes its future training data.

### Q9 — A team ships a "hotfix" prompt change directly to production with no shadow, canary, or eval gate, reasoning that it's "just a prompt." Six hours later, a support-ticket-classification quality regression is discovered. Walk through what should have happened, and how you'd contain the damage now.
**Testing:** applying the whole module's discipline to the LLM-specific case, and incident response under pressure.
**Answer:** The prompt change should have gone through the same registry-gated, eval-validated promotion as any model version change (`T09-tracking-registry`'s prompt registry) — at minimum an eval run against a held-out labeled set before promotion, ideally a canary at small traffic percentage given the blast radius of a classification quality regression. To contain it now: roll back the prompt registry's `production` alias to the prior version (fast, if the registry discipline exists) or revert the code if the prompt was inline (slower); check whether any downstream cache or automated action already acted on the misclassified tickets during the six-hour window and needs manual correction; and add the missing eval gate to the promotion pipeline before any future prompt change, treating the incident as a process gap, not a one-off mistake.
**Follow-up trap:** *"The prompt registry didn't exist, so rollback meant a full code revert and redeploy taking 40 minutes. How do you frame that gap to leadership?"* — the 40-minute rollback time is the direct, quantifiable cost of not having a prompt registry with alias-based promotion, versus what would have been a near-instant alias reassignment — use the incident's actual timeline as the concrete business case for the tooling investment, rather than arguing for it abstractly.

### Q10 — Design the full deployment pipeline for a new fraud-detection model version, from CI through full rollout, including what triggers an automatic rollback.
**Testing:** staff-level synthesis of the entire module as one coherent pipeline.
**Answer:** CI stage: data schema/quality validation on training data, train, evaluate against a fixed held-out set, gate on the new model's metric being >= the current champion's on the same set — fail the pipeline otherwise. If it passes, register the version and tag it `candidate` (`T09-tracking-registry`). Shadow deployment against 100% of real traffic for a defined window sized to detect the smallest prediction-distribution difference worth caring about, logging paired comparisons; halt and investigate if the shadow divergence rate exceeds an expected threshold. If shadow passes, canary at 1% with a pre-registered minimum sample size and significance threshold on the actual outcome metric (fraud catch rate, false-positive rate); ramp through 5/20/50/100% only when each stage's significance check passes, with an automatic halt-and-rollback trigger if any stage shows a statistically significant *regression* in either metric. Rollback, if triggered at any stage, reassigns the `champion` alias back to the prior version, invalidates or version-tags the fraud-scoring response cache, and confirms the feature pipeline still matches what the prior version expects.
**Follow-up trap:** *"What's the one metric most teams forget to gate the automatic rollback on, specifically for fraud detection?"* — false-positive rate, not just fraud-catch-rate (recall) — a new model that catches more fraud but also blocks significantly more legitimate transactions can look like an improvement on the primary metric while being a real regression on user experience and revenue; gate on both, and specifically alert on false-positive rate moving in the wrong direction even if catch rate improves.

### Q11 — What's the actual difference between "rollback" and "roll-forward," and when would you choose roll-forward instead of reverting?
**Testing:** whether the candidate defaults reflexively to rollback without considering the alternative.
**Answer:** Rollback reverts to the last known-good version; roll-forward ships a new fix on top of the current (bad) version rather than reverting. Roll-forward is preferable when the root cause is well-understood and a targeted fix is faster/safer to ship than a full multi-component rollback (especially if the "bad" version's downstream state — cache, features — has already diverged enough that reverting would itself introduce the version-drift problems described above), or when reverting would also lose unrelated improvements that shipped in the same version.
**Follow-up trap:** *"The root cause isn't understood yet, but users are actively affected. Rollback or roll-forward?"* — rollback, almost always, when root cause is unknown — roll-forward requires confidence in a fix, and shipping an unvalidated fix under pressure with an unknown root cause risks compounding the incident; revert to known-good first, then diagnose calmly, then decide whether the next deploy is a proper fix or a re-attempt of the reverted change with the actual issue addressed.

---

## Red flags that fail you

- Treating shadow deployment as sufficient validation on its own, without a canary step to validate real outcome impact.
- Ramping canary traffic based on a dashboard glance rather than a pre-registered sample size and significance threshold.
- Describing "rollback" as only reverting the serving container, with no mention of cache, feature pipeline, or batch job consistency.
- Not knowing that a rollback can itself introduce training-serving skew if the feature pipeline moved forward independently of the model.
- Treating "the CI build passed" as equivalent to "the model is at least as good as what's currently deployed," with no metric-comparison gate against the current champion.
- Applying zero staged-rollout discipline to prompt or fine-tune changes because they "feel" lower stakes than a full model retrain.
- Not being able to name a concrete case (bandit systems) where shadow deployment fundamentally can't replicate real deployment conditions.
- Defaulting to rollback without considering roll-forward as a legitimate alternative when root cause is understood.

---

## Cheat card

```
CI FOR A MODEL != CI FOR CODE
  data validation (schema, nulls, drift) -> train -> eval vs FIXED held-out
  set -> gate: new metric >= CURRENT CHAMPION's metric on SAME set (not an
  absolute threshold alone) -> input/output contract check
  CML (DVC/Iterative): posts metric/plot comparisons as PR comments

SHADOW: 100% real traffic to BOTH models, only CURRENT model's output served.
  PAIRED observations (same request, both models) -> shared noise cancels ->
  detects prediction-distribution diffs with LESS traffic than unpaired.
  CANNOT validate business/outcome impact -- output never acted on.
  Cost: DOUBLED inference infra for the window + mirroring complexity.

CANARY: small REAL slice (1-5% typical) gets new model's ACTUAL output.
  Ramp 1% -> 5% -> 20% -> 50% -> 100%, gated on SIGNIFICANCE not gut feel.
  Define min sample size + min detectable effect BEFORE starting.
  Validates real outcome metrics shadow structurally cannot.

SEQUENCE: shadow (catch gross regressions cheap) THEN canary (validate
  real impact) THEN ramp. Not either/or.

ROLLBACK = 4 COMPONENTS, not just serving:
  1. serving container -> prior version
  2. cache -- version-tag entries or invalidate on version mismatch
  3. feature pipeline -- confirm/pin schema the prior version expects
     (else rollback ITSELF introduces training-serving skew)
  4. batch/offline scoring jobs -- separate schedule, won't auto-follow
     a serving-only rollback

VERSION DRIFT: dashboard says X is live, deploy log clean, complaints
  continue = inconsistent version mix across serving/cache/batch. Only
  PER-REQUEST version logging makes this detectable.

BANDIT EXCEPTION: shadow can't replicate a system whose future inputs
  depend on its own past served actions (contextual bandit) -- logged
  shadow predictions != what the real bandit's exploration history would be.

ROLLBACK vs ROLL-FORWARD: unknown root cause + active user impact ->
  rollback first, diagnose after. Known root cause + fast targeted fix ->
  roll-forward may be safer than reverting already-diverged downstream state.
```

## Sources
- [Shadow Deployment for ML Models: Strategy, Patterns and Risks — Atlan](https://atlan.com/know/shadow-deployment-for-ml-models/) — accessed 2026-08-03
- [Shadow deployment vs. canary release of machine learning models — Qwak/JFrog ML](https://www.qwak.com/post/shadow-deployment-vs-canary-release-of-machine-learning-models) — accessed 2026-08-03
- [CI/CD for Machine Learning — DVC](https://dvc.org/doc/use-cases/ci-cd-for-machine-learning) — accessed 2026-08-03
- [CML (DVC) — Arize AX Docs](https://arize.com/docs/ax/machine-learning/machine-learning/integrations-ml/integrations/ci-cd-cml) — accessed 2026-08-03
- [11 production lessons from a model rollback that didn't rollback — Medium](https://medium.com/@komalbaparmar007/11-production-lessons-from-a-model-rollback-that-didnt-rollback-669629360815) — accessed 2026-08-03
- [Model Version Drift in Production Systems — Interwebicly](https://interwebicly.com/blog/model-version-drift-production-systems) — accessed 2026-08-03
- [Safe ML Model Rollout: Canary Deployments, Shadow Mode, and Rollback — CalibreOS](https://www.calibreos.com/learn/mlsd-canary-deployment) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
