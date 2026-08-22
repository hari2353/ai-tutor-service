# Eval Harness Design, Golden Datasets, Task Rubrics

> **Track:** T08 Eval & Observability · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T08-eval-harness` · **Tags:** eval

## The 30-second version

An eval harness is a dataset, a runner, a set of scorers, a reporting layer, and version control glueing all four together — the same shape as a test suite, and it rots the same way an ad-hoc test script does if you skip the structure: someone writes a notebook cell that loops over ten examples and eyeballs the output, it works until the prompt changes, and six months later nobody knows which ten examples or why. The part that actually determines whether the harness is worth anything is the golden dataset — sourced from real production traffic, not invented cases, stratified across the failure modes you actually see, big enough that a real regression clears the noise floor (roughly 200-300 examples to detect a meaningful swing at typical pass rates), and refreshed on a cadence because the product drifts out from under a frozen set. A rubric two different engineers score the same output on and get the same number is an engineering artifact, not a one-line prompt — it needs anchor examples per score level and explicit exclusions, the same discipline as a well-written unit test assertion. None of this replaces watching real users; a harness that passes while support tickets rise means the eval set stopped representing production, not that the product got worse.

## Why this gets asked

Every interviewer running an LLM feature at scale has watched an eval suite go green while the on-call channel filled up with complaints, and they want to know if you understand *why* that happens — usually eval-set staleness or a scorer that's checking the wrong thing — rather than just being able to name a framework. At staff level they're probing whether you've built the versioning and CI-gating discipline that makes an eval trustworthy enough to block a release on, or whether your "eval" is a notebook that ran once during a demo.

---

## Lineage: past → present → future

**What came before.** Early LLM development evaluation was a loop of "change the prompt, run it against five examples I remember, read the outputs, ship if it looks better." This is how essentially every team starts, and it works exactly until someone else touches the prompt, or the five examples stop representing what users actually send, or a fix for one case silently breaks three others nobody was checking. The pain that killed it was concrete: teams shipped regressions that a five-example gut check couldn't catch, because five hand-picked examples have no claim to represent a production distribution, and there was no record of what "looks better" had even been checked against three weeks earlier when the last change went out.

**Where it stands now.** The consensus structure is a harness with four separable parts — a **dataset** (input, expected output or expected properties, metadata for stratification), a **runner** (executes the system under test against every dataset row, capturing full output plus trace), **scorers** (deterministic checks and/or model-graded judges, see `T08-llm-as-judge`), and a **reporting layer** (aggregate pass rate, per-slice breakdown, diff against the last run) — versioned together with the prompt and model that produced the run. This is the same shape as `pytest` plus a coverage report, and that similarity is intentional: frameworks like DeepEval, Promptfoo, and LangSmith datasets (see `T08-ragas-deepeval`) exist specifically to make this loop CI-native rather than a bespoke script per team. The live disagreement is over how much of the golden set can be synthetic: some teams generate large synthetic eval sets to get volume, others insist every row must trace back to a real production input or a human-authored edge case, because a synthetic generator left unchecked tends to produce questions the system can already answer trivially, which measures nothing. What's actually deployed at scale is a hybrid — synthetic generation for volume, with a human-reviewed subset validating that the synthetic rows are realistic and non-trivial.

**Where it's heading.** Eval-as-code — datasets, rubrics, and scorer thresholds checked into the same repo as the prompts and gated in CI on every PR — is becoming the default at teams serious about the pipeline, the same way unit tests gate application code; this is real and already shipping in DeepEval's pytest integration and Promptfoo's CI configs. Continuous production evaluation, where the same rubric that gates a PR is sampled continuously against live traffic rather than run only at eval time, is a medium-confidence direction (see `T09-model-monitoring`) — it collapses "eval" and "monitoring" into one discipline instead of two separate systems that drift apart. More speculative: automated golden-set curation that mines production failure replays and clusters them into new stratified slices without a human manually triaging every incident first — early tooling exists, not yet a settled default.

---

## Mental model

```
   PRODUCTION TRAFFIC / INCIDENTS / HAND-WRITTEN EDGE CASES
                         │
                         ▼
          ┌───────────────────────────┐
          │      GOLDEN DATASET        │   versioned (git/DVC), stratified,
          │  {input, expected, tags}    │   refreshed on a cadence
          └──────────────┬─────────────┘
                         │
                         ▼
          ┌───────────────────────────┐
          │          RUNNER            │   executes system-under-test,
          │  (pinned prompt + model)    │   captures output + full trace
          └──────────────┬─────────────┘
                         │
                         ▼
          ┌───────────────────────────┐
          │          SCORERS           │   deterministic checks (fast, free,
          │  deterministic + model-    │   exact) + model-graded judges
          │  graded (see llm-as-judge) │   (subjective, calibrated)
          └──────────────┬─────────────┘
                         │
                         ▼
          ┌───────────────────────────┐
          │        REPORTING            │   aggregate pass rate, per-slice
          │  diff vs last run, per-slice│   breakdown, CI gate pass/fail
          └──────────────┬─────────────┘
                         │
                         ▼
              CI GATE (block/allow release) ── or feeds T09 production monitoring
