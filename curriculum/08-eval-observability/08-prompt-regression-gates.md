# Prompt Regression Gates: Golden Cases, Slices, Thresholds, Auto-Revert

> **Track:** T08 Eval & Observability · **Time:** 2.5h · **Prereqs:** T08-eval-harness, T08-agent-eval · **Updated:** 2026-10-11
> **Module id:** `T08-prompt-regression-gates` · **Tags:** eval, critical
> **Lab:** `labs/py/35-prompt-regression-gates/`

## The 30-second version
Prompt regression gates turn a prompt or model change into a release decision backed by replayable evidence. A case has an input, expected properties, a slice, and a scorer; the runner records a versioned result, then gates both the aggregate score and the slices that can hide inside it. The gate should prefer deterministic checks, keep a held-out set, and report deltas against the last accepted baseline. A green aggregate is not enough: a 98% overall score can conceal a critical locale or safety slice falling from 96% to 70%.

## Why this gets asked
Interviewers have seen a prompt tweak improve a demo and silently break production users. They are testing whether you understand regression control as measurement design, not whether you can name Promptfoo or an LLM judge. The senior failure is shipping a threshold that flakes until engineers ignore it.

## Lineage: past -> present -> future
**What came before.** Prompt changes were reviewed by running five remembered examples in a notebook. The specific pain was irreproducibility: the examples, model version, and pass criterion were not recorded, so a later engineer could not explain why a release was called better. Unit tests for deterministic code did not cover open-ended output behavior.

**Where it stands now.** The durable pattern is eval-as-code: versioned cases, a pinned prompt/model, deterministic assertions where possible, model-graded assertions only for subjective criteria, and CI output broken down by slice. OpenAI Evals provides a framework and registry; Promptfoo documents exact, contains, JSON, cost, latency, and model-assisted assertions. The live disagreement is whether every row must be human-authored. Production teams commonly use synthetic rows for volume, but retain human-reviewed and incident-replay rows as the anchor corpus. [Corpus evidence] in this repo reports a 2,000+ row golden baseline and 200+ tests for the skill-resolution service; the number is personal evidence, not a general benchmark.

**Where it is heading.** High confidence: prompt, dataset, and model versions will be release artifacts, and live failure replays will feed the next golden-set revision. Medium confidence: continuous sampled production evaluation will share infrastructure with monitoring. Speculative: automatic case generation and auto-revert will safely replace human review; generated cases can reproduce the generator's blind spots, so keep a human approval boundary.

## Mental model
```text
case {input, expected, slice} + prompt/model version
                     |
                  runner
                     v
          deterministic + judge scorers
                     |
       overall rate + per-slice rates + diff
                     |
             release gate / rollback
```
The aggregate is a dashboard. The slice minimum is the guardrail. The baseline is the comparison point. A gate with only one of the three is easy to game accidentally.

## How it actually works
Represent each case with a stable id, input, expected properties, and tags such as `locale:de`, `intent:refund`, `risk:high`. The runner records prompt hash, model id, dataset version, output, latency, token counts, and scorer results. Never compare two numbers unless all three versions are known.

For a deterministic scorer, `score = passed_assertions / applicable_assertions`. For a slice `s`, `rate_s = passed_s / n_s`. The release predicate is:
`overall >= overall_min AND every critical slice >= slice_min AND no critical slice delta < max_drop`.
For an 80% pass rate, 250 cases gives a standard error near 2.5 percentage points. Therefore a 1-point threshold movement is usually noise, not a useful release signal. A 20-case slice can catch a catastrophic break, but cannot support fine-grained threshold tuning.

Use exact JSON validation for schema correctness and a judge only for qualities such as groundedness or helpfulness. A judge that is allowed to call a malformed JSON response "basically valid" is not measuring the contract. Run the fast 200-300 row stratified subset on pull requests and the larger corpus nightly or on merge. Hold out a slice from active prompt tuning, otherwise the team can optimize to the wording of the test set.

## Build it from scratch
The matching lab implements a pure-stdlib scorer and gate. It has golden cases, required evidence terms, per-slice thresholds, overall thresholds, and baseline comparison. It deliberately has no model call: the harness contract is deterministic and can be tested before a provider is introduced.

