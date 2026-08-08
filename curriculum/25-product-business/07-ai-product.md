# Pricing and Positioning AI Products, and Why Most AI Features Never Ship or Fail After Launch

> **Track:** T25 Product Thinking & Business (MBA) · **Time:** 2h · **Prereqs:** T25-unit-economics · **Updated:** 2026-08-08
> **Module id:** `T25-ai-product` · **Tags:** product, critical

## The 30-second version

AI product pricing is converging on three models — per-seat, usage-based, and outcome-based — and the industry is actively moving away from pure per-seat pricing specifically because AI inverts the assumption that made per-seat work: seat-based pricing assumes value scales with headcount, but a genuinely good AI agent reduces the number of humans needed to do the work, which means a vendor on a pure seat model is financially rewarded for their own product under-delivering. Usage-based pricing is now the default starting point (roughly 85% of SaaS companies use some form of it), and outcome-based pricing — charging per resolved ticket, per successful conversation, per completed task — is becoming the dominant model specifically for AI agents because it's the only structure that aligns vendor incentive with the thing the AI is actually supposed to deliver; most successful vendors now combine a base platform fee with variable usage or outcome charges rather than picking one model exclusively. Separately and more soberly: the majority of AI features that get built never ship, and a majority of the ones that do ship fail to deliver measurable value — not primarily because the models are bad, but because success criteria were never defined before the project started, and nobody checked the metric after launch. The single highest-leverage practice covered in this module, and the one most consistently skipped, is defining a quantified success metric before writing code and actually re-checking it after shipping — teams that do this see roughly 4-5x the success rate of teams that don't.

## Why this gets asked

