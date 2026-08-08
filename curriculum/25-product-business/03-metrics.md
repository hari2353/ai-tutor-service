# North Star, AARRR, Leading vs Lagging Indicators, Guardrail Metrics, and Goodhart's Law

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** T25-product-thinking · **Updated:** 2026-08-08
> **Module id:** `T25-metrics` · **Tags:** product, critical

## The 30-second version

A North Star metric is the single number a team optimizes for that's supposed to correlate with long-term business value — but it's only useful if it's genuinely hard to game and if it's paired with guardrail metrics that catch the ways it gets gamed anyway, because every sufficiently important metric eventually does. AARRR (Acquisition, Activation, Retention, Referral, Revenue) is a funnel decomposition that stops teams from over-indexing on the top of the funnel (signups are easy to pump, and worthless if Activation and Retention are broken underneath). Leading indicators move before the outcome you care about and let you course-correct early; lagging indicators confirm the outcome after it's already happened and are what the business actually cares about — the discipline is picking leading indicators that are genuinely causally upstream of the lagging one, not just correlated with it in last quarter's data. Goodhart's Law — "when a measure becomes a target, it ceases to be a good measure" — is not a cute aphorism, it is the single most reliable predictor of how your own metrics program will fail, and the fix is never "pick a better metric," it's pairing every optimization target with guardrails that make the cheap way to win visible and unacceptable.

## Why this gets asked

The interviewer has watched a team hit its metric and lose the business — engagement went up because a dark pattern made the product harder to leave, a support-ticket SLA improved because agents started closing tickets early, DAU climbed because a notification system got more aggressive and churn quietly rose behind it. They want to know whether you pick metrics defensively, assuming they will be gamed (by your own team, under pressure, even unconsciously) and building the tripwire in from day one, or whether you pick a metric, ship, and get surprised six months later when the "win" turns out to have been extracted from somewhere the dashboard doesn't show.

---

## Lineage: past → present → future

