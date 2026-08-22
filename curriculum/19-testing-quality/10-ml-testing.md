# Testing ML: Data Tests, Model Tests, Behavioural Tests, Metamorphic

> **Track:** T19 Testing & Quality Engineering · **Time:** 2.5h · **Prereqs:** T19-test-strategy
> **Module id:** `T19-ml-testing` · **Tags:** ml, critical
> **Updated:** 2026-07-26

## The 30-second version

Testing an ML system requires four genuinely distinct test categories because a model can fail in ways that traditional software testing has no vocabulary for: data tests validate the training/serving data itself (schema, distribution, missing-value rates, label balance) before a single model is trained on it, because "garbage in, garbage out" is measurable and preventable, not just a saying; model tests validate the model artifact's behavior against held-out data (accuracy/AUC/F1 thresholds, calibration, per-slice performance, not just aggregate performance) the way a unit test validates a function; behavioral tests, formalized by CheckList (Ribeiro et al., ACL 2020), test specific linguistic/behavioral capabilities directly — invariance (a label-preserving perturbation like a name swap shouldn't change the prediction), directional expectation (a perturbation should change the prediction in a known direction), and minimum functionality (simple, targeted examples that catch a model using a shortcut instead of the actual capability) — independent of overall accuracy, because a model can hit 95% accuracy while systematically failing an entire behavioral category the aggregate metric never surfaces; and metamorphic testing generalizes this idea beyond NLP to any ML system by defining relations between inputs and expected relations between outputs (rotate an image slightly, the classification shouldn't change; swap a credit applicant's gender, the default-risk score shouldn't increase) without needing ground-truth labels for every test case, which matters because ground truth is often the exact thing you don't have for the edge cases you're worried about. Drift testing — monitoring whether production input distributions (data drift) or the input-output relationship (concept drift) have shifted away from what the model was trained/validated on, typically via PSI (Population Stability Index, with PSI > 0.25 conventionally flagged as significant drift) or the Kolmogorov-Smirnov test — closes the loop, because a model that passed every test above at training time can still silently fail in production as the world it's scoring changes underneath it.

## Why this gets asked

Because ML systems fail silently in ways traditional software doesn't: a model with a subtle bug doesn't throw an exception, it returns a confidently wrong prediction that looks exactly like a confidently right one, and a single aggregate accuracy number can hide a model that's excellent on the majority slice of data and badly broken on a minority slice nobody's looking at. The interviewer has likely shipped or inherited a model that "tested fine" (good aggregate accuracy on a held-out set) and then either discriminated against a demographic slice discovered post-launch, failed a case that should have been trivial (a behavioral gap CheckList-style testing would have caught), or degraded in production months later as real-world data drifted away from training data — and wants to know whether you test ML systems with the same rigor and the same *right* techniques as traditional software, not with traditional software's techniques applied naively (a "unit test" that just re-checks aggregate accuracy tells you almost nothing about any of these failure modes).

---

## Lineage: past → present → future

**What came before.** Early ML system evaluation (through the 2010s, and still common today in less mature teams) was almost entirely aggregate-metric-driven: train, hold out a test set, report accuracy/F1/AUC on that set, ship if the number clears a threshold. The pain this produced, repeatedly and publicly: models that hit strong aggregate numbers while failing badly on specific slices (documented gender/racial bias in commercial face-recognition and hiring-screening systems through the mid-2010s, well-known enough to be cited in fairness-in-ML literature broadly), and models that passed evaluation via shortcuts — learning a spurious correlation in the training distribution (a specific word strongly correlated with a label in the training set for reasons unrelated to the actual task) rather than the intended capability, invisible to an aggregate metric that only measures whether predictions matched labels, not *why*. Software engineering's testing discipline (unit tests, property-based testing, mutation testing) had no native vocabulary for "the model is 95% accurate but systematically wrong on negation" — that gap is specifically what CheckList and metamorphic testing were built to close.

**Where it stands now.** CheckList (Ribeiro, Wu, Guestrin, Singh — ACL 2020, awarded Best Paper) established the now-standard behavioral testing vocabulary — Minimum Functionality Tests (MFT, simple targeted examples per capability), Invariance tests (INV, label-preserving perturbations), Directional Expectation tests (DIR, perturbations with a known expected direction of change) — and its own published user study found practitioners using CheckList wrote roughly twice as many tests and found roughly three times as many bugs as those without it, a genuinely large, real effect size. Metamorphic testing (older than CheckList as a general software-testing technique, adapted specifically to ML by multiple groups through the 2010s-2020s) generalizes the same idea beyond text: image rotation/augmentation as a dataset multiplier with a known label-preserving or label-transforming relation, temporal consistency in video (adjacent frames in a 30fps sequence should produce similar predictions, providing a self-supervisory signal without needing new labels), and fairness-oriented metamorphic relations (a protected-attribute perturbation like swapping gender on a credit application shouldn't increase a risk score) that have become a standard fairness-testing technique specifically because they don't require ground-truth labels for the counterfactual case, which usually doesn't exist. The live disagreement is less about whether these techniques are valuable (broad consensus that they are, given the concrete evidence CheckList itself reports) and more about organizational adoption — most teams still under-invest relative to the demonstrated bug-finding yield, largely because building a good behavioral/metamorphic test suite requires genuine domain expertise about what capabilities and relations actually matter for a given task, which doesn't come free the way running an aggregate-metric eval does.

**Where it's heading.** Drift detection and monitoring is maturing from ad hoc dashboard-watching into a standardized statistical toolkit — PSI (with the PSI > 0.25 "significant drift" convention originally from credit-risk scorecard monitoring, now applied broadly to any model feature or output distribution), KS tests, KL/JS divergence, and the Wasserstein metric are all now common, with practical guidance converging on combining a distributional test (PSI, KS) with actual downstream performance monitoring rather than relying on distributional drift alone, since input distributions can shift without the model's actual performance degrading (and, more dangerously, performance can degrade — concept drift — without an easily detectable shift in the input distribution itself). LLM-based systems introduce a related but distinct testing challenge (nondeterminism, evaluation via another model rather than fixed ground truth) that's substantial enough to warrant its own separate discipline — see the llm-testing module — and increasingly, metamorphic and behavioral testing techniques originally built for classical ML are being adapted to test LLM-based systems too, a confident and actively growing overlap between the two modules, not yet a fully unified practice.

---

## Mental model

```
FOUR TEST LAYERS, each catching a DIFFERENT failure mode:

DATA TESTS          "Is the INPUT trustworthy?"
  (schema, nulls,     Catches: silent schema drift, a pipeline bug
   distribution,       feeding garbage, label leakage, class imbalance
   label balance)      nobody accounted for.

MODEL TESTS          "Does the MODEL meet a bar, per SLICE not just
  (accuracy/AUC/F1     aggregate?"
   per slice,          Catches: a model that's 95% accurate overall
   calibration)        and 60% accurate on an underrepresented slice.

BEHAVIORAL TESTS     "Does the model have the CAPABILITY, independent
  (CheckList: MFT,     of whether the training distribution happened
   INV, DIR)           to test it?"
                       Catches: shortcut learning — a model that's
                       "accurate" for the wrong reasons.

METAMORPHIC TESTS   "Does a KNOWN INPUT RELATION produce the expected
  (perturb, check      OUTPUT RELATION, without needing new labels?"
   the relation,        Catches: fairness violations, robustness gaps —
   not the label)        exactly where ground truth is scarce/nonexistent.

DRIFT TESTS (production, ongoing)
  "Has the world underneath the model changed since it was validated?"
  Catches: everything above, silently re-breaking, months after launch,
  as the input distribution or input-output relationship shifts.
```

## How it actually works

**Data tests, concretely** — usually implemented with Great Expectations, Pandera, TFDV (TensorFlow Data Validation), or hand-rolled assertions run as a pipeline step before training or before serving a batch:
```python
# untested sketch — data tests with Pandera-style schema + statistical checks
import pandera as pa
from pandera import Column, Check

training_data_schema = pa.DataFrameSchema({
    "age": Column(int, Check.in_range(0, 120), nullable=False),
    "income": Column(float, Check.greater_than(0), nullable=False),
    "label": Column(int, Check.isin([0, 1]), nullable=False),
})

def test_training_data_quality(df):
    training_data_schema.validate(df)                     # schema-level
    assert df["label"].mean() > 0.05, "positive class < 5% — check for a labeling bug"
    assert df.isnull().mean().max() < 0.01, "a column has >1% nulls — pipeline regression?"
    # detect a specific, historically-real bug class: silent duplicate rows
    assert df.duplicated().mean() < 0.001, "unexpected duplicate rate — check upstream join"
```
The failure mode this catches concretely: a join upstream in the feature pipeline silently starts producing duplicate rows after an unrelated schema change, doubling the weight of a subset of training examples — a bug that never throws an exception and only surfaces as a slightly-off model that nobody traces back to its actual cause without this kind of check.

**Model tests, per slice, not just aggregate** — the single most important discipline gap versus naive ML evaluation:
```python
# untested sketch — per-slice model evaluation, not just aggregate accuracy
from sklearn.metrics import accuracy_score, roc_auc_score

def evaluate_per_slice(model, X_test, y_test, slice_column: str, min_acceptable_auc=0.75):
    results = {}
    for slice_value in X_test[slice_column].unique():
        mask = X_test[slice_column] == slice_value
        preds = model.predict_proba(X_test[mask])[:, 1]
        auc = roc_auc_score(y_test[mask], preds)
        results[slice_value] = auc
        if auc < min_acceptable_auc:
            print(f"FAIL: slice={slice_value} AUC={auc:.3f} below {min_acceptable_auc}")
    overall_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"Overall AUC: {overall_auc:.3f}  (can look fine while a slice above fails)")
    return results
```
The specific, concrete number to internalize: a model can post a 0.90 overall AUC while a slice representing 8% of real traffic sits at 0.65 — an aggregate-only test suite never surfaces this, and it's precisely the failure pattern behind most publicly documented ML fairness incidents.

**Behavioral tests, CheckList-style, for an NLP classifier (sentiment):**
```python
# untested sketch — CheckList-style behavioral tests
def test_mft_negation():  # Minimum Functionality Test
    # simple, targeted: does the model handle basic negation at all?
    assert model.predict("I don't like this product") == "negative"
    assert model.predict("This is not bad at all") == "positive"

def test_invariance_name_swap():  # INV: label should NOT change
    base = model.predict("John was incredibly helpful and kind.")
    swapped = model.predict("Maria was incredibly helpful and kind.")
    assert base == swapped, "prediction changed on a name swap — spurious correlation"

def test_directional_add_negative_clause():  # DIR: label SHOULD change, in a known direction
    base_score = model.predict_proba("The food was great.")["positive"]
    perturbed_score = model.predict_proba("The food was great, but the service was awful.")["positive"]
    assert perturbed_score < base_score, "adding a clear negative clause should lower positive score"
```
The reason these three test types are distinct and all needed: MFT catches a model that can't do the task at all on trivial cases (a real gap, often from insufficient training coverage); INV catches spurious correlations the model learned as shortcuts (name, gender, dialect correlating with the label for reasons unrelated to sentiment); DIR catches a model that's technically "sensitive to input" but not sensitive in the *correct direction* — a subtler and easily-missed failure than either of the other two.

**Metamorphic testing, generalized beyond text — credit scoring example:**
```python
# untested sketch — metamorphic relation for fairness, no new ground truth needed
def test_metamorphic_gender_invariance(credit_model, applicant_profile):
    base_risk = credit_model.predict_default_probability(applicant_profile)
    swapped_profile = {**applicant_profile, "gender": "F" if applicant_profile["gender"] == "M" else "M"}
    swapped_risk = credit_model.predict_default_probability(swapped_profile)
    # metamorphic RELATION being tested: this perturbation should not increase risk
    assert swapped_risk <= base_risk + 0.01, (
        f"gender swap increased predicted default risk by "
        f"{swapped_risk - base_risk:.3f} — investigate proxy discrimination"
    )
```
This is the specific reason metamorphic testing matters for fairness testing in particular: you don't have (and often can't ethically or legally obtain) a labeled "correct" default probability for a counterfactual applicant who is identical except for gender — the metamorphic relation ("shouldn't increase") is testable without that label, which a traditional accuracy-based test structurally cannot express.

**Drift testing — PSI, concretely:**
```python
# untested sketch — Population Stability Index for drift detection
import numpy as np

def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints[0], breakpoints[-1] = -np.inf, np.inf
    expected_pct = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_pct = np.histogram(actual, breakpoints)[0] / len(actual)
    expected_pct = np.clip(expected_pct, 1e-6, None)  # avoid log(0)
    actual_pct = np.clip(actual_pct, 1e-6, None)
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))

# training_scores = model's predicted scores on TRAINING distribution
# production_scores = model's predicted scores on THIS WEEK'S production traffic
psi = population_stability_index(training_scores, production_scores)
# PSI < 0.1: no significant drift. 0.1-0.25: moderate, investigate.
# PSI > 0.25: significant drift — conventionally the alert threshold
```
PSI's specific value: it's a single interpretable number with widely-used, actionable thresholds (a convention originating in credit-risk scorecard monitoring, now applied broadly), unlike a raw KS-test p-value, which becomes oversensitive and flags trivial drift as "significant" at the large sample sizes production monitoring typically has — a real, commonly-cited pitfall of relying on KS tests alone for production drift alerting.

## Build it from scratch

The exercise: build a minimal test-suite scaffold enforcing all four layers against a toy classifier, to internalize that they're checking genuinely different things rather than variations on "run more accuracy checks."
```python
# untested sketch — minimal four-layer ML test harness
class MLTestSuite:
    def __init__(self, model, train_df, test_df, slice_col):
        self.model, self.train_df, self.test_df, self.slice_col = model, train_df, test_df, slice_col

    def run_data_tests(self):
        assert self.train_df.isnull().mean().max() < 0.01
        assert 0.05 < self.train_df["label"].mean() < 0.95

    def run_model_tests(self, min_auc=0.75):
        for slice_val in self.test_df[self.slice_col].unique():
            mask = self.test_df[self.slice_col] == slice_val
            auc = self._auc(self.test_df[mask])
            assert auc >= min_auc, f"slice {slice_val} AUC {auc:.3f} < {min_auc}"

    def run_behavioral_tests(self, checklist_cases: list[dict]):
        for case in checklist_cases:
            pred = self.model.predict(case["input"])
            if case["type"] == "MFT":
                assert pred == case["expected_label"]
            elif case["type"] == "INV":
                other_pred = self.model.predict(case["perturbed_input"])
                assert pred == other_pred
            elif case["type"] == "DIR":
                assert self._compare(pred, case["perturbed_input"], case["direction"])

    def run_metamorphic_tests(self, relations: list[callable]):
        for relation_check in relations:
            assert relation_check(self.model), f"metamorphic relation violated: {relation_check.__name__}"

    def run_all(self):
        self.run_data_tests()
        self.run_model_tests()
        # behavioral + metamorphic need task-specific test cases/relations supplied by the caller
```
Building this scaffold and then trying to actually populate the behavioral/metamorphic layers for a real task is the part that teaches the real skill: it forces naming, explicitly, what capabilities and relations should hold for *this specific model*, which is domain judgment no generic tool provides for you.

## How it's done in production

Production ML testing pipelines run data tests (Great Expectations, TFDV, or Pandera) as a required pre-training and pre-serving pipeline gate; model tests per-slice as part of the model-evaluation/model-registry promotion step (a model doesn't get promoted to a candidate-for-production registry entry unless every tracked slice clears its threshold, not just the aggregate); behavioral/CheckList-style suites maintained as a growing, curated regression suite specific to the task (the CheckList tool itself provides templates and a UI for authoring these at scale, and teams typically build a task-specific library over time rather than starting from scratch each model version); and drift monitoring (Evidently AI, WhyLabs, Arize, or a homegrown PSI/KS dashboard) running continuously against live production traffic, alerting when PSI crosses the significant-drift threshold or when a monitored downstream business metric (not just distributional drift) moves.

| Symptom | Cause | Fix |
|---|---|---|
| Model hits 92% aggregate accuracy in evaluation, discriminates badly against an 8% minority slice discovered post-launch | Evaluation only checked aggregate accuracy, never sliced by the relevant demographic/segment dimension | Add per-slice model tests as a required promotion gate, with slices chosen deliberately (known sensitive attributes, known underrepresented segments), not just whatever the eval script happened to compute |
| Model passes all standard evaluation, fails obviously on trivial negation/name-swap cases a human would never get wrong | No behavioral test suite; aggregate accuracy doesn't surface systematic capability gaps or shortcut learning | Build a CheckList-style MFT/INV/DIR suite specific to the task's known-important capabilities, run as a required regression gate on every model version |
| A fairness audit can't get labeled data for the counterfactual cases it needs to test | Ground truth genuinely doesn't exist for "what should this counterfactual applicant's risk score be" | Use metamorphic testing — assert the *relation* (perturbation shouldn't increase risk) rather than requiring a label for the perturbed case |
| Model performance silently degrades over months in production despite no code or data-pipeline change | Real-world input distribution or input-output relationship drifted away from what the model was trained/validated on (data drift or concept drift) | Add continuous PSI/KS-based distributional monitoring AND downstream business-metric monitoring (don't rely on distributional drift alone — concept drift can occur without a detectable distributional shift) |
| PSI dashboard flags "significant drift" on a feature that turns out to be a benign seasonal pattern (e.g., holiday shopping) | PSI threshold applied without accounting for known cyclical/seasonal variation in the reference window | Use a reference window and cadence that accounts for known seasonality, or track PSI trend over comparable periods (same season last year) rather than a single static training-time baseline forever |

## Tradeoffs & when NOT to use it

- **Don't rely on aggregate accuracy/AUC alone as a promotion gate.** It's necessary but not sufficient — the concrete, real failure pattern (a model excellent in aggregate, badly broken on a specific slice) is exactly what per-slice testing exists to catch, and skipping it is how fairness incidents ship.
- **Don't build a CheckList-style behavioral suite without real domain expertise about which capabilities matter.** A generic, template-driven suite with no task-specific thought behind it produces shallow coverage; the actual value CheckList's own study reports (2x tests, 3x bugs found) came from practitioners applying real domain judgment to the matrix of capabilities, not from mechanically running a template.
- **Don't use metamorphic testing as a substitute for real labeled evaluation where labels are actually available and affordable.** Metamorphic testing's value is specifically for cases where ground truth is scarce or nonexistent (counterfactual fairness cases, edge-case robustness); where real labels exist, a direct model test is a stronger, more specific signal.
- **Don't treat distributional drift (PSI/KS) alone as sufficient production monitoring.** Concept drift — the relationship between inputs and the correct output changing — can occur with no detectable shift in the input distribution itself; pair distributional monitoring with actual downstream performance/business-metric monitoring.
- **Small, low-stakes internal tool with no fairness/regulatory exposure and cheap, plentiful labels?** The full four-layer investment (especially a curated behavioral suite, which takes real time to build well) may be disproportionate; a solid data-test + per-slice model-test pair, with drift monitoring added once the model is actually in sustained production use, is a reasonable proportionate starting point.

---

## Interview questions

### Q1 — Why isn't aggregate accuracy sufficient to validate a model before shipping?
**Testing:** whether the candidate can name the specific slice-masking failure mode, not just say "you should test more."
**Answer:** A model can post a strong aggregate number (say 0.90 AUC) while a specific slice of real traffic — often a minority demographic or an underrepresented segment — sits far below an acceptable bar (say 0.65), and the aggregate metric mathematically dilutes that failure into invisibility if the slice is a small enough fraction of the test set.
**Follow-up trap:** *"So should you always optimize for the worst slice instead of aggregate?"* — no, that's also wrong in isolation; the point is measuring and gating on both, and making an explicit, documented tradeoff decision if they conflict, rather than silently only measuring aggregate and never knowing a conflict exists.

### Q2 — Explain CheckList's three test types (MFT, INV, DIR) and what each catches that the others don't.
**Answer:** Minimum Functionality Tests are simple, targeted examples checking whether the model has a basic capability at all (handling negation, basic entity types) — catches outright capability gaps. Invariance tests apply a label-preserving perturbation (swap a name, a dialect marker) and assert the prediction shouldn't change — catches spurious correlations/shortcut learning. Directional Expectation tests apply a perturbation with a known expected direction of change (add a clearly negative clause) and assert the prediction moves that way — catches a model that's technically sensitive to input but not sensitive in the *correct* direction, a subtler failure than either of the other two.
**Follow-up trap:** *"Which one would catch a model that's memorized training examples rather than learning the task?"* — none directly and reliably; that's closer to a held-out/model-test concern (performance gap between train and a genuinely held-out test set), though a well-designed INV test on inputs structurally similar to training data but with irrelevant details changed can sometimes surface memorization indirectly.

### Q3 — What's a metamorphic relation, and why is it useful specifically when ground truth is unavailable?
**Answer:** A metamorphic relation defines an expected relationship between an input perturbation and the corresponding output change (or non-change) — e.g., "swapping the gender field on a credit application shouldn't increase predicted default risk" — testable and assertable without needing a ground-truth label for the perturbed (counterfactual) input, which is exactly the case where a traditional labeled test can't be constructed at all (you usually can't get a real, labeled "correct" outcome for a hypothetical counterfactual applicant).
**Follow-up trap:** *"Doesn't this just move the problem to defining the right relation?"* — yes, and that's a real, non-trivial domain-expertise requirement — a poorly chosen relation (one that doesn't actually reflect a legitimate fairness/robustness expectation for the task) tests the wrong thing just as confidently as a well-chosen one tests the right thing; the technique doesn't eliminate the need for domain judgment, it just changes where that judgment is applied.

### Q4 — What's the difference between data drift and concept drift, and why does distinguishing them matter for how you respond?
**Answer:** Data drift is a shift in the input feature distribution (e.g., average customer age creeping up over time); concept drift is a shift in the actual relationship between inputs and the correct output (the same input now genuinely warrants a different prediction than it used to, e.g., due to a real behavioral or market change). Data drift alone doesn't necessarily mean the model is now wrong — it might still generalize fine to the shifted distribution — while concept drift means the model actively needs retraining or recalibration regardless of whether the input distribution moved at all.
**Follow-up trap:** *"Can concept drift happen without any detectable data drift?"* — yes, and this is the more dangerous case: the same inputs can now warrant different outputs (a change in real-world behavior/economics) while the input distribution itself looks statistically unchanged, meaning input-distribution monitoring alone would miss it entirely — this is why downstream performance/business-metric monitoring has to be paired with distributional monitoring, not used as a replacement.

### Q5 — What does PSI > 0.25 conventionally indicate, and where does this threshold come from?
**Answer:** PSI (Population Stability Index) compares a reference distribution (e.g., training-time feature or score distribution) against a current one; PSI < 0.1 is conventionally "no significant drift," 0.1-0.25 "moderate, investigate," and >0.25 "significant drift" warranting action. The threshold convention originates in credit-risk scorecard monitoring in financial services, now applied broadly across ML monitoring generally.
**Follow-up trap:** *"Why not just use a KS-test p-value instead of PSI?"* — a raw KS-test p-value becomes oversensitive at the large sample sizes typical of production monitoring, flagging even trivially small, practically-irrelevant distribution shifts as "statistically significant" — PSI's binned, magnitude-based calculation gives a more practically interpretable, actionable signal at scale, which is why it's the more common default for production drift alerting even though KS tests remain useful as a complementary check.

### Q6 — A PSI-based drift alert fires on a feature that turns out to just be a benign seasonal pattern (holiday shopping). What went wrong, and how do you fix the monitoring?
**Answer:** The reference distribution (likely a single static training-time snapshot) didn't account for known cyclical/seasonal variation, so a normal seasonal shift got flagged identically to a genuine, concerning drift. Fix by comparing against a reference window or cadence that accounts for known seasonality (e.g., compare this December against last December, not against a non-seasonal training baseline), or by tracking the PSI trend over comparable periods rather than relying on one static forever-baseline.
**Follow-up trap:** *"Doesn't this risk missing real drift that happens to coincide with a seasonal pattern?"* — yes, this is a genuine tradeoff, not a fully solved problem; a reasonable mitigation is tracking both a seasonally-adjusted comparison and a shorter-window trend simultaneously, and treating a large deviation from *both* as the stronger signal, rather than picking one comparison method and trusting it exclusively.

### Q7 — Why can't behavioral testing (CheckList-style) be fully automated/templated without domain expertise, unlike, say, a linter?
**Answer:** The value CheckList itself demonstrated (roughly 2x more tests written, 3x more bugs found in its published user study) came from practitioners applying real task-specific judgment to decide which capabilities and perturbations actually matter for their model's use case — a generic template run mechanically without that judgment produces shallow, low-signal coverage, because "what capability matters here" and "what perturbation would a real adversary or edge case actually produce" are domain questions, not something a generic tool can infer.
**Follow-up trap:** *"Could an LLM help generate CheckList-style test cases at scale?"* — plausibly yes as an assistive drafting tool, and this is an active area of development, but a human still needs to validate that the generated capability/relation actually matters for the task and that the expected behavior encoded is actually correct — treat LLM-assisted test generation here as a draft to review, not a substitute for the domain judgment step.

### Q8 — Your model's data tests all pass, model tests (including per-slice) all pass, but a specific behavioral capability the business cares about (say, correctly handling sarcasm) fails badly. How do you explain this to a stakeholder who says "but you told me it passed testing"?
**Answer:** Explain that "passed testing" was never a single binary statement — data and model tests validate that the training data was clean and the model meets a statistical performance bar on held-out data, which is necessary but says nothing about specific behavioral capabilities that may not be well-represented in that held-out data's distribution; behavioral testing is a distinct, additional layer specifically because a model can be statistically strong while having a systematic capability gap the aggregate-style tests structurally can't see. The honest framing: testing layers are cumulative, not redundant, and a gap found at one layer doesn't mean the other layers' results were wrong, just incomplete on their own.
**Follow-up trap:** *"Shouldn't behavioral tests have been run before this point?"* — yes, ideally; if they weren't, that's a real process gap to acknowledge directly (missing coverage, not a testing methodology failure) — a senior answer owns the process gap rather than implying it was an inherent, unavoidable limitation of testing ML systems.

### Q9 — How would you design a metamorphic test suite for a computer vision model where you're worried about robustness to real-world camera conditions (lighting, angle, blur)?
**Answer:** Define relations specific to conditions the model will actually face: image rotation within a small realistic range should not change classification (an invariance-style relation, doubling as a dataset augmentation/multiplier technique too); brightness/contrast perturbation within a realistic camera-noise range should not change classification; and for video specifically, adjacent frames in a real frame sequence (e.g., 30fps) should produce similar/consistent predictions (a temporal-consistency relation providing a self-supervisory signal without new labels, catching frame-to-frame prediction flicker that indicates instability). Choose the perturbation ranges from real deployment conditions (actual camera specs, actual lighting variance in the deployment environment), not arbitrary ranges.
**Follow-up trap:** *"What if a large rotation genuinely SHOULD change the classification (e.g., a sideways vs. upright sign)?"* — that's exactly the distinction between an invariance relation and a directional-expectation relation; not every perturbation implies "shouldn't change" — some imply "should change in a specific, known way," and choosing the wrong relation type for a given perturbation produces a test that fails for the wrong reason (flagging correct behavior as a bug).

### Q10 — Staff-level: your org wants to reduce ML testing investment because "the model's aggregate metrics have been stable for two years." What's your response?
**Answer:** Stable aggregate metrics over two years is weak evidence of true system health for two specific reasons named in this module: aggregate metrics structurally can't reveal slice-level degradation (a slice could be silently getting worse while other slices compensate to keep the aggregate flat), and stable *input* distributions don't rule out concept drift (the input-output relationship shifting while the input distribution itself stays put) — plus, "stable" could simply mean nobody's been checking the right things, not that nothing has changed. The response: don't frame this as "more testing forever regardless of evidence," frame it as pointing to the specific things two years of aggregate-metric stability genuinely doesn't tell you, and propose a proportionate, risk-based continuation (e.g., keep per-slice and drift monitoring running continuously since they're cheap relative to an undetected fairness or performance incident, while being open to scaling back the more expensive behavioral-suite-authoring effort if the task's capability surface has genuinely stopped changing).
**Follow-up trap:** *"Isn't this just testing for testing's sake if nothing's ever been found?"* — name the actual asymmetry: the cost of continuous per-slice/drift monitoring is low and ongoing, while the cost of an undetected fairness incident or a silent concept-drift-driven business-metric decline is high and often discovered late — that asymmetry, not a blanket "always test more" instinct, is the actual argument for continuing the cheaper monitoring layers even absent recent findings.

---

## Red flags that fail you

- Treating aggregate accuracy/AUC as sufficient evidence a model is ready to ship.
- Confusing data drift and concept drift, or not knowing a model can suffer one without the other.
- Describing behavioral testing as "just more unit tests" without naming MFT/INV/DIR as distinct mechanisms catching distinct failure modes.
- Proposing metamorphic testing as a replacement for labeled evaluation where real labels are actually available and affordable.
- No answer for why PSI is more commonly used than a raw statistical test p-value for production drift alerting.

## Cheat card

```
FOUR LAYERS: DATA TESTS (is input trustworthy — schema, nulls, label
  balance) -> MODEL TESTS (per-SLICE, not just aggregate, AUC/accuracy/
  calibration) -> BEHAVIORAL TESTS (CheckList: MFT/INV/DIR — capability
  independent of aggregate accuracy) -> METAMORPHIC TESTS (input-output
  RELATIONS, no ground truth needed) -> DRIFT (production, ongoing).

CHECKLIST (Ribeiro et al., ACL 2020, Best Paper): MFT = simple targeted
  capability check. INV = label-preserving perturbation, prediction
  should NOT change (catches shortcut learning). DIR = perturbation
  with known expected direction, prediction SHOULD change that way.
  Published result: ~2x tests written, ~3x bugs found vs. no CheckList.

METAMORPHIC: relation between input perturbation and output relation,
  no new label needed. KEY for fairness (gender/race swap shouldn't
  increase risk score) where counterfactual ground truth doesn't exist.

DRIFT: DATA drift = input distribution shifts. CONCEPT drift = input-
  output RELATIONSHIP shifts (can happen w/ NO detectable data drift —
  more dangerous, invisible to distributional monitoring alone).

PSI: <0.1 no drift, 0.1-0.25 moderate/investigate, >0.25 significant
  (convention from credit-risk scorecards). Preferred over raw KS-test
  p-value for production monitoring — KS becomes oversensitive at
  large production sample sizes, flags trivial shifts as "significant."

MODEL CAN LOOK FINE AND BE BROKEN: 0.90 aggregate AUC masking a
  0.65-AUC slice at 8% of traffic is the single most common
  real-world ML-testing failure pattern.
```

## Sources
- [Beyond Accuracy: Behavioral Testing of NLP Models with CheckList — ACL Anthology](https://aclanthology.org/2020.acl-main.442/) — accessed 2026-07-26
- [Test machine learning the right way: Metamorphic relations — Lakera](https://www.lakera.ai/blog/metamorphic-relations-guide) — accessed 2026-07-26
- [How to test Machine Learning Models? Metamorphic testing — Giskard](https://www.giskard.ai/knowledge/how-to-test-ml-models-4-metamorphic-testing) — accessed 2026-07-26
- [Drift Detection: KS Test, PSI, and Interpreting Signals — StatsTest](https://www.statstest.com/drift-detection-ks-test-psi-interpret-signals) — accessed 2026-07-26
- [Understanding Data Drift and Model Drift — DataCamp](https://www.datacamp.com/tutorial/understanding-data-drift-model-drift) — accessed 2026-07-26
- Ribeiro, M.T., Wu, T., Guestrin, C., Singh, S. — "Beyond Accuracy: Behavioral Testing of NLP Models with CheckList" (ACL 2020, Best Paper)

## Changelog
- 2026-07-26 — created
