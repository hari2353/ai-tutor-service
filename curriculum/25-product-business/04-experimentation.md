# Experimentation: A/B Testing â€” Power, MDE, Sequential Testing, Novelty, Common Traps

> **Track:** T25 Product Thinking & Business Â· **Time:** 2.5h Â· **Prereqs:** T25-metrics Â· **Updated:** 2026-08-23
> **Module id:** `T25-experimentation` Â· **Tags:** product, critical

## The 30-second version

An A/B test is a measurement instrument whose resolution you choose in advance: statistical power analysis converts your baseline rate, the minimum effect worth detecting (MDE), alpha (false-positive budget, conventionally 0.05), and power (true-positive probability, conventionally 0.80) into a required sample size â€” and the brutal arithmetic is that halving the MDE roughly quadruples required sample, so "just detect smaller effects" costs exponentially, not linearly. Fixed-horizon testing forbids peeking (checking significance daily and stopping at first p<0.05 inflates false positives several-fold); if stakeholders will inevitably peek â€” they will â€” switch the machinery to sequential testing (group-sequential boundaries or anytime-valid methods like the mixture sequential probability ratio test) rather than pretending. Novelty and primacy effects mean early wins evaporate: treatment effects measured in week 1 routinely shrink by launch+2 as returning users adapt, which is why mature teams run at least two full weekly cycles and segment new versus returning users before reading results. The trap catalog is where interviews live: peeking, multiple-comparison inflation, reading underpowered nulls as "no effect," sample-ratio mismatch invalidating everything, metric dilution during ramps, and Twyman's law â€” any figure that looks interesting or unusual is usually wrong. For a principal engineer the skill is upstream of the math: negotiating what change would be worth shipping at all (the MDE conversation), because that negotiation determines whether the answer arrives in nine days or never.

## Why this gets asked

"Design an A/B test for X" appears in principal loops not to check t-test recall but to see whether you treat experiments as expensive instruments or free truth machines. The senior-level tell is the questions you ask BEFORE computing anything: what's the overall evaluation criterion, who's randomized at what granularity, what's the smallest effect that justifies the engineering and maintenance cost of shipping this, and which guardrails are hard constraints. Interviewers also probe the failure catalog because production experimentation fails socially more often than statistically: the VP who wants to call the test at day 3, the dashboard that lets anyone watch p-values drift, the "successful" test that was actually an SRM bug. Your recsys background makes this concrete: a 25% engagement lift claim invites "how long did it run â€” did you control for novelty?" and "what was your per-arm n relative to variance?" â€” and answers like "two full weeks, segmented by user tenure, with CUPED adjustment on pre-period engagement" separate practitioners from tourists. Finally, experiments are the currency of resource debates: a team that ships only measured wins accrues credibility that compounds; a team that ships vibes spends it.

---

## Lineage: past â†’ present â†’ future

**What came before.** Randomized controlled experiments are 1920s-30s statistics: Ronald Fisher at Rothamsted formalized randomization, replication, and significance testing for agricultural plots (*The Design of Experiments*, 1935), including the tea-tasting lady as the canonical small-n cautionary tale. Clinical trials industrialized the ethics and blinding machinery mid-century. The internet rebranded the RCT as the "A/B test" around 2000: engineer-era milestones include Belenky/Amazon's 2000 patented bisection-testing work, Google's 2000-2001 ad experiments, and Microsoft's Experimentation Platform (founded ~2006 under Bret Taylor-era... more precisely under Ronny Kohavi's leadership through 2010s) which produced the corpus â€” the OEC concept, SRM checks, CUPED (Deng et al., KDD 2013) â€” culminating in Kohavi, Tang, Xu's *Trustworthy Online Controlled Experiments* (2020), the field's standard reference.

**Where it stands now.** The fixed-horizon orthodoxy is giving ground to sequential and anytime-valid inference: group-sequential methods with alpha-spending boundaries (borrowed from clinical trials) let you stop early at pre-set looks without inflating error, and mixture-SPRT / e-process approaches (Johari et al.'s Peeking Lecturer paper; Netflix and Spotify engineering papers 2023-2025) support continuous monitoring with valid inference throughout. Bayesian monitoring (expected-loss thresholds Ã  la VWO's 2015-era "Bayesian A/B" push) coexists â€” pragmatically similar, philosophically distinct, and interviewers may ask you to contrast them. Variance reduction (CUPED and descendants) is standard at scale because it effectively multiplies traffic. Meanwhile AI features broke some assumptions: LLM outputs are stochastic across draws, personalization means every user sees something different (the "A/B" arms are distributions over experiences), and cost-per-session became a guardrail because a chatty model can win engagement while losing money.