**What came before.** Early web and SaaS metrics culture (2000s) was largely vanity-metric driven — pageviews, registered users, raw signups — numbers that were easy to instrument and easy to grow but weakly or not at all correlated with durable business value. Dave McClure's "Pirate Metrics" (AARRR — Acquisition, Activation, Retention, Referral, Revenue), popularized around 2007 in the startup/VC ecosystem, was a direct correction: it forced founders to decompose "growth" into a funnel and notice that a business pumping Acquisition while leaking at Activation or Retention was building on sand. Sean Ellis's growth-hacking movement (also mid-2000s) pushed further into leading-indicator thinking — the "40% test" (would 40%+ of users be "very disappointed" if the product disappeared) as an early, pre-revenue signal of product-market fit, precisely because revenue and retention take too long to observe to steer by directly in an early-stage product. The specific vocabulary "North Star Metric" was popularized later (Sean Ellis, then widely by Amplitude's product-led-growth content through the 2010s) as companies matured past pure funnel thinking and wanted one metric the whole company could rally around, rather than a scorecard nobody internalized.

**Where it stands now.** North Star metrics are widely adopted at product-led-growth companies, but the practitioner consensus by the 2020s is that a single North Star without guardrails is a known failure pattern — Amplitude's own later guidance explicitly pairs a North Star with a small set of "input metrics" (leading indicators the team can actually act on) and guardrails (metrics that must not degrade while the North Star is being pushed). The live disagreement is about granularity: some orgs run one company-wide North Star (e.g., "weekly active teams" for a collaboration tool), others argue a single number can't represent a multi-product portfolio and instead run a North Star per product line or per team, trading company-wide alignment for local actionability. Goodhart's Law itself is uncontested as a description of the risk — nobody in a metrics-mature org argues it doesn't apply to them — but there's real, ongoing disagreement about mitigation: some teams rely on guardrail metrics and manual review, others (particularly in ML-driven ranking/recommendation systems) are moving toward explicitly multi-objective optimization (optimizing a weighted composite or a constrained objective, e.g. "maximize engagement subject to a floor on well-being/diversity metrics") rather than trusting a human review process to catch gaming after the fact.

**Where it's heading.** High confidence: guardrail metrics and automated health-check dashboards (similar in spirit to the SRM checks in experimentation) are becoming table stakes at metrics-mature orgs, catching gamed or degraded guardrails automatically rather than relying on someone noticing in a monthly review. Moderate confidence: AI-generated or AI-summarized metrics narratives (an LLM producing "what moved and why" from raw dashboard data) are spreading, which raises a new version of the Goodhart risk — a model summarizing metrics can itself learn to produce narratives that make the numbers look good rather than accurately diagnosing them, echoing the exact incentive problem this module describes, just moved into the reporting layer instead of the operating layer. More speculative: as AI products increasingly optimize their own behavior against user engagement/satisfaction signals in near-real-time (RLHF-adjacent online optimization against user feedback), Goodhart's Law risk moves from "a team games a dashboard" to "a model games a live human feedback signal," a harder and less-understood version of the same failure mode — active research area, not settled practice.

---

## Mental model

```
LEADING vs LAGGING, and why the gap between them is where guardrails live

  LEADING INDICATOR              [TIME LAG]              LAGGING INDICATOR
  (moves first, actionable)       days-months            (confirms outcome, business cares)
  e.g. activation rate    ─────────────────────────▶     e.g. 90-day retention
  e.g. weekly active use   ─────────────────────────▶    e.g. net revenue retention
  e.g. NPS / CSAT          ─────────────────────────▶    e.g. churn rate

  GOODHART RISK: optimize the leading indicator directly, and it can be pumped
  in ways that DON'T move the lagging one it's supposed to predict --
  e.g. sign-up flow "activation" redefined to a trivially easy action inflates
  activation rate while retention stays flat or falls. The guardrail metric's
  job is to sit in that gap and catch the divergence early, before the lagging
  metric confirms it three months later.
```

---

## How it actually works

### North Star metric: what makes one good, and the two failure modes

A North Star metric should satisfy several properties simultaneously, and most candidate metrics fail at least one:

- **It reflects real customer value delivered, not company effort or company output.** "Number of features shipped" fails this immediately — it's an output metric, not a value metric. "Weekly active teams completing a core workflow" is closer, because it requires the customer to have actually gotten value, not just for the company to have shipped something.
- **It's a leading indicator of revenue/durable business value, not revenue itself.** Revenue is usually a poor North Star for a single team to optimize directly, because it's downstream of pricing, sales motion, and market conditions the team doesn't control, and because it moves too slowly to steer day-to-day decisions by. Slack's classic example — messages sent between team members within the first two weeks — was chosen because it correlated with long-term retention and was fast enough to observe to actually steer product decisions.
- **It's resistant, though never immune, to gaming.** "Time spent in app" is a famously weak North Star for exactly this reason — it's trivially inflated by making the product harder to navigate or more addictive in ways that don't reflect real value, and several major consumer platforms have had to publicly walk this back once the correlation with actual user well-being and long-term retention broke down.

**Failure mode one: choosing a vanity metric that's easy to move and weakly connected to value** — total signups, raw DAU with no activation qualifier, page views. **Failure mode two: choosing a metric so lagging and aggregate (like company-wide ARR) that no individual team's decisions visibly move it**, so it fails to actually guide day-to-day prioritization even though it's a "real" business metric. The right North Star sits in the narrow band between these — connected to real value, but proximate enough to be actionable.

### AARRR: the funnel discipline

Acquisition (how do people find you), Activation (do they experience real value fast), Retention (do they come back), Referral (do they bring others), Revenue (do they pay). The discipline it enforces is refusing to celebrate a metric at one stage without checking the stages after it. A 3x increase in signups (Acquisition) driven by a paid campaign is worthless, and can even be actively harmful to unit economics, if Activation is unchanged — you've just paid to acquire a larger cohort of users who churn at the same rate as before, at real CAC, with no corresponding LTV improvement (see the unit economics module for the arithmetic on why this specifically destroys a business's payback period).

Two practical uses beyond the mnemonic itself:

