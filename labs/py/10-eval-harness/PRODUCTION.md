# Production notes -- eval harnesses and LLM-as-judge

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Eval framework | ~150 lines, two scorers | Ragas, DeepEval, promptfoo, or an in-house harness wired into CI -- same shape (dataset + runner + scorers + report), more scorer types and dashboards |
| Golden dataset | 3 hardcoded cases | 200-300+ examples sourced from real production traffic, stratified across failure modes, refreshed on a cadence |
| Scorers | exact match / substring | LLM-as-judge for free-text quality, embedding similarity for semantic match, task-specific rubrics with anchor examples per score level |
| Regression gate | one JSON file, one tolerance | versioned baselines per metric per golden-set version, wired into CI so a PR that regresses eval metrics can't merge |
| Judge | one biased fake, on purpose | a real model prompted as a judge, calibrated against human labels with Cohen's kappa / Krippendorff's alpha, recalibrated whenever the rubric or judge model changes |

## What the real ones add over yours

- **A golden set that's actually representative.** This lab's 3 cases are
  for testing the harness itself, not for evaluating a real model -- a
  real golden set needs enough cases (roughly 200-300 for a meaningful
  swing to clear noise at typical pass rates) sourced from what production
  traffic actually looks like, not invented examples an engineer thought
  of in an afternoon.
- **Judge calibration against humans, continuously.** A judge you haven't
  compared against human raters is a number you can't defend in a
  postmortem. Production teams compute agreement (Cohen's kappa,
  Krippendorff's alpha) between judge and human labels on a held-out
  sample, and recalibrate every time the rubric or the judge model
  changes -- swapping GPT-4 for GPT-4o as your judge without
  recalibrating silently changes what "good" means.
- **Multiple bias mitigations stacked together**, not just awareness of
  them: randomize answer order and average both directions (cancels
  position bias, as `measure_verbosity_bias` does here), normalize for
  length or explicitly instruct the judge to ignore length, and use a
  judge from a different model family than the thing being judged
  (mitigates self-preference bias, which this lab doesn't model but is
  real -- 10-25% self-preference in some studies).
- **CI-gating discipline.** A regression gate that isn't wired into the
  actual merge/deploy pipeline is a chart nobody looks at. Production
  makes the gate a required check, the same way a failing unit test
  blocks a merge.
- **Rubrics with anchor examples.** "Rate 1-10" without anchor examples at
  each score level gets wildly different numbers from two different
  engineers looking at the same output -- the rubric needs the same
  discipline as a well-written test assertion, not a vibe.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Eval suite stays green, support tickets rise | Golden set went stale -- it stopped representing what production traffic actually looks like | Refresh the golden set on a cadence from real (anonymized) production traffic, not just once at launch |
| Judge silently favors one vendor's model over another | Self-preference bias -- the judge is itself an LLM from the same family as one of the candidates | Use a judge model from a different family than any candidate being compared, or blind the judge to model identity |
| A prompt change looks like a huge win in eval, does nothing in production | Verbosity bias in the judge rewarded a longer, chattier prompt without it being more correct -- exactly what `measure_verbosity_bias` demonstrates numerically in this lab | Normalize for length, or explicitly instruct the judge to penalize unnecessary length, and validate the "win" against real user metrics before shipping |
| Position-randomized eval still shows a skew | The randomization isn't averaged correctly (only one order tested per pair, not both) | Always run both orderings and average -- a single-direction judgment can't distinguish "this answer is better" from "this slot is better" |
| Regression gate blocks every PR, gets disabled | Tolerance too tight for golden-set size -- normal sampling noise trips it constantly | Size the golden set (or the tolerance) so noise doesn't clear the gate threshold; add a significance test instead of a flat tolerance (see stretch goal 4) |

## Cost & latency

A scripted eval harness like this lab's runs in milliseconds -- the whole
point of testing it against a fake model. A real eval run against a live
API is the expensive part: 200-300 golden cases at even $0.01-0.05 per
call is $2-15 per run, multiplied by however many prompt/model variants
you're comparing and however often CI runs it. LLM-as-judge doubles that,
since scoring each output is itself a model call -- a 300-case eval with a
judge easily costs more than the generation run it's evaluating. Teams
that skip caching identical (prompt, judge) pairs across CI runs pay for
the same judgment repeatedly.

## The 3 questions an interviewer asks after you describe this

1. *"Your eval suite passed and the PR shipped. A week later users
   complain. What do you check first?"* -- whether the golden set still
   represents production (staleness), then whether the judge is
   overfitting to a bias like length or position rather than actual
   quality -- both invisible from the eval score alone.
2. *"How do you know your judge isn't just measuring verbosity?"* -- run
   the same comparison with the candidate answers swapped in length
   independent of quality (this lab's `measure_verbosity_bias` pattern) and
   check the win rate tracks length rather than correctness; if it does,
   the judge needs length normalization or an explicit instruction against
   rewarding padding.
3. *"What's the actual failure mode if you A/B test your eval harness
   itself against a newer judge model?"* -- score drift that looks like a
   product regression but is really a judge recalibration event; without
   versioning which judge model produced which baseline, you can't tell
   the two apart, which is exactly why the regression gate needs the
   baseline tied to a specific judge version, not just a bare number.
