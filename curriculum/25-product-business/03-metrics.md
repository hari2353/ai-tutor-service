# Metrics: North Star, AARRR, Leading vs Lagging, Guardrail Metrics, Goodhart's Law

> **Track:** T25 Product Thinking & Business Â· **Time:** 2h Â· **Prereqs:** T25-product-thinking Â· **Updated:** 2026-08-23
> **Module id:** `T25-metrics` Â· **Tags:** product, critical

## The 30-second version

A metric system is a causal tree, not a dashboard: one **North Star metric** â€” the single measure of the value customers get that, when it grows, the business grows (Airbnb's nights booked, Spotify's total listening time, Amplitude's guidance is "output, not input") â€” decomposed via an **input/input/input** structure into metrics teams can actually move this sprint. **AARRR** (McClure's pirate metrics: Acquisition, Activation, Retention, Referral, Revenue) orders the funnel so you diagnose *where* users leak instead of staring at totals; typical consumer funnels lose 60-80% at activation alone, which is why retention curves that flatten into a smile are the difference between a business and a bucket. **Leading indicators** (this week's activation rate) predict **lagging outcomes** (next quarter's revenue) but only if you've validated the correlation with cohort data â€” most "leading indicators" are wishful correlation. **Guardrail metrics** are the things you must not break while moving the headline (latency p95, complaint rate, relevance): they're written down with thresholds BEFORE experiments launch, which is what makes later vetoes non-political. And **Goodhart's Law** â€” "when a measure becomes a target, it ceases to be a good measure" â€” is not folklore but a mechanism: any single metric optimized hard enough gets gamed (support closing tickets unread to hit resolution-time targets), so mature systems fight back with paired counter-metrics, quality sampling, and deliberately imperfect composite measures.

## Why this gets asked

"Which metric would you use for X and why?" is a principal-loop standard because it compresses three checks into one question: can you reason causally about products, can you resist vanity numbers, and do you know what happens when measurement meets human incentives. The engineer-flavored version is sharper: your recsys drove ~25% engagement uplift â€” engagement of *what*, measured how, and what if it went up because recommendations got clickbaity? That question is Goodhart in miniature: the same ranker change that lifts clicks can degrade long-run trust, and the interviewer wants to hear you reach for guardrails unprompted. There's also a resource-debate angle: teams that can't state their North Star decomposition end up arguing priorities by seniority; teams that can, argue by "which input metric does each project move, with what expected magnitude." Owning that argument is exactly where a principal engineer earns scope.

---

## Lineage: past â†’ present â†’ future

**What came before.** Pre-internet business measurement was quarterly and financial: revenue, profit, market share â€” all lagging, none actionable at product-team altitude. Dave McClure's AARRR framework (circa 2007, from the startup-marketing talks that became 500 Startups canon) was the first widely adopted *product* funnel vocabulary, born from web-analytics data finally being cheap enough to instrument per-step. Sean Ellis coined "growth hacking" around 2010 out of his Dropbox-era work (his famous survey question â€” "how would you feel if you could no longer use this product?" with ~40% "very disappointed" predicting growth â€” became the Sean Ellis test). North Star thinking crystallized in the mid-2010s: GrowthHackers' own 2016-2017 writings popularized the term, and Amplitude's "North Star playbook" (2018) gave it a mechanical definition. Goodhart's Law predates all of it â€” Charles Goodhart formulated the monetary-policy version in 1975, Marilyn Strathern generalized it to its popular form in 1997 â€” and Campbell's Law (1976, education testing) says nearly the same thing independently.

**Where it stands now.** Current practice: every serious org has a metric tree (North Star â†’ inputs), experiment platforms enforce guardrails automatically (module 04), and the craft debates have moved to second-order questions â€” how many input metrics is too many (practical answer: 3-5 per team), whether North Stars should be composites (Airbnb-style "nights booked" vs ratio metrics like DAU/MAU, which hide absolute decline), and how AI features complicate everything: engagement is no longer obviously good (a chatbot can engage users while being wrong), so cost-per-resolution and correction-rate enter trees as first-class citizens rather than footnotes. The chronic failure remains unchanged: metric theater â€” trees drawn once in an offsite, screenshotted, never used in weekly decisions.