```

Every box is versioned alongside the prompt and model that produced the run. If you can't answer "which dataset version, which prompt version, which model version produced this 87%," you don't have a harness, you have a number.

---

## How it actually works

### Why ad-hoc eval scripts rot

A notebook cell that loops over a handful of examples has three failure modes that compound: (1) the example set is never version-controlled, so nobody can reproduce last month's "looks good" judgment; (2) the pass/fail criterion lives in the engineer's head, not in code, so two people running the same notebook reach different conclusions; (3) there's no aggregate number to diff against, so a regression that affects 8% of a hidden slice is invisible unless that exact slice happens to be in the five examples someone remembered to check. The symptom in practice: a PR that "passed eval" (someone glanced at outputs and they looked fine) ships a regression that a stratified 200-row run would have caught in the one slice — say, multi-turn conversations, or non-English input — that the ad-hoc check never covered.

### Building a golden dataset that is not garbage

**Source from real traffic, not imagination.** Hand-invented test cases systematically under-represent the ways users actually phrase things and over-represent the cases the author already thought of. Pull from production logs (with PII scrubbing), support escalations, and — critically — every incident that already shipped: a replayed failure that becomes a permanent dataset row is the cheapest regression test you will ever write, because you already paid for the incident once.

**Structure it in four buckets**, not one undifferentiated pile:
1. A stratified sample of real production traffic (by intent, length, language, user segment — whatever axes actually vary in your traffic).
2. An adversarial library (prompt injection attempts, jailbreak patterns, edge-of-policy requests) — see `T19-llm-testing` for the security-testing angle.
3. Deliberately constructed edge cases (empty input, max-length input, malformed structured input, the specific ambiguous phrasing that's hard even for a human).
4. Replays of failures that already shipped — every postmortem produces at least one new golden row.

**Size guidance.** If your system runs at roughly an 80% pass rate and you want a 5% margin of error at 95% confidence, you need on the order of **~250 examples per slice** you care about distinguishing — the standard binomial-proportion sample-size arithmetic (n ≈ 1.96² · p(1-p) / e² ≈ 246 at p=0.8, e=0.05). In practice, PR-time gating runs a stratified subset of **200-300 rows** for speed, with the full set (which can run into the thousands as it accumulates replayed failures) run nightly or on merge to main. A 20-example eval set can tell you the system isn't completely broken; it cannot tell you a change moved the true pass rate by 3 points, because 3 points on 20 examples is noise.

**Annotation guidelines and inter-annotator agreement.** If two humans labeling the same golden-set row (correct/incorrect, or a graded rubric) disagree, the label is unusable as ground truth. Standard workflow: two annotators independently label an initial batch of ~50 cases against a written guideline, compute Cohen's kappa; **below ~0.7, the labels are noise** and the guideline needs concrete examples of borderline cases before you scale up annotation. This is the same discipline covered in depth for judge calibration in `T08-llm-as-judge` — a golden dataset's labels need the same rigor as the judge that will later be checked against them, because a rubric two annotators can't agree on will produce a judge two people also can't trust.

**Refreshing the eval set.** A golden set frozen at product launch measures how well you handle a product that no longer exists six months later — new features shift the input distribution, and a set that never adds new slices will show a flat, reassuring 95% pass rate while missing every case introduced since. Refresh on every incident (add the replay), every new feature (add a stratification slice), and on a fixed cadence (quarterly, at minimum) even with no trigger, specifically to catch product drift the team hasn't noticed yet.

### Task rubrics two people can actually apply the same way

A rubric that says "rate helpfulness 1-5" is not a rubric, it's a vibe with a number attached. A rubric that works:
- States concretely what a 1, a 3, and a 5 look like for *this task*, with an example of each — not adjectives, anchors.
- Explicitly excludes dimensions not being scored ("ignore formatting," "do not penalize length," "do not compare to how you personally would answer").
- Scores one criterion per pass. A rubric asking for "correctness, tone, and completeness" in a single number conflates three independent signals into one you can't debug later when it drops.
- Is tested the same way a judge is calibrated: two humans score the same 30-50 outputs against the written rubric before anyone scales it up, and if their agreement is weak the rubric gets rewritten, not the annotators re-trained.

### Deterministic vs model-graded scorers

| | Deterministic scorer | Model-graded scorer |
|---|---|---|
| Examples | JSON schema validity, regex match, exact string match, unit test on generated code, retrieval hit@k against known-relevant doc IDs | LLM judge scoring helpfulness, faithfulness, tone, instruction-following (see `T08-llm-as-judge`, `T08-ragas-deepeval`) |
| Cost | Near-zero, milliseconds | Cents to dollars per run, seconds, and needs calibration against human labels before it's trustworthy |
| When it's the right tool | The correct answer is a checklist a human could apply without thinking — valid syntax, contains a required field, matches a known-good ID | The criterion is genuinely subjective or open-ended — no single string is "the" correct answer |
| Failure mode if misapplied | Using a judge for a criterion that has a deterministic answer wastes money and adds judge noise to a signal that should be exact | Using a deterministic exact-match check on open-ended generation fails every valid paraphrase, producing a pass rate that looks catastrophic and is meaningless |

Rule of thumb: reach for deterministic first. Every criterion you can turn into a deterministic check should be, because it's free, exact, and has zero calibration burden — reserve the model-graded judge for what's left after the checklist items are stripped out.

### Pass thresholds and CI gating

A threshold has to reflect a real minimum acceptable quality bar, not be picked because "90% sounds good." Set it with headroom against the eval set's own noise floor: if your stratified 250-row PR gate has a binomial standard error of roughly 2.5 points at an 80% pass rate, a threshold that fails on any 1-point dip will flake on every PR and get muted within a month — the classic failure mode is an eval gate everyone has learned to ignore because it cries wolf, which is strictly worse than no gate, because it gives false confidence that regressions are being caught. Working pattern: cheap deterministic checks plus a fast model-graded pass on every PR against the stratified subset, the full golden set (including the slower/pricier judge-graded rows) nightly or on merge to main, and any threshold breach reported with the per-slice diff, not just the aggregate number, so a reviewer can tell "database queries got 6 points worse" from "everything got 1 point worse" — very different incidents.

### Eval-set contamination and overfitting to your own eval

Two distinct failure modes share a name. **Contamination** is when eval examples leak into training or fine-tuning data — a model fine-tuned on data that happens to include your eval questions will score suspiciously well on your eval and normally on everything else; the tell is a gap between your eval score and independent third-party benchmarks, or an eval score improbably close to 100%. **Overfitting to your own eval** is subtler and doesn't require any data leakage: if the same 300-row eval set gates every prompt iteration for months, engineers unconsciously (or consciously) tune prompts against the specific phrasings in that set, and the eval score climbs while true production quality plateaus or drops — Goodhart's law applied to a prompt-engineering loop. The fix for both is the same discipline: keep a held-out slice of the golden set that is never looked at during iteration, only checked before a major release, and treat a large gap between the actively-tuned-against set and the held-out set as the actual regression signal.

### Versioning eval sets alongside prompts and models

An eval score is meaningless without the triple that produced it: dataset version, prompt version, model version. Practically this means the golden dataset lives in the same repo (or a data-versioning tool like DVC pointed at object storage) as the prompts, tagged or hashed per release, so a report can say "87% on golden-set v14 with prompt v22 on gpt-5.1-2026-06" rather than just "87%." Without this, a score from three months ago is not comparable to today's, because you cannot tell whether a delta is a real regression or the eval set silently grew five new adversarial rows in between.

### The failure mode where the eval passes and users complain

**Symptom:** dashboard shows the golden-set pass rate flat or improving release over release; support tickets, refund requests, or churn signals rise in the same window. **Cause:** almost always eval-set staleness — the golden set stopped representing the current input distribution (a new feature shipped and nobody added a stratification slice for it, or a competitor/market shift changed what users ask for) — or a scorer measuring the wrong thing (a deterministic check on the wrong field, or a judge rubric that quietly drifted from what "good" means to actual users). The fix is never to make the threshold stricter; it's to pull a fresh stratified sample of *current* production traffic, diff it against the golden set's coverage, and add the slices that are missing.

---

## Build it from scratch

Minimal harness: dataset loader, runner, pluggable scorer interface, and a report that diffs against the previous run. Full version with stratified sampling, CI integration, and a golden-set refresh script: reference implementation pattern used across `labs/py/` eval labs (see `T08-agent-eval`'s `labs/py/04-agent-eval-harness/` for the agent-trajectory variant of this same shape).

```python
# untested sketch
import json, hashlib
from dataclasses import dataclass, field
from datetime import date

