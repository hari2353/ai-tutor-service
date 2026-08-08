# Unit Economics: CAC/LTV, Contribution Margin, Payback Period, and the Real Per-Request Cost of an AI Feature

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** T25-metrics · **Updated:** 2026-08-08
> **Module id:** `T25-unit-economics` · **Tags:** finance, critical

## The 30-second version

Unit economics answers one question: does making and keeping one customer generate more cash than it costs, and how fast do you get that cash back. CAC (customer acquisition cost) and LTV (lifetime value) combine into the LTV:CAC ratio — 3:1 is the conventional minimum, 4:1-5:1 is strong, below 2:1 signals a model that isn't capital-efficient — but the ratio hides the more operationally important number, **payback period**: how many months until a customer's cumulative contribution margin repays what it cost to acquire them, because a business can have a great LTV:CAC ratio on paper and still die from a cash-flow crunch if payback takes 18+ months and growth is funded by acquiring the next cohort before the last one paid back. For AI features specifically, engineers routinely under-cost the unit economics by pricing only the LLM API call and ignoring the three costs that often dominate it in production: retrieval/infrastructure (vector search, reranking, context assembly), evaluation (an LLM-as-judge or automated eval pass, sometimes run on every request), and human review (manual QA or escalation handling for low-confidence outputs) — a feature that looks like $0.007/request on a token-pricing spreadsheet can be $0.02-0.05/request once retrieval, eval, and review are counted, and that gap is exactly the number that turns a profitable feature into a loss-making one at scale.

## Why this gets asked

The interviewer has sat in a room where an engineer proposed an AI feature, priced it by multiplying a token count by a per-token rate, and got approval — and then watched the actual production cost come in three to five times higher once retrieval infrastructure, evaluation pipelines, and human-in-the-loop review for the cases the model got wrong were all added up. They want to know whether you cost a feature the way finance will actually bill it, before you pitch it, not after finance flags the gross margin miss in a quarterly review. At senior/staff/principal level, this is also a proxy for whether you can hold a two-sided conversation with a CFO or a VP of Product without needing a translator.

---

## Lineage: past → present → future

**What came before.** Pre-SaaS software economics were largely license-and-maintenance based: a large upfront payment, a smaller recurring maintenance fee, and unit economics that were comparatively simple because acquisition and delivery costs were both dominated by a sales team's effort and a one-time engineering build, not a recurring per-use cost. The shift to SaaS subscription models (2000s-2010s, Salesforce as the canonical early example) introduced the CAC/LTV framing the industry now takes for granted, because subscription revenue arrives in monthly slices while acquisition cost is paid entirely upfront — this mismatch is *why* payback period exists as a concept at all; it doesn't matter in a license-based world where the cash arrives immediately. David Skok's widely-cited "SaaS Metrics 2.0" writing (For Entrepreneurs, ~2010s) and subsequent venture-capital benchmarking (Bessemer's "efficient growth" frameworks, among others) formalized the ratios (3:1 LTV:CAC, payback-period targets) that became industry-standard shorthand.

**Where it stands now.** The benchmarks have shifted materially in the current environment: mid-market SaaS CAC payback drifted from roughly 15 months in 2023 to roughly 18 months in 2026, reflecting a tougher capital environment where investors reward efficiency more than pure growth than they did in the 2020-2021 zero-rate era. AI-native products have introduced a genuinely new unit-economics complication the SaaS-era framework didn't have to handle: **marginal cost per user is no longer near-zero.** Classic SaaS gross margins (70-85%+) assumed serving one more customer costs almost nothing incremental; an AI feature with meaningful per-request inference, retrieval, and (especially) human-review cost can have real, non-trivial marginal cost that scales with usage, which means "contribution margin" has to be computed per-request or per-active-user for AI features in a way it rarely needed to be for a traditional CRUD SaaS feature. The live disagreement in AI-product unit economics specifically is how to allocate genuinely variable costs (eval and human review scale with volume and, worse, with the *error rate* of the underlying model, which is itself uncertain and shifting) into a stable per-unit economics model investors and finance teams can actually plan against.