The interviewer has either sat through an AI feature's pricing meeting that went in circles because nobody could agree whether to charge per seat or per API call, or has been the engineer who built something technically excellent that got quietly killed six months post-launch because nobody had defined what "working" meant and nobody was checking. They want to know whether you can reason about AI economics from the vendor's side (what pricing model actually captures the value you're creating, and what it does to your own margin given the unit-economics reality from the previous module) and whether you build in the accountability loop — a defined metric, checked post-launch — that the data shows most AI projects skip entirely.

---

## Lineage: past → present → future

**What came before.** Early SaaS pricing (2000s-2010s) converged heavily on per-seat/per-user licensing because it mapped cleanly onto the dominant mental model of software as a tool one human uses — Salesforce, Workday, and most of the first generation of enterprise SaaS priced this way, and it worked because value genuinely did scale roughly with headcount for that generation of tools. Usage-based pricing grew steadily as an alternative through the 2010s (infrastructure/API-first companies like AWS, Twilio, and Stripe pioneered pay-for-what-you-use at scale), but remained a minority pattern relative to per-seat until quite recently — usage-based pricing adoption grew from roughly 30% of SaaS companies in 2019 to roughly 85% by the mid-2020s, a genuinely dramatic shift, driven significantly by AI products where "how many people have a login" stopped being a meaningful proxy for value delivered.

**Where it stands now.** The current (2026) picture, per multiple industry pricing surveys: pure per-seat pricing has fallen from roughly 21% to roughly 15% of SaaS companies year-over-year, most vendors are moving to *hybrid* models (a base seat or platform fee plus usage or outcome-based charges on top) rather than abandoning seats entirely, and outcome-based pricing — Salesforce Agentforce charging per conversation, Intercom's Fin charging per successfully resolved support ticket are commonly cited real examples — is specifically associated with AI agents rather than traditional SaaS features, because it's the only model where the vendor only gets paid when the AI actually did the job. A 2026 buyer survey found 43% of buyers now prefer consumption-based pricing and 27% favor outcome-based, while seat-only vendors are increasingly disqualified from AI-product deals before they even reach a demo — buyers have absorbed the "seat pricing rewards under-delivery" argument and are actively selecting against it. On the failure-rate side: MIT Sloan research (2025) found 95% of organizations see no measurable P&L return from their generative AI pilots, with only around 5% capturing value at scale; separately, 61% of enterprise AI projects were approved on a projected ROI that was never actually measured after launch — the project shipped, and nobody checked whether it worked, which is a process failure, not a model-capability failure.

**Where it's heading.** High confidence: hybrid pricing (a base platform fee plus usage/outcome components) continues consolidating as the majority pattern for AI products specifically, because pure usage-based pricing creates unpredictable bills that make enterprise procurement uncomfortable, while pure outcome-based pricing requires an unambiguous, disputable-free definition of "outcome" that many AI use cases genuinely don't have yet — the hybrid model splits the difference and is what most successful AI vendors have converged on. Moderate confidence: the "success metric defined before building, checked after shipping" discipline is likely to become more procedurally enforced (built into project approval templates, tied to budget release gates) specifically because the 2025-2026 data on AI project failure rates is now widely enough cited internally at large enterprises that "we didn't define success criteria" is becoming an unacceptable answer in a post-mortem, not just a bad practice. More speculative: as agentic AI systems increasingly chain multiple actions together (not just answer one question), outcome-based pricing may need to evolve toward *partial-credit* or *multi-step* outcome definitions (charging for progress toward a goal, not just binary success), which is an open pricing-design problem without settled industry practice yet.

---

## Mental model

```
PRICING MODEL              WHO BEARS THE RISK OF AI QUALITY?          COMMON FAILURE MODE
─────────────              ──────────────────────────────────         ───────────────────
PER-SEAT                   Customer bears it entirely --              vendor is paid the
                            pays the same whether the AI               same regardless of
                            works great or barely works                whether the AI
                                                                        actually delivers
                                                                        value -- misaligned
                                                                        incentive

USAGE-BASED                Shared, imperfectly --                     customer's bill grows
                            customer pays more for more                even on FAILED or
                            usage, but usage != value                  low-value interactions
                            (a bad answer still                        (a chatbot that needs
                            consumes tokens)                           5 retries costs 5x,
                                                                        delivers 1x value)

OUTCOME-BASED               Vendor bears the most --                  requires an
                            only paid when the defined                 unambiguous, hard-
                            outcome actually happens                   to-dispute definition
                            (ticket resolved, task                     of "outcome" -- often
                            completed)                                 the hardest part to
                                                                        design, not the
                                                                        pricing itself

HYBRID (base + usage/outcome)  Split -- base covers platform          most common in
                                cost/predictability, variable          practice; the design
                                component aligns incentive             problem shifts to HOW
                                on the marginal unit                   MUCH of the price is
                                                                        variable vs. fixed
```

---

## How it actually works

### Per-seat pricing and why it specifically breaks for AI agents

Per-seat pricing's foundational assumption — one human uses one license, value grows with headcount — inverts under AI agents in a way it never did for traditional software. A traditional SaaS tool (a CRM, a project tracker) genuinely does need more seats as a team grows, and the vendor's incentive (sell more seats) aligns reasonably well with the customer's growth. An AI agent that automates a task a human used to do has the opposite relationship to headcount: the better the agent performs, the *fewer* human seats the customer needs — which means a vendor pricing that agent per seat is financially rewarded when their own product under-delivers (the customer keeps more human seats, and pays for more of them, precisely because the AI isn't good enough to replace the work). This is not a hypothetical concern; it's the specific, named reason per-seat pricing's share of SaaS pricing models has been declining, and why usage varies so much within a seat tier for AI tools specifically — usage can vary 20x within the same nominal plan, because a "seat" doesn't correspond to a consistent unit of value the way it did for a tool with one human doing one predictable job.

### Usage-based pricing: the default starting point, and its own alignment gap

Usage-based pricing (charge per token, per API call, per query, per minute) ties revenue more directly to actual consumption, and it's now the default starting point for most AI products — the adoption curve (roughly 30% of SaaS companies in 2019 to roughly 85% using some form of it by the mid-2020s) reflects both AI-driven demand and the broader maturation of usage-metering infrastructure that makes it operationally easier to bill this way than it used to be. But usage-based pricing has its own, less-discussed alignment gap: **usage is not the same as value delivered.** A poorly-performing AI assistant that needs five retries to answer a question correctly generates five times the usage-based revenue of one that answers correctly on the first try, for delivering less value to the customer, not more — this is a real, structural misalignment that usage-based pricing alone doesn't solve, and it's part of why the industry has been pushing further, toward outcome-based models, specifically for AI products where this gap is most visible and most costly to the customer.