@dataclass
class GoldenRow:
    id: str
    input: str
    expected: str | None      # None when only a scorer, not exact-match, applies
    tags: list[str] = field(default_factory=list)   # for stratified reporting

@dataclass
class ScoreResult:
    row_id: str
    passed: bool
    score: float
    detail: str = ""

def load_golden_set(path: str) -> list[GoldenRow]:
    rows = [GoldenRow(**r) for r in json.load(open(path))]
    return rows

def dataset_hash(rows: list[GoldenRow]) -> str:
    """Content hash so a report can cite the exact dataset version used."""
    blob = json.dumps([r.__dict__ for r in rows], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:12]

def run_harness(rows, system_under_test, scorers: list) -> list[ScoreResult]:
    results = []
    for row in rows:
        output = system_under_test(row.input)          # pinned prompt+model version
        for scorer in scorers:
            r = scorer(row, output)                      # deterministic or model-graded
            results.append(r)
    return results

def report(results: list[ScoreResult], rows: list[GoldenRow], dataset_ver: str):
    tag_index = {r.id: r.tags for r in rows}
    by_tag: dict[str, list[bool]] = {}
    for res in results:
        for tag in tag_index.get(res.row_id, ["untagged"]):
            by_tag.setdefault(tag, []).append(res.passed)

    overall = sum(r.passed for r in results) / len(results)
    print(f"dataset={dataset_ver} date={date.today()} overall_pass={overall:.1%}")
    for tag, passes in sorted(by_tag.items()):
        rate = sum(passes) / len(passes)
        print(f"  slice={tag:20s} n={len(passes):4d} pass={rate:.1%}")