**Where it's heading.** High confidence: per-request cost instrumentation (token counts, retrieval calls, eval runs, and review escalations all tagged and billed to the specific feature/customer that triggered them) is becoming a standard finance-and-engineering joint requirement for any AI feature before it ships broadly, not an afterthought discovered after a surprising cloud bill. Moderate confidence: as foundation-model inference costs continue to fall (a well-documented multi-year trend across most model tiers), the center of gravity in AI feature cost is shifting away from raw generation cost and toward the human-review and evaluation layers, which don't benefit from the same cost curve — meaning the "real" cost of an AI feature increasingly is dominated by the parts that don't get cheaper just because the underlying model does. More speculative: outcome-based and usage-based pricing models (discussed in the AI-product module) are partly a direct response to this unit-economics reality — if marginal cost genuinely varies with usage and error rate, a flat per-seat price structurally mismatches cost, and pricing has to follow the cost structure more closely than classic SaaS ever required.

---

## Mental model

```
LTV:CAC RATIO tells you IF the unit economics work.
PAYBACK PERIOD tells you WHEN you find out, and how much cash you need to survive until then.

  month:  0    3    6    9    12   15   18   21
  CAC     ┃────────────────────────────────────▶  (paid entirely up front, month 0)
          │
  cumulative
  contribution
  margin           ╱───────────────────────────▶
                  ╱
                ╱          ◀── PAYBACK PERIOD ──▶
              ╱             (cumulative margin
            ╱                crosses CAC line)
          ╱
  ───────┴──────────────────────────────────────
         a company can have LTV:CAC = 5:1 (great ratio) and STILL run out
         of cash if payback takes 24 months and it's acquiring cohort N+1
         before cohort N has paid back -- the ratio is a health signal,
         payback period is the cash-flow constraint that actually kills you
```

---

## How it actually works

### CAC, LTV, and the ratio that actually gets checked in a boardroom

**CAC (Customer Acquisition Cost)** = total sales + marketing spend over a period, divided by new customers acquired in that period. The most common real-world mistake is under-scoping the numerator — CAC should include fully-loaded sales/marketing headcount cost, not just ad spend, and for AI products specifically, any cost of running pilots, proofs-of-concept, or "try before you buy" usage that's given away during the sales cycle (a meaningfully larger category for AI products than for traditional SaaS, because buyers reasonably want to see the AI work on their own data before committing).

**LTV (Lifetime Value)**, in its simplest useful form: `LTV = ARPA × Gross Margin % × Average Customer Lifetime (or 1/churn rate)`. The two most common ways this gets inflated (deliberately or through wishful modeling) in a pitch: using **gross** revenue instead of **gross margin**-adjusted revenue (ignoring the cost of serving the customer entirely), and using an optimistic churn assumption not yet supported by actual cohort data.

**The ratio benchmarks** (current, per multiple 2026 SaaS benchmarking sources): **3:1 is the conventional minimum** viable ratio; **4:1-5:1 is considered strong**, particularly for enterprise/post-Series-B companies; **below 2:1 signals a business model that isn't yet capital-efficient**, meaning growth is likely being subsidized by capital rather than by the unit economics themselves — survivable for a period with investor backing, not survivable indefinitely.

### Payback period: the number that actually determines survival

`CAC Payback Period (months) = CAC / (Monthly Recurring Revenue per customer × Gross Margin %)` — the number of months of contribution margin it takes to recoup the acquisition cost. Current benchmarks: **healthy B2B SaaS reaches CAC payback within 6-12 months; elite performers reach it in 80-90 days; mid-market SaaS payback has drifted from roughly 15 months (2023) to roughly 18 months (2026)**, reflecting a broadly tougher capital environment; **companies with payback periods longer than 18 months usually face real funding pressure and struggling unit economics**.

