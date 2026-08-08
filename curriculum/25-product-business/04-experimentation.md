# A/B Testing: Power, MDE, Sequential Testing and Peeking, Novelty and Primacy Effects, Sample Ratio Mismatch, Common Traps

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2.5h · **Prereqs:** T25-metrics · **Updated:** 2026-08-08
> **Module id:** `T25-experimentation` · **Tags:** product, critical

## The 30-second version

A/B testing is the one place product thinking meets statistics, and the traps are almost all traps of impatience: checking results before you have enough data (peeking), trusting a variant's early win because it's new rather than because it's better (novelty effect), and shipping a result that was never actually valid because the traffic split itself was broken (sample ratio mismatch). Power and minimum detectable effect (MDE) tell you, before you run anything, how much traffic and time you need to trust a result — halving the effect size you want to detect roughly quadruples the sample size you need, and most underpowered "no significant difference" results are misread as "no effect" when they actually mean "we didn't collect enough data to know." Sequential testing and peeking are the same problem from two angles: looking at a fixed-horizon test's p-value repeatedly before it's done inflates your false-positive rate from 5% toward 25%+, and the fix is either a pre-committed analysis schedule with correction, an always-valid sequential testing method, or discipline about not looking. Novelty and primacy effects mean a variant's day-one lift and its week-four lift are frequently different numbers, and you need to know which one you're actually shipping on. This module deliberately does not re-derive the power formula, factorial/multivariate design, or stratified sampling in depth — see `T32-experiment-design` for that; this module covers what's specific to product experimentation: the traps that kill experiments run by teams without a dedicated experimentation platform.

## Why this gets asked

The interviewer has shipped a "winning" variant that evaporated within a month, and has been the one who had to explain to leadership why a test that showed +8% for two weeks showed +0.3% by week six. They want to know whether you treat a green metric on a dashboard as a decision-ready fact or as a claim that needs to survive a specific checklist — power, peeking discipline, SRM, and enough runtime to separate novelty from durable lift — before you act on it. At senior/staff level, they're also checking whether you can push back on a leadership team that wants to call a winner after three days because the number "looks good."

---

## Lineage: past → present → future

**What came before.** Product teams running early online experiments (2000s-early 2010s) largely borrowed clinical-trial-style fixed-horizon hypothesis testing wholesale: pick a sample size up front via a power calculation, don't look until you hit it, compute one p-value at the end. The practice broke down against real product-team behavior almost immediately — dashboards updated results live, and nobody with access to a live dashboard showing a promising early trend actually waited for the pre-committed sample size before making a call, especially under launch-deadline pressure. This produced a well-documented, quietly epidemic problem: teams calling winners off p-values that were transient noise, because checking a fixed-horizon test's significance repeatedly before its planned end is itself a form of multiple comparisons that the classic framework was never designed to survive.

**Where it stands now.** The mainstream fix, developed and popularized through the 2010s by Optimizely (mSPRT-based "always valid p-values," Johari, Pekelis, Walsh et al.), Microsoft's Experimentation Platform, and others, is sequential testing methodology purpose-built to let teams monitor continuously without inflating false positives — either via alpha-spending functions (pre-declare how much of your Type I error budget you use at each interim look) or always-valid confidence sequences (valid at every sample size simultaneously, so looking any number of times never inflates the error rate). Most mature commercial experimentation platforms (Optimizely, Statsig, Eppo, GrowthBook) now default to some form of sequential/always-valid testing specifically because they know their users will look early and often regardless of what the documentation says. The live disagreement is less about whether sequential methods work — they're well-established statistics — and more about whether teams without a mature platform actually implement them correctly versus nominally claiming to use "sequential testing" while still eyeballing a dashboard without any real correction; the gap between the tooling that exists and the discipline teams actually apply remains wide, echoing the exact tooling-vs-practice gap in `T32-experiment-design`'s discussion of retry budgets.

**Where it's heading.** High confidence: always-valid/sequential monitoring becomes the invisible default inside commercial platforms, removing the choice from individual analysts (you can't easily misuse a dashboard that was built sequential-safe from the start) — already well underway. Moderate confidence: novelty/primacy correction (holdback groups, longer-horizon readouts built into the default reporting rather than requested manually) becomes a standard platform feature rather than a manual analyst step, following the same "make the safe path the default path" trajectory SRM checks already went through. More speculative: AI-assisted experiment design and auto-generated variant proposals are increasing the *volume* of tests a team can propose and run, which increases the multiple-comparisons and false-discovery-rate risk across a whole experimentation program (not just within one test) — an underappreciated, still-emerging concern as of 2026, since most teams' statistical rigor was built for "how many tests are we running," not "how many tests is our AI proposing per week."