### Outcome-based pricing: the strongest alignment, the hardest design problem

Outcome-based pricing charges for the thing the customer actually wanted — a resolved support ticket (Intercom's Fin), a completed conversation that achieved its purpose (Salesforce Agentforce's per-conversation charge) — and it's becoming the dominant model specifically for AI agents because it's the only structure where the vendor's revenue is directly tied to the AI doing its job, not merely attempting it. The design difficulty is real and specific: **"outcome" has to be defined unambiguously and in a way both parties can verify without ongoing dispute.** "Resolved ticket" needs a hard, auditable definition (did the customer confirm resolution, did the ticket stay closed for N days without reopening, was there a follow-up escalation) — a vague or gameable definition of outcome reintroduces exactly the Goodhart's Law risk covered in the metrics module, just at the pricing layer: if "resolved" is defined loosely, a vendor (or the AI system itself, if it's optimizing against this metric) has a direct financial incentive to close tickets that aren't actually resolved, which is a more dangerous version of the support-ticket-gaming example from the metrics module because now it's the *pricing contract itself* creating the incentive, not just an internal KPI.

**Practical implementation pattern:** most outcome-based AI pricing in production pairs the outcome charge with a verification mechanism that's harder to game than a simple status flag — a reopened-ticket clawback (if a "resolved" ticket reopens within N days, the outcome charge is reversed or credited), a customer confirmation step, or a downstream metric check (did the customer's account show reduced support volume in the following period) — precisely because a naive "AI marks it resolved, customer gets billed" design has the exact gaming vulnerability the metrics module warns about.

### Hybrid pricing: the actual majority pattern

Hybrid pricing — a base platform/subscription fee combined with usage and/or outcome-based charges on top — is used by a substantial and growing share of SaaS companies and is the pattern most successful AI vendors have actually converged on, for a structural reason beyond just "splitting the difference": pure usage-based pricing produces unpredictable bills that make enterprise budget owners uncomfortable (a procurement team wants to know roughly what next quarter costs, not find out after the invoice arrives), while pure outcome-based pricing requires a verifiable outcome definition many AI use cases genuinely don't have yet, and it also puts 100% of the demand-volatility risk on the vendor's revenue, which most vendors can't sustain as a sole pricing model at meaningful scale. The base fee covers platform access and predictability for both sides; the variable component (usage or outcome) captures the value/incentive-alignment benefit without pushing all the risk to one party. Stripe's own analysis of its customer base found hybrid pricing associated with meaningfully higher median growth than either pure subscription or pure usage-based pricing alone — a genuinely useful data point when a stakeholder pushes for a single clean pricing model out of a preference for simplicity.

### Positioning: pricing model as a signal, not just a mechanism

The pricing model a company chooses is itself a positioning statement customers read, whether or not that's intended. Per-seat pricing signals "this is a tool a human uses," usage-based signals "this is infrastructure you consume," and outcome-based signals "we're confident enough in what this does that we'll only get paid when it actually does it" — the last of these is a genuine competitive differentiator in a market where buyers have become skeptical of AI claims generally (a direct consequence of the failure-rate data discussed below becoming widely known), and vendors who can credibly offer outcome-based pricing are using it explicitly as a trust signal in sales conversations, not just a revenue mechanism.

### Why most AI features never ship or fail after launch

The data here is sobering and worth having exactly right, because it's easy to either overstate it into "AI doesn't work" (wrong — the pattern is a process failure, not a capability failure) or understate it into a footnote (also wrong — this is the single most important thing to internalize before pitching any AI feature):