**Why payback period matters more operationally than the LTV:CAC ratio in a resourcing conversation:** LTV is a projection over a customer's entire (uncertain, multi-year) lifetime; payback period is a much more falsifiable, near-term number, and it directly determines how much cash a growing company needs on hand to keep acquiring customers before the flywheel becomes self-funding. A company growing fast with an 18-month payback needs to fund roughly a year and a half of acquisition spend across its entire growing customer base before that spend becomes self-sustaining from contribution margin — this is a cash and runway question, not just a unit-economics-health question, and it's the number a Principal engineer proposing a resource-intensive AI feature should be able to reason about, because a feature that worsens payback period (by adding cost that eats contribution margin) has a real, calculable cost to the business's growth capacity, independent of whether the feature is "good."

### Contribution margin: the lever hiding in plain sight

`Contribution Margin = Revenue − Variable Costs` (per unit, or as a percentage of revenue). For a SaaS business, this is close to gross margin — the cost of goods sold is mostly hosting/infrastructure and, for AI features, inference/retrieval/review cost. The mechanically important fact: **contribution margin improvements compound directly into payback period improvements**, because payback period's denominator is monthly revenue times margin percentage. A documented benchmark: moving gross margin from 72% to 78% shortens payback by roughly 4.3 months at typical SaaS unit economics; at $500 ARPU, a 72% margin produces $360/month contribution versus $390/month at 78% margin — an 8.3% contribution lift that compresses payback proportionally. This is the exact mechanism by which an AI feature's *cost efficiency* (not just its capability) is a direct lever on the business's growth capacity — a feature that's technically impressive but drags margin down measurably worsens the company's ability to fund its own growth, independent of whether customers like the feature.

### The real per-request cost of an AI feature — worked example

The single most common engineering mistake in AI-feature cost estimation is pricing only the generation call and treating retrieval, evaluation, and human review as either free or "someone else's line item." Walk through a realistic RAG-based support-copilot feature, per request, at current (August 2026) pricing:

**1. Retrieval.** Query embedding is genuinely near-free at scale (roughly $3.25 per 500K queries embedded with a mid-tier embedding model at ~50 tokens/query) — this is the part engineers correctly assume is cheap. Vector search infrastructure is where the real, easy-to-miss cost sits: a modestly-scaled system (low millions of vectors, a few thousand queries/day) runs **roughly $100-1,500/month in infrastructure** depending on vector DB choice and scale, which amortized per-request is small individually but is a real fixed cost line that a pure per-token estimate omits entirely. Add a reranking pass (a second-pass cross-encoder model reordering retrieved candidates before generation, standard practice for production RAG quality) — a modest additional cost per request, often comparable in order of magnitude to the embedding cost, rarely zero.

**2. Generation.** At current Claude Sonnet 5 pricing (~$2/M input tokens, ~$10/M output tokens as of August 2026, subject to change on the provider's own schedule), a request with ~2,000 input tokens (system prompt, retrieved context, conversation history) and ~300 output tokens costs: input `2,000/1,000,000 × $2 = $0.004`, output `300/1,000,000 × $10 = $0.003`, **generation subtotal ≈ $0.007/request**. This is the number most cost estimates stop at.

**3. Evaluation.** If every response is scored by an LLM-as-judge pass before being shown to the user (common for high-stakes support content), that's roughly another generation-sized call — call it **$0.003-0.006/request** if run on 100% of traffic. Most production systems sample rather than eval every request (e.g., 10-20% sampled for ongoing quality monitoring, 100% for a new feature's first weeks), which amortizes this to **roughly $0.0005-0.001/request** at a 10-15% sampling rate — but note that a genuinely new or high-risk feature often *should* run eval on 100% of traffic initially, and that decision alone can materially change the unit economics during the rollout period.

**4. Human review.** This is the cost category most consistently missing from engineering estimates and most consistently dominant once included. If 5% of requests are escalated to human review (low-confidence outputs, flagged content, a customer explicitly requesting a human), and a review takes roughly 1-2 minutes at a loaded cost of **$18-24/hour for a vetted reviewer** (current market rate for quality human-review/RLHF-adjacent work), each review costs roughly **$0.30-0.80**, amortized across *all* requests (not just the reviewed ones) at a 5% escalation rate that's **$0.015-0.04/request** — frequently larger than the generation cost itself.