# Deterministic scorer example
def json_schema_scorer(row: GoldenRow, output: str) -> ScoreResult:
    try:
        json.loads(output)
        return ScoreResult(row.id, True, 1.0)
    except json.JSONDecodeError as e:
        return ScoreResult(row.id, False, 0.0, detail=str(e))

# CI gate
def gate(results: list[ScoreResult], threshold: float = 0.85) -> bool:
    rate = sum(r.passed for r in results) / len(results)
    return rate >= threshold
```

---

## How it's done in production

**Frameworks:** Promptfoo (config-driven, prompt-level regression testing, CI-native — see `T08-ragas-deepeval`), DeepEval (pytest-native, `assert_test()` gates a build on a metric threshold), LangSmith and Braintrust (full lifecycle: dataset management with versioning, scoring, human annotation queues, production monitoring in one system so eval and monitoring share infrastructure — see `T08-obs-platforms`). None of these replace the discipline above; they give you the plumbing to run it at CI speed and keep history.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Eval passes every release; support tickets/complaints rise anyway | Golden set no longer represents current traffic, or scorer measures the wrong criterion | Pull a fresh stratified sample of current production traffic, diff against golden-set coverage, add missing slices |
| Eval score improbably high (>95%) and doesn't match independent benchmarks | Contamination — eval examples leaked into fine-tuning/training data | Check for exact-match overlap between eval inputs and training corpus; compare against a held-out or third-party benchmark |
| Eval score climbs steadily but production quality plateaus | Overfitting to the actively-tuned-against eval set (Goodhart) | Keep a held-out slice never used during iteration; gate major releases on it, not just the actively-tuned set |
| CI gate fails on ~1 in 4 PRs with no real regression | Threshold set tighter than the eval set's own statistical noise floor | Compute the binomial standard error for the sample size in use, set threshold with headroom, or increase sample size |
| Two annotators produce a golden-set label disagreement no one resolves | No inter-annotator agreement check before scaling labeling | Compute Cohen's kappa on an initial ~50-case batch; rewrite the guideline with concrete anchor examples if kappa < 0.7 |
| A regression ships in a slice (e.g. non-English input) that the eval never flagged | Golden set has no stratification tag for that slice | Add the slice explicitly, backfill from production logs or the incident that just happened |

---

## Tradeoffs & when NOT to use it

- **Don't build a full harness for a single-prompt, low-stakes internal tool used by three people.** The fixed cost of dataset curation, scorer calibration, and CI wiring is real; for something that low-stakes, a manual spot-check on every change is proportionate, and formalizing it is wasted engineering time better spent elsewhere.
- **Don't gate every PR on the full golden set if it's slow or expensive.** Running thousands of rows with a model-graded judge on every commit burns money and developer time waiting on CI; stratified subset on PR, full set nightly/on-merge is the standard tradeoff.
- **Don't treat a passing eval as sufficient sign-off for anything safety-critical.** A harness measures what's in the dataset; it says nothing about the failure mode nobody thought to add a row for. Pair it with human review and staged rollout for anything with real consequences.
- **Don't let the eval set become the product spec.** If engineers start asking "does this pass eval" instead of "does this serve the user," the harness has become the target instead of the proxy — watch for eval scores climbing while the held-out slice or real user metrics don't move.
- **Don't over-invest in synthetic dataset generation before you have any real traffic.** A synthetic set built with no production data to ground it tends to test what the generator's author imagined, which is the same failure mode as the five-example gut-check, just with better tooling.

---

## Interview questions

### Q1 — What are the components of an eval harness, and why does an ad-hoc eval script fail at scale?
**Testing:** baseline structural understanding.
**Answer:** Dataset, runner, scorers, reporting, all versioned together. An ad-hoc script fails because the example set isn't version-controlled (no reproducibility), the pass criterion lives in someone's head rather than in code (no consistency across reviewers), and there's no aggregate/per-slice number to diff, so a regression confined to an uncovered slice is invisible.
**Follow-up trap:** *"Isn't that just over-engineering for a small team?"* — for a low-stakes single-prompt tool, yes, a manual check is proportionate; the harness earns its cost once more than one person touches the prompt or the system gates a release that matters.

### Q2 — How do you build a golden dataset that isn't garbage?
**Testing:** whether they've actually sourced real data, not invented cases.
**Answer:** Source from real production traffic (with PII scrubbing), support escalations, and every shipped incident replayed as a permanent row. Structure into four buckets: stratified production sample, adversarial library, deliberately constructed edge cases, incident replays. Size to roughly 200-300 examples per slice you care about distinguishing, refreshed on incidents, new features, and a fixed cadence regardless of trigger.
**Follow-up trap:** *"Why not just generate 10,000 synthetic examples and skip the sourcing work?"* — a synthetic generator left unchecked produces questions the system can trivially answer, testing nothing; synthetic is fine for volume but needs a human-reviewed subset validating realism, and it should supplement real-traffic sourcing, not replace it.

### Q3 — What sample size do you need to trust a golden-set pass-rate number?
**Testing:** whether "more examples is better" is backed by actual arithmetic.
**Answer:** For a system around an 80% pass rate and a 5% margin of error at 95% confidence, the binomial-proportion formula gives roughly n ≈ 1.96² · p(1-p) / e² ≈ 246 examples per slice. A 20-example set can tell you the system isn't badly broken; it can't tell you a 3-point shift is real versus noise.
**Follow-up trap:** *"Your CI gate fails intermittently with no real regression — why?"* — the threshold is probably tighter than the sample's own statistical noise floor; compute the standard error for the actual sample size in use and set the threshold with headroom, or the gate gets muted within a month and stops catching anything.

### Q4 — Deterministic vs model-graded scorers — how do you decide which to use for a given criterion?
**Testing:** cost/precision tradeoff awareness.
**Answer:** If a competent human could apply the criterion as a checklist without re-reading context (valid JSON, contains a required field, matches a known-good ID), use a deterministic check — free, exact, zero calibration burden. Reserve model-graded judges for genuinely subjective or open-ended criteria with no single correct string.
**Follow-up trap:** *"Someone's using an LLM judge to check if output is valid JSON. What's wrong with that?"* — wasted cost and added judge noise on a criterion that has an exact deterministic answer; `json.loads()` either succeeds or it doesn't, no judgment required.

### Q5 — How do you compute and interpret inter-annotator agreement for a golden dataset's labels?
**Testing:** the annotation-quality discipline, not just the statistic name.
**Answer:** Have two annotators independently label an initial batch (~50 cases) against a written guideline, compute Cohen's kappa. Below roughly 0.7, the labels are noise and unusable as ground truth — the fix is rewriting the guideline with concrete borderline-case examples, not retraining the annotators.
**Follow-up trap:** *"Your annotators agree 92% of the time on a golden set that's 90% one label. Good?"* — no, that's likely near chance-level agreement given the label imbalance; raw percent agreement doesn't correct for it, kappa does, and a kappa near zero on that same data would reveal the annotators aren't tracking a real signal.

### Q6 — Design a rubric two engineers can score the same output on and reliably get the same number.
**Testing:** rubric-design discipline.
**Answer:** State concretely what a 1, 3, and 5 look like for the specific task with example outputs at each level, not adjectives. Explicitly exclude dimensions not being scored. Score one criterion per pass rather than conflating correctness/tone/completeness into a single number. Validate it the same way a judge is calibrated — two humans score 30-50 outputs before scaling.
**Follow-up trap:** *"Your rubric has three criteria in one number and the score just dropped 10 points. What do you do?"* — you can't tell which criterion regressed; split into three single-criterion passes going forward, and for the historical drop, manually re-read a sample to attribute it before deciding what to fix.

### Q7 — What's the difference between eval-set contamination and overfitting to your own eval, and how do you catch each?
**Testing:** distinguishing two similarly-named but mechanically different failures.
**Answer:** Contamination is eval examples leaking into training/fine-tuning data, producing suspiciously high scores that don't match independent benchmarks — check for exact-match overlap and compare against third-party eval. Overfitting is engineers unconsciously tuning prompts against the specific phrasings in a static eval set over months, with no data leakage involved — eval score climbs while true quality plateaus. Catch it with a held-out slice never used during active iteration, checked only before major releases.
**Follow-up trap:** *"Your held-out slice score matches the actively-tuned set almost exactly. Does that clear you of overfitting?"* — it's reassuring but not proof; also check real production signal (complaint rate, task success) for the same period, since both slices being drawn from the same distribution can still miss a real-world shift neither slice's original sourcing captured.

### Q8 — Your golden-set pass rate is flat at 95% for three releases, but support tickets are rising. Diagnose it.
**Testing:** the specific named failure mode from the module.
**Answer:** Almost always eval-set staleness — the golden set stopped representing current production traffic (a new feature shipped with no stratification slice, or user behavior shifted) — or a scorer checking the wrong thing. Fix: pull a fresh stratified sample of current traffic, diff its coverage against the golden set, add what's missing. Never respond by just raising the threshold.
**Follow-up trap:** *"What if you add the new slice and the pass rate drops to 80%? Is the eval now 'worse'?"* — no, it's now honest; a flat 95% that excluded a real failure mode was never a true number, and the drop is the harness finally measuring the gap that already existed in production.

### Q9 — Why version the eval dataset alongside the prompt and model, and what breaks if you don't?
**Testing:** whether they treat eval infra with the same rigor as code.
**Answer:** An eval score is only meaningful as the triple (dataset version, prompt version, model version). Without pinning all three, a score from three months ago isn't comparable to today's — you can't tell if a delta is a real regression or the dataset silently grew new rows in between.
**Follow-up trap:** *"Your eval score dropped 4 points overnight and nobody touched the prompt or model. What do you check first?"* — the dataset version; someone likely added new adversarial or replayed-failure rows, which is a legitimate score drop (the eval got harder and more honest), not a regression in the system under test.

### Q10 — Set a CI pass threshold for a release gate. Walk through the reasoning.
**Testing:** whether they ground the threshold in statistics, not vibes.
**Answer:** Start from the eval set's own noise floor at the sample size in use (binomial standard error), set the threshold with headroom above it so normal run-to-run variance doesn't trip it, and validate the threshold reflects a genuine minimum acceptable quality bar rather than an arbitrary round number. Pair the aggregate gate with per-slice reporting so a reviewer can see which slice moved, not just that something moved.
**Follow-up trap:** *"The team wants the threshold at 99% because 'quality matters.'"* — check whether 99% is even statistically distinguishable from the current baseline at the sample size in CI; if the standard error is ±2.5 points, a 99% threshold either fails constantly (theater) or the sample size needs to increase to make that precision meaningful, which changes the cost/speed tradeoff of the gate.

### Q11 — When should you NOT build a formal eval harness?
**Testing:** the "when not to use it" signal.
**Answer:** Single-prompt, low-stakes internal tools with a handful of users, where the fixed cost of dataset curation and CI wiring exceeds the value of formalizing a check three people could do by eyeballing changes. Also: don't run the full expensive golden set on every PR if a stratified subset plus nightly full-run is statistically sufficient — that's an engineering-cost mistake, not a correctness one.
**Follow-up trap:** *"The 'low-stakes internal tool' just got embedded in a customer-facing workflow. Now what?"* — that's exactly the trigger to build the harness; the decision should be re-made whenever the blast radius of a regression changes, not fixed at initial build time.

### Q12 — An engineer says "the eval score went up, ship it." What do you ask before agreeing?
**Testing:** staff-level skepticism, tying together contamination/overfitting/staleness.
**Answer:** Which dataset version produced that score, and is it the actively-tuned-against set or the held-out slice? Has the eval set been refreshed recently, or could this be measuring against a stale distribution? Does the improvement hold on the held-out slice and on any independent/production signal, not just the set that's been iterated against for months?
**Follow-up trap:** *"The held-out slice also improved. Confident now?"* — more confident, but check real production signal over the same window regardless — both slices sharing a sourcing bias (e.g. neither covers a recently-launched feature) is still possible even when they agree with each other.

---

## Red flags that fail you

- Describing "eval" as a notebook cell someone runs manually before a demo.
- No mention of versioning the dataset alongside the prompt/model that produced a score.
- Treating a passing eval as sufficient sign-off with no held-out slice or human review for anything consequential.
- Not knowing the difference between contamination and overfitting to your own eval set.
- Picking a CI threshold with no reference to the eval set's own statistical noise floor.
- Using a model-graded judge for a criterion that has an exact deterministic answer.
- No inter-annotator agreement check before trusting golden-set labels at scale.
- Responding to "eval passes but users complain" by raising the threshold instead of refreshing the dataset.

---

## Cheat card

```
HARNESS       dataset -> runner -> scorers -> reporting, all versioned together
              (dataset ver + prompt ver + model ver, or the score is meaningless)

