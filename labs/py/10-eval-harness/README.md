# Lab 10: Eval Harness + LLM-as-Judge Bias, Measured

**Track:** T08 Eval & Observability · **Time:** 3h · **XP:** 50
**Modules:** `T08-eval-harness`, `T08-llm-as-judge`

**You will build:** a golden-set eval runner against a scripted fake
model (per-case scoring, aggregate metrics, a regression gate that fails
the build on a metric drop) -- then a deliberately biased fake
LLM-as-judge that lets you *measure* position bias and verbosity bias
with real numbers instead of reading about them.

**You will be able to answer:** *"Your eval suite is green but users are
complaining. What's stale, and how would a biased judge make that worse
without anyone noticing?"*

## Setup

```bash
cd labs/py/10-eval-harness
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`GoldenCase`** -- `id`, `input`, `expected`, `tags`. **Scorers**
   (`Callable[[output, case], float]`): `exact_match_scorer` (1.0/0.0) and
   `contains_scorer` (looser, case-insensitive substring match).
2. **`ScriptedModel`** -- plays back a fixed `{input: output}` dict, records
   every call, raises `KeyError` (or falls back to a `default`) on an
   unscripted input. Deterministic and free, same philosophy as `FakeModel`
   in Lab 02.
3. **`EvalRunner.run(model, cases)`** -- scores every case, returns an
   `EvalReport` with per-case `CaseResult`s and aggregate `metrics`
   (`mean_score`, `pass_rate` at `pass_threshold`). Empty golden set must
   not divide by zero.
4. **Regression gate** -- `check_regression(current_metrics, baseline,
   tolerance)` fails when a baseline metric dropped by more than
   `tolerance`, and fails (not silently passes) when a metric goes missing
   entirely. `save_baseline`/`load_baseline` round-trip a metrics dict
   through JSON on disk -- this is "the build" failing on a real
   regression, not a mocked assertion.
5. **`biased_judge(question, answer_a, answer_b)`** -- a deliberately
   biased fake judge with the bias constants in plain sight:
   `POSITION_BONUS` (favors whichever answer is in slot A) and
   `VERBOSITY_WEIGHT` (favors longer text, per character), on top of a
   constant "quality" baseline so any winner it picks is attributable
   *only* to position or length.
6. **`measure_position_bias`** / **`measure_verbosity_bias`** -- helpers
   that run the judge over both slot orderings and report a measured win
   rate: the same two answers, order swapped, should show a different
   winner; a longer-but-equally-good answer should win at a measurable,
   predictable rate tied directly to `VERBOSITY_WEIGHT`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Self-preference bias** -- extend the biased judge with a third
   constant that favors answers tagged as coming from "the judge's own
   family," and write a test measuring how many points of win rate that's
   worth, the same way this lab measures position and verbosity bias.
2. **Calibration** -- add a small set of human-labeled pairs (hardcoded in
   the test, no real annotators needed) and compute Cohen's kappa between
   the biased judge's verdicts and the "human" labels, to show numerically
   how far off an uncalibrated judge is.
3. **Golden-set staleness detector** -- add a function that flags when a
   golden set's case count or tag distribution has drifted more than X%
   from a stored snapshot, the mechanical version of "the eval set stopped
   representing production."
4. **Statistical significance** -- the regression gate currently fires on
   any drop past `tolerance`. Add a variant that only fires when the drop
   is significant at a chosen confidence level given the golden-set size
   (a binomial proportion test), so a 1-case fluke doesn't block a release.