**Total, worked:** retrieval (~$0.001-0.003 amortized) + generation (~$0.007) + eval (~$0.0005-0.001 sampled) + human review (~$0.015-0.04 at 5% escalation) ≈ **$0.024-0.051/request**, roughly **3.5-7x the raw generation-only estimate of $0.007** that a token-pricing-only spreadsheet would have produced. At meaningful volume (say, 500,000 requests/month), that's the difference between a feature costing roughly $3,500/month (generation only, the number that got approved) and one actually costing $12,000-25,500/month (fully loaded) — a gap large enough to flip a feature's contribution margin from healthy to negative, and exactly the kind of miss that shows up as a surprise in a quarterly finance review instead of being caught in the original pitch.

**The lever that actually matters operationally:** human review cost scales with the model's error/uncertainty rate, not with a fixed unit cost — which means the single highest-leverage way to improve this feature's unit economics is usually reducing the escalation rate (better confidence calibration, better retrieval quality reducing the cases that need human judgment) rather than negotiating a cheaper per-token rate on the generation call, even though the generation call is the line item engineers instinctively focus on.

---

## Build it from scratch

```python
# untested sketch — per-request AI feature cost model, the kind of spreadsheet-as-code
# a Principal engineer should be able to produce before pitching an AI feature

def ai_feature_unit_cost(
    input_tokens: int = 2000,
    output_tokens: int = 300,
    input_price_per_m: float = 2.0,      # $/M tokens, generation model input
    output_price_per_m: float = 10.0,    # $/M tokens, generation model output
    retrieval_infra_monthly: float = 800.0,
    monthly_requests: int = 500_000,
    eval_sample_rate: float = 0.15,      # fraction of requests scored by LLM-as-judge
    eval_cost_per_call: float = 0.005,   # roughly one generation-sized call
    human_review_rate: float = 0.05,     # fraction of requests escalated to a human
    human_review_minutes: float = 1.5,
    human_review_hourly_rate: float = 22.0,
) -> dict:
    generation_cost = (input_tokens / 1_000_000 * input_price_per_m
                        + output_tokens / 1_000_000 * output_price_per_m)
    retrieval_cost = retrieval_infra_monthly / monthly_requests
    eval_cost = eval_sample_rate * eval_cost_per_call
    review_cost_per_reviewed = (human_review_minutes / 60) * human_review_hourly_rate
    review_cost = human_review_rate * review_cost_per_reviewed

    total = generation_cost + retrieval_cost + eval_cost + review_cost
    return {
        "generation_only": round(generation_cost, 5),
        "retrieval_amortized": round(retrieval_cost, 5),
        "eval_amortized": round(eval_cost, 5),
        "human_review_amortized": round(review_cost, 5),
        "total_per_request": round(total, 5),
        "multiple_vs_generation_only": round(total / generation_cost, 2),
    }

# ai_feature_unit_cost() -> total ~= $0.03/request, ~4.3x the generation-only estimate
# most engineering cost pitches implicitly make
```