```python
def gate(cases, outputs, slice_thresholds, overall_threshold):
    scores = [score(case, outputs[case.id]) for case in cases]
    by_slice = aggregate(cases, scores)
    return (mean(scores) >= overall_threshold and
            all(by_slice[name] >= threshold
                for name, threshold in slice_thresholds.items()))
```

## How it's done in production
OpenAI Evals supplies a framework and registry for LLM/system evaluation. Promptfoo provides deterministic and model-assisted assertion types, thresholds, weights, assertion sets, and custom scoring. A production gate also needs dataset ownership, PII scrubbing, an immutable report, CI annotations, a baseline approval workflow, and a canary or auto-revert policy. Keep the gate outside the model provider so a provider outage is reported as an infrastructure result rather than a false quality pass.

| Symptom | Cause | Fix |
|---|---|---|
| Aggregate stays 98% while German cases fail | Slice imbalance hides a small critical segment | Require per-slice minimums and minimum sample counts |
| Gate flakes on harmless prompt changes | Threshold is tighter than sampling noise | Increase cases or add statistical headroom |
| Score rises for months but users complain | Active-set overfitting or stale distribution | Keep held-out rows and refresh from production failures |
| Judge says invalid JSON is acceptable | Subjective judge used for deterministic contract | Parse JSON first; judge only the remaining criterion |
| Auto-revert loops between two prompt versions | Revert itself is not gated or baseline is mutable | Pin baseline, cap rollback attempts, alert a human |
| A model outage looks like a quality regression | Provider errors counted as normal failures | Separate provider, harness, and product outcomes |

## Tradeoffs & when NOT to use it
- Do not build a full model-graded gate for a three-user, low-stakes internal prompt; a reviewed checklist is cheaper.
- Do not gate every pull request on thousands of slow or paid calls. Use a deterministic subset in PR CI and a full run on merge or nightly.
- Do not use exact-match for a valid open-ended answer. Score required facts, schema, citations, or rubric dimensions instead.
- Do not auto-revert on one small slice with `n=3`; require a minimum sample and distinguish a data outage from a true regression.
- Do not treat the gate as production monitoring. It tests known cases; traffic drift and unseen failures need live telemetry and incident replay.

## Interview questions
### Q1 - What is a prompt regression gate?
**Testing:** Whether you can define the release contract.
**Answer:** A versioned dataset, runner, scorer, report, and release predicate over aggregate and slice-level results. It compares a candidate prompt/model against an accepted baseline and blocks when quality or a protected slice falls below policy.
**Follow-up trap:** *What if the aggregate improves but a critical locale drops 8 points?* Require the slice gate; the release fails even if overall quality rises.

### Q2 - What belongs in a golden case?
**Testing:** Test-design depth.
**Answer:** Stable id, representative input, expected output or properties, tags for slices, risk/locale metadata, and provenance such as production replay or human author. Store dataset version with prompt and model versions.
**Follow-up trap:** *Why not only use synthetic cases?* Synthetic data gives volume but can be trivial or biased; anchor it with reviewed production and incident rows.

### Q3 - How do you choose deterministic versus LLM scoring?
**Testing:** Signal and cost judgment.
**Answer:** Use code for JSON validity, required fields, IDs, regexes, and tool traces. Use a calibrated judge for subjective, open-ended dimensions. Deterministic checks are milliseconds and free; judges cost seconds, money, and calibration.
**Follow-up trap:** *Can a judge score JSON validity?* It can, but it should not. `json.loads` is exact and avoids judge variance.

### Q4 - How many cases do you need?
**Testing:** Statistical reasoning.
**Answer:** It depends on the detectable delta and baseline pass rate. Around 250 cases per slice gives roughly a 5-point margin at 95% confidence near an 80% rate; 20 cases is smoke coverage, not precision.
**Follow-up trap:** *Why does a 1-point drop fail intermittently?* The threshold is inside the sample's noise floor; add headroom or more samples.

### Q5 - How do you prevent a gate from becoming theater?
**Testing:** Operational maturity.
**Answer:** Publish false-positive rate, show per-slice diffs, separate provider failures, review threshold changes, and alert when failures are waived. A gate that pages on noise gets disabled and creates false confidence.
**Follow-up trap:** *Who can approve a waiver?* An owner with an expiry, rationale, affected slices, and follow-up issue, not an untracked rerun.

