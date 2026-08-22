# Hypothesis Testing: Null Hypothesis, p-value, t-test, ANOVA, Chi-Square, Power

> **Track:** T03 Classical ML · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T03-statistics-inference` · **Tags:** fundamentals,critical

## The 30-second version

A p-value is `P(data this extreme or more extreme | H0 is true)` — a statement about how surprising the data would be *if* the null hypothesis held, not `P(H0 true | data)`, and conflating the two is the single most common statistics mistake made by working engineers, not just students. Type I error is falsely rejecting a true null (a false positive, controlled by your significance threshold α); Type II is falsely failing to reject a false null (a false negative, controlled by power, `1 - β`). t-tests compare means of one or two groups, ANOVA extends to three or more groups by comparing between-group to within-group variance, chi-square tests independence of categorical variables — pick based on the number of groups and the data type, not habit. Run five hypothesis tests at α=0.05 with no correction and your family-wise false-positive rate isn't 5%, it's roughly 23%; Bonferroni or Benjamini-Hochberg correction exists specifically to fix this. In A/B testing, checking results early and stopping when you like what you see ("peeking") inflates the true false-positive rate far above your nominal α, and Simpson's paradox — where a trend reverses when a confounding variable is properly accounted for — can make a genuinely worse variant look like a winner in aggregate.

## Why this gets asked

Because the p-value misinterpretation isn't a beginner's mistake that people grow out of — the American Statistical Association issued a formal statement in 2016 specifically because working scientists and engineers with years of experience kept getting it wrong, and the interviewer has almost certainly watched a colleague ship a decision based on "the p-value was 0.03, so there's a 97% chance the effect is real," which is not what a p-value says. They are also testing whether you've personally been burned by peeking at an A/B test dashboard daily and calling it early — nearly everyone who's run real experiments has a story here, and the interviewer wants to know if you learned the lesson or are still doing it.

---

## Lineage: past → present → future

**What came before.** Ronald Fisher's significance testing (1920s-30s) introduced the p-value as an informal, continuous measure of evidence against a null hypothesis, explicitly *not* intended as a fixed accept/reject rule. Jerzy Neyman and Egon Pearson (1930s) built a competing, more rigid framework around fixed error rates — α (Type I) and β (Type II), decided *before* the experiment — designed for repeated decision-making rather than one-off evidence assessment. The pain that produced the modern mess: the field collapsed these two incompatible frameworks into a single hybrid procedure taught in most statistics courses — Fisher's p-value borrowed to make Neyman-Pearson's binary reject/fail-to-reject decision at an arbitrary α=0.05 threshold — which neither Fisher nor Neyman-Pearson individually endorsed, and this hybrid is the direct ancestor of both the widespread misinterpretation of what a p-value means and the "replication crisis" in psychology and biomedical science that came to a head in the early-to-mid 2010s.

**Where it stands now.** The American Statistical Association's 2016 statement on p-values (Wasserstein & Lazar) is the closest thing to an official current consensus document, and its core message is that p-values indicate how incompatible data are with a specified model, not the probability that a hypothesis is true, and that scientific conclusions should not rest on whether a p-value crosses 0.05. [The ASA's Statement on p-Values: Context, Process, and Purpose](https://www.tandfonline.com/doi/full/10.1080/00031305.2016.1154108) — accessed 2026-08-01. In applied industry practice, the live disagreement is over what replaces the simple threshold: Bayesian methods (posterior probability of a real effect, credible intervals) are gaining ground in tech-company experimentation platforms because they answer the question people actually want answered (`P(variant B is better | data)`), but frequentist sequential testing (group sequential designs, always-valid inference) has also matured specifically to fix the peeking problem *within* the frequentist framework rather than abandoning it, and both are genuinely deployed at scale today — this is not settled, and reasonable teams pick either.

**Where it's heading.** Always-valid inference and sequential testing frameworks (mSPRT-based, e.g. what Optimizely and other experimentation platforms use) are becoming the default for online A/B testing specifically because they let you monitor results continuously without inflating Type I error, which matches how product teams actually want to work — this is largely settled and shipping, not speculative. More contested: the push to de-emphasize or ban "statistical significance" language entirely (a 2019 *Nature* comment signed by hundreds of scientists argued for retiring the term) is a live, unresolved debate rather than consensus, and treating "nobody uses p-values anymore" as fact would be wrong — p-values remain the dominant reporting convention in most applied and academic work as of this writing, even as their sole use as a bright-line decision rule is increasingly criticized.

---

## Mental model

```
                    NULL HYPOTHESIS SIGNIFICANCE TESTING, THE ACTUAL LOGIC

  H0: "no effect" (the thing you're trying to find evidence AGAINST)
  H1: "there is an effect" (what you actually believe / want to show)

  Assume H0 is TRUE. Compute how surprising your observed data would be
  under that assumption. That surprise-quantification IS the p-value.

  p-value = P( data this extreme or more | H0 true )   <-- NOT P(H0 true | data)

  small p-value  = "if H0 were true, seeing this would be rare"
                 = evidence AGAINST H0 (doesn't prove H1, doesn't give P(H1 true))

  ┌─────────────────────┬───────────────────┬───────────────────────┐
  │                      │   H0 actually     │   H0 actually         │
  │                      │   TRUE            │   FALSE               │
  ├─────────────────────┼───────────────────┼───────────────────────┤
  │  You REJECT H0       │  TYPE I ERROR (α) │  Correct (power, 1-β) │
  │  You FAIL TO REJECT  │  Correct          │  TYPE II ERROR (β)    │
  └─────────────────────┴───────────────────┴───────────────────────┘

  alpha is a KNOB YOU SET before the experiment (usually 0.05).
  beta (and power = 1 - beta) depends on effect size, sample size, and alpha —
  it's not free; you have to explicitly plan for it via a power analysis.
```

The one thing to internalize: the p-value's randomness comes entirely from the data given a *fixed, assumed-true* null. It says nothing about the probability that the null or alternative is actually true in reality — that would require a prior probability over hypotheses, which frequentist NHST doesn't use (Bayesian inference does, which is exactly why Bayesian methods answer a different, often more intuitive, question).

---

## How it actually works

### The p-value, stated precisely, and why the common misreading is wrong

**Correct:** `p = P(test statistic this extreme or more extreme | H0 is true)`.

**Wrong, but extremely common:** "p = P(H0 is true | data)" or "p = the probability the result is due to chance" or "1 - p is the probability the effect is real."

Why the wrong version is wrong: `P(H0 | data)` requires Bayes' theorem and a prior `P(H0)` — `P(H0|data) = P(data|H0)·P(H0) / P(data)`. The p-value only gives you `P(data|H0)` (the extreme-tail version of it), one term in that equation. Without a prior, you cannot get from "data is unlikely under H0" to "H0 is unlikely," any more than you can conclude "this person is unlikely to be a doctor" purely from "doctors are a small fraction of the population" without also using the evidence about this specific person. [The ASA's Statement on p-Values: Context, Process, and Purpose](https://www.tandfonline.com/doi/full/10.1080/00031305.2016.1154108) — accessed 2026-08-01 lists this exact confusion as principle-violating.

### Type I and Type II error, and the tradeoff between them

- **Type I error (α):** rejecting a true null — a false positive. You set this directly, conventionally at 0.05, meaning you accept a 5% chance of a false alarm *when H0 is actually true*, in the long run across repeated experiments.
- **Type II error (β):** failing to reject a false null — a false negative, missing a real effect. **Power** is `1 - β`, the probability of correctly detecting an effect that's actually there. Power is *not* a fixed knob like α — it depends jointly on the true effect size, the sample size, the variance in the data, and your chosen α, and it has to be explicitly computed (a power analysis) before running the experiment, not discovered afterward.

**The tradeoff, concretely:** lowering α (demanding stronger evidence, e.g. 0.01 instead of 0.05) reduces false positives but, holding everything else fixed, increases β (more true effects get missed) unless you compensate with a larger sample size. This is why you cannot simply "use a stricter threshold" without cost — it directly trades against your ability to detect real effects.

### Power analysis — computing sample size before you run the experiment

```python
from statsmodels.stats.power import TTestIndPower

# Given a desired effect size (Cohen's d), significance level, and desired power,
# solve for the required sample size per group. This is the calculation that should
# happen BEFORE data collection, not after ("how much data do we need to run this test").
analysis = TTestIndPower()
n_per_group = analysis.solve_power(effect_size=0.2, alpha=0.05, power=0.8, ratio=1.0)
# effect_size=0.2 (Cohen's "small") requires roughly 393 per group at alpha=0.05, power=0.8
```
**Concrete numbers worth memorizing:** detecting a small effect (Cohen's d = 0.2) at the conventional α=0.05, power=0.8 requires roughly 393 samples *per group*; a medium effect (d=0.5) needs roughly 64 per group; a large effect (d=0.8) needs roughly 26 per group. This is the arithmetic behind "why did my A/B test need to run for six weeks" — small, realistic effect sizes in product experimentation (a 1-2% conversion lift) require large samples, and underpowered tests that stop early are why so many "no significant difference" results in industry are actually "we never had enough power to detect the effect even if it existed."

### t-test, ANOVA, chi-square — picking the right one

| Test | Compares | Groups | Data type |
|---|---|---|---|
| One-sample t-test | Sample mean vs a known/hypothesized value | 1 | Continuous |
| Independent two-sample t-test | Means of two independent groups | 2 | Continuous |
| Paired t-test | Means of two *related* measurements (before/after on the same subjects) | 2 (paired) | Continuous |
| Welch's t-test | Means of two groups **without assuming equal variance** | 2 | Continuous |
| One-way ANOVA | Means across three or more independent groups | 3+ | Continuous |
| Chi-square test of independence | Association between two categorical variables | 2+ categories each | Categorical |

```python
from scipy import stats

# Independent two-sample t-test. By default scipy assumes equal variance (Student's t);
# pass equal_var=False for Welch's t-test, which is the SAFER DEFAULT in practice —
# real-world groups rarely have exactly equal variance, and Welch's degrades gracefully
# to the same answer as Student's t when variances ARE equal, at negligible cost.
t_stat, p_value = stats.ttest_ind(group_a, group_b, equal_var=False)

# One-way ANOVA: tests whether AT LEAST ONE group mean differs, not which one
f_stat, p_value = stats.f_oneway(group_a, group_b, group_c)

# Chi-square test of independence on a contingency table
from scipy.stats.contingency import chi2_contingency
chi2, p_value, dof, expected = chi2_contingency(contingency_table)
```
[scipy.stats.contingency.chi2_contingency — SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html) — accessed 2026-08-01

**ANOVA's blind spot, precisely:** a significant one-way ANOVA (`p < 0.05`) tells you *at least one* group mean differs from the others — it does not tell you *which* group(s). This is why ANOVA is always followed by **post-hoc tests** (Tukey's HSD is the standard default) that perform pairwise comparisons *while controlling the family-wise error rate* across all those pairwise comparisons — running plain t-tests on every pair after a significant ANOVA reintroduces the multiple-comparisons problem the ANOVA omnibus test was partly designed to sidestep.

```python
from statsmodels.stats.multicomp import pairwise_tukeyhsd
tukey = pairwise_tukeyhsd(endog=values, groups=group_labels, alpha=0.05)
```

### The multiple-comparisons problem, with the actual number

Running `k` independent tests at α=0.05 each, the probability of *at least one* false positive across the family is `1 - (1 - 0.05)^k`, not 0.05. At `k=5`: `1 - 0.95^5 ≈ 0.226` — a 22.6% chance of at least one false alarm even if every single null hypothesis is true. At `k=20`: `1 - 0.95^20 ≈ 0.642` — you're more likely than not to get a false positive somewhere.

**Corrections:**
- **Bonferroni** — divide α by `k` (test each at `α/k`); simple, guarantees family-wise error rate ≤ α, but conservative and loses power fast as `k` grows.
- **Benjamini-Hochberg (fdr_bh)** — controls the *false discovery rate* (expected proportion of false positives *among rejected* hypotheses) rather than the family-wise error rate, which is less conservative and standard in genomics/high-dimensional testing where Bonferroni would kill nearly all power.

```python
from statsmodels.stats.multitest import multipletests

reject, p_corrected, _, _ = multipletests(p_values, alpha=0.05, method="fdr_bh")
# method options include 'bonferroni', 'holm', 'fdr_bh', 'fdr_by', 'fdr_tsbh'
```
[statsmodels.stats.multitest.multipletests — statsmodels documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html) — accessed 2026-08-01

### A/B testing pitfalls — peeking, sample ratio mismatch, Simpson's paradox

**Peeking** is checking a running experiment's results repeatedly and stopping the moment `p < 0.05` appears, rather than waiting for the pre-planned sample size. This inflates the *true* Type I error rate far above the nominal 5%, because you're effectively running many implicit hypothesis tests (one at each peek) and stopping at the first "success," which is exactly the multiple-comparisons problem in disguise — each peek is another chance for a false positive, and stopping only when you see one guarantees you'll see them more often than α suggests. **Fix:** either commit to a fixed sample size decided by a power analysis *before* starting and don't look at significance until you hit it, or use a sequential testing method (group sequential design, always-valid/mSPRT-based inference) explicitly designed to control Type I error under continuous monitoring. [A/B testing using sequential hypothesis — patent filing describing the mechanism](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11593667) — accessed 2026-08-01

**Sample ratio mismatch (SRM):** the actual traffic split observed in an experiment doesn't match the intended split (e.g. you configured 50/50 but observe 52/48 with a chi-square test rejecting the null of equal proportions). This is a red flag that something in the randomization or logging pipeline is broken — a bug causing certain users to be systematically excluded or misassigned — and it *invalidates* the experiment's results regardless of what the treatment-effect p-value says, because the groups are no longer comparable by construction. Checking for SRM (a simple chi-square goodness-of-fit test on the actual group sizes) should be the first thing you do before interpreting any A/B test result, not an afterthought.

```python
from scipy.stats import chisquare
observed = [n_control, n_treatment]
expected = [total / 2, total / 2]     # or whatever the intended split was
chi2, p = chisquare(observed, expected)
# p < 0.05 here means the SPLIT itself is suspect — investigate before trusting any downstream metric
```

**Simpson's paradox:** an aggregate trend reverses when you split by a confounding variable. Classic A/B testing case: variant B looks worse overall, but is actually better *within every individual segment* (new users, returning users, mobile, desktop) — because the segments themselves were unevenly distributed between control and treatment (e.g. treatment got disproportionately more of a low-converting segment by chance or by a rollout bug), the aggregate comparison is confounded even though each within-segment comparison is clean. [Simpson's Paradox In A/B Testing](https://medium.com/homeaway-tech-blog/simpsons-paradox-in-a-b-testing-93af7a2f3307) — accessed 2026-08-01 notes that unequal sample sizes across segments between arms is the most common trigger in practice, which is also the easiest version to detect: check whether segment composition is balanced between control and treatment before trusting the aggregate number.

---

## Build it from scratch

A minimal from-scratch two-sample t-test and the permutation-test equivalent, to show what the closed-form formula and the resampling-based alternative are both actually computing:

```python
import numpy as np
from scipy.stats import t as t_dist

def welch_ttest_from_scratch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Welch's t-test: does not assume equal variance. Matches
    scipy.stats.ttest_ind(a, b, equal_var=False) to floating-point precision."""
    mean_a, mean_b = a.mean(), b.mean()
    var_a, var_b = a.var(ddof=1), b.var(ddof=1)
    n_a, n_b = len(a), len(b)

    se = np.sqrt(var_a / n_a + var_b / n_b)
    t_stat = (mean_a - mean_b) / se

    # Welch-Satterthwaite degrees of freedom — the formula that makes this "Welch's" t-test
    df = (var_a / n_a + var_b / n_b) ** 2 / (
        (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    )
    p_value = 2 * (1 - t_dist.cdf(abs(t_stat), df))    # two-tailed
    return t_stat, p_value


def permutation_test(a: np.ndarray, b: np.ndarray, n_permutations: int = 10_000, seed: int = 0) -> float:
    """Model-free alternative: shuffle group labels, recompute the mean difference,
    ask how often the SHUFFLED difference is as extreme as the OBSERVED one. This is
    literally the p-value definition made concrete — no distributional assumption needed."""
    rng = np.random.default_rng(seed)
    observed_diff = abs(a.mean() - b.mean())
    combined = np.concatenate([a, b])
    n_a = len(a)
    count_as_extreme = 0
    for _ in range(n_permutations):
        rng.shuffle(combined)
        perm_diff = abs(combined[:n_a].mean() - combined[n_a:].mean())
        if perm_diff >= observed_diff:
            count_as_extreme += 1
    return count_as_extreme / n_permutations
```

The permutation test is worth building once because it makes the p-value definition unavoidable and concrete: it is *literally* "the fraction of relabelings of the data at least as extreme as what we observed, under the assumption that the labels don't matter (H0)." Reference lab: `(lab pending)` (build if not present) — includes a test asserting the from-scratch Welch's t-test matches `scipy.stats.ttest_ind(equal_var=False)` and that the permutation test converges to the same p-value as the closed-form test on normally-distributed data as `n_permutations` grows.

---

## How it's done in production

| Tool | What it adds |
|---|---|
| `scipy.stats` | Closed-form implementations of t-test, ANOVA, chi-square — the reference implementations everything else is checked against |
| `statsmodels` | Post-hoc tests (Tukey HSD), multiple comparison correction (`multipletests`), power analysis (`TTestIndPower`, `NormalIndPower`), and more complex ANOVA designs (two-way, repeated measures) |
| Experimentation platforms (Optimizely, Statsig, GrowthBook, in-house) | Sequential/always-valid testing so product teams can monitor dashboards continuously without manually correcting for peeking; automated SRM detection; pre-registered metrics to prevent post-hoc metric shopping |
| Bayesian A/B testing tools (e.g. `PyMC`, or built-in Bayesian modes in experimentation platforms) | Report `P(variant B > variant A | data)` directly, sidestepping the p-value interpretation problem entirely, at the cost of needing to specify (and defend) a prior |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Team reports "p=0.03, so we're 97% confident B is better" | The core p-value misinterpretation — treating `P(data\|H0)` as `P(H1\|data)` | Report and communicate what the p-value actually is, or switch to a Bayesian framework that directly answers the probability-of-effect question people want |
| An A/B test that "kept improving the longer we watched" and hit significance right when someone checked | Peeking — informal sequential testing without the statistical correction that makes sequential monitoring valid | Fix sample size via power analysis before starting and don't check significance early, or adopt a proper sequential testing method (group sequential, mSPRT) |
| 15 metrics tested in one experiment report, 2 came back significant, team ships based on those 2 | Multiple comparisons — at k=15 tests, family-wise false positive rate is `1-0.95^15 ≈ 0.537`, over 50% | Pre-register a small number of primary metrics before running the experiment; apply Bonferroni or Benjamini-Hochberg correction to any secondary/exploratory metrics |
| Aggregate A/B result says treatment is worse, but every individual customer segment shows treatment is better | Simpson's paradox driven by unequal segment allocation between arms | Check segment balance between control/treatment before trusting the aggregate; report segment-level results, not just the pooled number |
| Experiment's actual traffic split is 54/46 instead of the configured 50/50 | Sample ratio mismatch — a bug in randomization, logging, or bot filtering that differentially affects one arm | Run a chi-square goodness-of-fit check on group sizes as a pre-check before interpreting any result; treat any significant SRM as grounds to invalidate the experiment, not a footnote |
| ANOVA comes back significant, team runs six pairwise t-tests to find "the" difference and reports all significant pairs | Reintroducing the multiple-comparisons problem the ANOVA was meant to control for | Use a proper post-hoc test (Tukey's HSD) that corrects for the number of pairwise comparisons, not raw t-tests |
| A test with a real 2% effect keeps coming back "not significant" across several underpowered small samples | Insufficient power for the true (small) effect size — nobody ran a power analysis to size the sample beforehand | Compute required sample size from the expected effect size before running the experiment; report power alongside "not significant," since "no evidence of an effect" is different from "evidence of no effect" |

---

## Tradeoffs & when NOT to use it

- **Don't run a t-test on data you haven't checked for the assumptions it needs.** Independent two-sample t-tests assume (approximate) normality and, in the Student's variant, equal variance; with clearly non-normal data or small samples, prefer a non-parametric alternative (Mann-Whitney U) or a permutation test, which makes no distributional assumption at the cost of needing more compute.
- **Don't run ANOVA and stop there.** A significant omnibus ANOVA result tells you *something* differs, not *what*; always follow with a proper post-hoc test if you need to know which groups differ.
- **Don't peek at a running experiment's dashboard and call it early because the p-value looks good today.** This is not a stylistic nitpick, it's a direct inflation of your actual false-positive rate, often severely — the "test showed significance after 3 days" story is frequently just this bug.
- **Don't run dozens of metrics through an A/B test and report whichever came back significant.** Pre-register your primary metric(s); treat anything discovered post-hoc as a hypothesis for a *new*, separate experiment, not a finding.
- **Don't treat "not statistically significant" as proof of "no effect."** An underpowered test with `p=0.12` on a real small effect is a failure to detect, not evidence of absence — report power and effect-size confidence intervals, not just the p-value.
- **When NOT to use classical NHST at all:** when what stakeholders actually want is "what's the probability variant B is better, and by how much" — that's a Bayesian question, and forcing it through a p-value framework produces answers people will (understandably) misinterpret as answering that question when it technically doesn't. Consider a Bayesian approach when decision-makers need a direct probability statement and can tolerate specifying a prior.
- **Chi-square test of independence requires adequate expected cell counts** (a common rule of thumb: expected count ≥ 5 in at least 80% of cells) — with sparse contingency tables, use Fisher's exact test instead, which doesn't rely on the chi-square distribution's large-sample approximation.

---

## Interview questions

### Q1 — State the definition of a p-value precisely.
**Testing:** the single most-failed question in applied statistics interviews.
**Answer:** The probability, assuming the null hypothesis is true, of observing a test statistic at least as extreme as the one actually observed. Formally, `P(data this extreme or more | H0 true)`. It is not the probability that the null hypothesis is true, not the probability the result is "due to chance" in the sense of quantifying belief in H0, and not one minus the probability the alternative is true.
**Follow-up trap:** *"So a p-value of 0.03 means there's a 97% chance the effect is real?"* — no, and this is the exact conflation the ASA's 2016 statement calls out explicitly. Getting from `P(data|H0)` to `P(H0|data)` requires Bayes' theorem and a prior probability on H0, which a frequentist p-value doesn't use or provide. Say this precisely; garbling it here is close to a disqualifying answer at senior level.

### Q2 — Define Type I and Type II error, and explain the tradeoff between them.
**Answer:** Type I (α) is rejecting a true null hypothesis — a false positive. Type II (β) is failing to reject a false null — a false negative, missing a real effect; power is `1 - β`. Holding sample size and effect size fixed, lowering α to reduce false positives increases β, since you're demanding stronger evidence before rejecting, which necessarily makes you miss more real (but modest) effects. You escape this tradeoff only by increasing sample size, which reduces both simultaneously.
**Follow-up trap:** *"Your team lowered alpha to 0.01 to be 'more rigorous.' What did they just do to power, and what should they have done instead?"* — they reduced power without acknowledging it, likely increasing the false-negative rate for genuinely real effects. The correct move, if stricter significance is genuinely needed (e.g. for multiple-comparisons correction), is to also increase sample size via a power analysis to compensate, not just tighten the threshold and hope.

### Q3 — Walk through a power analysis: what inputs do you need, and what number does it produce?
**Answer:** Inputs: the expected effect size (often Cohen's d for continuous outcomes), the significance level α, and the desired power (conventionally 0.80). Output: the required sample size per group. Concretely, at α=0.05 and power=0.80, detecting a small effect (d=0.2) needs roughly 393 per group, a medium effect (d=0.5) needs roughly 64 per group, and a large effect (d=0.8) needs roughly 26 per group — the sample size requirement grows sharply as the effect you're trying to detect shrinks.
**Follow-up trap:** *"Your product change has a real but small true effect (d≈0.1) and you only collected 200 users per group. What should you conclude from a non-significant result?"* — nothing conclusive about whether the effect exists; 200 per group is well under the roughly 1,570 needed to reliably detect d=0.1 at standard power, so this is an underpowered test, and "not significant" here means "we didn't have enough data to tell," not "there's no effect."

### Q4 — When do you use a t-test versus ANOVA versus chi-square?
**Answer:** t-test compares means between one or two groups on continuous data (paired or independent, and Welch's if you can't assume equal variance). ANOVA extends to three or more groups' means by comparing between-group variance to within-group variance. Chi-square tests independence/association between two categorical variables using a contingency table. The choice is driven by number of groups and data type, not by which test you're more comfortable computing.
**Follow-up trap:** *"You have 3 groups and want to compare means — why not just run 3 pairwise t-tests instead of ANOVA?"* — because that reintroduces the multiple-comparisons problem: 3 pairwise tests at α=0.05 each gives a family-wise error rate of `1-0.95^3≈14.3%`, not 5%. ANOVA's omnibus test controls the overall false-positive rate for "is there any difference at all" in one test, and if it's significant, a proper post-hoc test (Tukey's HSD) then does the pairwise comparisons while correcting for their number.

### Q5 — A significant one-way ANOVA — what have you actually learned, and what haven't you?
**Answer:** You've learned that at least one group's mean differs from at least one other's — the omnibus F-test rejects the null that all group means are equal. You have not learned which group(s) differ, by how much, or in which direction; that requires a post-hoc test.
**Follow-up trap:** *"Can you skip ANOVA and go straight to post-hoc pairwise tests?"* — some argue for this in practice, but the standard defense of running ANOVA first is that it provides a single, correctly-calibrated omnibus test before you commit to the multiple-comparisons exposure of pairwise testing — going straight to pairwise tests without ANOVA as a gate is defensible only if you're already using a correction method (like Tukey's) that accounts for all pairwise comparisons regardless.

### Q6 — Explain the multiple-comparisons problem with the actual arithmetic, and name two corrections.
**Answer:** Running `k` independent tests each at α=0.05, the probability of at least one false positive across the family is `1-(1-0.05)^k`. At k=5, that's about 22.6%; at k=20, about 64.2% — you're more likely than not to see a spurious "significant" result somewhere. Bonferroni divides α by k per test, simple and guarantees the family-wise error rate but loses power quickly as k grows; Benjamini-Hochberg (`fdr_bh`) controls the false discovery rate — the expected proportion of false positives *among rejections* — which is less conservative and standard when testing many hypotheses (genomics, large-scale A/B metric dashboards).
**Follow-up trap:** *"Your experiment report has 20 metrics and 3 came back significant at raw p<0.05. After Bonferroni correction at k=20, none survive. Do you ship the feature?"* — the honest answer is that with 20 uncorrected tests, expecting roughly 1 false positive by chance alone (20 × 0.05 = 1) means 3 "hits" isn't strong evidence on its own; without pre-registration of a primary metric, the responsible move is to treat the 3 as hypothesis-generating for a focused follow-up experiment, not as grounds to ship.

### Q7 — What is "peeking" in A/B testing, why does it break your statistics, and how do you fix it?
**Answer:** Peeking is checking a running experiment's significance repeatedly and stopping the moment it crosses your threshold, rather than committing to a pre-planned sample size or duration. It breaks the statistics because each peek is effectively another implicit hypothesis test, and stopping at the first "significant" peek is a selection process that inflates the true Type I error rate far above the nominal α — this is the multiple-comparisons problem wearing a different costume. Fix: either fix the sample size via a power analysis beforehand and don't interpret significance before reaching it, or use a sequential testing method (group sequential design, or an always-valid/mSPRT-based approach) explicitly built to control Type I error under continuous monitoring.
**Follow-up trap:** *"Your platform's dashboard shows real-time significance and product managers check it daily — is that inherently broken?"* — not necessarily, if the underlying statistical engine is a proper sequential testing method (this is exactly what modern experimentation platforms like always-valid inference are for) — the problem isn't looking often, it's looking often *using a method that assumes you only look once*. Ask which statistical engine is under the dashboard before judging whether daily checking is safe.

### Q8 — What is sample ratio mismatch (SRM) and why should you check for it before trusting any A/B test result?
**Answer:** SRM is when the actual observed split between control and treatment doesn't match the intended split (e.g. configured 50/50, observed 54/46, with a chi-square goodness-of-fit test rejecting equal proportions). It's a symptom of a broken randomization, logging, or bot-filtering pipeline, and it invalidates the experiment's causal comparison regardless of what the treatment-effect p-value says, because the groups may no longer be comparable — whatever mechanism skewed the ratio may also have skewed *composition*, introducing exactly the kind of confounding that makes a treatment effect estimate meaningless.
**Follow-up trap:** *"Your SRM check comes back with p=0.06 — technically not significant at 0.05. Do you proceed?"* — treat SRM checks with more caution than a normal hypothesis test rather than less; a borderline SRM result is a reason to dig into the pipeline (check for known-bug patterns, examine subgroup-level ratios) rather than a green light, because an undetected randomization bug is far more costly than a normal false positive on a business metric.

### Q9 — Explain Simpson's paradox with an A/B testing example, and how you'd detect it.
**Answer:** An aggregate metric can show variant B losing to variant A overall, while B actually wins within every individual segment (e.g., new users, returning users) — this happens when segment composition is unbalanced between the two arms (say, treatment happened to get proportionally more new users, who convert at a lower baseline rate regardless of variant), so the aggregate comparison is confounded by segment mix even though every within-segment comparison is clean. Detect it by checking segment balance between control and treatment before trusting the pooled result, and by reporting segment-level breakdowns alongside the aggregate number as standard practice, not just when something looks off.
**Follow-up trap:** *"If your randomization was truly random, can Simpson's paradox still happen?"* — yes, especially with a large number of segments and imperfect randomization in practice (non-uniform traffic ramp, geographic rollout order, time-of-day effects during a partial rollout) — true randomization at the *user* level doesn't guarantee balance across every possible way you might later choose to segment, particularly with smaller sample sizes or many segment cuts explored after the fact.

### Q10 — Design the statistical plan for an A/B test on a checkout flow change, expecting roughly a 1% relative conversion lift, where the team has historically had problems with peeking and post-hoc metric shopping.
**Testing:** synthesis of the whole module under realistic constraints.
**Answer:** Pre-register a single primary metric (conversion rate) and compute required sample size via a power analysis using the expected 1% relative lift and historical conversion variance — likely a large sample given how small that effect is. Use a sequential testing framework so the team can monitor without manually inflating Type I error from peeking, removing the temptation to stop early on a raw p-value check. Run an SRM check automatically before any result is surfaced. Limit secondary/exploratory metrics to a pre-declared list with Benjamini-Hochberg correction applied, and treat any interesting metric discovered outside that list as a hypothesis for a follow-up experiment, explicitly not a finding from this one. Report segment-level breakdowns alongside the aggregate to catch Simpson's-paradox-style confounding from uneven rollout.
**Follow-up trap:** *"Leadership wants an answer in one week but the power analysis says you need six."* — surface the actual tradeoff rather than silently shipping the experiment underpowered: either accept you'll only be powered to detect a larger effect than you actually expect (and be explicit that a null result at one week doesn't rule out a real 1% effect), or reduce the risk profile of what you're willing to conclude, or extend the timeline. Presenting "we can look, but here's exactly what confidence you'll have" is the senior move over either refusing or silently complying.

### Q11 — Your chi-square test of independence between two categorical variables gives a warning about low expected cell counts. What do you do?
**Answer:** Chi-square's p-value relies on a large-sample approximation to the chi-square distribution, and it becomes unreliable when expected cell counts are small (a common threshold cited is expected count ≥ 5 in at least 80% of cells). With sparse tables — common with rare categories or small samples — use Fisher's exact test instead, which computes the exact probability under the null without relying on that asymptotic approximation.
**Follow-up trap:** *"Does Fisher's exact test scale to large contingency tables?"* — computing the exact hypergeometric probabilities becomes expensive for large tables with many categories or larger sample sizes, which is exactly why chi-square (an efficient approximation) is preferred once cell counts are large enough for the approximation to hold — the two methods are complementary based on sample size, not competing defaults.

---

## Red flags that fail you

- Saying a p-value is the probability the null hypothesis is true.
- Not knowing that peeking inflates the true Type I error rate.
- Running an ANOVA and treating "significant" as answering "which group differs."
- Running multiple tests with no mention of correction.
- Not knowing what sample ratio mismatch is or why it invalidates a test.
- Treating "not statistically significant" as proof of no effect.
- Being unable to explain, even roughly, how sample size relates to effect size and power.
- Not recognizing Simpson's paradox as a real risk in segmented A/B analysis.

---

## Cheat card

```
P-VALUE (get this exactly right)
  p = P(data this extreme or more | H0 TRUE)     NOT P(H0 true | data)
  going from P(data|H0) to P(H0|data) needs Bayes' theorem + a PRIOR — p-value alone can't do it

TYPE I / II
  Type I (alpha)   reject a TRUE null      = false positive     -- you SET this, usually 0.05
  Type II (beta)   fail to reject a FALSE null = false negative -- power = 1 - beta
  lower alpha (fixed n) -> higher beta. Only more DATA reduces both.

POWER ANALYSIS (alpha=0.05, power=0.80, per group, Cohen's d)
  d=0.2 (small)  ~393/group     d=0.5 (medium) ~64/group     d=0.8 (large) ~26/group
  "not significant" with low power = "couldn't tell," NOT "no effect"

TEST CHOICE
  t-test (1-2 groups, continuous) -- Welch's (unequal var) is the SAFER DEFAULT over Student's
  ANOVA (3+ groups, continuous)  -- significant = SOMETHING differs, not WHICH. Needs post-hoc.
  chi-square (categorical x categorical)  -- needs expected cell count >= 5 in ~80% of cells,
                                             else use Fisher's exact test

POST-HOC   Tukey's HSD after significant ANOVA — corrects pairwise comparisons for their count.
           Never run raw pairwise t-tests after ANOVA; reintroduces multiple-comparisons problem.

MULTIPLE COMPARISONS   k independent tests @ alpha=0.05: P(>=1 false positive) = 1-0.95^k
  k=5  -> 22.6%     k=20 -> 64.2%
  Bonferroni: alpha/k per test, controls family-wise error, conservative
  Benjamini-Hochberg (fdr_bh): controls FALSE DISCOVERY RATE, less conservative, standard at scale

A/B PITFALLS
  PEEKING          checking + stopping early inflates true Type I error far above nominal alpha
                   fix: fixed sample size decided upfront, OR sequential/always-valid testing
  SAMPLE RATIO MISMATCH (SRM)   actual split != intended split -> randomization/logging bug ->
                   invalidates the WHOLE test. Chi-square check on group sizes BEFORE trusting results.
  SIMPSON'S PARADOX   aggregate trend reverses vs every individual segment, caused by unequal
                   segment allocation between arms. Check segment balance before trusting aggregate.
```

## Sources

- [The ASA's Statement on p-Values: Context, Process, and Purpose (Wasserstein & Lazar, 2016)](https://www.tandfonline.com/doi/full/10.1080/00031305.2016.1154108) — accessed 2026-08-01
- [scipy.stats.contingency.chi2_contingency — SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html) — accessed 2026-08-01
- [statsmodels.stats.multitest.multipletests — statsmodels documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html) — accessed 2026-08-01
- [Simpson's Paradox In A/B Testing — HomeAway Tech Blog](https://medium.com/homeaway-tech-blog/simpsons-paradox-in-a-b-testing-93af7a2f3307) — accessed 2026-08-01
- [A/B testing using sequential hypothesis testing (mechanism description)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11593667) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