```python
# untested sketch — payback period and the contribution-margin lever
def cac_payback_months(cac: float, monthly_revenue_per_customer: float, gross_margin_pct: float) -> float:
    monthly_contribution = monthly_revenue_per_customer * gross_margin_pct
    return cac / monthly_contribution

# payback at 72% margin vs 78% margin, $500 ARPU, $3000 CAC:
# cac_payback_months(3000, 500, 0.72) -> 8.33 months
# cac_payback_months(3000, 500, 0.78) -> 7.69 months
# a 6-point margin improvement (e.g. from cutting AI feature cost) shortens
# payback by roughly 2/3 of a month per $500 of ARPU at this CAC -- small
# per-customer, real in aggregate across a growing customer base
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| An AI feature's actual cloud/API bill comes in 3-5x the pitched estimate | Estimate only priced the generation call, omitted retrieval infra, eval, and human review | Require a per-request cost model covering all four layers (retrieval, generation, eval, human review) before a feature is approved, not just a token-cost estimate |
| A feature looks profitable on paper but margin is eroding at scale | Human review/escalation rate wasn't modeled as scaling with the model's real-world error rate, which was optimistic in the original estimate | Instrument and monitor actual escalation rate in production from week one; re-forecast unit economics against observed rate, not the launch-time assumption |
| LTV:CAC ratio looks strong (5:1) but the company is burning cash faster than expected | Payback period wasn't checked separately — a good ratio can coexist with a long, cash-intensive payback period | Report payback period alongside the ratio in every unit-economics review; treat it as the operative cash-planning number |
| CAC is quietly understated in a pitch | Numerator excludes fully-loaded team cost, or excludes AI-specific pilot/POC giveaway cost common in AI sales cycles | Include fully-loaded sales/marketing cost and any pre-purchase usage given away during evaluation in the CAC calculation |
| Contribution margin on an AI feature declines as usage grows, contrary to typical SaaS scaling intuition | Marginal cost per request isn't near-zero the way a traditional SaaS feature's is — retrieval, eval, and especially human review scale with volume | Model AI feature margin per-request explicitly, don't assume traditional SaaS's near-zero-marginal-cost intuition transfers |

---

## Tradeoffs & when NOT to use it

- **Don't over-engineer a full unit-economics model for a low-volume, experimental AI feature still in validation.** A rough back-of-envelope estimate (generation cost, plus a stated assumption for eval/review rate) is proportionate for a pilot; save the detailed per-request model for a feature about to scale to real volume.
- **LTV projections beyond 24-36 months are usually more fiction than forecast** for any reasonably young product or company — treat long-horizon LTV numbers with real skepticism, especially in a pitch deck; anchor decisions more heavily on payback period and near-term cohort data, which are far more falsifiable.
- **Contribution margin optimization has diminishing returns and real tradeoffs against quality** — cutting human review rate to improve margin without a corresponding improvement in model confidence calibration just moves errors from being caught to being shipped to customers, trading a margin improvement for a quality/trust cost that doesn't show up in the same spreadsheet.
- **CAC payback benchmarks vary enormously by go-to-market motion** — self-serve/PLG (current benchmark roughly $420 CAC), mid-market/blended (roughly $1,680), and enterprise sales-led (roughly $9,400) are not comparable numbers; don't benchmark an enterprise-sales AI feature's economics against a PLG company's payback period, the underlying cost structures are fundamentally different.
- **Don't reflexively minimize human review to cut cost on a high-stakes AI feature** (medical, legal, financial, safety-critical) — the unit-economics case for reducing review rate has to be weighed explicitly against the cost of a serious error slipping through, which is often not well captured by a pure cost-per-request model at all.

---

## Interview questions

### Q1 — Explain LTV:CAC ratio and payback period, and why a company can have a strong ratio and still be in financial trouble.
**Answer:** LTV:CAC (3:1 minimum, 4:1-5:1 strong) measures whether the unit economics work over a customer's full lifetime. Payback period measures how many months it takes cumulative contribution margin to recoup the acquisition cost — a near-term, cash-flow-relevant number. A company can have a great ratio (high projected lifetime value relative to acquisition cost) and still run out of cash if payback takes 18-24 months and it's acquiring the next cohort before the last one has paid back, because the ratio is a long-run health signal while payback period is the actual cash-flow constraint.
**Follow-up trap:** *"Given a fixed amount of cash, would you rather improve the ratio or shorten the payback period?"* — shorten payback, if forced to choose, because it directly determines how much runway is needed to keep growing without additional capital; a better ratio realized only over years doesn't solve a near-term cash constraint.

### Q2 — Walk through the true per-request cost of a RAG-based AI feature, beyond just the LLM call.
**Answer:** Retrieval (embedding — near-free at scale; vector search infrastructure — real fixed cost, roughly $100-1,500/month at modest scale; reranking — a real per-request add-on), generation (the token-priced call most estimates stop at), evaluation (an LLM-as-judge pass, often sampled rather than run on 100% of traffic), and human review (escalated low-confidence cases, typically the largest and most consistently omitted category). A realistic worked total can run 3.5-7x the generation-only estimate.
**Follow-up trap:** *"Which of these four scales worst as the model's error rate rises?"* — human review, because its cost is driven by escalation rate, not a fixed per-unit price — a model with a higher-than-expected error rate doesn't just produce worse outputs, it directly inflates the feature's unit cost through the review layer, which is a distinct and often larger effect than the generation cost itself.

### Q3 — Your team pitched an AI feature at $0.007/request (generation cost only) and it approved. Actual production cost comes in at $0.03/request. Walk me through how you'd diagnose and communicate this.
**Answer:** Diagnose by breaking the actual bill into the same four categories (retrieval, generation, eval, review) and comparing each against the original estimate — the gap is almost certainly concentrated in retrieval infrastructure and human review, both commonly omitted from a token-only estimate. Communicate it as a specific, itemized correction (not a vague "costs were higher than expected"), and propose the highest-leverage fix, which is usually reducing the human-review escalation rate rather than negotiating the generation price, since review cost is typically the largest previously-unmodeled line.
**Follow-up trap:** *"Finance asks if this makes the feature no longer worth shipping. How do you answer?"* — recompute contribution margin and payback impact with the corrected cost, and give a real answer either way — sometimes the corrected number still clears the bar, sometimes it doesn't, and the credible answer shows the recomputation rather than defending the original pitch or immediately conceding.

### Q4 — Why does the "near-zero marginal cost" assumption that underlies classic SaaS gross margins not transfer cleanly to AI features?
**Answer:** Traditional SaaS features cost almost nothing incremental to serve one more customer (mostly fixed infrastructure, amortized). AI features have real, non-trivial marginal cost per request — inference tokens, retrieval calls, and especially human review scale with usage (and with the model's error rate) rather than approaching zero at scale. This means AI feature margin has to be modeled per-request explicitly, and margin can even *decline* as usage grows if review/escalation rates don't improve proportionally, the opposite of the intuition a traditional SaaS engineer would bring in.
**Follow-up trap:** *"Does this mean AI features can never reach SaaS-like margins?"* — no, but it means margin improvement has to come from a different lever than traditional SaaS (which mostly just needed more customers on the same fixed infra) — for AI features, margin improvement mostly comes from reducing per-unit cost drivers directly: better confidence calibration to cut review rate, cheaper/faster models for easy cases via routing, and retrieval efficiency, not simply "scale and margin improves on its own."

### Q5 — A stakeholder wants to cut the human-review escalation rate on a support AI copilot from 5% to 1% to improve margin. How do you evaluate this?
**Answer:** Check what's actually driving the 5% rate — if it's a well-calibrated confidence threshold catching genuinely uncertain or high-risk cases, cutting it to 1% doesn't reduce uncertainty, it just ships more of those uncertain cases directly to customers unreviewed, trading a margin improvement for a quality/trust cost that likely shows up later as increased support tickets, churn, or reputational damage — costs that don't appear in the same per-request spreadsheet. The right question isn't "can we cut the rate" but "can we reduce the *number of genuinely uncertain cases* through better retrieval or model quality," which cuts the rate without cutting the safety margin.
**Follow-up trap:** *"How would you actually test whether 1% is safe before committing to it?"* — a staged rollout with close monitoring of downstream quality signals (customer-reported errors, reopened tickets, CSAT) compared against a holdback group still reviewed at 5% — treat it as an experiment with a guardrail (see the experimentation module), not a one-way cost-cutting decision made from the spreadsheet alone.

### Q6 — Explain contribution margin and derive why a 6-point margin improvement matters more than it sounds like it should.
**Answer:** Contribution margin = revenue minus variable cost, and it's the direct multiplier in the payback-period denominator (`CAC / (monthly revenue × margin %)`) — improving margin doesn't just add a few points to a percentage, it directly compresses payback period, which compounds across every customer acquired going forward, not just retroactively. A documented benchmark: moving margin from 72% to 78% shortens payback by roughly 4.3 months at typical SaaS unit economics — a seemingly modest percentage-point change with a real, multi-month cash-flow effect at scale.
**Follow-up trap:** *"Where would you look first to find a 6-point margin improvement on an AI feature specifically?"* — human review rate and retrieval efficiency before generation cost, because generation cost is usually the smallest of the three real cost categories once retrieval and review are properly counted, and it's also the one most engineers already optimize reflexively (model choice, prompt length) while under-investing in the larger review-cost lever.

### Q7 — How do CAC benchmarks differ across go-to-market motions, and why does this matter when comparing an AI feature's economics across product lines?
**Answer:** Current benchmarks: self-serve/PLG roughly $420 CAC, mid-market/blended roughly $1,680, enterprise sales-led roughly $9,400 — these reflect fundamentally different cost structures (largely automated acquisition vs. a human sales team), not just different scale of the same motion. An AI feature's unit economics evaluated against a PLG-style payback benchmark would look artificially unhealthy if the actual go-to-market motion is enterprise sales-led, and vice versa — the comparison has to be motion-matched, not treated as one universal benchmark.
**Follow-up trap:** *"Your AI feature is sold as an add-on across both PLG and enterprise segments. How do you evaluate its unit economics?"* — separately, per segment, with segment-appropriate CAC and payback benchmarks — a blended number across two structurally different motions obscures whether the feature is healthy in one segment and unhealthy in the other, which is exactly the kind of averaging error that hides a real problem.

### Q8 — Why should evaluation (LLM-as-judge) cost be sampled rather than run on 100% of production traffic, and when is 100% actually the right call?
**Answer:** Running eval on every request roughly doubles per-request generation-layer cost (a second, similarly-sized call), which is rarely justified once a feature's quality has stabilized — sampling at 10-20% for ongoing monitoring captures the same statistical signal about quality trends at a fraction of the cost. 100% eval is the right call temporarily: during a new feature's initial rollout (before you trust the quality signal), after a significant model or prompt change (to re-establish the quality baseline), or for a genuinely high-stakes surface where even a small undetected quality regression is unacceptable.
**Follow-up trap:** *"How do you decide when to step down from 100% to sampled eval?"* — a pre-committed criterion (e.g., quality metrics stable within a defined band for N consecutive days/weeks), not an ad hoc judgment call made under cost pressure — the same discipline as a pre-committed kill threshold in the discovery module, applied to a cost-vs-confidence tradeoff instead of a product bet.

### Q9 — A CFO asks you to justify an AI feature's unit economics in a way they can actually act on. What do you bring to that conversation?
**Answer:** A per-request fully-loaded cost breakdown (retrieval, generation, eval, review, not just generation), the resulting contribution margin at current and projected volume, the payback-period impact if this feature is bundled into pricing versus sold separately, and an explicit sensitivity analysis showing how the economics change if the human-review escalation rate moves up or down — because that's the input most likely to shift and the one least under direct engineering control on day one.
**Follow-up trap:** *"The CFO asks what happens to the economics if usage grows 10x. What's your answer?"* — retrieval infrastructure cost per request likely improves with scale (fixed costs amortize further), but human review cost does not — it scales roughly linearly with request volume at a constant escalation rate, so a 10x usage increase without a corresponding improvement in model confidence/calibration produces close to a 10x increase in the largest cost category, not the margin-improving effect a naive "scale helps SaaS economics" intuition would predict.

### Q10 — Design the unit-economics section of a one-pager pitching a new AI feature, using this module's frameworks.
**Testing:** synthesis — can you assemble a real business-facing artifact, not just recite definitions.
**Answer:** Fully-loaded per-request cost model (all four layers, with explicit assumptions for eval sample rate and human-review escalation rate, both flagged as the most uncertain and highest-leverage inputs); resulting contribution margin at a stated pricing assumption; payback-period impact if this feature affects CAC (does it help close deals faster, lowering CAC) or affects churn/expansion (does it lift LTV); and a sensitivity table showing margin and payback under a pessimistic (higher escalation rate, higher token usage) and optimistic case, not a single point estimate.
**Follow-up trap:** *"Your optimistic case assumes a 2% human-review rate you have no data for yet. How does that affect the pitch's credibility?"* — flag it explicitly as an unvalidated assumption with a plan to validate it in a limited pilot before full-scale commitment, rather than presenting a single confident number — this mirrors the "give a range with stated confidence" discipline from the product-thinking module, applied to a cost estimate instead of an impact estimate.

---

## Red flags that fail you

- Pricing an AI feature by generation/token cost alone, with no mention of retrieval, eval, or human review cost.
- Citing LTV:CAC ratio without mentioning payback period, or treating them as interchangeable.
- Using gross revenue instead of gross-margin-adjusted revenue in an LTV calculation.
- Assuming AI feature margin improves with scale the same way traditional SaaS margin does, with no acknowledgment of human-review cost scaling with volume.
- Comparing CAC/payback numbers across fundamentally different go-to-market motions (PLG vs. enterprise) as if they're the same benchmark.
- Proposing to cut human review rate purely for margin, with no plan to validate that quality doesn't degrade.

---

## Cheat card

```
CAC             fully-loaded sales+marketing spend / new customers acquired
                (include AI-specific pilot/POC giveaway cost -- often missed)