- **Diagnosing where a business's growth problem actually lives.** Plot conversion rate stage-to-stage; the stage with the steepest drop-off is usually where the highest-leverage fix lives, and it's very often not the stage getting the most executive attention (Acquisition, because it's the most visible and the easiest to buy more of with a bigger ad budget).
- **Assigning metric ownership without cross-team blame diffusion.** A team can own Activation without owning Acquisition; a clean funnel decomposition lets you localize responsibility instead of everyone pointing at a single blended conversion number nobody can act on directly.

### Leading vs lagging indicators, and the causal trap

The mechanical distinction is straightforward — leading indicators move before the outcome, lagging indicators confirm it after the fact. The trap that catches experienced people is treating **correlation in historical data as causation you can steer by**. If activation rate and 90-day retention were correlated in last year's cohort data, it's tempting to conclude "improve activation rate, and retention will follow" — but if the correlation exists because both are driven by a third factor (say, initial product-market fit for a specific segment), then artificially pumping activation rate (by redefining it to an easier action, by adding an onboarding checklist that gets clicked through without real engagement) will move the leading indicator while doing nothing to the lagging one it was supposed to predict. This is the single most common way North Star / leading-indicator programs quietly fail: the team hits its leading indicator targets every quarter, and eighteen months later someone notices the lagging metric (retention, revenue) never actually moved.

**The fix is not "pick a better indicator," it's continuously re-validate the leading→lagging link** — periodically check, on fresh cohorts, whether movement in the leading indicator still predicts movement in the lagging one, because that relationship can and does decay, especially after the leading indicator itself becomes an optimization target (this is Goodhart's Law arriving in exactly this gap).

### Guardrail metrics

A guardrail metric is not a metric you're trying to improve — it's a metric you're prohibited from degrading while pursuing your actual target, and its entire purpose is to make the cheap, ugly way of hitting your target visible before it does real damage. Concretely: if the target is "increase weekly active users," a guardrail set might include support-ticket volume (catches "we made errors harder to escape from, so people click around more"), unsubscribe/uninstall rate, and a well-being or satisfaction proxy (catches engagement pumped via addictive-but-resented patterns). Guardrails need the same rigor as the target metric — a vague, unmonitored guardrail ("we'll keep an eye on user happiness") isn't a guardrail, it's a good intention. A real guardrail has a threshold, an owner, and — ideally — an automated check that fires before a launch ships broadly, the same discipline an SRM check applies to an experiment's traffic split.

### Goodhart's Law: mechanism, not just aphorism

The formal statement (Charles Goodhart, 1975, originally about UK monetary policy targets) generalizes cleanly to any organization: once people's incentives (bonus, promotion, avoiding a bad review) are tied to a metric, the metric stops measuring the underlying thing it was a proxy for, because people optimize the metric itself, including through routes that don't touch the underlying thing at all. This isn't a claim about bad actors — it describes rational responses to incentive structures, which is exactly why "hire good people" doesn't fix it. A support agent hanging up on a hard call to protect average-handle-time is behaving completely rationally given what they're measured on; the failure is in the measurement design, not the agent's character.

Concrete, well-documented examples worth having ready:

- **Wells Fargo (2016 scandal)** — aggressive cross-sell targets tied to compensation led employees to open millions of unauthorized accounts to hit sales numbers; the metric ("accounts opened") completely decoupled from the thing it was meant to proxy (genuine customer relationship depth).
- **Call center average handle time (AHT)** — optimizing AHT directly produces agents who transfer calls unnecessarily, rush customers, or hang up on difficult calls; the metric goes down, customer satisfaction goes down with it, and the two were never as tightly coupled as the metric's designers assumed.
- **Support ticket resolution time/count** — agents close tickets before the issue is actually fixed to hit a resolution-count or resolution-time target; reopened-ticket rate (a guardrail) is what catches this, resolution count alone never will.
- **The Soviet nail factory anecdote** (whether the specific factory is apocryphal or not, the pattern is extremely well documented across command economies) — a factory measured on nail count produces huge numbers of tiny, useless nails; switched to a weight target, it produces a few enormous, equally useless nails. Any single-number proxy for "useful nail production" gets gamed the instant it's the thing being measured, and the failure mode reappears under a different metric definition, not just the first one you pick.