### Q6 - What does held-out mean for prompts?
**Testing:** Overfitting awareness.
**Answer:** A set not shown during prompt iteration, used periodically to estimate generalization. If the active set rises while held-out and live quality do not, the prompt was tuned to the test wording.
**Follow-up trap:** *Can the held-out set be permanently frozen?* No. Hold it out during a cycle, then rotate and refresh with incidents so it does not become stale.

### Q7 - How do you gate a non-deterministic model?
**Testing:** Distribution thinking.
**Answer:** Pin model/config where possible, run enough repetitions for high-risk cases, use tolerances and confidence intervals, and gate deterministic harness behavior separately. Report distributions, not one lucky output.
**Follow-up trap:** *Would temperature zero make it deterministic?* It reduces variance but does not guarantee provider-level reproducibility or remove model updates.

### Q8 - What should auto-revert do?
**Testing:** Safe delivery.
**Answer:** Store the accepted artifact and report hash, block or canary the candidate, revert only on a confirmed policy breach, cap retries, and page an owner. Revert must not erase the failed report.
**Follow-up trap:** *What if the baseline is already bad?* Baselines require approval and periodic review; compare against an independent holdout and production signal before trusting auto-revert.

### Q9 - How do you handle a newly added case lowering the score?
**Testing:** Dataset governance.
**Answer:** Treat the dataset change as a versioned change. A lower score may mean the test became more honest, not that the candidate regressed. Review the new case, report the diff, and do not silently move the threshold.
**Follow-up trap:** *Can you compare old and new rates directly?* Only with a common subset or a documented population adjustment.

### Q10 - Design gates for a safety-sensitive agent.
**Testing:** Principal synthesis.
**Answer:** Separate contract, policy, trajectory, and outcome gates; make high-risk slices mandatory; include injection and refusal cases; use human review for release; canary with kill switch; and monitor live failures. No golden gate alone proves safety.
**Follow-up trap:** *What is your first signal in an incident?* Trace whether the failure is data, prompt/model, tool, scorer, or provider before changing thresholds.

## Red flags that fail you
- “We eyeball ten examples and ship if it looks better.”
- One aggregate threshold with no slice reporting.
- Claiming temperature zero makes model output fully reproducible.
- Using a judge for JSON validity.
- Auto-reverting without preserving the failed report or capping loops.

## Cheat card
```text
Gate = versioned cases + runner + scorers + report + release predicate.
Pin dataset version, prompt version, and model/config version together.
Prefer deterministic checks for schema, fields, IDs, and traces.
Use judges only for subjective/open-ended criteria; calibrate them.
Report overall AND every critical slice; aggregate can hide a failure.
~250 cases/slice gives ~5-point precision near an 80% pass rate.
PR: 200-300 stratified rows; full corpus nightly/on-merge.
Keep a held-out set; rotate it after a tuning cycle.
Separate provider errors from product-quality failures.
Auto-revert needs a pinned baseline, attempt cap, and human alert.
Refresh from incidents, new features, and production distribution drift.
``` 