**Where it's heading.** Three trajectories, confidence-ordered. First: automated anomaly detection and metric-lineage tooling (dbt-style lineage applied to KPIs) make trees living documents that update with the warehouse â€” high confidence, already shipping commercially. Second: AI-mediated measurement â€” LLMs summarizing "why did activation dip?" across dashboards and sessions â€” moves analysts from query-writing to hypothesis-checking; moderate-high confidence within 2-3 years. Third, genuinely contested: privacy regulation (ATT-era signal loss since iOS 14.5, cookie deprecation churn) keeps degrading third-party attribution, pushing measurement toward first-party behavioral proxies and incrementality testing (geo holdouts); expect interview questions to probe whether you understand that some classic metrics (last-click attribution) are now structurally unreliable rather than merely noisy.

---

## Mental model

```
                    NORTH STAR
              "weekly learning minutes
               with demonstrated progress"
                        |
     +------------------+------------------+
     |                  |                  |
 INPUT: ACTIVATE    INPUT: HABIT       INPUT: DEPTH
 % new users        % W4 returners     median exercises
 finishing first    (retention curve   per active week
 session w/ a win   flattens?)         (quality proxy)
     |                  |                  |
 leading -----> predicts -----> lagging outcome:
 (days-weeks)                renewals / revenue (months-quarters)

 GUARDRAILS ring the whole tree:
 latency p95 < 300ms | complaint rate < 0.5% | content-mix diversity >= floor
```

Three properties of a usable North Star: it measures **customer value received**, not activity performed ("minutes of productive practice," not "logins"); it's a **sum, not a ratio** (ratios mask absolute decline â€” 40% of nothing is nothing); and it **predicts revenue with a lag you can name** (validated on historical cohorts, not asserted). Input metrics inherit SMART-style constraints: movable by one team within one quarter, instrumented today, and causally linked upward â€” if you can't say how moving the input moves the star, it isn't an input, it's a hobby.

---

## How it actually works

### AARRR as a diagnostic order, not a checklist

Run the funnel in reverse-priority: retention first (a leaking bucket makes everything upstream pointless â€” if W4 retention is under ~5-10% for a consumer app, fix the product before buying traffic), then activation (the largest single-step loss in most funnels; consumer products commonly lose 60-80% of signups before a first meaningful action), then acquisition efficiency (CAC by channel, module 06), then referral and monetization. The practical artifact is a **funnel table with per-stage conversion and volume**, refreshed weekly:

```
STAGE          RATE      VOLUME/wk    NOTE
visitâ†’signup   3.2%      41,000       industry median landing ~2-5%
signupâ†’active  28%       1,300        "active" = completed first exercise
activeâ†’W4      19%       250          retention smile check here
W4â†’paid        4.1%      10           monetization gate
```

Each row's rate is a candidate input metric; the biggest rate Ã— volume product points to where engineering effort buys the most North Star movement. This arithmetic â€” not intuition â€” is how you win "what should we work on next" debates.

### Leading vs lagging: validation or it isn't one

A leading indicator earns its title only after cohort validation: take historical data, confirm that weeks where the candidate moved up were followed by quarters where the outcome moved up, across enough independent periods to matter. The Sean Ellis test (â‰¥40% of surveyed users answering "very disappointed" if the product vanished) is a leading indicator of growth *because* Ellis reported that threshold separated scaling from struggling companies across his dataset of hundreds of startups â€” whether your product's true threshold is 35% or 50% requires your own calibration against your own history. Engineering-flavored leading indicators are often better: time-to-first-successful-action, error-rate on critical path, week-1 depth of usage. Lagging outcomes (revenue, churn, NPS-driven referral) arrive too late to steer sprints but anchor the tree's validity.

### Guardrails: written thresholds make vetoes non-political