GOLDEN SET    4 buckets: stratified real traffic, adversarial library,
              edge cases, replayed shipped failures
              SIZE: ~250/slice for 5% margin @ 95% CI at ~80% pass rate
              PR gate: 200-300 stratified rows. Full set: nightly/on-merge.
              REFRESH: every incident, every feature, quarterly minimum

ANNOTATION    2 annotators, ~50 cases, Cohen's kappa. <0.7 = labels are noise,
              fix the guideline (concrete anchors), not the annotators

RUBRIC        concrete anchor per score level, explicit exclusions,
              ONE criterion per pass, validate w/ 2 humans on 30-50 outputs first

SCORERS       deterministic: checklist-style, free, exact -> use by default
              model-graded: subjective/open-ended -> needs judge calibration
              (see T08-llm-as-judge)

CONTAMINATION eval rows leaked into training -> improbable scores vs benchmark
OVERFITTING   months of tuning against same static set -> score up, quality flat
              FIX (both): held-out slice never touched during iteration

FAILURE MODE  eval passes, users complain -> golden set is stale, not the
              product regressing. Refresh coverage, don't raise the bar.

THRESHOLD     set above the sample's own binomial SE, or gate flakes -> gets
              muted -> worse than no gate (false confidence)
```

## Sources

- [LLM Eval Golden Set Design: A 2026 Engineering Guide — FutureAGI](https://futureagi.com/blog/llm-eval-golden-set-design-2026/) — accessed 2026-08-01
- [Building a "Golden Dataset" for AI Evaluation: A Step-by-Step Guide — Maxim](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/) — accessed 2026-08-01
- [What is LLM evaluation? A practical guide to evals, metrics, and regression testing — Braintrust](https://www.braintrust.dev/articles/llm-evaluation-guide) — accessed 2026-08-01
- [CI/CD LLM Eval with GitHub Actions: 2026 Workflow — FutureAGI](https://futureagi.com/blog/ci-cd-llm-eval-github-actions-2026/) — accessed 2026-08-01
- [How to Calibrate Your LLM Judge With Human Annotations — Galileo](https://galileo.ai/blog/calibrate-llm-judge-human-annotations) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