- **Between 60% and 90% of AI projects are at risk of failure**, where failure is defined broadly as abandonment before deployment, failure to deliver measurable business value, or outright cancellation — a failure rate roughly twice that of regular (non-AI) IT projects.
- **95% of organizations see no measurable P&L return from their generative AI pilots**, per 2025 MIT Sloan research; only around 5% capture value at scale.
- **61% of enterprise AI projects were approved on a projected ROI that was never actually measured after launch** — the project shipped, and nobody checked whether the projected value materialized. This is not a capability failure; this is a process failure, and it's the specific failure mode this curriculum's product-thinking and metrics modules are built to prevent (a shipped feature with no defined outcome metric, never re-checked post-launch).
- **73% of failed AI projects had no agreed definition of success before the project started.** This is the single most correctable input in the entire dataset: projects with quantified success metrics defined upfront achieve roughly a **54% success rate**, versus roughly **12% for those without** — a 4-5x difference attributable to one specific, cheap, entirely process-level practice (exactly the reframe-into-an-outcome discipline from the product-thinking module, applied specifically to AI projects where it matters even more because the technology's actual capability is harder to intuit than a traditional feature's).
- **57% of organizations that experienced AI failure attributed it to expecting too much, too fast** — teams assumed AI would immediately automate complex tasks without the necessary data foundation or change management, a scoping and expectations failure more than a technology failure.
- At the extreme end, AI "wrapper" **startups show roughly 80% failure rates**, with 60-70% generating zero revenue at any point — directly connecting back to the strategy module's point that a thin wrapper around a foundation model, with no process power, switching costs, or genuine differentiation, is not a durable business, and the market is bearing this out empirically.

**The mechanical takeaway, stated plainly:** the dominant cause of AI project failure in this data is not "the model wasn't good enough" — it's "nobody defined what success meant before building, and nobody checked after shipping." Every practice covered earlier in this track (reframing a request into an outcome, defining a North Star with guardrails, running a real experiment rather than trusting a vibe) is the direct, specific antidote to the two largest named causes of AI project failure in the current data. A Principal engineer who can cite these numbers and connect them explicitly to "this is why I insist on a defined success metric before we start building" is making a scoped, evidence-backed argument, not a generic plea for process.

---

## Build it from scratch

No code lab; the artifact worth producing is a pricing-model decision memo and a pre-launch success-criteria checklist, in the shape that would actually get used.

```text
# untested sketch — pricing model selection worksheet for an AI feature

CANDIDATE PRICING MODELS for [feature]:
  per-seat:      value scales with headcount? [Y/N] -- if N, per-seat likely
                 misaligns incentive (rewards under-delivery)
  usage-based:   is usage a reasonable proxy for value delivered, or can
                 low-quality output inflate usage (retries, longer sessions
                 needed to get a correct answer)? [assess before committing]
  outcome-based: can "outcome" be defined unambiguously and verified without
                 ongoing dispute? [write the exact definition -- if you can't
                 write a hard, auditable definition, outcome pricing isn't
                 ready yet for this feature]
  hybrid:        base fee for predictability + variable component for
                 incentive alignment -- default recommendation absent a
                 strong reason to pick a pure model

RECOMMENDATION: [model], because [value-scaling rationale], with
  [specific verification mechanism if outcome-based, e.g. reopened-ticket
   clawback within N days]
```