Every experiment and every launch carries 2-4 guardrails with numeric thresholds agreed pre-launch: latency p95 must stay within +10% of baseline; complaint/flag rate below 0.5% of sessions; relevance or quality score no worse than âˆ’1%; cost per session within budget. When a change breaches a guardrail, the decision was made weeks earlier â€” you're enforcing, not arguing. The subtle craft is choosing guardrails that catch Goodhart gaming: if the headline is engagement minutes, pair it with a quality counter-metric (completion rates, next-day return) so grinding fake minutes shows up somewhere visible.

### Goodhart's Law: mechanism and defenses

The mechanism is selection pressure on the measured proxy: humans (and ML rankers) optimize what's counted, and the residual gap between proxy and true goal becomes waste or harm. Canonical failures: support teams closing tickets unread to hit resolution-time SLAs; Uber-early-era drivers gaming destination filters; YouTube watch-time optimization historically rewarding clickbait until paired metrics corrected it; education teaching-to-the-test (Campbell's Law). Defenses, in increasing sophistication: (1) **paired counter-metrics** â€” every target gets an opposite number that gaming degrades; (2) **quality sampling** â€” human review of random slices (5% audit catches ticket-closing scams cheaply); (3) **composite indices** â€” combine speed+quality so gaming one hurts the other (with the known drawback that weights become political); (4) **rotating/randomized targets** and holdout groups so optimization can't fully lock on; (5) **deliberately keeping some things unmeasured** â€” trust, team health â€” and defending them qualitatively rather than letting a bad proxy colonize them.

### Building the tree: a worked pass

For the tutoring platform, suppose the business outcome is annual renewal revenue. Working backward: renewal correlates with demonstrated progress; demonstrated progress happens inside productive sessions; sessions require activation and habit. Tree: NS = weekly productive-practice minutes per active learner (productive = session ending in a passed checkpoint). Inputs: activation rate (% new users passing a checkpoint in session 1), W4 return rate, median session depth. Guardrails: p95 latency, hint-abuse flag rate, parent-complaint rate. Each input gets an owner, a current value, a quarterly target, and projects listed beneath it â€” this exact structure is what turns "we should invest in personalization" into "personalization targets activation, currently 28%, target 34%, expected +0.6pts W4 which history says â‰ˆ +$380K/yr renewals."

---

## Build it from scratch

**Exercise 1: metric-tree workshop on a Cornerstone-style enterprise LMS (90 min, pen and warehouse queries).**

Pick the outcome: seat-renewal revenue for the LMS product line (B2B: seats renewed annually). Build downward:

1. NS candidates â€” argue each: "logins/month" (activity, gameable, reject); "courses completed" (quantity over quality, completion-gaming risk, weak); "weekly active learners completing at least one assessed activity" (value received, sum not ratio, plausible renewal link â€” accept).
2. Decompose into inputs: new-seat activation (% provisioned seats with a first assessed activity â‰¤7 days), manager-assigned-content coverage, median weekly learning minutes per active learner, W8 return rate.
3. Attach guardrails: course-quality rating floor (â‰¥4.0/5), compliance-deadline miss rate (must fall), support tickets per 1K learners.
4. For each input, write one SQL-shaped definition (exact event names, dedup rules, time zone) â€” most "metric disagreements" are secretly definition disagreements, and writing the query settles them.
5. Validate one leading link: pull 8 quarters of history, check whether quarters with high early-quarter activation were followed by higher renewal â€” record the correlation and its n honestly.

**Exercise 2: code the tree's arithmetic and a Goodhart stress test.**