LTV             ARPA x Gross Margin % x avg customer lifetime (1/churn)
                common inflation trap: using gross revenue, not margin-adjusted
LTV:CAC RATIO   3:1 minimum · 4:1-5:1 strong · <2:1 = not capital-efficient
PAYBACK PERIOD  CAC / (monthly revenue/customer x gross margin %)
                healthy: 6-12mo · elite: 80-90 days · mid-market drifted
                15mo(2023) -> 18mo(2026) · >18mo = real funding pressure
                THE CASH-FLOW NUMBER -- a good ratio can still coexist with
                a payback period long enough to run the company out of cash
CONTRIB MARGIN  revenue - variable cost; directly compresses payback (denominator)
                72%->78% margin shortens payback ~4.3mo at typical SaaS economics
CAC BY MOTION   PLG/self-serve ~$420 · mid-market/blended ~$1,680 ·
                enterprise sales-led ~$9,400 -- NOT comparable across motions

AI FEATURE COST (per request, worked example, Aug 2026 pricing)
  retrieval    embed ~free at scale; vector infra ~$100-1,500/mo amortized;
               + reranking pass, real but modest per-request add-on
  generation   ~2000 in / 300 out tokens @ ~$2/$10 per M (Sonnet-tier) = ~$0.007
               <- most estimates STOP here
  eval         LLM-as-judge, ~generation-sized call, sample 10-20% not 100%
               once stable -> ~$0.0005-0.001/req amortized
  human review LARGEST, MOST OFTEN OMITTED: 5% escalation x $18-24/hr x
               1-2min review = ~$0.015-0.04/req amortized across ALL requests
  TOTAL        ~$0.024-0.051/req = 3.5-7x the generation-only estimate
  HIGHEST-LEVERAGE FIX: cut escalation rate (better calibration/retrieval),
    NOT negotiate token price -- review cost scales w/ error rate, not volume