```text
# untested sketch — pre-launch AI feature success-criteria gate,
# directly targeting the two largest named causes of AI project failure

Before this project is approved for engineering investment:
  [ ] Quantified success metric defined (a number, not an adjective --
      see T25-product-thinking's reframe discipline)
  [ ] Baseline/current-state number captured (or explicitly flagged as
      "not measured" -- see T25-product-thinking)
  [ ] Owner assigned to check this metric POST-LAUNCH, with a calendar
      date set now, not "eventually"
  [ ] Guardrail metrics identified (see T25-metrics) specific to AI risk:
      escalation/error rate, cost per request (see T25-unit-economics),
      user-reported dissatisfaction

Without all four checked, this is a pilot, not an approved project --
label it that way explicitly rather than letting it proceed as if
success criteria exist when they don't.
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| An AI feature's revenue doesn't grow even as usage/adoption grows | Priced per-seat while usage varies 20x within a tier — seat count isn't tracking value delivered | Move to hybrid (base + usage or outcome component) so revenue tracks actual consumption/value |
| A poorly-performing AI assistant generates more usage-based revenue than a well-performing one | Usage isn't a value proxy — retries and longer sessions from a worse assistant inflate the bill | Pair usage pricing with a quality/outcome check, or move the variable component to outcome-based where feasible |
| Outcome-based pricing dispute: customer contests whether an "outcome" actually happened | Outcome definition was vague or unverifiable at contract time | Write a hard, auditable outcome definition (with clawback/reopened-item mechanisms) before signing, not after the first dispute |
| AI project shipped, nobody can say six months later whether it delivered value | No success metric defined before building, no owner assigned to check post-launch (matches the 61%/73% failure-cause data directly) | Require the four-item success-criteria gate before approval; assign a calendar date for a post-launch check at kickoff |
| AI feature killed after one quarter for "not delivering value" | Expectations were scoped too aggressively relative to the data foundation and change management actually in place (the 57% "expected too much too fast" cause) | Scope the pilot to a narrower, well-instrumented use case first; expand only after the metric confirms value at the smaller scope |

---

## Tradeoffs & when NOT to use it

- **Don't default to outcome-based pricing when you can't write an unambiguous, auditable outcome definition.** A vague outcome definition is worse than usage-based pricing, because it creates billing disputes and (per the metrics module's Goodhart logic) a direct financial incentive to game the definition rather than deliver real value.
- **Don't force pure usage-based pricing on an enterprise buyer who needs budget predictability.** Enterprise procurement processes are often structurally incompatible with unpredictable variable bills; a base-fee-plus-capped-usage hybrid is frequently the only structure that clears procurement at all, regardless of which model is theoretically most aligned.
- **Per-seat pricing is still the right call when value genuinely does scale with headcount** — a collaboration tool, a tool augmenting (not replacing) human work where more humans using it well genuinely creates more value — don't reflexively abandon per-seat for every AI-adjacent feature; the inversion argument applies specifically to features that substitute for human labor, not every AI-touched product.
- **Don't build a full success-criteria and metrics program for a genuinely small, low-risk AI pilot.** The four-item gate is proportionate for anything requesting real engineering investment; a two-person, one-week spike doesn't need the same ceremony — but even a spike should have a one-line stated hypothesis and a way to know if it worked.
- **The AI failure-rate statistics are aggregate and should be interpreted with real nuance, not used as a blanket argument against building anything.** A 95% no-measurable-return figure for generic enterprise genAI pilots is not the same population as a well-scoped, metric-defined feature at a company with strong data foundations — cite the data to argue for rigor, not to argue against building AI features at all.

---

## Interview questions

### Q1 — Why does per-seat pricing specifically break down for AI agents, in a way it didn't for traditional SaaS?
**Answer:** Per-seat pricing assumes value scales with headcount. Traditional SaaS tools generally do need more seats as a team grows. An AI agent that automates work a human used to do has the opposite relationship — the better it performs, the fewer human seats the customer needs — so a vendor pricing per seat is financially rewarded when their own product under-delivers, since the customer keeps (and pays for) more human seats precisely because the AI isn't good enough to replace the work.
**Follow-up trap:** *"Is per-seat pricing ever still right for an AI feature?"* — yes, when the AI augments rather than substitutes for human work (a coding assistant genuinely used by more engineers as a team grows is closer to the traditional per-seat value curve) — the inversion argument applies specifically to substitution-style agents, not every AI-adjacent product.

### Q2 — Design an outcome-based pricing structure for an AI customer-support agent, and name its biggest design risk.
**Answer:** Charge per resolved ticket, with "resolved" defined hard and auditably — e.g., customer confirmation of resolution, or the ticket staying closed without reopening for a defined window (e.g., 7 days), with a clawback/credit if it reopens. The biggest design risk is Goodhart's Law applied at the pricing layer: a loosely-defined "resolved" status creates a direct financial incentive (for the vendor, or for the AI system itself if optimizing against this metric) to mark tickets resolved that aren't, which is more dangerous than an internal KPI being gamed because it's baked into the commercial contract.
**Follow-up trap:** *"How would you catch this gaming if it started happening?"* — monitor reopened-ticket rate and post-resolution customer-reported dissatisfaction as guardrail metrics specifically on the outcome-billing pipeline, the same guardrail discipline from the metrics module applied to a pricing mechanism instead of an internal target.

### Q3 — Why has hybrid pricing (base fee plus usage or outcome component) become the majority pattern for AI products, rather than a pure model winning out?
**Answer:** Pure usage-based pricing produces unpredictable bills that enterprise procurement is often structurally uncomfortable with; pure outcome-based pricing requires a verifiable outcome definition many AI use cases don't yet have, and pushes all demand-volatility risk onto the vendor's revenue, which most vendors can't sustain alone at scale. A base fee covers platform access and predictability for both sides; the variable component captures the incentive-alignment benefit without concentrating all the risk on one party — Stripe's own analysis found hybrid pricing associated with meaningfully higher median growth than either pure model.
**Follow-up trap:** *"A stakeholder wants pure usage-based pricing for simplicity. How do you respond?"* — name the specific procurement and revenue-volatility costs of going pure usage-based rather than just preferring hybrid on principle, and offer the concrete alternative (a base fee with a usage cap or overage) that preserves most of the simplicity while avoiding the predictability problem.

### Q4 — Cite the AI project failure-rate data and explain what it actually attributes failure to.
**Answer:** 60-90% of AI projects are at risk of failure (roughly double the rate of regular IT projects); 95% of organizations see no measurable P&L return from generative AI pilots (MIT Sloan, 2025); 61% of enterprise AI projects were approved on projected ROI never actually measured post-launch; 73% of failed AI projects had no agreed success definition before starting, and projects that did define one upfront saw roughly 54% success versus 12% for those that didn't. The data attributes failure overwhelmingly to process failures — no defined success criteria, no post-launch measurement — not primarily to model capability failures.
**Follow-up trap:** *"Doesn't a 95% no-measurable-return figure mean AI just doesn't deliver value?"* — no — it's measuring organizations that, per the same research, mostly never defined what value they were measuring for in the first place; the 54% vs. 12% success-rate gap based purely on whether success criteria were defined upfront is the more informative number, and it argues for rigor, not for abandoning AI investment.

### Q5 — A PM says "we don't need a formal success metric, we'll know if it's working." How do you respond, grounded in the failure-rate data?
**Answer:** Point to the specific, quantified gap: projects with defined success metrics upfront succeed at roughly 4-5x the rate of those without (54% vs. 12%), and 73% of failed AI projects specifically lacked an agreed success definition before starting — "we'll know if it's working" is exactly the pattern behind 61% of projects being approved on a projected ROI that was never actually checked after launch. This isn't a generic process preference, it's the single most correctable, cheapest input in the whole dataset.
**Follow-up trap:** *"What if defining a metric upfront feels premature because we don't know enough about the problem yet?"* — that's a legitimate concern for early discovery-stage work (see the discovery module), but it's an argument for running a smaller, cheaper validation step first, not for skipping metric definition once real engineering investment is being requested — the gate applies at the point of committing resources, not at the point of first exploring an idea.

### Q6 — Why is usage-based pricing not fully aligned with value delivered, even though it's the current default?
**Answer:** Usage is a proxy for consumption, not for whether the consumption produced value — a poorly-performing AI assistant that needs five retries to get a correct answer generates five times the usage-based revenue of one that answers correctly the first time, despite delivering less value. This structural gap is part of why the industry has pushed further toward outcome-based pricing specifically for AI products, where the usage-vs-value gap is unusually visible and costly compared to traditional SaaS usage metering (API calls for a well-defined, deterministic operation don't have this ambiguity the way AI-quality-dependent usage does).
**Follow-up trap:** *"How would you detect this misalignment happening on your own product?"* — monitor retries-per-successful-outcome or sessions-per-resolved-task as a guardrail alongside usage-based revenue — a rising ratio is the signature of usage growing for the wrong reason (worse quality generating more billable usage), the same pattern as a Goodhart-gamed metric, just showing up in revenue instead of an internal KPI.

### Q7 — How would you price a new AI feature that's genuinely novel, with no comparable outcome definition or usage benchmark yet?
**Answer:** Start with a base platform fee (or a time-limited pilot at reduced/no cost) to gather real usage and quality data before committing to a variable pricing structure, rather than guessing at an outcome definition or usage rate you can't yet validate — this mirrors the discovery module's assumption-testing discipline applied to pricing: don't commit to an expensive, hard-to-reverse pricing structure before you have evidence for what "value" and "outcome" actually look like for this specific feature.
**Follow-up trap:** *"Sales wants a price today to close a deal. How do you handle the tension?"* — offer a structured pilot period with a pre-committed transition to a validated pricing model at a stated date, rather than either delaying the deal indefinitely or locking in a permanent pricing structure based on guesses — name the tradeoff explicitly to sales rather than absorbing the pressure silently.

### Q8 — What's the connection between the strategy module's point about AI wrappers lacking a moat, and the observed ~80% failure rate of AI wrapper startups?
**Answer:** A thin wrapper around a foundation model has no process power (the visible product is trivial to copy), no meaningful switching costs, and usually no cornered resource — exactly the "not a moat" case from the strategy module — and the empirical failure rate (roughly 80% of AI wrapper startups fail, 60-70% generate zero revenue) is the market outcome of that lack of defensibility playing out at scale: a fast-follower or the foundation-model provider itself can replicate the visible value proposition faster than the wrapper company can build a durable position.
**Follow-up trap:** *"Does this mean building a thin AI wrapper is never a reasonable strategy?"* — it can be a reasonable *speed-to-market* strategy if the plan is explicitly to use the early traction to build a real moat (process power, data, switching costs) before a fast-follower catches up — the failure mode is treating the wrapper itself as the durable business, not using it as a starting position.

### Q9 — How do you design guardrails specifically for outcome-based AI pricing, distinct from the guardrails you'd use for a normal product metric?
**Answer:** The guardrails need to catch gaming that's now financially incentivized by the contract itself, not just organizationally incentivized by an internal KPI — reopened-ticket/item rate (catches a false "resolved" mark), customer-reported dissatisfaction specifically on outcome-billed interactions, and an audit sample of a subset of billed outcomes reviewed manually against the actual conversation/transcript, since the financial stakes of gaming an outcome-billing metric are typically higher than gaming an internal dashboard metric.
**Follow-up trap:** *"Who should own monitoring these guardrails — the vendor or the customer?"* — ideally both, with the customer having audit rights written into the contract (spot-check access to a sample of billed outcomes), because a vendor self-policing its own outcome-billing metric has the exact conflict of interest this pricing model was supposed to solve in the first place — the guardrail needs independence from the party being paid based on it.

### Q10 — You're pitching an AI feature. Using this module and the earlier ones in the track, what does your pitch include to maximize the odds it's in the 54% success group, not the 12%?
**Testing:** synthesis across the whole track.
**Answer:** A reframed problem/outcome statement (T25-product-thinking), evidenced by real discovery data (T25-discovery), a quantified success metric with guardrails (T25-metrics), a plan for how the launch decision will actually be validated — a real experiment, not a vibe (T25-experimentation), a fully-loaded unit-economics model including human review and eval cost, not just token cost (T25-unit-economics), a pricing model chosen deliberately for incentive alignment given whether the feature substitutes for or augments human work (this module), and a named owner with a calendar date to check the metric post-launch — directly targeting the single most-cited cause of AI project failure in the data.
**Follow-up trap:** *"Which of these would you cut if you had to ship in two weeks?"* — never the success metric and the post-launch check-date — those are cheap (a sentence and a calendar invite) and are the two specific items the failure-rate data identifies as most predictive; the unit-economics model and the discovery evidence can be lighter-weight/back-of-envelope under real time pressure, but should never be entirely absent.

---

## Red flags that fail you

- Recommending per-seat pricing for an AI feature that substitutes for human labor, without naming the incentive inversion.
- Proposing outcome-based pricing with no concrete, auditable definition of "outcome."
- Citing the AI failure-rate statistics as evidence that AI features are inherently unreliable, rather than evidence of a process failure (no defined success metric, no post-launch check).
- No mention of guardrails against gaming when designing an outcome-based pricing structure — missing the Goodhart's Law connection.
- Treating usage-based pricing as automatically value-aligned, with no acknowledgment that usage can be inflated by lower quality (more retries).
- Pitching an AI feature with no stated success metric and no named owner to check it post-launch.

---

## Cheat card

```
PER-SEAT        assumes value scales with headcount -- INVERTS for AI agents
                that substitute human labor (better AI = fewer seats needed =
                vendor rewarded for under-delivering). Share fell 21%->15% YoY.
                Still right when AI augments (not substitutes) human work.

