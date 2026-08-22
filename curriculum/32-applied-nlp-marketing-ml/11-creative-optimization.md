# Creative Testing & Dynamic Creative Optimization: Text + Image, Bandits for Allocation, Creative Fatigue

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2.5h · **Prereqs:** T32-personalization (bandits), T32-experiment-design · **Updated:** 2026-08-02
> **Module id:** `T32-creative-optimization` · **Tags:** marketing

## The 30-second version

Creative testing is experiment design applied to the actual assets — headlines, images, video, CTA copy — and dynamic creative optimization (DCO) is what happens when you stop treating "which creative wins" as a one-time A/B question and instead run it as a continuous allocation problem: a multi-armed (or contextual) bandit that shifts traffic toward better-performing creative combinations in near-real time instead of waiting for a fixed-horizon test to conclude. The natural formulation is a bandit, not a static test, because creative performance isn't stationary — it decays. Creative fatigue is the specific, well-documented phenomenon where a given creative's engagement metrics (CTR, hook rate) degrade as the same audience sees it repeatedly, commonly flagged at a CTR drop of roughly 10%+ or a frequency exceeding about 3 impressions per user in prospecting campaigns, and a bandit that doesn't explicitly model decay will keep exploiting a creative well past the point it's actually still the best option. DCO across text and image multiplies the combinatorial space the same way multivariate testing does (module 07's factorial-design math applies directly), so production DCO systems constrain the search space with feature-level bandits (learning which *elements* work, not just which whole combinations) rather than brute-force testing every combination.

## Why this gets asked

Expedia's marketing content spans images, headlines, and promotional copy across a huge and constantly refreshing property/campaign catalog — creative goes stale fast, and a static "pick a winner and run it forever" approach both wastes early-test traffic and misses the point where a winning creative starts fatiguing. The interviewer wants to know you think of creative selection as an ongoing allocation and decay-modeling problem, connected directly to the bandit and experiment-design machinery covered earlier in this track, not a one-off design exercise.

---

## Lineage: past → present → future

**What came before.** Manual creative testing — a marketer's hypothesis, a handful of variants, a fixed-duration A/B test, a manual decision to roll the winner out to 100% of spend — was standard through the 2000s-2010s display and search advertising era. It works but is slow (each cycle takes as long as the test needs to reach significance), doesn't adapt within a campaign's run, and has no native mechanism for detecting when a "winning" creative starts fatiguing partway through its run. Platform-level auto-optimization (Google/Meta ad platforms' automated creative rotation and "best-performing ad" features, mid-2010s onward) began automating the allocation decision but largely as an opaque black box, giving advertisers limited visibility or control over the underlying explore/exploit logic.

**Where it stands now.** DCO is standard tooling at ad platforms and MarTech vendors, formulated explicitly as a multi-armed or contextual bandit problem in the applied literature and in most vendor documentation — real reported results include double-digit CTR lifts and cost-neutral acquisition-rate gains (e.g., published case studies report Thompson Sampling improving customer acquisition roughly 8% at no added cost, and bandit-based creative selection improving CTR by roughly 10% versus a static baseline in reported comparisons) versus static A/B rotation. The live disagreement is less about "bandit vs. static test" (bandits have largely won for ongoing allocation) and more about **how granular to make the bandit's action space**: full-combination bandits (each unique headline+image+CTA combination is one arm) hit the same combinatorial explosion problem as full-factorial MVT, so most production DCO systems instead use feature-level or component-level bandits (learning which individual elements or element-pairs perform well, then composing) — a genuinely harder modeling problem than a flat bandit, and different vendors and teams make different tradeoffs about how much interaction structure to model explicitly versus approximate.