---

## Mental model

```
DAY 1        DAY 7         DAY 14        DAY 21        DAY 28
 │             │             │             │             │
 ▼             ▼             ▼             ▼             ▼
+15%*        +9%*          +6%*          +2%           +0.4%
(novelty:    (still novel  (early        (novelty      (true effect,
 first-time  for repeat    adopters      largely worn   if any --
 exposure    users;        driving       off; late      this is what
 inflates    dilution      most of       adopters'      you're
 the number) starting)     the signal)   response       actually
                                          shows)         shipping on)

* every one of these numbers is "significant" if you peek and call it --
  none of them is the number the business will actually experience in month 3
```

The peeking problem and the novelty-effect problem look identical on a live dashboard — an early, real-looking lift — but they are different mechanisms and need different fixes. Peeking is a **statistical** artifact of looking too often at noisy data (fixable with sequential-testing methodology). Novelty is a **behavioral** artifact of users reacting to newness itself (fixable only by running longer and comparing early-cohort to late-cohort behavior, no statistical correction substitutes for calendar time).

---

## How it actually works

### Power and MDE — the operating summary (full derivation: T32-experiment-design)

Power is the probability your test detects a real effect of a given size, given your sample size and variance; MDE (minimum detectable effect) is the smallest true effect your planned sample size is powered to reliably catch. The relationship that matters operationally, independent of the derivation: **required sample size scales roughly with the inverse square of the effect size you want to detect** — ask to detect half the lift, and you need roughly four times the traffic. This is the number to have ready when a stakeholder asks "can we just detect a smaller improvement with the traffic we already have" — no, not without a proportionally much bigger sample, a longer runtime, or a variance-reduction technique (CUPED, covered in T32).

The practical failure this causes: a test runs, shows no significant difference, and gets reported as "the feature had no effect" when the honest claim is "we weren't powered to detect an effect smaller than the MDE we computed going in — smaller-but-real effects are still possible and this test can't rule them out." Always report the achieved MDE next to a null result, not just the p-value.

### Sequential testing and the peeking problem

**The problem, mechanically:** a classical fixed-horizon significance test controls the false-positive rate (typically 5%) *at one specific, pre-planned sample size*. If you instead check the p-value repeatedly as data accumulates and stop the first time it crosses 0.05, you are running many implicit hypothesis tests, and the chance that *at least one* of those looks crosses the threshold purely from noise is much higher than 5% — commonly cited estimates put uncorrected repeated peeking's realized false-positive rate above 25%, meaning roughly one in four "wins" called this way is noise, not signal.

**The fixes, in order of how commonly they're actually implemented:**