```python
# metric_tree.py -- North Star decomposition with revenue translation + gaming check

def renewal_projection(seats, activation_now, activation_target,
                       w4_per_activation_pt, rev_per_w4_pt):
    """Chain: activation pts -> W4 pts -> $ ; each coefficient labeled."""
    d_w4 = (activation_target - activation_now) * w4_per_activation_pt
    return {"d_w4_pts": round(d_w4, 2),
            "annual_$": round(d_w4 * rev_per_w4_pt * seats, -3)}

# 120K seats; +1pt activation -> +0.22pt W4 (cohort-fit); +1pt W4 -> $18/seat/yr
print(renewal_projection(120_000, 28, 34, 0.22, 18))
# {'d_w4_pts': 1.32, 'annual_$': 2851000} -> present as band +/-40%

def goodhart_check(headline_gain, guardrail_losses):
    """Guardrail losses are NEGATIVE numbers (degradations)."""
    net = headline_gain + sum(guardrail_losses.values())
    verdict = ("SHIP" if net > 0 else
               "BLOCK - headline gain consumed by guardrail damage")
    return {"net": round(net, 3), **{k: round(v, 3) for k, v in guardrail_losses.items()},
            "verdict": verdict}

# +25% engagement but clickbait drift hurt relevance (-12%) and next-day return (-9%)
print(goodhart_check(0.25, {"relevance": -0.12, "next_day_return": -0.09}))
# -> BLOCK: net +0.04 is noise-level; grind detected, iterate the ranker instead
```

The second function institutionalizes the reflex: any headline claim arrives pre-netted against its guardrails, so Goodhart gaming becomes visible arithmetic instead of an argument.

---

## How it's done in production

| Org | Metric practice | The engineer-visible part |
|---|---|---|
| Airbnb | NS = nights booked; every project states its NS-input linkage; "system health" metrics tracked beside growth ones | Experiment dashboards render guardrails with automatic red-lines |
| Spotify | Squads own input metrics under a chapter-level NS; quarterly "metric reviews" prune dead metrics | Squad dashboards show the tree path from their metric to the star |
| Netflix | Consumer-science discipline: A/B decision reports include secondary metrics explicitly labeled exploratory vs confirmatory | Launch review requires pre-registered primary + guardrails, or no launch |
| LinkedIn | OTE (overall evaluation criteria) â€” a single pre-declared composite deciding launches | Engineers see OTE math in every experiment readout, including weights |
| Amplitude/Analytics vendors | North Star playbooks: NS must be an output (value delivered), inputs are the levers | Templates force the "input â†’ star" causal claim into writing |

Production realities worth knowing before you walk into one of these cultures: metric definitions live in version-controlled semantic layers (dbt models / metric stores) because dashboard drift across teams is endemic â€” two teams reporting "activation" differently is the default state of nature, and the fix is a single query everyone imports. Weekly business reviews walk the tree top-down; any input that hasn't moved for 2+ quarters gets pruned or re-owned. And AI features are pushing a new pattern: cost-per-outcome entering the tree as a first-class input (e.g., cost per successfully-resolved support ticket), because token COGS makes engagement-without-economics fatal at scale.

---

## Tradeoffs & when NOT to use it

- **Don't impose a full tree on pre-product/market-fit work.** When even the audience is unknown, the tree's inputs churn weekly and become ceremony. Early stage needs one retention curve and honest cohort analysis, not a five-level OKR cascade.
- **North Stars fail when the business has genuinely multiple value streams.** A marketplace with supply-side and demand-side health may need TWO stars explicitly balanced (e.g., bookings AND host earnings) rather than one star pretending the tension away â€” forcing one number invites optimizing the easier side into imbalance.
- **Ratios as North Stars hide absolute decline** (DAU/MAU can rise while both fall); sums can hide efficiency collapse (revenue up because sales doubled headcount). Pick the form whose failure mode you can detect, and pair it with the other.
- **Over-guardrailing freezes product motion:** ten hard thresholds mean most experiments ship nothing and teams stop trying. Keep 2-4 per experiment; park nice-to-know secondaries in monitoring, not gates.
- **Goodhart defenses have their own failure modes:** composite indices make weights political; quality sampling adds reviewer bias; unmeasured values invite "trust me" abuse. Revisit defenses annually â€” gaming strategies evolve like pathogens.

---

## Interview questions