The mitigation that actually works in practice is not picking a ungameable metric (there mostly isn't one) — it's the combination of (a) a small set of guardrail metrics specifically designed to catch the *known* cheap ways to win, (b) periodic qualitative review (real conversations, real trace-throughs of a few "wins," not just dashboard trust), and (c) treating any metric that's been an explicit target for more than a couple of quarters with elevated suspicion, because Goodhart's effect compounds with how long and how directly a metric has been an incentive target.

---

## Build it from scratch

No code lab; the artifact worth building is a metrics tree with guardrails attached, in the shape a staff/principal engineer would actually bring into a planning review.

```text
# untested sketch — North Star + guardrails worksheet

NORTH STAR: Weekly Active Teams completing >= 1 core workflow
  why this and not "signups":     requires real value delivered, not just acquisition
  why this and not "revenue":     too lagging/aggregate for a single team to steer by day-to-day
  known cheap ways to game it:    - count "workflow started but abandoned" as completed
                                   - add a trivial forced action that inflates "active"
                                   - spam notifications to pump session count

GUARDRAILS (must not degrade while North Star improves):
  - support ticket volume/team          threshold: no >10% increase QoQ
  - 30-day team retention                threshold: no decrease QoQ
  - unsubscribe / seat-reduction rate    threshold: no increase QoQ
  - workflow completion QUALITY          threshold: manual review of a sample of "completed"
                                          workflows each quarter -- confirms the metric's
                                          definition hasn't drifted to something trivial

RE-VALIDATION CADENCE: quarterly check that North Star movement still predicts
  the lagging metric (net revenue retention) it was chosen to proxy for --
  if the correlation has decayed, the North Star itself needs to be revisited,
  not just re-optimized harder.
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| North Star hits target every quarter, revenue/retention flat or declining | Leading indicator's causal link to the lagging metric decayed, often because the leading indicator itself became an incentive target (Goodhart) | Periodically re-validate the leading→lagging correlation on fresh cohorts; don't assume last year's relationship still holds |
| "Activation rate" keeps improving but support tickets and churn are both rising | Activation was redefined (consciously or not) to an easier, more gameable action | Freeze the metric definition, audit for silent redefinition, add a guardrail on the specific behavior that changed |
| Team hits DAU/engagement targets via more aggressive notifications | Optimizing a single engagement metric with no well-being/satisfaction guardrail | Add an explicit guardrail (uninstall rate, notification opt-out rate, CSAT) with a hard threshold, reviewed before broad rollout |
| Dashboard says everything's healthy, a qualitative review of "wins" finds hollow ones | Metrics program has no periodic manual trace-through of a sample of the wins the dashboard reports | Add a recurring (monthly/quarterly) qualitative audit — pick five "wins," trace them end to end, confirm they reflect real value |
| Cross-team blame diffusion on a blended conversion number | No AARRR-style funnel decomposition, so no team can be held accountable for a specific stage | Decompose the funnel and assign stage ownership; report stage-level, not just blended, conversion |

---

## Tradeoffs & when NOT to use it

- **Don't run a single company-wide North Star for a genuinely multi-product portfolio.** Forcing unrelated product lines onto one number produces a metric nobody can actually act on locally; per-product-line North Stars, rolled up qualitatively at the company level, usually serve better.
- **Don't add so many guardrails that the team can't tell what actually matters.** Two to four guardrails, chosen specifically against the known cheap ways to game the target, beats a dashboard of twenty metrics nobody reviews closely enough to catch anything.
- **Leading indicators lose their value once the leading→lagging link decays** — don't keep optimizing an indicator on faith; re-validate the correlation periodically, especially after the indicator's been an explicit incentive target for multiple quarters.
- **Vanity metrics (raw signups, pageviews, raw DAU) are fine for external communication (press, investor updates) but are actively dangerous as internal optimization targets** — know which audience a metric is for, and don't let an externally-facing vanity number quietly become an internally-optimized one.
- **Goodhart mitigation has a real cost** — guardrails, periodic qualitative review, and re-validation all take time away from shipping. The intensity of mitigation should scale with how directly and how long a metric has been tied to real incentives (compensation, promotion), not applied uniformly to every internal dashboard number.

---

## Interview questions

### Q1 — What makes a good North Star metric, and give a real example of a company that got it right (or wrong).
**Answer:** It should reflect real customer value delivered (not company output), act as a leading indicator of durable business value fast enough to steer decisions by, and resist easy gaming. Slack's "messages sent between teammates in the first two weeks" is a commonly cited good example — it required genuine usage, not just signup, and correlated with long-term retention. "Time spent in app" as a North Star for consumer social products is a commonly cited failure — trivially inflatable via addictive patterns that decoupled from real user value and eventually had to be walked back publicly by more than one major platform.
**Follow-up trap:** *"How do you know your North Star hasn't already decoupled from the lagging metric it's supposed to predict?"* — you don't, by default; you have to periodically re-validate the correlation on fresh cohort data rather than assuming a relationship measured once still holds, especially after the metric has been an explicit target for several quarters.

### Q2 — Explain AARRR and why celebrating an Acquisition win in isolation is often a mistake.
**Answer:** Acquisition, Activation, Retention, Referral, Revenue — a funnel decomposition. Celebrating Acquisition alone (e.g., a 3x signup spike from a paid campaign) without checking Activation and Retention risks paying real CAC to acquire a cohort that behaves no differently than before, which can actively worsen unit economics rather than grow the business — you've spent money to make the funnel wider at the top without checking whether it leaks the same amount as before.
**Follow-up trap:** *"Which stage of AARRR gets the most executive attention, and is that where the leverage actually is?"* — Acquisition, usually, because it's visible and buyable with a bigger ad budget; the actual highest-leverage stage is wherever the steepest stage-to-stage drop-off is, which is very often Activation or Retention and gets comparatively less attention because it's harder and slower to fix.

### Q3 — Explain Goodhart's Law and why "hire people with integrity" doesn't fix it.
**Answer:** "When a measure becomes a target, it ceases to be a good measure" — once a metric is tied to real incentives (bonus, promotion, avoiding a bad review), people rationally optimize the metric itself, including through routes that decouple from the underlying thing it was meant to proxy for. It's not a claim about bad actors — a call center agent hanging up to protect average handle time is behaving rationally given what they're measured on. The fix has to be in measurement design (guardrails, periodic qualitative review), not personnel selection.
**Follow-up trap:** *"Give a real, named example, not the aphorism."* — Wells Fargo's 2016 unauthorized-accounts scandal: cross-sell targets tied to compensation produced millions of fake accounts, completely decoupled from genuine customer relationship depth, the thing the metric was meant to proxy for.

### Q4 — What's a guardrail metric, and how is it different from just tracking more metrics?
**Answer:** A guardrail is a metric you're explicitly prohibited from degrading while pursuing your actual target — it needs a threshold, an owner, and ideally an automated check, specifically designed against the *known* cheap ways to game the target metric. Tracking more metrics generally, without designing them against specific gaming vectors, produces a dashboard nobody reviews closely enough to catch anything — quantity of tracked metrics is not the same as protection.
**Follow-up trap:** *"How many guardrails is too many?"* — enough is usually two to four, chosen deliberately against the specific ways you expect the target to be gamed; a twenty-metric dashboard with no prioritization dilutes attention and none of them get the scrutiny a real guardrail needs.

### Q5 — Your team's leading indicator (activation rate) has hit target for three straight quarters, but retention hasn't moved. Diagnose it.
**Answer:** Most likely the leading→lagging causal link has decayed or was correlational rather than causal to begin with, and possibly the activation definition itself drifted toward something easier to hit (a form of Goodhart gaming) once it became an explicit target. Re-validate on fresh cohort data whether activation, as currently defined, still predicts retention; audit whether the definition of "activated" has silently changed; check whether a guardrail on retention or a proxy for real engagement would have caught this earlier.
**Follow-up trap:** *"The metric definition hasn't changed on paper. Could it still be gamed?"* — yes — the underlying user behavior that satisfies the definition can shift (e.g., users click through an onboarding checklist without genuinely engaging) even if the metric's formal definition is untouched; this is harder to catch than an explicit redefinition and needs qualitative sampling, not just a metrics-pipeline audit.

### Q6 — When would you use revenue itself as a North Star, versus a proxy metric?
**Answer:** Revenue is usually a poor North Star for a single team to optimize day-to-day — it's downstream of pricing, sales motion, and market conditions outside the team's control, and it moves too slowly to steer decisions by. It's a reasonable company-level or portfolio-level lagging metric to report against, but a team needs a faster, more proximate leading indicator it can actually act on, validated to correlate with revenue over time.
**Follow-up trap:** *"What if leadership insists every team's success is measured on revenue contribution directly?"* — push for revenue as the eventual validation/lagging check, but negotiate a team-level leading indicator for actual day-to-day steering, and make the leading→lagging link explicit and periodically re-checked so the team isn't flying blind between the (slow) revenue readouts.

### Q7 — How would you design a metrics program for a brand-new AI feature with no historical data to validate a leading indicator against?
**Answer:** Start with a small number of directly observable proxy metrics tied closely to the stated outcome (e.g., task completion rate, time-to-resolution, escalation-to-human rate) rather than inventing a North Star prematurely; treat the leading→lagging link as an open hypothesis to validate over the first few months, not an assumed fact; instrument guardrails from day one (hallucination/error rate, cost per interaction, user-reported dissatisfaction) since a new AI feature has more, and less well-understood, cheap ways to "win" the surface metric than a mature product does.
**Follow-up trap:** *"What's the single most likely way this specific metrics program gets gamed?"* — an AI system (or the team operating it) optimizing for a proxy like "conversation length" or "user replies to the bot" that superficially looks like engagement but actually reflects the system failing to resolve the user's need efficiently — a strong "gamed metric" instinct here is a real signal at the AI-product layer specifically.

### Q8 — A VP wants to add "features shipped per quarter" as a team metric. How do you respond?
**Answer:** Name it explicitly as an output metric, not a value metric — it measures company effort, not customer value delivered, and it actively incentivizes shipping more, smaller, less-validated things rather than fewer things that move a real outcome. Propose replacing it with (or pairing it with) an outcome-oriented leading indicator tied to the team's actual North Star, and if leadership needs a velocity signal, keep it as an internal engineering-health metric, explicitly not tied to compensation or promotion, to limit the Goodhart risk.
**Follow-up trap:** *"Leadership says they need something they can track weekly, and outcome metrics move too slowly for that."* — offer a faster-moving *leading* indicator of the outcome (e.g., adoption rate of shipped features within two weeks of release) rather than reverting to a pure output count — the cadence problem is real, but the fix is a better leading indicator, not abandoning outcome-orientation for effort-tracking.

### Q9 — What's the difference between a leading indicator that's genuinely causal and one that's merely correlated with the lagging metric, and why does it matter operationally?
**Answer:** A causal leading indicator, when you intervene to move it, actually moves the lagging outcome; a merely correlated one moved alongside the outcome historically because both were driven by some third factor, and intervening on the leading indicator directly does nothing to the outcome. It matters because teams routinely optimize the leading indicator on the assumption of causality, hit their targets every quarter, and only discover eighteen months later — when the lagging metric is finally checked — that nothing real moved.
**Follow-up trap:** *"How would you actually test whether the relationship is causal?"* — ideally a randomized experiment that manipulates the leading indicator directly (if feasible) and observes the lagging one; short of that, look for natural variation (different cohorts, different rollout timing) and check whether the correlation holds up out-of-sample, on data the leading indicator wasn't chosen or tuned against.

### Q10 — Design a North Star and guardrail set for an AI coding assistant feature.
**Testing:** synthesis — applying the whole module to a domain the candidate presumably knows well.
**Answer:** North Star candidate: accepted-suggestion rate that survives to a shipped, unmodified-or-lightly-modified commit within N days (proxies real value delivered, not just a suggestion being shown or clicked). Guardrails: bug/regression rate attributable to AI-suggested code (catches "accepted fast but wrong"), suggestion latency (catches a North Star win achieved by showing worse-but-faster suggestions), and a manual quarterly review of a sample of "accepted" suggestions for real usefulness versus rubber-stamped acceptance. Known cheap ways to game the North Star: making suggestions blandly safe/boilerplate to raise acceptance rate without raising real usefulness, or measuring "accepted" at the keystroke level rather than at the surviving-commit level.
**Follow-up trap:** *"Your accepted-suggestion rate is climbing nicely. What's the first thing you check before trusting it?"* — whether the suggestions accepted are getting *more* boilerplate/generic over time (a classic cheap way to raise acceptance without raising value), by sampling actual accepted suggestions rather than trusting the aggregate rate — this is the qualitative-review discipline the module argues for, applied concretely.

---

## Red flags that fail you

- Naming a vanity metric (raw signups, raw DAU, pageviews) as a proposed North Star without caveats.
- Describing Goodhart's Law as being about bad actors ("bad employees game metrics") rather than rational responses to incentive design.
- No guardrail metrics mentioned when describing how you'd protect a target metric from gaming.
- Treating a historical correlation between a leading and lagging indicator as permanent, with no mention of re-validation.
- Celebrating a top-of-funnel (Acquisition) win without checking Activation/Retention underneath it.
- Proposing "features shipped" or similarly effort-based metrics as an outcome measure.

---

## Cheat card

```
NORTH STAR      reflects real customer VALUE (not company output), leading
                indicator of durable business value, fast enough to steer by,
                resistant (never immune) to gaming
                good: Slack "msgs sent/teammate in first 2 wks" (predicts retention)
                bad:  "time spent in app" -- trivially gamed via addictive patterns
AARRR           Acquisition -> Activation -> Retention -> Referral -> Revenue
                celebrating Acquisition alone while Activation/Retention are flat
                = paying CAC for a cohort that behaves the same as before
LEADING/LAGGING leading moves first & is actionable; lagging confirms outcome later
                TRAP: correlation != causation -- pumping a leading indicator
                directly can leave the lagging metric it "predicts" untouched
                FIX: periodically re-validate the leading->lagging link on fresh data
GUARDRAIL       metric you're PROHIBITED from degrading while chasing the target;
                needs a threshold + owner + ideally automated check
                design each guardrail against a SPECIFIC known cheap way to game
                the target -- 2-4 sharp guardrails beat 20 unreviewed metrics
GOODHART'S LAW  "when a measure becomes a target, it ceases to be a good measure"
                (Goodhart, 1975) -- rational response to incentives, not bad actors
                examples: Wells Fargo fake accounts (cross-sell targets), call
                center AHT (agents hang up/transfer to protect the number),
                support ticket "resolved" count (closed before actually fixed),
                Soviet nail factory (count target -> tiny useless nails; switch
                to weight target -> few giant useless nails -- ANY single proxy
                gets gamed once it's the thing measured)
MITIGATION      no ungameable metric exists; combine guardrails + periodic
                QUALITATIVE review (trace through real "wins") + treat any metric
                that's been an incentive target 2+ quarters with elevated suspicion
```

## Sources

- [Goodhart's Law and the Death of Honest Metrics — Medium](https://medium.com/@claus.nisslmueller/goodharts-law-and-the-death-of-honest-metrics-e08cc756f93a) — accessed 2026-08-08
- [Goodhart's Law: Why Metrics Get Gamed and How to Prevent It — KPI Tree](https://kpitree.co/guides/frameworks/goodharts-law) — accessed 2026-08-08
- [Goodhart's Law in Software: Why Your Metrics Get Gamed — Code Pulse](https://codepulsehq.com/guides/goodharts-law-engineering-metrics) — accessed 2026-08-08
- Charles Goodhart, "Problems of Monetary Management: The U.K. Experience" (1975) — original formulation
- Dave McClure, "Startup Metrics for Pirates" (2007) — AARRR framework

## Changelog
- 2026-08-08 — created