**Where it's heading.** Automated creative generation (LLM/diffusion-model-generated variants feeding directly into the bandit's action space, rather than a human-authored fixed set of variants) is real and growing — this connects directly to the content-generation-ml module's quality-gate and brand-safety machinery, because an auto-generating creative pipeline needs the same grounding/compliance gates before a variant is even eligible to enter the bandit's rotation. Moderate-to-high confidence this becomes standard at platforms with the volume to support it. Proactive fatigue prediction — using ML to flag a creative's fatigue trajectory days before human analysts would notice the metric decline, enabling refresh before performance visibly degrades rather than after — is an active direction with reported production use, moderate confidence on how widespread this becomes versus reactive monitoring remaining the norm at smaller-scale operations. More speculative: fully autonomous creative lifecycle management (generation, testing, allocation, and retirement with no human creative director in the loop at any stage) — technically plausible given the pieces above, but brand and creative-quality judgment remains a genuinely hard-to-automate piece, and no consensus exists on how far this goes before requiring human creative oversight.

---

## Mental model

Static A/B test vs. bandit-based DCO, over time:

```
STATIC A/B TEST                          BANDIT-BASED DCO
traffic split fixed (e.g. 50/50)          traffic split shifts continuously toward
for the whole test duration,               better-performing arms as evidence accumulates,
regardless of interim results.             and back away from a decaying "winner" as its
Winner declared once, deployed             performance data starts trending down --
100% until manually refreshed.             NO single "declare winner and freeze" moment.

  50% |------A------|                      100%|                    A pulled back as
  50% |------B------|--> pick winner            |  A rising            fatigue detected
       (fixed duration,                          |    \___________
        no adaptation                       0%   |________B_______\____ C introduced,
        mid-test)                                 t0      t1        t2   ramping
```

Creative fatigue as a decay curve layered on top of the bandit's reward estimate: the bandit's naive assumption is that a creative's true reward is stationary (constant over time); fatigue breaks that assumption, so a fatigue-aware system either treats reward as explicitly time-varying (discounting older observations more, or modeling a decay trend directly) or triggers a forced-refresh/re-exploration signal once a fatigue threshold (e.g., CTR decline, frequency cap) is crossed.

---

## How it actually works

### Creative testing as applied experiment design

Everything from module 07 (experiment-design) applies directly: a creative test needs a defined MDE (what CTR or conversion-rate lift is worth detecting), adequate power at the traffic the campaign actually has, a correct randomization unit (typically user/device, since the same user seeing both variant A and variant B across sessions dilutes the comparison exactly as described in that module), and an SRM check before trusting any result — creative tests are exactly as vulnerable to a tracking-pixel bug silently breaking one variant's measurement as any other online experiment, and creative-specific bugs (a broken image asset, a truncated headline on certain devices) are a common, underappreciated real-world cause.

### Dynamic creative optimization: the combinatorial problem

DCO assembling creative from independent components — say 4 headlines x 5 images x 3 CTAs — creates 60 full combinations, and naive full-combination testing hits the same `L^k`-style traffic cost problem as full-factorial MVT (module 07): each combination needs enough impressions to estimate its performance reliably, and the total requirement multiplies with combination count. Two practical responses: (1) **feature-level / component bandits** — instead of treating each full combination as one bandit arm, model the *marginal* contribution of each component (this headline tends to perform well, this image tends to perform well) and combine the best-performing components, which is a much lower-dimensional learning problem but assumes limited interaction effects between components (the same aliasing bet fractional-factorial design makes, just applied to an online bandit instead of a fixed test); (2) **contextual bandits over the combination space**, using shared structure (e.g., a linear or low-rank model over component-level features rather than treating each of the 60 combinations as an independent unknown arm) to let data about one combination partially inform estimates for related combinations that share a component.

**When feature-level bandits are wrong.** If there's a real, strong interaction (a specific headline only works paired with a specific image — e.g., an urgency-toned headline paired with an image implying scarcity, versus the same headline paired with a calm lifestyle image), a component-level bandit that assumes components combine additively will systematically underrate that specific pairing relative to treating it as its own arm — the same fundamental limitation fractional-factorial designs accept in exchange for traffic efficiency, and worth naming explicitly when defending a component-level DCO design.

### Bandits for creative allocation, with numbers