```

## Sources

- [SaaS Unit Economics 2026: CAC, LTV & Payback Reference — Digital Applied](https://www.digitalapplied.com/blog/saas-unit-economics-2026-cac-ltv-payback-reference) — accessed 2026-08-08
- [LTV:CAC Ratio Benchmarks 2026 — Foundry CRO](https://foundrycro.com/blog/ltv-cac-ratio-benchmarks-2026/) — accessed 2026-08-08
- [CAC Payback Period Benchmarks 2026 — Foundry CRO](https://foundrycro.com/blog/cac-payback-benchmarks-2026/) — accessed 2026-08-08
- [The Hidden Cost of Every RAG Query — Sivaro](https://sivaro.in/articles/the-hidden-cost-of-every-rag-query-what-vector-search/) — accessed 2026-08-08
- [RAG in Production: Cost Surprises After Sprint 3 — Kalvium Labs](https://www.kalviumlabs.ai/blog/rag-in-production-what-it-actually-costs-after-sprint-3/) — accessed 2026-08-08
- [Complete Guide to RLHF Human Annotation — Annotera](https://www.annotera.ai/blog/rlhf-human-annotation-guide/) — accessed 2026-08-08
- [LLM API Pricing (August 2026) — BenchLM.ai](https://benchlm.ai/anthropic/api-pricing) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