### Q1 â€” Pick a North Star metric for our product and defend it against alternatives.
**Testing:** whether they reach for customer-value-output metrics or grab activity counts.
**Answer:** State the business outcome first (renewal revenue), then the user value that causes it (demonstrated learning progress), then propose a sum-form NS â€” weekly active learners completing an assessed activity â€” and argue alternatives down: logins (activity not value, gameable), courses completed (quantity over quality), DAU/MAU (ratio hides absolute decline). Close with the validation step: confirm on historical cohorts that quarters with higher NS preceded higher renewal.
**Follow-up trap:** *"What if leadership already reports DAU everywhere?"* â€” don't relitigate vocabulary; define the NS as DAU-with-quality-condition ("DAU completing a meaningful action") so it composes with existing dashboards while fixing the gaming hole.

### Q2 â€” Your recsys shows +25% engagement. What could be wrong, and what do you check before celebrating?
**Testing:** Goodhart reflex under a realistic scenario.
**Answer:** Engagement is a proxy; ask what changed compositionally: clickbait drift (recommendations rewarding curiosity gaps over usefulness), session-stuffing (longer sessions â‰  better outcomes), segment mix (did heavy users just get heavier?). Check paired counter-metrics â€” relevance scores, next-day return rate, complaint flags â€” and run the net arithmetic: +25% headline against âˆ’12% relevance and âˆ’9% next-day return nets to noise; iterate rather than ship.
**Follow-up trap:** *"'Engagement went up, users chose to engage' â€” isn't revealed preference enough?"* â€” revealed preference reveals preference under the choice set you engineered; if the ranker learned to exploit impulse, users reveal exploitation vulnerability, not long-run value. That's why platforms measure delayed outcomes (next-day, next-week return) instead of trusting same-session clicks.

### Q3 â€” Leading vs lagging: give an example where a plausible leading indicator failed validation.
**Testing:** whether "leading indicator" means validated correlation or vibes.
**Answer:** Classic: NPS as a leading indicator of revenue â€” multiple published analyses find weak-to-inconsistent predictive power at segment level despite its popularity; feature-adoption counts similarly fail (adopting a feature correlates with being a power user, which was already true). Validation method: take 8+ historical periods, regress lagged outcome on candidate leading series, require stability across segments; report honestly when the coefficient collapses.
**Follow-up trap:** *"So is NPS useless?"* â€” no, it's a useful relationship-maintenance signal and a conversation generator; it fails as a *forecasting* metric. Mislabeling it leading-vs-lagging is the error, not the metric itself.

### Q4 â€” Design the guardrail set for a change to your recommendation ranking. Be specific.
**Testing:** operational fluency with thresholds and tradeoff surfaces.
**Answer:** Pre-launch thresholds in writing: p95 latency â‰¤ baseline+10%; relevance/quality score â‰¥ âˆ’1% vs control; content diversity above floor (no single category exceeding e.g. 40% of impressions); complaint/flag rate < 0.5% of sessions; next-7-day return rate non-negative within measurement noise. Each has an owner and an automated check in the experiment platform; breach blocks launch review.
**Follow-up trap:** *"Who decides thresholds?"* â€” the owning team proposes from historical variance (thresholds tighter than natural noise cause constant false alarms; looser than materiality are decorative), then product/data/engineering sign off BEFORE results exist â€” after-the-fact threshold-setting is exactly the politics guardrails exist to prevent.

### Q5 â€” Explain Goodhart's Law with a mechanism, then name two defenses and their costs.
**Testing:** depth beyond quoting the aphorism.
**Answer:** Mechanism: optimization pressure concentrates on the measured proxy; the proxy-goal gap becomes waste â€” support closes tickets unread to hit resolution SLAs because closure time is measured and comprehension isn't. Defenses: paired counter-metrics (reopen-rate, satisfaction sampling) whose cost is added complexity and occasional contradictory signals; quality sampling (human audit of ~5% random slices) whose cost is reviewer time and reviewer bias; composite indices whose cost is politically contested weights.
**Follow-up trap:** *"Can't you just measure more things?"* â€” measurement isn't free and every added metric dilutes attention; also each new metric becomes its own gaming target. Mature systems keep few targets, many monitors, and rotate audits.