Multi-armed bandit algorithms (epsilon-greedy, UCB, Thompson Sampling — the same family covered in the personalization module, applied here with creative variants as arms instead of content recommendations) shift allocation continuously rather than waiting for a fixed-horizon test to conclude, which is the mechanical reason they outperform static rotation in reported comparisons: traffic isn't wasted on a clearly-losing variant for the full test duration, and a clearly-winning variant gets more traffic sooner. Reported production results in the applied literature include Thompson Sampling improving customer acquisition roughly 8% at no additional cost in a large-scale retail-banking display advertising deployment, and bandit-based creative selection improving CTR by roughly 10% relative to a static baseline in an online retail platform case study — these numbers are context-specific (traffic volume, baseline creative quality, market) and shouldn't be quoted as universal, but they're representative of the magnitude reported when moving from static rotation to bandit-based allocation.

### Creative fatigue

**The phenomenon.** A creative's engagement metrics degrade the more times the same audience sees it — this is distinct from a creative simply being bad from the start; a genuinely strong creative fatigues too, just later. Commonly cited operational signals: CTR decline of roughly 10%+ from the creative's own early-run baseline, CPA rising roughly 15%+, and impression frequency exceeding roughly 3 per user in prospecting (top-of-funnel, not-yet-converted-audience) campaigns — these are heuristic thresholds used in practice, not universal constants, and the right threshold depends on category, funnel stage, and audience size.

**Why a naive bandit misses this.** A standard bandit's reward model implicitly assumes each arm's true reward is stationary — it updates its belief about a creative's performance as an average (or a Bayesian posterior) over all historical observations, weighting old and new data similarly (sometimes with a mild recency bias built into some implementations, but not by default). If a creative's true performance is declining, a bandit using an un-decayed average will keep believing it's better than it currently is for a while after the decline starts, continuing to over-allocate traffic to a fatiguing creative — this is the direct, mechanical link between "creative fatigue" as a marketing phenomenon and "non-stationary bandit" as the correct statistical framing.