1. **Lock the dashboard until the pre-committed sample size is reached.** The simplest fix, purely procedural — nobody can misuse what they can't see. Works, but fights against how teams actually want to operate (leadership wants to know what's happening now, not in three weeks).
2. **Alpha-spending functions.** Pre-declare an interim-analysis schedule (e.g., look at 25%, 50%, 75%, 100% of planned sample) and an alpha-spending function (e.g., O'Brien-Fleming, Pocock) that allocates a shrinking or constant slice of your total Type I error budget to each look, so the cumulative false-positive rate across all looks still equals your target alpha. You only "spend" alpha at looks you actually take; skip a look and that budget carries forward.
3. **Always-valid p-values / confidence sequences (mSPRT-based).** Constructed so the significance test is valid *simultaneously at every sample size* — you can look as often as you want, including continuously, with no correction needed, because the method was built to control the error rate under arbitrary, even adversarial, stopping rules. This is what most modern commercial platforms (Optimizely, and equivalents at Statsig/Eppo/GrowthBook) implement under the hood specifically so that a user staring at a live dashboard can't accidentally produce an inflated false-positive rate.

**The trap that catches people who know the theory:** knowing that sequential methods exist is not the same as having one correctly configured. A team that says "we use sequential testing" but is actually just eyeballing a p-value chart with no alpha-spending schedule and no always-valid correction underneath it has the vocabulary without the protection — this is worth probing for directly in an interview, and worth auditing for directly on your own team.

### Novelty and primacy effects

**Novelty effect:** users respond to a change simply because it's new — attention spikes, curiosity clicks happen, engagement or conversion looks inflated — and the effect **decays as users become accustomed to the change**, typically over days to a few weeks depending on how frequently they encounter the changed surface. A documented real pattern: a landing-page redesign shows a 12% conversion lift in week one; three weeks later, conversion is back to baseline — the entire measured "win" was novelty, not durable improvement.

**Primacy effect (change aversion):** the mirror image — users accustomed to the old way initially resist or perform worse with the new one, even when the new design is genuinely better, and this initial dip also decays as users adjust. A test read too early can therefore show a *false negative* for a genuinely better variant, exactly as easily as novelty can show a false positive for a genuinely worse one.

**Dilution and why traffic composition matters:** the size and duration of a novelty (or primacy) effect depends heavily on what fraction of your traffic is new versus returning. High-new-visitor surfaces (content sites, top-of-funnel landing pages, roughly 80% first-time traffic in common cases) see relatively small novelty effects, because most visitors are experiencing the "new" thing for the first time regardless of variant — there's nothing to be novel *relative to*. High-returning-visitor surfaces (SaaS product UI, marketplace repeat-usage flows, often 80%+ returning traffic) see the opposite: nearly everyone in the treatment arm is experiencing a real change from their established habit, so novelty (or primacy) effects can be large and take weeks to wash out.

**How to actually catch it, not just know it exists:**

- **Segment the analysis by new-vs-returning user, and separately by first-exposure-vs-Nth-exposure within returning users.** A flattening or reversing trend in the Nth-exposure cohort as N grows is the signature of decaying novelty.
- **Run longer than your power calculation's minimum, specifically on any surface with high returning traffic**, and compare early-window lift to late-window lift explicitly rather than reading the topline number once at the end.
- **Use a holdback/haircut approach for high-stakes launches**: keep a small permanent control group running for weeks after the "winning" variant ships broadly, specifically to catch a lift that fades once you've already committed. This is the single most reliable way to catch a novelty-driven false win, because it doesn't rely on catching the decay *during* the test — it catches it after rollout, when the real long-run number becomes visible.

A documented real failure pattern worth having ready: a monetization-model change increased friction, revenue rose ~30% with no visible engagement drop in the test window, the team shipped it — and months later realized the friction had quietly been driving away users who'd only just started to churn by the time the test would have caught it, materially damaging the business well after the "win" was declared.

### Sample ratio mismatch and other common traps (brief — full treatment in T32-experiment-design)

SRM — the observed traffic split deviating from the intended one by more than chance, caught with a chi-squared test — is covered in full mechanical and root-cause detail in `T32-experiment-design`; the operational summary for a product team without a dedicated experimentation platform is: **run the SRM check automatically, before any metric is displayed, on every single test, with no exceptions**, because it's cheap, catches the single most common real-world experiment-invalidating bug, and a team without automated tooling is exactly the team most likely to skip it under deadline pressure.

Other common traps specific to product-team experimentation, beyond SRM and peeking:

- **Multiple-metric fishing.** Running one test but checking twenty metrics and reporting whichever one crossed significance is the AARRR-funnel version of peeking — the same multiple-comparisons inflation, applied across metrics instead of across time. Pre-register a single primary metric; treat everything else as directional/exploratory, not a basis for a launch decision.
- **Interaction with concurrent experiments.** Two unrelated tests running simultaneously on overlapping user populations can interact in ways that bias both — a layered/orthogonal experimentation platform (see T32) is the systemic fix; without one, at minimum track which tests share traffic and sanity-check for overlap before trusting either result.
- **Stopping a test early because it "looks bad,"** the mirror image of peeking for a win — a genuinely good variant showing a false-negative dip from primacy effect, killed before it had time to recover, is a quiet, hard-to-detect way good ideas die in organizations with weak experimentation discipline.
- **Confusing statistical significance with practical significance.** At high traffic volumes, a test can detect a "significant" 0.1% lift that is real but not worth the engineering or maintenance cost of the variant — always evaluate a result against the MDE and against a pre-agreed practical threshold, not against the p-value alone.

---

## Build it from scratch

```python
# untested sketch — sequential monitoring guardrail + novelty-effect segmentation check,
# meant to sit alongside (not replace) the SRM/CUPED/power code already in T32-experiment-design

import numpy as np
from scipy import stats

def obrien_fleming_boundary(info_fraction: float, alpha: float = 0.05) -> float:
    """
    O'Brien-Fleming-style alpha-spending boundary: very conservative early,
    approaches the nominal alpha only near the planned end -- makes early
    peeking nearly impossible to misuse into a false "win."
    info_fraction: fraction of the pre-planned sample size collected so far (0,1].
    Returns the z-critical value to require at this look (higher early, lower late).
    """
    z_alpha_final = stats.norm.ppf(1 - alpha / 2)
    return z_alpha_final / np.sqrt(info_fraction)  # untested sketch: simplified O'Brien-Fleming form

def novelty_decay_check(daily_lift: list[float], window: int = 7) -> dict:
    """
    Compare early-window vs late-window average lift within a single test's
    running data. A large gap flags novelty/primacy decay before you ship on
    a topline number that hasn't stabilized.
    """
    early = np.mean(daily_lift[:window])
    late = np.mean(daily_lift[-window:])
    return {
        "early_window_lift": early,
        "late_window_lift": late,
        "decayed_more_than_half": abs(late) < abs(early) * 0.5,
    }

# usage: at every interim look, require |z| > obrien_fleming_boundary(info_fraction)
# before calling significance -- and independently, once you have >= 3 weeks of
# daily lift data, run novelty_decay_check before trusting the topline number.
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A test showed +8% at day 5, +0.3% at day 30, and leadership already announced the win | Novelty effect on a high-returning-traffic surface, read at day 5 instead of after decay stabilized | Segment by exposure count, extend runtime on high-returning-traffic surfaces, use a post-launch holdback group for high-stakes changes |
| Team reports "no significant difference" and concludes the feature doesn't work | Test was underpowered for the true effect size, or the MDE was never computed and communicated | Always report the achieved MDE next to a null result; distinguish "no effect" from "not powered to see this effect" |
| A dashboard shows a "significant" result on day 3 of a planned 14-day test, team ships immediately | Uncorrected peeking on a fixed-horizon test; realized false-positive rate is inflated well above the nominal 5% | Lock results until planned sample size, or use an always-valid/sequential method that's safe to check continuously |
| Test flagged significant on one of twenty tracked metrics, none pre-registered as primary | Multiple-metric fishing — same inflation mechanism as peeking, applied across metrics instead of time | Pre-register one primary metric per test; treat other movements as directional only |
| A "losing" variant killed on day 2 for looking bad turns out, in a later re-test, to actually be better | Primacy/change-aversion false negative, test stopped before the initial dip recovered | Pre-commit to a minimum runtime regardless of early trend, especially for genuinely different (not just cosmetic) changes |
| Two concurrent experiments show contradictory or inconsistent results on the same users | Overlapping traffic between unrelated tests, no orthogonal/layered experiment isolation | Track which tests share traffic; use a layered experimentation platform where available (see T32) |

---

## Tradeoffs & when NOT to use it

- **Don't run a full sequential-testing setup for a two-day, fully reversible copy tweak.** The overhead of alpha-spending schedules or always-valid tooling is worth it for launch-critical or hard-to-reverse decisions; for cheap, low-risk changes, a simple fixed-horizon test (or even just shipping and watching) is proportionate.
- **Don't extend every test's runtime to chase novelty-effect certainty when the surface has low returning traffic.** If 80%+ of traffic is new visitors, novelty decay is a small, often negligible concern — spending three extra weeks guarding against it on a top-of-funnel landing page is often not worth the delay.
- **A/B testing is the wrong tool for effects that take months to manifest** (retention shifts from a fundamental product change, brand perception shifts) — a two-week test cannot observe a three-month effect regardless of how well-powered or peeking-safe it is; use longitudinal cohort analysis or holdback groups measured over a much longer horizon instead.
- **Don't treat statistical significance as the finish line.** A statistically significant but practically trivial lift, especially at high traffic volumes, may not justify the engineering and long-term maintenance cost of shipping and supporting a new variant permanently.
- **When the population is too small to power a real test** (a B2B product with a few hundred customers, an enterprise feature used by a handful of accounts), classical A/B testing is often the wrong tool entirely — qualitative discovery (see the discovery module) and case-study-style rollouts with close monitoring are more honest than running an underpowered test and pretending its result is statistically meaningful.

---

## Interview questions

### Q1 — Your test shows +8% lift on day 3 of a planned 14-day run. Leadership wants to ship now. What do you say?
**Testing:** whether you'll push back on a stakeholder who wants to call an early win.
**Answer:** An early significant-looking result on a fixed-horizon test is exactly the peeking pattern that inflates false positives well past the nominal 5% — you'd need either a pre-registered interim-analysis schedule with alpha-spending, or an always-valid sequential method, to trust a look this early; absent that, the honest answer is you don't yet know if this is signal or noise, and shipping now risks committing to a result that regresses toward a much smaller (or null) effect by day 14.
**Follow-up trap:** *"What if the business genuinely can't wait 14 days?"* — offer a faster, statistically valid alternative (an always-valid/sequential method configured before the test started, or a smaller MDE target that needs less runtime) rather than either blocking the business entirely or quietly caving to the deadline — the senior move is presenting the real tradeoff, not picking a side unilaterally.

### Q2 — Explain the difference between the peeking problem and the novelty effect. Why do teams confuse them?
**Answer:** Peeking is a statistical artifact — checking a fixed-horizon test's p-value repeatedly inflates the realized false-positive rate, purely from noise, regardless of whether any real effect exists. The novelty effect is a behavioral artifact — users genuinely respond differently to something because it's new, a real (if temporary) effect, not noise. They're confused because both produce the same visible symptom on a dashboard: an encouraging early number that fades. The fix for peeking is statistical (sequential methods); the fix for novelty is calendar time (running longer, segmenting by exposure count) — no statistical correction substitutes for actually observing what happens after the novelty wears off.
**Follow-up trap:** *"Could both be happening in the same test simultaneously?"* — yes, and that's the harder real-world case — a sequential-testing correction can validly confirm significance early while the underlying effect is still partly novelty-driven and will still decay; passing the statistical check doesn't mean the behavioral effect has stabilized, they're independent checks and you need both.

### Q3 — What's an always-valid p-value and why do modern experimentation platforms default to it?
**Answer:** A significance test constructed (typically via a mixture sequential probability ratio test, mSPRT) so the Type I error rate is controlled *simultaneously at every sample size*, meaning you can look as often as you want — including continuously — without inflating the false-positive rate, because the method accounts for arbitrary stopping rules by design rather than assuming one fixed look. Platforms default to it because they know users will look at a live dashboard early and often regardless of documentation, so building the correction into the statistic itself removes the failure mode instead of relying on user discipline.
**Follow-up trap:** *"If a platform gives you always-valid p-values, do you still need a pre-registered sample size?"* — you still want a target sample size for power/MDE planning purposes (to know roughly how long the test needs to run to detect the effect size you care about), but you no longer need to enforce it as a hard "don't look before this" rule — the two serve different purposes and always-valid testing doesn't eliminate the need for an upfront power calculation.

### Q4 — Why does a high-returning-traffic surface need a longer test runtime than a high-new-visitor surface, holding sample size constant?
**Answer:** Novelty and primacy effects require repeat exposure to manifest and decay — on a high-new-visitor surface, most users experience the "new" thing for the first time regardless of variant, so there's little novelty differential to decay. On a high-returning-visitor surface, most of the treatment arm is experiencing a genuine change from an established habit, so the novelty (or primacy/change-aversion) effect can be large and can take weeks to wash out — reading the result before it washes out risks shipping on a transient number.
**Follow-up trap:** *"How do you know how long is long enough, rather than picking an arbitrary extra week?"* — segment by exposure count (1st visit vs. 5th visit post-launch) within the returning-user cohort and watch for the lift to flatten across exposure count, rather than picking a fixed calendar duration blindly — the decay curve itself tells you when it's stabilized, a fixed extra week is a heuristic, not a measurement.

### Q5 — A test shows no statistically significant difference. A stakeholder concludes "the feature doesn't work." What's wrong with that conclusion and how do you correct it?
**Answer:** A null result only rules out effects larger than the test's achieved MDE at the collected sample size — it says nothing about smaller, still-meaningful effects that the test wasn't powered to detect. The corrected framing: "we can rule out an effect larger than X%, but we can't distinguish a smaller real effect from no effect at this sample size" — and if a smaller effect would still matter to the business, propose either a longer run or a variance-reduction technique (CUPED, see T32) rather than accepting a false "no effect" conclusion.
**Follow-up trap:** *"What if getting the sample size for a smaller MDE just isn't feasible given current traffic?"* — say that plainly rather than pretending the null result answers the question — "we cannot economically detect an effect this small on our current traffic" is a legitimate, honest business conclusion, distinct from "there is no effect."

### Q6 — Describe a holdback/haircut group and why you'd use one even after a test has already "won."
**Answer:** A small permanent control group kept running after a winning variant ships to 100% of the remaining traffic — its purpose is to catch a lift that was partly or wholly novelty-driven and fades over the following weeks, which a test window alone, even a well-powered one, may not have run long enough to observe. Comparing the holdback's stable long-run behavior to the shipped variant's is the most reliable way to confirm a launch decision was actually correct, after the fact.
**Follow-up trap:** *"Isn't keeping users in a permanently worse experience (if the new variant really is better) a real cost?"* — yes, and that's exactly why holdbacks are reserved for high-stakes, hard-to-reverse launches, not used on every test — the cost of a small permanent holdback is worth it specifically when the downside of having shipped on a novelty-driven false win is large (a major UX or pricing change, not a button-color test).

### Q7 — What's sample ratio mismatch, at a level of detail appropriate for a product engineer who doesn't own the experimentation platform?
**Answer:** The observed traffic split between arms deviates from the intended split by more than chance, detected with a chi-squared test (commonly at p<0.001), and it invalidates the test's causal comparison until root-caused, because the missing or excess users are systematically, not randomly, different. Full pipeline root-causing (assignment/execution/logging/analysis stages) is in T32-experiment-design; the operational takeaway for a product team is: this check should run automatically, before any metric is shown, on every test, with zero exceptions — it's the cheapest, highest-value check in the entire experimentation stack.
**Follow-up trap:** *"Your team has no dedicated experimentation platform and no automated SRM check. What's the minimum you'd add?"* — a one-line chi-squared test on arm counts, run in whatever job computes the topline metrics, that hard-fails (not just warns) the report if triggered — this is a few lines of code and should be non-negotiable before any experimentation program is trusted with real launch decisions.

### Q8 — You're told a variant is "significant" because it beat one of the fifteen metrics your dashboard tracks. How do you evaluate this?
**Answer:** This is multiple-metric fishing — the same multiple-comparisons inflation as peeking, applied across metrics instead of time — checking fifteen metrics for significance at alpha=0.05 gives a much-higher-than-5% chance that at least one crosses the threshold from noise alone. Ask what the pre-registered primary metric was before the test started; if this metric wasn't it, treat the result as directional/exploratory at best, worth generating a new, separately-tested hypothesis from, not a basis for a launch decision on its own.
**Follow-up trap:** *"What if the metric that lit up is genuinely important, just not the one we pre-registered?"* — that's a legitimate reason to run a *new*, focused test with that metric pre-registered as primary, not to retroactively promote an exploratory finding to a launch decision — the fix for a good idea discovered by fishing is to validate it properly, not to grandfather it in.

### Q9 — Explain the relationship between MDE and sample size, and why "just detect a smaller lift with the same traffic" isn't free.
**Answer:** Required sample size scales roughly with the inverse square of the target effect size (the effect appears squared in the denominator of the standard two-proportion power formula, derived in full in T32-experiment-design) — halving the MDE you want to detect roughly quadruples the sample size needed at fixed power and significance. So "detect a smaller lift with the same traffic" is mathematically close to "detect a 4x smaller lift for free," which the statistics don't support.
**Follow-up trap:** *"Is there any way to detect a smaller effect without more traffic?"* — variance-reduction techniques like CUPED (covered in T32) can meaningfully narrow the gap by regressing out predictable pre-experiment variance, but the improvement is bounded by how correlated the covariate is with the outcome — it reduces the multiplier, it doesn't eliminate the underlying tradeoff.

### Q10 — Design the experimentation guardrails you'd insist on before your team is allowed to make a launch decision off a test result, given you don't have a dedicated experimentation platform.
**Testing:** synthesis — can you assemble the module into a real minimum bar.
**Answer:** At minimum: (1) a pre-registered primary metric and target MDE/sample size before the test starts; (2) an automated SRM check that hard-blocks the report if triggered; (3) either a locked dashboard until planned sample size, or a real alpha-spending/always-valid method if continuous monitoring is required by the business; (4) a minimum runtime tied to traffic composition (longer for high-returning-traffic surfaces) with early-vs-late window comparison before trusting the topline number; (5) explicit reporting of achieved MDE alongside any null result.
**Follow-up trap:** *"Which one of these would you cut first if you had to ship something in a week with no platform investment?"* — never the SRM check (a few lines of code, catches the single most common invalidating bug) — the sequential-testing tooling is the one to defer, replaced temporarily with the blunter "lock the dashboard until planned sample size" rule, which costs nothing to implement and, while less flexible, is still statistically safe.

---

## Red flags that fail you

- Calling a test's early significant result a "win" without checking whether peeking correction was in place.
- Reporting a null result as "the feature has no effect" without stating the achieved MDE.
- Not knowing the difference between the peeking problem (statistical) and the novelty effect (behavioral).
- No mention of segmenting by new-vs-returning traffic or exposure count when asked how to catch novelty decay.
- Treating "we use sequential testing" as sufficient without being able to describe what method (alpha-spending vs. always-valid) or configuration is actually in place.
- Reporting a result significant on a non-pre-registered metric as a basis for a launch decision.

---

## Cheat card

```
POWER/MDE       full derivation: T32-experiment-design. Operating rule: halve
                the MDE you want -> ~4x the sample size needed (squared denom)
                null result != "no effect" -- report achieved MDE alongside it

PEEKING         checking a fixed-horizon test's p-value repeatedly before its
                planned end inflates false-positive rate from ~5% toward 25%+
FIXES           1) lock dashboard until planned n   2) alpha-spending (O'Brien-
                Fleming/Pocock, pre-declared interim schedule)   3) always-valid
                p-values / confidence sequences (mSPRT) -- safe to look anytime
                "we do sequential testing" != having a real method configured