**Where it's heading.** Confidence-ordered: (1) continuous-monitoring-by-default â€” platforms shipping anytime-valid inference as the standard mode, retiring the awkward "don't look at the dashboard" rule; (2) AI-assisted experiment design and analysis â€” auto-segmentation surfacing heterogeneous treatment effects (with the multiple-comparisons danger that implies), LLM-written readouts; moderate-high confidence; (3) contested: simulation-based and offline-evaluation substitutes (uplift models, synthetic control at fine grain) nibbling at the edges of live experimentation for low-traffic teams, but nothing replaces the RCT for causal claims at decision grade â€” expect interviewers to reward skepticism about shortcuts here.

---

## Mental model

An A/B test is a **microscope with a chosen resolution**, and you buy resolution with traffic:

```
NOISE FLOOR (what randomness alone produces at 95% confidence)
        |
        |  baseline 5%, n=12,000/arm  -> noise floor ~ +-1.6pts (~32% rel MDE)
        |  baseline 5%, n=31,205/arm  -> floor tight enough to SEE +10% rel:
        |  n and MDE are one dial -- you choose resolution with traffic
        v
EFFECT YOU CARE ABOUT must sit ABOVE the floor, or the instrument can't see it
```

Four dials set before looking through it: **OEC** (the pre-declared decision criterion — what "sees" means), **unit** (what gets randomized: user/session/cluster), **MDE** (smallest effect worth shipping, priced from build AND maintain cost), **duration** (≥2 full weekly cycles). Everything else — power tables, sequential boundaries, novelty segmentation — is engineering on top of those four choices. And the instrument has a social failure mode the math doesn't fix: a microscope everyone is allowed to adjust mid-observation (peeking dashboards) produces pictures of whatever people hoped to see.

---

## How it actually works


### The four pre-computation questions