### Q6 â€” Activation is 28% and W4 retention 19%. Where does engineering effort go?
**Testing:** funnel arithmetic over instinct.
**Answer:** Compute leverage: activation improvements multiply everything downstream â€” moving 28%â†’34% (+6pts) lifts every later stage by ~21% relative; W4 moves affect only retained cohorts. But check ceiling first: if the retention curve never flattens (no smile), acquisition multiplies leak â€” fix product-market fit signals before activation polish. With a healthy flattening curve, attack activation: biggest rate Ã— volume Ã— tractability wins, typically first-session time-to-value.
**Follow-up trap:** *"How do you know activation is tractable rather than structural?"* â€” segment it: if some channels/cohorts activate at 50%+, the gap is learnable experience design, not product-category gravity; uniformly low across segments suggests a positioning problem, not an onboarding bug.

### Q7 â€” What's wrong with using DAU/MAU as your North Star?
**Testing:** ratio-metric literacy.
**Answer:** Ratios mask absolute decline (both terms can shrink while the ratio rises), it conflates frequency with value (a daily-habit app and a tax tool shouldn't share targets), and it's gameable via notifications that generate hollow opens. If stickiness matters, report it as a diagnostic alongside a sum-form NS measuring value delivered â€” never alone.
**Follow-up trap:** *"When IS a ratio acceptable?"* â€” as a guardrail or efficiency metric (cost per successful outcome, success per session) where normalization is the point and absolute volume is tracked separately by its components.

### Q8 â€” Leadership wants a single number on the exec dashboard. What goes up there?
**Testing:** executive translation without losing rigor.
**Answer:** One output-form NS plus 2-3 inputs and 1-2 guardrails, rendered as sparklines against targets â€” the tree compressed, not abandoned. The discipline is annotation: any anomaly carries a linked explanation (launch, outage, seasonality) within a day, because unexplained exec metrics breed folklore that outlives the data.
**Follow-up trap:** *"They'll still ask 'why did it move?'"* â€” build the drill-down path before asking for the slot: NS â†’ inputs â†’ segments/experiments in two clicks. Owning the question chain is what keeps the number yours instead of becoming a Rorschach test.

### Q9 â€” How do privacy changes since iOS 14.5 alter classic marketing metrics?
**Testing:** awareness that attribution degraded structurally, not just noisily.
**Answer:** Third-party identifiers shrank, so last-click attribution systematically misassigns credit and platform-reported conversions double-count across walled gardens. Directionally the field moved to incrementality methods â€” geo holdouts, conversion lift studies â€” and first-party behavioral proxies. Practical stance: treat channel-level ROI figures as directional, budget with holdout-tested increments, and say so in writing when presenting numbers derived from degraded signals.
**Follow-up trap:** *"Does this matter for product engineers?"* â€” yes: it shifts growth budgets toward channels/products whose value survives measurement loss â€” retention-led products â€” which strengthens the case that product-side metrics (your tree) now carry more decision weight than ad-platform dashboards.

### Q10 â€” Build the metric system for a brand-new AI tutoring feature in month one.
**Testing:** greenfield judgment â€” minimal viable instrumentation.
**Answer:** Month one needs four things only: (1) outcome definition with baseline plan â€” % of hint-sessions ending in independent correct solution within 24h; (2) two inputs â€” hint-request rate, post-hint success rate; (3) guardrails â€” over-reliance flag (% learners requesting hints on >70% of attempts), token cost per session; (4) a weekly cohort readout, not real-time dashboards. Explicitly defer: NPS, referral loops, fancy trees until behavior stabilizes around week 6-8.
**Follow-up trap:** *"Why not instrument everything now, storage is cheap?"* â€” instrumentation is cheap but ATTENTION isn't: twenty early metrics guarantee three debates about vanity numbers per week; the constraint is the team's decision bandwidth, and month-one metrics exist to answer one question â€” do learners who use hints progress better?

### Q11 â€” Two teams own conflicting input metrics: growth wants more signups, infra wants lower cost/user. Resolve.
**Testing:** organizational metric diplomacy.
**Answer:** Escalate to the shared parent: express both in North Star units â€” marginal NS value per signup (cohort LTV by channel) vs cost per user â€” then set the exchange rate explicitly: e.g., accept paid signups while CAC payback â‰¤12 months and gross margin stays â‰¥75%. Conflicts between local optima are normal; what's broken is resolving them by seniority instead of by written exchange rates agreed in planning.
**Follow-up trap:** *"And if finance disagrees with your LTV assumptions?"* â€” good: disagreement should land on assumption provenance (which cohort fit, what churn curve), and the resolution is a jointly owned sensitivity table, not a louder opinion. Whoever writes down ranges first frames the negotiation.

### Q12 â€” When should a metric be retired?
**Testing:** metric hygiene â€” most orgs drown in zombie KPIs.
**Answer:** Retire when (1) its causal link to the NS broke (product changed, proxy stopped predicting â€” verify with the cohort regression annually); (2) it's been gamed past informativeness (numbers improve, reality doesn't); (3) two owners report different definitions and nobody can reconcile them; or (4) it hasn't appeared in a real decision for two quarters. Retirement needs a funeral â€” announce removal, archive the dashboard â€” otherwise zombie metrics respawn.
**Follow-up trap:** *"Isn't deleting metrics risky â€” what if you need history later?"* â€” archive raw events, delete the KPI: the warehouse retains facts forever cheaply; the scarce resource is the team's attention surface, and that's what retirement protects.