USAGE-BASED     default starting point (~30% of SaaS in 2019 -> ~85% by 2026).
                gap: usage != value -- a worse assistant needing 5 retries
                generates 5x the revenue of a better one for less value

OUTCOME-BASED   becoming dominant for AI AGENTS specifically (Agentforce: per
                conversation; Intercom Fin: per resolved ticket) -- vendor only
                paid when the AI actually delivers. HARDEST PART: writing an
                unambiguous, auditable "outcome" definition -- vague def =
                Goodhart risk baked into the CONTRACT itself (gameable billing)
                mitigate: reopened-item clawback, customer confirmation,
                independent audit sample

HYBRID          base fee + usage/outcome component -- MAJORITY real pattern.
                base = predictability for procurement; variable = incentive
                alignment. Stripe data: hybrid > pure subscription or pure
                usage on median growth. 43% buyers prefer usage, 27% outcome
                (2026 survey) -- seat-only vendors increasingly disqualified
                pre-demo

AI FAILURE DATA 60-90% of AI projects at risk of failure (~2x normal IT
                project rate). 95% of orgs: no measurable P&L return from
                genAI pilots (MIT Sloan 2025); only ~5% capture value at scale
                61% approved on projected ROI NEVER measured post-launch
                73% of FAILED projects had NO agreed success definition upfront
                DEFINED metric upfront -> 54% success rate vs 12% without
                (4-5x) -- single most correctable, cheapest fix in the data
                57% of failures: "expected too much too fast" (scoping error)
                AI wrapper startups: ~80% fail, 60-70% zero revenue ever
                  (connects to strategy module: no moat = no durable business)