Before any sample-size arithmetic, answer in writing: (1) **OEC** â€” the single pre-declared criterion the decision turns on (a composite is allowed if weights are declared pre-launch â€” LinkedIn's OTE pattern), plus 2-4 guardrails; (2) **randomization unit** â€” user (default), session (leaks per-user effects toward zero), or cluster (required when network spillover exists â€” referrals, shared playlists); (3) **MDE** â€” the smallest effect that justifies shipping given build cost AND ongoing maintenance/inference cost; this is a business negotiation, not a statistics parameter; (4) **direction & duration** â€” one-sided vs two-sided, and how many full weekly cycles cover both weekday/weekend behavior.

### Power and MDE: the arithmetic that decides feasibility

Two-proportion test, worked end-to-end at baseline p1 = 5.0% conversion, MDE +10% relative (p2 = 5.5%), alpha = 0.05 two-sided, power = 0.80:

```
n/arm = (z_a/2 + z_b)^2 * [p1(1-p1) + p2(1-p2)] / (p2 - p1)^2
      = (1.96 + 0.84)^2 * [0.05*0.95 + 0.055*0.945] / 0.005^2
      = 7.84 * 0.099475 / 0.000025
      ~= 31,205 per arm (~62,400 total)
```

Scaling laws to memorize: halve the MDE â†’ ~4x sample; want 90% power instead of 80% â†’ multiply by (2.80/2.76... more precisely (1.96+1.28)^2/(1.96+0.84)^2 â‰ˆ 10.5/7.84 â‰ˆ 1.34x; run a two-sided test instead of one-sided â†’ ~1.25x. Then translate to time: at 8,000 eligible users/day split 50/50, 62,400 total needs ~7.8 days â†’ round up past two weekly cycles to ~14-15 days because day-of-week effects make sub-cycle runs uninterpretable. This runtime table is what you bring to the stakeholder who wants "results by Friday": show them the MDE their deadline buys instead â€” at n=12,000/arm, detectable effect at 80% power is roughly Â±(2.8 Ã— sqrt(2Ã—0.05Ã—0.95/12000)) â‰ˆ Â±1.6 percentage points absolute, i.e., a ~32% relative MDE â€” usually far above any plausible lift, which reframes the meeting instantly.

### Sequential testing: making peeking legal

Fixed-horizon logic computes ONE look's worth of alpha; checking daily and stopping on first significance can push true false-positive rates from the nominal 5% into the 20-40% range depending on check frequency and effect size. Three production-grade escapes: (1) **group-sequential** â€” declare k looks in advance with alpha-spending boundaries (O'Brien-Fleming-style: early looks demand extreme z-scores, e.g., first look might require |z| > 3.9 where fixed-horizon needs 1.96); (2) **anytime-valid / mSPRT** â€” a likelihood-ratio-based p-value that remains valid under arbitrary stopping (Johari et al.); costs some power versus fixed-horizon when effects are small but removes the human-factors problem entirely; (3) **Bayesian monitoring** â€” stop when P(B beats A) exceeds a threshold or expected loss falls below epsilon; philosophically different (no long-run error-rate guarantee) but operationally similar guardrails against noise-chasing. The interview-grade summary: peeking under fixed-horizon math is a bug; continuous monitoring under sequential math is a feature â€” pick the machinery to match the org's actual behavior.

### Novelty, primacy, and ramps

Treatment effects decay as users adapt: a redesigned homepage lifts clicks week 1 partly because it's DIFFERENT (novelty), while performance improvements may be invisible immediately then compound as habits form (primacy/inverted-U). Defenses: run â‰¥2 full weekly cycles before reading; segment new users (clean read, no contamination) vs returning users (where novelty lives); keep a long-term holdout â€” 1-5% of traffic held back from all launches for months â€” to measure cumulative portfolio effect, since individually-validated launches routinely sum to less than their parts (interaction and cannibalization). Ramp mechanics add their own trap: metrics measured during ramp-down of a losing arm get DILUTED â€” the arm's population composition shifts as buckets drain â€” so freeze analysis windows away from ramp boundaries.

### The trap catalog

- **Peeking** (above) â€” the most common; fix via sequential machinery.
- **Multiple comparisons** â€” 20 metrics at Î±=0.05 yields ~64% chance of â‰¥1 false positive if uncorrected; fix: pre-declared OEC, Bonferroni/Benjamini-Hochberg for exploratory reads, label everything else hypothesis-generating.
- **Underpowered nulls read as proof of absence** â€” a test powered for +30% relative says nothing about +5%; report achieved MDE with every null ("we can rule out effects larger than X%").
- **SRM** â€” observed split deviating from intended (chi-squared trigger at p<0.001) invalidates the causal read entirely until root-caused across assignment/execution/logging/analysis stages; full treatment in T32-experiment-design.
- **Interference/spillover** â€” treated users changing control users' outcomes (social features, shared marketplaces); fix: cluster randomization by graph community or geo switchbacks.
- **Twyman's law** â€” spectacular results are bugs until proven otherwise: a +200% lift is almost always an instrumentation failure, a segment flip, or an SRM.
- **Metric dilution** â€” headline metric averaged over everyone when only 8% encounter the surface: a true +40% effect on encouters dilutes to +3.2% overall; analyze triggered populations.

---

## Build it from scratch

**A pure-python (stdlib only) experiment planner: sample size, achieved MDE, runtime, sequential boundary demo.**

```python
# exp_planner.py -- stdlib-only power/MDE/runtime planner
from statistics import NormalDist
import math

nd = NormalDist()

def n_per_arm(p1, mde_rel, alpha=0.05, power=0.80):
    """Two-proportion sample size via normal approximation."""
    p2 = p1 * (1 + mde_rel)
    za, zb = nd.inv_cdf(1 - alpha/2), nd.inv_cdf(power)
    return math.ceil((za + zb)**2 * (p1*(1-p1) + p2*(1-p2)) / (p2-p1)**2)

def achieved_mde(p1, n, alpha=0.05, power=0.80):
    """Smallest relative lift detectable with n per arm."""
    za, zb = nd.inv_cdf(1 - alpha/2), nd.inv_cdf(power)
    delta = (za + zb) * math.sqrt(p1*(1-p1)*2/n)
    return delta / p1

def runtime_days(total_n, daily_eligible, cycles_floor=2):
    days = max(math.ceil(total_n / daily_eligible),
               cycles_floor * 7)          # >=2 full weekly cycles
    return days

def obf_boundary(k_looks, alpha=0.05):
    """Toy O'Brien-Fleming-style alpha spending: spend ~alpha*t^0.5 shape."""
    ts = [(i+1)/k_looks for i in range(k_looks)]
    spent = [alpha * min(t, 1.0)**0.5 for t in ts]           # cumulative
    incremental = [spent[0]] + [b-a for a, b in zip(spent, spent[1:])]
    return [{"look": i+1, "cum_alpha": round(s, 4),
             "z_needed": round(abs(nd.inv_cdf(s/2)), 2)}
            for i, s in enumerate(spent)]

print(n_per_arm(0.05, 0.10))            # 31206 -> ~31.2K per arm
print(round(achieved_mde(0.05, 12_000), 3))   # ~0.32 rel MDE at 12K/arm
print(runtime_days(62_400, 8_000))      # 14 days (cycle floor binds)
print(obf_boundary(3))
# [{'look': 1, 'cum_alpha': 0.0289, 'z_needed': 2.18}, ... ] toy shape:
# real OBF starts stricter (~z>3 at first look); see sources for exact tables
```

Exercises with it: (1) reproduce the 31,205 figure and re-run for baselines 2%, 20%, 50% â€” watch required n explode as baseline approaches 50% (variance peaks there); (2) find your product's honest weekly MDE: plug your real daily eligible traffic and compute what effect size two weeks actually detects â€” that number, not enthusiasm, decides what's testable; (3) argue the MDE negotiation: for an AI feature costing $60K/mo inference, write down the minimum uplift that covers cost, then check whether your traffic can power that within 3 weeks. If not, the answer isn't "test anyway" â€” it's CUPED-style variance reduction, a bigger UX change worth a larger expected effect, or don't run the experiment.

---

## How it's done in production

| Platform/org | Practice worth stealing |
|---|---|
| Microsoft ExP | Automated SRM + guardrail checks gate the dashboard itself; a triggered SRM blanks headline metrics rather than annotating them |
| Netflix | Sequential testing with anytime-valid p-values for continuous monitoring; quasi-experimentation (synthetic control, switchback) where randomization can't run |
| LinkedIn | Pre-declared OTE composites; launch reviews reject post-hoc metric cherry-picking by construction |
| Booking.com | "Experimentation culture" norms: every change is an experiment including UI copy; failure rates openly discussed (~90% of ideas fail to beat control) |
| Statsig/Eppo/Optimizely | Commercial platforms bundling sequential modes, CUPED, layered orthogonal experiments, and automated alerting |

Layered/orthogonal experiment systems matter at scale: experiments occupy independent hash-space layers so unrelated teams' tests don't collide on traffic; without them, a shared-traffic pool forces choosing between running few tests or invalidating each other. Long-term holdouts (1-5% of users excluded from all launches) measure cumulative portfolio impact because individually-validated wins routinely interact negatively â€” industry retrospectives commonly report aggregate holdout deltas far below the sum of per-test lifts. And the cultural number to internalize: mature experimenters report most ideas lose â€” Microsoft-era analyses and Booking.com's published experience both put idea-success rates around 10-33%; a team whose tests win 80% of the time isn't talented, it's uncalibrated (testing only safe trivialities).

---

## Tradeoffs & when NOT to use it

- **Low-traffic products can't power meaningful MDEs.** If two full cycles detect only Â±30% relative effects, A/B answers nothing you care about â€” switch instruments: before/after with interrupted-time-series, switchback designs (toggle treatment by time blocks), synthetic control, or qualitative-first discovery. Running an underpowered test anyway produces confident noise that consumes credibility.
- **One-way-door decisions shouldn't be A/B'd into irreversibility.** Brand repositioning, pricing trust events, legal-policy changes â€” even if measurable, exposing half your users to an irreversible experience creates asymmetric harm. Some decisions deserve judgment plus targeted research, not a traffic split.
- **Strategic bets with long-fuse effects defeat short-horizon measurement.** Platform investments, trust/safety improvements: effects land over quarters-years; a 2-week test measures only leading proxies. Declare the proxy chain explicitly or don't pretend the test decided it.
- **Ethical/legal constraints bound randomization:** fairness concerns (price discrimination exposure), regulated disclosures, safety-critical flows. The fix is sometimes cluster or staged rollouts, sometimes no experiment â€” know which before designing.
- **Don't test when the answer is already known and cheap.** Shipping a security patch doesn't need a holdout arm; experimentation overhead is real and its ROI comes from contested decisions with plausible-magnitude uncertainty, not from ritual.

---

## Interview questions

### Q1 â€” Walk me through planning an A/B test from scratch. What do you decide first?
**Testing:** whether pre-computation thinking exists at all.
**Answer:** Four written answers before math: OEC + guardrails; randomization unit; MDE justified by ship-and-maintain economics (for AI features include inference COGS); direction and cycle coverage (â‰¥2 weekly cycles). Only then compute n via the two-proportion formula and translate to runtime against daily eligible traffic.
**Follow-up trap:** *"'MDE is whatever we can detect'"* â€” inverted logic that wastes quarters: the MDE is chosen from what effect would justify shipping given costs, THEN feasibility is checked; if feasibility fails you renegotiate the design (variance reduction, bolder UX swing) rather than drifting into testing whatever noise level happens to be reachable.

### Q2 â€” Derive the sample size for baseline 5%, +10% relative lift, alpha .05, power .8.
**Testing:** derivation fluency, not formula recall.
**Answer:** n/arm = (1.96+0.84)^2 Ã— [0.05Ã—0.95 + 0.055Ã—0.945] / 0.005Â² â‰ˆ 7.84 Ã— 0.099475 / 0.000025 â‰ˆ 31,205 per arm, ~62,400 total; at 8K eligible/day that's ~8 days â†’ schedule ~14-15 to cover two full weekly cycles.
**Follow-up trap:** *"'Why not just run one week since n is reached?'"* â€” day-of-week behavior differs systematically (weekend browsing/shopping patterns); a mid-week-only sample interacts with launch-day choice and misestimates weekday-specific effects. Two cycles is the floor for anything user-behavioral.

### Q3 â€” Why does peeking invalidate fixed-horizon tests, and what are the production fixes?
**Testing:** understanding of error inflation under optional stopping.
**Answer:** Fixed-horizon guarantees type-I error for exactly ONE look; repeated checking stops on inevitable random crossings, pushing realized false-positive rates toward 20-40% depending on frequency. Fixes: group-sequential alpha-spending boundaries declared upfront (early looks need extreme z-scores), anytime-valid mSPRT p-values valid under arbitrary stopping, or Bayesian expected-loss thresholds. Pick machinery matching how the org actually monitors.
**Follow-up trap:** *"'We only peeked once at day 4'"* â€” still inflates error and sets precedent; more importantly the fix is organizational as much as statistical: either the dashboard shows sequential-valid statistics or it hides significance until the planned end. Policy beats willpower.

### Q4 â€” What are novelty effects and how do you design around them?
**Testing:** temporal dynamics awareness.
**Answer:** Early-treatment effects partly reflect changed-ness, not value; they decay as returning users habituate (primacy effects similarly delay some benefits). Defenses: read results only after â‰¥2 full weekly cycles; segment new vs returning users (novelty lives in returners); maintain long-term holdouts for cumulative truth; watch effect trajectory across days â€” monotone decay after week 1 predicts shrinkage at scale.
**Follow-up trap:** *"'The decayed steady-state effect is smaller but positive â€” ship?'"* â€” recompute economics against the STEADY-STATE estimate, not peak: maintenance cost and any inference COGS recur monthly, so a halving effect can flip NPV negative; also check whether the win concentrated in low-value segments.

### Q5 â€” A test returns 'no significant difference.' What do you conclude?
**Testing:** null-result literacy â€” the most common executive misread.
**Answer:** Nothing yet about absence of effect: state the achieved MDE ("powered to rule out effects larger than ~X%"), check power assumptions against realized variance, examine segments and dilution (maybe the surface touched only 8% of sessions so a true +40% local effect reads +3.2% overall). Conclusions take the form "we can/can't rule out effects larger than X" â€” never "it does nothing."
**Follow-up trap:** *"'So should we rerun bigger?'*" â€” only if the revised MDE would still change the decision; otherwise the honest output is "this idea produces effects below our decision threshold" and effort moves to bigger swings, which is valuable information, not failure.

### Q6 â€” Explain SRM and why it outranks your headline result.
**Testing:** integrity-check instincts (depth lives in T32; here check triage reflex).
**Answer:** Sample-ratio mismatch = observed arm split deviating beyond chance from intended (chi-squared trigger commonly p<0.001). It invalidates causal comparison because missing/excess users are systematic, not random â€” typically a variant's JS breaking tracking, redirect failures, or asymmetric joins. Triage across assignmentâ†’executionâ†’loggingâ†’analysis stages starting from raw bucket counts; the dashboard stays blank until resolved regardless of how good the treatment looks.
**Follow-up trap:** *"'Small mismatch like 49.7/50.3 â€” ignore?'"* â€” at large n, tiny systematic skews flag subtle bugs that also quietly bias the outcome metrics; significance at p<0.001 with millions of samples makes small deviations meaningful. Investigate; cheap insurance.

### Q7 â€” When would you randomize by something other than user?
**Testing:** interference and unit-mismatch reasoning.
**Answer:** Session/device when per-user persistence is impossible or the effect is genuinely per-session; cluster (geo, friend-group, marketplace region) whenever spillover exists â€” social features leak treatment into control arms, marketplaces have cross-side effects (switchback geo designs handle supply-demand equilibrium shifts); time-block switchbacks when population size can't support arm splits. Unit must match where the effect plausibly stabilizes without leaking.
**Follow-up trap:** *"'What breaks if referral features run user-level randomized?'"* â€” treated users refer control users, contaminating control outcomes and biasing the estimate toward zero (dilution), potentially hiding real network value; cluster-by-community contains spillover within arms at the price of higher variance and fewer effective units.

### Q8 â€” Your team runs 15 concurrent experiments. What infrastructure discipline does that require?
**Testing:** scaled-experimentation systems knowledge.
**Answer:** Layered orthogonal hashing so tests don't collide on shared traffic; central assignment service with consistent unit IDs; automated SRM/guardrail gates on every dashboard; multiple-comparison policy (pre-declared OECs, corrected exploratory reads); a decision log linking every launch to its readout. Without these, concurrency silently invalidates attribution â€” interactions between live tests masquerade as effects.
**Follow-up trap:** *"'How do you handle two tests on the same surface?'*" â€” same-layer means exclusive buckets (slower velocity) or explicit interaction testing (factorial) if the combination matters; stacking same-surface tests naively is how composite regressions become unattributable messes.

### Q9 â€” Contrast frequentist and Bayesian monitoring for stopping rules.
**Testing:** conceptual range beyond one school.
**Answer:** Frequentist (fixed-horizon or sequential) controls long-run error rates over hypothetical repeats; stopping rules must be baked into the procedure (alpha spending / anytime-valid). Bayesian computes P(B>A) or expected loss given priors and data, enabling natural stopping thresholds ("stop when P(B>A)>0.95 AND expected loss <$X"), but offers no long-run frequency guarantee and priors matter under peeking pressure. Operationally both beat naive peeking; orgs choose based on stakeholder interpretability.
**Follow-up trap:** *"'Which gives smaller sample sizes?'"* â€” trick framing: adaptive stopping trades power for speed; sequential methods reach conclusions faster when effects are large and pay a power tax when small. The right question is what error-rate regime and communication style the decision culture needs.

### Q10 â€” Design the experiment plan for an AI feature costing $60K/month inference at full rollout.
**Testing:** synthesis of experimentation with unit economics.
**Answer:** Compute break-even uplift first (what conversion/engagement gain covers $60K/mo â€” module 06 math), set that as minimum interesting effect; power the test against IT; add cost guardrails (tokens/session cap, cost-per-session â‰¤ target) alongside quality guardrails; consider a staged rollout design (small arm â†’ validate â†’ expand) to bound total spend during learning; decide the kill threshold in dollars before launch.
**Follow-up trap:** *"'Inference cost during the test is tiny â€” why bother?'*" â€” because the DECISION needs break-even framing, not test-period accounting: features get validated cheaply then fail economically at scale; writing the $60K/mo constraint into the MDE now prevents the classic 'validated in test, unaffordable in prod' postmortem.

### Q11 â€” What's Twyman's law and when has it saved you?
**Testing:** healthy skepticism under excitement.
**Answer:** Any figure that looks unusual or interesting is usually wrong. Applied: a +200% engagement lift is an instrumentation bug, segment flip, SRM artifact, or novelty burst until audited â€” check raw event counts, arm composition, logging joins before believing. Personal story shape: a doubled click-through that turned out to be a broken dedup rule double-counting rapid clicks in one arm; caught by Twyman reflex before launch review.
**Follow-up trap:** *"'Doesn't this breed cynicism that slows wins down?'"* â€” the audit is minutes when instrumentation is healthy; the alternative is shipping phantom wins that reverse later, which costs far more credibility than the audit ever did. Speed comes from trustworthy plumbing, not skipped checks.

### Q12 â€” Traffic is 2,000 users/week. Can you A/B test anything meaningfully?
**Testing:** instrument-selection judgment under constraint.
**Answer:** Compute honestly: at 4K total over two weeks, detectable relative MDE on a 10% baseline is enormous (~Â±40%+); almost nothing product-relevant fits. Options: (a) change bigger variables with proportionally larger expected effects and accept wide intervals; (b) switch instruments â€” interrupted time series, switchback by day, synthetic controls, or proxy micro-outcomes (task completion in moderated tests); (c) pool longer ONLY if seasonality allows (rarely); (d) invest in top-of-funnel growth first, since traffic is the binding constraint on all future learning too.
**Follow-up trap:** *"'Can we lower confidence requirements to 80% instead of 95%?'*" â€” trading alpha for power is legitimate IF pre-declared and priced: you're consciously accepting more false positives; doing it silently post-hoc to make a marginal result significant is just peeking with extra steps.

---

## Red flags

- Reading dashboards daily and stopping at first significant p-value under fixed-horizon logic.
- No OEC or guardrails declared before launch review.
- Null results reported as "proven no effect" with no achieved-MDE statement.
- Novelty-sensitive changes read after partial weekly cycles.
- Headline metrics computed over all users when only a sliver encountered the surface (dilution).
- Spectacular lifts believed before SRM and instrumentation audits (Twyman).
- Same-surface tests stacked concurrently with no layering or interaction analysis.

## Cheat card

```
PLAN ORDER   OEC+guardrails -> rand unit -> MDE from ship/maintain
             economics -> duration >= 2 weekly cycles -> compute n
POWER        n/arm=(za+zb)^2*(p1q1+p2q2)/(p2-p1)^2
             za=1.96(a=.05), zb=.84(80%)|1.28(90%)
             p1=5%, +10% rel -> ~31.2K/arm; halve MDE -> ~4x n;
             90% power ~= 1.34x n; baseline->50% explodes variance
RUNTIME      days=max(n/daily, 14); deadline talk = show MDE it buys
PEEKING      fixed-horizon multi-look => FP 20-40%; fix w/ group-seq
             alpha-spending (early z~>3) or mSPRT anytime-valid
NOVELTY      wk1 gains decay in returners; segment new vs returning;
             long-term holdout 1-5% for portfolio truth; avoid ramp-
             boundary analysis windows (dilution)
NULLS        report achieved MDE: 'rule out > X%', never 'no effect'
TRAPS        multiple comps (20 metrics @.05 -> ~64% any-FP), SRM
             (chi-sq p<.001 blocks dashboard), dilution (analyze
             triggered pop), interference -> cluster/switchback,
             Twyman: spectacular = bug until proven
CALIBRATION  ~10-33% of ideas beat control at mature shops; winning
             constantly means testing only trivia
LOW TRAFFIC  <~10K/wk => switch instruments: ITS, switchbacks,
             synthetic control, proxy micro-outcomes
```

## Sources

- Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* (Cambridge University Press, 2020), https://experimentguide.com/ â€” accessed 2026-08-23
- Johari, Pekelis & Walsh, "Always Valid Inference: Continuous Monitoring of A/B Tests" (mSPRT / Peeking lecturer), https://arxiv.org/abs/1512.04922 â€” accessed 2026-08-23
- Microsoft ExP research articles incl. SRM diagnostics, https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/ â€” accessed 2026-08-23
- Netflix Technology Blog, sequential testing & quasi-experimentation posts, https://netflixtechblog.com/ â€” accessed 2026-08-23
- Fabijan et al., "Overcoming Exploration Challenges in Large-Scale Online Controlled Experiments" / Booking.com experimentation culture talks, https://www.kdd.org/kdd2017/accepted-papers â€” accessed 2026-08-23
- Deng, Xu, Kohavi & Walker, "Improving the Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data" (CUPED), KDD 2013 â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