---

## Red flags

- North Star stated as activity ("logins," "messages sent") rather than value received.
- Ratio-only headline metrics with no absolute companion.
- Guardrail thresholds invented after seeing experiment results.
- "Leading indicators" never validated against historical outcomes.
- Every metric trending up forever â€” nobody owns counter-metrics.
- Two dashboards, two definitions of the same named metric, both used in meetings.
- Goodhart defenses absent wherever targets carry bonuses or performance reviews.

## Cheat card

```
NORTH STAR   output not input; sum not ratio; predicts revenue with
             nameable lag; validate NS->revenue on cohorts yearly
AARRR ORDER  diagnose retention FIRST (W4 <~5-10% consumer = bucket),
             then activation (60-80% typical signup loss), then acquisition
TREE         NS -> 3-5 inputs -> projects; each input: owner, current,
             target, SQL-exact definition; unmoved 2 qtrs -> prune
LEADING      earns title ONLY via cohort validation (8+ periods);
             Sean Ellis test: >=40% "very disappointed" ~= growth signal
GUARDRAILS   2-4 per experiment, numeric thresholds signed BEFORE launch;
             latency p95 <= +10%, complaints <0.5%, relevance >= -1%
GOODHART     measure->target->gamed; defenses: paired counter-metrics,
             ~5% human audit sampling, composites (weights=politics),
             holdouts; revisit annually - gaming evolves
FUNNEL MATH  effort -> biggest rate x volume x tractability;
             activation +6pts on 28% ~= +21% downstream relative lift
AI FEATURE   add cost-per-outcome input (token COGS) + over-reliance
             guardrail; engagement alone is not value
```

## Sources

- Amplitude, "The North Star Playbook," https://amplitude.com/north-star â€” accessed 2026-08-23
- Dave McClure, "Startup Metrics for Pirates" (AARRR), original deck and essay, https://500hats.typepad.com/500blogs/2007/09/startup-metrics.html â€” accessed 2026-08-23
- Sean Ellis, startup-marketing.com archives incl. the 40% disappointment-threshold survey, https://www.startup-marketing.com/ â€” accessed 2026-08-23
- Charles Goodhart (1975) and Marilyn Strathern's generalization; overview https://en.wikipedia.org/wiki/Goodhart%27s_law â€” accessed 2026-08-23
- Kohavi, Tang & Xu, *Trustworthy Online Controlled Experiments* (Cambridge University Press, 2020) â€” guardrail/OTE practice, ch. 2-4 â€” accessed 2026-08-23
- Reichheld, "The One Number You Need to Grow," Harvard Business Review (2003), https://hbr.org/2003/12/the-one-number-you-need-to-grow â€” accessed 2026-08-23

## Changelog

- 2026-08-23 â€” created