```

## Sources

- [AI Product Pricing Strategy in 2026 — Value Add VC](https://valueaddvc.com/blog/pricing-strategy-for-ai-products-seat-based-usage-based-or-value-based) — accessed 2026-08-08
- [7 AI Pricing Models: What Works, What Breaks — Lago](https://getlago.com/blog/ai-pricing-models) — accessed 2026-08-08
- [Why AI Companies Have Adopted Usage Based Pricing in 2026 — Flexprice](https://flexprice.io/blog/why-ai-companies-have-adopted-usage-based-pricing) — accessed 2026-08-08
- [Report: 80% of AI Projects Fail Overall, With 84% of Failures Caused by Leadership — Labor411](https://labor411.org/411-blog/report-80-of-ai-projects-fail-overall-with-84-of-the-failures-caused-by-leadership/) — accessed 2026-08-08
- [AI Project Failure Statistics 2026: Why 85% of Enterprise Initiatives Stall — Syntes.ai](https://syntes.ai/ai-project-failure-statistics-2026-why-85-of-enterprise-initiatives-stall/) — accessed 2026-08-08
- [Startup Strategy in the AI Era: Why 80% of Wrappers Die — Value Add VC](https://valueaddvc.com/blog/how-to-build-a-startup-in-a-market-where-ai-will-eventually-do-what-you-do) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