**Fixes.** Sliding-window or exponentially-decayed reward estimates (weight recent impressions more heavily than old ones, so the bandit's belief tracks a declining trend instead of averaging it away), explicit frequency capping (hard limits on impressions per user regardless of what the bandit's reward estimate says, directly addressing the frequency-driven fatigue mechanism rather than relying on the reward signal to catch it after the fact), and proactive fatigue-prediction models (a separate model trained to predict a creative's decay trajectory from early engagement-curve shape, flagging likely fatigue before the aggregate metric has visibly declined enough for a simple threshold rule to catch it) — this last approach is reported to catch fatigue "days before human analysts would," which matters because by the time a lagging threshold-based check fires, real spend has already gone to a decaying creative.

---

## Build it from scratch

```python
# untested sketch — Thompson Sampling creative bandit with exponential-decay fatigue tracking
import numpy as np

class FatigueAwareCreativeBandit:
    def __init__(self, n_creatives: int, decay: float = 0.98):
        self.decay = decay  # < 1.0: older observations count for less each round
        self.alpha = np.ones(n_creatives)   # Beta posterior params per creative
        self.beta = np.ones(n_creatives)
        self.impressions_per_user = {}       # frequency cap tracking

    def select(self, user_id: str, max_frequency: int = 3) -> int:
        eligible = [
            i for i in range(len(self.alpha))
            if self.impressions_per_user.get((user_id, i), 0) < max_frequency
        ]
        if not eligible:
            eligible = list(range(len(self.alpha)))  # fallback if all frequency-capped
        samples = np.random.beta(self.alpha[eligible], self.beta[eligible])
        return eligible[int(np.argmax(samples))]

    def update(self, creative_idx: int, user_id: str, clicked: bool):
        # decay ALL creatives' posteriors slightly toward the uninformative prior each round --
        # keeps the bandit responsive to a creative whose true performance is declining,
        # instead of averaging the whole history together as if it were stationary
        self.alpha = 1 + (self.alpha - 1) * self.decay
        self.beta = 1 + (self.beta - 1) * self.decay
        if clicked:
            self.alpha[creative_idx] += 1
        else:
            self.beta[creative_idx] += 1
        key = (user_id, creative_idx)
        self.impressions_per_user[key] = self.impressions_per_user.get(key, 0) + 1
```

---

## How it's done in production

Ad-platform native tools (Meta Advantage+ Creative, Google's Performance Max asset optimization) run DCO largely as a managed black box, giving advertisers a component library (headlines, images, CTAs) and handling allocation internally — high convenience, low visibility into the underlying bandit logic or fatigue-handling approach. Dedicated MarTech DCO vendors (e.g., platforms specializing in dynamic creative assembly) offer more configurable component-level bandits with explicit frequency capping and fatigue dashboards. In-house systems at large advertisers typically build a contextual or component-level bandit on top of standard bandit tooling (the same Vowpal Wabbit-class infrastructure as personalization bandits), specifically because they want visibility into and control over the fatigue-handling and exploration-budget logic rather than trusting a platform's opaque auto-optimization.

| Symptom | Cause | Fix |
|---|---|---|
| A previously winning creative's performance quietly declines while the bandit keeps allocating it heavy traffic | Non-stationary reward (fatigue) not modeled — bandit's un-decayed average lags the true declining trend | Add exponential decay / sliding window to the reward estimate, or add explicit frequency capping independent of the reward signal |
| DCO combination testing never converges / results look noisy across dozens of combinations | Full-combination bandit hitting the same combinatorial explosion as full-factorial MVT | Move to feature-level/component bandits, accepting the same additive-interaction assumption fractional-factorial designs make |
| A specific headline+image pairing underperforms what component-level scores predicted | Real interaction effect the additive component model can't capture | Treat that specific pairing as its own arm (partial full-combination testing) rather than relying purely on component-level composition for that segment |
| Creative test result invalidated after the fact | SRM or a creative-specific tracking bug (broken image asset, truncated headline on some devices) went unchecked | Run the standard SRM check and creative-rendering QA before trusting any creative test result, same discipline as any other online experiment |
| Fatigue detected only after CPA has already risen significantly | Reactive threshold-based monitoring catching decline only after it's well underway | Add a proactive fatigue-prediction model using early engagement-curve shape, flagging likely decay before the lagging aggregate metric crosses a threshold |

---

## Tradeoffs & when NOT to use it

- **Don't run full-combination DCO bandits when the component count makes the combinatorial space large relative to available traffic** — same math as module 07's factorial design cost; feature-level bandits are the practical answer, with the explicit tradeoff of assuming limited component interactions.
- **Don't use a plain (non-decayed) bandit reward model for creative allocation** if fatigue is a real dynamic in the category — a stationary-reward assumption is simply wrong for creative, and the bandit will systematically over-serve declining creative without a decay or frequency-cap mechanism.
- **Don't rely purely on reactive fatigue thresholds (CTR drop, frequency cap) without any proactive signal** in high-spend campaigns — by the time a lagging threshold fires, meaningful budget has already gone to a decaying creative; the gap between reactive and proactive detection is a real, quantifiable cost.
- **Don't fully automate creative generation and allocation with zero human creative oversight** — this module's numeric optimization machinery (bandits, decay models, frequency caps) has no mechanism for judging brand fit, creative quality, or the compliance/brand-safety concerns covered in the content-generation-ml module; those gates still apply to whatever feeds the creative bandit's action space.
- **A static A/B test, not a bandit, is still the right choice for a one-off, low-volume creative decision** (a single flagship campaign asset, tested once before a launch) — the bandit's continuous-allocation advantage matters most for high-volume, frequently-refreshing creative pools, not a single high-stakes one-time choice where a clean, auditable fixed-horizon test is easier to defend to stakeholders.

---

## Interview questions

### Q1 — Why is dynamic creative optimization better framed as a bandit problem than a sequence of A/B tests?
**Answer:** Creative performance isn't stationary — it fatigues — and a fixed-horizon A/B test has no mechanism to reallocate traffic mid-test as evidence accumulates or as a "winner" starts declining; it waits for the test to conclude, then makes one discrete decision. A bandit continuously shifts allocation toward better-performing arms and can pull back from a decaying one in near-real time, which is a direct match for how creative actually behaves over a campaign's run.
**Follow-up trap:** *"Is a bandit always better than a fixed A/B test for creative?"* — no; for a one-off, low-volume, high-stakes decision (a single flagship campaign asset), a clean fixed-horizon test is easier to defend and audit, and the bandit's continuous-allocation advantage matters most for high-volume, frequently-refreshing creative pools.

### Q2 — Why does full-combination DCO hit a traffic wall, and what's the standard fix?
**Answer:** Testing every combination of independent creative components (e.g., 4 headlines x 5 images x 3 CTAs = 60 combinations) requires roughly the same per-arm sample size a single test would need for each combination, so total traffic need scales with combination count — the same `L^k`-style cost as full-factorial MVT. The standard fix is feature-level/component bandits, modeling each component's marginal contribution rather than each full combination as an independent unknown.
**Follow-up trap:** *"What does the component-level approach assume, and when does that assumption fail?"* — it assumes components combine roughly additively (limited interaction effects); it fails when a specific pairing (e.g., a specific headline-image combination) has a real interaction the additive model can't capture, in which case that pairing should be tested as its own arm.

### Q3 — Define creative fatigue and explain why a standard bandit's reward model doesn't automatically account for it.
**Answer:** Creative fatigue is the decline in a creative's engagement metrics (CTR, hook rate) as the same audience sees it repeatedly — commonly flagged around a 10%+ CTR drop or 15%+ CPA rise, or frequency exceeding roughly 3 in prospecting campaigns. A standard bandit's reward estimate is implicitly an average (or Bayesian posterior) over all historical observations with no built-in decay, so it assumes stationary reward — it will keep believing a fatiguing creative is as good as its historical average for a while after true performance starts declining.
**Follow-up trap:** *"How would you fix the bandit's model, not just add an external threshold rule?"* — exponential decay or a sliding window on the reward estimate so recent (post-decline) observations are weighted more heavily than the stale historical average, making the bandit's belief track the actual declining trend instead of averaging it away.

### Q4 — What's the difference between reactive and proactive fatigue detection, and why does the gap matter?
**Answer:** Reactive detection fires once an aggregate metric (CTR, CPA) crosses a threshold, which by construction happens only after meaningful decline has already occurred and real spend has already gone to the decaying creative. Proactive detection uses a model trained on early engagement-curve shape to predict the decay trajectory before the aggregate metric has visibly crossed a threshold, catching fatigue earlier and reducing wasted spend.
**Follow-up trap:** *"Isn't a proactive model just guessing without full information?"* — it's a genuine tradeoff (earlier signal vs. higher false-positive risk from predicting off less data), and the right answer names both: proactive detection is worth it in high-spend campaigns where the cost of late detection is large, and reactive thresholds remain a reasonable, simpler baseline in lower-stakes campaigns.

### Q5 — A component-level DCO bandit shows headline X and image Y each perform well individually, but the combination underperforms what the additive model predicted. What's going on?
**Answer:** A real interaction effect the additive component model doesn't capture — this is the same tradeoff fractional-factorial designs make explicitly (aliasing/assuming away certain interactions to save traffic), just implicit in a component-level bandit's structure. The fix is treating that specific pairing as its own arm going forward, rather than relying on component-level composition for that segment.
**Follow-up trap:** *"How would you detect this systematically rather than noticing it by chance?"* — periodically spot-check a sample of full combinations against what the component model predicts, flagging combinations with large prediction residuals as candidates for dedicated testing.

### Q6 — What experiment-design fundamentals from a standard A/B test still apply directly to creative testing?
**Answer:** Randomization unit (user/device, to avoid the same user seeing multiple variants across sessions and diluting the comparison), power analysis and MDE (is the traffic sufficient to detect a meaningful CTR/conversion lift), and SRM checks (a broken image asset or truncated headline on certain devices is a common, creative-specific real-world cause of exactly the tracking-pixel-style bug that produces sample ratio mismatch).
**Follow-up trap:** *"Give a creative-specific example of an SRM-causing bug."* — an image asset that fails to render on a specific device/browser combination for one variant, silently dropping impressions or clicks from that variant's logged data in a way that isn't randomly distributed across the audience.

### Q7 — What reported real-world magnitude of improvement does bandit-based creative allocation show over static rotation, and how should you caveat those numbers?
**Answer:** Published case studies report Thompson Sampling improving customer acquisition roughly 8% at no added cost in a large retail-banking display deployment, and bandit-based selection improving CTR roughly 10% versus static baseline in an online retail case study. These are context-specific (traffic volume, baseline creative quality, market, category) and shouldn't be quoted as universal constants — cite them as representative of the reported magnitude, not a guaranteed lift for any given deployment.
**Follow-up trap:** *"Would you promise a stakeholder an 8-10% lift based on these numbers?"* — no; frame it as "comparable deployments have reported gains in this range" and commit to measuring the actual lift for this specific campaign rather than promising a number pulled from someone else's case study.

### Q8 — How does frequency capping interact with a bandit's exploration/exploitation logic?
**Answer:** Frequency capping is an external hard constraint (no more than N impressions per user for a given creative) applied independently of the bandit's reward-driven allocation decision — it directly addresses the frequency-driven component of fatigue rather than waiting for the reward signal to reflect it. It effectively removes an arm from eligibility for a specific user once the cap is hit, which the bandit's selection logic needs to respect (skip capped arms, don't let them silently distort the remaining arms' relative selection probabilities).
**Follow-up trap:** *"Could you achieve the same effect purely through reward decay instead of a hard frequency cap?"* — decay handles population-level average fatigue over time but doesn't guarantee any specific user isn't shown the same creative excessively; a hard per-user cap is a more direct guarantee and the two mechanisms are complementary, not substitutes.

### Q9 — Design a creative optimization system for a campaign with 6 headlines, 8 images, and 4 CTAs (192 possible combinations) and a moderate traffic budget.
**Testing:** synthesis combining factorial-cost awareness, bandit allocation, and fatigue handling.
**Answer:** Reject full-combination testing outright given the traffic math (192 arms each needing meaningful sample size). Use a component-level (or low-rank contextual) bandit learning marginal performance per headline/image/CTA, composing the top-scoring combination for serving while periodically spot-checking a sample of full combinations against component-model predictions to catch real interaction effects. Layer exponential-decay reward estimation and explicit per-user frequency capping on top to handle fatigue, and route any newly-generated creative (if creative is auto-generated) through the same quality-gate/brand-safety checks as module 10 before it's eligible to enter the bandit at all.
**Follow-up trap:** *"How would you validate the component-level model isn't systematically missing important interactions?"* — periodic full-combination spot-checks against component-model predictions, using large residuals as a signal to add specific high-value pairings as their own dedicated arms.

### Q10 — Your bandit converges on one creative within hours and almost stops exploring the rest. Is that a problem, and how do you manage the exploration budget?
**Testing:** whether the candidate recognizes exploitation starving exploration as a real failure mode and treats exploration as an explicit, budgeted cost rather than a free algorithmic byproduct.
**Answer:** Yes — early convergence usually means the bandit is exploiting noisy short-run signal, and arms killed off after a few hundred impressions never get the chance to reveal slower-burn appeal or headline-image interaction effects. Budget exploration explicitly: reserve roughly ~10-20% of traffic as a protected explore allocation (an epsilon floor or forced rotation on new/underexposed arms) independent of what current reward estimates say, and treat that spend as the standing cost of maintaining option value against fatigue and drift. Review the explore allocation's conversion drag separately from campaign ROAS so it isn't optimized away by someone reading only blended performance.
**Follow-up trap:** *"Doesn't Thompson Sampling handle exploration automatically?"* — it samples suboptimal arms probabilistically, but its explore rate collapses fast once one arm's posterior pulls ahead, so "automatic" exploration decays precisely when you still need it; without a hard traffic floor, allocation quietly approaches pure exploitation and the system stops learning about everything except the incumbent.

---

## Red flags that fail you

- Treating creative testing as a one-time fixed-duration A/B test with no ongoing allocation adjustment for high-volume, frequently-refreshing creative pools.
- Not recognizing creative fatigue as a non-stationary-reward problem that a plain bandit doesn't handle by default.
- Proposing full-combination testing/bandits without checking the combinatorial traffic cost first.
- Not knowing frequency capping and reward decay are complementary fatigue mechanisms, not interchangeable.
- Quoting a specific published lift percentage (8%, 10%) as a guaranteed outcome rather than a context-specific reported result.
- Fully automating creative generation and allocation with no reference to brand-safety/quality gating on what enters the bandit's action space.

---

## Cheat card

```
DCO vs A/B    static test: fixed split, one discrete winner decision at test end
              bandit DCO: continuous reallocation, pulls back from decaying "winner" in
                near-real time -- correct framing because creative reward is NON-STATIONARY
COMBINATORIAL 4 headlines x 5 images x 3 CTAs = 60 combos -- same L^k cost as full-factorial
              MVT (module 07). Fix: feature-level/component bandits (assumes additive
              components, misses real interactions -- same bet as fractional factorial)
BANDIT ALGOS  epsilon-greedy / UCB / Thompson Sampling -- same family as personalization
              bandits, creative variants as arms. Reported gains: ~8% acquisition lift
              (Thompson Sampling, retail banking), ~10% CTR lift vs static (retail case
              study) -- context-specific, not universal.
FATIGUE       CTR decline ~10%+, CPA rise ~15%+, frequency > ~3 in prospecting = heuristic
              flags (not universal constants). Plain bandit assumes stationary reward ->
              over-serves a fatiguing creative because its un-decayed average lags reality.
FIXES         exponential decay / sliding window on reward estimate (tracks decline),
              explicit frequency capping (hard limit, independent of reward signal),
              proactive fatigue-prediction from early engagement-curve shape (catches
              decay before lagging threshold fires)
STILL APPLIES randomization unit, power/MDE, SRM checks -- creative-specific SRM cause:
              broken image asset / truncated headline on some devices/browsers
WHEN NOT      one-off high-stakes single asset -> static test simpler/more auditable.
              full-combination bandit with large component count -> traffic wall.
              zero human creative oversight -> no mechanism to judge brand fit/compliance.
```

## Sources

- [Dynamic Creative Optimization (DCO) — Omneky](https://www.omneky.com/blog/dynamic-creative-optimization) — accessed 2026-08-02
- [Conversion-Based Dynamic-Creative-Optimization in Native Advertising](https://arxiv.org/pdf/2211.11524) — accessed 2026-08-02
- [DCO in 2026: How to Run Dynamic Creative Optimization That Actually Scales — AllAspect](https://allaspect.com/insights/dynamic-creative-optimization-dco-guide-2026/) — accessed 2026-08-02
- [Utilizing Multi-Armed Bandit Algorithms for Advertising: An In-Depth Case Study on an Online Retail Platform's Advertising Campaign](https://www.researchgate.net/publication/381525216_Utilizing_Multi-Armed_Bandit_Algorithms_for_Advertising_An_In-Depth_Case_Study_on_an_Online_Retail_Platform's_Advertising_Campaign) — accessed 2026-08-02
- [Multi-armed bandits for performance marketing — Springer Nature Link](https://link.springer.com/article/10.1007/s41060-023-00493-7) — accessed 2026-08-02
- [Customer Acquisition via Display Advertising Using Multi-Armed Bandit Experiments](https://www.researchgate.net/publication/316286718_Customer_Acquisition_via_Display_Advertising_Using_Multi-Armed_Bandit_Experiments) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