## Sources
- [OpenAI Evals repository](https://github.com/openai/evals) - official framework and registry; accessed 2026-10-11
- [Promptfoo assertions and metrics](https://www.promptfoo.dev/docs/configuration/expected-outputs/) - official deterministic/model-assisted assertion documentation; accessed 2026-10-11
- [Eval Harness Design, Golden Datasets, Task Rubrics](01-eval-harness.md) - internal curriculum source; accessed 2026-10-11
- [30-Story STAR Bank](../14-behavioral-principal/01-star-bank.md) - internal corpus evidence for the 2,000+ golden-row claim; accessed 2026-10-11

## Changelog
- 2026-10-11 - created

## Lineage detail: why the gate became a release artifact
**What came before.** A prompt was often stored beside application code but evaluated outside the change. An engineer ran 5 examples, changed 1 instruction, and compared outputs by eye. That workflow failed when the system had 3 locales, 4 intents, 2 safety classes, and a long tail of 1% cases. The failure was not that the engineer lacked care; the failure was that the denominator was 5, the baseline was implicit, and the previous result was not reproducible.

**Where it stands now.** A useful gate stores at least 6 pieces of identity: dataset version, prompt version, model identifier, decoding configuration, scorer version, and run timestamp. A pull-request run can use 200 to 300 rows, while a nightly run can use 1,000 or 10,000 rows. Critical slices need a minimum sample such as 20 rows before a hard decision, and a high-risk slice may require 100 or 250 rows before threshold tuning. Those numbers are policy choices; the important engineering property is that they are explicit and reviewed.

**Where it's heading.** The likely direction is a single quality control plane spanning offline evals, canary traffic, and incident replay. Confidence is high for versioned reports and per-slice dashboards. Confidence is medium for automatic golden-set generation from live traces. Confidence is low for fully automatic rollback decisions, because a gate cannot distinguish a real regression from a changed product policy without context.

## Dataset governance and failure investigation
Every case should have a stable identifier such as `refund-de-0042`, a source class, and a slice. Source classes should distinguish production replay, human-authored edge case, synthetic expansion, and incident regression. A 4-field row with only input and expected output is insufficient when the input contains tenant data or a policy-sensitive request. Keep redacted source text, not raw secrets. A practical record has `id`, `input`, `expected`, `tags`, `source`, `dataset_version`, and a retention decision.

When a gate fails, investigate in this order: provider availability, harness execution, scorer correctness, dataset change, aggregate rate, slice rate, then individual examples. A provider timeout is not a prompt-quality failure. A malformed scorer output is not evidence that the model regressed. A newly added adversarial row lowering a rate is a dataset change that should be reviewed separately. This classification prevents the worst operational response: loosening the threshold until the dashboard turns green.

Use a 3-way report for every run: current result, accepted baseline, and independent holdout. The baseline answers whether the candidate changed. The holdout answers whether the active set was overfit. The production replay slice answers whether the set still resembles reality. If the current result is 0.94, baseline is 0.93, holdout is 0.81, and live replay is 0.76, the release is not healthy even though the headline number improved.

## Gate design checklist
1. Pin the dataset and configuration before running.
2. Fail closed on missing critical slices.
3. Keep deterministic contract checks before model judges.
4. Record every failed case, not only the aggregate rate.
5. Require an owner and expiry for every waiver.
6. Store the failed report before rollback.
7. Cap automatic retries at 1 or 2 attempts.
8. Separate cost, latency, provider, and quality failures.
9. Rotate held-out cases after a tuning cycle.
10. Add at least 1 regression row for every production incident.

## Additional interview drills
### Q11 - The overall score drops from 96% to 94%. Do you block?
**Testing:** Threshold judgment.
**Answer:** Not from the aggregate alone. Compare the common dataset subset, slice deltas, confidence/noise, and whether the 2-point move is concentrated in a critical class. A 2-point drop across 1,000 stable rows is different from a 2-point drop caused by 50 newly added safety cases.
**Follow-up trap:** *What if the critical slice falls from 99% to 92%?* Block or canary it even if overall quality improves, because the protected slice is part of the release contract.

### Q12 - How do you version a judge rubric?
**Testing:** Reproducibility.
**Answer:** Give the rubric, judge model, judge prompt, anchor examples, and threshold a version. Store the rubric version in each result row. Re-run a calibration set of at least 30 labeled examples when changing it.
**Follow-up trap:** *Can you compare scores across rubric versions?* Only through a common re-evaluated subset with the version difference recorded.

### Q13 - How do you handle a 3-row critical slice?
**Testing:** Sample-size discipline.
**Answer:** Treat it as a smoke check, not a statistically stable rate. Require 20 or more for a blocking policy, add more real or reviewed cases, and mark the decision as high uncertainty until the slice is large enough.
**Follow-up trap:** *Would you ever block on 3 rows?* Yes for a deterministic safety or authorization contract, not for a subjective quality percentage.

### Q14 - What is the rollback artifact?
**Testing:** Safe delivery.
**Answer:** The accepted prompt/model/config bundle, dataset hash, report hash, scorer version, and deployment identifier. Rollback must restore the artifact and preserve the failed candidate's evidence.
**Follow-up trap:** *What prevents rollback thrashing?* A bounded attempt count, a stable baseline, a cooldown, and human escalation after the second failed transition.

### Q15 - How do you detect a stale golden set?
**Testing:** Monitoring connection.
**Answer:** Compare production traffic intent, language, length, and failure clusters with golden-set tags. If live slices have no representation or support failures rise while offline scores stay flat, refresh the set from scrubbed replays.
**Follow-up trap:** *Who approves new rows?* A product or domain owner approves expected behavior; engineering owns the executable scorer and provenance.