NOVELTY EFFECT  users react to NEWNESS itself -> early lift inflated, decays over
                days-weeks as users habituate. Statistical fix does NOT apply --
                only calendar time + segmentation fixes this
PRIMACY EFFECT  change aversion -- mirror image, early FALSE NEGATIVE dip that
                recovers as users adjust; can kill a genuinely better variant
                if the test is stopped too early
DILUTION        high-new-traffic surfaces: small novelty effect (nothing to be
                novel relative to). high-returning-traffic surfaces (SaaS,
                marketplaces): large effect, can take weeks to wash out
CATCH IT        segment by new-vs-returning + exposure count (1st vs Nth visit);
                use a post-launch HOLDBACK group for high-stakes launches

SRM             full treatment: T32-experiment-design. Operating rule: automated
                chi-squared check on EVERY test, hard-blocks the report if
                triggered, no exceptions -- cheapest highest-value check that exists

OTHER TRAPS     multiple-metric fishing (checking 15 metrics = peeking across
                metrics instead of time) -- pre-register ONE primary metric
                stopping a "losing" test early = primacy false-negative risk
                statistical significance != practical significance at high traffic
```

## Sources

- [The Peeking Problem in A/B Testing — DRIP](https://dripagency.de/blog/peeking-problem-ab-testing) — accessed 2026-08-08
- [Choosing a Sequential Testing Framework — Spotify Engineering](https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions) — accessed 2026-08-08
- [Alpha Spending — VWO Glossary](https://vwo.com/glossary/alpha-spending/) — accessed 2026-08-08
- [The Novelty Effect: Why Your A/B Test Winner Might Be Temporary — Atticus Li](https://atticusli.com/blog/posts/novelty-effect-ab-test-winner-temporary/) — accessed 2026-08-08
- [How to catch the novelty effect in A/B testing — LogRocket](https://blog.logrocket.com/product-management/novelty-effect-ab-testing/) — accessed 2026-08-08
- Johari, Pekelis, Walsh et al., "Peeking at A/B Tests" (Optimizely, mSPRT / always-valid p-values), KDD 2017
- `curriculum/32-applied-nlp-marketing-ml/07-experiment-design.md` — factorial/multivariate design, stratified sampling, SRM root-cause pipeline, CUPED derivation

## Changelog
- 2026-08-08 — created
